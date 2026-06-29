from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable

from pydantic import BaseModel

from systematic_trading.domain.events import (
    EVENT_SCHEMA_VERSION,
    EVENT_SUBJECT_PREFIX,
    AlertRaisedEvent,
    FeatureComputedEvent,
    FillRecordedEvent,
    IncidentRecordedEvent,
    MarketDataRecordedEvent,
    OrderIntentCreatedEvent,
    OrderStatusChangedEvent,
    PlatformEvent,
    PlatformEventType,
    ProposalCreatedEvent,
    ProposalDecisionRecordedEvent,
    ReconciliationCompletedEvent,
)
from systematic_trading.domain.execution import BrokerOrderRecord
from systematic_trading.domain.market import FXRate, FundamentalSnapshot, Instrument, PriceBar


class SchemaKind(StrEnum):
    EVENT = "event"
    DATA = "data"
    CONFIG = "config"


class SchemaStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class CompatibilityMode(StrEnum):
    STRICT = "strict"
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class SchemaRegistryEntry:
    schema_id: str
    kind: SchemaKind
    version: int
    model: type[BaseModel]
    owner: str
    compatibility: CompatibilityMode
    status: SchemaStatus = SchemaStatus.ACTIVE
    subject: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("schema_id must not be empty")
        if self.version < 1:
            raise ValueError("schema version must be positive")

    @property
    def key(self) -> tuple[str, int]:
        return (self.schema_id, self.version)

    def json_schema(self) -> dict[str, Any]:
        return self.model.model_json_schema()

    def summary(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "kind": self.kind.value,
            "version": self.version,
            "model": f"{self.model.__module__}.{self.model.__name__}",
            "owner": self.owner,
            "compatibility": self.compatibility.value,
            "status": self.status.value,
            "subject": self.subject,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    mode: CompatibilityMode
    compatible: bool
    issues: tuple[CompatibilityIssue, ...] = field(default_factory=tuple)


class SchemaRegistry:
    def __init__(self, entries: Iterable[SchemaRegistryEntry] = ()) -> None:
        self._entries: dict[tuple[str, int], SchemaRegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: SchemaRegistryEntry) -> None:
        if entry.key in self._entries:
            schema_id, version = entry.key
            raise ValueError(f"duplicate schema registration: {schema_id} v{version}")
        self._entries[entry.key] = entry

    def get(self, schema_id: str, version: int | None = None) -> SchemaRegistryEntry:
        if version is not None:
            try:
                return self._entries[(schema_id, version)]
            except KeyError as exc:
                raise KeyError(f"schema not registered: {schema_id} v{version}") from exc
        candidates = [entry for entry in self._entries.values() if entry.schema_id == schema_id]
        if not candidates:
            raise KeyError(f"schema not registered: {schema_id}")
        return max(candidates, key=lambda entry: entry.version)

    def iter_entries(self, *, kind: SchemaKind | None = None) -> list[SchemaRegistryEntry]:
        entries = list(self._entries.values())
        if kind is not None:
            entries = [entry for entry in entries if entry.kind == kind]
        return sorted(entries, key=lambda entry: (entry.kind.value, entry.schema_id, entry.version))

    def json_schema(self, schema_id: str, version: int | None = None) -> dict[str, Any]:
        return self.get(schema_id, version).json_schema()

    def summary(self) -> list[dict[str, Any]]:
        return [entry.summary() for entry in self.iter_entries()]

    def resolve_event(self, event: PlatformEvent) -> SchemaRegistryEntry:
        schema_id = platform_event_schema_id(event.event_type)
        entry = self.get(schema_id, event.schema_version)
        if not isinstance(event, entry.model):
            raise TypeError(f"event {event.event_type.value} does not match registered model {entry.model.__name__}")
        return entry


def platform_event_schema_id(event_type: PlatformEventType | str) -> str:
    value = event_type.value if isinstance(event_type, PlatformEventType) else event_type
    return f"event.{value}"


def build_default_schema_registry() -> SchemaRegistry:
    return SchemaRegistry([*_event_schema_entries(), *_data_schema_entries()])


def check_model_compatibility(
    previous: type[BaseModel],
    candidate: type[BaseModel],
    *,
    mode: CompatibilityMode = CompatibilityMode.BACKWARD,
) -> CompatibilityReport:
    return check_schema_compatibility(previous.model_json_schema(), candidate.model_json_schema(), mode=mode)


def check_schema_compatibility(
    previous_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    *,
    mode: CompatibilityMode = CompatibilityMode.BACKWARD,
) -> CompatibilityReport:
    if mode == CompatibilityMode.NONE:
        return CompatibilityReport(mode=mode, compatible=True)

    previous_props = _properties(previous_schema)
    candidate_props = _properties(candidate_schema)
    previous_required = _required(previous_schema)
    candidate_required = _required(candidate_schema)
    issues: list[CompatibilityIssue] = []

    missing = sorted(set(previous_props) - set(candidate_props))
    for name in missing:
        issues.append(CompatibilityIssue(path=name, message="field removed from candidate schema"))

    added = sorted(set(candidate_props) - set(previous_props))
    for name in added:
        if mode in {CompatibilityMode.FORWARD, CompatibilityMode.FULL, CompatibilityMode.STRICT}:
            issues.append(CompatibilityIssue(path=name, message="field added to candidate schema"))
        elif name in candidate_required:
            issues.append(CompatibilityIssue(path=name, message="required field added to candidate schema"))

    newly_required = sorted(candidate_required - previous_required)
    for name in newly_required:
        if name in previous_props:
            issues.append(CompatibilityIssue(path=name, message="existing optional field became required"))

    no_longer_required = sorted(previous_required - candidate_required)
    if mode in {CompatibilityMode.FULL, CompatibilityMode.STRICT}:
        for name in no_longer_required:
            issues.append(CompatibilityIssue(path=name, message="required field became optional or was removed"))

    common = sorted(set(previous_props) & set(candidate_props))
    for name in common:
        previous_signature = _field_signature(previous_props[name])
        candidate_signature = _field_signature(candidate_props[name])
        if previous_signature != candidate_signature:
            issues.append(CompatibilityIssue(path=name, message="field schema changed"))

    if mode == CompatibilityMode.STRICT and previous_required != candidate_required:
        issues.append(CompatibilityIssue(path="$required", message="required field set changed"))

    return CompatibilityReport(mode=mode, compatible=not issues, issues=tuple(issues))


def _event_schema_entries() -> tuple[SchemaRegistryEntry, ...]:
    mappings: tuple[tuple[PlatformEventType, type[PlatformEvent], str], ...] = (
        (PlatformEventType.MARKET_DATA_RECORDED, MarketDataRecordedEvent, "market-data-recorder"),
        (PlatformEventType.FEATURE_COMPUTED, FeatureComputedEvent, "feature-service"),
        (PlatformEventType.PROPOSAL_CREATED, ProposalCreatedEvent, "portfolio-service"),
        (PlatformEventType.PROPOSAL_DECISION_RECORDED, ProposalDecisionRecordedEvent, "operator-api"),
        (PlatformEventType.ORDER_INTENT_CREATED, OrderIntentCreatedEvent, "order-management-service"),
        (PlatformEventType.ORDER_STATUS_CHANGED, OrderStatusChangedEvent, "order-management-service"),
        (PlatformEventType.FILL_RECORDED, FillRecordedEvent, "execution-adapter"),
        (PlatformEventType.RECONCILIATION_COMPLETED, ReconciliationCompletedEvent, "reconciliation-service"),
        (PlatformEventType.ALERT_RAISED, AlertRaisedEvent, "alert-service"),
        (PlatformEventType.INCIDENT_RECORDED, IncidentRecordedEvent, "incident-service"),
    )
    return tuple(
        SchemaRegistryEntry(
            schema_id=platform_event_schema_id(event_type),
            kind=SchemaKind.EVENT,
            version=EVENT_SCHEMA_VERSION,
            model=model,
            owner=owner,
            compatibility=CompatibilityMode.STRICT,
            subject=f"{EVENT_SUBJECT_PREFIX}.v{EVENT_SCHEMA_VERSION}.{event_type.value}",
            notes="Event subject major version matches PlatformEvent.schema_version.",
        )
        for event_type, model, owner in mappings
    )


def _data_schema_entries() -> tuple[SchemaRegistryEntry, ...]:
    return (
        SchemaRegistryEntry(
            schema_id="data.instrument",
            kind=SchemaKind.DATA,
            version=1,
            model=Instrument,
            owner="reference-data",
            compatibility=CompatibilityMode.BACKWARD,
            notes="Canonical instrument reference record.",
        ),
        SchemaRegistryEntry(
            schema_id="data.price_bar",
            kind=SchemaKind.DATA,
            version=1,
            model=PriceBar,
            owner="market-data",
            compatibility=CompatibilityMode.BACKWARD,
            notes="Canonical OHLCV bar record before columnar table-specific metadata.",
        ),
        SchemaRegistryEntry(
            schema_id="data.fx_rate",
            kind=SchemaKind.DATA,
            version=1,
            model=FXRate,
            owner="market-data",
            compatibility=CompatibilityMode.BACKWARD,
            notes="CNH-centered FX rate record.",
        ),
        SchemaRegistryEntry(
            schema_id="data.fundamental_snapshot",
            kind=SchemaKind.DATA,
            version=1,
            model=FundamentalSnapshot,
            owner="fundamentals",
            compatibility=CompatibilityMode.BACKWARD,
            notes="Point-in-time fundamental snapshot with available_date semantics.",
        ),
        SchemaRegistryEntry(
            schema_id="data.broker_order_record",
            kind=SchemaKind.DATA,
            version=1,
            model=BrokerOrderRecord,
            owner="execution",
            compatibility=CompatibilityMode.BACKWARD,
            notes="Current local broker order record contract.",
        ),
    )


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return {}
    return properties


def _required(schema: dict[str, Any]) -> set[str]:
    required = schema.get("required", [])
    if not isinstance(required, list):
        return set()
    return {str(item) for item in required}


def _field_signature(field_schema: dict[str, Any]) -> str:
    relevant = _without_descriptive_fields(field_schema)
    return json.dumps(relevant, sort_keys=True, separators=(",", ":"))


def _without_descriptive_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_descriptive_fields(item)
            for key, item in value.items()
            if key not in {"title", "description", "default", "examples"}
        }
    if isinstance(value, list):
        return [_without_descriptive_fields(item) for item in value]
    return value
