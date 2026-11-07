"""Governed reusable assets, composite demand and audited lifecycle decisions.

Definitions persist independently of monitoring. Demand schedules existing app
providers; the catalog never fetches prices, fits models or places orders.
"""
from datetime import UTC, datetime
from importlib import import_module
import json
from pathlib import Path

from systematic_trading.market_data.analytics_store import digest, encode

REGISTRY = Path(__file__).with_name('strategy_assets.json')
SCOPE = 'strategy-assets-v1'
MONITORS = {'evidence_gap', 'm1_rank_ic', 'broadtrend_time_series'}


def load_registry():
    data = json.loads(REGISTRY.read_text(encoding='utf8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('assets'), dict):
        raise ValueError('Unsupported strategy asset registry')
    return data


def resolve(roots, registry=None):
    registry = registry if registry is not None else load_registry()
    assets, ordered, visiting = registry['assets'], {}, []
    def visit(key, pin):
        if key in visiting:
            raise ValueError('Strategy asset dependency cycle: ' + ' -> '.join([*visiting, key]))
        if key not in assets:
            raise ValueError('Unregistered strategy asset: ' + key)
        item = assets[key]; contract = item['contract']
        actual = digest(encode(contract))
        if pin != actual or item['sha256'] != actual:
            raise ValueError('Strategy asset contract changed: ' + key + '. Version and migrate consumers explicitly.')
        if key in ordered:
            return
        if contract.get('kind') not in {'time_series', 'model', 'signal'}:
            raise ValueError('Unsupported strategy asset kind: ' + key)
        if contract['kind'] == 'signal' and contract.get('monitor') not in MONITORS:
            raise ValueError('Signal requires a registered monitoring contract: ' + key)
        try:
            module, name = contract['provider'].split(':')
            if not callable(getattr(import_module(module), name)):
                raise AttributeError(name)
        except (ImportError, AttributeError) as exc:
            raise ValueError('Strategy asset provider unavailable: ' + key) from exc
        visiting.append(key)
        for parent, expected in contract['inputs'].items():
            visit(parent, expected)
        visiting.pop()
        ordered[key] = actual
    for key, pin in sorted(roots.items()):
        visit(key, pin)
    return ordered


def composite_assets(keys, registry=None):
    registry = registry if registry is not None else load_registry()
    roots = {}
    for key in sorted(set(keys)):
        if key not in registry['composites']:
            raise ValueError('Composite requires a registered asset decomposition: ' + key)
        review = registry.get('reuse_reviews', {}).get(key, {})
        if not review.get('search_terms') or not review.get('decision') or not set(registry['composites'][key]).issubset(review.get('inspected_assets', [])):
            raise ValueError('Composite requires a recorded asset-pool reuse review: ' + key)
        for asset, pin in registry['composites'][key].items():
            if asset in roots and roots[asset] != pin:
                raise ValueError('Conflicting composite asset pins: ' + asset)
            roots[asset] = pin
    return resolve(roots, registry)


def lifecycle_state(store):
    reader = getattr(store, 'strategy_control_state', None)
    return (reader(SCOPE) if reader else None) or dict(revision=0, overrides={})


def demand(keys, registry=None, state=None):
    registry = registry if registry is not None else load_registry()
    state = state or dict(revision=0, overrides={})
    consumers = {}
    for key in sorted(set(keys)):
        for asset in composite_assets([key], registry):
            consumers.setdefault(asset, []).append(key)
    jobs = composite_assets(keys, registry)
    for asset in jobs:
        if state['overrides'].get(asset, {}).get('lifecycle') == 'retired':
            raise ValueError('Required strategy asset is retired: ' + asset)
    return dict(registry_sha256=digest(encode(registry)), lifecycle_revision=state['revision'],
        roots=sorted(set(keys)), jobs=list(jobs), contracts=jobs, consumers=consumers,
        monitored_signals=[a for a in jobs if registry['assets'][a]['contract']['kind'] == 'signal'])


def live_plan(settings, store, monitored=None):
    from .strategy_dependencies import protected_roots, calculation_plan
    from .strategy_lifecycle import membership
    from systematic_trading.portfolio.strategy_allocation import control_state
    keys = membership(settings, store)['monitored'] if monitored is None else list(monitored)
    plan = calculation_plan(keys, control_state(store)['sota_key'])
    roots = set(protected_roots(settings, store, keys)) | set(plan['benchmarks']) | set(plan['dependency_only'])
    return demand(roots, state=lifecycle_state(store))


def retirement_impact(settings, store, key):
    registry = load_registry()
    if key not in registry['assets']:
        raise ValueError('Unknown strategy asset: ' + key)
    plan = live_plan(settings, store)
    consumers = [k for k in registry['composites'] if key in composite_assets([k], registry)]
    upstream = [a for a, v in registry['assets'].items() if a != key and key in resolve({a:v['sha256']}, registry)]
    blockers = []
    if consumers or upstream:
        blockers.append('Migrate retained composite and asset consumers before retiring this version.')
    result = dict(asset_id=key, allowed=not blockers, blockers=blockers,
        consumers=consumers, asset_consumers=upstream, tracked_consumers=plan['consumers'].get(key, []),
        membership_revision=_membership_revision(settings, store),
        asset_revision=lifecycle_state(store)['revision'], registry_sha256=plan['registry_sha256'])
    result['review_sha256'] = digest(encode(result))
    return result


def _membership_revision(settings, store):
    from .strategy_lifecycle import membership
    return membership(settings, store)['revision']


def retire(settings, store, *, key, review_sha256, expected_revision, event_id, operator, reason):
    from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
    from systematic_trading.portfolio.strategy_allocation import control_state, scope_for
    from .strategy_lifecycle import SCOPE as MONITORING_SCOPE
    if not operator.strip() or not reason.strip():
        raise ValueError('Operator and retirement reason are required.')
    request_hash = digest(encode([key,review_sha256,expected_revision,operator,reason]))
    with ORDER_CONNECTION_LOCK:
        for prior in store.strategy_control_events(SCOPE):
            if prior['event_id'] == event_id:
                if prior['request_hash'] != request_hash:
                    raise ValueError('Idempotency key was used for a different retirement.')
                return lifecycle_state(store)
        roles = control_state(store)
        review = retirement_impact(settings, store, key)
        if not review['allowed']:
            raise ValueError('; '.join(review['blockers']))
        if review['review_sha256'] != review_sha256:
            raise ValueError('Asset retirement impact changed. Review it again.')
        state = lifecycle_state(store)
        if state['revision'] != expected_revision:
            raise ValueError('Asset lifecycle changed. Refresh and try again.')
        now = datetime.now(UTC).isoformat()
        overrides = dict(state['overrides'], **{key:dict(lifecycle='retired',changed_at=now)})
        if retirement_impact(settings, store, key) != review:
            raise ValueError('Asset dependencies changed during retirement review.')
        store.commit_strategy_control(SCOPE, expected_revision, dict(overrides=overrides),
            dict(event_id=event_id,request_hash=request_hash,kind='asset_retired',at=now,
                asset_id=key,operator=operator,reason=reason,dependencies=review),
            guard_revisions={MONITORING_SCOPE:review['membership_revision'],scope_for(store):roles['revision']})
        return lifecycle_state(store)


def catalog(settings, store, analytics=None, *, query=''):
    registry = load_registry(); state = lifecycle_state(store)
    plan = live_plan(settings, store)
    from .strategy_asset_monitoring import asset_evidence
    evidence = asset_evidence(analytics, plan)
    rows = []
    for key, asset in registry['assets'].items():
        contract = asset['contract']
        if query and query.casefold() not in encode([key, asset]).casefold():
            continue
        consumers = [k for k in registry['composites'] if key in composite_assets([k], registry)]
        lifecycle = state['overrides'].get(key, {}).get('lifecycle', 'active')
        rows.append(dict(asset_id=key, **asset, lifecycle=lifecycle,
            tracking='required' if key in plan['jobs'] else 'idle', required_by=plan['consumers'].get(key, []),
            consumers=consumers, evidence=evidence.get(key, {}),
            inspection_url='/platform/market-data-audit' if contract['kind']=='time_series' else None))
    return dict(schema_version=1, revision=state['revision'], plan=plan, assets=rows,
        note='Tracking follows composite demand. Idle assets retain their definitions; shared market-data capture has its own governance. No funding or execution authority.')
