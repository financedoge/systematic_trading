from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import trained_review as m
from test_stop_review import flat,fixture,RULE


def fit(kind='price',margin=0,hold=0,recover=0):
    d=11 if kind=='price' else 14
    def model(value):
        beta=np.zeros((d,2));beta[0,0]=value
        return dict(beta=beta.tolist(),mean=np.zeros(d).tolist(),scale=np.ones(d).tolist(),kind=kind)
    return dict(kind=kind,margin=margin,models=dict(hold=model(hold),recover=model(recover)))


def state(f,c,level=97,owned=False):
    return dict(reference=100.,origin=2,peak=100.,level=level,risk=100*c['sigma'],owned=owned)


@pytest.mark.parametrize('delay',[0,1])
@pytest.mark.parametrize('cost',[5,10,20])
def test_disabled_control_exact(delay,cost):
    f,c=fixture(180);a=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,rule=RULE)
    b=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,rule=RULE,arm='stop',fit=fit(margin=None))
    np.testing.assert_array_equal(a['nav'],b['nav']);assert a['fills']==b['fills']


def test_label_stop_gap_and_full_maturity():
    f,c=flat();q=m.inputs(f);f.open[4]=90;f.low[4]=89
    a=m.path_label(f,c,q,3,state(f,c),'hold')
    assert a['exit_price']==pytest.approx(90*.9995)
    assert a['maturity']==14 and a['reason']=='stop'
    assert a['y'][0]==pytest.approx(-.0005/q['scale'][3])
    assert m.path_label(f,c,q,30,state(f,c),'hold') is None


def test_label_never_uses_todays_high_to_raise_stop():
    f,c=flat();q=m.inputs(f);f.high[4]=150;f.low[4]=98;f.low[5]=96
    a=m.path_label(f,c,q,3,state(f,c),'hold')
    assert a['exit_price']==pytest.approx(97*.9995)


def test_recovery_handoff_avoids_stale_hmm_exit():
    f,c=flat();f.low[3]=96;c['eligible'][3:]=False;c['fast_down'][3:]=True
    c['fast_probability'][3:]=[.9,.09,.01]
    a=m.simulate(f,c,start=1,arm='stop',fit=fit(hold=2,recover=2),rule=RULE)
    b=m.simulate(f,c,start=1,arm='stop',fit=fit(hold=2,recover=2),rule=RULE,handoff=False)
    assert a['episodes'][1]['entry_reason']=='exit_review'
    assert a['episodes'][1]['entry_index']==5 and a['episodes'][1]['exit_index'] is None
    assert b['episodes'][1]['exit_index']==6
    c['eligible'][8]=True;c['fast_down'][8]=False
    d=m.simulate(f,c,start=1,arm='stop',fit=fit(hold=2,recover=2),rule=RULE)
    assert d['episodes'][1]['handoff_index']==8 and d['episodes'][1]['exit_index']==10


def test_recovery_open_guard_and_emergency_protection():
    f,c=flat();f.low[3]=96;c['eligible'][3:]=False;c['fast_probability'][3:]=[.9,.09,.01]
    f.open[5]=110;f.high[5]=111
    a=m.simulate(f,c,start=1,arm='stop',fit=fit(hold=2,recover=2),rule=RULE)
    assert any('recovery_open_cancelled' in e['reasons'] for e in a['events'])
    f.open[5]=100;f.low[5]=95
    b=m.simulate(f,c,start=1,arm='stop',fit=fit(hold=2,recover=2),rule=RULE)
    assert b['episodes'][1]['entry_index']==b['episodes'][1]['exit_index']==5


def test_episode_weights_and_purged_training():
    rows=[dict(group='a',x=[1.]+[0.]*13,y=[1.,0.],t=t,maturity=t+11,task=task)
        for t in range(20) for task in ('hold','recover')]
    assert m.weights(rows).sum()==pytest.approx(1)
    a,b=m.fit_family(rows,'price',15)
    # Train origins only0..3, not origins4..14 with labels past split.
    assert b['models']['hold']['rows']==4
    np.testing.assert_allclose(np.array(b['models']['hold']['beta'])[0],[1,0])


def test_prefix_invariance_and_ledger():
    f,c=fixture(180);a=m.simulate(f,c,start=1,rule=RULE,arm='review',fit=fit('volume',hold=-.5,recover=.5),record=True)
    ff=SimpleNamespace(**{k:v[:110] if isinstance(v,np.ndarray) else v for k,v in vars(f).items()})
    cc={k:v[:110] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(ff,cc,start=1,rule=RULE,arm='review',fit=fit('volume',hold=-.5,recover=.5),record=True)
    for k in ('nav','stop','hold_value','recover_value','reviewer_owned','desired'):np.testing.assert_array_equal(a[k][:110],b[k])
    cash=1.;units=0.
    for t in range(1,len(f.days)):
        for e in [e for e in a['fills'] if e['session']==t]:
            sign=1 if e['side']=='buy' else -1;cash-=sign*e['price']*e['units']+e['fee'];units+=sign*e['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    for e in a['episodes']:
        stops=a['stop'][e['entry_index']:e['exit_index']];assert np.all(np.diff(stops[np.isfinite(stops)])>=0)


def test_shadow_prefix_and_delayed_labels():
    f,c=fixture(180);chosen=fit(hold=-.5,recover=.5)
    a=m.simulate(f,c,start=1,rule=RULE,arm='stop',fit=chosen,record=True);score=m.shadow_diagnostics(f,c,a,chosen)
    assert all(r['maturity']==r['origin']+11 for r in score)
    ff=SimpleNamespace(**{k:v[:110] if isinstance(v,np.ndarray) else v for k,v in vars(f).items()})
    cc={k:v[:110] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(ff,cc,start=1,rule=RULE,arm='stop',fit=chosen,record=True);prefix=m.shadow_diagnostics(ff,cc,b,chosen)
    assert prefix==[r for r in score if r['maturity']<110]
