from __future__ import annotations

from threading import Event

import pytest

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import BrokerConnectionProfile
from systematic_trading.recorders import IbApiMarketDataRecorderClient
from systematic_trading.recorders.ib import _TradeBarAccumulator, _parse_rt_volume


def test_historical_timeout_does_not_abort_later_symbols() -> None:
    app = _FakeIbApp(timeout_symbol="SPY")
    client = _client_with_app(app)

    result = client.record_historical_bars(
        profile=_profile(),
        symbols=["SPY", "QQQ"],
        recorder=_RecorderNotes(),
        duration="60 S",
        request_spacing_seconds=0,
    )

    assert result.completed_successfully is False
    assert result.failed_symbols == ["SPY"]
    assert result.symbols_with_data == ["QQQ"]
    assert result.requests_completed == 1
    assert app.requested_symbols == ["SPY", "QQQ"]


def test_historical_live_channel_reports_per_symbol_coverage() -> None:
    app = _FakeIbApp()
    client = _client_with_app(app)

    result = client.record_historical_live_bars(
        profile=_profile(),
        symbols=["SPY", "QQQ"],
        recorder=_RecorderNotes(),
        duration_seconds=0.01,
        request_spacing_seconds=0,
    )

    assert result.completed_successfully is True
    assert result.feed_channel == "reqHistoricalData.keepUpToDate"
    assert result.failed_symbols == []
    assert result.bars_by_symbol == {"QQQ": 1, "SPY": 1}
    assert result.subscriptions_started == 2
    assert result.subscriptions_cancelled == 2
    assert app.keep_up_to_date == [True, True]


def test_delayed_trade_channel_reports_per_symbol_coverage() -> None:
    app = _FakeIbApp()
    client = _client_with_app(app)

    result = client.record_delayed_trade_bars(
        profile=_profile(),
        symbols=["SPY", "QQQ"],
        recorder=_RecorderNotes(),
        duration_seconds=0.01,
        request_spacing_seconds=0,
    )

    assert result.completed_successfully is True
    assert result.feed_channel == "reqMktData.delayedTrades"
    assert result.bars_by_symbol == {"QQQ": 1, "SPY": 1}
    assert app.generic_ticks == ["233", "233"]


def test_rt_volume_trade_aggregation_preserves_exchange_time_and_ohlcv() -> None:
    first = _parse_rt_volume("512.10;100;1783951200000;1000;512.05;true")
    second = _parse_rt_volume("512.30;50;1783951201000;1050;512.06;true")

    assert first is not None
    assert second is not None
    first_price, first_size, exchange_timestamp = first
    second_price, second_size, _ = second
    bar = _TradeBarAccumulator.start(exchange_timestamp, first_price, first_size)
    bar.add(second_price, second_size)

    assert str(bar.open) == "512.10"
    assert str(bar.high) == "512.30"
    assert str(bar.low) == "512.10"
    assert str(bar.close) == "512.30"
    assert bar.volume == 150
    assert bar.count == 2
    assert str(bar.wap.quantize(first_price)) == "512.17"


def _client_with_app(app: "_FakeIbApp") -> IbApiMarketDataRecorderClient:
    client = IbApiMarketDataRecorderClient(
        historical_timeout_seconds=0.01,
        sleep_seconds=0.001,
    )
    client._connect_app = lambda profile, recorder: app  # type: ignore[method-assign]
    client._disconnect_app = lambda connected_app, recorder: None  # type: ignore[method-assign]
    return client


def _profile() -> BrokerConnectionProfile:
    return BrokerConnectionProfile(
        environment=OrderEnvironment.PAPER,
        host="127.0.0.1",
        port=7497,
        client_id=121,
        enabled=True,
    )


class _FakeIbApp:
    def __init__(self, *, timeout_symbol: str | None = None) -> None:
        self.timeout_symbol = timeout_symbol
        self.requested_mode = None
        self.request_symbols: dict[int, str] = {}
        self.max_bars_by_request: dict[int, int | None] = {}
        self.bar_size_seconds_by_request: dict[int, int | None] = {}
        self.done_events: dict[int, Event] = {}
        self.request_errors: dict[int, str] = {}
        self.cancelled_request_ids: set[int] = set()
        self.bars_by_symbol: dict[str, int] = {}
        self.last_activity_monotonic_by_request: dict[int, float] = {}
        self.historical_live_requests: set[int] = set()
        self.historical_initial_max_bars_by_request: dict[int, int] = {}
        self.errors: list[str] = []
        self.bars_seen = 0
        self.requested_symbols: list[str] = []
        self.keep_up_to_date: list[bool] = []
        self.generic_ticks: list[str] = []

    def reqMarketDataType(self, market_data_type: int) -> None:
        return None

    def reqHistoricalData(
        self,
        request_id: int,
        contract: object,
        end_datetime: str,
        duration: str,
        bar_size: str,
        what_to_show: str,
        use_rth: int,
        format_date: int,
        keep_up_to_date: bool,
        options: list[object],
    ) -> None:
        symbol = self.request_symbols[request_id]
        self.requested_symbols.append(symbol)
        self.keep_up_to_date.append(keep_up_to_date)
        if symbol == self.timeout_symbol:
            return
        self.bars_by_symbol[symbol] = 1
        self.bars_seen += 1
        self.done_events[request_id].set()

    def cancelHistoricalData(self, request_id: int) -> None:
        return None

    def flush_completed_historical_update(self, request_id: int) -> None:
        return None

    def reqMktData(
        self,
        request_id: int,
        contract: object,
        generic_ticks: str,
        snapshot: bool,
        regulatory_snapshot: bool,
        options: list[object],
    ) -> None:
        symbol = self.request_symbols[request_id]
        self.generic_ticks.append(generic_ticks)
        self.bars_by_symbol[symbol] = 1
        self.bars_seen += 1

    def cancelMktData(self, request_id: int) -> None:
        return None

    def flush_delayed_trade_bar(self, request_id: int) -> None:
        return None


class _RecorderNotes:
    def note_pacing_sleep(self, seconds: float) -> None:
        return None

    def note_subscription_started(self, **kwargs: object) -> None:
        return None

    def note_subscription_cancelled(self, **kwargs: object) -> None:
        return None

    def note_error(self, code: str | int, message: str | None = None) -> None:
        return None


@pytest.mark.parametrize("channel", ["realtime", "historical", "delayed"])
def test_fractional_volume_warning_keeps_capture_alive_and_flags_affected_bars(monkeypatch, channel):
    from datetime import UTC, datetime
    from decimal import Decimal
    from types import SimpleNamespace

    from ibapi.client import EClient
    from systematic_trading.recorders.market_data import CaptureMode, IBMarketDataMode

    # Exercise the real callback class without opening a network connection.
    monkeypatch.setattr(EClient, "connect", lambda app, *args: app.nextValidId(1))
    monkeypatch.setattr(EClient, "run", lambda app: None)
    recorder = _RecorderNotes()
    captured = []
    recorder.record_bar = captured.append
    app = IbApiMarketDataRecorderClient()._connect_app(_profile(), recorder=recorder)
    app.request_symbols.update({1: "SPY", 2: "QQQ"})
    app.error(1, 2176, "Warning: fractional size trimmed")
    app.error(1, 2176, "Warning: fractional size trimmed again")
    assert 1 not in app.request_errors
    assert 1 not in app.done_events
    assert len(app.errors) == 2

    for request_id in (1, 2):
        if channel == "realtime":
            app.realtimeBar(request_id, 1790337600, 100, 101, 99, 100, Decimal(5), Decimal(100), 1)
        elif channel == "historical":
            app.requested_mode = IBMarketDataMode.DELAYED
            app._record_historical_bar(request_id, SimpleNamespace(
                date="1790337600", open=100, high=101, low=99, close=100,
                volume=5, average=100, barCount=1,
            ), capture_mode=CaptureMode.HISTORICAL_BACKFILL)
        else:
            bar = _TradeBarAccumulator.start(datetime.fromtimestamp(1790337600, tz=UTC), Decimal(100), 5)
            app._record_delayed_trade_bar(request_id, bar)

    assert len(captured) == 2
    assert captured[0].quality_flags.count("ib_fractional_volume_rounded") == 1
    assert "ib_fractional_volume_rounded" not in captured[1].quality_flags
    if channel == "delayed":
        assert captured[0].market_data_mode == IBMarketDataMode.DELAYED
        assert "ib_delayed_trade_aggregate" in captured[0].quality_flags
    # Subscription failures must still terminate their request.
    app.error(2, 10089, "Requested market data requires additional subscription")
    assert 2 in app.request_errors
    assert app.done_events[2].is_set()
