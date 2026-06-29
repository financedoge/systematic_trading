from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Thread
from typing import Iterable
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.execution.broker import BrokerConnectionProfile
from systematic_trading.recorders.market_data import (
    CapturedMarketDataBar,
    CaptureMode,
    IBMarketDataMode,
    MarketDataRecorder,
    TokenBucket,
)


IB_MARKET_DATA_TYPE_CODES = {
    IBMarketDataMode.LIVE: 1,
    IBMarketDataMode.FROZEN: 2,
    IBMarketDataMode.DELAYED: 3,
    IBMarketDataMode.DELAYED_FROZEN: 4,
}
IB_MARKET_DATA_MODES_BY_CODE = {value: key for key, value in IB_MARKET_DATA_TYPE_CODES.items()}


class IBMarketDataRunResult(BaseModel):
    mode: str
    symbols_requested: list[str] = Field(default_factory=list)
    subscriptions_started: int = 0
    subscriptions_cancelled: int = 0
    requests_completed: int = 0
    bars_seen: int = 0
    errors: list[str] = Field(default_factory=list)


class IbApiMarketDataRecorderClient:
    def __init__(
        self,
        *,
        connection_timeout_seconds: float = 10.0,
        historical_timeout_seconds: float = 30.0,
        sleep_seconds: float = 0.25,
    ) -> None:
        self.connection_timeout_seconds = connection_timeout_seconds
        self.historical_timeout_seconds = historical_timeout_seconds
        self.sleep_seconds = sleep_seconds

    def record_realtime_bars(
        self,
        *,
        profile: BrokerConnectionProfile,
        symbols: Iterable[str],
        recorder: MarketDataRecorder,
        duration_seconds: float,
        market_data_mode: IBMarketDataMode = IBMarketDataMode.LIVE,
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        request_spacing_seconds: float = 10.0,
        request_rate_per_second: float = 5.0,
        request_burst: int = 10,
    ) -> IBMarketDataRunResult:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        requested_symbols = _normalize_symbols(symbols)
        app = self._connect_app(profile, recorder=recorder)
        app.requested_mode = market_data_mode
        app.reqMarketDataType(IB_MARKET_DATA_TYPE_CODES[market_data_mode])
        pacer = TokenBucket(rate_per_second=request_rate_per_second, burst=request_burst)
        request_ids: dict[int, str] = {}
        subscriptions_started = 0
        try:
            for index, symbol in enumerate(requested_symbols, start=1):
                if index > 1:
                    time.sleep(request_spacing_seconds)
                    recorder.note_pacing_sleep(request_spacing_seconds)
                sleep_time = pacer.consume()
                recorder.note_pacing_sleep(sleep_time)
                request_id = 93000 + index
                request_ids[request_id] = symbol
                app.request_symbols[request_id] = symbol
                app.reqRealTimeBars(
                    request_id,
                    _stock_contract(symbol),
                    5,
                    what_to_show,
                    1 if use_rth else 0,
                    [],
                )
                subscriptions_started += 1
                recorder.note_subscription_started(
                    symbol=symbol,
                    request_id=request_id,
                    market_data_mode=market_data_mode,
                    capture_mode=CaptureMode.STREAM,
                )
            deadline = time.monotonic() + duration_seconds
            while time.monotonic() < deadline:
                time.sleep(self.sleep_seconds)
        finally:
            subscriptions_cancelled = 0
            for request_id in request_ids:
                try:
                    app.cancelRealTimeBars(request_id)
                    subscriptions_cancelled += 1
                    recorder.note_subscription_cancelled(symbol=request_ids.get(request_id), request_id=request_id)
                except Exception as exc:  # pragma: no cover - defensive IB disconnect cleanup
                    app.errors.append(f"{request_id}:cancel:{exc}")
            self._disconnect_app(app, recorder)
        return IBMarketDataRunResult(
            mode="realtime",
            symbols_requested=requested_symbols,
            subscriptions_started=subscriptions_started,
            subscriptions_cancelled=subscriptions_cancelled,
            bars_seen=app.bars_seen,
            errors=app.errors,
        )

    def record_historical_bars(
        self,
        *,
        profile: BrokerConnectionProfile,
        symbols: Iterable[str],
        recorder: MarketDataRecorder,
        duration: str = "1 D",
        bar_size: str = "5 secs",
        end_datetime: str = "",
        market_data_mode: IBMarketDataMode = IBMarketDataMode.LIVE,
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        request_spacing_seconds: float = 10.0,
        request_rate_per_second: float = 5.0,
        request_burst: int = 10,
        max_bars_per_symbol: int | None = None,
    ) -> IBMarketDataRunResult:
        requested_symbols = _normalize_symbols(symbols)
        app = self._connect_app(profile, recorder=recorder)
        app.requested_mode = market_data_mode
        app.reqMarketDataType(IB_MARKET_DATA_TYPE_CODES[market_data_mode])
        pacer = TokenBucket(rate_per_second=request_rate_per_second, burst=request_burst)
        requests_completed = 0
        try:
            for index, symbol in enumerate(requested_symbols, start=1):
                if index > 1:
                    time.sleep(request_spacing_seconds)
                    recorder.note_pacing_sleep(request_spacing_seconds)
                sleep_time = pacer.consume()
                recorder.note_pacing_sleep(sleep_time)
                request_id = 94000 + index
                app.request_symbols[request_id] = symbol
                app.max_bars_by_request[request_id] = max_bars_per_symbol
                app.done_events[request_id] = Event()
                app.reqHistoricalData(
                    request_id,
                    _stock_contract(symbol),
                    end_datetime,
                    duration,
                    bar_size,
                    what_to_show,
                    1 if use_rth else 0,
                    2,
                    False,
                    [],
                )
                recorder.note_subscription_started(
                    symbol=symbol,
                    request_id=request_id,
                    market_data_mode=market_data_mode,
                    capture_mode=CaptureMode.HISTORICAL_BACKFILL,
                )
                if not app.done_events[request_id].wait(self.historical_timeout_seconds):
                    recent_errors = app.errors[-5:]
                    suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
                    raise TimeoutError(f"Timed out waiting for IB historical bars for {symbol}.{suffix}")
                requests_completed += 1
        finally:
            self._disconnect_app(app, recorder)
        return IBMarketDataRunResult(
            mode="historical",
            symbols_requested=requested_symbols,
            requests_completed=requests_completed,
            bars_seen=app.bars_seen,
            errors=app.errors,
        )

    def _connect_app(self, profile: BrokerConnectionProfile, *, recorder: MarketDataRecorder):
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB market data recorder requires the ibapi package. Install the optional IB dependency first.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = Event()
                self.errors: list[str] = []
                self.request_symbols: dict[int, str] = {}
                self.request_modes: dict[int, IBMarketDataMode] = {}
                self.done_events: dict[int, Event] = {}
                self.max_bars_by_request: dict[int, int | None] = {}
                self.bars_by_request: dict[int, int] = {}
                self.bars_seen = 0
                self.requested_mode = IBMarketDataMode.LIVE

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.ready.set()

            def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802
                mode = ib_market_data_mode_from_code(marketDataType)
                self.request_modes[reqId] = mode
                symbol = self.request_symbols.get(reqId)
                if symbol is not None:
                    recorder.market_data_modes[symbol] = mode.value
                    recorder.note_market_data_mode(symbol=symbol, request_id=reqId, market_data_mode=mode)
                    recorder.write_state(running=True, message="IB market data mode update.")

            def realtimeBar(  # noqa: N802
                self,
                reqId: int,
                time_: int,
                open_: float,
                high: float,
                low: float,
                close: float,
                volume: Decimal,
                wap: Decimal,
                count: int,
            ) -> None:
                symbol = self.request_symbols.get(reqId)
                if symbol is None:
                    return
                mode = self.request_modes.get(reqId, self.requested_mode)
                try:
                    recorder.record_bar(
                        CapturedMarketDataBar(
                            environment=profile.environment,
                            symbol=symbol,
                            request_id=reqId,
                            exchange_timestamp=datetime.fromtimestamp(int(time_), tz=UTC),
                            capture_mode=CaptureMode.STREAM,
                            market_data_mode=mode,
                            source_sequence=f"{symbol}:{time_}",
                            open=Decimal(str(open_)),
                            high=Decimal(str(high)),
                            low=Decimal(str(low)),
                            close=Decimal(str(close)),
                            volume=int(Decimal(str(volume or 0))),
                            wap=Decimal(str(wap)) if wap else None,
                            count=int(count),
                            bar_size_seconds=5,
                        )
                    )
                    self.bars_seen += 1
                except Exception as exc:  # pragma: no cover - defensive callback isolation
                    message = f"{reqId}:record_bar:{type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    recorder.note_error("record_bar", message)

            def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
                symbol = self.request_symbols.get(reqId)
                if symbol is None:
                    return
                seen = self.bars_by_request.get(reqId, 0)
                max_bars = self.max_bars_by_request.get(reqId)
                if max_bars is not None and seen >= max_bars:
                    return
                mode = self.request_modes.get(reqId, self.requested_mode)
                try:
                    exchange_timestamp = _parse_ib_bar_datetime(str(getattr(bar, "date", "") or ""))
                    recorder.record_bar(
                        CapturedMarketDataBar(
                            environment=profile.environment,
                            symbol=symbol,
                            request_id=reqId,
                            exchange_timestamp=exchange_timestamp,
                            capture_mode=CaptureMode.HISTORICAL_BACKFILL,
                            market_data_mode=mode,
                            source_sequence=f"{symbol}:{getattr(bar, 'date', '')}",
                            open=Decimal(str(getattr(bar, "open", "0"))),
                            high=Decimal(str(getattr(bar, "high", "0"))),
                            low=Decimal(str(getattr(bar, "low", "0"))),
                            close=Decimal(str(getattr(bar, "close", "0"))),
                            volume=int(Decimal(str(getattr(bar, "volume", "0") or "0"))),
                            wap=Decimal(str(getattr(bar, "average", "0") or "0")) or None,
                            count=int(Decimal(str(getattr(bar, "barCount", "0") or "0"))),
                            bar_size_seconds=_bar_size_to_seconds(str(getattr(bar, "barSize", "") or "")),
                        )
                    )
                    self.bars_seen += 1
                    self.bars_by_request[reqId] = seen + 1
                except Exception as exc:  # pragma: no cover - defensive callback isolation
                    message = f"{reqId}:historicalData:{type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    recorder.note_error("historicalData", message)

            def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
                self.done_events.setdefault(reqId, Event()).set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                message = f"{reqId}:{errorCode}:{errorString}"
                self.errors.append(message)
                recorder.note_error(errorCode, errorString)
                if reqId >= 0 and errorCode not in {2104, 2106, 2158, 2107, 2108}:
                    self.done_events.setdefault(reqId, Event()).set()

        app = _App()
        app.connect(profile.host, profile.port, profile.client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        app._thread = thread  # type: ignore[attr-defined]
        if not app.ready.wait(self.connection_timeout_seconds):
            app.disconnect()
            raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")
        return app

    def _disconnect_app(self, app: object, recorder: MarketDataRecorder) -> None:
        try:
            app.disconnect()
        finally:
            recorder.note_disconnect()
            thread = getattr(app, "_thread", None)
            if thread is not None:
                thread.join(timeout=2)


def ib_market_data_mode_from_code(code: int) -> IBMarketDataMode:
    return IB_MARKET_DATA_MODES_BY_CODE.get(code, IBMarketDataMode.UNKNOWN)


def _stock_contract(symbol: str) -> object:
    try:
        from ibapi.contract import Contract
    except ImportError as exc:
        raise RuntimeError("IB market data recorder requires the ibapi package. Install the optional IB dependency first.") from exc
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = Currency.USD.value
    return contract


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    normalized = []
    seen = set()
    for symbol in symbols:
        value = symbol.strip().upper()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    if not normalized:
        raise ValueError("At least one symbol is required.")
    return normalized


def _parse_ib_bar_datetime(value: str) -> datetime | None:
    text = " ".join(value.strip().split())
    if not text:
        return None
    timezone = UTC
    for suffix, zone in [
        (" US/Eastern", ZoneInfo("America/New_York")),
        (" US/Central", ZoneInfo("America/Chicago")),
        (" US/Pacific", ZoneInfo("America/Los_Angeles")),
        (" UTC", UTC),
    ]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            timezone = zone
            break
    if text.isdigit() and len(text) != 8:
        return datetime.fromtimestamp(int(text), tz=UTC)
    for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


def _bar_size_to_seconds(value: str) -> int | None:
    text = value.strip().lower()
    if not text:
        return None
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        return None
    unit = parts[1]
    if unit.startswith("sec"):
        return amount
    if unit.startswith("min"):
        return amount * 60
    if unit.startswith("hour"):
        return amount * 3600
    if unit.startswith("day"):
        return amount * 86400
    return None
