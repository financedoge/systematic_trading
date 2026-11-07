"""Condition eligibility, corrections and occurrence-preserving comparisons."""
import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("csl_reconcile", SCRIPTS / "reconcile_csl_trades.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)
sys.path.pop(0)


def trade(**updates):
    return {"t": "2025-02-24T14:30:00Z", "i": 1, "x": "N", "z": "A",
            "p": 100, "s": 20, "c": [" "], **updates}


def test_odd_lots_count_in_volume_but_do_not_create_prices():
    row = trade(c=[" ", "I"])
    assert study.eligible(row)
    assert not study.eligible(row, price=True)


@pytest.mark.parametrize("condition", ["M", "Q", "9"])
def test_official_price_reference_is_not_double_counted_as_volume(condition):
    assert not study.eligible(trade(c=[" ", condition]))


def test_canceled_and_superseded_records_excluded_corrected_record_retained():
    assert not study.eligible(trade(u="canceled"))
    assert not study.eligible(trade(u="incorrect"))
    assert study.eligible(trade(u="corrected"))
    with pytest.raises(ValueError, match="correction"):
        study.eligible(trade(u="unrecognized"))


def test_unknown_condition_does_not_silently_enter_activity():
    with pytest.raises(ValueError, match="Unsupported"):
        study.eligible(trade(c=["8"]))


def test_repeated_same_second_price_size_keeps_multiplicity():
    ib = [{"time": study.timestamp_ns(trade()["t"]) // 10**9, "price": "100", "size": "20"}]
    result = study.multiset_match([trade(), trade(i=2)], ib)
    assert result["matched_volume"] == 20
    assert result["matched_occurrences"] == 1
    assert result["alpaca_unmatched_volume"] == 20


def test_clock_bins_keep_1600_minute_separate():
    assert study.clock_bucket(study.START + 34200 - 1) == "before_0930"
    assert study.clock_bucket(study.START + 34200) == "0930_to_before_1600"
    assert study.clock_bucket(study.START + 57600) == "1600_minute"
    assert study.clock_bucket(study.START + 57660) == "1601_onward"


def test_residual_patterns_do_not_change_primary_exact_match():
    a = [trade(), trade(i=2, p=101, s=5)]
    second = study.timestamp_ns(trade()["t"]) // 10**9
    ib = [{"time": second + 1, "price": "100", "size": "20"},
          {"time": second, "price": "101.0001", "size": "5"}]
    result = study.residual_diagnostics(a, ib)
    assert result["ib_one_second_later"]["occurrences"] == 1
    assert result["ib_price_0001_higher_same_second"]["occurrences"] == 1
    assert result["unexplained_alpaca_occurrences"] == 0
    assert study.multiset_match(a, ib)["matched_occurrences"] == 0
