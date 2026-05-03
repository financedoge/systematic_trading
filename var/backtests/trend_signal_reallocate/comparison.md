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