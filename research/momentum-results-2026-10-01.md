# Momentum research results — 2026-10-01

**Decision for review: retain the current strategies. No candidate clears the registered evidence standard for promotion.**

The short/older-window and regime-gating variants lost return against the current monthly parent. Membership buffers saved costs but also lost return. The USD feature has a small positive increment with wide uncertainty; it remains a research question.

## Scope and evidence

- **102 Python replays:** 34 complete strategy/control portfolios × 5/10/20 bp per traded dollar. This comprises 24 additional SOTA recipes, two parent clocks, two benchmarks, two other-parent controls and four USD transfers.
- **36 native LEAN parity checks passed:** all 34 portfolios at 5 bp, plus monthly parent and weekly one-week momentum at 20 bp. The remaining cost-stress runs use the same Python accounting contract; native parity is not claimed for every cost cell.
- All three monthly parent target schedules reproduce the monitored service exactly: 129 decisions per parent, zero weight difference. USD cash, integer adjusted units, prior-close sizing and next-session-open fills are declared explicitly. USD results are not the monitored CNH-accounting return series.
- Used all 16 logical CPUs for independent Python jobs, with one numerical thread per worker. The 26-portfolio initial Python batch completed in 67.2 seconds. Native jobs used three 4 GiB containers × five CPUs within Docker’s 15.4 GiB memory limit. The service reserve remains available.
- The frozen family has 58 comparisons, including USD and six transfer slots. Primary inference uses 20,000 joint six-month calendar-block bootstrap draws; three/twelve-month sensitivities are retained. Holm correction includes unused/selected transfer slots as p=1. Transfer results are descriptive because selection used this same history.
- The 2016–2026 history and 2023 split have been examined previously. These are retrospective causal replays on audited revised price vintages, not untouched validation or fully certified historical availability.

## 1. Main comparisons

Net USD results, January 2016–September 2026. “Paired difference” is 12 × mean monthly candidate-minus-parent return; CAGR is a separate compounded measure. The cost column includes initial deployment. A negative drawdown is a loss from the previous peak.

| Monthly recipe | Net CAGR | Max drawdown | Paired difference / year | Cost bp/year | Holm p |
|---|---:|---:|---:|---:|---:|
| Current parent | 9.17% | -20.84% | — | 31.8 | — |
| A1-M: 1-week momentum | 4.17% | -21.10% | -481.0 bp | 46.7 | 0.064 |
| A2-M: 2-week momentum | 5.61% | -21.04% | -338.6 bp | 46.9 | 0.244 |
| A3-M: 1-month momentum | 7.46% | -20.84% | -165.3 bp | 43.7 | 1.000 |
| A4-M: Month 2 only | 5.99% | -21.18% | -303.5 bp | 41.6 | 1.000 |
| A5-M: Months 2–3 | 7.04% | -22.27% | -199.7 bp | 35.3 | 0.829 |
| A6-M: Short blend S | 4.89% | -21.42% | -410.8 bp | 47.4 | 0.182 |
| A7-M: Older blend L | 6.95% | -20.84% | -209.1 bp | 36.4 | 1.000 |
| A8-M: 50/50 S/L | 6.43% | -21.21% | -261.0 bp | 39.4 | 0.257 |
| B1-M: More short when trend up | 5.27% | -20.84% | -375.2 bp | 44.8 | 0.182 |
| B2-M: More short when trend down | 6.33% | -21.49% | -269.5 bp | 38.5 | 0.243 |
| B3-M: More short when right-skewed | 6.56% | -20.84% | -247.9 bp | 38.4 | 0.933 |
| B4-M: More short when left-skewed | 5.50% | -21.41% | -352.5 bp | 43.5 | 0.094 |
| C0-M: Flexible breadth, immediate | 8.30% | -20.84% | -81.9 bp | 30.6 | 0.538 |
| C1-M: Fast entry, slow exit | 8.32% | -20.84% | -81.7 bp | 26.0 | 1.000 |
| C2-M: Slow entry, fast exit | 8.41% | -20.84% | -71.2 bp | 28.5 | 0.439 |

![Monthly return and cost comparisons](momentum-experiments-2026-10-01/monthly-comparisons.png)

The current pool blends 63/126/252-session momentum. The new horizon rules replace only its trend component; the existing 20/60 relative tilt, tree and adaptive exposure layer remain. These results do not support replacing that component with the tested rules at this stage; they do not establish that short-term information is universally useless.

Descriptive split of annualized paired mean returns; both periods were previously inspected:

| Monthly recipe | 2016–2022 (84 months) | 2023–Sep 2026 (45 months) |
|---|---:|---:|
| A1-M | -390.7 bp | -649.7 bp |
| A2-M | -323.0 bp | -367.8 bp |
| A3-M | -125.5 bp | -239.7 bp |
| A4-M | -97.3 bp | -688.5 bp |
| A5-M | -97.9 bp | -389.8 bp |
| A6-M | -308.7 bp | -601.4 bp |
| A7-M | -56.1 bp | -494.5 bp |
| A8-M | -185.9 bp | -401.3 bp |
| B1-M | -283.2 bp | -546.7 bp |
| B2-M | -156.3 bp | -480.8 bp |
| B3-M | -141.8 bp | -445.9 bp |
| B4-M | -269.1 bp | -508.0 bp |
| C0-M | -61.5 bp | -120.2 bp |
| C1-M | -83.3 bp | -78.6 bp |
| C2-M | -49.4 bp | -111.9 bp |

## 2. Weekly trading and cost stress

| Weekly recipe | Net CAGR at 5 bp | Max drawdown | Paired bp/year vs weekly parent | Cost bp/year | Net CAGR at 20 bp |
|---|---:|---:|---:|---:|---:|
| parent-W: Current parent, weekly | 8.05% | -27.64% | — | 82.0 | 5.42% |
| A1-W: 1-week momentum | 3.41% | -27.64% | -445.5 | 181.8 | -2.09% |
| A2-W: 2-week momentum | 3.71% | -27.64% | -413.4 | 149.0 | -0.82% |
| A7-W: Older blend L | 6.09% | -27.64% | -189.9 | 102.2 | 2.89% |
| A8-W: 50/50 S/L | 4.62% | -27.64% | -325.6 | 136.0 | 0.43% |
| C0-W: Flexible breadth, immediate | 7.39% | -27.64% | -62.7 | 81.7 | 4.79% |
| C1-W: Fast entry, slow exit | 6.81% | -27.64% | -116.5 | 65.9 | 4.72% |
| C2-W: Slow entry, fast exit | 8.12% | -27.64% | +6.5 | 67.8 | 5.95% |

The unchanged weekly parent lost 98.6 bp/year in paired mean return relative to monthly rebalancing. Its annual cost rose from 31.8 to 82.0 bp. The 25 bp/year figure is treated as the proposed cost allowance, not a fixed fee subtraction or an agreed return hurdle.

| Monthly recipe | CAGR at 5 bp | CAGR at 10 bp | CAGR at 20 bp | 20 bp paired difference / year |
|---|---:|---:|---:|---:|
| parent-M | 9.17% | 8.83% | 8.14% | +0.0 bp |
| A1-M | 4.17% | 3.69% | 2.73% | -525.7 bp |
| A2-M | 5.61% | 5.12% | 4.14% | -383.8 bp |
| A7-M | 6.95% | 6.57% | 5.80% | -222.9 bp |
| A8-M | 6.43% | 6.01% | 5.18% | -283.8 bp |
| C0-M | 8.30% | 7.97% | 7.31% | -78.4 bp |
| C1-M | 8.32% | 8.04% | 7.48% | -64.4 bp |
| C2-M | 8.41% | 8.10% | 7.49% | -61.3 bp |

## 3. Membership symmetry and market states

C1 (fast entry, slow exit) reduced annual cost to **26.0 bp**, with net CAGR 8.32%. C2 (slow entry, fast exit) cost 28.5 bp/year and returned 8.41% CAGR. Neither beats the original parent.
C1 minus the breadth-only C0 control was +0.3 bp/year; C2 minus C0 was +10.8 bp/year. Both Holm p-values are 1.000. The timing direction is not resolved by this evidence.

| Policy | Selected-count distribution at scheduled decisions | Minimum-six override assets | Neutral fallback decisions |
|---|---|---:|---:|
| C0-M | 4: 5, 5: 7, 6: 51, 7: 39, 8: 7, 9: 2 | 0 | 18 |
| C1-M | 4: 5, 5: 7, 6: 25, 7: 51, 8: 19, 9: 4 | 0 | 18 |
| C2-M | 4: 5, 5: 7, 6: 67, 7: 31, 8: 1 | 10 | 18 |
| C1-W | 10: 3, 4: 27, 5: 23, 6: 106, 7: 203, 8: 91, 9: 24 | 0 | 84 |
| C2-W | 4: 27, 5: 23, 6: 356, 7: 67, 8: 4 | 73 | 84 |

Counts include four/five eligible-asset exceptions. “Neutral fallback” means the inherited pool filter lets the full inverse-volatility basket through when fewer than four pass; it does not move to cash. Slow-entry delays are sometimes overridden by the minimum-six rule. Held counts also include residual integer-unit positions, so they differ from selected counts.

The trend/skew hypothesis must keep the two measures separate:

| Trailing equity trend | Left skew | Neutral skew | Right skew |
|---|---:|---:|---:|
| up | 42 | 33 | 11 |
| down | 18 | 17 | 8 |

These are 129 monthly decisions. There were 17 trend-state changes and 26 skew-state changes. Upward trend coincided with left skew in 42 months and right skew in only 11. All four dynamic gates underperformed the parent; conditional cell results are descriptive and saved in the diagnostics.
The dynamic-versus-static comparison also matters: B3 exceeded the 50/50 blend by +13.1 bp/year (Holm p=1.000), but trailed the older blend by 38.9 bp/year. All twelve gate-versus-static comparisons are retained in the ledger.

## 4. USD data and predictive test

Downloaded the Fed’s revised daily broad-dollar history (5,410 dated rows, including source-missing values) and **92 ALFRED snapshots** for monthly decisions from March 2019 through October 2026. The new broad index began in February 2019. Every 21/63-observation USD change uses one complete vintage, so rebasing and historical revisions are not spliced across snapshots. Missing source values remain missing; valid-observation horizons and maximum span/staleness checks are explicit.
The snapshots passed identity, date order, positivity, coverage, staleness and level-jump checks, then were published with hash-verified analytical readback. A conservative prior-calendar-day vintage makes them available before the signal close. ALFRED supplies daily vintage evidence; independent intraday dissemination timestamps remain uncertified.
U0 uses short/older momentum and volatility. U1 adds 21/63-observation broad-dollar changes with separate shrunken coefficients per ETF. Both use the same expanding ridge model, fixed penalty, training-only standardization and bounded allocation tilt. They require 60 completed monthly labels with a strict fit-close embargo. Before eligibility, both portfolios follow the unchanged parent.

**Matched evaluation: April 2024–September 2026, 30 months.**

| Comparison | Annualized paired difference | Marginal 95% interval | Raw p | Holm p |
|---|---:|---:|---:|---:|
| U0-parent-M | +33.1 bp | [-7.3, +85.2] bp | 0.152 | 1.000 |
| U1-parent-M | +46.9 bp | [+16.5, +85.5] bp | 0.013 | 0.574 |
| U1-U0-M | +13.9 bp | [-11.4, +33.7] bp | 0.204 | 1.000 |

![USD predictive ablation](momentum-experiments-2026-10-01/usd-ablation.png)

The USD-specific result is **U1 minus U0**. U1 beating the parent alone would mix the price-model effect with USD information. The USD increment’s interval spans zero; 30 months has limited power and this history is reused. Best/worst active months and asset contributions are saved in diagnostics without removing them from the primary result.

| Parent | U0 minus parent | U1 minus parent | USD increment U1 minus U0 |
|---|---:|---:|---:|
| SOTA | +33.1 bp | +46.9 bp | +13.9 bp |
| activity | +33.6 bp | +46.7 bp | +13.1 bp |
| rolling | +36.7 bp | +50.9 bp | +14.2 bp |

Transfers preserve both recipes and fitted predictions. They are selected, correlated robustness checks on the same 30 months; no independent confirmatory p-value is claimed. The two within-transfer USD differences above are descriptive subtractions, not additional family-controlled tests.

| Bootstrap block | USD increment bp/year | Marginal 95% interval | Holm p |
|---|---:|---:|---:|
| 6 months | +13.9 | [-11.4, +33.7] | 1.000 |
| 3 months | +13.9 | [-6.4, +34.4] | 1.000 |
| 12 months | +13.9 | [-22.2, +33.8] | 1.000 |

Latest standardized USD coefficients (next-month relative return, bp per one training-standard-deviation predictor move; explanatory model diagnostics, not current trade advice):

| ETF | USD21 coefficient | USD63 coefficient |
|---|---:|---:|
| DBC | -4.5 | -27.0 |
| EWH | -41.3 | -20.8 |
| EWJ | +16.6 | -7.1 |
| EWY | -28.3 | -11.4 |
| GLD | -0.6 | +22.5 |
| HYG | +20.4 | +1.3 |
| IEF | +3.0 | +5.6 |
| LQD | +5.2 | +11.4 |
| MCHI | -13.5 | -9.3 |
| SPY | +40.1 | -11.4 |
| TLT | -12.0 | +12.3 |
| VGK | +5.8 | +16.2 |

Full historical CNH translation remains unavailable for this new study: the older USD/CNH/CNY legacy input is explicitly uncertified and was excluded. This does not change the user’s accepted unhedged exposure. Broad-dollar prediction and USD/CNH translation remain different questions.

## 5. Benchmarks, risk and limits

| Portfolio | CAGR | Volatility | Sharpe (zero cash return) | Max drawdown |
|---|---:|---:|---:|---:|
| Current parent, monthly | 9.17% | 9.81% | 0.946 | -20.84% |
| Monthly inverse volatility | 5.73% | 7.90% | 0.747 | -22.46% |
| URTH buy and hold | 12.68% | 16.92% | 0.792 | -33.54% |

Fixed calendar stresses (net USD holding-period returns):

| Portfolio | 2018 | Feb–Apr 2020 | 2022 |
|---|---:|---:|---:|
| parent-M | -3.01% | -0.43% | -15.89% |
| A1-M | -4.68% | -2.04% | -15.89% |
| A7-M | -3.35% | -3.48% | -15.89% |
| C1-M | -2.86% | -4.54% | -15.89% |
| C2-M | -3.82% | -2.39% | -15.89% |
| risk-M | -3.89% | -4.39% | -14.15% |
| urth | -8.41% | -11.47% | -17.78% |

**Inherited risk-contract issue:** the 45% setting constrains the inverse-volatility base before pool reallocation; it is not a final portfolio cap. The unchanged monthly parent reached 54.68% held weight, with 258 sessions above 45%. The weekly parent reached 61.52%. No cap was weakened for these tests. A final-weight cap requires a separately versioned control and review; these replays must not be described as satisfying a hard 45% portfolio limit.
Parent features deliberately retain their audited split-adjusted price/source-volume basis, so frozen models keep their original meaning. The activity parents are legacy price×volume proxies, not measured ETF flows or audited raw traded-dollar activity. Raw ETF fields were available and checked; no new raw activity feature was introduced.
Daily NAV/cash reconcile to integer fills and fees. Asset PnL sums reconcile to terminal NAV. Full daily exposures, asset contributions, annual costs, holdings counts, stress periods and all comparison signs are retained. Cents rounding, instant settlement, zero cash interest, no spread/market-impact model and whole adjusted units limit economic realism. Fixed-bp costs are scenarios; no capacity claim follows.
Percentile intervals are marginal; centered two-sided bootstrap p-values and Holm correction are reported separately. They need not be exact duals in a skewed finite sample. Circular blocks assume a useful degree of stationarity; no guaranteed coverage or complete accounting of unknown earlier research trials is claimed.

## 6. Review decision and next work

1. Keep the monitored strategies and current monthly horizon blend. Do not combine losing variants or widen the parameter search on this evidence.
2. Retain both membership directions as documented cost/return trade-offs. C1 comes closest to the proposed annual cost allowance, but has lower net return here. A cost-only mandate would need an explicit objective.
3. Retain the USD pair for discussion. Its consistent small increment is encouraging enough to preserve the hypothesis, but falls short of the family-adjusted evidence standard. Any new forward observation starts at a new dated freeze; no prospective performance is claimed in this report.
4. Resolve the final-weight risk contract before promotion work, and define an economic improvement hurdle separately from the 25 bp/year cost allowance. Obtain audited historical USD/CNH if a full historical CNH bridge is needed.
5. No new combined model, learned regime selector, paper promotion or extra parameter grid was launched. Broker/execution settings and monitored definitions remain unchanged.

## 7. Reproduction and retained failures

Full local artifact root: `D:\projects\systematic_trading\var\research\momentum-20261001-v1b`. Price batch: `7a5b3b7d442f3be171d73327a3d92769b7ae3510a45f76d872ecdb073fee7d57`. USD batch: `ddb5624ba023c71b9ca41ff0571318eb48f390ad4131ab20858d7eaafdae006b`.
Files include immutable input/model/source hashes, daily features, complete decisions/rationales, targets, fills, daily NAV/cash, final holdings, fitted USD model coefficients, all cost runs and native receipts. Summary JSON and the registered protocol are next to this report’s charts.
Engineering failures were retained: an interrupted initial input preparation; a native adapter import that pulled unavailable database dependencies into the isolated container; one later native parent-weekly run that stalled and was stopped. The corrected adapter and the identical weekly bundle replay passed parity. None of these retries changed a recipe or count as fresh statistical evidence.
A selection-script error initially omitted U0/U1 despite their now-published prerequisite. The prior empty selection and a correction note are preserved. Applying the original frozen rule selected U1 and U0; no criterion or model parameter was changed. Transfers are descriptive regardless of that correction.
Validation: 48 relevant tests passed, one PostgreSQL-dependent integration test skipped; focused checks cover causal prefixes, exact horizons, mirrored gates, membership counters/floors, holiday clocks, USD vintage identity, training embargo, heterogeneous coefficients, sizing/fees and multiple-testing calculations.

Commands (use a fresh input/output root for a new immutable study; do not overwrite this run):

```powershell
.venv/Scripts/python.exe scripts/prepare_momentum_research.py --root <fresh-root>
.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage features --workers 16
.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage python --workers 16
.venv/Scripts/python.exe scripts/collect_usd_index.py
.venv/Scripts/python.exe scripts/publish_usd_index.py --root <fresh-usd-batch>
.venv/Scripts/python.exe scripts/run_usd_momentum_research.py --root <fresh-root>
.venv/Scripts/python.exe scripts/analyze_momentum_research.py --root <fresh-root>
.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage transfer --workers 16
.venv/Scripts/python.exe scripts/run_usd_momentum_transfers.py --root <fresh-root>
.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage native --workers 3
.venv/Scripts/python.exe scripts/analyze_momentum_research.py --root <fresh-root>
```

Data sources: [Fed H.10 history and release policy](https://www.federalreserve.gov/releases/h10/about.htm), [Fed methodology/rebasing changes](https://www.federalreserve.gov/releases/h10/h10_technical_qa.htm), [ALFRED vintage history](https://alfred.stlouisfed.org/series?seid=DTWEXBGS), [vintage-date definition](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html). Earlier paper sources and firsthand notes remain in the [reference library](references/README.md).
