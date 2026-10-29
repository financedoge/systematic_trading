from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import thesis_exit as m, reset_policy as old


def fixture(n=180):
    rng=np.random.default_rng(63)
    close=100*np.exp(np.cumsum(rng.normal(0,.02,n)))
    f=SimpleNamespace(days=np.arange(n),open=close*np.exp(rng.normal(0,.004,n)),close=close)
    p=dict(family='switch',entry=.6,exit=.6,reset=.5,tight=5.,wide=10.,context=False)
    fast=np.tile([.05,.1,.85],(n,1));fast[np.arange(n)%15>=7]=[.1,.85,.05]
    slope=np.where(fast[:,2]>.5,.004,-.004)
    cl=dict(parameters=p,sigma=.02,fast_probability=fast,fast_slope=slope,
            fast_variance=np.full(n,1e-6),aligned=np.arange(n)%45<15,counter=np.zeros(n,bool))
    seed=[dict(n=2.,s=.2,w=1.) for _ in m.grid(p)]
    regimes=dict(probability=fast,change=np.zeros(n),confirmed=np.zeros(n,bool))
    return f,cl,seed,regimes


@pytest.mark.parametrize('delay',[0,1])
@pytest.mark.parametrize('cost',[5,20])
def test_control_exact_parent(delay,cost):
    f,c,s,q=fixture()
    a=m.simulate(f,c,s,dict(winner_sigma=.04),start=1,regimes=q,cost_bp=cost,delay=delay)
    b=old.simulate(f,c,s,dict(winner_sigma=.04),start=1,regimes=q,arm='regime_reset',cost_bp=cost,delay=delay)
    for k in ('nav','policy','stop','posterior_mean','desired','effective_count'):
        np.testing.assert_array_equal(a[k],b[k])
    assert a['episodes']==b['episodes']


@pytest.mark.parametrize('arm',['thesis','directional'])
@pytest.mark.parametrize('delay',[0,1])
def test_prefix_timing_ledger_stop_and_reentry(arm,delay):
    f,c,s,q=fixture();rule=dict(enabled=True,floor=.2,count=2)
    a=m.simulate(f,c,s,dict(winner_sigma=.04),start=1,regimes=q,arm=arm,rule=rule,delay=delay)
    short=SimpleNamespace(**{k:v[:120] for k,v in vars(f).items()})
    cc={k:v[:120] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(short,cc,s,dict(winner_sigma=.04),start=1,regimes={k:v[:120] for k,v in q.items()},arm=arm,rule=rule,delay=delay)
    for k in ('nav','policy','posterior_mean','stop','bad_run','effective_down'):
        np.testing.assert_array_equal(a[k][:120],b[k])
    cash=1.;units=0.;fills={e['session']:e for e in a['fills']}
    for t in range(1,len(f.days)):
        if t in fills:
            e=fills[t];sign=1 if e['side']=='buy' else -1
            cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    assert len(a['episodes'])>3
    for e in a['episodes']:
        assert e['entry_index']==e['entry_signal']+1+delay
        if e['exit_index'] is not None:assert e['exit_index']==e['exit_signal']+1+delay
        z=a['stop'][e['entry_index']:e['exit_index']];assert np.all(np.diff(z[np.isfinite(z)])>=0)


def test_thesis_confirmation_and_context():
    _,c,_,_=fixture(8);c['fast_probability'][:]=[.01,.84,.15];c['fast_slope'][:]=-.001
    c['aligned'][:]=False;p=m.grid(c['parameters'])[0];rule=dict(enabled=True,floor=.2,count=2)
    z=m.classification(c,p,rule)
    assert not z['thesis_exit'][0] and z['thesis_exit'][1]
    c['aligned'][:]=True
    z=m.classification(c,p,rule);assert not z['thesis_exit'].any()
    c['fast_probability'][:,2]=.05
    z=m.classification(c,p,rule);assert not z['thesis_exit'][2] and z['thesis_exit'][3]
    c['fast_slope'][:]=.001
    assert not m.classification(c,p,rule)['thesis_exit'].any()


def test_directional_neutral_mass_and_no_double_repair_for_slope_family():
    _,c,_,_=fixture(8);c['fast_probability'][:]=[.01,.98,.01]
    c['fast_slope'][:]=-.004;c['aligned'][:]=False
    p=m.grid(c['parameters'])[0];rule=dict(enabled=True,floor=.2,count=3)
    z=m.classification(c,p,rule,True)
    assert z['effective_down'][0]>.9 and z['shallow_exit'][0]
    c['fast_slope'][:]=.004
    assert not m.classification(c,p,rule,True)['shallow_exit'].any()
    p['family']='slope';c['fast_slope'][:]=-.004
    np.testing.assert_array_equal(m.classification(c,p,rule,True)['effective_down'],c['fast_probability'][:,0])


@pytest.mark.parametrize('arm',['thesis','directional'])
def test_training_rejection_means_exact_control(arm):
    f,c,s,q=fixture()
    a=m.simulate(f,c,s,dict(winner_sigma=.04),start=1,regimes=q)
    b=m.simulate(f,c,s,dict(winner_sigma=.04),start=1,regimes=q,arm=arm,rule=dict(enabled=False))
    np.testing.assert_array_equal(a['nav'],b['nav'])


def test_changed_shadow_outcomes_seed_the_new_policy():
    f,c,_,_=fixture();rule=dict(enabled=True,floor=.2,count=2)
    shadows=[m.coupled_trends.simulate(f,m.classification(c,p,rule),start=1) for p in m.grid(c['parameters'])]
    states=m.seed_from_shadows(f,c,shadows)
    assert all(x['closed']>3 and 0<x['n']<=4 for x in states)
    assert all(e['exit_reason']=='fast_down' or e['exit_reason']=='protection' for e in shadows[0]['episodes'] if e['exit_index'] is not None)
