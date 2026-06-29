from __future__ import annotations

import ctypes
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.services.manifest import (
    HealthCheckKind,
    ServiceImplementationStatus,
    ServiceManifest,
    ServiceSpec,
    load_service_manifest,
)


class ServiceHealthLevel(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    PLANNED = "planned"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ServiceRuntimeSnapshot(BaseModel):
    running: bool | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    last_error: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ServiceHealthState(BaseModel):
    service_id: str
    display_name: str
    service_type: str
    implementation_status: str
    required: bool
    status: ServiceHealthLevel
    checked_at: datetime
    health_check_kind: str | None = None
    target: str | None = None
    running: bool | None = None
    pid: int | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    last_error: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PlatformHealthState(BaseModel):
    status: ServiceHealthLevel
    checked_at: datetime
    services: list[ServiceHealthState] = Field(default_factory=list)


def build_platform_health(
    *,
    settings: AppSettings,
    manifest: ServiceManifest | None = None,
    service_overrides: Mapping[str, ServiceRuntimeSnapshot] | None = None,
    base_dir: Path | str | None = None,
    now: datetime | None = None,
) -> PlatformHealthState:
    checked_at = _as_utc(now or datetime.now(tz=UTC))
    resolved_manifest = manifest or load_service_manifest()
    resolved_base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    overrides = service_overrides or {}
    services = [
        evaluate_service_health(
            service,
            settings=settings,
            override=overrides.get(service.service_id),
            base_dir=resolved_base_dir,
            now=checked_at,
        )
        for service in resolved_manifest.ordered_services()
    ]
    return PlatformHealthState(status=_overall_status(services), checked_at=checked_at, services=services)


def evaluate_service_health(
    service: ServiceSpec,
    *,
    settings: AppSettings,
    override: ServiceRuntimeSnapshot | None = None,
    base_dir: Path | str | None = None,
    now: datetime | None = None,
) -> ServiceHealthState:
    checked_at = _as_utc(now or datetime.now(tz=UTC))
    resolved_base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    health_check = service.health_check

    if service.service_id == "trading_management_loop" and not settings.automation_enabled:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.DISABLED,
            message="Trading management automation is disabled by configuration.",
            running=False,
            health_check_kind=health_check.kind.value if health_check else None,
            target=health_check.target if health_check else None,
        )

    if service.implementation_status == ServiceImplementationStatus.PLANNED:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.PLANNED,
            message="Service is declared but not implemented yet.",
            running=False,
            health_check_kind=health_check.kind.value if health_check else None,
            target=health_check.target if health_check else None,
        )

    if health_check is None or health_check.kind == HealthCheckKind.NONE:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.UNKNOWN,
            message="No health check is declared.",
            health_check_kind=health_check.kind.value if health_check else None,
            target=health_check.target if health_check else None,
        )

    if override is not None:
        return _from_snapshot(
            service,
            health_check=health_check,
            snapshot=override,
            checked_at=checked_at,
        )

    if health_check.kind == HealthCheckKind.HTTP:
        return _evaluate_http(service, health_check=health_check, checked_at=checked_at)
    if health_check.kind == HealthCheckKind.TCP:
        return _evaluate_tcp(service, health_check=health_check, checked_at=checked_at)
    if health_check.kind == HealthCheckKind.PID_FILE:
        return _evaluate_pid_file(
            service,
            health_check=health_check,
            settings=settings,
            base_dir=resolved_base_dir,
            checked_at=checked_at,
        )
    if health_check.kind == HealthCheckKind.STATE_FILE:
        return _evaluate_state_file(
            service,
            health_check=health_check,
            settings=settings,
            base_dir=resolved_base_dir,
            checked_at=checked_at,
        )
    return _state(
        service,
        checked_at=checked_at,
        status=ServiceHealthLevel.UNKNOWN,
        message=f"Unsupported health check kind: {health_check.kind}.",
        health_check_kind=health_check.kind.value,
        target=health_check.target,
    )


def write_service_state_file(
    path: Path | str,
    *,
    service_id: str,
    running: bool,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    last_error: str | None = None,
    message: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    heartbeat = _as_utc(heartbeat_at or datetime.now(tz=UTC))
    payload = {
        "schema_version": 1,
        "service_id": service_id,
        "running": running,
        "started_at": _iso_or_none(started_at),
        "heartbeat_at": heartbeat.isoformat(),
        "last_error": last_error,
        "message": message,
        "details": dict(details or {}),
    }
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _evaluate_http(
    service: ServiceSpec,
    *,
    health_check,
    checked_at: datetime,
) -> ServiceHealthState:
    if not health_check.target:
        return _missing_target(service, health_check=health_check, checked_at=checked_at)
    try:
        with urllib.request.urlopen(health_check.target, timeout=health_check.timeout_seconds) as response:
            status_code = response.status
    except (OSError, urllib.error.URLError) as exc:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DEGRADED,
            message=f"HTTP health check failed: {exc}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
        )
    level = ServiceHealthLevel.OK if status_code < 400 else ServiceHealthLevel.ERROR
    return _state(
        service,
        checked_at=checked_at,
        status=level,
        message=f"HTTP health check returned {status_code}.",
        health_check_kind=health_check.kind.value,
        target=health_check.target,
        running=status_code < 400,
        heartbeat_at=checked_at,
        details={"status_code": status_code},
    )


def _evaluate_tcp(
    service: ServiceSpec,
    *,
    health_check,
    checked_at: datetime,
) -> ServiceHealthState:
    if not health_check.target:
        return _missing_target(service, health_check=health_check, checked_at=checked_at)
    try:
        host, raw_port = health_check.target.rsplit(":", 1)
        port = int(raw_port)
    except ValueError:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR,
            message=f"TCP health check target must be host:port: {health_check.target}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
        )
    try:
        with socket.create_connection((host, port), timeout=health_check.timeout_seconds):
            pass
    except OSError as exc:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DEGRADED,
            message=f"TCP health check failed: {exc}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"host": host, "port": port},
        )
    return _state(
        service,
        checked_at=checked_at,
        status=ServiceHealthLevel.OK,
        message="TCP health check connected.",
        health_check_kind=health_check.kind.value,
        target=health_check.target,
        running=True,
        heartbeat_at=checked_at,
        details={"host": host, "port": port},
    )


def _evaluate_pid_file(
    service: ServiceSpec,
    *,
    health_check,
    settings: AppSettings,
    base_dir: Path,
    checked_at: datetime,
) -> ServiceHealthState:
    if not health_check.target:
        return _missing_target(service, health_check=health_check, checked_at=checked_at)
    pid_path = _resolve_local_path(health_check.target, settings=settings, base_dir=base_dir)
    try:
        raw_pid = pid_path.read_text(encoding="ascii").strip()
        pid = int(raw_pid)
    except FileNotFoundError:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DEGRADED,
            message=f"PID file is missing: {pid_path}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"path": str(pid_path)},
        )
    except (OSError, ValueError) as exc:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR,
            message=f"PID file could not be read: {exc}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"path": str(pid_path)},
        )

    running = _pid_is_running(pid)
    return _state(
        service,
        checked_at=checked_at,
        status=ServiceHealthLevel.OK if running else ServiceHealthLevel.ERROR,
        message="PID file points to a running process." if running else "PID file is stale.",
        health_check_kind=health_check.kind.value,
        target=health_check.target,
        running=running,
        pid=pid,
        heartbeat_at=checked_at if running else None,
        details={"path": str(pid_path)},
    )


def _evaluate_state_file(
    service: ServiceSpec,
    *,
    health_check,
    settings: AppSettings,
    base_dir: Path,
    checked_at: datetime,
) -> ServiceHealthState:
    if not health_check.target:
        return _missing_target(service, health_check=health_check, checked_at=checked_at)
    state_path = _resolve_local_path(health_check.target, settings=settings, base_dir=base_dir)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DEGRADED,
            message=f"State file is missing: {state_path}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"path": str(state_path)},
        )
    except (OSError, json.JSONDecodeError) as exc:
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR,
            message=f"State file could not be read: {exc}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"path": str(state_path)},
        )

    if not isinstance(payload, dict):
        return _state(
            service,
            checked_at=checked_at,
            status=ServiceHealthLevel.ERROR,
            message=f"State file is not a JSON object: {state_path}",
            health_check_kind=health_check.kind.value,
            target=health_check.target,
            running=False,
            details={"path": str(state_path)},
        )
    snapshot = ServiceRuntimeSnapshot(
        running=_optional_bool(payload.get("running")),
        started_at=_parse_datetime(payload.get("started_at")),
        heartbeat_at=_parse_datetime(payload.get("heartbeat_at")),
        last_error=_optional_str(payload.get("last_error")),
        message=_optional_str(payload.get("message")),
        details={"path": str(state_path), "state_service_id": payload.get("service_id")},
    )
    return _from_snapshot(service, health_check=health_check, snapshot=snapshot, checked_at=checked_at)


def _from_snapshot(
    service: ServiceSpec,
    *,
    health_check,
    snapshot: ServiceRuntimeSnapshot,
    checked_at: datetime,
) -> ServiceHealthState:
    status = ServiceHealthLevel.OK
    message = snapshot.message or "Service heartbeat is healthy."
    if snapshot.running is False:
        status = ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DISABLED
        message = snapshot.message or "Service reports it is not running."
    elif snapshot.heartbeat_at is None:
        status = ServiceHealthLevel.DEGRADED
        message = snapshot.message or "Service heartbeat timestamp is missing."
    elif snapshot.heartbeat_at is not None and health_check.stale_after_seconds is not None:
        age_seconds = (checked_at - _as_utc(snapshot.heartbeat_at)).total_seconds()
        if age_seconds > health_check.stale_after_seconds:
            status = ServiceHealthLevel.ERROR if service.required else ServiceHealthLevel.DEGRADED
            message = f"Service heartbeat is stale by {int(age_seconds)} second(s)."
    if snapshot.last_error:
        status = ServiceHealthLevel.DEGRADED if status == ServiceHealthLevel.OK else status
        message = snapshot.last_error
    return _state(
        service,
        checked_at=checked_at,
        status=status,
        message=message,
        health_check_kind=health_check.kind.value,
        target=health_check.target,
        running=snapshot.running,
        started_at=snapshot.started_at,
        heartbeat_at=snapshot.heartbeat_at,
        last_error=snapshot.last_error,
        details=snapshot.details,
    )


def _missing_target(service: ServiceSpec, *, health_check, checked_at: datetime) -> ServiceHealthState:
    return _state(
        service,
        checked_at=checked_at,
        status=ServiceHealthLevel.ERROR,
        message="Health check target is not declared.",
        health_check_kind=health_check.kind.value,
    )


def _overall_status(services: list[ServiceHealthState]) -> ServiceHealthLevel:
    active_required = [
        service
        for service in services
        if service.required and service.implementation_status == ServiceImplementationStatus.ACTIVE.value
    ]
    if any(service.status == ServiceHealthLevel.ERROR for service in active_required):
        return ServiceHealthLevel.ERROR
    if any(service.status in {ServiceHealthLevel.DEGRADED, ServiceHealthLevel.UNKNOWN} for service in active_required):
        return ServiceHealthLevel.DEGRADED
    return ServiceHealthLevel.OK


def _state(
    service: ServiceSpec,
    *,
    checked_at: datetime,
    status: ServiceHealthLevel,
    message: str,
    health_check_kind: str | None = None,
    target: str | None = None,
    running: bool | None = None,
    pid: int | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    last_error: str | None = None,
    details: dict[str, Any] | None = None,
) -> ServiceHealthState:
    return ServiceHealthState(
        service_id=service.service_id,
        display_name=service.display_name,
        service_type=service.service_type.value,
        implementation_status=service.implementation_status.value,
        required=service.required,
        status=status,
        checked_at=checked_at,
        health_check_kind=health_check_kind,
        target=target,
        running=running,
        pid=pid,
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        last_error=last_error,
        message=message,
        details=details or {},
    )


def _resolve_local_path(value: str, *, settings: AppSettings, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "var":
        return Path(settings.data_dir, *parts[1:]).resolve()
    return (base_dir / path).resolve()


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _windows_pid_is_running(pid: int) -> bool:
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    try:
        return _as_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_or_none(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value is not None else None
