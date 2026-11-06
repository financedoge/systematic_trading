# ETF winner dependence and historical stability

The two FR25 6/4 portfolios derived more than half their later gains from three ETFs. The cash-withholding replays still produced positive later returns. The training stability rule selected standalone monthly Alpha54. Its gaps in CAGR and Sharpe were smaller than both 6/4 books and its return stayed positive after withholding the largest three winners in each era. Its earlier 19.33% drawdown and lower later return matter when comparing portfolio quality.

| Recipe | IS CAGR | OOS CAGR | Gap (pp) | IS Sharpe | OOS Sharpe | Gap | IS / OOS max DD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Original14 FR25 6/4 | 6.71% | 27.17% | 20.46 | 0.701 | 2.003 | 1.302 | 7.38% / 8.31% |
| Expanded FR25 6/4 | 6.07% | 38.75% | 32.68 | 0.462 | 1.726 | 1.264 | 18.30% / 15.18% |
| Monthly Alpha54 | 7.49% | 13.97% | 6.48 | 0.679 | 1.569 | 0.890 | 19.33% / 7.54% |

IS is January 4, 2021–December 31, 2024. The later chronological window runs January 2, 2025–October 30, 2026. All returns include actual whole-unit rebalances at 5 bp per traded notional and next-open execution. Sharpe uses zero as the reference rate and CAGR uses 252 sessions per year. Earlier studies inspected both periods and Alpha54 before this comparison.

## How much depended on a few ETFs?

| Portfolio | Era | Largest three contributors (pp of starting NAV) | Share of net gain | Share of positive contributions | CAGR after exclusion | Sharpe after exclusion |
| --- | --- | --- | --- | --- | --- | --- |
| Original14 FR25 6/4 | IS | DBC 9.73, SPY 9.22, XLE 7.31 | 88.9% | 67.3% | 0.60% | 0.121 |
| Original14 FR25 6/4 | OOS | EWY 14.75, GLD 10.04, XLE 7.73 | 59.2% | 58.6% | 10.63% | 1.286 |
| Expanded FR25 6/4 | IS | EWT 6.52, XLC 6.06, XLK 5.24 | 67.2% | 32.9% | 1.93% | 0.209 |
| Expanded FR25 6/4 | OOS | SOXX 18.42, USO 12.65, SLV 11.78 | 52.5% | 42.9% | 18.81% | 1.159 |
| Monthly Alpha54 | IS | EMB 5.00, EWU 3.15, USO 2.95 | 33.3% | 22.4% | 5.00% | 0.504 |
| Monthly Alpha54 | OOS | PPLT 6.10, IBB 3.59, XLB 3.28 | 48.3% | 36.3% | 7.24% | 0.974 |

| Portfolio | Era | Baseline CAGR | Top 1 removed | Top 3 removed | IS top 3 removed | SOXX & XLK removed | Also remove EWY & EWT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Original14 FR25 6/4 | IS | 6.71% | 4.30% | 0.60% | 0.60% | 6.71% | 7.06% |
| Original14 FR25 6/4 | OOS | 27.17% | 19.31% | 10.63% | 20.12% | 27.17% | 19.31% |
| Expanded FR25 6/4 | IS | 6.07% | 4.51% | 1.93% | 1.93% | 3.88% | 2.49% |
| Expanded FR25 6/4 | OOS | 38.75% | 30.10% | 18.81% | 39.63% | 32.48% | 25.66% |
| Monthly Alpha54 | IS | 7.49% | 6.34% | 5.00% | 5.00% | 7.08% | 7.27% |
| Monthly Alpha54 | OOS | 13.97% | 10.59% | 7.24% | 13.24% | 14.41% | 12.75% |

Contribution is actual net ETF P&L divided by the portfolio's opening NAV in each era. The share of positive contributions uses the sum over all positive ETF contributions before offsetting losses. The exclusion replays place the named ETFs' target weights in zero-interest cash on the entire calendar, keep the unperturbed adoption dates and other target weights, and recalculate units, costs and NAV. The later window inherits the counterfactual book's positions. The ex-post leaders are a deliberate stress. The IS-leaders column freezes the names before the later window. [Per-ETF attribution](attribution.json) · [Full cash-withholding results](withholding.json).

SOXX and XLK proxy direct semiconductor and technology-fund exposure. The regional extension removes whole Korea and Taiwan funds, including their nontechnology holdings. Broad equities can retain indirect exposure to AI. These calculations can measure portfolio dependence on named funds. Attributing common market moves to AI would require additional evidence. The future frequency of this regime remains unknown.

## How the candidate was selected

Each sleeve produces its daily prior-close target on the same 52 supported histories. FR25 combines momentum and financial ranks and retains the existing six-name selection, four-qualifier fallback, downstream risk overlays and final cap. Standalone Alpha54 uses the published adjusted-price formula, ranks eligible risky ETFs and sizes its top six by inverse volatility. The third sleeve applies inverse 63-session volatility to the full eligible risky pool. Target weights are averaged before trading so offsetting changes net within one book. All 15 combinations in 25-point steps were tested with monthly and monthly-plus-0.40 target-change timing. The event compares current theoretical and last adopted targets including cash. [Parent Alpha54 definition and formula](../alpha101-net-20261031-v1/protocol.json) · [FR25 and inverse-volatility controls](../expanded-fr25-net-20261102-v1/protocol.json).

The 2021–2022 and 2023–2024 halves were ranked on four criteria. Higher weaker-half CAGR and Sharpe reward positive performance across both halves. Smaller half-to-half changes in CAGR and Sharpe reward consistency. The rule chose the eligible candidate with the best worst rank across these criteria, breaking ties by the frozen rule. Each half had to be profitable. Training CAGR had to reach 5.57%, and drawdown could exceed expanded 6/4 by at most 2 points. Removing the candidate's three biggest training winners or imposing 20 bp and an extra session both had to leave positive training CAGR. 8 of 30 candidates qualified.

Monthly Alpha54 earned 5.34% CAGR with 0.455 Sharpe in the first half and 9.69% with 1.020 in the second. Selection used data through 2024-12-31. This is additional diagnostic evidence on a previously retained recipe. [Frozen protocol](protocol.json) · [Training search](training.json) · [Sealed choice](selection.json).

For perspective, the earlier 42/33 breadth winner had still closer point estimates (3.22% vs 5.09% CAGR and 0.876 vs 1.271 Sharpe). Its 3.22% IS CAGR falls below this study's return floor. The floor states the return trade-off explicitly. [Breadth comparison](../fr25-breadth-20261103-v1/index.html).

## Years, frictions and uncertainty

| Year | Original 6/4 CAGR / Sharpe | Expanded 6/4 CAGR / Sharpe | Alpha54 CAGR / Sharpe |
| --- | --- | --- | --- |
| 2021 | 10.09% / 0.863 | 9.97% / 0.650 | 19.79% / 2.130 |
| 2022 | 3.30% / 0.405 | -8.59% / -0.439 | -7.42% / -0.373 |
| 2023 | 8.86% / 0.906 | 10.33% / 0.787 | 5.78% / 0.617 |
| 2024 | 4.74% / 0.572 | 14.11% / 1.064 | 13.70% / 1.455 |
| 2025 | 24.30% / 1.960 | 29.34% / 1.602 | 20.81% / 2.394 |
| 2026 | 30.69% / 2.056 | 50.91% / 1.873 | 6.30% / 0.711 |

| Cost bp | Extra sessions | Era | CAGR | Sharpe | Max DD | Annual turnover | Actual fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | IS | 7.49% | 0.679 | 19.33% | 19.92 | 45,066 |
| 5 | 0 | OOS | 13.97% | 1.569 | 7.54% | 20.17 | 28,254 |
| 5 | 1 | IS | 7.30% | 0.663 | 19.74% | 19.91 | 45,272 |
| 5 | 1 | OOS | 12.72% | 1.447 | 6.61% | 20.19 | 27,575 |
| 10 | 0 | IS | 6.43% | 0.594 | 19.89% | 19.93 | 88,382 |
| 10 | 0 | OOS | 12.84% | 1.449 | 7.63% | 20.18 | 53,850 |
| 10 | 1 | IS | 6.24% | 0.577 | 20.30% | 19.92 | 88,796 |
| 10 | 1 | OOS | 11.60% | 1.329 | 6.70% | 20.20 | 52,554 |
| 20 | 0 | IS | 4.33% | 0.422 | 21.01% | 19.94 | 170,020 |
| 20 | 0 | OOS | 10.60% | 1.206 | 7.80% | 20.20 | 97,795 |
| 20 | 1 | IS | 4.15% | 0.405 | 21.42% | 19.94 | 170,863 |
| 20 | 1 | OOS | 9.38% | 1.090 | 6.87% | 20.21 | 95,443 |

| Control | IS CAGR / Sharpe | OOS CAGR / Sharpe |
| --- | --- | --- |
| alternate | -12.97% / -1.310 | -5.04% / -0.493 |
| unranked | 2.22% / 0.317 | 10.85% / 1.536 |
| momentum-monthly | 1.49% / 0.172 | 31.13% / 1.211 |
| cash | 0.00% / 0.000 | 0.00% / 0.000 |
| BIL_buyhold | 2.83% / 9.875 | 3.94% / 18.663 |
| URTH_buyhold | 9.95% / 0.679 | 17.71% / 1.118 |
| pool_buyhold | 4.79% / 0.467 | 20.12% / 1.515 |

The alternate timing row uses the same selected Alpha54 weights with monthly-plus-0.40 adoption. The separate portfolio performance guard requires higher Sharpe, CAGR loss at most 0.5 pp and drawdown worsening at most 2 pp. Alpha54 passed against expanded 6/4 in 6/6 training and 0/6 later settings, and against original 6/4 in 0/6 and 0/6. [All 66 base and friction cases](results.json).

| Portfolio | Later minus IS Sharpe, 95% interval | Later minus IS CAGR, 95% interval (pp) |
| --- | --- | --- |
| Original14 FR25 6/4 | -0.05 to 2.78 | 2.3 to 40.6 |
| Expanded FR25 6/4 | -0.09 to 2.93 | 2.4 to 73.1 |
| Monthly Alpha54 | -0.82 to 2.66 | -11.4 to 25.5 |

The intervals resample paired dates across portfolios within each era using 21-session circular blocks, 4,000 draws. Both reference comparisons' intervals for the difference in absolute gaps include zero for both metrics. The observed stability ranking could plausibly reverse. The intervals condition on the chosen candidate and observed regimes. The full strategy-search history is larger than these 30 trials. [Bootstrap results](uncertainty.json). Repeatability still needs a rule frozen before new observations arrive.

## Weakest risky ETF inspections

The selected monthly portfolio exactly reproduces the archived Alpha54 daily NAV, turnover, fees, exposure and every symbol's daily contribution, verified by the hash of the complete primary path. The original dated inspection charts and trade files therefore apply directly. The criterion is lowest net contribution divided by era-opening NAV in each era, excluding BIL, the benchmark and cash. Protection comes from selection, the target cap and cash allocation. Exits occur at adopted rebalances.

IS · EWY contributed -3.12 pp. [Inspection chart](../alpha101-net-20261031-v1/weakest-calibration-EWY.png) · [Daily prices, volume, states and fills](../alpha101-net-20261031-v1/weakest-calibration-EWY-daily.csv) · [FIFO trade outcomes](../alpha101-net-20261031-v1/weakest-calibration-EWY-trades.csv)

OOS · XLC contributed -1.70 pp. [Inspection chart](../alpha101-net-20261031-v1/weakest-later-XLC.png) · [Daily prices, volume, states and fills](../alpha101-net-20261031-v1/weakest-later-XLC-daily.csv) · [FIFO trade outcomes](../alpha101-net-20261031-v1/weakest-later-XLC-trades.csv)

## Evidence

The parent price batch is e22f27a465e95f86cd40f7f9d24b63533a4a397eb0c02c8f40a696b0350d7731. Candidate targets and published input hashes were checked before the search. Historical membership and publication availability remain reconstructed. The replay models zero cash interest and fixed trading frictions. [Inspection verification](weakest-inspections.json) · [Independent native checks](native-validation.json) · [Evidence review](assessment.json).
