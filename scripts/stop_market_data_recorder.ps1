param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PidPath = Join-Path $RepoRoot "var\run\market_data_recorder.pid"
$StatePath = Join-Path $RepoRoot "var\run\market_data_recorder.state.json"
$OperationLogPath = Join-Path $RepoRoot "var\log\platform_operations.jsonl"

function Write-JsonNoBom {
    param(
        [string]$Path,
        [object]$Payload
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $json = $Payload | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Add-OperationLog {
    param(
        [string]$Event,
        [string]$Level = "info",
        [string]$Message = $null,
        [hashtable]$Details = @{}
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OperationLogPath) | Out-Null
    $payload = [ordered]@{
        schema_version = 1
        occurred_at = (Get-Date).ToUniversalTime().ToString("o")
        service_id = "market_data_recorder"
        level = $Level
        event = $Event
        message = $Message
        details = $Details
    }
    $line = $payload | ConvertTo-Json -Compress -Depth 8
    [System.IO.File]::AppendAllText($OperationLogPath, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Write-StoppedState {
    param(
        [string]$Message,
        [string]$PidText = $null
    )
    Write-JsonNoBom -Path $StatePath -Payload ([ordered]@{
        schema_version = 1
        service_id = "market_data_recorder"
        running = $false
        started_at = $null
        heartbeat_at = (Get-Date).ToUniversalTime().ToString("o")
        last_error = $null
        message = $Message
        details = @{
            stopped_pid = $PidText
        }
    })
}

if (-not (Test-Path $PidPath)) {
    Write-StoppedState -Message "Market data recorder is stopped; no PID file was present."
    Add-OperationLog -Event "recorder_stop_no_pid" -Message "No market data recorder PID file found."
    Write-Output "No market data recorder PID file found."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
if (-not $pidText) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-StoppedState -Message "Market data recorder is stopped; empty PID file was removed."
    Add-OperationLog -Event "recorder_stop_empty_pid" -Message "Removed empty market data recorder PID file."
    Write-Output "Removed empty market data recorder PID file."
    exit 0
}

$process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-StoppedState -Message "Market data recorder is stopped; stale PID file was removed." -PidText $pidText
    Add-OperationLog -Event "recorder_stop_stale_pid" -Message "Market data recorder stale PID file removed." -Details @{ pid = $pidText }
    Write-Output "Market data recorder process $pidText was not running. Removed stale PID file."
    exit 0
}

try {
    Stop-Process -Id $process.Id -Force:$Force -ErrorAction Stop
} catch {
    Stop-Process -Id $process.Id -Force -ErrorAction Stop
}
$process.WaitForExit(5000) | Out-Null

if (-not $process.HasExited) {
    throw "Market data recorder process $pidText did not exit after stop request."
}

Remove-Item -LiteralPath $PidPath -Force
Write-StoppedState -Message "Market data recorder stopped by operator." -PidText $pidText
Add-OperationLog -Event "recorder_stopped" -Message "Market data recorder stopped by operator." -Details @{ pid = $pidText; force = [bool]$Force }
Write-Output "Market data recorder stopped."
Write-Output "PID: $pidText"
