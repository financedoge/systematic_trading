param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PidPath = Join-Path $RepoRoot "var\run\operator_dashboard.pid"

if (-not (Test-Path $PidPath)) {
    Write-Output "No operator dashboard PID file found."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
if (-not $pidText) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-Output "Removed empty operator dashboard PID file."
    exit 0
}

$process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-Output "Operator dashboard process $pidText was not running. Removed stale PID file."
    exit 0
}

try {
    Stop-Process -Id $process.Id -Force:$Force -ErrorAction Stop
} catch {
    Stop-Process -Id $process.Id -Force -ErrorAction Stop
}
$process.WaitForExit(5000) | Out-Null

if (-not $process.HasExited) {
    throw "Operator dashboard process $pidText did not exit after stop request."
}

Remove-Item -LiteralPath $PidPath -Force
Write-Output "Operator dashboard stopped."
Write-Output "PID: $pidText"
