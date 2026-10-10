from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.trend import AssetPoolFilterOverlay,AssetPoolSelectionScore
from systematic_trading.research.candidate_pool import CandidatePool
from systematic_trading.research.selection_blend import SelectionBlend,match_gross


def inputs(monkeypatch,eligible=14):
    symbols=[f'A{i:02}' for i in range(14)]
    scores={s:AssetPoolSelectionScore(total=D(i),components={},raw_metrics={
        'shortMomentum':D('.1'),'mediumMomentum':D('.1'),'longMomentum':D('.1') if i<eligible else D('-.1'),
        'upVolumeShare':D('.5'),'signedVolumePressure':D(0)}) for i,s in enumerate(symbols)}
    monkeypatch.setattr(CandidatePool,'_selection_scores',lambda self,targets,context:scores)
    xgb={s:-i/100 for i,s in enumerate(symbols)}
    ridge=dict(ready=True,models={s:dict(linear_forecast=-i/100,mean_return=i/100) for i,s in enumerate(symbols)})
    targets=[AllocationTarget(symbol=s,sleeve='test',target_weight=D('.98')/14,rationale='test') for s in symbols]
    context=SimpleNamespace(bars_by_symbol={s:[None]*130 for s in symbols})
    return symbols,scores,xgb,ridge,targets,context


def test_equal_blend_changes_membership_but_never_forces_an_ineligible_asset(monkeypatch):
    symbols,scores,xgb,ridge,targets,context=inputs(monkeypatch,eligible=10)
    selector=SelectionBlend(AssetPoolFilterOverlay(min_selected=4,fallback_policy='defensive_cash'),
        dict(blend='EQ'),xgb,ridge)
    selected=selector.apply(targets,context)
    held=[t.symbol for t in selected if t.target_weight>0]
    assert held==symbols[:6]
    assert all(scores[s].raw_metrics['longMomentum']>0 for s in held)
    assert len(held)==6


def test_unavailable_ridge_reverts_entire_selector_to_original_order(monkeypatch):
    symbols,_,xgb,ridge,targets,context=inputs(monkeypatch)
    ridge['ready']=False
    selector=SelectionBlend(AssetPoolFilterOverlay(min_selected=4,fallback_policy='defensive_cash'),dict(blend='EQ'),xgb,ridge)
    output=selector.apply(targets,context)
    assert selector.abstained
    assert [t.symbol for t in output if t.target_weight>0]==symbols[-6:]


def test_mean_control_and_total_forecast_have_distinct_registered_rankings(monkeypatch):
    _,_,xgb,ridge,targets,context=inputs(monkeypatch)
    parent=AssetPoolFilterOverlay(min_selected=4)
    model=SelectionBlend(parent,dict(blend='EQ'),xgb,ridge)
    mean=SelectionBlend(parent,dict(blend='EQ',mean_only=True),xgb,ridge)
    a=model._selection_scores(targets,context)
    b=mean._selection_scores(targets,context)
    assert a['A00'].total>a['A13'].total
    assert b['A00'].total<b['A13'].total


def test_missing_predictor_fails_closed_instead_of_renormalizing(monkeypatch):
    _,_,xgb,ridge,targets,context=inputs(monkeypatch)
    del xgb['A00']
    selector=SelectionBlend(AssetPoolFilterOverlay(),dict(blend='EQ'),xgb,ridge)
    with pytest.raises(ValueError,match='Incomplete XGBoost'):
        selector.apply(targets,context)


def test_ties_keep_shared_midrank_and_alphabetical_selection(monkeypatch):
    symbols,_,xgb,ridge,targets,context=inputs(monkeypatch)
    # Equal and opposite ranks cancel exactly in the half-and-half blend.
    selector=SelectionBlend(AssetPoolFilterOverlay(min_selected=4),dict(blend='X50'),xgb,ridge)
    out=selector.apply(targets,context)
    assert [t.symbol for t in out if t.target_weight>0]==symbols[:6]
    assert len({D(r['combined']) for r in selector.rank_table.values()})==1


def test_matched_gross_preserves_membership_and_reports_cap_capacity():
    targets=[AllocationTarget(symbol=s,sleeve='test',target_weight=D(w),rationale='test')
             for s,w in [('A','.4'),('B','.2'),('C','0')]]
    out,info=match_gross(targets,D('.8'))
    assert info['matched'] and sum(t.target_weight for t in out)==D('.8')
    assert out[0].target_weight==D('.45') and out[2].target_weight==0
    out,info=match_gross(targets,D('.98'))
    assert not info['matched'] and sum(t.target_weight for t in out)==D('.90')
