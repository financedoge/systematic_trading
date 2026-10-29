from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import coupled_trends as m


def test_transition_factors_and_independent_restriction():
    xi=np.arange(81,dtype=float).reshape(9,9)+1
    for coupled in (False,True):
        long,short=m.update_transitions(xi,coupled)
        a=m.transition(long,short)
        np.testing.assert_allclose(a.sum(axis=1),1)
        for i in range(3):
            assert ((long[i,:,i]>=.98)&(long[i,:,i]<=.999)).all()
            assert ((short[i,:,i]>=.65)&(short[i,:,i]<=.97)).all()
            for j in range(3):
                for k in range(3):
                    for l in range(3):
                        assert a[i*3+j,k*3+l]==pytest.approx(long[i,j,k]*short[j,k,l])
        if not coupled:
            np.testing.assert_allclose(long[:,0],long[:,1])
            np.testing.assert_allclose(short[:,0],short[:,1])


def test_training_labels_and_forward_prefix():
    rng=np.random.default_rng(41)
    x=rng.normal(0,.008,(601,2));x[:180,0]-=.005;x[350:,0]+=.005
    fitted=m.fit(x[:510],coupled=True,iterations=4)
    observations=np.vstack([np.full(2,np.nan),x])
    full=m.filtered(observations,fitted)
    prefix=m.filtered(observations[:580],fitted)
    for key in ('joint','slow_probability','fast_probability','drift','forecast_drift'):
        np.testing.assert_allclose(full[key][:580],prefix[key],atol=1e-12)
    np.testing.assert_allclose(full['joint'].sum(axis=1),1.)
    means=np.array(fitted['means'])[:,0]
    assert means[0]<0<means[8]
    assert means[4]==0


@pytest.mark.parametrize('delay',[0,1])
def test_countertrend_entry_context_exit_and_independent_cash_ledger(delay):
    close=np.array([100.,100,102,108,110,109,106,101,100,102,104,99,97,98])
    n=len(close);f=SimpleNamespace(days=np.arange(n),open=close*.999,close=close)
    p=dict(entry=.5,exit=.5,aligned_exit=.8,reset=.35,tight=2.,wide=6.,context=True)
    fast=np.tile([.1,.1,.8],(n,1));fast[8:10]=[.6,.3,.1]
    cl=dict(parameters=p,eligible=fast[:,2]>.5,fast_down=fast[:,0]>.5,
            fast_probability=fast,aligned=np.zeros(n,bool),counter=np.ones(n,bool),sigma=.01)
    sim=m.simulate(f,cl,start=1,delay=delay,cost_bp=10)
    assert sim['episodes'][0]['entry_signal']==1
    assert sim['reason'][1]=='counter_up'
    cash,units=1.,0.;fills={e['fill']:e['side'] for e in sim['events']}
    for t in range(1,n):
        if fills.get(t)=='buy':units,cash=cash/(f.open[t]*1.001),0.
        if fills.get(t)=='sell':cash,units=units*f.open[t]*.999,0.
        assert sim['nav'][t]==pytest.approx(cash+units*f.close[t])
    for e in sim['episodes']:
        if e['exit_index'] is not None:
            assert e['exit_index']==e['exit_signal']+1+delay
        levels=sim['stop'][e['entry_index']:e['exit_index']]
        assert (np.diff(levels[np.isfinite(levels)])>=0).all()
    assert sim['episodes'][0]['exit_reason']=='protection'


def test_price_observations_ignore_volume_and_volume_missing_is_rejected():
    data=dict(close=np.array([100.,99.,102.]),volume=np.array([1.,0.,3.]))
    assert np.isfinite(m.observations(data)[1:]).all()
    with pytest.raises(ValueError):m.observations(data,True)


def test_context_cannot_loosen_previously_adopted_protection():
    n=12;f=SimpleNamespace(days=np.arange(n),open=np.full(n,100.),close=np.full(n,100.))
    p=dict(reset=.35,tight=2.,wide=8.,context=True)
    cl=dict(parameters=p,eligible=np.ones(n,bool),fast_down=np.zeros(n,bool),
            fast_probability=np.tile([.1,.1,.8],(n,1)),aligned=np.arange(n)>=5,
            counter=np.arange(n)<5,sigma=.01)
    sim=m.simulate(f,cl,start=1)
    np.testing.assert_allclose(sim['stop'][2:],98.)
