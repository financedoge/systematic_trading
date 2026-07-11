# Postgres Transactional Store Design

Status: P2.4 target design; P2.9 initial runtime adapter implemented

Decision date: 2026-06-27

## Implementation Status

Implemented on 2026-07-11:

- Versioned migration runner: `scripts/apply_postgres_migrations.py`.
- Initial DDL migration: `deploy/postgres/migrations/001_initial_transactional_store.sql`.
- Runtime adapter: `systematic_trading.storage.postgres.PostgresStore`.
- Factory support: `ST_TRANSACTIONAL_STORE_BACKEND=postgres`.
- One-way SQLite transactional sync: `scripts/sync_sqlite_transactional_to_postgres.py`.
- Adapter smoke: `scripts/smoke_postgres_transactional_store.py`.

Current local runtime split:

- Postgres stores transactional and audit state: instruments, theses, proposals, approvals, broker order records, PnL snapshots, fundamental snapshots, and event outbox.
- ClickHouse stores serving market data: daily bars and FX rates.
- SQLite remains a legacy fallback and migration source only; it is not the recommended local operator runtime.

Verification from the 2026-07-11 migration session:

- Applied migration `001_initial_transactional_store`.
- Smoke test wrote and read proposal/order/PnL/fundamental/outbox state through `PostgresStore`, then cleaned up.
- Copied SQLite transactional state into Postgres: 39 instruments, 38 proposals, 7 approval decisions, 16 broker order records, 37 PnL snapshots, and 955 outbox events.
- Direct Postgres count check after sync: 39 instruments, 38 proposals, 7 approval decisions, 16 broker orders, 37 PnL snapshots, 955 outbox events, and 0 pending migrated outbox events.
- FastAPI smoke with `postgres + clickhouse`: `/health`, `/api/v1/proposals`, and `/api/v1/market-data/bars/SPY?start_date=2026-06-01&end_date=2026-06-01` returned HTTP 200; SPY close was `756.5908203125` with volume `43634900`.
- Test evidence: focused storage/script tests passed; full suite passed with 194 tests before the final startup-default doc/script adjustment; affected script/manifest/storage tests passed afterward.

## Local Runtime Smoke

Validated on 2026-06-27:

- Local Windows service: `postgresql-x64-18`.
- PostgreSQL version from installer registry: `18.4-2`.
- Base directory: `C:\Program Files\PostgreSQL\18`.
- Data directory: `C:\Program Files\PostgreSQL\18\data`.
- Service status: running, automatic startup.
- Listening socket: `127.0.0.1:5432` and `::`:5432.
- Tool path: `C:\Program Files\PostgreSQL\18\bin`.
- Readiness check: `pg_isready -h 127.0.0.1 -p 5432` returned accepting connections.
- Initial authenticated SQL check: blocked because no project Postgres password, `.env` DSN, or `pgpass.conf` was configured for this repository.
- Authenticated role smoke after local credentials were provided:
  - `st_app` connects to `systematic_trading`; database timezone is `UTC`.
  - Expected schemas exist: `core`, `strategy`, `portfolio`, `execution`, `ops`, and `events`.
  - `st_migrator` can `SET ROLE st_owner` and create DDL inside a rolled-back transaction.
  - `st_app` is denied schema DDL, as intended.
  - `st_readonly` connects to `systematic_trading`.
  - No project application tables are present yet; table creation should be handled by migration tooling rather than ad hoc setup.

Current runtime conclusion: Postgres is installed, reachable, and the project role/database/schema posture is valid. The next Postgres step is migration tooling and table creation from versioned migrations.

## Purpose

Postgres is the target transactional system of record for operator decisions, strategy promotion state, proposals, order lifecycle, fills, reconciliation, alerts, incidents, and the platform event outbox.

SQLite remains the local v0 store until P2.5 introduces a storage boundary and a controlled migration path.

## Design Principles

- Every state mutation that matters operationally must commit with its outbox event in the same transaction.
- JSON payloads are allowed for audit fidelity, but key query fields must be extracted into typed columns.
- All timestamps are `timestamptz` and stored in UTC.
- Money and quantities use exact numeric types, not floats.
- Idempotency keys are first-class unique constraints.
- Live routing must be blockable from database state as well as config.
- Schema changes are migration-managed and reversible where practical.

## Core Schemas

Use separate Postgres schemas to make ownership clear:

- `core`: instruments, reference entities, operators, config state.
- `strategy`: strategy definitions, versions, artifacts, promotion decisions.
- `portfolio`: proposals, targets, intended orders, approval decisions.
- `execution`: broker orders, order status history, fills, broker reconciliation.
- `ops`: alerts, incidents, service health snapshots.
- `events`: platform event outbox and publish audit.

## Core Tables

### `core.instruments`

Purpose: canonical instrument metadata used by proposals, execution, and reporting.

Columns:

- `symbol text primary key`
- `name text not null`
- `asset_class text not null`
- `exchange text not null`
- `quote_currency text not null`
- `country text not null`
- `sector text`
- `metadata jsonb not null default '{}'`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### `strategy.strategies`

Purpose: stable strategy identity.

Columns:

- `strategy_id text primary key`
- `name text not null`
- `owner text`
- `status text not null`
- `description text`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### `strategy.strategy_versions`

Purpose: immutable strategy version with spec and artifact links.

Columns:

- `strategy_version_id text primary key`
- `strategy_id text not null references strategy.strategies(strategy_id)`
- `version text not null`
- `spec jsonb not null`
- `spec_hash text not null`
- `created_at timestamptz not null default now()`
- `created_by text`
- `unique(strategy_id, version)`
- `unique(spec_hash)`

### `strategy.promotion_decisions`

Purpose: formal idea to research to paper to live state transitions.

Columns:

- `decision_id text primary key`
- `strategy_version_id text not null references strategy.strategy_versions(strategy_version_id)`
- `from_state text not null`
- `to_state text not null`
- `decision text not null`
- `decided_by text not null`
- `decided_at timestamptz not null`
- `evidence jsonb not null default '{}'`
- `comment text`
- `event_id text references events.platform_event_outbox(event_id)`

## Portfolio And Approval Tables

### `portfolio.proposals`

Purpose: rebalance proposal header and audit payload.

Columns:

- `proposal_id text primary key`
- `strategy_id text`
- `strategy_version_id text references strategy.strategy_versions(strategy_version_id)`
- `environment text not null`
- `sleeve text not null`
- `status text not null`
- `as_of date not null`
- `intended_trade_date date`
- `base_currency text not null`
- `summary text not null`
- `payload jsonb not null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Indexes:

- `(status, as_of desc)`
- `(strategy_version_id, as_of desc)`
- `(environment, intended_trade_date)`

### `portfolio.proposal_targets`

Purpose: queryable target weights and values.

Columns:

- `proposal_id text not null references portfolio.proposals(proposal_id)`
- `symbol text not null`
- `target_weight numeric(18, 10) not null`
- `target_value_cnh numeric(24, 6)`
- `payload jsonb not null`
- `primary key(proposal_id, symbol)`

### `portfolio.proposal_orders`

Purpose: intended order rows generated by a proposal.

Columns:

- `proposal_id text not null references portfolio.proposals(proposal_id)`
- `order_index integer not null`
- `local_order_id text not null`
- `symbol text not null`
- `side text not null`
- `order_type text not null`
- `quantity numeric(24, 8) not null`
- `reference_price numeric(24, 10) not null`
- `currency text not null`
- `notional_cnh numeric(24, 6)`
- `payload jsonb not null`
- `primary key(proposal_id, order_index)`
- `unique(local_order_id)`

### `portfolio.approval_decisions`

Purpose: human/operator decisions.

Columns:

- `approval_id bigserial primary key`
- `proposal_id text not null references portfolio.proposals(proposal_id)`
- `status text not null`
- `decided_at timestamptz not null`
- `decided_by text`
- `comment text`
- `payload jsonb not null`
- `event_id text references events.platform_event_outbox(event_id)`

Indexes:

- `(proposal_id, decided_at desc)`
- `(status, decided_at desc)`

## Execution Tables

### `execution.broker_orders`

Purpose: one row per local broker order identity.

Columns:

- `local_order_id text primary key`
- `proposal_id text not null references portfolio.proposals(proposal_id)`
- `order_index integer not null`
- `environment text not null`
- `broker text not null`
- `broker_order_id bigint`
- `order_ref text not null`
- `symbol text not null`
- `side text not null`
- `order_type text not null`
- `quantity numeric(24, 8) not null`
- `status text not null`
- `submitted_at timestamptz`
- `updated_at timestamptz not null`
- `filled_quantity numeric(24, 8) not null default 0`
- `remaining_quantity numeric(24, 8)`
- `average_fill_price numeric(24, 10)`
- `message text`
- `payload jsonb not null`
- `unique(environment, broker, broker_order_id)`
- `unique(environment, order_ref)`
- `unique(proposal_id, order_index, order_ref)`

### `execution.broker_order_status_history`

Purpose: append-only lifecycle audit.

Columns:

- `status_event_id text primary key`
- `local_order_id text not null references execution.broker_orders(local_order_id)`
- `status text not null`
- `broker_order_id bigint`
- `message text`
- `observed_at timestamptz not null`
- `payload jsonb not null`
- `event_id text references events.platform_event_outbox(event_id)`

### `execution.fills`

Purpose: broker fills normalized for PnL, reconciliation, and slippage.

Columns:

- `fill_id text primary key`
- `local_order_id text references execution.broker_orders(local_order_id)`
- `proposal_id text references portfolio.proposals(proposal_id)`
- `environment text not null`
- `broker text not null`
- `broker_order_id bigint`
- `order_ref text`
- `symbol text not null`
- `side text not null`
- `quantity numeric(24, 8) not null`
- `average_price numeric(24, 10) not null`
- `currency text not null`
- `filled_at timestamptz not null`
- `commission numeric(24, 10)`
- `commission_currency text`
- `payload jsonb not null`
- `event_id text references events.platform_event_outbox(event_id)`

Indexes:

- `(symbol, filled_at desc)`
- `(proposal_id, filled_at desc)`
- `(environment, broker_order_id)`

### `execution.reconciliation_runs`

Purpose: durable broker/local reconciliation result.

Columns:

- `reconciliation_id text primary key`
- `environment text not null`
- `broker text not null`
- `scope text not null`
- `status text not null`
- `reconciled_at timestamptz not null`
- `checked_counts jsonb not null default '{}'`
- `breaks jsonb not null default '[]'`
- `message text`
- `payload jsonb not null`
- `event_id text references events.platform_event_outbox(event_id)`

## Alert And Incident Tables

### `ops.alerts`

Purpose: alert registry independent of delivery channels.

Columns:

- `alert_id text primary key`
- `severity text not null`
- `category text not null`
- `message text not null`
- `details jsonb not null default '{}'`
- `raised_at timestamptz not null`
- `source_service text not null`
- `status text not null default 'raised'`
- `event_id text references events.platform_event_outbox(event_id)`

Indexes:

- `(status, severity, raised_at desc)`
- `(category, raised_at desc)`

### `ops.alert_deliveries`

Purpose: channel delivery audit.

Columns:

- `delivery_id text primary key`
- `alert_id text not null references ops.alerts(alert_id)`
- `channel text not null`
- `target text`
- `status text not null`
- `attempted_at timestamptz not null`
- `delivered_at timestamptz`
- `error text`
- `payload jsonb not null default '{}'`

### `ops.incidents`

Purpose: operator-visible incident lifecycle.

Columns:

- `incident_id text primary key`
- `status text not null`
- `severity text not null`
- `summary text not null`
- `details jsonb not null default '{}'`
- `opened_at timestamptz not null`
- `updated_at timestamptz not null`
- `resolved_at timestamptz`
- `event_id text references events.platform_event_outbox(event_id)`

## Event Outbox

### `events.platform_event_outbox`

Purpose: transactional outbox for all platform events.

Columns:

- `event_id text primary key`
- `event_type text not null`
- `schema_version integer not null`
- `subject text not null`
- `payload jsonb not null`
- `occurred_at timestamptz not null`
- `created_at timestamptz not null default now()`
- `published_at timestamptz`
- `publish_attempts integer not null default 0`
- `last_error text`
- `locked_by text`
- `locked_at timestamptz`

Indexes:

- `(published_at, created_at, event_id)` for pending dispatch.
- `(event_type, occurred_at desc)` for audit.
- `(subject, created_at desc)` for queue diagnostics.

Dispatch query should use `FOR UPDATE SKIP LOCKED` so multiple dispatchers can safely share work later.

## Transaction Boundaries

Required same-transaction writes:

- Proposal save: proposal rows, target/order rows, `proposal.created` event.
- Approval decision: proposal status update, approval row, `proposal.decision_recorded` event.
- Broker order update: broker order row, status history row, `order.status_changed` event.
- Fill save: broker order fill fields, fill row, `fill.recorded` event.
- Alert raise: alert row, `alert.raised` event.
- Incident update: incident row, `incident.recorded` event.
- Promotion decision: promotion row, `promotion` event once the event contract exists.

## Migration Plan

1. Completed: add a storage/repository boundary in P2.5 while SQLite remains the only implementation.
2. Add Alembic or equivalent migration tooling for Postgres.
3. Create Postgres schema from this design.
4. Build a one-way SQLite to Postgres backfill script.
5. Validate row counts, primary ids, event ids, and payload hashes between stores.
6. Run shadow writes in paper mode: SQLite remains primary, Postgres receives mirrored writes.
7. Run shadow reads for dashboards and reports and compare responses.
8. Switch paper trading primary store to Postgres behind a config flag.
9. Keep SQLite read-only fallback until at least 20 clean paper trading sessions.
10. Only consider live trading after Postgres backup/restore, monitoring, and failover drills pass.

## Operational Requirements

- Backups: daily logical dump plus WAL archiving once live-like paper trading starts.
- Retention: event outbox and order/fill history are long-retention audit data.
- Monitoring: connection count, transaction latency, lock waits, deadlocks, replication lag if any, outbox backlog, and storage growth.
- Security: no broker credentials in payload JSON; secrets stay in environment or secret manager.
- Recovery: restore drill must prove proposals, approvals, order records, fills, outbox, alerts, and incidents survive.

## Open Decisions

- Exact migration tool: Alembic is the likely default for Python, but P2.5 should confirm.
- Project Postgres access: local PostgreSQL 18 is installed and reachable, but a project role/database/DSN is not configured yet.
- ClickHouse runtime path: P2.8 remains blocked until the columnar runtime path is selected and validated.
- Promotion event type: strategy promotion events need a formal event contract in P4.
