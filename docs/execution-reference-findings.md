# P4.19 — Matched execution references, October 12, 2026

**Decision: retain the current execution policy.** The retrospective reference comparison is complete.
It does not establish that switching to close or VWAP execution improves realizable returns. All
allocations remain unchanged: F3 has 100% of paper capital, control revision 5, no pending change.

The application now collects full regular sessions and publishes a separate, versioned reference
audit. Thirty sessions passed the scoped consistency audit against published governed raw daily
history. This is a retrospective diagnostic contract, **not** admission of a continuous intraday
research dataset. The earlier [zero-coverage audit](execution-timing-findings.md) remains immutable.

## Matched findings

The frozen sample contains all 270 retained paper orders, 45 with filled quantity. **27 orders across
seven ETFs and five sessions** have complete execution details and all six references: original/routed
TWAP, daily close and session VWAP. The same executed quantity, side and order identity is used for
every reference. Original and routed dates coincide for all 27; some intraday windows differ.

Positive cost means the actual paper fill was worse than the reference. The denominator is gross
reference notional, about USD 196,800; buys and sells are never netted in that denominator.

| Reference | Signed price cost, USD | Signed cost, bps |
| --- | ---: | ---: |
| Original intended-window TWAP | 24.16 | 1.228 |
| Routed-window TWAP | 23.31 | 1.185 |
| Governed raw daily close | 74.22 | 3.769 |
| Full-session IB historical TRADES VWAP estimate | 186.28 | 9.471 |

The close and VWAP results are identical for original and routed dates because those dates match.
Original-minus-routed TWAP cost is USD 0.84. This is a reference-price decomposition of intraday
rescheduling and intervening market movement, not a causal estimate of an approval-delay penalty.
There are **zero** matched orders in the cross-date-delay cohort; its costs remain unavailable.

| Routed session | Orders | Routed TWAP, bps | Daily close, bps | Session VWAP, bps |
| --- | ---: | ---: | ---: | ---: |
| 2026-09-25 | 6 | 1.243 | -11.473 | 2.758 |
| 2026-10-01 | 6 | 0.277 | 41.880 | 31.914 |
| 2026-10-02 | 5 | 1.002 | -2.861 | -0.803 |
| 2026-10-05 | 6 | 3.500 | 25.785 | 13.660 |
| 2026-10-08 | 4 | 1.458 | 26.943 | 2.580 |

Leaving out one whole session at a time gives **1.017–1.429 bps** for routed TWAP,
**-6.436–31.268 bps** for close, and **3.457–21.572 bps** for VWAP. These are descriptive sensitivity
ranges, not confidence intervals. Five sessions are too few for a defensible execution-policy effect.
In particular, the close comparison changes sign when a session is omitted.

| ETF | Matched orders | Routed TWAP, bps | Daily close, bps | Session VWAP, bps |
| --- | ---: | ---: | ---: | ---: |
| DBC | 5 | 0.921 | 48.188 | 33.867 |
| EWH | 5 | 2.567 | 8.794 | 10.955 |
| EWJ | 5 | -1.700 | -34.124 | -9.186 |
| EWY | 5 | -1.310 | -36.584 | -17.203 |
| GLD | 2 | 0.282 | -2.222 | -1.993 |
| SPY | 2 | 2.728 | -17.283 | -2.354 |
| VGK | 3 | 2.108 | 50.666 | 45.993 |

This dispersion is consistent with substantial session/direction exposure in close and VWAP comparisons.
It is not an estimate of stable ETF-specific execution alpha. DBB, IWM and USO have no matched orders;
their costs are missing rather than zero. ETFs absent from retained fills were not selectively omitted.

## Exclusions and basis limitations

Eighteen filled orders lack complete execution details. Overlapping exclusions are 13 orders without
an explicit TWAP window (ten legacy TWAP and three limit orders), plus one USO and one DBB order
whose configured IB contracts are absent. Do not add these counts. No execution timestamps, prices
or windows were reconstructed. There are 225 unfilled orders; this study does not estimate their
opportunity cost or fill probability.

The app retained **34 order windows plus 30 full sessions**, all 64 later verified identical in local
storage and ClickHouse. Two further requested sessions are unavailable because of USO/DBB contract
configuration. This says nothing about XLE/XLB trading permission. Original/routed windows and
sessions deduplicate independently. Early closes use the app calendar; gaps are never filled.

The audit uses the existing 0.5% raw-price consistency threshold on all session OHLC fields. The
largest observed OHLC difference is 23.05 bps (EWH opening price); the largest daily-close versus last
IB minute-close difference is 9.12 bps (DBC). These differences alone caution against interpreting
small close-reference costs as precise exchange-auction execution effects. The close reference is
the governed raw daily close, not the last IB minute close or a certified closing-auction price.

VWAP uses per-minute WAP and provider volume, never volume-weighted minute closes. IB filters some
trade types and can round WAP; provider quantity is retained in its reported units. A common unit
scale cancels within a session, but share counts and traded dollar value are not certified. Governed
raw prices are reconstructed from reported corporate actions, not tape-certified. The governed
action vintage precedes the new IB capture; later actions are not independently covered by that
ledger. Known subsequent splits are excluded, and OHLC agreement is only a consistency check.
Retrospective auditing does not establish historical publication availability. See the
[full audit contract](execution-benchmark-collection.md).

All observations retain `research_approved: false`; the separate approval scope is retrospective
execution diagnostics only. There is no inference about live fills, counterfactual close/VWAP fills,
spread, impact, fees, FX, financing, rejected orders or future alpha capacity. P5.11 intraday data
admission and execution controls remain prerequisites for faster signals and intraday stops.

## Reproduction and validation

Frozen root: `var/research/execution-references-20261012-v1/`, captured at
2026-10-12 00:24:52 Shanghai time. It retains protocol, all orders, published documents, checked
governed inputs/manifests, original raw captures and calculation sources. The reader verified the
daily catalog and each symbol's actual published storage batch, including inherited histories.
The frozen inputs contain 62 operational documents at that instant and all 30 qualified sessions in
the separate reference publication. The remaining two operational documents arrived in its next
import; this does not alter the frozen references or result.

| Artifact | SHA-256 / version |
| --- | --- |
| Governed catalog | `b02d9372e7a53adbdb78a28d98a5b74e86ab402482091311036667d8eb9cdff4` |
| Reference audit publication | `7c91cbf9536867ade915999a431a5240fcc4810d1dff3bab7d1c3406473a4785` |
| Protocol | `165bed086e866153b9c365947a4340aa83aa79dec5c1864a2ea12820c8f4a6f1` |
| Manifest | `a6f38fa251b4652346a521d893109d28207110e0508d6ebbba3cf77a18193172` |
| Analysis | `38539a975cb310321aed5f09c121c09158d24b42d46a78cc1f29a05ca2ad5b58` |

```powershell
.venv\Scripts\python.exe scripts/analyze_execution_references.py --verify --root var/research/execution-references-20261012-v1
```

Exact frozen replay passed. The focused regression suite passed **100 tests, one disposable-ClickHouse
test skipped**; seven final analysis checks also passed after tightening the session boundary. Ruff
passed. Actual publication/readback verified all 64 captures separately. Before/after receipts and
test XML are `var/research/benchmark-qualification-20261012-*`. The app, analytics and IB gateway are
healthy; collector coverage is degraded only by the explicit legacy gaps. Orders remain 270 total /
45 filled; paper control state matches exactly.

## Next research step

Close this retrospective P4.19 item without changing execution style. Keep the app collecting future
evidence. A prospective style comparison would require a separately registered matched protocol with
session-level uncertainty, fees/impact and adequate independent sessions; do not tune timing on this
five-session sample.

Next in the agreed research programme is **P4.16d: substantial ETF-universe expansion**, beginning with
an explicit candidate inventory and comparable peer groups before any new alpha search. The requested
**P6.15 worker-resource measurements** should accompany its scale-up. The minimum P8 execution contract
remains a separate prerequisite for the conditional 5% FR25 paper allocation; this study does not
unlock it. P4.20 decay gates and actual fill-based TP/SL contracts remain part of the alpha prerequisites.
