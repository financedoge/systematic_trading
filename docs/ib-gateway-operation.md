# One IB Gateway for the local platform

The operator API, order router, execution synchronizer, account snapshots, reconciliation and market-data clients all use `InteractiveBrokersAdapter` connection profiles. One authenticated paper Gateway can serve these API clients; they do not each need a separate IB login.

## Local configuration

Set in the machine's ignored `.env`:

```dotenv
ST_DEFAULT_ENVIRONMENT=paper
ST_IB_HOST=127.0.0.1
ST_IB_PAPER_PORT=4002
ST_IB_LIVE_PORT=4001
ST_IB_CLIENT_ID=101
ST_IB_MARKET_DATA_CLIENT_ID=121
ST_IB_EXECUTION_SYNC_CLIENT_ID=131
ST_IB_ACCOUNT_SNAPSHOT_CLIENT_ID=141
ST_IB_HEALTH_CLIENT_ID=151
ST_IB_RECONCILIATION_CLIENT_ID=161
ST_MARKET_DATA_STORAGE_POLICY_PATH=D:/systematic_trading_runtime/market-data/storage-policy.json
```

The live profile remains disabled in code. A configured live port does not enable live trading. Defaults in `AppSettings` retain TWS compatibility; the machine-local override selects Gateway.

| Client | ID | Purpose |
| --- | ---: | --- |
| Order router | 101 | Approved paper orders only |
| Recorder / market-data adapter | 121 | Market data; avoid concurrent ad hoc requests on the same ID |
| Execution sync | 131 | Broker fill retrieval |
| Account snapshot | 141 | Cash and positions |
| Health | 151 | API readiness |
| Reconciliation | 161 | Broker/local consistency |
| FX history | 181 | Observed CNH midpoint closes; configurable via `ST_IB_FX_CLIENT_ID` |

Use a separate unused client ID for manual probes. Do not operate a second TWS/Gateway session with the same username. Configure daily Auto Restart and complete the weekly authentication. API client IDs distinguish connections inside one login; they do not grant separate market-data subscriptions or independent account state.

The receiving PC's local policy uses `D:/systematic_trading_runtime/market-data/hot` for raw writes. The recorder, catalog/replay CLIs and audit API now honor the same `ST_MARKET_DATA_STORAGE_POLICY_PATH`; an explicit CLI `--storage-policy` still takes precedence. Keep the policy file local to each PC and configure existing writable disks. The NAS path in that policy is only a destination: PostgreSQL/SQLite snapshots do not back up raw intraday files.

## Startup and validation

Use the normal `scripts/stop_local_platform.ps1 -KeepInfrastructure` and `scripts/start_local_platform.ps1` for a coordinated restart. The `ib_tws_api` state/service identifier and probe filename are retained for compatibility and cover both TWS and Gateway.

```powershell
.\.venv\Scripts\python.exe scripts/probe_ib_tws_health.py
.\.venv\Scripts\python.exe scripts/test_ib_paper_connection.py
.\.venv\Scripts\python.exe scripts/reconcile_ib_paper_account.py
```

The connection smoke only connects/disconnects; it does not place an order. Reconciliation reports must be checked for breaks. Do not reset the PnL baseline or erase historical fills to make a report pass.

For a bounded recorder check, use a separate state/PID file and unused client ID. Historical bars verify connectivity/storage but do not prove continuous streaming. A stream canary must show advancing exchange timestamps, raw/catalog records and matching payload hashes. The five-symbol delayed pilot is testing data, not an approved realtime decision feed. Its scheduled service records US regular sessions and idles outside them.

IB warning 2176 means an older API client received rounded fractional volume. The recorder retains the warning and marks subsequent bars for that request `ib_fractional_volume_rounded`, while allowing collection to continue. Other request failures still terminate/degrade the request. The receiving PC now uses official IB API 10.45.1; a fractional-volume storage contract remains follow-up work, and historical rounded bars must not be represented as exact fractional-volume data.

Install the pinned official SDK before starting broker-connected services on another PC:

```powershell
.\.venv\Scripts\python.exe scripts/install_ib_api.py
```

The installer checks the official archive SHA-256 and installs IB API 10.45.1 with its pinned protobuf dependency. Local SDK files remain ignored under `var/dependencies/`. PyPI's old 9.81 API negotiates version 157, which Gateway rejects for these FX historical requests with error 10285. Error callback adapters handle the new timestamp argument, and cancellation supplies the current SDK's `OrderCancel` object. See the [official download](https://interactivebrokers.github.io/) and [IB error codes](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes).

No validation order was sent during cutover. If Gateway's **Read-Only API** remains enabled from the recorder setup, it will block even approved paper orders; review that setting before the first operator-approved paper trade. Do not disable order precautions or reconciliation checks as part of this migration.

## Cutover evidence and remaining checks

On September 25, 2026, the paper order connection and health probes passed on port 4002, account snapshots succeeded, and broker reconciliation matched. Historical capture returned 60 bars across five symbols; a subsequent 45-second delayed stream returned 16 new bars. SPY replay validated all 16 stored records with no invalid records, duplicates or hash mismatches. The full test suite passed (365 passed, 1 skipped).

The later September 25 FX repair completed September 24 EOD PnL and restored proposal readiness. The loop refreshes currencies actually present in broker cash, using observed IB USD/CNH and same-date USD crosses (HKD/CNH = USD/CNH ÷ USD/HKD). Evidence is written before normalized rates under `var/market_data/fx_observations/`. Future bars and incomplete FX daily closes are excluded. The old Yahoo CNY-to-CNH substitution is no longer used for operational FX refresh; earlier stored history is unchanged and needs a separate provenance audit. Routine EOD refresh no longer repeatedly repairs years of old synthetic bars; explicit historical data repair remains available. Gateway restart/reconnect soak and an operator-approved paper order remain untested.
