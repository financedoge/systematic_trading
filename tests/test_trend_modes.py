from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from systematic_trading.research import trend_modes as model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_trend_modes as study  # noqa: E402


def prices(n=600):
    rng=np.random.default_rng(17)
    c=100*np.exp(np.cumsum(.0003+rng.normal(0,.012,n)))
    return dict(days=np.arange(n)+np.datetime64('2020-01-01'),open=c*.998,high=c*1.01,low=c*.99,close=c,volume=rng.uniform(50000,150000,n))


def test_range_and_missing_evidence_do_not_close_a_long_position():
    s=np.array([model.UNKNOWN,model.RANGE,model.UP,model.RANGE,model.RANGE,model.DOWN,model.RANGE,model.UP])
    assert model.desired_position(s,start=1).tolist()==[False,False,True,True,True,False,False,True]
    assert not model.desired_position(np.array([model.UNKNOWN,model.UP,model.UP]),start=1).any()


@pytest.mark.parametrize('delay',[0,1])
def test_binding_delayed_targets_and_exact_cash_ledger(delay):
    n=12
    f=SimpleNamespace(days=np.arange(n),open=np.array([100,100,110,95,90,105,110,88,102,103,104,105.]),close=np.linspace(100,110,n))
    state=np.array([0,1,-1,0,1,0,-1,0,1,1,0,-1],np.int8)
    out=model.simulate(f,dict(state=state),start=1,cost_bp=20,delay=delay)
    cash,units=1.,0.
    fills={e['fill']:e['side'] for e in out['events']}
    for t in range(1,n):
        if fills.get(t)=='buy':units,cash=cash/(f.open[t]*1.002),0.
        if fills.get(t)=='sell':cash,units=units*f.open[t]*.998,0.
        assert out['nav'][t]==pytest.approx(cash+units*f.close[t])
    assert out['events'][0]==dict(day=1,side='buy',fill=2+delay)
    assert out['events'][1]==dict(day=2,side='sell',fill=3+delay)
    assert all(e['exit_reason'] in ('down',None) for e in out['episodes'])


def test_features_classification_and_returns_are_prefix_causal():
    data=prices();a=model.Features.build(data);b=model.Features.build({k:v[:400] for k,v in data.items()})
    def check(x,y):
        if isinstance(x,dict):
            for k in x:check(x[k],y[k])
        else:np.testing.assert_allclose(x[:400],y,atol=1e-10,rtol=0,equal_nan=True)
    check(a.cache,b.cache)
    for c in study.grid('short')[::32]:
        ca,cb=model.classify(a,c),model.classify(b,c)
        for key in ('state','evidence'):np.testing.assert_array_equal(ca[key][:400],cb[key])
        sa,sb=model.simulate(a,ca,delay=1),model.simulate(b,cb,delay=1)
        np.testing.assert_allclose(sa['nav'][:400],sb['nav'],equal_nan=True,atol=1e-10,rtol=0)


def test_published_string_dates_are_supported_without_date_substitution():
    data=prices();data['days']=data['days'].astype(str)
    f=model.Features.build(data)
    assert len(f.truncated(data['days'][399]).days)==400


def test_separate_blocks_and_paired_price_volume_search_budget():
    for domain in ('short','long'):
        rows=study.grid(domain)
        assert len(rows)==384
        assert len({r['range']['length'] for r in rows})==4
        assert any(r['up']!=r['down'] for r in rows)
        for family in study.FAMILIES:assert sum(r['family']==family for r in rows)==64
        for method in model.METHODS:
            p=[r for r in rows if r['method']==method and not r['volume']]
            v=[r for r in rows if r['method']==method and r['volume']]
            for a,b in zip(p,v,strict=True):
                for mode in ('range','up','down'):assert a[mode]==b[mode]


def test_volume_evidence_is_invariant_to_share_unit_rescaling():
    data=prices();a=model.Features.build(data);data['volume']=data['volume']*1000;b=model.Features.build(data)
    for length in a.cache:
        for key in ('activity','pressure'):
            np.testing.assert_allclose(a.cache[length][key],b.cache[length][key],atol=1e-12,equal_nan=True)


def test_intact_prior_range_has_priority_and_needs_a_prior_box():
    data=prices();f=model.Features.build(data);c=study.grid('short')[0];length=c['range']['length']
    # Controlled independent detectors: both up and range qualify; box contains
    # today's close, while the up detector on its own is also strong.
    for feature in f.cache.values():
        feature['regression']['up'][:]=10;feature['regression']['down'][:]=-10
        feature['regression']['quality'][:]=1;feature['regression']['flat'][:]=0
        feature['width'][:]=1;feature['efficiency'][:]=0
    f.cache[length]['box_lower'][:]=0;f.cache[length]['box_upper'][:]=10000
    r=model.classify(f,c)
    assert np.all(r['state'][50:]==model.RANGE)
    f.cache[length]['box_upper'][:]=1
    r=model.classify(f,c)
    assert np.all(r['state'][50:]==model.UP)


def test_unresolved_direction_conflict_is_not_range():
    f=model.Features.build(prices());c=study.grid('short')[0]
    for feature in f.cache.values():
        feature['regression']['up'][:]=10;feature['regression']['down'][:]=10
        feature['regression']['quality'][:]=1;feature['regression']['flat'][:]=100
    r=model.classify(f,c)
    assert np.all(r['evidence'][50:]==model.UNKNOWN)
    assert np.all(r['state'][50:]==model.UNKNOWN)


def test_unsupported_input_is_not_filled():
    data=prices();data['volume'][100]=np.nan
    with pytest.raises(ValueError,match='volume'):model.Features.build(data)
