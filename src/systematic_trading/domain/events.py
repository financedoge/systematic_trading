from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)

EVENT_SCHEMA_VERSION = 1
EVENT_SUBJECT_PREFIX = "systematic_trading.events"


class PlatformEventType(StrEnum):
    MARKET_DATA_RECORDED = "market_data.recorded"
    FEATURE_COMPUTED = "feature.computed"
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_DECISION_RECORDED = "proposal.decision_recorded"
    ORDER_INTENT_CREATED = "order.intent_created"
    ORDER_STATUS_CHANGED = "order.status_changed"
    FILL_RECORDED = "fill.recorded"
    RECONCILIATION_COMPLETED = "reconciliation.completed"
    ALERT_RAISED = "alert.raised"
    INCIDENT_RECORDED = "incident.recorded"


class MarketDataKind(StrEnum):
    TRADE = "trade"
    QUOTE = "quote"
    BAR = "bar"
    ORDER_BOOK = "order_book"
    FX = "fx"
    BROKER_STATUS = "broker_status"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReconciliationStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


JSONScalar: TypeAlias = str | int | float | bool | None
FeatureValue: TypeAlias = Decimal | JSONScalar


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EventSource(EventModel):
    service: str = Field(min_length=1)
    instance: str | None = None
    environment: OrderEnvironment | None = None


class MarketDataRecordedPayload(EventModel):
    source_name: str = Field(min_length=1)
    data_kind: MarketDataKind
    symbol: str | None = None
    currency: Currency | None = None
    trade_date: date | None = None
    exchange_timestamp: datetime | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    price: Decimal | None = Field(default=None, gt=0)
    bid: Decimal | None = Field(default=None, gt=0)
    ask: Decimal | None = Field(default=None, gt=0)
    volume: int | None = Field(default=None, ge=0)
    source_sequence: str | None = None
    raw_ref: str | None = None
    normalized_ref: str | None = None
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("exchange_timestamp", "received_at")
    @classmethod
    def _timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _to_utc(value)


class FeatureComputedPayload(EventModel):
    feature_set: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    as_of: date
    available_at: datetime
    symbol: str | None = None
    universe_id: str | None = None
    input_data_version: str | None = None
    values: dict[str, FeatureValue] = Field(default_factory=dict)

    @field_validator("values", mode="before")
    @classmethod
    def _restore_decimal_values(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        return {key: _feature_value(item) for key, item in value.items()}

    @field_validator("available_at")
    @classmethod
    def _available_at_must_be_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)


class ProposalEventPayload(EventModel):
    proposal_id: str = Field(min_length=1)
    status: ProposalStatus
    strategy_id: str | None = None
    strategy_version: str | None = None
    sleeve: str | None = None
    as_of: date | None = None
    intended_trade_date: date | None = None
    target_count: int = Field(default=0, ge=0)
    order_count: int = Field(default=0, ge=0)
    artifact_ref: str | None = None
    message: str | None = None


class OrderLifecyclePayload(EventModel):
    local_order_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    broker: str = Field(default="interactive-brokers", min_length=1)
    environment: OrderEnvironment
    symbol: str = Field(min_length=1)
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(ge=1)
    status: BrokerOrderStatus
    order_ref: str | None = None
    broker_order_id: int | None = None
    message: str | None = None


class FillRecordedPayload(EventModel):
    local_order_id: str | None = None
    proposal_id: str | None = None
    broker: str = Field(default="interactive-brokers", min_length=1)
    environment: OrderEnvironment
    broker_order_id: int | None = None
    order_ref: str | None = None
    symbol: str = Field(min_length=1)
    side: OrderSide
    quantity: int = Field(ge=1)
    average_price: Decimal = Field(gt=0)
    currency: Currency
    filled_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    commission: Decimal | None = Field(default=None, ge=0)
    commission_currency: Currency | None = None

    @field_validator("filled_at")
    @classmethod
    def _filled_at_must_be_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)


class ReconciliationCompletedPayload(EventModel):
    broker: str = Field(default="interactive-brokers", min_length=1)
    environment: OrderEnvironment
    scope: str = Field(min_length=1)
    status: ReconciliationStatus
    reconciled_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    checked_counts: dict[str, int] = Field(default_factory=dict)
    breaks: list[str] = Field(default_factory=list)
    message: str | None = None

    @field_validator("reconciled_at")
    @classmethod
    def _reconciled_at_must_be_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)


class AlertRaisedPayload(EventModel):
    alert_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    severity: EventSeverity
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    linked_event_ids: list[str] = Field(default_factory=list)


class IncidentRecordedPayload(EventModel):
    incident_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    status: IncidentStatus
    severity: EventSeverity
    summary: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    linked_event_ids: list[str] = Field(default_factory=list)
    resolved_at: datetime | None = None

    @field_validator("resolved_at")
    @classmethod
    def _resolved_at_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _to_utc(value)


class PlatformEvent(EventModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: PlatformEventType
    schema_version: int = Field(default=EVENT_SCHEMA_VERSION, ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source: EventSource
    correlation_id: str | None = None
    causation_id: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_must_be_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)

    @property
    def subject(self) -> str:
        return event_subject(self)


class MarketDataRecordedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.MARKET_DATA_RECORDED] = PlatformEventType.MARKET_DATA_RECORDED
    payload: MarketDataRecordedPayload


class FeatureComputedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.FEATURE_COMPUTED] = PlatformEventType.FEATURE_COMPUTED
    payload: FeatureComputedPayload


class ProposalCreatedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.PROPOSAL_CREATED] = PlatformEventType.PROPOSAL_CREATED
    payload: ProposalEventPayload


class ProposalDecisionRecordedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.PROPOSAL_DECISION_RECORDED] = PlatformEventType.PROPOSAL_DECISION_RECORDED
    payload: ProposalEventPayload


class OrderIntentCreatedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.ORDER_INTENT_CREATED] = PlatformEventType.ORDER_INTENT_CREATED
    payload: OrderLifecyclePayload


class OrderStatusChangedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.ORDER_STATUS_CHANGED] = PlatformEventType.ORDER_STATUS_CHANGED
    payload: OrderLifecyclePayload


class FillRecordedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.FILL_RECORDED] = PlatformEventType.FILL_RECORDED
    payload: FillRecordedPayload


class ReconciliationCompletedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.RECONCILIATION_COMPLETED] = PlatformEventType.RECONCILIATION_COMPLETED
    payload: ReconciliationCompletedPayload


class AlertRaisedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.ALERT_RAISED] = PlatformEventType.ALERT_RAISED
    payload: AlertRaisedPayload


class IncidentRecordedEvent(PlatformEvent):
    event_type: Literal[PlatformEventType.INCIDENT_RECORDED] = PlatformEventType.INCIDENT_RECORDED
    payload: IncidentRecordedPayload


AnyPlatformEvent: TypeAlias = Annotated[
    MarketDataRecordedEvent
    | FeatureComputedEvent
    | ProposalCreatedEvent
    | ProposalDecisionRecordedEvent
    | OrderIntentCreatedEvent
    | OrderStatusChangedEvent
    | FillRecordedEvent
    | ReconciliationCompletedEvent
    | AlertRaisedEvent
    | IncidentRecordedEvent,
    Field(discriminator="event_type"),
]


class PlatformEventOutboxRecord(EventModel):
    event_id: str
    event_type: PlatformEventType
    subject: str
    payload: AnyPlatformEvent
    occurred_at: datetime
    created_at: datetime
    published_at: datetime | None = None
    publish_attempts: int = Field(default=0, ge=0)
    last_error: str | None = None

    @field_validator("occurred_at", "created_at", "published_at")
    @classmethod
    def _timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _to_utc(value)


_PLATFORM_EVENT_ADAPTER = TypeAdapter(AnyPlatformEvent)


def decode_platform_event(payload: str | bytes | dict[str, Any]) -> AnyPlatformEvent:
    if isinstance(payload, str | bytes):
        return _PLATFORM_EVENT_ADAPTER.validate_json(payload)
    return _PLATFORM_EVENT_ADAPTER.validate_python(payload)


def event_subject(event: PlatformEvent) -> str:
    return f"{EVENT_SUBJECT_PREFIX}.v{event.schema_version}.{event.event_type.value}"


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _feature_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return value
    if not decimal_value.is_finite():
        return value
    return decimal_value
