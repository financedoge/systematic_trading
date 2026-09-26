from __future__ import annotations

from datetime import date
import json

from systematic_trading.domain import Currency, FXRate, PriceBar, PnLSnapshot
from systematic_trading.storage.interfaces import MarketDataStore, TradingStore


class MarketDataRoutedTradingStore:
    def __init__(self, transactional_store: TradingStore, market_data_store: MarketDataStore) -> None:
        self.transactional_store = transactional_store
        self.market_data_store = market_data_store
        self.analytics = None

    def list_pnl_snapshots(self, *, limit: int = 100) -> list[PnLSnapshot]:
        if self.analytics is None:
            return self.transactional_store.list_pnl_snapshots(limit=limit)
        rows = self.analytics.observations("transactional-history", family="pnl_snapshot", limit=limit)
        return [PnLSnapshot.model_validate(json.loads(row["payload"])) for row in rows]

    def __getattr__(self, name: str):
        return getattr(self.transactional_store, name)

    def initialize(self) -> None:
        self.transactional_store.initialize()
        initializer = getattr(self.market_data_store, "initialize", None)
        if callable(initializer):
            initializer()

    def upsert_price_bar(self, symbol: str, bar: PriceBar) -> PriceBar:
        return self.market_data_store.upsert_price_bar(symbol, bar)

    def list_price_bars(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PriceBar]:
        return self.market_data_store.list_price_bars(symbol, start_date=start_date, end_date=end_date)

    def upsert_fx_rate(self, rate: FXRate) -> FXRate:
        return self.market_data_store.upsert_fx_rate(rate)

    def list_fx_rates(
        self,
        base_currency: Currency,
        *,
        quote_currency: Currency = Currency.CNH,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[FXRate]:
        return self.market_data_store.list_fx_rates(
            base_currency,
            quote_currency=quote_currency,
            start_date=start_date,
            end_date=end_date,
        )
