from pathlib import Path
import runpy
import shutil
import subprocess

import psycopg
import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage import postgres_readiness as readiness


class ProbeConnection:
    def __init__(self, failure_at=None):
        self.queries = []
        self.failure_at = failure_at
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def execute(self, query):
        self.queries.append(query if isinstance(query, str) else query.as_string())
        if len(self.queries) == self.failure_at:
            raise psycopg.errors.InternalError_(
                'could not read blocks 2..2 in file "base/16393/1259": Invalid argument'
            )
        return self

    def fetchone(self):
        return None  # Empty initialized tables must be accepted.


def settings(**overrides):
    return AppSettings(
        _env_file=None, postgres_host="db.example.test", postgres_port=5544,
        postgres_database="test_db", postgres_app_user="probe_role",
        postgres_app_password="probe-secret",
        transactional_store_backend="postgres", **overrides,
    )


def test_authenticated_read_probe_uses_config_and_bounded_read_only_session(monkeypatch):
    connection = ProbeConnection()
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return connection

    monkeypatch.setattr(readiness.psycopg, "connect", connect)
    result = readiness.probe_postgres_readiness(settings(market_data_store_backend="parquet"))
    assert captured["host"] == "db.example.test"
    assert captured["port"] == 5544
    assert captured["dbname"] == "test_db"
    assert captured["user"] == "probe_role"
    assert captured["password"] == "probe-secret"
    assert captured["connect_timeout"] == 5
    for guard in ("default_transaction_read_only=on", "statement_timeout=10000",
                  "lock_timeout=3000", "transaction_timeout=30000"):
        assert guard in captured["options"]
    assert "information_schema.columns" in connection.queries[0]
    assert '"native_analytics"."publication_heads"' in connection.queries[5]
    assert all(q.startswith("SELECT ") for q in connection.queries)
    assert all("LIMIT 1" in q for q in connection.queries[1:])
    assert connection.closed
    assert result["status"] == "ready"
    assert "probe-secret" not in str(result)


@pytest.mark.parametrize("failure_at", [1, 3, 6])
def test_catalog_or_relation_failure_aborts_probe(monkeypatch, failure_at):
    connection = ProbeConnection(failure_at)
    monkeypatch.setattr(readiness.psycopg, "connect", lambda **kwargs: connection)
    with pytest.raises(psycopg.errors.InternalError_, match="Invalid argument"):
        readiness.probe_postgres_readiness(settings(market_data_store_backend="parquet"))
    assert len(connection.queries) == failure_at
    assert connection.closed


def test_legacy_backend_does_not_require_native_schema(monkeypatch):
    connection = ProbeConnection()
    monkeypatch.setattr(readiness.psycopg, "connect", lambda **kwargs: connection)
    readiness.probe_postgres_readiness(settings(market_data_store_backend="clickhouse"))
    assert not any("native_analytics" in q for q in connection.queries)


def test_cli_exits_nonzero_with_actionable_redacted_error(monkeypatch, capsys):
    def fail(**kwargs):
        raise psycopg.OperationalError("connection failed probe-secret")

    monkeypatch.setattr(readiness.psycopg, "connect", fail)
    module = runpy.run_path("scripts/probe_postgres_readiness.py")
    monkeypatch.setitem(module["main"].__globals__, "AppSettings", settings)
    assert module["main"]() == 1
    output = capsys.readouterr()
    assert "read readiness FAILED" in output.err
    assert "before database preparation and retention" in output.err
    assert "probe-secret" not in output.err + output.out
    assert "[redacted]" in output.err
    assert "OK" not in output.out


@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
def test_launcher_rejects_probe_failure_before_continuing(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} unavailable")
    source = Path("scripts/start_local_platform.ps1").resolve()
    text = source.read_text(encoding="utf-8")
    assert text.index("    Assert-PostgresReady") < text.index('".\\scripts\\sync_databases.py" prepare')
    assert text.index('".\\scripts\\sync_databases.py" prepare') < text.index("'maintain_research_storage.ps1'")
    runner = tmp_path / "test-probe.ps1"
    runner.write_text(r'''
param([string]$Source)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Parse failed' }
$helper = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-PostgresReady'}, $true)
. ([scriptblock]::Create($helper.Extent.Text))
$Python = 'Invoke-ProbeStub'; $ScriptDir = Split-Path -Parent $Source
function Invoke-ProbeStub {
    param($Path)
    if ((Split-Path -Leaf $Path) -ne 'probe_postgres_readiness.py') { throw 'Wrong probe' }
    $global:LASTEXITCODE = $script:probeExit
}
$script:probeExit = 1; $continued = $false; $caught = $false
try { Assert-PostgresReady; $continued = $true }
catch {
    if ($_.Exception.Message -notmatch 'PostgreSQL read readiness failed') { throw }
    $caught = $true
}
if ($continued -or -not $caught) { throw 'Startup ignored failed reads' }
$script:probeExit = 0
Assert-PostgresReady
Write-Output 'readiness-gate-passed'
''', encoding="utf-8")
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-File", str(runner), str(source)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "readiness-gate-passed" in result.stdout
