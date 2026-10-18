$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
& (Join-Path $RepoRoot ".venv\Scripts\python.exe") (Join-Path $ScriptDir "local_recovery.py") pause nats
if ($LASTEXITCODE -ne 0) { throw "Could not pause NATS recovery before stopping." }
& (Join-Path $ScriptDir 'native_nats.ps1') -Action stop
if ($LASTEXITCODE -ne 0) { throw 'Native NATS stop failed.' }
