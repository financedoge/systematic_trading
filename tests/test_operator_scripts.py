from pathlib import Path


def test_operator_dashboard_scripts_manage_pid_logs_and_health() -> None:
    start_script = Path("scripts/start_operator_dashboard.ps1").read_text(encoding="utf-8")
    stop_script = Path("scripts/stop_operator_dashboard.ps1").read_text(encoding="utf-8")
    serve_script = Path("scripts/serve_operator_dashboard.py").read_text(encoding="utf-8")
    nats_start_script = Path("scripts/start_nats_jetstream.ps1").read_text(encoding="utf-8")
    nats_stop_script = Path("scripts/stop_nats_jetstream.ps1").read_text(encoding="utf-8")
    clickhouse_start_script = Path("scripts/start_clickhouse.ps1").read_text(encoding="utf-8")
    clickhouse_stop_script = Path("scripts/stop_clickhouse.ps1").read_text(encoding="utf-8")
    clickhouse_smoke_script = Path("scripts/smoke_clickhouse_columnar_store.ps1").read_text(encoding="utf-8")
    local_start_script = Path("scripts/start_local_platform.ps1").read_text(encoding="utf-8")
    local_stop_script = Path("scripts/stop_local_platform.ps1").read_text(encoding="utf-8")
    recorder_stop_script = Path("scripts/stop_market_data_recorder.ps1").read_text(encoding="utf-8")
    watchdog_script = Path("scripts/watch_local_platform.ps1").read_text(encoding="utf-8")

    assert "operator_dashboard.pid" in start_script
    assert "event_outbox_dispatcher.pid" in start_script
    assert "operator_dashboard.out.log" in start_script
    assert "operator_dashboard.err.log" in start_script
    assert "event_outbox_dispatcher.out.log" in start_script
    assert "event_outbox_dispatcher.err.log" in start_script
    assert "event_outbox_dispatcher.state.json" in start_script
    assert "serve_operator_dashboard.py" in start_script
    assert "dispatch_event_outbox.py" in start_script
    assert "--loop" in start_script
    assert "--state-path" in start_script
    assert "DisableEventDispatcher" in start_script
    assert "EventPublisher" in start_script
    assert "--publisher" in start_script
    assert "OperationLogPath" in start_script
    assert "--operation-log" in start_script
    assert "--log-heartbeat-every-iterations" in start_script
    assert "nats://127.0.0.1:4222" in start_script
    assert "platform_events.jsonl" in start_script
    assert "/health" in start_script
    assert "/operator" in start_script
    assert "Start-Process" in start_script
    assert "-WindowStyle Hidden" in start_script

    assert "operator_dashboard.pid" in stop_script
    assert "event_outbox_dispatcher.pid" in stop_script
    assert "Event outbox dispatcher" in stop_script
    assert "Stop-Process" in stop_script
    assert "Remove-Item" in stop_script

    assert "uvicorn.run" in serve_script
    assert "systematic_trading.app:app" in serve_script
    assert "os.getpid()" in serve_script
    assert "ST_AUTOMATION_ENABLED" in serve_script
    assert "--disable-automation" in serve_script

    assert "docker compose" in nats_start_script
    assert "deploy\\nats\\docker-compose.yml" in nats_start_script
    assert "nats://127.0.0.1:4222" in nats_start_script
    assert "$LASTEXITCODE" in nats_start_script
    assert "docker compose" in nats_stop_script
    assert "$LASTEXITCODE" in nats_stop_script
    assert Path("scripts/configure_nats_stream.py").exists()

    assert "docker compose" in clickhouse_start_script
    assert "deploy\\clickhouse\\docker-compose.yml" in clickhouse_start_script
    assert "Data volume: clickhouse_data" in clickhouse_start_script
    assert "D:/systematic_trading_data/clickhouse/logs" in clickhouse_start_script
    assert "http://127.0.0.1:8123" in clickhouse_start_script
    assert "docker compose" in clickhouse_stop_script
    assert "$LASTEXITCODE" in clickhouse_stop_script
    assert "clickhouse-client" in clickhouse_smoke_script
    assert "smoke_p2_8" in clickhouse_smoke_script

    assert "start_nats_jetstream.ps1" in local_start_script
    assert "configure_nats_stream.py" in local_start_script
    assert "start_clickhouse.ps1" in local_start_script
    assert "start_operator_dashboard.ps1" in local_start_script
    assert "StartMarketDataRecorder" in local_start_script
    assert "RecorderMarketDataMode" in local_start_script
    assert "platform_operations.jsonl" in local_start_script
    assert "Write-OperationLog" in local_start_script
    assert "local_platform_start_requested" in local_start_script
    assert "--market-data-mode" in local_start_script
    assert "Market data recorder not started" in local_start_script
    assert "/platform" in local_start_script
    assert "pg_isready" in local_start_script
    assert "stop_market_data_recorder.ps1" in local_stop_script
    assert "stop_operator_dashboard.ps1" in local_stop_script
    assert "stop_clickhouse.ps1" in local_stop_script
    assert "stop_nats_jetstream.ps1" in local_stop_script
    assert "External Postgres was not stopped" in local_stop_script
    assert "market_data_recorder.pid" in recorder_stop_script
    assert "local_platform_watchdog" in watchdog_script
    assert "nats_repair_requested" in watchdog_script
    assert "clickhouse_repair_requested" in watchdog_script
    assert "operator_repair_requested" in watchdog_script
    assert "market_data_recorder.state.json" in watchdog_script
    assert "local_platform_watchdog.state.json" in watchdog_script
    assert "start_nats_jetstream.ps1" in watchdog_script
    assert "start_clickhouse.ps1" in watchdog_script
    assert "start_operator_dashboard.ps1" in watchdog_script
