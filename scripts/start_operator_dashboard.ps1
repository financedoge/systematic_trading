param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$DisableEventDispatcher,
    [int]$EventDispatcherIntervalSeconds = 5,
    [ValidateSet("jsonl", "nats")]
    [string]$EventPublisher = "nats",
    [string]$NatsUrl = "nats://127.0.0.1:4222",
    [string]$OperationLogPath = "var\log\platform_operations.jsonl",
    [int]$DispatcherLogHeartbeatEveryIterations = 12
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $RepoRoot "var\run"
$LogDir = Join-Path $RepoRoot "var\log"
$PidPath = Join-Path $RunDir "operator_dashboard.pid"
$OutLog = Join-Path $LogDir "operator_dashboard.out.log"
$ErrLog = Join-Path $LogDir "operator_dashboard.err.log"
$DispatcherPidPath = Join-Path $RunDir "event_outbox_dispatcher.pid"
$DispatcherOutLog = Join-Path $LogDir "event_outbox_dispatcher.out.log"
$DispatcherErrLog = Join-Path $LogDir "event_outbox_dispatcher.err.log"
$DispatcherOutput = Join-Path $RepoRoot "var\events\platform_events.jsonl"
$DispatcherStatePath = Join-Path $RunDir "event_outbox_dispatcher.state.json"
$DatabasePath = Join-Path $RepoRoot "var\systematic_trading.db"
$ResolvedOperationLogPath = if ([System.IO.Path]::IsPathRooted($OperationLogPath)) { $OperationLogPath } else { Join-Path $RepoRoot $OperationLogPath }

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found at $Python"
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Start-EventOutboxDispatcher {
    if ($DisableEventDispatcher) {
        Write-Output "Event outbox dispatcher disabled for this start."
        return
    }

    if (Test-Path $DispatcherPidPath) {
        $existingDispatcherPidText = (Get-Content -LiteralPath $DispatcherPidPath -Raw).Trim()
        if ($existingDispatcherPidText) {
            $existingDispatcher = Get-Process -Id ([int]$existingDispatcherPidText) -ErrorAction SilentlyContinue
            if ($existingDispatcher) {
                Write-Output "Event outbox dispatcher already appears to be running."
                Write-Output "Dispatcher PID: $existingDispatcherPidText"
                Write-Output "Dispatcher output: $DispatcherOutput"
                return
            }
        }
        Remove-Item -LiteralPath $DispatcherPidPath -Force
    }

    $dispatcherArgs = @(
        ".\scripts\dispatch_event_outbox.py",
        "--database",
        $DatabasePath,
        "--output",
        $DispatcherOutput,
        "--state-path",
        $DispatcherStatePath,
        "--publisher",
        $EventPublisher,
        "--operation-log",
        $ResolvedOperationLogPath,
        "--log-heartbeat-every-iterations",
        [string]$DispatcherLogHeartbeatEveryIterations,
        "--loop",
        "--interval-seconds",
        [string]$EventDispatcherIntervalSeconds
    )
    if ($EventPublisher -eq "nats") {
        $dispatcherArgs += @("--nats-url", $NatsUrl)
    }

    $dispatcherProcess = Start-Process `
        -FilePath $Python `
        -ArgumentList $dispatcherArgs `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $DispatcherOutLog `
        -RedirectStandardError $DispatcherErrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $DispatcherPidPath -Value ([string]$dispatcherProcess.Id) -Encoding ascii
    Write-Output "Event outbox dispatcher started."
    Write-Output "Dispatcher PID: $($dispatcherProcess.Id)"
    Write-Output "Dispatcher publisher: $EventPublisher"
    if ($EventPublisher -eq "nats") {
        Write-Output "Dispatcher NATS URL: $NatsUrl"
    }
    Write-Output "Dispatcher output: $DispatcherOutput"
    Write-Output "Dispatcher state: $DispatcherStatePath"
    Write-Output "Dispatcher logs: $DispatcherOutLog"
    Write-Output "Dispatcher errors: $DispatcherErrLog"
}

if (Test-Path $PidPath) {
    $existingPidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
    if ($existingPidText) {
        $existing = Get-Process -Id ([int]$existingPidText) -ErrorAction SilentlyContinue
        if ($existing) {
            Start-EventOutboxDispatcher
            Write-Output "Operator dashboard already appears to be running."
            Write-Output "PID: $existingPidText"
            Write-Output "URL: http://$HostName`:$Port/operator"
            exit 0
        }
    }
    Remove-Item -LiteralPath $PidPath -Force
}

try {
    $client = [System.Net.Sockets.TcpClient]::new()
    $connect = $client.BeginConnect($HostName, $Port, $null, $null)
    if ($connect.AsyncWaitHandle.WaitOne(500, $false)) {
        $client.EndConnect($connect)
        $client.Close()
        throw "Port $Port on $HostName is already accepting connections. Pick another port with -Port."
    }
    $client.Close()
} catch [System.Net.Sockets.SocketException] {
    # Expected when the port is free.
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$process = Start-Process `
    -FilePath $Python `
    -ArgumentList @(
        ".\scripts\serve_operator_dashboard.py",
        "--host",
        $HostName,
        "--port",
        [string]$Port,
        "--pid-path",
        $PidPath
    ) `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

$healthUrl = "http://$HostName`:$Port/health"
$deadline = (Get-Date).AddSeconds(12)
do {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        if ($health.StatusCode -eq 200) {
            $serverPid = if (Test-Path $PidPath) { (Get-Content -LiteralPath $PidPath -Raw).Trim() } else { [string]$process.Id }
            Write-Output "Operator dashboard started."
            Write-Output "PID: $serverPid"
            Write-Output "URL: http://$HostName`:$Port/operator"
            Write-Output "Health: $($health.Content)"
            Write-Output "Logs: $OutLog"
            Write-Output "Errors: $ErrLog"
            Start-EventOutboxDispatcher
            exit 0
        }
    } catch {
        if ($process.HasExited) {
            throw "Dashboard process exited during startup. Check $ErrLog"
        }
    }
} while ((Get-Date) -lt $deadline)

throw "Dashboard process started but health did not respond before timeout. Check $ErrLog"
