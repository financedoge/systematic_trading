param(
    [switch]$Force,
    [switch]$KeepInfrastructure
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $ScriptDir "..\.venv\Scripts\python.exe") (Join-Path $ScriptDir "local_recovery.py") stop
if ($LASTEXITCODE -ne 0) { throw "Recovery worker did not stop; refusing to race automatic startup." }

& (Join-Path $ScriptDir "stop_market_data_recorder.ps1") -Force:$Force
& (Join-Path $ScriptDir "stop_operator_dashboard.ps1") -Force:$Force

$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $Python (Join-Path $ScriptDir "sync_databases.py") stop-worker
if ($LASTEXITCODE -ne 0) { throw "Local backup worker did not stop; inspect its process before shutting down database infrastructure." }
& $Python (Join-Path $ScriptDir "sync_databases.py") release
if ($LASTEXITCODE -ne 0) { throw "Database shutdown checkpoint failed; inspect local restore state and backup logs." }

if ($KeepInfrastructure) {
    Write-Output "Keeping NATS JetStream, ClickHouse, and external Postgres running."
    exit 0
}

& (Join-Path $ScriptDir "stop_clickhouse.ps1")
& (Join-Path $ScriptDir "stop_nats_jetstream.ps1")
Write-Output "Local platform stopped. External Postgres was not stopped."
