"""Published asset evidence and automatically discovered signal monitoring."""
from datetime import UTC, datetime
import json
import math

from systematic_trading.market_data.analytics_store import digest, encode

SOURCE = 'tracked-strategies/calculations'
BROADTREND = 'broadtrend-signals-v1'


def _document(analytics, key):
    saved = analytics.document(SOURCE, key) if analytics is not None else None
    return (json.loads(saved[0]['payload']), saved[1]) if saved else (None, None)


def broadtrend_publication(signal_data, provenance, *, cost_bp):
    """Publish values actually consumed by the composite, never recompute in HTTP."""
    days, symbols, arrays, states = signal_data
    offset = 0
    from .broadtrend import model_pack
    start = model_pack()['prospective_start']
    now = datetime.now(UTC).isoformat()
    observations = []
    for j, symbol in enumerate(symbols):
        for t, day in enumerate(days):
            i = offset+t
            value = dict(date=day, symbol=symbol, close=float(arrays['close'][i,j]),
                desired=bool(arrays['desired'][i,j]), held=bool(arrays['held'][i,j]),
                fast_up=float(arrays['fast_up'][i,j]),fast_down=float(arrays['fast_down'][i,j]),
                slow_up=float(arrays['slow_up'][i,j]),shadow_nav=float(arrays['nav'][i,j]),
                stop=float(arrays['stop'][i,j]) if math.isfinite(arrays['stop'][i,j]) else None)
            observations.append(dict(point_key=f'asset/{BROADTREND}/{symbol}/{day}', family='strategy_asset_signal',
                entity=BROADTREND+'/'+symbol, observed_at=day, available_at=now, payload=encode(value)))
    prospective = [i for i, d in enumerate(days) if d >= start]
    # Close of each decision day -> next open -> following open; never include a
    # partly observed horizon or count 51 correlated ETFs as 51 independent days.
    completed = [i for i in prospective if i+2 < len(days)]
    by_symbol = []
    daily_edges = []
    for i in completed:
        edges = []
        for j in range(len(symbols)):
            r = arrays['open'][offset+i+2,j]/arrays['open'][offset+i+1,j]-1
            edges.append(float((1 if arrays['desired'][offset+i,j] else -1)*r))
        daily_edges.append(sum(edges)/len(edges))
    for j, symbol in enumerate(symbols):
        edge = [float((1 if arrays['desired'][offset+i,j] else -1)*
            (arrays['open'][offset+i+2,j]/arrays['open'][offset+i+1,j]-1)) for i in completed]
        by_symbol.append(dict(symbol=symbol, completed_decisions=len(edge),
            directional_forward_mean=sum(edge)/len(edge) if edge else None, **states[symbol]))
    count = len(completed)
    # Descriptive association only. No universal IC threshold is appropriate for
    # independently timed long/cash policies or a five-day prospective sample.
    reason = (f'{count} completed prospective daily labels since {start}. '
        'Long/cash direction is compared with next-open to following-open returns. '
        'No calibrated effectiveness/decay threshold is approved; inspect the evidence and net portfolio report.')
    summary = dict(asset_id=BROADTREND, through=days[-1], first=days[0], symbols=symbols,
        computed_at=now, provenance=provenance, observations=len(observations),
        health=dict(status='insufficient', reason=reason, prospective_start=start, completed_decisions=count,
            directional_forward_mean=sum(daily_edges)/count if count else None,
            current_long=sum(bool(s['desired']) for s in states.values()), universe_size=len(symbols),
            diagnostic='Time-series long/cash direction; gross association, not portfolio alpha or a cost-adjusted edge.',
            shadow_cost_bp=cost_bp, per_symbol=by_symbol),
        limits=['Forward labels are diagnostics and never inputs to the signal.',
            'Retrospective signals reconstructed now; available_at records actual publication, never backdated.',
            'No independent-name assumption or ranking-IC substitution. Historical development was repeatedly inspected.'])
    return dict(point_key='asset/'+BROADTREND, media_type='application/json', payload=encode(summary)), observations


def asset_evidence(analytics, plan):
    from .strategy_assets import load_registry
    registry = load_registry()
    details = {}
    pinned = analytics.latest(SOURCE) if analytics is not None else None
    for key in plan['roots']:
        detail, pub = _document(analytics, 'detail/'+key)
        if detail:
            if not pinned or pub['version'] != pinned['version']:
                raise ValueError('Asset evidence publication changed while reading; refresh.')
            provenance = detail.get('input_provenance') or {}
            details[key] = dict(through=detail.get('end_date'), publication=pub['version'],
                batch=provenance.get('batch'), price_basis=provenance.get('price_basis'),
                provenance_sha256=digest(encode(provenance)),
                evidence_url='/api/v1/strategies/'+key)
    result = {}
    for key in registry['assets']:
        asset = registry['assets'][key]
        item = dict(status='unpublished', effectiveness='insufficient',
            reason='Per-decision diagnostic is not yet published for this asset; composite results alone do not establish signal health.')
        lineage = {k:details[k] for k in plan['consumers'].get(key, []) if k in details}
        if lineage:
            item.update(lineage=lineage, lineage_through=min((d['through'] for d in lineage.values() if d['through']), default=None),
                status='lineage_only')
        if asset.get('source') and analytics is not None:
            pub = analytics.latest(asset['source'])
            if pub:
                item.update(status='published', publication=pub['version'], published_at=pub.get('published_at'),
                    source=asset['source'], reason='Inspect the source audit for per-series coverage and limitations.')
        if asset['contract'].get('monitor') == 'm1_rank_ic' and analytics is not None:
            saved = analytics.document('signal-decay/report', 'report')
            if saved:
                data = json.loads(saved[0]['payload'])
                measured = next((r for r in data.get('signals', []) if r['name']=='m1_total'), None)
                if measured:
                    item.update(status='diagnostic_published',effectiveness=measured['status'],
                        reason=measured['reason'], diagnostic=measured, publication=saved[1]['version'],
                        diagnostic_through=data.get('last_decision'), diagnostic_batch=data.get('batch'))
        if key == BROADTREND:
            value, pub = _document(analytics, 'asset/'+key)
            if value:
                if not pinned or pub['version'] != pinned['version']:
                    raise ValueError('Asset evidence publication changed while reading; refresh.')
                item.update(value, status='published', effectiveness=value['health']['status'],
                    reason=value['health']['reason'], publication=pub['version'])
                from systematic_trading.live.trading_calendar import latest_completed_us_session
                # Use the same completed-session deadline as the operator page.
                expected = str(latest_completed_us_session())
                item['expected_through'] = expected
                item['freshness'] = ('current' if value['through'] >= expected else 'stale') if key in plan['jobs'] else 'paused'
        result[key] = item
    return result


def signal_rows(settings, store, analytics):
    from .strategy_assets import catalog
    return [r for r in catalog(settings,store,analytics)['assets']
        if r['contract']['kind']=='signal' and r['tracking']=='required']


def series(analytics, asset_id, symbol, limit=260):
    if asset_id != BROADTREND:
        return dict(available=False, rows=[], message='Per-decision series not yet published; inspect lineage and source audit.')
    value, pub = _document(analytics, 'asset/'+asset_id)
    if not value or symbol not in value['symbols']:
        raise ValueError('Unknown or unpublished signal symbol')
    version = value.get('series_version',pub['version'])
    rows = analytics.pinned_rows('observations', SOURCE, version,
        family='strategy_asset_signal', entity=asset_id+'/'+symbol, limit=min(max(limit,1),1500), order=(('observed_at','DESC'),))
    return dict(available=True, publication=version, asset_id=asset_id, symbol=symbol,
        rows=[json.loads(r['payload']) for r in reversed(rows)])


def retain_idle_assets(analytics, plan, documents):
    """Preserve inspectable paused series by reference, without copying its rows."""
    from .strategy_assets import load_registry
    present = {d['point_key'] for d in documents}
    retained = []
    for asset in load_registry()['assets']:
        key = 'asset/'+asset
        if key in present or asset in plan['jobs']:
            continue
        old, pub = _document(analytics, key)
        if old:
            old.setdefault('series_version',pub['version'])
            retained.append(dict(point_key=key,media_type='application/json',payload=encode(old)))
    return retained
