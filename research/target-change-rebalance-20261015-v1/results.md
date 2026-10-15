# Target-change rebalance backtest — 15 October 2026

Completed finite research. USD1m; whole adjusted units; zero cash interest; 5bp per traded side in the main comparison. Prices through 14 October 2026. Threshold is the sum of absolute latest-theoretical versus last-adopted target differences, including cash.

**Monthly macro assumption:** exact pinned daily snapshot when available, otherwise the previous completed monthly snapshot; source dates remain intact. Daily prices/activity and price-based features update normally. No trading housekeeping trigger is included.

**Decision:** No extra-rebalance threshold qualified in any annual selection window; retain monthly rebalancing. This is inspected historical evidence, not proof of superiority or trading approval.

## Walk-forward evaluation: 2024-01-02 to 2026-10-14

| Parent | Policy | Net Sharpe | CAGR | Max drawdown | Annual turnover |
| --- | --- | ---: | ---: | ---: | ---: |
| FR25 | Monthly | 1.613 | 19.15% | -8.66% | 8.70× |
| FR25 | Selected walk-forward | 1.613 | 19.15% | -8.66% | 8.70× |
| F3 | Monthly | 1.664 | 19.60% | -8.75% | 6.12× |
| F3 | Selected walk-forward | 1.664 | 19.60% | -8.75% | 6.12× |

F3 retains the current published adjusted-price/source-volume activity proxy. Its results are a legacy-parent sensitivity check; audited raw-activity transfer confirmation remains unavailable.

## Causal threshold selection

| Training window | Applied from | Selected policy |
| --- | --- | --- |
| 2021-01-04–2023-12-29 | 2024-01-02 | monthly |
| 2022-01-03–2024-12-31 | 2025-01-02 | monthly |
| 2023-01-03–2025-12-31 | 2026-01-02 | monthly |

Final trailing-three-year selector (2023-10-16–2026-10-14): **monthly**. A monthly outcome means no extra threshold qualified. This freezes a research candidate only; no prospective monitoring is started.

## Full 2021–2026 grid: descriptive, not threshold selection

| Parent | Policy | Sharpe | CAGR | Max drawdown | Turnover/year | Filled rebalance dates |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| FR25 | monthly | 1.190 | 13.05% | -8.66% | 8.05× | 70 |
| FR25 | daily | 0.941 | 9.73% | -13.35% | 62.43× | 1452 |
| FR25 | 0.025 | 0.942 | 9.73% | -13.34% | 62.28× | 1253 |
| FR25 | 0.05 | 0.955 | 9.88% | -13.23% | 61.08× | 1047 |
| FR25 | 0.075 | 0.959 | 9.96% | -13.11% | 59.51× | 863 |
| FR25 | 0.10 | 0.966 | 10.05% | -13.10% | 58.36× | 769 |
| FR25 | 0.15 | 0.965 | 10.04% | -13.04% | 57.05× | 688 |
| FR25 | 0.20 | 0.987 | 10.27% | -12.63% | 56.47× | 660 |
| FR25 | 0.30 | 0.991 | 10.30% | -12.86% | 54.62× | 604 |
| FR25 | 0.40 | 1.077 | 11.32% | -12.23% | 47.70× | 469 |
| FR25 | walk_forward | 1.190 | 13.05% | -8.66% | 8.05× | 70 |
| F3 | monthly | 1.052 | 10.48% | -11.69% | 5.85× | 70 |
| F3 | daily | 0.811 | 7.66% | -12.38% | 41.65× | 1452 |
| F3 | 0.025 | 0.814 | 7.69% | -12.35% | 41.47× | 1163 |
| F3 | 0.05 | 0.819 | 7.74% | -12.39% | 40.17× | 939 |
| F3 | 0.075 | 0.833 | 7.88% | -12.34% | 38.16× | 722 |
| F3 | 0.10 | 0.834 | 7.93% | -12.18% | 36.59× | 599 |
| F3 | 0.15 | 0.848 | 8.06% | -11.87% | 35.09× | 495 |
| F3 | 0.20 | 0.862 | 8.21% | -11.77% | 33.88× | 434 |
| F3 | 0.30 | 0.873 | 8.33% | -11.51% | 31.99× | 372 |
| F3 | 0.40 | 0.876 | 8.36% | -11.28% | 28.21× | 300 |
| F3 | walk_forward | 1.052 | 10.48% | -11.69% | 5.85× | 70 |

Annual turnover is gross buys plus sells divided by each session’s pretrade NAV; 5bp cost drag is charged on that actual notional. Rebalance dates include scheduled events with no required whole-unit trade.

## Why the threshold creates frequent trading

| Parent / policy | Extra threshold events | Median sessions between adoptions | Opposite-direction fills within five sessions | Annual fee drag |
| --- | ---: | ---: | ---: | ---: |
| FR25 / monthly | 0 | 21.0 | 0 | 40.2bp |
| FR25 / 0.10 | 700 | 1.0 | 3258 | 291.8bp |
| FR25 / 0.40 | 399 | 2.0 | 1930 | 238.5bp |
| F3 / monthly | 0 | 21.0 | 0 | 29.2bp |
| F3 / 0.10 | 530 | 1.0 | 2255 | 183.0bp |
| F3 / 0.40 | 230 | 2.0 | 1011 | 141.1bp |

This measures reactivity and trading churn. It does not identify the causal economic reason for every reversal. Full per-ETF PnL, mean exposures, holding spells and costs are retained in each replay’s metrics artifact.

## Macro snapshot coverage

| Parent | Daily target dates | USD active dates | USD monthly fallbacks | Maximum USD snapshot carry | Financial monthly fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| FR25 | 1453 | 639 | 599 | 32 days | 1382 |
| F3 | 1453 | 639 | 599 | 32 days | 0 |

## Cost and delay robustness: walk-forward evaluation

| Parent | Cost per side | Extra delay | Monthly Sharpe | Walk-forward Sharpe | CAGR difference | Drawdown difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FR25 | 5bp | 0 session | 1.613 | 1.613 | +0.00pp | +0.00pp |
| FR25 | 10bp | 0 session | 1.574 | 1.574 | +0.00pp | +0.00pp |
| FR25 | 5bp | 1 session | 1.591 | 1.591 | +0.00pp | +0.00pp |
| FR25 | 20bp | 0 session | 1.495 | 1.495 | +0.00pp | +0.00pp |
| FR25 | 10bp | 1 session | 1.552 | 1.552 | +0.00pp | +0.00pp |
| FR25 | 20bp | 1 session | 1.474 | 1.474 | +0.00pp | +0.00pp |
| F3 | 5bp | 0 session | 1.664 | 1.664 | +0.00pp | +0.00pp |
| F3 | 10bp | 0 session | 1.636 | 1.636 | +0.00pp | +0.00pp |
| F3 | 5bp | 1 session | 1.623 | 1.623 | +0.00pp | +0.00pp |
| F3 | 20bp | 0 session | 1.581 | 1.581 | +0.00pp | +0.00pp |
| F3 | 10bp | 1 session | 1.595 | 1.595 | +0.00pp | +0.00pp |
| F3 | 20bp | 1 session | 1.540 | 1.540 | +0.00pp | +0.00pp |

## Conditional uncertainty

20,000 paired stationary-bootstrap replicates; seed 20261015; common 2024–2026 calendar across all policies, parents and URTH. Mean block 63 sessions, with 21/126 sensitivity. These intervals condition on the chosen annual policy calendar. The selector is not rerun within resamples, so neither the intervals nor the descriptive Holm adjustment over 18 contrasts establish formal superiority.

| Parent | Mean block | Walk-forward Sharpe difference | Conditional 95% interval | Descriptive Holm p |
| --- | ---: | ---: | --- | ---: |
| FR25 | 63 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 63 | +0.000 | [+0.000, +0.000] | 1.000 |
| FR25 | 21 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 21 | +0.000 | [+0.000, +0.000] | 1.000 |
| FR25 | 126 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 126 | +0.000 | [+0.000, +0.000] | 1.000 |

## Evidence and limits

- All 132 full-size parent/policy/cost/delay replays retain decisions, actual fills, fees, cash, NAV and full-constituent attribution. USD100k diagnostics use the same selected rules without retuning.
- Each parent matches its frozen monthly target decisions. Six independent native LEAN checks cover both monthly controls, selected walk-forward policies and the 0.10 intramonth policies. Every event is independently checked against the last logical adoption.
- Monthly macro fallback assumes no newly available signal information between snapshots. Source dates and carry ages are in the target tapes; this assumption can understate responsiveness to macro releases.
- Price and economic publication vintages are retrospective; current strategy and universe choices used inspected data. Adjusted units are not raw broker shares. Fixed bps costs do not establish capacity, taxes, bid-ask spreads or realized fills.
- Risk, turnover, holding spells, five-session reversal counts and constituent PnL are retained. Full-pool qualification, a corrected-basis F3 comparison, prospective evidence and existing promotion gates remain separate.

Artifacts: [Replay evidence](../../var/research/target-change-rebalance-20261015-v1/run-02/analysis.json).

Detailed reports use the application’s shared SOTA report format:
- [FR25-monthly.html](FR25-monthly.html)
- [FR25-walk_forward.html](FR25-walk_forward.html)
- [F3-monthly.html](F3-monthly.html)
- [F3-walk_forward.html](F3-walk_forward.html)
