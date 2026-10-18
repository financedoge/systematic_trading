param(
    [string]$Receipt = 'var\maintenance\windows-cutover\docker-retirement.json'
)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Windows VHD compaction requires Administrator PowerShell. This script does not request elevation itself.'
}
$ReceiptPath = [IO.Path]::GetFullPath((Join-Path $RepoRoot $Receipt))
$Evidence = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
if (-not $Evidence.completed -or -not $Evidence.native_restore_verified -or -not $Evidence.native_cold_start_verified -or
    $Evidence.native_backup_snapshot -notmatch '^[a-f0-9]{64}$') {
    throw 'Verified native restore, cold startup, backup and Docker retirement are required before compaction.'
}
if (Get-Process -Name 'Docker Desktop','com.docker.backend' -ErrorAction SilentlyContinue) {
    throw 'Stop Docker Desktop before compacting its retired data disk.'
}
$DiskPath = (Resolve-Path -LiteralPath $Evidence.docker_data_disk).Path
if ([IO.Path]::GetFileName($DiskPath) -ne 'docker_data.vhdx' -or $DiskPath -match '["\r\n]') {
    throw 'The retirement receipt does not identify the expected Docker data disk.'
}
$Disk = Get-Item -LiteralPath $DiskPath
if ($Disk.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse disk path rejected.' }
# Exclusive access confirms that the exact recorded disk is detached. Do not
# stop unrelated WSL distributions or attach/change filesystem contents.
$Handle = [IO.File]::Open($DiskPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$Handle.Dispose()
$Before = $Disk.Length
$OutputRoot = Split-Path -Parent $ReceiptPath
$Instructions = Join-Path $OutputRoot 'compact-retired-docker.diskpart'
$Log = Join-Path $OutputRoot 'compact-retired-docker.log'
@("select vdisk file=`"$DiskPath`"",'compact vdisk','exit') | Set-Content -LiteralPath $Instructions -Encoding ascii
& diskpart.exe /s $Instructions *> $Log
$ExitCode = $LASTEXITCODE
$After = (Get-Item -LiteralPath $DiskPath).Length
$Result = [ordered]@{
    at = (Get-Date).ToUniversalTime().ToString('o')
    disk = $DiskPath
    before_bytes = $Before
    after_bytes = $After
    reclaimed_file_bytes = $Before - $After
    diskpart_exit_code = $ExitCode
    status = $(if ($ExitCode -eq 0 -and $After -lt $Before) { 'shrunk' } else { 'inspect_log' })
    log = $Log
}
$Result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputRoot 'docker-compaction.json') -Encoding utf8
$Result | ConvertTo-Json
if ($ExitCode -ne 0) { throw 'DiskPart failed; inspect the saved log. No success is assumed.' }
