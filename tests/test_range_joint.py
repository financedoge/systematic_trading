import numpy as np
import pytest

from systematic_trading.research.range_joint import (
    History, PARAMETERS, canonical, v1_anchor, lifecycle_joint, screen_stats,
    risk_stats, utility, objective_components,
)
from systematic_trading.research.range_breakout import lifecycle,BreakoutSpec


def history():
    t=np.arange(1450);c=100+np.sin(t/6);c[1300:1380]=np.linspace(105,180,80);c[1380:]=np.linspace(160,90,70)
    o=np.r_[c[0],c[:-1]];v=np.ones(len(c))*1000;v[1300:1380]=3000
    return dict(close=c,open=o,high=np.maximum(c,o)+.5,low=np.minimum(c,o)-.5,volume=v,
                days=np.array([str(i) for i in t]))


def test_joint_anchor_reproduces_v1_trades():
    a=history();h=History.build(a);r=h.signals(v1_anchor())
    old=lifecycle(a['close'],a['open'],a['high'],a['low'],a['volume'],BreakoutSpec())
    np.testing.assert_array_equal(r['active'],old['active'])


def test_prefix_invariance_includes_stop_risk_and_future_opens():
    a=history();p=v1_anchor();p[2]=1;p[1]=.8;p[14]=0
    full=History.build(a).signals(p);n=1303
    cut=History.build({k:v[:n] for k,v in a.items()}).signals(p)
    for k in full:
        np.testing.assert_array_equal(full[k][:n],cut[k])
    changed={k:v.copy() for k,v in a.items()};changed['open'][n:]*=1.5
    later=History.build(changed).signals(p)
    np.testing.assert_array_equal(later['active'][:n],full['active'][:n])


def test_jit_and_python_reference_agree():
    h=History.build(history());p=v1_anchor()
    a=lifecycle_joint(p,*h.arrays);b=lifecycle_joint.py_func(p,*h.arrays)
    for x,y in zip(a,b,strict=True):
        np.testing.assert_allclose(x,y,equal_nan=True,rtol=1e-12,atol=1e-12)
    x=screen_stats(h.arrays[0],h.arrays[1],a[0],252,len(h.days))
    y=screen_stats.py_func(h.arrays[0],h.arrays[1],a[0],252,len(h.days))
    np.testing.assert_allclose(x,y,rtol=1e-10,atol=1e-10)


def test_single_close_confirmation_waits_until_next_open_for_fill():
    a=history();p=v1_anchor();p[13]=1
    h=History.build(a);r=h.signals(p)
    assert r['active'][1300]
    assert np.isnan(r['risk'][1300,0])
    assert np.isfinite(r['risk'][1301,0])


def test_penalties_cannot_read_outside_evaluation_window():
    a=history();r=History.build(a).signals(v1_anchor())
    before=risk_stats(r,a['open'],252,1320)
    for key in ('risk','stop'):
        r[key][1320:]=999
    after=risk_stats(r,a['open'],252,1320)
    np.testing.assert_array_equal(before,after)


def test_cash_sharpe_cannot_dominate_return_objective():
    b=np.zeros((4,7));s=b.copy();b[:,1]=18;s[:,1]=100
    np.testing.assert_array_equal(utility(s,b),np.zeros(4))
    s[:,0]=.10
    np.testing.assert_allclose(utility(s,b),np.full(4,.45))


def test_wide_stops_and_buyhold_behavior_have_soft_penalties():
    s=np.zeros((4,7));s[:,0]=.1;s[:,1]=1;s[:,2]=1;s[:,4]=.99;s[:,5]=.99;s[:,6]=10
    b=s.copy();risk=np.array([.3,.4,2,1,10.])
    result=objective_components(s,b,risk)
    assert result['raw']==0
    assert result['strong']<result['moderate']<result['weak']<result['raw']


def test_parameter_bounds_and_integer_contract():
    assert len(PARAMETERS)==33
    p=v1_anchor();p[13]=2.6;p[3]=4;p[4]=3
    q=canonical(p)
    assert q[13]==3 and q[4]==4
    with pytest.raises(ValueError):
        canonical([np.nan]*33)


def test_zero_atr_flat_history_cannot_create_zero_risk_trade():
    a=history();a['close'][:1300]=100;a['open'][:1300]=100;a['high'][:1300]=100;a['low'][:1300]=100
    p=v1_anchor();p[13]=1
    r=History.build(a).signals(p)
    assert not r['active'][1300]


@pytest.mark.parametrize('basis',[0,1,2])
def test_all_trailing_bases_are_causal_and_ratchet(basis):
    a=history();p=v1_anchor();p[20]=basis;p[13]=1;p[14]=0;p[18:20]=-1
    p[24]=1;p[25]=1;p[27]=1;p[28]=.3;p[30]=4;p[31]=2
    full=History.build(a).signals(p);n=1355
    prefix=History.build({k:v[:n] for k,v in a.items()}).signals(p)
    for k in full:
        np.testing.assert_array_equal(full[k][:n],prefix[k])
    same=full['active'][1:] & full['active'][:-1] & np.isfinite(full['stop'][1:]) & np.isfinite(full['stop'][:-1])
    assert np.all(np.diff(full['stop'])[same]>=-1e-10)
