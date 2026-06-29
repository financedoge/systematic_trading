# Service Supervisor Plan

This is the Windows-first operating plan for local 24x7 service supervision. It covers the current operator stack and defines the conventions future services must follow.

The machine-readable manifest is `config/service-manifest.json`.

## Current Local Stack

| Service | Status | Supervisor | PID | Logs | Health |
| --- | --- | --- | --- | --- | --- |
| Operator dashboard API | Active | `scripts/start_operator_dashboard.ps1` | `var/run/operator_dashboard.pid` | `var/log/operator_dashboard.*.log` | `GET /health` |
| Event outbox dispatcher | Active | `scripts/start_operator_dashboard.ps1` | `var/run/event_outbox_dispatcher.pid` | `var/log/event_outbox_dispatcher.*.log` | `var/run/event_outbox_dispatcher.state.json` |
| Trading management loop | Active embedded worker | FastAPI process | Parent dashboard PID | Dashboard/API logs and state file | `var/live/trading_management_service_state.json` |
| NATS JetStream | Active | `scripts/start_nats_jetstream.ps1` | Docker Compose | Docker logs | `http://127.0.0.1:8222/healthz?js-enabled-only=true` |
| Postgres transactional store | Active external service | Windows service | External | PostgreSQL logs | TCP `127.0.0.1:5432` |
| ClickHouse columnar store | Active | `scripts/start_clickhouse.ps1` | Docker Compose | Docker logs plus `D:/systematic_trading_data/clickhouse/logs` | `http://127.0.0.1:8123/ping` |
| Market data recorder | Active optional | Manual script/service | `var/run/market_data_recorder.pid` | `var/log/market_data_recorder.*.log` | `var/run/market_data_recorder.state.json` and freshness metrics |
| Local platform watchdog | Active operator script | Manual now; Windows Task Scheduler later | `var/run/local_platform_watchdog.state.json` | `var/log/platform_operations.jsonl` | Checks NATS, Postgres, ClickHouse, operator API, and optional recorder state |

The recorder implementation follows `docs/market-data-recorder-contract.md` and the source/capacity plan in `docs/market-data-recorder-source-plan.md`. The initial P3.2 entry point is `scripts/record_ib_market_data.py`; use `--mode realtime` for session recording and `--mode historical-smoke` for bounded closed-market tests.

## Rules

- Every long-running process gets a PID file under `var/run/`.
- Every long-running process writes stdout and stderr under `var/log/`.
- Every operationally important lifecycle event writes a structured JSONL record to `var/log/platform_operations.jsonl`.
- Every service is declared in `config/service-manifest.json`.
- Every long-running service health report must include `service_id`, `running`, `heartbeat_at`, and `last_error`.
- Start scripts must remove stale PID files only after verifying the process is absent.
- Stop scripts must stop all child/companion services they start.
- Services must be safe to restart without duplicating broker orders or market data.
- Live trading services remain disabled until the live rollout checklist is complete.

## Startup Order

Recommended local startup:

```powershell
.\scripts\start_local_platform.ps1
```

This starts NATS JetStream, configures the `ST_EVENTS` stream, verifies Postgres readiness, starts ClickHouse, then starts the operator dashboard and event outbox dispatcher. The dispatcher publishes to NATS by default. The platform health portal is served at `http://127.0.0.1:8000/platform`.

The market-data recorder is deliberately opt-in because raw high-frequency data can fill disks:

```powershell
.\scripts\start_local_platform.ps1 -StartMarketDataRecorder
```

Recorder pilots default to `-RecorderMarketDataMode delayed` because IB paper accounts can connect successfully while still lacking live exchange market-data permissions. Use `-RecorderMarketDataMode live` only after the required subscriptions are enabled.

Startup order:

1. NATS JetStream event bus.
2. Postgres transactional store readiness check.
3. ClickHouse columnar store.
4. Operator dashboard API.
5. Event outbox dispatcher.
6. Embedded trading management loop inside the dashboard API.
7. Optional market data recorder pilot.

The dashboard is health-gated before startup is considered successful. The outbox dispatcher is started as a companion process and can be disabled for debugging with:

```powershell
.\scripts\start_operator_dashboard.ps1 -DisableEventDispatcher
```

For a standalone local-file event test, use:

```powershell
.\scripts\start_operator_dashboard.ps1 -EventPublisher jsonl
```

## Watchdog And Network Recovery

The local stack must not depend on an external VPN for localhost infrastructure. The 2026-06-29 incident showed that VPN or network-adapter changes can disrupt Docker Desktop networking and can leave NATS or ClickHouse absent even though Docker Desktop itself is still running.

Check the current local platform state:

```powershell
.\scripts\watch_local_platform.ps1
```

Attempt repair of required local services:

```powershell
.\scripts\watch_local_platform.ps1 -Repair
```

The repair path may recreate NATS JetStream and ClickHouse through their Docker Compose files, reconfigure the `ST_EVENTS` stream, and restart the operator dashboard if its health endpoint is unavailable. It does not auto-start the market-data recorder because recorder startup consumes disk space, broker data lines, and IB session capacity.

If TWS or IB Gateway logs out, the platform must not spin indefinitely. The trading management loop now opens an IB automation circuit breaker after repeated IB failures, backs off recurring execution/account-snapshot retries, records the circuit state in `var/live/trading_management_service_state.json`, and requires a human relogin before IB-dependent work can become healthy again.

## Stop Order

1. Optional market data recorder.
2. Event outbox dispatcher.
3. Operator dashboard API.
4. ClickHouse and NATS when using the full local platform script.

The stop script removes PID files only after the target process exits or is confirmed absent.

Recommended local stop:

```powershell
.\scripts\stop_local_platform.ps1
```

Postgres is not stopped by the platform stop script because it is managed as an external Windows service.

## Restart Policy

Current local policy is manual restart. This is deliberate while service contracts are still changing.

Use the watchdog as the first local recovery command after VPN, Wi-Fi, Docker Desktop, or TWS disruptions. For true 24x7 operation, migrate NATS, ClickHouse, and IB Gateway to a supervised server or native service path; Docker Desktop plus an idle-sensitive VPN is not a production-grade dependency chain.

The service manifest driven health check reports:

- Running or stopped.
- PID file present or stale.
- Health endpoint response.
- Heartbeat age.
- Last log update time.
- Last error line.
- Event outbox backlog.

## Operational Logs

Structured operational logs are written to:

```text
var/log/platform_operations.jsonl
```

Each row includes:

- `occurred_at`
- `service_id`
- `level`
- `event`
- `message`
- `details`

Current emitters:

- `local_platform_supervisor`: platform startup sequence, dependency checks, recorder opt-in decisions, and startup failures.
- `local_platform_watchdog`: local health checks, required-service repair attempts, and watchdog summary state.
- `operator_dashboard`: API lifespan and embedded automation loop start/stop.
- `event_outbox_dispatcher`: dispatcher start, dispatch batches with activity, failures, periodic heartbeats, and stop/interruption.
- `market_data_recorder`: run lifecycle, IB market-data mode callbacks, subscriptions, pacing sleeps, first/periodic bar writes, source errors, and disconnects.

The writer redacts obvious secret fields such as passwords, tokens, credentials, and API keys. Do not log broker credentials, account passwords, API tokens, or raw secret-bearing environment variables.

The operator API exposes the normalized platform health contract at `GET /health`. The endpoint returns HTTP 200 for API liveness and uses the response `status` plus per-service records to show `ok`, `degraded`, `error`, `planned`, `disabled`, or `unknown`.

## Server Path

When the stack moves to a server, keep the same service ids and manifest fields. Replace the Windows PowerShell supervisor with systemd, Docker Compose, or another explicit process manager only after the manifest contract is stable.
