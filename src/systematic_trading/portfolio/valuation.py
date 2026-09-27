"""Shared observed-mark policy; unsupported/stale observations remain unavailable."""
from datetime import date

from systematic_trading.domain.enums import Currency
from systematic_trading.live.trading_calendar import is_us_trading_day, previous_us_trading_day


def valuation_session(day: date) -> date:
    return day if is_us_trading_day(day) else previous_us_trading_day(day)


def price(store, symbol, day, warnings):
    rows = store.list_price_bars(symbol, end_date=day)
    if not rows or rows[-1].trade_date < valuation_session(day):
        warnings.append(f"{symbol}: missing or stale price for {valuation_session(day)}; valuation unavailable.")
        return None
    return rows[-1].close


def fx_rate(store, currency, day, warnings):
    if currency == Currency.CNH:
        from decimal import Decimal
        return Decimal(1)
    rows = store.list_fx_rates(currency, end_date=day)
    if not rows or rows[-1].rate_date < valuation_session(day):
        warnings.append(f"{currency.value}/CNH: missing or stale FX for {valuation_session(day)}; valuation unavailable.")
        return None
    return rows[-1].rate
