"""Read-only IB portfolio P&L. Never substitute research marks for broker values."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from threading import Event, RLock, Thread

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors


def broker_number(value: object) -> Decimal | None:
    """IB's unset double, NaN and infinity are unavailable, never zero."""
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and abs(number) < Decimal('1e100') else None
    except (InvalidOperation, ValueError):
        return None


class PositionPnl(BaseModel):
    contract_id: int
    symbol: str
    currency: str
    quantity: Decimal | None = None
    daily_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    market_value: Decimal | None = None
    received_at: datetime | None = None
    stale: bool = True


class BrokerPnlSnapshot(BaseModel):
    source: str = 'ib_portfolio_pnl'
    environment: str = 'paper'
    status: str = 'unavailable'
    connected: bool = False
    account: str | None = None
    currency: str | None = None
    daily_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    received_at: datetime | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    age_seconds: float | None = None
    positions: list[PositionPnl] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BrokerPnlService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.lock = RLock()
        self.stop_event = Event()
        self.thread: Thread | None = None
        self.app = None
        self.connected = False
        self.error: str | None = None
        self.data = BrokerPnlSnapshot()

    def start(self) -> None:
        with self.lock:
            if self.thread is not None or not self.settings.ib_pnl_enabled:
                return
            if self.settings.default_environment != OrderEnvironment.PAPER:
                self.error = 'Broker P&L is configured for the paper account only.'
                return
            self.stop_event.clear()
            self.thread = Thread(target=self._run, daemon=True, name='ib-readonly-pnl')
            self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        if self.app is not None:
            self.app.disconnect()
        if self.thread is not None:
            self.thread.join(timeout=5)

    def snapshot(self, *, now: datetime | None = None) -> BrokerPnlSnapshot:
        now = now or datetime.now(UTC)
        with self.lock:
            result = self.data.model_copy(deep=True)
            connected, error = self.connected, self.error
        result.checked_at = now
        result.connected = connected
        if result.received_at is not None:
            result.age_seconds = max(0, (now - result.received_at).total_seconds())
        fresh = result.age_seconds is not None and result.age_seconds <= self.settings.ib_pnl_stale_seconds
        available = result.currency is not None and any(value is not None for value in (
            result.daily_pnl, result.unrealized_pnl, result.realized_pnl,
        ))
        result.status = 'live' if connected and fresh and available else (
            'stale' if result.received_at else 'unavailable'
        )
        for row in result.positions:
            row.stale = not connected or row.received_at is None or (
                now - row.received_at
            ).total_seconds() > self.settings.ib_pnl_stale_seconds
        result.warnings = [
            'Account totals use IB base currency; position rows use contract currency. Broker reset schedule; independent of the local accounting reset.',
            'Received time measures callback freshness, not exchange quote age or market-data entitlement.',
        ]
        if error:
            result.warnings.append(error)
        if not self.settings.ib_pnl_enabled:
            result.warnings.append('IB P&L feed disabled in configuration.')
        elif result.status != 'live':
            result.warnings.append(
                'Showing last received broker values with their timestamps, not current quotes. '
                'Callbacks can pause after hours; stale values are not an official closing valuation.'
                if result.received_at else 'Waiting for broker P&L values.'
            )
        return result

    def select_account(self, accounts: list[str]) -> str:
        requested = self.settings.ib_pnl_account
        if requested:
            if requested not in accounts or not requested.startswith('DU'):
                raise ValueError('Configured paper P&L account is not a managed DU account.')
            return requested
        if len(accounts) != 1 or not accounts[0].startswith('DU'):
            raise ValueError('P&L requires one verified paper DU account or ST_IB_PNL_ACCOUNT.')
        return accounts[0]

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._session()
            except Exception as exc:
                with self.lock:
                    self.error = f'{type(exc).__name__}: {exc}'
            finally:
                with self.lock:
                    self.connected = False
                if self.app is not None:
                    self.app.disconnect()
                    self.app = None
            self.stop_event.wait(self.settings.ib_pnl_reconnect_seconds)

    def _session(self) -> None:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper

        service = self

        class App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.ready = Event()
                self.accounts_ready = Event()
                self.accounts: list[str] = []
                self.account = ''
                self.contracts: dict[int, int] = {}
                self.requests: dict[int, int] = {}
                self.next_request = 100

            def nextValidId(self, orderId):  # noqa: N802
                self.ready.set()

            def managedAccounts(self, accountsList):  # noqa: N802
                self.accounts = [item.strip() for item in accountsList.split(',') if item.strip()]
                self.accounts_ready.set()

            def accountSummary(self, reqId, account, tag, value, currency):  # noqa: N802
                if account != self.account:
                    return
                if tag == 'NetLiquidation' and currency.isalpha() and currency != 'BASE':
                    with service.lock:
                        service.data.currency = currency.upper()

            def pnl(self, reqId, dailyPnL, unrealizedPnL, realizedPnL):
                if reqId != 1:
                    return
                with service.lock:
                    service.data.daily_pnl = broker_number(dailyPnL)
                    service.data.unrealized_pnl = broker_number(unrealizedPnL)
                    service.data.realized_pnl = broker_number(realizedPnL)
                    service.data.received_at = datetime.now(UTC)

            def position(self, account, contract, position, avgCost):
                if account != self.account:
                    return
                con_id = int(contract.conId)
                quantity = broker_number(position)
                if quantity is None or con_id <= 0:
                    return
                with service.lock:
                    if quantity == 0:
                        request = self.contracts.pop(con_id, None)
                        if request is not None:
                            self.requests.pop(request, None)
                            self.cancelPnLSingle(request)
                        service.data.positions = [r for r in service.data.positions if r.contract_id != con_id]
                    elif con_id not in self.contracts:
                        request = self.next_request
                        self.next_request += 1
                        self.contracts[con_id] = request
                        self.requests[request] = con_id
                        service.data.positions.append(PositionPnl(
                            contract_id=con_id, symbol=contract.symbol, currency=contract.currency, quantity=quantity,
                        ))
                        self.reqPnLSingle(request, self.account, '', con_id)
                    else:
                        for row in service.data.positions:
                            if row.contract_id == con_id and row.quantity != quantity:
                                row.quantity = quantity
                                row.daily_pnl = row.unrealized_pnl = row.realized_pnl = row.market_value = None
                                row.received_at = None

            def pnlSingle(self, reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value):  # noqa: N802
                con_id = self.requests.get(reqId)
                with service.lock:
                    for row in service.data.positions:
                        if row.contract_id == con_id:
                            row.quantity = broker_number(pos)
                            row.daily_pnl = broker_number(dailyPnL)
                            row.unrealized_pnl = broker_number(unrealizedPnL)
                            row.realized_pnl = broker_number(realizedPnL)
                            row.market_value = broker_number(value)
                            row.received_at = datetime.now(UTC)

            @compatible_ib_errors
            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
                if errorCode in {2104, 2106, 2107, 2108, 2158}:
                    return
                with service.lock:
                    service.error = f'IB {errorCode}: {errorString}'
                # Recreate all subscriptions after a connectivity loss/restoration.
                if errorCode in {502, 504, 1100, 1101, 1102, 1300}:
                    self.disconnect()

        profile = InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER)
        app = App()
        self.app = app
        reader = None
        try:
            with self.lock:
                self.data = BrokerPnlSnapshot()
                self.error = None
            app.connect(profile.host, profile.port, self.settings.ib_pnl_client_id or self.settings.ib_client_id + 100)
            reader = Thread(target=app.run, daemon=True, name='ib-pnl-reader')
            reader.start()
            for event in (app.ready, app.accounts_ready):
                deadline = datetime.now(UTC).timestamp() + 15
                while not event.wait(0.2):
                    if self.stop_event.is_set() or not app.isConnected():
                        return
                    if datetime.now(UTC).timestamp() >= deadline:
                        raise TimeoutError('Timed out waiting for IB P&L account handshake.')
            app.account = self.select_account(app.accounts)
            with self.lock:
                self.data.account = app.account
                self.connected = True
            app.reqAccountSummary(2, 'All', 'NetLiquidation')
            app.reqPositions()
            app.reqPnL(1, app.account, '')
            while not self.stop_event.wait(1) and app.isConnected() and reader.is_alive():
                pass
        finally:
            if app.isConnected():
                app.cancelPnL(1)
                for request in list(app.requests):
                    app.cancelPnLSingle(request)
                app.cancelPositions()
                app.cancelAccountSummary(2)
            app.disconnect()
            if reader is not None:
                reader.join(timeout=2)
