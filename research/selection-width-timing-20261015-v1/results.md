# Joint ETF selection width and rebalance threshold

The causal selector retained the current top-six monthly policy in all three folds.

Final trailing-three-year research candidate: **(X,n) = 6/monthly**. This is the selected pair within the tested grid, not a global optimum or trading approval.

X = 4, 6, 8, 10, 12, all eligible (maximum 14 for FR25 and 12 for F3). n = 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00, or monthly only. Cash is included in target distance. Existing eligibility gates, defensive fallback, models and sizing stay fixed. The approved previous-monthly macro fallback remains explicit.

## Causal selections

| Training window | Activation | (X,n) | Pairs passing performance guards |
| --- | --- | --- | --- |
| 2021-01-04–2023-12-29 | 2024-01-02 | 6/monthly | 4/monthly |
| 2022-01-03–2024-12-31 | 2025-01-02 | 6/monthly | 4/monthly |
| 2023-01-03–2025-12-31 | 2026-01-02 | 6/monthly | None |

Performance checks also require a passing adjacent grid pair before selection. An isolated passing pair is rejected by the registered stability rule. These annual decisions use only the preceding training window, but the historical sample and parent strategies were already inspected; this is not an untouched holdout.

## Validation performance: 2024-01-02 through 2026-10-14

| Parent | Policy | Net Sharpe | CAGR | Max drawdown | Annual gross turnover |
| --- | --- | ---: | ---: | ---: | ---: |
| FR25 | 6/monthly | 1.613 | 19.15% | -8.66% | 8.70× |
| FR25 | WF | 1.613 | 19.15% | -8.66% | 8.70× |
| F3 | 6/monthly | 1.664 | 19.60% | -8.75% | 6.12× |
| F3 | WF | 1.664 | 19.60% | -8.75% | 6.12× |

F3 is a legacy-parent sensitivity comparison because its current activity overlay uses adjusted price and inherited source volume. Its 12 and all columns are identical and do not provide independent confirmation.

## Does increasing X reduce churn?

Full 2021–2026 period at 5bp per traded side. These fixed-pair comparisons are descriptive and use inspected data.

| Parent | X | n | Sharpe | CAGR | Max drawdown | Turnover/year | Mean held ETFs | Entry/exit share of trading |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FR25 | 4 | monthly | 1.122 | 14.28% | -12.38% | 8.96× | 3.56 | 84.2% |
| FR25 | 4 | 0.10 | 0.864 | 10.38% | -10.53% | 65.35× | 3.55 | 80.4% |
| FR25 | 6 | monthly | 1.190 | 13.05% | -8.66% | 8.05× | 5.20 | 78.2% |
| FR25 | 6 | 0.10 | 0.966 | 10.05% | -13.10% | 58.36× | 5.20 | 74.1% |
| FR25 | 8 | monthly | 1.048 | 10.08% | -8.24% | 7.01× | 6.65 | 71.3% |
| FR25 | 8 | 0.10 | 0.614 | 5.47% | -15.38% | 48.32× | 6.72 | 68.1% |
| FR25 | 10 | monthly | 0.918 | 8.07% | -8.66% | 6.11× | 7.85 | 62.1% |
| FR25 | 10 | 0.10 | 0.625 | 5.13% | -13.98% | 38.69× | 7.92 | 60.2% |
| FR25 | 12 | monthly | 0.830 | 6.96% | -8.77% | 5.85× | 8.45 | 57.8% |
| FR25 | 12 | 0.10 | 0.584 | 4.56% | -13.04% | 34.60× | 8.52 | 54.3% |
| FR25 | all | monthly | 0.841 | 6.99% | -8.76% | 5.51× | 8.70 | 53.3% |
| FR25 | all | 0.10 | 0.631 | 4.91% | -12.54% | 30.60× | 8.76 | 49.2% |
| F3 | 4 | monthly | 1.137 | 14.27% | -12.47% | 7.45× | 3.37 | 75.0% |
| F3 | 4 | 0.10 | 0.962 | 10.99% | -11.62% | 44.07× | 3.32 | 73.9% |
| F3 | 6 | monthly | 1.052 | 10.48% | -11.69% | 5.85× | 4.91 | 67.5% |
| F3 | 6 | 0.10 | 0.834 | 7.93% | -12.18% | 36.59× | 4.84 | 66.2% |
| F3 | 8 | monthly | 0.841 | 7.24% | -12.10% | 5.16× | 6.28 | 57.7% |
| F3 | 8 | 0.10 | 0.764 | 6.16% | -11.42% | 30.24× | 6.19 | 56.8% |
| F3 | 10 | monthly | 0.773 | 5.89% | -12.12% | 4.32× | 7.21 | 48.5% |
| F3 | 10 | 0.10 | 0.716 | 5.12% | -11.33% | 23.70× | 7.08 | 47.5% |
| F3 | 12 | monthly | 0.729 | 5.39% | -12.13% | 3.85× | 7.58 | 39.8% |
| F3 | 12 | 0.10 | 0.747 | 5.22% | -11.33% | 18.57× | 7.46 | 35.2% |
| F3 | all | monthly | 0.729 | 5.39% | -12.13% | 3.85× | 7.58 | 39.8% |
| F3 | all | 0.10 | 0.747 | 5.22% | -11.33% | 18.57× | 7.46 | 35.2% |

Entry/exit share excludes initial establishment and counts trades where actual units cross zero. The remainder adjusts retained ETF weights. FR25 target membership counts below distinguish rank-cutoff changes from eligibility/fallback changes; they are counts, not causal PnL attribution.

| FR25 pair | Rank-cutoff changes | Eligibility changes | Fallback changes |
| --- | ---: | ---: | ---: |
| 4/0.10 | 1074 | 56 | 114 |
| 6/0.10 | 1096 | 173 | 124 |
| 8/0.10 | 926 | 341 | 124 |
| 10/0.10 | 485 | 512 | 124 |
| 12/0.10 | 216 | 625 | 124 |
| all/0.10 | 0 | 645 | 124 |

## Reactivity, concentration and liquidity diagnostics

| Parent | Pair | Rebalance dates | Five-session fill reversals | Effective holdings | Maximum held weight | P95 daily-volume fraction |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| FR25 | 6/monthly | 70 | 0 | 4.44 | 46.7% | 0.168% |
| FR25 | 6/0.10 | 769 | 3258 | 4.50 | 45.5% | 0.158% |
| FR25 | 8/monthly | 70 | 0 | 5.36 | 46.8% | 0.086% |
| FR25 | 8/0.10 | 778 | 4034 | 5.47 | 45.0% | 0.075% |
| FR25 | 12/monthly | 70 | 0 | 6.38 | 46.8% | 0.064% |
| FR25 | 12/0.10 | 747 | 4441 | 6.42 | 45.0% | 0.052% |
| F3 | 6/monthly | 70 | 0 | 3.96 | 53.7% | 0.149% |
| F3 | 6/0.10 | 599 | 2255 | 3.96 | 58.8% | 0.120% |
| F3 | 8/monthly | 70 | 0 | 4.77 | 53.7% | 0.100% |
| F3 | 8/0.10 | 607 | 2817 | 4.64 | 58.8% | 0.064% |
| F3 | 12/monthly | 70 | 0 | 5.53 | 53.6% | 0.059% |
| F3 | 12/0.10 | 561 | 2685 | 5.43 | 58.8% | 0.042% |

Reversals count opposite-direction consecutive fills in the same ETF within five sessions, including monthly events. Effective holdings are the inverse concentration of invested ETF weights. The volume proxy is simulated traded USD divided by audited raw daily dollar volume, measured ex post; it is not a capacity or slippage model. All 98 base-case policies retain these diagnostics in the analysis artifact.

## Cost and delay robustness of the selected walk-forward policy

| Parent | Cost | Extra delay | Sharpe difference | CAGR difference | Drawdown difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| FR25 | 5bp | 0 | +0.000 | +0.00pp | +0.00pp |
| FR25 | 5bp | 1 | +0.000 | +0.00pp | +0.00pp |
| FR25 | 10bp | 0 | +0.000 | +0.00pp | +0.00pp |
| FR25 | 10bp | 1 | +0.000 | +0.00pp | +0.00pp |
| FR25 | 20bp | 0 | +0.000 | +0.00pp | +0.00pp |
| FR25 | 20bp | 1 | +0.000 | +0.00pp | +0.00pp |
| F3 | 5bp | 0 | +0.000 | +0.00pp | +0.00pp |
| F3 | 5bp | 1 | +0.000 | +0.00pp | +0.00pp |
| F3 | 10bp | 0 | +0.000 | +0.00pp | +0.00pp |
| F3 | 10bp | 1 | +0.000 | +0.00pp | +0.00pp |
| F3 | 20bp | 0 | +0.000 | +0.00pp | +0.00pp |
| F3 | 20bp | 1 | +0.000 | +0.00pp | +0.00pp |

## Conditional uncertainty

20,000 jointly paired stationary-bootstrap replicates on the common 2024–2026 calendar, including URTH. Seed 20261015, primary mean block 63 sessions and sensitivities 21/126. Holm spans 96 contrasts. The selector is not rerun within bootstrap replicates, so inference is conditional/descriptive; no formal superiority claim.

| Parent | Mean block | WF Sharpe difference | Conditional 95% interval | Descriptive Holm p |
| --- | ---: | ---: | --- | ---: |
| FR25 | 63 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 63 | +0.000 | [+0.000, +0.000] | 1.000 |
| FR25 | 21 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 21 | +0.000 | [+0.000, +0.000] | 1.000 |
| FR25 | 126 | +0.000 | [+0.000, +0.000] | 1.000 |
| F3 | 126 | +0.000 | [+0.000, +0.000] | 1.000 |

## Verification and limits

- 576 fixed-pair scenarios plus 12 continuous walk-forward scenarios; USD100k checks use the selected pairs without retuning.
- Top-six targets match all 1,453 parent daily evaluations, including the final pending date; 60 common parent economic replays match fills, cash, NAV and final positions exactly.
- 6 independent native LEAN/Python checks; independent adoption checks for all 98 parent/policy combinations. Monthly width/threshold switches carry the account and adopted-target state.
- Whole adjusted units, zero cash interest, fixed bps transaction costs, next-open execution, and one extra session delay stress. Revised price/economic vintages and current universe membership remain retrospective limitations.
- Shared SOTA-format detail reports retain constituent attribution, holdings, benchmark curves and the complete variant decision contract. No tracking, allocation, approvals or broker settings changed.
- This current-universe study cannot establish behavior in the expanded ETF pool. Full-pool validation requires a separately qualified parent and preserved point-in-time/data/promotion gates.

[Full replay evidence](../../var/research/selection-width-timing-20261015-v1/analysis.json) · [All scenarios](grid.csv)

- [FR25-6-monthly.html](FR25-6-monthly.html)
- [FR25-WF.html](FR25-WF.html)
- [FR25-8-0.10.html](FR25-8-0.10.html)
- [F3-6-monthly.html](F3-6-monthly.html)
- [F3-WF.html](F3-WF.html)
- [F3-8-0.10.html](F3-8-0.10.html)
