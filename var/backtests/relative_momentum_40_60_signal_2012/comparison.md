# Signal Comparison

- Baseline: SOTA: risk parity + relative momentum 126/252d regime
- Candidate: Research: risk parity + relative-momentum-40-60d-regime
- Out-of-sample split: 2023-01-01
- Range: 2012-01-03 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | SOTA: risk parity + relative momentum 126/252d regime | 281.84% | 9.81% | -29.60% | 0.68 | 0.64 | 0.33 | n/a |
| Full | Research: risk parity + relative-momentum-40-60d-regime | 280.56% | 9.78% | -29.52% | 0.68 | 0.64 | 0.33 | -1.29% |
| In Sample | SOTA: risk parity + relative momentum 126/252d regime | 110.19% | 6.99% | -29.60% | 0.51 | 0.47 | 0.24 | n/a |
| In Sample | Research: risk parity + relative-momentum-40-60d-regime | 109.40% | 6.96% | -29.52% | 0.51 | 0.47 | 0.24 | -0.80% |
| Out Of Sample | SOTA: risk parity + relative momentum 126/252d regime | 82.58% | 19.89% | -12.97% | 1.28 | 1.28 | 1.53 | n/a |
| Out Of Sample | Research: risk parity + relative-momentum-40-60d-regime | 82.82% | 19.94% | -12.91% | 1.28 | 1.29 | 1.54 | 0.24% |

Alpha here is candidate return minus baseline return over the same window.

## Model Structure

### Baseline / SOTA

- Name: SOTA: risk parity + relative momentum 126/252d regime
- State: sota
- Promoted on: 2026-05-05
- Description: Monthly risk parity with a regime-gated cross-sectional relative momentum tilt. This is the current research hurdle for new candidate strategies.

#### Layers

```mermaid
flowchart LR
  L1["Market data<br/>Adjusted ETF closes, volumes, and USD/CNH FX for SPY, VGK, EWJ, EWH, EWY."]
  L2["Monthly rebalance<br/>Recompute targets on the first available trading day of each month."]
  L1 --> L2
  L3["Risk parity beta<br/>63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve."]
  L2 --> L3
  L4["Relative momentum overlay<br/>Score = 45% 126d momentum + 55% 252d momentum; regime drawdown trigger -0.08, vol-ratio trigger 1.35; tilt 0.12 calm / 0.12 risk; cap active weight 0.07."]
  L3 --> L4
  L5["Final target weights<br/>Normalize portfolio weights and feed the daily backtest execution engine."]
  L4 --> L5
```

#### Decision Tree

```mermaid
flowchart TD
  A(["Risk-parity targets"]) --> B{"Enough 126d and 252d history for the basket?"}
  B -- "No" --> C["Keep risk-parity targets"]
  B -- "Yes" --> D["Score each ETF = 45% medium momentum + 55% long momentum"]
  D --> E{"Basket drawdown <= -0.08 or vol-ratio >= 1.35?"}
  E -- "Yes" --> F["Use risk tilt 0.12"]
  E -- "No" --> G["Use calm tilt 0.12"]
  F --> H["Rank ETFs by score"]
  G --> H
  H --> I["Multiply base weight by 1 + tilt * rank score"]
  I --> J["Cap active delta at +/-0.07 per ETF"]
  J --> K["Rescale to preserve original invested weight"]
  K --> L(["Final SOTA/research targets"])
```

### Research Candidate

- Name: Research: risk parity + relative-momentum-40-60d-regime
- State: research
- Description: Research candidate using a regime-gated cross-sectional relative momentum overlay.

#### Layers

```mermaid
flowchart LR
  L1["Market data<br/>Adjusted ETF closes, volumes, and USD/CNH FX for SPY, VGK, EWJ, EWH, EWY."]
  L2["Monthly rebalance<br/>Recompute targets on the first available trading day of each month."]
  L1 --> L2
  L3["Risk parity beta<br/>63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve."]
  L2 --> L3
  L4["Relative momentum overlay<br/>Score = 45% 40d momentum + 55% 60d momentum; regime drawdown trigger -0.08, vol-ratio trigger 1.35; tilt 0.12 calm / 0.12 risk; cap active weight 0.07."]
  L3 --> L4
  L5["Final target weights<br/>Normalize portfolio weights and feed the daily backtest execution engine."]
  L4 --> L5
```

#### Decision Tree

```mermaid
flowchart TD
  A(["Risk-parity targets"]) --> B{"Enough 126d and 252d history for the basket?"}
  B -- "No" --> C["Keep risk-parity targets"]
  B -- "Yes" --> D["Score each ETF = 45% medium momentum + 55% long momentum"]
  D --> E{"Basket drawdown <= -0.08 or vol-ratio >= 1.35?"}
  E -- "Yes" --> F["Use risk tilt 0.12"]
  E -- "No" --> G["Use calm tilt 0.12"]
  F --> H["Rank ETFs by score"]
  G --> H
  H --> I["Multiply base weight by 1 + tilt * rank score"]
  I --> J["Cap active delta at +/-0.07 per ETF"]
  J --> K["Rescale to preserve original invested weight"]
  K --> L(["Final SOTA/research targets"])
```

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

- Lookback bars: 60
- Threshold: 0.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 835 | 515 | 320 | 0.76% | 0.92% | -0.16% | 53.17% | -0.08 |
| In Sample | 640 | 370 | 270 | 0.36% | 0.93% | -0.56% | 50.94% | -0.10 |
| Out Of Sample | 195 | 145 | 50 | 1.79% | 0.89% | 0.90% | 60.51% | -0.10 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 167 | 1.32% | 0.31% | 1.01% | 50.90% | -0.03 |
| EWJ | 167 | 0.84% | 0.55% | 0.29% | 53.89% | -0.07 |
| EWH | 167 | 0.40% | 0.81% | -0.41% | 51.50% | -0.14 |
| VGK | 167 | 0.43% | 1.34% | -0.91% | 51.50% | -0.10 |
| SPY | 167 | 0.83% | 2.19% | -1.36% | 58.08% | -0.18 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 168 | 86 | 82 | -0.27% | -1.29% | -0.00% |
| In Sample | 128 | 69 | 59 | -0.47% | -0.98% | -0.00% |
| Out Of Sample | 40 | 17 | 23 | 0.20% | 0.24% | 0.00% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2020-05-01 to 2020-06-01 | -0.36% | -0.36% | SPY underweight (-0.19%, asset 8.05%) |
| 2024-06-03 to 2024-07-01 | -0.34% | -0.34% | EWH overweight (-0.22%, asset -6.36%) |
| 2024-01-02 to 2024-02-01 | -0.34% | -0.34% | EWY overweight (-0.14%, asset -5.31%) |
| 2013-01-02 to 2013-02-01 | -0.30% | -0.31% | EWY overweight (-0.19%, asset -8.36%) |
| 2015-02-02 to 2015-03-02 | -0.24% | -0.25% | SPY underweight (-0.14%, asset 4.99%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2025-06-02 to 2025-07-01 | 0.47% | 0.48% | EWY overweight (0.70%, asset 16.03%) |
| 2023-05-01 to 2023-06-01 | 0.37% | 0.36% | EWH underweight (0.31%, asset -8.22%) |
| 2022-10-03 to 2022-11-01 | 0.37% | 0.35% | EWH underweight (0.28%, asset -9.78%) |
| 2014-07-01 to 2014-08-01 | 0.35% | 0.35% | VGK underweight (0.32%, asset -5.92%) |
| 2024-09-03 to 2024-10-01 | 0.24% | 0.25% | EWH overweight (0.26%, asset 20.68%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 765 | 380 | 385 | 49.67% | 226 | 151 | 25 | -0.27% |
| In Sample | 591 | 298 | 293 | 50.42% | 175 | 124 | 19 | -0.47% |
| Out Of Sample | 174 | 82 | 92 | 47.13% | 51 | 27 | 6 | 0.20% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 154 | 65 | 89 | 42.21% | 68 | 3 | -2.65% |
| EWH | 155 | 82 | 73 | 52.90% | 38 | 7 | -0.33% |
| EWY | 150 | 74 | 76 | 49.33% | 38 | 5 | -0.23% |
| EWJ | 154 | 77 | 77 | 50.00% | 44 | 6 | 0.66% |
| VGK | 152 | 82 | 70 | 53.95% | 38 | 4 | 2.29% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2020-04-01 to 2020-05-01 | SPY | underweight | 14.89% | -0.34% |
| 2022-11-01 to 2022-12-01 | EWH | underweight | 21.44% | -0.26% |
| 2020-11-02 to 2020-12-01 | SPY | underweight | 10.85% | -0.25% |
| 2019-01-02 to 2019-02-01 | SPY | underweight | 7.95% | -0.25% |
| 2020-11-02 to 2020-12-01 | VGK | underweight | 17.65% | -0.23% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |
| 2022-08-01 to 2022-09-01 | VGK | -8.80% |
| 2014-01-02 to 2014-02-03 | EWH | -7.80% |
| 2023-09-01 to 2023-10-02 | EWY | -7.53% |
| 2023-09-01 to 2023-10-02 | EWH | -7.33% |
| 2014-01-02 to 2014-02-03 | EWJ | -7.04% |