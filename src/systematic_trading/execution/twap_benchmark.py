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
from systematic_trading.execution.benchmark_archive import capture, retained_state, validate_ready


def benchmark_window(record, *, original_intent=False):
    order = record.order
    if original_intent and order.slippage_trade_date:
        order = order.model_copy(update=dict(intended_trade_date=order.slippage_trade_date,
            execution_start_time=order.slippage_start_time, execution_end_time=order.slippage_end_time))
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


def session_window(record, *, original_intent=True):
    from systematic_trading.live.trading_calendar import us_equity_market_close
    start, end = benchmark_window(record, original_intent=original_intent)
    zone = ZoneInfo("America/New_York")
    day = start.astimezone(zone).date()
    close = us_equity_market_close(day)
    if close is None or end.astimezone(zone).date() != day:
        raise ValueError("Benchmark window is not in a supported US session")
    opening = datetime.combine(day, datetime.min.time().replace(hour=9, minute=30), zone).astimezone(UTC)
    closing = datetime.combine(day, close, zone).astimezone(UTC)
    if not opening <= start < end <= closing:
        raise ValueError("Benchmark window is outside the regular session")
    return opening, closing


class IBMinuteBars:
    def __init__(self, settings):
        self.settings = settings

    def fetch(self, symbol, start, end):
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper

        class App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.ready, self.done, self.contract_done = Event(), Event(), Event()
                self.bars, self.failures, self.messages, self.contracts = [], [], [], []
            def nextValidId(self, orderId):
                self.ready.set()
            def historicalData(self, reqId, bar):
                self.bars.append({'at': datetime.fromtimestamp(int(bar.date), UTC).isoformat(),
                                  'close': str(bar.close), 'open': str(bar.open), 'high': str(bar.high),
                                  'low': str(bar.low), 'volume': str(bar.volume), 'wap': str(bar.wap),
                                  'trade_count': bar.barCount})
            def contractDetails(self, reqId, details):
                if reqId == 97100:
                    self.contracts.append(details.contract)
            def contractDetailsEnd(self, reqId):
                if reqId == 97100:
                    self.contract_done.set()
            def historicalDataEnd(self, reqId, start, end):
                self.done.set()
            @compatible_ib_errors
            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
                self.messages.append(f"{reqId}:{errorCode}:{errorString}")
                # IB can emit this advisory alongside complete older history.
                # It concerns the latest 15 minutes; still await historicalDataEnd
                # and enforce exact interval coverage before accepting any bars.
                if (reqId == 97101 and errorCode == 2188
                        and end <= datetime.now(UTC) - timedelta(minutes=15)):
                    return
                if reqId in (97100, 97101):
                    self.failures.append(f"IB {errorCode}: {errorString}")
                    self.done.set()
                    self.contract_done.set()

        profile = InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER)
        app, thread = App(), None
        try:
            app.connect(profile.host, profile.port, self.settings.ib_benchmark_client_id or profile.client_id + 90)
            thread = Thread(target=app.run, daemon=True)
            thread.start()
            if not app.ready.wait(10):
                raise TimeoutError("Gateway benchmark connection unavailable.")
            contract = InteractiveBrokersOrderRouter(self.settings).contract_spec_for(symbol)
            app.reqContractDetails(97100, _to_ib_contract(contract))
            if not app.contract_done.wait(10) or app.failures or len(app.contracts) != 1:
                raise ValueError("Benchmark contract identity unavailable or ambiguous. " + "; ".join(app.failures))
            resolved = app.contracts[0]
            if (not resolved.conId or resolved.symbol != symbol or resolved.secType != contract.security_type
                    or resolved.currency != contract.currency.value
                    or (contract.primary_exchange and resolved.primaryExchange != contract.primary_exchange)):
                raise ValueError("Benchmark contract details do not match the requested instrument")
            app.reqHistoricalData(97101, resolved, end.strftime('%Y%m%d-%H:%M:%S'),
                f"{int((end-start).total_seconds())+120} S", '1 min', 'TRADES', 1, 2, False, [])
            if not app.done.wait(25):
                if any(':2105:' in m and 'ushmds' in m for m in app.messages):
                    raise TimeoutError("IB US historical-data farm (ushmds) is disconnected; waiting for complete minute history.")
                raise TimeoutError("Gateway minute-bar benchmark request timed out. " + "; ".join(app.messages[-4:]))
            if app.failures:
                raise ValueError('; '.join(app.failures))
            return dict(bars=app.bars, contract=dict(con_id=resolved.conId, symbol=resolved.symbol,
                security_type=resolved.secType, currency=resolved.currency, exchange=resolved.exchange,
                primary_exchange=resolved.primaryExchange, local_symbol=resolved.localSymbol),
                request=dict(what_to_show='TRADES', bar_size='1 min', use_rth=True), messages=app.messages)
        except Exception as exc:
            exc.evidence = dict(bars=app.bars, messages=app.messages)
            raise
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
        self.closed = False
        self.analytics = None
        if getattr(settings, 'analytics_enabled', False) and settings.market_data_store_backend == 'clickhouse':
            from systematic_trading.market_data.analytics_store import AnalyticsStore
            self.analytics = AnalyticsStore.from_settings(settings)

    def get(self, record, *, now=None, original_intent=True, schedule=True):
        now = now or datetime.now(UTC)
        base = dict(average_fill_price=str(record.average_fill_price) if record.average_fill_price else None,
                    currency=record.order.currency.value, method='Time-weighted 1-minute trade closes over the original intended TWAP window; includes approval and rescheduling delay, excludes fees.')
        if record.execution_sync_issue:
            return dict(base, status='unavailable', message='Execution history requires review before calculating slippage.')
        try:
            start, end = benchmark_window(record, original_intent=original_intent)
        except ValueError as exc:
            return dict(base, status='unavailable', message=str(exc))
        base.update(window_start=start.isoformat(), window_end=end.isoformat())
        if not original_intent:
            base['method'] = 'Time-weighted 1-minute trade closes over the routed TWAP window; excludes fees.'
        result = self.get_window(record.order.symbol, start, end, now=now, schedule=schedule)
        result = dict(base, **result)
        if result['status'] == 'ready' and record.average_fill_price and record.filled_quantity:
            price = Decimal(result['twap_price'])
            sign = Decimal(1) if record.order.side == OrderSide.BUY else Decimal(-1)
            difference = sign * (record.average_fill_price - price)
            result.update(slippage_bps=str(difference / price * 10000),
                          price_cost=str(difference * record.filled_quantity))
        return result

    def get_session(self, record, *, now=None, original_intent=True, schedule=True):
        try:
            start, end = session_window(record, original_intent=original_intent)
        except ValueError as exc:
            return dict(status='unavailable', message=str(exc))
        return self.get_window(record.order.symbol, start, end, now=now, schedule=schedule)

    def get_window(self, symbol, start, end, *, now=None, schedule=True):
        now = now or datetime.now(UTC)
        base = dict(window_start=start.isoformat(), window_end=end.isoformat())
        if now < end:
            return dict(base, status='waiting', message='Benchmark available after the scheduled TWAP window closes.')
        key = sha256(f'v1:{symbol}:{start.isoformat()}:{end.isoformat()}'.encode()).hexdigest()
        path = self.settings.data_dir / 'execution_benchmarks' / f'{key}.json'
        with self.lock:
            cached = self.cache.get(key)
            if cached is None and self.analytics is not None:
                try:
                    saved = self.analytics.document('execution-benchmarks', key)
                    if saved:
                        candidate = json.loads(saved[0]['payload'])
                        validate_ready(candidate, root=self.settings.data_dir, symbol=symbol, start=start, end=end)
                        cached = self.cache[key] = candidate
                except (RuntimeError, OSError, ValueError, KeyError, TypeError):
                    # Original immutable observation is retained for recovery;
                    # it undergoes the same identity/coverage checks below.
                    cached = None
            if cached is None and path.exists():
                try:
                    cached = json.loads(path.read_text(encoding='utf-8'))
                    validate_ready(cached, root=self.settings.data_dir, symbol=symbol, start=start, end=end)
                    self.cache[key] = cached
                except (OSError, ValueError, KeyError, TypeError):
                    return dict(base, status='unavailable', message='Retained benchmark failed validation; preserve and review its evidence.')
            if cached and cached['status'] == 'ready':
                try:
                    price, count = validate_ready(cached, root=self.settings.data_dir, symbol=symbol, start=start, end=end)
                except (OSError, ValueError, KeyError, TypeError):
                    return dict(base, status='unavailable', message='Retained benchmark failed validation; preserve and review its evidence.')
                result = dict(base, status='ready', twap_price=str(price), bar_count=count,
                              coverage='100%', observed_at=cached['observed_at'], source='IB historical TRADES',
                              benchmark_key=key, research_approved=False,
                              price_basis=cached.get('price_basis', 'Legacy operational benchmark; raw basis not independently certified'))
                return result
            if cached is None:
                try:
                    state = retained_state(self.settings.data_dir, key)
                except (OSError, ValueError):
                    return dict(base, status='unavailable', message='Benchmark retry state is unreadable; review retained evidence.')
                if state:
                    cached = dict(status='unavailable', message=state.get('message', 'Previous attempt interrupted'),
                                  next_retry_at=state.get('next_retry_at', 0))
            due = not cached or now.timestamp() >= cached.get('next_retry_at', 0)
            if (schedule and not self.closed and due and key not in self.pending
                    and len(self.pending) < self.settings.execution_benchmark_max_pending):
                self.pending.add(key)
                self.pool.submit(self._fetch, key, path, symbol, start, end)
            return dict(base, status='loading' if key in self.pending else 'unavailable',
                        benchmark_key=key, next_retry_at=cached.get('next_retry_at') if cached else None,
                        message=cached.get('message','Awaiting collection capacity.') if cached else 'Awaiting collection capacity.')

    def _fetch(self, key, path, symbol, start, end):
        try:
            result = capture(self.provider, root=self.settings.data_dir, key=key, path=path,
                             symbol=symbol, start=start, end=end)
        except Exception as exc:
            result = dict(status='unavailable', message=str(exc), next_retry_at=datetime.now(UTC).timestamp() + 300)
        with self.lock:
            self.cache[key] = result
            self.pending.discard(key)

    def close(self):
        with self.lock:
            self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        with self.lock:
            self.pending.clear()
