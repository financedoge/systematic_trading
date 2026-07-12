param(
    [switch]$Repair,
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$NatsUrl = "nats://127.0.0.1:4222",
    [string]$OperationLogPath = "var\log\platform_operations.jsonl",
    [string]$StatePath = "var\run\local_platform_watchdog.state.json"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $RepoRoot "var\run"
$ResolvedOperationLogPath = if ([System.IO.Path]::IsPathRooted($OperationLogPath)) { $OperationLogPath } else { Join-Path $RepoRoot $OperationLogPath }
$ResolvedStatePath = if ([System.IO.Path]::IsPathRooted($StatePath)) { $StatePath } else { Join-Path $RepoRoot $StatePath }

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResolvedOperationLogPath) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ResolvedStatePath) | Out-Null

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
        service_id = "local_platform_watchdog"
        level = $Level
        event = $Event
        message = $Message
        details = $Details
    }
    [System.IO.File]::AppendAllText(
        $ResolvedOperationLogPath,
        ($payload | ConvertTo-Json -Compress -Depth 8) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function New-Check {
    param(
        [string]$ServiceId,
        [bool]$Required,
        [string]$Status,
        [string]$Message,
        [bool]$Repaired = $false,
        [hashtable]$Details = @{}
    )

    [pscustomobject]@{
        service_id = $ServiceId
        required = $Required
        status = $Status
        message = $Message
        repaired = $Repaired
        details = $Details
    }
}

function Test-HttpEndpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 3
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds
        if ($response.StatusCode -lt 400) {
            return @{ ok = $true; message = "HTTP $($response.StatusCode)"; content = [string]$response.Content }
        }
        return @{ ok = $false; message = "HTTP $($response.StatusCode)"; content = [string]$response.Content }
    } catch {
        return @{ ok = $false; message = $_.Exception.Message; content = $null }
    }
}

function Test-TcpEndpoint {
    param(
        [string]$Address,
        [int]$TcpPort,
        [int]$TimeoutMilliseconds = 1500
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($Address, $TcpPort, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return @{ ok = $false; message = "TCP timeout at $Address`:$TcpPort" }
        }
        $client.EndConnect($connect)
        return @{ ok = $true; message = "TCP OK at $Address`:$TcpPort" }
    } catch {
        return @{ ok = $false; message = $_.Exception.Message }
    } finally {
        $client.Close()
    }
}

function Get-ContainerStatus {
    param([string]$Name)

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return "docker unavailable"
    }
    $status = docker ps -a --filter "name=^/$Name$" --format "{{.Status}}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        return "docker ps failed"
    }
    if (-not $status) {
        return "missing"
    }
    return [string]$status
}

function Test-RecorderState {
    $recorderStatePath = Join-Path $RepoRoot "var\run\market_data_recorder.state.json"
    $recorderPidPath = Join-Path $RepoRoot "var\run\market_data_recorder.pid"
    if (-not (Test-Path $recorderStatePath)) {
        return New-Check -ServiceId "market_data_recorder" -Required $false -Status "disabled" -Message "Recorder has no state file; optional recorder is not running."
    }
    try {
        $state = Get-Content -Raw -LiteralPath $recorderStatePath | ConvertFrom-Json
    } catch {
        return New-Check -ServiceId "market_data_recorder" -Required $false -Status "degraded" -Message "Recorder state file could not be parsed: $($_.Exception.Message)"
    }

    $pidAlive = $false
    if (Test-Path $recorderPidPath) {
        $pidText = (Get-Content -Raw -LiteralPath $recorderPidPath).Trim()
        if ($pidText) {
            $pidAlive = $null -ne (Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)
        }
    }

    $recordsWritten = 0
    if ($null -ne $state.details -and $null -ne $state.details.records_written) {
        $recordsWritten = [int]$state.details.records_written
    }
    $lastError = [string]$state.last_error
    if (-not $state.running) {
        return New-Check -ServiceId "market_data_recorder" -Required $false -Status "disabled" -Message "Recorder is stopped." -Details @{ records_written = $recordsWritten }
    }
    if ($state.running -and $pidAlive -and -not $lastError) {
        return New-Check -ServiceId "market_data_recorder" -Required $false -Status "ok" -Message "Recorder process and state file are live." -Details @{ records_written = $recordsWritten }
    }
    if ($state.running -and $pidAlive) {
        return New-Check -ServiceId "market_data_recorder" -Required $false -Status "degraded" -Message "Recorder process is running with last_error: $lastError" -Details @{ records_written = $recordsWritten }
    }
    return New-Check -ServiceId "market_data_recorder" -Required $false -Status "degraded" -Message "Recorder state exists but the PID is not alive." -Details @{ records_written = $recordsWritten }
}

function Test-IbTwsState {
    $statePath = Join-Path $RepoRoot "var\run\ib_tws_api.state.json"
    if (-not (Test-Path $Python)) {
        return New-Check -ServiceId "ib_tws_api" -Required $true -Status "error" -Message "Python virtualenv not found; cannot probe IB TWS API." -Details @{ python = $Python }
    }
    & $Python ".\scripts\probe_ib_tws_health.py" --state-path $statePath | Out-Null
    $probeExitCode = $LASTEXITCODE
    if (-not (Test-Path $statePath)) {
        return New-Check -ServiceId "ib_tws_api" -Required $true -Status "error" -Message "IB TWS health probe did not write a state file." -Details @{ state_path = $statePath; exit_code = $probeExitCode }
    }
    try {
        $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    } catch {
        return New-Check -ServiceId "ib_tws_api" -Required $true -Status "error" -Message "IB TWS state file could not be parsed: $($_.Exception.Message)" -Details @{ state_path = $statePath; exit_code = $probeExitCode }
    }
    $details = @{
        state_path = $statePath
        exit_code = $probeExitCode
        host = $state.details.host
        port = $state.details.port
        client_id = $state.details.client_id
        managed_accounts = $state.details.managed_accounts
        next_valid_order_id = $state.details.next_valid_order_id
    }
    if ($state.running) {
        return New-Check -ServiceId "ib_tws_api" -Required $true -Status "ok" -Message "IB TWS API probe passed." -Details $details
    }
    return New-Check -ServiceId "ib_tws_api" -Required $true -Status "error" -Message ([string]$state.last_error) -Details $details
}

Push-Location $RepoRoot
try {
    Write-OperationLog -Event "watchdog_run_started" -Message "Local platform watchdog run started." -Details @{ repair = [bool]$Repair }
    $checks = @()

    $natsHealth = Test-HttpEndpoint -Url "http://127.0.0.1:8222/healthz?js-enabled-only=true"
    $natsRepaired = $false
    if (-not $natsHealth.ok -and $Repair) {
        Write-OperationLog -Event "nats_repair_requested" -Level "warning" -Message "NATS health check failed; attempting Docker Compose repair." -Details @{ error = $natsHealth.message }
        & (Join-Path $ScriptDir "start_nats_jetstream.ps1")
        if ($LASTEXITCODE -eq 0 -and (Test-Path $Python)) {
            & $Python ".\scripts\configure_nats_stream.py" --nats-url $NatsUrl
        }
        $natsRepaired = $true
        $natsHealth = Test-HttpEndpoint -Url "http://127.0.0.1:8222/healthz?js-enabled-only=true"
    }
    $checks += New-Check `
        -ServiceId "nats_jetstream" `
        -Required $true `
        -Status $(if ($natsHealth.ok) { "ok" } else { "error" }) `
        -Message $natsHealth.message `
        -Repaired $natsRepaired `
        -Details @{ container_status = Get-ContainerStatus -Name "systematic-trading-nats" }

    $postgres = Test-TcpEndpoint -Address "127.0.0.1" -TcpPort 5432
    $checks += New-Check `
        -ServiceId "postgres_transactional" `
        -Required $true `
        -Status $(if ($postgres.ok) { "ok" } else { "error" }) `
        -Message $postgres.message

    $checks += Test-IbTwsState

    $clickhouseHealth = Test-HttpEndpoint -Url "http://127.0.0.1:8123/ping"
    $clickhouseRepaired = $false
    if (-not $clickhouseHealth.ok -and $Repair) {
        Write-OperationLog -Event "clickhouse_repair_requested" -Level "warning" -Message "ClickHouse health check failed; attempting Docker Compose repair." -Details @{ error = $clickhouseHealth.message }
        & (Join-Path $ScriptDir "start_clickhouse.ps1")
        $clickhouseRepaired = $true
        Start-Sleep -Seconds 2
        $clickhouseHealth = Test-HttpEndpoint -Url "http://127.0.0.1:8123/ping"
    }
    $checks += New-Check `
        -ServiceId "clickhouse_columnar" `
        -Required $true `
        -Status $(if ($clickhouseHealth.ok) { "ok" } else { "error" }) `
        -Message $clickhouseHealth.message `
        -Repaired $clickhouseRepaired `
        -Details @{ container_status = Get-ContainerStatus -Name "systematic-trading-clickhouse" }

    $operatorHealth = Test-HttpEndpoint -Url "http://$HostName`:$Port/health"
    $operatorRepaired = $false
    if (-not $operatorHealth.ok -and $Repair) {
        Write-OperationLog -Event "operator_repair_requested" -Level "warning" -Message "Operator health check failed; attempting operator restart." -Details @{ error = $operatorHealth.message }
        & (Join-Path $ScriptDir "start_operator_dashboard.ps1") -HostName $HostName -Port $Port -EventPublisher "nats" -NatsUrl $NatsUrl -OperationLogPath $ResolvedOperationLogPath
        $operatorRepaired = $true
        $operatorHealth = Test-HttpEndpoint -Url "http://$HostName`:$Port/health"
    }
    $checks += New-Check `
        -ServiceId "operator_dashboard" `
        -Required $true `
        -Status $(if ($operatorHealth.ok) { "ok" } else { "error" }) `
        -Message $operatorHealth.message `
        -Repaired $operatorRepaired

    $checks += Test-RecorderState

    $requiredFailures = @($checks | Where-Object { $_.required -and $_.status -ne "ok" })
    $overallStatus = if ($requiredFailures.Count -eq 0) { "ok" } else { "error" }
    $summary = [ordered]@{
        schema_version = 1
        service_id = "local_platform_watchdog"
        status = $overallStatus
        checked_at = (Get-Date).ToUniversalTime().ToString("o")
        repair = [bool]$Repair
        checks = $checks
    }
    $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ResolvedStatePath -Encoding utf8
    Write-OperationLog -Event "watchdog_run_completed" -Level $(if ($overallStatus -eq "ok") { "info" } else { "error" }) -Message "Local platform watchdog run completed." -Details @{ status = $overallStatus; required_failures = $requiredFailures.Count }
    $summary | ConvertTo-Json -Depth 10
    if ($overallStatus -ne "ok") {
        exit 1
    }
} finally {
    Pop-Location
}
