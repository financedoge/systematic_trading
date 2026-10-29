"""Additional provenance and recovery checks; no changes to frozen research."""
from copy import deepcopy
import numpy as np
from systematic_trading.research import entry_value as m


def test_unused_legacy_hmm_cannot_change_forecast_inputs():
    from test_entry_value import fixture
    f,_=fixture(700)
    f.days=np.datetime64('2010-01-01')+np.arange(700)
    hm=dict(means=[[-.3],[0.],[.3]],variance=[[.1],[.01],[.1]],initial=[.3,.4,.3],transition=[[.9,.05,.05],[.05,.9,.05],[.05,.05,.9]])
    models=dict(sigma=.01,slow=dict(ratio=1e-8,variance=.0001),fast=dict(ratio=1e-4,variance=.0001),hmm=deepcopy(hm))
    p=dict(family='hmm',context=True,entry=.7,exit=.7,tight=3.,wide=5.,reset=.5)
    f.hmm_models=models;f.coupled_cache={}
    a=m.classification(f,p,dict(enabled=True,floor=.2,count=2),hm)
    x=m.features(f,a)
    f.hmm_models=deepcopy(models);f.hmm_models['hmm']['means']=[[-100.],[-50.],[100.]];f.coupled_cache={}
    b=m.classification(f,p,dict(enabled=True,floor=.2,count=2),hm)
    np.testing.assert_array_equal(x,m.features(f,b))
    for k in ('fast_probability','eligible','fast_down','thesis_exit'):np.testing.assert_array_equal(a[k],b[k])


def test_negative_history_can_reopen_without_real_trades():
    from test_entry_value import fixture
    f,c=fixture(1100)
    prices=100*np.exp(np.r_[np.arange(600)*-.002,-1.198+np.arange(500)*.005])
    f.open=prices;f.close=prices
    fc=m.forecast(f,c,10,63,'intercept')
    _,_,allowed=m.gate(dict(eligible=np.ones(1100,bool)),fc,5)
    assert not allowed[550] and allowed[900]
    assert fc['mass'][900]>fc['mass'][550]
