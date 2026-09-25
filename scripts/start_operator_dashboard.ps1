param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$DisableEventDispatcher,
    [int]$EventDispatcherIntervalSeconds = 5,
    [ValidateSet("jsonl", "nats")]
    [string]$EventPublisher = "nats",
    [string]$NatsUrl = "nats://127.0.0.1:4222",
    [ValidateSet("sqlite", "postgres")]
    [string]$TransactionalStoreBackend = "postgres",
    [ValidateSet("sqlite", "clickhouse")]
    [string]$MarketDataStoreBackend = "clickhouse",
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

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$env:ST_TRANSACTIONAL_STORE_BACKEND = $TransactionalStoreBackend
$env:ST_MARKET_DATA_STORE_BACKEND = $MarketDataStoreBackend

& $Python (Join-Path $ScriptDir "sync_databases.py") guard
if ($LASTEXITCODE -ne 0) { throw "NAS handoff is not ready. Start through start_local_platform.ps1." }

function Test-ProcessOwnsPort {
    param(
        [int]$ProcessId,
        [int]$ExpectedPort
    )

    $pattern = ":$ExpectedPort\s+.*LISTENING\s+$ProcessId$"
    return $null -ne (netstat -ano -p tcp | Select-String -Pattern $pattern | Select-Object -First 1)
}

function Test-DispatcherStatePid {
    param([int]$ProcessId)

    if (-not (Test-Path $DispatcherStatePath)) { return $false }
    try {
        $state = Get-Content -LiteralPath $DispatcherStatePath -Raw | ConvertFrom-Json
        return $state.running -and [int]$state.details.process_id -eq $ProcessId
    } catch {
        return $false
    }
}

function Update-IbTwsHealthState {
    $statePath = Join-Path $RunDir "ib_tws_api.state.json"
    & $Python ".\scripts\probe_ib_tws_health.py" --state-path $statePath | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "IB TWS API health probe OK."
    } else {
        Write-Output "IB TWS API health probe failed. Check $statePath and the platform health page."
    }
}

function Start-EventOutboxDispatcher {
    if ($DisableEventDispatcher) {
        Write-Output "Event outbox dispatcher disabled for this start."
        return
    }

    if (Test-Path $DispatcherPidPath) {
        $existingDispatcherPidText = (Get-Content -LiteralPath $DispatcherPidPath -Raw).Trim()
        if ($existingDispatcherPidText) {
            $existingDispatcherPid = [int]$existingDispatcherPidText
            $existingDispatcher = Get-Process -Id $existingDispatcherPid -ErrorAction SilentlyContinue
            if ($existingDispatcher -and (Test-DispatcherStatePid -ProcessId $existingDispatcherPid)) {
                Write-Output "Event outbox dispatcher already appears to be running."
                Write-Output "Dispatcher PID: $existingDispatcherPidText"
                Write-Output "Dispatcher output: $DispatcherOutput"
                return
            }
        }
        Remove-Item -LiteralPath $DispatcherPidPath -Force
    }

    if (Test-Path $DispatcherStatePath) {
        Remove-Item -LiteralPath $DispatcherStatePath -Force
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

    $dispatcherPid = $dispatcherProcess.Id
    $dispatcherStateDeadline = (Get-Date).AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 200
        if (Test-Path $DispatcherStatePath) {
            try {
                $dispatcherState = Get-Content -LiteralPath $DispatcherStatePath -Raw | ConvertFrom-Json
                if ($dispatcherState.running -and $dispatcherState.details.process_id) {
                    $dispatcherPid = [int]$dispatcherState.details.process_id
                    break
                }
            } catch {
                # State file may be between atomic updates; retry until the deadline.
            }
        }
    } while ((Get-Date) -lt $dispatcherStateDeadline)
    Set-Content -LiteralPath $DispatcherPidPath -Value ([string]$dispatcherPid) -Encoding ascii
    Write-Output "Event outbox dispatcher started."
    Write-Output "Dispatcher PID: $dispatcherPid"
    Write-Output "Dispatcher publisher: $EventPublisher"
    if ($EventPublisher -eq "nats") {
        Write-Output "Dispatcher NATS URL: $NatsUrl"
    }
    Write-Output "Dispatcher output: $DispatcherOutput"
    Write-Output "Dispatcher state: $DispatcherStatePath"
    Write-Output "Dispatcher logs: $DispatcherOutLog"
    Write-Output "Dispatcher errors: $DispatcherErrLog"
}

Update-IbTwsHealthState

if (Test-Path $PidPath) {
    $existingPidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
    if ($existingPidText) {
        $existingPid = [int]$existingPidText
        $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existing -and (Test-ProcessOwnsPort -ProcessId $existingPid -ExpectedPort $Port)) {
            Start-EventOutboxDispatcher
            Write-Output "Operator dashboard already appears to be running."
            Write-Output "PID: $existingPidText"
            Write-Output "URL: http://$HostName`:$Port/operator"
            exit 0
        }
        if ($existing) {
            Write-Output "Operator dashboard PID $existingPidText belongs to another process. Removing stale PID file."
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
            Write-Output "Transactional store backend: $TransactionalStoreBackend"
            Write-Output "Market data store backend: $MarketDataStoreBackend"
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
