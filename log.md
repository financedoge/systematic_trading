# Project Log

This file records durable project decisions, operating status, incidents, and next actions. Keep entries concise, dated, and useful for future agents and human review.

## 2026-06-29

### Recorder/VPN/TWS Incident And Hardening

- Operator reported a one-day recorder run with multiple failures: external VPN was switched off or idled, NATS/ClickHouse became unavailable, and IB TWS later logged out and produced repeated API failures that required manual relogin.
- Local evidence showed a repeated automation alert storm from IB execution/account snapshot tasks. Messages progressed from IB farm disconnects to repeated `Timed out waiting for IB nextValidId callback for client_id 131/141`.
- The 2026-06-29 delayed 5-symbol recorder pilot for `SPY`, `QQQ`, `TLT`, `GLD`, and `IWM` wrote 0 records and received IB 420 market-data-permission errors for AMEX/ISLAND ETF contracts. Delayed mode remains useful for tiny experiments, but it is not sufficient proof that the 5-second streaming recorder can run before live subscriptions are enabled.
- Decision: do not rely on an external idle-sensitive VPN as part of the critical local trading platform network path. For 24x7 operation, move required infrastructure and IB Gateway toward a supervised server/native-service path.
- Decision: keep IB live-data subscriptions planned for July 2026 as the gating event for real intraday streaming. After subscriptions are enabled, run live-mode entitlement smoke tests before scaling from 1 symbol to 5 symbols and then to 30-40 ETFs.
- Added an IB automation circuit breaker to the trading management loop. After repeated IB failures, automation backs off execution/account-snapshot retries, records circuit state in `var/live/trading_management_service_state.json`, and exposes it through platform health details.
- Added automation alert deduplication so repeated identical warning/error events do not flood `var/log/automation_alerts.jsonl` or the platform outbox.
- Added `scripts/watch_local_platform.ps1` for local health checks and optional repair. It checks NATS, Postgres, ClickHouse, the operator API, and recorder state; `-Repair` recreates NATS/ClickHouse through Docker Compose and restarts the operator dashboard if needed. It does not auto-start the recorder.
- Hardened SOTA automation against account snapshots that include holdings outside the current SOTA universe. Non-SOTA positions such as `DBB` and `USO` are filtered with warnings for SOTA proposal staging instead of failing the trading management loop.
- Updated platform health semantics so an optional service with `running=false`, such as the intentionally stopped recorder, reports `disabled` rather than stale/degraded.
- Ran the watchdog after repair: required services were `ok` for NATS JetStream, Postgres, ClickHouse, and operator dashboard. The recorder was explicitly stopped and reported as optional/disabled.
- Verification passed: full suite `173 passed`; focused watchdog smoke returned required-service status `ok`; final `GET /health` returned overall `ok` with NATS, Postgres, ClickHouse, operator dashboard, event dispatcher, and trading management loop all `ok`, and the optional recorder `disabled`.

## 2026-06-27

### Foundation Proving Session

- Started P6.0 after the operator chose to prove the current foundation before expanding market-data recording or normalization.
- Scope: add a recommended local startup path, monitor NATS/Postgres/ClickHouse/operator/dispatcher/recorder health, expose a web portal with a service connection chart, and keep market-data recording opt-in to protect disk space.
- P3.4a was added as the next market-data step: a small ETF raw-data recording and audit loop before broad normalized-bar ingestion.
- Completed P6.0 foundation proving.
- Added `scripts/start_local_platform.ps1` as the recommended local startup path. It starts NATS JetStream, configures the `ST_EVENTS` stream, verifies Postgres, starts ClickHouse, starts the operator dashboard and event dispatcher, and leaves market-data recording opt-in behind `-StartMarketDataRecorder`.
- Added `scripts/stop_local_platform.ps1` and `scripts/stop_market_data_recorder.ps1`; the stop path does not stop external Postgres.
- Promoted NATS, Postgres, and ClickHouse into active health-monitored services in `config/service-manifest.json`.
- Added TCP health checks for Postgres and a service graph contract at `/api/v1/platform/service-graph`.
- Added the platform health portal at `/platform`; it shows summary health, per-service cards, detail rows, and a manifest-derived service connection chart.
- Local smoke after startup reported required services `ok`: NATS JetStream, Postgres, ClickHouse, operator dashboard, event outbox dispatcher, and embedded trading management loop. Optional market-data recorder was degraded because it was intentionally not started.
- Browser check of `/platform` showed 7 service cards, 7 detail rows, an in-bounds SVG graph, overall `ok`, and no console errors.
- Verification passed: full test suite `166 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.
- Next action remains P3.4a: run a small ETF raw-data pilot and data audit before broad normalization.
- Started P3.4a pilot operation. First live-mode IB recorder attempt reached TWS but failed with IB error 420: no live market-data permissions for AMEX STK.
- Decision: default local recorder pilots to IB delayed market data until live exchange subscriptions are explicitly enabled. Added `-RecorderMarketDataMode` to `scripts/start_local_platform.ps1`; default is `delayed`, with `live`, `frozen`, and `delayed_frozen` available.

### Observability Logs

- Completed P6.0a structured operational logs v0.
- Added `systematic_trading.services.operational_log` with `OperationalLogger`, JSONL append helpers, UTC timestamps, level/event/message/details fields, and redaction for obvious secret keys such as passwords, tokens, credentials, secrets, and API keys.
- Standard operational log path is `var/log/platform_operations.jsonl`.
- `scripts/start_local_platform.ps1` now logs local supervisor startup requests, NATS/ClickHouse/Postgres readiness steps, operator startup, recorder opt-in decisions, recorder pilot process start, completion, and startup failures.
- `scripts/start_operator_dashboard.ps1` passes the shared operational log path to `scripts/dispatch_event_outbox.py`.
- `scripts/dispatch_event_outbox.py` now logs dispatcher start, dispatch batches with activity or periodic heartbeat, publish failures, max-iteration stops, one-shot completion, and operator interruption.
- Operator API lifespan logs are emitted by `systematic_trading.app`: API startup/shutdown plus embedded automation loop start/stop.
- Market-data recorder logs now include run start/completion/failure/interruption, PID removal, initialization, subscriptions/request starts, IB market-data mode callbacks, pacing sleeps, first/periodic bar writes, source errors, and disconnects.
- `scripts/stop_market_data_recorder.ps1` now rewrites the recorder state file as stopped and appends operational log events for normal stops, stale PID cleanup, empty PID cleanup, and no-PID cases.
- Smoke check wrote `dispatcher_started`, `dispatch_batch`, and `dispatcher_completed` rows to `var/log/dispatch_smoke_operations.jsonl`.
- Verification passed: focused observability suite `31 passed`; full suite `169 passed`; final focused script/log/recorder suite `9 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.

### Execution Process

- Added `docs/execution-kanban.md` as the durable Kanban-style execution tracker.
- Future sessions must update the Kanban before starting and after completing implementation work.
- Status values are `Done`, `In Progress`, `Pending`, `Blocked`, and `Review`.
- `AGENTS.md`, `README.md`, and `docs/industrial-platform-plan.md` now point future agents to the tracker.

### Direction

- Reframed the project target from a local Python research toolkit into a 24x7 industrial systematic trading platform.
- Target architecture now requires micro-services, message queue, columnar analytics storage, transactional order state, live market-data recording, LEAN-compatible backtesting, Interactive Brokers execution, Grafana-class monitoring, strong rebalance blotter, and explicit research-to-paper-to-live promotion controls.
- Python remains the default for research, APIs, reports, and orchestration. Go, Rust, or C++ should be introduced only at measured bottlenecks or reliability-critical service boundaries.

### Decisions

- Keep the existing FastAPI, SQLite, dashboard, and paper-routing implementation as the v0 control plane.
- Treat `docs/industrial-platform-plan.md` as the target-state architecture and execution schedule.
- Treat `docs/research-state.md` as the current strategy research memory and SOTA promotion reference.
- Treat `docs/live-rollout.md` as the current paper-to-live operating path.
- Live trading remains blocked until paper execution, reconciliation, alerts, monitoring, market-data recording, and rollback procedures are proven.

### Next Actions

1. Select the initial local queue and storage stack: NATS JetStream or Redpanda for events, Postgres for transactional state, ClickHouse or Parquet-first warehouse for columnar analytics.
2. Define event schemas for market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
3. Add a market-data recorder service that writes immutable raw data before publishing normalized events.
4. Add a strategy promotion registry with artifact hashes and explicit state transitions.
5. Build the strong rebalance blotter model and dashboard workflow.
6. Add Grafana-class metrics and dashboards for data, services, portfolio, and execution.
7. Add daily post-trade, continuous research, and robustness review reports.

### Open Risks

- SQLite is not a sufficient target-state system of record for 24x7 trading operations.
- Current backtesting is useful but must be supplemented with LEAN or a proven equivalent before production promotion.
- Current alerting is not broad enough for live trading because urgent SMS, push, desktop popup, dashboard, and incident workflows are not complete.
- Live market-data recording is not yet a first-class always-on service.

### Implementation Progress

- Added initial versioned platform event contracts in `systematic_trading.domain.events`.
- Covered market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
- Added tests for event subjects, JSON round trips, typed decoding, timezone-aware timestamps, positive trading quantities, and strict payload fields.
- Full test suite passed: 123 tests.
- Added durable SQLite platform event outbox with append, pending-list, publish-success, and publish-failure recording.
- Added queue-agnostic event outbox dispatcher and in-memory publisher in `systematic_trading.messaging.outbox`.
- Added tests for idempotent event append, pending order, publish marking, failure retention, retry, and successful dispatch.
- Wired transactional event producers into SQLite storage for proposal creation, approval decisions, broker order status changes, and aggregate fill records.
- Added tests proving real storage mutations append the expected outbox events without duplicate proposal or fill events on repeated saves.
- Added local JSONL platform event publisher and `scripts/dispatch_event_outbox.py`.
- The dispatch script can run once or poll continuously with `--loop`; default output is `var/events/platform_events.jsonl`.
- Integrated the event outbox dispatcher into `scripts/start_operator_dashboard.ps1` and `scripts/stop_operator_dashboard.ps1`.
- Start script now launches `dispatch_event_outbox.py --loop` unless `-DisableEventDispatcher` is passed.
- Stop script now stops both the event outbox dispatcher and the dashboard.
- Smoke tested the operator stack on port 8765: dashboard health returned `{"status":"ok"}`, dispatcher PID existed, and stop removed both processes.
- Added `docs/service-supervisor.md` and `config/service-manifest.json`.
- Added `systematic_trading.services.manifest` loader and validation models.
- Service manifest currently covers the operator dashboard, event outbox dispatcher, embedded trading management loop, and planned market data recorder.
- Corrected execution ordering after review: P1.6 event replay and P1.7 queue selection should come before P2.3 health-check work.
- Marked P1.8 real queue publisher adapter as blocked until P1.7 selects a queue and a local/server runtime is available.
- Added platform event replay support for JSONL and SQLite outbox records in `systematic_trading.messaging.replay`.
- Added `scripts/replay_platform_events.py` for event replay summaries and detailed event inspection.
- Selected NATS JetStream as the initial real queue adapter target; rationale and adapter contract are documented in `docs/queue-adapter-selection.md`.
- P1.8 remains blocked until a local/server NATS JetStream runtime path and Python client dependency are available.
- Added the P2.3 service health contract in `systematic_trading.services.health`.
- `GET /health` now returns normalized platform health with per-service status, heartbeat, running state, and last error while preserving HTTP 200 for API liveness.
- The event outbox dispatcher now writes `var/run/event_outbox_dispatcher.state.json` heartbeats via `--state-path`.
- Updated `config/service-manifest.json`, `docs/service-supervisor.md`, and `docs/data-contracts.md` for the health contract.
- Full test suite passed: 144 tests.
- Added the P6.4 alert event producer.
- `AutomationAlertNotifier` now accepts an optional event store and appends typed `alert.raised` platform events for automation warnings and errors.
- `TradingManagementService` passes its SQLite store to the default alert notifier, so automation alerts enter the durable outbox without changing existing JSONL/email behavior.
- Alert outbox append failures are logged to `automation_alert_event_errors.log` and do not suppress existing alert logging.
- Full test suite passed: 146 tests.
- Added the P3.1 market data recorder contract in `docs/market-data-recorder-contract.md`.
- The contract defines raw-before-publish rules, the raw JSONL envelope, storage layout, normalized `market_data.recorded` mapping, replay behavior, quality flags, and service-health state requirements.
- Linked the contract from `README.md`, `docs/data-contracts.md`, and `docs/service-supervisor.md`.
- `git diff --check` passed after the documentation update.
- Accepted Docker Compose as the recommended NATS JetStream runtime path.
- Added `deploy/nats/docker-compose.yml`, `deploy/nats/nats-server.conf`, `scripts/start_nats_jetstream.ps1`, `scripts/stop_nats_jetstream.ps1`, and `scripts/configure_nats_stream.py`.
- Added optional queue dependency `nats-py` and `systematic_trading.messaging.NatsJetStreamPublisher`.
- `scripts/dispatch_event_outbox.py` now supports `--publisher nats --nats-url nats://127.0.0.1:4222`.
- Added `nats_jetstream` to `config/service-manifest.json` as a planned Docker Compose service.
- Docker CLI is not installed on this machine, so live NATS startup/stream smoke remains blocked under P2.8.
- Full test suite passed: 147 tests.
- Attempted live NATS smoke after operator reported Docker installation.
- `docker --version` and `docker compose version` are still unavailable in this shell; standard Docker Desktop paths were not present.
- `winget list --name Docker` showed `Docker.sbx`, not Docker Desktop or a visible Docker CLI/engine.
- Installed the queue optional dependency into `.venv`; `nats-py` imports successfully.
- Focused queue tests passed after dependency install: `tests/test_nats_publisher.py` and `tests/test_event_outbox.py`.
- Docker became visible in the shell: Docker version 29.5.3 and Docker Compose v5.1.4.
- Started NATS JetStream through `scripts/start_nats_jetstream.ps1`; NATS health returned `{"status":"ok"}` and container `systematic-trading-nats` is running.
- Created JetStream stream `ST_EVENTS` with subject `systematic_trading.events.v1.>`.
- Published smoke event `evt-nats-smoke-20260627-001` through `scripts/dispatch_event_outbox.py --publisher nats`; dispatcher result was `attempted=1`, `published=1`, `failed=0`.
- Verified SQLite outbox marked the event published with no pending records and JetStream stream state shows one message.
- Added the P2.4 Postgres transactional store design in `docs/postgres-transactional-store-design.md`.
- The design covers schema families for core, strategy, portfolio, execution, ops, and events; transaction boundaries; indexes; outbox locking; migration stages; and operational controls.
- Linked the Postgres design from `README.md` and `docs/data-contracts.md`.
- Full test suite passed after NATS smoke and script fix: 147 tests.
- Inspected local storage for market-data recording: D has 600.25 GB free, E has 308.15 GB free, and Z is a network drive at `\\WDMYCLOUDMIRROR\Public` with 1138.21 GB free.
- Added `config/market-data-storage.json` with a tiered policy: E hot spool, D local archive, Z asynchronous backup.
- Updated `docs/market-data-recorder-contract.md` to keep bulk market data outside the git repo and to enforce free-space watermarks before recorder implementation.
- Completed P2.5 SQLite-to-Postgres adapter boundary.
- Added protocol contracts in `systematic_trading.storage.interfaces` for watchlist, proposals, broker orders, market data, PnL, event append, outbox dispatch, and outbox replay.
- Added `systematic_trading.storage.create_transactional_store` and `ST_TRANSACTIONAL_STORE_BACKEND`; SQLite is the only implemented backend today and unsupported backends fail explicitly until the Postgres adapter is built.
- Routed FastAPI app composition and the event dispatch/replay scripts through the transactional store factory.
- Replaced production package type dependencies on `SQLiteStore` with storage protocols; direct SQLite imports remain only in the concrete storage package and local research/CLI scripts.
- Added `tests/test_storage_factory.py`.
- Full test suite passed: 151 tests.
- Validated local Postgres runtime for P2.8 after operator reported it installed and running.
- PostgreSQL service `postgresql-x64-18` is running with automatic startup; installer registry reports PostgreSQL `18.4-2`, base directory `C:\Program Files\PostgreSQL\18`, and data directory `C:\Program Files\PostgreSQL\18\data`.
- Port `5432` is listening on IPv4 and IPv6; `pg_isready -h 127.0.0.1 -p 5432` returned accepting connections.
- `psql` authenticated SQL check was blocked because no project password, `.env` DSN, or `pgpass.conf` is configured; next Postgres implementation work needs a project role/database/DSN before adapter or migration smoke tests.
- P2.8 remains blocked overall because ClickHouse is still pending.
- Ran authenticated Postgres role smoke after operator configured local project roles/database and supplied current-session credentials.
- `st_app`, `st_migrator`, and `st_readonly` all connect to database `systematic_trading`; timezone is UTC.
- Expected schemas exist: `core`, `strategy`, `portfolio`, `execution`, `ops`, and `events`.
- `st_migrator` can `SET ROLE st_owner` and create DDL inside a rolled-back transaction.
- `st_app` is correctly denied schema DDL.
- No project application tables are present yet; table creation should come from versioned migration tooling, not manual setup.
- Passwords were not written into repo files or durable logs.
- Completed P2.6 columnar store target design.
- Selected ClickHouse as the serving analytical store, Parquet as the immutable archive/interchange layer, and DuckDB as the local/offline Parquet research reader.
- Added `docs/columnar-store-target-design.md`, `config/columnar-store.json`, `deploy/clickhouse/docker-compose.yml`, `scripts/start_clickhouse.ps1`, `scripts/stop_clickhouse.ps1`, and `scripts/smoke_clickhouse_columnar_store.ps1`.
- Linked the columnar target from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, `docs/industrial-platform-plan.md`, and `docs/service-supervisor.md`.
- Added ClickHouse to `config/service-manifest.json` as the planned local columnar store service.
- Focused verification passed: JSON validation for `config/service-manifest.json` and `config/columnar-store.json`; `pytest tests/test_service_manifest.py tests/test_operator_scripts.py`; `git diff --check`.
- Attempted ClickHouse data storage on `E:/systematic_trading_runtime/clickhouse/data`; health and table creation worked, but MergeTree inserts failed because the Windows bind mount denied atomic part renames.
- Switched the local Windows ClickHouse runtime to Docker volume `clickhouse_clickhouse_data` for `/var/lib/clickhouse`; ClickHouse logs remain on `D:/systematic_trading_data/clickhouse/logs`.
- Completed P2.8 external service runtime smoke: NATS JetStream container is running and healthy, Postgres `pg_isready` reports `127.0.0.1:5432` accepting connections, and ClickHouse container `systematic-trading-clickhouse` is healthy.
- ClickHouse smoke passed through `scripts/smoke_clickhouse_columnar_store.ps1`: created a MergeTree smoke table, inserted one row, and queried `smoke_rows=1`.
- Keep the durable market-data lake on D with async Z backup; ClickHouse is a rebuildable serving store until server/native-disk deployment is validated.
- Completed P2.7 schema registry convention.
- Added `systematic_trading.schemas` as the code-based schema registry for the current single-repo phase.
- Registered current platform event schemas and core data schemas with stable schema ids, owners, statuses, JSON Schema export, and compatibility modes.
- Event schemas remain strict by default because current event models reject extra fields; core data schemas start with backward compatibility.
- Added compatibility checks for Pydantic models and JSON Schema snapshots; optional additions can be backward-compatible, while required additions, field removals, and type changes are flagged.
- Added `docs/schema-registry-convention.md` and linked it from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, and `docs/industrial-platform-plan.md`.
- Focused verification passed: `pytest tests/test_schema_registry.py tests/test_events.py tests/test_event_replay.py tests/test_nats_publisher.py`; `git diff --check`.
- P2 Service Foundation is now complete on the Kanban; next recommended work starts P3.2 IB paper market-data recorder v0.
- Completed P3.2a recorder source and capacity spec before implementing the IB recorder.
- Added `docs/market-data-recorder-source-plan.md` to define two recorder lanes: a low-frequency daily reference recorder and an intraday IB recorder.
- Documented IBKR capacity assumptions for P3.2: default 100 market-data lines, reserve 20 lines, record 5-second real-time bars for the 40-symbol ETF seed, keep top-of-book optional, keep tick-by-tick to a 3-symbol default canary set with hard cap 5, and keep Level 2 out of scope.
- Added `config/market-data-recorder-sources.json` as the machine-readable lane, pacing, ETF seed, and secondary-source policy.
- Secondary intraday candidates for later validation are IB delayed mode, Alpaca, Alpha Vantage Premium, Massive/Polygon, and Wind intraday if local entitlement/storage rights allow it.
- Verification passed: `python -m json.tool config\market-data-recorder-sources.json`, 40 unique seed symbols, and `git diff --check`.
- Started and completed P3.2 IB paper market-data recorder v0 after the operator logged into IB TWS paper and enabled the API.
- Added `systematic_trading.recorders` with raw JSONL envelope writing, deterministic raw/event ids, source-policy capacity validation, token-bucket pacing, recorder state-file updates, and raw replay dry-run validation.
- Added `scripts/record_ib_market_data.py` for IB realtime recording and bounded `historical-smoke` tests, plus `scripts/replay_market_data_raw.py` for one-symbol/day raw validation.
- Updated the service manifest so `market_data_recorder` is an implemented optional worker with state-file health, PID path, and manual startup command.
- Smoke-tested the running IB TWS paper connection: `scripts/test_ib_paper_connection.py --timeout-seconds 15` connected to `127.0.0.1:7497` and received `nextValidId=1`.
- Ran a bounded SPY historical-smoke request ending at the 2026-06-26 US market close: wrote 3 raw 5-second bar records under `E:/systematic_trading_runtime/market-data/hot/...`, appended 3 `market_data.recorded` events to `var/systematic_trading.db`, and wrote `var/run/market_data_recorder.state.json`.
- Raw replay dry-run for `SPY` on recorder partition date `2026-06-27` read 3 records, validated 3 records, and found 0 payload-hash mismatches.
- Verification passed: focused recorder/service/event tests, full test suite `162 passed in 172.62s`, JSON validation for recorder and service config, and `git diff --check`.
- Started and completed P3.3 raw data catalog.
- Added append-only raw manifest entries under `<root>/raw/_manifest/date=<YYYY-MM-DD>.jsonl` with source, environment, data kind, symbol, recorder date, raw schema version, raw ref, byte offset, byte count, payload hash, timestamps, capture mode, request id, and quality flags.
- Recorder write order is now raw JSONL first, raw catalog entry second, and `market_data.recorded` outbox event third.
- Added query and rebuild helpers in `systematic_trading.recorders.market_data` and `scripts/catalog_market_data_raw.py` for operator-level discovery and manifest recovery from existing raw partitions.
- Rebuilt and queried the existing IB SPY smoke data in the E hot spool: 3 catalog entries, 0 invalid records, 0 duplicate raw refs; query filters covered source `interactive-brokers`, environment `paper`, data kind `bar`, date `2026-06-27`, symbol `SPY`, and raw schema version 1.
- Verification passed: focused recorder/service/event suite `38 passed`, full test suite `163 passed in 173.86s`, JSON validation for service/recorder/storage configs, and `git diff --check`.
