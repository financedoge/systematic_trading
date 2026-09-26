from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol, Sequence

from pydantic import BaseModel, Field

from systematic_trading.domain.market import PriceBar
from systematic_trading.daily_quality import completed_session, captured_before_close, valid_ohlc
from systematic_trading.market_data.golden import ClickHouseMarketDataClient, daily_bar_row


class DailyBarProvider(Protocol):
    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        """Fetch daily bars for one symbol."""


class DailyBackfillSymbolResult(BaseModel):
    symbol: str
    requested_start_date: date
    requested_end_date: date
    source_name: str
    fallback_used: bool = False
    existing_dates: int = 0
    provider_bars: int = 0
    inserted_bars: int = 0
    repaired_existing_dates: int = 0
    deleted_stale_dates: int = 0
    first_inserted_date: date | None = None
    last_inserted_date: date | None = None
    warnings: list[str] = Field(default_factory=list)


class DailyBackfillResult(BaseModel):
    refreshed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    symbols_requested: int
    symbols_updated: int
    bars_inserted: int
    start_date: date
    end_date: date
    source_name: str
    refresh_existing: bool = False
    results: list[DailyBackfillSymbolResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def backfill_clickhouse_daily_bars(
    *,
    client: ClickHouseMarketDataClient,
    provider: DailyBarProvider,
    symbols: Sequence[str],
    start_date: date,
    end_date: date,
    source_name: str,
    source_priority: int = 80,
    adjustment: str = "provider_default",
    fallback_provider: DailyBarProvider | None = None,
    fallback_source_name: str | None = None,
    fallback_source_priority: int | None = None,
    refresh_existing: bool = False,
    quality_flags: Sequence[str] = ("daily_backfill",),
) -> DailyBackfillResult:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")
    normalized_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
    if not normalized_symbols:
        raise ValueError("At least one symbol is required for daily-bar backfill.")

    client.ensure_daily_bars_table()
    results: list[DailyBackfillSymbolResult] = []
    for symbol in normalized_symbols:
        results.append(
            _backfill_symbol(
                client=client,
                provider=provider,
                fallback_provider=fallback_provider,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                source_name=source_name,
                source_priority=source_priority,
                fallback_source_name=fallback_source_name,
                fallback_source_priority=fallback_source_priority,
                adjustment=adjustment,
                refresh_existing=refresh_existing,
                quality_flags=quality_flags,
            )
        )

    return DailyBackfillResult(
        symbols_requested=len(normalized_symbols),
        symbols_updated=sum(1 for result in results if result.inserted_bars > 0),
        bars_inserted=sum(result.inserted_bars for result in results),
        start_date=start_date,
        end_date=end_date,
        source_name=source_name,
        refresh_existing=refresh_existing,
        results=results,
        warnings=_dedupe([warning for result in results for warning in result.warnings]),
    )


def _backfill_symbol(
    *,
    client: ClickHouseMarketDataClient,
    provider: DailyBarProvider,
    fallback_provider: DailyBarProvider | None,
    symbol: str,
    start_date: date,
    end_date: date,
    source_name: str,
    source_priority: int,
    fallback_source_name: str | None,
    fallback_source_priority: int | None,
    adjustment: str,
    refresh_existing: bool,
    quality_flags: Sequence[str],
) -> DailyBackfillSymbolResult:
    existing_rows = client.query_daily_bars(
        symbol=symbol,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        limit=50000,
    )
    existing_by_date = {
        date.fromisoformat(str(row["trade_date"])): row
        for row in existing_rows
    }
    existing_dates = set(existing_by_date)
    repair_dates = {
        trade_date
        for trade_date, row in existing_by_date.items()
        if _existing_daily_row_needs_repair(row)
    }
    if not existing_rows:
        existing_dates = {
            date.fromisoformat(value)
            for value in client.query_daily_bar_dates(
                symbol=symbol,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
        }
        repair_dates = set()
    bars, used_source_name, used_source_priority, fallback_used, warnings = _fetch_bars(
        provider=provider,
        fallback_provider=fallback_provider,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        source_name=source_name,
        source_priority=source_priority,
        fallback_source_name=fallback_source_name,
        fallback_source_priority=fallback_source_priority,
    )
    rejected = [bar.trade_date for bar in bars if not completed_session(bar.trade_date) or not valid_ohlc(bar)]
    if rejected:
        warnings.append(f"{symbol}: rejected unfinished/non-session or invalid OHLC bars: {rejected}")
    bars_by_date = {
        bar.trade_date: bar
        for bar in bars
        if start_date <= bar.trade_date <= end_date and completed_session(bar.trade_date) and valid_ohlc(bar)
    }
    candidate_dates = sorted(bars_by_date)
    delete_dates = sorted(repair_dates - set(candidate_dates)) if candidate_dates else []
    insert_dates = (
        candidate_dates
        if refresh_existing
        else [day for day in candidate_dates if day not in existing_dates or day in repair_dates]
    )
    rows = [
        daily_bar_row(
            symbol=symbol,
            bar=bars_by_date[trade_date],
            source_name=used_source_name,
            source_priority=used_source_priority,
            adjustment=adjustment,
            quality_flags=list(quality_flags),
        )
        for trade_date in insert_dates
    ]
    inserted = client.insert_daily_bar_rows(rows)
    deleted = client.delete_daily_bar_dates(
        symbol=symbol,
        trade_dates=[trade_date.isoformat() for trade_date in delete_dates],
    )
    return DailyBackfillSymbolResult(
        symbol=symbol,
        requested_start_date=start_date,
        requested_end_date=end_date,
        source_name=used_source_name,
        fallback_used=fallback_used,
        existing_dates=len(existing_dates),
        provider_bars=len(candidate_dates),
        inserted_bars=inserted,
        repaired_existing_dates=len([day for day in insert_dates if day in repair_dates]),
        deleted_stale_dates=deleted,
        first_inserted_date=insert_dates[0] if insert_dates else None,
        last_inserted_date=insert_dates[-1] if insert_dates else None,
        warnings=warnings,
    )


def _fetch_bars(
    *,
    provider: DailyBarProvider,
    fallback_provider: DailyBarProvider | None,
    symbol: str,
    start_date: date,
    end_date: date,
    source_name: str,
    source_priority: int,
    fallback_source_name: str | None,
    fallback_source_priority: int | None,
) -> tuple[list[PriceBar], str, int, bool, list[str]]:
    try:
        bars = provider.fetch_daily_bars(symbol, start_date, end_date)
    except Exception as exc:
        if fallback_provider is None:
            return [], source_name, source_priority, False, [
                f"{symbol}: {source_name} daily backfill failed for {start_date} to {end_date}: {exc}"
            ]
        fallback_bars, fallback_warnings = _fetch_fallback(
            fallback_provider=fallback_provider,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            primary_source_name=source_name,
            primary_error=exc,
            fallback_source_name=fallback_source_name or "fallback",
        )
        return (
            fallback_bars,
            fallback_source_name or "fallback",
            fallback_source_priority if fallback_source_priority is not None else source_priority + 10,
            True,
            fallback_warnings,
        )
    eligible_bars = [bar for bar in bars if start_date <= bar.trade_date <= end_date]
    if eligible_bars or fallback_provider is None:
        return bars, source_name, source_priority, False, []

    fallback_bars, fallback_warnings = _fetch_fallback(
        fallback_provider=fallback_provider,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        primary_source_name=source_name,
        primary_error=None,
        fallback_source_name=fallback_source_name or "fallback",
    )
    return (
        fallback_bars,
        fallback_source_name or "fallback",
        fallback_source_priority if fallback_source_priority is not None else source_priority + 10,
        True,
        fallback_warnings,
    )


def _fetch_fallback(
    *,
    fallback_provider: DailyBarProvider,
    symbol: str,
    start_date: date,
    end_date: date,
    primary_source_name: str,
    primary_error: Exception | None,
    fallback_source_name: str,
) -> tuple[list[PriceBar], list[str]]:
    try:
        fallback_bars = fallback_provider.fetch_daily_bars(symbol, start_date, end_date)
    except Exception as exc:
        primary_detail = f"{primary_source_name} failed: {primary_error}; " if primary_error is not None else ""
        return [], [f"{symbol}: {primary_detail}{fallback_source_name} fallback failed: {exc}"]
    eligible_bars = [bar for bar in fallback_bars if start_date <= bar.trade_date <= end_date]
    if not eligible_bars:
        primary_detail = f"{primary_source_name} returned no bars; " if primary_error is None else f"{primary_source_name} failed: {primary_error}; "
        return [], [f"{symbol}: {primary_detail}{fallback_source_name} fallback returned no bars."]
    primary_detail = f"{primary_source_name} failed: {primary_error}; " if primary_error is not None else f"{primary_source_name} returned no bars; "
    return fallback_bars, [f"{symbol}: {primary_detail}used {fallback_source_name} fallback."]


def _dedupe(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        deduped.append(message)
    return deduped


def _existing_daily_row_needs_repair(row: dict[str, object]) -> bool:
    quality_flags = row.get("quality_flags")
    if captured_before_close(row):
        return True
    if isinstance(quality_flags, list) and any(str(flag).lower() in {"carry_forward", "stale", "stale_carry_forward"} for flag in quality_flags):
        return True
    volume = _float(row.get("volume"))
    open_price = _float(row.get("open"))
    high = _float(row.get("high"))
    low = _float(row.get("low"))
    close = _float(row.get("close"))
    if None not in {open_price, high, low, close} and not low <= min(open_price, close) <= max(open_price, close) <= high:
        return True
    if volume == 0 and None not in {open_price, high, low, close}:
        return open_price == high == low == close
    return False


def _float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
