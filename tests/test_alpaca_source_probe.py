"""Frozen scope, authenticated transport and failure/coverage contracts."""
import importlib.util
import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location(
    "alpaca_source_probe", Path(__file__).resolve().parents[1] / "scripts/probe_alpaca_sip_source.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def bar(timestamp="2025-02-24T05:00:00Z"):
    return {"t": timestamp, "o": 100, "h": 102, "l": 99, "c": 101, "v": 120, "n": 10}


def test_request_locks_raw_sip_literal_ticker_and_frozen_dates():
    symbols, dates = probe.scope("sample")
    assert len(symbols) == 10 and len(dates) == 5
    params = probe.parameters(symbols, dates, "1Day")
    assert (params["feed"], params["adjustment"], params["asof"]) == ("sip", "raw", "-")
    assert params["start"] == "2025-02-24T00:00:00-05:00"
    assert params["end"] == "2025-02-28T23:59:59-05:00"


def test_transport_keeps_keys_off_argv_and_refuses_redirects(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{"bars":{}}\n200')

    monkeypatch.setattr(probe.subprocess, "run", run)
    credentials = {"key_id": "synthetic-key-id", "secret_key": "synthetic-secret"}
    assert probe.fetch(probe.parameters(["CSL"], ["2025-02-24"], "1Day"), credentials, local_proxy=True)[0] == 200
    args, kwargs = calls[0]
    assert all(secret not in " ".join(args) for secret in credentials.values())
    assert all(secret.encode() in kwargs["input"] for secret in credentials.values())
    assert "--location" not in args and "--insecure" not in args
    assert "--ipv4" in args
    assert args[args.index("--proxy") + 1] == "http://127.0.0.1:7892"
    assert args[args.index("--proto") + 1] == "=https"
    assert probe.ENDPOINT.encode() in kwargs["input"]


def test_credential_echo_refused_before_archiving(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout=b'synthetic-secret\n200'))
    with pytest.raises(ValueError, match="credential echo"):
        probe.fetch(probe.parameters(["CSL"], ["2025-02-24"], "1Day"),
                    {"key_id": "synthetic-key-id", "secret_key": "synthetic-secret"})


@pytest.mark.parametrize("row", [bar("2025-02-24T00:00:00Z"), bar("2025-02-24T05:00:01Z"),
                                  bar("2025-02-24T05:00:00"), {**bar(), "v": -1},
                                  {**bar(), "c": float("nan")}, {**bar(), "h": 98}])
def test_invalid_or_misaligned_rows_rejected(row):
    params = probe.parameters(["CSL"], ["2025-02-24"], "1Day")
    with pytest.raises(ValueError):
        probe.inspect_page({"bars": {"CSL": [row]}}, params, ["2025-02-24"], set())


def test_duplicate_across_pages_is_not_silently_deduplicated():
    params = probe.parameters(["CSL"], ["2025-02-24"], "1Day")
    seen = set()
    probe.inspect_page({"bars": {"CSL": [bar()]}}, params, ["2025-02-24"], seen)
    with pytest.raises(ValueError, match="Duplicate"):
        probe.inspect_page({"bars": {"CSL": [bar()]}}, params, ["2025-02-24"], seen)


def test_http_denial_is_retained_and_stops_before_more_requests(tmp_path, monkeypatch):
    calls = []

    def denied(params, credentials):
        calls.append(params)
        return 403, b'{"message":"No entitlement"}'

    monkeypatch.setattr(probe, "fetch", denied)
    root = probe.capture("probe", {}, tmp_path, transport_attempts=3)
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(calls) == 1
    assert manifest["status"] == "incomplete"
    assert manifest["requests"][0]["http_status"] == 403
    assert (root / manifest["requests"][0]["path"]).is_file()
    assert manifest["series"]["1Day"]["missing_stock_days"] == [["CSL", "2025-02-24"]]


def test_missing_daily_rows_remain_missing_and_stop_minute_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "fetch", lambda *args: (200, b'{"bars":{},"next_page_token":null}'))
    root = probe.capture("probe", {}, tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["status"] == "incomplete"
    assert len(manifest["requests"]) == 1


def test_connection_timeout_retry_is_bounded_and_retained(tmp_path, monkeypatch):
    calls = []

    def timeout(*args):
        calls.append(args)
        raise OSError("Verified HTTPS transport failed (curl 28)")

    monkeypatch.setattr(probe, "fetch", timeout)
    monkeypatch.setattr(probe.time, "sleep", lambda _: None)
    root = probe.capture("probe", {}, tmp_path, transport_attempts=3)
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(calls) == 3
    assert [r["curl_exit_code"] for r in manifest["requests"][0]["transport_attempts"]] == [28, 28, 28]
    assert manifest["status"] == "incomplete"


def test_repeated_page_token_is_a_failure_not_a_complete_sample(tmp_path, monkeypatch):
    count = 0

    def pages(*args):
        nonlocal count
        count += 1
        payload = {"bars": {"CSL": [bar()]} if count == 1 else {}, "next_page_token": "same"}
        return 200, json.dumps(payload).encode()

    monkeypatch.setattr(probe, "fetch", pages)
    root = probe.capture("probe", {}, tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    assert count == 2
    assert manifest["status"] == "incomplete"
    assert manifest["requests"][-1]["status"] == "failed"


def test_existing_credentials_never_overwritten(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text("existing")
    with pytest.raises(FileExistsError):
        probe.setup_credentials(path)
    assert path.read_text() == "existing"


def test_existing_project_env_credentials_are_reused_without_copying(tmp_path):
    env = tmp_path / ".env"
    env.write_text('ST_ALPACA_MARKET_API_KEY="synthetic-key"\n'
                   'ST_ALPACA_MARKET_API_SECRET="synthetic-${UNCHANGED}"\n')
    private = tmp_path / "credentials.json"
    assert probe.load_credentials(private, env) == {
        "key_id": "synthetic-key", "secret_key": "synthetic-${UNCHANGED}"}
    assert not private.exists()


def test_incomplete_credential_pair_is_not_mixed_with_another_source(tmp_path):
    env = tmp_path / ".env"
    env.write_text('ST_ALPACA_MARKET_API_KEY=synthetic-key\nAPCA_API_SECRET_KEY=wrong-source\n')
    with pytest.raises(ValueError):
        probe.load_credentials(tmp_path / "missing.json", env)


def test_credential_entry_refuses_echo_fallback(tmp_path, monkeypatch):
    def fallback(_):
        warnings.warn("Cannot disable echo", probe.getpass.GetPassWarning)
        return "must-not-be-read"

    monkeypatch.setattr(probe.getpass, "getpass", fallback)
    path = tmp_path / "credentials.json"
    with pytest.raises(probe.getpass.GetPassWarning):
        probe.setup_credentials(path)
    assert not path.exists()


def test_session_clock_bins_preserve_closing_minute_and_missing_stock_days():
    spec = importlib.util.spec_from_file_location(
        "alpaca_source_compare", Path(__file__).resolve().parents[1] / "scripts/compare_alpaca_sip_source.py"
    )
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    rows = [{"symbol": "CSL", "t": "2025-02-24T" + time + "Z", "v": volume}
            for time, volume in [("14:29:00", 1), ("14:30:00", 10), ("20:59:00", 100),
                                 ("21:00:00", 1000), ("21:01:00", 10000)]]
    totals = comparison.minute_totals(rows)
    assert set(totals) == {("CSL", "2025-02-24")}
    day = totals["CSL", "2025-02-24"]
    assert day["before_0930"] == 1
    assert day["0930_to_before_1600"] == 110
    assert day["1600_minute"] == 1000
    assert day["1601_onward"] == 10000
    assert day["all_observed_minutes"] == 11111
    assert day["minute_bar_count"] == 5
