"""Focused tests for the causal range-lifecycle reference implementation."""
from __future__ import annotations

import numpy as np
import pytest

from systematic_trading.research import range_lifecycle as rl


def synthetic(n=1200, seed=7):
    rng = np.random.default_rng(seed)
    # regimes: quiet range, breakout trend, overheated reversal, new range
    logp = np.empty(n)
    logp[0] = np.log(100.0)
    drift = np.zeros(n)
    drift[250:330] = 0.004
    drift[330:400] = -0.006
    drift[520:700] = 0.003
    drift[700:760] = -0.005
    for i in range(1, n):
        logp[i] = logp[i - 1] + drift[i] + rng.normal(0, 0.006)
    close = np.exp(logp)
    open_ = close * (1 + rng.normal(0, 0.001, n))
    high = np.maximum(close, open_) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(close, open_) * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    days = np.datetime64("2010-01-01", "D") + np.arange(n).astype("timedelta64[D]")
    return dict(open=open_, high=high, low=low, close=close, volume=volume, days=days)


def canonical_vector():
    return rl.canonical([0.15, 1, 0.6, 1.2, 1, 0.25, 2, 1, 1.8, 0, 8.0, 1.0, 0, 5.0, 0.10, 1.0,
                         1, 6.0, 2.0, 1.0, 0.6, 3, 2.0, 10, 1, 1.0, 3])


def test_parameter_canonicalization_bounds_and_integrality():
    p = rl.canonical(np.full(len(rl.PARAMETERS), -999.0))
    assert np.all(p >= rl.BOUNDS[:, 0] - 1e-12)
    assert np.all(p <= rl.BOUNDS[:, 1] + 1e-12)
    assert np.all(p[rl.INTEGRAL] == np.round(p[rl.INTEGRAL]))
    with pytest.raises(ValueError):
        rl.canonical(np.zeros(len(rl.PARAMETERS) - 1))


def test_features_are_prefix_consistent_and_truncation_preserves_history():
    data = synthetic()
    full = rl.Features.build(data)
    cut = full.truncated("2012-01-01")
    keep = len(cut.days)
    np.testing.assert_allclose(cut.close, full.close[:keep])
    for period in rl.ATR_PERIODS:
        np.testing.assert_allclose(cut.atr[period], full.atr[period][:keep], equal_nan=True)
    for tail in rl.TAILS:
        for length in rl.WINDOWS:
            np.testing.assert_allclose(cut.width[tail][length], full.width[tail][length][:keep],
                                       equal_nan=True)
            np.testing.assert_allclose(cut.upper[tail][length], full.upper[tail][length][:keep],
                                       equal_nan=True)
            np.testing.assert_allclose(cut.lower[tail][length], full.lower[tail][length][:keep],
                                       equal_nan=True)


def test_future_prices_do_not_change_past_signals():
    data = synthetic()
    baseline = rl.Features.build(data)
    p = canonical_vector()
    prepared = rl.prepare(baseline, p)
    cut = 800
    shocked = {k: np.array(v, copy=True) for k, v in data.items()}
    shocked["close"][cut:] *= 3.0
    shocked["open"][cut:] *= 3.0
    shocked["high"][cut:] *= 3.0
    shocked["low"][cut:] *= 1.5
    changed = rl.prepare(rl.Features.build(shocked), p)
    for key in ("L", "upper", "lower", "width", "drift", "vol_ratio", "boundary"):
        np.testing.assert_allclose(changed[key][:cut], prepared[key][:cut], equal_nan=True)
    np.testing.assert_array_equal(changed["cross"][:cut], prepared["cross"][:cut])


def test_simulation_nav_matches_with_and_without_trace():
    data = synthetic()
    features = rl.Features.build(data)
    p = canonical_vector()
    prepared = rl.prepare(features, p)
    plain = rl.simulate(features, prepared, start=252, cost_bp=5.0)
    trace = rl.simulate(features, prepared, start=252, cost_bp=5.0, trace=True)
    np.testing.assert_allclose(plain["nav"], trace["nav"], atol=1e-12)
    np.testing.assert_allclose(plain["weight"], trace["weight"], atol=1e-12)
    assert len(plain["episodes"]) == len(trace["episodes"])


def test_truncated_run_reproduces_prefix_nav_exactly():
    """A run that ends at the fit boundary must equal the full run's prefix."""
    data = synthetic()
    features = rl.Features.build(data)
    p = canonical_vector()
    cut = int(np.flatnonzero(features.days <= np.datetime64("2012-06-29"))[-1]) + 1
    short = rl.simulate(features, rl.prepare(features, p), start=252, end=cut, cost_bp=5.0)
    full = rl.simulate(features, rl.prepare(features, p), start=252, cost_bp=5.0)
    np.testing.assert_allclose(short["nav"][:cut], full["nav"][:cut], atol=1e-12)


def test_buy_hold_nav_is_a_linear_price_path():
    data = synthetic()
    features = rl.Features.build(data)
    bh = rl.buy_hold(features, 300, cost_bp=0.0)
    q = 1.0 / features.open[300]
    np.testing.assert_allclose(bh["nav"][300:], q * features.close[300:], atol=1e-12)
    assert np.isnan(bh["nav"][:300]).all()


def test_stop_is_executed_no_earlier_than_next_open_and_trace_levels_are_causal():
    data = synthetic()
    features = rl.Features.build(data)
    p = canonical_vector()
    prepared = rl.prepare(features, p)
    sim = rl.simulate(features, prepared, start=252, cost_bp=5.0, trace=True)
    for episode in sim["episodes"]:
        fill = episode["entry_index"]
        assert episode["confirmation"] < fill, "entry must follow the confirming close"
        if episode["exit_index"] is not None:
            assert episode["exit_index"] > episode["exit_signal"], "fill must follow exit signal"
        window = sim["stop"][fill:episode["exit_signal"] + 1 if episode["exit_signal"] is not None
                             else len(features.close)]
        assert np.isfinite(window).all()
        # trailing stop never moves down
        ratchet = window[1:][window[1:] >= window[:-1] - 1e-12]
        assert len(ratchet) > 0


def test_evaluate_is_deterministic_and_has_three_blocks():
    data = synthetic()
    features = rl.Features.build(data)
    p = canonical_vector()
    first = rl.evaluate(features, p, 252, len(features.days), cost_bp=5.0)
    second = rl.evaluate(features, p, 252, len(features.days), cost_bp=5.0)
    assert first["fitness"] == pytest.approx(second["fitness"], abs=1e-12)
    assert len(first["blocks"]) == 3
    assert first["full"]["sessions"] > 100
