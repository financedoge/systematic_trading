# Run from an elevated PowerShell. Retains the original directory for rollback.
[CmdletBinding()]
param(
    [string]$ServiceName = "postgresql-x64-18",
    [string]$Source = "C:\Program Files\PostgreSQL\18\data",
    [string]$Destination = "D:\systematic_trading_data\postgresql\18\data"
)
$ErrorActionPreference = "Stop"

function Set-PostgresServiceCommand {
    param([string]$Name, [string]$Command)
    # Structured CIM arguments preserve nested quotes in both Windows PowerShell
    # 5.1 and PowerShell 7; sc.exe argument serialization does not.
    $currentService = Get-CimInstance -ClassName Win32_Service | Where-Object Name -EQ $Name
    if (-not $currentService) { throw "PostgreSQL service not found: $Name" }
    $result = Invoke-CimMethod -InputObject $currentService -MethodName Change -Arguments @{ PathName = $Command }
    if ($result.ReturnValue -ne 0) {
        throw "Service reconfiguration failed (Win32_Service.Change code $($result.ReturnValue))."
    }
    $updatedService = Get-CimInstance -ClassName Win32_Service | Where-Object Name -EQ $Name
    if ($updatedService.PathName -cne $Command) { throw "Service command readback did not match the requested command." }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator access is required to stop and reconfigure the PostgreSQL Windows service."
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
# SMB sessions can differ between normal and elevated Windows logons. Check from
# this exact process before interrupting any application service.
& $python (Join-Path $PSScriptRoot 'sync_databases.py') preflight
if ($LASTEXITCODE -ne 0) {
    throw 'NAS preflight failed; no services were stopped. Connect to \\192.168.1.32\Public from this same Administrator PowerShell and retry. Do not disable NAS sync or remove ownership records.'
}
$sourcePath = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
$targetPath = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
if (-not $targetPath.StartsWith('D:\systematic_trading_data\postgresql\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must be a child of D:\systematic_trading_data\postgresql."
}
if ($sourcePath -eq $targetPath -or (Test-Path -LiteralPath $targetPath)) {
    throw "Destination must not exist; inspect any prior attempt before retrying."
}
$service = Get-CimInstance Win32_Service | Where-Object Name -EQ $ServiceName
if (-not $service -or -not $service.PathName.Contains('"' + $sourcePath + '"')) {
    throw "Service command does not contain the expected quoted source directory."
}
$oldCommand = $service.PathName
$newCommand = $oldCommand.Replace('"' + $sourcePath + '"', '"' + $targetPath + '"')
# Fail before downtime for configurations this bounded relocation cannot safely handle.
$conf = Join-Path $sourcePath "postgresql.conf"
if (Select-String -LiteralPath $conf -Pattern '^\s*(data_directory|hba_file|ident_file|include|include_dir|include_if_exists)\s*=' -Quiet) {
    throw "External configuration paths require a separately reviewed relocation."
}
if (Select-String -LiteralPath (Join-Path $sourcePath 'postgresql.auto.conf') -Pattern '^\s*data_directory\s*=' -Quiet) {
    throw "postgresql.auto.conf overrides data_directory; review before relocation."
}
if (Get-ChildItem -LiteralPath $sourcePath -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
    throw "External tablespace, WAL or other reparse points require explicit relocation."
}
$sourceBytes = (Get-ChildItem -LiteralPath $sourcePath -Recurse -File -Force | Measure-Object Length -Sum).Sum
if ((Get-PSDrive D).Free -lt ($sourceBytes * 2 + 1GB)) { throw "Insufficient D: free space." }
# This performs the normal final snapshot and NAS ownership release, preserving guards.
& (Join-Path $PSScriptRoot 'stop_local_platform.ps1') -KeepInfrastructure
if ($LASTEXITCODE -ne 0) { throw "Clean platform stop failed." }
$state = Get-Content -LiteralPath (Join-Path $repo 'var\database-sync\state.json') -Raw | ConvertFrom-Json
if ($state.phase -ne 'clean') { throw "A clean NAS handoff is required before relocating." }
$changed = $false
try {
    Stop-Service -Name $ServiceName
    (Get-Service -Name $ServiceName).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
    if (Test-Path -LiteralPath (Join-Path $sourcePath 'postmaster.pid')) { throw "PostgreSQL did not shut down cleanly." }
    New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
    # Copy with original ACLs; never /MIR, /MOVE or delete the source.
    & robocopy.exe $sourcePath $targetPath /E /COPYALL /DCOPY:DAT /R:1 /W:1 /XJ /NFL /NDL /NP
    if ($LASTEXITCODE -ge 8) { throw "PostgreSQL directory copy failed." }
    $verified = 0
    foreach ($item in Get-ChildItem -LiteralPath $sourcePath -Recurse -File -Force) {
        $relative = $item.FullName.Substring($sourcePath.Length + 1)
        $copy = Join-Path $targetPath $relative
        if (-not (Test-Path -LiteralPath $copy) -or
            (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash) {
            throw "Copy hash mismatch: $relative"
        }
        $verified++
    }
    # A failure after the API accepted the change still needs rollback.
    $changed = $true
    Set-PostgresServiceCommand -Name $ServiceName -Command $newCommand
    Start-Service -Name $ServiceName
    (Get-Service -Name $ServiceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(60))
    $pidFile = Get-Content -LiteralPath (Join-Path $targetPath 'postmaster.pid')
    if ([IO.Path]::GetFullPath($pidFile[1]).TrimEnd('\') -ne $targetPath) { throw "Server did not select the new data directory." }
    $process = Get-Process -Id ([int]$pidFile[0]) -ErrorAction Stop
    if ($process.ProcessName -ne 'postgres') { throw "Unexpected database process." }
    $evidence = [ordered]@{ service=$ServiceName; source=$sourcePath; destination=$targetPath; verified_files=$verified; at=(Get-Date).ToUniversalTime().ToString('o') }
    $evidence | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $repo 'var\migration\postgres-relocation.json') -Encoding utf8
} catch {
    $failure = $_
    if ($changed) {
        Stop-Service -Name $ServiceName -ErrorAction Stop
        Set-PostgresServiceCommand -Name $ServiceName -Command $oldCommand
    }
    Start-Service -Name $ServiceName -ErrorAction Continue
    throw $failure
}
# The standard startup verifies fingerprints and reacquires NAS ownership.
& (Join-Path $PSScriptRoot 'start_local_platform.ps1')
if ($LASTEXITCODE -ne 0) { throw "Postgres moved; platform startup failed. Inspect health; do not revert an active ledger." }
Write-Output "PostgreSQL is using $targetPath. Original copy retained at $sourcePath; do not reuse it after new writes."
