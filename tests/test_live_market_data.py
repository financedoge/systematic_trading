from datetime import date
from decimal import Decimal

from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.live.market_data import refresh_sota_market_data
from systematic_trading.storage.sqlite import SQLiteStore


def test_refresh_sota_market_data_fetches_missing_bars_and_fx(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "market_refresh.db")
    store.initialize()
    store.upsert_price_bar("SPY", _bar(date(2026, 5, 18), Decimal("100")))
    store.upsert_fx_rate(FXRate(rate_date=date(2026, 5, 18), base_currency=Currency.USD, rate=Decimal("7.20")))
    price_provider = _FakeMarketDataProvider(
        {
            "SPY": [_bar(date(2026, 5, 19), Decimal("101"))],
            "TLT": [_bar(date(2026, 5, 19), Decimal("90"))],
        }
    )
    fx_provider = _FakeMarketDataProvider({"CNY=X": [_bar(date(2026, 5, 19), Decimal("7.21"))]})

    result = refresh_sota_market_data(
        store=store,
        target_date=date(2026, 5, 19),
        symbols=["SPY", "TLT"],
        provider=price_provider,
        fx_provider=fx_provider,
    )

    assert result.latest_bar_date == date(2026, 5, 19)
    assert result.latest_fx_date == date(2026, 5, 19)
    assert result.symbols_requested == 2
    assert result.symbols_updated == 2
    assert result.bars_upserted == 2
    assert result.fx_rates_upserted == 1
    assert store.list_price_bars("SPY")[-1].close == Decimal("101")
    assert store.list_price_bars("TLT")[-1].close == Decimal("90")
    assert store.list_fx_rates(Currency.USD)[-1].rate == Decimal("7.21")
    assert ("SPY", date(2026, 5, 19), date(2026, 5, 19)) in price_provider.requests
    assert ("TLT", date(2012, 1, 1), date(2026, 5, 19)) in price_provider.requests


def test_refresh_sota_market_data_uses_fallback_provider_when_primary_fails(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "market_refresh_fallback.db")
    store.initialize()
    store.upsert_price_bar("HYXU", _bar(date(2026, 5, 18), Decimal("53.29")))
    primary = _FailingMarketDataProvider(RuntimeError("HTTP Error 403: Forbidden"))
    fallback = _FakeMarketDataProvider({"HYXU": [_bar(date(2026, 5, 19), Decimal("53.31"))]})

    result = refresh_sota_market_data(
        store=store,
        target_date=date(2026, 5, 19),
        symbols=["HYXU"],
        provider=primary,
        fallback_provider=fallback,
        fx_provider=_FakeMarketDataProvider({}),
    )

    assert result.latest_bar_date == date(2026, 5, 19)
    assert result.symbols_updated == 1
    assert store.list_price_bars("HYXU")[-1].close == Decimal("53.31")
    assert any("used ib fallback" in warning for warning in result.warnings)
    assert fallback.requests == [("HYXU", date(2026, 5, 19), date(2026, 5, 19))]


def test_refresh_sota_market_data_carries_forward_missing_price_and_fx_when_providers_fail(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "market_refresh_carry_forward.db")
    store.initialize()
    store.upsert_price_bar("BWX", _bar(date(2026, 5, 19), Decimal("21.50")))
    store.upsert_fx_rate(FXRate(rate_date=date(2026, 5, 19), base_currency=Currency.USD, rate=Decimal("7.20")))
    primary = _FailingMarketDataProvider(RuntimeError("HTTP Error 429: Too Many Requests"))
    fallback = _FailingMarketDataProvider(TimeoutError("Timed out waiting for IB nextValidId callback"))
    fx_provider = _FailingMarketDataProvider(RuntimeError("HTTP Error 429: Too Many Requests"))

    result = refresh_sota_market_data(
        store=store,
        target_date=date(2026, 5, 20),
        symbols=["BWX"],
        provider=primary,
        fallback_provider=fallback,
        fx_provider=fx_provider,
        allow_stale_carry_forward=True,
    )

    assert result.latest_bar_date == date(2026, 5, 20)
    assert result.latest_fx_date == date(2026, 5, 20)
    assert result.bars_upserted == 1
    assert result.fx_rates_upserted == 1
    assert result.carried_forward_price_bars == 1
    assert result.carried_forward_fx_rates == 1
    carried_bar = store.list_price_bars("BWX")[-1]
    assert carried_bar.trade_date == date(2026, 5, 20)
    assert carried_bar.close == Decimal("21.50")
    assert carried_bar.volume == 0
    assert store.list_fx_rates(Currency.USD)[-1].rate == Decimal("7.20")
    assert any("BWX: carried forward stale close" in warning for warning in result.warnings)
    assert any("USD/CNH: carried forward stale FX rate" in warning for warning in result.warnings)


class _FakeMarketDataProvider:
    def __init__(self, bars_by_symbol: dict[str, list[PriceBar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.requests = []

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        self.requests.append((symbol, start_date, end_date))
        return [
            bar
            for bar in self.bars_by_symbol.get(symbol, [])
            if start_date <= bar.trade_date <= end_date
        ]


class _FailingMarketDataProvider:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.requests = []

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        self.requests.append((symbol, start_date, end_date))
        raise self.exc


def _bar(trade_date: date, close: Decimal) -> PriceBar:
    return PriceBar(
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )
