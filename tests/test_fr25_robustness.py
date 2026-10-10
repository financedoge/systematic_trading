"""P4.14 Part A — FR25 robustness attribution."""
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pytest

from systematic_trading.research import fr25_robustness as robust


def _arm(nav, decisions):
    return dict(complete=True, nav=[dict(date=d, nav=str(v)) for d, v in nav],
                decisions=decisions)


def _decisions(dates, weights):
    return {d: dict(targets=[dict(symbol=s, target_weight=str(w)) for s, w in row.items()])
            for d, row in zip(dates, weights)}


def _write_study(root, nav_candidate, nav_control, decisions_candidate, decisions_control):
    (root / "python").mkdir(parents=True, exist_ok=True)
    for arm, nav, dec in (("FR25", nav_candidate, decisions_candidate),
                          ("CP", nav_control, decisions_control)):
        payload = _arm(nav, dec)
        (root / "python" / f"{arm}-cost5-delay0-evaluation.json").write_text(
            json.dumps(payload), encoding="utf8")
    (root / "protocol.json").write_text(json.dumps({"version": "test"}), encoding="utf8")


# --- changed selections ------------------------------------------------------

def test_changed_decisions_detects_only_real_weight_moves():
    dates = ["2026-01-02", "2026-02-02"]
    candidate = _arm([("2026-01-02", 100), ("2026-02-02", 100)], _decisions(
        dates, [{"SPY": Decimal("0.5"), "TLT": Decimal("0.5")},
                {"SPY": Decimal("0.4"), "TLT": Decimal("0.6")}]))
    control = _arm([("2026-01-02", 100), ("2026-02-02", 100)], _decisions(
        dates, [{"SPY": Decimal("0.5"), "TLT": Decimal("0.5")},
                {"SPY": Decimal("0.5"), "TLT": Decimal("0.5")}]))
    changes = robust.changed_decisions(candidate, control)
    assert [c["decision"] for c in changes] == ["2026-02-02"]
    assert changes[0]["added"] == ["TLT"] and changes[0]["removed"] == ["SPY"]


def test_changed_decisions_rejects_a_mismatched_calendar():
    candidate = _arm([("2026-01-02", 100)], _decisions(["2026-01-02"], [{"SPY": Decimal("1")}]))
    control = _arm([("2026-01-02", 100)], _decisions(["2026-03-02"], [{"SPY": Decimal("1")}]))
    with pytest.raises(ValueError, match="decision calendar"):
        robust.changed_decisions(candidate, control)


# --- yearly ------------------------------------------------------------------

def test_yearly_excess_excludes_a_partial_final_year():
    # Two complete calendar years, then a stub ending mid-year.
    dates = ["2024-01-02", "2024-12-30", "2025-01-02", "2025-12-30", "2026-01-02", "2026-06-01"]
    nav = [100, 110, 110, 121, 121, 130]
    rows = robust.yearly_excess(dates, nav, [100, 105, 105, 110, 110, 115])
    by_year = {r["year"]: r for r in rows}
    assert by_year["2024"]["complete"] is True
    assert by_year["2025"]["complete"] is True
    assert by_year["2026"]["complete"] is False  # window ends mid-year
    assert by_year["2024"]["excess"] == pytest.approx((110 / 100) - (105 / 100))
    assert by_year["2026"]["last_session"] == "2026-06-01"


# --- tiles -------------------------------------------------------------------

def test_tiles_are_disjoint_and_telescope_to_the_total():
    dates = [f"2026-0{m}-01" for m in range(1, 7)]
    candidate = [100, 101, 103, 102, 106, 110]
    control = [100, 100, 101, 101, 102, 103]
    changes = [dict(decision="2026-02-01", changed=["SPY"], added=["SPY"], removed=["TLT"]),
               dict(decision="2026-04-01", changed=["SPY"], added=["TLT"], removed=["SPY"])]
    out = robust.leave_one_out(dates, candidate, control, changes)
    tiles = out["contributions"]
    assert len(tiles) == 2
    total = out["total_log_difference"]
    assert out["changed_tiles_log_difference"] + out["pre_change_log_difference"] == pytest.approx(total)
    assert sum(t["log_difference"] for t in tiles) == pytest.approx(out["changed_tiles_log_difference"])
    # tiles must not overlap and must run forward in time
    ordered = sorted(tiles, key=lambda t: t["decision"])
    assert ordered[0]["through"] <= ordered[1]["decision"]


def test_tile_starts_the_session_after_the_decision():
    """A decision is filled at the next open, so the decision session itself is not attributable."""
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    candidate = [100.0, 100.0, 121.0]      # the whole move happens after the decision session
    control = [100.0, 100.0, 100.0]
    changes = [dict(decision="2026-01-01", changed=["SPY"], added=["SPY"], removed=["TLT"])]
    out = robust.leave_one_out(dates, candidate, control, changes)
    assert out["contributions"][0]["log_difference"] == pytest.approx(np.log(1.21))


# --- bootstrap ---------------------------------------------------------------

def test_monthly_excess_uses_month_end_to_month_end():
    dates = ["2026-01-30", "2026-02-27", "2026-03-31"]
    monthly = robust.monthly_excess(dates, [100, 110, 121], [100, 100, 100])
    assert monthly["2026-02"] == pytest.approx(0.10)
    assert monthly["2026-03"] == pytest.approx(0.10)
    assert "2026-01" not in monthly  # no prior month to difference against


# --- verdict -----------------------------------------------------------------

def _attribution(total, tiles):
    return dict(total_log_difference=total, total_return_difference=total,
                changed_tiles_log_difference=sum(tiles),
                pre_change_log_difference=total - sum(tiles),
                contributions=[dict(decision=f"d{i}", log_difference=v) for i, v in enumerate(tiles)])


def _years(excesses, complete=True):
    return [dict(year=str(2020 + i), excess=e, complete=complete) for i, e in enumerate(excesses)]


def _blocks(lower):
    return {b: dict(n=60, mean_annual=0.01, ci95=[lower, 0.03], p=0.1) for b in (3, 6, 12)}


def test_verdict_rejects_when_the_aggregate_is_negative():
    verdict = robust.assess(_attribution(-0.01, [-0.01]), _years([0.01] * 5), _blocks(0.001))
    assert verdict["status"] == "reject"


def test_verdict_rejects_when_one_selection_carries_everything():
    verdict = robust.assess(_attribution(0.05, [0.06, -0.01]), _years([0.01] * 5), _blocks(0.001))
    assert verdict["status"] == "reject"
    assert verdict["leave_one_out_test"] is False


def test_verdict_is_inconclusive_when_the_interval_spans_zero():
    verdict = robust.assess(_attribution(0.05, [0.03, 0.02]), _years([0.01] * 5), _blocks(-0.001))
    assert verdict["status"] == "inconclusive"
    assert verdict["years_test"] and verdict["leave_one_out_test"] and not verdict["interval_test"]


def test_verdict_fails_the_years_test_below_two_thirds():
    verdict = robust.assess(_attribution(0.05, [0.03, 0.02]), _years([0.01, -0.01, -0.01]), _blocks(0.001))
    assert verdict["years_test"] is False
    assert verdict["status"] == "inconclusive"


def test_verdict_can_never_be_preserve_without_the_placebo():
    """Part B is unrun, so a full preserve must be impossible."""
    verdict = robust.assess(_attribution(0.05, [0.03, 0.02]), _years([0.01] * 5), _blocks(0.001))
    assert verdict["placebo_test"] is None
    assert verdict["status"] != "preserve"
    assert "never as preserved" in verdict["placebo_note"]


def test_verdict_preserves_only_when_every_check_passes_including_placebo():
    verdict = robust.assess(_attribution(0.05, [0.03, 0.02]), _years([0.01] * 5), _blocks(0.001),
                            placebo_percentile=0.04)
    assert verdict["status"] == "preserve"


# --- loading -----------------------------------------------------------------

def test_load_requires_a_complete_shared_calendar(tmp_path):
    _write_study(tmp_path, [("2026-01-02", 100)], [("2026-03-02", 100)],
                 _decisions(["2026-01-02"], [{"SPY": Decimal("1")}]),
                 _decisions(["2026-03-02"], [{"SPY": Decimal("1")}]))
    with pytest.raises(ValueError, match="valuation calendar"):
        robust.load(tmp_path)


def test_load_reports_input_hashes(tmp_path):
    dates = ["2026-01-02", "2026-02-02"]
    decisions = _decisions(dates, [{"SPY": Decimal("1")}, {"SPY": Decimal("1")}])
    _write_study(tmp_path, [("2026-01-02", 100), ("2026-02-02", 100)],
                 [("2026-01-02", 100), ("2026-02-02", 100)], decisions, decisions)
    data = robust.load(tmp_path)
    assert len(data["hashes"]) == 2 and all(len(v) == 64 for v in data["hashes"].values())
    assert data["protocol_sha256"]


def test_load_rejects_an_incomplete_replay(tmp_path):
    dates = ["2026-01-02"]
    decisions = _decisions(dates, [{"SPY": Decimal("1")}])
    _write_study(tmp_path, [("2026-01-02", 100)], [("2026-01-02", 100)], decisions, decisions)
    path = tmp_path / "python" / "FR25-cost5-delay0-evaluation.json"
    payload = json.loads(path.read_text(encoding="utf8"))
    payload["complete"] = False
    path.write_text(json.dumps(payload), encoding="utf8")
    with pytest.raises(ValueError, match="not marked complete"):
        robust.load(tmp_path)
