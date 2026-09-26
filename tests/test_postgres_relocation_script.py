"""Exercise the service-command helper in Windows PowerShell without touching services."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
def test_service_change_preserves_quotes_and_checks_errors(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} not available")
    source = Path("scripts/move_postgres_data_to_d.ps1").resolve()
    test_script = tmp_path / "test-service-command.ps1"
    test_script.write_text(r'''
param([string]$Source)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Script parse failed' }
$helper = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Set-PostgresServiceCommand'}, $true)
if (-not $helper) { throw 'Missing service helper' }
# Load only the helper, never the relocation entry point.
. ([scriptblock]::Create($helper.Extent.Text))
$script:stored = 'original'; $script:returnCode = 0; $script:mismatch = $false
$script:received = $null
function Get-CimInstance {
    param($ClassName)
    if ($ClassName -ne 'Win32_Service') { throw 'Unexpected service class' }
    [pscustomobject]@{Name='postgresql-x64-18'; PathName=$script:stored}
}
function Invoke-CimMethod {
    param($InputObject, $MethodName, $Arguments)
    if ($MethodName -ne 'Change' -or $Arguments.Count -ne 1) { throw 'Unexpected service mutation' }
    $script:received = $Arguments.PathName
    if ($script:returnCode -eq 0 -and -not $script:mismatch) { $script:stored = $Arguments.PathName }
    [pscustomobject]@{ReturnValue=$script:returnCode}
}
$old = '"C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" runservice -N "postgresql-x64-18" -D "C:\Program Files\PostgreSQL\18\data" -w'
$new = $old.Replace('"C:\Program Files\PostgreSQL\18\data"', '"D:\systematic_trading_data\postgresql\18\data"')
Set-PostgresServiceCommand -Name 'postgresql-x64-18' -Command $new
if ($script:stored -cne $new -or $script:received -cne $new) { throw 'Quotes changed' }
Set-PostgresServiceCommand -Name 'postgresql-x64-18' -Command $old
if ($script:stored -cne $old) { throw 'Rollback quotes changed' }
$script:returnCode = 5
$caught = $false
try { Set-PostgresServiceCommand -Name 'postgresql-x64-18' -Command $new }
catch { if ($_.Exception.Message -notmatch 'code 5') { throw }; $caught = $true }
if (-not $caught -or $script:stored -cne $old) { throw 'Failed change was not rejected' }
$script:returnCode = 0; $script:mismatch = $true; $caught = $false
try { Set-PostgresServiceCommand -Name 'postgresql-x64-18' -Command $new }
catch { if ($_.Exception.Message -notmatch 'readback') { throw }; $caught = $true }
if (-not $caught) { throw 'Readback mismatch was not rejected' }
Write-Output 'service-command-tests-passed'
''', encoding="utf-8")
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-File", str(test_script), str(source)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "service-command-tests-passed" in result.stdout
