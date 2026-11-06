# Expanded-pool FR25 net replay — November 2, 2026

Expanded FR25 does not establish robust net superiority over the matched controls across both eras. Retain the completed numerical study as research evidence; no recipe is promoted.

**Completed 144 cost/delay cases. Training-selected expanded policy: expanded-monthly.** 52 supported histories from 54 candidates. Both eras are previously inspected historical evidence. The later period cannot select or rescue a recipe.

## Main comparison

All three recipes below use the expanded recipe's training-selected timing to isolate recipe differences. Net USD1m replay,5bp per traded notional, next-open fills. Original14 is freshly refitted on the same warmup; it is distinct from the app's longer-warmup incumbent evidence.

| Recipe | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Expanded FR25 | calibration | 26.49% | 6.07% | 0.462 | 18.30% | 13.895 | 30,768 |
| Original14 FR25 | calibration | 29.56% | 6.71% | 0.701 | 7.38% | 8.438 | 19,885 |
| Expanded M1 | calibration | 18.17% | 4.28% | 0.359 | 17.86% | 14.928 | 32,044 |
| Expanded FR25 | later | 81.59% | 38.75% | 1.726 | 15.18% | 13.841 | 21,625 |
| Original14 FR25 | later | 54.93% | 27.17% | 2.003 | 8.31% | 7.491 | 10,977 |
| Expanded M1 | later | 65.71% | 31.96% | 1.406 | 13.37% | 15.640 | 22,607 |

![Net portfolio and drawdown comparison](comparison.png)

## Decision flow and mathematical definitions

Published audited price/raw-volume and macro vintages → complete common calendar from 2018-08-24 → prior253 observations and raw-dollar/duplicate admission → M1 or FR25 ranks → positive126-session gate → top6/minimum4, otherwise qualifying IEF/TLT/GLD weights plus cash → original inverse-volatility base and rolling-XGBoost/relative/adaptive/activity/USD sizing → final45% target cap, excess cash → monthly or target-change adoption → delayed next-open whole adjusted-unit fills → fees and daily net NAV.

M1 combines 75% momentum and25% volume score. Momentum combines ranked21/63/126-session returns with20%/35%/45% weights. FR25 combines75% M1 midrank and25% financial total-return forecast midrank. The financial forecast is a per-ETF standardized expanding ridge (alpha1, minimum36 completed monthly labels) on eight features from five published financial series. Missing financial inputs revert the whole selector to M1. XGBoost has zero selector weight and retains its downstream sizing role. [Exact versioned definitions](definitions.json) retain every overlay parameter.

Original14 and expanded FR25 share the same common price warmup and model fitting schedule. Expanded M1 changes only the financial selector and retains every downstream layer and the final cap. Expanded BIL can compete, preserving the original expansion recipe. Simple momentum ranks126-session returns; it and the unranked inverse63-vol control exclude BIL from risky ranks and share98% budget/final45% cap/admission. Admission never forces allocation. Cash, BIL, URTH and full risky-pool initial equal-weight buy-and-hold remain references.

Dynamic adoption uses strict L1 target distance >0.10/0.40/0.80 versus the last adopted target, including cash, plus monthly first-session adoption. Actual held drift does not trigger it. Models refit monthly. Financial forecasts retain the causal monthly source date. USD uses an exact published snapshot where available, otherwise the previous month with a35-day limit. These explicit carries do not invent daily macro data. [Macro readiness and carry counts](macro-coverage.json).

## Timing, costs and execution delay

| Expanded timing | Training return / Sharpe | Later return / Sharpe | Training / later turnover |
| --- | --- | --- | --- |
| monthly | 26.49% / 0.462 | 81.59% / 1.726 | 13.895 / 13.841 |
| 0.10 | 15.99% / 0.332 | 53.11% / 1.408 | 85.709 / 93.553 |
| 0.40 | 16.12% / 0.335 | 53.16% / 1.405 | 73.344 / 80.246 |
| 0.80 | 24.00% / 0.449 | 45.04% / 1.221 | 43.198 / 45.641 |

| Cost bp | Extra delay | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | calibration | 26.49% | 6.07% | 0.462 | 18.30% | 13.895 | 30,768 |
| 5 | 0 | later | 81.59% | 38.75% | 1.726 | 15.18% | 13.841 | 21,625 |
| 5 | 1 | calibration | 20.58% | 4.80% | 0.384 | 18.11% | 13.900 | 29,927 |
| 5 | 1 | later | 85.16% | 40.24% | 1.759 | 15.74% | 13.824 | 20,699 |
| 10 | 0 | calibration | 23.04% | 5.34% | 0.417 | 18.84% | 13.899 | 60,713 |
| 10 | 0 | later | 79.36% | 37.82% | 1.691 | 15.31% | 13.846 | 41,808 |
| 10 | 1 | calibration | 17.29% | 4.08% | 0.338 | 18.82% | 13.904 | 59,058 |
| 10 | 1 | later | 82.91% | 39.31% | 1.726 | 15.87% | 13.828 | 40,014 |
| 20 | 0 | calibration | 16.43% | 3.89% | 0.326 | 19.89% | 13.908 | 118,211 |
| 20 | 0 | later | 75.00% | 35.97% | 1.621 | 15.58% | 13.854 | 78,125 |
| 20 | 1 | calibration | 10.98% | 2.65% | 0.247 | 20.89% | 13.913 | 115,026 |
| 20 | 1 | later | 78.47% | 37.44% | 1.659 | 16.14% | 13.837 | 74,774 |

The selected policy maximizes2021–2024 primary net Sharpe only. Guards require strictly higher Sharpe, CAGR loss no more than0.5pp and drawdown worsening no more than2pp. Six cases span5/10/20bp and zero/one extra session; they are sensitivity cases, not independent discoveries. No cost ceiling or IC veto applies.

| Control | Training guard passes | Later guard passes |
| --- | --- | --- |
| original-monthly | 0/6 | 0/6 |
| m1-monthly | 6/6 | 2/6 |
| momentum-monthly | 6/6 | 6/6 |
| unranked-monthly | 4/6 | 0/6 |
| cash | 0/6 | 0/6 |
| BIL_buyhold | 0/6 | 0/6 |
| URTH_buyhold | 0/6 | 6/6 |
| pool_buyhold | 0/6 | 0/6 |

| Reference | Period | Net return | CAGR | Sharpe | Max DD | Turnover/yr | Fees USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| momentum-monthly | calibration | 6.09% | 1.49% | 0.172 | 24.44% | 10.688 | 22,208 |
| momentum-monthly | later | 63.82% | 31.13% | 1.211 | 16.70% | 8.174 | 10,208 |
| unranked-monthly | calibration | 9.15% | 2.22% | 0.317 | 17.26% | 1.384 | 2,753 |
| unranked-monthly | later | 20.64% | 10.85% | 1.536 | 6.42% | 1.198 | 1,336 |
| cash | calibration | 0.00% | 0.00% | 0.000 | -0.00% | 0.000 | 0 |
| cash | later | 0.00% | 0.00% | 0.000 | -0.00% | 0.000 | 0 |
| BIL_buyhold | calibration | 11.79% | 2.83% | 9.875 | 0.18% | 0.251 | 500 |
| BIL_buyhold | later | 7.29% | 3.94% | 18.663 | 0.01% | 0.000 | 0 |
| URTH_buyhold | calibration | 46.00% | 9.95% | 0.679 | 26.05% | 0.251 | 500 |
| URTH_buyhold | later | 34.58% | 17.71% | 1.118 | 16.94% | 0.000 | 0 |
| pool_buyhold | calibration | 20.52% | 4.79% | 0.467 | 18.01% | 0.251 | 500 |
| pool_buyhold | later | 39.65% | 20.12% | 1.515 | 11.97% | 0.000 | 0 |

Independently training-selected controls below are additional diagnostics; the main comparison remains matched timing. Their complete six-case metrics are retained in [all results](results.json).

| Model | Training-selected timing |
| --- | --- |
| expanded | monthly |
| m1 | monthly |
| momentum | 0.80 |
| original | monthly |
| unranked | 0.40 |

## Chronological stability and uncertainty

| Year | Expanded return / Sharpe | Original14 return / Sharpe | M1 return / Sharpe |
| --- | --- | --- | --- |
| 2021 | 9.97% / 0.650 | 10.09% / 0.863 | 5.61% / 0.417 |
| 2022 | -8.56% / -0.439 | 3.29% / 0.405 | -6.22% / -0.315 |
| 2023 | 10.24% / 0.787 | 8.79% / 0.906 | 8.19% / 0.690 |
| 2024 | 14.11% / 1.064 | 4.74% / 0.572 | 10.30% / 0.807 |
| 2025 | 29.08% / 1.602 | 24.09% / 1.960 | 33.75% / 1.818 |
| 2026 | 40.68% / 1.873 | 24.85% / 2.056 | 23.90% / 1.134 |

Training-prefix policy choices for2021/22/23/24: monthly, 0.10, 0.80, monthly. [Full prefix metrics](training-stability.json). [All constituent attribution](attribution.json) exposes both recipes' asset dependence. [Every ETF fresh-era buyhold reference](individual-buyhold.json) uses fractional units and one5bp entry fee, unlike the whole-unit portfolio replay.

| Period | Control | Family95% Sharpe difference | Family95% CAGR difference |
| --- | --- | --- | --- |
| calibration | original-monthly | -1.155 to 0.672 | -13.20% to 13.38% |
| calibration | m1-monthly | -0.248 to 0.494 | -3.68% to 7.79% |
| calibration | momentum-monthly | -0.374 to 1.035 | -6.58% to 16.36% |
| calibration | unranked-monthly | -1.011 to 1.272 | -9.92% to 19.40% |
| later | original-monthly | -1.669 to 1.384 | -19.37% to 60.26% |
| later | m1-monthly | -0.509 to 1.303 | -17.82% to 30.83% |
| later | momentum-monthly | -0.573 to 1.907 | -28.93% to 41.58% |
| later | unranked-monthly | -1.600 to 1.988 | -5.49% to 85.90% |

Paired circular21-session bootstrap,4000 draws, seed20261102. Family intervals cover16 declared expanded-policy/control contrasts using Bonferroni tails. They are approximate: dependence, regimes, small tail samples and the much larger prior strategy search remain. They do not restore an untouched holdout or implement Dwork et al.'s formal reusable-holdout method.

| Period | Forward sessions | Rank IC | Block95% interval |
| --- | --- | --- | --- |
| calibration | 1 | 0.006 | -0.010 to 0.021 |
| calibration | 5 | -0.018 | -0.046 to 0.010 |
| calibration | 10 | -0.021 | -0.061 to 0.019 |
| calibration | 21 | -0.016 | -0.071 to 0.035 |
| calibration | 63 | 0.023 | -0.044 to 0.089 |
| later | 1 | 0.031 | 0.007 to 0.055 |
| later | 5 | 0.040 | -0.011 to 0.089 |
| later | 10 | 0.043 | -0.022 to 0.107 |
| later | 21 | 0.056 | -0.021 to 0.128 |
| later | 63 | 0.136 | 0.043 to 0.216 |

Forward next-open gross rank IC is a diagnostic. Horizons1/5/10/21/63 were declared before results and labels end inside each era.1000 block draws estimate uncertainty;21-session blocks can understate63-session label dependence. No exponential half-life is identified from these return-horizon curves. Annual net contrasts and cost/delay behavior remain the portfolio evidence. [Full diagnostics](signal-diagnostics.json).

## Weakest risky ETF inspections

Criterion: lowest actual net contribution divided by era-opening portfolio NAV, under the selected expanded policy at5bp/next-open, excluding BIL/URTH/cash. This measures actual portfolio damage with changing allocations, rather than standalone ETF return. Charts include dated adjusted prices, audited raw volume, fills, theoretical/adopted/held weights and contributions. Protection is allocation-based positive-momentum eligibility, defensive cash fallback and a45% target cap; there is no intraday stop. Held weights can drift. [All FIFO outcomes](trade-outcomes.csv) reconcile to full net P&L.

### calibration: EWC, -5.06 pp

![Dated inspection](weakest-calibration-EWC.png)

[Daily prices, raw volume, weights, states and fills](weakest-calibration-EWC-daily.csv) · [FIFO outcomes](weakest-calibration-EWC-trades.csv). Whole cross-era lots and final open marks are included; their sum is not the era contribution.

### later: XLK, -5.61 pp

![Dated inspection](weakest-later-XLK.png)

[Daily prices, raw volume, weights, states and fills](weakest-later-XLK-daily.csv) · [FIFO outcomes](weakest-later-XLK-trades.csv). Whole cross-era lots and final open marks are included; their sum is not the era contribution.

Visual observations are hypotheses for a future declared test, never silent retrospective tuning. Largest selected-book order was 6.614% of prior median raw-dollar volume; 77 orders exceeded the0.5% diagnostic. [Participation details](liquidity.json). Dollar activity does not certify spreads or execution impact.

## Evidence and limits

Pinned price batch: e22f27a465e95f86cd40f7f9d24b63533a4a397eb0c02c8f40a696b0350d7731. BWX/XOP retain identity holds. Adjusted return prices and audited raw activity have verified publication hashes. Historical membership and price-publication availability remain reconstructed; archived macro availability and first-seen limitations are retained. Zero cash interest, no FX/taxes/measured spread/impact; whole adjusted units are synthetic research accounting. No inputs were acquired directly from online prices.

[Frozen protocol](protocol.json) · [Input verification](input-verification.json) · [Monthly policy parity](monthly-target-parity.json) · [Native LEAN accounting checks](native-validation.json) · [Evidence dossier](dossier.json) · [P4.20 assessment](assessment.json) · [Acceptance receipt](acceptance.json).

Native LEAN checks orders/fills/cash/NAV on frozen targets, not independent policy inference. Shared-policy parity and tests separately address recipe preservation, causal histories, adoption and selection. Reused chronological evidence is not prospective validation. Formal paper/monitoring/promotion evidence and operator approval would still be required for those stages.

**Stop for discussion after this item.** Next is the class/volatility-construction net replay. No monitoring, funding, promotion or broker action has been taken.
