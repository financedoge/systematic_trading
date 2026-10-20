"""Resolve the adopted deployed target, never a file's modification time."""
from systematic_trading.domain.enums import ProposalStatus
from systematic_trading.portfolio.context import portfolio_context


def approved_target(store, definition, first_decision, through):
    """Latest adopted target for the active allocation.

    A rebalance whose execution window elapsed can end as ``missed`` even when most
    legs filled and only a residual failed. The filled part already changed the book,
    so the proposal's frozen targets remain the adopted target until a later rebalance
    is approved; falling back to the previous month-end would drift the account toward
    a stale target. A fully missed proposal with no fill was never adopted.
    """
    from systematic_trading.portfolio.strategy_allocation import allocation_binding_issues
    context = portfolio_context(store)
    adopted_missed = {
        record.proposal_id for record in store.list_broker_order_records()
        if record.filled_quantity > 0 and record.proposal_id
    }
    candidates = [p for p in store.list_proposals()
        if not allocation_binding_issues(store, p) and p.sleeve == definition.sleeve_name and p.targets
        and (p.status == ProposalStatus.APPROVED
             or (p.status == ProposalStatus.MISSED and p.proposal_id in adopted_missed))
        and all(order.environment.value == context.environment for order in p.orders)
        and first_decision <= (p.target_as_of or p.as_of) <= through
        and context.includes(p.created_at)]
    return max(candidates, key=lambda p: (p.target_as_of or p.as_of, p.created_at), default=None)
