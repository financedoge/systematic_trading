"""Portfolio objectives outlive execution windows.

Intent state uses the existing transactional CAS/audit store under its own scope.
Proposals and broker records remain immutable attempt evidence; no schema migration
or reinterpretation of an uncertain broker outcome is required.
"""
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4

from systematic_trading.domain.enums import ProposalStatus
from systematic_trading.portfolio.context import portfolio_context
from systematic_trading.portfolio.strategy_allocation import allocation_binding_issues, scope_for, trading_definition

TRIGGERS = {'empty_portfolio', 'portfolio_drift', 'scheduled_rebalance', 'deferred_rebalance', 'allocation_handover'}
CLOSED = {'cancelled', 'superseded', 'completed'}


def target_key(proposal):
    # Cash is the residual of these weights, so it is included in this identity.
    return tuple(sorted((t.symbol, str(Decimal(t.target_weight).normalize())) for t in proposal.targets))


def sources(store):
    definition, context = trading_definition(store), portfolio_context(store)
    return [p for p in store.list_proposals() if p.trigger in TRIGGERS
            and (p.automation_strategy_key or p.input_provenance.get('prepared_account') or p.input_provenance.get('allocation'))
            and p.sleeve == definition.sleeve_name and context.includes(p.created_at)
            and all(o.environment.value == context.environment == 'paper' for o in p.orders)
            and not allocation_binding_issues(store, p)]


def effective_target_date(proposal, candidates):
    # Older allocated-plan versions copied the weights but stamped the month-end
    # instead of the retained decision date. Resolve only identical stored vectors.
    return max([proposal.target_as_of or proposal.as_of] + [p.target_as_of or p.as_of
        for p in candidates if p.created_at <= proposal.created_at and target_key(p) == target_key(proposal)])


def latest_rebalance(store):
    candidates = sources(store)
    replaced = {p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') for p in candidates}
    leaves = [p for p in candidates if p.proposal_id not in replaced]
    rank = lambda p: (effective_target_date(p, candidates), p.created_at)
    if not leaves:
        if candidates:
            raise ValueError('Cyclic rebalance successors require review.')
        return None
    newest = max(map(rank, leaves))
    latest = [p for p in leaves if rank(p) == newest]
    if len(latest) != 1:
        raise ValueError('Conflicting newest rebalance intents require review.')
    return latest[0]


def root_id(proposal):
    return proposal.input_provenance.get('deferred_rebalance', {}).get('root_proposal_id', proposal.proposal_id)


def intent_scope(store, proposal):
    return f'rebalance-intent:{scope_for(store)}:{root_id(proposal)}'


def intent_state(store, proposal):
    return store.strategy_control_state(intent_scope(store, proposal)) or {}


def record_intent(store, proposal, *, status='outstanding', now=None, reason='', **details):
    now = now or datetime.now(UTC)
    root = store.get_proposal(root_id(proposal)) or proposal
    previous = intent_state(store, proposal)
    if previous.get('status') in CLOSED:
        # A concurrent refresh or recovery writer must never resurrect a closed
        # objective after reading an older proposal snapshot.
        return previous
    state = dict(previous or dict(intent_id=root.proposal_id, created_at=root.created_at.isoformat(),
        target_as_of=str(effective_target_date(root, sources(store))),
        targets=[t.model_dump(mode='json') for t in root.targets],
        allocation=root.input_provenance.get('allocation', {}).get('version')),
        status=status, proposal_id=proposal.proposal_id, reason=reason, **details)
    if {k:v for k,v in state.items() if k != 'updated_at'} == {k:v for k,v in previous.items() if k != 'updated_at'}:
        return previous
    state['updated_at'] = now.isoformat()
    return store.commit_strategy_control(intent_scope(store, proposal), previous.get('revision', 0), state,
        dict(event_id=uuid4().hex, request_hash=sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
             kind='rebalance_intent', at=now.isoformat(), reason=reason))


def sync_intents(store, *, now=None):
    """Lazy migration from persisted proposals/approvals; expiration never cancels."""
    proposals = sources(store)
    approvals = store.strategy_approval_times()
    records = store.list_broker_order_records()
    replaced = {p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') for p in proposals}
    leaves = [p for p in proposals if p.proposal_id not in replaced]
    adopted = [p for p in leaves if p.proposal_id in approvals or p.status == ProposalStatus.APPROVED]
    latest_adopted = max(adopted, key=lambda p:(effective_target_date(p, proposals), p.created_at), default=None)
    for p in leaves:
        state = intent_state(store, p)
        if state.get('status') in CLOSED:
            continue
        status, reason = 'outstanding', state.get('reason') or 'Awaiting reconciliation and completion of the retained target.'
        if p.status == ProposalStatus.REJECTED:
            status, reason = 'cancelled', 'The operator rejected this portfolio objective.'
        elif latest_adopted and root_id(p) != root_id(latest_adopted) and (
                effective_target_date(p, proposals), p.created_at) < (
                effective_target_date(latest_adopted, proposals), latest_adopted.created_at):
            status, reason = 'superseded', f'Newer adopted objective: {root_id(latest_adopted)}.'
        elif p.proposal_id in approvals or p.status == ProposalStatus.APPROVED:
            own = [r for r in records if r.proposal_id == p.proposal_id]
            unsettled = any(r.pending_action or r.execution_sync_issue or r.status.value in {
                'pending_submit', 'submitted', 'acknowledged', 'partially_filled'} for r in own)
            if not unsettled and (not p.orders or all(any(r.order_index == i and r.status.value == 'filled'
                    and r.filled_quantity >= o.quantity and not r.pending_action and not r.execution_sync_issue
                    for r in own) for i,o in enumerate(p.orders))):
                status, reason = 'completed', 'All approved legs completed.'
        record_intent(store, p, status=status, now=now, reason=reason)


def route_issues(store, proposal):
    state = intent_state(store, proposal)
    if state.get('status') in CLOSED:
        return [f"Rebalance intent is {state['status']}: {state.get('reason', '')}"]
    if any(p.input_provenance.get('deferred_rebalance', {}).get('previous_proposal_id') == proposal.proposal_id
           for p in store.list_proposals()):
        return ['This rebalance has a newer proposal. Review that proposal before routing.']
    if proposal in sources(store):
        latest = latest_rebalance(store)
        if latest and latest.proposal_id != proposal.proposal_id:
            return [f'Newer rebalance objective {latest.proposal_id} requires review before routing this proposal.']
    return []


def cancel_intent(store, proposal_id, *, operator, reason, now=None):
    proposal = store.get_proposal(proposal_id)
    if proposal is None or proposal not in sources(store):
        raise ValueError('Unknown active paper rebalance.')
    if not operator.strip() or not reason.strip():
        raise ValueError('Operator and cancellation reason are required.')
    if intent_state(store, proposal).get('status') in {'completed', 'superseded'}:
        raise ValueError('This rebalance objective is already completed or superseded.')
    # Cancellation ends retry authority. Working orders remain explicitly blocked
    # in the ordinary order-management/reconciliation path; never cancel IB here.
    return record_intent(store, proposal, status='cancelled', now=now,
        reason=reason.strip(), operator=operator.strip())


def recovery_summary(store, proposal, now):
    state = intent_state(store, proposal)
    root = store.get_proposal(root_id(proposal)) or proposal
    return dict(intent_id=root_id(proposal), intent_status=state.get('status', 'outstanding'),
        pending_since=root.created_at, pending_age_seconds=max(0, int((now-root.created_at).total_seconds())))
