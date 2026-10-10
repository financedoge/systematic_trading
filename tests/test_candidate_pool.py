from datetime import date, timedelta
from decimal import Decimal as D
import math

import pytest

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext, apply_target_overlays
from systematic_trading.signals.trend import AssetPoolFilterOverlay
from systematic_trading.research.candidate_pool import CandidatePool, audited_bar, audited_activity_features, AuditedActivity
from systematic_trading.research.flow_concentration import FlowConcentrationSpec


def fixture():
    symbols=['SPY','VGK','EWJ','EWH','EWY','MCHI','GLD','IEF','TLT','LQD','HYG','DBC','XLE','XLB']
    histories={}
    for j,s in enumerate(symbols):
        values=[D(str(100*math.exp((.001+j*.0001)*i+.01*math.sin(i*.7)))) for i in range(501)]
        histories[s]=[PriceBar(trade_date=date(2018,1,1)+timedelta(days=i),open=p,high=p,low=p,close=p,volume=1000+i*3) for i,p in enumerate(values)]
    targets=[AllocationTarget(symbol=s,sleeve='test',target_weight=D('.98')/len(symbols),rationale='test') for s in symbols]
    context=SignalContext(as_of=date(2018,1,1)+timedelta(days=500),instruments={},bars_by_symbol=histories,trade_dates=[])
    return targets,context


def parent():return AssetPoolFilterOverlay(top_n=6,min_selected=4,fallback_policy='defensive_cash')


def test_existing_policy_exact_selector_parity():
    targets,context=fixture()
    assert CandidatePool(parent(),'M0').apply(targets,context)==parent().apply(targets,context)


@pytest.mark.parametrize('policy',['M0','M1','M2','M3'])
def test_additions_must_qualify_and_win_slot(policy):
    targets,context=fixture()
    # Make new ETFs persistently falling while all original ETFs rise.
    bars=dict(context.bars_by_symbol)
    for s in ['XLE','XLB']:
        bars[s]=[r.model_copy(update=dict(close=D(10000)/r.close)) for r in bars[s]]
    changed=SignalContext(as_of=context.as_of,instruments={},bars_by_symbol=bars,trade_dates=[])
    selector=CandidatePool(parent(),policy)
    output=selector.apply(targets,changed)
    assert len([r for r in output if r.target_weight>0])==6
    assert all(r.target_weight==0 for r in output if r.symbol in ['XLE','XLB'])
    assert not set(['XLE','XLB']) & set(selector.observation['eligible'])


def test_defensive_fallback_keeps_incoming_budget():
    targets,context=fixture();bars=dict(context.bars_by_symbol)
    for s in bars:
        if s!='GLD':bars[s]=[r.model_copy(update=dict(close=D(10000)/r.close)) for r in bars[s]]
    context=SignalContext(as_of=context.as_of,instruments={},bars_by_symbol=bars,trade_dates=[])
    selector=CandidatePool(parent(),'M0');output=apply_target_overlays(targets,[selector],context)
    assert selector.cash_budget_active
    assert {r.symbol for r in output if r.target_weight>0}=={'GLD'}
    assert sum(r.target_weight for r in output)==next(r.target_weight for r in targets if r.symbol=='GLD')


def test_skip_month_momentum_gate_ignores_latest_month_crash():
    targets,context=fixture();bars=dict(context.bars_by_symbol)
    bars['SPY']=[r.model_copy(update=dict(close=D(1))) if i>=len(bars['SPY'])-21 else r for i,r in enumerate(bars['SPY'])]
    context=SignalContext(as_of=context.as_of,instruments={},bars_by_symbol=bars,trade_dates=[])
    a=CandidatePool(parent(),'M0')._selection_scores(targets,context)['SPY'].raw_metrics['longMomentum']
    b=CandidatePool(parent(),'M2')._selection_scores(targets,context)['SPY'].raw_metrics['longMomentum']
    assert a<0<b


@pytest.mark.parametrize('key,value',[('raw_volume',None),('raw_volume',1.5),('raw_close',None),('raw_close',0)])
def test_unsupported_raw_input_fails_closed(key,value):
    row=dict(symbol='XLE',trade_date='2020-01-02',raw_open=10,raw_high=10,raw_low=10,raw_close=10,raw_volume=100)
    row[key]=value
    with pytest.raises(ValueError):audited_bar(row,raw=True)


def test_raw_turnover_and_adjusted_confirmation_across_split():
    _,context=fixture();adjusted=context.bars_by_symbol;raw={}
    for s,rows in adjusted.items():
        # A split changes raw shares and raw price, but not raw dollar activity.
        raw[s]=[r.model_copy(update=dict(close=r.close*(2 if i<490 else 1),volume=r.volume//2 if i<490 else r.volume)) for i,r in enumerate(rows)]
    spec=FlowConcentrationSpec(difference_lag=20)
    features=audited_activity_features(adjusted,raw,spec)
    for s,rows in adjusted.items():
        assert features[s]['momentum_20']==float(rows[-1].close/rows[-21].close-1)>0
    # Current/future raw bars cannot influence a causal decision.
    targets,_=fixture();before=AuditedActivity(spec,raw).apply(targets,context)
    future={s:rows+[rows[-1].model_copy(update=dict(trade_date=context.as_of,close=D(1),volume=999999))] for s,rows in raw.items()}
    assert AuditedActivity(spec,future).apply(targets,context)==before


def test_input_calendar_mismatch_is_rejected():
    _,context=fixture();raw=dict(context.bars_by_symbol);raw['XLE']=raw['XLE'][:-1]
    with pytest.raises(ValueError,match='calendars'):audited_activity_features(context.bars_by_symbol,raw,FlowConcentrationSpec(difference_lag=20))
