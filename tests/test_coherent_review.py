from types import SimpleNamespace
import numpy as np
import pytest
from systematic_trading.research import coherent_review as m
from test_stop_review import flat,fixture,RULE


def fit(kind='price',enabled=True):
    d=6 if kind=='price' else 9
    return dict(kind=kind,enabled=enabled,margin=.05,change=.10,
        model=dict(beta=np.zeros(d).tolist(),mean=np.zeros(d).tolist(),scale=np.ones(d).tolist(),constant=0))


@pytest.mark.parametrize('cost',[5,10,20])
@pytest.mark.parametrize('delay',[0,1])
def test_disabled_exact_parent(cost,delay):
    f,c=fixture();a=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,rule=RULE)
    b=m.simulate(f,c,start=1,cost_bp=cost,delay=delay,rule=RULE,arm='review',fit=fit('volume',False))
    np.testing.assert_array_equal(a['nav'],b['nav']);assert a['fills']==b['fills']


def test_same_information_cannot_reverse_trade_decision():
    for score in np.linspace(-4,4,101):
        # Same-state decisions are disjoint, even without a change requirement.
        hold,recover=m.decisions(score,0,.02,.0005,change=0)
        assert not(hold and recover)
        assert m.decisions(score,score,.02,.0005)==(False,False)
    f,c=flat()
    for score in (-1.,1.):
        a=m.simulate(f,c,start=1,rule=RULE,arm='review',fit=fit(),score_override=np.full(len(f.days),score))
        assert len(a['episodes'])==1 and a['episodes'][0]['exit_index'] is None


def test_new_evidence_required_then_exit_at_next_open():
    f,c=flat();s=np.full(len(f.days),-.2);s[5:]=-.25;s[8:]=-.5
    a=m.simulate(f,c,start=1,rule=RULE,arm='stop',fit=fit(),score_override=s)
    assert a['episodes'][0]['entry_index']==2
    assert a['episodes'][0]['exit_signal']==8 and a['episodes'][0]['exit_index']==9
    assert a['episodes'][0]['exit_reason']=='entry_invalidated'


@pytest.mark.parametrize('delay',[0,1])
def test_recovery_cost_change_handoff_and_protection(delay):
    f,c=flat();entry=2+delay;f.low[entry]=96;c['eligible'][entry:]=False
    c['fast_probability'][entry:]=[.9,.09,.01];c['fast_down'][entry:]=True
    s=np.full(len(f.days),-.2);s[entry+1:]=.3
    a=m.simulate(f,c,start=1,rule=RULE,arm='stop',fit=fit(),score_override=s,delay=delay)
    r=a['episodes'][1];assert r['entry_reason']=='exit_review' and r['exit_index'] is None
    assert r['entry_index']==entry+2+delay
    # Original HMM cannot terminate a recovery while its buy is pending.
    assert all(e['side']=='buy' or e['session']<=entry for e in a['fills'])
    f.low[r['entry_index']]=95
    b=m.simulate(f,c,start=1,rule=RULE,arm='stop',fit=fit(),score_override=s,delay=delay)
    assert b['episodes'][1]['entry_index']==b['episodes'][1]['exit_index']


def test_gap_cancel_and_no_same_day_recovery():
    f,c=flat();f.low[2]=96;c['eligible'][2:]=False;c['fast_probability'][2:]=[.9,.09,.01]
    s=np.full(len(f.days),-.2);s[3:]=.3;f.open[4]=110
    a=m.simulate(f,c,start=1,rule=RULE,arm='stop',fit=fit(),score_override=s)
    assert any('recovery_open_cancelled' in e['reasons'] for e in a['events'])
    assert not a['review_signal'][2]


def test_label_clock_scaling_and_rolling_purge():
    f,c=fixture(900);q=m.inputs(f);ix,y=m.observations(f,q)
    np.testing.assert_allclose(y*q['scale'][ix],f.open[ix+2]/f.open[ix+1]-1)
    a=m.fit_family(f,'price')
    assert a['last_maturity']==str(f.days[-1])
    for fold in a['selection']['folds']:
        assert fold['training_last_origin']<fold['training_last_maturity']<fold['first']
    if a['enabled']:
        assert a['model']['ridge'] is not None and a['selection']['fold_wins']>=2
        assert a['selection']['relative_loss_gain']>.005


def test_constant_model_abstains():
    f,c=fixture(900);f.open[:]=100
    a=m.fit_family(f,'volume')
    assert a['model']['ridge'] is None and not a['enabled']


def test_prefix_invariance_and_accounting():
    f,c=fixture(180);chosen=fit('volume');chosen['model']['beta'][1]=.2
    a=m.simulate(f,c,start=1,rule=RULE,arm='review',fit=chosen)
    ff=SimpleNamespace(**{k:v[:110] if isinstance(v,np.ndarray) else v for k,v in vars(f).items()})
    cc={k:v[:110] if isinstance(v,np.ndarray) else v for k,v in c.items()}
    b=m.simulate(ff,cc,start=1,rule=RULE,arm='review',fit=chosen)
    for k in ('nav','stop','shared_score','decision_anchor','desired'):
        np.testing.assert_array_equal(a[k][:110],b[k])
    cash=1.;units=0.
    for t in range(1,len(f.days)):
        for e in [e for e in a['fills'] if e['session']==t]:
            sign=1 if e['side']=='buy' else -1;cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
        assert a['nav'][t]==pytest.approx(cash+units*f.close[t],abs=1e-12)
    for e in a['episodes']:
        stops=a['stop'][e['entry_index']:e['exit_index']];assert np.all(np.diff(stops[np.isfinite(stops)])>=0)
