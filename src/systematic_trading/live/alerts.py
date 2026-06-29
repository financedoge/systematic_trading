from __future__ import annotations

import json
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Protocol

from systematic_trading.config import AppSettings
from systematic_trading.domain import (
    AlertRaisedEvent,
    AlertRaisedPayload,
    EventSeverity,
    EventSource,
)
from systematic_trading.storage.interfaces import PlatformEventAppendStore


class AutomationEvent(Protocol):
    timestamp: datetime
    event_type: str
    status: str
    message: str
    details: dict[str, Any]


class AutomationAlertNotifier:
    def __init__(self, settings: AppSettings, *, event_store: PlatformEventAppendStore | None = None) -> None:
        self.settings = settings
        self.event_store = event_store
        self.alert_log_path = settings.data_dir / "log" / "automation_alerts.jsonl"
        self.email_error_log_path = settings.data_dir / "log" / "automation_alert_email_errors.log"
        self.event_error_log_path = settings.data_dir / "log" / "automation_alert_event_errors.log"
        self._lock = Lock()
        self._last_alert_at: dict[str, datetime] = {}
        self._last_email_at: dict[str, datetime] = {}
        self._last_email_config_warning_at: datetime | None = None

    def notify(self, event: AutomationEvent) -> None:
        if event.status not in {"warning", "error"}:
            return
        if not self._reserve_alert_record(event):
            return
        self._append_alert_log(event)
        self._append_platform_alert_event(event)
        email_config_issue = self.email_config_issue()
        if email_config_issue is not None:
            self._append_email_config_warning_once(email_config_issue)
            return
        if not self._reserve_email_delivery(event):
            return
        Thread(target=self._send_email_safely, args=(event,), daemon=True).start()

    def _append_alert_log(self, event: AutomationEvent) -> None:
        payload = {
            "alerted_at": datetime.now(tz=UTC).isoformat(),
            "timestamp": _isoformat(event.timestamp),
            "event_type": event.event_type,
            "status": event.status,
            "message": event.message,
            "details": event.details,
        }
        with self._lock:
            self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.alert_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def _append_platform_alert_event(self, event: AutomationEvent) -> None:
        if self.event_store is None:
            return
        try:
            self.event_store.append_platform_event(
                AlertRaisedEvent(
                    occurred_at=_as_utc(event.timestamp),
                    source=EventSource(
                        service="trading-management-service",
                        environment=self.settings.default_environment,
                    ),
                    payload=AlertRaisedPayload(
                        severity=_event_severity(event.status),
                        category=event.event_type,
                        message=event.message,
                        details={
                            "automation_status": event.status,
                            "automation_event_type": event.event_type,
                            "automation_event_timestamp": _isoformat(event.timestamp),
                            **event.details,
                        },
                    ),
                )
            )
        except Exception as exc:
            self._append_alert_event_error(exc)

    def email_config_issue(self) -> str | None:
        missing: list[str] = []
        if not _split_recipients(self.settings.automation_alert_email_to):
            missing.append("ST_AUTOMATION_ALERT_EMAIL_TO")
        if not self.settings.automation_alert_smtp_host:
            missing.append("ST_AUTOMATION_ALERT_SMTP_HOST")
        if not missing:
            return None
        return f"Email alert delivery is disabled; missing {', '.join(missing)}."

    def email_configured(self) -> bool:
        return self.email_config_issue() is None

    def _append_email_config_warning_once(self, message: str) -> None:
        now = datetime.now(tz=UTC)
        with self._lock:
            if (
                self._last_email_config_warning_at is not None
                and (now - self._last_email_config_warning_at).total_seconds()
                < self.settings.automation_alert_dedupe_seconds
            ):
                return
            self._last_email_config_warning_at = now
            self.email_error_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.email_error_log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{now.isoformat()} {message}\n")

    def _reserve_alert_record(self, event: AutomationEvent) -> bool:
        key = _alert_dedupe_key(event)
        now = datetime.now(tz=UTC)
        with self._lock:
            last_alert = self._last_alert_at.get(key)
            if last_alert is not None and (now - last_alert).total_seconds() < self.settings.automation_alert_dedupe_seconds:
                return False
            self._last_alert_at[key] = now
            return True

    def _reserve_email_delivery(self, event: AutomationEvent) -> bool:
        key = _alert_dedupe_key(event)
        now = datetime.now(tz=UTC)
        with self._lock:
            last_sent = self._last_email_at.get(key)
            if last_sent is not None and (now - last_sent).total_seconds() < self.settings.automation_alert_dedupe_seconds:
                return False
            self._last_email_at[key] = now
            return True

    def _send_email_safely(self, event: AutomationEvent) -> None:
        try:
            self._send_email(event)
        except Exception as exc:
            self._append_email_error(exc)

    def _send_email(self, event: AutomationEvent) -> None:
        recipients = _split_recipients(self.settings.automation_alert_email_to)
        if not recipients or self.settings.automation_alert_smtp_host is None:
            return
        sender = (
            self.settings.automation_alert_email_from
            or self.settings.automation_alert_smtp_username
            or f"{self.settings.app_name}@localhost"
        )
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = f"[{self.settings.app_name}] automation {event.status}: {event.event_type}"
        message.set_content(_email_body(event))

        with smtplib.SMTP(
            self.settings.automation_alert_smtp_host,
            self.settings.automation_alert_smtp_port,
            timeout=self.settings.automation_alert_smtp_timeout_seconds,
        ) as smtp:
            if self.settings.automation_alert_smtp_use_tls:
                smtp.starttls()
            if self.settings.automation_alert_smtp_username and self.settings.automation_alert_smtp_password:
                smtp.login(self.settings.automation_alert_smtp_username, self.settings.automation_alert_smtp_password)
            smtp.send_message(message)

    def _append_email_error(self, exc: Exception) -> None:
        line = f"{datetime.now(tz=UTC).isoformat()} {type(exc).__name__}: {exc}\n"
        with self._lock:
            self.email_error_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.email_error_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def _append_alert_event_error(self, exc: Exception) -> None:
        line = f"{datetime.now(tz=UTC).isoformat()} {type(exc).__name__}: {exc}\n"
        with self._lock:
            self.event_error_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.event_error_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)


def _email_body(event: AutomationEvent) -> str:
    details = json.dumps(event.details, indent=2, sort_keys=True, default=str)
    return (
        f"Automation event: {event.event_type}\n"
        f"Status: {event.status}\n"
        f"Timestamp: {_isoformat(event.timestamp)}\n"
        f"Message: {event.message}\n\n"
        f"Details:\n{details}\n"
    )


def _alert_dedupe_key(event: AutomationEvent) -> str:
    details = json.dumps(event.details, sort_keys=True, default=str, separators=(",", ":"))
    return f"{event.event_type}:{event.status}:{event.message}:{details}"


def _split_recipients(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def _isoformat(value: datetime) -> str:
    return _as_utc(value).isoformat()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_severity(status: str) -> EventSeverity:
    if status == "error":
        return EventSeverity.ERROR
    if status == "warning":
        return EventSeverity.WARNING
    return EventSeverity.INFO
