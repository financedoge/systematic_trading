"""Exact residuals, corrected records and scoped reuse for the five-case audit."""
from collections import Counter
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("large_volume_reconcile", SCRIPTS / "reconcile_large_volume_sources.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)
sys.path.pop(0)


def trade(size=100, **updates):
    return {"t":"2024-04-29T14:00:00Z", "p":100, "s":size, "c":[" "], "z":"A", **updates}


def test_frozen_selection_is_five_prior_outliers_and_every_case_has_an_ib_control():
    p = study.scope.protocol()
    assert p["cases"] == p["ibkr_tick_controls"]
    assert [(c["symbol"], c["date"]) for c in p["cases"]] == [
        ("RPM","2024-04-29"), ("UTHR","2024-06-25"), ("UTHR","2024-06-21"),
        ("FIX","2025-02-07"), ("FIX","2025-02-04")]


def test_reference_markers_and_invalid_updates_are_not_volume_and_old_series_is_not_repaired():
    p = study.scope.protocol()
    old = dict(sip_raw_volume=130, published_raw_volume=140)
    rows = [trade(), trade(30, c=[" ","I"],u="corrected"), trade(400,u="canceled"),
            trade(200,u="incorrect"), trade(1000,c=["M"]), trade(0,c=["9"],u=None)]
    result, _ = study.compare_case(p["cases"][0], rows, old, p["rules"])
    assert result["eligible_volume"] == 130
    assert result["trades_minus_sip_daily"] == 0
    assert result["trades_minus_published"] == -10
    assert old == dict(sip_raw_volume=130, published_raw_volume=140)
    assert result["source_update_states"]["no_update_flag"] == 3


def test_unmatched_multisets_keep_duplicate_occurrences_without_forcing_time_matches():
    rows = [trade(10,i=1), trade(10,i=2), trade(20,i=3)]
    counts = Counter({study.signature(rows[0],"alpaca"):1})
    assert study.residual_records(rows,counts,"alpaca") == rows[:1]
    assert counts.total() == 1
    assert study.signature(trade(10,c=["@"]),"alpaca") == study.signature(
        dict(price="100.000",size="10",special_conditions=" "),"ibkr")


@pytest.mark.parametrize("value", ["0.1", "-1", "NaN", "Infinity"])
def test_ib_fractional_or_invalid_size_is_not_silently_truncated(value):
    with pytest.raises(ValueError):
        study.strict_shares(value)


def test_full_day_independent_volume_difference_is_retained():
    p = study.scope.protocol()
    old = dict(sip_raw_volume=100,published_raw_volume=80,ibkr_regular_volume=101)
    ib = [dict(time=1714399200,price="100",size="101",special_conditions=" ",unreported=False)]
    result, detail = study.compare_case(p["cases"][0],[trade()],old,p["rules"],ib)
    control = result["independent_ibkr"]
    assert control["delta_vs_alpaca_eligible"] == 1
    assert control["delta_vs_published"] == 21
    assert not control["price_size_condition_multisets_exact"]
    assert len(detail["alpaca_unmatched"]) == len(detail["ibkr_unmatched"]) == 1
