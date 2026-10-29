# BroadTrend / FR25 70/30 comparison — 2026-10-29

[Full report and 51 ETF inspectors](../research/broadtrend-fr25-20261029-v1/index.html)
· [Versioned BroadTrend specification](broadtrend-strategy-v1.md).

The operator requested full-pool monitoring and a 70% FR25 / 30% full-pool test.
BroadTrend is the named full-pool strategy. Its monitoring registration does not
fund it. The 70/30 mix reduces risk but **does not improve the tested portfolio
under the predeclared Sharpe/return/drawdown comparison**. Preserve the current
funded allocation.

Common cash anchor 2024-01-31, first fills 2024-02-01, final mark 2026-10-12.
USD adjusted fractional units, zero cash interest, 5 bp per side and next-open
fills. Both strategies retain cash and shares between monthly capital resets.
BroadTrend still executes its own daily signals. Same-ETF changes are netted
across the two books before exchange fees; no daily70/30 capital rebalance or
average of terminal returns is assumed.

| Portfolio | Net return | CAGR | Sharpe | Annual volatility | Maximum drawdown | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| 100% FR25 | 62.89% | 19.95% | 1.649 | 11.43% | 8.64% | 2.308 |
| 70% FR25 / 30% BroadTrend | 47.94% | 15.72% | 1.640 | 9.16% | 7.66% | 2.051 |
| 100% BroadTrend | 17.50% | 6.20% | 1.147 | 5.37% | 6.10% | 1.015 |

Primary blend: volatility falls19.8%, drawdown falls0.98pp, CAGR loses4.23pp.
Average invested capital falls97.9%→84.1%. Average held names rises5.97→28.57,
but effective invested breadth is4.97→7.03. Component daily correlation is.677;
FR25 contributes approximately86.5% of the constant70/30 covariance risk.
Net annual costs44.86→48.55bp, gross turnover8.97→9.71 times capital. More trades
are not rejected by a cost ceiling; their actual net return does not justify the
mix under the stated guardrails.

Annual block returns FR25/blend: Feb–Dec2024 4.67%/3.56%;2025 24.06%/19.56%;
2026throughOct12 25.44%/19.49%. The blend gives up return in each block.
At10/20bp next-open Sharpe is1.587/1.479, againstFR25 1.610/1.529. One extra
session gives1.594vs1.609 at5bp. The monthly mix passes0/6 comparisons requiring
higher Sharpe, no more1pp CAGR loss and no more2pp drawdown worsening.

Explicit dynamic control: monthly OR cash-inclusive theoretical-target L1≥.10,
compared with the last actually adopted target, with one pending instruction.
This may update FR25 target adoption too; it is not a pure capital-drift test.
At5bp it returns47.92%, Sharpe1.634, drawdown7.60%, with125capital resets versus33,
and50.65bp annual costs. It also passes0/6. No threshold or allocation-weight
search was performed after evaluation.

A paired circular21-session bootstrap,1000draws,seed2910 yields descriptive95%
blend-minus-FR25 intervals: Sharpe[−.159,+.144], CAGR[−7.47,−1.35]pp. It resamples
realized daily returns rather than replaying decisions; it is not selection-
adjusted inference. Comparable frozen FR25 targets endOct12 and do not establish
an earlier regime test. Both periods and single-ETF models were repeatedly
inspected. These are development results, not prospective confirmation.

Weakest actual contributors: BroadTrend TLT−.418pp, CORN−.294pp, INDA−.239pp;
blend LQD−1.092pp, TLT−1.009pp, CORN−.096pp. The report defaults to TLT and offers
a dedicated LQD button, all51ETF OHLCV/state/stop/trade charts, date hover and
two-click zoom. Portfolio fills are distinct from continuing shadow trades.

Pre-evaluation protocol SHA-256:
`c548532a35a805a3ab3a992dc113933152d3a3ed201bb4952f100c19b6bf78fb`.
24portfolio/friction cases reconcile against an independent cash/share ledger.
Matched standalone FR25 and BroadTrend controls reproduce prior results;
published price arrays agree exactly. Two native Windows fixtures agree with
the app whole-share reference to$0.00; their execution-open oracle checks
accounting only, not independent policy inference or fractional execution.

The useful follow-up is prospective monitoring and matched-risk/cash controls,
not declaring the full pool globally optimal or implementing the blend as an
approved trading allocation.
