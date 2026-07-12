param(
    [string]$Context = "Docker Compose service startup",
    [switch]$StartDockerDesktopIfStopped,
    [int]$WaitSeconds = 120
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Install Docker Desktop or run this on a server with Docker before $Context."
}

function Test-DockerDaemon {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = docker info 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    return @{
        ok = ($exitCode -eq 0)
        exit_code = $exitCode
        output = [string]::Join([Environment]::NewLine, @($output))
    }
}

$result = Test-DockerDaemon
if ($result.ok) {
    return
}

if ($StartDockerDesktopIfStopped) {
    $dockerDesktopPath = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktopPath) {
        Write-Output "Docker daemon is not reachable for $Context. Starting Docker Desktop and waiting up to $WaitSeconds seconds..."
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden | Out-Null
        $deadline = (Get-Date).AddSeconds($WaitSeconds)
        do {
            Start-Sleep -Seconds 3
            $result = Test-DockerDaemon
            if ($result.ok) {
                Write-Output "Docker daemon is reachable."
                return
            }
        } while ((Get-Date) -lt $deadline)
    }
}

$lastLine = (($result.output -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 1)
throw @"
Docker daemon is not reachable for $Context.
Docker Desktop may be closed, still starting, or its Linux engine may be stopped.
Start Docker Desktop and wait until the engine is running, then retry.
For partial startup without Docker-backed services, use -SkipNats -SkipClickHouse.
Last docker error: $lastLine
"@
