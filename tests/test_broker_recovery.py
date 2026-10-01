from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from systematic_trading.config import AppSettings
from systematic_trading.live.management_service import TradingManagementService, TradingServiceStatus
from systematic_trading.services import broker_monitor


def test_health_monitor_only_wakes_on_connection_edges(monkeypatch):
    results = [SimpleNamespace(ok=ok) for ok in (False, True, True, False, True)]
    pending = iter(results)
    monkeypatch.setattr(broker_monitor, "probe_ib_tws_health", lambda _: next(pending))
    callbacks = []
    monitor = broker_monitor.BrokerHealthMonitor(AppSettings(), on_available=callbacks.append)
    for _ in results:
        monitor.probe_once()
    assert callbacks == [results[1], results[4]]


def test_startup_healthy_gateway_wakes_both_workers(monkeypatch, tmp_path):
    from systematic_trading import app as module
    from systematic_trading.research import analytics_service
    from systematic_trading.market_data.analytics_store import AnalyticsStore

    calls = []
    now = datetime.now(UTC)
    trading = SimpleNamespace(start=lambda: calls.append("trading-start"), stop=lambda: None,
        request_broker_recovery=lambda at: calls.append(("reconcile", at)))
    analytics = SimpleNamespace(start=lambda: None, stop=lambda: None,
        request_refresh=lambda **kw: calls.append(("analytics", kw)))
    monkeypatch.setattr(module, "TradingManagementService", lambda **kw: trading)
    monkeypatch.setattr(analytics_service, "AnalyticsService", lambda *args: analytics)
    monkeypatch.setattr(AnalyticsStore, "from_settings", lambda _: object())
    monkeypatch.setattr(broker_monitor, "probe_ib_tws_health", lambda _: SimpleNamespace(ok=True, checked_at=now))
    monkeypatch.setattr(broker_monitor.BrokerHealthMonitor, "start", broker_monitor.BrokerHealthMonitor.probe_once)
    monkeypatch.setattr(broker_monitor.BrokerHealthMonitor, "close", lambda _: None)
    settings = AppSettings(data_dir=tmp_path, automation_enabled=True, analytics_enabled=True,
                           market_data_store_backend="clickhouse", health_monitor_enabled=True)
    with TestClient(module.create_app(settings)):
        assert calls == ["trading-start", ("analytics", {"reason": "broker_reconnected"}), ("reconcile", now)]


def recovery_service(tmp_path):
    service = TradingManagementService(settings=AppSettings(data_dir=tmp_path), store=object())
    now = datetime(2026, 9, 30, 14, tzinfo=UTC)
    service._status = TradingServiceStatus(
        ib_automation_consecutive_errors=3, ib_automation_circuit_open_until=now+timedelta(minutes=30),
        ib_automation_circuit_reason="disconnected", ib_automation_last_failure_at=now-timedelta(minutes=5),
        next_eod_attempt_at=now+timedelta(minutes=5), next_execution_sync_at=now+timedelta(minutes=30),
        pending_eod_dates=[date(2026, 9, 28), date(2026, 9, 29)], last_eod_date=date(2026, 9, 25),
        last_reconciliation_status="break", last_reconciliation_at=now-timedelta(days=1),
        last_rebalance_proposal_id="awaiting-approval")
    return service, now


def test_recovery_retries_reads_without_granting_reconciliation_or_approval(tmp_path):
    service, now = recovery_service(tmp_path)
    previous = service._status.model_dump()
    service.request_broker_recovery(now-timedelta(seconds=1))
    assert service._wake.is_set()
    service._consume_broker_recovery(now)
    status = service._status
    assert status.ib_automation_circuit_open_until is None
    assert status.ib_automation_consecutive_errors == 0
    assert status.next_execution_sync_at == now
    assert status.next_eod_attempt_at is None
    for field in ("last_reconciliation_status", "last_reconciliation_at", "last_rebalance_proposal_id",
                  "pending_eod_dates", "last_eod_date"):
        assert status.model_dump()[field] == previous[field]
    service._consume_broker_recovery(now)
    assert service._status == status  # One read retry, not a continuous circuit override.


@pytest.mark.parametrize("age", [121, -1, 301])
def test_old_future_or_pre_failure_probe_cannot_clear_circuit(tmp_path, age):
    service, now = recovery_service(tmp_path)
    if age == 301:
        service._status.ib_automation_last_failure_at = now-timedelta(seconds=10)
        age = 20
    previous = service._status.model_dump()
    service.request_broker_recovery(now-timedelta(seconds=age))
    service._consume_broker_recovery(now)
    assert service._status.model_dump() == previous
