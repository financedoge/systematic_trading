from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1")
REPO_ROOT = Path(__file__).resolve().parents[3]


class ServiceActionInfo(BaseModel):
    service_id: str
    restartable: bool
    reason: str | None = None


class ServiceActionCatalog(BaseModel):
    services: list[ServiceActionInfo] = Field(default_factory=list)


class ServiceActionResult(BaseModel):
    service_id: str
    action: str
    status: str
    started_at: datetime
    completed_at: datetime
    commands: list[str] = Field(default_factory=list)
    stdout: list[str] = Field(default_factory=list)
    stderr: list[str] = Field(default_factory=list)


_RESTARTABLE_SERVICES = {
    "nats_jetstream": {
        "commands": [
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "stop_nats_jetstream.ps1")],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "start_nats_jetstream.ps1")],
            [sys.executable, str(REPO_ROOT / "scripts" / "configure_nats_stream.py"), "--nats-url", "nats://127.0.0.1:4222"],
        ]
    },
    "clickhouse_columnar": {
        "commands": [
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "stop_clickhouse.ps1")],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "start_clickhouse.ps1")],
        ]
    },
    "market_data_recorder": {
        "commands": [
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "stop_market_data_recorder.ps1")],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "scripts" / "start_market_data_recorder_service.ps1")],
        ]
    },
}

_DISABLED_REASONS = {
    "postgres_transactional": "Postgres is an external database service; restart it outside the trading API.",
    "operator_dashboard": "The operator API cannot safely restart its own hosting process from inside a request.",
    "event_outbox_dispatcher": "Dispatcher lifecycle is tied to the operator dashboard startup script.",
    "trading_management_loop": "The management loop is embedded in the operator API; restart the operator supervisor instead.",
    "ib_tws_api": "TWS/Gateway login and 2FA recovery must be handled by the operator.",
}


@router.get("/platform/service-actions", response_model=ServiceActionCatalog)
def platform_service_actions() -> ServiceActionCatalog:
    service_ids = [
        "nats_jetstream",
        "postgres_transactional",
        "ib_tws_api",
        "clickhouse_columnar",
        "operator_dashboard",
        "event_outbox_dispatcher",
        "trading_management_loop",
        "market_data_recorder",
    ]
    return ServiceActionCatalog(
        services=[
            ServiceActionInfo(
                service_id=service_id,
                restartable=service_id in _RESTARTABLE_SERVICES,
                reason=None if service_id in _RESTARTABLE_SERVICES else _DISABLED_REASONS.get(service_id, "No local restart action is configured."),
            )
            for service_id in service_ids
        ]
    )


@router.post("/platform/services/{service_id}/restart", response_model=ServiceActionResult)
def restart_platform_service(service_id: str) -> ServiceActionResult:
    spec = _RESTARTABLE_SERVICES.get(service_id)
    if spec is None:
        reason = _DISABLED_REASONS.get(service_id, "No local restart action is configured.")
        raise HTTPException(status_code=400, detail=reason)
    started_at = datetime.now(tz=UTC)
    stdout: list[str] = []
    stderr: list[str] = []
    commands: list[str] = []
    for command in spec["commands"]:
        commands.append(" ".join(command))
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.stdout:
            stdout.append(result.stdout.strip())
        if result.stderr:
            stderr.append(result.stderr.strip())
        if result.returncode != 0:
            completed_at = datetime.now(tz=UTC)
            raise HTTPException(
                status_code=500,
                detail={
                    "service_id": service_id,
                    "command": " ".join(command),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
    completed_at = datetime.now(tz=UTC)
    return ServiceActionResult(
        service_id=service_id,
        action="restart",
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        commands=commands,
        stdout=stdout,
        stderr=stderr,
    )
