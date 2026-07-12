param(
    [string]$ComposeFile = "deploy\nats\docker-compose.yml"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$ResolvedComposeFile = Resolve-Path (Join-Path $RepoRoot $ComposeFile)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Install Docker Desktop or run this on a server with Docker."
}

& (Join-Path $ScriptDir "assert_docker_ready.ps1") -Context "NATS JetStream startup" -StartDockerDesktopIfStopped

Push-Location $RepoRoot
try {
    docker compose -f $ResolvedComposeFile up -d
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed with exit code $LASTEXITCODE"
    }
    Write-Output "NATS JetStream requested via Docker Compose."
    Write-Output "Client URL: nats://127.0.0.1:4222"
    Write-Output "Monitoring URL: http://127.0.0.1:8222"
} finally {
    Pop-Location
}
