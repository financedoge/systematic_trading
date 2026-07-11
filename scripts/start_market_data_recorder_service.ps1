param(
    [string[]]$RecorderSymbols = @("SPY", "QQQ", "TLT", "GLD", "IWM"),
    [int]$RecorderRealtimeChunkSeconds = 300,
    [int]$RecorderGapFillLookbackMinutes = 60,
    [int]$RecorderPollSeconds = 60,
    [int]$RecorderClientId = 121,
    [ValidateSet("live", "frozen", "delayed", "delayed_frozen")]
    [string]$RecorderMarketDataMode = "live",
    [switch]$DisableDailyBackfill,
    [int]$DailyBackfillLookbackDays = 14,
    [int]$DailyBackfillIntervalMinutes = 360,
    [ValidateSet("yahoo", "ib", "tushare")]
    [string]$DailyBackfillProvider = "yahoo",
    [ValidateSet("none", "yahoo", "ib", "tushare")]
    [string]$DailyBackfillFallbackProvider = "ib",
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

$pidPath = Join-Path $RunDir "market_data_recorder.pid"
$statePath = Join-Path $RunDir "market_data_recorder.state.json"
$outLog = Join-Path $LogDir "market_data_recorder.out.log"
$errLog = Join-Path $LogDir "market_data_recorder.err.log"
if (Test-Path $pidPath) {
    $existingPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    if ($existingPid) {
        $existing = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Output "Market data recorder service already appears to be running."
            Write-Output "Recorder PID: $existingPid"
            return
        }
    }
    Remove-Item -LiteralPath $pidPath -Force
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$symbolsArg = $RecorderSymbols -join ","
$recorderArgs = @(
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
    "--daily-backfill-lookback-days",
    [string]$DailyBackfillLookbackDays,
    "--daily-backfill-interval-minutes",
    [string]$DailyBackfillIntervalMinutes,
    "--daily-backfill-provider",
    $DailyBackfillProvider,
    "--daily-backfill-fallback-provider",
    $DailyBackfillFallbackProvider,
    "--pid-path",
    $pidPath,
    "--state-path",
    $statePath,
    "--operation-log",
    $ResolvedOperationLogPath
)
if ($DisableDailyBackfill) {
    $recorderArgs += "--disable-daily-backfill"
}
$process = Start-Process `
    -FilePath $Python `
    -ArgumentList $recorderArgs `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Write-Output "Market data recorder service started."
Write-Output "Recorder PID: $($process.Id)"
Write-Output "Recorder symbols: $symbolsArg"
Write-Output "Recorder market data mode: $RecorderMarketDataMode"
Write-Output "Recorder realtime chunk seconds: $RecorderRealtimeChunkSeconds"
Write-Output "Recorder gap-fill lookback minutes: $RecorderGapFillLookbackMinutes"
Write-Output "Daily ClickHouse backfill: $(-not $DisableDailyBackfill)"
Write-Output "Daily ClickHouse backfill provider: $DailyBackfillProvider"
Write-Output "Daily ClickHouse backfill fallback: $DailyBackfillFallbackProvider"
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
        daily_backfill_enabled = -not $DisableDailyBackfill
        daily_backfill_lookback_days = $DailyBackfillLookbackDays
        daily_backfill_interval_minutes = $DailyBackfillIntervalMinutes
        daily_backfill_provider = $DailyBackfillProvider
        daily_backfill_fallback_provider = $DailyBackfillFallbackProvider
        client_id = $RecorderClientId
        state_path = $statePath
    }
