"""Post-trade TWAP estimates from complete, observed one-minute IB trade bars."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from threading import Event, Lock, Thread
from zoneinfo import ZoneInfo

from systematic_trading.domain.enums import OrderSide, OrderType, OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter, InteractiveBrokersOrderRouter, _to_ib_contract
from systematic_trading.execution.ib_compat import compatible_ib_errors


def benchmark_window(record):
    order = record.order
    if order.order_type != OrderType.TWAP or not all((order.intended_trade_date, order.execution_start_time, order.execution_end_time)):
        raise ValueError("No explicit TWAP window is recorded for this order.")
    zone = ZoneInfo("America/New_York")
    start = datetime.fromisoformat(f"{order.intended_trade_date}T{order.execution_start_time}").replace(tzinfo=zone).astimezone(UTC)
    end = datetime.fromisoformat(f"{order.intended_trade_date}T{order.execution_end_time}").replace(tzinfo=zone).astimezone(UTC)
    if not timedelta(0) < end - start <= timedelta(hours=4):
        raise ValueError("Invalid TWAP benchmark window.")
    return start, end


def calculate_twap(bars, start, end):
    """Duration-weighted minute closes; missing/conflicting observations fail closed."""
    points = {}
    for bar in bars:
        at = datetime.fromisoformat(bar['at'])
        if at.tzinfo is None:
            raise ValueError("Benchmark observations require an explicit timezone.")
        at = at.astimezone(UTC)
        price = Decimal(str(bar['close']))
        if not price.is_finite() or price <= 0:
            raise ValueError("Invalid market price in benchmark evidence.")
        if at in points and points[at] != price:
            raise ValueError("Conflicting market bars in benchmark evidence.")
        points[at] = price
    cursor, covered, weighted, count = start, Decimal(0), Decimal(0), 0
    for at, price in sorted(points.items()):
        left, right = max(start, at), min(end, at + timedelta(minutes=1))
        if right <= left:
            continue
        if left != cursor:
            raise ValueError("Incomplete or overlapping intraday coverage; benchmark withheld.")
        seconds = Decimal(str((right-left).total_seconds()))
        weighted += price * seconds
        covered += seconds
        count += 1
        cursor = right
    if cursor != end or covered <= 0:
        raise ValueError("Incomplete intraday coverage; benchmark withheld.")
    return weighted / covered, count


class IBMinuteBars:
    def __init__(self, settings):
        self.settings = settings

    def fetch(self, symbol, start, end):
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper

        class App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.ready, self.done = Event(), Event()
                self.bars, self.failures, self.messages = [], [], []
            def nextValidId(self, orderId):
                self.ready.set()
            def historicalData(self, reqId, bar):
                self.bars.append({'at': datetime.fromtimestamp(int(bar.date), UTC).isoformat(),
                                  'close': str(bar.close)})
            def historicalDataEnd(self, reqId, start, end):
                self.done.set()
            @compatible_ib_errors
            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
                self.messages.append(f"{reqId}:{errorCode}:{errorString}")
                if reqId == 97101:
                    self.failures.append(f"IB {errorCode}: {errorString}")
                    self.done.set()

        profile = InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER)
        app, thread = App(), None
        try:
            app.connect(profile.host, profile.port, self.settings.ib_benchmark_client_id or profile.client_id + 90)
            thread = Thread(target=app.run, daemon=True)
            thread.start()
            if not app.ready.wait(10):
                raise TimeoutError("Gateway benchmark connection unavailable.")
            contract = InteractiveBrokersOrderRouter(self.settings).contract_spec_for(symbol)
            app.reqHistoricalData(97101, _to_ib_contract(contract), end.strftime('%Y%m%d-%H:%M:%S'),
                f"{int((end-start).total_seconds())+120} S", '1 min', 'TRADES', 1, 2, False, [])
            if not app.done.wait(25):
                if any(':2105:' in m and 'ushmds' in m for m in app.messages):
                    raise TimeoutError("IB US historical-data farm (ushmds) is disconnected; waiting for complete minute history.")
                raise TimeoutError("Gateway minute-bar benchmark request timed out. " + "; ".join(app.messages[-4:]))
            if app.failures:
                raise ValueError('; '.join(app.failures))
            return app.bars
        finally:
            app.disconnect()
            if thread:
                thread.join(timeout=2)


class TwapBenchmarkService:
    def __init__(self, settings, provider=None):
        self.settings = settings
        self.provider = provider or IBMinuteBars(settings)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='twap-benchmark')
        self.lock, self.pending = Lock(), set()
        self.cache = {}
        self.analytics = None
        if getattr(settings, 'analytics_enabled', False) and settings.market_data_store_backend == 'clickhouse':
            from systematic_trading.market_data.analytics_store import AnalyticsStore
            self.analytics = AnalyticsStore.from_settings(settings)

    def get(self, record, *, now=None):
        now = now or datetime.now(UTC)
        base = dict(average_fill_price=str(record.average_fill_price) if record.average_fill_price else None,
                    currency=record.order.currency.value, method='Time-weighted 1-minute trade closes over the scheduled TWAP window; includes approval delay, excludes fees.')
        if record.execution_sync_issue:
            return dict(base, status='unavailable', message='Execution history requires review before calculating slippage.')
        try:
            start, end = benchmark_window(record)
        except ValueError as exc:
            return dict(base, status='unavailable', message=str(exc))
        base.update(window_start=start.isoformat(), window_end=end.isoformat())
        if now < end:
            return dict(base, status='waiting', message='Benchmark available after the scheduled TWAP window closes.')
        key = sha256(f'v1:{record.order.symbol}:{start.isoformat()}:{end.isoformat()}'.encode()).hexdigest()
        path = self.settings.data_dir / 'execution_benchmarks' / f'{key}.json'
        with self.lock:
            cached = self.cache.get(key)
            if cached is None and self.analytics is not None:
                try:
                    saved = self.analytics.document('execution-benchmarks', key)
                    if saved:
                        candidate = json.loads(saved[0]['payload'])
                        if (candidate['status'], candidate['symbol'], candidate['window_start'], candidate['window_end']) != ('ready', record.order.symbol, start.isoformat(), end.isoformat()):
                            raise ValueError('Published benchmark identity does not match this order.')
                        datetime.fromisoformat(candidate['observed_at'])
                        calculate_twap(candidate['bars'], start, end)
                        cached = self.cache[key] = candidate
                except (RuntimeError, OSError, ValueError, KeyError, TypeError):
                    # Original immutable observation is retained for recovery;
                    # it undergoes the same identity/coverage checks below.
                    cached = None
            if cached is None and path.exists():
                try:
                    cached = json.loads(path.read_text(encoding='utf-8'))
                    if (cached['status'], cached['symbol'], cached['window_start'], cached['window_end']) != ('ready', record.order.symbol, start.isoformat(), end.isoformat()):
                        raise ValueError('Cached benchmark identity does not match this order.')
                    datetime.fromisoformat(cached['observed_at'])
                    calculate_twap(cached['bars'], start, end)
                    self.cache[key] = cached
                except (OSError, ValueError, KeyError, TypeError):
                    cached = None
            if cached and cached['status'] == 'ready':
                price, count = calculate_twap(cached['bars'], start, end)
                result = dict(base, status='ready', twap_price=str(price), bar_count=count,
                              coverage='100%', observed_at=cached['observed_at'], source='IB historical TRADES')
                if record.average_fill_price and record.filled_quantity:
                    sign = Decimal(1) if record.order.side == OrderSide.BUY else Decimal(-1)
                    difference = sign * (record.average_fill_price - price)
                    result.update(slippage_bps=str(difference / price * 10000),
                                  price_cost=str(difference * record.filled_quantity))
                return result
            if key not in self.pending and (not cached or now.timestamp()-cached['retry_at'] >= 300):
                self.pending.add(key)
                self.pool.submit(self._fetch, key, path, record.order.symbol, start, end)
            return dict(base, status='loading' if key in self.pending else 'unavailable',
                        message=cached.get('message','Loading observed market bars.') if cached else 'Loading observed market bars.')

    def _fetch(self, key, path, symbol, start, end):
        try:
            bars = self.provider.fetch(symbol, start, end)
            calculate_twap(bars, start, end)
            result = dict(status='ready', symbol=symbol, bars=bars, window_start=start.isoformat(),
                          window_end=end.isoformat(), observed_at=datetime.now(UTC).isoformat())
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
            temporary.replace(path)
        except Exception as exc:
            result = dict(status='unavailable', message=str(exc), retry_at=datetime.now(UTC).timestamp())
        with self.lock:
            self.cache[key] = result
            self.pending.discard(key)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
