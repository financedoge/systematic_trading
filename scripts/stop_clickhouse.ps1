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
