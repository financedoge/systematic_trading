# Expanded FR25 selection width and defensive breadth

Monthly trading on the 52 supported ETFs. The highest 2021–2024 net Sharpe on the declared grid was **0.876 at M=42, N=33** (63.46% breadth). The chosen pair was sealed before its later replay. Both historical periods had been inspected in the earlier study.

| Policy | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD | Average ETF exposure | Defensive months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Expanded 6 / 4 | calibration | 26.49% | 6.07% | 0.462 | 18.30% | 13.89 | 30,768 | 93.1% | 1 / 48 |
| Expanded 6 / 15 | calibration | 17.16% | 4.05% | 0.347 | 21.03% | 12.53 | 27,052 | 81.6% | 8 / 48 |
| IS choice 42 / 33 | calibration | 13.45% | 3.22% | 0.876 | 3.26% | 4.41 | 9,342 | 52.5% | 22 / 48 |
| Expanded 6 / 4 | later | 81.59% | 38.75% | 1.726 | 15.18% | 13.84 | 21,625 | 98.2% | 0 / 22 |
| Expanded 6 / 15 | later | 81.58% | 38.75% | 1.726 | 15.18% | 13.84 | 20,029 | 98.2% | 0 / 22 |
| IS choice 42 / 33 | later | 9.46% | 5.09% | 1.271 | 5.08% | 4.10 | 4,455 | 62.1% | 8 / 22 |

The original 14-ETF FR25 on the same warmup appears in the benchmark table. Its defensive rule fired on 8 training months, with 6 of those dates in common with the expanded proportional rule. Compare the 6/4 and 6/15 rows to isolate the switch to proportional breadth with width held constant. Compare the selected pair separately to measure the effect of searching across widths and thresholds.

The 28.57% threshold restored the training fallback frequency. Sharpe fell from 0.462 to 0.347 and drawdown deepened from 18.30% to 21.03%. In the later period both six-slot rules passed the breadth gate on every monthly date and adopted identical targets. Their primary return difference is about 0.0012 percentage points. Inherited positions, starting capital and whole-unit rounding matter at that precision, including when counting strict Sharpe guard passes.

In two of the seven extra defensive training months, May 2022 and November 2023, the legacy book returned 3.60% and 5.32% respectively, against −0.75% and 0.55% for the proportional book. These are whole-calendar-month returns including entry and exit effects at the boundary. [All seven months](extra-defensive-months-is.json).

| Policy | Period | Risky ETFs | BIL | Cash | Average risky ETF count |
| --- | --- | --- | --- | --- | --- |
| Expanded 6 / 4 | calibration | 90.4% | 2.8% | 6.9% | 5.8 |
| Expanded 6 / 4 | later | 98.2% | 0.0% | 1.8% | 6.0 |
| Expanded 6 / 15 | calibration | 81.6% | 0.0% | 18.4% | 5.0 |
| Expanded 6 / 15 | later | 98.2% | 0.0% | 1.8% | 6.0 |
| IS choice 42 / 33 | calibration | 37.8% | 14.6% | 47.5% | 21.0 |
| IS choice 42 / 33 | later | 36.0% | 26.1% | 37.9% | 25.7 |

The 42/33 choice improves training Sharpe mainly by reducing portfolio risk. Its training CAGR falls from 6.07% for 6/4 to 3.22%, outside the 0.5-point return guard. Later it averages 36.0% in risky ETFs, 26.1% in BIL and 37.9% in cash. Cash earns zero and BIL earns its audited ETF return. With the same 33-qualifier gate, the six-slot control earns 73.71% later against 9.46% for the 42-slot selection. Both enter defensive mode in eight of 22 later months. This comparison isolates width while keeping fallback dates fixed.

## What the rule counts

First count admitted ETFs with positive 126-session momentum. With fewer than N qualifiers, keep only qualifying IEF, TLT and GLD at their incoming weights, carry their cash budget through the later overlays and hold residual cash. With at least N, take the highest-ranked M qualifiers, or all qualifiers when fewer than M are available. Apply the original FR25 sizing, USD and activity overlays and final 45% cap. BIL participates under the original expanded recipe. Each monthly decision uses the prior close and fills at the next open in the primary 5 bp case.

The primary denominator is the full supported cohort. Four out of 14 gives a 28.57% rule. At 52 funds it requires ceil(52 × 4/14) = 15. The alternative denominator uses the 45–51 funds passing that day's admission checks before the momentum gate. Its threshold varies by decision. [All qualified counts and admission counts](breadth-observations.json) · [Exact fallback dates](fallback.json).

## The IS search

All 2,704 integer pairs were evaluated from January 4, 2021 through December 31, 2024 at 5 bp with monthly execution. They gave 1351 distinct target paths. 1 pairs tied at the maximum to 12 decimal places. 28 pairs were within 0.05 Sharpe of it. Ties favor breadth closest to 15, then width closest to six. IS prefix winners through 2021, 2022, 2023 and 2024 were (14, 33), (14, 33), (12, 33), (42, 33).

The near-maximum set contains 14 distinct IS target paths. Moving M or N by one while holding the other fixed gives neighboring IS Sharpes from 0.658 to 0.874.

Of the 26 training months that passed the selected breadth threshold, the width cap excluded a qualifying ETF in only 4. This limits how precisely these dates distinguish a specific large M from nearby widths.

![IS selection surface](is-surface.png)

[Frozen selection](selection.json) · [Complete compressed IS grid and prefix results](training-grid.json.gz) · [Research recipes](recipes.json) · [Protocol](protocol.json).

## Attribution to width, breadth and timing

| Policy | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6 / 28.57% of admitted | calibration | 20.45% | 4.78% | 0.392 | 22.20% | 13.02 | 28,178 |
| 6 / 28.57% of admitted | later | 81.58% | 38.75% | 1.726 | 15.18% | 13.84 | 20,592 |
| Breadth alone 6 / 33 | calibration | 22.88% | 5.30% | 0.545 | 10.58% | 9.47 | 21,547 |
| Breadth alone 6 / 33 | later | 73.71% | 35.42% | 1.778 | 11.50% | 9.40 | 14,262 |
| Width alone 42 / 4 | calibration | 11.46% | 2.76% | 0.465 | 8.47% | 5.02 | 10,461 |
| Width alone 42 / 4 | later | 12.51% | 6.69% | 1.494 | 5.08% | 3.45 | 3,794 |
| 6 / 15, dynamic 0.40 | calibration | 27.36% | 6.25% | 0.539 | 11.74% | 69.00 | 157,914 |
| 6 / 15, dynamic 0.40 | later | 52.52% | 26.08% | 1.393 | 13.09% | 81.52 | 114,887 |
| IS pair, dynamic 0.40 | calibration | 7.09% | 1.73% | 0.461 | 4.56% | 20.34 | 41,598 |
| IS pair, dynamic 0.40 | later | 10.20% | 5.48% | 1.546 | 3.79% | 20.18 | 20,675 |

The dynamic variant adopts on the monthly anchor or when the L1 distance from the last adopted target, including cash, exceeds 0.40. The chosen monthly pair also receives the same 5/10/20 bp and zero/one additional session stress cases. Across these six cases, the 6/15 rule passes the legacy comparison 0/6 in IS and 4/6 later. The selected pair passes 1/6 and 0/6, respectively. Each pass requires higher Sharpe, CAGR loss at most 0.5 percentage points and drawdown worsening at most 2 points.

| Cost (bp) | Extra sessions | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | calibration | 13.45% | 3.22% | 0.876 | 3.26% | 4.41 | 9,342 |
| 5 | 0 | later | 9.46% | 5.09% | 1.271 | 5.08% | 4.10 | 4,455 |
| 5 | 1 | calibration | 11.98% | 2.88% | 0.789 | 3.27% | 4.41 | 9,279 |
| 5 | 1 | later | 9.88% | 5.31% | 1.353 | 4.46% | 4.11 | 4,411 |
| 10 | 0 | calibration | 12.47% | 2.99% | 0.817 | 3.31% | 4.42 | 18,612 |
| 10 | 0 | later | 9.04% | 4.87% | 1.218 | 5.14% | 4.10 | 8,818 |
| 10 | 1 | calibration | 10.99% | 2.65% | 0.728 | 3.31% | 4.41 | 18,481 |
| 10 | 1 | later | 9.47% | 5.09% | 1.295 | 4.53% | 4.11 | 8,734 |
| 20 | 0 | calibration | 10.50% | 2.54% | 0.697 | 3.41% | 4.42 | 36,909 |
| 20 | 0 | later | 8.25% | 4.45% | 1.114 | 5.26% | 4.10 | 17,277 |
| 20 | 1 | calibration | 9.06% | 2.20% | 0.606 | 3.41% | 4.41 | 36,667 |
| 20 | 1 | later | 8.64% | 4.66% | 1.181 | 4.65% | 4.11 | 17,105 |

| Calendar year | Legacy return / Sharpe | Scaled return / Sharpe | Selected return / Sharpe |
| --- | --- | --- | --- |
| 2021 | 9.97% / 0.650 | 9.97% / 0.650 | 6.84% / 1.149 |
| 2022 | -8.56% / -0.439 | -11.04% / -0.767 | -0.11% / -0.978 |
| 2023 | 10.24% / 0.787 | 4.95% / 0.430 | 1.16% / 0.527 |
| 2024 | 14.11% / 1.064 | 14.11% / 1.063 | 5.09% / 1.329 |
| 2025 | 29.08% / 1.602 | 29.08% / 1.602 | 5.49% / 2.427 |
| 2026 | 40.68% / 1.873 | 40.67% / 1.873 | 3.77% / 0.859 |

| Policy vs legacy | Period | Paired 95% interval, Sharpe difference |
| --- | --- | --- |
| IS choice 42 / 33 | calibration | -0.318 to 1.152 |
| Expanded 6 / 15 | calibration | -0.379 to 0.143 |
| IS choice 42 / 33 | later | -2.120 to 1.230 |
| Expanded 6 / 15 | later | -0.000 to 0.000 |

Intervals use 4,000 paired circular 21-session block draws and are conditional on the chosen comparison. Searching 2,704 pairs on four years can inflate the best IS Sharpe. The 2025–October 2026 results measure transfer to a previously inspected period, with positions carried across the boundary. Fresh validation requires observations collected after this rule freeze.

## Same-price and friction benchmarks

| Policy | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original-monthly | calibration | 29.56% | 6.71% | 0.701 | 7.38% | 8.44 | 19,885 |
| original-monthly | later | 54.93% | 27.17% | 2.003 | 8.31% | 7.49 | 10,977 |
| m1-monthly | calibration | 18.17% | 4.28% | 0.359 | 17.86% | 14.93 | 32,044 |
| m1-monthly | later | 65.71% | 31.96% | 1.406 | 13.37% | 15.64 | 22,607 |
| momentum-monthly | calibration | 6.09% | 1.49% | 0.172 | 24.44% | 10.69 | 22,208 |
| momentum-monthly | later | 63.82% | 31.13% | 1.211 | 16.70% | 8.17 | 10,208 |
| unranked-monthly | calibration | 9.15% | 2.22% | 0.317 | 17.26% | 1.38 | 2,753 |
| unranked-monthly | later | 20.64% | 10.85% | 1.536 | 6.42% | 1.20 | 1,336 |
| cash | calibration | 0.00% | 0.00% | 0.000 | -0.00% | 0.00 | 0 |
| cash | later | 0.00% | 0.00% | 0.000 | -0.00% | 0.00 | 0 |
| BIL_buyhold | calibration | 11.79% | 2.83% | 9.875 | 0.18% | 0.25 | 500 |
| BIL_buyhold | later | 7.29% | 3.94% | 18.663 | 0.01% | 0.00 | 0 |
| URTH_buyhold | calibration | 46.00% | 9.95% | 0.679 | 26.05% | 0.25 | 500 |
| URTH_buyhold | later | 34.58% | 17.71% | 1.118 | 16.94% | 0.00 | 0 |
| pool_buyhold | calibration | 20.52% | 4.79% | 0.467 | 18.01% | 0.25 | 500 |
| pool_buyhold | later | 39.65% | 20.12% | 1.515 | 11.97% | 0.00 | 0 |

These controls use the hash-bound parent study's identical price batch, USD accounting, dates and frictions. The original14 FR25, expanded M1, momentum and unranked controls retain their specified constructions. [Parent study](../expanded-fr25-net-20261102-v1/index.html) · [All new cost/delay and annual metrics](results.json).

## Weakest held-risk contributions

The criterion is lowest actual net contribution divided by era-opening NAV for the selected monthly book, excluding BIL, cash and URTH. Daily files include adjusted OHLC, raw price and volume, current theoretical target, adopted and held weights, breadth state and fills. Protection comes from portfolio allocation and the final cap. The strategy has no intraday stop. FIFO outcomes include partial exits and final marks. [All ETF contributions](attribution.json).

### MBB in calibration

![Dated inspection](weakest-calibration-MBB.png)

[Daily state and fills](weakest-calibration-MBB-daily.csv) · [FIFO trade outcomes](weakest-calibration-MBB-trades.json)

### TLT in later

![Dated inspection](weakest-later-TLT.png)

[Daily state and fills](weakest-later-TLT-daily.csv) · [FIFO trade outcomes](weakest-later-TLT-trades.json)

## Evidence

The retained batch is e22f27a465e95f86cd40f7f9d24b63533a4a397eb0c02c8f40a696b0350d7731. Historical membership and first availability remain reconstructed. Whole adjusted units and fixed trading frictions omit measured spreads and impact. The full six-case legacy NAV paths reproduce the parent, and the selected full replay reproduces its sealed IS Sharpe. [Independent native accounting](native-validation.json) · [Evidence assessment](assessment.json).
