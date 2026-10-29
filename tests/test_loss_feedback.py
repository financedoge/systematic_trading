from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import coupled_trends, loss_feedback as m
from systematic_trading.research.strategy_health import ClosedTrade, Mode


def fixture(n=180):
    rng = np.random.default_rng(18)
    close = 100*np.exp(np.cumsum(rng.normal(-.001, .025, n)))
    f = SimpleNamespace(days=np.arange(n), open=close*np.exp(rng.normal(0, .006, n)), close=close)
    fast = np.tile([.1, .1, .8], (n, 1))
    fast[np.arange(n) % 12 >= 8] = [.8, .1, .1]
    p = dict(reset=.5, tight=3., wide=6., context=True)
    cl = dict(parameters=p, sigma=.02, aligned=np.arange(n) % 33 < 12,
              eligible=fast[:, 2] > .6, fast_down=fast[:, 0] > .6, fast_probability=fast,
              counter=np.zeros(n, bool))
    return f, cl


@pytest.mark.parametrize('delay', [0, 1])
@pytest.mark.parametrize('cost', [5, 20])
def test_fixed_control_matches_original_simulator(delay, cost):
    f, cl = fixture()
    a = m.simulate(f, cl, dict(winner_sigma=.03), start=1, arm='fixed', cost_bp=cost, delay=delay)
    b = coupled_trends.simulate(f, cl, start=1, cost_bp=cost, delay=delay)
    for key in ('nav', 'desired', 'held', 'stop'):
        np.testing.assert_allclose(a[key], b[key], atol=1e-12, equal_nan=True)
    assert [(e['entry_index'], e['exit_index']) for e in a['episodes']] == [
        (e['entry_index'], e['exit_index']) for e in b['episodes']]


@pytest.mark.parametrize('arm', ['streak', 'severity'])
@pytest.mark.parametrize('delay', [0, 1])
def test_adaptive_prefix_cash_ledger_stop_monotonicity_and_fill_delay(arm, delay):
    f, cl = fixture()
    a = m.simulate(f, cl, dict(winner_sigma=.02), start=1, arm=arm, delay=delay)
    small = SimpleNamespace(**{k:v[:130] for k,v in vars(f).items()})
    csmall = {k:v[:130] if isinstance(v, np.ndarray) else v for k,v in cl.items()}
    b = m.simulate(small, csmall, dict(winner_sigma=.02), start=1, arm=arm, delay=delay)
    for key in ('nav', 'desired', 'held', 'stop'):
        np.testing.assert_allclose(a[key][:130], b[key], atol=1e-12, equal_nan=True)
    cash, units = 1., 0.
    fills = {r['session']:r for r in a['fills']}
    for t in range(1, len(f.days)):
        if t in fills:
            r = fills[t]
            if r['side'] == 'buy':
                cash -= r['units']*r['price']+r['fee']; units += r['units']
            else:
                cash += r['units']*r['price']-r['fee']; units -= r['units']
        assert a['nav'][t] == pytest.approx(cash+units*f.close[t], abs=1e-12)
    for e in a['episodes']:
        assert e['entry_index'] == e['entry_signal']+1+delay
        if e['exit_index'] is not None:
            assert e['exit_index'] == e['exit_signal']+1+delay
        stops = a['stop'][e['entry_index']:e['exit_index']]
        assert np.all(np.diff(stops[np.isfinite(stops)]) >= 0)
        if e['entry_mode'] == 'defensive':
            assert e['entry_weight'] == .5
    assert all(r['earliest_effective_session'] > r['session'] for r in a['health_events'])


def test_single_marked_loss_exits_next_open_not_at_threshold_or_before_loss():
    f, cl = fixture(20)
    f.open[:] = 100.; f.close[:] = 100.
    cl['fast_probability'][:] = [.1, .1, .8]; cl['eligible'][:] = True; cl['fast_down'][:] = False
    cl['sigma'] = .1  # existing protection is deliberately much wider
    f.close[3] = 95.; f.open[4] = 92.
    sim = m.simulate(f, cl, dict(winner_sigma=.04), start=1)
    e = sim['episodes'][0]
    assert (e['entry_index'], e['exit_signal'], e['exit_index']) == (2, 3, 4)
    assert e['exit_price'] == 92. and e['net_return'] < -.08
    assert e['exit_reason'] == 'large_mark_loss'
    assert sim['health_events'][0]['day'] == '4'
    assert sim['health_events'][0]['mode'] == 'paused'


def test_profitable_protection_does_not_warn_losing_protection_does():
    c = m.LossController('p')
    positive = ClosedTrade('1', 'p', 1, 3, 3, .02, .04)
    assert c.observe_loss(positive).mode == Mode.NORMAL
    negative = ClosedTrade('2', 'p', 5, 8, 8, -.01, .04)
    d = c.observe_loss(negative, losing_stop=True)
    assert d.mode == Mode.DEFENSIVE and not d.request_refit
    d = c.observe_loss(ClosedTrade('3', 'p', 10, 14, 14, -.05, .04), severity=True)
    assert d.mode == Mode.PAUSED and d.request_refit


def test_insufficient_training_winners_leave_sigma_missing():
    f, cl = fixture(280)
    cl['eligible'][:] = False
    c = m.calibrate(f, cl)
    assert c['winner_sigma'] is None and c['winning_trades'] == 0


def test_missing_sigma_does_not_silently_use_other_volatility():
    f, cl = fixture()
    result = m.simulate(f, cl, dict(winner_sigma=None), start=1)
    assert result['threshold'] is None
    assert 'large_mark_loss' not in result['reason']


def test_calibration_uses_only_closed_positive_net_returns(monkeypatch):
    outcomes = [.01, .02, .03, .04, .05, -.03]
    episodes = [dict(entry=100., exit_price=100*(1+r), exit_index=i+1)
                for i,r in enumerate(outcomes)]
    episodes.append(dict(entry=100., exit_price=200., exit_index=None))
    monkeypatch.setattr(m.coupled_trends, 'simulate', lambda *a, **kw: dict(episodes=episodes))
    f = SimpleNamespace(days=np.array(['2019-12-31']))
    actual = m.calibrate(f, {}, cost_bp=5)
    gains = (1+np.array(outcomes[:5]))*.9995/1.0005-1
    assert actual['winning_trades'] == 5
    assert actual['winner_sigma'] == pytest.approx(gains.std(ddof=1))


def test_dynamic_targets_compare_latest_theory_with_last_adopted_including_cash():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
    from research_loss_feedback import risk_targets
    panel = dict(close=np.ones((5, 2)), symbols=['ETF', 'BIL'])
    theory = np.tile([.6, .38, 0.], (5, 1))
    multiplier = np.array([[1., 1.], [.95, 1.], [.9, 1.], [.8, 1.], [1., 1.]])
    dynamic, dates, _ = risk_targets(panel, theory, multiplier, np.array([0, 4]), 'dynamic')
    assert list(dates) == [0, 2, 3, 4]
    assert dynamic[2, 1] == pytest.approx(.44)
    monthly, dates, _ = risk_targets(panel, theory, multiplier, np.array([0, 4]), 'monthly')
    assert list(dates) == [0, 4] and not monthly[2].any()
