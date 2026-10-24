# Paper rebalance renewal — missed 2026-10-16 handover

The October 24 [durable intent recovery repair](rebalance-intent-recovery-2026-10-24.md)
supersedes the narrow renewal eligibility and manual-only partial-fill limitations
below. This document retains the original incident and deployment evidence.

## Incident

The FR25 14-ETF allocation `allocation-fe2d3613-4694-4d27-925a-c53536932eab`
was activated after the 2026-10-15 US close. The application prepared the
handover rebalance `handover-fe2d3613-4694-4d27-925a-c53536932eab` for the
2026-10-16 09:30–10:00 America/New_York TWAP window with six net orders
(sell DBC, sell EWH, buy EWJ, sell SPY, buy VGK, buy XLE).

The proposal was never approved and never routed:

| When (UTC) | Evidence |
| --- | --- |
| 2026-10-15 14:47 | paper policy revision 10 enabled, bound to the previous allocation |
| 2026-10-15 21:02 | allocation activated; handover proposal created for 2026-10-16 |
| 2026-10-16 14:00 | execution deadline elapsed with no approval |
| 2026-10-17 03:44 | proposal marked `missed`; six synthetic missed records written; no broker attempt, no broker order ID, no fill |
| 2026-10-17 03:45, 2026-10-18 08:37 | operator re-enabled automatic paper trading (revisions 11 and 19, bound to the current allocation) |
| 2026-10-19 00:20 | trading service running; `portfolio_alignment.status = review` with "Rebalance retained. Refresh for approval to choose a new window…"; no pending proposal, no approval, no order |

The operator expected the enabled automatic paper policy to resubmit the missed
rebalance. Nothing happened.

## Root causes

1. **No automatic renewal path.** The paper policy only approves *pending*
   proposals. A missed application-prepared handover is retained as an expired
   intent and only the explicit operator refresh endpoint
   (`POST /api/v1/proposals/{id}/refresh-rebalance`) could create a successor;
   the automatic loop never called it, and no UI control did either. Enabling
   automatic trading therefore had nothing eligible to act on.
2. **Stale model binding during renewal.** The renewal rebuilt component models
   from the source proposal's target date (2026-10-15). After the application's
   daily calculation advanced to 2026-10-16, the FR25 financial overlay's exact
   daily decision (`as_of` 2026-10-16) was replaced by the next indicative
   decision and the rebuild failed with "Exact FR25 decision missing; await
   application catch-up".
3. **Over-strict order-intent comparison.** The renewal required every refreshed
   leg to match an original `(symbol, side)`. At the refreshed 2026-10-16 closes
   one whole-share top-up (buy 1 EWY) appeared while all retained target weights
   and directions were unchanged, so a legitimate intent-preserving renewal was
   rejected.
4. **Execution-universe data gap.** The trading-market-data refresh, drift
   valuation and end-of-day account snapshot used the SOTA designation
   (12 ETFs) rather than the active 14-ETF allocation. XLB and XLE had no daily
   bars in the execution market-data store, so the automatic preflight and
   drift monitor could not accept the allocation even after a successful
   renewal.
5. **Stale target-date binding in drift monitoring.** `build_allocated_plan`
   forced component model targets to `max(monthly target date, allocation
   effective close)`. Mid-month that asked the daily FR25 financial overlay for
   an exact decision session that the advancing publication no longer carries,
   so drift monitoring failed with "Exact FR25 decision missing" after the
   handover was approved.
6. **Adopted-target loss after a residual failure.** Target resolution only
   accepted `approved` proposals. The renewed handover filled 6 of 7 legs; its
   last one-share leg was cancelled by IB at the window end and the approved
   proposal then expired to `missed`. The drift monitor therefore fell back to
   the previous month-end target and staged a full rebalance toward stale
   weights. The frozen targets of a partially executed rebalance must stay
   adopted until a later rebalance is approved.

## Change

**Automatic renewal (paper-only).** When the policy is enabled and bound to the
active allocation, each management tick may renew one expired
application-prepared rebalance into the next complete TWAP window. The source
must carry application-prepared account evidence, match the active allocation
binding, be expired without a real broker attempt, have no claimed automatic
attempt, and not be a rejected or superseded intent. Session-limited operator
catch-up authorizations are never extended. The successor keeps the retained
target weights and original slippage benchmark, recalculates whole-share
quantities from the latest completed session and current reconciled account,
gets `automation_strategy_key` and the policy revision in its deferred-rebalance
lineage, and then passes the ordinary eligibility, reconciliation, sizing,
preflight and router checks before approval and submission. Renewals are
persisted in `var/live/paper_auto_approval.json` under `renewals`; a blocked
renewal retries no sooner than five minutes later. A changed target vector or a
reversed trade direction still requires a new allocation review; a small extra
whole-share leg inside the same allocation is allowed and starts its benchmark
with the refreshed plan.

**Data universe.** The app-owned daily market-data refresh now covers the union
of the SOTA designation and the active trading allocation, the end-of-day account
snapshot filters on the same union, and drift valuation uses the active
allocation universe. Missing allocation-only bars are acquired through the
normal Yahoo/IB refresh path and stored in the execution market-data store; the
provider archive is never read directly as a research input.

**Target binding and adoption.** Component targets bind to the requested
decision session (normally the latest month-end) instead of the later allocation
activation close. Target resolution also treats the frozen targets of a
`missed` proposal as adopted when at least one of its orders filled, so a
residual cancelled leg cannot make the account rebalance toward an older
month-end target.

Code: `src/systematic_trading/live/auto_approval.py`,
`src/systematic_trading/live/deferred_rebalance.py`,
`src/systematic_trading/live/allocated_plan.py`,
`src/systematic_trading/live/market_data.py`,
`src/systematic_trading/live/management_service.py`,
`src/systematic_trading/live/initial_allocation.py`,
`src/systematic_trading/live/account_snapshot.py`,
`src/systematic_trading/portfolio/targets.py`.

## Recovery evidence

The updated modules became active when the dashboard restarted at
2026-10-19 16:47:54 UTC (restart not initiated by the investigation session;
two `operator_lifespan_starting` events are recorded at 16:47:37 and 16:47:55
and no supervisor `operator_start_requested` event exists). The embedded
management loop then performed the recovery through the normal automatic path:

| When (UTC) | Evidence |
| --- | --- |
| 16:47:59.920 | policy renewal audit: `handover-fe2d3613…` → `renew-d349f9fb67b4efa58df5`, policy revision 19, new window 2026-10-19 12:50–13:20 New York, 7 orders, 346,488.42 CNH gross |
| 16:50:24.816 | automatic approval decision (atomic pending → approved) under policy revision 19 |
| 16:50:27 | seven paper TWAP orders submitted; IB broker order IDs 47–53 |
| 17:10–17:19 | six orders filled: DBC 185, EWH 813, EWJ 18, SPY 2, VGK 22, XLE 327; 42 broker execution records synced |
| 17:20 | IB cancelled the unfilled 1-share EWY remainder at the window end (0 filled) |
| 17:23 | IB portfolio reconciliation matched all six positions and cash; zero breaks |
| 17:24 | explicit `Sync orders` update: six filled, EWY cancelled; no working/uncertain orders remain |

Resulting broker positions: DBC 471, EWJ 230, EWY 40, SPY 46, VGK 278, XLE 327,
HKD cash 16,883.14. The partially failed batch then expired to `missed`, which is
the documented expiry semantics and remains durable audit evidence.

After the adopted-target fix the drift monitor keeps the frozen handover targets
and reports all holding drifts below the 2 percentage-point threshold (largest:
SPY +0.56 pp). It staged one residual cleanup proposal,
`drift-97f2af32c2d7-20261019` (buy 1 EWY, 1,005.89 CNH), which remains
**pending operator review**; it predates the restored policy revision and is
therefore not auto-eligible, and it has no broker records.

Maintenance controls used during the fix: a first stale-target drift proposal
`drift-2fdda5799533-20261019` (built from September month-end weights after the
partial fill made the handover `missed`) was rejected with no broker records,
and automatic approval was paused at policy revision 20 while the target-source
fix was deployed. After a fresh matched reconciliation and the guarded restart
the operator-approved policy was restored at revision 21 with the same
allocation, paper account and CNH 1,000,000 batch cap. No order was routed under
the stale-target proposal.

## Guards and limitations

- Paper only; live routing remains disabled. No allocation, funding, monitoring
  membership or promotion authority changes.
- Renewal never releases an existing approval and never resends a broker order.
  Any real/uncertain broker attempt, partial fill or unsettled management action
  blocks the refresh path and requires manual reconciliation.
- Renewal runs only inside the trading-monitoring loop (trading days). A renewal
  prepared after the close targets the next session; it does not backdate a
  fill or use stale same-session prices.
- A missing governed model publication blocks renewal visibly instead of
  substituting a stale decision.
- The execution market-data universe is not a research input: strategy signals
  and benchmarks continue to use the pinned audited histories/publications.
