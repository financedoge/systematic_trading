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

## Remaining close/VWAP qualification contract

P4.19's execution-style comparison remains separate from this delivery. The current collector retains
order windows, not complete sessions, and does not reconstruct absent execution details. The following
inputs must be qualified and bound into a new frozen study before the comparison can proceed:

| Reference | Required definition and evidence | Current status |
| --- | --- | --- |
| Trading-time raw basis | Match contract and session to an audited raw-price publication, with input hashes and explicit corporate-action/unit handling; do not compare adjusted historical prices to unadjusted fills | Not independently qualified |
| Session close | Declare last regular-session trade versus official closing-auction price, then bind the selected audited raw closing-price source and session date | Not qualified |
| Session VWAP | Full regular-session coverage using the shared calendar, including early closes; valid traded volume and per-bar WAP/value with explicit units, positive total volume and no missing intervals | Not qualified; volume/WAP now retained for the available order windows |

IB's historical feed filters some trade types, and per-bar WAP can be rounded. Even a complete
volume-weighted aggregation must be labelled an **IB historical TRADES session-VWAP estimate**, not
an exact exchange-wide VWAP. Multiplying each minute close by volume is a different approximation
and cannot be substituted. [Historical-bar semantics](https://interactivebrokers.github.io/tws-api/historical_bars.html).

The future matched cohort fixes symbol, decision, side and quantity across styles, records both
intended and actual dates, separates approval/rescheduling delay, and reports exclusions. Reference
price comparisons do not establish counterfactual fill prices, impact or fill probability. A prospective
execution-style experiment needs its own declared protocol. No execution-style change follows from
collection alone.

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
