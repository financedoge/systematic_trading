"""Durable rebalance preparation; renewed windows always require a new decision."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from decimal import Decimal

from systematic_trading.domain.enums import OrderEnvironment, OrderType, ProposalStatus
from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
from systematic_trading.execution.reconciliation import load_latest_ib_reconciliation
from systematic_trading.execution.window import proposal_is_expired
from systematic_trading.market_data.analytics_store import encode


def account_evidence(report):
    """Bind sizing to economic balances, not to the age of an unchanged capture."""
    return dict(accounts=sorted(report.managed_accounts),
        positions=sorted((p.model_dump(mode='json') for p in report.broker_positions), key=lambda p:p['symbol']),
        cash=sorted((dict(currency=str(p['currency']), amount=str(Decimal(str(p['amount'])).normalize()))
            for p in report.broker_cash), key=lambda p:p['currency']))


def prepared_proposal(proposal, report):
    return proposal.model_copy(update={'input_provenance': dict(proposal.input_provenance,
        prepared_account=account_evidence(report), account_observed_at=report.checked_at.isoformat())})


def prepared_submission_issues(settings, store, proposal):
    """Called by every router, including automatic and manual submission."""
    expected = proposal.input_provenance.get('prepared_account')
    if not expected:
        return []
    from systematic_trading.live.strategy_control import activation_issues
    issues = activation_issues(settings, store, datetime.now(UTC))
    report = load_latest_ib_reconciliation(settings)
    if report is None or encode(account_evidence(report)) != encode(expected):
        issues.append('Account balances changed since preparation. Refresh the rebalance and review the new orders.')
    # An immutable successor supersedes the old approval even before it expires.
    if any(p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') == proposal.proposal_id
           for p in store.list_proposals()):
        issues.append('This rebalance has a newer proposal. Review that proposal before routing.')
    return issues


def refresh_rebalance(settings, store, proposal_id, *, now=None):
    """Prepare a successor without approving, routing, or replaying broker attempts."""
    from systematic_trading.live.allocated_plan import build_allocated_plan
    from systematic_trading.live.initial_allocation import initial_allocation_window
    from systematic_trading.live.strategy_control import activation_issues, snapshot_for
    from systematic_trading.portfolio.strategy_allocation import allocation_binding_issues
    from systematic_trading.execution.broker import InteractiveBrokersAdapter
    now = now or datetime.now(UTC)
    with ORDER_CONNECTION_LOCK:
        source = store.get_proposal(proposal_id)
        if source is None:
            raise ValueError('Unknown proposal.')
        seen = set()
        while source.proposal_id not in seen:
            seen.add(source.proposal_id)
            children = [p for p in store.list_proposals()
                if p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') == source.proposal_id]
            if not children:
                break
            if len(children) != 1:
                raise ValueError('Conflicting rebalance successors require review.')
            source = children[0]
            if source.status == ProposalStatus.PENDING and not proposal_is_expired(source, settings, now=now):
                issues = allocation_binding_issues(store, source)
                if issues:
                    raise ValueError('; '.join(issues))
                return source
        if not source.input_provenance.get('prepared_account') or not source.input_provenance.get('allocation'):
            raise ValueError('Only an application-prepared allocation rebalance can be refreshed here.')
        if source.status == ProposalStatus.REJECTED:
            raise ValueError('A rejected rebalance requires a new allocation decision.')
        issues = allocation_binding_issues(store, source) + activation_issues(settings, store, now)
        if issues:
            raise ValueError('; '.join(issues))
        ancestors, cursor = set(), source
        while cursor and cursor.proposal_id not in ancestors:
            ancestors.add(cursor.proposal_id)
            parent = cursor.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id')
            cursor = store.get_proposal(parent) if parent else None
        for record in store.list_broker_order_records():
            if record.proposal_id not in ancestors:
                continue
            if (record.status.value != 'missed' or record.submitted_at or record.broker_order_id
                    or record.filled_quantity or record.execution_fills or record.pending_action
                    or record.execution_sync_issue or record.broker_observation):
                raise ValueError('A broker attempt exists. Reconcile and manage its outcome before refreshing; no automatic resend.')
        day, start, end = initial_allocation_window(settings, now)
        report = load_latest_ib_reconciliation(settings)
        snapshot = snapshot_for(settings, day)
        plan = build_allocated_plan(store=store, broker=InteractiveBrokersAdapter(settings),
            account_snapshot=snapshot, decision_date=day, intended_trade_date=start.date(),
            environment=OrderEnvironment.PAPER, order_type=OrderType.TWAP,
            target_decision_date=source.target_as_of or source.as_of, target_proposal=source)
        if plan.validation_issues:
            raise ValueError('; '.join(plan.validation_issues))
        fresh = load_latest_ib_reconciliation(settings)
        if fresh is None or account_evidence(fresh) != account_evidence(report):
            raise ValueError('Account changed during preparation. Refresh again.')
        old_orders = {(o.symbol, o.side):o for o in source.orders}
        orders = []
        for order in plan.proposal.orders:
            old = old_orders.get((order.symbol, order.side))
            if old is None:
                raise ValueError('The required trades changed direction or asset. Review a new allocation instead of renewing this intent.')
            orders.append(order.model_copy(update=dict(
                execution_start_time=start.strftime('%H:%M'), execution_end_time=end.strftime('%H:%M'),
                slippage_reference_price=old.slippage_reference_price or old.reference_price,
                slippage_trade_date=old.slippage_trade_date or old.intended_trade_date,
                slippage_start_time=old.slippage_start_time or old.execution_start_time,
                slippage_end_time=old.slippage_end_time or old.execution_end_time)))
        ancestry = source.input_provenance.get('deferred_rebalance', {})
        lineage = dict(root_proposal_id=ancestry.get('root_proposal_id', source.proposal_id),
            previous_proposal_id=source.proposal_id, prepared_at=now.isoformat(),
            original_intended_trade_date=ancestry.get('original_intended_trade_date', str(source.intended_trade_date)))
        proposal = prepared_proposal(plan.proposal, report).model_copy(update=dict(
            proposal_id='renew-'+sha256(source.proposal_id.encode()).hexdigest()[:20],
            created_at=now, status=ProposalStatus.PENDING, trigger='deferred_rebalance',
            automation_strategy_key=None, orders=orders,
            execution_deadline_at=min(end, start+timedelta(minutes=settings.execution_rebalance_timeout_minutes)).astimezone(UTC),
            summary='Refreshed rebalance; review quantities and window before approving. '+plan.proposal.summary))
        proposal.input_provenance['deferred_rebalance'] = lineage
        # Durable lineage invalidates the old route; a crash cannot erase the original approval.
        return store.queue_proposal_once(proposal)
