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
    docker_ready_script = Path("scripts/assert_docker_ready.ps1").read_text(encoding="utf-8")
    local_start_script = Path("scripts/start_local_platform.ps1").read_text(encoding="utf-8")
    local_stop_script = Path("scripts/stop_local_platform.ps1").read_text(encoding="utf-8")
    recorder_start_script = Path("scripts/start_market_data_recorder_service.ps1").read_text(encoding="utf-8")
    recorder_stop_script = Path("scripts/stop_market_data_recorder.ps1").read_text(encoding="utf-8")
    watchdog_script = Path("scripts/watch_local_platform.ps1").read_text(encoding="utf-8")
    golden_sync_script = Path("scripts/sync_sqlite_daily_bars_to_clickhouse.py").read_text(encoding="utf-8")
    fx_sync_script = Path("scripts/sync_sqlite_fx_rates_to_clickhouse.py").read_text(encoding="utf-8")
    daily_backfill_script = Path("scripts/backfill_clickhouse_daily_bars.py").read_text(encoding="utf-8")
    postgres_migration_script = Path("scripts/apply_postgres_migrations.py").read_text(encoding="utf-8")
    postgres_sync_script = Path("scripts/sync_sqlite_transactional_to_postgres.py").read_text(encoding="utf-8")
    postgres_smoke_script = Path("scripts/smoke_postgres_transactional_store.py").read_text(encoding="utf-8")
    ib_tws_probe_script = Path("scripts/probe_ib_tws_health.py").read_text(encoding="utf-8")
    ib_reconcile_script = Path("scripts/reconcile_ib_paper_account.py").read_text(encoding="utf-8")

    assert "operator_dashboard.pid" in start_script
    assert "Test-ProcessOwnsPort" in start_script
    assert "Test-DispatcherStatePid" in start_script
    assert "dispatcherState.details.process_id" in start_script
    assert "belongs to another process" in start_script
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
    assert "TransactionalStoreBackend" in start_script
    assert "ST_TRANSACTIONAL_STORE_BACKEND" in start_script
    assert "MarketDataStoreBackend" in start_script
    assert "ST_MARKET_DATA_STORE_BACKEND" in start_script
    assert "--log-heartbeat-every-iterations" in start_script
    assert "nats://127.0.0.1:4222" in start_script
    assert "platform_events.jsonl" in start_script
    assert "/health" in start_script
    assert "/operator" in start_script
    assert "Start-Process" in start_script
    assert "-WindowStyle Hidden" in start_script
    assert "probe_ib_tws_health.py" in start_script
    assert "ib_tws_api.state.json" in start_script

    assert "operator_dashboard.pid" in stop_script
    assert "Test-ExpectedServiceProcess" in stop_script
    assert "Removed stale PID file without stopping it" in stop_script
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
    assert "assert_docker_ready.ps1" in nats_start_script
    assert "deploy\\nats\\docker-compose.yml" in nats_start_script
    assert "nats://127.0.0.1:4222" in nats_start_script
    assert "$LASTEXITCODE" in nats_start_script
    assert "docker compose" in nats_stop_script
    assert "$LASTEXITCODE" in nats_stop_script
    assert Path("scripts/configure_nats_stream.py").exists()

    assert "docker compose" in clickhouse_start_script
    assert "assert_docker_ready.ps1" in clickhouse_start_script
    assert "deploy\\clickhouse\\docker-compose.yml" in clickhouse_start_script
    assert "Data volume: clickhouse_data" in clickhouse_start_script
    assert "D:/systematic_trading_data/clickhouse/logs" in clickhouse_start_script
    assert "http://127.0.0.1:8123" in clickhouse_start_script
    assert "docker compose" in clickhouse_stop_script
    assert "$LASTEXITCODE" in clickhouse_stop_script
    assert "clickhouse-client" in clickhouse_smoke_script
    assert "smoke_p2_8" in clickhouse_smoke_script
    assert "docker info" in docker_ready_script
    assert "Docker daemon is not reachable" in docker_ready_script
    assert "StartDockerDesktopIfStopped" in docker_ready_script
    assert "Docker Desktop.exe" in docker_ready_script
    assert "-SkipNats -SkipClickHouse" in docker_ready_script
    assert "Last docker error" in docker_ready_script

    assert "start_nats_jetstream.ps1" in local_start_script
    assert "configure_nats_stream.py" in local_start_script
    assert "start_clickhouse.ps1" in local_start_script
    assert "start_operator_dashboard.ps1" in local_start_script
    assert "StartMarketDataRecorder" in local_start_script
    assert "SkipMarketDataRecorder" in local_start_script
    assert "run_market_data_recorder_service.py" in local_start_script
    assert "RecorderMarketDataMode" in local_start_script
    assert "TransactionalStoreBackend" in local_start_script
    assert "MarketDataStoreBackend" in local_start_script
    assert "ST_TRANSACTIONAL_STORE_BACKEND" in local_start_script
    assert "ST_MARKET_DATA_STORE_BACKEND" in local_start_script
    assert "platform_operations.jsonl" in local_start_script
    assert "Write-OperationLog" in local_start_script
    assert "local_platform_start_requested" in local_start_script
    assert "--market-data-mode" in local_start_script
    assert "Market data recorder service started" in local_start_script
    assert "recorder_service_not_started" in local_start_script
    assert "/platform" in local_start_script
    assert "pg_isready" in local_start_script
    assert "probe_ib_tws_health.py" in local_start_script
    assert "ib_tws_api.state.json" in local_start_script
    assert "stop_market_data_recorder.ps1" in local_stop_script
    assert "stop_operator_dashboard.ps1" in local_stop_script
    assert "stop_clickhouse.ps1" in local_stop_script
    assert "stop_nats_jetstream.ps1" in local_stop_script
    assert "External Postgres was not stopped" in local_stop_script
    assert "run_market_data_recorder_service.py" in recorder_start_script
    assert "market_data_recorder.pid" in recorder_start_script
    assert "market_data_recorder.state.json" in recorder_start_script
    assert "DailyBackfillProvider" in recorder_start_script
    assert "--daily-backfill-provider" in recorder_start_script
    assert "--daily-backfill-fallback-provider" in recorder_start_script
    assert "-WindowStyle Hidden" in recorder_start_script
    assert "market_data_recorder.pid" in recorder_stop_script
    assert "local_platform_watchdog" in watchdog_script
    assert "nats_repair_requested" in watchdog_script
    assert "clickhouse_repair_requested" in watchdog_script
    assert "operator_repair_requested" in watchdog_script
    assert "market_data_recorder.state.json" in watchdog_script
    assert "local_platform_watchdog.state.json" in watchdog_script
    assert "ib_tws_api.state.json" in watchdog_script
    assert "probe_ib_tws_health.py" in watchdog_script
    assert "start_nats_jetstream.ps1" in watchdog_script
    assert "start_clickhouse.ps1" in watchdog_script
    assert "start_operator_dashboard.ps1" in watchdog_script
    assert "ClickHouseMarketDataClient" in golden_sync_script
    assert "price_bars" in golden_sync_script
    assert "fx_rates" in fx_sync_script
    assert "insert_fx_rate_rows" in fx_sync_script
    assert "backfill_clickhouse_daily_bars" in daily_backfill_script
    assert "--refresh-existing" in daily_backfill_script
    assert "--fallback-provider" in daily_backfill_script
    assert "ops.schema_migrations" in postgres_migration_script
    assert "SET ROLE" in postgres_migration_script
    assert "platform_event_outbox" in postgres_sync_script
    assert "price_bars" not in postgres_sync_script
    assert "fx_rates" not in postgres_sync_script
    assert "transactional_store_backend=\"postgres\"" in postgres_smoke_script
    assert "--keep-records" in postgres_smoke_script
    assert "probe_ib_tws_health" in ib_tws_probe_script
    assert "write_service_state_file" in ib_tws_probe_script
    assert "reconcile_ib_paper_account" in ib_reconcile_script
    assert "--record-pnl-reset-baseline" in ib_reconcile_script
    assert "--confirm-paper-reset" in ib_reconcile_script
