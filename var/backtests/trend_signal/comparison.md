# Signal Comparison

- Baseline: Baseline risk parity
- Candidate: Risk parity + ts-momentum-252d-cash
- Out-of-sample split: 2023-01-01
- Range: 2021-01-04 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | Baseline risk parity | 42.11% | 6.84% | -24.40% | 0.51 | 0.49 | 0.28 | n/a |
| Full | Risk parity + ts-momentum-252d-cash | 40.89% | 6.66% | -13.47% | 0.63 | 0.58 | 0.49 | -1.23% |
| In Sample | Baseline risk parity | -14.18% | -7.42% | -24.40% | -0.41 | -0.38 | -0.30 | n/a |
| In Sample | Risk parity + ts-momentum-252d-cash | -0.61% | -0.31% | -13.47% | 0.01 | 0.01 | -0.02 | 13.57% |
| Out Of Sample | Baseline risk parity | 66.44% | 16.60% | -13.03% | 1.09 | 1.08 | 1.27 | n/a |
| Out Of Sample | Risk parity + ts-momentum-252d-cash | 43.09% | 11.40% | -10.81% | 0.94 | 0.91 | 1.05 | -23.35% |

Alpha here is candidate return minus baseline return over the same window.

## Market Data Audit

- Source: SQLite var\systematic_trading.db
- Price field: close
- Adjusted prices validated: no
- Required observations: 1336
- Common required observations: 1336

| Symbol | Obs. | Required Coverage | Missing Required | Max Gap Days | Stale Runs | Non-Positive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWH | 1336 | 100.00% | 0 | 4 | 0 | 0 |
| EWJ | 1336 | 100.00% | 0 | 4 | 0 | 0 |
| EWY | 1336 | 100.00% | 0 | 4 | 0 | 0 |
| SPY | 1336 | 100.00% | 0 | 4 | 0 | 0 |
| VGK | 1336 | 100.00% | 0 | 4 | 0 | 0 |

Warnings:
- Stored prices are close prices, not validated adjusted total-return prices; ETF dividends and split adjustments remain a research risk.

## Signal Forecast Quality

- Lookback bars: 252
- Threshold: 0.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 250 | 147 | 103 | 1.13% | 0.21% | 0.91% | 55.60% | 0.04 |
| In Sample | 55 | 5 | 50 | -2.65% | -1.18% | -1.48% | 58.18% | -0.30 |
| Out Of Sample | 195 | 142 | 53 | 1.26% | 1.53% | -0.27% | 54.87% | -0.00 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWH | 50 | 1.24% | -0.48% | 1.72% | 60.00% | 0.03 |
| EWJ | 50 | 1.15% | -0.18% | 1.33% | 60.00% | -0.01 |
| EWY | 50 | 2.07% | 1.03% | 1.05% | 46.00% | 0.10 |
| SPY | 50 | 1.03% | 0.28% | 0.75% | 58.00% | -0.05 |
| VGK | 50 | 0.55% | 0.66% | -0.11% | 54.00% | -0.14 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 60 | 22 | 29 | -4.03% | -1.23% | -0.05% |
| In Sample | 20 | 6 | 5 | 12.14% | 13.08% | 0.65% |
| Out Of Sample | 40 | 16 | 24 | -16.17% | -23.35% | -0.39% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2022-11-01 to 2022-12-01 | -13.01% | -13.40% | EWH cut (-4.78%, asset 21.44%) |
| 2023-01-03 to 2023-02-01 | -8.65% | -8.85% | EWY cut (-3.02%, asset 17.46%) |
| 2024-09-03 to 2024-10-01 | -4.03% | -4.09% | EWH cut (-4.09%, asset 20.68%) |
| 2022-07-01 to 2022-08-01 | -3.37% | -3.31% | EWJ cut (-1.66%, asset 7.20%) |
| 2025-06-02 to 2025-07-01 | -2.85% | -2.87% | EWY cut (-2.87%, asset 16.03%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-09-01 to 2022-10-03 | 8.63% | 8.39% | EWY cut (2.37%, asset -14.57%) |
| 2022-06-01 to 2022-07-01 | 7.45% | 7.41% | EWY cut (2.57%, asset -15.10%) |
| 2022-04-01 to 2022-05-02 | 5.91% | 5.67% | EWJ cut (2.02%, asset -8.61%) |
| 2022-08-01 to 2022-09-01 | 5.59% | 5.47% | EWJ cut (1.67%, asset -6.89%) |
| 2023-02-01 to 2023-03-01 | 4.90% | 4.78% | EWY cut (1.28%, asset -8.43%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 103 | 51 | 52 | 49.51% | 52 | 51 | 83 | -4.03% |
| In Sample | 50 | 30 | 20 | 60.00% | 20 | 30 | 27 | 12.14% |
| Out Of Sample | 53 | 21 | 32 | 39.62% | 32 | 21 | 56 | -16.17% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 27 | 11 | 16 | 40.74% | 16 | 18 | -4.94% |
| VGK | 14 | 6 | 8 | 42.86% | 8 | 19 | -2.32% |
| SPY | 13 | 6 | 7 | 46.15% | 7 | 17 | -0.67% |
| EWJ | 17 | 10 | 7 | 58.82% | 7 | 18 | 0.76% |
| EWH | 32 | 18 | 14 | 56.25% | 14 | 11 | 3.13% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2022-11-01 to 2022-12-01 | EWH | cut | 21.44% | -4.78% |
| 2024-09-03 to 2024-10-01 | EWH | cut | 20.68% | -4.09% |
| 2023-01-03 to 2023-02-01 | EWY | cut | 17.46% | -3.02% |
| 2025-06-02 to 2025-07-01 | EWY | cut | 16.03% | -2.87% |
| 2022-11-01 to 2022-12-01 | EWJ | cut | 11.53% | -2.61% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |
| 2026-03-02 to 2026-04-01 | EWY | -14.45% |
| 2025-11-03 to 2025-12-01 | EWY | -10.08% |
| 2022-02-01 to 2022-03-01 | VGK | -8.90% |
| 2022-04-01 to 2022-05-02 | SPY | -8.49% |
| 2021-09-01 to 2021-10-01 | EWY | -8.20% |