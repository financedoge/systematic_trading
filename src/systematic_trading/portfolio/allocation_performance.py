"""Read-only comparison of dated capital allocations using published strategy NAVs.

This is a strategy-NAV benchmark, separate from the reference-fill/holdings ledger.
Switches buy virtual units at the effective close; the outgoing mix earns that
close's return. Capital weights drift within each allocation period.
"""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from systematic_trading.live.trading_calendar import us_trading_dates_after
from systematic_trading.market_data.analytics_store import digest


CONTRACT = "allocation-strategy-nav-v2-reset-spot"


def comparison_timeline(store, timeline, account):
    """Recover display-only legacy epochs from executed, identified proposals.

    This does not rewrite allocation authority. Daily NAV comparisons use the
    close before the first evidenced execution; intraday timing is disclosed.
    """
    from systematic_trading.portfolio.context import portfolio_context, NY
    from systematic_trading.live.trading_calendar import previous_us_trading_day
    from systematic_trading.research.strategy_catalog import registered_strategy_definition
    if not account:
        return timeline
    opening = str(account[0][0])
    context = portfolio_context(store)
    # Retain the allocation already active at a later P&L reset, clipped to
    # that reset's opening value, rather than resetting at its old switch.
    prior = [e for e in timeline if e['effective_close'] <= opening]
    explicit = ([dict(prior[-1], effective_close=opening)] if prior else []) + [
        e for e in timeline if e['effective_close'] > opening]
    if prior:
        return explicit
    stop = explicit[0]['effective_close'] if explicit else '9999-12-31'
    fills = {}
    records = store.list_broker_order_records()
    accounts = {f.account for r in records for f in r.execution_fills if f.account and context.includes(f.filled_at)}
    account_id = context.account_id or (next(iter(accounts)) if len(accounts) == 1 else None)
    if not account_id:
        return explicit
    for record in records:
        if record.execution_sync_issue:
            continue
        for fill in record.execution_fills:
            if context.includes(fill.filled_at) and fill.account == account_id:
                fills.setdefault(record.proposal_id, []).append(fill.filled_at)
    candidates = []
    for proposal in store.list_proposals():
        if proposal.proposal_id not in fills or proposal.input_provenance.get('allocation'):
            continue
        key = proposal.input_provenance.get('strategy_definition', {}).get('key') or proposal.sleeve.replace('-', '_')
        try:
            definition = registered_strategy_definition(key)
        except ValueError:
            continue
        if definition.sleeve_name != proposal.sleeve:
            continue
        first_fill = min(fills[proposal.proposal_id])
        start = max(opening, str(previous_us_trading_day(first_fill.astimezone(NY).date())))
        if start < stop:
            candidates.append((first_fill, dict(version='executed/'+proposal.proposal_id,
                effective_close=start, activated_at=first_fill.isoformat(), label='100% '+definition.name,
                allocations=[dict(strategy_key=key, weight='1')],
                evidence=dict(proposal_id=proposal.proposal_id, first_fill_at=first_fill.isoformat()),
                warning='Legacy allocation recovered from executed proposal. Daily comparison starts at the preceding close; intraday handover timing and costs are not modeled.')))
    recovered = []
    for _, epoch in sorted(candidates, key=lambda item: item[0]):
        if recovered and recovered[-1]['allocations'] == epoch['allocations']:
            continue
        if recovered and recovered[-1]['effective_close'] == epoch['effective_close']:
            recovered.pop()
        recovered.append(epoch)
    return recovered + explicit


def published_nav(analytics, key, version):
    """An old parent is also available as an exact named, app-run benchmark."""
    saved = analytics.document('strategy-serving', 'detail/'+key)
    detail = json.loads(saved[0]['payload']) if saved else {}
    if detail.get('app_tracking'):
        if saved[1]['version'] != version:
            raise ValueError('Strategy publication changed during allocation performance calculation.')
        return detail, dict(publication=version, document_sha256=digest(saved[0]['payload']))
    source = 'tracked-strategies/calculations'
    anchor = analytics.document(source, 'detail/'+key+'_usd_v1')
    report = analytics.document(source, 'report/'+key+'_usd_v1')
    if anchor and report and anchor[1]['version'] == report[1]['version']:
        parent = json.loads(anchor[0]['payload'])
        rows = json.loads(report[0]['payload']).get('chart', [])
        if (parent.get('strategy_id') == key+'_usd_v1' and parent.get('app_tracking')
                and rows and all(key in r.get('benchmarks', {}) for r in rows)):
            return dict(parent, strategy_id=key, nav_series=[dict(trade_date=r['date'],
                nav_cnh=r['benchmarks'][key]['nav']) for r in rows]), dict(
                    publication=report[1]['version'], source=source, benchmark_key=key,
                    document_sha256=digest(report[0]['payload']), lineage_sha256=digest(anchor[0]['payload']))
    return detail, dict(publication=version, document_sha256=digest(saved[0]['payload']) if saved else None)


def positive(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number > 0 else None
    except (InvalidOperation, ValueError):
        return None


def build_strategy_comparison(timeline, analytics, account):
    """Pin one complete app publication; never substitute archived/provider prices.

Missing observations stop a period rather than implying zero returns. Independent
actual-rebased periods may resume at the next verified switch, but an interrupted
continuous chain cannot resume without its missing handover value.
    """
    result = dict(strategy=[], actual_rebased=[], periods=[], sources={}, warnings=[],
                  base_nav_cnh=None, comparison_start_date=None, contract=CONTRACT)
    if not timeline:
        return result
    publication = analytics.latest("strategy-serving") if analytics else None
    version = publication["version"] if publication else None
    account_values = {str(day): value for day, value in account}
    histories = {}
    for key in sorted({r['strategy_key'] for e in timeline for r in e['allocations']}):
        detail, source = published_nav(analytics, key, version) if analytics else ({}, {})
        if not detail:
            result['warnings'].append(f"Theoretical performance: published strategy NAV unavailable for {key}.")
            continue
        provenance = detail.get('input_provenance', {})
        if (detail.get('strategy_id') != key or not detail.get('app_tracking')
                or not provenance.get('batch') or not provenance.get('governed_files')):
            result['warnings'].append(f"Theoretical performance: {key} has no app-calculated, audited NAV publication.")
            continue
        rows = {}
        for row in detail.get('cnh_nav_series' if detail.get('accounting_currency')=='USD' else 'nav_series', []):
            day = date.fromisoformat(row['trade_date']).isoformat()
            nav = positive(row.get('nav_cnh'))
            if day in rows or nav is None:
                raise ValueError(f'Invalid or duplicate published strategy NAV: {key} on {day}.')
            rows[day] = nav
        histories[key] = rows
        result['sources'][key] = dict(source, input_provenance=provenance)
        result['warnings'].extend(detail.get('warnings', []))

    carried, base, anchored = None, None, False
    for i, epoch in enumerate(timeline):
        start = epoch['effective_close']
        end = timeline[i+1]['effective_close'] if i+1 < len(timeline) else None
        weights = {r['strategy_key']: Decimal(r['weight']) for r in epoch['allocations']}
        if not weights or any(not w.is_finite() or w <= 0 for w in weights.values()) or sum(weights.values()) > 1:
            raise ValueError('Invalid capital weights in allocation history.')
        observed_account_nav = positive(account_values.get(start))
        actual_base = observed_account_nav or positive(epoch.get('opening_nav_cnh'))
        period = dict(version=epoch['version'], label=epoch['label'], start=start, end=end,
                      through=None, observations=0, theoretical_return=None, actual_return=None,
                      actual_start_nav_cnh=str(actual_base) if actual_base else None,
                      theoretical_start_nav_cnh=str(carried) if carried else None,
                      warnings=[epoch['warning']] if epoch.get('warning') else [])
        result['periods'].append(period)
        missing = [k for k in weights if start not in histories.get(k, {})]
        if missing:
            period['warnings'].append(f"Missing exact switch-date NAV on {start}: {', '.join(missing)}.")
            carried = None
            continue
        anchored_now = False
        # Once an earlier allocation could not be verified, only a matched
        # observed account NAV may establish the recovery anchor. Recorded
        # opening values remain valid for an uninterrupted first allocation,
        # but cannot bridge a later historical gap.
        anchor_base = observed_account_nav if i > 0 else actual_base
        if not anchored and anchor_base is not None:
            # Do not invent a link through an unavailable historical allocation.
            # Begin at the first later close with both audited strategy NAV and
            # an observed account value; use its NAV as the explicit 1.0 base.
            carried = base = anchor_base
            anchored = anchored_now = True
            result['base_nav_cnh'] = str(base)
            result['comparison_start_date'] = start
            if i:
                result['warnings'].append(
                    f"Cumulative strategy comparison starts at the verified account NAV on {start}; "
                    "earlier allocation history is excluded because its exact audited strategy NAV is unavailable.")
        # Each strategy keeps its own scheduled rebalances and costs already in
        # NAV. No daily reset of capital weights or extra model fees are implied.
        last_available = min(max(histories[k]) for k in weights)
        stop = min(end, last_available) if end else last_available
        days = [start] + [str(d) for d in us_trading_dates_after(date.fromisoformat(start), date.fromisoformat(stop))]
        growth = Decimal(1)
        for day in days:
            if any(day not in histories[k] for k in weights):
                period['warnings'].append(f"Missing published strategy NAV on {day}; period stops before the gap.")
                break
            growth = 1 - sum(weights.values()) + sum(
                w * histories[k][day] / histories[k][start] for k, w in weights.items())
            common = dict(trade_date=day, allocation_version=epoch['version'], allocation_label=epoch['label'],
                          period_start=start, period_growth=str(growth), is_theoretical=True)
            if carried is not None:
                point = dict(common, nav_cnh=str(carried*growth), index=str(carried*growth/base*100))
                # A single shared boundary point preserves continuity; its return
                # belongs to the outgoing allocation. Mark an incoming anchor
                # so a current-period-only view reports its zero opening.
                if not result['strategy'] or result['strategy'][-1]['trade_date'] != day:
                    result['strategy'].append(point)
                else:
                    result['strategy'][-1]['switch_anchor'] = True
            if actual_base is not None:
                result['actual_rebased'].append(dict(common, nav_cnh=str(actual_base*growth),
                    index=str(carried*growth/base*100) if carried is not None else str(growth*100),
                    break_before=day == start and i > 0 and not anchored_now,
                    return_break=day == start and i > 0 and carried is None))
            period.update(through=day, observations=period['observations']+1, theoretical_return=str(growth-1))
        if period['through']:
            actual_end = positive(account_values.get(period['through']))
            if actual_base:
                period['theoretical_pnl_cnh'] = str(actual_base*(growth-1))
            if actual_end and actual_base:
                period.update(actual_return=str(actual_end/actual_base-1), actual_end_nav_cnh=str(actual_end),
                              actual_pnl_cnh=str(actual_end-actual_base))
        if not actual_base:
            period['warnings'].append(f"Actual rebasing unavailable: no observed account NAV at {start}.")
        if end and period['through'] != end:
            period['warnings'].append(f"No complete theoretical handover at {end}; continuous compounding stops.")
            carried = None
        elif carried is not None:
            carried *= growth
    if analytics and (analytics.latest('strategy-serving') or {}).get('version') != version:
        raise ValueError('Strategy publication changed during allocation performance calculation.')
    for source in result['sources'].values():
        if source.get('source') and (analytics.latest(source['source']) or {}).get('version') != source['publication']:
            raise ValueError('Strategy benchmark publication changed during allocation performance calculation.')
    result['warnings'].extend(w for p in result['periods'] for w in p['warnings'])
    result['warnings'].append('Theoretical comparison buys capital-weighted published strategy NAV units at each switch close; weights drift until the next switch. Unallocated capital is flat CNH reserve. Strategy rebalances and simulated costs are already included; extra handover costs are not modeled. This comparison is separate from the monthly-reset execution reference.')
    if account and str(account[0][0]) < timeline[0]['effective_close']:
        result['warnings'].append('Strategy assignment is unavailable for part of this reset episode; the theoretical comparison begins at its first evidenced allocation.')
    result['warnings'].append('Cumulative returns carry through allocation switches. Actual rebasing changes displayed period levels only; those changes are excluded from strategy returns.')
    return result
