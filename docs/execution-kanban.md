# Execution Kanban

This is the durable build tracker for the industrial trading platform. Update it at the start and end of every implementation session.

Status values:

- `Done`: implemented, documented, and verified.
- `In Progress`: actively being worked in the current session or branch.
- `Pending`: planned but not started.
- `Blocked`: cannot proceed without an explicit external decision, credential, service, dependency, or infrastructure change.
- `Review`: implemented but needs human review, operational soak, or production evidence.

## Operating Rule

Before starting work:

1. Read `docs/industrial-platform-plan.md`, `docs/execution-kanban.md`, and `log.md`.
2. Pick the highest-priority `Pending` or `Review` item that is not blocked.
3. Move it to `In Progress`.
4. Record assumptions or blockers in the item notes.

After finishing work:

1. Move completed items to `Done` only after tests or equivalent verification pass.
2. Add evidence paths, commands, or reports.
3. Update dependent items if their status changed.
4. Add a concise entry to `log.md`.

## Current Snapshot

| Area | Done | In Progress | Pending | Blocked |
| --- | ---: | ---: | ---: | ---: |
| Project memory and governance | 6 | 0 | 1 | 0 |
| Event spine and local operations | 8 | 0 | 0 | 0 |
| Service foundation | 8 | 0 | 0 | 0 |
| Market data recording | 4 | 1 | 3 | 1 |
| Research/backtest promotion | 0 | 0 | 6 | 1 |
| Portfolio and execution controls | 0 | 0 | 8 | 1 |
| Observability and alerts | 4 | 0 | 6 | 1 |
| Daily operating loops | 0 | 0 | 6 | 0 |

## P0: Project Memory And Governance

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P0.1 | Done | Industrial target-state plan | System chart, service boundaries, daily loop, and execution schedule are documented. | `docs/industrial-platform-plan.md` |
| P0.2 | Done | README project goal memory | README states industrial platform goal and links target-state plan. | `README.md` |
| P0.3 | Done | Live-disabled-by-default policy | Live rollout doc preserves paper-first gates and minimum live checklist. | `docs/live-rollout.md` |
| P0.4 | Done | Agent operating rules | Agent rules define required reading, promotion discipline, and log updates. | `AGENTS.md` |
| P0.5 | Done | Recurring operating playbooks | Daily post-trade, research, robustness, and promotion playbooks exist. | `.agents/skills/` |
| P0.6 | Done | Kanban execution tracker | This file exists, is linked from project memory, and becomes mandatory for future sessions. | `docs/execution-kanban.md`; linked from `README.md`, `AGENTS.md`, and `docs/industrial-platform-plan.md`. |
| P0.7 | Pending | Decision log discipline | Every architecture or production-control decision gets a dated `log.md` entry. | Ongoing habit, not a one-time task. |

## P1: Event Spine And Local Operations

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P1.1 | Done | Versioned platform event contracts | Typed contracts exist for market data, features, proposals, orders, fills, reconciliation, alerts, and incidents. | `src/systematic_trading/domain/events.py`; `tests/test_events.py` |
| P1.2 | Done | Durable local event outbox | SQLite stores unpublished events, attempts, errors, and published state. | `platform_event_outbox`; `tests/test_event_outbox.py` |
| P1.3 | Done | Transactional event producers | Proposal creation, approval decisions, broker order status changes, and aggregate fills emit outbox events. | `src/systematic_trading/storage/sqlite.py` |
| P1.4 | Done | Local outbox dispatcher | JSONL publisher and dispatch script can drain pending events once or continuously. | `scripts/dispatch_event_outbox.py`; `var/events/platform_events.jsonl` |
| P1.5 | Done | Run dispatcher with operator stack | Dashboard startup process can run or supervise the outbox dispatcher. | `scripts/start_operator_dashboard.ps1` starts dispatcher unless disabled; `scripts/stop_operator_dashboard.ps1` stops it. Smoke tested on port 8765. |
| P1.6 | Done | Event replay reader | JSONL or outbox events can be replayed into typed event objects for audit/debugging. | `systematic_trading.messaging.replay`; `scripts/replay_platform_events.py`; `tests/test_event_replay.py` |
| P1.7 | Done | Queue adapter selection | Select initial broker: NATS JetStream, Redpanda, or Kafka. | Selected NATS JetStream for the initial queue adapter target. Evidence: `docs/queue-adapter-selection.md`. |
| P1.8 | Done | Real queue publisher adapter | Implement publisher protocol for selected queue. | `NatsJetStreamPublisher`; dispatcher `--publisher nats`; optional `queue` dependency; Docker Compose path in `deploy/nats/`; stream bootstrap script `scripts/configure_nats_stream.py`; `tests/test_nats_publisher.py`; full suite passed: 147 tests. Live NATS smoke passed after Docker became available. |

## P2: Service Foundation

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P2.1 | Done | Local service supervisor plan | Operator dashboard, outbox dispatcher, automation loop, and future recorder have start/stop/restart conventions. | `docs/service-supervisor.md` |
| P2.2 | Done | Service manifest | Machine-readable list of services, ports, env vars, health checks, and logs. | `config/service-manifest.json`; `systematic_trading.services.manifest`; `tests/test_service_manifest.py` |
| P2.3 | Done | Health check contract | Every long-running service exposes health, heartbeat, and last-error state. | `systematic_trading.services.health`; `GET /health`; dispatcher state file `var/run/event_outbox_dispatcher.state.json`; `tests/test_service_health.py`; full suite passed: 146 tests. |
| P2.4 | Done | Postgres target design | Transactional schema target for approvals, orders, fills, outbox, incidents, and strategy registry. | `docs/postgres-transactional-store-design.md`; linked from `README.md` and `docs/data-contracts.md`; `git diff --check` passed. |
| P2.5 | Done | SQLite-to-Postgres adapter boundary | Storage interface or repository boundary avoids hard-coding SQLite as final state store. | Added `systematic_trading.storage.interfaces` protocol contracts and `systematic_trading.storage.create_transactional_store`; app/service/outbox/replay composition now goes through the factory; production package code no longer imports `SQLiteStore` outside the concrete storage package. SQLite remains the only implemented backend via `ST_TRANSACTIONAL_STORE_BACKEND=sqlite`; unsupported backends fail explicitly. Evidence: `tests/test_storage_factory.py`; full suite passed: 151 tests. |
| P2.6 | Done | Columnar store target design | Decide ClickHouse versus Parquet-first warehouse for analytics. | Selected ClickHouse as the serving analytical store, Parquet as the immutable archive/interchange layer, and DuckDB as the local/offline research reader. Added `docs/columnar-store-target-design.md`, `config/columnar-store.json`, `deploy/clickhouse/docker-compose.yml`, `scripts/start_clickhouse.ps1`, `scripts/stop_clickhouse.ps1`, and `scripts/smoke_clickhouse_columnar_store.ps1`. Evidence: JSON validation passed; `pytest tests/test_service_manifest.py tests/test_operator_scripts.py`; `git diff --check`. |
| P2.7 | Done | Schema registry convention | Version event/data schemas with compatibility rules. | Added code-based registry in `systematic_trading.schemas` with registered event/data contracts, JSON Schema export, duplicate registration checks, runtime event resolution, and compatibility checks. Added `docs/schema-registry-convention.md` and linked it from project docs. Evidence: `tests/test_schema_registry.py`; focused suite `pytest tests/test_schema_registry.py tests/test_events.py tests/test_event_replay.py tests/test_nats_publisher.py`; `git diff --check`. |
| P2.8 | Done | External service runtime | Running Postgres, ClickHouse, and queue locally or on server requires infrastructure choice/install. | Queue path is live-smoked with Docker Compose NATS JetStream; container `systematic-trading-nats` is running and NATS health returns `{"status":"ok"}`. Local PostgreSQL 18 service `postgresql-x64-18` is running and `pg_isready -h 127.0.0.1 -p 5432` returns accepting connections; authenticated role smoke previously passed. ClickHouse Docker Compose path is live-smoked; container `systematic-trading-clickhouse` is healthy, `http://127.0.0.1:8123/ping` returns `Ok.`, and `scripts/smoke_clickhouse_columnar_store.ps1` created a MergeTree smoke table, inserted one row, and queried `smoke_rows=1`. Local Windows E-drive bind mount failed MergeTree atomic rename semantics, so the local ClickHouse runtime uses Docker volume `clickhouse_clickhouse_data`; Parquet archive remains on D with async Z backup. |

## P3: Market Data Recording And Data Quality

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P3.1 | Done | Market data recorder contract | Define raw payload envelope, normalized event mapping, storage paths, and replay behavior. | `docs/market-data-recorder-contract.md`; linked from `README.md`, `docs/data-contracts.md`, and `docs/service-supervisor.md`; `git diff --check` passed. |
| P3.2a | Done | Recorder source and capacity spec | Define low-frequency and high-frequency recorder lanes, IB request/market-data-line limits, initial ETF universe capacity, and fallback delayed intraday sources. | Added `docs/market-data-recorder-source-plan.md` and `config/market-data-recorder-sources.json`. Evidence: `python -m json.tool config\market-data-recorder-sources.json`; 40-symbol seed sanity check; `git diff --check`. |
| P3.2 | Done | IB market data recorder v0 | Capture IB paper market data to immutable JSONL or Parquet path. | Added `systematic_trading.recorders`, `scripts/record_ib_market_data.py`, and `scripts/replay_market_data_raw.py`. Smoke tested against running IB TWS paper: `scripts/test_ib_paper_connection.py` connected to `127.0.0.1:7497`; historical-smoke SPY 5-second bars wrote 3 raw JSONL records under E hot spool and appended 3 `market_data.recorded` outbox events; replay dry-run read 3 valid records with 0 hash mismatches. Evidence: full suite `162 passed`; JSON validation; `git diff --check`. |
| P3.3 | Done | Raw data catalog | Recorded data is discoverable by source, symbol, date, and schema version. | Added append-only raw manifest/catalog entries in `systematic_trading.recorders.market_data`, wired catalog writes into the IB recorder, and added `scripts/catalog_market_data_raw.py` for rebuild/query. Rebuilt/query-tested the existing SPY IB smoke data: 3 manifest entries, 0 invalid records, 0 duplicate raw refs. Evidence: focused suite 38 passed; full suite `163 passed`; JSON validation; `git diff --check`. |
| P3.4a | In Progress | Pilot raw-data proving and audit loop | Record a small ETF pilot, audit raw/catalog coverage, inspect gaps/duplicates/freshness/disk use, and only then scale. | Operator agreed to prove the foundation before broad normalization. Recorder should remain opt-in because market data can fill disk quickly. First live-mode pilot hit IB error 420: no live market-data permissions for AMEX STK. A 2026-06-29 delayed 5-symbol real-time-bar pilot also wrote 0 records and hit IB 420 permission errors for AMEX/ISLAND ETF contracts. Until live subscriptions are enabled in July 2026 and smoke-tested, use historical-smoke/daily lanes for plumbing only and do not scale streaming capture. |
| P3.4 | Pending | Normalized bar/quote pipeline | Convert raw records to normalized bars/quotes with quality flags. | Must emit events and persist audit state. |
| P3.5 | Pending | Data freshness checks | Detect stale bars, missing FX, source gaps, duplicates, and clock drift. | Alerts must be generated. |
| P3.6 | Pending | Replay a trading day | Reconstruct a paper-trading day from recorded data and compare to stored decisions. | Phase 2 exit criterion. |
| P3.7 | Blocked | Paid/primary market-data vendor | Source-of-record vendor choice and credentials are not settled. | Use IB/Yahoo/Tushare only as current interim sources. |

## P4: Research, Backtest, And Promotion Registry

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P4.1 | Pending | Strategy spec schema | Versioned strategy spec includes universe, data, features, schedule, risk, execution, and artifacts. | Required before registry. |
| P4.2 | Pending | Strategy promotion registry | Persist state transitions from idea to retired with evidence and approval. | Should emit promotion events. |
| P4.3 | Pending | LEAN integration design | Document how current strategy definitions map into LEAN or LEAN-equivalent runs. | Avoid parallel strategy logic. |
| P4.4 | Pending | LEAN smoke backtest | One current SOTA or simplified strategy runs through LEAN path with reproducible artifacts. | Promotion path cannot depend only on custom engine. |
| P4.5 | Pending | Backtest artifact hashes | Reports, inputs, configs, and outputs are hashed and linked to strategy versions. | Required for audit. |
| P4.6 | Pending | Overfit/stability gate | Promotion requires split, benchmark, turnover, fee, stress, and parameter stability checks. | Extend current SOTA workflow. |
| P4.7 | Blocked | LEAN runtime/dependency setup | Requires installing/configuring LEAN runtime or choosing equivalent deployment path. | Not blocked conceptually, blocked operationally. |

## P5: Portfolio Blotter And Execution Controls

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P5.1 | Pending | Rebalance blotter domain model | Model current, target, proposed orders, expected cash, FX, fees, residuals, and constraints. | Stronger than current proposal preview. |
| P5.2 | Pending | Pre-trade check engine | Checks stale data, missing FX, price bands, buying power, duplicate orders, open orders, turnover, concentration, and live caps. | Must block routing. |
| P5.3 | Pending | Blotter API | Dashboard/API can show proposal, constraints, violations, and operator decision actions. | Current dashboard can be extended. |
| P5.4 | Pending | Resize/defer workflow | Operator can approve, reject, resize, defer, or cancel generated orders. | Must persist audit events. |
| P5.5 | Pending | IB connection health gate | Confirm server time, account, managed accounts, next valid id, and profile before routing. | Listed as next in live rollout. |
| P5.6 | Pending | Broker reconciliation gate | Compare IB positions, cash, open orders, fills, and commissions before routing. | Required before live. |
| P5.7 | Pending | Live kill switch | A hard config/runtime switch prevents live order routing immediately. | Must be tested in paper. |
| P5.8 | Pending | Live capital caps | Per-account, per-strategy, per-symbol, per-order, turnover, and drawdown caps. | Required before Phase 5. |
| P5.9 | Blocked | Live account enablement | Requires explicit human approval, credentials, account id, and proven paper evidence. | Keep live disabled. |

## P6: Observability, Alerts, And Incidents

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P6.0 | Done | Foundation service health portal and startup path | A single recommended local startup script brings up NATS, verifies Postgres, starts ClickHouse, starts the operator API/dispatcher, keeps market-data recording opt-in, and exposes a web portal with per-service health plus a connection graph. | Added `scripts/start_local_platform.ps1`, `scripts/stop_local_platform.ps1`, `scripts/stop_market_data_recorder.ps1`, `/platform`, and `/api/v1/platform/service-graph`. Local smoke: required services `ok` for NATS, Postgres, ClickHouse, operator API, dispatcher, and embedded automation; optional recorder degraded because not started. Browser check: 7 service cards, graph rendered in-bounds, no console errors. Evidence: full suite `166 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings. |
| P6.0a | Done | Structured operational logs v0 | Core scripts and services write durable JSONL operational events with service id, level, event name, timestamp, message, and details so later agents can debug startup, health, dispatcher, and recorder behavior. | Added `systematic_trading.services.operational_log` and shared `var/log/platform_operations.jsonl`. Emitters now include `local_platform_supervisor`, `operator_dashboard`, `event_outbox_dispatcher`, and `market_data_recorder`; obvious secret fields are redacted. Recorder stop script now rewrites stopped state and logs stop/stale/no-PID cases. Smoke log wrote `dispatcher_started`, `dispatch_batch`, and `dispatcher_completed`. Evidence: full suite `169 passed`; focused observability suite `31 passed`; final focused suite `9 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings. |
| P6.0b | Done | Recorder/VPN/TWS incident triage and resilience hardening | Diagnose the one-day recorder run incident, document the VPN/TWS operational risk, and add local restart/health tooling so NATS, ClickHouse, and recorder failures are visible and recoverable. | Added `scripts/watch_local_platform.ps1`; watchdog writes `var/run/local_platform_watchdog.state.json` and `local_platform_watchdog` operation logs, checks NATS/Postgres/ClickHouse/operator/recorder state, and can repair required NATS/ClickHouse/operator services with `-Repair`. Added IB automation circuit breaker and alert dedupe to prevent repeated TWS logout/`nextValidId` storms. Hardened SOTA automation so non-SOTA IB account positions such as `DBB`/`USO` are filtered with warnings instead of breaking rebalance staging. Updated optional stopped-service health semantics. Updated README, service supervisor, live rollout, source plan, and `log.md`. Evidence: full suite `173 passed`; final `/health` overall `ok`; watchdog smoke required services `ok`; optional recorder `disabled`. |
| P6.1 | Pending | Metrics contract | Define service, data, queue, strategy, portfolio, execution, and reconciliation metrics. | Prometheus/OpenTelemetry compatible. |
| P6.2 | Pending | Local metrics endpoint | API/service exposes metrics for scraping or dashboard display. | Start with FastAPI endpoint if needed. |
| P6.3 | Pending | Grafana dashboard plan | Dashboard panels defined for data freshness, queue lag, broker state, PnL, exposure, and alerts. | Implementation depends on metrics path. |
| P6.4 | Done | Alert event producer | Automation alerts also emit `alert.raised` into platform outbox. | `AutomationAlertNotifier` accepts an event store and appends `AlertRaisedEvent`; default `TradingManagementService` passes its SQLite store; `tests/test_alerts.py`; full suite passed: 146 tests. |
| P6.5 | Pending | Desktop popup alert channel | Local machine popup for trading-critical warnings/errors. | Windows implementation required. |
| P6.6 | Pending | Incident registry | Alerts can open/update/resolve incidents with durable status. | Links to event ids. |
| P6.7 | Pending | Alert delivery audit | Track which channels received each alert and whether delivery failed. | Required before live. |
| P6.8 | Blocked | SMS/push provider | Requires provider choice and credentials. | Email exists; urgent channel pending. |

## P7: Daily Operating Loops

| ID | Status | Work Item | Acceptance Criteria | Evidence / Notes |
| --- | --- | --- | --- | --- |
| P7.1 | Pending | Daily post-trade report | Generate PnL, attribution, slippage, fills, reconciliation, and alert summary. | Uses `.agents/skills/daily-post-trade-analysis.md`. |
| P7.2 | Pending | Continuous research report | Daily/weekly challenger report updates research state and candidate status. | Uses `.agents/skills/continuous-research-loop.md`. |
| P7.3 | Pending | Robustness review report | Weekly service/data/queue/broker/alert health review. | Uses `.agents/skills/system-robustness-review.md`. |
| P7.4 | Pending | Promotion review report | Formal approve/reject/defer/retire artifact for strategy transitions. | Uses `.agents/skills/strategy-promotion-control.md`. |
| P7.5 | Pending | Automated Kanban reminder | Daily loop reports include open `In Progress`, `Blocked`, and high-priority `Pending` items. | Keeps execution tracker current. |
| P7.6 | Pending | Disaster recovery drill | Backup and restore check for trading-critical local state. | Required before live. |

## Next Recommended Work Order

1. Continue P3.4a with historical-smoke/daily recorder audits only; rerun IB streaming pilot after July 2026 live market-data subscriptions are enabled and confirmed.
2. Start P3.4: implement the normalized bar/quote pipeline after pilot raw-data quality is inspected.
3. Start P4.1: define the versioned strategy spec schema.
4. Start P6.1: define service, data, queue, strategy, portfolio, execution, and reconciliation metrics.
5. Start P5.1: define the stronger rebalance blotter domain model.
