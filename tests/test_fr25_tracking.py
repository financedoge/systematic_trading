from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from systematic_trading.research import fr25_tracking as f
from systematic_trading.research.strategy_catalog import fr25_definition, m1_14_definition, registered_strategy_definition, instantiate_overlays
from systematic_trading.research.strategy_diagram import decision_diagrams
from systematic_trading.research.strategy_lifecycle import replay_supported


def test_frozen_selection_recipe_preserves_downstream_stack_and_cap():
    d, parent = fr25_definition(), m1_14_definition()
    assert registered_strategy_definition(f.KEY) == d and replay_supported(f.KEY)
    assert d.overlays[1:-1] == parent.overlays[1:]
    assert d.overlays[0].parameters == f.PARAMETERS
    assert d.overlays[-1].kind == 'final_weight_cap'
    assert d.universe_key == 'multi_asset_14' and d.promoted_on is None
    assert isinstance(instantiate_overlays(d)[0], f.FinancialRankSelection)
    diagram = decision_diagrams(d, 'USD')[0]['svg']
    assert '75% M1 rank + 25% financial' in diagram
    assert 'positive' in diagram.lower() and '126d' in diagram
    assert 'zero selection weight' in diagram


def test_prediction_requires_exact_clock_universe_and_completed_labels():
    history = {'SPY':[SimpleNamespace(trade_date=date(2026,10,9))]}
    model = dict(known_through='2026-10-09',last_label_end='2026-10-01',ready=False)
    schedule = dict(parameters=f.PARAMETERS,models={'2026-10-12':model})
    assert f.prediction(schedule,history,'2026-10-12') is model
    with pytest.raises(ValueError,match='schedule required'):f.prediction(None,history,'2026-10-12')
    with pytest.raises(ValueError,match='Exact FR25'):f.prediction(schedule,history,'2026-10-13')
    model['last_label_end']='2026-10-12'
    with pytest.raises(ValueError,match='cutoffs differ'):f.prediction(schedule,history,'2026-10-12')
    model.update(last_label_end='2026-10-01',ready=True,models={'TLT':{}})
    with pytest.raises(ValueError,match='universe changed'):f.prediction(schedule,history,'2026-10-12')


def test_late_capture_abstains_and_missing_exact_vintage_is_not_filled(monkeypatch):
    class Reader:
        def __init__(self, **kwargs):pass
        def snapshot(self, s, v):return dict(first_seen_at='2026-10-10T20:00:00+00:00')
    monkeypatch.setattr(f,'EconomicInputs',Reader)
    monkeypatch.setattr(f,'panel',lambda r,v,k,**kw:dict(vintage=v,known_at=k.isoformat(),
        sources={s:{} for s in f.SERIES},features={s:'1' for s in f.FEATURES},
        unavailable=[],financial_ready=True))
    inputs=dict(pin={},known={'2026-10-09':'2026-10-08','2026-10-12':'2026-10-09'},
        entries=[dict(series=s,vintage=v) for s in f.SERIES for v in ['2026-10-07','2026-10-08']])
    states=f.feature_states(inputs)
    assert states['2026-10-09']['financial_ready']
    assert not states['2026-10-12']['financial_ready']
    assert states['2026-10-12']['features']=={}
    assert {v['reason'] for v in states['2026-10-12']['unavailable']}=={'not_captured_before_decision'}
    inputs['entries']=[]
    assert {v['reason'] for v in f.feature_states(inputs)['2026-10-12']['unavailable']}=={'unpublished_exact_vintage'}


def test_unrelated_economic_series_does_not_invalidate_financial_recipe(monkeypatch):
    catalog={'snapshots':[dict(series='T10Y2Y',vintage='2026-09-29',batch='same',root='immutable')]}
    class Reader:
        def __init__(self,**kwargs):self.catalog=deepcopy(catalog)
        def snapshot(self,*a):return {}
    monkeypatch.setattr(f,'load_catalog',lambda a:({},dict(root='catalog',batch='catalog-pin')))
    monkeypatch.setattr(f,'EconomicInputs',Reader)
    bars={'SPY':[dict(trade_date=d) for d in ['2026-09-30','2026-10-01','2026-10-02']]}
    before=f.economic_inputs(None,bars,'2026-10-01')['provenance']
    catalog['snapshots'].append(dict(series='PAYEMS',vintage='2026-09-29',batch='new',root='new'))
    assert f.economic_inputs(None,bars,'2026-10-01')['provenance']==before
    catalog['snapshots'][0]['batch']='changed'
    assert f.economic_inputs(None,bars,'2026-10-01')['provenance']!=before


def test_financial_only_panel_never_reads_unrelated_context(monkeypatch):
    from systematic_trading.research import economic_financial as e
    from datetime import datetime
    monkeypatch.setattr(e,'original_panel',lambda *a:pytest.fail('Unrelated context read'))
    class Reader:
        def snapshot(self,s,v):
            assert s in f.SERIES
            return dict(archive_available_at='2026-10-08T01:00:00+00:00',last='2026-10-08',
                usable=False,observations=[],series=dict(max_age_days=400))
    state=e.panel(Reader(),'2026-10-08',datetime.fromisoformat('2026-10-09T20:00:00+00:00'),include_context=False)
    assert not state['financial_ready'] and len(state['unavailable'])==5


def test_fr25_cannot_be_allocated_without_separate_execution_contract(monkeypatch):
    from systematic_trading.live import strategy_control as c
    monkeypatch.setattr(c,'require_monitored',lambda *a:dict(monitored=[f.KEY]))
    with pytest.raises(ValueError,match='Trading allocations currently support'):
        c.candidate_evidence(SimpleNamespace(),f.KEY,store=SimpleNamespace())
