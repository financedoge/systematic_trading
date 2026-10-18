param(
    [Parameter(Mandatory=$true)][ValidateSet('start','stop','status')][string]$Action,
    [switch]$Migration
)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Config = Get-Content -LiteralPath (Join-Path $RepoRoot 'config\native-runtime.json') -Raw | ConvertFrom-Json
$Binary = [IO.Path]::GetFullPath((Join-Path $RepoRoot $Config.nats_binary))
$RunRoot = Join-Path $RepoRoot 'var\run'
$LogRoot = Join-Path $RepoRoot 'var\log'
$StoreRoot = Join-Path $Config.bulk_root 'nats\jetstream'
$ConfigPath = Join-Path $RunRoot 'native-nats.conf'
$PidPath = Join-Path $RunRoot 'native-nats.pid'
$ReadyPath = Join-Path $Config.bulk_root 'nats\migration-ready.json'

function Get-OwnedNatsProcess {
    if (-not (Test-Path -LiteralPath $PidPath)) { return $null }
    $ServerProcessId = [int](Get-Content -LiteralPath $PidPath -Raw).Trim()
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId=$ServerProcessId"
    if (-not $Process) { return $null }
    if ($Process.ExecutablePath -ne $Binary -or -not $Process.CommandLine.Contains($ConfigPath)) {
        throw 'NATS PID identity does not match the configured executable and config.'
    }
    return $Process
}

$Owned = Get-OwnedNatsProcess
if ($Action -eq 'status') {
    if (-not $Owned) { throw 'Native NATS is not running.' }
    Invoke-RestMethod "http://127.0.0.1:$($Config.nats_monitor_port)/healthz?js-enabled-only=true"
    exit 0
}
if ($Action -eq 'stop') {
    if ($Owned) {
        # On Windows NATS -sl targets SCM services, not standalone process IDs.
        & (Join-Path $RepoRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'stop_native_console.py') $Owned.ProcessId
        if ($LASTEXITCODE -ne 0) { throw 'Native NATS graceful stop failed.' }
        $Deadline = (Get-Date).AddSeconds(30)
        while ((Get-Process -Id $Owned.ProcessId -ErrorAction SilentlyContinue) -and (Get-Date) -lt $Deadline) { Start-Sleep -Milliseconds 250 }
        if (Get-Process -Id $Owned.ProcessId -ErrorAction SilentlyContinue) { throw 'Native NATS did not stop.' }
    }
    exit 0
}
if ($Owned) {
    Invoke-RestMethod "http://127.0.0.1:$($Config.nats_monitor_port)/healthz?js-enabled-only=true"
    exit 0
}
if (-not (Test-Path -LiteralPath $Binary)) { throw 'Install the pinned native NATS package with scripts/install_native_nats.py.' }
$Provenance = Get-Content -LiteralPath (Join-Path (Split-Path $Binary) 'provenance.json') -Raw | ConvertFrom-Json
$ExpectedHash = ($Provenance | Where-Object { $_.executable -eq 'nats-server.exe' }).executable_sha256
$Hasher = [Security.Cryptography.SHA256]::Create()
$BinaryStream = [IO.File]::OpenRead($Binary)
try { $ActualHash = [BitConverter]::ToString($Hasher.ComputeHash($BinaryStream)).Replace('-', '').ToLowerInvariant() }
finally { $BinaryStream.Dispose(); $Hasher.Dispose() }
if (-not $ExpectedHash -or $ActualHash -ne $ExpectedHash) { throw 'Native NATS executable checksum changed.' }
if (-not $Migration -and -not (Test-Path -LiteralPath $ReadyPath)) { throw 'Native NATS migration has not been verified. Refusing an empty stream replacement.' }
if (-not $Migration -and -not (Test-Path -LiteralPath (Join-Path $StoreRoot 'jetstream\$G\streams\ST_EVENTS'))) { throw 'Migrated stream storage is missing; restore before starting.' }
if (Get-NetTCPConnection -State Listen -LocalPort $Config.nats_client_port -ErrorAction SilentlyContinue) { throw 'NATS port is owned by another process. Complete the stopped-writer cutover first.' }
New-Item -ItemType Directory -Force -Path $RunRoot,$LogRoot,$StoreRoot | Out-Null
$StoreText = $StoreRoot.Replace('\','/')
$PidText = $PidPath.Replace('\','/')
$LogText = (Join-Path $LogRoot 'native-nats.log').Replace('\','/')
$Contents = @"
server_name: systematic-trading-native
listen: "127.0.0.1:$($Config.nats_client_port)"
http: "127.0.0.1:$($Config.nats_monitor_port)"
pid_file: "$PidText"
log_file: "$LogText"
log_size_limit: 20Mb
logtime_utc: true
jetstream {
  store_dir: "$StoreText"
  max_mem_store: 256Mb
  max_file_store: 5Gb
}
"@
[IO.File]::WriteAllText($ConfigPath, $Contents, [Text.UTF8Encoding]::new($false))
& $Binary -t -c $ConfigPath
if ($LASTEXITCODE -ne 0) { throw 'Native NATS configuration validation failed.' }
$Started = Start-Process -FilePath $Binary -ArgumentList @('-c', ('"' + $ConfigPath + '"')) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
$Deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $Deadline) {
    if ($Started.HasExited) { throw 'Native NATS exited during startup; inspect native-nats.log.' }
    try {
        $Health = Invoke-RestMethod "http://127.0.0.1:$($Config.nats_monitor_port)/healthz?js-enabled-only=true"
        if ($Health.status -eq 'ok' -and (Get-OwnedNatsProcess)) { Write-Output 'Native NATS is ready on loopback.'; exit 0 }
    } catch { Start-Sleep -Milliseconds 250 }
}
throw 'Native NATS readiness timed out.'
