from pathlib import Path
import sys

import numpy as np
import pytest

from systematic_trading.research import latent_slope as m


def test_scalar_kalman_matches_dense_reference():
    rng=np.random.default_rng(19);y=np.cumsum(rng.normal(0,.01,300))
    ratio,variance=1e-4,.003
    actual=m.kalman(y,ratio,variance)
    mean=np.array([y[0],0.]);cov=np.eye(2)*variance
    F=np.array([[1.,1.],[0.,1.]]);H=np.array([1.,0.]);Q=np.diag([0.,ratio*variance])
    for t in range(1,len(y)):
        pred=F@mean;P=F@cov@F.T+Q;S=H@P@H+variance;K=P@H/S
        mean=pred+K*(y[t]-H@pred)
        # Joseph form is an independent covariance reference.
        I=np.eye(2)-np.outer(K,H);cov=I@P@I.T+np.outer(K,K)*variance
        np.testing.assert_allclose([actual['level'][t],actual['slope'][t]],mean,atol=1e-12)
        np.testing.assert_allclose([actual['level_variance'][t],actual['slope_variance'][t]],np.diag(cov),atol=1e-12)


def test_profiled_scale_and_filter_prefix():
    rng=np.random.default_rng(2);y=np.cumsum(rng.normal(0,.01,650))
    fit=m.fit_filter(y[:550],(1e-8,1e-5))
    q=m.kalman(y,fit['ratio'],fit['variance']);p=m.kalman(y[:600],fit['ratio'],fit['variance'])
    for key in q:np.testing.assert_allclose(q[key][:600],p[key],atol=1e-12)
    unit=m.kalman(y[:550],fit['ratio'])
    assert fit['variance']==pytest.approx(np.mean(unit['innovation'][252:]**2/unit['innovation_variance'][252:]))
    assert fit['bounds'][0]<=fit['ratio']<=fit['bounds'][1]*(1+1e-12)


def test_constant_slope_converges_and_flattens_without_relabelling_past():
    y=np.r_[np.arange(400)*-.002, -.798+np.arange(1,201)*.0001]
    q=m.kalman(y,1e-6,.0001)
    assert q['slope'][399]==pytest.approx(-.002,abs=1e-6)
    assert q['slope'][-1]>-.0001
    prefix=m.kalman(y[:400],1e-6,.0001)
    np.testing.assert_allclose(prefix['slope'],q['slope'][:400])


def data(n=650):
    rng=np.random.default_rng(8);close=100*np.exp(np.cumsum(rng.normal(.0003,.012,n)))
    return dict(days=np.arange(n)+np.datetime64('2018-01-01'),open=close*.999,close=close,volume=np.ones(n)*10000)


def test_model_probability_partition_and_trading_prefix():
    d=data(950);f=m.Features.build(d);f.hmm_models=m.fit_models(f.truncated(str(f.days[800])))
    small=m.Features.build({k:v[:900] for k,v in d.items()});small.hmm_models=f.hmm_models
    q=m.probabilities(f)
    for key in ('slow_probability','slope_probability','hmm_probability'):
        np.testing.assert_allclose(q[key][252:].sum(axis=1),1.,atol=1e-12)
    for family in ('slope','switch','context'):
        p=dict(family=family,entry=.6,exit=.6,context=family=='context',tight=3.,wide=6.,reset=.5)
        a=m.simulate(f,m.classify(f,p),delay=1);b=m.simulate(small,m.classify(small,p),delay=1)
        for key in ('nav','desired','held','stop','fast_probability','slow_probability'):
            np.testing.assert_allclose(a[key][:900],b[key],equal_nan=True,atol=1e-12)


def test_context_changes_threshold_without_vetoing_countertrend_entry():
    f=m.Features.build(data());n=len(f.days)
    f.hmm_models=dict(sigma=.01)
    f.coupled_cache['latent']=dict(
        slow_probability=np.tile([.1,.1,.8],(n,1)),hmm_probability=np.tile([.7,.1,.2],(n,1)),
        slope_probability=np.tile([.7,.1,.2],(n,1)),
        fast=dict(slope=np.ones(n)*.001,slope_variance=np.ones(n),level=np.ones(n),level_variance=np.ones(n)),
        slow=dict(slope=np.ones(n),slope_variance=np.ones(n),level=np.ones(n),level_variance=np.ones(n)))
    p=dict(family='switch',entry=.6,exit=.6,context=False)
    assert m.classify(f,p)['fast_down'].all()
    assert not m.classify(f,dict(p,family='context',context=True))['fast_down'].any()
    f.coupled_cache['latent']['slow_probability'][:]=[.8,.1,.1]
    f.coupled_cache['latent']['hmm_probability'][:]=[.1,.1,.8]
    c=m.classify(f,dict(p,family='context',context=True))
    assert c['eligible'].all() and c['counter'].all()


def test_only_three_paired_candidate_families():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import research_latent_slope as study
    rows=study.grid();assert len(rows)==24
    assert study.FAMILIES==('slope','switch','context')
    for family in study.FAMILIES:assert sum(p['family']==family for p in rows)==8
