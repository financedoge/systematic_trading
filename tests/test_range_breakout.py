import numpy as np
import pytest

from systematic_trading.research.range_breakout import (
    BreakoutSpec, adaptive_features, features, lifecycle, slot_weights, adopted_indices,
)


def example():
    t = np.arange(820)
    close = 100+np.sin(t/6)
    close[790:800] = np.arange(103, 113)
    close[800:] = np.linspace(112, 85, 20)
    opens = np.r_[close[0], close[:-1]]
    volume = np.ones(len(close))*1000
    volume[790:800] = 3000
    return close, opens, np.maximum(close, opens)+.5, np.minimum(close, opens)-.5, volume


def test_three_close_confirmation_never_buys_initial_crossing():
    result = lifecycle(*example(), BreakoutSpec())
    assert result['entries']
    entry = next(t for t in result['entries'] if t >= 790)
    assert entry == 792
    assert not result['active'][790] and not result['active'][791]
    assert result['active'][792]
    assert result['episodes'][-1]['fill_index'] == 793


@pytest.mark.parametrize('lookback', ['adaptive', 252, 504])
def test_prefix_invariance_and_future_open_independence(lookback):
    arrays = example()
    spec = BreakoutSpec(lookback)
    full = lifecycle(*arrays, spec)
    prefix = lifecycle(*(x[:793] for x in arrays), spec)
    for key in ('active', 'score', 'state', 'heat'):
        np.testing.assert_array_equal(full[key][:793], prefix[key])
    altered = [a.copy() for a in arrays]
    altered[1][793:] *= 2
    later = lifecycle(*altered, spec)
    np.testing.assert_array_equal(full['active'][:793], later['active'][:793])


def test_price_breakout_does_not_imply_volume_confirmation():
    arrays = list(example())
    arrays[-1][:] = 1000
    confirmed = lifecycle(*arrays, BreakoutSpec(volume_confirmation=True))
    price_only = lifecycle(*arrays, BreakoutSpec(volume_confirmation=False))
    assert not confirmed['entries']
    assert price_only['entries']


def test_single_day_breakout_fails_confirmation():
    arrays = list(example())
    arrays[0][791:] = 100
    arrays[2] = np.maximum(arrays[0], arrays[1])+.5
    arrays[3] = np.minimum(arrays[0], arrays[1])-.5
    result = lifecycle(*arrays, BreakoutSpec())
    assert not result['entries']
    assert result['failed_confirmations'] > 0


def test_stops_ratchet_and_a_gap_cannot_fill_at_the_stop():
    arrays = list(example())
    result = lifecycle(*arrays, BreakoutSpec())
    episode = result['episodes'][-1]
    stop = result['stop'][episode['fill_index']:episode['exit_signal']+1]
    assert np.all(np.diff(stop) >= -1e-12)
    assert episode['heated']
    # Exit is a close decision, fill is a subsequent observation, never the threshold.
    k = episode['exit_signal']
    arrays[1][k+1] = 70
    delayed = lifecycle(*arrays, BreakoutSpec())
    assert delayed['episodes'][-1]['exit_signal'] == k
    assert arrays[1][k+1] < result['stop'][k]


def test_adaptive_range_uses_short_history_and_longest_available_range():
    t = np.arange(250)
    c = 100+np.sin(t/4)
    f = adaptive_features(c, c+.5, c-.5, np.ones(250))
    assert f['tight'][100:250].any()
    for i in np.flatnonzero(f['tight']):
        qualifying = [k for k in (42, 63, 126, 252, 504, 756)
                      if features(c, c+.5, c-.5, np.ones(250), k)['tight'][i]]
        assert f['duration'][i] == max(qualifying)


def test_missing_raw_volume_is_not_silently_substituted():
    arrays = list(example())
    arrays[-1][400] = np.nan
    with pytest.raises(ValueError, match='Unsupported'):
        lifecycle(*arrays, BreakoutSpec())


def test_unused_slots_and_overlap_stay_cash():
    w = slot_weights(np.array([5, 4, 3]), np.array([.1, .2, .3]), np.ones(3, bool),
                     ['SPY', 'XLK', 'GLD'], {frozenset(('SPY', 'XLK'))})
    assert w[1] == 0
    assert w.sum() == pytest.approx(.98*2/6)
    assert w.max() <= .45


def test_event_distance_includes_cash_and_uses_last_adopted_anchor():
    days = ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09']
    weights = np.array([[.20], [.24], [.26], [.26], [.26]])
    assert adopted_indices(weights, days, days[1], 'event') == [0, 2]
    assert adopted_indices(weights, days, days[1], 'monthly') == [0]


def test_small_risk_exit_overrides_event_threshold():
    days = ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08']
    weights = np.array([[.03], [0], [0], [0]])
    exits = np.array([[False], [True], [False], [False]])
    assert adopted_indices(weights, days, days[1], 'event', exits=exits) == [0, 1]


def test_heat_rule_never_delays_exit_on_same_path():
    a = example()
    ordinary = lifecycle(*a, BreakoutSpec(heat_exit=False))
    heat = lifecycle(*a, BreakoutSpec(heat_exit=True))
    assert heat['episodes'][-1]['exit_signal'] <= ordinary['episodes'][-1]['exit_signal']
