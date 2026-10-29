from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import online_policy as m, coupled_trends


def fixture(n=180):
    rng=np.random.default_rng(18)
    close=100*np.exp(np.cumsum(rng.normal(-.001,.025,n)))
    f=SimpleNamespace(days=np.arange(n),open=close*np.exp(rng.normal(0,.006,n)),close=close)
    fast=np.tile([.1,.1,.8],(n,1));fast[np.arange(n)%12>=8]=[.8,.1,.1]
    p=dict(reset=.5,tight=3.,wide=6.,context=True,entry=.6,exit=.6)
    cl=dict(parameters=p,sigma=.02,aligned=np.arange(n)%33<12,eligible=fast[:,2]>.6,
            fast_down=fast[:,0]>.6,fast_probability=fast,fast_slope=fast[:,2]-.5,
            counter=np.zeros(n,bool))
    # Context raises the baseline down threshold to .85.
    cl['fast_down']=fast[:,0]>=np.where(cl['aligned'],.85,.6)
    initial=[dict(n=0.,s=0.,w=0.) for _ in m.grid(p)]
    return f,cl,initial


@pytest.mark.parametrize('delay',[0,1])
@pytest.mark.parametrize('cost',[5,20])
def test_frozen_matches_existing(delay,cost):
    f,c,initial=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.03),start=1,arm='fixed',delay=delay,cost_bp=cost)
    b=coupled_trends.simulate(f,c,start=1,delay=delay,cost_bp=cost)
    for key in ('nav','stop','desired','held'):
        np.testing.assert_allclose(a[key],b[key],equal_nan=True,atol=1e-12)


@pytest.mark.parametrize('arm',m.ARMS)
@pytest.mark.parametrize('delay',[0,1])
def test_prefix_invariance_ledger_and_causal_fills(arm,delay):
    f,c,initial=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.02),start=1,arm=arm,delay=delay)
    small=SimpleNamespace(**{k:v[:130] for k,v in vars(f).items()})
    cs={k:v[:130] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(small,cs,initial,dict(winner_sigma=.02),start=1,arm=arm,delay=delay)
    for key in ('nav','stop','desired','policy','posterior_mean','effective_count'):
        np.testing.assert_allclose(a[key][:130],b[key],equal_nan=True,atol=1e-12)
    cash=1.;units=0.;fills={z['session']:z for z in a['fills']}
    for t in range(1,len(f.days)):
        if t in fills:
            z=fills[t];sign=1 if z['side']=='buy' else -1
            cash-=sign*z['units']*z['price']+z['fee'];units+=sign*z['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    for e in a['episodes']:
        assert e['entry_index']==e['entry_signal']+1+delay
        if e['exit_index'] is not None:assert e['exit_index']==e['exit_signal']+1+delay
        s=a['stop'][e['entry_index']:e['exit_index']]
        assert np.all(np.diff(s[np.isfinite(s)])>=0)
    assert all(e['earliest_fill']>e['session'] for e in a['events'])


def test_posterior_shrinks_uses_magnitude_not_only_wins_and_stays_separate():
    p=m.Posterior([dict(n=0,s=0,w=0) for _ in range(2)])
    for _ in range(4):p.observe(0,.1,True)
    p.observe(0,-2,False);p.observe(1,.5,True)
    mu,sd,win=p.values()
    assert mu[0]<0<mu[1] and win[0]>win[1]
    assert p.choose(0)==1
    before=p.n.copy();p.discount(.25)
    np.testing.assert_allclose(p.n,before*.25)
    assert np.all(p.values()[1]>sd)


def test_unobserved_candidate_cannot_replace_current_from_training_alone():
    p=m.Posterior([dict(n=4,s=0,w=2),dict(n=4,s=12,w=4)])
    assert p.choose(0)==0
    p.observe(1,1.,True)
    assert p.choose(0)==1


def test_warnings_discount_without_pause_and_without_double_counting_real_trade():
    f,c,initial=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.01),start=1,arm='warning')
    assert any(e['accelerated'] for e in a['events'])
    first=min(e['session'] for e in a['events'] if e['accelerated'])
    assert any(e['entry_index']>first for e in a['episodes'])
    # Effective observations never exceed completed shadow trades plus training.
    assert np.nanmax(a['effective_count'])<len(a['episodes'])+4
    assert set(np.unique(a['desired'])) <= {0,1}


def test_missing_sigma_and_cooldown():
    f,c,initial=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=None),start=1)
    assert a['threshold'] is None
    assert not any('large_' in e['reason'] for e in a['events'])
    times=[e['session'] for e in a['events'] if e['accelerated']]
    assert all(y-x>=20 for x,y in zip(times,times[1:]))


def test_grid_preserves_baseline_and_bounds():
    _,c,_=fixture();g=m.grid(c['parameters'])
    assert len(g)==9
    for k,v in c['parameters'].items():assert g[0][k]==v
    assert all(.5<=p['entry']<=.9 and p['tight']>0 for p in g)


def test_training_excludes_open_trades(monkeypatch):
    f,c,_=fixture()
    episodes=[dict(entry=100.,exit_price=105.,entry_index=5,exit_index=10),
              dict(entry=100.,exit_price=None,entry_index=20,exit_index=None)]
    monkeypatch.setattr(m.coupled_trends,'simulate',lambda *a,**kw:dict(episodes=episodes))
    initial=m.initialize(f,c)
    assert all(z['closed']==1 and 0<z['n']<=4 for z in initial)
