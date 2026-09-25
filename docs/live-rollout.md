# Live Rollout

## Rebalance Execution Window

- Monthly signals are calculated from the decision-date close and scheduled orders target the next session open. Empty-account allocation and drift maintenance may propose a current-session TWAP using completed daily data and active targets; see [trading operations](trading-operations.md#initial-allocation-and-drift-monitoring).
- `ST_EXECUTION_REBALANCE_TIMEOUT_MINUTES` controls how long after `ST_EXECUTION_TWAP_START_TIME` approval or retry remains allowed; default is 30 minutes in `ST_AUTOMATION_TIMEZONE`.
- Pending proposals and approved proposals with failed or missing broker orders become `missed` after the deadline.
- Orders already accepted by the broker remain active and are not falsely expired.
- Missed orders are durable audit records. They cannot be resubmitted and their count/reference notional appear in execution-quality analysis; no synthetic fill price or invented slippage PnL is created.

## Policy

Live trading is disabled until the platform proves paper trading reliability through service health checks, market-data recording, pre-trade validation, order idempotency, broker reconciliation, post-trade reporting, alerting, and rollback drills.

The target rollout path is defined in `docs/industrial-platform-plan.md`. This document tracks the current IB paper-to-live implementation path.

## Paper-first stages

1. Proposal preview only: no orders leave the system.
2. Paper routing: manual approval by default, or explicitly enabled automatic approval for new current-strategy paper TWAP proposals under the operator's batch cap. See [approval mode](trading-operations.md#automatic-paper-approval).
3. Shadow live review: proposals are compared against paper fills and manual expectations.
4. Live enablement: capital caps, stronger validations, and rollback procedures are in place.

## Promotion Gates

- A strategy must be registered with versioned data, feature, universe, risk, and artifact metadata before paper trading.
- A paper strategy must run long enough to validate order routing, fills, cash, positions, slippage, and reconciliation.
- A live strategy must have explicit capital caps, kill-switch conditions, alert coverage, and a rollback plan.
- No live route is allowed from an unapproved proposal, stale market data, unresolved broker mismatch, or missing operator approval.

## Safeguards

- Separate paper and live environments.
- Persisted approval before submission: manual, or the explicitly enabled paper-only policy. Existing proposals and uncertain attempts are never released/retried automatically.
- Buying-power, duplicate-order, and stale-price checks.
- Local reconciliation of positions, orders, and cash balances against broker state.
- Durable local storage for proposal, approval, and broker order history before and after broker routing.
- Live remains disabled until paper trading is stable for an extended period.
- Idempotent order submission so retries cannot create duplicate exposure.
- Persistent incident logging for every alert that affects trading or data quality.

## v1 order assumptions

- Stocks and ETFs only.
- Long-only.
- Daily monitoring.
- Limit, market, and open-oriented workflows only.

## Minimum Live Checklist

- IB account, port, client id, and environment are verified against the intended live profile.
- Latest market data, FX, corporate actions, and account snapshot are fresh.
- Broker open orders, positions, cash, fills, and commissions reconcile to local state.
- Rebalance blotter shows current, target, proposed, expected cash, fees, residuals, and risk limits.
- Alerts are active through email plus one urgent channel such as SMS, push, or desktop popup.
- Kill switch and rollback procedure were tested in paper mode.
- Operator has approved the exact strategy version, proposal id, and capital cap.

## SOTA Nightly Job

The first live bridge separates proposal generation from broker submission:

1. Backfill/validate latest adjusted ETF prices and USD/CNH FX after the market close.
2. Run `scripts/run_sota_live_rebalance.py` with an account snapshot JSON.
3. Review the generated markdown report and queued proposal.
4. Approve the proposal only after price, FX, position, cash, and open-order checks pass.
5. The operator dashboard immediately routes approved proposals as TWAP paper orders.

Example:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_sota_live_rebalance.py `
  --account-snapshot var\live\account_snapshot.paper.json `
  --as-of 2026-04-29 `
  --intended-trade-date 2026-04-30 `
  --queue
```

Account snapshot shape:

```json
{
  "as_of": "2026-04-29",
  "cash": [{"currency": "CNH", "amount": "1000000"}],
  "positions": [
    {"symbol": "SPY", "quantity": 10, "average_cost": "500"}
  ]
}
```

The proposal job writes JSON and markdown artifacts under `var/live/sota_rebalance/` and can persist the proposal to the existing approval queue. In the dashboard, approval is the one-click handoff to TWAP paper routing via `POST /api/v1/proposals/{proposal_id}/approve-and-submit`; the standalone submit API/CLI still exists for retries and controlled operational use.

Automatic staging follows the registered `static_monthly` scheduler: generate the proposal after the final US market session of the month for execution in the next month's first session. Daily market-data refresh, reconciliation and PnL reporting still run on intervening sessions. Unsupported scheduler names stop automatic staging rather than defaulting to daily trading. Manual API/CLI proposal generation remains an explicit operator action. Default execution dates in both live plans and API routing use the shared US holiday calendar.

The automated after-close workflow refreshes Yahoo adjusted daily bars first and then falls back to the configured Interactive Brokers paper connection for missing or failed equity/ETF daily-bar updates. Use separate client IDs for each automated IB operation so a stuck request does not block the other clients:

```powershell
ST_IB_MARKET_DATA_CLIENT_ID=121
ST_IB_EXECUTION_SYNC_CLIENT_ID=131
ST_IB_ACCOUNT_SNAPSHOT_CLIENT_ID=141
```

If Yahoo and IB cannot supply current observations, EOD processing and proposal staging remain blocked and the service reports the missing data. Synthetic bars and FX rates are never written to the trading store. The legacy carry-forward settings are still accepted for configuration compatibility, but enabling them only adds a warning; the day limit no longer authorizes synthetic writes:

```powershell
ST_AUTOMATION_MARKET_DATA_CARRY_FORWARD=false
ST_AUTOMATION_MARKET_DATA_CARRY_FORWARD_MAX_CALENDAR_DAYS=4
```

Existing zero-volume daily bars are treated as suspect and retried through the refresh path. Older synthetic FX rows have no provenance in the legacy contract and require an explicit provider backfill before relying on historical results; this code change does not rewrite stored history.

All submission entry points, including the CLI, require a successful paper reconciliation no more than 180 seconds old. The CLI uses the configured trading-store factory. Order intents are reserved atomically in SQLite/Postgres before placement. A timeout or unclassified client error retains `pending_submit`; it is an uncertain outcome, is not automatically expired as missed, and cannot be overridden with `--allow-resubmit`. Investigate the broker order/fill state before resolving it. Only an explicit rejection or cancellation with no fills is retryable. Generic IB error responses are treated conservatively as uncertain unless the client establishes a definitive rejection.

PnL collapse advances the existing baseline, retaining broker-reset holdings and applying only subsequent fills. A cutoff earlier than the active baseline is rejected. Backtests use decision-date holdings marks and FX for sizing, and execution-date prices/FX only for fills and valuation. Previously generated backtest artifacts are not regenerated or promoted by this repair.

Broker records now retain individual executions in their existing JSON payloads. SQLite immediate transactions and Postgres row locks commit execution evidence, cumulative order quantities and outbox events together; no database schema migration is needed. Short history windows and duplicate responses do not remove or recount executions. Matching requires the local order reference; numeric IB order IDs alone are insufficient. Execution prices come from the individual `price` field, with broker cumulative quantities checked for gaps/overlaps. PnL and reconciliation use individual execution times across baseline cutoffs. Reconciliation still compares broker positions when old executions fall outside the broker query window.

Legacy aggregate records can adopt full execution history only when broker cumulative quantities establish complete coverage without reducing the prior filled amount. Incomplete legacy history, missing identities, conflicting replays, corrections, overfills and account changes create a persistent execution-history issue. These issues block routing and PnL collapse and are not cleared by a later empty response or account reset. Active paper histories can be repaired with the reviewed recovery command below. Automatic correction application, zero-fill bust recovery and corrections affecting saved baselines remain unsupported. Controlled IB paper-session validation remains required before deployment.

### Reviewed execution recovery

`scripts/recover_ib_paper_executions.py` uses the configured transactional backend and never connects to IB or submits orders. It requires a complete, operator-verified broker execution export for one local paper order. Preview is read-only and does not initialize a database. Apply requires the preview token, which binds the exact order, request metadata, execution evidence and current PnL baseline. Concurrent changes invalidate the token.

Prepare an evidence JSON file with this shape, replacing every example value with verified broker data. Include the complete effective execution history, selecting only the latest accepted correction per execution family:

```json
{
  "local_order_id": "replace-with-local-order-id",
  "operator": "operator-name",
  "reason": "Broker export reviewed against the execution correction",
  "account": "DU123",
  "fills": [{
    "execution_id": "broker-execution.02",
    "account": "DU123",
    "broker_order_id": 100,
    "order_ref": "st-proposal-00",
    "symbol": "SPY",
    "side": "buy",
    "quantity": 4,
    "average_price": "101.25",
    "cumulative_quantity": 4,
    "currency": "USD",
    "filled_at": "2026-08-03T15:00:00Z"
  }]
}
```

Here `average_price` is the individual execution's broker `price`, not the order-wide average. Preview, review the quantities/prices/IDs, then apply the unchanged request using its token:

```powershell
.\.venv\Scripts\python.exe scripts/recover_ib_paper_executions.py --evidence reviewed-executions.json
.\.venv\Scripts\python.exe scripts/recover_ib_paper_executions.py --evidence reviewed-executions.json --apply --review-token <preview-token>
```

An existing SQLite file can be selected with `--database` when SQLite is configured. The command refuses account changes, missing executions, conflicting reuse of an execution ID, older correction revisions, incomplete cumulative quantities, future/naive timestamps, overfills, live orders and evidence at or before the active PnL baseline. A historical baseline rebuild requires a separate reviewed workflow; the command does not rewrite baselines or snapshots.

The recovery and its before/after evidence, operator, reason and review token are saved atomically with the order and outbox. Superseded broker revisions remain in the audit and can be replayed without undoing the approved correction. Generic stale order updates cannot erase the audit or restore a cleared issue. A successful reconciliation whose check started after recovery is mandatory before routing. Rebuild any PnL calculation that was in flight during recovery: baseline commits check both the execution-state token and the parent baseline. SQLite write transactions and a shared Postgres transaction advisory lock serialize these operations.

Run the real Postgres concurrency and rollback tests against a disposable cluster by setting `ST_TEST_POSTGRES_BIN` to a local Postgres `bin` directory and running `tests/test_execution_recovery.py`. The fixture creates a password-protected cluster on a temporary loopback port, applies the schema only there and stops it afterward. Without that setting, Postgres cases are skipped; SQLite cases still run.

The correction identity rule follows the [IB execution contract](https://www.interactivebrokers.com/docs/tws-api/ref/execution): a changed numeric suffix after the final period denotes a correction, not an additional fill.

Backtests and live order routing use the same execution timing convention: signals are decided after the decision-date close, order quantities are sized from the decision close, and fills are modeled/routed in the next trading session's opening TWAP window. Daily-bar backtests use the next session open as the available proxy for a 30-minute open-window TWAP. Live IB TWAP orders use:

```powershell
ST_EXECUTION_TWAP_START_TIME=09:30
ST_EXECUTION_TWAP_END_TIME=10:00
```

On startup and every automation loop, the service derives a durable EOD replay backlog from the last completed EOD date through the latest eligible after-close New York business date. Missing dates are processed oldest-first until caught up: execution fills are synced, market data is refreshed into the configured store, account snapshots are refreshed or recovered from same-day files, EOD PnL snapshots are saved, and SOTA rebalance proposals are staged only on scheduled monthly decision dates.

Automation warnings and errors are written immediately to `var/log/automation_alerts.jsonl`. Configure SMTP to send the same alerts by email:

```powershell
ST_AUTOMATION_ALERT_SMTP_HOST=smtp.example.com
ST_AUTOMATION_ALERT_SMTP_PORT=587
ST_AUTOMATION_ALERT_SMTP_USERNAME=alerts@example.com
ST_AUTOMATION_ALERT_SMTP_PASSWORD=...
ST_AUTOMATION_ALERT_EMAIL_FROM=alerts@example.com
ST_AUTOMATION_ALERT_EMAIL_TO=operator@example.com
```

## Operator Dashboard

Start the recommended local platform stack:

```powershell
.\scripts\start_local_platform.ps1
```

Open `http://127.0.0.1:8000/platform` for service health and the service connection chart.

Start only the local operator stack:

```powershell
.\scripts\start_operator_dashboard.ps1
```

Open `http://127.0.0.1:8000/operator`.

The start script also runs the event outbox dispatcher in loop mode unless disabled. In the recommended path the dispatcher publishes to NATS JetStream; for isolated local-file dispatch use `-EventPublisher jsonl`. The dispatcher has separate PID and log files:

```powershell
.\scripts\start_operator_dashboard.ps1 -DisableEventDispatcher
```

Stop it:

```powershell
.\scripts\stop_local_platform.ps1
```

The dashboard lists proposals, shows target/order details, approves or rejects queued proposals, submits approved proposals as TWAP paper orders, exposes a resubmit button only for failed or missing broker records, and shows persisted broker order records. Keep this service bound to localhost until authentication and network controls are added.

CLI dry-run for an approved proposal:

```powershell
.\.venv\Scripts\python.exe .\scripts\submit_ib_paper_orders.py `
  --proposal-id <proposal_id>
```

CLI submit to IB paper:

```powershell
.\.venv\Scripts\python.exe .\scripts\submit_ib_paper_orders.py `
  --proposal-id <proposal_id> `
  --confirm-submit
```

The API equivalent is `POST /api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit`. Use `confirm_submit=false` for validation and `confirm_submit=true` for actual paper routing.

## IB Paper Connection Plan

Install the optional IB dependency before real paper routing:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[ib]"
```

Official IBKR TWS API notes that matter for this rollout:

- TWS must be configured to accept socket clients before an API client can connect.
- Default TWS ports are `7497` for paper and `7496` for live, but the client and TWS settings must match.
- TWS read-only API mode prevents API orders.
- A client should wait for `nextValidId` before sending requests.
- `placeOrder` returns order lifecycle callbacks such as `openOrder` and `orderStatus`.

Implementation stages:

1. Implemented: translate approved `OrderRequest` objects into IB stock/ETF contracts and orders using SMART routing; attach a stable `orderRef` containing the local proposal id.
2. Implemented: require explicit approval, block live routing, reject duplicate submissions by default, and persist local broker order records.
3. Implemented initial monitoring: `scripts/probe_ib_tws_health.py` checks TWS/Gateway paper API connectivity by waiting for `nextValidId`, captures managed accounts/server time when available, and writes `var/run/ib_tws_api.state.json` for the platform health page.
4. Implemented broker-authoritative portfolio reconciliation: the management loop and Trading page fetch IB positions, cash, and executions, persist timestamped/latest reports under `var/reconciliation`, raise a durable alert on breaks, and block EOD PnL, rebalance staging, and IB routing until matched. `Reset local to IB` requires trader confirmation and creates a broker-derived PnL baseline while retaining historical orders/fills.
5. Next: capture broker open orders and commissions in the same persisted reconciliation contract.
6. Later: live switch with explicit config, separate port/account check, capital caps, and a fresh dry-run report before live routing is enabled.

References:

- IBKR TWS API documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/
- TWS API initial setup: https://interactivebrokers.github.io/tws-api/initial_setup.html
- TWS API order submission: https://interactivebrokers.github.io/tws-api/order_submission.html

## IB Session Robustness

TWS is acceptable for interactive local paper testing, but it is not a production-grade unattended dependency on this workstation. The 2026-06-29 incident showed that VPN/network instability plus a TWS logout can leave API clients timing out on `nextValidId` and account-summary requests until the operator manually logs in again.

Current controls:

- Recurring automation opens an IB circuit breaker after repeated IB failures, backs off execution/account-snapshot retries, and exposes the circuit state through automation status and platform health details.
- The platform health page includes `ib_tws_api`; startup and watchdog runs refresh `var/run/ib_tws_api.state.json`.
- TWS down or not logged in is an operator-visible health error, not a silent recorder/execution failure.
- Reconciliation after a paper-account reset is report-first. Local broker order records remain audit history; a broker-authoritative PnL baseline can only be written by the explicit Trading-page confirmation or `--record-pnl-reset-baseline --confirm-paper-reset`.
- The platform does not attempt to automate TWS login or 2FA recovery.
- After any TWS relogin, run `scripts/test_ib_paper_connection.py` before restarting IB-dependent recorder or paper-execution work.
- For server or 24x7 operation, prefer IB Gateway under an explicit process supervisor and keep VPN dependency out of the critical network path.
