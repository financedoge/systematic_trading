from __future__ import annotations

from systematic_trading.execution.ib_compat import compatible_ib_errors

import time
from collections import deque
from dataclasses import dataclass
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
    feed_channel: str | None = None
    symbols_requested: list[str] = Field(default_factory=list)
    symbols_with_data: list[str] = Field(default_factory=list)
    failed_symbols: list[str] = Field(default_factory=list)
    bars_by_symbol: dict[str, int] = Field(default_factory=dict)
    subscriptions_started: int = 0
    subscriptions_cancelled: int = 0
    requests_completed: int = 0
    bars_seen: int = 0
    completed_successfully: bool = True
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
                if request_ids and all(request_id in app.request_errors for request_id in request_ids):
                    break
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
            feed_channel="reqRealTimeBars",
            symbols_requested=requested_symbols,
            symbols_with_data=sorted(app.bars_by_symbol),
            failed_symbols=sorted(
                symbol for symbol in requested_symbols if app.bars_by_symbol.get(symbol, 0) == 0
            ),
            bars_by_symbol=dict(sorted(app.bars_by_symbol.items())),
            subscriptions_started=subscriptions_started,
            subscriptions_cancelled=subscriptions_cancelled,
            bars_seen=app.bars_seen,
            completed_successfully=all(app.bars_by_symbol.get(symbol, 0) > 0 for symbol in requested_symbols),
            errors=app.errors,
        )

    def record_historical_live_bars(
        self,
        *,
        profile: BrokerConnectionProfile,
        symbols: Iterable[str],
        recorder: MarketDataRecorder,
        duration_seconds: float,
        initial_duration: str = "3600 S",
        initial_write_lookback_seconds: int = 60,
        bar_size: str = "5 secs",
        market_data_mode: IBMarketDataMode = IBMarketDataMode.LIVE,
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        request_spacing_seconds: float = 10.0,
        request_rate_per_second: float = 5.0,
        request_burst: int = 10,
    ) -> IBMarketDataRunResult:
        """Record IB 5-second bars through a keep-up-to-date historical subscription.

        IB exposes this separately from ``reqRealTimeBars``. It is useful for a
        prospective raw recorder when the account can retrieve 5-second HMDS bars
        but does not have the additional API entitlement required by
        ``reqRealTimeBars``.
        """
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        requested_symbols = _normalize_symbols(symbols)
        bar_size_seconds = _bar_size_to_seconds(bar_size)
        if bar_size_seconds is None or bar_size_seconds < 5:
            raise ValueError("historical live updates require a bar size of at least 5 seconds")
        if initial_write_lookback_seconds < bar_size_seconds:
            raise ValueError("initial_write_lookback_seconds must cover at least one bar")
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
                recorder.note_pacing_sleep(pacer.consume())
                request_id = 95000 + index
                request_ids[request_id] = symbol
                app.request_symbols[request_id] = symbol
                app.bar_size_seconds_by_request[request_id] = bar_size_seconds
                app.historical_initial_max_bars_by_request[request_id] = (
                    initial_write_lookback_seconds // bar_size_seconds + 1
                )
                app.done_events[request_id] = Event()
                app.historical_live_requests.add(request_id)
                app.reqHistoricalData(
                    request_id,
                    _stock_contract(symbol),
                    "",
                    initial_duration,
                    bar_size,
                    what_to_show,
                    1 if use_rth else 0,
                    2,
                    True,
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
                if request_ids and all(request_id in app.request_errors for request_id in request_ids):
                    break
                time.sleep(self.sleep_seconds)
        finally:
            subscriptions_cancelled = 0
            for request_id in request_ids:
                try:
                    app.cancelled_request_ids.add(request_id)
                    app.flush_completed_historical_update(request_id)
                    app.cancelHistoricalData(request_id)
                    subscriptions_cancelled += 1
                    recorder.note_subscription_cancelled(symbol=request_ids[request_id], request_id=request_id)
                except Exception as exc:  # pragma: no cover - defensive IB disconnect cleanup
                    app.errors.append(f"{request_id}:cancel:{exc}")
            self._disconnect_app(app, recorder)
        failed_symbols = sorted(
            symbol
            for request_id, symbol in request_ids.items()
            if request_id in app.request_errors or app.bars_by_symbol.get(symbol, 0) == 0
        )
        return IBMarketDataRunResult(
            mode="historical-live",
            feed_channel="reqHistoricalData.keepUpToDate",
            symbols_requested=requested_symbols,
            symbols_with_data=sorted(app.bars_by_symbol),
            failed_symbols=failed_symbols,
            bars_by_symbol=dict(sorted(app.bars_by_symbol.items())),
            subscriptions_started=subscriptions_started,
            subscriptions_cancelled=subscriptions_cancelled,
            requests_completed=sum(
                1 for request_id in request_ids if app.done_events[request_id].is_set() and request_id not in app.request_errors
            ),
            bars_seen=app.bars_seen,
            completed_successfully=not failed_symbols,
            errors=app.errors,
        )

    def record_delayed_trade_bars(
        self,
        *,
        profile: BrokerConnectionProfile,
        symbols: Iterable[str],
        recorder: MarketDataRecorder,
        duration_seconds: float,
        request_spacing_seconds: float = 0.25,
        request_rate_per_second: float = 5.0,
        request_burst: int = 10,
    ) -> IBMarketDataRunResult:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        requested_symbols = _normalize_symbols(symbols)
        app = self._connect_app(profile, recorder=recorder)
        app.requested_mode = IBMarketDataMode.DELAYED
        app.reqMarketDataType(IB_MARKET_DATA_TYPE_CODES[IBMarketDataMode.DELAYED])
        pacer = TokenBucket(rate_per_second=request_rate_per_second, burst=request_burst)
        request_ids: dict[int, str] = {}
        subscriptions_started = 0
        try:
            for index, symbol in enumerate(requested_symbols, start=1):
                if index > 1:
                    time.sleep(request_spacing_seconds)
                    recorder.note_pacing_sleep(request_spacing_seconds)
                recorder.note_pacing_sleep(pacer.consume())
                request_id = 96000 + index
                request_ids[request_id] = symbol
                app.request_symbols[request_id] = symbol
                app.reqMktData(request_id, _stock_contract(symbol), "233", False, False, [])
                subscriptions_started += 1
                recorder.note_subscription_started(
                    symbol=symbol,
                    request_id=request_id,
                    market_data_mode=IBMarketDataMode.DELAYED,
                    capture_mode=CaptureMode.STREAM,
                )
            deadline = time.monotonic() + duration_seconds
            while time.monotonic() < deadline:
                if request_ids and all(request_id in app.request_errors for request_id in request_ids):
                    break
                time.sleep(self.sleep_seconds)
        finally:
            subscriptions_cancelled = 0
            for request_id in request_ids:
                try:
                    app.cancelled_request_ids.add(request_id)
                    app.flush_delayed_trade_bar(request_id)
                    app.cancelMktData(request_id)
                    subscriptions_cancelled += 1
                    recorder.note_subscription_cancelled(symbol=request_ids[request_id], request_id=request_id)
                except Exception as exc:  # pragma: no cover - defensive IB disconnect cleanup
                    app.errors.append(f"{request_id}:cancel:{exc}")
            self._disconnect_app(app, recorder)
        failed_symbols = sorted(
            symbol
            for request_id, symbol in request_ids.items()
            if request_id in app.request_errors or app.bars_by_symbol.get(symbol, 0) == 0
        )
        return IBMarketDataRunResult(
            mode="delayed-trades",
            feed_channel="reqMktData.delayedTrades",
            symbols_requested=requested_symbols,
            symbols_with_data=sorted(app.bars_by_symbol),
            failed_symbols=failed_symbols,
            bars_by_symbol=dict(sorted(app.bars_by_symbol.items())),
            subscriptions_started=subscriptions_started,
            subscriptions_cancelled=subscriptions_cancelled,
            bars_seen=app.bars_seen,
            completed_successfully=not failed_symbols,
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
                app.bar_size_seconds_by_request[request_id] = _bar_size_to_seconds(bar_size)
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
                if not self._wait_for_historical_completion(app, request_id):
                    recent_errors = app.errors[-5:]
                    suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
                    message = f"{request_id}:timeout:Timed out waiting for IB historical bars for {symbol}.{suffix}"
                    app.errors.append(message)
                    app.request_errors[request_id] = message
                    recorder.note_error("historical_timeout", message)
                    try:
                        app.cancelHistoricalData(request_id)
                    except Exception:  # pragma: no cover - defensive IB cleanup
                        pass
                    continue
                if request_id not in app.request_errors:
                    requests_completed += 1
        finally:
            self._disconnect_app(app, recorder)
        failed_symbols = sorted(
            symbol
            for request_id, symbol in app.request_symbols.items()
            if request_id in app.request_errors or app.bars_by_symbol.get(symbol, 0) == 0
        )
        return IBMarketDataRunResult(
            mode="historical",
            feed_channel="reqHistoricalData",
            symbols_requested=requested_symbols,
            symbols_with_data=sorted(app.bars_by_symbol),
            failed_symbols=failed_symbols,
            bars_by_symbol=dict(sorted(app.bars_by_symbol.items())),
            requests_completed=requests_completed,
            bars_seen=app.bars_seen,
            completed_successfully=not failed_symbols,
            errors=app.errors,
        )

    def _wait_for_historical_completion(self, app: object, request_id: int) -> bool:
        started_at = time.monotonic()
        while not app.done_events[request_id].wait(self.sleep_seconds):
            last_activity = app.last_activity_monotonic_by_request.get(request_id, started_at)
            if time.monotonic() - last_activity >= self.historical_timeout_seconds:
                return False
        return True

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
                self.bar_size_seconds_by_request: dict[int, int | None] = {}
                self.bars_by_request: dict[int, int] = {}
                self.bars_by_symbol: dict[str, int] = {}
                self.request_errors: dict[int, str] = {}
                self.request_quality_flags: dict[int, list[str]] = {}
                self.cancelled_request_ids: set[int] = set()
                self.last_activity_monotonic_by_request: dict[int, float] = {}
                self.historical_live_requests: set[int] = set()
                self.historical_initial_max_bars_by_request: dict[int, int] = {}
                self.historical_initial_buffers: dict[int, deque[object]] = {}
                self.pending_historical_updates: dict[int, object] = {}
                self.delayed_trade_bars: dict[int, _TradeBarAccumulator] = {}
                self.delayed_last_prices: dict[int, Decimal] = {}
                self.delayed_last_sizes: dict[int, int] = {}
                self.delayed_last_timestamps: dict[int, datetime] = {}
                self.last_accepted_delayed_trade_timestamp: dict[int, datetime] = {}
                self.recorded_bar_fingerprints: set[tuple[object, ...]] = set()
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
                            quality_flags=list(self.request_quality_flags.get(reqId, [])),
                        )
                    )
                    self.bars_seen += 1
                    self.bars_by_symbol[symbol] = self.bars_by_symbol.get(symbol, 0) + 1
                except Exception as exc:  # pragma: no cover - defensive callback isolation
                    message = f"{reqId}:record_bar:{type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    recorder.note_error("record_bar", message)

            def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
                self.last_activity_monotonic_by_request[reqId] = time.monotonic()
                if reqId in self.historical_live_requests:
                    max_bars = self.historical_initial_max_bars_by_request.get(reqId, 13)
                    buffer = self.historical_initial_buffers.setdefault(reqId, deque(maxlen=max_bars))
                    buffer.append(bar)
                    return
                self._record_historical_bar(reqId, bar, capture_mode=CaptureMode.HISTORICAL_BACKFILL)

            def historicalDataUpdate(self, reqId: int, bar: object) -> None:  # noqa: N802
                if reqId not in self.historical_live_requests:
                    return
                self.last_activity_monotonic_by_request[reqId] = time.monotonic()
                previous = self.pending_historical_updates.get(reqId)
                if previous is None:
                    self.pending_historical_updates[reqId] = bar
                    return
                previous_timestamp = _parse_ib_bar_datetime(str(getattr(previous, "date", "") or ""))
                current_timestamp = _parse_ib_bar_datetime(str(getattr(bar, "date", "") or ""))
                if previous_timestamp is None or current_timestamp is None:
                    self.pending_historical_updates[reqId] = bar
                    return
                if current_timestamp == previous_timestamp:
                    self.pending_historical_updates[reqId] = bar
                    return
                if current_timestamp > previous_timestamp:
                    self._record_historical_bar(
                        reqId,
                        previous,
                        capture_mode=CaptureMode.STREAM,
                        quality_flags=["ib_historical_live_update_channel"],
                    )
                    self.pending_historical_updates[reqId] = bar

            def flush_completed_historical_update(self, reqId: int) -> None:
                bar = self.pending_historical_updates.pop(reqId, None)
                if bar is None:
                    return
                timestamp = _parse_ib_bar_datetime(str(getattr(bar, "date", "") or ""))
                bar_size_seconds = self.bar_size_seconds_by_request.get(reqId) or 5
                if timestamp is None or (datetime.now(tz=UTC) - timestamp).total_seconds() < bar_size_seconds:
                    return
                self._record_historical_bar(
                    reqId,
                    bar,
                    capture_mode=CaptureMode.STREAM,
                    quality_flags=["ib_historical_live_update_channel"],
                )

            def tickString(self, reqId: int, tickType: int, value: str) -> None:  # noqa: N802
                if tickType == 88:
                    try:
                        self.delayed_last_timestamps[reqId] = datetime.fromtimestamp(int(value), tz=UTC)
                    except (ValueError, OverflowError):
                        return
                    self._accept_delayed_last(reqId)
                    return
                if tickType not in {48, 77}:
                    return
                parsed = _parse_rt_volume(value)
                if parsed is None:
                    return
                price, size, exchange_timestamp = parsed
                bucket_timestamp = datetime.fromtimestamp(
                    int(exchange_timestamp.timestamp()) // 5 * 5,
                    tz=UTC,
                )
                current = self.delayed_trade_bars.get(reqId)
                if current is not None and bucket_timestamp > current.exchange_timestamp:
                    self._record_delayed_trade_bar(reqId, current)
                    current = None
                if current is None:
                    current = _TradeBarAccumulator.start(bucket_timestamp, price, size)
                    self.delayed_trade_bars[reqId] = current
                else:
                    current.add(price, size)

            def tickPrice(self, reqId: int, tickType: int, price: float, attrib: object) -> None:  # noqa: N802
                if tickType != 68 or price <= 0:
                    return
                self.delayed_last_prices[reqId] = Decimal(str(price))
                self._accept_delayed_last(reqId)

            def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:  # noqa: N802
                if tickType != 71:
                    return
                self.delayed_last_sizes[reqId] = int(Decimal(str(size or 0)))
                self._accept_delayed_last(reqId)

            def _accept_delayed_last(self, reqId: int) -> None:
                price = self.delayed_last_prices.get(reqId)
                size = self.delayed_last_sizes.get(reqId)
                exchange_timestamp = self.delayed_last_timestamps.get(reqId)
                if price is None or size is None or exchange_timestamp is None:
                    return
                if exchange_timestamp <= self.last_accepted_delayed_trade_timestamp.get(
                    reqId, datetime.min.replace(tzinfo=UTC)
                ):
                    return
                self.last_accepted_delayed_trade_timestamp[reqId] = exchange_timestamp
                bucket_timestamp = datetime.fromtimestamp(
                    int(exchange_timestamp.timestamp()) // 5 * 5,
                    tz=UTC,
                )
                current = self.delayed_trade_bars.get(reqId)
                if current is not None and bucket_timestamp > current.exchange_timestamp:
                    self._record_delayed_trade_bar(reqId, current)
                    current = None
                if current is None:
                    self.delayed_trade_bars[reqId] = _TradeBarAccumulator.start(
                        bucket_timestamp,
                        price,
                        size,
                    )
                else:
                    current.add(price, size)

            def flush_delayed_trade_bar(self, reqId: int) -> None:
                current = self.delayed_trade_bars.pop(reqId, None)
                if current is not None:
                    self._record_delayed_trade_bar(reqId, current)

            def _record_delayed_trade_bar(self, reqId: int, bar: "_TradeBarAccumulator") -> None:
                symbol = self.request_symbols.get(reqId)
                if symbol is None:
                    return
                try:
                    recorder.record_bar(
                        CapturedMarketDataBar(
                            environment=profile.environment,
                            symbol=symbol,
                            request_id=reqId,
                            exchange_timestamp=bar.exchange_timestamp,
                            capture_mode=CaptureMode.STREAM,
                            market_data_mode=IBMarketDataMode.DELAYED,
                            source_sequence=f"{symbol}:{int(bar.exchange_timestamp.timestamp())}",
                            open=bar.open,
                            high=bar.high,
                            low=bar.low,
                            close=bar.close,
                            volume=bar.volume,
                            wap=bar.wap,
                            count=bar.count,
                            bar_size_seconds=5,
                            quality_flags=["ib_delayed_trade_aggregate", *self.request_quality_flags.get(reqId, [])],
                        )
                    )
                    self.bars_seen += 1
                    self.bars_by_symbol[symbol] = self.bars_by_symbol.get(symbol, 0) + 1
                except Exception as exc:  # pragma: no cover - defensive callback isolation
                    message = f"{reqId}:delayedRTVolume:{type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    recorder.note_error("delayedRTVolume", message)

            def _record_historical_bar(
                self,
                reqId: int,
                bar: object,
                *,
                capture_mode: CaptureMode,
                quality_flags: list[str] | None = None,
            ) -> None:
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
                    fingerprint = (
                        symbol,
                        exchange_timestamp,
                        str(getattr(bar, "open", "0")),
                        str(getattr(bar, "high", "0")),
                        str(getattr(bar, "low", "0")),
                        str(getattr(bar, "close", "0")),
                        str(getattr(bar, "volume", "0")),
                        str(getattr(bar, "average", "0")),
                        str(getattr(bar, "barCount", "0")),
                    )
                    if fingerprint in self.recorded_bar_fingerprints:
                        return
                    self.recorded_bar_fingerprints.add(fingerprint)
                    recorder.record_bar(
                        CapturedMarketDataBar(
                            environment=profile.environment,
                            symbol=symbol,
                            request_id=reqId,
                            exchange_timestamp=exchange_timestamp,
                            capture_mode=capture_mode,
                            market_data_mode=mode,
                            source_sequence=f"{symbol}:{getattr(bar, 'date', '')}",
                            open=Decimal(str(getattr(bar, "open", "0"))),
                            high=Decimal(str(getattr(bar, "high", "0"))),
                            low=Decimal(str(getattr(bar, "low", "0"))),
                            close=Decimal(str(getattr(bar, "close", "0"))),
                            volume=int(Decimal(str(getattr(bar, "volume", "0") or "0"))),
                            wap=Decimal(str(getattr(bar, "average", "0") or "0")) or None,
                            count=int(Decimal(str(getattr(bar, "barCount", "0") or "0"))),
                            bar_size_seconds=self.bar_size_seconds_by_request.get(reqId)
                            or _bar_size_to_seconds(str(getattr(bar, "barSize", "") or "")),
                            quality_flags=[*(quality_flags or []), *self.request_quality_flags.get(reqId, [])],
                        )
                    )
                    self.bars_seen += 1
                    self.bars_by_request[reqId] = seen + 1
                    self.bars_by_symbol[symbol] = self.bars_by_symbol.get(symbol, 0) + 1
                except Exception as exc:  # pragma: no cover - defensive callback isolation
                    message = f"{reqId}:historicalData:{type(exc).__name__}: {exc}"
                    self.errors.append(message)
                    recorder.note_error("historicalData", message)

            def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
                if reqId in self.historical_live_requests:
                    for bar in self.historical_initial_buffers.pop(reqId, deque()):
                        self._record_historical_bar(
                            reqId,
                            bar,
                            capture_mode=CaptureMode.HISTORICAL_BACKFILL,
                            quality_flags=["ib_historical_live_initial_tail"],
                        )
                self.done_events.setdefault(reqId, Event()).set()

            @compatible_ib_errors
            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                if reqId in self.cancelled_request_ids and (
                    errorCode in {162, 300, 366} or "cancel" in errorString.lower()
                ):
                    return
                message = f"{reqId}:{errorCode}:{errorString}"
                self.errors.append(message)
                if errorCode == 10167:
                    return
                recorder.note_error(errorCode, errorString)
                if reqId >= 0 and errorCode == 2176:
                    # IB still delivers data after rounding fractional sizes for
                    # older clients. Preserve the warning and flag every later
                    # bar for this request, without terminating the subscription.
                    flags = self.request_quality_flags.setdefault(reqId, [])
                    if "ib_fractional_volume_rounded" not in flags:
                        flags.append("ib_fractional_volume_rounded")
                    return
                if reqId >= 0 and errorCode not in {2104, 2106, 2158, 2107, 2108}:
                    self.request_errors[reqId] = message
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


def _parse_rt_volume(value: str) -> tuple[Decimal, int, datetime] | None:
    parts = value.split(";")
    if len(parts) < 3:
        return None
    try:
        price = Decimal(parts[0])
        size = int(Decimal(parts[1] or "0"))
        timestamp = datetime.fromtimestamp(int(parts[2]) / 1000, tz=UTC)
    except (ArithmeticError, ValueError, OverflowError):
        return None
    if price <= 0 or size < 0:
        return None
    return price, size, timestamp


@dataclass
class _TradeBarAccumulator:
    exchange_timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    notional: Decimal
    count: int

    @classmethod
    def start(cls, exchange_timestamp: datetime, price: Decimal, size: int) -> "_TradeBarAccumulator":
        return cls(
            exchange_timestamp=exchange_timestamp,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=size,
            notional=price * size,
            count=1,
        )

    def add(self, price: Decimal, size: int) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += size
        self.notional += price * size
        self.count += 1

    @property
    def wap(self) -> Decimal:
        return self.notional / self.volume if self.volume else self.close
