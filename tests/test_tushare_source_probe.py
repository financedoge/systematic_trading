import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location(
    "tushare_source_probe", Path(__file__).resolve().parents[1] / "scripts/probe_tushare_us_source.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def response(rows):
    return {"code": 0, "data": {"fields": ["ts_code", "trade_date", "close", "vol"], "items": rows}}


def test_incomplete_source_is_missing_not_filled():
    result = probe.inspect_response(response([["CSL", "20250224", 100, 20]]), "CSL")
    assert result["row_count"] == 1
    assert result["complete_five_sessions"] is False
    assert len(result["missing_dates"]) == 4


@pytest.mark.parametrize("rows", [
    [["WRONG", "20250224", 100, 20]],
    [["CSL", "20250221", 100, 20]],
    [["CSL", "20250224", 100, 20], ["CSL", "20250224", 100, 20]],
    [["CSL", "20250224", 100]],
])
def test_wrong_identity_date_duplicates_or_schema_are_rejected(rows):
    with pytest.raises(ValueError):
        probe.inspect_response(response(rows), "CSL")


def test_permission_error_is_not_empty_market_data():
    result = probe.inspect_response({"code": 2002, "msg": "No entitlement", "data": None}, "CSL")
    assert result["status"] == "api_error"
    assert result["api_code"] == 2002


def test_native_post_keeps_credential_off_command_line_and_requires_tls(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{"code":0}')

    monkeypatch.setattr(probe.subprocess, "run", run)
    payload = b'{"token":"synthetic-secret"}'
    assert probe.native_post(payload) == b'{"code":0}'
    args, kwargs = calls[0]
    assert "synthetic-secret" not in " ".join(args)
    assert kwargs["input"] == payload
    assert args[args.index("--proto") + 1] == "=https"
    assert args[-1] == probe.ENDPOINT
    assert "--insecure" not in args and "--location" not in args
