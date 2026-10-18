param([Parameter(Mandatory=$true)][string]$Manifest)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Cli = Join-Path $PSScriptRoot 'retire_research_artifacts.py'
$AllowedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'var\tracked_strategies'))
$ManifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$Plan = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Plan.scope -eq 'closed_studies') { $AllowedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'var\research')) }
if ($Plan.scope -eq 'governance') { $AllowedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'var\governance')) }
if ($Plan.scope -eq 'models') { $AllowedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'var\tracked_models')) }
if ($Plan.allowed_root -ne $AllowedRoot) { throw 'Unexpected retirement root.' }
$LockPath = Join-Path $RepoRoot 'var\run\research-retention.lock'
$Lock = [IO.File]::Open($LockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
try {
    $Lock.Lock(0, 1)
    $BackupLockPath = Join-Path $RepoRoot 'var\system-backup\capture.lock'
    if (Test-Path -LiteralPath $BackupLockPath) {
        $BackupProbe = [IO.File]::Open($BackupLockPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        $BackupProbe.Dispose()
    }
    # Old application versions do not acquire this lock. The initial CLI is an
    # offline maintenance operation, including after upgrades.
    foreach ($PidName in @('operator_dashboard', 'event_outbox_dispatcher', 'market_data_recorder', 'system_backup', 'database_sync')) {
        $PidPath = Join-Path $RepoRoot "var\run\$PidName.pid"
        if (Test-Path -LiteralPath $PidPath) {
            $ServiceProcessId = [int](Get-Content -LiteralPath $PidPath -Raw).Trim()
            if (Get-Process -Id $ServiceProcessId -ErrorAction SilentlyContinue) { throw "Stop $PidName before applying retirement." }
        }
    }
    if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) { throw 'Stop the operator API before retirement.' }
    & $Python $Cli verify --manifest $ManifestPath
    if ($LASTEXITCODE -ne 0) { throw 'Manifest protection or inventory verification failed.' }
    foreach ($Candidate in $Plan.candidates) {
        $Target = (Resolve-Path -LiteralPath $Candidate.path).Path
        $IsTracked = $Plan.scope -ne 'closed_studies' -and [IO.Path]::GetDirectoryName($Target) -eq $AllowedRoot -and [IO.Path]::GetFileName($Target) -match '^[a-f0-9]{64}$'
        $IsClosedStudy = $Plan.scope -eq 'closed_studies' -and [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($Target)) -eq $AllowedRoot
        $IsGovernance = $Plan.scope -eq 'governance' -and [IO.Path]::GetDirectoryName($Target) -eq $AllowedRoot -and [IO.Path]::GetFileName($Target) -match '^(listed|research)-\d{4}-\d{2}-\d{2}-[a-f0-9]{12}$'
        if (-not ($IsTracked -or $IsClosedStudy -or $IsGovernance)) {
            throw 'Target is outside the permitted tracked revision directory.'
        }
        if ((Get-Item -LiteralPath $Target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse target rejected.' }
        & $Python $Cli intent --manifest $ManifestPath --target $Target
        if ($LASTEXITCODE -ne 0) { throw 'Could not persist retirement intent.' }
        Remove-Item -LiteralPath $Target -Recurse -Force
        & $Python $Cli record --manifest $ManifestPath --target $Target
        if ($LASTEXITCODE -ne 0) { throw 'Could not record retirement outcome.' }
        Write-Output "Retired $Target"
    }
} finally {
    $Lock.Dispose()
}
