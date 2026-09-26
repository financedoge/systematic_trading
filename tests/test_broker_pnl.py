from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from systematic_trading.config import AppSettings
from systematic_trading.live.broker_pnl import BrokerPnlService, BrokerPnlSnapshot, broker_number


def test_unset_broker_values_are_not_zero():
    for value in [float('nan'), float('inf'), 1.7976931348623157e308, 'bad', None]:
        assert broker_number(value) is None
    assert broker_number(0) == Decimal('0')


def test_currency_identity_staleness_and_disconnect():
    service = BrokerPnlService(AppSettings(ib_pnl_enabled=True))
    now = datetime.now(UTC)
    service.connected = True
    service.data = BrokerPnlSnapshot(received_at=now, daily_pnl=1, unrealized_pnl=1, realized_pnl=0)
    assert service.snapshot(now=now).status != 'live'
    service.data.currency = 'HKD'
    assert service.snapshot(now=now).status == 'live'
    assert service.snapshot(now=now + timedelta(seconds=16)).status == 'stale'
    service.connected = False
    assert service.snapshot(now=now).status == 'stale'
    assert service.select_account(['DU123']) == 'DU123'
    for accounts in [[], ['U123'], ['DU1', 'DU2']]:
        with pytest.raises(ValueError):
            service.select_account(accounts)


def test_readonly_subscription_lifecycle_and_new_session_clears_cache(monkeypatch):
    service = BrokerPnlService(AppSettings(ib_pnl_enabled=True))
    calls = []

    class Client:
        def __init__(self, wrapper):
            self.done = threading.Event()
        def connect(self, *args):
            self.nextValidId(1)
            self.managedAccounts('DU123')
        def run(self):
            self.done.wait(2)
        def isConnected(self):
            return not self.done.is_set()
        def disconnect(self):
            self.done.set()
        def reqAccountSummary(self, *args):
            self.accountSummary(2, 'OTHER', 'NetLiquidation', '1', 'USD')
            assert service.data.currency is None
            self.accountSummary(2, 'DU123', 'NetLiquidation', '1', 'HKD')
        def reqPositions(self):
            contract = SimpleNamespace(conId=42, symbol='SPY', currency='USD')
            self.position('DU123', contract, 2, 100)
            self.position('DU123', contract, 2, 100)
        def reqPnLSingle(self, req, account, model, con):
            calls.append(('single', req, con))
            self.pnlSingle(req, 2, 1, 1, float('inf'), 202)
        def reqPnL(self, *args):
            calls.append(('account',))
            self.pnl(1, 7.8, 7.8, 0)
            self.position('DU123', SimpleNamespace(conId=42, symbol='SPY', currency='USD'), 3, 100)
            row = service.data.positions[0]
            assert row.quantity == 3 and row.daily_pnl is None and row.market_value is None
            assert row.received_at is None
            self.pnlSingle(100, 3, 2, 2, float('inf'), 303)
            service.stop_event.set()
        def cancelPnL(self, *args): calls.append(('cancel_account',))
        def cancelPnLSingle(self, *args): calls.append(('cancel_single',))
        def cancelPositions(self): calls.append(('cancel_positions',))
        def cancelAccountSummary(self, *args): calls.append(('cancel_summary',))

    monkeypatch.setitem(sys.modules, 'ibapi.client', SimpleNamespace(EClient=Client))
    monkeypatch.setitem(sys.modules, 'ibapi.wrapper', SimpleNamespace(EWrapper=type('Wrapper', (), {})))
    service.data.currency = 'OLD'
    service._session()
    result = service.snapshot()
    assert result.status == 'live'
    assert result.currency == 'HKD'
    assert result.positions[0].currency == 'USD'
    assert result.positions[0].realized_pnl is None
    assert [c[0] for c in calls].count('single') == 1
    assert ('cancel_account',) in calls and ('cancel_single',) in calls
    assert ('cancel_positions',) in calls and ('cancel_summary',) in calls


def test_api_disabled_feed_is_explicitly_unavailable(tmp_path):
    from systematic_trading.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path))) as client:
        result = client.get('/api/v1/dashboard/pnl/live').json()
    assert result['status'] == 'unavailable'
    assert result['daily_pnl'] is None
    assert any('disabled' in item for item in result['warnings'])


def test_live_pnl_ui_retains_timestamped_stale_values_and_independent_rows():
    import shutil
    import subprocess
    from systematic_trading.web.operator import _OPERATOR_HTML
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    script = r'''
const assert = require('node:assert/strict');
const html = require('node:fs').readFileSync(0, 'utf8');
const start = html.indexOf('function renderLivePnl(payload)');
const end = html.indexOf('let livePnlLoading', start);
const elements = new Map();
const el = id => { if (!elements.has(id)) elements.set(id, {}); return elements.get(id); };
const esc = String, fmtDateTime = String;
eval(html.slice(start,end));
renderLivePnl({status:'live', currency:'HKD', daily_pnl:0, realized_pnl:null, unrealized_pnl:12});
assert.equal(el('pnl-total').textContent,'0.00');
assert.equal(el('pnl-realized').textContent,'n/a');
renderLivePnl({status:'stale', currency:'HKD', daily_pnl:12, received_at:'2026-09-25T20:00:00Z',
  positions:[{symbol:'SPY',currency:'USD',daily_pnl:9,received_at:'2026-09-25T20:01:00Z',stale:false}]});
assert.equal(el('pnl-total').textContent,'12.00');
assert.match(el('pnl-as-of').textContent,/Last received · stale/);
assert.match(el('live-pnl-table').innerHTML,/9.00/);
assert.match(el('live-pnl-table').innerHTML,/2026-09-25T20:01:00Z/);
assert.equal(el('pnl-open-value').textContent,'HKD');
renderLivePnl({status:'live',currency:'HKD',daily_pnl:Infinity,unrealized_pnl:3});
assert.equal(el('pnl-total').textContent,'n/a');
assert.equal(el('pnl-unrealized').textContent,'3.00');
renderLivePnl({status:'unavailable'});
assert.equal(el('pnl-total').textContent,'n/a');
'''
    subprocess.run([node, '-e', script], input=_OPERATOR_HTML, text=True, encoding='utf-8',
                   capture_output=True, check=True, timeout=20)


def test_browser_keeps_last_received_values_on_http_failure_and_recovers():
    import shutil
    import subprocess
    from systematic_trading.web.operator import _OPERATOR_HTML
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    script = r'''
const assert = require('node:assert/strict');
const html = require('node:fs').readFileSync(0, 'utf8');
let fail = false, output;
const api = async () => {
  if (fail) throw new Error('timeout');
  return {status:'live', currency:'HKD', daily_pnl:12, received_at:'2026-09-25T20:00:00Z',
          positions:[{daily_pnl:3,stale:false}], warnings:[]};
};
const renderLivePnl = value => output = value;
const start = html.indexOf('let livePnlLoading');
eval(html.slice(start, html.indexOf('function renderPnl(payload',start)));
(async () => {
  await loadLivePnl();
  assert.equal(output.status, 'live');
  fail = true;
  await loadLivePnl();
  assert.equal(output.daily_pnl, 12);
  assert.equal(output.connected, false);
  assert.equal(output.positions[0].stale, true);
  assert.match(output.warnings[0], /not current/);
  fail = false;
  await loadLivePnl();
  assert.equal(output.status, 'live');
  assert.deepEqual(output.warnings, []);
})().catch(error => {console.error(error); process.exitCode=1;});
'''
    subprocess.run([node, '-e', script], input=_OPERATOR_HTML, text=True, encoding='utf-8',
                   capture_output=True, check=True, timeout=20)


def test_worker_reconnects_after_failure_and_clears_connection_state(monkeypatch):
    service = BrokerPnlService(AppSettings(ib_pnl_enabled=True))
    attempts = []
    class Stop:
        stopped = False
        def is_set(self): return self.stopped
        def wait(self, seconds):
            assert seconds == service.settings.ib_pnl_reconnect_seconds
            return self.stopped
    service.stop_event = Stop()
    def session():
        attempts.append(1)
        assert not service.connected
        service.connected = True
        if len(attempts) == 1:
            raise ConnectionError('fixture disconnect')
        service.stop_event.stopped = True
    monkeypatch.setattr(service, '_session', session)
    service._run()
    assert len(attempts) == 2 and not service.connected
    assert 'fixture disconnect' in service.error


def test_missing_realized_does_not_hide_other_live_values():
    service = BrokerPnlService(AppSettings(ib_pnl_enabled=True))
    now = datetime.now(UTC)
    service.connected = True
    service.data = BrokerPnlSnapshot(currency='HKD', received_at=now, daily_pnl=42)
    result = service.snapshot(now=now)
    assert result.status == 'live' and result.connected
    assert result.realized_pnl is None
    service.connected = False
    result = service.snapshot(now=now + timedelta(hours=10))
    assert result.status == 'stale' and not result.connected
    assert result.daily_pnl == 42 and result.age_seconds == 36000
    assert any('not an official closing valuation' in warning for warning in result.warnings)
