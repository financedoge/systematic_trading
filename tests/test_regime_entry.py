from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import regime_entry as m
from systematic_trading.research import coupled_trends


def fixture(n=180):
    from test_thesis_exit import fixture as old
    f,c,_,_=old(n)
    return f,m.thesis_exit.classification(c,m.thesis_exit.grid(c['parameters'])[0],dict(enabled=True,floor=.2,count=2))


@pytest.mark.parametrize('cost',[5,10,20])
@pytest.mark.parametrize('delay',[0,1])
def test_exact_fixed_control_and_ledger(cost,delay):
    f,c=fixture();a=m.simulate(f,c,start=1,cost_bp=cost,delay=delay)
    b=coupled_trends.simulate(f,c,start=1,cost_bp=cost,delay=delay)
    np.testing.assert_allclose(a['nav'],b['nav'],atol=2e-14,rtol=0)
    cash=1.;units=0.;fills={e['session']:e for e in a['fills']}
    for t in range(1,len(f.days)):
        if t in fills:
            e=fills[t];sgn=1 if e['side']=='buy' else -1
            cash-=sgn*e['units']*e['price']+e['fee'];units+=sgn*e['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-13)
    for e in a['episodes']:
        assert e['entry_index']==e['entry_signal']+1+delay
        if e['exit_index'] is not None:assert e['exit_index']==e['exit_signal']+1+delay
        stops=a['stop'][e['entry_index']:e['exit_index']];assert np.all(np.diff(stops[np.isfinite(stops)])>=0)


@pytest.mark.parametrize('delay',[0,1])
def test_guard_prefix_and_disabled(delay):
    f,c=fixture();guard=dict(enabled=True,count=2,advance=.5)
    a=m.simulate(f,c,start=1,guard=guard,delay=delay)
    ff=SimpleNamespace(**{k:v[:100] for k,v in vars(f).items()})
    cc={k:v[:100] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(ff,cc,start=1,guard=guard,delay=delay)
    for key in ('nav','desired','stop','run','anchor','blocked'):np.testing.assert_array_equal(a[key][:100],b[key])
    np.testing.assert_array_equal(m.simulate(f,c,start=1)['nav'],m.simulate(f,c,start=1,guard=dict(enabled=False))['nav'])


def test_guards_require_confirmation_without_permanent_pause():
    f,c=fixture(80);f.close[:]=100*np.exp(np.arange(80)*.004);f.open[:]=f.close
    c['sigma']=.01;c['fast_probability'][:]=[.02,.08,.9];c['fast_slope'][:]=.004
    c['aligned'][:]=False;c['eligible'][:]=True;c['fast_down'][:]=False
    a=m.simulate(f,c,start=1,guard=dict(enabled=True,count=3,advance=.5))
    assert a['episodes'][0]['entry_signal']==3
    assert a['blocked'][1] and a['blocked'][2]
    c['aligned'][:]=True
    b=m.simulate(f,c,start=1,guard=dict(enabled=True,count=3,advance=.5))
    assert b['episodes'][0]['entry_signal']==1


def test_hmm_constraints_and_causal_filter():
    rng=np.random.default_rng(78);x=np.r_[rng.normal(-.3,.06,250),rng.normal(0,.04,250),rng.normal(.25,.08,250)]
    h=m.fit_hmm(x,.05,iterations=8)
    assert h['means'][0][0]<=-.1 and h['means'][1][0]==0 and h['means'][2][0]>=.1
    assert h['variance'][1][0]<=.05**2
    a=m.filtered(x,h)[0];b=m.filtered(x[:600],h)[0]
    np.testing.assert_array_equal(a[:600],b);np.testing.assert_allclose(a.sum(axis=1),1)
    assert a[200,0]>.95 and a[450,1]>.8 and a[700,2]>.9
    initial=m.fit_hmm(x,.1,iterations=1)
    assert initial['means'][0][0]<=-.2 and initial['means'][2][0]>=.2


def test_dependence_known_beta_alpha():
    x=np.random.default_rng(9).normal(.0003,.01,400)
    z=m.dependence(.0001+.4*x,x)
    assert z['beta']==pytest.approx(.4)
    assert z['alpha_annual']==pytest.approx(.0252)
    assert z['correlation']==pytest.approx(1.)


def test_reentry_after_loss_needs_fresh_reset_and_extra_close():
    f,c=fixture(70);f.close[:]=100;f.open[:]=100
    c['sigma']=.01;c['aligned'][:]=False;c['fast_probability'][:]=[.02,.08,.9]
    c['fast_slope'][:]=.002;c['eligible'][:]=True;c['fast_down'][:]=False
    f.close[2:6]=np.arange(101,105);f.open[2:6]=f.close[2:6]
    c['fast_down'][5]=True;f.open[6]=95;f.close[6:10]=95
    c['fast_probability'][10]=[.5,.3,.2];c['eligible'][10]=False;f.close[10]=95
    f.close[11:]=95*np.exp(np.arange(1,60)*.005);f.open[11:]=f.close[11:]
    a=m.simulate(f,c,start=1,guard=dict(enabled=True,count=2,advance=.5))
    assert a['episodes'][0]['net_return']<0
    assert a['episodes'][1]['entry_signal']==13
    assert a['required'][11]==3 and a['blocked'][11] and a['blocked'][12]
