"""Operator previews, scheduled changes and guarded after-close handovers."""
import json
from datetime import UTC, date, datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

from systematic_trading.domain.enums import OrderEnvironment, OrderType
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
from systematic_trading.execution.reconciliation import load_latest_ib_reconciliation, submission_reconciliation_issues
from systematic_trading.live.sota import LiveAccountSnapshotInput
from systematic_trading.live.trading_calendar import next_us_trading_day, us_equity_market_close
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.portfolio.strategy_allocation import AllocationChange, control_events, control_state, scope_for
from systematic_trading.portfolio.strategy_book import initial_book
from systematic_trading.portfolio.context import portfolio_context
from systematic_trading.research.strategy_catalog import registered_strategy_definition

NY = ZoneInfo('America/New_York')


def candidate_evidence(settings, key):
    definition = registered_strategy_definition(key)
    if definition.universe_key != 'multi_asset' or definition.scheduler != 'static_monthly':
        raise ValueError('Trading allocations currently support the monitored monthly multi-asset strategies.')
    document = AnalyticsStore.from_settings(settings).document('tracked-strategies/calculations', 'report/'+key)
    if not document:
        raise ValueError('A completed application-owned strategy report is required.')
    report, provenance = json.loads(document[0]['payload']), json.loads(document[1]['provenance'])
    if report['strategyDefinition'] != definition.to_dict():
        raise ValueError('Published strategy definition differs from the registered version.')
    monitoring = report['monitoring']
    if monitoring.get('calculationOwner') != 'application' or not provenance['inputs'].get('batch'):
        raise ValueError('Application calculation and pinned audited inputs are required.')
    return dict(strategy_key=key, name=definition.name, definition=definition.to_dict(),
        report_url='/api/v1/strategies/'+key+'/report', calculation_revision=document[1]['version'],
        price_batch=provenance['inputs']['batch'], through=monitoring['monitoredThrough'],
        prospective_start=monitoring.get('prospectiveStart'), prospective_observations=monitoring.get('prospectiveObservations'),
        summary=report['summary'], warnings=report['warnings'],
        model_fit=report.get('modelTraining', {}).get('fitAsOf'),
        model_hash=report.get('modelTraining', {}).get('modelSha256'),
        usd_batch=report.get('usdModel', {}).get('batch'))


def next_handover(now):
    from systematic_trading.live.trading_calendar import previous_us_trading_day
    local = now.astimezone(NY)
    if us_equity_market_close(local.date()):
        return local.date()
    previous = previous_us_trading_day(local.date())
    if now < datetime.combine(next_us_trading_day(previous), time(9, 30), NY):
        return previous
    return next_us_trading_day(local.date())


def account_binding_issues(store, account):
    context = portfolio_context(store)
    state = control_state(store)
    expected = {value for value in (context.account_id,
        state['active'].get('account_id'), (state.get('pending') or {}).get('account_id')) if value}
    for record in store.list_broker_order_records():
        if record.environment.value == context.environment:
            expected.update(fill.account for fill in record.execution_fills
                if fill.account and context.includes(fill.filled_at))
    if expected and expected != {account}:
        return ['The reviewed portfolio account differs from reconciled or historical execution evidence.']
    return []


def activation_issues(settings, store, now):
    issues = submission_reconciliation_issues(settings, now=now)
    report = load_latest_ib_reconciliation(settings)
    if settings.default_environment != OrderEnvironment.PAPER:
        issues.append('Strategy changes are available for the paper portfolio only.')
    if not report or len(report.managed_accounts) != 1 or not report.managed_accounts[0].startswith('DU'):
        issues.append('One verified paper account is required.')
    elif report.warnings or report.ib_position_count != len(report.broker_positions):
        issues.append('Resolve broker reconciliation warnings before activation.')
    if report and len(report.managed_accounts) == 1:
        issues.extend(account_binding_issues(store, report.managed_accounts[0]))
    baseline = store.latest_pnl_baseline()
    for record in store.list_broker_order_records():
        if record.environment != OrderEnvironment.PAPER:
            continue
        if record.execution_sync_issue:
            issues.append(f'{record.order.symbol}: execution history requires review. {record.execution_sync_issue}')
        elif (record.pending_action or record.status.value == 'pending_submit'
                or ((baseline is None or (record.submitted_at or record.updated_at) > baseline.cutoff_at)
                    and record.status.value in {'submitted', 'acknowledged', 'partially_filled'})):
            issues.append(f'{record.order.symbol}: an open or uncertain order blocks strategy activation.')
    return sorted(set(issues))


def snapshot_for(settings, day):
    report = load_latest_ib_reconciliation(settings)
    if not report:
        raise ValueError('A reconciled account snapshot is required to calculate the order preview.')
    return LiveAccountSnapshotInput(as_of=day, captured_at=report.checked_at,
        positions=report.broker_positions, cash=report.broker_cash)


def preview_change(settings, store, change, *, now=None):
    now = now or datetime.now(UTC)
    state = control_state(store)
    if state['revision'] != change.expected_revision:
        raise ValueError('Configuration changed. Refresh before previewing.')
    if state.get('pending'):
        raise ValueError('Cancel the pending change before scheduling another.')
    keys = sorted({r.strategy_key for r in change.allocations or []} | ({change.sota_key} if change.sota_key else set()))
    evidence = {k:candidate_evidence(settings,k) for k in keys}
    result = dict(change=change.model_dump(mode='json'), evidence=evidence,
        current=state['active'], previewed_at=now.isoformat(), blockers=[],
        rollback=state['active']['allocations'], effects='SOTA designation only',
        approval_policy='A new trading allocation requires a new paper automatic-approval opt-in.')
    if change.allocations is not None:
        effective = date.fromisoformat(change.effective_close)
        if not us_equity_market_close(effective) or now >= datetime.combine(next_us_trading_day(effective), time(9, 30), NY):
            raise ValueError('Choose a current or future US market session for the after-close handover.')
        active = dict(version=change.event_id, key='allocation-'+change.event_id,
            allocations=[r.model_dump(mode='json') for r in change.allocations],
            effective_close=change.effective_close, max_batch_notional_cnh=str(change.max_batch_notional_cnh))
        # A future handover is priced on the latest completed, published session.
        day = min(date.fromisoformat(e['through']) for e in evidence.values())
        from systematic_trading.live.allocated_plan import build_allocated_plan
        snapshot = snapshot_for(settings, day)
        reconciliation = load_latest_ib_reconciliation(settings)
        if len(reconciliation.managed_accounts) != 1:
            raise ValueError('One verified account is required for an allocation preview.')
        account_id = reconciliation.managed_accounts[0]
        if not account_id.startswith('DU') or account_binding_issues(store, account_id):
            raise ValueError('The allocation preview requires matching paper account evidence.')
        active['account_id'] = account_id
        plan = build_allocated_plan(store=store, broker=InteractiveBrokersAdapter(settings),
            account_snapshot=snapshot, decision_date=day, intended_trade_date=next_us_trading_day(effective),
            environment=OrderEnvironment.PAPER, order_type=OrderType.TWAP,
            active_override=dict(active, effective_close=str(day)))
        result.update(proposal=plan.proposal.model_dump(mode='json'), account_id=account_id,
            account=dict(positions=snapshot.model_dump(mode='json')['positions'], cash=snapshot.model_dump(mode='json')['cash']),
            valuation_date=str(day), active=active, blockers=sorted(set(activation_issues(settings, store, now)+plan.validation_issues)),
            effects='After-close handover; net ETF orders require approval for the next US trading session.',
            intended_trade_date=str(next_us_trading_day(effective)),
            reserve_weight=str(1-sum(r.weight for r in change.allocations)))
    # Timestamps and random proposal IDs are not economic preview inputs.
    binding = dict(change=result['change'], current_revision=state['revision'], evidence=evidence,
        account=result.get('account'), account_id=result.get('account_id'), targets=result.get('proposal', {}).get('targets'),
        orders=result.get('proposal', {}).get('orders'))
    result['review_token'] = digest(encode(binding))
    return result


def schedule_change(settings, store, change, review_token, *, evidence_reviewed, now=None):
    now = now or datetime.now(UTC)
    with ORDER_CONNECTION_LOCK:
        # Resolve an exact duplicate before fresh-market checks; never execute twice.
        request_hash = digest(encode(change.model_dump(mode='json')))
        existing = next((e for e in control_events(store) if e['event_id'] == change.event_id), None)
        if existing:
            if existing['request_hash'] != request_hash:
                raise ValueError('Idempotency key was used for a different change.')
            return control_state(store)
        if not evidence_reviewed:
            raise ValueError('Confirm review of the strategy reports, prospective evidence, limits and rollback.')
        preview = preview_change(settings, store, change, now=now)
        if preview['review_token'] != review_token:
            raise ValueError('Prices, model inputs or account holdings changed. Preview again.')
        state = control_state(store)
        if change.allocations is None:
            state = dict(state, sota_key=change.sota_key)
            kind = 'sota_designated'
        else:
            state = dict(state, pending=dict(change=change.model_dump(mode='json'), preview=preview,
                approved_at=now.isoformat(), scope=scope_for(store), account_id=preview.get('account_id')))
            kind = 'change_scheduled'
        event = dict(event_id=change.event_id, request_hash=request_hash, kind=kind, at=now.isoformat(),
            operator=change.operator, reason=change.reason, evidence=preview['evidence'],
            rollback=preview['rollback'], review_token=review_token)
        return store.commit_strategy_control(scope_for(store), change.expected_revision, state, event)


def cancel_pending(store, expected_revision, operator, reason, *, now=None):
    now = now or datetime.now(UTC)
    if not operator.strip() or not reason.strip():
        raise ValueError('Operator and reason are required.')
    with ORDER_CONNECTION_LOCK:
        state = control_state(store)
        if not state.get('pending'):
            raise ValueError('No pending allocation change.')
        event = dict(event_id=uuid4().hex, request_hash=digest(encode([expected_revision,operator,reason])),
            kind='change_cancelled', at=now.isoformat(), operator=operator, reason=reason,
            cancelled_event=state['pending']['change']['event_id'])
        return store.commit_strategy_control(scope_for(store), expected_revision, dict(state,pending=None), event)


def activate_pending(settings, store, *, now=None, order_client=None):
    now = now or datetime.now(UTC)
    with ORDER_CONNECTION_LOCK:
        state = control_state(store)
        pending = state.get('pending')
        if not pending:
            return None
        change = AllocationChange.model_validate(pending['change'])
        day = date.fromisoformat(change.effective_close)
        close = datetime.combine(day, us_equity_market_close(day), NY)
        next_open = datetime.combine(next_us_trading_day(day), time(9, 30), NY)
        if now < close:
            return 'Waiting for the approved session close.'
        if now >= next_open:
            return 'Handover window missed. Cancel and review a new date; history will not be backdated.'
        issues = activation_issues(settings, store, now)
        if issues:
            return '; '.join(issues)
        from systematic_trading.execution.management import TERMINAL, sync_orders
        broker = sync_orders(settings, store, client=order_client)
        if any(r.get('status') not in TERMINAL for r in broker['orders']):
            return 'Broker open or uncertain orders block the handover.'
        from systematic_trading.live.allocated_plan import build_allocated_plan
        snapshot = snapshot_for(settings, day)
        active = dict(pending['preview']['active'], activated_at=now.isoformat(), approved_at=pending['approved_at'],
            capital_rebalance='monthly', history_label='Operator-approved allocation',
            opening=dict(at=now.isoformat(), snapshot=snapshot.model_dump(mode='json'),
                book=initial_book(snapshot.model_dump(mode='json'), pending['preview']['active']['allocations'])))
        try:
            plan = build_allocated_plan(store=store, broker=InteractiveBrokersAdapter(settings),
                account_snapshot=snapshot, decision_date=day, intended_trade_date=next_us_trading_day(day),
                environment=OrderEnvironment.PAPER, order_type=OrderType.TWAP, active_override=active)
        except (ValueError, OSError) as exc:
            return str(exc)
        if plan.validation_issues:
            return '; '.join(plan.validation_issues)
        # Normal app refreshes may advance prices and scheduled model fits. The
        # approved recipe is frozen; execution receipts bind the fresh audited inputs.
        for key,evidence in pending['preview']['evidence'].items():
            if candidate_evidence(settings,key)['definition'] != evidence['definition']:
                return 'Strategy recipe changed since approval. Cancel and review the updated evidence.'
        latest = snapshot_for(settings, day)
        if (latest.positions,latest.cash) != (snapshot.positions,snapshot.cash):
            return 'Account changed during activation; waiting for reconciliation.'
        active['opening'].update(targets=[t.model_dump(mode='json') for t in plan.proposal.targets], prices=plan.proposal.input_provenance['allocation']['intent']['prices'],
            fx=plan.proposal.input_provenance['allocation']['intent']['fx'],
            input_provenance=plan.proposal.input_provenance)
        event = dict(event_id='activate-'+change.event_id, request_hash=digest(encode(pending)),
            kind='allocation_activated', at=now.isoformat(), effective_close=str(day),
            operator=change.operator, reason=change.reason, previous=state['active'], active=active)
        updated = dict(state, active=active, pending=None, sota_key=change.sota_key or state['sota_key'])
        store.commit_strategy_control(scope_for(store), state['revision'], updated, event)
        return 'Trading allocation activated. A fresh proposal and routing approval are required.'
