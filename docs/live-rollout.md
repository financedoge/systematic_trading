# Live Rollout

## Paper-first stages

1. Proposal preview only: no orders leave the system.
2. Paper routing: manually approved paper orders are sent to IB paper.
3. Shadow live review: proposals are compared against paper fills and manual expectations.
4. Live enablement: capital caps, stronger validations, and rollback procedures are in place.

## Safeguards

- Separate paper and live environments.
- Explicit approval before order submission.
- Buying-power, duplicate-order, and stale-price checks.
- Local reconciliation of positions, orders, and cash balances against broker state.
- Durable local storage for proposal, approval, and broker order history before and after broker routing.
- Live remains disabled until paper trading is stable for an extended period.

## v1 order assumptions

- Stocks and ETFs only.
- Long-only.
- Daily monitoring.
- Limit, market, and open-oriented workflows only.

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

The automated after-close workflow refreshes Yahoo adjusted daily bars first and then falls back to the configured Interactive Brokers paper connection for missing or failed equity/ETF daily-bar updates. Use separate client IDs for each automated IB operation so a stuck request does not block the other clients:

```powershell
ST_IB_MARKET_DATA_CLIENT_ID=121
ST_IB_EXECUTION_SYNC_CLIENT_ID=131
ST_IB_ACCOUNT_SNAPSHOT_CLIENT_ID=141
```

If Yahoo and IB both fail for a recent after-close date, automation can carry forward the last stored close/FX rate for a short window so EOD PnL and proposal staging do not stall silently. The carry-forward is recorded as an automation warning and defaults to four calendar days:

```powershell
ST_AUTOMATION_MARKET_DATA_CARRY_FORWARD=true
ST_AUTOMATION_MARKET_DATA_CARRY_FORWARD_MAX_CALENDAR_DAYS=4
```

Backtests and live order routing use the same execution timing convention: signals are decided after the decision-date close, order quantities are sized from the decision close, and fills are modeled/routed in the next trading session's opening TWAP window. Daily-bar backtests use the next session open as the available proxy for a 30-minute open-window TWAP. Live IB TWAP orders use:

```powershell
ST_EXECUTION_TWAP_START_TIME=09:30
ST_EXECUTION_TWAP_END_TIME=10:00
```

On startup and every automation loop, the service derives a durable EOD replay backlog from the last completed EOD date through the latest eligible after-close New York business date. Missing dates are processed oldest-first until caught up: execution fills are synced, market data is refreshed into SQLite, account snapshots are refreshed or recovered from same-day files, EOD PnL snapshots are saved, and SOTA rebalance proposals are staged.

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

Start the local web service:

```powershell
.\scripts\start_operator_dashboard.ps1
```

Open `http://127.0.0.1:8000/operator`.

Stop it:

```powershell
.\scripts\stop_operator_dashboard.ps1
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
3. Next: connection health check that confirms account, server time, next valid order id, and managed accounts before routing.
4. Next: reconciliation that pulls IB positions, cash/account values, and open orders; compare with the local proposal snapshot before any order can route.
5. Next: fill capture that persists order status, execution, and commission events locally and reconciles them against the proposal.
6. Later: live switch with explicit config, separate port/account check, capital caps, and a fresh dry-run report before live routing is enabled.

References:

- IBKR TWS API documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/
- TWS API initial setup: https://interactivebrokers.github.io/tws-api/initial_setup.html
- TWS API order submission: https://interactivebrokers.github.io/tws-api/order_submission.html
