from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from systematic_trading.backtest.risk import realized_volatility
from systematic_trading.domain.market import PriceBar


def close_to_close_returns(bars: Sequence[PriceBar]) -> list[Decimal]:
    ordered = sorted(bars, key=lambda item: item.trade_date)
    returns: list[Decimal] = []
    for previous, current in zip(ordered, ordered[1:]):
        returns.append((current.close / previous.close) - Decimal("1"))
    return returns


def realized_volatility_from_bars(bars: Sequence[PriceBar], *, periods_per_year: int = 252) -> Decimal:
    return realized_volatility(close_to_close_returns(bars), periods_per_year=periods_per_year)
