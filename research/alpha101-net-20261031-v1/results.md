# Six standalone Alpha101 net retests — October 31, 2026

The training-selected candidate does not robustly improve both matched simple controls across the two eras. Retain the completed experiment as evidence; no standalone candidate is established for promotion.

**Completed: 222 net cases, six formulas, four timing policies and six friction settings.** All formerly cost-excluded formulas received full portfolio replays. The globally training-selected policy is **alpha54-monthly**. Each formula also has its own training-selected timing below. No later winner changes those selections. This is a new full-pool experiment, not an exact reproduction of the old 14-ETF cost screen.

## Main comparison

| Policy | Period | Net return | CAGR | Sharpe | Max DD | Calmar | Turnover/yr | Fees USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| alpha54-monthly | calibration | 33.37% | 7.49% | 0.679 | 19.33% | 0.387 | 19.918 | 45,066 |
| 126-session momentum | calibration | 6.09% | 1.49% | 0.172 | 24.44% | 0.061 | 10.688 | 22,208 |
| FR25 incumbent | calibration | 30.58% | 6.92% | 0.721 | 7.17% | 0.965 | 8.269 | 19,637 |
| alpha54-monthly | later | 26.90% | 13.97% | 1.569 | 7.54% | 1.852 | 20.174 | 28,254 |
| 126-session momentum | later | 63.82% | 31.13% | 1.211 | 16.70% | 1.864 | 8.174 | 10,208 |
| FR25 incumbent | later | 55.26% | 27.32% | 2.013 | 8.31% | 3.288 | 7.407 | 10,967 |

![Selected policy, matching momentum and incumbent](comparison.png)

## All six signals

| Signal | Training-selected timing | Training return / Sharpe | Later return / Sharpe / DD | Momentum guards early/later | Unranked guards early/later | FR25 guards early/later |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 24 | monthly | 38.42% / 0.643 | 35.74% / 1.068 / 13.50% | 6/6 ; 0/6 | 0/6 ; 0/6 | 0/6 ; 0/6 |
| 26 | monthly | 22.66% / 0.507 | 27.79% / 1.212 / 12.05% | 6/6 ; 0/6 | 2/6 ; 0/6 | 0/6 ; 0/6 |
| 46 | monthly | -2.20% / 0.002 | 37.98% / 1.605 / 11.45% | 0/6 ; 0/6 | 0/6 ; 0/6 | 0/6 ; 0/6 |
| 49 | monthly | 11.03% / 0.260 | 58.51% / 1.778 / 13.76% | 0/6 ; 2/6 | 0/6 ; 0/6 | 0/6 ; 0/6 |
| 53 | monthly | 24.17% / 0.506 | 31.89% / 1.596 / 8.63% | 4/6 ; 0/6 | 0/6 ; 0/6 | 0/6 ; 0/6 |
| 54 | monthly | 33.37% / 0.679 | 26.90% / 1.569 / 7.54% | 6/6 ; 0/6 | 0/6 ; 1/6 | 0/6 ; 0/6 |

Each guard requires strictly higher net Sharpe, CAGR no more than 0.5 percentage points lower and drawdown no more than 2 points worse. A count spans 5/10/20 bp and zero/one extra execution session. Counts are sensitivity evidence, not six independent discoveries. No annual cost ceiling or IC veto was applied.

## Full decision flow and definitions

Published audited batch and identity checks → complete supported price/raw-volume calendar → completed-close 253-session warmup and prior-63-session liquidity/duplicate admission → original Alpha101 score for each eligible risky ETF → highest six scores → inverse 63-return sample volatility weights with 98% budget and 45% final name cap → compare theoretical target with last adopted target including cash → monthly/event adoption → next open plus declared delay → whole adjusted-unit fills, actual fees, daily NAV and contribution accounting.

Selected score: ((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5))). The matching momentum score is C(t)/C(t−126)−1 and otherwise uses identical allocation and timing. The unranked control keeps all eligible names with the same inverse-volatility budget/cap. FR25 is the frozen app-owned empirical incumbent with financial/momentum and protection overlays; its full versioned definition and signal-input provenance are in [incumbent provenance](incumbent-provenance.json). These are three main model choices; the remaining references are controls, not post-result alternatives.

Alpha scores can be negative; only rank matters. Fewer than six valid scores or a constant cross-section produces cash. Ties follow inherited alphabetical selection, so ties in 46/49 can encode ticker ordering. Original absolute-price formulas24/46/49 are sensitive to adjusted price units across ETFs; no normalization was silently added. Formula53/54 same-close paper timing is adapted to next-open execution here. There are no stops or intraday protections in these standalone recipes; allocation exits occur only at adopted rebalances.

Dynamic thresholds are strict L1 distances greater than 0.10/0.40/0.80, including residual cash, plus the monthly anchor. They compare latest theoretical and last adopted targets. Held-position drift never triggers them. Delayed execution retains the original adopted target, resized at the close immediately before execution.

## Costs, execution delay and controls

| Fee bp | Extra sessions | Training return / Sharpe / DD | Later return / Sharpe / DD |
| --- | ---: | ---: | ---: |
| 5 | 0 | 33.37% / 0.679 / 19.33% | 26.90% / 1.569 / 7.54% |
| 5 | 1 | 32.45% / 0.663 / 19.74% | 24.37% / 1.447 / 6.61% |
| 10 | 0 | 28.19% / 0.594 / 19.89% | 24.61% / 1.449 / 7.63% |
| 10 | 1 | 27.31% / 0.577 / 20.30% | 22.12% / 1.329 / 6.70% |
| 20 | 0 | 18.42% / 0.422 / 21.01% | 20.14% / 1.206 / 7.80% |
| 20 | 1 | 17.61% / 0.405 / 21.42% | 17.74% / 1.090 / 6.87% |

| Alpha54 timing | Training return / Sharpe | Later return / Sharpe | Training / later turnover per year |
| --- | ---: | ---: | ---: |
| monthly | 33.37% / 0.679 | 26.90% / 1.569 | 19.918 / 20.174 |
| 0.10 | -42.59% / -1.312 | -9.18% / -0.505 | 401.902 / 417.097 |
| 0.40 | -42.54% / -1.310 | -8.99% / -0.493 | 400.896 / 416.803 |
| 0.80 | -42.79% / -1.319 | -7.18% / -0.376 | 394.083 / 409.194 |

All four timing options were evaluated for every formula and both simple controls. Monthly wins the training selection for all six formulas; this conclusion belongs to this pool, mapping and cost grid. Extra turnover was allowed and judged by its realized net outcome.

| Reference | Calibration passed | Later passed |
| --- | ---: | ---: |
| momentum-monthly | 6/6 | 0/6 |
| unranked-monthly | 0/6 | 1/6 |
| FR25 | 0/6 | 0/6 |

| Reference | Training return / Sharpe / DD | Later return / Sharpe / DD |
| --- | ---: | ---: |
| unranked-monthly | 9.15% / 0.317 / 17.26% | 20.64% / 1.536 / 6.42% |
| cash | 0.00% / 0.000 / -0.00% | 0.00% / 0.000 / -0.00% |
| BIL_buyhold | 11.79% / 9.875 / 0.18% | 7.29% / 18.663 / 0.01% |
| URTH_buyhold | 46.00% / 0.679 / 26.05% | 34.58% / 1.118 / 16.94% |
| pool_buyhold | 20.52% / 0.467 / 18.01% | 39.65% / 1.515 / 11.97% |

Cash has zero interest and undefined Calmar at zero drawdown. Reported Sharpe uses zero as its reference rate, so BIL's small-volatility Sharpe is not directly comparable risk exposure. BIL is the investable cash reference. Buy-and-hold portfolios buy initially and drift thereafter; their later window inherits positions. [Individual ETF buy-and-hold references](individual-buyhold.json) instead start fresh each era, use fractional units and one 5 bp entry fee, and are explicitly descriptive. [All 222 case metrics](results.json) include actual fees, turnover, exposure and annual outcomes; [every guarded comparison](comparisons.json) is retained. The matched-control rules govern this test; additional guard calculations against cash/buy-and-hold are descriptive and not a new acceptance requirement.

## Chronological robustness and uncertainty

| Year | Selected return / Sharpe | Momentum return / Sharpe | FR25 return / Sharpe |
| --- | ---: | ---: | ---: |
| 2021 | 19.79% / 2.130 | 11.57% / 0.691 | 10.96% / 0.929 |
| 2022 | -7.39% / -0.373 | -10.65% / -0.460 | 3.29% / 0.405 |
| 2023 | 5.74% / 0.617 | -0.92% / -0.003 | 8.79% / 0.906 |
| 2024 | 13.70% / 1.455 | 7.41% / 0.586 | 4.74% / 0.572 |
| 2025 | 20.63% / 2.394 | 33.79% / 1.740 | 24.36% / 1.981 |
| 2026 | 5.19% / 0.711 | 22.45% / 0.933 | 24.85% / 2.055 |

| Period | Family-adjusted Sharpe difference | Family-adjusted CAGR difference |
| --- | ---: | ---: |
| calibration | -0.623 to 1.636 | -10.90% to 21.67% |
| later | -2.140 to 2.704 | -87.02% to 32.42% |

| Signal | Training / later 21-session IC | Training / later tied-score fraction | Training-prefix winning policies 2021/22/23/24 |
| --- | ---: | ---: | --- |
| 24 | 0.062 / 0.033 | 2.57% / 1.21% | monthly, 0.80, 0.80, monthly |
| 26 | 0.033 / 0.008 | 5.64% / 5.21% | monthly, monthly, monthly, monthly |
| 46 | 0.003 / 0.004 | 63.31% / 64.94% | monthly, monthly, monthly, monthly |
| 49 | 0.010 / 0.030 | 30.07% / 30.26% | monthly, monthly, monthly, monthly |
| 53 | 0.007 / 0.018 | 0.04% / 0.04% | monthly, monthly, monthly, monthly |
| 54 | 0.009 / 0.005 | 1.09% / 0.93% | monthly, monthly, monthly, monthly |

Intervals are paired circular 21-session block bootstraps, 4,000 draws, seed20261031, Bonferroni-adjusted across24 alpha/timing contrasts against matching momentum. Tail estimates are approximate; related formulas and repeatedly inspected histories limit discovery claims. [All intervals](uncertainty.json), [training-prefix policy stability](training-stability.json), and [1/5/10/21-session rank IC, coverage and ties](signal-diagnostics.json) are diagnostics. The primary IC horizon was21; no horizon was selected by its result. Later history is chronological holdout from this selection, not untouched or prospective evidence.

FR25 is not a universal truth benchmark: DBC/SPY/XLE contribute 9.96/9.67/7.42 points in calibration; EWY/GLD/XLE contribute14.78/10.47/7.75 points later. Those later three account for about60% of its net gain. Its asset contribution extremes in each era are in [incumbent dependence](incumbent-dependence.json), and annual results above expose period dependence. Its saved signal decisions use their own audited batch/model warmup; all portfolios are replayed on the same study prices, costs and dates, but FR25 is not a pure alpha ablation. [Full portfolio attribution](attribution.json) reconciles to NAV in every era.

## Weakest risky ETF inspections

The declared criterion is **lowest actual net contribution divided by opening portfolio NAV**, at5bp/next-open under the training-selected policy, excluding BIL, cash and URTH. This explicit portfolio criterion accounts for changing allocations; it is not a standalone ETF return. Both eras include every dated state/fill and price/volume context. No protective stop exists in this recipe. Visual observations will become hypotheses for a subsequent declared test, never retrospective tuning.

### Calibration: EWY, -3.12 pp

![Dated EWY inspection](weakest-calibration-EWY.png)

[Every dated observation and fill](weakest-calibration-EWY-daily.csv) · [FIFO outcomes overlapping this era](weakest-calibration-EWY-trades.csv). The trade file marks open lots at October 30 and includes complete cross-era lots; its summed P&L is not the era contribution.

### Later: XLC, -1.70 pp

![Dated XLC inspection](weakest-later-XLC.png)

[Every dated observation and fill](weakest-later-XLC-daily.csv) · [FIFO outcomes overlapping this era](weakest-later-XLC-trades.csv). The trade file marks open lots at October 30 and includes complete cross-era lots; its summed P&L is not the era contribution.

[All FIFO trade outcomes](trade-outcomes.csv) include partial exits, allocated entry/exit fees and open-lot marks. Total marked FIFO P&L reconciles to full portfolio net P&L. Era-specific contributions use actual held units and daily changes, including positions inherited from the earlier era.

## Evidence and limits

The frozen input batch is e22f27a465e95f86cd40f7f9d24b63533a4a397eb0c02c8f40a696b0350d7731. The full configured/admitted union contains 54 candidates: 52 supported histories, including BIL, with BWX/XOP identity holds preserved. Common audited support begins 2018-08-24; evaluation begins January4,2021 and ends October30,2026. No provider download or online price was used. Prices are dividend/split-adjusted; activity uses audited raw share volume and raw traded price. Unsupported observations remain missing; no fill/splice or FX input.

This is current-cohort retrospective research. Price auditing does not certify historical dissemination or historical membership; reconstructed raw prices are not tape-certified. Whole adjusted units are synthetic research accounting; fees do not model spreads, impact, taxes or broker lots. The original frozen screen and its verdicts remain historical evidence. The old cost exclusion is now superseded by actual net replay evidence for these six signals, without automatic monitoring or allocation.

[Frozen protocol and hashes](protocol.json) · [Native independent accounting checks](native-validation.json) · [Acceptance receipt](acceptance.json). Native LEAN verifies orders/fills/cash/NAV on frozen targets; it does not independently infer the alpha policy. Unit tests separately cover formulas, causal suffixes, missing activity, selection leakage, caps, adoption and accounting boundaries.

**Stop for operator discussion.** Cash-relative remains retained research evidence. No promotion, monitoring, funding, broker or app-calculation change was made. P4.20 decay governance and the remaining research queue have not been started in this item.
