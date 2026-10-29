import numpy as np
import pytest

from systematic_trading.research import breakout_revisit as baseline
from systematic_trading.research import post_breakout_trend as trend
from systematic_trading.research import range_lifecycle as old
from test_breakout_revisit import fixture
from test_range_lifecycle import synthetic


def test_support_excludes_current_close_and_requires_post_entry_history():
    c = np.exp(np.arange(20) * .01)
    value = trend.rising_support(c, 3, 10, 21, 1., .01)
    c[10:] *= .5
    assert value == trend.rising_support(c, 3, 10, 21, 1., .01)
    assert trend.rising_support(c, 8, 10, 21, 1., .01) is None
    assert trend.rising_support(c[::-1].copy(), 0, 5, 21, 1., .01) is None


@pytest.mark.parametrize("delay", [0, 1])
def test_baseline_is_exact_and_new_rule_is_prefix_causal(delay):
    f = old.Features.build(synthetic(n=800))
    vector = baseline.simple_prepared(f, lookback=21)["parameters"]
    p = trend.prepare(f, vector)
    a, b = baseline.simulate(f, p, delay=delay), trend.simulate(f, p, delay=delay)
    for key in ("nav", "desired", "held", "stop"):
        np.testing.assert_allclose(a[key], b[key], equal_nan=True, atol=0, rtol=0)
    p = trend.prepare(f, vector, dict(lookback=21, buffer_atr=1.))
    a = trend.simulate(f, p, delay=delay)
    b = trend.simulate(f, p, delay=delay, end=600)
    for key in ("nav", "desired", "held", "stop", "trend_level"):
        np.testing.assert_allclose(a[key][:600], b[key][:600], equal_nan=True, atol=0, rtol=0)
    for e in a["episodes"]:
        end = e.get("exit_signal", len(f.close) - 1)
        stops = a["stop"][e["entry_index"]:end + 1]
        assert np.all(np.diff(stops) >= 0)


def test_normal_pullback_stays_but_support_failure_sells_next_open():
    f, p = fixture((100, 101, 102, 103, 104, 105, 106, 107, 106.5, 103, 102, 101))
    p["trend_rule"] = dict(lookback=21, buffer_atr=2.)
    p["parameters"][15] = 1e12
    sim = trend.simulate(f, p, start=1)
    assert sim["held"][8] and sim["desired"][8]
    assert sim["events"][1] == dict(day=9, side="sell", fill=10)
    assert np.isfinite(sim["trend_level"][7])


def test_initial_risk_stop_remains_before_trend_exists():
    f, p = fixture()
    p["trend_rule"] = dict(lookback=21, buffer_atr=1.)
    p["parameters"][15] = 1e12
    sim = trend.simulate(f, p, start=1)
    assert sim["events"][1] == dict(day=2, side="sell", fill=3)
    assert np.isnan(sim["trend_level"][2])
