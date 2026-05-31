from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from math import ceil
from threading import Event, Thread
from typing import Protocol

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import PriceBar
from systematic_trading.execution.broker import BrokerConnectionProfile, InteractiveBrokersAdapter


class IBHistoricalDataClient(Protocol):
    def fetch_daily_bars(
        self,
        profile: BrokerConnectionProfile,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[PriceBar]:
        """Fetch adjusted daily bars from Interactive Brokers."""


class IbHistoricalDailyBarProvider:
    """Daily-bar provider backed by the configured IB paper connection."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        client: IBHistoricalDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.adapter = InteractiveBrokersAdapter(settings)
        self.client = client

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        profile = self.adapter.profile_for(self.settings.default_environment).model_copy(
            update={"client_id": self.settings.ib_market_data_client_id or self.settings.ib_client_id + 20}
        )
        client = self.client or IbApiHistoricalDataClient()
        return client.fetch_daily_bars(profile, symbol.upper(), start_date, end_date)


class IbApiHistoricalDataClient:
    def __init__(
        self,
        *,
        connection_timeout_seconds: float = 10.0,
        historical_timeout_seconds: float = 30.0,
    ) -> None:
        self.connection_timeout_seconds = connection_timeout_seconds
        self.historical_timeout_seconds = historical_timeout_seconds

    def fetch_daily_bars(
        self,
        profile: BrokerConnectionProfile,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[PriceBar]:
        if end_date < start_date:
            return []
        try:
            from ibapi.client import EClient
            from ibapi.contract import Contract
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB market data fallback requires the ibapi package. Install the optional IB dependency first.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = Event()
                self.done = Event()
                self.errors: list[str] = []
                self.bars: list[PriceBar] = []

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.ready.set()

            def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
                try:
                    trade_date = _parse_ib_bar_date(str(getattr(bar, "date", "") or ""))
                    open_price = Decimal(str(getattr(bar, "open", "0")))
                    high = Decimal(str(getattr(bar, "high", "0")))
                    low = Decimal(str(getattr(bar, "low", "0")))
                    close = Decimal(str(getattr(bar, "close", "0")))
                    volume = int(Decimal(str(getattr(bar, "volume", "0") or "0")))
                except (ValueError, ArithmeticError):
                    return
                if min(open_price, high, low, close) <= 0:
                    return
                self.bars.append(
                    PriceBar(
                        trade_date=trade_date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=max(volume, 0),
                    )
                )

            def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
                self.done.set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                self.errors.append(f"{reqId}:{errorCode}:{errorString}")
                if reqId >= 0 and errorCode not in {2104, 2106, 2158}:
                    self.done.set()

        app = _App()
        app.connect(profile.host, profile.port, profile.client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        try:
            if not app.ready.wait(self.connection_timeout_seconds):
                raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")

            contract = Contract()
            contract.symbol = symbol.upper()
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = Currency.USD.value

            app.reqHistoricalData(
                92001,
                contract,
                _ib_end_datetime(end_date),
                _ib_duration(start_date, end_date),
                "1 day",
                "ADJUSTED_LAST",
                1,
                1,
                False,
                [],
            )
            if not app.done.wait(self.historical_timeout_seconds):
                recent_errors = app.errors[-5:]
                suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
                raise TimeoutError(f"Timed out waiting for IB historical daily bars for {symbol}.{suffix}")
            blocking_errors = [message for message in app.errors if not _is_ib_market_data_status(message)]
            if blocking_errors and not app.bars:
                raise RuntimeError("; ".join(blocking_errors[-5:]))
            return sorted(
                [bar for bar in app.bars if start_date <= bar.trade_date <= end_date],
                key=lambda item: item.trade_date,
            )
        finally:
            app.disconnect()
            thread.join(timeout=2)


def _ib_end_datetime(value: date) -> str:
    end = datetime.combine(value, time(23, 59, 59), tzinfo=UTC)
    return end.strftime("%Y%m%d %H:%M:%S UTC")


def _ib_duration(start_date: date, end_date: date) -> str:
    days = max((end_date - start_date).days + 1, 1)
    if days <= 7:
        return "1 W"
    if days <= 31:
        return "1 M"
    if days <= 365:
        return "1 Y"
    return f"{ceil(days / 365)} Y"


def _parse_ib_bar_date(value: str) -> date:
    text = value.strip()
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    return datetime.fromtimestamp(int(text), tz=UTC).date()


def _is_ib_market_data_status(message: str) -> bool:
    return any(f":{code}:" in message for code in (2104, 2106, 2158))
