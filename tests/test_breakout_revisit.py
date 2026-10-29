from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import breakout_revisit as br
from systematic_trading.research import range_lifecycle as old


def fixture(close=(100, 101, 80, 82, 83, 84, 85, 86), confirm=1):
    c = np.array(close, float)
    n = len(c)
    p = old.canonical([.15, 1, .6, 1.2, 1, 0, confirm, 0, 2, 0,
                       3, -1, 0, 6, .1, 6, 0, 6, 2, 1, .6, 0, 2, 0, 0, 1, 3])
    f = SimpleNamespace(close=c, open=np.full(n, 100.), volume=np.ones(n), spec=old.SHORT_SPEC)
    cross = np.zeros(n, bool)
    cross[1] = True
    prepared = dict(parameters=p, atr=np.ones(n), upper=np.full(n, 100.), boundary=np.full(n, 100.),
                    cross=cross, cross_idx=np.array([1]), lower=np.full(n, 90.), volmed=np.ones(n))
    return f, prepared


def test_one_close_confirms_and_entry_close_can_exit():
    f, p = fixture()
    result = br.simulate(f, p, start=1, cost_bp=0)
    assert result["events"][:2] == [dict(day=1, side="buy", fill=2), dict(day=2, side="sell", fill=3)]
    assert result["desired"][1] and not result["held"][1]
    assert result["held"][2] and not result["desired"][2]
    assert result["nav"][2] == .8
    # Frozen legacy reproduction misses this otherwise valid crossing entirely.
    assert not old.simulate(f, p, start=1)["episodes"]


def test_both_entry_and_exit_obey_extra_delay_and_gaps():
    f, p = fixture()
    f.open[5] = 70
    result = br.simulate(f, p, start=1, delay=1, cost_bp=0)
    assert result["events"][:2] == [dict(day=1, side="buy", fill=3), dict(day=3, side="sell", fill=5)]
    assert result["held"][4] and not result["held"][5]
    assert result["nav"][5] == pytest.approx(.7)


def test_confirmation_uses_final_confirmation_atr():
    f, p = fixture((100, 101, 102, 103, 104, 105, 106, 107), confirm=2)
    p["atr"][2] = 2
    result = br.simulate(f, p, start=1)
    assert result["episodes"][0]["confirmation"] == 2
    assert result["episodes"][0]["atr"] == 2
    assert result["stop"][3] == 94


def test_pending_orders_and_terminal_decisions_are_prefix_consistent():
    f, p = fixture()
    full = br.simulate(f, p, start=1, delay=1)
    for end in range(2, len(f.close)):
        prefix = br.simulate(f, p, start=1, end=end, delay=1)
        for field in ("desired", "held", "nav", "stop", "level"):
            np.testing.assert_allclose(prefix[field][:end], full[field][:end], equal_nan=True)
        assert prefix["events"] == [e for e in full["events"] if e["day"] < end]


def test_fees_funded_without_leverage():
    f, p = fixture((100, 101, 102, 103, 104, 105, 106, 107))
    result = br.simulate(f, p, start=1, cost_bp=20)
    assert result["nav"][2] == pytest.approx(1.02 / 1.002)
    assert result["nav"][2] <= 1.02


def test_all_trailing_stops_ratchet():
    f, p = fixture((100, 101, 103, 108, 107, 109, 108, 110))
    p["parameters"][15] = 0
    result = br.simulate(f, p, start=1)
    stops = result["stop"][result["held"]]
    assert np.all(np.diff(stops) >= 0)


def test_continuation_cannot_bypass_cooldown():
    f, p = fixture((100, 101, 80, 110, 120, 130, 140, 150))
    p["parameters"][24] = 1
    p["parameters"][23] = 3
    result = br.simulate(f, p, start=1)
    buys = [e for e in result["events"] if e["side"] == "buy"]
    assert buys[1]["day"] >= 6


def test_selector_vacancies_replacement_and_monthly_control():
    panel = dict(symbols=np.array(["A", "B", "C", "D", "BIL"]))
    active = np.ones((4, 5), bool)
    scores = np.array([[4, 3, 2, 1, 0], [1, 3, 4, 5, 0], [1, 3, 4, 5, 0], [-1, -1, -1, -1, 0.]])
    dynamic = br.select_targets(panel, active, scores, [0], slots=1)
    assert dynamic[2][0, 0] == .98
    assert dynamic[2][1, 3] == .98  # old incumbent is now outside top 3
    assert dynamic[2][-1, 4] == .98  # negative momentum -> cash proxy
    monthly = br.select_targets(panel, active, scores, [0], slots=1, clock="monthly")
    assert monthly[1].tolist() == [0]
    assert monthly[2][-1, 0] == .98
    sticky = br.select_targets(panel, active, scores, [0], slots=1, replace=False)
    assert sticky[2][1, 0] == .98


def test_momentum_and_simple_breakout_features_are_causal():
    from test_range_lifecycle import synthetic
    data = synthetic(n=800)
    baseline = old.Features.build(data)
    changed = {k: v.copy() for k, v in data.items()}
    for key in ("open", "high", "low", "close"):
        changed[key][600:] *= 2
    alternate = old.Features.build(changed)
    for f in (baseline, alternate):
        assert not br.simple_prepared(f)["cross"][:63].any()
    a = br.simulate(baseline, br.simple_prepared(baseline))
    b = br.simulate(alternate, br.simple_prepared(alternate))
    for key in ("desired", "held", "stop", "level", "nav"):
        np.testing.assert_allclose(a[key][:600], b[key][:600], equal_nan=True)
    np.testing.assert_allclose(br.momentum_score(baseline.close)[:600],
                               br.momentum_score(alternate.close)[:600], equal_nan=True)
