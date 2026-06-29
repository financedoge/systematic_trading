param(
    [string]$ComposeFile = "deploy\clickhouse\docker-compose.yml"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$ResolvedComposeFile = Resolve-Path (Join-Path $RepoRoot $ComposeFile)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Install Docker Desktop or run this on a server with Docker."
}

$LogRoot = if ($env:ST_CLICKHOUSE_LOG_ROOT) { $env:ST_CLICKHOUSE_LOG_ROOT } else { "D:/systematic_trading_data/clickhouse/logs" }

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$env:ST_CLICKHOUSE_LOG_ROOT = $LogRoot

Push-Location $RepoRoot
try {
    docker compose -f $ResolvedComposeFile up -d
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed with exit code $LASTEXITCODE"
    }
    Write-Output "ClickHouse requested via Docker Compose."
    Write-Output "HTTP URL: http://127.0.0.1:8123"
    Write-Output "Native client: 127.0.0.1:9000"
    Write-Output "Data volume: clickhouse_data"
    Write-Output "Log root: $LogRoot"
} finally {
    Pop-Location
}
