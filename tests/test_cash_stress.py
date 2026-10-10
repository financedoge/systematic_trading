from decimal import Decimal as D
from systematic_trading.research.cash_stress import StressPolicy


def setup(arm='R2',parking='ZERO'):
    days=['2020-04-01','2020-05-01','2020-06-01','2020-07-01']
    symbols=['SPY','GLD','TLT','IEF','BIL','URTH']
    quotes={s:{d:dict(reference='100',open='100',close='100') for d in days} for s in symbols}
    signals={d:dict(known_through='2020-03-31',episode_id=1,active=True,max_level=1,confirmed=False,
        exit_reason=None,drawdown='-.15',losers=['GLD','TLT','IEF'],winners=['SPY','GLD','TLT']) for d in days}
    parent={d:dict(targets=[dict(symbol=s,target_weight='.10' if s in ['GLD','TLT','IEF'] else '0') for s in symbols if s not in ['BIL','URTH']]) for d in days}
    return StressPolicy(arm,parking,signals,parent,quotes),days


def fill(policy,day):
    after={s:int(q)+1 for s,q in policy.desired.items() if q>0}
    policy.filled(day,{},after,{s:D(100) for s in policy.quotes},{})
    return after


def test_stress_sleeve_explicitly_buys_rejected_spy_and_preserves_parent():
    p,days=setup();w=p.plan(days[0],days[0],{},D(1000000))
    assert D('.066')<w['SPY']<D('.067')
    assert w['GLD']==D('.10') and sum(w.values())<=D('.98')
    assert p.pending['new_tranches']==1 and p.pending['cycle_budget_usd']=='200000.00'


def test_no_repeat_buy_or_loss_top_up_for_spent_stage():
    p,days=setup();p.plan(days[0],days[0],{},D(1000000));positions=fill(p,days[0]);owned=dict(p.quantities)
    p.quotes['SPY'][days[1]]['reference']='50'
    p.plan(days[1],days[1],positions,D(900000))
    assert p.desired['SPY']==owned['SPY'] and p.pending['new_tranches']==0


def test_confirmation_locks_same_budget_before_buying():
    p,days=setup('R3');w=p.plan(days[0],days[0],{},D(1000000))
    assert w['SPY']==0 and p.budget==D(200000)
    fill(p,days[0]);p.signals[days[1]].update(confirmed=True,max_level=2)
    p.plan(days[1],days[1],{},D(1200000))
    assert p.budget==D(200000) and p.pending['new_tranches']==2
    assert abs(D(p.pending['requested_usd'])-D(400000)/3)<D('1e-20')


def test_loser_basket_freezes_until_episode_exit():
    p,days=setup('L2');p.plan(days[0],days[0],{},D(1000000));positions=fill(p,days[0])
    p.signals[days[1]].update(losers=['SPY','BIL','URTH'],max_level=2)
    p.plan(days[1],days[1],positions,D(900000))
    assert p.basket==['GLD','TLT','IEF'] and p.desired['SPY']==0
    p.signals[days[2]].update(active=False,exit_reason='recovered_to_95pct_anchor')
    p.plan(days[2],days[2],positions,D(900000));assert sum(p.desired.values())==0


def test_parent_cash_reentry_crowds_out_sleeve_without_rearming():
    p,days=setup();p.plan(days[0],days[0],{},D(1000000));positions=fill(p,days[0])
    p.parent[days[1]]['targets']=[dict(symbol='SPY',target_weight='.98')]
    w=p.plan(days[1],days[1],positions,D(900000))
    assert sum(p.desired.values())==0 and w['SPY']==D('.98') and p.levels==1


def test_bil_parking_cap_and_reserve_source_are_separate():
    p,days=setup('B10_fixed','BIL');w=p.plan(days[0],days[0],{},D(1000000))
    assert w['GLD']==D('.09') and w['BIL']==D('.45')
    assert sum(w.values())==D('.72') and p.quantities['BIL']==0


def test_tiny_decimal_cash_does_not_lock_a_zero_budget():
    p,days=setup();p.parent[days[0]]['targets']=[dict(symbol='SPY',target_weight='.979999999999999999999')]
    p.plan(days[0],days[0],{},D(1000000));assert p.budget is None and p.levels==0


def test_virtual_ownership_cannot_exceed_actual_fills():
    p,days=setup();p.plan(days[0],days[0],{},D(1000000))
    p.filled(days[0],{},dict(SPY=100),{s:D(100) for s in p.quotes},dict(SPY=D(5)))
    assert p.quantities['SPY']==D(100)
    assert sum(D(v) for v in p.events[days[0]]['fees'].values())==D(5)


def test_stress_signal_ignores_decision_day_and_future_and_expires():
    from datetime import date,timedelta
    from copy import deepcopy
    from systematic_trading.research.cash_stress import signal_rows
    days=[str(date(2010,1,1)+timedelta(days=i)) for i in range(900)]
    values=[100]*270+[80]*430+[96]*200
    bars={s:[dict(trade_date=d,close=str(v)) for d,v in zip(days,values)] for s in ('SPY','GLD','TLT')}
    parent={days[i]:{} for i in range(280,850,30)}
    signals=signal_rows(bars,parent);first=min(parent)
    changed=deepcopy(bars)
    for rows in changed.values():
        for row in rows:
            if row['trade_date']>=first:row['close']='2000'
    assert signal_rows(changed,{first:{}})[first]==signals[first]
    rows=list(signals.values())
    assert rows[0]['active'] and rows[0]['max_level']==2
    assert rows[12]['exit_reason']=='12_month_limit' and not rows[13]['active']
    assert sum(r['active'] for r in rows)==12


def test_attribution_counts_actual_buys_and_reconciles_entry_exit_fees():
    from systematic_trading.research.cash_stress_analysis import attribution
    p,days=setup();p.plan(days[0],days[0],{},D(1000000))
    p.desired={s:D(2) if s=='SPY' else D(0) for s in p.quotes}
    p.filled(days[0],{},dict(SPY=2),{s:D(100) for s in p.quotes},dict(SPY=D(1)))
    p.signals[days[1]].update(active=False,exit_reason='recovery')
    p.plan(days[1],days[1],dict(SPY=2),D(999799))
    p.filled(days[1],dict(SPY=2),{},{s:D(95) for s in p.quotes},dict(SPY=D(1)))
    p.quotes['SPY'][days[0]]['close']='110';p.quotes['SPY'][days[1]]['close']='90'
    e=dict(nav=[dict(date=days[0],nav='1000019'),dict(date=days[1],nav='999988')])
    a=attribution(e,p.quotes,p.events)
    assert a['stress_pnl_usd']==-12 and a['stress_daily_pnl']==[19,-31]
    assert a['deployed_cycles']==1 and a['open_funded_cycles']==0
    p,days=setup();p.plan(days[0],days[0],{},D(1000000));p.filled(days[0],{},{},{s:D(100) for s in p.quotes},{})
    a=attribution(dict(nav=[dict(date=days[0],nav='1000000')]),p.quotes,p.events)
    assert a['funded_cycles']==1 and a['deployed_cycles']==0
