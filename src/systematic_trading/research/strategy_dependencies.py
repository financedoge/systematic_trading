"""Versioned recipe dependencies and lifecycle impact, without trading authority.

Recipe inheritance, shared services and report comparisons are distinct contracts.
An archived recipe may still be required, without its report being monitored.
"""
from importlib import import_module
import json
from pathlib import Path

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.strategy_catalog import registered_strategy_definition

REGISTRY = Path(__file__).with_name('strategy_dependencies.json')
M1 = {'research_m1_14_v1', 'research_fr25_14_v1', 'research_fr25_alpha_tilt_5_v1'}
USD = {'research_fallback_f3_v1', 'research_economic_context_ridge_v1'}
USD_REFERENCE = 'research_fallback_f3_v1'
SERVICES = {
    'audited-prices': dict(name='Published audited price histories', source='governance/catalog',
        provider='systematic_trading.research.governed_inputs:GovernedInputs', contract='audited-continuous-history-v1'),
    'observed-fx': dict(name='Observed USD/CNH publication and exact-date conversion', source='governance/fx-usd-cnh',
        provider='systematic_trading.research.tracked_inputs:publish_observed_fx', contract='observed-midpoint-post-close-v1'),
    'usd-vintages': dict(name='Published broad-dollar vintages', source='governance/usd-broad-index',
        provider='systematic_trading.research.usd_data:load_usd', contract='original-vintage-usd-v1'),
    'rolling-models': dict(name='Causal rolling model schedule',
        provider='systematic_trading.research.rolling_tracking:prepare_model_schedule', contract='causal-monthly-models-v1'),
    'economic-vintages': dict(name='Published economic vintages and expanding ridge',
        provider='systematic_trading.research.economic_tracking:economic_inputs', contract='economic-original-vintages-v1'),
    'financial-vintages': dict(name='FR25 financial vintages and rank selection',
        provider='systematic_trading.research.fr25_tracking:economic_inputs', contract='fr25-selection-v1'),
    'raw-activity': dict(name='Audited raw price and volume activity', source='governance/catalog',
        provider='systematic_trading.research.m1_monitoring:load_inputs', contract='raw-dollar-adjusted-direction-v1'),
    'usd-reference': dict(name='USD benchmark replay, independent of report membership',
        provider='systematic_trading.research.usd_monitored:calculate', contract='matched-usd-benchmark-v1'),
    'conditional-snapshot': dict(name='Pinned conditional strategy panel and controls',
        provider='systematic_trading.research.fr25_lifecycle_conditional:verified_input_provenance', contract='frozen-conditional-input-v1'),
    'broadtrend-models': dict(name='Pinned BroadTrend model pack and full-pool inputs',
        provider='systematic_trading.research.broadtrend:load_inputs', contract='broadtrend-full-pool-v1'),
}


def definition_fingerprint(definition):
    value = definition.to_dict()
    return digest(encode({k: value.get(k) for k in (
        'key', 'sleeveName', 'universeKey', 'scheduler', 'overlays', 'universeMembers')}))


def load_registry():
    registry = json.loads(REGISTRY.read_text(encoding='utf8'))
    if registry.get('schema_version') != 1 or not isinstance(registry.get('strategies'), dict):
        raise ValueError('Unsupported strategy dependency registry')
    return registry


def closure(keys, registry, *, relation='parents'):
    """Resolve required recipes, with explicit missing-reference/cycle failures."""
    entries, visited, visiting, ordered = registry['strategies'], set(), [], []

    def visit(key):
        if key in visiting:
            raise ValueError('Strategy dependency cycle: ' + ' -> '.join([*visiting, key]))
        if key in visited:
            return
        if key not in entries:
            raise ValueError('Strategy dependency is not registered: ' + key)
        visiting.append(key)
        for parent in entries[key].get(relation, []):
            visit(parent)
        visiting.pop()
        visited.add(key)
        ordered.append(key)

    for key in sorted(set(keys)):
        visit(key)
    return ordered


def validate_required(keys, registry=None):
    registry = registry if registry is not None else load_registry()
    ordered = closure(closure(keys, registry, relation='requires_monitoring'), registry)
    fingerprints, services = {}, set()
    for key in ordered:
        entry = registry['strategies'][key]
        try:
            actual = definition_fingerprint(registered_strategy_definition(key))
        except (ValueError, ImportError, AttributeError, NameError) as exc:
            raise ValueError(f'Required strategy recipe unavailable: {key}: {exc}') from exc
        if actual != entry.get('definition_sha256'):
            raise ValueError(f'Strategy contract changed under existing version {key}. '
                'Create a new version and explicitly migrate its dependents; retain the last complete calculation.')
        fingerprints[key] = actual
        services.update(entry.get('services', []))
    for service in sorted(services):
        if service not in SERVICES:
            raise ValueError('Unknown shared strategy dependency: ' + service)
        module, name = SERVICES[service]['provider'].split(':')
        try:
            provider = getattr(import_module(module), name)
        except (ImportError, AttributeError) as exc:
            raise ValueError('Required shared strategy service unavailable: ' + service) from exc
        if not callable(provider):
            raise ValueError('Required shared strategy service is not callable: ' + service)
    from .strategy_assets import composite_assets, load_registry as load_assets
    asset_registry = load_assets()
    assets = composite_assets(keys, asset_registry)
    return dict(schema_version=1, registry_sha256=digest(encode(registry)),
        assets=assets, asset_registry_sha256=digest(encode(asset_registry)),
        roots=sorted(set(keys)), definitions=fingerprints,
        services={key: SERVICES[key] for key in sorted(services)})


def calculation_plan(monitored, sota_key, registry=None):
    registry = registry if registry is not None else load_registry()
    requested = sorted(set(monitored))
    required = sorted(set(requested) | {sota_key})
    dependency_only = [USD_REFERENCE] if M1.intersection(requested) and not USD.intersection(requested) else []
    benchmarks = sorted({b for key in requested for b in benchmark_recipes(key, sota_key, registry)})
    receipt = validate_required([*required, *dependency_only, *benchmarks], registry)
    for key in closure(required, registry, relation='requires_monitoring'):
        for provider in registry['strategies'][key].get('requires_monitoring', []):
            if provider not in requested:
                raise ValueError(f'{key} requires continuing calculations from {provider}; restore it or migrate the dependency first.')
    if sota_key in M1 and sota_key not in requested and (USD | M1).intersection(requested):
        raise ValueError('The matched SOTA benchmark must remain monitored: ' + sota_key)
    return dict(requested=requested, dependency_only=dependency_only, benchmarks=benchmarks, receipt=receipt)


def benchmark_recipes(key, sota_key, registry):
    # Report edges are separate from recipe inheritance: cross-family matched
    # comparisons can point both ways without creating a calculation cycle.
    return [sota_key if b == '$sota' else b for b in registry['strategies'].get(key, {}).get('benchmarks', [])]


def protected_roots(settings, store, monitored=None):
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.research.strategy_lifecycle import membership
    roles = control_state(store)
    roots = set(membership(settings, store)['monitored'] if monitored is None else monitored)
    roots.add(roles['sota_key'])
    roots.update(r['strategy_key'] for r in roles['active']['allocations'])
    pending = (roles.get('pending') or {}).get('change', {})
    if pending.get('sota_key'):
        roots.add(pending['sota_key'])
    roots.update(r['strategy_key'] for r in pending.get('allocations') or [])
    return sorted(roots)


def membership_preflight(settings, store, monitored):
    from systematic_trading.portfolio.strategy_allocation import control_state
    plan = calculation_plan(monitored, control_state(store)['sota_key'])
    validate_required(protected_roots(settings, store, monitored))
    from .strategy_assets import live_plan
    return dict(plan['receipt'], asset_plan=live_plan(settings, store, monitored))


def contract_issue(key):
    try:
        registry = load_registry()
        benchmarks = [b for b in registry['strategies'].get(key, {}).get('benchmarks', []) if b != '$sota']
        validate_required([key, *benchmarks], registry)
    except ValueError as exc:
        return str(exc)
    return None


def inspection(settings, store, *, key=None, action='modify'):
    """Read-only impact; archive retains recipes, retirement removes them."""
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.research.strategy_lifecycle import membership
    if action not in {'archive', 'modify', 'retire'}:
        raise ValueError('Dependency action must be archive, modify or retire')
    registry = load_registry()
    state = membership(settings, store)
    roots = protected_roots(settings, store, state['monitored'])
    sota_key = control_state(store)['sota_key']
    users, all_users, issues, rows = {}, {}, {}, []
    for root in sorted(set(roots) | set(registry['strategies'])):
        try:
            required = [root, *benchmark_recipes(root, sota_key, registry)]
            for dependency in closure(closure(required, registry, relation='requires_monitoring'), registry):
                all_users.setdefault(dependency, []).append(root)
                if root in roots:
                    users.setdefault(dependency, []).append(root)
            if root in roots:
                validate_required(required, registry)
        except ValueError as exc:
            issues[root] = str(exc)
    for identity, entry in sorted(registry['strategies'].items()):
        try:
            definition = registered_strategy_definition(identity)
            name = definition.name
            actual = definition_fingerprint(definition)
        except (ValueError, ImportError, AttributeError, NameError):
            name, actual = identity, None
        problem = contract_issue(identity)
        rows.append(dict(strategy_key=identity, name=name, monitored=identity in state['monitored'],
            parents=entry.get('parents', []), services=[dict(id=s, **SERVICES.get(s, {})) for s in entry.get('services', [])],
            requires_monitoring=entry.get('requires_monitoring', []),
            benchmarks=benchmark_recipes(identity, sota_key, registry),
            optional_comparisons=entry.get('optional_comparisons', []),
            consumers=sorted(set(all_users.get(identity, [])) - {identity}),
            required_by=sorted(users.get(identity, [])), definition_sha256=entry['definition_sha256'],
            actual_sha256=actual, contract_ok=problem is None, issue=problem))
    result = dict(schema_version=1, registry_sha256=digest(encode(registry)),
        membership_revision=state['revision'], protected_roots=roots, strategies=rows, issues=issues)
    if key:
        selected = next((row for row in rows if row['strategy_key'] == key), None)
        if not selected:
            raise ValueError('Unknown dependency strategy: ' + key)
        blockers = []
        affected = sorted(set(selected['required_by']) | set(selected['consumers']))
        if action in {'modify', 'retire'} and affected:
            blockers.append('Retain this version while required by: ' + ', '.join(affected) +
                '. This includes retained archived consumers. Create a new version and migrate consumers first.')
        if action == 'archive':
            roles = control_state(store)
            pending = (roles.get('pending') or {}).get('change', {})
            if key == roles['sota_key'] or any(r['strategy_key'] == key for r in roles['active']['allocations']):
                blockers.append('Remove the SOTA/active-allocation role before archiving.')
            if key == pending.get('sota_key') or any(r['strategy_key'] == key for r in pending.get('allocations') or []):
                blockers.append('Cancel or complete the pending allocation change before archiving.')
            try:
                membership_preflight(settings, store, [k for k in state['monitored'] if k != key])
            except ValueError as exc:
                blockers.append(str(exc))
        result['impact'] = dict(strategy_key=key, action=action, affected=affected, blockers=blockers,
            protected_affected=selected['required_by'],
            archived_affected=[k for k in selected['consumers'] if k not in roots],
            allowed=not blockers, message='Archive pauses this report and retains its recipe. Required internal benchmarks and shared publishers continue independently.' if action == 'archive' else
            'Existing executable versions are pinned. Modification or recipe removal requires an explicit version migration; this preview changes nothing.')
        from .strategy_assets import live_plan
        before = live_plan(settings, store)
        if action == 'archive' and not blockers:
            after = live_plan(settings, store, [k for k in state['monitored'] if k != key])
            result['impact'].update(assets_continuing=after['jobs'],
                assets_becoming_idle=sorted(set(before['jobs'])-set(after['jobs'])))
        result['impact']['asset_registry_sha256'] = before['registry_sha256']
        result['impact']['review_sha256'] = digest(encode(result['impact']))
    return result


def require_retirement_review(settings, store, key, *, action='archive'):
    """Mandatory service-side check, also used by non-UI lifecycle callers."""
    impact = inspection(settings, store, key=key, action=action)['impact']
    if not impact['allowed']:
        raise ValueError('; '.join(impact['blockers']))
    return impact
