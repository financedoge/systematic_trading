from datetime import date
from decimal import Decimal

from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.market_data import (
    DAILY_BARS_TABLE,
    ClickHouseMarketDataStore,
    backfill_clickhouse_daily_bars,
    daily_bar_row,
)


class _FakeClickHouseDailyClient:
    def __init__(self, existing_dates: list[str] | None = None, existing_rows: list[dict] | None = None) -> None:
        self.existing_dates = existing_dates or []
        self.existing_rows = existing_rows
        self.inserted_rows: list[dict] = []
        self.deleted_dates: list[str] = []
        self.ensure_called = False

    def ensure_daily_bars_table(self) -> None:
        self.ensure_called = True

    def query_daily_bar_dates(self, *, symbol: str, start_date: str | None = None, end_date: str | None = None) -> list[str]:
        return list(self.existing_dates)

    def query_daily_bars(
        self,
        *,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50000,
    ) -> list[dict]:
        if self.existing_rows is not None:
            return list(self.existing_rows)
        return [
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1000,
                "quality_flags": [],
            }
            for trade_date in self.existing_dates
        ]

    def insert_daily_bar_rows(self, rows) -> int:
        materialized = list(rows)
        self.inserted_rows.extend(materialized)
        return len(materialized)

    def delete_daily_bar_dates(self, *, symbol: str, trade_dates) -> int:
        materialized = list(trade_dates)
        self.deleted_dates.extend(materialized)
        return len(materialized)


class _StaticDailyProvider:
    def __init__(self, bars: list[PriceBar] | None = None, error: Exception | None = None) -> None:
        self.bars = bars or []
        self.error = error

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        if self.error is not None:
            raise self.error
        return list(self.bars)


class _FakeClickHouseStoreClient:
    def __init__(self) -> None:
        self.daily_rows: list[dict] = []
        self.fx_rows: list[dict] = []
        self.ensure_daily_called = False
        self.ensure_fx_called = False

    def ensure_daily_bars_table(self) -> None:
        self.ensure_daily_called = True

    def ensure_fx_rates_table(self) -> None:
        self.ensure_fx_called = True

    def insert_daily_bar_rows(self, rows) -> int:
        materialized = list(rows)
        self.daily_rows.extend(materialized)
        return len(materialized)

    def query_daily_bars(self, *, symbol: str, start_date: str | None = None, end_date: str | None = None, limit: int = 50000):
        return list(self.daily_rows)

    def insert_fx_rate_rows(self, rows) -> int:
        materialized = list(rows)
        self.fx_rows.extend(materialized)
        return len(materialized)

    def query_fx_rates(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        return list(self.fx_rows)


def test_daily_bar_row_maps_price_bar_for_clickhouse_golden_source() -> None:
    row = daily_bar_row(
        symbol="spy",
        bar=PriceBar(
            trade_date=date(2026, 7, 10),
            open=Decimal("750.00"),
            high=Decimal("752.00"),
            low=Decimal("749.00"),
            close=Decimal("751.28"),
            volume=12345,
        ),
        source_name="sqlite_price_bars",
        quality_flags=["from_sqlite"],
    )

    assert DAILY_BARS_TABLE == "market_data.daily_bars"
    assert row["symbol"] == "SPY"
    assert row["trade_date"] == "2026-07-10"
    assert row["close"] == 751.28
    assert row["source_name"] == "sqlite_price_bars"
    assert row["quality_flags"] == ["from_sqlite"]
    assert row["payload_hash"].startswith("sha256:")


def test_clickhouse_market_data_store_round_trips_price_bars_and_fx_rates() -> None:
    client = _FakeClickHouseStoreClient()
    store = ClickHouseMarketDataStore(client)  # type: ignore[arg-type]
    bar = _price_bar(date(2026, 7, 10), "624")
    rate = FXRate(rate_date=date(2026, 7, 10), base_currency=Currency.USD, rate=Decimal("7.20"))

    store.initialize()
    store.upsert_price_bar("spy", bar)
    store.upsert_fx_rate(rate)

    bars = store.list_price_bars("SPY")
    rates = store.list_fx_rates(Currency.USD)
    assert client.ensure_daily_called is True
    assert client.ensure_fx_called is True
    assert bars == [bar]
    assert rates == [rate]


def test_backfill_clickhouse_daily_bars_inserts_missing_provider_dates_only() -> None:
    client = _FakeClickHouseDailyClient(existing_dates=["2026-07-09"])
    provider = _StaticDailyProvider(
        [
            _price_bar(date(2026, 7, 9), "622"),
            _price_bar(date(2026, 7, 10), "624"),
        ]
    )

    result = backfill_clickhouse_daily_bars(
        client=client,
        provider=provider,
        symbols=["spy"],
        start_date=date(2026, 7, 9),
        end_date=date(2026, 7, 10),
        source_name="yahoo_adjusted",
        source_priority=80,
    )

    assert client.ensure_called is True
    assert result.symbols_requested == 1
    assert result.symbols_updated == 1
    assert result.bars_inserted == 1
    assert result.results[0].provider_bars == 2
    assert result.results[0].existing_dates == 1
    assert result.results[0].first_inserted_date == date(2026, 7, 10)
    assert client.inserted_rows[0]["symbol"] == "SPY"
    assert client.inserted_rows[0]["trade_date"] == "2026-07-10"
    assert client.inserted_rows[0]["source_name"] == "yahoo_adjusted"
    assert client.inserted_rows[0]["quality_flags"] == ["daily_backfill"]


def test_backfill_clickhouse_daily_bars_uses_fallback_provider() -> None:
    client = _FakeClickHouseDailyClient(existing_dates=[])
    provider = _StaticDailyProvider(error=RuntimeError("primary unavailable"))
    fallback = _StaticDailyProvider([_price_bar(date(2026, 7, 10), "624")])

    result = backfill_clickhouse_daily_bars(
        client=client,
        provider=provider,
        fallback_provider=fallback,
        symbols=["SPY"],
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 10),
        source_name="yahoo_adjusted",
        fallback_source_name="interactive_brokers_adjusted_last",
        fallback_source_priority=90,
    )

    assert result.bars_inserted == 1
    assert result.results[0].fallback_used is True
    assert result.results[0].source_name == "interactive_brokers_adjusted_last"
    assert "used interactive_brokers_adjusted_last fallback" in result.warnings[0]
    assert client.inserted_rows[0]["source_name"] == "interactive_brokers_adjusted_last"


def test_backfill_clickhouse_daily_bars_repairs_stale_zero_volume_rows() -> None:
    client = _FakeClickHouseDailyClient(
        existing_rows=[
            {
                "symbol": "SPY",
                "trade_date": "2026-06-01",
                "open": 745.7,
                "high": 745.7,
                "low": 745.7,
                "close": 745.7,
                "volume": 0,
                "quality_flags": [],
            }
        ]
    )
    provider = _StaticDailyProvider([_price_bar(date(2026, 6, 1), "756.59")])

    result = backfill_clickhouse_daily_bars(
        client=client,
        provider=provider,
        symbols=["SPY"],
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 1),
        source_name="yahoo_adjusted",
    )

    assert result.bars_inserted == 1
    assert result.results[0].repaired_existing_dates == 1
    assert client.inserted_rows[0]["trade_date"] == "2026-06-01"
    assert client.inserted_rows[0]["close"] == 756.59


def test_backfill_clickhouse_daily_bars_deletes_stale_dates_absent_from_provider() -> None:
    client = _FakeClickHouseDailyClient(
        existing_rows=[
            {
                "symbol": "SPY",
                "trade_date": "2026-05-25",
                "open": 745.7,
                "high": 745.7,
                "low": 745.7,
                "close": 745.7,
                "volume": 0,
                "quality_flags": [],
            },
            {
                "symbol": "SPY",
                "trade_date": "2026-05-26",
                "open": 745.7,
                "high": 745.7,
                "low": 745.7,
                "close": 745.7,
                "volume": 0,
                "quality_flags": [],
            },
        ]
    )
    provider = _StaticDailyProvider([_price_bar(date(2026, 5, 26), "751.00")])

    result = backfill_clickhouse_daily_bars(
        client=client,
        provider=provider,
        symbols=["SPY"],
        start_date=date(2026, 5, 25),
        end_date=date(2026, 5, 26),
        source_name="yahoo_adjusted",
    )

    assert result.bars_inserted == 1
    assert result.results[0].repaired_existing_dates == 1
    assert result.results[0].deleted_stale_dates == 1
    assert client.inserted_rows[0]["trade_date"] == "2026-05-26"
    assert client.deleted_dates == ["2026-05-25"]


def _price_bar(trade_date: date, close: str) -> PriceBar:
    return PriceBar(
        trade_date=trade_date,
        open=Decimal("620"),
        high=Decimal("625"),
        low=Decimal("619"),
        close=Decimal(close),
        volume=1000,
    )
