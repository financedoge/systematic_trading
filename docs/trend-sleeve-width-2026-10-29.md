# Strategy portfolios: N15, N20 and N30 — 2026-10-29

The operator requested N20 and N30 after the N15 result. Both were run with the same frozen ETF strategies, 63/252-session ranking, cash treatment, monthly allocation and dynamic control. N30 improves later diversification and Sharpe, but does not establish an advantage over unranked full-pool sleeves. N20 is weaker in both primary periods.

[Interactive comparison and all ETF charts](../research/trend-sleeve-width-20261029-v1/index.html) · [N15 methodology](trend-sleeve-portfolio-2026-10-29.md)

## Equal-capital primary comparison

5 bp per side, next-open execution, monthly capital allocation and daily ETF strategy signals. Idle sleeve cash earns zero. Sharpe uses a zero reference rate.

| Period | N | Net return | CAGR | Sharpe | Maximum drawdown | Average active ETFs |
|---|---:|---:|---:|---:|---:|---:|
| late | 15 | 18.15% | 6.38% | 0.776 | 7.67% | 8.64 |
| late | 20 | 13.84% | 4.92% | 0.682 | 8.14% | 11.16 |
| late | 30 | 16.72% | 5.90% | 0.917 | 6.47% | 16.51 |
| late | Full | 17.50% | 6.16% | 1.144 | 6.10% | 26.21 |
| early | 15 | -4.19% | -2.12% | -0.217 | 12.91% | 7.99 |
| early | 20 | -4.53% | -2.29% | -0.269 | 11.91% | 10.40 |
| early | 30 | -4.03% | -2.04% | -0.251 | 12.18% | 15.35 |
| early | Full | -1.13% | -0.57% | -0.049 | 11.04% | 23.76 |

Late funded dates: 2024-02-01 through 2026-10-16; early: 2021-01-04 through 2022-12-30. At least 252 post-fit strategy-return observations precede selection. Models trained through 2022 and 2019 respectively. These periods exclude the 2020 crash and 2023 from funded portfolio evaluation and have been repeatedly inspected. Width extension is explicitly subsequent development evidence, not a fresh holdout.

## Interpretation

N30 equal capital passes the declared Sharpe/return/drawdown guard against N15 in 8/12 era/friction settings, but 0/12 against the unranked full pool. N20 equal passes 4/12 and 1/12, respectively. N30 risk parity passes 7/12 against N15 risk parity and 0/12 against full pool. Guards require higher Sharpe, CAGR no more than 1 percentage point lower and drawdown no more than 2 points worse. The 12 settings are not independent statistical samples.

N30 daily active ETF counts average 16.51 later and 15.35 earlier, compared with 8.64/7.99 at N15. Cash averages 44.61%/48.50%; capital is not redistributed from inactive sleeves. N30 risk parity has effective invested breadth 11.78/10.64 and maximum sleeve weights 15.20%/16.35%, versus 27.18%/24.99% at N15. Count diversification improves, but ETFs share economic risks.

N30 monthly risk parity returns 10.77% later / −3.90% earlier, Sharpe .867/−.374, drawdown 4.44%/10.02%. This lowers some risk but does not consistently improve net returns over equal capital (earlier N30 risk parity loses slightly less). Retain both evidence sets; no automatic switch in base or promotion.

Monthly N30 equal costs 67.16/69.35 bp annually versus 76.97/78.29 at N15. No annual cost ceiling was used. Dynamic uses the unchanged cash-inclusive 10% trigger: one equal sleeve flip contributes 2/N, so N20 remains at the trigger and N30 falls below it. Later adoption count is 407 at N30 versus 538 at N15 and 561 at N20; monthly remains 33. N30 dynamic equal primary returns 17.57%/−3.20%, but costs 103/104 bp annually and deteriorates under higher costs. It is not a stable timing replacement.

Matched raw-price rank and hold controls, with the same four-metric score and widths, return 57.34%/5.55% at N20 and 50.94%/7.36% at N30 (later/earlier). They stay fully invested and bear higher drawdown. They change both rank source and daily trading/cash behavior, so do not attribute the performance gap solely to rank source. A future factorial comparison can separate those effects while fixing N30 and matching cash economics. This is a proposed next experiment, not a tested finding.

## Weakest constituents and inspection

Same virtual strategy/window implies unchanged weakest shadows: TLT later −18.56%, MCHI earlier −31.99%. Actual worst N30 equal contributors are CPER later −0.960pp and PPLT earlier −1.187pp. Risk parity: WEAT −0.898pp and GLD −0.775pp. N20 equal: IAT −1.200pp later and XLY −1.957pp earlier. Actual holdings/fees explain these differences; they are not standalone strategy returns.

CPER actual N30 daily entry 2026-02-27 at adjusted 37.14, small allocation addition on March 2 at36.39, then signal exit March19 at32.80. PPLT enters November11 2021 at10.16 and exits November23 at9.15; April19 2022 entry9.39 exits April25 at8.52. The charts show these repeated failed upswings and delayed exits for discussion. No parameters were tuned to those episodes.

Report provides all 100 risky ETF-era charts, all three widths and three weighting/control views, dated OHLCV/state/protection and actual fills, full attribution, and historical rank tables for every monthly decision. Default is N30/CPER. Each selection-width/weight change updates actual portfolio fills; shadow histories remain the same.

## Evidence and recipe

120 new width cases plus 106 N15/control/diagnostic cases; 612 exact frozen shadow reproductions. Twenty focused/regression checks pass. N15 report: 100 chart combinations and 171 allocation-date views; extension: 900 chart/width/weight combinations and 513 allocation-date views. Date hover, interval selection and empty-range behavior pass offline. Static NAV/CPER figures inspected; browser layout is not certified.

Five native Windows multiasset fixtures across both studies match their independent app reference to the cent. Native uses execution-open target oracles reconstructed from fractional fills and whole-share/cent-price accounting. It does not independently validate HMM inference, ranks, covariance optimization or causal live execution. Fractional global cash/share ledgers and per-ETF P&L reconcile separately.

New code: `scripts/research_trend_sleeve_width.py prepare/evaluate`, `scripts/build_trend_sleeve_width_report.py`; native validator accepts `--width`. Uses the shared versioned engine and verified cached shadow panel from N15. Existing results reject overwrite; later reruns should use a new versioned output. Protocol and evidence hashes retained.

Published audited batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd; adjusted OHLC, audited raw share volume, no missing-value fill or online prices. Retrospective cohort and publication-vintage limits persist. No FX, taxes, true market impact, intraday stop guarantee or cash interest. All model/rank research history and post-inspection width expansion limit inference. No recurring tracking, registry, capital, broker, approval or live changes.
