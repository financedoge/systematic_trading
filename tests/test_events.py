from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.domain.events import (
    AlertRaisedEvent,
    AlertRaisedPayload,
    EventSeverity,
    EventSource,
    FeatureComputedEvent,
    FeatureComputedPayload,
    FillRecordedEvent,
    FillRecordedPayload,
    IncidentRecordedEvent,
    IncidentStatus,
    MarketDataKind,
    MarketDataRecordedEvent,
    MarketDataRecordedPayload,
    OrderLifecyclePayload,
    OrderStatusChangedEvent,
    ProposalCreatedEvent,
    ProposalEventPayload,
    ReconciliationCompletedEvent,
    ReconciliationCompletedPayload,
    ReconciliationStatus,
    decode_platform_event,
)


def test_market_data_event_has_subject_and_round_trips_through_envelope() -> None:
    event = MarketDataRecordedEvent(
        event_id="evt-market-1",
        occurred_at=datetime(2026, 6, 27, 1, 30, tzinfo=UTC),
        source=_source("market-data-recorder"),
        correlation_id="corr-1",
        payload=MarketDataRecordedPayload(
            source_name="ib-paper",
            data_kind=MarketDataKind.BAR,
            symbol="SPY",
            currency=Currency.USD,
            trade_date="2026-06-26",
            exchange_timestamp=datetime(2026, 6, 26, 20, 0, tzinfo=UTC),
            price=Decimal("512.34"),
            volume=1000000,
            raw_ref="raw/ib/2026-06-26/SPY.jsonl",
            quality_flags=["delayed"],
        ),
    )

    payload = event.model_dump(mode="json")

    assert event.subject == "systematic_trading.events.v1.market_data.recorded"
    assert payload["schema_version"] == 1
    assert payload["payload"]["price"] == "512.34"
    decoded = decode_platform_event(event.model_dump_json())
    assert isinstance(decoded, MarketDataRecordedEvent)
    assert decoded.payload.price == Decimal("512.34")
    assert decoded.payload.quality_flags == ["delayed"]


def test_decode_platform_event_dispatches_typed_payloads_from_dict() -> None:
    decoded = decode_platform_event(
        {
            "event_id": "evt-alert-1",
            "event_type": "alert.raised",
            "schema_version": 1,
            "occurred_at": "2026-06-27T01:31:00+00:00",
            "source": {"service": "risk-service", "environment": "paper"},
            "payload": {
                "severity": "critical",
                "category": "reconciliation",
                "message": "Broker cash mismatch.",
                "details": {"currency": "USD", "delta": "10.00"},
                "linked_event_ids": ["evt-recon-1"],
            },
        }
    )

    assert isinstance(decoded, AlertRaisedEvent)
    assert decoded.source.environment == OrderEnvironment.PAPER
    assert decoded.payload.severity == EventSeverity.CRITICAL
    assert decoded.payload.details["currency"] == "USD"


def test_feature_event_records_point_in_time_metadata() -> None:
    event = FeatureComputedEvent(
        event_id="evt-feature-1",
        occurred_at=datetime(2026, 6, 27, 2, tzinfo=UTC),
        source=_source("feature-service"),
        payload=FeatureComputedPayload(
            feature_set="multi_asset_momentum",
            feature_version="1.0.0",
            as_of="2026-06-26",
            available_at=datetime(2026, 6, 27, 1, tzinfo=UTC),
            symbol="SPY",
            input_data_version="bars-v1",
            values={"momentum_63d": Decimal("0.12"), "rank": 1},
        ),
    )

    decoded = decode_platform_event(event.model_dump(mode="json"))

    assert isinstance(decoded, FeatureComputedEvent)
    assert decoded.payload.feature_version == "1.0.0"
    assert decoded.payload.values["momentum_63d"] == Decimal("0.12")


def test_proposal_order_fill_and_reconciliation_events_share_common_contract() -> None:
    proposal = ProposalCreatedEvent(
        event_id="evt-proposal-1",
        source=_source("portfolio-service"),
        occurred_at=datetime(2026, 6, 27, 3, tzinfo=UTC),
        payload=ProposalEventPayload(
            proposal_id="proposalabc1",
            status=ProposalStatus.PENDING,
            strategy_id="sota",
            strategy_version="2026.06.27",
            target_count=6,
            order_count=2,
        ),
    )
    order = OrderStatusChangedEvent(
        event_id="evt-order-1",
        source=_source("oms"),
        occurred_at=datetime(2026, 6, 27, 3, 1, tzinfo=UTC),
        causation_id=proposal.event_id,
        payload=OrderLifecyclePayload(
            local_order_id="local1",
            proposal_id="proposalabc1",
            environment=OrderEnvironment.PAPER,
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.TWAP,
            quantity=10,
            status=BrokerOrderStatus.SUBMITTED,
            order_ref="st-proposalabc1-0",
            broker_order_id=100,
        ),
    )
    fill = FillRecordedEvent(
        event_id="evt-fill-1",
        source=_source("ib-execution-adapter"),
        occurred_at=datetime(2026, 6, 27, 3, 2, tzinfo=UTC),
        causation_id=order.event_id,
        payload=FillRecordedPayload(
            local_order_id="local1",
            proposal_id="proposalabc1",
            environment=OrderEnvironment.PAPER,
            broker_order_id=100,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            average_price=Decimal("512.50"),
            currency=Currency.USD,
            commission=Decimal("1.00"),
            commission_currency=Currency.USD,
        ),
    )
    reconciliation = ReconciliationCompletedEvent(
        event_id="evt-recon-1",
        source=_source("reconciliation-service"),
        occurred_at=datetime(2026, 6, 27, 3, 3, tzinfo=UTC),
        payload=ReconciliationCompletedPayload(
            environment=OrderEnvironment.PAPER,
            scope="orders",
            status=ReconciliationStatus.OK,
            checked_counts={"orders": 1, "fills": 1},
        ),
    )

    decoded = [decode_platform_event(item.model_dump(mode="json")) for item in [proposal, order, fill, reconciliation]]

    assert [item.subject for item in decoded] == [
        "systematic_trading.events.v1.proposal.created",
        "systematic_trading.events.v1.order.status_changed",
        "systematic_trading.events.v1.fill.recorded",
        "systematic_trading.events.v1.reconciliation.completed",
    ]
    assert decoded[2].payload.average_price == Decimal("512.50")
    assert decoded[3].payload.checked_counts == {"orders": 1, "fills": 1}


def test_event_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        MarketDataRecordedEvent(
            event_id="evt-naive",
            occurred_at=datetime(2026, 6, 27, 1, 30),
            source=_source("market-data-recorder"),
            payload=MarketDataRecordedPayload(
                source_name="ib-paper",
                data_kind=MarketDataKind.TRADE,
                symbol="SPY",
                price=Decimal("512.34"),
            ),
        )


def test_trading_event_quantities_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        OrderLifecyclePayload(
            local_order_id="local1",
            proposal_id="proposalabc1",
            environment=OrderEnvironment.PAPER,
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.TWAP,
            quantity=0,
            status=BrokerOrderStatus.SUBMITTED,
        )
    with pytest.raises(ValidationError):
        FillRecordedPayload(
            environment=OrderEnvironment.PAPER,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=0,
            average_price=Decimal("512.50"),
            currency=Currency.USD,
        )


def test_incident_event_forbids_uncontracted_fields() -> None:
    with pytest.raises(ValidationError):
        IncidentRecordedEvent(
            event_id="evt-incident-1",
            source=_source("ops"),
            occurred_at=datetime(2026, 6, 27, 4, tzinfo=UTC),
            payload={
                "status": IncidentStatus.OPEN,
                "severity": EventSeverity.ERROR,
                "summary": "Queue lag breached threshold.",
                "unexpected": "not allowed",
            },
        )


def _source(service: str) -> EventSource:
    return EventSource(service=service, environment=OrderEnvironment.PAPER)
