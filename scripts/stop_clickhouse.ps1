param(
    [string]$ComposeFile = "deploy\clickhouse\docker-compose.yml"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
& (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $ScriptDir "local_recovery.py") pause clickhouse
if ($LASTEXITCODE -ne 0) { throw "Could not pause ClickHouse recovery before stopping." }
$ResolvedComposeFile = Resolve-Path (Join-Path $RepoRoot $ComposeFile)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Install Docker Desktop or run this on a server with Docker."
}

Push-Location $RepoRoot
try {
    docker compose -f $ResolvedComposeFile down
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose down failed with exit code $LASTEXITCODE"
    }
    Write-Output "ClickHouse Docker Compose stack stopped."
} finally {
    Pop-Location
}
