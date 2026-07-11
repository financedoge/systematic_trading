param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$SkipNats,
    [switch]$SkipClickHouse,
    [switch]$SkipOperator,
    [switch]$SkipMarketDataRecorder,
    [switch]$StartMarketDataRecorder,
    [string[]]$RecorderSymbols = @("SPY", "QQQ", "TLT", "GLD", "IWM"),
    [int]$RecorderRealtimeChunkSeconds = 300,
    [int]$RecorderGapFillLookbackMinutes = 60,
    [int]$RecorderPollSeconds = 60,
    [int]$RecorderClientId = 121,
    [ValidateSet("live", "frozen", "delayed", "delayed_frozen")]
    [string]$RecorderMarketDataMode = "live",
    [ValidateSet("jsonl", "nats")]
    [string]$EventPublisher = "nats",
    [string]$NatsUrl = "nats://127.0.0.1:4222",
    [ValidateSet("sqlite", "postgres")]
    [string]$TransactionalStoreBackend = "postgres",
    [ValidateSet("sqlite", "clickhouse")]
    [string]$MarketDataStoreBackend = "clickhouse",
    [string]$OperationLogPath = "var\log\platform_operations.jsonl"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $RepoRoot "var\run"
$LogDir = Join-Path $RepoRoot "var\log"
$ResolvedOperationLogPath = if ([System.IO.Path]::IsPathRooted($OperationLogPath)) { $OperationLogPath } else { Join-Path $RepoRoot $OperationLogPath }

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found at $Python"
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResolvedOperationLogPath) | Out-Null

function Write-OperationLog {
    param(
        [string]$Event,
        [string]$Level = "info",
        [string]$Message = $null,
        [hashtable]$Details = @{}
    )

    $payload = [ordered]@{
        schema_version = 1
        occurred_at = (Get-Date).ToUniversalTime().ToString("o")
        service_id = "local_platform_supervisor"
        level = $Level
        event = $Event
        message = $Message
        details = $Details
    }
    $line = ($payload | ConvertTo-Json -Compress -Depth 8)
    [System.IO.File]::AppendAllText(
        $ResolvedOperationLogPath,
        $line + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Wait-HttpHealth {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -lt 400) {
                Write-Output "$Name health OK: $Url"
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)

    throw "$Name health did not respond before timeout: $Url"
}

function Test-TcpPort {
    param(
        [string]$Name,
        [string]$Address,
        [int]$TcpPort,
        [int]$TimeoutMilliseconds = 1500
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($Address, $TcpPort, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            throw "$Name TCP check timed out at $Address`:$TcpPort"
        }
        $client.EndConnect($connect)
        Write-Output "$Name TCP OK: $Address`:$TcpPort"
    } finally {
        $client.Close()
    }
}

function Assert-PostgresReady {
    $pgReady = Get-Command pg_isready -ErrorAction SilentlyContinue
    if ($pgReady) {
        & $pgReady.Source -h 127.0.0.1 -p 5432
        if ($LASTEXITCODE -ne 0) {
            throw "pg_isready failed with exit code $LASTEXITCODE"
        }
        Write-Output "Postgres readiness OK via pg_isready."
        return
    }
    Test-TcpPort -Name "Postgres" -Address "127.0.0.1" -TcpPort 5432
}

function Start-RecorderService {
    $pidPath = Join-Path $RunDir "market_data_recorder.pid"
    $statePath = Join-Path $RunDir "market_data_recorder.state.json"
    $outLog = Join-Path $LogDir "market_data_recorder.out.log"
    $errLog = Join-Path $LogDir "market_data_recorder.err.log"
    if (Test-Path $pidPath) {
        $existingPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
        if ($existingPid) {
            $existing = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
            if ($existing) {
                Write-Output "Market data recorder already appears to be running."
                Write-Output "Recorder PID: $existingPid"
                return
            }
        }
        Remove-Item -LiteralPath $pidPath -Force
    }

    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    $symbolsArg = $RecorderSymbols -join ","
    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            ".\scripts\run_market_data_recorder_service.py",
            "--symbols",
            $symbolsArg,
            "--realtime-chunk-seconds",
            [string]$RecorderRealtimeChunkSeconds,
            "--gap-fill-lookback-minutes",
            [string]$RecorderGapFillLookbackMinutes,
            "--poll-seconds",
            [string]$RecorderPollSeconds,
            "--market-data-mode",
            $RecorderMarketDataMode,
            "--client-id",
            [string]$RecorderClientId,
            "--pid-path",
            $pidPath,
            "--state-path",
            $statePath
        ) `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -Encoding ascii
    Write-Output "Market data recorder service started."
    Write-Output "Recorder PID: $($process.Id)"
    Write-Output "Recorder symbols: $symbolsArg"
    Write-Output "Recorder market data mode: $RecorderMarketDataMode"
    Write-Output "Recorder realtime chunk seconds: $RecorderRealtimeChunkSeconds"
    Write-Output "Recorder gap-fill lookback minutes: $RecorderGapFillLookbackMinutes"
    Write-Output "Recorder state: $statePath"
    Write-OperationLog `
        -Event "recorder_service_started" `
        -Message "Market data recorder service process started." `
        -Details @{
            pid = $process.Id
            symbols = $RecorderSymbols
            market_data_mode = $RecorderMarketDataMode
            realtime_chunk_seconds = $RecorderRealtimeChunkSeconds
            gap_fill_lookback_minutes = $RecorderGapFillLookbackMinutes
            client_id = $RecorderClientId
            state_path = $statePath
        }
}

Push-Location $RepoRoot
try {
    $env:ST_TRANSACTIONAL_STORE_BACKEND = $TransactionalStoreBackend
    $env:ST_MARKET_DATA_STORE_BACKEND = $MarketDataStoreBackend
    Write-OperationLog `
        -Event "local_platform_start_requested" `
        -Message "Local platform startup requested." `
        -Details @{
            host = $HostName
            port = $Port
            event_publisher = $EventPublisher
            transactional_store_backend = $TransactionalStoreBackend
            market_data_store_backend = $MarketDataStoreBackend
            nats_url = $NatsUrl
            skip_nats = [bool]$SkipNats
            skip_clickhouse = [bool]$SkipClickHouse
            skip_operator = [bool]$SkipOperator
            skip_market_data_recorder = [bool]$SkipMarketDataRecorder
            start_market_data_recorder = -not [bool]$SkipMarketDataRecorder
            recorder_symbols = $RecorderSymbols
            recorder_market_data_mode = $RecorderMarketDataMode
        }
    if (-not $SkipNats) {
        Write-OperationLog -Event "nats_start_requested" -Message "NATS JetStream startup requested." -Details @{ nats_url = $NatsUrl }
        & (Join-Path $ScriptDir "start_nats_jetstream.ps1")
        Wait-HttpHealth -Name "NATS JetStream" -Url "http://127.0.0.1:8222/healthz?js-enabled-only=true" -TimeoutSeconds 30
        & $Python ".\scripts\configure_nats_stream.py" --nats-url $NatsUrl
        if ($LASTEXITCODE -ne 0) {
            throw "NATS stream configuration failed with exit code $LASTEXITCODE"
        }
        Write-OperationLog -Event "nats_stream_configured" -Message "NATS JetStream stream configured." -Details @{ nats_url = $NatsUrl; stream = "ST_EVENTS" }
    } elseif ($EventPublisher -eq "nats") {
        Write-Output "NATS startup skipped; dispatcher will use existing NATS at $NatsUrl."
        Write-OperationLog -Event "nats_start_skipped" -Message "NATS startup skipped; dispatcher will use existing NATS." -Details @{ nats_url = $NatsUrl }
    }

    Assert-PostgresReady
    Write-OperationLog -Event "postgres_ready" -Message "Postgres readiness check passed." -Details @{ host = "127.0.0.1"; port = 5432 }

    if (-not $SkipClickHouse) {
        Write-OperationLog -Event "clickhouse_start_requested" -Message "ClickHouse startup requested." -Details @{ url = "http://127.0.0.1:8123" }
        & (Join-Path $ScriptDir "start_clickhouse.ps1")
        Wait-HttpHealth -Name "ClickHouse" -Url "http://127.0.0.1:8123/ping" -TimeoutSeconds 45
        Write-OperationLog -Event "clickhouse_ready" -Message "ClickHouse health check passed." -Details @{ url = "http://127.0.0.1:8123/ping" }
    }

    if (-not $SkipOperator) {
        Write-OperationLog -Event "operator_start_requested" -Message "Operator dashboard startup requested." -Details @{ host = $HostName; port = $Port; event_publisher = $EventPublisher; transactional_store_backend = $TransactionalStoreBackend; market_data_store_backend = $MarketDataStoreBackend }
        & (Join-Path $ScriptDir "start_operator_dashboard.ps1") `
            -HostName $HostName `
            -Port $Port `
            -EventPublisher $EventPublisher `
            -NatsUrl $NatsUrl `
            -TransactionalStoreBackend $TransactionalStoreBackend `
            -MarketDataStoreBackend $MarketDataStoreBackend `
            -OperationLogPath $ResolvedOperationLogPath
    }

    if (-not $SkipMarketDataRecorder) {
        Start-RecorderService
    } else {
        Write-Output "Market data recorder service not started because -SkipMarketDataRecorder was passed."
        Write-OperationLog -Event "recorder_service_not_started" -Message "Market data recorder service was not started by request." -Details @{}
    }

    Write-Output "Local platform startup completed."
    Write-Output "Operator URL: http://$HostName`:$Port/operator"
    Write-Output "Platform health URL: http://$HostName`:$Port/platform"
    Write-OperationLog `
        -Event "local_platform_start_completed" `
        -Message "Local platform startup completed." `
        -Details @{ operator_url = "http://$HostName`:$Port/operator"; platform_url = "http://$HostName`:$Port/platform" }
} catch {
    Write-OperationLog `
        -Event "local_platform_start_failed" `
        -Level "error" `
        -Message $_.Exception.Message `
        -Details @{ error = [string]$_ }
    throw
} finally {
    Pop-Location
}
