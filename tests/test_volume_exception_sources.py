"""Frozen cases, tape-aware parsing and retained pagination boundaries."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("volume_exception_capture", SCRIPTS / "capture_volume_exception_trades.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
sys.path.pop(0)


def case():
    return next(c for c in source.protocol()["cases"] if c["symbol"] == "MANH")


def trade(**updates):
    return {"t": case()["date"] + "T14:30:00.000000001Z", "i": 1, "x": "Q", "z": "C",
            "c": ["@", "I"], "p": 100, "s": 4, **updates}


def test_scope_is_exactly_fourteen_cases_and_three_independent_controls():
    p = source.protocol()
    assert len({source.key(c) for c in p["cases"]}) == 14
    assert len(p["ibkr_tick_controls"]) == 3
    assert source.parameters(case())["end"].endswith("04:59:59.999999999Z")


def test_nasdaq_conditions_and_distinct_occurrences_are_preserved():
    rows = [trade(), trade(i=2, c=["@", "B"])]
    assert source.validate_page({"symbol": "MANH", "trades": rows}, case(), set(), 0)[0] == rows


@pytest.mark.parametrize("changed", [{"z": "A"}, {"c": ["8"]}, {"u": "unknown"},
                                     {"t": "2025-02-28T14:30:00Z"}, {"s": -1}])
def test_wrong_source_basis_or_window_fails(changed):
    with pytest.raises(ValueError):
        source.validate_page({"symbol": "MANH", "trades": [trade(**changed)]}, case(), set(), 0)


def test_saved_short_page_does_not_imply_completion(tmp_path):
    params = source.parameters(case())
    data = {"symbol": "MANH", "trades": [trade()], "next_page_token": "second-page"}
    receipt = source.retain(tmp_path, "one", json.dumps(data).encode())
    receipt.update(case=source.key(case()), parameters=params, http_status=200)
    state = source.retained_state(tmp_path, {"requests": [receipt]}, case())
    assert state[2:] == ("second-page", 1, False)
    receipt["parameters"]["page_token"] = "wrong"
    with pytest.raises(ValueError, match="chain"):
        source.retained_state(tmp_path, {"requests": [receipt]}, case())


def test_transport_rejects_changed_scope_and_keeps_auth_off_argv(monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{}\n200')

    monkeypatch.setattr(source.subprocess, "run", run)
    credentials = {"key_id": "synthetic-key", "secret_key": "synthetic-secret"}
    assert source.fetch(case(), source.parameters(case()), credentials)[0] == 200
    argv, options = calls[0]
    assert all(v not in " ".join(argv) for v in credentials.values())
    assert all(v.encode() in options["input"] for v in credentials.values())
    assert "--insecure" not in argv and "--location" not in argv
    with pytest.raises(ValueError, match="scope"):
        source.fetch(case(), {**source.parameters(case()), "feed": "iex"}, credentials)
