import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from systematic_trading.execution.broker import IbApiExecutionSyncClient, _parse_ib_execution_time
from systematic_trading.execution.fills import merge_execution_fills
from systematic_trading.execution.evidence import retain_execution_response
from test_execution_history import store, fill, sync


@pytest.fixture
def broker(monkeypatch, tmp_path):
    client = pytest.importorskip('ibapi.client').EClient
    monkeypatch.setattr(client, 'connect', lambda self, *args: self.nextValidId(1))
    monkeypatch.setattr(client, 'run', lambda self: None)
    monkeypatch.setattr(client, 'disconnect', lambda self: None)
    monkeypatch.setattr(client, 'serverVersion', lambda self: 223)
    requests = []

    def query(changes=None, outcome='complete'):
        def request(app, request_id, filter):
            requests.append(filter.lastNDays)
            execution = dict(execId='trade-a.01', acctNumber='DU123', orderId=10,
                orderRef='st-proposal-00', side='BOT', shares=4, price=100, cumQty=4,
                time='20260803 11:00:00 US/Eastern', pendingPriceRevision=False)
            execution.update(changes or {})
            app.execDetails(request_id, SimpleNamespace(symbol='SPY', currency='USD'), SimpleNamespace(**execution))
            if outcome == 'error':
                app.error(request_id, 321, 'Invalid execution query')
            elif outcome == 'disconnect':
                app.connectionClosed()
            else:
                app.execDetailsEnd(request_id)
        monkeypatch.setattr(client, 'reqExecutions', request)
        return IbApiExecutionSyncClient(evidence_dir=tmp_path / 'evidence').fetch_fills(
            SimpleNamespace(host='unused', port=0, client_id=1))

    return query, requests


def test_seven_day_replay_and_transport_metadata_are_idempotent(broker, store):
    query, requests = broker
    first = query()
    sync(store, first)
    before = store.list_broker_order_records()[0]
    assert Path(first[0].evidence_ref).is_file()
    again = query({'orderId': 900, 'time': '20260803-15:00:00'})
    assert first[0].evidence_ref != again[0].evidence_ref
    sync(store, again)
    assert store.list_broker_order_records()[0] == before
    assert requests == [7, 7]


@pytest.mark.parametrize('raw', ['', '20260803', '20260803 11:00:00', 'nonsense',
    '20260803 11:00:00 Mars/Olympus', '20260308 02:30:00 America/New_York',
    '20261101 01:30:00 US/Eastern'])
def test_missing_malformed_or_ambiguous_times_never_become_now(raw):
    with pytest.raises(ValueError):
        _parse_ib_execution_time(raw)


def test_midnight_and_timezones_resolve_to_one_instant():
    assert _parse_ib_execution_time('20261003 00:05:05 Asia/Hong_Kong') == datetime(2026, 10, 2, 16, 5, 5, tzinfo=UTC)
    assert _parse_ib_execution_time('20261002 12:05:05 US/Eastern') == _parse_ib_execution_time('20261002-16:05:05')


@pytest.mark.parametrize('changes, expected', [
    ({'time': 'unsupported'}, 'timestamp'),
    ({'shares': '4.5'}, 'whole positive'),
    ({'price': 'NaN'}, 'invalid price'),
    ({'cumQty': 'missing'}, 'snapshot rejected'),
    ({'pendingPriceRevision': True}, 'price revision is pending'),
])
def test_bad_callbacks_reject_whole_read_and_retain_raw_evidence(broker, store, tmp_path, changes, expected):
    query, _ = broker
    before = store.list_broker_order_records()[0]
    with pytest.raises(ValueError, match=expected):
        sync(store, query(changes))
    assert store.list_broker_order_records()[0] == before
    latest = json.loads((tmp_path / 'evidence/latest-1.json').read_text())
    raw = json.loads(Path(latest['evidence_ref']).read_text())
    assert raw['rows'][0]['execution'][next(iter(changes))] == str(next(iter(changes.values())))


@pytest.mark.parametrize('outcome', ['error', 'disconnect'])
def test_partial_or_failed_requests_are_never_successful_snapshots(broker, store, tmp_path, outcome):
    query, _ = broker
    with pytest.raises(RuntimeError, match='snapshot failed'):
        sync(store, query(outcome=outcome))
    assert not store.list_broker_order_records()[0].execution_fills
    latest = json.loads((tmp_path / 'evidence/latest-1.json').read_text())
    assert latest['completed'] is False and latest['request_error']


def test_conflict_retains_both_versions_differences_and_survives_stale_write(store):
    sync(store, [fill()])
    stale = store.list_broker_order_records()[0]
    changed = fill(price='101', evidence_ref='retained/raw.json')
    sync(store, [changed])
    blocked = store.list_broker_order_records()[0]
    assert 'average_price' in blocked.execution_sync_issue
    audit = blocked.execution_conflicts[0]
    assert audit.previous_fills == stale.execution_fills
    assert audit.incoming_fills == [changed]
    assert audit.differences['trade-a.01']['average_price'] == {'stored': '100', 'incoming': '101'}
    assert merge_execution_fills(blocked, [changed]) == blocked
    assert merge_execution_fills(blocked, [fill()]) == blocked
    store.save_broker_order_record(stale)
    persisted = store.list_broker_order_records()[0]
    assert persisted.execution_conflicts == [audit]
    assert persisted.average_fill_price == Decimal('100')


def test_raw_archive_deduplicates_and_detects_tampering(tmp_path):
    response = dict(completed=True, rows=[])
    path = retain_execution_response(tmp_path, response, client_id=1, captured_at='first')
    assert path == retain_execution_response(tmp_path, response, client_id=1, captured_at='second')
    Path(path).write_text('changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        retain_execution_response(tmp_path, response, client_id=1, captured_at='third')
