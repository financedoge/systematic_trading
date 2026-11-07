from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research import strategy_assets as a, strategy_asset_monitoring as m
from systematic_trading.research import strategy_dependencies as d, strategy_lifecycle as lifecycle
from systematic_trading.research.strategy_catalog import registered_strategy_definitions
from test_strategy_lifecycle import setup, change, KEY


def repin(registry, key):
    row = registry['assets'][key]
    row['sha256'] = digest(encode(row['contract']))
    return row['sha256']


def test_complete_composite_decomposition_and_all_signals_have_monitor_contracts():
    registry = a.load_registry()
    assert set(registry['composites']) == {r.key for r in registered_strategy_definitions()}
    assert len(a.resolve({k:v['sha256'] for k,v in registry['assets'].items()},registry)) == len(registry['assets'])
    plan = a.demand(registry['composites'],registry)
    assert 'broadtrend-signals-v1' in plan['monitored_signals']
    assert all(registry['assets'][k]['contract']['monitor'] in a.MONITORS for k in plan['monitored_signals'])


def test_missing_or_modified_asset_and_unknown_composite_fail_closed():
    registry = deepcopy(a.load_registry())
    registry['assets']['prices-adjusted-v1']['contract']['basis']='silently changed'
    with pytest.raises(ValueError,match='contract changed'):
        a.demand([KEY],registry)
    registry = deepcopy(a.load_registry())
    del registry['assets']['prices-adjusted-v1']
    with pytest.raises(ValueError,match='Unregistered strategy asset'):
        a.demand([KEY],registry)
    with pytest.raises(ValueError,match='registered asset decomposition'):
        a.demand(['new-unregistered-composite'])


def test_new_signal_cannot_enter_tracking_without_monitoring_contract():
    registry = deepcopy(a.load_registry()); key='technical-features-v1'
    registry['assets'][key]['contract']['monitor']=None
    pin = repin(registry,key)
    with pytest.raises(ValueError,match='monitoring contract'):
        a.resolve({key:pin},registry)


def test_demand_deduplicates_shared_inputs_and_unused_assets_are_idle():
    plan = a.demand([KEY,'research_fr25_14_v1','broadtrend_full_pool_v1'])
    assert plan['jobs'].count('prices-adjusted-v1') == 1
    assert len(plan['consumers']['prices-adjusted-v1']) == 3
    assert 'broadtrend-signals-v1' not in a.demand([KEY])['jobs']
    assert 'rolling-xgboost-12-v1' in plan['jobs'] and 'rolling-xgboost-14-v1' in plan['jobs']


def test_monitoring_follows_archive_restore_and_keeps_shared_dependencies(setup):
    before = a.live_plan(*setup)
    assert 'rolling-xgboost-12-v1' in before['monitored_signals']
    impact = d.require_retirement_review(*setup,KEY)
    assert 'rolling-xgboost-12-v1' in impact['assets_becoming_idle']
    change(setup,'archived',0)
    assert 'rolling-xgboost-12-v1' not in a.live_plan(*setup)['jobs']
    assert 'prices-adjusted-v1' in a.live_plan(*setup)['jobs']
    event = setup[1].strategy_control_events(lifecycle.SCOPE)[-1]
    assert event['retirement_review']['review_sha256'] == impact['review_sha256']
    change(setup,'monitored',1)
    assert 'rolling-xgboost-12-v1' in a.live_plan(*setup)['monitored_signals']


def test_stale_strategy_retirement_review_is_rejected(setup):
    with pytest.raises(ValueError,match='impact changed'):
        lifecycle.change_membership(*setup,key=KEY,lifecycle='archived',expected_revision=0,
            event_id='stale-review',operator='test',reason='test',retirement_review_sha256='0'*64)
    assert lifecycle.membership(*setup)['revision']==0


def test_retirement_blocks_archived_consumers_and_keeps_all_state(setup):
    change(setup,'archived',0)
    impact = a.retirement_impact(*setup,'rolling-xgboost-12-v1')
    assert KEY in impact['consumers'] and not impact['tracked_consumers'] and not impact['allowed']
    with pytest.raises(ValueError,match='Migrate retained'):
        a.retire(*setup,key='rolling-xgboost-12-v1',review_sha256=impact['review_sha256'],
            expected_revision=0,event_id='retire-used',operator='test',reason='test')
    assert a.lifecycle_state(setup[1])['revision']==0


def test_unused_asset_retirement_is_reviewed_idempotent_and_retains_definition(setup,monkeypatch):
    registry=deepcopy(a.load_registry())
    registry['assets']['unused-test-v1']=deepcopy(registry['assets']['prices-adjusted-v1'])
    monkeypatch.setattr(a,'load_registry',lambda:registry)
    impact=a.retirement_impact(*setup,'unused-test-v1')
    kwargs=dict(key='unused-test-v1',review_sha256=impact['review_sha256'],expected_revision=0,
        event_id='retire-unused',operator='test',reason='unused after migration')
    with pytest.raises(ValueError,match='impact changed'):
        a.retire(*setup,**dict(kwargs,review_sha256='0'*64))
    result=a.retire(*setup,**kwargs)
    assert result['revision']==1 and a.retire(*setup,**kwargs)==result
    assert 'unused-test-v1' in a.load_registry()['assets']
    registry['composites'][KEY]['unused-test-v1']=registry['assets']['unused-test-v1']['sha256']
    registry['reuse_reviews'][KEY]['inspected_assets'].append('unused-test-v1')
    with pytest.raises(ValueError,match='asset is retired'):
        a.live_plan(*setup)


def test_new_signal_automatically_appears_without_a_health_ui_mapping(setup,monkeypatch):
    registry=deepcopy(a.load_registry())
    registry['assets']['new-test-signal-v1']=deepcopy(registry['assets']['technical-features-v1'])
    registry['composites'][KEY]['new-test-signal-v1']=registry['assets']['new-test-signal-v1']['sha256']
    registry['reuse_reviews'][KEY]['inspected_assets'].append('new-test-signal-v1')
    monkeypatch.setattr(a,'load_registry',lambda:registry)
    rows=m.signal_rows(*setup,None)
    row=next(r for r in rows if r['asset_id']=='new-test-signal-v1')
    assert row['evidence']['effectiveness']=='insufficient'
    assert KEY in row['required_by']
    assert {r['asset_id'] for r in rows}==set(a.live_plan(*setup)['monitored_signals'])


def test_asset_retirement_commit_guards_against_concurrent_membership_change(setup,monkeypatch):
    registry=deepcopy(a.load_registry())
    registry['assets']['unused-test-v1']=deepcopy(registry['assets']['prices-adjusted-v1'])
    monkeypatch.setattr(a,'load_registry',lambda:registry)
    review=a.retirement_impact(*setup,'unused-test-v1')
    store=setup[1];commit=store.commit_strategy_control
    def racing(scope,*args,**kwargs):
        if scope==a.SCOPE:
            commit(lifecycle.SCOPE,0,dict(overrides={}),dict(event_id='concurrent-monitoring',request_hash='other',kind='test'))
        return commit(scope,*args,**kwargs)
    monkeypatch.setattr(store,'commit_strategy_control',racing)
    with pytest.raises(ValueError):
        a.retire(*setup,key='unused-test-v1',review_sha256=review['review_sha256'],
            expected_revision=0,event_id='retire-racing',operator='test',reason='test')
    assert a.lifecycle_state(store)['revision']==0


def test_composite_requires_reuse_search_before_tracking():
    registry=deepcopy(a.load_registry())
    del registry['reuse_reviews'][KEY]
    with pytest.raises(ValueError,match='asset-pool reuse review'):
        a.demand([KEY],registry)


def signal_fixture():
    days=np.array(['2026-10-30','2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06'])
    opens=np.array([[100.],[101.],[102.],[103.],[104.],[105.]])
    arrays=dict(open=opens,close=opens+.2,desired=np.array([[1],[0],[1],[0],[1],[0]],bool),
        held=np.zeros((6,1),bool),fast_up=np.full((6,1),.6),fast_down=np.full((6,1),.2),
        slow_up=np.full((6,1),.7),stop=np.full((6,1),np.nan),nav=np.ones((6,1)))
    return days,['TEST'],arrays,{'TEST':dict(desired=False,held=False,fast_up=.6,fast_down=.2,slow_up=.7,close_test_stop=None,last_trade=None)}


def test_broadtrend_publishes_consumed_values_and_only_completed_forward_labels():
    signal=signal_fixture()
    doc,rows=m.broadtrend_publication(signal,{'batch':'audited'},cost_bp=5)
    summary=json.loads(doc['payload'])
    assert len(rows)==6 and len({r['point_key'] for r in rows})==6
    assert summary['health']['completed_decisions']==4
    expected=((102/101-1)-(103/102-1)+(104/103-1)-(105/104-1))/4
    assert summary['health']['directional_forward_mean']==pytest.approx(expected)
    assert summary['health']['status']=='insufficient'
    assert json.loads(rows[0]['payload'])['stop'] is None
    assert all(r['available_at']>r['observed_at'] for r in rows)
    # A later price cannot change the historical signal values already consumed.
    signal[2]['open'][-1]=1000
    later,later_rows=m.broadtrend_publication(signal,{'batch':'audited'},cost_bp=5)
    assert [r['payload'] for r in later_rows]==[r['payload'] for r in rows]
    assert json.loads(later['payload'])['health']['directional_forward_mean']!=expected


def test_paused_signal_history_keeps_original_published_version(monkeypatch):
    doc,_=m.broadtrend_publication(signal_fixture(),{'batch':'audited'},cost_bp=5)
    class Analytics:
        def document(self,source,key):
            return (doc,dict(version='old')) if key=='asset/'+m.BROADTREND else None
    retained=m.retain_idle_assets(Analytics(),{'jobs':[]},[])
    assert json.loads(retained[0]['payload'])['series_version']=='old'
    assert not m.retain_idle_assets(Analytics(),{'jobs':[m.BROADTREND]},[])


def test_catalog_api_auto_signals_and_retirement_preview_are_read_only(setup):
    from systematic_trading.web.strategy_assets_api import router
    app=FastAPI();app.include_router(router);app.state.settings,app.state.store=setup
    with TestClient(app) as client:
        result=client.get('/api/v1/strategy-assets');assert result.status_code==200
        signals=client.get('/api/v1/strategy-assets/signals').json()['signals']
        assert {s['asset_id'] for s in signals}==set(result.json()['plan']['monitored_signals'])
        assert client.get('/api/v1/strategy-assets/prices-adjusted-v1/retirement').json()['allowed'] is False
        assert client.get('/api/v1/strategy-assets/unknown/retirement').status_code==409
        assert client.get('/api/v1/strategy-assets/broadtrend-signals-v1/series?symbol=TEST&limit=2000').status_code==422
    assert lifecycle.membership(*setup)['revision']==0 and a.lifecycle_state(setup[1])['revision']==0


def test_asset_registry_is_pinned_in_calculation_source_identity():
    from systematic_trading.research.tracked_runtime import calculation_code_hashes
    from pathlib import Path
    assert str(Path('research/strategy_assets.json')) in calculation_code_hashes()
