from pathlib import Path
import shutil
import subprocess

import pytest


def test_watchdog_does_not_treat_api_liveness_as_worker_readiness():
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is needed for watchdog readiness checks")
    script = Path("scripts/watch_local_platform.ps1").read_text()
    # Evaluate only the two pure functions; never run production checks/repairs.
    def extract(name, following):
        return script[script.index("function "+name):script.index("function "+following)]
    command = extract("New-Check", "Test-HttpEndpoint") + extract("Get-EmbeddedWorkerChecks", "Get-ContainerStatus")
    command += '''
$checks = @(Get-EmbeddedWorkerChecks -HealthContent '{"services":[{"service_id":"analytics","required":true,"status":"degraded","message":"Calculation stalled"},{"service_id":"trading_management_loop","required":true,"status":"ok","message":"Running"}]}')
if ($checks.Count -ne 2 -or $checks[0].status -ne "degraded" -or -not $checks[0].required) { throw "Lost worker readiness failure" }
$invalid = Get-EmbeddedWorkerChecks -HealthContent "not JSON"
if ($invalid.status -ne "error") { throw "Malformed readiness became healthy" }
'''
    subprocess.run([shell, "-NoProfile", "-Command", command], check=True, capture_output=True, text=True, timeout=15)
