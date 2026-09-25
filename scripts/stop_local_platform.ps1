param(
    [switch]$Force,
    [switch]$KeepInfrastructure
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $ScriptDir "stop_market_data_recorder.ps1") -Force:$Force
& (Join-Path $ScriptDir "stop_operator_dashboard.ps1") -Force:$Force

$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $Python (Join-Path $ScriptDir "sync_databases.py") stop-worker
if ($LASTEXITCODE -ne 0) { throw "Database backup worker stop failed; NAS ownership retained." }
& $Python (Join-Path $ScriptDir "sync_databases.py") release
if ($LASTEXITCODE -ne 0) { throw "Final NAS backup failed; NAS ownership retained. Retry before switching PCs." }

if ($KeepInfrastructure) {
    Write-Output "Keeping NATS JetStream, ClickHouse, and external Postgres running."
    exit 0
}

& (Join-Path $ScriptDir "stop_clickhouse.ps1")
& (Join-Path $ScriptDir "stop_nats_jetstream.ps1")
Write-Output "Local platform stopped. External Postgres was not stopped."
