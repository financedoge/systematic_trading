param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PidPath = Join-Path $RepoRoot "var\run\operator_dashboard.pid"
$DispatcherPidPath = Join-Path $RepoRoot "var\run\event_outbox_dispatcher.pid"

function Stop-ProcessFromPidFile {
    param(
        [string]$Name,
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        Write-Output "No $Name PID file found."
        return
    }

    $pidText = (Get-Content -LiteralPath $Path -Raw).Trim()
    if (-not $pidText) {
        Remove-Item -LiteralPath $Path -Force
        Write-Output "Removed empty $Name PID file."
        return
    }

    $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -LiteralPath $Path -Force
        Write-Output "$Name process $pidText was not running. Removed stale PID file."
        return
    }

    try {
        Stop-Process -Id $process.Id -Force:$Force -ErrorAction Stop
    } catch {
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
    }
    $process.WaitForExit(5000) | Out-Null

    if (-not $process.HasExited) {
        throw "$Name process $pidText did not exit after stop request."
    }

    Remove-Item -LiteralPath $Path -Force
    Write-Output "$Name stopped."
    Write-Output "PID: $pidText"
}

Stop-ProcessFromPidFile -Name "Event outbox dispatcher" -Path $DispatcherPidPath
Stop-ProcessFromPidFile -Name "Operator dashboard" -Path $PidPath
