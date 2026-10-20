"""Tests specific to the two predeclared structural domains."""
from __future__ import annotations

import numpy as np

from systematic_trading.research import range_lifecycle as rl


def synthetic_long(n=1500, seed=11):
    rng = np.random.default_rng(seed)
    logp = np.empty(n)
    logp[0] = np.log(100.0)
    drift = np.zeros(n)
    drift[400:560] = 0.0025
    drift[560:700] = -0.0035
    drift[900:1200] = 0.0020
    for i in range(1, n):
        logp[i] = logp[i - 1] + drift[i] + rng.normal(0, 0.006)
    close = np.exp(logp)
    open_ = close * (1 + rng.normal(0, 0.001, n))
    high = np.maximum(close, open_) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(close, open_) * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    days = np.datetime64("2004-01-01", "D") + np.arange(n).astype("timedelta64[D]")
    return dict(open=open_, high=high, low=low, close=close, volume=volume, days=days)


def test_structural_domains_are_declared_and_well_formed():
    assert rl.SHORT_SPEC.windows == (21, 42, 63, 126, 252, 504)
    assert min(rl.LONG_SPEC.windows) >= 126
    assert max(rl.LONG_SPEC.windows) == 756
    assert len(rl.SHORT_SPEC.parameters) == len(rl.LONG_SPEC.parameters) == 27
    assert rl.SHORT_SPEC.names == rl.LONG_SPEC.names
    short_mid = rl.SHORT_SPEC.canonical(rl.SHORT_SPEC.bounds.mean(axis=1))
    long_mid = rl.LONG_SPEC.canonical(rl.LONG_SPEC.bounds.mean(axis=1))
    assert rl.SHORT_SPEC.describe(short_mid)["domain"] == "short_range"
    assert rl.LONG_SPEC.describe(long_mid)["domain"] == "long_range"
    # Long-domain minimum stops and trails are structurally larger than the short domain.
    names = list(rl.SHORT_SPEC.names)
    stop = names.index("initial_stop_atr")
    trail = names.index("trail_atr")
    assert rl.LONG_SPEC.bounds[stop, 1] > rl.SHORT_SPEC.bounds[stop, 1]
    assert rl.LONG_SPEC.bounds[trail, 1] > rl.SHORT_SPEC.bounds[trail, 1]


def test_long_domain_features_and_causality():
    data = synthetic_long()
    features = rl.Features.build(data, rl.LONG_SPEC)
    assert features.spec is rl.LONG_SPEC
    long_mid = rl.LONG_SPEC.canonical(rl.LONG_SPEC.bounds.mean(axis=1))
    prepared = rl.prepare(features, long_mid)
    cut = 1000
    shocked = {k: np.array(v, copy=True) for k, v in data.items()}
    shocked["close"][cut:] *= 2.5
    shocked["open"][cut:] *= 2.5
    shocked["high"][cut:] *= 2.5
    shocked["low"][cut:] *= 2.0
    changed = rl.prepare(rl.Features.build(shocked, rl.LONG_SPEC), long_mid)
    for key in ("L", "upper", "lower", "width", "boundary"):
        np.testing.assert_allclose(changed[key][:cut], prepared[key][:cut], equal_nan=True)
    np.testing.assert_array_equal(changed["cross"][:cut], prepared["cross"][:cut])
    sim = rl.simulate(features, prepared, start=300, cost_bp=5.0)
    assert np.isfinite(sim["nav"][300:]).all()
    assert len(sim["episodes"]) >= 0


def test_short_domain_remains_the_default():
    data = synthetic_long()
    default = rl.Features.build(data)
    explicit = rl.Features.build(data, rl.SHORT_SPEC)
    assert default.spec is rl.SHORT_SPEC
    np.testing.assert_allclose(default.close, explicit.close)
    np.testing.assert_allclose(default.upper[0.05][63], explicit.upper[0.05][63], equal_nan=True)
