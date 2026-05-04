# Signal Comparison

- Baseline: Baseline risk parity
- Candidate: Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05
- Out-of-sample split: 2023-01-01
- Range: 2012-01-03 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | Baseline risk parity | 280.63% | 9.78% | -29.39% | 0.68 | 0.64 | 0.33 | n/a |
| Full | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | 205.52% | 8.11% | -29.54% | 0.60 | 0.56 | 0.27 | -75.11% |
| In Sample | Baseline risk parity | 110.98% | 7.03% | -29.39% | 0.51 | 0.47 | 0.24 | n/a |
| In Sample | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | 69.01% | 4.89% | -29.54% | 0.40 | 0.36 | 0.17 | -41.97% |
| Out Of Sample | Baseline risk parity | 81.34% | 19.65% | -12.86% | 1.27 | 1.28 | 1.53 | n/a |
| Out Of Sample | Risk parity + adaptive-trend-63-126-252d-reallocate-thr-m0p05 | 81.70% | 19.72% | -13.06% | 1.28 | 1.28 | 1.51 | 0.36% |

Alpha here is candidate return minus baseline return over the same window.

## Market Data Audit

- Source: SQLite var\systematic_trading.db
- Price field: close
- Adjusted prices validated: yes
- Required observations: 3601
- Common required observations: 3601

| Symbol | Obs. | Required Coverage | Missing Required | Max Gap Days | Stale Runs | Non-Positive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWH | 3601 | 100.00% | 0 | 5 | 2 | 0 |
| EWJ | 3601 | 100.00% | 0 | 5 | 1 | 0 |
| EWY | 3601 | 100.00% | 0 | 5 | 0 | 0 |
| SPY | 3601 | 100.00% | 0 | 5 | 0 | 0 |
| VGK | 3601 | 100.00% | 0 | 5 | 0 | 0 |

Warnings:
- EWH has 2 stale close-price runs of at least 3 observations.
- EWJ has 1 stale close-price runs of at least 3 observations.

## Signal Forecast Quality

- Lookback bars: 252
- Threshold: -5.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 790 | 611 | 179 | 0.67% | 1.23% | -0.56% | 55.06% | -0.03 |
| In Sample | 595 | 453 | 142 | 0.40% | 1.03% | -0.63% | 54.79% | -0.06 |
| Out Of Sample | 195 | 158 | 37 | 1.45% | 2.03% | -0.58% | 55.90% | -0.00 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 158 | 1.32% | 0.12% | 1.20% | 55.70% | 0.04 |
| EWJ | 158 | 0.70% | 0.89% | -0.19% | 55.06% | -0.11 |
| EWH | 158 | 0.13% | 1.46% | -1.33% | 49.37% | -0.08 |
| SPY | 158 | 1.05% | 2.61% | -1.55% | 65.82% | -0.10 |
| VGK | 158 | 0.17% | 2.66% | -2.49% | 49.37% | -0.12 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 168 | 83 | 85 | -24.28% | -75.11% | -0.14% |
| In Sample | 128 | 62 | 66 | -24.41% | -41.75% | -0.19% |
| Out Of Sample | 40 | 21 | 19 | 0.14% | 0.36% | 0.00% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2022-11-01 to 2022-12-01 | -8.43% | -8.71% | EWH underweight (-3.10%, asset 21.44%) |
| 2020-04-01 to 2020-05-01 | -6.35% | -6.40% | SPY underweight (-1.71%, asset 14.89%) |
| 2015-10-01 to 2015-11-02 | -5.44% | -5.48% | EWY underweight (-1.43%, asset 11.58%) |
| 2012-06-01 to 2012-07-02 | -5.20% | -5.23% | EWJ underweight (-1.53%, asset 9.48%) |
| 2019-01-02 to 2019-02-01 | -4.98% | -5.11% | EWH underweight (-1.20%, asset 9.31%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-09-01 to 2022-10-03 | 5.51% | 5.37% | EWY underweight (1.52%, asset -14.57%) |
| 2022-06-01 to 2022-07-01 | 5.42% | 5.41% | EWY underweight (1.67%, asset -15.10%) |
| 2022-03-01 to 2022-04-01 | 2.28% | 2.28% | SPY overweight (2.95%, asset 5.66%) |
| 2016-03-01 to 2016-04-01 | 1.21% | 1.23% | EWY overweight (1.49%, asset 8.68%) |
| 2014-10-01 to 2014-11-03 | 0.72% | 0.73% | SPY overweight (0.36%, asset 3.82%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 540 | 270 | 270 | 50.00% | 145 | 98 | 118 | -24.28% |
| In Sample | 425 | 210 | 215 | 49.41% | 122 | 83 | 90 | -24.41% |
| Out Of Sample | 115 | 60 | 55 | 52.17% | 23 | 15 | 28 | 0.14% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| VGK | 108 | 52 | 56 | 48.15% | 27 | 26 | -12.54% |
| EWH | 108 | 50 | 58 | 46.30% | 31 | 22 | -4.92% |
| EWJ | 108 | 57 | 51 | 52.78% | 26 | 25 | -4.13% |
| EWY | 108 | 50 | 58 | 46.30% | 44 | 27 | -3.72% |
| SPY | 108 | 61 | 47 | 56.48% | 17 | 18 | 1.03% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2022-11-01 to 2022-12-01 | EWH | underweight | 21.44% | -3.10% |
| 2020-04-01 to 2020-05-01 | SPY | underweight | 14.89% | -1.71% |
| 2022-11-01 to 2022-12-01 | EWJ | underweight | 11.53% | -1.70% |
| 2020-05-01 to 2020-06-01 | EWJ | underweight | 10.62% | -1.69% |
| 2022-11-01 to 2022-12-01 | EWY | underweight | 14.42% | -1.68% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |
| 2020-03-02 to 2020-04-01 | EWY | -22.27% |
| 2020-03-02 to 2020-04-01 | VGK | -21.62% |
| 2020-03-02 to 2020-04-01 | SPY | -19.89% |
| 2020-03-02 to 2020-04-01 | EWH | -15.29% |
| 2012-05-01 to 2012-06-01 | VGK | -14.78% |