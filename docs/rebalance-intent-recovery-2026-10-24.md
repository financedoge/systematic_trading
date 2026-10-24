# Outstanding paper rebalance recovery — October 24, 2026

## Local incident evidence

Read-only inspection used the configured native PostgreSQL store and the saved
paper policy/management status. The October 21 proposal is
`drift-97f2af32c2d7-20261021`: sell 1 SPY, buy 3 VGK and buy 2 XLE. It was created
October 20 at 19:28:24 UTC, using October 19 data, for October 21's opening window.
Its deadline was October 21 at 14:00 UTC (22:00 Asia/Shanghai). It has three
synthetic missed records, no broker IDs, no fills and no automatic attempt claim.
Policy revision 21 remains enabled for the active allocation and paper account.
Its saved message is “Proposal requires a current, unexpired US trading session.”

The saved state establishes failed eligibility and no recorded send; it does not
establish the computer/Gateway's availability at every instant of the original
window. The batch also fails the latest-completed-session data requirement:
October 21 execution requires October 20 marks/FX. The old renewal path excludes
this ordinary drift proposal because it lacks `prepared_account`. Its weights
match the adopted October 16 handover target, although the old allocated-plan
builder incorrectly stamped `target_as_of` as September 30.

The October 19 handover had six filled legs and one cancelled, unfilled EWY leg.
The adopted target remains `renew-d349f9fb67b4efa58df5`, dated October 16.
Read-only evaluation of the repaired selection resolves the newest recovery
candidate to the October 21 batch and its effective target date to October 16.

There is also a current external dependency failure: alignment requires October 23
USD/CNH and HKD/CNH observations, but the latest stored observations are October 21.
The management log records IB historical-data timeouts and disconnected `cashhmds`
and `ushmds` farms. Missing observations remain missing; this repair does not
substitute FX, relax freshness, or invent current drift values.

## Contract and implementation

An objective and an execution window now have separate lifecycles. Durable intent
state is stored through the existing PostgreSQL/SQLite compare-and-swap and
immutable audit contract, under `rebalance-intent:<portfolio scope>:<root proposal>`.
There is no schema migration. The objective retains its root, frozen targets,
creation date, current attempt, status and blocker. Successor proposals retain
lineage and original slippage references. Historical proposals, missed markers,
broker records and approvals remain available.

- Background management expires all relevant proposals, including while the
  exchange is closed or automatic approval is disabled. Dashboard visits are not
  required. Validation failures do not consume the whole automatic queue cycle;
  a submission claim still stops further batch submission pending reconciliation.
- Approval adopts the target independently of fills. Approved virtual transfers
  remain in the strategy ledger after an execution window becomes missed.
  A never-approved, never-filled missed proposal is not an adopted target.
- The newest bound objective controls recovery. Independent newer proposals and
  rejections block revival of earlier targets; identical stored legacy vectors
  resolve the old incorrect target-date label. Ambiguous newest entries fail
  visibly. A newer adoption explicitly supersedes the earlier outstanding intent.
- The enabled paper policy can recover ordinary scheduled, initial and drift
  proposals as well as prepared handovers. Expired windows and stale forward
  pricing are rebuilt with current completed-session marks/FX and fresh reconciled
  holdings. Every successor is pending and passes normal approval and router
  checks. No expired proposal is routed in place. A zero-residual objective can
  complete after fresh reconciliation without creating a broker order.
- A partial fill permits only fresh residual sizing. Real attempts require
  complete execution evidence, terminal broker outcomes, a later matched account
  reconciliation and an open-order snapshot. New or inconsistent evidence blocks
  recovery. Filled quantities and original orders are never rewritten.
- New automatic claims persist the router phase and its reserve-before-send
  contract. A claim before routing, or a known router with no durable reservation,
  can be conclusively unsubmitted. Legacy unknown claims remain blocked unless
  every leg has actual attempt evidence and the terminal/reconciliation checks
  pass. Absence from an IB snapshot never proves cancellation or no send.
- Cancellation uses the explicit `Cancel rebalance intent` action or
  `POST /api/v1/proposals/{id}/cancel-rebalance` with operator/reason. It survives
  restarts and cannot be overwritten by a stale recovery writer. It ends recovery
  authority; existing broker orders still need order management. It does not undo
  fills or virtual transfers. A new target decision is needed to resume.
- Drift against retained targets is calculated without requiring successful
  strategy/order-plan rebuilding. Blocked/review states remain warnings. When
  current valuation is unavailable, the last valid table remains dated and labelled
  stale. The dashboard exposes intent status, pending age and the next retry
  condition. No current-value claim is made from stale evidence.

Paper account, environment, allocation binding, capital caps, instrument admission,
audited input hashes, fresh reconciliation, uncertainty and approval guards remain
mandatory. Session-limited catch-up authorizations are never extended through a
successor. Changed target vectors or reversed required trade directions still
require review. The existing 2 percentage-point per-holding housekeeping trigger
is unchanged; it is not a new research or portfolio-allocation rule.

## Verification and rollout

Offline tests cover ordinary proposal renewal, zero-fill adoption, partial-fill
residual quantities, uncertainty, stale reconciliation, open broker orders,
restart recovery, cancellation, supersession, queue progress, background expiry,
drift visibility, retained virtual transfers and terminal-state write protection.
Both SQLite and disposable native PostgreSQL exercise the durable intent contract.
The combined coverage is 282 distinct passing tests across targeted runs, including
existing broker, approval, API, UI and management suites. Ruff and whitespace
checks pass. No test uses
the operational database for writes or submits to the user's broker.

Source changes preserve the pre-existing uncommitted recovery and research work.
Runtime activation is pending: the running app was not restarted because that also
loads unrelated pre-existing uncommitted research changes. No policy, allocation,
approval or broker state was changed. The missing FX observations remain a real dependency for any
actual successor; a code deployment alone cannot establish portfolio alignment.
