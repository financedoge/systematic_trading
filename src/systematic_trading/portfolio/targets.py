"""Resolve the approved deployed target, never a file's modification time."""
from systematic_trading.domain.enums import ProposalStatus
from systematic_trading.portfolio.context import portfolio_context


def approved_target(store, definition, first_decision, through):
    context = portfolio_context(store)
    candidates = [p for p in store.list_proposals()
        if p.sleeve == definition.sleeve_name and p.targets and p.status == ProposalStatus.APPROVED
        and all(order.environment.value == context.environment for order in p.orders)
        and first_decision <= (p.target_as_of or p.as_of) <= through
        and context.includes(p.created_at)]
    return max(candidates, key=lambda p: (p.target_as_of or p.as_of, p.created_at), default=None)
