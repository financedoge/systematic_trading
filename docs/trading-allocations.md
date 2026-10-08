# Trading strategy roles and capital allocation

## Operator workflow

On **Strategies**, use **Promote / allocate** for a monitored strategy, or open
**Change strategies & weights** on Strategies or Trading.

1. Choose SOTA designation, trading allocation, or both. SOTA is the research
   reference; changing that designation alone does not change trading targets.
2. For trading, enter positive strategy capital percentages totalling at most
   100%. The remainder is reserve cash. Each strategy retains its own cash target.
3. Choose the US session close for the handover, the maximum net order batch in
   CNH, and the operator and reason. Review the combined ETF targets, named assets,
   net orders, paper account, evidence, model dates, limitations and rollback.
4. Confirm the paper configuration. A trading change is scheduled; activation
   occurs after that close and before the next session opens. It never backdates.
5. Review the newly staged order proposal through the existing trading workflow.
   A new allocation requires a fresh automatic paper approval opt-in. Configuration
   approval itself does not send orders.

An unresolved reconciliation break, uncertain order, wrong account, missing
audited input, changed model recipe or exceeded capital cap blocks activation.
A missed handover window retains the approved configuration for the next available
after-close handover; the effective close is recorded separately from the requested
close and history is never backdated. The app shows the pending status. History records the request, activation and first fill
separately. Cancel and rollback append events; rollback requires a new review.

IB connectivity and a snapshot older than 180 seconds are **yellow routing
warnings**, not allocation-preparation blockers. Preparation uses the last recorded
verified paper-account balances, with the capture time retained. These are indicative
holdings, not proof of the current broker position. Account mismatch, a future-dated
capture, known reconciliation breaks and uncertain executions still block preparation
and are shown in red. Routing still requires fresh matching account evidence.

Activation persists the handover's pending rebalance in its immutable event before
adding it to the proposal queue. The worker recovers an interrupted queue write by
proposal ID. Configuration approval never authorizes those orders. On Trading,
**Refresh for approval** prepares a successor when the window is missed or balances
have changed, then the operator uses the usual order approval. The original proposal
and any approval remain in history; a successor invalidates the old route. Renewed
proposals do not inherit approval or automatic execution authority. Known broker
attempts, partial fills and uncertain outcomes require reconciliation/management;
this button never blindly resends them.

Renewal retains the original target intent and original price/TWAP benchmarks while
recalculating whole-share quantities from current available marks and recorded
balances. Direction/asset changes require a new allocation review. Total price
slippage includes approval and rescheduling delay for executed quantities, using the
original benchmark; unfilled orders remain missed-order evidence, not fictitious
slippage. TWAP statistics remain unavailable when complete original-window minute
bars are unavailable. Fees and unclassified cash movements remain separate.

## Multiple strategies

Version 1 uses manual capital weights. It does not fit strategy weights from
recent returns. For example, two strategies at 60% and 40%, each holding an ETF
at 20% and 10% internally, initially imply a 16% portfolio target for that ETF.
This is an illustration, not a recommended mix.

Each strategy owns a virtual share of the real account's positions and cash.
Its capital drifts with actual performance between monthly capital resets.
At the monthly rebalance, internal cash transfers restore the approved capital
percentages. Transfers are excluded from strategy PnL. Reserve cash participates
in the same capital accounting. If an unclassified cash debit overdraws the
reserve, explicit pro-rata capital transfers fund it without resetting relative
strategy weights. The cash debit remains shared and unclassified in attribution.

Opposing ETF changes are crossed internally at the recorded audited raw mark.
Only net account trades reach the broker. Partial fills are allocated pro rata
among the strategies with demand in that direction, retaining fractional virtual
ownership even though broker orders use whole shares. Virtual totals must
reconcile to the real account before subsequent proposals can be built.
New allocations enforce a 45% final combined ETF limit and the reviewed batch cap.
Current support is the registered monthly multi-asset strategies; an all-reserve
configuration and automatic allocation optimizers are outside version 1.

## Dates, performance and attribution

Cumulative strategy/account returns are anchored to the confirmed P&L reset, including evidenced earlier strategy periods. Changing allocations does not reset these returns. Legacy comparisons may use executed proposal identity and the audited app-published parent benchmark, with the preceding-close timing convention disclosed. The Trading page can append a provisional broker-mark endpoint during the session; see [performance contracts](dashboard-performance.md) for freshness, FX, cash and rebasing rules.

- Immutable events are scoped to the portfolio's paper episode. Account identity
  is pinned in the reviewed trading change and checked against reconciliation,
  portfolio context and retained execution evidence. Old contexts without an
  account field can be bound without resetting their accounting history.
- The handover values inherited holdings at the selected completed close. The
  prior allocation earns returns through that close; the new allocation earns
  subsequent returns. Tax-lot cost basis and account history are preserved.
- Performance and PnL charts include allocation markers and labels. Performance
  can select the current or previous allocation period. The strategy table gives
  opening capital, capital transfers, closing capital and marked PnL by period.
  Execution attribution identifies the originating proposal's strategy.
- Earlier dates without verified assignment records remain **Legacy / unknown**.
  Before the first handover, the SOTA curve is labelled a standalone comparison.
- After handover, the allocation reference carries its own holdings and cash
  across changes. It uses the recorded targets at next-session adjusted closes,
  USD cash conversion at observed FX, and a 25 bp/year model cost accrued over
  252 sessions. It never concatenates standalone strategy NAV curves. This
  convention differs from actual fills and from proposal-price execution PnL.
- The Performance panel separately compares published strategy NAV units at each
  dated capital allocation. Its selector compounds theoretical value continuously
  or rebases each switch to actual capital; reset jumps are excluded from returns.
  This comparison lets capital weights drift until the next allocation switch,
  with flat CNH reserve, and retains strategy-level costs/rebalances already in NAV.
  It does not replace the monthly-reset holdings reference or actual-fill ledger.
  See [dashboard performance](dashboard-performance.md) for the formula and gaps.
- The account chart retains observed NAV change. Missing cash-flow classification
  prevents a fully flow-adjusted return claim. Unclassified dividends, fees,
  external cash movements and other cash differences remain a disclosed shared
  residual; unknown reserve PnL is withheld. A missing mark or incomplete fill
  ledger produces an incomplete result rather than invented observations.
- Late fills replay by execution time. Changes to executions or virtual-transfer
  approvals invalidate the saved attribution even without a new account snapshot.

## Storage and calculation contract

Migration `005_strategy_control.sql` adds PostgreSQL state and append-only events.
SQLite has equivalent tables/triggers. Compare-and-swap revisions and request
hashes protect against stale review and duplicate submission. Allocation versions
are stamped into proposals; old proposals cannot route after a switch or rollback.

The application management worker activates pending changes and its normal
strategy service produces targets/proposals. The analytics worker publishes
performance and attribution. No agent or reminder owns recurring calculations.

Rolling XGBoost trading requires the exact monitored definition, a matching audited
price batch, verified model artifact hashes and the causal scheduled fit. USD
remains a separate, verified prediction overlay. Historical FX publication
availability remains uncertified; model fit evidence does not remove that limit.

Native replay validates that the requested US session is complete before running.
LEAN's end-date setter otherwise clamps to yesterday in the algorithm timezone
([upstream implementation](https://github.com/QuantConnect/Lean/blob/master/Algorithm/QCAlgorithm.cs)).
The frozen runner sets that boundary in UTC+14 and restores New York before
subscriptions; quote, signal, fill and NAV dates are unchanged. Native/Python
parity and complete-session checks remain mandatory.

## Deployment acceptance

The October 3 deployment retains the existing SOTA at 100%, with no scheduled
change. Promotion to Rolling 1y XGBoost + ETF activity lag-20 + USD remains an
operator decision after review. The existing IB reconciliation/open-order issues
must be resolved through their normal controls before a trading handover.

Verification artifacts are under `var/research/strategy-control-*`: full and
focused tests, native publication receipts, read-only order previews and browser
screenshots. No backtest result is represented as prospective paper evidence.
