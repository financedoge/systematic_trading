from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerOrderRecord, TradeProposal
from systematic_trading.domain.enums import BrokerOrderStatus, ProposalStatus
from systematic_trading.storage.interfaces import TradingStore


ACTIONABLE_FAILURE_STATUSES = {
    BrokerOrderStatus.CANCELLED,
    BrokerOrderStatus.REJECTED,
    BrokerOrderStatus.MISSED,
}


def execution_deadline(proposal: TradeProposal, settings: AppSettings) -> datetime | None:
    if proposal.execution_deadline_at is not None:
        return proposal.execution_deadline_at.astimezone(UTC)
    if proposal.intended_trade_date is None:
        return None
    start_text = next(
        (order.execution_start_time for order in proposal.orders if order.execution_start_time),
        settings.execution_twap_start_time,
    )
    start = time.fromisoformat(start_text)
    local_start = datetime.combine(
        proposal.intended_trade_date,
        start,
        tzinfo=ZoneInfo(settings.automation_timezone),
    )
    return datetime.fromtimestamp(
        local_start.timestamp() + max(settings.execution_rebalance_timeout_minutes, 0) * 60,
        tz=UTC,
    )


def attach_execution_deadline(proposal: TradeProposal, settings: AppSettings) -> TradeProposal:
    deadline = execution_deadline(proposal, settings)
    if deadline is None or proposal.execution_deadline_at is not None:
        return proposal
    return proposal.model_copy(update={"execution_deadline_at": deadline})


def expire_due_proposals(
    store: TradingStore,
    settings: AppSettings,
    *,
    now: datetime | None = None,
) -> list[TradeProposal]:
    checked_at = (now or datetime.now(tz=UTC)).astimezone(UTC)
    updated: list[TradeProposal] = []
    for stored in store.list_proposals():
        proposal = attach_execution_deadline(stored, settings)
        deadline = execution_deadline(proposal, settings)
        if proposal != stored:
            store.save_proposal(proposal)
        if deadline is None or checked_at <= deadline:
            continue
        if proposal.status not in {ProposalStatus.PENDING, ProposalStatus.APPROVED}:
            continue
        actionable = _actionable_order_indexes(proposal, store.list_broker_order_records(proposal.proposal_id))
        if proposal.status == ProposalStatus.APPROVED and not actionable:
            continue
        reason = (
            f"Execution window expired at {deadline.isoformat()}; "
            f"proposal was not fully routed within {settings.execution_rebalance_timeout_minutes} minute(s) of market open."
        )
        for index in actionable:
            order = proposal.orders[index]
            store.save_broker_order_record(
                BrokerOrderRecord(
                    local_order_id=f"missed-{proposal.proposal_id}-{index:03d}",
                    proposal_id=proposal.proposal_id,
                    environment=order.environment,
                    order_index=index,
                    order=order,
                    order_ref=f"st-{proposal.proposal_id}-{index:02d}-missed",
                    status=BrokerOrderStatus.MISSED,
                    updated_at=checked_at,
                    remaining_quantity=order.quantity,
                    message=reason,
                )
            )
        missed = proposal.model_copy(
            update={
                "status": ProposalStatus.MISSED,
                "execution_deadline_at": deadline,
                "missed_at": checked_at,
                "missed_reason": reason,
            }
        )
        store.save_proposal(missed)
        updated.append(missed)
    return updated


def proposal_is_expired(
    proposal: TradeProposal,
    settings: AppSettings,
    *,
    now: datetime | None = None,
) -> bool:
    deadline = execution_deadline(proposal, settings)
    checked_at = (now or datetime.now(tz=UTC)).astimezone(UTC)
    return proposal.status == ProposalStatus.MISSED or (deadline is not None and checked_at > deadline)


def _actionable_order_indexes(
    proposal: TradeProposal,
    records: list[BrokerOrderRecord],
) -> set[int]:
    latest: dict[int, BrokerOrderRecord] = {}
    for record in records:
        current = latest.get(record.order_index)
        if current is None or record.updated_at >= current.updated_at:
            latest[record.order_index] = record
    return {
        index
        for index in range(len(proposal.orders))
        if index not in latest or latest[index].status in ACTIONABLE_FAILURE_STATUSES
    }
