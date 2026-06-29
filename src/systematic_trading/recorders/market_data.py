from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.events import (
    EventSource,
    MarketDataKind,
    MarketDataRecordedEvent,
    MarketDataRecordedPayload,
)
from systematic_trading.services import OperationalLogger, write_service_state_file
from systematic_trading.storage.interfaces import PlatformEventAppendStore


SERVICE_ID = "market_data_recorder"
DEFAULT_SOURCE_NAME = "interactive-brokers"
DEFAULT_INSTANCE_ID = "local-windows"


class IBMarketDataMode(StrEnum):
    LIVE = "live"
    FROZEN = "frozen"
    DELAYED = "delayed"
    DELAYED_FROZEN = "delayed_frozen"
    UNKNOWN = "unknown"


class CaptureMode(StrEnum):
    STREAM = "stream"
    SNAPSHOT = "snapshot"
    HISTORICAL_BACKFILL = "historical_backfill"
    REPLAY = "replay"


class MarketDataStoragePolicy(BaseModel):
    schema_version: int = Field(ge=1)
    profile: str
    hot_spool_root: Path
    local_archive_root: Path | None = None
    backup_archive_root: Path | None = None
    policy: dict[str, Any] = Field(default_factory=dict)
    retention: dict[str, Any] = Field(default_factory=dict)
    watermarks: dict[str, Any] = Field(default_factory=dict)


class RecorderSourcePolicy(BaseModel):
    schema_version: int = Field(ge=1)
    profile: str
    lanes: dict[str, Any]
    ibkr_capacity_policy: dict[str, Any]
    initial_etf_universe_seed: dict[str, Any]
    secondary_intraday_candidates: list[dict[str, Any]] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @property
    def seed_symbols(self) -> list[str]:
        groups = self.initial_etf_universe_seed.get("groups", {})
        symbols: list[str] = []
        for group_symbols in groups.values():
            symbols.extend(str(symbol).upper() for symbol in group_symbols)
        return symbols

    @property
    def usable_market_data_lines(self) -> int:
        return int(self.ibkr_capacity_policy.get("usable_market_data_lines_for_recorder", 0))

    @property
    def realtime_subscription_spacing_seconds(self) -> float:
        value = self.ibkr_capacity_policy.get("realtime_bars", {}).get("recorder_startup_spacing_seconds", 10)
        return float(value)

    @property
    def historical_request_spacing_seconds(self) -> float:
        value = self.ibkr_capacity_policy.get("historical_small_bars", {}).get("recorder_default_spacing_seconds", 10)
        return float(value)

    @property
    def request_rate_per_second(self) -> float:
        value = self.ibkr_capacity_policy.get("api_request_pacing", {}).get("recorder_default_requests_per_second", 5)
        return float(value)

    @property
    def request_burst(self) -> int:
        value = self.ibkr_capacity_policy.get("api_request_pacing", {}).get("recorder_burst_requests", 10)
        return int(value)

    def estimated_line_usage(
        self,
        symbols: Iterable[str],
        *,
        include_top_of_book: bool = False,
        tick_by_tick_symbols: Iterable[str] = (),
    ) -> int:
        symbol_count = len({symbol.upper() for symbol in symbols})
        tick_count = len({symbol.upper() for symbol in tick_by_tick_symbols})
        top_of_book_lines = symbol_count if include_top_of_book else 0
        return symbol_count + top_of_book_lines + tick_count

    def validate_line_budget(
        self,
        symbols: Iterable[str],
        *,
        include_top_of_book: bool = False,
        tick_by_tick_symbols: Iterable[str] = (),
    ) -> None:
        usage = self.estimated_line_usage(
            symbols,
            include_top_of_book=include_top_of_book,
            tick_by_tick_symbols=tick_by_tick_symbols,
        )
        if usage > self.usable_market_data_lines:
            raise ValueError(
                f"Configured recorder subscriptions require {usage} market-data lines, "
                f"above the configured P3.2 budget of {self.usable_market_data_lines}."
            )


class CapturedMarketDataBar(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_name: str = DEFAULT_SOURCE_NAME
    environment: OrderEnvironment = OrderEnvironment.PAPER
    symbol: str = Field(min_length=1)
    currency: Currency = Currency.USD
    exchange: str = "SMART"
    request_id: int | None = None
    exchange_timestamp: datetime | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    capture_mode: CaptureMode = CaptureMode.STREAM
    market_data_mode: IBMarketDataMode = IBMarketDataMode.UNKNOWN
    source_sequence: str | None = None
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    wap: Decimal | None = Field(default=None, gt=0)
    count: int | None = Field(default=None, ge=0)
    bar_size_seconds: int | None = Field(default=5, ge=1)
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange_timestamp", "received_at")
    @classmethod
    def _timestamps_to_utc(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None

    def raw_payload(self) -> dict[str, Any]:
        return {
            "bar_source": "ibapi",
            "bar_size_seconds": self.bar_size_seconds,
            "market_data_mode": self.market_data_mode.value,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": self.volume,
            "wap": str(self.wap) if self.wap is not None else None,
            "count": self.count,
        }


class RawMarketDataEnvelope(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    raw_event_id: str
    source: dict[str, Any]
    recorder: dict[str, Any]
    data_kind: Literal["trade", "quote", "bar", "order_book", "fx", "broker_status"]
    symbol: str | None = None
    currency: str | None = None
    exchange: str | None = None
    exchange_timestamp: datetime | None = None
    received_at: datetime
    available_at: datetime
    source_sequence: str | None = None
    capture_mode: str
    payload_encoding: str = "json"
    payload: dict[str, Any]
    payload_hash: str
    quality_flags: list[str] = Field(default_factory=list)
    previous_raw_event_id: str | None = None
    ingest_batch_id: str | None = None
    request_id: str | None = None
    raw_ref: str | None = None

    @field_validator("exchange_timestamp", "received_at", "available_at")
    @classmethod
    def _timestamps_to_utc(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None


class RawAppendResult(BaseModel):
    raw_ref: str
    path: Path
    byte_offset: int
    bytes_written: int


class RawCatalogEntry(BaseModel):
    schema_version: int = 1
    cataloged_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    raw_schema_version: int
    source_name: str
    source_kind: str | None = None
    environment: str
    data_kind: str
    symbol: str | None = None
    currency: str | None = None
    exchange: str | None = None
    recorder_date: date
    exchange_date: date | None = None
    exchange_timestamp: datetime | None = None
    received_at: datetime
    available_at: datetime
    capture_mode: str
    request_id: str | None = None
    raw_event_id: str
    raw_ref: str
    raw_path: str
    byte_offset: int
    bytes_written: int
    payload_hash: str
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("cataloged_at", "exchange_timestamp", "received_at", "available_at")
    @classmethod
    def _timestamps_to_utc(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None


class RawCatalogAppendResult(BaseModel):
    catalog_ref: str
    path: Path
    byte_offset: int
    bytes_written: int


class RawCatalogRebuildSummary(BaseModel):
    root: str
    files_seen: int = 0
    records_seen: int = 0
    entries_written: int = 0
    records_invalid: int = 0
    manifest_dates: list[date] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MarketDataRecorderRunSummary(BaseModel):
    records_received: int = 0
    records_written: int = 0
    catalog_entries_appended: int = 0
    events_appended: int = 0
    last_raw_ref: str | None = None
    last_catalog_ref: str | None = None
    last_event_id: str | None = None
    quality_flag_counts: dict[str, int] = Field(default_factory=dict)
    error_counts: dict[str, int] = Field(default_factory=dict)


class RawReplayDryRunSummary(BaseModel):
    schema_version: int = 1
    root: str
    source: str
    environment: str
    data_kind: str
    date: date
    symbol: str
    files_seen: int = 0
    records_read: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    payload_hash_mismatches: int = 0
    duplicate_raw_event_ids: int = 0
    first_exchange_timestamp: datetime | None = None
    last_exchange_timestamp: datetime | None = None
    quality_flag_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class RawCatalogQueryResult(BaseModel):
    root: str
    entries: list[RawCatalogEntry] = Field(default_factory=list)
    files_seen: int = 0
    records_read: int = 0
    records_invalid: int = 0
    duplicate_raw_refs: int = 0
    errors: list[str] = Field(default_factory=list)


class TokenBucket:
    def __init__(
        self,
        *,
        rate_per_second: float,
        burst: int,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self.rate_per_second = rate_per_second
        self.burst = float(burst)
        self.sleep = sleep
        self.monotonic = monotonic
        self.tokens = float(burst)
        self.updated_at = monotonic()
        self.total_sleep_seconds = 0.0
        self.sleep_count = 0

    def consume(self, tokens: float = 1.0) -> float:
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        now = self.monotonic()
        elapsed = max(now - self.updated_at, 0.0)
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate_per_second)
        self.updated_at = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return 0.0
        wait_seconds = (tokens - self.tokens) / self.rate_per_second
        self.sleep(wait_seconds)
        self.total_sleep_seconds += wait_seconds
        self.sleep_count += 1
        self.tokens = 0.0
        self.updated_at = self.monotonic()
        return wait_seconds


class RawMarketDataWriter:
    def __init__(
        self,
        root: Path | str,
        *,
        part_id: str | None = None,
        fsync: bool = True,
    ) -> None:
        self.root = Path(root)
        self.part_id = part_id or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        self.fsync = fsync

    def append(self, envelope: RawMarketDataEnvelope) -> RawAppendResult:
        payload = envelope.model_dump(mode="json", exclude_none=True)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        raw_path = self.path_for(envelope)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = f"{line}\n".encode("utf-8")
        with raw_path.open("ab") as handle:
            byte_offset = handle.tell()
            handle.write(encoded)
            handle.flush()
            if self.fsync:
                os.fsync(handle.fileno())
        return RawAppendResult(
            raw_ref=f"{raw_path.as_posix()}#offset={byte_offset}",
            path=raw_path,
            byte_offset=byte_offset,
            bytes_written=len(encoded),
        )

    def path_for(self, envelope: RawMarketDataEnvelope) -> Path:
        received_day = envelope.received_at.date().isoformat()
        symbol = envelope.symbol or "UNKNOWN"
        source = _partition_value(str(envelope.source.get("name", "unknown")))
        environment = _partition_value(str(envelope.source.get("environment", "unknown")))
        data_kind = _partition_value(envelope.data_kind)
        return (
            self.root
            / "raw"
            / f"source={source}"
            / f"environment={environment}"
            / f"data_kind={data_kind}"
            / f"date={received_day}"
            / f"symbol={_partition_value(symbol)}"
            / f"part-{self.part_id}.jsonl"
        )


class RawDataCatalog:
    def __init__(
        self,
        root: Path | str,
        *,
        fsync: bool = True,
    ) -> None:
        self.root = Path(root)
        self.fsync = fsync

    def append(self, envelope: RawMarketDataEnvelope, append: RawAppendResult) -> RawCatalogAppendResult:
        return self.append_entry(raw_catalog_entry_for(envelope, append))

    def append_entry(self, entry: RawCatalogEntry) -> RawCatalogAppendResult:
        manifest_path = self.manifest_path(entry.recorder_date)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        encoded = f"{line}\n".encode("utf-8")
        with manifest_path.open("ab") as handle:
            byte_offset = handle.tell()
            handle.write(encoded)
            handle.flush()
            if self.fsync:
                os.fsync(handle.fileno())
        return RawCatalogAppendResult(
            catalog_ref=f"{manifest_path.as_posix()}#offset={byte_offset}",
            path=manifest_path,
            byte_offset=byte_offset,
            bytes_written=len(encoded),
        )

    def manifest_path(self, day: date) -> Path:
        return self.root / "raw" / "_manifest" / f"date={day.isoformat()}.jsonl"

    def query(
        self,
        *,
        source: str | None = None,
        environment: str | None = None,
        data_kind: str | None = None,
        symbol: str | None = None,
        day: date | None = None,
        raw_schema_version: int | None = None,
    ) -> RawCatalogQueryResult:
        manifest_paths = _manifest_paths(self.root, day=day)
        entries: list[RawCatalogEntry] = []
        seen_raw_refs: set[str] = set()
        duplicate_raw_refs = 0
        records_read = 0
        invalid = 0
        errors: list[str] = []
        for manifest_path in manifest_paths:
            try:
                lines = manifest_path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                errors.append(f"{manifest_path}: {exc}")
                continue
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                records_read += 1
                try:
                    entry = RawCatalogEntry.model_validate_json(line)
                except ValueError as exc:
                    invalid += 1
                    errors.append(f"{manifest_path}#{line_number}: {exc}")
                    continue
                if entry.raw_ref in seen_raw_refs:
                    duplicate_raw_refs += 1
                    continue
                seen_raw_refs.add(entry.raw_ref)
                if not _catalog_entry_matches(
                    entry,
                    source=source,
                    environment=environment,
                    data_kind=data_kind,
                    symbol=symbol,
                    day=day,
                    raw_schema_version=raw_schema_version,
                ):
                    continue
                entries.append(entry)
        entries.sort(
            key=lambda item: (
                item.recorder_date,
                item.source_name,
                item.environment,
                item.data_kind,
                item.symbol or "",
                item.exchange_timestamp or item.received_at,
                item.byte_offset,
            )
        )
        return RawCatalogQueryResult(
            root=str(self.root),
            entries=entries,
            files_seen=len(manifest_paths),
            records_read=records_read,
            records_invalid=invalid,
            duplicate_raw_refs=duplicate_raw_refs,
            errors=errors[:50],
        )

    def rebuild_from_raw_files(
        self,
        *,
        source: str | None = None,
        environment: str | None = None,
        data_kind: str | None = None,
        symbol: str | None = None,
        day: date | None = None,
    ) -> RawCatalogRebuildSummary:
        raw_files = _raw_data_files(
            self.root,
            source=source,
            environment=environment,
            data_kind=data_kind,
            symbol=symbol,
            day=day,
        )
        files_seen = 0
        records_seen = 0
        entries_written = 0
        invalid = 0
        manifest_dates: set[date] = set()
        errors: list[str] = []
        for raw_file in raw_files:
            files_seen += 1
            byte_offset = 0
            try:
                handle = raw_file.open("rb")
            except OSError as exc:
                errors.append(f"{raw_file}: {exc}")
                continue
            with handle:
                for line_number, line_bytes in enumerate(handle, start=1):
                    bytes_written = len(line_bytes)
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        byte_offset += bytes_written
                        continue
                    records_seen += 1
                    try:
                        envelope = RawMarketDataEnvelope.model_validate_json(line)
                    except ValueError as exc:
                        invalid += 1
                        errors.append(f"{raw_file}#{line_number}: {exc}")
                        byte_offset += bytes_written
                        continue
                    if symbol is not None and (envelope.symbol or "").upper() != symbol.upper():
                        byte_offset += bytes_written
                        continue
                    append = RawAppendResult(
                        raw_ref=f"{raw_file.as_posix()}#offset={byte_offset}",
                        path=raw_file,
                        byte_offset=byte_offset,
                        bytes_written=bytes_written,
                    )
                    entry = raw_catalog_entry_for(envelope, append)
                    self.append_entry(entry)
                    entries_written += 1
                    manifest_dates.add(entry.recorder_date)
                    byte_offset += bytes_written
        return RawCatalogRebuildSummary(
            root=str(self.root),
            files_seen=files_seen,
            records_seen=records_seen,
            entries_written=entries_written,
            records_invalid=invalid,
            manifest_dates=sorted(manifest_dates),
            errors=errors[:50],
        )


class MarketDataRecorder:
    def __init__(
        self,
        *,
        writer: RawMarketDataWriter,
        catalog: RawDataCatalog | None = None,
        event_store: PlatformEventAppendStore | None = None,
        state_path: Path | str | None = None,
        service_id: str = SERVICE_ID,
        instance_id: str = DEFAULT_INSTANCE_ID,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
        started_at: datetime | None = None,
        software_version: str | None = None,
        operation_logger: OperationalLogger | None = None,
        log_every_records: int = 100,
    ) -> None:
        self.writer = writer
        self.catalog = catalog
        self.event_store = event_store
        self.state_path = Path(state_path) if state_path is not None else Path("var/run/market_data_recorder.state.json")
        self.service_id = service_id
        self.instance_id = instance_id
        self.environment = environment
        self.started_at = _as_utc(started_at or datetime.now(tz=UTC))
        self.software_version = software_version
        self.operation_logger = operation_logger
        self.log_every_records = max(1, int(log_every_records))
        self.records_received = 0
        self.records_written = 0
        self.catalog_entries_appended = 0
        self.events_appended = 0
        self.last_received_at: datetime | None = None
        self.last_raw_ref: str | None = None
        self.last_catalog_ref: str | None = None
        self.last_event_id: str | None = None
        self.active_symbols: set[str] = set()
        self.market_data_modes: dict[str, str] = {}
        self.quality_flag_counts: Counter[str] = Counter()
        self.error_counts: Counter[str] = Counter()
        self.pacing_sleep_count = 0
        self.pacing_sleep_seconds = 0.0
        self.disconnects = 0
        self._log_info(
            "recorder_initialized",
            "Market data recorder initialized.",
            state_path=self.state_path,
            environment=self.environment.value,
            instance_id=self.instance_id,
        )

    def record_bar(self, bar: CapturedMarketDataBar) -> MarketDataRecordedEvent:
        self.records_received += 1
        self.active_symbols.add(bar.symbol)
        self.market_data_modes[bar.symbol] = bar.market_data_mode.value
        self.last_received_at = bar.received_at
        envelope = self._envelope_for_bar(bar)
        append = self.writer.append(envelope)
        self.records_written += 1
        self.last_raw_ref = append.raw_ref
        if self.catalog is not None:
            catalog_append = self.catalog.append(envelope, append)
            self.catalog_entries_appended += 1
            self.last_catalog_ref = catalog_append.catalog_ref
        for flag in envelope.quality_flags:
            self.quality_flag_counts[flag] += 1
        event = self._event_for_bar(bar=bar, envelope=envelope, raw_ref=append.raw_ref)
        if self.event_store is not None:
            self.event_store.append_platform_event(event)
            self.events_appended += 1
        self.last_event_id = event.event_id
        self.write_state(running=True, message="Market data recorder heartbeat.")
        if self.records_written == 1 or self.records_written % self.log_every_records == 0 or envelope.quality_flags:
            self._log_info(
                "market_data_bar_recorded",
                "Market data bar recorded.",
                symbol=bar.symbol,
                request_id=bar.request_id,
                market_data_mode=bar.market_data_mode.value,
                capture_mode=bar.capture_mode.value,
                raw_ref=append.raw_ref,
                catalog_ref=self.last_catalog_ref,
                event_id=event.event_id,
                records_written=self.records_written,
                events_appended=self.events_appended,
                quality_flags=list(envelope.quality_flags),
            )
        return event

    def note_error(self, code: str | int, message: str | None = None) -> None:
        key = str(code)
        self.error_counts[key] += 1
        self._log_error(
            "recorder_error",
            "Market data recorder received an error.",
            code=key,
            error_message=message,
            error_count=self.error_counts[key],
        )
        self.write_state(
            running=True,
            last_error=f"{key}: {message}" if message else key,
            message="Market data recorder received an error.",
        )

    def note_pacing_sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self.pacing_sleep_count += 1
        self.pacing_sleep_seconds += seconds
        if self.pacing_sleep_count == 1 or self.pacing_sleep_count % 25 == 0:
            self._log_info(
                "recorder_pacing_sleep",
                "Market data recorder pacing sleep.",
                seconds=round(seconds, 6),
                pacing_sleep_count=self.pacing_sleep_count,
                pacing_sleep_seconds=round(self.pacing_sleep_seconds, 6),
            )

    def note_disconnect(self) -> None:
        self.disconnects += 1
        self._log_info(
            "recorder_disconnected",
            "Market data recorder disconnected from source.",
            disconnects=self.disconnects,
            records_written=self.records_written,
            events_appended=self.events_appended,
        )

    def note_subscription_started(
        self,
        *,
        symbol: str,
        request_id: int,
        market_data_mode: IBMarketDataMode,
        capture_mode: CaptureMode,
    ) -> None:
        self._log_info(
            "recorder_subscription_started",
            "Market data recorder request/subscription started.",
            symbol=symbol,
            request_id=request_id,
            market_data_mode=market_data_mode.value,
            capture_mode=capture_mode.value,
        )

    def note_subscription_cancelled(self, *, symbol: str | None, request_id: int) -> None:
        self._log_info(
            "recorder_subscription_cancelled",
            "Market data recorder subscription cancelled.",
            symbol=symbol,
            request_id=request_id,
        )

    def note_market_data_mode(self, *, symbol: str, request_id: int, market_data_mode: IBMarketDataMode) -> None:
        self._log_info(
            "recorder_market_data_mode",
            "IB market data mode received.",
            symbol=symbol,
            request_id=request_id,
            market_data_mode=market_data_mode.value,
        )

    def summary(self) -> MarketDataRecorderRunSummary:
        return MarketDataRecorderRunSummary(
            records_received=self.records_received,
            records_written=self.records_written,
            catalog_entries_appended=self.catalog_entries_appended,
            events_appended=self.events_appended,
            last_raw_ref=self.last_raw_ref,
            last_catalog_ref=self.last_catalog_ref,
            last_event_id=self.last_event_id,
            quality_flag_counts=dict(self.quality_flag_counts),
            error_counts=dict(self.error_counts),
        )

    def write_state(
        self,
        *,
        running: bool,
        message: str,
        last_error: str | None = None,
    ) -> None:
        write_service_state_file(
            self.state_path,
            service_id=self.service_id,
            running=running,
            started_at=self.started_at,
            heartbeat_at=datetime.now(tz=UTC),
            last_error=last_error,
            message=message,
            details={
                "environment": self.environment.value,
                "symbols_active": sorted(self.active_symbols),
                "market_data_modes": dict(sorted(self.market_data_modes.items())),
                "last_received_at": self.last_received_at.isoformat() if self.last_received_at else None,
                "last_raw_ref": self.last_raw_ref,
                "last_catalog_ref": self.last_catalog_ref,
                "last_event_id": self.last_event_id,
                "records_received": self.records_received,
                "records_written": self.records_written,
                "catalog_entries_appended": self.catalog_entries_appended,
                "events_appended": self.events_appended,
                "quality_flag_counts": dict(self.quality_flag_counts),
                "error_counts": dict(self.error_counts),
                "pacing_sleep_count": self.pacing_sleep_count,
                "pacing_sleep_seconds": round(self.pacing_sleep_seconds, 6),
                "disconnects": self.disconnects,
            },
        )

    def _log_info(self, event: str, message: str, **details: Any) -> None:
        if self.operation_logger is None:
            return
        self.operation_logger.info(event, message=message, **details)

    def _log_error(self, event: str, message: str, **details: Any) -> None:
        if self.operation_logger is None:
            return
        self.operation_logger.error(event, message=message, **details)

    def _envelope_for_bar(self, bar: CapturedMarketDataBar) -> RawMarketDataEnvelope:
        payload = bar.raw_payload()
        payload_hash = canonical_payload_hash(payload)
        quality_flags = _bar_quality_flags(bar)
        raw_event_id = deterministic_raw_event_id(
            source_name=bar.source_name,
            environment=bar.environment,
            data_kind="bar",
            symbol=bar.symbol,
            exchange_timestamp=bar.exchange_timestamp,
            source_sequence=bar.source_sequence,
            request_id=bar.request_id,
            payload_hash=payload_hash,
        )
        return RawMarketDataEnvelope(
            raw_event_id=raw_event_id,
            source={
                "name": bar.source_name,
                "kind": "broker",
                "environment": bar.environment.value,
                "market_data_mode": bar.market_data_mode.value,
            },
            recorder={
                "service_id": self.service_id,
                "instance_id": self.instance_id,
                "software_version": self.software_version,
            },
            data_kind="bar",
            symbol=bar.symbol,
            currency=bar.currency.value,
            exchange=bar.exchange,
            exchange_timestamp=bar.exchange_timestamp,
            received_at=bar.received_at,
            available_at=datetime.now(tz=UTC),
            source_sequence=bar.source_sequence,
            capture_mode=bar.capture_mode.value,
            payload=payload,
            payload_hash=payload_hash,
            quality_flags=quality_flags,
            request_id=str(bar.request_id) if bar.request_id is not None else None,
        )

    def _event_for_bar(
        self,
        *,
        bar: CapturedMarketDataBar,
        envelope: RawMarketDataEnvelope,
        raw_ref: str,
    ) -> MarketDataRecordedEvent:
        occurred_at = bar.exchange_timestamp or bar.received_at
        return MarketDataRecordedEvent(
            event_id=f"market_data.recorded.{envelope.raw_event_id}",
            occurred_at=occurred_at,
            source=EventSource(
                service="market-data-recorder",
                instance=self.instance_id,
                environment=bar.environment,
            ),
            payload=MarketDataRecordedPayload(
                source_name=bar.source_name,
                data_kind=MarketDataKind.BAR,
                symbol=bar.symbol,
                currency=bar.currency,
                trade_date=occurred_at.date(),
                exchange_timestamp=bar.exchange_timestamp,
                received_at=bar.received_at,
                price=bar.close,
                volume=bar.volume,
                source_sequence=envelope.source_sequence,
                raw_ref=raw_ref,
                quality_flags=envelope.quality_flags,
            ),
        )


def load_storage_policy(path: Path | str = "config/market-data-storage.json") -> MarketDataStoragePolicy:
    return MarketDataStoragePolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_recorder_source_policy(path: Path | str = "config/market-data-recorder-sources.json") -> RecorderSourcePolicy:
    return RecorderSourcePolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))


def deterministic_raw_event_id(
    *,
    source_name: str,
    environment: OrderEnvironment,
    data_kind: str,
    symbol: str,
    exchange_timestamp: datetime | None,
    source_sequence: str | None,
    request_id: int | None,
    payload_hash: str,
) -> str:
    timestamp = _as_utc(exchange_timestamp).isoformat() if exchange_timestamp else ""
    seed = "|".join(
        [
            source_name,
            environment.value,
            data_kind,
            symbol.upper(),
            timestamp,
            source_sequence or "",
            str(request_id) if request_id is not None else "",
            payload_hash,
        ]
    )
    return f"raw_{sha1(seed.encode('utf-8')).hexdigest()}"


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def dry_run_raw_replay(
    root: Path | str,
    *,
    source: str,
    environment: str,
    data_kind: str,
    day: date,
    symbol: str,
) -> RawReplayDryRunSummary:
    root_path = Path(root)
    target_dir = (
        root_path
        / "raw"
        / f"source={_partition_value(source)}"
        / f"environment={_partition_value(environment)}"
        / f"data_kind={_partition_value(data_kind)}"
        / f"date={day.isoformat()}"
        / f"symbol={_partition_value(symbol.upper())}"
    )
    files = sorted(target_dir.glob("*.jsonl"))
    quality_counts: Counter[str] = Counter()
    errors: list[str] = []
    seen_raw_event_ids: set[str] = set()
    duplicate_raw_event_ids = 0
    records_read = 0
    valid = 0
    invalid = 0
    hash_mismatches = 0
    first_exchange_timestamp: datetime | None = None
    last_exchange_timestamp: datetime | None = None

    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{file_path}: {exc}")
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            records_read += 1
            try:
                payload = json.loads(line)
                envelope = RawMarketDataEnvelope.model_validate(payload)
            except (json.JSONDecodeError, ValueError) as exc:
                invalid += 1
                errors.append(f"{file_path}#{line_number}: {exc}")
                continue
            if envelope.raw_event_id in seen_raw_event_ids:
                duplicate_raw_event_ids += 1
            seen_raw_event_ids.add(envelope.raw_event_id)
            expected_hash = canonical_payload_hash(envelope.payload)
            if envelope.payload_hash != expected_hash:
                hash_mismatches += 1
            if envelope.exchange_timestamp is not None:
                first_exchange_timestamp = _min_datetime(first_exchange_timestamp, envelope.exchange_timestamp)
                last_exchange_timestamp = _max_datetime(last_exchange_timestamp, envelope.exchange_timestamp)
            for flag in envelope.quality_flags:
                quality_counts[flag] += 1
            valid += 1

    return RawReplayDryRunSummary(
        root=str(root_path),
        source=source,
        environment=environment,
        data_kind=data_kind,
        date=day,
        symbol=symbol.upper(),
        files_seen=len(files),
        records_read=records_read,
        records_valid=valid,
        records_invalid=invalid,
        payload_hash_mismatches=hash_mismatches,
        duplicate_raw_event_ids=duplicate_raw_event_ids,
        first_exchange_timestamp=first_exchange_timestamp,
        last_exchange_timestamp=last_exchange_timestamp,
        quality_flag_counts=dict(quality_counts),
        errors=errors[:50],
    )


def raw_catalog_entry_for(envelope: RawMarketDataEnvelope, append: RawAppendResult) -> RawCatalogEntry:
    source_name = str(envelope.source.get("name", "unknown"))
    source_kind = envelope.source.get("kind")
    environment = str(envelope.source.get("environment", "unknown"))
    return RawCatalogEntry(
        raw_schema_version=envelope.schema_version,
        source_name=source_name,
        source_kind=str(source_kind) if source_kind is not None else None,
        environment=environment,
        data_kind=envelope.data_kind,
        symbol=envelope.symbol,
        currency=envelope.currency,
        exchange=envelope.exchange,
        recorder_date=envelope.received_at.date(),
        exchange_date=envelope.exchange_timestamp.date() if envelope.exchange_timestamp else None,
        exchange_timestamp=envelope.exchange_timestamp,
        received_at=envelope.received_at,
        available_at=envelope.available_at,
        capture_mode=envelope.capture_mode,
        request_id=envelope.request_id,
        raw_event_id=envelope.raw_event_id,
        raw_ref=append.raw_ref,
        raw_path=append.path.as_posix(),
        byte_offset=append.byte_offset,
        bytes_written=append.bytes_written,
        payload_hash=envelope.payload_hash,
        quality_flags=envelope.quality_flags,
    )


def query_raw_catalog(
    root: Path | str,
    *,
    source: str | None = None,
    environment: str | None = None,
    data_kind: str | None = None,
    symbol: str | None = None,
    day: date | None = None,
    raw_schema_version: int | None = None,
) -> RawCatalogQueryResult:
    return RawDataCatalog(root).query(
        source=source,
        environment=environment,
        data_kind=data_kind,
        symbol=symbol,
        day=day,
        raw_schema_version=raw_schema_version,
    )


def rebuild_raw_catalog(
    root: Path | str,
    *,
    source: str | None = None,
    environment: str | None = None,
    data_kind: str | None = None,
    symbol: str | None = None,
    day: date | None = None,
) -> RawCatalogRebuildSummary:
    return RawDataCatalog(root).rebuild_from_raw_files(
        source=source,
        environment=environment,
        data_kind=data_kind,
        symbol=symbol,
        day=day,
    )


def _bar_quality_flags(bar: CapturedMarketDataBar) -> list[str]:
    flags = list(bar.quality_flags)
    if bar.exchange_timestamp is None:
        flags.append("source_timestamp_missing")
    elif bar.received_at < bar.exchange_timestamp:
        flags.append("received_before_exchange_timestamp")
    if bar.market_data_mode == IBMarketDataMode.DELAYED:
        flags.append("ib_market_data_mode_delayed")
    elif bar.market_data_mode == IBMarketDataMode.DELAYED_FROZEN:
        flags.append("ib_market_data_mode_delayed_frozen")
    elif bar.market_data_mode == IBMarketDataMode.FROZEN:
        flags.append("ib_market_data_mode_frozen")
    elif bar.market_data_mode == IBMarketDataMode.UNKNOWN:
        flags.append("ib_market_data_mode_unknown")
    return sorted(set(flags))


def _partition_value(value: str) -> str:
    return value.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")


def _manifest_paths(root: Path, *, day: date | None) -> list[Path]:
    manifest_root = root / "raw" / "_manifest"
    if day is not None:
        path = manifest_root / f"date={day.isoformat()}.jsonl"
        return [path] if path.exists() else []
    return sorted(manifest_root.glob("date=*.jsonl"))


def _raw_data_files(
    root: Path,
    *,
    source: str | None,
    environment: str | None,
    data_kind: str | None,
    symbol: str | None,
    day: date | None,
) -> list[Path]:
    source_part = f"source={_partition_value(source)}" if source else "source=*"
    environment_part = f"environment={_partition_value(environment)}" if environment else "environment=*"
    data_kind_part = f"data_kind={_partition_value(data_kind)}" if data_kind else "data_kind=*"
    date_part = f"date={day.isoformat()}" if day else "date=*"
    symbol_part = f"symbol={_partition_value(symbol.upper())}" if symbol else "symbol=*"
    pattern = f"raw/{source_part}/{environment_part}/{data_kind_part}/{date_part}/{symbol_part}/*.jsonl"
    return sorted(root.glob(pattern))


def _catalog_entry_matches(
    entry: RawCatalogEntry,
    *,
    source: str | None,
    environment: str | None,
    data_kind: str | None,
    symbol: str | None,
    day: date | None,
    raw_schema_version: int | None,
) -> bool:
    if source is not None and entry.source_name != source:
        return False
    if environment is not None and entry.environment != environment:
        return False
    if data_kind is not None and entry.data_kind != data_kind:
        return False
    if symbol is not None and (entry.symbol or "").upper() != symbol.upper():
        return False
    if day is not None and entry.recorder_date != day:
        return False
    if raw_schema_version is not None and entry.raw_schema_version != raw_schema_version:
        return False
    return True


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _min_datetime(left: datetime | None, right: datetime) -> datetime:
    return right if left is None or right < left else left


def _max_datetime(left: datetime | None, right: datetime) -> datetime:
    return right if left is None or right > left else left
