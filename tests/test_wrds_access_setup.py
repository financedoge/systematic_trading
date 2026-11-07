"""Credential handling and read-only setup, without real account credentials."""

import importlib.util
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "wrds_access_setup", Path(__file__).resolve().parents[1] / "scripts/setup_wrds_access.py"
)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def test_password_record_escapes_colons_and_backslashes():
    assert setup.password_record("example", "a:b\\c") == (
        "wrds-pgdata.wharton.upenn.edu:9737:wrds:example:a\\:b\\\\c\n"
    )


@pytest.mark.parametrize("value", ["", "one\ntwo", "one\rtwo", "one\0two"])
def test_password_record_rejects_invalid_fields(value):
    with pytest.raises(ValueError):
        setup.password_record("example", value)


def test_existing_password_file_is_preserved(tmp_path):
    path = tmp_path / "pgpass.conf"
    path.write_text("unrelated-existing-entry\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        setup.save_new_passfile(path, "example", "test-only")
    assert path.read_text(encoding="utf-8") == "unrelated-existing-entry\n"


def test_acl_failure_never_writes_password(tmp_path, monkeypatch):
    path = tmp_path / "pgpass.conf"

    def fail(_):
        raise PermissionError("synthetic ACL failure")

    monkeypatch.setattr(setup, "protect_new_file", fail)
    with pytest.raises(PermissionError):
        setup.save_new_passfile(path, "example", "test-only")
    assert path.read_bytes() == b""


def test_connection_enforces_tls_read_only_and_bound_timeouts(tmp_path, monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    captured = {}
    monkeypatch.setattr(setup.psycopg, "connect", lambda **kwargs: captured.update(kwargs))
    setup.connect("example", tmp_path / "pgpass.conf", tmp_path / "ca.pem")
    assert captured["host"] == setup.WRDS_HOST
    assert captured["sslmode"] == "verify-full"
    assert "default_transaction_read_only=on" in captured["options"]
    assert "statement_timeout=30000" in captured["options"]
    assert captured["connect_timeout"] == 120
    assert "password" not in captured


def test_connection_refuses_environment_password(tmp_path, monkeypatch):
    monkeypatch.setenv("PGPASSWORD", "synthetic-not-a-secret")
    with pytest.raises(RuntimeError, match="PGPASSWORD"):
        setup.connect("example", tmp_path / "pgpass.conf", tmp_path / "ca.pem")


def test_proxy_preserves_verified_hostname_and_password_file_matching(tmp_path, monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    captured = {}
    monkeypatch.setattr(setup.psycopg, "connect", lambda **kwargs: captured.update(kwargs))
    setup.connect("example", tmp_path / "pgpass.conf", tmp_path / "ca.pem", via_proxy=True)
    assert captured["hostaddr"] == "127.0.0.1"
    assert captured["host"] == setup.WRDS_HOST
    assert captured["port"] == 9737
    assert captured["sslmode"] == "verify-full"


@pytest.mark.parametrize("proxy", ["http://outside.invalid:80", "http://user:pw@127.0.0.1:7892",
                                  "socks5://127.0.0.1:7892", "http://127.0.0.1"])
def test_proxy_rejects_unapproved_routes(proxy):
    with pytest.raises(ValueError):
        setup.WrdsProxyTunnel(proxy)
