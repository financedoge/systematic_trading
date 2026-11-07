from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from systematic_trading.research import strategy_dependencies as deps, strategy_lifecycle
from systematic_trading.research.strategy_catalog import registered_strategy_definitions, registered_strategy_definition, OverlaySpec
from test_strategy_lifecycle import setup, change, KEY, detail


FR25 = 'research_fr25_14_v1'
ALPHA = 'research_fr25_alpha_tilt_5_v1'


def test_every_executable_strategy_has_a_valid_pinned_contract_and_resolvable_dependencies():
    registry = deps.load_registry()
    assert set(registry['strategies']) == {d.key for d in registered_strategy_definitions()}
    receipt = deps.validate_required(registry['strategies'])
    assert len(receipt['definitions']) == 15
    assert 'observed-fx' in receipt['services']


def test_changed_ancestor_blocks_descendants_but_cosmetic_labels_do_not(monkeypatch):
    original = registered_strategy_definition
    parent = original(KEY)
    monkeypatch.setattr(deps, 'registered_strategy_definition', lambda key: replace(parent, name='New label') if key == KEY else original(key))
    assert deps.validate_required([ALPHA])
    changed = replace(parent, overlays=(*parent.overlays, OverlaySpec('final_weight_cap', {'cap': '.2'})))
    monkeypatch.setattr(deps, 'registered_strategy_definition', lambda key: changed if key == KEY else original(key))
    with pytest.raises(ValueError, match='existing version '+KEY):
        deps.validate_required([ALPHA])


def test_missing_reference_and_cycles_fail_before_work():
    registry = deepcopy(deps.load_registry())
    registry['strategies'][KEY]['parents'] = ['missing']
    with pytest.raises(ValueError, match='not registered: missing'):
        deps.closure([FR25], registry)
    registry = deepcopy(deps.load_registry())
    registry['strategies'][KEY]['requires_monitoring'] = [FR25]
    registry['strategies'][FR25]['requires_monitoring'] = [KEY]
    with pytest.raises(ValueError, match='dependency cycle'):
        deps.calculation_plan([KEY, FR25], FR25, registry)
    registry['strategies'][KEY]['parents'] = [FR25]
    with pytest.raises(ValueError, match='dependency cycle'):
        deps.closure([FR25], registry)


def test_missing_shared_provider_blocks_publication(monkeypatch):
    monkeypatch.setitem(deps.SERVICES, 'observed-fx', dict(provider='systematic_trading.research.tracked_inputs:removed_publisher'))
    with pytest.raises(ValueError, match='shared strategy service unavailable: observed-fx'):
        deps.validate_required([FR25])


def test_m1_without_older_monitored_reports_keeps_required_reference_replay():
    plan = deps.calculation_plan([FR25, ALPHA], FR25)
    assert plan['dependency_only'] == [KEY]
    assert KEY not in plan['requested']
    assert 'observed-fx' in plan['receipt']['services']
    assert {'risk_parity', FR25} <= set(plan['benchmarks'])
    assert not deps.calculation_plan([FR25, KEY], FR25)['dependency_only']


def test_required_continuing_calculation_blocks_archive_and_preserves_revision(setup, monkeypatch):
    settings, store = setup
    config = json.loads(settings.strategy_monitoring_config_path.read_text())
    config['monitored_strategy_ids'].append(FR25)
    settings.strategy_monitoring_config_path.write_text(json.dumps(config))
    registry = deepcopy(deps.load_registry())
    registry['strategies'][FR25]['requires_monitoring'] = [KEY]
    monkeypatch.setattr(deps, 'load_registry', lambda: registry)
    with pytest.raises(ValueError, match='requires continuing calculations'):
        change(setup, 'archived', 0)
    assert strategy_lifecycle.membership(*setup)['revision'] == 0
    preview = deps.inspection(*setup, key=KEY, action='archive')['impact']
    assert not preview['allowed']


def test_archiving_retains_recipe_dependency_but_retirement_is_blocked(setup):
    settings, store = setup
    config = json.loads(settings.strategy_monitoring_config_path.read_text())
    config['monitored_strategy_ids'].append(FR25)
    settings.strategy_monitoring_config_path.write_text(json.dumps(config))
    archive = deps.inspection(*setup, key=KEY, action='archive')['impact']
    assert archive['allowed'] and FR25 in archive['affected']
    change(setup, 'archived', 0)
    assert KEY not in strategy_lifecycle.membership(*setup)['monitored']
    assert deps.calculation_plan(strategy_lifecycle.membership(*setup)['monitored'],
        'sota_price_volume_technical_tree_relative_adaptive_top6_usd_v1')['dependency_only'] == [KEY]
    retired = deps.inspection(*setup, key=KEY, action='retire')['impact']
    assert not retired['allowed'] and FR25 in retired['affected']
    events = store.strategy_control_events(strategy_lifecycle.SCOPE)
    assert events[-1]['dependencies']['registry_sha256']


def test_archived_consumer_is_visible_and_prevents_silent_recipe_removal(setup):
    # The alpha challenger is not monitored in this fixture, but its retained
    # executable recipe still needs FR25 and must remain restorable.
    preview = deps.inspection(*setup, key=FR25, action='retire')
    assert ALPHA in preview['impact']['archived_affected']
    assert ALPHA in preview['impact']['affected']
    assert not preview['impact']['allowed']
    assert not preview['impact']['protected_affected']


def test_contract_change_blocks_allocation_readiness_and_restore(setup, monkeypatch):
    registry = deepcopy(deps.load_registry())
    registry['strategies'][KEY]['definition_sha256'] = 'different'
    monkeypatch.setattr(deps, 'load_registry', lambda: registry)
    assert not strategy_lifecycle.calculation_ready(detail(), strategy_lifecycle.membership(*setup))
    with pytest.raises(ValueError, match='contract changed'):
        strategy_lifecycle.require_monitored(*setup, [KEY])


def test_dependency_change_during_lifecycle_review_is_not_committed(setup, monkeypatch):
    change(setup, 'archived', 0)
    calls = []
    def preflight(*args):
        calls.append(1)
        return {'registry_sha256': str(len(calls))}
    monkeypatch.setattr(deps, 'membership_preflight', preflight)
    with pytest.raises(ValueError, match='dependencies changed during lifecycle review'):
        change(setup, 'monitored', 1)
    assert strategy_lifecycle.membership(*setup)['revision'] == 1


def test_internal_reference_replay_preserves_archived_report_and_no_new_monitoring():
    from systematic_trading.research.tracked_runtime import retain_archived_reports
    old_detail = dict(strategy_id=KEY, end_date='2026-10-30', lifecycle='monitored')
    old_report = dict(monitoring={'monitoredThrough': '2026-10-30'})
    documents = [dict(point_key='detail/'+k, payload=json.dumps({'end_date': '2026-11-06'})) for k in [KEY, FR25]]
    observations = [dict(entity=k) for k in [KEY, FR25]]
    docs, rows, archives = retain_archived_reports(documents, observations, {KEY: (old_detail, old_report)}, [FR25], [KEY])
    assert archives == [KEY] and rows == [dict(entity=FR25)]
    detail = json.loads(next(d['payload'] for d in docs if d['point_key'] == 'detail/'+KEY))
    assert detail['end_date'] == '2026-10-30' and detail['lifecycle'] == 'archived'
    assert old_detail['lifecycle'] == 'monitored'
    assert sum(d['point_key'] == 'detail/'+KEY for d in docs) == 1


def test_read_only_endpoint_returns_transitive_impact_and_precedes_detail_route(setup):
    from systematic_trading.web import api
    paths = [r.path for r in api.router.routes]
    assert paths.index('/api/v1/strategies/dependencies') < paths.index('/api/v1/strategies/{strategy_id}')
    app = FastAPI()
    app.include_router(api.router)
    app.state.settings, app.state.store = setup
    with TestClient(app) as client:
        result = client.get('/api/v1/strategies/dependencies', params={'key': KEY, 'action': 'modify'})
        assert result.status_code == 200
        assert not result.json()['impact']['allowed']
        assert client.get('/api/v1/strategies/dependencies?action=delete').status_code == 409
    assert strategy_lifecycle.membership(*setup)['revision'] == 0


def test_dependency_ui_is_read_only_and_embedded_in_assembled_page():
    from html.parser import HTMLParser
    from systematic_trading.web.operator import _strategy_portal_html
    from systematic_trading.web.strategy_dependencies_ui import JS
    class Page(HTMLParser):
        inside = False
        def __init__(self):
            super().__init__(); self.scripts = []
        def handle_starttag(self, tag, attrs):
            if tag == 'script': self.inside = True
        def handle_endtag(self, tag):
            if tag == 'script': self.inside = False
        def handle_data(self, data):
            if self.inside: self.scripts.append(data)
    page = Page(); html = _strategy_portal_html(); page.feed(html)
    assert sum(JS in script for script in page.scripts) == 1
    assert 'id="dependency-detail"' in html
    assert 'method:' not in JS and 'localStorage' not in JS
