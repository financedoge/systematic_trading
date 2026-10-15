# P4.19 — Execution timing: retained-evidence audit

Reviewed October 11, 2026. **The evidence audit is complete; the execution-style comparison remains
blocked.** There is no supported cost ranking of opening-window TWAP, session close and session VWAP.
The earlier plan's assumption that retained benchmarks already made this a no-new-data comparison
was incorrect. At this frozen snapshot, the published benchmark dataset was empty.

**Subsequent work, October 12:** [P4.19a's app-owned collector](execution-benchmark-collection.md)
now publishes order windows, full sessions and scoped retrospective reference audits. The separate
[matched comparison](execution-reference-findings.md) covers 27 orders and retains the current
execution policy. It does not change the frozen counts below. Continuous intraday research admission,
raw-tape certification and an achievable execution-style ranking remain outside that diagnostic scope.

## Frozen coverage

Read-only snapshot at 21:43 Shanghai time on October 11. The PostgreSQL order query and pinned
ClickHouse publication were copied before analysis; no broker calls, price downloads or database
writes were made. All retained paper history is included, including legacy orders and partial fills;
this is not a current-account PnL report or a comparison of identical trading decisions.

| Evidence | Count |
| --- | ---: |
| Retained paper order records | 270 |
| Orders with any filled quantity | 45 |
| Filled TWAP / limit orders | 42 / 3 |
| Filled TWAP orders with explicit original and routed windows | 32 |
| Orders with complete, consistent execution details | 27 |
| Individual retained execution details | 134 |
| Filled orders missing execution details | 18 |
| Partially filled orders | 10 |
| Published TWAP benchmark documents | **0** |
| Orders with usable TWAP / close / VWAP comparisons | **0 / 0 / 0** |

All 27 orders with complete details are TWAP orders with explicit windows. Their execution timestamps
span just five sessions: September 25 and October 1, 2, 5 and 8. The other 18 orders retain aggregate
fill information but not complete execution details; do not fabricate timestamps or reconstruct them
from an order's intended date. Ten TWAP orders have no complete explicit benchmark window; the three
limit orders do not have a TWAP window by design. These cohorts overlap and must not be added together.

| Symbol | Filled orders | Complete execution details | TWAP orders | Usable TWAP benchmarks |
| --- | ---: | ---: | ---: | ---: |
| DBB | 3 | 0 | 3 | 0 |
| DBC | 6 | 5 | 6 | 0 |
| EWH | 5 | 5 | 5 | 0 |
| EWJ | 6 | 5 | 6 | 0 |
| EWY | 10 | 5 | 9 | 0 |
| GLD | 2 | 2 | 2 | 0 |
| IWM | 3 | 0 | 2 | 0 |
| SPY | 2 | 2 | 2 | 0 |
| USO | 5 | 0 | 4 | 0 |
| VGK | 3 | 3 | 3 | 0 |

All retained filled orders use USD. Per-symbol and per-style price cost and basis-point slippage are
**unavailable**, not zero. The frozen JSON includes explicit nulls, exclusion reasons and every order's
original/routed window so that future evidence collection can target the gaps without changing this run.
Symbols absent from this table have no filled order in the retained sample; there is no inference about
their tradability or execution quality. TWAP order type alone does not establish an opening-window order.

## Why existing infrastructure does not answer the question

`execution/twap_benchmark.py` validates complete one-minute trade closes and computes the original
intended window's duration-weighted price. It can measure signed actual-fill slippage, including delay
from approval/rescheduling, once observations exist. Its fetch path is triggered by order-analytics
requests; the analytics worker publishes retained files but does not itself create missing benchmarks.
The source `execution-benchmarks` has publication version
`c7e5a289fc7fc026f514000cfe564123c50409d69a48cba3f4e149b795a9e5a1`, zero documents/observations,
and an empty file manifest. The benchmark cache directory was also absent at the inspection.

The current minute payload records closes, not traded value and volume for a full session. It cannot
establish session VWAP. A close comparison also needs a separately pinned, identity-matched raw closing
price on the actual relevant session; an adjusted return series or an order's planning reference price
is not a replacement. No such close benchmark was bound into this retained-evidence snapshot.

When data becomes available, positive signed slippage means worse execution. Aggregate signed price
cost divided by gross benchmark notional within each currency; do not average order bps. The analyzer
uses the existing window and minute-price functions and actual execution-weighted fill prices. Fees,
funding, FX and unfilled-order opportunity cost are excluded. Comparing an actual fill with three
reference prices still does not establish what a different routing algorithm would have filled at,
including spread, impact and fill probability. Paper fills are not evidence of live execution quality.

## Next executable prerequisite: P4.19a benchmark collection and publication

1. Make post-trade benchmark collection an **app-owned, idempotent job**, independent of opening the
   blotter. Cover every eligible filled order; retain original and routed windows separately, collection
   attempts, source identity, coverage, failures, raw hashes and publication identity. Old snapshots
   remain immutable. Recover missing execution details only from retained broker evidence with the
   existing reconciliation/recovery controls; otherwise preserve them as excluded.
2. Define and audit the additional benchmark contract: raw close and complete intraday traded-value/
   volume coverage for the same decision, symbol, direction and quantity. A volume-weighted average of
   bar closes is an approximation and must not be labelled exact session VWAP. Pass new observations
   through audit/publication before a new study; operational cache validation alone is not certification
   of continuous research history. Do not substitute the delayed/incomplete recorder stream.
3. Publish coverage by instrument, decision date and style, including incomplete/unfilled intentions.
   Then freeze a new matched comparison with a common availability cohort, signed cost, timing-delay
   decomposition and clustered session uncertainty. Register any prospective execution-style experiment
   separately; benchmark collection requires no capital allocation or orders.

Keep the existing execution policy while this evidence is missing. The audit does not advance to
P4.20 or select a preferred execution style. This also follows the
[continuous research playbook](../.agents/skills/continuous-research-loop.md), whose stop condition is
“Missing benchmark comparison.” The immediate constraint is missing observations, not a failed strategy.

## Reproduction and validation

Evidence root: `var/research/execution-timing-20261011-v1/`.

- Protocol SHA-256: `a8bb77f142d5edd232004ebd2a3a51beacf3e9769a8682f69ca3b757dcaff0e4`.
- Manifest SHA-256: `d648765092b36c2df3975d89aa17b1505890212e7b317f10973893659fdb9b5a`.
- Analysis SHA-256: `334ea97a9dbeb6a4d0be07b3146f3510d85055d4bc2e4880052f4551a2f9d508`.
- `scripts/analyze_execution_timing.py --root var/research/execution-timing-20261011-v1 --verify`
  reproduces offline and leaves evidence unchanged. It verifies frozen input/source hashes and refuses
  completed-output overwrites. The saved protocol records that preflight had already found empty
  benchmark coverage; no performance outcome was inspected before the rules were fixed.
- 25 focused tests passed, including the existing TWAP benchmark tests; Ruff passed. Tests cover signs,
  gross-notional aggregation, original intent, incomplete/incorrect/future-dated benchmarks, execution
  detail conflicts, hash tampering and read-only reproduction.

No app runtime, strategy calculation, allocation, instrument admission or broker order changed.
