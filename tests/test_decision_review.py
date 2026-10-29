from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import decision_review as m
from test_stop_review import fixture,flat,RULE


def prefix(f,n):
    return SimpleNamespace(**{k:v[:n] if isinstance(v,np.ndarray) else v for k,v in vars(f).items()})


def trained():
    f,c=fixture(650)
    # Deterministic returns with both outcome signs and nontrivial features.
    t=np.arange(650);f.close=100*np.exp(.03*np.sin(t/13)+.01*np.sin(t/2))
    f.open=f.close*np.exp(.001*np.cos(t));f.high=np.maximum(f.open,f.close)*1.005
    f.low=np.minimum(f.open,f.close)*.995;f.volume=100+30*np.cos(t/7)
    return f,c,m.fit(prefix(f,450),c['sigma'])


@pytest.mark.parametrize('delay',[0,1])
@pytest.mark.parametrize('cost',[5,10,20])
def test_disabled_review_exact_parent(delay,cost):
    f,c,seed=trained()
    a=m.simulate(f,c,start=449,delay=delay,cost_bp=cost,rule=RULE)
    b=m.simulate(f,c,start=449,delay=delay,cost_bp=cost,rule=RULE,arm='stop',seed=seed,entry_review=False,exit_review=False)
    np.testing.assert_array_equal(a['nav'],b['nav'])
    assert a['fills']==b['fills']


@pytest.mark.parametrize('arm',['stop','review'])
def test_prefix_invariance_and_independent_accounting(arm):
    f,c,seed=trained();args=dict(start=449,rule=RULE,arm=arm,seed=seed,loss_threshold=.002)
    a=m.simulate(f,c,**args);ff=prefix(f,570);cc={k:v[:570] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(ff,cc,**args)
    for k in ('nav','stop','probability','forecast','recent_weight','up_evidence','down_evidence','reset'):
        np.testing.assert_array_equal(a[k][:570],b[k])
    cash=1.;units=0.
    for t in range(449,len(f.days)):
        for e in [e for e in a['fills'] if e['session']==t]:
            sign=1 if e['side']=='buy' else -1;cash-=sign*e['price']*e['units']+e['fee'];units+=sign*e['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    for e in a['episodes']:
        assert e['entry_index']==e['entry_signal']+1
        level=a['stop'][e['entry_index']:e['exit_index']]
        assert np.all(np.diff(level[np.isfinite(level)])>=-1e-12)


def test_fit_excludes_unmatured_origins_and_features_use_only_past():
    f,c,seed=trained()
    assert seed['last_maturity']==str(f.days[449])
    assert seed['last_origin']==str(f.days[443])
    np.testing.assert_array_equal(m.observations(f,c['sigma'])[:500],m.observations(prefix(f,500),c['sigma']))


def test_predict_then_mature_and_soft_warning():
    f,c,seed=trained();f.review_sigma=c['sigma'];x=m.observations(f,c['sigma']);a=m.ReviewModels(seed,True)
    a.forecast(449,x[449]);count=a.models[1].n.sum()
    a.mature(454,f,x);assert a.models[1].n.sum()==count
    stored=a.pending[449][1]['p'];a.mature(455,f,x)
    assert a.scores[0]['probabilities'][1]==pytest.approx(np.clip(stored,.01,.99))
    assert a.scores[0]['origin']==449 and a.scores[0]['maturity']==455
    a.weights=np.array([.99,.01]);old=a.models[1].n.copy();a.warning(456)
    assert .01<a.weights[1]<.5
    np.testing.assert_array_equal(old,a.models[1].n)
    assert a.fast_until==477


class FakeModels:
    def __init__(self,seed,adaptive):self.weights=np.array([1.,0.]);self.scores=[]
    def mature(self,*args):pass
    def warning(self,*args):pass
    def forecast(self,t,x):return .9,3.,1.


def recovery_case(monkeypatch,gap=False):
    f,c=flat();c['eligible'][3:]=False;c['fast_probability'][3:]=[.9,.09,.01]
    f.low[3]=96;f.close[3]=97;f.open[4:]=97.8;f.close[4:]=98
    f.close[5:]=98.2;f.high[4:]=98.3;f.low[4:]=97.7
    f.open[6]=110 if gap else 98.1;f.high[6]=max(f.open[6],f.close[6])+.1
    monkeypatch.setattr(m,'ReviewModels',FakeModels)
    original=m.activity
    def activity(ff):
        q=original(ff);q['pressure'][:]=1;q['location'][:]=.8;return q
    monkeypatch.setattr(m,'activity',activity)
    return m.simulate(f,c,start=1,rule=RULE,arm='stop',seed={})


def test_recovery_independent_of_lagging_hmm(monkeypatch):
    a=recovery_case(monkeypatch)
    assert a['episodes'][0]['exit_index']==3
    assert a['episodes'][1]['entry_index']==6
    assert a['episodes'][1]['entry_reason']=='exit_review'


def test_recovery_cancels_chased_open(monkeypatch):
    a=recovery_case(monkeypatch,True)
    assert not any(e['side']=='buy' and e['session']==6 for e in a['fills'])
    assert any('recovery_open_cancelled' in e['reasons'] for e in a['events'])


def test_entry_invalidation_without_hmm_down(monkeypatch):
    f,c=flat();f.close[3:]=98.7;f.open[3:]=99.3;f.low[3:]=98.6
    class Negative(FakeModels):
        def forecast(self,t,x):return .1,-3.,-2.
    monkeypatch.setattr(m,'ReviewModels',Negative)
    a=m.simulate(f,c,start=1,rule=RULE,arm='stop',seed={})
    assert a['episodes'][0]['exit_reason']=='entry_invalidated'
    assert a['episodes'][0]['exit_index']==4
