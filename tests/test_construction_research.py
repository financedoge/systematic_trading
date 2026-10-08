from decimal import Decimal as D

import numpy as np
import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.construction_controls import (
    ConstantExposureOverlay, FinalWeightCapOverlay, ForecastRankPool, calibrate_exposure, gross, match_gross,
)
from systematic_trading.research.construction_analysis import bootstrap_ratios, ratio_metrics, ranks
from systematic_trading.research.construction_study import jobs, ARMS, COMPARISONS
from test_fallback_policy import fixture, pool, SYMBOLS


def targets(weights):
    return [AllocationTarget(symbol=s,sleeve='test',target_weight=D(w),rationale='test') for s,w in weights.items()]


def test_final_cap_keeps_cash_and_rejected_assets_without_renormalization():
    source=targets(dict(SPY='.6',GLD='.3',TLT='0'))
    capped=FinalWeightCapOverlay().apply(source,None)
    assert [t.target_weight for t in capped]==[D('.45'),D('.3'),D(0)]
    assert gross(capped)==D('.75')
    assert source[0].target_weight==D('.6')


def test_exposure_controls_match_only_the_budget_not_the_selection():
    source=targets(dict(SPY='.4',GLD='.3',TLT='.2'))
    reference=targets(dict(SPY='0',GLD='.15',TLT='0'))
    scaled=match_gross(source,reference)
    assert abs(gross(scaled)-gross(reference))<D('1e-25')
    assert {t.symbol for t in scaled if t.target_weight}>={'SPY','GLD','TLT'}
    assert scaled[0].target_weight/scaled[1].target_weight==source[0].target_weight/source[1].target_weight
    assert gross(match_gross(source,targets(dict(SPY='0',GLD='0',TLT='0'))))==0
    with pytest.raises(ValueError,match='increased exposure'):
        match_gross(reference,source)


@pytest.mark.parametrize('value',['NaN','Infinity','-.1','1.1'])
def test_invalid_scale_is_rejected(value):
    with pytest.raises(ValueError):ConstantExposureOverlay(D(value))


def test_calibration_never_reads_evaluation_decisions():
    def row(weight):return dict(known_through='2020-11-30',targets=[t.model_dump(mode='json') for t in targets(dict(SPY=weight))])
    a={'2020-12-01':row('.9'),'2021-01-04':None}
    b={'2020-12-01':row('.3'),'2021-01-04':{'poison':'must never be read'}}
    assert D(calibrate_exposure(a,b)['scale'])==D(1)/3
    a['2020-12-01']['known_through']='2020-12-01'
    with pytest.raises(ValueError,match='unavailable'):calibrate_exposure(a,b)


def test_forecast_ranking_overrides_composite_and_ties_are_deterministic():
    ts,context=fixture(SYMBOLS)
    base=pool('defensive_cash');base.top_n=4
    # All tied: alphabetical ordering, not incoming target order or composite.
    ranker=ForecastRankPool(base,{s:1. for s in SYMBOLS})
    selected=ranker.apply(list(reversed(ts)),context)
    assert {t.symbol for t in selected if t.target_weight>0}==set(sorted(SYMBOLS)[:4])
    assert abs(gross(selected)-gross(ts))<D('1e-20')


def test_forecast_rank_never_revives_negative_momentum_to_fill_n():
    ts,context=fixture(SYMBOLS[:4])
    base=pool('defensive_cash');base.top_n=10
    ranker=ForecastRankPool(base,{s:100. if s not in SYMBOLS[:4] else 0 for s in SYMBOLS})
    selected=ranker.apply(ts,context)
    assert {t.symbol for t in selected if t.target_weight>0}==set(SYMBOLS[:4])
    assert ranker.cash_budget_active is False


def test_forecast_rank_retains_defensive_fallback_and_rejects_missing_predictions():
    ts,context=fixture(['SPY','GLD'])
    ranker=ForecastRankPool(pool('defensive_cash'),{s:i for i,s in enumerate(SYMBOLS)})
    selected=ranker.apply(ts,context)
    assert ranker.cash_budget_active and {t.symbol for t in selected if t.target_weight>0}=={'GLD'}
    assert gross(selected)==D('.15')
    for forecasts in [{s:float('nan') for s in SYMBOLS},{'SPY':1}]:
        with pytest.raises(ValueError,match='forecasts'):ForecastRankPool(pool('defensive_cash'),forecasts).apply(ts,context)


def test_joint_month_bootstrap_identical_paths_and_cash_ratios():
    dates=['2021-01-04','2021-01-05','2021-02-01','2021-02-02','2021-02-03','2021-03-01']
    returns=[.01,-.02,.01,.005,-.01,.01]
    answer=bootstrap_ratios(dates,returns,returns,replications=200,block=1)
    assert answer['sharpe']['difference']==0 and answer['sharpe']['ci95']==[0,0]
    assert answer['calmar_252']['ci95']==[0,0]
    cash=bootstrap_ratios(dates,[0]*6,[0]*6,replications=20,block=1)
    assert cash['sharpe']['difference'] is None and cash['calmar_252']['ci95'] is None
    # Padding a short month does not add false zero-return observations.
    sample=np.array(returns)[None,:,None]
    padded=np.concatenate([sample,np.zeros((1,4,1))],axis=1)
    mask=np.concatenate([np.ones_like(sample,dtype=bool),np.zeros((1,4,1),dtype=bool)],axis=1)
    np.testing.assert_allclose(ratio_metrics(sample,np.ones_like(sample,dtype=bool)),ratio_metrics(padded,mask))


def test_finite_family_inventory_and_tie_ranks():
    assert len(jobs())==len(set(jobs()))==66
    assert len(ARMS)==16 and len(COMPARISONS)==15
    np.testing.assert_equal(ranks([3,1,3,2]),[2.5,0,2.5,1])
