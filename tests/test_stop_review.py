from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import stop_review as m


RULE=dict(enabled=True,floor=.2,count=2)


def fixture(n=180):
    from test_regime_entry import fixture as old
    f,c=old(n)
    f.high=np.maximum(f.open,f.close)*1.001;f.low=np.minimum(f.open,f.close)*.999;f.volume=np.full(n,100.)
    return f,c


@pytest.mark.parametrize('cost',[5,10,20])
@pytest.mark.parametrize('delay',[0,1])
def test_close_engine_matches_frozen_b(cost,delay):
    f,c=fixture();a=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,mode='baseline')
    b=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,mode='close_next',rule=RULE)
    np.testing.assert_allclose(a['nav'],b['nav'],atol=2e-14,rtol=0)


def flat():
    f,c=fixture(40)
    f.open[:]=100;f.close[:]=100;f.high[:]=101;f.low[:]=99;f.volume[:]=100
    c['sigma']=.01;c['parameters'].update(tight=3.,wide=3.,context=False)
    c['fast_probability'][:]=[.02,.08,.9];c['fast_slope'][:]=.002;c['fast_down'][:]=False;c['eligible'][:]=True
    return f,c


def test_gap_fill_and_old_stop_not_today_high():
    f,c=flat();f.high[3]=150;f.low[3]=98
    f.open[4]=95;f.close[4]=94;f.low[4]=93
    s=m.simulate(f,c,start=1,rule=RULE)
    assert s['episodes'][0]['exit_index']==4
    assert s['episodes'][0]['exit_price']==pytest.approx(95*.9995)
    assert s['fills'][1]['phase']=='open_gap'
    assert s['stop'][3]==pytest.approx(97)


def test_entry_day_bracket_and_independent_ledger():
    f,c=flat();f.low[2]=96
    s=m.simulate(f,c,start=1,rule=RULE)
    assert [z['session'] for z in s['fills'][:2]]==[2,2]
    assert s['fills'][1]['price']==pytest.approx(97*.9995)
    cash=1.;units=0.
    for t in range(1,len(f.days)):
        for e in [z for z in s['fills'] if z['session']==t]:
            sign=1 if e['side']=='buy' else -1;cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
        assert s['nav'][t]==pytest.approx(cash+units*f.close[t])


def test_touch_close_is_explicitly_different_from_stop():
    f,c=flat();f.low[3]=96;f.close[3]=99
    a=m.simulate(f,c,start=1,rule=RULE);b=m.simulate(f,c,start=1,rule=RULE,mode='touch_close')
    assert a['episodes'][0]['exit_price']==pytest.approx(97*.9995)
    assert b['episodes'][0]['exit_price']==pytest.approx(99*.9995)
    assert b['fills'][1]['phase']=='conditional_close'


def test_recovery_needs_later_nearby_supportive_bar():
    f,c=flat();q=m.activity(f);watch=dict(day=3,price=100.,atr=2.)
    f.open[4]=100;f.close[3]=99;f.close[4]=101;f.high[4]=101.1;f.low[4]=100;q=m.activity(f)
    assert m.recovered(f,c,watch,4,q,.0005)
    assert not m.recovered(f,c,watch,3,q,.0005)
    f.close[4]=104
    assert not m.recovered(f,c,watch,4,q,.0005)
    f.close[4]=101;q['pressure'][4]=-.1
    assert not m.recovered(f,c,watch,4,q,.0005)


@pytest.mark.parametrize('delay',[0,1])
def test_adaptive_prefix_and_reversal_warnings(delay):
    f,c=fixture();sh=m.shadow_returns(f,c,RULE,start=1,delay=delay)
    a=m.simulate(f,c,start=1,delay=delay,rule=RULE,recovery=True,adaptive=True,shadows=sh,loss_threshold=.01)
    ff=SimpleNamespace(**{k:v[:100] for k,v in vars(f).items()});cc={k:v[:100] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    ss=m.shadow_returns(ff,cc,RULE,start=1,delay=delay)
    np.testing.assert_array_equal(sh[:100],ss)
    b=m.simulate(ff,cc,start=1,delay=delay,rule=RULE,recovery=True,adaptive=True,shadows=ss,loss_threshold=.01)
    for k in ('nav','desired','stop','policy','reset','posterior_mean'):np.testing.assert_array_equal(a[k][:100],b[k])
    assert all(e['entry_index']==e['entry_signal']+1+delay for e in a['episodes'])
    assert any(e['reset'] for e in a['events'])
    for e in a['episodes']:
        stop=a['stop'][e['entry_index']:e['exit_index']]
        assert np.all(np.diff(stop[np.isfinite(stop)])>=-1e-12)
