from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol, Sequence

from pydantic import BaseModel, Field

from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.sqlite import SQLiteStore


class DailyBarProvider(Protocol):
    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        """Fetch daily bars for one symbol."""


class MarketDataRefreshResult(BaseModel):
    refreshed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    target_date: date
    source: str = "yahoo"
    symbols_requested: int = 0
    symbols_updated: int = 0
    bars_upserted: int = 0
    fx_rates_upserted: int = 0
    carried_forward_price_bars: int = 0
    carried_forward_fx_rates: int = 0
    latest_bar_date: date | None = None
    latest_fx_date: date | None = None
    warnings: list[str] = Field(default_factory=list)


def refresh_sota_market_data(
    *,
    store: SQLiteStore,
    target_date: date,
    symbols: Sequence[str] | None = None,
    provider: DailyBarProvider | None = None,
    fallback_provider: DailyBarProvider | None = None,
    fx_provider: DailyBarProvider | None = None,
    source: str = "yahoo",
    fallback_source: str = "ib",
    allow_stale_carry_forward: bool = False,
    carry_forward_max_calendar_days: int = 4,
) -> MarketDataRefreshResult:
    price_provider = provider or YahooChartProvider(adjust_prices=True)
    currency_provider = fx_provider or YahooChartProvider()
    configured_instruments = instruments_for_definition(current_sota_definition())
    refresh_symbols = sorted({symbol.upper() for symbol in (symbols or configured_instruments)})
    warnings: list[str] = []
    bars_upserted = 0
    symbols_updated = 0
    carried_forward_price_bars = 0

    for symbol in refresh_symbols:
        instrument = configured_instruments.get(symbol)
        if instrument is not None:
            store.upsert_instrument(instrument)
        start_date = _next_missing_price_date(store, symbol, target_date)
        if start_date is None:
            continue
        bars, fetch_warnings = _fetch_price_bars(
            provider=price_provider,
            fallback_provider=fallback_provider,
            symbol=symbol,
            start_date=start_date,
            target_date=target_date,
            primary_source=source,
            fallback_source=fallback_source,
        )
        warnings.extend(fetch_warnings)
        symbol_bars_upserted = 0
        if bars is not None:
            eligible_bars = [bar for bar in bars if start_date <= bar.trade_date <= target_date]
            for bar in eligible_bars:
                store.upsert_price_bar(symbol, bar)
            symbol_bars_upserted += len(eligible_bars)
            if not eligible_bars:
                warnings.append(f"{symbol}: no new market bars returned for {start_date} to {target_date}.")

        if allow_stale_carry_forward and _latest_price_date(store, symbol) != target_date:
            carried_bars, carry_warnings = _carry_forward_price_bars(
                store,
                symbol,
                target_date=target_date,
                max_calendar_days=max(carry_forward_max_calendar_days, 0),
            )
            for bar in carried_bars:
                store.upsert_price_bar(symbol, bar)
            symbol_bars_upserted += len(carried_bars)
            carried_forward_price_bars += len(carried_bars)
            warnings.extend(carry_warnings)

        if symbol_bars_upserted:
            bars_upserted += symbol_bars_upserted
            symbols_updated += 1

    fx_rates_upserted = 0
    carried_forward_fx_rates = 0
    fx_start = _next_missing_fx_date(store, Currency.USD, target_date)
    if fx_start is not None:
        try:
            fx_bars = currency_provider.fetch_daily_bars("CNY=X", fx_start, target_date)
        except Exception as exc:
            warnings.append(f"USD/CNH market data refresh failed for {fx_start} to {target_date}: {exc}")
        else:
            for bar in fx_bars:
                if not (fx_start <= bar.trade_date <= target_date):
                    continue
                store.upsert_fx_rate(
                    FXRate(
                        rate_date=bar.trade_date,
                        base_currency=Currency.USD,
                        quote_currency=Currency.CNH,
                        rate=bar.close,
                    )
                )
                fx_rates_upserted += 1
            if not fx_rates_upserted:
                warnings.append(f"USD/CNH: no new FX bars returned for {fx_start} to {target_date}.")
        if allow_stale_carry_forward and _latest_fx_date(store, Currency.USD) != target_date:
            carried_rates, carry_warnings = _carry_forward_fx_rates(
                store,
                Currency.USD,
                target_date=target_date,
                max_calendar_days=max(carry_forward_max_calendar_days, 0),
            )
            for rate in carried_rates:
                store.upsert_fx_rate(rate)
            fx_rates_upserted += len(carried_rates)
            carried_forward_fx_rates += len(carried_rates)
            warnings.extend(carry_warnings)

    return MarketDataRefreshResult(
        target_date=target_date,
        source=source,
        symbols_requested=len(refresh_symbols),
        symbols_updated=symbols_updated,
        bars_upserted=bars_upserted,
        fx_rates_upserted=fx_rates_upserted,
        carried_forward_price_bars=carried_forward_price_bars,
        carried_forward_fx_rates=carried_forward_fx_rates,
        latest_bar_date=_complete_bar_date(store, refresh_symbols),
        latest_fx_date=_latest_fx_date(store, Currency.USD),
        warnings=_dedupe(warnings),
    )


def _fetch_price_bars(
    *,
    provider: DailyBarProvider,
    fallback_provider: DailyBarProvider | None,
    symbol: str,
    start_date: date,
    target_date: date,
    primary_source: str,
    fallback_source: str,
) -> tuple[list[PriceBar] | None, list[str]]:
    warnings: list[str] = []
    try:
        primary_bars = provider.fetch_daily_bars(symbol, start_date, target_date)
    except Exception as exc:
        primary_message = f"{symbol}: {primary_source} market data refresh failed for {start_date} to {target_date}: {exc}"
        if fallback_provider is None:
            return None, [primary_message]
        fallback_bars, fallback_message = _fetch_fallback_bars(
            fallback_provider=fallback_provider,
            symbol=symbol,
            start_date=start_date,
            target_date=target_date,
            fallback_source=fallback_source,
        )
        if fallback_bars:
            warnings.append(f"{primary_message}; used {fallback_source} fallback.")
            return fallback_bars, warnings
        warnings.append(f"{primary_message}; {fallback_message}")
        return None, warnings

    eligible_primary_bars = [bar for bar in primary_bars if start_date <= bar.trade_date <= target_date]
    if eligible_primary_bars or fallback_provider is None:
        return primary_bars, warnings

    fallback_bars, fallback_message = _fetch_fallback_bars(
        fallback_provider=fallback_provider,
        symbol=symbol,
        start_date=start_date,
        target_date=target_date,
        fallback_source=fallback_source,
    )
    if fallback_bars:
        warnings.append(
            f"{symbol}: {primary_source} returned no new market bars for {start_date} to {target_date}; used {fallback_source} fallback."
        )
        return fallback_bars, warnings
    warnings.append(f"{symbol}: no new market bars returned for {start_date} to {target_date}; {fallback_message}")
    return None, warnings


def _fetch_fallback_bars(
    *,
    fallback_provider: DailyBarProvider,
    symbol: str,
    start_date: date,
    target_date: date,
    fallback_source: str,
) -> tuple[list[PriceBar] | None, str]:
    try:
        fallback_bars = fallback_provider.fetch_daily_bars(symbol, start_date, target_date)
    except Exception as exc:
        return None, f"{fallback_source} fallback failed: {exc}"
    eligible_bars = [bar for bar in fallback_bars if start_date <= bar.trade_date <= target_date]
    if not eligible_bars:
        return None, f"{fallback_source} fallback returned no bars."
    return fallback_bars, f"{fallback_source} fallback returned {len(eligible_bars)} bar(s)."


def _next_missing_price_date(store: SQLiteStore, symbol: str, target_date: date) -> date | None:
    bars = store.list_price_bars(symbol)
    if bars and bars[-1].trade_date >= target_date:
        return None
    if bars:
        return bars[-1].trade_date + timedelta(days=1)
    return date(2012, 1, 1)


def _latest_price_date(store: SQLiteStore, symbol: str) -> date | None:
    bars = store.list_price_bars(symbol)
    return bars[-1].trade_date if bars else None


def _next_missing_fx_date(store: SQLiteStore, currency: Currency, target_date: date) -> date | None:
    rates = store.list_fx_rates(currency)
    if rates and rates[-1].rate_date >= target_date:
        return None
    if rates:
        return rates[-1].rate_date + timedelta(days=1)
    return date(2012, 1, 1)


def _carry_forward_price_bars(
    store: SQLiteStore,
    symbol: str,
    *,
    target_date: date,
    max_calendar_days: int,
) -> tuple[list[PriceBar], list[str]]:
    bars = store.list_price_bars(symbol)
    if not bars:
        return [], [f"{symbol}: cannot carry forward missing market data; no prior price bar exists."]
    source_bar = bars[-1]
    if source_bar.trade_date >= target_date:
        return [], []
    gap_days = (target_date - source_bar.trade_date).days
    if gap_days > max_calendar_days:
        return [], [
            f"{symbol}: cannot carry forward stale market data from {source_bar.trade_date} to {target_date}; "
            f"{gap_days} calendar days exceeds limit {max_calendar_days}."
        ]
    carried: list[PriceBar] = []
    for trade_date in _business_dates_after(source_bar.trade_date, target_date):
        carried.append(
            PriceBar(
                trade_date=trade_date,
                open=source_bar.close,
                high=source_bar.close,
                low=source_bar.close,
                close=source_bar.close,
                volume=0,
            )
        )
    if not carried:
        return [], []
    return carried, [
        f"{symbol}: carried forward stale close from {source_bar.trade_date} through {target_date} "
        "because live market data providers did not return current data."
    ]


def _carry_forward_fx_rates(
    store: SQLiteStore,
    currency: Currency,
    *,
    target_date: date,
    max_calendar_days: int,
) -> tuple[list[FXRate], list[str]]:
    rates = store.list_fx_rates(currency)
    if not rates:
        return [], [f"{currency.value}/CNH: cannot carry forward missing FX data; no prior rate exists."]
    source_rate = rates[-1]
    if source_rate.rate_date >= target_date:
        return [], []
    gap_days = (target_date - source_rate.rate_date).days
    if gap_days > max_calendar_days:
        return [], [
            f"{currency.value}/CNH: cannot carry forward stale FX data from {source_rate.rate_date} to {target_date}; "
            f"{gap_days} calendar days exceeds limit {max_calendar_days}."
        ]
    carried = [
        FXRate(
            rate_date=rate_date,
            base_currency=source_rate.base_currency,
            quote_currency=source_rate.quote_currency,
            rate=source_rate.rate,
        )
        for rate_date in _business_dates_after(source_rate.rate_date, target_date)
    ]
    if not carried:
        return [], []
    return carried, [
        f"{currency.value}/CNH: carried forward stale FX rate from {source_rate.rate_date} through {target_date} "
        "because live FX providers did not return current data."
    ]


def _complete_bar_date(store: SQLiteStore, symbols: Sequence[str]) -> date | None:
    dates: list[date] = []
    for symbol in symbols:
        bars = store.list_price_bars(symbol)
        if bars:
            dates.append(bars[-1].trade_date)
    return min(dates) if dates else None


def _latest_fx_date(store: SQLiteStore, currency: Currency) -> date | None:
    rates = store.list_fx_rates(currency)
    return rates[-1].rate_date if rates else None


def _business_dates_after(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    cursor = start_date + timedelta(days=1)
    while cursor <= end_date:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def _dedupe(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        deduped.append(message)
    return deduped
