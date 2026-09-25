"""Broker-owned lifecycle snapshots and audited, conservative paper management."""
from __future__ import annotations

from systematic_trading.execution.ib_compat import compatible_ib_errors, cancel_ib_order

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from threading import Event, Thread
from uuid import uuid4

from pydantic import BaseModel, Field

from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment, ProposalStatus
from systematic_trading.execution.broker import InteractiveBrokersAdapter, InteractiveBrokersOrderRouter, order_spec_for
from systematic_trading.execution.reconciliation import submission_reconciliation_issues
from systematic_trading.execution.window import proposal_is_expired

# The operator API is one broker order writer. DB claims also protect against
# competing processes; the lock prevents same-client-ID connection collisions.
from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
ACTIVE = {"PendingSubmit", "ApiPending", "PreSubmitted", "Submitted", "PendingCancel"}
TERMINAL = {"Cancelled", "ApiCancelled", "Filled"}


def review_token(record):
    return sha256(record.model_dump_json().encode()).hexdigest()


class OrderActionInput(BaseModel):
    expected_token: str
    confirm: bool = False
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    quantity: int | None = Field(default=None, ge=1)
    limit_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)


class GatewayOrderClient:
    """Read all API open orders; modify only same-client, positively matched orders."""
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.app = None
        self.thread = None

    def connect(self, profile):
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper

        class App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.ready = Event()
                self.accounts_ready = Event()
                self.open_done = Event()
                self.completed_done = Event()
                self.accounts = []
                self.rows = {}
                self.raw = {}
                self.events = {}
                self.errors = []

            def nextValidId(self, orderId):
                self.ready.set()

            def managedAccounts(self, accountsList):
                self.accounts = [a for a in accountsList.split(',') if a]
                self.accounts_ready.set()

            def capture(self, contract, order, status, source):
                key = ('completed', int(order.permId)) if source == 'completed' else (int(order.clientId), int(order.orderId))
                previous = self.rows.get(key, {})
                row = dict(previous, broker_order_id=int(order.orderId), client_id=int(order.clientId),
                           perm_id=int(order.permId), order_ref=order.orderRef, account=order.account,
                           symbol=contract.symbol, side=order.action, quantity=str(order.totalQuantity),
                           limit_price=str(order.lmtPrice) if order.orderType == 'LMT' else None,
                           order_type=order.orderType, algo_strategy=order.algoStrategy, tif=order.tif,
                           status=status, source=source, checked_at=datetime.now(UTC).isoformat())
                if source == 'completed' and hasattr(order, 'filledQuantity'):
                    row['filled'] = str(order.filledQuantity)
                self.rows[key] = row
                self.raw[key] = (contract, order)
                self.events.setdefault(key, Event()).set()

            def openOrder(self, orderId, contract, order, orderState):
                order.orderId = orderId
                self.capture(contract, order, orderState.status, 'open')

            def openOrderEnd(self):
                self.open_done.set()

            def completedOrder(self, contract, order, orderState):
                self.capture(contract, order, orderState.status, 'completed')

            def completedOrdersEnd(self):
                self.completed_done.set()

            def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId,
                            parentId, lastFillPrice, clientId, whyHeld, mktCapPrice=0):
                key = (int(clientId), int(orderId))
                self.rows.setdefault(key, {}).update(status=status, filled=str(filled), remaining=str(remaining),
                    average_fill_price=str(avgFillPrice), why_held=whyHeld, checked_at=datetime.now(UTC).isoformat())
                self.events.setdefault(key, Event()).set()

            @compatible_ib_errors
            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
                self.errors.append((reqId, errorCode, errorString))

        self.profile = profile
        self.app = App()
        self.app.connect(profile.host, profile.port, profile.client_id)
        self.thread = Thread(target=self.app.run, daemon=True)
        self.thread.start()
        if not self.app.ready.wait(self.timeout) or not self.app.accounts_ready.wait(self.timeout):
            raise TimeoutError('Gateway handshake/account discovery timed out.')
        if not self.app.accounts or any(not a.startswith('DU') for a in self.app.accounts):
            raise ValueError('Only a verified IB paper account is supported.')

    def snapshot(self):
        app = self.app
        app.rows.clear()
        app.raw.clear()
        app.open_done.clear()
        app.completed_done.clear()
        app.reqAllOpenOrders()
        if not app.open_done.wait(self.timeout):
            raise TimeoutError('Open-order snapshot incomplete; no actions were sent.')
        app.reqCompletedOrders(False)
        if not app.completed_done.wait(self.timeout):
            raise TimeoutError('Completed-order snapshot incomplete; retry sync.')
        return [dict(row) for row in app.rows.values() if 'order_ref' in row]

    def change(self, observation, action, quantity=None, limit_price=None):
        key = (observation['client_id'], observation['broker_order_id'])
        event = self.app.events.setdefault(key, Event())
        event.clear()
        if action == 'cancel':
            cancel_ib_order(self.app, key[1])
        else:
            contract, order = self.app.raw[key]
            order.totalQuantity = quantity
            order.lmtPrice = float(limit_price)
            self.app.placeOrder(key[1], contract, order)
        # Receipt is not a terminal outcome. Only a later broker snapshot can
        # resolve the persisted pending action, including after a process crash.
        event.wait(self.timeout)

    def disconnect(self):
        if self.app:
            self.app.disconnect()
        if self.thread:
            self.thread.join(timeout=2)


def matching(record, row, client_id):
    previous = record.broker_observation or (record.pending_action or {}).get('before', {})
    identity = (row.get('broker_order_id') == record.broker_order_id and row.get('client_id') == client_id)
    if row.get('source') == 'completed' and row.get('client_id') == 0:
        # completedOrder does not carry the API client/order IDs in IB API 9.81.
        # Require the permanent identity previously observed on this attempt.
        identity = bool(previous.get('perm_id')) and row.get('perm_id') == previous['perm_id']
    return (identity and row.get('order_ref') == record.order_ref
            and row.get('symbol') == record.order.symbol
            and row.get('side', '').lower() == record.order.side.value
            and str(row.get('account', '')).startswith('DU')
            and (not previous.get('account') or row.get('account') == previous['account']))


def apply_observation(record, row):
    observation = dict(row, broker_order_id=record.broker_order_id)
    pending = record.pending_action
    updates = {'broker_observation': observation, 'management_revision': record.management_revision + 1,
               'updated_at': record.updated_at}
    # Execution quantities still come exclusively from immutable executions.
    status = row.get('status')
    if status in {'Cancelled', 'ApiCancelled'}:
        updates['status'] = BrokerOrderStatus.CANCELLED
    elif status in {'Submitted', 'PreSubmitted'} and record.filled_quantity == 0:
        updates['status'] = BrokerOrderStatus.ACKNOWLEDGED
    audit = list(record.management_audit)
    if pending:
        resolved = status in TERMINAL
        if pending['action'] == 'amend' and status in (ACTIVE | TERMINAL) and status != 'PendingCancel':
            terms_match = (Decimal(str(row.get('quantity', -1))) == Decimal(str(pending['quantity']))
                        and Decimal(str(row.get('limit_price') or -1)) == Decimal(str(pending['limit_price'])))
            resolved = resolved or terms_match
            if terms_match:
                updates['order'] = record.order.model_copy(update={'quantity': pending['quantity'],
                    'reference_price': Decimal(pending['limit_price']),
                    'notional_cnh': record.order.notional_cnh * Decimal(pending['quantity']) / record.order.quantity
                        * Decimal(pending['limit_price']) / record.order.reference_price})
        if resolved:
            updates['pending_action'] = None
            audit.append(dict(pending, outcome='broker_confirmed', broker_status=status,
                              completed_at=datetime.now(UTC).isoformat()))
            updates['management_audit'] = audit
    if updates.get('status', record.status) != record.status or updates.get('management_audit'):
        updates['updated_at'] = datetime.now(UTC)
    return record.model_copy(update=updates)


def sync_orders(settings, store, client=None):
    client = client or GatewayOrderClient()
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER)
    with ORDER_CONNECTION_LOCK:
        try:
            client.connect(profile)
            rows = client.snapshot()
            for record in store.list_broker_order_records():
                if record.environment != OrderEnvironment.PAPER:
                    continue
                found = [r for r in rows if matching(record, r, profile.client_id)]
                if len(found) == 1:
                    found[0].update(broker_order_id=record.broker_order_id, client_id=profile.client_id)
                    store.update_order_management(record.local_order_id, lambda current, row=found[0]:
                        apply_observation(current, row) if matching(current, row, profile.client_id) else current)
            return {'checked_at': datetime.now(UTC).isoformat(), 'orders': rows,
                    'note': 'Open orders and broker-retained completed orders; absence does not prove cancellation.'}
        finally:
            client.disconnect()


def manage_order(settings, store, local_order_id, action, request, client=None):
    if not request.confirm:
        raise ValueError('Explicit confirmation of the reviewed order is required.')
    if not request.operator.strip() or not request.reason.strip():
        raise ValueError('Operator and reason are required.')
    if action not in {'cancel', 'amend', 'resubmit'}:
        raise ValueError('Unsupported order action.')
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER)
    with ORDER_CONNECTION_LOCK:
        record = next((r for r in store.list_broker_order_records() if r.local_order_id == local_order_id), None)
        if record is None:
            raise KeyError(local_order_id)
        if record.environment != OrderEnvironment.PAPER or record.order.environment != OrderEnvironment.PAPER:
            raise ValueError('Live order management is disabled.')
        if review_token(record) != request.expected_token or record.pending_action:
            raise ValueError('Order changed or an action is unresolved. Sync and review again.')
        if action != 'cancel':
            proposal = store.get_proposal(record.proposal_id)
            if not proposal or proposal.status != ProposalStatus.APPROVED or proposal_is_expired(proposal, settings):
                raise ValueError('A current approved proposal is required; execution window may have expired.')
            issues = submission_reconciliation_issues(settings)
            if issues or record.execution_sync_issue:
                raise ValueError(' '.join(issues) or record.execution_sync_issue)
        if action == 'resubmit':
            if record.status not in {BrokerOrderStatus.CANCELLED, BrokerOrderStatus.REJECTED} or record.filled_quantity:
                raise ValueError('Only a definitively failed, unfilled order can be resubmitted.')
            retry_client = client or GatewayOrderClient()
            try:
                retry_client.connect(profile)
                confirmed = [r for r in retry_client.snapshot() if matching(record, r, profile.client_id)]
                if len(confirmed) != 1 or confirmed[0].get('status') not in {'Cancelled', 'ApiCancelled'}:
                    raise ValueError('Fresh definitive broker cancellation required before resubmission.')
                observation = confirmed[0]
            finally:
                retry_client.disconnect()
            if not observation or Decimal(str(observation.get('filled', '-1'))) != 0:
                raise ValueError('Broker-confirmed zero fills required before resubmission.')
            def audit_retry(current):
                if review_token(current) != request.expected_token or current.pending_action:
                    raise ValueError('Order changed. Sync and review again.')
                return current.model_copy(update={'updated_at': datetime.now(UTC), 'management_revision': current.management_revision + 1,
                    'message': f'Operator {request.operator} requested resubmission: {request.reason}',
                    'management_audit': [*current.management_audit, dict(action='resubmit',
                        operator=request.operator, reason=request.reason, outcome='routing_requested',
                        requested_at=datetime.now(UTC).isoformat(), before=current.model_dump(mode='json',
                            exclude={'management_audit'}))]})
            store.update_order_management(local_order_id, audit_retry)
            # Retain the exact routed terms, not the pre-routing proposal order type.
            orders = list(proposal.orders)
            orders[record.order_index] = record.order
            proposal = proposal.model_copy(update={'orders': orders})
            router = InteractiveBrokersOrderRouter(settings)
            result = router.submit_approved_proposal(proposal=proposal, store=store, allow_resubmit=True,
                                                     order_indexes={record.order_index})
            if result.validation_issues:
                raise ValueError(' '.join(result.validation_issues))
            return result.model_dump(mode='json')
        client = client or GatewayOrderClient()
        try:
            client.connect(profile)
            rows = client.snapshot()
            found = [r for r in rows if matching(record, r, profile.client_id)]
            if len(found) != 1 or found[0].get('status') not in ACTIVE or found[0].get('source') != 'open':
                raise ValueError('No uniquely matched working order owned by this API client. Sync and review.')
            observation = found[0]
            if observation['status'] == 'PendingCancel':
                raise ValueError('IB cancellation is already pending.')
            quantity, limit_price = request.quantity, request.limit_price
            if action == 'amend':
                if observation.get('order_type') != 'LMT' or observation.get('algo_strategy'):
                    raise ValueError('Only plain limit orders can be amended; cancel/review a new proposal for algorithms.')
                if quantity is None or limit_price is None:
                    raise ValueError('Total quantity and limit price are required.')
                if 'filled' not in observation:
                    raise ValueError('Fresh broker fill quantity unavailable; sync again.')
                if quantity > record.order.quantity or quantity <= Decimal(observation['filled']):
                    raise ValueError('Quantity must exceed filled quantity and cannot increase approved exposure.')
                approved_limit = order_spec_for(record.order, order_ref=record.order_ref).limit_price
                if approved_limit is None or (record.order.side.value == 'buy' and limit_price > approved_limit
                    or record.order.side.value == 'sell' and limit_price < approved_limit):
                    raise ValueError('Price must stay within the approved limit; create a new proposal to expand it.')
            claim = dict(action_id=uuid4().hex, action=action, operator=request.operator, reason=request.reason,
                         requested_at=datetime.now(UTC).isoformat(), quantity=quantity,
                         limit_price=str(limit_price) if limit_price is not None else None,
                         before=observation, outcome='pending')
            def reserve(current):
                if review_token(current) != request.expected_token or current.pending_action:
                    raise ValueError('Order changed while reviewing. Sync and review again.')
                return current.model_copy(update={'updated_at': datetime.now(UTC), 'pending_action': claim, 'broker_observation': observation,
                    'management_revision': current.management_revision + 1,
                    'message': f'Operator {request.operator} requested {action}: {request.reason}',
                    'management_audit': [*current.management_audit, claim]})
            store.update_order_management(local_order_id, reserve)
            try:
                client.change(observation, action, quantity, limit_price)
            except Exception as exc:
                # Durable pending claim remains: disconnect is not proof of failure.
                return {'outcome': 'uncertain', 'message': f'Gateway outcome unknown; sync before another action: {exc}'}
            return {'outcome': 'pending', 'message': 'Request sent. Sync to confirm the broker outcome.'}
        finally:
            client.disconnect()
