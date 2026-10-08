"""Connection interruption and independent worker supervision regressions."""
from datetime import UTC, datetime, timedelta
from http.client import IncompleteRead
import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.market_data import golden
from systematic_trading.research import analytics_service as module
from systematic_trading.web.strategy_control import calculation_readiness
from systematic_trading.market_data.analytics_store import digest
from systematic_trading.research.analytics_projection import import_lean_histories


@pytest.mark.parametrize('failure', [TimeoutError('timed out'), URLError(TimeoutError('WinError 10060')),
    URLError(ConnectionRefusedError('unavailable')), ConnectionResetError('reset'), IncompleteRead(b'partial')])
@pytest.mark.parametrize('sql', ['SELECT secret_payload FROM private_table', 'INSERT INTO t VALUES (\'secret_payload\')'])
def test_transport_failure_names_dependency_without_secrets_or_retries(monkeypatch, failure, sql):
    calls = []
    def fail(request, **kwargs):
        calls.append(request)
        raise failure
    monkeypatch.setattr(golden.urllib.request, 'urlopen', fail)
    client = golden.ClickHouseMarketDataClient('http://secret_user:secret_password@localhost:8123/private?token=secret_token',
        password='secret_password', timeout_seconds=3)
    with pytest.raises(golden.ClickHouseConnectionError) as error:
        client.execute(sql)
    message = str(error.value)
    assert all(value in message for value in ['ClickHouse', sql.split()[0], 'http://localhost:8123', '3s', 'sleep/resume'])
    assert not any(value in message for value in ['secret_', 'private_table', '/private'])
    assert 'not automatically retried' in message and len(calls) == 1
    assert error.value.__cause__ is failure
    assert isinstance(error.value, OSError)  # Preserve callers' transport-failure handling.


def service(tmp_path):
    events = []
    worker = module.AnalyticsService(AppSettings(data_dir=tmp_path), None, None,
        alert_notifier=SimpleNamespace(notify=events.append))
    worker._started_at = datetime.now(UTC)
    worker._thread = worker._account_thread = worker._archive_thread = SimpleNamespace(is_alive=lambda: True)
    return worker, events


def test_watchdog_alerts_when_all_refreshes_are_blocked_and_no_http_request_arrives(tmp_path):
    worker, events = service(tmp_path)
    old = datetime.now(UTC)-timedelta(hours=3)
    worker._started_at = old
    worker._status.update(research_job='tracked-strategies', research_job_started_at=old.isoformat(),
        operations_completed_at=old.isoformat(), archives_job_started_at=old.isoformat())
    worker._watchdog_tick()
    assert {e.event_type for e in events} >= {'analytics_research_overdue',
        'analytics_operations_overdue', 'analytics_archives_overdue'}
    worker._archive_thread = SimpleNamespace(is_alive=lambda: False)
    worker._watchdog_tick()
    assert events[-1].event_type == 'analytics_archives_stopped'
    assert calculation_readiness(worker.status())['severity'] == 'error'


def test_resume_wakes_every_lane_and_requires_fresh_success_before_clearing(tmp_path):
    worker, events = service(tmp_path)
    now = datetime.now(UTC)
    worker._watchdog_last_tick = now-timedelta(minutes=23)
    worker._watchdog_tick(now=now)
    assert any(e.event_type == 'analytics_host_interruption' for e in events)
    assert all(wake.is_set() for wake in (worker._wake, worker._operations_wake, worker._archive_wake))
    assert '1380 seconds' in worker.status()['errors']['host-interruption']
    worker._complete_interruption_refresh('research', now-timedelta(seconds=1), {})
    worker._complete_interruption_refresh('operations', now, {'database': 'unavailable'})
    assert len(worker.status()['interruption']['pending_lanes']) == 3
    for lane in ['research', 'operations']:
        worker._complete_interruption_refresh(lane, now, {})
    assert 'host-interruption' in worker.status()['errors']
    worker._complete_interruption_refresh('archives', now, {})
    assert 'host-interruption' not in worker.status()['errors']
    assert worker.status()['interruption']['recovered_at']


def test_an_unrelated_failure_cannot_erase_an_unretried_archive_error(tmp_path, monkeypatch):
    worker, _ = service(tmp_path)
    worker.analytics = SimpleNamespace(initialize=lambda: None)
    worker._performance_payload = {'already': 'published'}
    worker._lane_errors['archives'] = {'lean-history': 'Previous connection timeout'}
    observed = []
    def fail(*args):
        raise ValueError('Research artifact corrupted')
    def lean(*args):
        observed.append(dict(worker.status()['errors']))
        return False
    monkeypatch.setattr(module, 'import_json_group', fail)
    monkeypatch.setattr(module, 'import_lean_histories', lean)
    monkeypatch.setattr(module, 'import_raw_market_data', lambda *args: False)
    result = worker.refresh('archives')
    assert observed[0] == {'lean-history': 'Previous connection timeout', 'research-history': 'Research artifact corrupted'}
    assert result['errors'] == {'research-history': 'Research artifact corrupted'}


@pytest.mark.parametrize('state', [{'archives_running': False}, {'watchdog_running': False}, {'watchdog_stale': True}])
def test_archive_and_watchdog_failures_are_operator_visible(state):
    assert calculation_readiness(state)['severity'] == 'error'


def test_watchdog_thread_runs_when_refresh_threads_do_not_progress(tmp_path, monkeypatch):
    from threading import Event
    worker, _ = service(tmp_path)
    ran = Event()
    class Stop:
        def wait(self, interval):
            return ran.is_set()
    worker._stop = Stop()
    monkeypatch.setattr(worker, '_watchdog_tick', ran.set)
    worker._run_watchdog()
    assert ran.is_set()


def test_archive_resumes_from_verified_run_without_recopying_committed_history(tmp_path):
    from test_analytics_projection import MemoryAnalytics
    runs = []
    for key in ('one', 'two'):
        root = tmp_path/key
        root.mkdir()
        artifacts = {}
        for name in ('reference.json', 'economic.json'):
            raw = json.dumps({'nav': [{'date': '2026-10-07', 'value': 123}]}).encode()
            (root/name).write_bytes(raw)
            artifacts[name] = digest(raw)
        runs.append(dict(artifact_path=str(root), payload=dict(receipt=dict(artifacts=artifacts))))
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql):
            return self
        def fetchone(self):
            return {'name': 'ops.lean_research_runs'}
        def fetchall(self):
            return runs
    class PostgresStore:
        def _connect(self):
            return Connection()
    analytics = MemoryAnalytics()
    analytics.publish('lean-history', 'legacy', [{'point_key': 'legacy-evidence'}])
    publish = analytics.publish
    attempted = []
    first_source = 'lean-run/'+digest(str((tmp_path/'one').resolve()))
    second_source = 'lean-run/'+digest(str((tmp_path/'two').resolve()))
    def fail_second(source, *args, **kwargs):
        attempted.append(source)
        if source == second_source:
            raise golden.ClickHouseConnectionError('Interrupted exchange')
        return publish(source, *args, **kwargs)
    analytics.publish = fail_second
    with pytest.raises(golden.ClickHouseConnectionError):
        import_lean_histories(analytics, PostgresStore())
    assert analytics.latest(first_source)
    assert analytics.latest('lean-history')['version'] == 'legacy'
    assert analytics.rows['lean-history'] == [{'point_key': 'legacy-evidence'}]
    def record(source, *args, **kwargs):
        attempted.append(source)
        return publish(source, *args, **kwargs)
    analytics.publish = record
    assert import_lean_histories(analytics, PostgresStore())
    assert attempted.count(first_source) == 1
    assert attempted.count(second_source) == 2
    assert analytics.rows['lean-history'] == []
    assert json.loads(analytics.latest('lean-history')['provenance'])['count'] == 2
    writes = analytics.writes
    assert not import_lean_histories(analytics, PostgresStore())
    assert analytics.writes == writes
    # Even an unchanged published run is rehashed against its registry receipt.
    (tmp_path/'one/reference.json').write_text('{}')
    with pytest.raises(ValueError, match='Registered LEAN series changed'):
        import_lean_histories(analytics, PostgresStore())
    assert analytics.writes == writes
    (tmp_path/'one/reference.json').unlink()
    with pytest.raises(FileNotFoundError, match='Registered LEAN series unavailable'):
        import_lean_histories(analytics, PostgresStore())


def test_operator_refresh_wakes_archive_and_account_retries(tmp_path):
    worker, _ = service(tmp_path)
    worker.request_refresh()
    assert all(wake.is_set() for wake in (worker._wake, worker._operations_wake, worker._archive_wake))


def test_restart_does_not_claim_archive_recovery_before_its_first_refresh(tmp_path):
    worker, _ = service(tmp_path)
    worker._status.update(operations_completed_at=datetime.now(UTC).isoformat(),
        research_completed_at=datetime.now(UTC).isoformat())
    worker._strategy_inputs = dict(price_through='2099-01-01', valuation_through='2099-01-01')
    readiness = calculation_readiness(worker.status())
    assert readiness['severity'] == 'warning'
    assert 'Archives worker is starting' in readiness['message']
    worker._status['archives_completed_at'] = datetime.now(UTC).isoformat()
    assert not worker.status()['archives_initializing']
    assert calculation_readiness(worker.status())['severity'] == 'ok'
