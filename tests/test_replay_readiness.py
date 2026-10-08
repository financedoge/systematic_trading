"""Fault-injection coverage for after-close replay and operator-visible failures."""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.lean.session_boundary import set_completed_end_date
from systematic_trading.live.strategy_control import handover_phase
from systematic_trading.research.analytics_service import AnalyticsService
from systematic_trading.web.strategy_control import calculation_readiness


def test_native_calendar_does_not_import_live_or_database_packages(tmp_path):
    (tmp_path/'quotes').mkdir()
    (tmp_path/'quotes/SPY.csv').write_text('2026-10-07T16:00:00,100,close\n')
    source = Path(__file__).resolve().parents[1]/'src'
    script = '''
import sys, builtins
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def isolated_import(name, *args, **kwargs):
    if name.startswith(('systematic_trading.live', 'psycopg', 'ibapi')):
        raise ImportError('Offline engine must not need '+name)
    return original(name, *args, **kwargs)
builtins.__import__ = isolated_import
from datetime import UTC, datetime
from pathlib import Path
from systematic_trading.lean.session_boundary import set_completed_end_date
class Algorithm:
    def set_time_zone(self, zone): self.zone = zone
    def set_end_date(self, end): self.end_date = end
a = Algorithm()
set_completed_end_date(a, Path(sys.argv[2]), datetime(2026,10,7), ['SPY'], now=datetime(2026,10,7,21,tzinfo=UTC))
assert a.end_date == datetime(2026,10,7) and a.zone == 'America/New_York'
assert 'systematic_trading.live' not in sys.modules
'''
    subprocess.run([sys.executable, '-I', '-c', script, str(source), str(tmp_path)], check=True,
                   capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize('line', ['Runtime Error: Partial LEAN output; missing session',
    "20261008 ERROR:: Engine.Run(): During initialization: No module named 'psycopg'"])
def test_native_failure_retains_actionable_engine_error(tmp_path, line):
    from systematic_trading.lean.runner import replay_failure_detail
    (tmp_path/'lean.log').write_text('Engine started\n'+line+'\nEngine stopped\n')
    assert replay_failure_detail(tmp_path, RuntimeError('docker exit 1')) == line


def test_model_batch_mismatch_exposes_date_and_underlying_replay_failure(tmp_path, monkeypatch):
    from systematic_trading.live import strategy_models as module
    definition = SimpleNamespace(key='F3', name='Defensive ETFs', to_dict=lambda: {'key':'F3'})
    document = ({'payload':json.dumps({'strategyDefinition':definition.to_dict()})},
                {'provenance':json.dumps({'inputs':{'batch':'old-batch','price_through':'2026-10-06'}})})
    monkeypatch.setattr(module.AnalyticsStore, 'from_settings', lambda _: SimpleNamespace(document=lambda *args: document))
    path = tmp_path/'run/strategy-compute.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'phase':'failed','error':'F3: missing session 2026-10-07'}))
    with pytest.raises(ValueError) as error:
        module.published_rolling_schedule(AppSettings(data_dir=tmp_path), definition, 'new-batch')
    assert all(text in str(error.value) for text in ('Defensive ETFs','2026-10-06','old-batch',
        'new-batch','F3: missing session 2026-10-07','blocked'))
    path.write_text('corrupted status')
    with pytest.raises(ValueError, match='Calculation status is unreadable'):
        module.published_rolling_schedule(AppSettings(data_dir=tmp_path), definition, 'new-batch')


class ClampingAlgorithm:
    def __init__(self, now):
        self.now, self.zone = now, 'America/New_York'

    def set_time_zone(self, zone):
        self.zone = zone

    def set_end_date(self, end):
        yesterday = self.now.astimezone(ZoneInfo(self.zone)).date()-timedelta(days=1)
        self.end_date = datetime.combine(min(end.date(), yesterday), datetime.min.time())


@pytest.mark.parametrize('day,close', [('2026-10-07','16:00:00'), ('2026-11-27','13:00:00'),
                                      ('2026-12-01','16:00:00')])
def test_both_replays_retain_just_completed_session_without_future_prices(tmp_path, day, close):
    end = datetime.fromisoformat(day)
    now = datetime.fromisoformat(day+'T'+close).replace(tzinfo=ZoneInfo('America/New_York'))
    algorithm = ClampingAlgorithm(now)
    algorithm.set_end_date(end)
    assert algorithm.end_date.date() < end.date()  # Reproduce the incident.
    (tmp_path/'quotes').mkdir()
    for symbol in ('SPY','TLT'):
        (tmp_path/'quotes'/f'{symbol}.csv').write_text(f'{day}T{close},100,close\n')
    with pytest.raises(ValueError, match='completed US market session'):
        set_completed_end_date(algorithm, tmp_path, end, ['SPY','TLT'], now=now-timedelta(seconds=1))
    set_completed_end_date(algorithm, tmp_path, end, ['SPY','TLT'], now=now)
    assert algorithm.end_date == end and algorithm.zone == 'America/New_York'
    (tmp_path/'quotes/TLT.csv').write_text(f'{day}T09:30:00,100,open\n')
    with pytest.raises(ValueError, match='final quote for TLT'):
        set_completed_end_date(algorithm, tmp_path, end, ['SPY','TLT'], now=now)


def test_native_boundary_rejects_holidays_and_engine_truncation(tmp_path):
    with pytest.raises(ValueError, match='not a US market session'):
        set_completed_end_date(None, tmp_path, datetime(2026,12,25), ['SPY'])
    now = datetime(2026,10,7,21,tzinfo=UTC)
    algorithm = ClampingAlgorithm(now)
    algorithm.set_end_date = lambda _: None
    algorithm.end_date = datetime(2026,10,6)
    (tmp_path/'quotes').mkdir()
    (tmp_path/'quotes/SPY.csv').write_text('2026-10-07T16:00:00,100,close\n')
    with pytest.raises(ValueError, match='truncated requested end 2026-10-07 to 2026-10-06'):
        set_completed_end_date(algorithm, tmp_path, datetime(2026,10,7), ['SPY'], now=now)
    assert algorithm.zone == 'America/New_York'


def test_exhausted_native_attempts_report_strategy_cause_and_evidence(tmp_path, monkeypatch):
    from systematic_trading.research import usd_monitored as module
    originals = {}
    for i in range(1,4):
        path = tmp_path/'native'/'F3'/str(i)
        path.mkdir(parents=True)
        (path/'run.json').write_text(json.dumps(dict(status='failed', error='CalledProcessError')))
        (path/'lean.log').write_text('Runtime Error: Partial LEAN output; missing session/decision')
        originals[str(i)] = (path/'run.json').read_bytes()
    monkeypatch.setattr(module, 'native_parity', lambda *a, **kw: pytest.fail('Exhausted attempts cannot run'))
    with pytest.raises(ValueError) as error:
        module.native_attempt(tmp_path, 'F3', 'image', '2')
    message = str(error.value)
    assert all(text in message for text in ('F3', '3 attempts exhausted', 'Partial LEAN output',
        str((tmp_path/'native/F3/3').resolve()), 'Repair the cause', 'Previous publication retained'))
    assert originals == {str(i):(tmp_path/'native/F3'/str(i)/'run.json').read_bytes() for i in range(1,4)}


def test_native_retry_uses_new_path_and_preserves_failed_attempt(tmp_path, monkeypatch):
    from systematic_trading.research import usd_monitored as module
    failed = tmp_path/'native/F3/1'
    failed.mkdir(parents=True)
    (failed/'run.json').write_text('{"status":"failed","error":"timeout"}')
    calls = []
    monkeypatch.setattr(module, 'native_parity', lambda bundle, output, *a, **kw:
        calls.append(output) or {'status':'succeeded'})
    result = module.native_attempt(tmp_path, 'F3', 'image', '2')
    assert result[1]['status'] == 'succeeded' and calls == [tmp_path/'native/F3/2']
    assert 'timeout' in (failed/'run.json').read_text()


@pytest.mark.parametrize('message,phase', [(None,'idle'), ('Waiting for the approved session close.','waiting'),
    ('Trading allocation activated; rebalance queued for order approval.','ready'),
    ('Allocation rebalance restored to the approval queue.','ready'),
    ('Handover window missed; retained for 2026-10-08 close.','blocked'),
    ('Model hash mismatch','blocked'), ('Missing FX evidence','blocked'), ('An unexpected failure','blocked')])
def test_pending_errors_are_never_classified_as_normal_waiting(message, phase):
    assert handover_phase(message) == phase


@pytest.mark.parametrize('failure', ['Missing audited prices', 'FX evidence unavailable',
    'Model hash mismatch', 'Partial LEAN output', 'Native attempts exhausted', 'ClickHouse unavailable'])
def test_analytics_failures_emit_durable_deduplicated_alerts_and_keep_service_identity(tmp_path, failure):
    events = []
    service = AnalyticsService(AppSettings(data_dir=tmp_path),
        SimpleNamespace(append_platform_event=events.append), None)
    service._report_issue('tracked-strategies', failure)
    service._report_issue('tracked-strategies', failure)
    lines = (tmp_path/'log/automation_alerts.jsonl').read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])['status'] == 'error'
    assert failure in lines[0]
    assert len(events) == 1 and events[0].source.service == 'analytics-service'


def test_alert_write_failure_is_visible_and_can_recover(tmp_path):
    def fail(_):
        raise OSError('alert disk unavailable')
    notifier = SimpleNamespace(notify=fail)
    service = AnalyticsService(AppSettings(data_dir=tmp_path), None, None, alert_notifier=notifier)
    service._report_issue('tracked-strategies', 'Replay failed')
    assert 'alert disk unavailable' in service.status()['errors']['alert-delivery']
    notifier.notify = lambda _: None
    service._report_issue('tracked-strategies', 'Replay failed')
    assert 'alert-delivery' not in service.status()['errors']


def test_alert_log_failure_can_retry_and_outbox_failure_is_visible(tmp_path, monkeypatch):
    from systematic_trading.live.alerts import AutomationAlertNotifier
    notifier = AutomationAlertNotifier(AppSettings(data_dir=tmp_path))
    event = SimpleNamespace(timestamp=datetime.now(UTC), event_type='replay', status='error',
                            message='Partial replay', details={})
    original = notifier._append_alert_log
    def fail(_):
        raise OSError('disk unavailable')
    monkeypatch.setattr(notifier, '_append_alert_log', fail)
    with pytest.raises(OSError):
        notifier.notify(event)
    monkeypatch.setattr(notifier, '_append_alert_log', original)
    notifier.event_store = SimpleNamespace(append_platform_event=fail)
    assert notifier.notify(event)
    assert notifier.delivery_status()['status'] == 'failed'
    assert 'event persistence failed' in notifier.delivery_status()['error']
    events = []
    notifier.event_store = SimpleNamespace(append_platform_event=events.append)
    assert notifier.notify(event)
    assert len(events) == 1 and notifier.delivery_status()['status'] != 'failed'


def test_stale_inputs_and_stalled_research_alert_even_when_operations_continue(tmp_path):
    events = []
    service = AnalyticsService(AppSettings(data_dir=tmp_path), None, None,
        alert_notifier=SimpleNamespace(notify=events.append))
    service._strategy_inputs = dict(price_through='2026-10-06', valuation_through='2026-10-05')
    service._status.update(research_job='tracked-strategies',
        research_job_started_at=(datetime.now(UTC)-timedelta(hours=3)).isoformat(),
        operations_completed_at=datetime.now(UTC).isoformat())
    service._check_readiness()
    assert any('expected' in e.message and '2026-10-05' in e.message for e in events)
    assert any(e.event_type == 'analytics_research_overdue' for e in events)
    assert not any(e.event_type == 'analytics_operations_overdue' for e in events)


def test_startup_is_distinguished_from_an_overdue_first_refresh(tmp_path):
    events = []
    service = AnalyticsService(AppSettings(data_dir=tmp_path, analytics_refresh_seconds=60), None, None,
        alert_notifier=SimpleNamespace(notify=events.append))
    service._thread = service._account_thread = service._archive_thread = SimpleNamespace(is_alive=lambda: True)
    service._started_at = datetime.now(UTC)
    service._check_readiness()
    assert not any('overdue' in e.event_type for e in events)
    ready = calculation_readiness(service.status())
    assert ready['severity'] == 'warning' and 'first complete refresh' in ready['message']
    service._started_at -= timedelta(seconds=301)
    service._check_readiness()
    assert any(e.event_type == 'analytics_operations_overdue' for e in events)
    assert calculation_readiness(service.status())['severity'] == 'error'
    service._started_at -= timedelta(hours=2)
    service._check_readiness()
    assert any(e.event_type == 'analytics_research_overdue' for e in events)
    assert any(e.event_type == 'analytics_archives_overdue' for e in events)


@pytest.mark.parametrize('state,severity,detail', [
    (None,'error','unavailable'),
    ({'errors':{'tracked-strategies':'all 3 attempts exhausted'}},'error','all 3 attempts exhausted'),
    ({'research_running':False},'error','stopped or overdue'),
    ({'research_stale':True},'error','stopped or overdue'),
    ({'strategy_stale':True,'strategy_freshness_message':'Expected Oct 7; FX Oct 6'},'warning','FX Oct 6'),
    ({'errors':{},'strategy_stale':False},'ok','Calculations available')])
def test_trading_readiness_includes_failures_even_without_pending_allocation(state,severity,detail):
    result = calculation_readiness(state)
    assert result['severity'] == severity and detail in result['message']


def test_handover_error_alerts_once_then_reports_recovery(tmp_path, monkeypatch):
    from systematic_trading.live import strategy_control
    from systematic_trading.live.management_service import TradingManagementService
    events = []
    service = TradingManagementService(settings=AppSettings(data_dir=tmp_path), store=object(),
        alert_notifier=SimpleNamespace(notify=events.append))
    monkeypatch.setattr(service, '_consume_broker_recovery', lambda _: None)
    monkeypatch.setattr(service, '_execution_sync_due', lambda _: False)
    monkeypatch.setattr(service, '_is_monitoring_day', lambda _: False)
    monkeypatch.setattr(service, '_stage_portfolio_alignment', lambda _: None)
    monkeypatch.setattr(service.auto_approval, 'invalidate_stale_binding', lambda: None)
    monkeypatch.setattr(strategy_control, 'activate_pending', lambda *a, **kw: 'Missing audited inputs')
    service.run_once(); service.run_once()
    assert len(events) == 1 and events[0].event_type == 'strategy_handover' and events[0].status == 'error'
    assert service.status().strategy_change_phase == 'blocked'
    monkeypatch.setattr(strategy_control, 'activate_pending', lambda *a, **kw:
        'Trading allocation activated; rebalance queued for order approval.')
    assert service.run_once().strategy_change_phase == 'ready'
    assert events[-1].status == 'ok'
