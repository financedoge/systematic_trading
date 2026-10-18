param()
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Policy = Get-Content -LiteralPath (Join-Path $RepoRoot 'config\storage-retention.json') -Raw | ConvertFrom-Json
if (-not $Policy.startup_retention) { return }
$BackupLockPath = Join-Path $RepoRoot 'var\system-backup\capture.lock'
if (Test-Path -LiteralPath $BackupLockPath) {
    try {
        $BackupProbe = [IO.File]::Open($BackupLockPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        $BackupProbe.Dispose()
    } catch [IO.IOException] {
        Write-Output 'Research retention deferred while a backup capture/upload is active.'
        return
    }
}
# Startup performs bounded automatic maintenance only while all application
# writers are stopped. A successful publication queues maintenance for this
# boundary; it never races a running recorder or broker workflow.
if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    Write-Output 'Research retention deferred until the next stopped startup.'
    return
}
foreach ($PidName in @('operator_dashboard','event_outbox_dispatcher','market_data_recorder','system_backup','database_sync')) {
    $PidPath = Join-Path $RepoRoot "var\run\$PidName.pid"
    if (Test-Path -LiteralPath $PidPath) {
        $ServiceProcessId = [int](Get-Content -LiteralPath $PidPath -Raw).Trim()
        if (Get-Process -Id $ServiceProcessId -ErrorAction SilentlyContinue) {
            Write-Output "Research retention deferred while $PidName is running."
            return
        }
    }
}
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
foreach ($Scope in @('tracked','models')) {
    $Manifest = Join-Path $RepoRoot ('var\maintenance\startup-' + $Scope + '-' + [Guid]::NewGuid().ToString('N') + '.json')
    & $Python (Join-Path $PSScriptRoot 'retire_research_artifacts.py') plan --scope $Scope --manifest $Manifest
    if ($LASTEXITCODE -ne 0) { throw 'Could not establish safe retention protection set.' }
    & (Join-Path $PSScriptRoot 'apply_research_retention.ps1') -Manifest $Manifest
    if ($LASTEXITCODE -ne 0) { throw 'Guarded research retention did not complete.' }
}
$Pending = Join-Path $RepoRoot 'var\run\research-retention.pending.json'
if (Test-Path -LiteralPath $Pending) { Remove-Item -LiteralPath $Pending }
