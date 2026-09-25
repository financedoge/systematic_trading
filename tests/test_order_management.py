from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment, OrderType, ProposalStatus
from systematic_trading.execution.management import (
    OrderActionInput, apply_observation, manage_order, review_token, sync_orders,
)
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store
from test_execution_history import fill


@pytest.fixture
def prepared(backend_store, tmp_path):
    store = backend_store
    record = store.list_broker_order_records()[0]
    order = record.order.model_copy(update={'order_type': OrderType.LIMIT})
    store.save_broker_order_record(record.model_copy(update={'order': order}))
    proposal = store.get_proposal('proposal').model_copy(update={'status': ProposalStatus.APPROVED,
        'orders': [order], 'execution_deadline_at': datetime.now(UTC) + timedelta(hours=1)})
    store.save_proposal(proposal)
    path = tmp_path / 'reconciliation' / 'ib_paper_reconciliation_latest.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(IBPaperReconciliationReport(checked_at=datetime.now(UTC), local_order_history_count=1,
        local_order_count=1, local_filled_order_count=0, ib_fill_count=0, ib_position_count=0).model_dump_json())
    return store, AppSettings(data_dir=tmp_path)


def row(**changes):
    return dict(dict(order_ref='st-proposal-00', broker_order_id=10, client_id=101, perm_id=333,
        account='DU123', symbol='SPY', side='BUY', quantity='10', filled='0', remaining='10',
        limit_price='100', order_type='LMT', algo_strategy='', status='Submitted', source='open',
        checked_at=datetime.now(UTC).isoformat()), **changes)


class Gateway:
    def __init__(self, rows=None, fail=False):
        self.rows = [row()] if rows is None else rows
        self.fail = fail
        self.changes = []
        self.disconnected = False
    def connect(self, profile):
        self.profile = profile
    def snapshot(self):
        return self.rows
    def change(self, *args):
        self.changes.append(args)
        if self.fail:
            raise TimeoutError('disconnected')
    def disconnect(self):
        self.disconnected = True


def request(store, **changes):
    return OrderActionInput(expected_token=review_token(store.list_broker_order_records()[0]),
        confirm=True, operator='test', reason='reviewed', **changes)


def test_cancel_pending_until_broker_confirmation_and_audited(prepared):
    store, settings = prepared
    stale = store.list_broker_order_records()[0]
    client = Gateway()
    result = manage_order(settings, store, 'local', 'cancel', request(store), client)
    assert result['outcome'] == 'pending'
    assert client.disconnected and len(client.changes) == 1
    record = store.list_broker_order_records()[0]
    assert record.pending_action['action'] == 'cancel'
    assert record.status == BrokerOrderStatus.SUBMITTED
    store.save_broker_order_record(stale)
    assert store.list_broker_order_records()[0].pending_action
    sync_orders(settings, store, Gateway([row(status='Cancelled', source='completed')]))
    record = store.list_broker_order_records()[0]
    assert record.status == BrokerOrderStatus.CANCELLED
    assert record.pending_action is None
    assert [a['outcome'] for a in record.management_audit] == ['pending', 'broker_confirmed']


def test_timeout_never_releases_claim_or_repeats_action(prepared):
    store, settings = prepared
    client = Gateway(fail=True)
    req = request(store)
    assert manage_order(settings, store, 'local', 'cancel', req, client)['outcome'] == 'uncertain'
    with pytest.raises(ValueError, match='changed|unresolved'):
        manage_order(settings, store, 'local', 'cancel', req, client)
    assert len(client.changes) == 1
    sync_orders(settings, store, Gateway([]))
    assert store.list_broker_order_records()[0].pending_action


@pytest.mark.parametrize('change', [{'client_id': 999}, {'order_ref': 'foreign'}, {'account': 'U123'},
    {'symbol': 'QQQ'}, {'side': 'SELL'}, {'status': 'Filled'}, {'status': 'PendingCancel'}])
def test_foreign_or_terminal_orders_cannot_be_modified(prepared, change):
    store, settings = prepared
    client = Gateway([row(**change)])
    with pytest.raises(ValueError):
        manage_order(settings, store, 'local', 'cancel', request(store), client)
    assert not client.changes


@pytest.mark.parametrize('quantity,price', [(11,'100'),(5,'101'),(1,'99')])
def test_amend_envelope_and_fill_race(prepared, quantity, price):
    store, settings = prepared
    client = Gateway([row(filled='2')])
    with pytest.raises(ValueError):
        manage_order(settings, store, 'local', 'amend', request(store,quantity=quantity,limit_price=price), client)
    assert not client.changes


def test_amend_waits_for_exact_broker_terms_and_preserves_fills(prepared):
    store, settings = prepared
    manage_order(settings, store, 'local', 'amend', request(store,quantity=8,limit_price='99'), Gateway())
    sync_orders(settings, store, Gateway())
    assert store.list_broker_order_records()[0].pending_action
    store.apply_broker_execution_fills('local', [fill()])
    sync_orders(settings, store, Gateway([row(quantity='8',limit_price='99',filled='4',remaining='4')]))
    record = store.list_broker_order_records()[0]
    assert record.pending_action is None
    assert record.order.quantity == 8 and record.order.reference_price == Decimal('99')
    assert record.filled_quantity == 4 and record.remaining_quantity == 4
    assert len(record.execution_fills) == 1


def test_concurrent_action_claims_only_one_wins(prepared):
    store, settings = prepared
    req = request(store)
    barrier = Barrier(2)
    def claim(_):
        barrier.wait(timeout=5)
        def update(record):
            if review_token(record) != req.expected_token:
                raise ValueError('stale')
            return record.model_copy(update={'management_revision': record.management_revision + 1,
                'pending_action': {'action': 'cancel'}})
        try:
            store.update_order_management('local', update)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == [False, True]


def test_amend_requires_approval_fresh_reconciliation_and_confirmation(prepared):
    store, settings = prepared
    req = request(store,quantity=5,limit_price='99')
    with pytest.raises(ValueError,match='confirmation'):
        manage_order(settings,store,'local','cancel',req.model_copy(update={'confirm':False}),Gateway())
    store.save_proposal(store.get_proposal('proposal').model_copy(update={'status':ProposalStatus.PENDING}))
    with pytest.raises(ValueError,match='approved'):
        manage_order(settings,store,'local','amend',req,Gateway())
    # Cancellation must remain available when risk-increasing routing is blocked.
    (settings.data_dir/'reconciliation'/'ib_paper_reconciliation_latest.json').unlink()
    assert manage_order(settings,store,'local','cancel',req,Gateway())['outcome']=='pending'


def test_workspace_api_and_confirm_guard(tmp_path):
    with TestClient(create_app(AppSettings(database_path=tmp_path/'api.db',data_dir=tmp_path))) as client:
        client.app.state.ib_management_client = Gateway([])
        assert client.post('/api/v1/execution/interactive-brokers/orders/sync').status_code == 200
        payload = client.get('/api/v1/execution/interactive-brokers/workspace').json()
        assert payload['records'] == [] and payload['snapshot']['orders'] == []
        assert client.post('/api/v1/execution/interactive-brokers/orders/missing/cancel',json={
            'expected_token':'x','confirm':False,'operator':'test','reason':'test'}).status_code == 409
        html=client.get('/operator').text
        assert 'Sync orders' in html and 'order-action-dialog' in html and 'Sync portfolio' in html


def test_resubmit_preserves_identity_and_audit(prepared, monkeypatch):
    from systematic_trading.execution import management
    from systematic_trading.execution.broker import InteractiveBrokersOrderRouter
    from test_ib_execution import FakeIBClient
    store, settings = prepared
    sync_orders(settings,store,Gateway([row(status='Cancelled',source='completed')]))
    fake = FakeIBClient(first_order_id=20)
    monkeypatch.setattr(management,'InteractiveBrokersOrderRouter',lambda settings:
        InteractiveBrokersOrderRouter(settings,client=fake))
    result=manage_order(settings,store,'local','resubmit',request(store),Gateway([row(status='Cancelled',source='completed')]))
    assert len(result['records'])==1 and len(fake.placed_orders)==1
    record=store.list_broker_order_records()[0]
    assert record.local_order_id=='local' and record.broker_order_id==20
    assert record.management_audit[-1]['action']=='resubmit'
    assert record.broker_observation=={}


def test_completed_callback_keeps_distinct_permanent_ids_and_matches_attempt(prepared,monkeypatch):
    from ibapi.client import EClient
    from ibapi.order import Order
    from ibapi.contract import Contract
    from ibapi.order_state import OrderState
    from systematic_trading.execution.management import GatewayOrderClient,matching
    from systematic_trading.execution.broker import InteractiveBrokersAdapter
    store,settings=prepared
    monkeypatch.setattr(EClient,'connect',lambda self,*args:(self.nextValidId(1),self.managedAccounts('DU123')))
    monkeypatch.setattr(EClient,'run',lambda self:None)
    monkeypatch.setattr(EClient,'disconnect',lambda self:None)
    monkeypatch.setattr(EClient,'reqAllOpenOrders',lambda self:self.openOrderEnd())
    def completed(app,*args):
        for permanent in [333,444]:
            order=Order();order.permId=permanent;order.orderRef='st-proposal-00';order.account='DU123'
            order.action='BUY';order.totalQuantity=10;order.filledQuantity=0;order.orderType='LMT';order.lmtPrice=100
            contract=Contract();contract.symbol='SPY'
            state=OrderState();state.status='Cancelled'
            app.completedOrder(contract,order,state)
        app.completedOrdersEnd()
    monkeypatch.setattr(EClient,'reqCompletedOrders',completed)
    client=GatewayOrderClient(timeout=.1)
    try:
        client.connect(InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER))
        rows=client.snapshot()
        assert len(rows)==2
        record=store.list_broker_order_records()[0].model_copy(update={'broker_observation':row()})
        assert [matching(record,r,101) for r in rows]==[True,False]
        assert all(r['filled']=='0' for r in rows)
    finally:client.disconnect()


def test_snapshot_failure_never_changes_local_order(prepared):
    store,settings=prepared
    before=store.list_broker_order_records()[0]
    class Broken(Gateway):
        def snapshot(self):raise TimeoutError('incomplete')
    client=Broken()
    with pytest.raises(TimeoutError):sync_orders(settings,store,client)
    assert store.list_broker_order_records()[0]==before and client.disconnected


def test_management_does_not_reemit_existing_fills(prepared):
    store,settings=prepared
    store.apply_broker_execution_fills('local',[fill()])
    before=[e for e in store.list_pending_platform_events() if e.event_id.startswith('fill.recorded.')]
    manage_order(settings,store,'local','cancel',request(store),Gateway([row(filled='4')]))
    sync_orders(settings,store,Gateway([row(status='Cancelled',source='completed',filled='4')]))
    after=[e for e in store.list_pending_platform_events() if e.event_id.startswith('fill.recorded.')]
    assert len(before)==len(after)==1


def test_broker_fill_before_execution_sync_blocks_legacy_retry(prepared):
    from systematic_trading.execution.broker import InteractiveBrokersOrderRouter
    store,settings=prepared
    sync_orders(settings,store,Gateway([row(status='Cancelled',source='completed',filled='4')]))
    record=store.list_broker_order_records()[0]
    assert record.filled_quantity==0
    issues=InteractiveBrokersOrderRouter(settings).validate_proposal_for_submission(
        proposal=store.get_proposal('proposal'),store=store,allow_resubmit=True)
    assert any('broker fill evidence' in issue for issue in issues)
    assert not store.reserve_broker_order_record(record.model_copy(update={
        'broker_order_id':30,'status':BrokerOrderStatus.PENDING_SUBMIT}),allow_resubmit=True)
