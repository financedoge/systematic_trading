from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings


class OperationalLogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OperationalLogRecord(BaseModel):
    schema_version: int = 1
    occurred_at: datetime
    service_id: str = Field(min_length=1)
    level: OperationalLogLevel
    event: str = Field(min_length=1)
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OperationalLogger:
    def __init__(self, *, path: Path | str, service_id: str) -> None:
        self.path = Path(path)
        self.service_id = service_id

    def debug(self, event: str, *, message: str | None = None, **details: Any) -> OperationalLogRecord:
        return self.write(OperationalLogLevel.DEBUG, event, message=message, details=details)

    def info(self, event: str, *, message: str | None = None, **details: Any) -> OperationalLogRecord:
        return self.write(OperationalLogLevel.INFO, event, message=message, details=details)

    def warning(self, event: str, *, message: str | None = None, **details: Any) -> OperationalLogRecord:
        return self.write(OperationalLogLevel.WARNING, event, message=message, details=details)

    def error(self, event: str, *, message: str | None = None, **details: Any) -> OperationalLogRecord:
        return self.write(OperationalLogLevel.ERROR, event, message=message, details=details)

    def critical(self, event: str, *, message: str | None = None, **details: Any) -> OperationalLogRecord:
        return self.write(OperationalLogLevel.CRITICAL, event, message=message, details=details)

    def write(
        self,
        level: OperationalLogLevel | str,
        event: str,
        *,
        message: str | None = None,
        details: Mapping[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> OperationalLogRecord:
        return append_operational_log(
            self.path,
            service_id=self.service_id,
            level=level,
            event=event,
            message=message,
            details=details,
            occurred_at=occurred_at,
        )


def default_operational_log_path(settings: AppSettings | None = None) -> Path:
    resolved_settings = settings or AppSettings()
    return resolved_settings.data_dir / "log" / "platform_operations.jsonl"


def append_operational_log(
    path: Path | str,
    *,
    service_id: str,
    level: OperationalLogLevel | str,
    event: str,
    message: str | None = None,
    details: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> OperationalLogRecord:
    record = OperationalLogRecord(
        occurred_at=_as_utc(occurred_at or datetime.now(tz=UTC)),
        service_id=service_id,
        level=OperationalLogLevel(level),
        event=event,
        message=message,
        details=_sanitize_mapping(details or {}),
    )
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))
        handle.write("\n")
    return record


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _sanitize_value(str(key), item) for key, item in value.items()}


def _sanitize_value(key: str, value: Any) -> Any:
    if _is_secret_key(key):
        return "[redacted]"
    if isinstance(value, Mapping):
        return {str(item_key): _sanitize_value(str(item_key), item_value) for item_key, item_value in value.items()}
    if isinstance(value, list | tuple | set):
        return [_sanitize_value("", item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return _sanitize_value("", value.model_dump(mode="json"))
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in ("password", "secret", "token", "credential", "api_key"))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
