from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import reset_policy as m, online_policy as parent


def fixture(n=240):
    rng=np.random.default_rng(18);close=100*np.exp(np.cumsum(rng.normal(-.001,.025,n)))
    f=SimpleNamespace(days=np.arange(n),open=close*np.exp(rng.normal(0,.006,n)),close=close)
    fast=np.tile([.1,.1,.8],(n,1));fast[np.arange(n)%12>=8]=[.8,.1,.1]
    p=dict(reset=.5,tight=3.,wide=6.,context=True,entry=.6,exit=.6)
    cl=dict(parameters=p,sigma=.02,aligned=np.arange(n)%33<12,eligible=fast[:,2]>.6,
        fast_down=fast[:,0]>=np.where(np.arange(n)%33<12,.85,.6),
        fast_probability=fast,fast_slope=fast[:,2]-.5,counter=np.zeros(n,bool))
    initial=[dict(n=2.,s=.4,w=1.) for _ in m.grid(p)]
    regimes=dict(probability=fast,change=np.where(np.arange(n)%30==0,.95,.01),
                 confirmed=np.arange(n)%30==2)
    return f,cl,initial,regimes


@pytest.mark.parametrize('cost',[5,20])
@pytest.mark.parametrize('delay',[0,1])
def test_continuous_matches_frozen_learning(cost,delay):
    f,c,initial,q=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.02),start=1,arm='continuous',cost_bp=cost,delay=delay,regimes=q)
    b=parent.simulate(f,c,initial,dict(winner_sigma=.02),start=1,arm='bayes',cost_bp=cost,delay=delay)
    for k in ('nav','stop','desired','policy','posterior_mean','effective_count'):
        np.testing.assert_allclose(a[k],b[k],atol=1e-12,equal_nan=True)


@pytest.mark.parametrize('arm',m.ARMS)
@pytest.mark.parametrize('delay',[0,1])
def test_prefix_and_ledger_and_protection(arm,delay):
    f,c,initial,q=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.02),start=1,arm=arm,delay=delay,regimes=q)
    small=SimpleNamespace(**{k:v[:170] for k,v in vars(f).items()})
    cs={k:v[:170] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    qs={k:v[:170] for k,v in q.items()}
    b=m.simulate(small,cs,initial,dict(winner_sigma=.02),start=1,arm=arm,delay=delay,regimes=qs)
    for k in ('nav','stop','policy','posterior_mean','effective_count','reset_age','empty_evidence'):
        np.testing.assert_allclose(a[k][:170],b[k],atol=1e-12,equal_nan=True)
    cash=1.;units=0.;fills={z['session']:z for z in a['fills']}
    for t in range(1,len(f.days)):
        if t in fills:
            z=fills[t];sign=1 if z['side']=='buy' else -1
            cash-=sign*z['units']*z['price']+z['fee'];units+=sign*z['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    for e in a['episodes']:
        assert e['entry_index']==e['entry_signal']+1+delay
        if e['exit_index'] is not None:assert e['exit_index']==e['exit_signal']+1+delay
        z=a['stop'][e['entry_index']:e['exit_index']]
        assert np.all(np.diff(z[np.isfinite(z)])>=0)


def test_full_reset_neutral_prior_and_freshness():
    p=m.Posterior([dict(n=4,s=3,w=3),dict(n=2,s=-1,w=1)])
    p.observe(0,1,True);p.reset()
    np.testing.assert_array_equal(p.n,[0,0]);np.testing.assert_array_equal(p.fresh,[0,0])
    mean,sd,win=p.values()
    np.testing.assert_array_equal(mean,[0,0]);np.testing.assert_array_equal(sd,[.5,.5])
    np.testing.assert_array_equal(win,[.5,.5]);assert p.choose(1)==1


def test_reset_rejects_straddling_shadow_trades():
    f,c,initial,q=fixture(100)
    q['confirmed'][:]=False;q['confirmed'][10]=True
    e=dict(entry=100.,exit_price=200.,entry_index=9,exit_index=11)
    shadows=[dict(episodes=[e]) for _ in range(9)]
    a=m.simulate(f,c,initial,dict(winner_sigma=None),start=1,arm='regime_reset',shadows=shadows,regimes=q)
    assert a['rejected_outcomes']==9
    assert a['effective_count'][11]==0 and a['empty_evidence'][11]
    assert any(x['entry_index']>10 for x in a['episodes'])  # no health pause


def test_reset_cooldowns_and_not_ordinary_losing_stop():
    f,c,initial,q=fixture()
    a=m.simulate(f,c,initial,dict(winner_sigma=.02),start=1,regimes=q)
    resets=[e for e in a['events'] if e['reset']]
    assert resets and all(b['session']-a['session']>=20 for a,b in zip(resets,resets[1:]))
    assert all('losing_stop' not in e['reason'] for e in a['events'])
    assert all(e['effective_count']==0 for e in resets)


def test_transition_probability_is_filtered_joint_not_posterior_confidence():
    transition=np.array([[.9,.1],[.2,.8]])
    emission=np.log(np.array([[.8,.2],[.2,.8],[.1,.9],[.2,.8]]))
    alpha,change=m.transition_probability(emission,np.array([.5,.5]),transition)
    joint=alpha[0,:,None]*transition*np.exp(emission[1])[None,:];joint/=joint.sum()
    assert change[1]==pytest.approx(1-np.trace(joint))
    aa,cc=m.transition_probability(emission[:3],np.array([.5,.5]),transition)
    np.testing.assert_allclose(aa,alpha[:3]);np.testing.assert_allclose(cc,change[:3])
    assert abs(change[-1]-alpha[-1].max())>.1


def test_transition_confirmation_requires_three_closes_and_new_state_persistence():
    p=np.array([[.95,.03,.02],[.02,.03,.95],[.02,.03,.95],[.02,.03,.95],[.95,.03,.02],[.3,.3,.4]])
    q=np.array([0,.9,.02,.02,.9,.1])
    assert list(np.flatnonzero(m.confirmations(p,q)))==[3]
    assert not m.confirmations(p[:3],q[:3]).any()
