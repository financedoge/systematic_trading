"""Request-local market history for Strategy monitoring and reports."""
from bisect import bisect_left, bisect_right
from datetime import date

from systematic_trading.domain import Currency, FXRate, PriceBar
from systematic_trading.storage.interfaces import MarketDataStore


class StrategyMarketDataView:
    """Read each history once, then serve inclusive dated slices in memory.

    Instances must belong to one request. No cross-request cache hides backfills
    or revised FX, and slicing prevents later observations entering older marks.
    """

    def __init__(self, store: MarketDataStore) -> None:
        self._store = store
        self._prices: dict[str, tuple[list[date], list[PriceBar]]] = {}
        self._fx: dict[tuple[Currency, Currency], tuple[list[date], list[FXRate]]] = {}

    def latest_pnl_baseline(self):
        return self._store.latest_pnl_baseline()

    def list_price_bars(self, symbol: str, *, start_date: date | None = None,
                        end_date: date | None = None) -> list[PriceBar]:
        symbol = symbol.upper()
        if symbol not in self._prices:
            rows = self._store.list_price_bars(symbol)
            self._prices[symbol] = ([row.trade_date for row in rows], rows)
        dates, rows = self._prices[symbol]
        return rows[bisect_left(dates, start_date) if start_date else 0:
                    bisect_right(dates, end_date) if end_date else len(rows)]

    def list_fx_rates(self, base_currency: Currency, *, quote_currency: Currency = Currency.CNH,
                      start_date: date | None = None, end_date: date | None = None) -> list[FXRate]:
        key = (base_currency, quote_currency)
        if key not in self._fx:
            rows = self._store.list_fx_rates(base_currency, quote_currency=quote_currency)
            self._fx[key] = ([row.rate_date for row in rows], rows)
        dates, rows = self._fx[key]
        return rows[bisect_left(dates, start_date) if start_date else 0:
                    bisect_right(dates, end_date) if end_date else len(rows)]
