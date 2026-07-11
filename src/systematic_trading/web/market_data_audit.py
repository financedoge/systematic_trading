from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from systematic_trading.market_data import ClickHouseMarketDataClient
from systematic_trading.recorders.market_data import (
    RawCatalogEntry,
    RawMarketDataEnvelope,
    canonical_payload_hash,
    load_storage_policy,
    query_raw_catalog,
)

router = APIRouter(prefix="/api/v1")


class MarketDataAuditBar(BaseModel):
    raw_event_id: str
    symbol: str
    exchange_timestamp: datetime | None = None
    received_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    wap: Decimal | None = None
    count: int | None = None
    bar_size_seconds: int | None = None
    capture_mode: str
    market_data_mode: str | None = None
    quality_flags: list[str] = Field(default_factory=list)


class MarketDataAuditRow(BaseModel):
    raw_event_id: str
    raw_ref: str
    raw_path: str
    byte_offset: int
    bytes_written: int
    source_name: str
    environment: str
    data_kind: str
    symbol: str | None = None
    exchange: str | None = None
    recorder_date: date
    exchange_date: date | None = None
    exchange_timestamp: datetime | None = None
    received_at: datetime
    available_at: datetime
    capture_mode: str
    request_id: str | None = None
    payload_hash: str
    hash_ok: bool
    duplicate_raw_event_id: bool
    quality_flags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MarketDataAuditSummary(BaseModel):
    root: str
    source: str | None = None
    environment: str | None = None
    data_kind: str | None = None
    symbol: str | None = None
    recorder_date: date | None = None
    entry_count: int
    rows_returned: int
    records_read: int
    records_invalid: int
    duplicate_raw_refs: int
    duplicate_raw_event_ids: int
    payload_hash_mismatches: int
    first_exchange_timestamp: datetime | None = None
    last_exchange_timestamp: datetime | None = None
    quality_flag_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class MarketDataAuditResponse(BaseModel):
    summary: MarketDataAuditSummary
    bars: list[MarketDataAuditBar] = Field(default_factory=list)
    rows: list[MarketDataAuditRow] = Field(default_factory=list)


class MarketDataAuditSymbolsResponse(BaseModel):
    root: str
    source: str | None = None
    environment: str | None = None
    data_kind: str | None = None
    recorder_date: date | None = None
    symbols: list[str] = Field(default_factory=list)
    records_read: int
    records_invalid: int
    errors: list[str] = Field(default_factory=list)


class GoldenDailyBar(BaseModel):
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    source_name: str
    source_priority: int
    adjustment: str
    available_at: str
    ingested_at: str
    quality_flags: list[str] = Field(default_factory=list)
    payload_hash: str


class GoldenDailyBarsSummary(BaseModel):
    symbol: str
    start_date: date | None = None
    end_date: date | None = None
    rows_returned: int
    first_trade_date: date | None = None
    last_trade_date: date | None = None
    source_names: list[str] = Field(default_factory=list)
    quality_flag_counts: dict[str, int] = Field(default_factory=dict)


class GoldenDailyBarsResponse(BaseModel):
    summary: GoldenDailyBarsSummary
    bars: list[GoldenDailyBar] = Field(default_factory=list)


class GoldenDailySymbol(BaseModel):
    symbol: str
    row_count: int
    first_trade_date: date | None = None
    last_trade_date: date | None = None


class GoldenDailySymbolsResponse(BaseModel):
    symbols: list[GoldenDailySymbol] = Field(default_factory=list)


@router.get("/market-data/daily-symbols", response_model=GoldenDailySymbolsResponse)
@router.get("/market-data/golden/daily-symbols", response_model=GoldenDailySymbolsResponse)
def golden_daily_symbols(request: Request) -> GoldenDailySymbolsResponse:
    client = _clickhouse_client(request)
    try:
        rows = client.query_daily_bar_symbols()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GoldenDailySymbolsResponse(symbols=[GoldenDailySymbol.model_validate(row) for row in rows])


@router.get("/market-data/daily-bars", response_model=GoldenDailyBarsResponse)
@router.get("/market-data/golden/daily-bars", response_model=GoldenDailyBarsResponse)
def golden_daily_bars(
    request: Request,
    symbol: str = Query(..., min_length=1),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> GoldenDailyBarsResponse:
    client = _clickhouse_client(request)
    normalized_symbol = symbol.strip().upper()
    try:
        raw_rows = client.query_daily_bars(
            symbol=normalized_symbol,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            limit=limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    bars = [GoldenDailyBar.model_validate(row) for row in raw_rows]
    first_trade_date = bars[0].trade_date if bars else None
    last_trade_date = bars[-1].trade_date if bars else None
    quality_counts: Counter[str] = Counter()
    for bar in bars:
        for flag in bar.quality_flags:
            quality_counts[flag] += 1
    return GoldenDailyBarsResponse(
        summary=GoldenDailyBarsSummary(
            symbol=normalized_symbol,
            start_date=start_date,
            end_date=end_date,
            rows_returned=len(bars),
            first_trade_date=first_trade_date,
            last_trade_date=last_trade_date,
            source_names=sorted({bar.source_name for bar in bars}),
            quality_flag_counts=dict(quality_counts),
        ),
        bars=bars,
    )


@router.get("/market-data/audit/symbols", response_model=MarketDataAuditSymbolsResponse)
def market_data_audit_symbols(
    request: Request,
    source: str | None = Query(default="interactive-brokers"),
    environment: str | None = Query(default=None),
    data_kind: str | None = Query(default="bar"),
    recorder_date: date | None = Query(default=None),
) -> MarketDataAuditSymbolsResponse:
    settings = request.app.state.settings
    storage_policy = _load_storage_policy(settings.market_data_storage_policy_path)
    catalog_result = query_raw_catalog(
        storage_policy.hot_spool_root,
        source=source,
        environment=environment,
        data_kind=data_kind,
        day=recorder_date,
    )
    symbols = sorted({entry.symbol.upper() for entry in catalog_result.entries if entry.symbol})
    return MarketDataAuditSymbolsResponse(
        root=catalog_result.root,
        source=source,
        environment=environment,
        data_kind=data_kind,
        recorder_date=recorder_date,
        symbols=symbols,
        records_read=catalog_result.records_read,
        records_invalid=catalog_result.records_invalid,
        errors=catalog_result.errors,
    )


@router.get("/market-data/audit", response_model=MarketDataAuditResponse)
def market_data_audit(
    request: Request,
    source: str | None = Query(default="interactive-brokers"),
    environment: str | None = Query(default=None),
    data_kind: str | None = Query(default="bar"),
    symbol: str | None = Query(default=None),
    recorder_date: date | None = Query(default=None),
    capture_mode: str | None = Query(default=None),
    bar_size_seconds: int | None = Query(default=None, ge=1),
    limit: int = Query(default=500, ge=1, le=5000),
) -> MarketDataAuditResponse:
    settings = request.app.state.settings
    storage_policy = _load_storage_policy(settings.market_data_storage_policy_path)
    catalog_result = query_raw_catalog(
        storage_policy.hot_spool_root,
        source=source,
        environment=environment,
        data_kind=data_kind,
        symbol=symbol,
        day=recorder_date,
    )
    seen_event_ids: set[str] = set()
    duplicate_event_ids = 0
    hash_mismatches = 0
    quality_counts: Counter[str] = Counter()
    errors = list(catalog_result.errors)
    rows: list[MarketDataAuditRow] = []
    bars: list[MarketDataAuditBar] = []
    first_exchange_timestamp: datetime | None = None
    last_exchange_timestamp: datetime | None = None

    for entry in catalog_result.entries:
        if len(rows) >= limit:
            break
        envelope, read_error = _read_envelope(entry)
        payload = envelope.payload if envelope is not None else {}
        payload_bar_size = _int_or_none(payload.get("bar_size_seconds"))
        payload_capture_mode = envelope.capture_mode if envelope is not None else entry.capture_mode
        if capture_mode is not None and payload_capture_mode != capture_mode:
            continue
        if bar_size_seconds is not None and payload_bar_size != bar_size_seconds:
            continue
        duplicate = entry.raw_event_id in seen_event_ids
        if duplicate:
            duplicate_event_ids += 1
        seen_event_ids.add(entry.raw_event_id)
        hash_ok = False
        if envelope is not None:
            hash_ok = canonical_payload_hash(envelope.payload) == envelope.payload_hash
        if envelope is not None and not hash_ok:
            hash_mismatches += 1
        if read_error is not None:
            errors.append(read_error)
        quality_flags = list(envelope.quality_flags if envelope is not None else entry.quality_flags)
        for flag in quality_flags:
            quality_counts[flag] += 1
        timestamp = envelope.exchange_timestamp if envelope is not None else entry.exchange_timestamp
        if timestamp is not None:
            first_exchange_timestamp = timestamp if first_exchange_timestamp is None else min(first_exchange_timestamp, timestamp)
            last_exchange_timestamp = timestamp if last_exchange_timestamp is None else max(last_exchange_timestamp, timestamp)

        row = MarketDataAuditRow(
            raw_event_id=entry.raw_event_id,
            raw_ref=entry.raw_ref,
            raw_path=entry.raw_path,
            byte_offset=entry.byte_offset,
            bytes_written=entry.bytes_written,
            source_name=entry.source_name,
            environment=entry.environment,
            data_kind=entry.data_kind,
            symbol=entry.symbol,
            exchange=entry.exchange,
            recorder_date=entry.recorder_date,
            exchange_date=entry.exchange_date,
            exchange_timestamp=timestamp,
            received_at=entry.received_at,
            available_at=entry.available_at,
            capture_mode=payload_capture_mode,
            request_id=entry.request_id,
            payload_hash=entry.payload_hash,
            hash_ok=hash_ok,
            duplicate_raw_event_id=duplicate,
            quality_flags=quality_flags,
            payload=payload,
            error=read_error,
        )
        rows.append(row)
        if entry.data_kind == "bar" and envelope is not None:
            bar = _bar_from_envelope(envelope)
            if bar is not None:
                bars.append(bar)

    bars.sort(key=lambda item: (item.exchange_timestamp or item.received_at, item.raw_event_id))
    rows.sort(key=lambda item: (item.exchange_timestamp or item.received_at, item.raw_ref))
    return MarketDataAuditResponse(
        summary=MarketDataAuditSummary(
            root=catalog_result.root,
            source=source,
            environment=environment,
            data_kind=data_kind,
            symbol=symbol.upper() if symbol else None,
            recorder_date=recorder_date,
            entry_count=len(catalog_result.entries),
            rows_returned=len(rows),
            records_read=catalog_result.records_read,
            records_invalid=catalog_result.records_invalid,
            duplicate_raw_refs=catalog_result.duplicate_raw_refs,
            duplicate_raw_event_ids=duplicate_event_ids,
            payload_hash_mismatches=hash_mismatches,
            first_exchange_timestamp=first_exchange_timestamp,
            last_exchange_timestamp=last_exchange_timestamp,
            quality_flag_counts=dict(quality_counts),
            errors=errors[:50],
        ),
        bars=bars,
        rows=rows,
    )


def _load_storage_policy(path: Path):
    try:
        return load_storage_policy(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not load market-data storage policy {path}: {exc}") from exc


def _clickhouse_client(request: Request) -> ClickHouseMarketDataClient:
    settings = request.app.state.settings
    return ClickHouseMarketDataClient(
        settings.clickhouse_http_url,
        database=settings.clickhouse_database,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )


def _read_envelope(entry: RawCatalogEntry) -> tuple[RawMarketDataEnvelope | None, str | None]:
    path = Path(entry.raw_path)
    try:
        with path.open("rb") as handle:
            handle.seek(entry.byte_offset)
            line = handle.readline()
    except OSError as exc:
        return None, f"{entry.raw_ref}: {exc}"
    if not line:
        return None, f"{entry.raw_ref}: empty raw record"
    try:
        return RawMarketDataEnvelope.model_validate_json(line.decode("utf-8")), None
    except ValueError as exc:
        return None, f"{entry.raw_ref}: {exc}"


def _bar_from_envelope(envelope: RawMarketDataEnvelope) -> MarketDataAuditBar | None:
    payload = envelope.payload
    try:
        return MarketDataAuditBar(
            raw_event_id=envelope.raw_event_id,
            symbol=envelope.symbol or "",
            exchange_timestamp=envelope.exchange_timestamp,
            received_at=envelope.received_at,
            open=Decimal(str(payload["open"])),
            high=Decimal(str(payload["high"])),
            low=Decimal(str(payload["low"])),
            close=Decimal(str(payload["close"])),
            volume=int(Decimal(str(payload.get("volume", 0) or 0))),
            wap=Decimal(str(payload["wap"])) if payload.get("wap") is not None else None,
            count=int(Decimal(str(payload["count"]))) if payload.get("count") is not None else None,
            bar_size_seconds=_int_or_none(payload.get("bar_size_seconds")),
            capture_mode=envelope.capture_mode,
            market_data_mode=str(payload.get("market_data_mode")) if payload.get("market_data_mode") is not None else None,
            quality_flags=list(envelope.quality_flags),
        )
    except (KeyError, ValueError, ArithmeticError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(Decimal(str(value)))
    except (ValueError, ArithmeticError):
        return None
