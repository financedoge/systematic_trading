param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
& (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $ScriptDir "local_recovery.py") pause recorder
if ($LASTEXITCODE -ne 0) { throw "Could not pause recorder recovery before stopping." }
$PidPath = Join-Path $RepoRoot "var\run\market_data_recorder.pid"
$ChildPidPath = Join-Path $RepoRoot "var\run\market_data_recorder.child.pid"
$StatePath = Join-Path $RepoRoot "var\run\market_data_recorder.state.json"
$OperationLogPath = Join-Path $RepoRoot "var\log\platform_operations.jsonl"
$ServiceProcessLibrary = Join-Path $ScriptDir "service_process.ps1"
if (-not (Test-Path $ServiceProcessLibrary)) {
    throw "Process identity helper not found at $ServiceProcessLibrary"
}
. $ServiceProcessLibrary

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

function Stop-RecorderChild {
    $recoveryPidPath = Join-Path $RepoRoot "var\run\market_data_recorder.recovery.pid"
    if (Test-Path $recoveryPidPath) {
        $recoveryPidText = (Get-Content -LiteralPath $recoveryPidPath -Raw).Trim()
        if ($recoveryPidText) {
            $recoveryProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $recoveryPidText" -ErrorAction SilentlyContinue
            if ($recoveryProcess -and $recoveryProcess.CommandLine -like "*recover_ib_intraday.py*") {
                Stop-Process -Id ([int]$recoveryPidText) -Force -ErrorAction Stop
            }
        }
        Remove-Item -LiteralPath $recoveryPidPath -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $ChildPidPath)) {
        return
    }
    $childPidText = (Get-Content -LiteralPath $ChildPidPath -Raw).Trim()
    $childPid = 0
    if ($childPidText -and [int]::TryParse($childPidText, [ref]$childPid)) {
        # The capture child is a distinct Python script; a recycled PID that now
        # belongs to another program (or another Python entry point) is not ours.
        $childState = Get-ServiceProcessState -ProcessId $childPid -ExpectedScript "record_ib_market_data.py"
        if ($childState.Exists -and $childState.Matches -eq $true) {
            Stop-Process -Id $childPid -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 200
        } elseif ($childState.Exists -and $null -eq $childState.Matches) {
            Add-OperationLog `
                -Event "recorder_child_unverified" `
                -Level "warning" `
                -Message "Capture child PID could not be verified; leaving the process and PID file untouched." `
                -Details @{ pid = $childPidText }
            return
        }
    }
    Remove-Item -LiteralPath $ChildPidPath -Force -ErrorAction SilentlyContinue
    Add-OperationLog `
        -Event "recorder_child_stopped" `
        -Message "Market data recorder child stopped during supervisor shutdown." `
        -Details @{ pid = $childPidText }
}

if (-not (Test-Path $PidPath)) {
    Stop-RecorderChild
    Write-StoppedState -Message "Market data recorder is stopped; no PID file was present."
    Add-OperationLog -Event "recorder_stop_no_pid" -Message "No market data recorder PID file found."
    Write-Output "No market data recorder PID file found."
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
if (-not $pidText) {
    Stop-RecorderChild
    Remove-Item -LiteralPath $PidPath -Force
    Write-StoppedState -Message "Market data recorder is stopped; empty PID file was removed."
    Add-OperationLog -Event "recorder_stop_empty_pid" -Message "Removed empty market data recorder PID file."
    Write-Output "Removed empty market data recorder PID file."
    exit 0
}

$processId = 0
$processState = if ([int]::TryParse($pidText, [ref]$processId)) {
    Get-ServiceProcessState -ProcessId $processId -ExpectedScript "run_market_data_recorder_service.py"
} else {
    [pscustomobject]@{ Exists = $false; Matches = $false; ProcessName = $null; CommandLine = $null }
}

if (-not $processState.Exists) {
    Stop-RecorderChild
    Remove-Item -LiteralPath $PidPath -Force
    Write-StoppedState -Message "Market data recorder is stopped; stale PID file was removed." -PidText $pidText
    Add-OperationLog -Event "recorder_stop_stale_pid" -Message "Market data recorder stale PID file removed." -Details @{ pid = $pidText }
    Write-Output "Market data recorder process $pidText was not running. Removed stale PID file."
    exit 0
}

if ($processState.Matches -eq $false) {
    Stop-RecorderChild
    Remove-Item -LiteralPath $PidPath -Force
    Write-StoppedState -Message "Market data recorder is stopped; the PID file pointed at another process and was removed." -PidText $pidText
    Add-OperationLog `
        -Event "recorder_stop_pid_reused" `
        -Level "warning" `
        -Message "Recorder PID file pointed at another process (recycled PID); removed it without stopping that process." `
        -Details @{ pid = $pidText; process_name = $processState.ProcessName }
    Write-Output "Market data recorder PID $pidText belongs to another process ($($processState.ProcessName)); removed stale PID file without stopping it."
    exit 0
}

if ($null -eq $processState.Matches) {
    throw "Refusing to stop PID ${pidText}: its command line could not be verified as the market data recorder. Inspect the process manually before stopping it."
}

$process = Get-Process -Id $processId -ErrorAction Stop
try {
    Stop-Process -Id $process.Id -Force:$Force -ErrorAction Stop
} catch {
    Stop-Process -Id $process.Id -Force -ErrorAction Stop
}
$process.WaitForExit(5000) | Out-Null

if (-not $process.HasExited) {
    throw "Market data recorder process $pidText did not exit after stop request."
}

Stop-RecorderChild
Remove-Item -LiteralPath $PidPath -Force
Write-StoppedState -Message "Market data recorder stopped by operator." -PidText $pidText
Add-OperationLog -Event "recorder_stopped" -Message "Market data recorder stopped by operator." -Details @{ pid = $pidText; force = [bool]$Force }
Write-Output "Market data recorder stopped."
Write-Output "PID: $pidText"
