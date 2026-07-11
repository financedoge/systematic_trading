from __future__ import annotations

from systematic_trading.domain import (
    BrokerOrderRecord,
    EventSource,
    FillRecordedEvent,
    FillRecordedPayload,
    OrderEnvironment,
    OrderLifecyclePayload,
    OrderStatusChangedEvent,
    ProposalCreatedEvent,
    ProposalDecisionRecordedEvent,
    ProposalEventPayload,
    ApprovalDecision,
    TradeProposal,
)


def proposal_created_event(proposal: TradeProposal) -> ProposalCreatedEvent:
    return ProposalCreatedEvent(
        event_id=f"proposal.created.{proposal.proposal_id}",
        occurred_at=proposal.created_at,
        source=_event_source("proposal-store", proposal_environment(proposal)),
        payload=ProposalEventPayload(
            proposal_id=proposal.proposal_id,
            status=proposal.status,
            sleeve=proposal.sleeve,
            as_of=proposal.as_of,
            intended_trade_date=proposal.intended_trade_date,
            target_count=len(proposal.targets),
            order_count=len(proposal.orders),
            message=proposal.summary,
        ),
    )


def proposal_decision_event(
    proposal: TradeProposal,
    decision: ApprovalDecision,
) -> ProposalDecisionRecordedEvent:
    return ProposalDecisionRecordedEvent(
        event_id=f"proposal.decision.{decision.proposal_id}.{decision.decided_at.isoformat()}",
        occurred_at=decision.decided_at,
        source=_event_source("proposal-store", proposal_environment(proposal)),
        causation_id=f"proposal.created.{proposal.proposal_id}",
        payload=ProposalEventPayload(
            proposal_id=proposal.proposal_id,
            status=decision.status,
            sleeve=proposal.sleeve,
            as_of=proposal.as_of,
            intended_trade_date=proposal.intended_trade_date,
            target_count=len(proposal.targets),
            order_count=len(proposal.orders),
            message=decision.comment,
        ),
    )


def order_status_changed_event(record: BrokerOrderRecord) -> OrderStatusChangedEvent:
    return OrderStatusChangedEvent(
        event_id=f"order.status.{record.local_order_id}.{record.status.value}.{record.updated_at.isoformat()}",
        occurred_at=record.updated_at,
        source=_event_source("broker-order-store", record.environment),
        causation_id=f"proposal.created.{record.proposal_id}",
        payload=OrderLifecyclePayload(
            local_order_id=record.local_order_id,
            proposal_id=record.proposal_id,
            broker=record.broker,
            environment=record.environment,
            symbol=record.order.symbol,
            side=record.order.side,
            order_type=record.order.order_type,
            quantity=record.order.quantity,
            status=record.status,
            order_ref=record.order_ref,
            broker_order_id=record.broker_order_id,
            message=record.message,
        ),
    )


def fill_recorded_event(record: BrokerOrderRecord) -> FillRecordedEvent | None:
    if record.filled_quantity <= 0 or record.average_fill_price is None:
        return None
    return FillRecordedEvent(
        event_id=(
            f"fill.recorded.{record.local_order_id}."
            f"{record.filled_quantity}.{record.average_fill_price}.{record.updated_at.isoformat()}"
        ),
        occurred_at=record.updated_at,
        source=_event_source("broker-order-store", record.environment),
        causation_id=f"order.status.{record.local_order_id}.{record.status.value}.{record.updated_at.isoformat()}",
        payload=FillRecordedPayload(
            local_order_id=record.local_order_id,
            proposal_id=record.proposal_id,
            broker=record.broker,
            environment=record.environment,
            broker_order_id=record.broker_order_id,
            order_ref=record.order_ref,
            symbol=record.order.symbol,
            side=record.order.side,
            quantity=record.filled_quantity,
            average_price=record.average_fill_price,
            currency=record.order.currency,
            filled_at=record.updated_at,
        ),
    )


def proposal_environment(proposal: TradeProposal) -> OrderEnvironment | None:
    environments = {order.environment for order in proposal.orders}
    if len(environments) != 1:
        return None
    return next(iter(environments))


def _event_source(service: str, environment: OrderEnvironment | None = None) -> EventSource:
    return EventSource(service=service, environment=environment)
