from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import entry_value as m


def fixture(n=700):
    rng=np.random.default_rng(5);p=100*np.exp(np.cumsum(rng.normal(.0002,.01,n)))
    f=SimpleNamespace(days=np.arange(n),open=p,close=p*np.exp(rng.normal(0,.003,n)),volume=rng.uniform(100,200,n))
    c=dict(sigma=.01,fast_probability=np.tile([.2,.1,.7],(n,1)),slow_probability=np.tile([.4,.2,.4],(n,1)),
        fast_slope=rng.normal(0,.002,n),slow_slope=rng.normal(0,.0005,n),fast_level=np.log(p),slow_level=np.log(p))
    return f,c


def test_emission_semantics_and_filter_prefix():
    x=np.random.default_rng(9).normal(0,.4,700);h=m.fit_hmm(x,iterations=7)
    means=np.asarray(h['means']);var=np.asarray(h['variance'])
    assert means[0,0]==-means[2,0] and means[1,0]==0 and var[0,0]==var[2,0]
    assert var[1,0]<=.01+1e-15 and var[0,0]>=.01-1e-15
    points=np.linspace(-10,10,101)[:,None];ll=m.parent.trend_hmm.emissions(points,means,var)
    np.testing.assert_allclose(ll[:,2]-ll[:,0],2*means[2,0]*points[:,0]/var[0,0],atol=1e-11)
    assert np.all(np.diff(ll[:,2]-ll[:,0])>0)
    a=m.parent.filtered(x,h)[0];b=m.parent.filtered(x[:500],h)[0]
    np.testing.assert_array_equal(a[:500],b)
    assert m.parent.filtered(np.array([-10.]),h)[0][0,0]>.99
    assert m.parent.filtered(np.array([10.]),h)[0][0,2]>.99


def test_label_clock_and_sampled_risk():
    f=SimpleNamespace(days=np.arange(7),open=np.array([99,100,102,90,110,112,113.]),close=np.array([99,101,95,109,1,112,113.]))
    y=m.labels(f,3)
    assert y[0,0]==pytest.approx(np.log(110/100))
    assert y[0,1]==pytest.approx(-np.log(.9)) # excludes close[4]=1, after horizon exit
    assert np.isnan(y[-4:]).all()


@pytest.mark.parametrize('kind',['full','intercept'])
def test_forecast_prefix_and_maturation(kind):
    f,c=fixture();a=m.forecast(f,c,10,63,kind)
    ff=SimpleNamespace(**{k:v[:500] for k,v in vars(f).items()});cc={k:v[:500] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.forecast(ff,cc,10,63,kind)
    np.testing.assert_array_equal(a['prediction'][:500],b['prediction'])
    np.testing.assert_array_equal(a['mass'][:500],b['mass'])
    assert a['mass'][262]==0 and a['mass'][263]==pytest.approx(.1)
    f.open[500:]*=2;f.close[500:]*=2
    z=m.forecast(f,c,10,63,kind)
    np.testing.assert_array_equal(a['prediction'][:500],z['prediction'][:500])


def test_gate_cost_risk_and_continued_learning():
    f,c=fixture();fc=m.forecast(f,c,10,63);c['eligible']=np.ones(len(f.days),bool)
    _,u,a=m.gate(c,fc,5);_,v,b=m.gate(c,fc,20)
    assert np.all(v[252:]<u[252:]) and not np.any(b&~a)
    assert fc['mass'][-1]>0 and np.isfinite(fc['prediction'][252:]).all()
    pred=np.array([[.01,.02],[.001,.02]])
    out,u,a=m.gate(dict(eligible=np.array([True,True])),dict(prediction=pred),5)
    assert list(a)==[True,False] and list(out['eligible'])==[True,False]


@pytest.mark.parametrize('delay',[0,1])
def test_gate_cash_execution_and_disabled_control(delay):
    from test_regime_entry import fixture as old
    f,c=old(180);a=m.simulate(f,c,start=1,delay=delay)
    z=dict(prediction=np.tile([1.,0.],(len(f.days),1)))
    b=m.simulate(f,c,start=1,delay=delay,fc=z)
    np.testing.assert_array_equal(a['nav'],b['nav'])
    z['prediction'][:]=[-1.,0.];b=m.simulate(f,c,start=1,delay=delay,fc=z)
    assert len(b['fills'])==0 and np.all(b['nav'][1:]==1)
