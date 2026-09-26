from __future__ import annotations

from datetime import date
from decimal import Decimal

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.daily_quality import completed_session, captured_before_close
from systematic_trading.market_data.golden import ClickHouseMarketDataClient, daily_bar_row, fx_rate_row


class ClickHouseMarketDataStore:
    def __init__(
        self,
        client: ClickHouseMarketDataClient,
        *,
        source_name: str = "platform_market_data_store",
        source_priority: int = 60,
    ) -> None:
        self.client = client
        self.source_name = source_name
        self.source_priority = source_priority

    @classmethod
    def from_settings(cls, settings: AppSettings) -> ClickHouseMarketDataStore:
        return cls(
            ClickHouseMarketDataClient(
                settings.clickhouse_http_url,
                database=settings.clickhouse_database,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password,
            )
        )

    def initialize(self) -> None:
        self.client.ensure_daily_bars_table()
        self.client.ensure_fx_rates_table()

    def upsert_price_bar(self, symbol: str, bar: PriceBar) -> PriceBar:
        self.client.ensure_daily_bars_table()
        self.client.insert_daily_bar_rows(
            [
                daily_bar_row(
                    symbol=symbol,
                    bar=bar,
                    source_name=self.source_name,
                    source_priority=self.source_priority,
                    quality_flags=["platform_write"],
                )
            ]
        )
        return bar

    def list_price_bars(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PriceBar]:
        rows = self.client.query_daily_bars(
            symbol=symbol,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            limit=50000,
        )
        return [
            PriceBar(
                trade_date=date.fromisoformat(str(row["trade_date"])),
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
            )
            for row in rows
            if completed_session(date.fromisoformat(str(row["trade_date"]))) and not captured_before_close(row)
        ]

    def upsert_fx_rate(self, rate: FXRate) -> FXRate:
        self.client.ensure_fx_rates_table()
        self.client.insert_fx_rate_rows(
            [
                fx_rate_row(
                    rate=rate,
                    source_name=self.source_name,
                    source_priority=self.source_priority,
                    quality_flags=["platform_write"],
                )
            ]
        )
        return rate

    def list_fx_rates(
        self,
        base_currency: Currency,
        *,
        quote_currency: Currency = Currency.CNH,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[FXRate]:
        rows = self.client.query_fx_rates(
            base_currency=base_currency.value,
            quote_currency=quote_currency.value,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        return [
            FXRate(
                rate_date=date.fromisoformat(str(row["rate_date"])),
                base_currency=Currency(str(row["base_currency"])),
                quote_currency=Currency(str(row["quote_currency"])),
                rate=Decimal(str(row["rate"])),
            )
            for row in rows
        ]
