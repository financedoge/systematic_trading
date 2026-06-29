from datetime import UTC, datetime

from systematic_trading.config import AppSettings
from systematic_trading.domain import AlertRaisedEvent, EventSeverity, PlatformEventType
from systematic_trading.live.alerts import AutomationAlertNotifier
from systematic_trading.live.management_service import TradingServiceEvent
from systematic_trading.storage.sqlite import SQLiteStore


def test_automation_alert_notifier_persists_warning_log(tmp_path) -> None:
    notifier = AutomationAlertNotifier(AppSettings(data_dir=tmp_path, database_path=tmp_path / "alerts.db"))
    event = TradingServiceEvent(
        timestamp=datetime(2026, 5, 20, 12, tzinfo=UTC),
        event_type="market_data",
        status="warning",
        message="Market data stale.",
        details={"symbol": "HYXU"},
    )

    notifier.notify(event)

    alert_log = tmp_path / "log" / "automation_alerts.jsonl"
    assert alert_log.exists()
    text = alert_log.read_text(encoding="utf-8")
    assert "Market data stale." in text
    assert "HYXU" in text


def test_automation_alert_notifier_appends_alert_event_to_outbox(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "alerts.db")
    store.initialize()
    notifier = AutomationAlertNotifier(
        AppSettings(data_dir=tmp_path, database_path=tmp_path / "alerts.db"),
        event_store=store,
    )
    event = TradingServiceEvent(
        timestamp=datetime(2026, 5, 20, 12, tzinfo=UTC),
        event_type="market_data",
        status="warning",
        message="Market data stale.",
        details={"symbol": "HYXU"},
    )

    notifier.notify(event)

    pending = store.list_pending_platform_events()
    assert len(pending) == 1
    assert pending[0].event_type == PlatformEventType.ALERT_RAISED
    assert isinstance(pending[0].payload, AlertRaisedEvent)
    assert pending[0].subject == "systematic_trading.events.v1.alert.raised"
    assert pending[0].payload.payload.severity == EventSeverity.WARNING
    assert pending[0].payload.payload.category == "market_data"
    assert pending[0].payload.payload.message == "Market data stale."
    assert pending[0].payload.payload.details["symbol"] == "HYXU"
    assert pending[0].payload.payload.details["automation_status"] == "warning"


def test_automation_alert_notifier_dedupes_repeated_identical_alerts(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "alerts.db")
    store.initialize()
    notifier = AutomationAlertNotifier(
        AppSettings(
            data_dir=tmp_path,
            database_path=tmp_path / "alerts.db",
            automation_alert_dedupe_seconds=3600,
        ),
        event_store=store,
    )
    event = TradingServiceEvent(
        timestamp=datetime(2026, 5, 20, 12, tzinfo=UTC),
        event_type="execution_sync",
        status="error",
        message="Timed out waiting for IB nextValidId callback for client_id 131.",
    )

    notifier.notify(event)
    notifier.notify(event)

    alert_log = tmp_path / "log" / "automation_alerts.jsonl"
    assert alert_log.read_text(encoding="utf-8").count("nextValidId") == 1
    assert len(store.list_pending_platform_events()) == 1


def test_automation_alert_notifier_logs_outbox_failure_without_suppressing_alert_log(tmp_path) -> None:
    notifier = AutomationAlertNotifier(
        AppSettings(data_dir=tmp_path, database_path=tmp_path / "alerts.db"),
        event_store=_FailingAlertEventStore(),
    )
    event = TradingServiceEvent(
        timestamp=datetime(2026, 5, 20, 12, tzinfo=UTC),
        event_type="market_data",
        status="error",
        message="Market data refresh failed.",
    )

    notifier.notify(event)

    assert "Market data refresh failed." in (tmp_path / "log" / "automation_alerts.jsonl").read_text(encoding="utf-8")
    assert "RuntimeError: outbox unavailable" in (tmp_path / "log" / "automation_alert_event_errors.log").read_text(encoding="utf-8")


def test_automation_alert_notifier_records_missing_email_configuration(tmp_path) -> None:
    notifier = AutomationAlertNotifier(
        AppSettings(
            data_dir=tmp_path,
            database_path=tmp_path / "alerts.db",
            automation_alert_email_to="defeng.wu@hotmail.com",
            automation_alert_smtp_host=None,
        )
    )
    event = TradingServiceEvent(
        timestamp=datetime(2026, 5, 20, 12, tzinfo=UTC),
        event_type="market_data",
        status="warning",
        message="Market data stale.",
    )

    notifier.notify(event)

    email_error_log = tmp_path / "log" / "automation_alert_email_errors.log"
    assert email_error_log.exists()
    assert "ST_AUTOMATION_ALERT_SMTP_HOST" in email_error_log.read_text(encoding="utf-8")


class _FailingAlertEventStore:
    def append_platform_event(self, event):
        raise RuntimeError("outbox unavailable")
