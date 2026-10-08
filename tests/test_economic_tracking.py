from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research import economic_tracking as e
from systematic_trading.research.strategy_catalog import defensive_cash_definition, economic_context_definition, instantiate_overlays
from systematic_trading.research.strategy_diagram import decision_diagrams
from systematic_trading.research.strategy_lifecycle import replay_supported


def test_complete_registered_recipe_preserves_parent_and_fixed_contract():
    d = economic_context_definition()
    assert d.key == e.KEY and replay_supported(e.KEY)
    assert d.overlays[:-2] == defensive_cash_definition().overlays
    assert [o.kind for o in d.overlays[-2:]] == ['final_weight_cap','economic_ridge']
    assert d.overlays[-1].parameters == e.PARAMETERS
    assert d.state == 'tracked' and d.promoted_on is None
    assert 'actual app capture' in decision_diagrams(d,'USD')[0]['svg']
    assert len(instantiate_overlays(d)) == len(d.overlays)


def test_overlay_requires_exact_published_decision_and_known_date():
    history = {'SPY':[SimpleNamespace(trade_date=date(2026,10,6))]}
    context = SimpleNamespace(bars_by_symbol=history,as_of=date(2026,10,7))
    target = AllocationTarget(symbol='SPY',sleeve='test',target_weight=Decimal('.4'),rationale='capped')
    with pytest.raises(ValueError,match='schedule required'):
        e.EconomicRidgeOverlay().apply([target],context)
    model = dict(known_through='2026-10-06',last_label_end='2026-10-01',ready=False)
    schedule = dict(parameters=e.PARAMETERS,models={'2026-10-07':model})
    assert e.EconomicRidgeOverlay(schedule).apply([target],context) == [target]
    with pytest.raises(ValueError,match='Exact economic decision'):
        e.prediction(schedule,history,'2026-10-08')
    model['known_through'] = '2026-10-05'
    with pytest.raises(ValueError,match='cutoffs differ'):
        e.prediction(schedule,history,'2026-10-07')


def test_prospective_late_capture_abstains_without_backdating(monkeypatch):
    sources = e.LEADING+e.CONTEXT
    class Reader:
        def __init__(self,**kwargs): pass
        def snapshot(self,s,v):
            return dict(first_seen_at='2026-10-08T20:00:00+00:00')
    monkeypatch.setattr(e,'EconomicInputs',Reader)
    monkeypatch.setattr(e,'panel',lambda r,v,k:dict(vintage=v,known_at=k.isoformat(),
        sources={s:{} for s in sources},features={s:'1' for s in sources},unavailable=[],
        leading_ready=True,context_ready=True,availability='archive_daily'))
    inputs = dict(pin={},known={'2026-10-07':'2026-10-06','2026-10-08':'2026-10-07'},
        entries=[dict(series=s,vintage=v) for s in sources for v in ['2026-10-05','2026-10-06']])
    states = e.feature_states(inputs)
    assert states['2026-10-07']['context_ready']
    future = states['2026-10-08']
    assert not future['context_ready'] and not future['leading_ready']
    assert not future['features'] and future['availability']=='first_seen'
    assert {r['reason'] for r in future['unavailable']} == {'not_captured_before_decision'}
    inputs['entries'] = []
    assert {r['reason'] for r in e.feature_states(inputs)['2026-10-07']['unavailable']} == {'unpublished_exact_vintage'}


def test_unrelated_new_series_does_not_invalidate_frozen_model(monkeypatch):
    catalog = {'snapshots':[dict(series='PAYEMS',vintage='2026-09-29',batch='same',root='immutable')]}
    class Reader:
        def __init__(self,**kwargs):self.catalog=deepcopy(catalog)
        def snapshot(self,*a):return {}
    monkeypatch.setattr(e,'load_catalog',lambda a:({},dict(root='catalog',batch='catalog-pin')))
    monkeypatch.setattr(e,'EconomicInputs',Reader)
    bars = {'SPY':[dict(trade_date=d) for d in ['2026-09-30','2026-10-01','2026-10-02']]}
    before = e.economic_inputs(None,bars,'2026-10-01')['provenance']
    catalog['snapshots'].append(dict(series='T10Y2Y',vintage='2026-09-29',batch='new',root='new'))
    assert e.economic_inputs(None,bars,'2026-10-01')['provenance'] == before
    catalog['snapshots'][0]['batch'] = 'changed'
    assert e.economic_inputs(None,bars,'2026-10-01')['provenance'] != before


def test_proposal_binding_rejects_changed_model_or_wrong_price_batch(monkeypatch,tmp_path):
    import json
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    definition=economic_context_definition()
    path=tmp_path/'economic.models.json'
    path.write_text(json.dumps(dict(pin={},provenance={'subset':'frozen'})),encoding='utf-8')
    report=dict(strategyDefinition=definition.to_dict(),economicModel=dict(receipt=dict(path=str(path),sha256=e.sha256(path))))
    publication=dict(provenance=json.dumps(dict(inputs=dict(batch='prices'))),version='calculation')
    monkeypatch.setattr(AnalyticsStore,'from_settings',lambda s:SimpleNamespace(document=lambda *a:(dict(payload=json.dumps(report)),publication)))
    monkeypatch.setattr(e,'EconomicInputs',lambda **k:None)
    schedule,receipt=e.published_live_schedule(None,definition,'prices')
    assert schedule['provenance']=={'subset':'frozen'} and receipt['calculation_revision']=='calculation'
    with pytest.raises(ValueError,match='governed decision inputs differ'):
        e.published_live_schedule(None,definition,'other-prices')
    path.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='hash mismatch'):
        e.published_live_schedule(None,definition,'prices')
