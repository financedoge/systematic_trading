import numpy as np
import pytest

from systematic_trading.research import breakout_adaptive as a
from systematic_trading.research import breakout_revisit as base
from systematic_trading.research import range_lifecycle as old
from test_breakout_revisit import fixture
from test_range_lifecycle import synthetic


@pytest.mark.parametrize("delay", [0, 1])
def test_unmodified_engine_exact_parity(delay):
    f = old.Features.build(synthetic(n=900))
    p = base.simple_prepared(f, lookback=21, trail=2)
    x, y = base.simulate(f, p, delay=delay), a.simulate(f, p, delay=delay)
    for k in ("nav", "desired", "held", "stop", "level"):
        np.testing.assert_allclose(x[k], y[k], equal_nan=True, atol=0, rtol=0)
    assert x["events"] == y["events"]
    assert x["episodes"] == y["episodes"]


def test_gate_blocks_confirmation_and_continuation_but_not_binding_order():
    f, p = fixture((100, 101, 103, 104, 105, 106, 107, 108))
    p["entry_allowed"] = np.zeros(len(f.close), bool)
    assert not a.simulate(f, p, start=1)["events"]
    p["entry_allowed"][1] = True
    result = a.simulate(f, p, start=1, delay=1)
    assert result["held"][3]
    # Two-close confirmation is cancelled by the gate at the second close.
    p["parameters"][6] = 2
    assert not a.simulate(f, p, start=1)["events"]


def test_first_lower_arms_after_gain_and_fills_at_delayed_open():
    f, p = fixture((100, 101, 99.5, 102, 101, 100.5, 98, 97))
    p["exit_mode"] = "first_lower"
    p["parameters"][15] = 100
    result = a.simulate(f, p, start=1)
    assert result["events"][1] == dict(day=4, side="sell", fill=5)
    assert result["episodes"][0]["exit_reason"] == "first_lower"
    delayed = a.simulate(f, p, start=1, delay=1)
    assert delayed["events"][1] == dict(day=4, side="sell", fill=6)


def test_breakeven_is_level_not_guaranteed_fill():
    f, p = fixture((100, 101, 102, 99, 80, 81, 82, 83))
    p["exit_mode"] = "breakeven"
    p["parameters"][15] = 100
    f.open[4] = 80
    result = a.simulate(f, p, start=1, cost_bp=0)
    assert result["stop"][2] == 100
    assert result["nav"][4] == .8


def test_prior_boxes_and_all_decisions_causal():
    data = synthetic(n=900)
    changed = {k: v.copy() for k, v in data.items()}
    for k in ("open", "high", "low", "close"):
        changed[k][700:] *= 2
    f, g = old.Features.build(data), old.Features.build(changed)
    vector = base.simple_prepared(f)["parameters"]
    for name in a.range_menu("short")[1:]:
        b, c = a.boxes(f, name), a.boxes(g, name)
        for k in b:
            np.testing.assert_allclose(b[k][:701], c[k][:701], equal_nan=True)
        for mode in a.EXIT_MODES:
            p = a.prepare(f, vector, name, "avoid_down", mode, box_cache={name: b})
            q = a.prepare(g, vector, name, "avoid_down", mode, box_cache={name: c})
            x, y = a.simulate(f, p), a.simulate(g, q)
            for k in ("desired", "held", "stop", "nav"):
                np.testing.assert_allclose(x[k][:700], y[k][:700], equal_nan=True)


def test_regime_uses_only_available_history():
    c = np.exp(np.arange(400) / 1000)
    assert a.regimes(c)[-1] == "up"
    assert a.regimes(c[::-1])[-1] == "down"
    assert a.regimes(c)[0] == "unknown"
