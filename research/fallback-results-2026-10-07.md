# ETF fallback research — 2026-10-07

**Retain the active strategy for now. Cash-aware fallbacks merit further validation as drawdown controls; this study does not establish incremental return or promotion readiness.**

Implemented and tested the first roadmap batch against the active rolling one-year XGBoost + ETF activity lag-20 + USD strategy. Only the branch with fewer than four ETFs passing the positive 252-session momentum gate changes. Ordinary decisions, model schedules, execution clock and universe are held fixed. The three challengers are complete versioned research definitions, not new monitored or funded strategies.

## Results

January 4, 2016–October 6, 2026; USD accounting; 5 basis points per traded dollar; whole adjusted units; prior-close sizing and next-session-open execution. Cash earns zero in every comparison. Sharpe uses a zero reference rate; Calmar is CAGR divided by absolute maximum drawdown. These are simulated returns on audited revised price vintages, not account returns or an untouched validation sample.

| Policy | CAGR | Sharpe | Calmar | Max drawdown | Average cash |
|---|---:|---:|---:|---:|---:|
| F0: existing full-basket fallback | 9.78% | 0.978 | 0.443 | -22.10% | 2.78% |
| F1: qualifying incoming weights, residual cash | 9.70% | 1.034 | 0.572 | -16.98% | 13.59% |
| F2: all cash below four qualifiers | 9.92% | 1.058 | 0.604 | -16.42% | 15.45% |
| F3: qualifying IEF/TLT/GLD incoming weights, residual cash | 9.93% | 1.058 | 0.605 | -16.42% | 14.49% |
| URTH buy and hold benchmark | 12.83% | 0.801 | 0.383 | -33.54% | 1.32% |

F1 is the predeclared primary challenger. Its annual return is approximately 8 basis points lower than the parent, while its drawdown is about 5.1 percentage points smaller. F2 and F3 have nearly identical aggregate results; the additional defensive selection rule has not earned a clear advantage. None is promoted by this report.

The cash rule is applied in the shared strategy pipeline. Later tree, momentum, adaptive, activity and USD layers cannot restore pool-rejected assets or exceed the reduced invested budget. Further reductions tighten that budget. Missing features or an incomplete input universe cause a calculation failure, not an instruction to liquidate. The original neutral fallback remains the default for existing definitions.

![Portfolio value and drawdown](fallback-experiments-2026-10-07/comparison.png)

## Only three episodes drive the comparison

The active baseline has **18 fallback decisions out of 130**, concentrated in three contiguous episodes. These are the newly measured active-strategy counts. Calendar-month compounded returns across each episode include transition-day overnight exposure, execution costs and the prior portfolio until the sale fills; consequently an all-cash target need not produce exactly zero realized return in a transition month.

| Fallback episode | Decisions | Parent F0 | F1 | F2 | F3 |
|---|---:|---:|---:|---:|---:|
| Jan–Mar 2016 | 3 | +3.82% | +0.19% | 0.00% | +0.66% |
| Nov 2018–Jan 2019 | 3 | +3.70% | -0.67% | +0.22% | +0.32% |
| May 2022–Apr 2023 | 12 | -8.59% | -2.46% | -1.03% | -1.68% |

Cash avoided much of the third episode's loss and missed gains in the other two. It also missed some early-2023 recovery: over the retrospective 2023-onward split, parent Sharpe is 1.597 versus 1.497/1.513/1.503 for F1/F2/F3. Monthly re-entry and the three-to-four-qualifier discontinuity remain unchanged.

F2 spends 372 sessions at least 95% in cash, with a longest uninterrupted spell of 250 sessions. F1 records 124 sessions, longest 75; F3 records 211, longest 127. Maximum time below a prior portfolio peak falls from 733 sessions for F0 to 629/501/510 for F1/F2/F3. These are distinct path measures; cash duration is not drawdown duration.

## Robustness and limits

The finite batch contains 19 Python replays: four policies and URTH at 5/10/20 basis points, plus the four policies with an additional execution-session delay at 5 basis points. All four primary portfolios passed native LEAN execution/accounting parity. The native adapter consumes frozen target schedules; separate shared-strategy target replay reproduced the published parent exactly, with **zero difference on all 130 dates**. Every non-fallback challenger decision also matches F0.

| Sensitivity | F0 Sharpe / Calmar | F1 | F2 | F3 |
|---|---:|---:|---:|---:|
| 10 bp | 0.946 / 0.423 | 1.002 / 0.534 | 1.026 / 0.572 | 1.027 / 0.574 |
| 20 bp | 0.881 / 0.385 | 0.938 / 0.467 | 0.963 / 0.499 | 0.963 / 0.501 |
| One extra session delay, 5 bp | 0.973 / 0.456 | 1.034 / 0.667 | 1.059 / 0.685 | 1.060 / 0.686 |

Annual turnover, defined as total absolute traded notional divided by portfolio value, declines from 6.53 times for F0 to 6.03/5.95/5.99. Cost and delay sensitivities retain the drawdown advantage, but do not create independent evidence: they reuse the same three episodes.

Joint calendar-block bootstrap inference uses 20,000 replications and three predeclared candidate-minus-parent comparisons. Six-month blocks give annualized paired mean differences of -0.16%, +0.04% and +0.05%, with respective 95% intervals of [-2.42%, +2.69%], [-2.19%, +3.02%] and [-2.17%, +2.98%]. All Holm-adjusted p-values are 1.00. Three- and twelve-month block sensitivities also include zero. These intervals concern paired mean returns, not significance tests of Sharpe or Calmar. No statistical superiority of either ratio is claimed.

Remaining limitations:

- The lower exposure itself may explain much of the drawdown improvement. A separately frozen, exposure-matched baseline control remains necessary to attribute gains to asset selection. No independent alpha claim is made.
- Cash interest is zero, not reconstructed historical IB remuneration. Treasury-bill returns must not be substituted for broker cash interest. USD cash still has currency risk for a CNH investor; historical uncertified USD/CNH inputs are excluded here.
- Audited prices are revised dividend/split-adjusted OHLC. Historical availability is not fully certified. Existing split-adjusted source volume is retained to reproduce the parent and is not a new raw activity or fund-flow measurement.
- The inherited 45% base cap is not a final holdings cap. Maximum realized single-ETF weights are 55.09% for F0 and about 53.65% for the challengers. This study does not solve that separate constraint problem.
- The post-2023 period has already been inspected. Future paper observations, final concentration constraints, cash treatment and wider stress evidence are still required before promotion.

## Data and execution receipts

All research inputs came from the published audited continuous histories, pinned to price batch `9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e` and tracked baseline revision `f37f34dddade4342e7fa2f8dcb3d38a45578b953427ecafafc4852a09cffbfe1`. The existing published dollar-index snapshots and frozen model schedules were verified; no online price archive was used as a research input. The exact source snapshot, strategy definitions, inputs, targets, fills, daily cash/NAV, final holdings, model cards and hash receipts are in `var/research/fallback-20261007-v1/`.

Independent calculation jobs used **16 Python workers**; the decision and 19-replay phase completed in 8.30 seconds. Native checks used three memory-bounded lanes with **6/5/5 CPU allocations**, 4 GiB each, and completed in 56.54 seconds. Capacity is available across independent jobs; serial and I/O phases do not imply continuous full utilization. Production scheduling defaults are separate.

The reproducible entry point is `scripts/run_fallback_research.py`: `prepare`, `calculate`, `native`, `analyze`, each with `--root`. A new preparation creates an immutable study; calculations consume its frozen application source. Existing output roots must not be overwritten. Individual frozen USD bundles can also be replayed by the saved `momentum_replay` adapter. Registration preceded return inspection; the only runner correction was the required `monthly` cadence name before any decisions or returns were calculated.

Focused regression coverage includes weak breadth from zero to three qualifiers, normal allocation at four, re-entry reset, incomplete data, downstream cash protection, definition serialization, live/backtest contracts and undefined Sharpe for a constant all-cash path.

## Next batch: recorder before new research data

F4 has **not** been backtested: neither BIL nor SGOV has an admitted history in the current published catalog. Choose and freeze one eligible bill vehicle and its cap, implement its application-owned recorder, audit/publish its supported histories, expose it in Market Data, then run the parking comparison. No provider download alone qualifies it.

Apply the same sequence to each macro/sector source: recorder → preserved original releases and revisions → audited publication and coverage → Market Data inspection → frozen features → backtest. Store observation date, release/availability time, ingestion time, revision/vintage, identity, units, raw-source hash and quality flags. Expand the page's categories to economic and industry data as these feeds arrive. No new source was necessary for F0–F3, and this batch created no new recorder or data-page entry.

The next research registration should also isolate final-weight limits and include exposure-matched controls. The larger ETF/macro/sector program remains in [the roadmap](../docs/etf-research-expansion-roadmap.md). Strategy selection, monitoring membership, capital allocation and execution authority remain subject to their existing separate contracts.
