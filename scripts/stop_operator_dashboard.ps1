param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PidPath = Join-Path $RepoRoot "var\run\operator_dashboard.pid"
$DispatcherPidPath = Join-Path $RepoRoot "var\run\event_outbox_dispatcher.pid"
$DispatcherStatePath = Join-Path $RepoRoot "var\run\event_outbox_dispatcher.state.json"

function Test-ExpectedServiceProcess {
    param([int]$ProcessId, [string]$ExpectedService)

    if ($ExpectedService -eq "operator") {
        return $null -ne (netstat -ano -p tcp | Select-String -Pattern ":8000\s+.*LISTENING\s+$ProcessId$" | Select-Object -First 1)
    }
    if (-not (Test-Path $DispatcherStatePath)) { return $false }
    try {
        $state = Get-Content -LiteralPath $DispatcherStatePath -Raw | ConvertFrom-Json
        return $state.running -and [int]$state.details.process_id -eq $ProcessId
    } catch {
        return $false
    }
}

function Stop-ProcessFromPidFile {
    param(
        [string]$Name,
        [string]$Path,
        [string]$ExpectedService
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

    if (-not (Test-ExpectedServiceProcess -ProcessId $process.Id -ExpectedService $ExpectedService)) {
        Remove-Item -LiteralPath $Path -Force
        Write-Output "$Name PID $pidText belongs to another process. Removed stale PID file without stopping it."
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

Stop-ProcessFromPidFile -Name "Event outbox dispatcher" -Path $DispatcherPidPath -ExpectedService "dispatcher"
Stop-ProcessFromPidFile -Name "Operator dashboard" -Path $PidPath -ExpectedService "operator"
