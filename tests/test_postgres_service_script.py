"""Exercise the PostgreSQL service helper with mocked Windows service cmdlets.

The helper must start a stopped service, ask Windows for administrator permission
only when elevation is actually needed, refuse cleanly when it is declined, and
never report success when the service did not reach Running.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


RUNNER = r'''
param([string]$Source)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Script parse failed' }
foreach ($node in $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $true)) {
    . ([scriptblock]::Create($node.Extent.Text))
}

# The elevated child script is generated, not stored, so verify it parses before
# any Windows prompt would ever be requested.
$childScript = New-ElevatedPostgresChildScript -Action 'Restart' -ServiceName 'postgresql-x64-18' `
    -LibraryPath 'C:\Program Files\repo with space\scripts\postgres_service.ps1' `
    -ResultPath 'C:\Users\Some User\AppData\Local\Temp\result.json' -WaitSeconds 60
$childTokens = $null; $childErrors = $null
$null = [System.Management.Automation.Language.Parser]::ParseInput($childScript, [ref]$childTokens, [ref]$childErrors)
if ($childErrors.Count) { throw "child script parse failed: $($childErrors[0].Message)" }
if ($childScript -notmatch "Invoke-PostgresServiceControlDirect -Action 'Restart'") { throw 'child script missing direct call' }
if ($childScript -notmatch "repo with space") { throw 'child script lost the library path' }

# Mock state shared with the loaded functions through the script scope.
$script:serviceStatus = 'Running'
$script:elevated = $false
$script:elevatedOk = $true
$script:elevatedCalls = @()
$script:started = 0
$script:restarted = 0
$script:startThrows = $false

function Get-Service {
    param([string]$Name)
    if ($script:serviceStatus -eq 'Missing') { return $null }
    [pscustomobject]@{ Name = $Name; Status = $script:serviceStatus }
}
function Start-Service {
    param([string]$Name)
    if ($script:startThrows) { throw 'Access is denied.' }
    $script:started++
    $script:serviceStatus = 'Running'
}
function Restart-Service {
    param([string]$Name, [switch]$Force)
    $script:restarted++
    $script:serviceStatus = 'Running'
}
function Start-Sleep {
    param($Milliseconds, $Seconds)
}
function Test-IsElevated { return $script:elevated }
function Invoke-ElevatedPostgresAction {
    param([string]$Action, [string]$ServiceName, [int]$WaitSeconds = 90)
    $script:elevatedCalls += @("$Action|$ServiceName")
    if ($script:elevatedOk) { $script:serviceStatus = 'Running' }
    [pscustomobject]@{
        Ok = $script:elevatedOk; Action = $Action; ServiceName = $ServiceName
        Method = 'elevated'; Elevated = $true
        Error = if ($script:elevatedOk) { $null } else { 'Administrator permission was declined in the Windows prompt.' }
    }
}

$name = 'postgresql-x64-18'

# 1. A running service is left alone.
$script:serviceStatus = 'Running'; $script:started = 0; $script:elevatedCalls = @()
$result = Ensure-PostgresServiceStarted -ServiceName $name
if (-not $result.Ok -or $result.Action -ne 'None' -or $script:started -ne 0) { throw '1: running service was touched' }

# 2. A stopped service is started directly when the shell is already elevated.
$script:serviceStatus = 'Stopped'; $script:elevated = $true; $script:started = 0
$result = Ensure-PostgresServiceStarted -ServiceName $name
if (-not $result.Ok -or $result.Method -ne 'direct' -or $script:started -ne 1 -or $result.State -ne 'Running') { throw '2: direct start failed' }

# 3. Otherwise Windows is asked once for administrator permission.
$script:serviceStatus = 'Stopped'; $script:elevated = $false; $script:started = 0; $script:elevatedCalls = @(); $script:elevatedOk = $true
$result = Ensure-PostgresServiceStarted -ServiceName $name -AllowElevation
if (-not $result.Ok -or $result.Method -ne 'elevated' -or $result.Elevated -ne $true) { throw '3: elevation was not requested' }
if ($script:elevatedCalls.Count -ne 1 -or $script:elevatedCalls[0] -ne "Start|$name" -or $script:started -ne 0) { throw '3: elevation call mismatch' }

# 4. Without elevation permission the helper refuses with clear guidance.
$script:serviceStatus = 'Stopped'; $script:elevated = $false
$result = Ensure-PostgresServiceStarted -ServiceName $name
if ($result.Ok -or $result.Error -notmatch 'Administrator permission') { throw '4: missing refusal guidance' }

# 5. A declined prompt is reported, not swallowed.
$script:serviceStatus = 'Stopped'; $script:elevatedOk = $false
$result = Ensure-PostgresServiceStarted -ServiceName $name -AllowElevation
if ($result.Ok -or $result.Error -notmatch 'declined') { throw '5: declined elevation was not reported' }

# 6. Read failures restart the service through one elevation request.
$script:serviceStatus = 'Running'; $script:elevated = $false; $script:elevatedOk = $true; $script:elevatedCalls = @()
$result = Restart-PostgresService -ServiceName $name -AllowElevation
if (-not $result.Ok -or $result.Action -ne 'Restart' -or $script:elevatedCalls.Count -ne 1) { throw '6: elevated restart failed' }

# 7. An already elevated shell restarts directly.
$script:elevated = $true; $script:restarted = 0
$result = Restart-PostgresService -ServiceName $name
if (-not $result.Ok -or $result.Method -ne 'direct' -or $script:restarted -ne 1) { throw '7: direct restart failed' }

# 8. A missing service is reported as not found instead of being invented.
$script:serviceStatus = 'Missing'
$result = Ensure-PostgresServiceStarted -ServiceName $name
if (-not $result.Ok -or $result.Found -or $result.State -ne 'Missing') { throw '8: missing service handling wrong' }

# 9. Service-control failure keeps the error and does not claim success.
$script:serviceStatus = 'Stopped'; $script:elevated = $true; $script:startThrows = $true
$result = Ensure-PostgresServiceStarted -ServiceName $name
if ($result.Ok -or $result.Error -notmatch 'Access is denied') { throw '9: start failure was hidden' }

Write-Output 'postgres-service-tests-passed'
'''


@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
def test_postgres_service_helper_asks_for_elevation_only_when_needed(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} not available")
    source = Path("scripts/postgres_service.ps1").resolve()
    test_script = tmp_path / "test-postgres-service.ps1"
    test_script.write_text(RUNNER, encoding="utf-8")
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-File", str(test_script), str(source)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "postgres-service-tests-passed" in result.stdout


def test_postgres_service_script_declares_cli_and_elevation_contract():
    text = Path("scripts/postgres_service.ps1").read_text(encoding="utf-8")
    assert "-Verb RunAs" in text
    assert "Test-IsElevated" in text
    assert "Start-Service -Name" in text or "Restart-Service -Name" in text
    assert "Invoke-ElevatedPostgresAction" in text
    assert "Administrator permission was declined" in text
    assert "postgresql-x64-18" in text
    assert "$MyInvocation.InvocationName -ne \".\"" in text
