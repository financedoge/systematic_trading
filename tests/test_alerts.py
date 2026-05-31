from datetime import UTC, datetime

from systematic_trading.config import AppSettings
from systematic_trading.live.alerts import AutomationAlertNotifier
from systematic_trading.live.management_service import TradingServiceEvent


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
