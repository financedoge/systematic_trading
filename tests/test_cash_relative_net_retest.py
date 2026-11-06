"""Replay boundary, selection leakage and execution checks for the finite retest."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('cash_net', SCRIPTS/'research_cash_relative_retest.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_metric_includes_prior_close_and_initial_cost():
    days = ['2021-01-04', '2021-01-05', '2021-01-06']
    out = m.metric(days, [999_500, 1_010_000, 990_000], days[0], days[-1])
    assert out['cumulative'] == pytest.approx(-.01)
    out = m.metric(days, [999_500, 1_010_000, 990_000], days[1], days[-1])
    assert out['cumulative'] == pytest.approx(990_000/999_500-1)
    assert out['max_drawdown'] == pytest.approx(1-990_000/1_010_000)


def test_cash_calmar_is_undefined():
    out = m.metric(['2021-01-04', '2021-01-05'], [1e6, 1e6], '2021-01-04', '2021-01-05')
    assert out['calmar'] is None
    assert out['sharpe'] == 0


def test_adoption_verification_only_tolerates_decimal_sum_rounding():
    old = [dict(distance='1.234567890123456789012345670', adopted=True, latest={'SPY': '.5'})]
    new = [dict(old[0], distance='1.234567890123456789012345671')]
    assert m.adoption_equal(new, old)
    assert not m.adoption_equal([dict(new[0], adopted=False)], old)
    assert not m.adoption_equal([dict(new[0], distance='1.234567890123456789012')], old)


def test_training_selection_ignores_later_winner():
    rows = []
    for policy, training, later in [('monthly', 1., -5.), ('0.10', .8, 5.)]:
        for kind, delta in [('cash_relative', 0.), ('remove_bill', -.1)]:
            rows.append(dict(arm=f'class_{kind}_risk-{policy}', cost_bp=5, delay=0,
                windows={'calibration': dict(sharpe=training+delta, cagr=.1, max_drawdown=.1),
                         'later': dict(sharpe=later+delta, cagr=.1, max_drawdown=.1)}))
    assert m.select(rows)['selected'] == 'class_cash_relative_risk-monthly'
    rows[0]['windows']['calibration']['cagr'] = -.1
    assert m.select(rows)['selected'] == 'class_cash_relative_risk-0.10'


@pytest.mark.parametrize('delay', [0, 1])
def test_shared_replay_is_next_open_and_preserves_cash_exit(delay):
    from systematic_trading.domain.market import Instrument
    days = np.array(['2021-01-04', '2021-01-05', '2021-01-06', '2021-01-07', '2021-01-08'])
    arrays = dict(days=days, symbols=np.array(['SPY']),
                  open=np.array([[100.], [110.], [120.], [90.], [95.]]),
                  close=np.array([[100.], [112.], [118.], [91.], [96.]]),
                  urth_open=np.ones(5)*100, urth_close=np.ones(5)*100)
    recipe = dict(universeMembers=[Instrument(symbol=s, name=s, asset_class='etf', exchange='NYSE',
                      quote_currency='USD', country='US', sector='research').model_dump(mode='json')
                     for s in ('SPY', 'URTH')])
    engine = m.Replay(arrays, recipe, '2021-01-05')
    weights = np.zeros((5, 2)); weights[0, 0] = .5
    compact, economic, count = engine.run(weights, np.array([0, 2]), 5, delay, detailed=True)
    assert count == 2
    assert economic['fills'][0]['date'] == days[1+delay]
    assert economic['fills'][1]['date'] == days[3+delay]
    assert economic['fills'][1]['quantity'] == -economic['fills'][0]['quantity']
    assert float(economic['fills'][0]['price']) == arrays['open'][1+delay, 0]
    assert compact['fees'].sum() == pytest.approx(sum(float(f['fee']) for f in economic['fills']))
    if delay == 0:
        assert compact['contribution'].sum() == pytest.approx(compact['nav'][-1]-1e6, abs=.05)
    assert float(economic['nav'][-1]['cash']) == pytest.approx(compact['nav'][-1], abs=.01)


def test_fifo_outcomes_allocate_partial_fees_and_open_mark():
    from report_cash_relative_retest import trade_lots
    lots=trade_lots({'fills':[
        dict(symbol='SPY',date='2021-01-04',quantity=10,price='100',fee='1'),
        dict(symbol='SPY',date='2021-01-05',quantity=-4,price='110',fee='.44'),
    ]}, {'SPY':105}, '2021-01-06')
    assert len(lots)==2
    assert lots[0]['net_pnl']==pytest.approx(39.16)
    assert lots[1]['net_pnl']==pytest.approx(29.4)
    assert lots[1]['status']=='open marked'


def test_report_prices_use_shared_half_up_cents():
    from report_cash_relative_retest import money_prices
    assert money_prices([1.005,2.015]).tolist()==[1.01,2.02]
