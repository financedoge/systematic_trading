"""Broker credit previews only. This service cannot submit executable orders."""
from datetime import UTC, datetime
from threading import Event, Thread

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors
from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK


def preview_permissions(settings, identities, *, account, client_id=283, timeout=15):
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.wrapper import EWrapper

    if not account.startswith('DU'):
        raise ValueError('Paper account required for permission previews')
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER)

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.finished, self.states, self.errors = [], {}, {}, []

        def nextValidId(self, orderId):  # noqa: N802
            self.next_id = orderId
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [a.strip() for a in accountsList.split(',') if a.strip()]
            self.accounts_seen.set()

        def openOrder(self, orderId, contract, order, orderState):  # noqa: N802
            if orderId in self.finished:
                fields = ('status', 'initMarginBefore', 'initMarginAfter', 'maintMarginBefore',
                          'maintMarginAfter', 'commission', 'commissionCurrency', 'warningText')
                self.states[orderId] = {k:str(getattr(orderState,k,'')) for k in fields}
                self.finished[orderId].set()

        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):  # noqa: N802
            self.errors.append(dict(request=reqId, code=errorCode, message=errorString))
            if reqId in self.finished:
                self.finished[reqId].set()

    app, thread, result = App(), None, {}
    with ORDER_CONNECTION_LOCK:
        try:
            app.connect(profile.host, profile.port, client_id)
            thread = Thread(target=app.run, daemon=True)
            thread.start()
            if not app.ready.wait(timeout):
                raise TimeoutError('Paper preview handshake timed out')
            app.reqManagedAccts()
            if not app.accounts_seen.wait(timeout) or app.accounts != [account]:
                raise ValueError('Paper preview account mismatch')
            for offset, (symbol, identity) in enumerate(identities.items()):
                if identity['status'] != 'identity_verified':
                    raise ValueError('Unverified preview identity: ' + symbol)
                contract = Contract()
                details = identity['details']['contract']
                for field in ('conId', 'symbol', 'secType', 'currency', 'primaryExchange'):
                    setattr(contract, field, details[field])
                contract.exchange = 'SMART'
                if contract.secType != 'STK' or contract.currency != 'USD' or contract.conId <= 0:
                    raise ValueError('Unsupported preview contract: ' + symbol)
                order = Order()
                order.action, order.orderType, order.totalQuantity = 'BUY', 'MKT', 1
                order.account, order.tif = account, 'DAY'
                order.eTradeOnly = order.firmQuoteOnly = False
                # IB uses placeOrder to request this calculation. The hard-coded
                # whatIf flag prevents it from being sent to an execution venue.
                order.whatIf = True
                order.transmit = True
                order.orderRef = 'st-permission-preview-' + symbol
                request = app.next_id + offset
                app.finished[request] = Event()
                app.placeOrder(request, contract, order)
                completed = app.finished[request].wait(timeout)
                errors = [e for e in app.errors if e['request'] in {-1, request}
                          and e['code'] not in {2104,2106,2107,2108,2158}]
                if not completed:
                    errors.append(dict(message='Permission preview timed out'))
                result[symbol] = dict(kind='ib_paper_what_if', what_if=True, account=account,
                    con_id=contract.conId, captured_at=datetime.now(UTC).isoformat(),
                    state=app.states.get(request, {}), errors=errors)
        finally:
            app.disconnect()
            if thread is not None:
                thread.join(timeout=2)
    return result
