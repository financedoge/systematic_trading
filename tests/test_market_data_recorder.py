import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.recorders import (
    CapturedMarketDataBar,
    IBMarketDataMode,
    MarketDataRecorder,
    RawDataCatalog,
    RawMarketDataWriter,
    TokenBucket,
    dry_run_raw_replay,
    load_recorder_source_policy,
    rebuild_raw_catalog,
    query_raw_catalog,
)
from systematic_trading.services import OperationalLogger


def test_recorder_writes_raw_before_appending_event_and_state(tmp_path) -> None:
    store = _AssertingEventStore()
    state_path = tmp_path / "run" / "market_data_recorder.state.json"
    writer = RawMarketDataWriter(tmp_path / "hot", part_id="test", fsync=False)
    catalog = RawDataCatalog(tmp_path / "hot", fsync=False)
    recorder = MarketDataRecorder(
        writer=writer,
        catalog=catalog,
        event_store=store,
        state_path=state_path,
        started_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
    )

    event = recorder.record_bar(_bar())

    assert event.event_id.startswith("market_data.recorded.raw_")
    assert event.payload.symbol == "SPY"
    assert event.payload.price == Decimal("512.34")
    assert event.payload.raw_ref is not None
    raw_path = Path(event.payload.raw_ref.split("#offset=")[0])
    raw_payload = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0])
    assert raw_payload["raw_event_id"] in event.event_id
    assert "raw_ref" not in raw_payload
    assert raw_payload["payload_hash"].startswith("sha256:")
    assert store.appended_event_ids == [event.event_id]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["service_id"] == "market_data_recorder"
    assert state["details"]["records_written"] == 1
    assert state["details"]["catalog_entries_appended"] == 1
    assert state["details"]["events_appended"] == 1
    assert state["details"]["symbols_active"] == ["SPY"]
    assert state["details"]["last_catalog_ref"].endswith(".jsonl#offset=0")
    catalog_query = query_raw_catalog(
        tmp_path / "hot",
        source="interactive-brokers",
        environment="paper",
        data_kind="bar",
        symbol="SPY",
        day=datetime(2026, 6, 27, tzinfo=UTC).date(),
        raw_schema_version=1,
    )
    assert len(catalog_query.entries) == 1
    assert catalog_query.entries[0].raw_ref == event.payload.raw_ref
    assert catalog_query.entries[0].raw_schema_version == 1


def test_recorder_writes_operational_log_events(tmp_path) -> None:
    operation_log = tmp_path / "log" / "platform_operations.jsonl"
    recorder = MarketDataRecorder(
        writer=RawMarketDataWriter(tmp_path / "hot", part_id="test", fsync=False),
        state_path=tmp_path / "run" / "state.json",
        started_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
        operation_logger=OperationalLogger(path=operation_log, service_id="market_data_recorder"),
        log_every_records=1,
    )

    event = recorder.record_bar(_bar())
    recorder.note_error(420, "No market data permissions")
    recorder.note_disconnect()

    rows = [json.loads(line) for line in operation_log.read_text(encoding="utf-8").splitlines()]
    events = [row["event"] for row in rows]
    assert events[:2] == ["recorder_initialized", "market_data_bar_recorded"]
    assert "recorder_error" in events
    assert "recorder_disconnected" in events
    bar_row = next(row for row in rows if row["event"] == "market_data_bar_recorded")
    assert bar_row["details"]["event_id"] == event.event_id
    assert bar_row["details"]["raw_ref"].endswith(".jsonl#offset=0")


def test_recorder_source_policy_loads_seed_and_enforces_line_budget() -> None:
    policy = load_recorder_source_policy()

    assert len(policy.seed_symbols) == 40
    assert len(set(policy.seed_symbols)) == 40
    assert policy.estimated_line_usage(policy.seed_symbols) == 40
    policy.validate_line_budget(policy.seed_symbols)
    with pytest.raises(ValueError, match="market-data lines"):
        policy.validate_line_budget([f"S{i}" for i in range(81)])


def test_raw_replay_dry_run_validates_hashes_and_detects_duplicates(tmp_path) -> None:
    writer = RawMarketDataWriter(tmp_path / "hot", part_id="test", fsync=False)
    recorder = MarketDataRecorder(
        writer=writer,
        state_path=tmp_path / "run" / "state.json",
        started_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
    )
    recorder.record_bar(_bar())
    recorder.record_bar(_bar())

    summary = dry_run_raw_replay(
        tmp_path / "hot",
        source="interactive-brokers",
        environment="paper",
        data_kind="bar",
        day=datetime(2026, 6, 27, tzinfo=UTC).date(),
        symbol="SPY",
    )

    assert summary.files_seen == 1
    assert summary.records_read == 2
    assert summary.records_valid == 2
    assert summary.payload_hash_mismatches == 0
    assert summary.duplicate_raw_event_ids == 1


def test_rebuild_raw_catalog_discovers_existing_raw_files(tmp_path) -> None:
    writer = RawMarketDataWriter(tmp_path / "hot", part_id="legacy", fsync=False)
    recorder = MarketDataRecorder(
        writer=writer,
        state_path=tmp_path / "run" / "state.json",
        started_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
    )
    event = recorder.record_bar(_bar())

    before = query_raw_catalog(tmp_path / "hot", day=datetime(2026, 6, 27, tzinfo=UTC).date(), symbol="SPY")
    assert before.entries == []

    rebuild = rebuild_raw_catalog(
        tmp_path / "hot",
        source="interactive-brokers",
        environment="paper",
        data_kind="bar",
        day=datetime(2026, 6, 27, tzinfo=UTC).date(),
        symbol="SPY",
    )
    after = query_raw_catalog(
        tmp_path / "hot",
        source="interactive-brokers",
        environment="paper",
        data_kind="bar",
        day=datetime(2026, 6, 27, tzinfo=UTC).date(),
        symbol="SPY",
    )

    assert rebuild.files_seen == 1
    assert rebuild.entries_written == 1
    assert len(after.entries) == 1
    assert after.entries[0].raw_ref == event.payload.raw_ref
    assert after.entries[0].raw_path.endswith("part-legacy.jsonl")


def test_token_bucket_records_sleep_when_empty() -> None:
    now = [0.0]
    sleeps = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    bucket = TokenBucket(rate_per_second=1.0, burst=1, sleep=sleep, monotonic=lambda: now[0])

    assert bucket.consume() == 0
    assert bucket.consume() == pytest.approx(1.0)
    assert sleeps == [pytest.approx(1.0)]
    assert bucket.sleep_count == 1


def _bar() -> CapturedMarketDataBar:
    return CapturedMarketDataBar(
        environment=OrderEnvironment.PAPER,
        symbol="SPY",
        request_id=94001,
        exchange_timestamp=datetime(2026, 6, 27, 13, 30, tzinfo=UTC),
        received_at=datetime(2026, 6, 27, 13, 30, 5, tzinfo=UTC),
        market_data_mode=IBMarketDataMode.DELAYED,
        source_sequence="SPY:20260627T133000Z",
        open=Decimal("512.10"),
        high=Decimal("513.00"),
        low=Decimal("511.80"),
        close=Decimal("512.34"),
        volume=1000,
        wap=Decimal("512.50"),
        count=42,
    )


class _AssertingEventStore:
    def __init__(self) -> None:
        self.appended_event_ids = []

    def append_platform_event(self, event):
        assert event.payload.raw_ref is not None
        raw_path = Path(event.payload.raw_ref.split("#offset=")[0])
        assert raw_path.exists()
        self.appended_event_ids.append(event.event_id)
        return None
