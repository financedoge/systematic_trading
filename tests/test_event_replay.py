import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from scripts.replay_platform_events import replay_once
from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.events import (
    EventSource,
    MarketDataKind,
    MarketDataRecordedEvent,
    MarketDataRecordedPayload,
    PlatformEventType,
)
from systematic_trading.messaging import (
    EventOutboxDispatcher,
    EventReplayError,
    EventReplaySource,
    JsonlPlatformEventPublisher,
    replay_jsonl_platform_events,
    replay_outbox_platform_events,
    summarize_replayed_events,
)
from systematic_trading.storage.sqlite import SQLiteStore


def test_replay_jsonl_platform_events_round_trips_typed_events(tmp_path) -> None:
    store = _store(tmp_path)
    store.append_platform_event(_market_event("evt-001", "SPY"))
    output_path = tmp_path / "platform_events.jsonl"
    EventOutboxDispatcher(store, JsonlPlatformEventPublisher(output_path)).dispatch_pending()

    events = replay_jsonl_platform_events(output_path)
    summary = summarize_replayed_events(events)

    assert len(events) == 1
    assert events[0].source == EventReplaySource.JSONL
    assert events[0].event.event_id == "evt-001"
    assert events[0].event.payload.symbol == "SPY"
    assert events[0].published_at is not None
    assert summary.total == 1
    assert summary.by_event_type == {"market_data.recorded": 1}


def test_replay_outbox_platform_events_filters_published_and_event_type(tmp_path) -> None:
    store = _store(tmp_path)
    store.append_platform_event(_market_event("evt-001", "SPY"))
    store.append_platform_event(_market_event("evt-002", "TLT"))
    store.mark_platform_event_published("evt-001", published_at=datetime(2026, 6, 27, 9, 30, tzinfo=UTC))

    published = replay_outbox_platform_events(
        store,
        published=True,
        event_type=PlatformEventType.MARKET_DATA_RECORDED,
    )
    pending = replay_outbox_platform_events(store, published=False)

    assert [event.event.event_id for event in published] == ["evt-001"]
    assert published[0].publish_attempts == 1
    assert [event.event.event_id for event in pending] == ["evt-002"]
    assert pending[0].published_at is None


def test_replay_jsonl_platform_events_reports_bad_lines(tmp_path) -> None:
    path = tmp_path / "bad_events.jsonl"
    path.write_text(json.dumps({"subject": "missing-event"}) + "\n", encoding="utf-8")

    with pytest.raises(EventReplayError, match="bad_events.jsonl:1"):
        replay_jsonl_platform_events(path)


def test_replay_platform_events_script_replays_outbox_source(tmp_path) -> None:
    database_path = tmp_path / "events.db"
    store = SQLiteStore(database_path)
    store.initialize()
    store.append_platform_event(_market_event("evt-001", "SPY"))

    events = replay_once(
        source="outbox",
        jsonl_path=tmp_path / "unused.jsonl",
        database_path=database_path,
        limit=10,
        event_type=PlatformEventType.MARKET_DATA_RECORDED,
        published=None,
    )

    assert len(events) == 1
    assert events[0].source == EventReplaySource.OUTBOX
    assert events[0].event.event_id == "evt-001"


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
        ),
    )
