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


def test_adjusted_history_uses_empty_endpoint_and_filters_requested_dates(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    from systematic_trading.data.ib import IbApiHistoricalDataClient

    calls = []
    class Client:
        def __init__(self, wrapper): self.wrapper = wrapper
        def connect(self, *args): self.wrapper.nextValidId(1)
        def run(self): pass
        def disconnect(self): pass
        def reqHistoricalData(self, *args):
            calls.append(args)
            for stamp in ('20250102', '20250103', '20260925'):
                self.wrapper.historicalData(92001, SimpleNamespace(
                    date=stamp, open=100, high=101, low=99, close=100, volume=1000))
            self.wrapper.historicalDataEnd(92001, '', '')

    for module, name, value in [('client', 'EClient', Client), ('wrapper', 'EWrapper', type('Wrapper', (), {})),
                                ('contract', 'Contract', type('Contract', (), {}))]:
        fake = ModuleType('ibapi.' + module)
        setattr(fake, name, value)
        monkeypatch.setitem(sys.modules, 'ibapi.' + module, fake)
    profile = SimpleNamespace(host='localhost', port=4002, client_id=222)
    bars = IbApiHistoricalDataClient().fetch_daily_bars(profile, 'SPY', date(2025, 1, 2), date(2025, 1, 3))
    assert [b.trade_date for b in bars] == [date(2025, 1, 2), date(2025, 1, 3)]
    assert calls[0][2] == '' and calls[0][5] == 'ADJUSTED_LAST'
    IbApiHistoricalDataClient().fetch_daily_bars(profile, 'USD', date(2025, 1, 2), date(2025, 1, 3), forex_currency='CNH')
    assert calls[1][2] == '20250103 23:59:59 UTC' and calls[1][5] == 'MIDPOINT'
