from datetime import date, timedelta

import numpy as np
import pytest

from systematic_trading.research.usd_index_governance import audit_snapshot
from systematic_trading.research.momentum_analysis import holm, paired_bootstrap


def snapshot():
    first=date(2020,1,1)
    rows=['observation_date,DTWEXBGS_20200429']
    rows += [f'{first+timedelta(days=i)},{100+i/100}' for i in range(115) if (first+timedelta(days=i)).weekday()<5]
    return '\n'.join(rows),dict(vintage_date='2020-04-29',known_through='2020-04-30',decision_date='2020-05-01')


def test_usd_vintage_identity_availability_and_no_cross_vintage_rebasing():
    text,meta=snapshot();row=audit_snapshot(text,meta)
    assert set(row['features'])=={'USD21','USD63'}
    scaled='\n'.join(text.splitlines()[:1]+[d+','+str(float(v)*1.014163) for d,v in (r.split(',') for r in text.splitlines()[1:])])
    other=audit_snapshot(scaled,meta)
    assert row['features']==pytest.approx(other['features'],abs=1e-14)
    with pytest.raises(ValueError,match='precede'):audit_snapshot(text,dict(meta,vintage_date='2020-04-30'))
    with pytest.raises(ValueError,match='identity'):audit_snapshot(text.replace('20200429','20200428'),meta)
    with pytest.raises(ValueError,match='Future'):audit_snapshot(text+'\n2020-05-01,110',meta)


def test_holm_includes_reserved_slots_and_bootstrap_preserves_pairing():
    assert holm([.01,.04,1.,1.])==pytest.approx([.04,.12,1.,1.])
    rng=np.random.default_rng(3);x=rng.normal(.001,.01,60)
    matrix=np.column_stack([x,-x,np.zeros(60),np.full(60,np.nan)])
    result=paired_bootstrap(matrix,6,2000,42)
    assert result[0]['mean_annual']==pytest.approx(-result[1]['mean_annual'])
    assert result[0]['p']==result[1]['p']
    assert result[2]['p']==1 and result[3]['p']==1
    assert result[0]['ci95']==pytest.approx([-v for v in reversed(result[1]['ci95'])])


def test_ridge_excludes_uncompleted_labels_and_uses_asset_specific_usd_coefficients():
    from systematic_trading.research.usd_momentum_model import ridge_predict
    records=[]
    for i in range(72):
        year,month=2015+i//12,1+i%12
        known=f'{year:04d}-{month:02d}-01'
        label_end=f'{year:04d}-{month:02d}-28'
        for s,sign in [('A',1),('B',-1)]:
            records.append(dict(symbol=s,known_through=known,label_end=label_end,label=sign*(i%7)/100,
                features=dict(S=0,L=0,vol63=.2,USD21=(i%7)/10,USD63=(i%5)/20)))
    current={s:dict(S=0,L=0,vol63=.2,USD21=.6,USD63=.1) for s in ['A','B']}
    assert ridge_predict(records,current,'2019-12-01',True) is None
    original=ridge_predict(records,current,'2020-06-01',True)
    for r in records:
        if r['label_end']>='2020-06-01':r['label']=9999;r['features']['USD21']=9999
    assert ridge_predict(records,current,'2020-06-01',True)==original
    assert original['models']['A']['coefficients'][3]>0
    assert original['models']['B']['coefficients'][3]<0


def test_usd_tilt_preserves_gross_zero_weights_and_active_bounds():
    from decimal import Decimal as D
    from systematic_trading.domain.portfolio import AllocationTarget
    from systematic_trading.research.usd_momentum_model import apply_usd_predictions
    weights={'SPY':D('.4'),'VGK':D('.3'),'IEF':D('.2'),'GLD':D(0)}
    targets=[AllocationTarget(symbol=s,sleeve='test',target_weight=w,rationale='test') for s,w in weights.items()]
    result=apply_usd_predictions(targets,{'SPY':.01,'VGK':0,'IEF':-.01,'GLD':.02})
    assert sum(t.target_weight for t in result)==pytest.approx(D('.9'),abs=D('1e-20'))
    assert next(t.target_weight for t in result if t.symbol=='GLD')==0
    assert all(abs(t.target_weight-weights[t.symbol])<=D('.03')+D('1e-20') for t in result)
