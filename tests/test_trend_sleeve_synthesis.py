"""Mathematical and historical-preview contracts; no new trading rules."""
import importlib.util
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('synthesis',ROOT/'scripts/build_trend_sleeve_synthesis.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def charts():
    days=np.arange(np.datetime64('2020-01-01'),np.datetime64('2020-01-01')+np.timedelta64(300,'D')).astype(str).tolist()
    out={}
    for j in range(3):
        ret=.0004*(j+1)+.003*np.sin(np.arange(299)*.7+j)
        nav=np.r_[100,100*np.cumprod(1+ret)].tolist()
        out[f'E{j}_late']=dict(days=days.copy(),arms=dict(baseline=dict(nav=nav,held=[bool(j%2)]*300)))
    return out


def test_rank_only_reads_through_cutoff():
    c=charts();date=c['E0_late']['days'][280]
    a,_=s.rank_preview(c,date)
    for q in c.values():q['arms']['baseline']['nav'][281:]=[1e9]*19
    b,_=s.rank_preview(c,date)
    assert a==b
    assert len(a)==3 and [r['rank'] for r in a]==[1,2,3]


def test_zero_variance_not_ranked_and_no_cash_renormalization():
    c=charts();q=c['E0_late'];q['arms']['baseline']['nav']=[100]*300
    r,x=s.rank_preview(c,q['days'][-1]);assert len(r)==2
    for row in r:row['active']=False
    a=s.allocation(r,x,15,'equal')
    assert a['cash']==1 and a['invested']==0
    np.testing.assert_allclose(a['weights'],[.5,.5])


def test_equal_risk_uses_covariance_not_inverse_variance():
    # Orthogonal sine waves yield exactly diagonal covariance at different scales.
    t=np.arange(252);x={'A':.01*np.sin(2*np.pi*t/252),'B':.02*np.sin(4*np.pi*t/252)}
    rows=[dict(symbol='A',active=True),dict(symbol='B',active=False)]
    a=s.allocation(rows,x,2,'risk')
    np.testing.assert_allclose(a['weights'],[2/3,1/3],atol=1e-6)
    assert a['erc_error']<1e-6
    assert abs(a['cash']-1/3)<1e-6


def test_unaligned_calendars_rejected():
    import pytest
    c=charts();c['E1_late']['days'][200]='2019-12-31'
    with pytest.raises(ValueError,match='Unaligned'):s.rank_preview(c,c['E0_late']['days'][-1])


def test_all_frozen_models_and_preview_conservation():
    out=ROOT/'research/trend-sleeve-synthesis-20261029-v1'
    models=s.read(out/'selected-models.json');assert len(models)==102
    for q in models.values():
        h=q['fast_hmm'];mu=np.array(h['means']).ravel();v=np.array(h['variance']).ravel()
        assert mu[0]==-mu[2] and mu[1]==0 and v[0]==v[2]
        np.testing.assert_allclose(np.sum(h['transition'],axis=1),1,atol=1e-12)
        assert q['sigma']>0
        assert q['training_end']<('2023-01-03' if q['era']=='late' else '2020-01-02')
    p=s.read(out/'rank-preview.json')
    for variants in p['allocations'].values():
        for a in variants.values():
            assert abs(sum(a['weights'])-1)<1e-12
            assert abs(a['cash']+a['invested']-1)<1e-12
            assert min(a['weights'])>0
    assert s.read(out/'provenance.json')['exact_parent_return_comparisons']==612
