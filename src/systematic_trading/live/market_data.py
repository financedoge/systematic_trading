from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol, Sequence

from pydantic import BaseModel, Field

from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.daily_quality import completed_session, valid_ohlc
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import PriceBar
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.interfaces import MarketDataStore


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
    store: MarketDataStore,
    target_date: date,
    symbols: Sequence[str] | None = None,
    provider: DailyBarProvider | None = None,
    fallback_provider: DailyBarProvider | None = None,
    fx_provider: DailyBarProvider | None = None,
    source: str = "yahoo",
    fallback_source: str = "ib",
    allow_stale_carry_forward: bool = False,
    carry_forward_max_calendar_days: int = 4,
    fx_currencies: Sequence[Currency] = (Currency.USD,),
    repair_history: bool = True,
) -> MarketDataRefreshResult:
    """Refresh observed data only; legacy carry-forward options never authorize synthetic writes."""
    price_provider = provider or YahooChartProvider(adjust_prices=True)
    if fx_provider is None:
        from systematic_trading.config import AppSettings
        from systematic_trading.data.ib_fx import IbFxDailyBarProvider
        fx_provider = IbFxDailyBarProvider(AppSettings())
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
        start_date = _next_missing_price_date(store, symbol, target_date, repair_history=repair_history)
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
            eligible_bars = [bar for bar in bars if start_date <= bar.trade_date <= target_date and completed_session(bar.trade_date) and valid_ohlc(bar)]
            for bar in eligible_bars:
                store.upsert_price_bar(symbol, bar)
            symbol_bars_upserted += len(eligible_bars)
            if not eligible_bars:
                warnings.append(f"{symbol}: no new market bars returned for {start_date} to {target_date}.")

        if allow_stale_carry_forward and _latest_price_date(store, symbol) != target_date:
            warnings.append(f"{symbol}: stale close was not carried forward; synthetic bars cannot establish trading readiness.")

        if symbol_bars_upserted:
            bars_upserted += symbol_bars_upserted
            symbols_updated += 1

    from systematic_trading.live.fx import refresh_required_fx
    fx_result = refresh_required_fx(store=store, target_date=target_date, currencies=fx_currencies, provider=fx_provider)
    warnings.extend(fx_result.warnings)
    if allow_stale_carry_forward:
        warnings.extend(f"{currency}/CNH: stale FX was not carried forward; synthetic rates cannot establish trading readiness."
            for currency, latest in fx_result.latest_dates.items() if latest != target_date)
    latest_dates = list(fx_result.latest_dates.values())
    complete_fx_date = min(latest_dates) if latest_dates and all(latest_dates) else None

    return MarketDataRefreshResult(
        target_date=target_date,
        source=source,
        symbols_requested=len(refresh_symbols),
        symbols_updated=symbols_updated,
        bars_upserted=bars_upserted,
        fx_rates_upserted=fx_result.rates_upserted,
        carried_forward_price_bars=carried_forward_price_bars,
        carried_forward_fx_rates=0,
        latest_bar_date=_complete_bar_date(store, refresh_symbols),
        latest_fx_date=complete_fx_date,
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


def _next_missing_price_date(store: MarketDataStore, symbol: str, target_date: date, *, repair_history: bool = True) -> date | None:
    bars = store.list_price_bars(symbol)
    suspect = [bar.trade_date for bar in bars if bar.volume == 0 and bar.trade_date <= target_date and (repair_history or bar.trade_date == target_date)]
    if suspect:
        return min(suspect)
    if bars and bars[-1].trade_date >= target_date:
        return None
    if bars:
        return bars[-1].trade_date + timedelta(days=1)
    return date(2012, 1, 1)


def _latest_price_date(store: MarketDataStore, symbol: str) -> date | None:
    bars = store.list_price_bars(symbol)
    return bars[-1].trade_date if bars else None


def _next_missing_fx_date(store: MarketDataStore, currency: Currency, target_date: date) -> date | None:
    rates = store.list_fx_rates(currency)
    if rates and rates[-1].rate_date >= target_date:
        return None
    if rates:
        return rates[-1].rate_date + timedelta(days=1)
    return date(2012, 1, 1)


def _complete_bar_date(store: MarketDataStore, symbols: Sequence[str]) -> date | None:
    dates: list[date] = []
    for symbol in symbols:
        bars = store.list_price_bars(symbol)
        if not bars or bars[-1].volume == 0:
            return None
        dates.append(bars[-1].trade_date)
    return min(dates) if dates else None


def _latest_fx_date(store: MarketDataStore, currency: Currency) -> date | None:
    rates = store.list_fx_rates(currency)
    return rates[-1].rate_date if rates else None


def _dedupe(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        deduped.append(message)
    return deduped
