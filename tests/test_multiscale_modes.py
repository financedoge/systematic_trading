from itertools import product
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import multiscale_modes as model
from systematic_trading.research import trend_hmm

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_multiscale_modes as study  # noqa: E402


def data(n=650):
    rng=np.random.default_rng(21);c=100*np.exp(np.cumsum(rng.normal(.0002,.01,n)))
    return dict(days=np.arange(n)+np.datetime64('2000-01-01'),open=c*.997,high=c*1.01,low=c*.99,close=c,volume=rng.uniform(10000,20000,n))


def test_forward_and_training_smoother_match_exhaustive_state_paths():
    emission=np.array([[.8,.2],[.1,.9],[.4,.6],[.7,.3]])
    initial=np.array([.6,.4]);transition=np.array([[.8,.2],[.3,.7]])
    alpha,_,_,ll=trend_hmm.forward(np.log(emission),initial,transition)
    for end in range(1,5):
        weights=np.zeros(2)
        for path in product(range(2),repeat=end):
            weight=initial[path[0]]*emission[0,path[0]]
            for t in range(1,end):weight*=transition[path[t-1],path[t]]*emission[t,path[t]]
            weights[path[-1]]+=weight
        np.testing.assert_allclose(alpha[end-1],weights/weights.sum(),atol=1e-12)
    assert ll==pytest.approx(np.log(weights.sum()))
    gamma,xi,_=trend_hmm.expectation(np.log(emission),initial,transition)
    expected=np.zeros_like(gamma);trans=np.zeros((2,2));total=0.
    for path in product(range(2),repeat=4):
        w=initial[path[0]]*emission[0,path[0]]
        for t in range(1,4):w*=transition[path[t-1],path[t]]*emission[t,path[t]]
        total+=w
        for t in range(4):expected[t,path[t]]+=w
        for t in range(1,4):trans[path[t-1],path[t]]+=w
    np.testing.assert_allclose(gamma,expected/total,atol=1e-12)
    np.testing.assert_allclose(xi,trans/total,atol=1e-12)


def test_fitted_hmm_inference_does_not_use_future_observations():
    rng=np.random.default_rng(123)
    x=rng.normal(0,.4,(250,6));x[:80,:4]-=1;x[-80:,:4]+=1
    fitted=trend_hmm.fit(x[:180],iterations=5)
    full=trend_hmm.filtered(x,fitted);prefix=trend_hmm.filtered(x[:210],fitted)
    np.testing.assert_allclose(full[:210],prefix,atol=1e-12)
    assert np.isfinite(full).all()
    assert (full.sum(axis=1)<=1+1e-12).all()
    np.testing.assert_allclose(np.sum(fitted['transition'],axis=1),1.)


def test_multiscale_features_windows_and_classification_are_prefix_causal():
    d=data();full=model.Features.build(d);prefix=model.Features.build({k:v[:450] for k,v in d.items()})
    for k in full.errors:np.testing.assert_allclose(full.errors[k][:450],prefix.errors[k],equal_nan=True,atol=1e-10)
    for p in [study.grid()[0],study.grid()[64],study.grid()[192]]:
        a,b=model.classify(full,p),model.classify(prefix,p)
        for key in ('fast_length','slow_length','state','context','eligible','fast_down'):
            np.testing.assert_array_equal(a[key][:450],b[key])
        x,y=model.simulate(full,a,delay=1),model.simulate(prefix,b,delay=1)
        for key in ('nav','stop','desired','held'):np.testing.assert_allclose(x[key][:450],y[key],equal_nan=True,atol=1e-12)


@pytest.mark.parametrize('delay',[0,1])
def test_close_protection_next_open_fills_and_cash_ledger(delay):
    n=15;c=np.array([100,100,101,103,108,110,107,103,95,94,93,95,96,97,98.])
    f=SimpleNamespace(days=np.arange(n),open=c*.99,close=c,atr=np.full(n,2.),activity=np.ones(n),volatility=np.ones(n))
    p=dict(study.grid()[0],family='stress',stop_atr=2.,counter_atr=1.,vol_trigger=1.25,volume_trigger=1.5,tighten=.5)
    eligible=np.zeros(n,bool);eligible[1:]=True
    cl=dict(parameters=p,eligible=eligible,fast_down=np.zeros(n,bool),counter=np.zeros(n,bool),state=np.ones(n,int))
    sim=model.simulate(f,cl,start=1,cost_bp=20,delay=delay)
    cash,units=1.,0.;fills={e['fill']:e['side'] for e in sim['events']}
    for t in range(1,n):
        if fills.get(t)=='buy':units,cash=cash/(f.open[t]*1.002),0.
        if fills.get(t)=='sell':cash,units=units*f.open[t]*.998,0.
        assert sim['nav'][t]==pytest.approx(cash+units*f.close[t])
    assert len(sim['episodes'])==1 # stale up does not immediately re-enter
    ep=sim['episodes'][0];assert ep['exit_reason']=='protection'
    assert ep['exit_index']==ep['exit_signal']+1+delay
    finite=sim['stop'][np.isfinite(sim['stop'])]
    assert (np.diff(finite)>=0).all()


def test_volatility_and_volume_tighten_only_for_subsequent_close():
    n=12;f=SimpleNamespace(days=np.arange(n),open=np.full(n,100.),close=np.full(n,100.),atr=np.full(n,2.),activity=np.ones(n),volatility=np.ones(n))
    p=dict(study.grid()[0],family='stress',volume=True,stop_atr=4.,counter_atr=1.,vol_trigger=1.25,volume_trigger=1.5,tighten=.5)
    cl=dict(parameters=p,eligible=np.arange(n)>=1,fast_down=np.zeros(n,bool),counter=np.zeros(n,bool),state=np.ones(n,int))
    f.activity[5]=2.;f.atr[5:]=10.
    sim=model.simulate(f,cl,start=1)
    assert sim['stop'][5]==92.
    assert sim['stop'][6]==96.
    assert (sim['stop'][6:]==96.).all()


def test_price_down_exit_has_no_volume_veto_and_no_slow_up_override():
    f=model.Features.build(data());p=dict(study.grid()[0],family='adaptive',volume=True,up_strength=.5,down_strength=.5,down_quality=.1,down_confirm=1)
    for k in model.FAST:
        f.cache[k]['regression']['up'][:]=-10;f.cache[k]['regression']['quality'][:]=1;f.cache[k]['pressure'][:]=1
    for k in (126,189,252):f.cache[k]['regression']['up'][:]=10;f.cache[k]['regression']['quality'][:]=1
    f.activity[:]=.1
    cl=model.classify(f,p)
    assert cl['fast_down'][400:].all()
    assert (cl['state'][400:]==model.DOWN).all()


def test_grid_has_equal_paired_component_and_volume_budget():
    choices=study.grid();assert len(choices)==448
    for family in study.FAMILIES:assert sum(p['label']==family for p in choices)==32
    for component in study.COMPONENTS:
        a=[p for p in choices if p['family']==component and not p['volume']]
        b=[p for p in choices if p['family']==component and p['volume']]
        for x,y in zip(a,b,strict=True):assert {k:v for k,v in x.items() if k not in ('volume','label')}=={k:v for k,v in y.items() if k not in ('volume','label')}
