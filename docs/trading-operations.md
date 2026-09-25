# Gateway trading operations

Open [Trading operations](http://127.0.0.1:8000/operator). The page keeps the existing proposal approval queue and performance reporting, with an order blotter and broker portfolio at the top.

## Order visibility

The blotter defaults to **Today · All statuses**, so filled TWAP orders remain visible after leaving Working. Filter **Today**, **Last 7 days** (including today), an inclusive **Date range**, or **All dates**, independently of status. **Filled**, **Working**, **Needs attention**, **Completed / closed**, and **Missed** are separate views; missed proposals do not appear in Completed / closed. Rows are newest trading date/submission first, and counts/audit details follow the date selection.

Trading dates use the intended New York session, falling back to the actual submission date in New York for unscheduled legacy orders. Bulk updates of old missed records never make them today's orders. Submitted and updated timestamps use the browser's local timezone, named above the table. Missing submission times are explicitly marked **Not submitted**. Undated history is accessible under All dates. Unlinked working broker orders remain visible even when their trading date is unknown; an explicit notice identifies working local orders outside the selected date range. Gateway retention does not remove completed records from the durable local blotter.

**Sync portfolio** and the management loop save the exact execution batch retrieved for reconciliation before comparing holdings. This prevents an earlier fill-sync response from lagging behind new TWAP slices. The page refreshes the latest reconciliation every 15 seconds and ignores older responses. **Syncing fills** means new execution evidence awaits persistence; new routing and position resets remain blocked until it catches up, while existing IB orders continue. **Execution history needs review** is reserved for conflicting or incomplete evidence requiring audited recovery. Synchronization never clears a durable execution conflict.

The blotter queries IB open orders and broker-retained completed orders every 15 seconds while the page is visible. Use **Sync orders** for an immediate snapshot. Filter working orders, orders needing attention, terminal records or all history. Each linked row shows broker status, total/filled quantity, limit, account, broker order ID and reference. Expand the audit history for execution evidence, broker observations and operator actions. Broker callbacks and locally accumulated executions are separate evidence; a missing order is never treated as cancelled. Old local history remains visible after the broker's completed-order retention window ends.

External/unlinked orders are view-only. Changes require a positively matched paper account, the application's submitting client ID, symbol/side/reference, and current broker evidence. Completed callbacks from the installed IB API omit API client/order IDs: the previously observed permanent ID must match that exact attempt. The UI indicates stale observations and disables unsafe controls.

## Cancel, amend and resubmit

Each action requires a review dialog with operator name and reason. The review binds the current local record; concurrent fills or another operator's changes invalidate it. Actions are claimed atomically before contacting IB and persisted with audit/outbox state. Timeouts keep an unresolved claim rather than permitting another order. Sync confirms the broker result. If a claim cannot be resolved from broker evidence, investigate it; restarting the app does not erase it.

- **Cancel:** sends a cancellation only for a currently working, positively matched order. Cancellation does not require a matched portfolio, so a reconciliation break does not prevent reducing risk. A pending request is not presented as a completed cancellation; intervening fills are retained.
- **Amend:** supports plain limit orders. Total quantity may decrease but must remain above the broker's filled quantity. A buy limit may decrease; a sell limit may increase. Original contract, time-in-force and other broker fields are retained. A current approved proposal and fresh matched reconciliation are required. TWAP/VWAP, other algorithms, exposure increases and price changes beyond approval require cancellation and a newly reviewed proposal. The existing strategy approval workflow still routes TWAP by default.
- **Resubmit:** sends the stored routed terms only after a fresh broker snapshot confirms cancellation and zero fills, and the proposal is still approved and inside its execution deadline. Filled, partly filled, uncertain or expired orders cannot be resubmitted. Permanent identity and prior attempt details remain in the audit. Rejections that lack definitive broker cancellation evidence require investigation rather than a blind retry.

The normal routing API and database reservations also reject nonzero/unknown broker fill evidence before execution-history synchronization completes. Polling and management actions do not emit duplicate fill events for unchanged executions. Live routing remains disabled.

## Portfolio synchronization

**Sync portfolio** retrieves IB positions/cash and execution evidence, saves the account snapshot and runs reconciliation. Holdings and native-currency cash are shown independently of strategy targets. Synchronization does not reset the accounting baseline. If a discrepancy remains, review the report; **Reset local to IB** stays a separate explicitly confirmed operation. EOD data/FX freshness requirements remain unchanged.

## Initial allocation and drift monitoring

With automatic proposal staging enabled, each trading-management loop checks fresh, matched IB paper reconciliation. An empty account with investable cash can immediately stage an initial TWAP allocation; it does not wait for month-end. Holdings in the entire IB account count, including positions outside the strategy universe. Multiple accounts, unknown positions, cash liabilities, incomplete data, unmatched executions and uncertain orders block automatic building.

For an invested account, the monitor compares holding weights with the active strategy targets. The user-selected threshold is **2 percentage points per holding**, configured by `ST_AUTOMATION_REBALANCE_DRIFT_THRESHOLD=0.02`. A 20% target triggers at 18% or 22% actual weight. A breach in any holding stages one portfolio rebalance back toward the target weights, subject to whole-share sizing. Smaller tradable differences in other holdings can therefore be included in that same proposal. Differences below the threshold do not trigger orders by themselves.

Current quantities/cash come from IB; weights and sizing use the latest **completed daily close** and same-date FX. This is a daily-price monitor, not an intraday quote monitor. The page shows the valuation date, target date, actual/target weights and difference in percentage points, or an explicit readiness blocker. It uses approved target weights from the current monthly period (including an approved initial allocation), otherwise recomputes the latest scheduled month-end targets using point-in-time history. It does not recalculate strategy signals on every price check. Scheduled monthly signal updates remain in place.

TWAP uses the configured duration (normally 30 minutes). Before the open it targets 09:30 New York time; during the session it allows approximately 2–3 minutes for review before starting. When a full window no longer fits, including an early close, it targets the next US session. Approval/retry expires by the TWAP end. A delayed approval can therefore have a shorter remaining execution period. Generated proposals initially remain **pending approval**. Manual mode is the default; the optional paper policy below can approve and route newly generated proposals. Live routing remains disabled.

## Fill prices and TWAP execution costs

The blotter displays the retained average fill price independently of the order's limit. TWAP estimates use duration-weighted observed one-minute IB TRADES closes across the full scheduled New York TWAP window, including any delay before approval. They are minute-bar estimates, not tick-exact TWAP or a broker guaranteed execution price. A benchmark is published only after the window ends and every interval is covered without conflicting data. Hover over the estimate for the window and coverage. No fill price, zero or daily close is substituted for missing intraday observations.

Buy slippage is `(average fill − TWAP) / TWAP × 10,000`; sells reverse the sign. Price cost is the signed price difference multiplied by filled shares, in the instrument's currency. Positive means worse execution; negative means improvement. Commissions, fees, funding and currency conversion costs are excluded. Observations and provenance are cached under `var/execution_benchmarks/`; a separate read-only connection uses `ST_IB_BENCHMARK_CLIENT_ID` or the order client ID plus 90. Missing history retries after five minutes when the blotter is viewed. The recorder's delayed, incomplete aggregates are not silently substituted.

## Automatic paper approval

Use **Trading operations → Approval mode → Automatic: off** to open the policy dialog. Enter the gross batch cap in CNH, operator and reason, then choose **Enable automatic paper trading**. This authorizes approval **and submission** of new strategy TWAP proposals; switching back off stops future automatic submissions, while orders already at IB continue. A running management service and fresh matched single-paper-account reconciliation are required to enable it. The initial cap shown is CNH 1,000,000; review it before enabling.

Only proposals generated after enablement with the current strategy identifier are eligible. Existing queues, manually constructed proposals and rejected proposals are excluded. The controller waits for the explicit regular-session TWAP window, requires latest completed-day prices and FX, rechecks sizing against current holdings/cash, validates target weights and gross notional, and blocks liabilities, open/uncertain orders and reconciliation issues. The normal router retains all its checks and live remains disabled.

The local policy at `var/live/paper_auto_approval.json` includes operator/reason, revisions, switch history and attempt outcomes; switch events also enter the transactional outbox. Policy is bound to this machine, workspace, paper broker profile and strategy. Another machine or changed strategy requires re-enablement. Policy decisions use an atomic pending-to-approved status check. A persisted attempt claim comes before approval/routing; failures, partial submissions and interruptions require manual review and cannot be automatically retried. This is an opt-in paper execution policy, not evidence for live promotion. Automatic approval is left **off** after implementation.

## Restarting P&L after a paper-account reset

An operator-authorized opening reset uses a saved, matched, flat pre-trade snapshot of the same paper account. Current reconciliation must be fresh and today's retained executions must explain every current holding. The reset creates an audited baseline just before the requested New York trading day, retains execution history, and assigns the observed opening cash to a clearly identified prior-close reference while retaining its real capture timestamp. Earlier snapshots stay in storage but are excluded from active P&L charts. This differs from resetting positions to the broker at the current moment: today's trades remain in the active ledger.

Fresh broker open-order checks, local uncertain-order checks and existing proposal decisions prevent repeated attempts. A deterministic proposal ID is inserted atomically in SQLite/PostgreSQL and survives restarts. A rejected attempt is not recreated while the same account/target/position episode remains unchanged. Expired unapproved attempts can be reconsidered for a later session; same-session duplicates are suppressed. A later full liquidation or explicit portfolio reset permits a new initial-allocation episode. Existing approvals are never overwritten. Monthly staging waits for any unexpired initial/drift proposal.

Legacy approvals without intended trade dates are treated as history only when every order has a recorded attempt covered by the reconciled baseline. Their approvals and recorded broker statuses remain unchanged. Missing/new attempts, uncertain actions and current broker orders still block new allocation. The proposal list and readiness message refresh every 15 seconds while the page is visible; the current selection and decision comment are preserved. Readiness blockers are also shown next to the proposal queue.

The management loop refreshes all required cash currencies before testing proposal readiness. Operational FX comes from observed IB midpoint closes and matched-date cross rates, with source evidence saved locally. Same-date FX remains mandatory; no stale prices or rates are carried forward. See [Gateway setup](ib-gateway-operation.md) for the required official SDK and FX client ID.

The historical strategy benchmark still represents the monthly strategy. Initial intraday deployment and drift rebalancing are separately tagged paper execution policies; their extra turnover/costs are not yet represented by that benchmark and require paper evidence and replay/cost validation before live promotion.

## Paper test sequence

After a NAS move, the Gateway order-ID sequence may be lower than the restored ledger. Routing chooses IDs above both sequences and retains database uniqueness and intent claims. If approval succeeds but routing stops, the approval remains visible under **Approved**. Sync orders, inspect recorded outcomes, then use **Resubmit Failed/Missing** only for eligible legs before expiry. A pending/unknown broker outcome blocks retries; an HTTP error alone never proves an order was not sent. This workflow preserves earlier successful legs and does not repeat the whole batch automatically.

1. Sync orders and portfolio; check that the Gateway session is paper and reconciliation is matched.
2. Prepare and review a fresh, small paper proposal for the selected symbol, quantity and limit. Existing expired historical proposals are ineligible.
3. Submit through the existing approval/routing workflow. To exercise amendments, use a plain limit route rather than the strategy's default TWAP route.
4. Confirm the order appears in the blotter. Review an allowed amendment, sync, then cancel and wait for the broker-confirmed outcome.
5. Only if cancelled with zero fills and still within the approval window, review resubmission. If filled, verify executions and portfolio instead.

Implementation validation used isolated SQLite/PostgreSQL tests and a synthetic browser preview. Real Gateway order snapshots and portfolio reconciliation were read successfully; no broker order was placed, amended or cancelled during implementation. Restart/reconnect soak and an actual supervised paper lifecycle remain to be tested.

IB documents the [same-client modification rule](https://www.interactivebrokers.com/docs/tws-api/doc/orders/modifying-orders) and [cancellation ownership](https://interactivebrokers.github.io/tws-api/cancel_order.html). The installed API's completed-order decoder was also inspected to verify its identity fields.
