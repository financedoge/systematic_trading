from datetime import date
from decimal import Decimal

from systematic_trading.config import AppSettings
from systematic_trading.data.ib import IbHistoricalDailyBarProvider
from systematic_trading.domain.market import PriceBar


def test_ib_historical_daily_bar_provider_uses_market_data_client_id(tmp_path) -> None:
    fake_client = _FakeHistoricalClient()
    provider = IbHistoricalDailyBarProvider(
        AppSettings(
            database_path=tmp_path / "ib_market_data.db",
            ib_client_id=101,
            ib_market_data_client_id=222,
        ),
        client=fake_client,
    )

    bars = provider.fetch_daily_bars("hyxu", date(2026, 5, 19), date(2026, 5, 19))

    assert bars == [_bar(date(2026, 5, 19), Decimal("53.31"))]
    assert fake_client.calls[0]["profile"].client_id == 222
    assert fake_client.calls[0]["profile"].environment.value == "paper"
    assert fake_client.calls[0]["symbol"] == "HYXU"


class _FakeHistoricalClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch_daily_bars(self, profile, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        self.calls.append(
            {
                "profile": profile,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return [_bar(end_date, Decimal("53.31"))]


def _bar(trade_date: date, close: Decimal) -> PriceBar:
    return PriceBar(
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )
