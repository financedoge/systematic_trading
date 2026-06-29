from datetime import UTC, datetime, timedelta

from systematic_trading.config import AppSettings
from systematic_trading.services import (
    ServiceHealthLevel,
    ServiceManifest,
    ServiceRuntimeSnapshot,
    build_platform_health,
    write_service_state_file,
)


def test_platform_health_uses_state_file_heartbeat(tmp_path) -> None:
    now = datetime(2026, 6, 27, 12, tzinfo=UTC)
    state_path = tmp_path / "run" / "worker.state.json"
    write_service_state_file(
        state_path,
        service_id="worker",
        running=True,
        started_at=now - timedelta(minutes=1),
        heartbeat_at=now,
        message="worker heartbeat",
    )
    manifest = ServiceManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "test",
            "services": [
                {
                    "service_id": "worker",
                    "display_name": "Worker",
                    "service_type": "worker",
                    "startup_order": 1,
                    "command": ["python"],
                    "pid_file": "var/run/worker.pid",
                    "health_check": {
                        "kind": "state_file",
                        "target": "var/run/worker.state.json",
                        "stale_after_seconds": 30,
                    },
                }
            ],
        }
    )

    health = build_platform_health(
        settings=AppSettings(data_dir=tmp_path),
        manifest=manifest,
        base_dir=tmp_path,
        now=now,
    )

    assert health.status == ServiceHealthLevel.OK
    assert health.services[0].status == ServiceHealthLevel.OK
    assert health.services[0].heartbeat_at == now
    assert health.services[0].message == "worker heartbeat"


def test_platform_health_marks_required_stale_state_as_error(tmp_path) -> None:
    now = datetime(2026, 6, 27, 12, tzinfo=UTC)
    state_path = tmp_path / "run" / "worker.state.json"
    write_service_state_file(
        state_path,
        service_id="worker",
        running=True,
        heartbeat_at=now - timedelta(seconds=31),
    )
    manifest = ServiceManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "test",
            "services": [
                {
                    "service_id": "worker",
                    "display_name": "Worker",
                    "service_type": "worker",
                    "startup_order": 1,
                    "command": ["python"],
                    "pid_file": "var/run/worker.pid",
                    "health_check": {
                        "kind": "state_file",
                        "target": "var/run/worker.state.json",
                        "stale_after_seconds": 30,
                    },
                }
            ],
        }
    )

    health = build_platform_health(
        settings=AppSettings(data_dir=tmp_path),
        manifest=manifest,
        base_dir=tmp_path,
        now=now,
    )

    assert health.status == ServiceHealthLevel.ERROR
    assert health.services[0].status == ServiceHealthLevel.ERROR
    assert "stale" in health.services[0].message


def test_platform_health_marks_optional_stopped_state_as_disabled_even_if_old(tmp_path) -> None:
    now = datetime(2026, 6, 27, 12, tzinfo=UTC)
    state_path = tmp_path / "run" / "optional.state.json"
    write_service_state_file(
        state_path,
        service_id="optional",
        running=False,
        heartbeat_at=now - timedelta(hours=4),
        message="Optional worker is stopped.",
    )
    manifest = ServiceManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "test",
            "services": [
                {
                    "service_id": "optional",
                    "display_name": "Optional Worker",
                    "service_type": "worker",
                    "required": False,
                    "startup_order": 1,
                    "command": ["python"],
                    "pid_file": "var/run/optional.pid",
                    "health_check": {
                        "kind": "state_file",
                        "target": "var/run/optional.state.json",
                        "stale_after_seconds": 30,
                    },
                }
            ],
        }
    )

    health = build_platform_health(
        settings=AppSettings(data_dir=tmp_path),
        manifest=manifest,
        base_dir=tmp_path,
        now=now,
    )

    assert health.status == ServiceHealthLevel.OK
    assert health.services[0].status == ServiceHealthLevel.DISABLED
    assert health.services[0].message == "Optional worker is stopped."


def test_platform_health_supports_runtime_overrides_and_planned_services(tmp_path) -> None:
    now = datetime(2026, 6, 27, 12, tzinfo=UTC)
    manifest = ServiceManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "test",
            "services": [
                {
                    "service_id": "api",
                    "display_name": "API",
                    "service_type": "api",
                    "startup_order": 1,
                    "command": ["python"],
                    "pid_file": "var/run/api.pid",
                    "health_check": {"kind": "http", "target": "http://127.0.0.1:1/health"},
                },
                {
                    "service_id": "future_worker",
                    "display_name": "Future Worker",
                    "service_type": "worker",
                    "implementation_status": "planned",
                    "required": False,
                    "startup_order": 2,
                    "health_check": {"kind": "state_file", "target": "var/run/future.state.json"},
                },
            ],
        }
    )

    health = build_platform_health(
        settings=AppSettings(data_dir=tmp_path),
        manifest=manifest,
        service_overrides={
            "api": ServiceRuntimeSnapshot(
                running=True,
                heartbeat_at=now,
                message="API responded",
            )
        },
        base_dir=tmp_path,
        now=now,
    )

    assert health.status == ServiceHealthLevel.OK
    assert [service.status for service in health.services] == [
        ServiceHealthLevel.OK,
        ServiceHealthLevel.PLANNED,
    ]


def test_platform_health_marks_required_tcp_failure_as_error(tmp_path) -> None:
    now = datetime(2026, 6, 27, 12, tzinfo=UTC)
    manifest = ServiceManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "test",
            "services": [
                {
                    "service_id": "postgres",
                    "display_name": "Postgres",
                    "service_type": "worker",
                    "startup_order": 1,
                    "command": ["powershell"],
                    "pid_file": None,
                    "health_check": {
                        "kind": "tcp",
                        "target": "127.0.0.1:1",
                        "timeout_seconds": 1,
                    },
                    "restart_policy": {"mode": "external_windows_service"},
                }
            ],
        }
    )

    health = build_platform_health(
        settings=AppSettings(data_dir=tmp_path),
        manifest=manifest,
        base_dir=tmp_path,
        now=now,
    )

    assert health.status == ServiceHealthLevel.ERROR
    assert health.services[0].health_check_kind == "tcp"
    assert health.services[0].status == ServiceHealthLevel.ERROR
