"""Diagnostic calculations must remain causal and explain the frozen rules."""
import numpy as np
import pytest

from systematic_trading.research.range_joint import History, v1_anchor
from systematic_trading.research.range_trace import range_rows, trace


def sample():
    t = np.arange(500)
    c = 100 + np.sin(t / 6)
    c[400:430] = 106
    c[430:] = np.linspace(108, 150, 70)
    o = np.r_[c[0], c[:-1]]
    return dict(close=c, open=o, high=np.maximum(c, o) + .5,
                low=np.minimum(c, o) - .5, volume=np.full(len(c), 1000.),
                days=t.astype(str))


def rule():
    p = v1_anchor()
    p[3:5] = [0, 3]
    p[14] = 0
    p[17] = 10
    p[18:20] = -1
    p[23] = 6
    p[24] = 0
    p[30:33] = [1, 4, 11]
    return p


def test_range_uses_prior_prices_and_exact_log_quantiles():
    a = sample(); p = rule(); p[5] = 3
    h = History.build(a)
    r = range_rows(h, p, 400)[0]
    x = np.log(a['close'][379:400])
    assert (r['start'], r['end'], r['sessions']) == (379, 399, 21)
    np.testing.assert_allclose([r['lower'], r['upper']], np.exp(np.quantile(x, [.2, .8])))
    assert r['drift'] == pytest.approx(abs(np.median(x[-10:]) - np.median(x[:10])))
    assert r['short_vol'] == pytest.approx(np.std(np.diff(np.log(a['close']))[392:399], ddof=1))
    # A crossing session's price must not enter its own preceding range.
    changed = {k: v.copy() for k, v in a.items()}
    changed['close'][400:] *= 2
    changed['high'][400:] *= 2
    changed['low'][400:] *= 2
    after = range_rows(History.build(changed), p, 400)[0]
    for key in ('lower', 'upper', 'width', 'drift', 'short_vol', 'long_vol'):
        assert after[key] == pytest.approx(r[key])


def test_confirmation_virtual_fill_and_time_exit_explain_why_stop_did_not_fire():
    a = sample(); rows, episodes = trace(History.build(a), rule())
    ep = next(e for e in episodes if e['crossing'] == 400)
    assert ep['confirmation'] == 402
    assert ep['virtual_entry'] == 403
    assert ep['exit_signal'] == 408  # entry age 0, five sessions afterward
    assert ep['exit_reason'] == 3
    r = rows[408]
    assert r['time_failed'] and not r['trail_enabled']
    assert a['close'][408] > r['stop']
    assert not r['close_below_stop']
    assert not rows[407]['time_failed']
    assert rows[409]['state_before'] == 'cooldown'


@pytest.mark.parametrize('basis', [0, 1, 2])
def test_prefix_trace_and_trailing_levels_never_use_future_data(basis):
    a = sample(); p = rule(); p[20] = basis; p[23] = 0; p[30] = 0
    full, _ = trace(History.build(a), p)
    cut, _ = trace(History.build({k: v[:440] for k, v in a.items()}), p)
    for r, q in zip(full[:440], cut, strict=True):
        for k in r:
            if isinstance(r[k], (float, np.floating)):
                np.testing.assert_allclose(r[k], q[k], equal_nan=True)
            else:
                assert r[k] == q[k], k
    live = [r for r in full if r['virtual_entry'] == 403]
    assert len(live) > 1
    assert np.all(np.diff([r['ratchet'] for r in live]) >= 0)


def test_cancelled_confirmation_keeps_its_original_range_and_records_failure():
    a = sample(); a['close'][401] = 100; a['low'][401] = 99
    rows, episodes = trace(History.build(a), rule())
    assert rows[400]['action'] == 'breakout_cross'
    assert rows[401]['action'] == 'confirmation_cancel_price'
    assert rows[401]['frozen_upper'] == rows[400]['frozen_upper']
    assert rows[401]['state_after'] == 'seeking'
    assert not any(e['crossing'] == 400 for e in episodes)


def test_intraday_low_is_not_a_close_stop_trigger():
    a = sample(); p = rule(); p[30] = 0
    a['low'][404] = 50
    rows, _ = trace(History.build(a), p)
    assert a['low'][404] < rows[404]['stop'] < a['close'][404]
    assert rows[404]['active']
    assert rows[404]['exit_reason'] == 0
