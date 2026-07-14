from pathlib import Path

import pytest
from pydantic import ValidationError

from systematic_trading.services import ServiceManifest, load_service_manifest


def test_default_service_manifest_loads_current_operator_stack() -> None:
    manifest = load_service_manifest()

    assert manifest.schema_version == 1
    assert [service.service_id for service in manifest.ordered_services()[:4]] == [
        "nats_jetstream",
        "postgres_transactional",
        "ib_tws_api",
        "clickhouse_columnar",
    ]
    dashboard = manifest.service("operator_dashboard")
    dispatcher = manifest.service("event_outbox_dispatcher")
    automation = manifest.service("trading_management_loop")
    nats = manifest.service("nats_jetstream")
    postgres = manifest.service("postgres_transactional")
    ib_tws = manifest.service("ib_tws_api")
    clickhouse = manifest.service("clickhouse_columnar")
    recorder = manifest.service("market_data_recorder")

    assert dashboard.health_check.target == "http://127.0.0.1:8000/health"
    assert dashboard.pid_file == "var/run/operator_dashboard.pid"
    assert "scripts/serve_operator_dashboard.py" in dashboard.command
    assert dispatcher.pid_file == "var/run/event_outbox_dispatcher.pid"
    assert dispatcher.health_check.target == "var/run/event_outbox_dispatcher.state.json"
    assert dispatcher.health_check.stale_after_seconds == 30
    assert "scripts/dispatch_event_outbox.py" in dispatcher.command
    assert "--publisher" in dispatcher.command
    assert "nats" in dispatcher.command
    assert "--loop" in dispatcher.command
    assert dispatcher.depends_on == ["nats_jetstream"]
    assert automation.supervised_by == "operator_dashboard"
    assert automation.depends_on == ["operator_dashboard"]
    assert nats.implementation_status.value == "active"
    assert nats.health_check.target == "http://127.0.0.1:8222/healthz?js-enabled-only=true"
    assert "scripts/start_nats_jetstream.ps1" in nats.command
    assert postgres.implementation_status.value == "active"
    assert postgres.health_check.kind.value == "tcp"
    assert postgres.health_check.target == "127.0.0.1:5432"
    assert postgres.restart_policy.mode == "external_windows_service"
    assert ib_tws.required is True
    assert ib_tws.health_check.kind.value == "state_file"
    assert ib_tws.health_check.target == "var/run/ib_tws_api.state.json"
    assert "scripts/probe_ib_tws_health.py" in ib_tws.command
    assert ib_tws.restart_policy.mode == "external_tws_session"
    assert clickhouse.implementation_status.value == "active"
    assert clickhouse.health_check.target == "http://127.0.0.1:8123/ping"
    assert "scripts/start_clickhouse.ps1" in clickhouse.command
    assert clickhouse.environment["ST_CLICKHOUSE_LOG_ROOT"].startswith("D:/")
    assert recorder.implementation_status.value == "active"
    assert recorder.required is False
    assert "scripts/run_market_data_recorder_service.py" in recorder.command
    assert "SPY,QQQ,TLT,GLD,IWM" in recorder.command
    assert "--intraday-feed" in recorder.command
    assert "delayed-trades" in recorder.command
    assert recorder.health_check.stale_after_seconds == 420
    assert recorder.health_check.target == "var/run/market_data_recorder.state.json"


def test_service_manifest_matches_operator_scripts() -> None:
    manifest = load_service_manifest()
    start_script = Path("scripts/start_operator_dashboard.ps1").read_text(encoding="utf-8")
    stop_script = Path("scripts/stop_operator_dashboard.ps1").read_text(encoding="utf-8")

    for service_id in ["operator_dashboard", "event_outbox_dispatcher"]:
        service = manifest.service(service_id)
        assert Path(service.pid_file).name in start_script
        assert Path(service.pid_file).name in stop_script
        assert Path(service.stdout_log).name in start_script
        assert Path(service.stderr_log).name in start_script


def test_service_manifest_rejects_duplicate_service_ids() -> None:
    payload = {
        "schema_version": 1,
        "profile": "test",
        "services": [
            {
                "service_id": "duplicate",
                "display_name": "One",
                "service_type": "worker",
                "startup_order": 1,
                "command": ["python"],
                "pid_file": "var/run/one.pid",
            },
            {
                "service_id": "duplicate",
                "display_name": "Two",
                "service_type": "worker",
                "startup_order": 2,
                "command": ["python"],
                "pid_file": "var/run/two.pid",
            },
        ],
    }

    with pytest.raises(ValidationError, match="duplicate service_id"):
        ServiceManifest.model_validate(payload)


def test_service_manifest_rejects_unknown_dependencies() -> None:
    payload = {
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
                "depends_on": ["missing"],
            }
        ],
    }

    with pytest.raises(ValidationError, match="unknown dependencies"):
        ServiceManifest.model_validate(payload)
