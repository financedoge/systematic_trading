from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict

from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.events import (
    EVENT_SCHEMA_VERSION,
    MarketDataKind,
    MarketDataRecordedEvent,
    MarketDataRecordedPayload,
    PlatformEventType,
)
from systematic_trading.schemas import (
    CompatibilityMode,
    SchemaKind,
    SchemaRegistry,
    SchemaRegistryEntry,
    build_default_schema_registry,
    check_model_compatibility,
    platform_event_schema_id,
)


def test_default_schema_registry_registers_event_and_data_contracts() -> None:
    registry = build_default_schema_registry()

    event_entries = registry.iter_entries(kind=SchemaKind.EVENT)
    data_entries = registry.iter_entries(kind=SchemaKind.DATA)
    market_data_entry = registry.get(platform_event_schema_id(PlatformEventType.MARKET_DATA_RECORDED), 1)

    assert len(event_entries) == len(PlatformEventType)
    assert {entry.schema_id for entry in data_entries} >= {
        "data.instrument",
        "data.price_bar",
        "data.fx_rate",
        "data.fundamental_snapshot",
    }
    assert market_data_entry.model is MarketDataRecordedEvent
    assert market_data_entry.version == EVENT_SCHEMA_VERSION
    assert market_data_entry.subject == "systematic_trading.events.v1.market_data.recorded"
    assert "payload" in market_data_entry.json_schema()["properties"]


def test_schema_registry_rejects_duplicate_schema_versions() -> None:
    class Example(BaseModel):
        value: str

    entry = SchemaRegistryEntry(
        schema_id="data.example",
        kind=SchemaKind.DATA,
        version=1,
        model=Example,
        owner="test",
        compatibility=CompatibilityMode.BACKWARD,
    )
    registry = SchemaRegistry([entry])

    with pytest.raises(ValueError, match="duplicate schema registration"):
        registry.register(entry)


def test_schema_registry_resolves_runtime_event_instances() -> None:
    registry = build_default_schema_registry()
    event = MarketDataRecordedEvent(
        event_id="evt-registry-1",
        occurred_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
        source={"service": "market-data-recorder", "environment": OrderEnvironment.PAPER},
        payload=MarketDataRecordedPayload(
            source_name="ib-paper",
            data_kind=MarketDataKind.BAR,
            symbol="SPY",
            currency=Currency.USD,
            price=Decimal("512.34"),
        ),
    )

    entry = registry.resolve_event(event)

    assert entry.schema_id == "event.market_data.recorded"
    assert entry.model is MarketDataRecordedEvent


def test_schema_registry_rejects_unregistered_event_version() -> None:
    registry = build_default_schema_registry()
    event = MarketDataRecordedEvent(
        event_id="evt-registry-2",
        schema_version=99,
        occurred_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
        source={"service": "market-data-recorder", "environment": OrderEnvironment.PAPER},
        payload=MarketDataRecordedPayload(
            source_name="ib-paper",
            data_kind=MarketDataKind.BAR,
            symbol="SPY",
            price=Decimal("512.34"),
        ),
    )

    with pytest.raises(KeyError, match="schema not registered"):
        registry.resolve_event(event)


def test_backward_compatibility_allows_optional_additions() -> None:
    class Previous(BaseModel):
        model_config = ConfigDict(extra="forbid")

        symbol: str
        price: float

    class Candidate(BaseModel):
        model_config = ConfigDict(extra="forbid")

        symbol: str
        price: float
        source: str | None = None

    report = check_model_compatibility(Previous, Candidate, mode=CompatibilityMode.BACKWARD)

    assert report.compatible
    assert report.issues == ()


def test_backward_compatibility_rejects_required_additions_and_type_changes() -> None:
    class Previous(BaseModel):
        model_config = ConfigDict(extra="forbid")

        symbol: str
        price: float

    class Candidate(BaseModel):
        model_config = ConfigDict(extra="forbid")

        symbol: str
        price: str
        source: str

    report = check_model_compatibility(Previous, Candidate, mode=CompatibilityMode.BACKWARD)

    assert not report.compatible
    assert {issue.path for issue in report.issues} == {"price", "source"}


def test_full_compatibility_rejects_optional_additions() -> None:
    class Previous(BaseModel):
        value: str

    class Candidate(BaseModel):
        value: str
        note: str | None = None

    report = check_model_compatibility(Previous, Candidate, mode=CompatibilityMode.FULL)

    assert not report.compatible
    assert report.issues[0].path == "note"
