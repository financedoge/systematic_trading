"""Tape semantics, source residuals and retry boundary preservation."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("volume_exception_reconcile", SCRIPTS / "reconcile_volume_exceptions.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)
from capture_volume_exception_ibkr import saved_progress  # noqa: E402
from capture_csl_trade_sources import retain  # noqa: E402
sys.path.pop(0)


def trade(**updates):
    return {"t": "2025-02-25T14:30:00Z", "i": 1, "x": "Q", "z": "C",
            "c": ["@"], "p": 100, "s": 20, **updates}


def test_bunched_trade_is_price_eligible_on_nasdaq_but_average_price_on_nyse():
    rules = study.protocol()["rules"]
    assert study.eligible(trade(c=["@", "B"]), rules, price=True)
    assert not study.eligible(trade(z="A", c=[" ", "B"]), rules, price=True)
    assert not study.eligible(trade(c=["@", "W"]), rules, price=True)
    assert study.eligible(trade(c=["@", "W"]), rules)


@pytest.mark.parametrize("code", ["M", "Q", "9"])
def test_official_reference_records_never_add_volume_on_either_tape(code):
    rules = study.protocol()["rules"]
    assert not study.eligible(trade(c=["@", code]), rules)
    assert not study.eligible(trade(z="A", c=[" ", code]), rules)


def test_correction_state_is_separate_from_condition_eligibility():
    rules = study.protocol()["rules"]
    assert not study.eligible(trade(u="incorrect"), rules)
    assert not study.eligible(trade(u="canceled"), rules)
    assert study.eligible(trade(u="corrected"), rules)
    with pytest.raises(ValueError, match="update"):
        study.eligible(trade(u="new_unknown"), rules)


def test_reconstruction_retains_unexplained_published_residual_and_absent_minute():
    case = {"symbol": "MANH", "date": "2025-02-25", "tape": "C"}
    rows = [trade(), trade(i=2, t="2025-02-25T14:31:00Z", c=["@", "I"], s=5)]
    bars = [{"symbol": "MANH", "t": "2025-02-25T14:30:00Z", "v": 20}]
    old = {"alpaca_daily_volume": 25, "published_volume": 24, "ibkr_regular_volume": 20}
    result, _ = study.summarize_case(case, rows, bars, old, study.protocol()["rules"])
    assert result["eligible_minus_archived_daily"] == 0
    assert result["eligible_minus_published"] == 1
    assert result["absent_minute_volume"] == 5
    assert result["absent_minutes_without_price_trade"] == 1


def test_resume_ignores_failed_partial_page_but_preserves_complete_seconds(tmp_path):
    case = {"symbol": "FIX", "date": "2025-02-25", "tape": "A"}
    start, _ = study.window(case)
    complete = [{"time": start + 10, "price": "100", "size": "4"}] * 2
    good = retain(tmp_path, "one", json.dumps({"rows": complete}).encode())
    good.update(case=study.key(case), direction="forward", complete_callback=True, error_codes=[], row_count=2,
                parameters={"startDateTime": "20250225 05:00:00 UTC"})
    failed = retain(tmp_path, "two", json.dumps({"rows": [{"time": start + 11}]}).encode())
    failed.update(case=study.key(case), direction="forward", complete_callback=False, error_codes=[])
    assert saved_progress(tmp_path, {"requests": [good, failed]}, case) == (start + 11, 1, False, False)
    good["parameters"]["startDateTime"] = "20250225 05:00:01 UTC"
    with pytest.raises(ValueError, match="Gap"):
        saved_progress(tmp_path, {"requests": [good]}, case)


def test_empty_forward_completion_requires_separate_tail_record(tmp_path):
    case = {"symbol": "FIX", "date": "2025-02-25", "tape": "A"}
    empty = retain(tmp_path, "empty", b'{"rows": []}')
    empty.update(case=study.key(case), direction="forward", complete_callback=True, error_codes=[], row_count=0,
                 parameters={"startDateTime": "20250225 05:00:00 UTC"})
    state = saved_progress(tmp_path, {"requests": [empty]}, case)
    assert state[2:] == (True, False)
