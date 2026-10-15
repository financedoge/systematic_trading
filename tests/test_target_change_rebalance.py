from decimal import Decimal as D

import pytest

from systematic_trading.research.target_change_rebalance import (
    adoption_schedule, distance, execution_schedule, select_threshold, target_weights, window_metrics,
)


def row(day, known, weights):
    return dict(signal_session=day, known_through=known,
        targets=[dict(symbol=s,target_weight=str(w)) for s,w in weights.items()])


def test_cash_is_included_and_missing_symbols_are_zero():
    a = target_weights(row('2021-01-04','2020-12-31',{'SPY':'.5'}))
    b = target_weights(row('2021-01-05','2021-01-04',{'SPY':'.55'}))
    assert distance(a,b) == D('.10')
    assert distance(a,target_weights(row('a','b',{'TLT':'.5'}))) == 1


def test_strict_threshold_anchor_and_monthly_collision():
    tape = {
        '2021-01-04':row('2021-01-04','2020-12-31',{'SPY':'.5'}),
        '2021-01-05':row('2021-01-05','2021-01-04',{'SPY':'.55'}),
        '2021-01-06':row('2021-01-06','2021-01-05',{'SPY':'.56'}),
        '2021-01-07':row('2021-01-07','2021-01-06',{'SPY':'.56'}),
        '2021-02-01':row('2021-02-01','2021-01-29',{'SPY':'.7'}),
    }
    decisions, ledger = adoption_schedule(tape, ['2021-01-04','2021-02-01'], '.1')
    assert list(decisions) == ['2021-01-04','2021-01-06','2021-02-01']
    assert ledger[1]['distance'] == '0.10'
    assert ledger[3]['distance'] == '0.00'
    assert ledger[3]['anchor_before']['SPY'] == '.56' or D(ledger[3]['anchor_before']['SPY']) == D('.56')
    assert ledger[-1]['primary_reason'] == 'monthly'
    assert ledger[-1]['reasons'] == ['monthly','threshold']
    # Event generation has no account/rounding parameter; adoption also occurs
    # for unchanged monthly targets even when an account would have zero orders.
    monthly, _ = adoption_schedule(tape, ['2021-01-04','2021-01-07'], 'monthly')
    assert '2021-01-07' in monthly
    daily, _ = adoption_schedule(tape, [], 'daily')
    assert len(daily) == len(tape)


def test_delay_freezes_target_and_retains_pending_end_event():
    tape = {d:row(d,k,{'SPY':w}) for d,k,w in [
        ('2021-01-04','2020-12-31','.5'),('2021-01-05','2021-01-04','.6'),
        ('2021-01-06','2021-01-05','.7')]}
    executed,pending = execution_schedule(tape,['2021-01-04','2021-01-05'],1)
    assert executed == {'2021-01-05':tape['2021-01-04']}
    assert pending == [tape['2021-01-05'],tape['2021-01-06']]


def test_switch_only_at_monthly_event_and_carries_anchor():
    tape = {d:row(d,k,{'SPY':w}) for d,k,w in [
        ('2023-12-29','2023-12-28','.5'),('2024-01-02','2023-12-29','.6'),
        ('2024-01-03','2024-01-02','.66')]}
    decisions,ledger=adoption_schedule(tape,['2024-01-02'],'monthly',switches={'2024-01-02':'.1'})
    assert len(decisions) == 3
    assert D(ledger[1]['anchor_before']['SPY']) == D('.5')
    with pytest.raises(ValueError,match='monthly'):
        adoption_schedule(tape,[],'monthly',switches={'2024-01-02':'.1'})


@pytest.mark.parametrize('weights',[{'SPY':'NaN'},{'SPY':'-.1'},{'SPY':'1.1'}])
def test_bad_target_fails_closed(weights):
    with pytest.raises(ValueError):
        adoption_schedule({'2021-01-04':row('2021-01-04','2020-12-31',weights)},[],'monthly')


def test_window_includes_opening_nav_and_first_loss():
    data=dict(nav=[dict(date='2024-01-01',nav='100'),dict(date='2024-01-02',nav='90'),
        dict(date='2024-12-31',nav='95')])
    m=window_metrics(data,'2024-01-02','2024-12-31',initial=80)
    assert m['opening_nav'] == 100
    assert m['max_drawdown'] == pytest.approx(-.1)
    assert m['cagr'] < 0


def test_selection_window_cannot_see_future_nav_or_turnover():
    data=dict(nav=[dict(date='2023-01-03',nav='100'),dict(date='2023-12-29',nav='110'),
        dict(date='2024-01-02',nav='1000000')])
    first=window_metrics(data,'2023-01-03','2023-12-29',initial=100,
        turnover_by_day={'2023-01-03':1,'2024-01-02':1000000})
    data['nav'][-1]['nav']='.01'
    assert window_metrics(data,'2023-01-03','2023-12-29',initial=100,
        turnover_by_day={'2023-01-03':1,'2024-01-02':0}) == first


def test_selector_neighbor_stress_guardrails_and_turnover_tie():
    grid=['.05','.10','.20']
    def metrics(sharpe=1.,turnover=2.,cagr=.1):
        return {s:dict(sharpe=sharpe,cagr=cagr,max_drawdown=-.1,annual_turnover=turnover)
            for s in ('5-0','10-0','5-1')}
    values={'monthly':metrics(),'.05':metrics(1.1,4),'.10':metrics(1.09,3),'.20':metrics(1.08,2)}
    assert select_threshold(grid,values)['selected'] == '.20'
    values['.10']['5-1']['sharpe']=1.
    assert select_threshold(grid,values)['selected'] == 'monthly'
    values['.10']=metrics(1.09,3)
    values['.20']=metrics(1.5,1,cagr=.09)
    assert select_threshold(grid,values)['selected'] == '.10'


def test_usd_monthly_fallback_preserves_source_date_and_prefers_exact():
    from systematic_trading.research.usd_tracking import select_snapshot
    monthly=dict(known_through='2024-03-28',vintage_date='2024-03-27',observation_date='2024-03-22')
    daily=dict(known_through='2024-04-23',vintage_date='2024-04-22',observation_date='2024-04-19')
    assert select_snapshot([monthly],'2024-04-23',monthly_fallback='2024-03-28') is monthly
    assert select_snapshot([monthly,daily],'2024-04-23',monthly_fallback='2024-03-28') is daily
    assert monthly['known_through']=='2024-03-28'
    with pytest.raises(ValueError,match='Missing'):
        select_snapshot([monthly],'2024-04-23')
    with pytest.raises(ValueError,match='Invalid'):
        select_snapshot([monthly],'2024-04-23',monthly_fallback='2024-04-30')
    with pytest.raises(ValueError,match='Invalid'):
        select_snapshot([monthly],'2024-05-15',monthly_fallback='2024-03-28')


def test_financial_monthly_fallback_has_no_future_or_relabelled_model():
    from datetime import date
    from types import SimpleNamespace
    from systematic_trading.research.fr25_tracking import prediction, PARAMETERS
    histories={'SPY':[SimpleNamespace(trade_date=date(2024,3,28)),SimpleNamespace(trade_date=date(2024,4,23))]}
    model=dict(known_through='2024-03-28',last_label_end='2024-03-01',ready=False,models={})
    schedule=dict(parameters=PARAMETERS,models={'2024-04-01':model})
    assert prediction(schedule,histories,'2024-04-24',allow_monthly_fallback=True) is model
    assert model['known_through']=='2024-03-28'
    with pytest.raises(ValueError,match='Exact'):
        prediction(schedule,histories,'2024-04-24')
    schedule['models']={'2024-05-01':dict(model,known_through='2024-04-30')}
    with pytest.raises(ValueError,match='Missing'):
        prediction(schedule,histories,'2024-04-24',allow_monthly_fallback=True)
