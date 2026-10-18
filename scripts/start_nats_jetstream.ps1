param(
    [switch]$Recovery
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
if (-not $Recovery) {
    & (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $ScriptDir "local_recovery.py") resume nats
    if ($LASTEXITCODE -ne 0) { throw "Could not resume NATS recovery." }
}
& (Join-Path $ScriptDir 'native_nats.ps1') -Action start
if ($LASTEXITCODE -ne 0) { throw 'Native NATS startup failed.' }
