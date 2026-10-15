# App-owned execution benchmark collection

Implemented October 11, 2026, as the collection part of P4.19a. The operator application owns a
lightweight post-trade worker. It starts with the app, scans retained paper orders every 30 seconds,
and uses the same single request queue as the blotter. Collection no longer depends on a page visit.
It has no order, approval, allocation or account-recovery authority.

## Scope and evidence contract

- Only filled IB paper TWAP orders in the supported USD contract are eligible. Unfilled orders,
  other order types, unsupported currencies and execution-review blocks remain visible in coverage.
- Original intent and the actual routed window are tracked separately. A symbol/window identity is
  fetched once even if multiple orders refer to it. Rescheduling cannot replace the original benchmark.
- From October 12, the same bounded queue also collects the original and routed regular sessions.
  It uses the app's US calendar (including early closes), waits for session completion and gives order
  windows priority. All captured sessions remain separate immutable observations.
- The provider resolves exactly one matching IB contract before requesting historical `TRADES` bars.
  The capture retains conId, currency, venue, OHLC, volume, WAP, trade count, callback messages and
  observation time. Contract discovery is not a trading-permission test.
- A ready TWAP requires complete one-minute coverage, valid prices, matching window/identity,
  a completed historical response and unchanged source hashes. It is a duration-weighted estimate
  from minute closes, not tick-exact TWAP. Missing intervals are never filled.
- Captures retain the provider's historical price basis. **Trading-time raw-unit qualification is not
  independently certified**, so publications carry `research_approved: false`. These are operational
  observations, not permission to feed prices into a promoted strategy or a new return study.

IB warning 2188 refers to up-to-the-second historical-data subscription requirements. The service
retains it as an advisory only when the requested window ended at least 15 minutes ago; it still
waits for `historicalDataEnd` and checks every interval. Recent-window 2188 and genuine historical
permission failures remain unavailable. In deployment, the old handler rejected complete older bars
delivered alongside this warning; the first failed attempts remain preserved. See
[IB's error-code documentation](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes).

## Storage, publication and recovery

`var/execution_benchmark_attempts/<window-key>/` retains separate request, response and audit files
for every attempt, including failed/partial responses. `var/execution_benchmark_state/<key>.json`
is the mutable retry checkpoint. Retries start at five minutes and back off to one hour; the cooldown
survives process restarts. A crash during a request leaves its start receipt and cooldown for recovery.

Completed windows are immutable `var/execution_benchmarks/<key>.json` files. Each carries raw-response
and normalized-bar hashes. The importer rechecks identity, coverage and the retained raw capture before
advancing the existing `execution-benchmarks` ClickHouse publication. An invalid file is withheld and
its source retained for review, rather than silently replaced by another download. Prior frozen research
roots are untouched. Hash-verified publication does not remove historical source/revision limitations.

The worker separately publishes `execution-benchmark-coverage`, including per-order original/routed
status, missingness and retry information. Unchanged coverage has the same version. The local checkpoint
is `var/run/execution_benchmark_collection.json`. The GET endpoint
`/api/v1/execution/interactive-brokers/benchmark-coverage` only reads worker state. `/health` exposes
the collector's heartbeat, errors and coverage; collection problems are separate from execution authority.

Settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `ST_EXECUTION_BENCHMARK_COLLECTION_ENABLED` | `true` | Start the app-owned collector |
| `ST_EXECUTION_BENCHMARK_REFRESH_SECONDS` | `30` | Scan interval; minimum 15 seconds |
| `ST_EXECUTION_BENCHMARK_MAX_PENDING` | `4` | Bound running/queued data requests; one request runs at a time |
| `ST_IB_BENCHMARK_CLIENT_ID` | paper order client + 90 | Separate read-only data connection |

## Retrospective reference qualification — October 12

The app separately publishes `execution-reference-audits`. This publication admits only retrospective
execution diagnostics; `research_approved: false` remains explicit. It does not admit these bars to
strategy backtests or certify a continuous intraday price history. Missing execution details stay missing.

The versioned policy is fixed in `execution/benchmark_qualification.py` before examining price costs.
The audited daily catalog, per-symbol storage batch, source files and ClickHouse row hashes must agree.
Incremental catalog versions can point to an older storage batch; the reader verifies that publication
instead of assuming every symbol belongs to the newest batch. The app retains both passing and failing
audits with explicit reasons. A research freeze consumes this publication, not provider downloads.

| Reference | Required definition and evidence | Current status |
| --- | --- | --- |
| Trading-time raw basis | Resolved USD stock contract, governed raw row and all session OHLC fields within the existing raw-price audit tolerance (0.5%); actual differences retained | Scoped consistency audit; known subsequent splits, missing raw values and unresolved quality flags withhold the session |
| Session close | Governed reconstructed raw daily close on the declared session, with catalog/storage/row/source hashes | Audited reference; **not certified official auction price** |
| Session VWAP | Full regular-session one-minute coverage; sum of bar WAP times provider volume divided by summed provider volume | Filtered historical TRADES estimate; no substitution of minute closes for WAP |

Positive-volume bars require finite WAP within valid OHLC bounds. Zero-volume minutes contribute no
value; all-zero sessions fail. Missing/overlapping minutes, conflicting duplicate fields and negative
volume fail. Provider volume remains in its reported quantity units: a common scale cancels within
one contract/session, but the audit does **not** assert share counts, traded dollar value or comparable
volume across instruments. Subsequent reported splits are rejected rather than guessed or rebased.

The 0.5% threshold checks price-basis consistency; it is not a claim of sub-basis-point price accuracy.
The governed prices are reconstructed from reported corporate actions, not tape-certified. The action
ledger's vintage may precede the IB capture, so later actions are not independently covered. Cross-source
OHLC agreement does not repair that limitation or establish historical availability. These restrictions
are embedded in every policy publication and survive the frozen analysis.

IB's historical feed filters some trade types, and per-bar WAP can be rounded. Even a complete
volume-weighted aggregation must be labelled an **IB historical TRADES session-VWAP estimate**, not
an exact exchange-wide VWAP. Multiplying each minute close by volume is a different approximation
and cannot be substituted. [Historical-bar semantics](https://interactivebrokers.github.io/tws-api/historical_bars.html).

The matched cohort fixes symbol, decision, side and executed quantity across references, records both
intended and actual dates, separates approval/rescheduling delay, and reports exclusions. Reference
price comparisons do not establish counterfactual fill prices, impact or fill probability. A prospective
execution-style experiment needs its own declared protocol. No execution-style change follows from
collection alone.

`scripts/analyze_execution_references.py` freezes the publications, checked governed inputs, raw
capture evidence and calculation sources. It requires complete execution details and all six references
(original/routed TWAP, close, VWAP) for each included order. Overlapping window/session minute closes
must match exactly, otherwise the revised vintage is excluded. It reports signed USD cost divided by
gross reference notional, per-symbol/session results, same-date versus delayed-date cohorts and a
leave-one-session-out sensitivity. Original-minus-routed price cost includes intervening market movement;
it is not an isolated causal estimate of approval delay. No fees, FX or unfilled-order cost are imputed.

## Verification

Tests cover automatic worker collection without HTTP requests, deduplication, separate original/routed
windows, bounded queueing, durable failures/restarts, raw-capture tampering, publication withholding,
paper filtering, app lifecycle, and IB warning/permission behavior. Deployment evidence is retained in
`var/research/benchmark-collection-20261011-*.json`; test results are in
`var/research/benchmark-collection-20261011-tests.xml`. Final counts and app verification are recorded
in the session closeout in `log.md`.

Deployment readback on October 11 verified **34 windows covering 30 paper TWAP orders**, with identical
source-audited local and ClickHouse payloads. Two further explicit windows are legacy USO/DBB orders
outside the configured IB contract universe, and ten legacy TWAP orders have no recorded window.
These gaps keep coverage degraded; they are not a collector crash or evidence of denied XLE/XLB
trading permission. Paper capital and order counts were unchanged. The focused suite passed 96 tests;
one disposable-ClickHouse test was skipped, with actual publication/readback checked separately.

October 12 follow-up: 30 full sessions passed the scoped reference audit; all **64** order-window/session
captures were source-verified and read back identically from ClickHouse. The new matched research
freeze reproduced exactly (27 orders / five sessions); [findings](execution-reference-findings.md).
The extended suite passed 100 tests with one disposable-ClickHouse skip; seven final analysis checks
and Ruff passed. Receipts are `var/research/benchmark-qualification-20261012-*`. Allocations, orders
and execution authority remain unchanged.
