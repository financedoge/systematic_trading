import json
from datetime import UTC, date, datetime
from decimal import Decimal

from scripts.dispatch_event_outbox import dispatch_once
from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.domain.execution import (
    ApprovalDecision,
    BrokerOrderRecord,
    OrderRequest,
    ProposalReasoning,
    TradeProposal,
)
from systematic_trading.domain.events import (
    EventSource,
    FillRecordedEvent,
    MarketDataKind,
    MarketDataRecordedEvent,
    MarketDataRecordedPayload,
    OrderStatusChangedEvent,
    ProposalCreatedEvent,
    ProposalDecisionRecordedEvent,
)
from systematic_trading.messaging import EventOutboxDispatcher, InMemoryPlatformEventPublisher, JsonlPlatformEventPublisher
from systematic_trading.storage.sqlite import SQLiteStore


def test_sqlite_event_outbox_appends_event_idempotently(tmp_path) -> None:
    store = _store(tmp_path)
    event = _market_event("evt-001", "SPY")

    first = store.append_platform_event(event)
    second = store.append_platform_event(event)

    pending = store.list_pending_platform_events()
    assert first.event_id == "evt-001"
    assert second.event_id == "evt-001"
    assert len(pending) == 1
    assert pending[0].payload.event_id == event.event_id
    assert pending[0].subject == "systematic_trading.events.v1.market_data.recorded"
    assert pending[0].publish_attempts == 0


def test_sqlite_event_outbox_lists_pending_events_in_append_order_and_respects_limit(tmp_path) -> None:
    store = _store(tmp_path)
    for index, symbol in enumerate(["SPY", "TLT", "GLD"], start=1):
        store.append_platform_event(_market_event(f"evt-00{index}", symbol))

    pending = store.list_pending_platform_events(limit=2)

    assert [record.event_id for record in pending] == ["evt-001", "evt-002"]
    assert [record.payload.payload.symbol for record in pending] == ["SPY", "TLT"]


def test_sqlite_event_outbox_marks_event_published_idempotently(tmp_path) -> None:
    store = _store(tmp_path)
    event = _market_event("evt-001", "SPY")
    store.append_platform_event(event)
    published_at = datetime(2026, 6, 27, 9, 30, tzinfo=UTC)

    published = store.mark_platform_event_published(event.event_id, published_at=published_at)
    second = store.mark_platform_event_published(event.event_id, published_at=datetime(2026, 6, 27, 9, 31, tzinfo=UTC))

    assert published is not None
    assert published.published_at == published_at
    assert published.publish_attempts == 1
    assert second is not None
    assert second.published_at == published_at
    assert second.publish_attempts == 1
    assert store.list_pending_platform_events() == []


def test_event_outbox_dispatcher_records_failure_and_retries_pending_event(tmp_path) -> None:
    store = _store(tmp_path)
    store.append_platform_event(_market_event("evt-001", "SPY"))
    store.append_platform_event(_market_event("evt-002", "TLT"))
    publisher = _FlakyPublisher(fail_first_for={"evt-002"})
    dispatcher = EventOutboxDispatcher(store, publisher)

    first = dispatcher.dispatch_pending()

    assert first.attempted == 2
    assert first.published == 1
    assert first.failed == 1
    assert first.failures[0].event_id == "evt-002"
    failed_record = store.get_platform_event_outbox_record("evt-002")
    assert failed_record is not None
    assert failed_record.publish_attempts == 1
    assert "RuntimeError: simulated publish failure" in failed_record.last_error
    assert [record.event_id for record in store.list_pending_platform_events()] == ["evt-002"]

    second = dispatcher.dispatch_pending()

    assert second.attempted == 1
    assert second.published == 1
    assert second.failed == 0
    retried_record = store.get_platform_event_outbox_record("evt-002")
    assert retried_record is not None
    assert retried_record.publish_attempts == 2
    assert retried_record.last_error is None
    assert retried_record.published_at is not None
    assert store.list_pending_platform_events() == []
    assert publisher.calls == ["evt-001", "evt-002", "evt-002"]


def test_event_outbox_dispatcher_uses_in_memory_publisher_for_successful_batch(tmp_path) -> None:
    store = _store(tmp_path)
    store.append_platform_event(_market_event("evt-001", "SPY"))
    publisher = InMemoryPlatformEventPublisher()
    dispatcher = EventOutboxDispatcher(store, publisher)

    result = dispatcher.dispatch_pending()

    assert result.attempted == 1
    assert result.published == 1
    assert result.failed == 0
    assert publisher.published[0].subject == "systematic_trading.events.v1.market_data.recorded"
    assert publisher.published[0].event.event_id == "evt-001"


def test_jsonl_publisher_writes_dispatched_event_payloads(tmp_path) -> None:
    store = _store(tmp_path)
    store.append_platform_event(_market_event("evt-001", "SPY"))
    output_path = tmp_path / "events" / "platform_events.jsonl"
    dispatcher = EventOutboxDispatcher(store, JsonlPlatformEventPublisher(output_path))

    result = dispatcher.dispatch_pending()

    assert result.published == 1
    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["subject"] == "systematic_trading.events.v1.market_data.recorded"
    assert payload["event"]["event_id"] == "evt-001"
    assert payload["event"]["payload"]["symbol"] == "SPY"
    assert store.list_pending_platform_events() == []


def test_dispatch_event_outbox_script_dispatches_once_to_jsonl(tmp_path) -> None:
    database_path = tmp_path / "script_events.db"
    store = SQLiteStore(database_path)
    store.initialize()
    store.append_platform_event(_market_event("evt-001", "SPY"))
    output_path = tmp_path / "script_events.jsonl"

    result = dispatch_once(database_path=database_path, output_path=output_path, limit=10)

    assert result.attempted == 1
    assert result.published == 1
    payload = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"]["event_id"] == "evt-001"


def test_proposal_save_and_decision_emit_outbox_events(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal()
    store.save_proposal(proposal)
    store.save_proposal(proposal)

    decision = ApprovalDecision(
        proposal_id=proposal.proposal_id,
        status=ProposalStatus.APPROVED,
        decided_at=datetime(2026, 6, 27, 2, 0, tzinfo=UTC),
        comment="Approved for paper.",
    )
    store.apply_decision(decision)

    pending = store.list_pending_platform_events()

    assert len(pending) == 2
    assert isinstance(pending[0].payload, ProposalCreatedEvent)
    assert pending[0].event_id == "proposal.created.proposalabc1"
    assert pending[0].payload.payload.order_count == 1
    assert pending[0].payload.payload.status == ProposalStatus.PENDING
    assert isinstance(pending[1].payload, ProposalDecisionRecordedEvent)
    assert pending[1].payload.payload.status == ProposalStatus.APPROVED
    assert pending[1].payload.payload.message == "Approved for paper."


def test_broker_order_record_save_emits_order_status_and_fill_events(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal()
    store.save_proposal(proposal)
    submitted = _broker_record(
        proposal,
        status=BrokerOrderStatus.SUBMITTED,
        updated_at=datetime(2026, 6, 27, 3, 0, tzinfo=UTC),
    )
    store.save_broker_order_record(submitted)
    filled = submitted.model_copy(
        update={
            "status": BrokerOrderStatus.FILLED,
            "filled_quantity": 10,
            "remaining_quantity": 0,
            "average_fill_price": Decimal("512.50"),
            "updated_at": datetime(2026, 6, 27, 3, 5, tzinfo=UTC),
        }
    )
    store.save_broker_order_record(filled)
    store.save_broker_order_record(filled)

    pending = store.list_pending_platform_events()
    order_events = [record.payload for record in pending if isinstance(record.payload, OrderStatusChangedEvent)]
    fill_events = [record.payload for record in pending if isinstance(record.payload, FillRecordedEvent)]

    assert len(order_events) == 2
    assert [event.payload.status for event in order_events] == [BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.FILLED]
    assert len(fill_events) == 1
    assert fill_events[0].payload.quantity == 10
    assert fill_events[0].payload.average_price == Decimal("512.50")
    assert fill_events[0].causation_id.startswith(f"order.status.{submitted.local_order_id}.filled")


def _store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "events.db")
    store.initialize()
    return store


def _market_event(event_id: str, symbol: str) -> MarketDataRecordedEvent:
    return MarketDataRecordedEvent(
        event_id=event_id,
        occurred_at=datetime(2026, 6, 27, 1, 30, tzinfo=UTC),
        source=EventSource(service="market-data-recorder", environment=OrderEnvironment.PAPER),
        payload=MarketDataRecordedPayload(
            source_name="ib-paper",
            data_kind=MarketDataKind.BAR,
            symbol=symbol,
            currency=Currency.USD,
            trade_date="2026-06-26",
            price=Decimal("512.34"),
            raw_ref=f"raw/ib/2026-06-26/{symbol}.jsonl",
        ),
    )


def _proposal() -> TradeProposal:
    return TradeProposal(
        proposal_id="proposalabc1",
        created_at=datetime(2026, 6, 27, 1, 45, tzinfo=UTC),
        as_of=date(2026, 6, 26),
        sleeve="sota",
        summary="test proposal",
        orders=[_order()],
        reasoning=ProposalReasoning(summary="test"),
    )


def _order() -> OrderRequest:
    return OrderRequest(
        symbol="SPY",
        side=OrderSide.BUY,
        order_type=OrderType.TWAP,
        quantity=10,
        reference_price=Decimal("512.34"),
        currency=Currency.USD,
        environment=OrderEnvironment.PAPER,
        notional_cnh=Decimal("36888.48"),
        rationale="test order",
    )


def _broker_record(
    proposal: TradeProposal,
    *,
    status: BrokerOrderStatus,
    updated_at: datetime,
) -> BrokerOrderRecord:
    return BrokerOrderRecord(
        local_order_id="localorder1",
        proposal_id=proposal.proposal_id,
        environment=OrderEnvironment.PAPER,
        order_index=0,
        order=proposal.orders[0],
        order_ref="st-proposalabc1-00",
        broker_order_id=100,
        status=status,
        submitted_at=datetime(2026, 6, 27, 3, 0, tzinfo=UTC),
        updated_at=updated_at,
        remaining_quantity=10,
    )


class _FlakyPublisher:
    def __init__(self, *, fail_first_for: set[str]) -> None:
        self.fail_first_for = fail_first_for
        self.failed: set[str] = set()
        self.calls: list[str] = []

    def publish(self, event, *, subject: str) -> None:
        self.calls.append(event.event_id)
        if event.event_id in self.fail_first_for and event.event_id not in self.failed:
            self.failed.add(event.event_id)
            raise RuntimeError("simulated publish failure")
