# Signal Comparison

- Baseline: SOTA: risk parity + relative momentum 126/252d regime
- Candidate: Research: risk parity + ts-momentum-252d-reallocate
- Out-of-sample split: 2023-01-01
- Range: 2012-01-03 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | SOTA: risk parity + relative momentum 126/252d regime | 281.84% | 9.81% | -29.60% | 0.68 | 0.64 | 0.33 | n/a |
| Full | Research: risk parity + ts-momentum-252d-reallocate | 118.09% | 5.60% | -38.72% | 0.44 | 0.40 | 0.14 | -163.75% |
| In Sample | SOTA: risk parity + relative momentum 126/252d regime | 110.19% | 6.99% | -29.60% | 0.51 | 0.47 | 0.24 | n/a |
| In Sample | Research: risk parity + ts-momentum-252d-reallocate | 37.09% | 2.91% | -38.72% | 0.27 | 0.24 | 0.08 | -73.11% |
| Out Of Sample | SOTA: risk parity + relative momentum 126/252d regime | 82.58% | 19.89% | -12.97% | 1.28 | 1.28 | 1.53 | n/a |
| Out Of Sample | Research: risk parity + ts-momentum-252d-reallocate | 60.59% | 15.35% | -13.65% | 1.06 | 1.04 | 1.12 | -21.98% |

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

- Name: Research: risk parity + ts-momentum-252d-reallocate
- State: research
- Description: Research candidate using absolute time-series momentum gating.

#### Layers

```mermaid
flowchart LR
  L1["Market data<br/>Adjusted ETF closes, volumes, and USD/CNH FX for SPY, VGK, EWJ, EWH, EWY."]
  L2["Monthly rebalance<br/>Recompute targets on the first available trading day of each month."]
  L1 --> L2
  L3["Risk parity beta<br/>63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve."]
  L2 --> L3
  L4["Time-series momentum overlay<br/>Keep assets above 252d return threshold 0; otherwise reduce to zero and reallocate survivors."]
  L3 --> L4
  L5["Final target weights<br/>Normalize portfolio weights and feed the daily backtest execution engine."]
  L4 --> L5
```

#### Decision Tree

```mermaid
flowchart TD
  A(["Risk-parity targets"]) --> B{"Enough lookback history for asset?"}
  B -- "No" --> C["Keep asset weight"]
  B -- "Yes" --> D{"252d return > 0?"}
  D -- "Yes" --> C
  D -- "No" --> E["Set asset weight to zero"]
  E --> F["reallocate survivors"]
  F --> G(["Final trend targets"])
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

- Lookback bars: 252
- Threshold: 0.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 790 | 549 | 241 | 0.59% | 1.27% | -0.67% | 54.05% | -0.03 |
| In Sample | 595 | 400 | 195 | 0.29% | 1.10% | -0.81% | 53.61% | -0.06 |
| Out Of Sample | 195 | 149 | 46 | 1.42% | 2.00% | -0.58% | 55.38% | -0.00 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 158 | 1.02% | 0.71% | 0.32% | 52.53% | 0.04 |
| EWJ | 158 | 0.62% | 1.04% | -0.42% | 54.43% | -0.11 |
| EWH | 158 | 0.04% | 1.29% | -1.26% | 49.37% | -0.08 |
| VGK | 158 | 0.24% | 1.69% | -1.45% | 50.00% | -0.12 |
| SPY | 158 | 0.97% | 2.85% | -1.87% | 63.92% | -0.10 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 168 | 66 | 94 | -58.43% | -163.75% | -0.34% |
| In Sample | 128 | 51 | 69 | -44.83% | -73.34% | -0.34% |
| Out Of Sample | 40 | 15 | 25 | -13.61% | -21.98% | -0.33% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2022-11-01 to 2022-12-01 | -12.67% | -13.08% | EWH cut (-4.49%, asset 21.44%) |
| 2020-04-01 to 2020-05-01 | -9.85% | -9.90% | SPY cut (-2.93%, asset 14.89%) |
| 2023-01-03 to 2023-02-01 | -8.39% | -8.58% | EWY cut (-2.66%, asset 17.46%) |
| 2015-10-01 to 2015-11-02 | -8.34% | -8.40% | SPY cut (-2.41%, asset 9.50%) |
| 2019-01-02 to 2019-02-01 | -7.65% | -7.85% | EWH cut (-1.95%, asset 9.31%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-09-01 to 2022-10-03 | 8.37% | 8.14% | EWH cut (2.45%, asset -8.95%) |
| 2022-06-01 to 2022-07-01 | 6.35% | 6.33% | EWY cut (2.27%, asset -15.10%) |
| 2022-08-01 to 2022-09-01 | 5.50% | 5.40% | EWJ cut (1.76%, asset -6.89%) |
| 2023-02-01 to 2023-03-01 | 4.83% | 4.71% | EWY cut (1.20%, asset -8.43%) |
| 2022-03-01 to 2022-04-01 | 2.55% | 2.55% | SPY overweight (1.53%, asset 5.66%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 795 | 384 | 411 | 48.30% | 247 | 164 | 13 | -58.43% |
| In Sample | 595 | 290 | 305 | 48.74% | 191 | 139 | 13 | -44.83% |
| Out Of Sample | 200 | 94 | 106 | 47.00% | 56 | 25 | 0 | -13.61% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| VGK | 159 | 73 | 86 | 45.91% | 51 | 2 | -23.90% |
| EWH | 159 | 74 | 85 | 46.54% | 51 | 1 | -14.92% |
| EWY | 159 | 72 | 87 | 45.28% | 64 | 3 | -9.20% |
| EWJ | 159 | 79 | 80 | 49.69% | 41 | 4 | -8.94% |
| SPY | 159 | 86 | 73 | 54.09% | 40 | 3 | -1.47% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2022-11-01 to 2022-12-01 | EWH | cut | 21.44% | -4.49% |
| 2024-09-03 to 2024-10-01 | EWH | cut | 20.68% | -3.74% |
| 2020-04-01 to 2020-05-01 | SPY | cut | 14.89% | -2.93% |
| 2020-11-02 to 2020-12-01 | VGK | cut | 17.65% | -2.78% |
| 2022-11-01 to 2022-12-01 | EWJ | cut | 11.53% | -2.77% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |
| 2012-05-01 to 2012-06-01 | VGK | -14.78% |
| 2012-05-01 to 2012-06-01 | EWY | -13.74% |
| 2012-05-01 to 2012-06-01 | EWH | -11.81% |
| 2012-05-01 to 2012-06-01 | EWJ | -10.27% |
| 2012-05-01 to 2012-06-01 | SPY | -8.94% |