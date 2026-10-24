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
    from systematic_trading.portfolio.rebalance_intents import route_issues
    intent_issues = route_issues(store, proposal)
    expected = proposal.input_provenance.get('prepared_account')
    if not expected:
        return intent_issues
    from systematic_trading.live.strategy_control import activation_issues
    issues = activation_issues(settings, store, datetime.now(UTC))
    report = load_latest_ib_reconciliation(settings)
    if report is None or encode(account_evidence(report)) != encode(expected):
        issues.append('Account balances changed since preparation. Refresh the rebalance and review the new orders.')
    # An immutable successor supersedes the old approval even before it expires.
    if any(p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') == proposal.proposal_id
           for p in store.list_proposals()):
        issues.append('This rebalance has a newer proposal. Review that proposal before routing.')
    return list(dict.fromkeys(issues + intent_issues))


def refresh_rebalance(
    settings, store, proposal_id, *, now=None, automation_strategy_key=None,
    automation_policy_revision=None, order_client=None,
):
    """Prepare a successor without approving, routing, or replaying broker attempts.

    ``automation_strategy_key`` is supplied only by the enabled paper approval policy. It
    marks the successor as eligible for that policy's normal approval and routing checks;
    preparation itself still performs no approval or broker action.
    """
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
                from systematic_trading.portfolio.rebalance_intents import route_issues
                issues = allocation_binding_issues(store, source) + route_issues(store, source)
                if issues:
                    raise ValueError('; '.join(issues))
                return source
        from systematic_trading.portfolio.rebalance_intents import TRIGGERS, CLOSED, intent_state, route_issues, effective_target_date, sources
        if not (source.input_provenance.get('prepared_account') or
                (source.automation_strategy_key and source.trigger in TRIGGERS)):
            raise ValueError('Only an application-prepared rebalance can be refreshed here.')
        if source.status == ProposalStatus.REJECTED:
            raise ValueError('A rejected rebalance requires a new allocation decision.')
        if any(o.environment != OrderEnvironment.PAPER for o in source.orders) or source.portfolio_context.get('environment', 'paper') != 'paper':
            raise ValueError('Only paper rebalance objectives can be renewed.')
        if (automation_strategy_key is not None and source.automation_strategy_key is not None
                and source.automation_strategy_key != automation_strategy_key):
            raise ValueError('Source proposal differs from the enabled strategy policy.')
        if intent_state(store, source).get('status') in CLOSED:
            raise ValueError('The rebalance intent is closed; review a new objective.')
        if source.input_provenance.get('late_handover'):
            raise ValueError('Session-limited catch-up authority cannot be renewed.')
        if route_issues(store, source):
            raise ValueError('; '.join(route_issues(store, source)))
        issues = allocation_binding_issues(store, source) + activation_issues(settings, store, now)
        if issues:
            raise ValueError('; '.join(issues))
        ancestors, cursor = set(), source
        while cursor and cursor.proposal_id not in ancestors:
            if cursor.input_provenance.get('late_handover'):
                raise ValueError('Session-limited catch-up authority cannot be renewed, including through a successor.')
            ancestors.add(cursor.proposal_id)
            parent = cursor.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id')
            cursor = store.get_proposal(parent) if parent else None
        attempted = []
        for record in store.list_broker_order_records():
            if record.proposal_id not in ancestors:
                continue
            if (record.status.value != 'missed' or record.submitted_at or record.broker_order_id
                    or record.filled_quantity or record.execution_fills or record.pending_action
                    or record.execution_sync_issue or record.broker_observation):
                attempted.append(record)
        if attempted or automation_strategy_key is not None:
            validate_recovery_account(settings, store, attempted, now, order_client=order_client)
        # The durable router contract proves that no reservation means no send.
        # Old claims lack that evidence and require explicit operator recovery.
        import json
        policy_path = settings.data_dir / 'live' / 'paper_auto_approval.json'
        if policy_path.exists():
            policy = json.loads(policy_path.read_text(encoding='utf-8'))
            for ancestor in ancestors:
                claim = policy.get('attempts', {}).get(ancestor, {})
                ancestor_proposal = store.get_proposal(ancestor)
                if unresolved_submission_claim(store, ancestor_proposal, claim):
                    raise ValueError('An uncertain submission claim requires operator review; absence of orders is not proof of no send.')
        day, start, end = initial_allocation_window(settings, now)
        retained_date = effective_target_date(source, sources(store))
        report = load_latest_ib_reconciliation(settings)
        prepared_accounts = source.input_provenance.get('prepared_account', {}).get('accounts')
        if prepared_accounts and sorted(report.managed_accounts) != sorted(prepared_accounts):
            raise ValueError('Paper account changed since the original preparation; a new objective is required.')
        snapshot = snapshot_for(settings, day)
        # Component models must bind to the publication current at this decision date.
        # The stored target intent is taken from the source proposal below; binding the
        # component rebuild to an old target date makes the daily overlay schedule miss
        # its exact decision and blocks renewal after application catch-up.
        from systematic_trading.live.sota import build_sota_live_rebalance_plan
        builder = build_allocated_plan if source.input_provenance.get('allocation') else build_sota_live_rebalance_plan
        plan = builder(store=store, broker=InteractiveBrokersAdapter(settings),
            account_snapshot=snapshot, decision_date=day, intended_trade_date=start.date(),
            environment=OrderEnvironment.PAPER, order_type=OrderType.TWAP,
            target_decision_date=day, target_proposal=source.model_copy(update={'target_as_of':retained_date}))
        if plan.validation_issues:
            raise ValueError('; '.join(plan.validation_issues))
        fresh = load_latest_ib_reconciliation(settings)
        if fresh is None or account_evidence(fresh) != account_evidence(report):
            raise ValueError('Account changed during preparation. Refresh again.')
        old_orders = {(o.symbol, o.side):o for o in source.orders}
        old_sides = {o.symbol: o.side for o in source.orders}
        old_targets = sorted((t.symbol, t.target_weight) for t in source.targets)
        new_targets = sorted((t.symbol, t.target_weight) for t in plan.proposal.targets)
        if new_targets != old_targets:
            raise ValueError('Renewed target weights differ from the retained intent. Review a new allocation.')
        virtual = plan.proposal.input_provenance.get('allocation', {}).get('intent', {})
        if automation_strategy_key is not None and not plan.proposal.orders and not (
                virtual.get('crosses') or any(Decimal(v) for v in virtual.get('cash_transfers', {}).values())):
            from systematic_trading.portfolio.rebalance_intents import record_intent
            record_intent(store, source, status='completed', now=now,
                reason='Fresh reconciled holdings require no executable residual; remaining differences are below one share.')
            return source
        orders = []
        for order in plan.proposal.orders:
            old = old_orders.get((order.symbol, order.side))
            if old is None:
                if order.symbol in old_sides:
                    raise ValueError('The required trade direction changed. Review a new allocation instead of renewing this intent.')
                # Whole-share rounding at the refreshed prices can add a small leg in
                # the same allocation. Its benchmark starts with this refreshed plan.
                orders.append(order.model_copy(update=dict(
                    execution_start_time=start.strftime('%H:%M'), execution_end_time=end.strftime('%H:%M'),
                    slippage_reference_price=order.reference_price,
                    slippage_trade_date=order.intended_trade_date,
                    slippage_start_time=order.execution_start_time,
                    slippage_end_time=order.execution_end_time)))
                continue
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
        if automation_strategy_key is not None:
            lineage.update(automation_strategy_key=automation_strategy_key,
                automation_policy_revision=automation_policy_revision)
        proposal = prepared_proposal(plan.proposal, report).model_copy(update=dict(
            proposal_id='renew-'+sha256(source.proposal_id.encode()).hexdigest()[:20],
            created_at=now, status=ProposalStatus.PENDING, trigger='deferred_rebalance',
            target_as_of=retained_date, target_source_proposal_id=source.proposal_id,
            automation_strategy_key=automation_strategy_key, orders=orders,
            execution_deadline_at=min(end, start+timedelta(minutes=settings.execution_rebalance_timeout_minutes)).astimezone(UTC),
            summary=('Automatic renewal of a missed rebalance; review quantities and window. '
                if automation_strategy_key is not None else
                'Refreshed rebalance; review quantities and window before approving. ')
                + plan.proposal.summary))
        proposal.input_provenance['deferred_rebalance'] = lineage
        # Durable lineage invalidates the old route; a crash cannot erase the original approval.
        return store.queue_proposal_once(proposal)


def validate_recovery_account(settings, store, attempted, now, *, order_client=None):
    """Only terminal, reconciled execution evidence permits fresh residual sizing."""
    from systematic_trading.execution.management import TERMINAL, sync_orders
    from systematic_trading.execution.reconciliation import submission_reconciliation_issues
    issues = submission_reconciliation_issues(settings, now=now)
    if issues:
        raise ValueError(('Recovery of a broker attempt: ' if attempted else '') + '; '.join(issues))
    report = load_latest_ib_reconciliation(settings)
    for record in attempted:
        if record.pending_action or record.execution_sync_issue or record.status.value not in {'filled', 'cancelled', 'rejected'}:
            raise ValueError('A broker attempt is working or uncertain; reconcile before recovery.')
        if record.updated_at > report.checked_at or any(f.filled_at > report.checked_at for f in record.execution_fills):
            raise ValueError('A fresh reconciliation after the broker attempt is required.')
        if record.filled_quantity != sum(f.quantity for f in record.execution_fills):
            raise ValueError('Complete execution evidence is required before residual recovery.')
        if record.status.value == 'filled' and record.filled_quantity != record.order.quantity:
            raise ValueError('Filled order quantity is inconsistent; reconcile before recovery.')
        definitive_rejection = record.status.value == 'rejected' and not record.filled_quantity
        if record.status.value != 'filled' and not definitive_rejection and record.broker_observation.get('status') not in TERMINAL:
            raise ValueError('A broker attempt needs confirmed terminal broker evidence before recovery.')
        if record.broker_observation.get('status') == 'Filled' and record.filled_quantity != record.order.quantity:
            raise ValueError('Broker completion and fill history disagree; sync executions and reconcile again.')
    broker = sync_orders(settings, store, client=order_client)
    if any(row.get('status') not in TERMINAL for row in broker['orders']):
        raise ValueError('IB has an open or uncertain order; residual recovery must wait.')
    for record in attempted:
        current = next(r for r in store.list_broker_order_records(record.proposal_id)
                       if r.local_order_id == record.local_order_id)
        if current.updated_at > report.checked_at or current.pending_action or current.execution_sync_issue:
            raise ValueError('Broker evidence changed; sync executions and reconcile again before residual recovery.')
        observation = current.broker_observation
        if observation.get('filled') is not None and Decimal(str(observation['filled'])) != current.filled_quantity:
            raise ValueError('Broker filled quantity differs from execution history; sync executions and reconcile again.')


def unresolved_submission_claim(store, proposal, claim):
    if claim.get('outcome') not in {'claimed', 'review', 'submitted'}:
        return False
    if claim.get('phase') == 'before_router' or claim.get('reserve_before_send') is True:
        return False
    if proposal is None:
        return True
    # Legacy claims can recover only when every leg has real attempt evidence.
    # validate_recovery_account still requires those attempts to be terminal and
    # reconciled. Synthetic missed rows cannot prove that a send never occurred.
    covered = {r.order_index for r in store.list_broker_order_records(proposal.proposal_id)
               if r.broker_order_id is not None or r.submitted_at or r.filled_quantity or r.execution_fills}
    return covered != set(range(len(proposal.orders)))
