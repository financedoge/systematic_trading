# Signal Comparison

- Baseline: Baseline risk parity
- Candidate: Risk parity + ts-momentum-252d-reallocate
- Out-of-sample split: 2023-01-01
- Range: 2021-01-04 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | Baseline risk parity | 42.11% | 6.84% | -24.40% | 0.51 | 0.49 | 0.28 | n/a |
| Full | Risk parity + ts-momentum-252d-reallocate | 35.64% | 5.90% | -19.89% | 0.49 | 0.45 | 0.30 | -6.47% |
| In Sample | Baseline risk parity | -14.18% | -7.42% | -24.40% | -0.41 | -0.38 | -0.30 | n/a |
| In Sample | Risk parity + ts-momentum-252d-reallocate | -8.63% | -4.44% | -19.89% | -0.30 | -0.25 | -0.22 | 5.55% |
| Out Of Sample | Baseline risk parity | 66.44% | 16.60% | -13.03% | 1.09 | 1.08 | 1.27 | n/a |
| Out Of Sample | Risk parity + ts-momentum-252d-reallocate | 49.84% | 12.96% | -14.17% | 0.91 | 0.89 | 0.91 | -16.60% |

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
| Full | 60 | 27 | 25 | -6.87% | -6.47% | -0.10% |
| In Sample | 20 | 5 | 7 | 4.39% | 5.14% | 0.25% |
| Out Of Sample | 40 | 22 | 18 | -11.26% | -16.60% | -0.27% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2022-11-01 to 2022-12-01 | -13.01% | -13.40% | EWH cut (-4.78%, asset 21.44%) |
| 2023-01-03 to 2023-02-01 | -8.65% | -8.85% | EWY cut (-3.02%, asset 17.46%) |
| 2024-09-03 to 2024-10-01 | -3.73% | -3.79% | EWH cut (-4.09%, asset 20.68%) |
| 2022-07-01 to 2022-08-01 | -3.37% | -3.31% | EWJ cut (-1.66%, asset 7.20%) |
| 2023-03-01 to 2023-04-03 | -2.82% | -2.84% | EWJ cut (-1.25%, asset 5.23%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-09-01 to 2022-10-03 | 8.63% | 8.39% | EWY cut (2.37%, asset -14.57%) |
| 2022-06-01 to 2022-07-01 | 7.45% | 7.41% | EWY cut (2.57%, asset -15.10%) |
| 2022-08-01 to 2022-09-01 | 5.59% | 5.47% | EWJ cut (1.67%, asset -6.89%) |
| 2023-02-01 to 2023-03-01 | 4.89% | 4.78% | EWY cut (1.28%, asset -8.43%) |
| 2022-12-01 to 2023-01-03 | 2.55% | 2.61% | EWY cut (1.41%, asset -8.09%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 190 | 101 | 89 | 53.16% | 52 | 51 | 46 | -6.87% |
| In Sample | 55 | 32 | 23 | 58.18% | 20 | 30 | 24 | 4.39% |
| Out Of Sample | 135 | 69 | 66 | 51.11% | 32 | 21 | 22 | -11.26% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 38 | 16 | 22 | 42.11% | 16 | 12 | -5.46% |
| SPY | 38 | 20 | 18 | 52.63% | 7 | 6 | -4.73% |
| VGK | 38 | 20 | 18 | 52.63% | 8 | 9 | -3.69% |
| EWJ | 38 | 23 | 15 | 60.53% | 7 | 10 | 3.14% |
| EWH | 38 | 22 | 16 | 57.89% | 14 | 9 | 3.88% |

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
| 2021-09-01 to 2021-10-01 | EWY | -8.20% |
| 2021-09-01 to 2021-10-01 | EWH | -7.94% |
| 2021-11-01 to 2021-12-01 | VGK | -6.27% |