# Signal Comparison

- Baseline: Baseline risk parity
- Candidate: Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05
- Out-of-sample split: 2023-01-01
- Range: 2021-01-04 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | Baseline risk parity | 42.11% | 6.84% | -24.40% | 0.51 | 0.49 | 0.28 | n/a |
| Full | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | 40.98% | 6.68% | -19.16% | 0.53 | 0.49 | 0.35 | -1.13% |
| In Sample | Baseline risk parity | -14.18% | -7.42% | -24.40% | -0.41 | -0.38 | -0.30 | n/a |
| In Sample | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | -15.79% | -8.29% | -19.16% | -0.64 | -0.53 | -0.43 | -1.60% |
| Out Of Sample | Baseline risk parity | 66.44% | 16.60% | -13.03% | 1.09 | 1.08 | 1.27 | n/a |
| Out Of Sample | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | 68.26% | 16.98% | -13.11% | 1.11 | 1.10 | 1.30 | 1.82% |

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
- Threshold: -5.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 250 | 159 | 91 | 0.98% | 0.35% | 0.63% | 54.80% | 0.04 |
| In Sample | 55 | 8 | 47 | -3.63% | -0.92% | -2.71% | 52.73% | -0.30 |
| Out Of Sample | 195 | 151 | 44 | 1.22% | 1.71% | -0.49% | 55.38% | -0.00 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWJ | 50 | 1.16% | -0.40% | 1.57% | 60.00% | -0.01 |
| EWY | 50 | 1.96% | 1.05% | 0.91% | 46.00% | 0.10 |
| EWH | 50 | 0.67% | -0.22% | 0.90% | 56.00% | 0.03 |
| VGK | 50 | 0.54% | 0.75% | -0.22% | 56.00% | -0.14 |
| SPY | 50 | 0.79% | 1.02% | -0.24% | 56.00% | -0.05 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 60 | 32 | 28 | -2.01% | -1.13% | -0.03% |
| In Sample | 20 | 10 | 10 | -3.07% | -1.59% | -0.14% |
| Out Of Sample | 40 | 22 | 18 | 1.06% | 1.82% | 0.03% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2022-11-01 to 2022-12-01 | -8.46% | -8.71% | EWH underweight (-3.11%, asset 21.44%) |
| 2022-07-01 to 2022-08-01 | -2.20% | -2.15% | EWJ underweight (-1.08%, asset 7.20%) |
| 2022-03-01 to 2022-04-01 | -1.28% | -1.28% | SPY underweight (-0.63%, asset 5.34%) |
| 2022-05-02 to 2022-06-01 | -0.86% | -0.85% | EWH underweight (-0.49%, asset 3.56%) |
| 2025-01-02 to 2025-02-03 | -0.86% | -0.88% | VGK underweight (-0.88%, asset 5.25%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-09-01 to 2022-10-03 | 5.59% | 5.45% | EWY underweight (1.54%, asset -14.57%) |
| 2022-06-01 to 2022-07-01 | 5.06% | 5.05% | EWY underweight (1.67%, asset -15.10%) |
| 2021-12-01 to 2022-01-03 | 1.75% | 1.77% | SPY overweight (2.90%, asset 6.04%) |
| 2024-11-01 to 2024-12-02 | 0.62% | 0.62% | EWY underweight (0.50%, asset -5.51%) |
| 2024-12-02 to 2025-01-02 | 0.62% | 0.62% | EWY underweight (0.89%, asset -9.86%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 225 | 121 | 104 | 53.78% | 55 | 54 | 31 | -2.01% |
| In Sample | 90 | 42 | 48 | 46.67% | 29 | 33 | 5 | -3.07% |
| Out Of Sample | 135 | 79 | 56 | 58.52% | 26 | 21 | 26 | 1.06% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 45 | 26 | 19 | 57.78% | 7 | 6 | -4.85% |
| VGK | 45 | 25 | 20 | 55.56% | 9 | 6 | -1.96% |
| EWJ | 45 | 24 | 21 | 53.33% | 11 | 9 | -0.08% |
| EWY | 45 | 24 | 21 | 53.33% | 13 | 6 | 2.22% |
| EWH | 45 | 22 | 23 | 48.89% | 15 | 4 | 2.65% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2022-11-01 to 2022-12-01 | EWH | underweight | 21.44% | -3.11% |
| 2022-11-01 to 2022-12-01 | EWJ | underweight | 11.53% | -1.70% |
| 2022-11-01 to 2022-12-01 | EWY | underweight | 14.42% | -1.68% |
| 2022-11-01 to 2022-12-01 | VGK | underweight | 13.92% | -1.52% |
| 2023-11-01 to 2023-12-01 | VGK | underweight | 10.07% | -1.42% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |
| 2026-03-02 to 2026-04-01 | EWY | -14.45% |
| 2025-11-03 to 2025-12-01 | EWY | -10.08% |
| 2023-02-01 to 2023-03-01 | EWY | -8.43% |
| 2022-12-01 to 2023-01-03 | EWY | -8.09% |
| 2022-12-01 to 2023-01-03 | SPY | -6.52% |