# Class and volatility construction after trading costs

The training choice was **pooled_risk-monthly**. It earned 6.16% CAGR in training and 2.73% later. Its later Sharpe of 3.68 accompanies 12.96% average risky ETF exposure, 45.03% BIL and 42.01% cash. BIL buy-and-hold earned 3.94% later. Zero-interest cash and a zero-rate Sharpe reference matter here. The family supplies a low-risk historical allocation, with limited evidence for superior portfolio growth.

## Four monthly controls on 52 supported histories

| Recipe | IS CAGR | IS Sharpe | IS DD | Later CAGR | Later Sharpe | Later DD |
| --- | --- | --- | --- | --- | --- | --- |
| pooled_raw | -0.01% | 0.071 | 24.28% | 37.74% | 1.521 | 15.90% |
| pooled_risk | 6.16% | 0.790 | 7.08% | 2.73% | 3.684 | 0.57% |
| class_raw | 3.15% | 0.294 | 17.85% | 40.69% | 1.658 | 15.10% |
| class_risk | 1.40% | 0.195 | 18.22% | -0.05% | 0.061 | 16.18% |

Raw means the **unscaled adjusted-price return**. The risk score divides 126-session return by annualized 63-session sample volatility. Both scores require positive momentum, complete prior data and admission. Pooled selection takes up to six ETFs. Class-first selection ranks classes by the mean score of up to two eligible members, takes up to three classes, then sizes members by inverse volatility within their class budget. Overlap exclusions, empty-slot cash, 98% total budget and final 45% per-ETF cap apply. BIL competes for slots. Dividing by volatility for both ranking and sizing can favor bills. [Exact classes and overlap policy](construction.json).

With raw scores, class-first beat pooled on later CAGR and Sharpe but did so after a modest training return. With volatility-adjusted scores, class-first returned about zero later. The separate class and score comparisons depend on the other choice. [All matched effects across timing and friction](paired-effects.json).

## Selection, timing and holdings

2 of 12 challengers qualified in 2021–2024. The return floor was the higher of BIL training CAGR (2.83%) and matched pooled-raw CAGR minus 0.5 pp. Drawdown could worsen by up to 2 pp. Both training halves, the top-three withholding run and the 20 bp extra-delay run had to retain positive CAGR. The tie order favored higher weaker-half Sharpe and CAGR. The decision was sealed before later performance was calculated. [Training grid](training.json) · [Selection seal](selection.json).

| Policy | Era | Risky ETFs | BIL | Cash |
| --- | --- | --- | --- | --- |
| pooled_risk-monthly | calibration | 41.56% | 28.53% | 29.91% |
| pooled_risk-monthly | later | 12.96% | 45.03% | 42.01% |
| pooled_raw-monthly | calibration | 90.08% | 3.13% | 6.79% |
| pooled_raw-monthly | later | 97.97% | 0.00% | 2.03% |

Each timing policy has a monthly anchor. Dynamic thresholds adopt when the L1 distance from the last adopted target, including cash, strictly exceeds 0.10, 0.40 or 0.80. The later period begins January 2, 2025 and ends October 30, 2026. Each strategy carries its own positions across the boundary. All use whole adjusted units and next-open or one-session-delayed fills. Later periods were already inspected in related research.

| Recipe | IS CAGR | IS Sharpe | IS DD | Later CAGR | Later Sharpe | Later DD |
| --- | --- | --- | --- | --- | --- | --- |
| pooled_raw-monthly | -0.01% | 0.071 | 24.28% | 37.74% | 1.521 | 15.90% |
| pooled_raw-0.10 | -0.51% | 0.035 | 20.26% | 40.01% | 1.739 | 11.86% |
| pooled_raw-0.40 | 1.60% | 0.183 | 19.42% | 41.43% | 1.785 | 12.19% |
| pooled_raw-0.80 | 0.73% | 0.123 | 20.88% | 42.49% | 1.821 | 11.92% |
| pooled_risk-monthly | 6.16% | 0.790 | 7.08% | 2.73% | 3.684 | 0.57% |
| pooled_risk-0.10 | 0.92% | 0.159 | 13.00% | 2.61% | 3.758 | 0.42% |
| pooled_risk-0.40 | 2.35% | 0.340 | 11.24% | 2.73% | 3.681 | 0.57% |
| pooled_risk-0.80 | 1.61% | 0.241 | 14.20% | 2.73% | 3.678 | 0.57% |
| class_raw-monthly | 3.15% | 0.294 | 17.85% | 40.69% | 1.658 | 15.10% |
| class_raw-0.10 | 3.80% | 0.346 | 16.08% | 38.21% | 1.635 | 16.45% |
| class_raw-0.40 | 3.59% | 0.332 | 16.08% | 39.44% | 1.685 | 16.45% |
| class_raw-0.80 | 4.03% | 0.359 | 14.35% | 41.60% | 1.709 | 15.10% |
| class_risk-monthly | 1.40% | 0.195 | 18.22% | -0.05% | 0.061 | 16.18% |
| class_risk-0.10 | -0.40% | 0.003 | 12.02% | 11.73% | 0.956 | 10.57% |
| class_risk-0.40 | 0.70% | 0.122 | 13.53% | 11.47% | 0.912 | 8.43% |
| class_risk-0.80 | 2.29% | 0.287 | 15.46% | 1.55% | 0.189 | 12.13% |

## Dependence on winners and chronological stability

| Policy | Era | Three largest risky contributors (pp) | Share of positive ETF P&L | Share of net gain | CAGR, top 1 to cash | CAGR, top 3 to cash | CAGR, IS top 3 to cash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pooled_risk-monthly | calibration | XLE 4.56, DBC 3.97, EWT 3.45 | 33.8% | 44.5% | 5.13% | 3.38% | 3.38% |
| pooled_risk-monthly | later | SHY 0.57, EWY 0.41, GLD 0.31 | 23.1% | 25.6% | 2.41% | 2.02% | 2.79% |
| pooled_raw-monthly | calibration | XLC 6.38, SOXX 4.40, EWG 3.93 | 49.3% | — | -1.61% | -3.71% | -3.71% |
| pooled_raw-monthly | later | EWY 19.75, SOXX 19.68, GLD 10.84 | 58.5% | 63.5% | 28.27% | 13.44% | 27.36% |

Positive-share denominators include BIL. For net losses the net-share cell is left blank. Exclusions keep the adoption dates and other target weights, send the removed positions to cash, and recalculate fills, fees and NAV. Each era's own leaders are retrospective stresses. Both FR25 incumbents use these same current dates, prices and costs. Their verified later top-three-withheld CAGRs were 10.63% (original14) and 18.81% (expanded). [Incumbent withholding results](../etf-stability-20261103-v1/withholding.json).

| Year | Selected return / Sharpe | Control return / Sharpe |
| --- | --- | --- |
| 2021 | 17.17% / 1.333 | 8.87% / 0.580 |
| 2022 | 2.24% / 0.275 | -13.50% / -0.978 |
| 2023 | 2.79% / 2.970 | 1.66% / 0.194 |
| 2024 | 3.09% / 3.657 | 4.40% / 0.394 |
| 2025 | 3.36% / 4.685 | 35.73% / 1.821 |
| 2026 | 1.62% / 2.562 | 32.02% / 1.351 |

For the selected rule, the absolute CAGR gap is 3.43 pp and the Sharpe gap is 2.893. Assess these alongside cash and BIL exposure. The paired 21-session block intervals below compare the selected policy with pooled raw at matched timing, with Bonferroni adjustment for 12 contrasts and 4,000 draws. Earlier searches and regime uncertainty remain.

| Era | Family 95% Sharpe difference | Family 95% CAGR difference |
| --- | --- | --- |
| calibration | -0.20 to 1.70 | -7.9% to 18.7% |
| later | 0.73 to 3.77 | -106.7% to 10.2% |

## Benchmarks, costs and delay

| Recipe | IS CAGR | IS Sharpe | IS DD | Later CAGR | Later Sharpe | Later DD |
| --- | --- | --- | --- | --- | --- | --- |
| original-monthly | 6.71% | 0.701 | 7.38% | 27.17% | 2.003 | 8.31% |
| expanded-monthly | 6.07% | 0.462 | 18.30% | 38.75% | 1.726 | 15.18% |
| momentum-monthly | 1.49% | 0.172 | 24.44% | 31.13% | 1.211 | 16.70% |
| unranked-monthly | 2.22% | 0.317 | 17.26% | 10.85% | 1.536 | 6.42% |
| cash | 0.00% | 0.000 | -0.00% | 0.00% | 0.000 | -0.00% |
| BIL_buyhold | 2.83% | 9.875 | 0.18% | 3.94% | 18.663 | 0.01% |
| URTH_buyhold | 9.95% | 0.679 | 26.05% | 17.71% | 1.118 | 16.94% |
| pool_buyhold | 4.79% | 0.467 | 18.01% | 20.12% | 1.515 | 11.97% |
| Alpha54 monthly | 7.49% | 0.679 | 19.33% | 13.97% | 1.569 | 7.54% |

| Fee bp | Extra delay | Era | Net return | CAGR | Sharpe | DD | Calmar | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | calibration | 26.94% | 6.16% | 0.790 | 7.08% | 0.87 | 5.02 | 11,582 |
| 5 | 0 | later | 5.03% | 2.73% | 3.684 | 0.57% | 4.78 | 0.83 | 987 |
| 5 | 1 | calibration | 21.87% | 5.08% | 0.667 | 8.23% | 0.62 | 5.02 | 11,433 |
| 5 | 1 | later | 4.76% | 2.59% | 3.458 | 0.57% | 4.52 | 0.83 | 946 |
| 10 | 0 | calibration | 25.68% | 5.90% | 0.759 | 7.21% | 0.82 | 5.02 | 23,054 |
| 10 | 0 | later | 4.95% | 2.69% | 3.622 | 0.57% | 4.70 | 0.83 | 1,952 |
| 10 | 1 | calibration | 20.66% | 4.82% | 0.635 | 8.44% | 0.57 | 5.02 | 22,763 |
| 10 | 1 | later | 4.69% | 2.55% | 3.398 | 0.58% | 4.42 | 0.83 | 1,873 |
| 20 | 0 | calibration | 23.19% | 5.37% | 0.697 | 7.48% | 0.72 | 5.02 | 45,688 |
| 20 | 0 | later | 4.79% | 2.60% | 3.495 | 0.58% | 4.51 | 0.83 | 3,825 |
| 20 | 1 | calibration | 18.27% | 4.30% | 0.572 | 8.88% | 0.48 | 5.02 | 45,111 |
| 20 | 1 | later | 4.53% | 2.46% | 3.274 | 0.58% | 4.25 | 0.83 | 3,667 |

The selected policy passed the same-timing pooled-raw Sharpe/return/drawdown guards in 6/6 training and 0/6 later frictions. All six frictions are retained for every recipe. [Current net results](current-results.json) · [Uncertainty](uncertainty.json). The weight/forward-open-return rank correlations use 1/5/10/21/63-session endpoints inside each era. These overlapping diagnostics cannot identify a unique half-life. [Horizon results](weight-ic.json).

## Original withheld books

The 50-name October screen is a separate replay on its own published price batch and original targets. All 5,800 original daily target vectors and 4,485 adopted decisions were read from hash-verified evidence. All sixteen policies received all six cost/delay cases. Later dates end October 12 here. The current 52-name run adds supported CPER in the existing base-metals class and USO in a new commodity energy class with a DBC overlap conflict. BWX and XOP remain excluded on identity grounds. The two batches and end dates differ.

| Recipe | IS CAGR | IS Sharpe | IS DD | Later CAGR | Later Sharpe | Later DD |
| --- | --- | --- | --- | --- | --- | --- |
| pooled_raw | -0.17% | 0.058 | 26.45% | 35.62% | 1.490 | 15.82% |
| pooled_risk | 5.34% | 0.700 | 7.34% | 2.85% | 3.784 | 0.57% |
| class_raw | 3.27% | 0.319 | 17.48% | 48.06% | 1.858 | 15.10% |
| class_risk | 3.54% | 0.436 | 16.23% | 0.68% | 0.117 | 17.13% |
| FR25_frozen | 6.70% | 0.700 | 7.38% | 28.54% | 2.072 | 8.31% |
| URTH_buyhold | 9.87% | 0.678 | 25.84% | 19.59% | 1.218 | 16.83% |

[All original net results](historical-results.json) · [Target receipts](target-receipt.json) · [Both publication verifications](inputs.json). The earlier proxy-gate verdict remains historical evidence.

## Weakest risky ETF inspections

Lowest net contribution divided by era-opening NAV under the training-selected 5 bp, next-open policy. BIL, cash and URTH are excluded. Protection consists of positive momentum eligibility, overlap rules, the name cap and unused-slot cash. Fills occur at adopted rebalances with no intraday stop. Trade files contain full cross-era lots and mark open positions through the final date.

### calibration · XLB (-1.907 pp)

![Dated inspection](weakest-calibration-XLB.png)

[Daily states, volume and fills](weakest-calibration-XLB-daily.csv) · [FIFO outcomes](weakest-calibration-XLB-lots.json)

### later · LEMB (-0.118 pp)

![Dated inspection](weakest-later-LEMB.png)

[Daily states, volume and fills](weakest-later-LEMB-daily.csv) · [FIFO outcomes](weakest-later-LEMB-lots.json)

## Evidence boundary

Prices are dividend/split-adjusted. Raw price and volume support liquidity and activity checks. Cohort membership and historical dissemination remain reconstructed, and fixed costs omit measured spreads and impact. This retrospective study grants research evidence only. [Protocol](protocol.json) · [Independent native accounting](native-validation.json) · [Dossier](dossier.json) · [Assessment](assessment.json).
