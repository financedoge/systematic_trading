"""Lossless page boundaries and source-state handling for one-day inspection."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("csl_trade_capture", SCRIPTS / "capture_csl_trade_sources.py")
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)
sys.path.pop(0)


def trade(**updates):
    return {"t": "2025-02-24T14:30:00.123456789Z", "i": 1, "x": "N", "z": "A",
            "p": 100, "s": 3, "c": ["I"], **updates}


def test_nanosecond_boundary_never_rounds_into_next_day():
    assert capture.timestamp_ns("2025-02-25T04:59:59.999999999Z") == capture.END * 10**9 - 1
    a = capture.timestamp_ns("2025-02-24T14:30:00.000000001Z")
    assert capture.timestamp_ns("2025-02-24T14:30:00.000000002Z") == a + 1


def test_identical_looking_trades_and_correction_states_are_preserved():
    rows = [trade(), trade(i=2), trade(u="incorrect"), trade(u="corrected")]
    actual, _ = capture.validate_alpaca({"symbol": "CSL", "trades": rows}, set(), 0)
    assert actual == rows


def test_exact_repeated_page_record_is_rejected():
    seen = set()
    payload = {"symbol": "CSL", "trades": [trade()]}
    _, stamp = capture.validate_alpaca(payload, seen, 0)
    with pytest.raises(ValueError, match="duplicate"):
        capture.validate_alpaca(payload, seen, stamp)


def test_zero_size_official_price_marker_is_retained_without_trade_volume():
    rows = [trade(s=0, c=[" ", "9"])]
    assert capture.validate_alpaca({"symbol": "CSL", "trades": rows}, set(), 0)[0] == rows
    with pytest.raises(ValueError, match="zero-size"):
        capture.validate_alpaca({"symbol": "CSL", "trades": [trade(s=0)]}, set(), 0)


@pytest.mark.parametrize("changed", [{"u": "unknown"}, {"t": "2025-02-25T05:00:00Z"},
                                     {"s": -1}, {"p": float("nan")}, {"z": "C"}])
def test_invalid_source_records_fail_closed(changed):
    with pytest.raises(ValueError):
        capture.validate_alpaca({"symbol": "CSL", "trades": [trade(**changed)]}, set(), 0)


def test_ib_final_second_retains_all_occurrences_and_advances_once():
    rows = [{"time": capture.START, "price": "100", "size": "5"}] * 1005
    assert capture.next_ib_second(rows, capture.START) == capture.START + 1
    assert len(rows) == 1005
    with pytest.raises(ValueError, match="regress"):
        capture.next_ib_second(rows, capture.START + 1)


def test_ib_short_page_is_not_a_completion_signal():
    rows = [{"time": capture.START + 100, "price": "100", "size": "1"}]
    assert capture.next_ib_second(rows, capture.START) == capture.START + 101 < capture.END


def test_transport_is_fixed_origin_and_never_exposes_keys_on_argv(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{}\n200')

    monkeypatch.setattr(capture.subprocess, "run", run)
    credentials = {"key_id": "synthetic-key", "secret_key": "synthetic-secret"}
    assert capture.fetch("/v2/stocks/CSL/trades", {"feed": "sip", "asof": "-"}, credentials)[0] == 200
    argv, kwargs = calls[0]
    assert all(v not in " ".join(argv) for v in credentials.values())
    assert all(v.encode() in kwargs["input"] for v in credentials.values())
    assert "--insecure" not in argv and "--location" not in argv
    with pytest.raises(ValueError, match="Undeclared"):
        capture.fetch("https://unrelated.invalid", {}, credentials)


def test_credential_echo_is_not_archived(monkeypatch):
    monkeypatch.setattr(capture.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout=b'synthetic-secret\n200'))
    with pytest.raises(ValueError, match="credential echo"):
        capture.fetch("/v2/stocks/meta/exchanges", {},
                      {"key_id": "synthetic-key", "secret_key": "synthetic-secret"})


def test_resume_uses_complete_seconds_and_rejects_tampered_payload(tmp_path):
    runner = b"retained runner"
    (tmp_path / "capture_csl_trade_sources.py").write_bytes(runner)
    rows = [{"time": capture.START + 10, "price": "100", "size": "5"}] * 2
    receipt = capture.retain(tmp_path, "trades-01", json.dumps({"rows": rows}).encode())
    receipt.update(parameters={"startDateTime": "20250224 05:00:00 UTC", "endDateTime": ""},
                   complete_callback=True, error_codes=[], row_count=2)
    failed = capture.retain(tmp_path, "trades-02", b'{"rows": []}')
    failed.update(parameters={"endDateTime": ""}, complete_callback=False, error_codes=[])
    capture.save(tmp_path / "manifest.json", {"provider": "ibkr", "symbol": "CSL", "date": "2025-02-24",
        "protocol_sha256": capture.sha((capture.STUDY / "protocol.json").read_bytes()),
        "runner_sha256": capture.sha(runner), "requests": [receipt, failed]})
    cursor, count, _ = capture.resume_ib(tmp_path)
    assert cursor == capture.START + 11 and count == 1
    (tmp_path / receipt["path"]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="Changed resume payload"):
        capture.resume_ib(tmp_path)
