# Signal Comparison

- Baseline: SOTA: risk parity + relative momentum 126/252d regime
- Candidate: Research: risk parity + decision-tree-signal-d3-tilt-0p2
- Out-of-sample split: 2023-01-01
- Range: 2012-01-03 to 2026-04-29

| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | SOTA: risk parity + relative momentum 126/252d regime | 281.84% | 9.81% | -29.60% | 0.68 | 0.64 | 0.33 | n/a |
| Full | Research: risk parity + decision-tree-signal-d3-tilt-0p2 | 310.84% | 10.37% | -29.30% | 0.72 | 0.68 | 0.35 | 29.00% |
| In Sample | SOTA: risk parity + relative momentum 126/252d regime | 110.19% | 6.99% | -29.60% | 0.51 | 0.47 | 0.24 | n/a |
| In Sample | Research: risk parity + decision-tree-signal-d3-tilt-0p2 | 125.66% | 7.69% | -29.30% | 0.55 | 0.51 | 0.26 | 15.47% |
| Out Of Sample | SOTA: risk parity + relative momentum 126/252d regime | 82.58% | 19.89% | -12.97% | 1.28 | 1.28 | 1.53 | n/a |
| Out Of Sample | Research: risk parity + decision-tree-signal-d3-tilt-0p2 | 83.08% | 19.99% | -12.89% | 1.29 | 1.31 | 1.55 | 0.50% |

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

- Name: Research: risk parity + decision-tree-signal-d3-tilt-0p2
- State: research
- Description: Research candidate using an in-sample-trained regression decision tree over the signal library.

#### Layers

```mermaid
flowchart LR
  L1["Market data<br/>Adjusted ETF closes, volumes, and USD/CNH FX for SPY, VGK, EWJ, EWH, EWY."]
  L2["Monthly rebalance<br/>Recompute targets on the first available trading day of each month."]
  L1 --> L2
  L3["Risk parity beta<br/>63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve."]
  L2 --> L3
  L4["Decision-tree signal overlay<br/>Train a max-depth 3 regression tree on 655 in-sample asset-month observations from the signal library; tilt 0.20, cap active weight 0.06."]
  L3 --> L4
  L5["Final target weights<br/>Normalize portfolio weights and feed the daily backtest execution engine."]
  L4 --> L5
```

#### Decision Tree

```mermaid
flowchart TD
  A(["In-sample rebalance rows"]) --> B["Compute signal-library features"]
  B --> C["Target = next-month asset return minus basket mean"]
  C --> D["Fit regression tree, max depth 3"]
  D --> E(["Freeze tree before OOS starts"])
  E --> F["Score ETFs at each rebalance"]
  F --> G["Rank forecasts and apply tilt 0.20"]
  G --> H["Cap active delta at +/-0.06 per ETF"]
  H --> I["Rescale to preserve original invested weight"]
  I --> J(["Final decision-tree targets"])
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

- Lookback bars: 378
- Threshold: 0.00%
- Forward horizon: next_rebalance

| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 760 | 536 | 224 | 0.70% | 1.02% | -0.32% | 54.87% | -0.06 |
| In Sample | 565 | 407 | 158 | 0.31% | 1.09% | -0.77% | 54.34% | -0.09 |
| Out Of Sample | 195 | 129 | 66 | 1.92% | 0.86% | 1.06% | 56.41% | -0.00 |

### Forecast By Symbol

| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 152 | 1.15% | 0.70% | 0.45% | 51.32% | -0.04 |
| EWH | 152 | 0.54% | 0.52% | 0.02% | 56.58% | -0.08 |
| EWJ | 152 | 0.50% | 1.20% | -0.70% | 51.97% | -0.10 |
| VGK | 152 | 0.39% | 1.35% | -0.96% | 51.32% | -0.10 |
| SPY | 152 | 0.93% | 3.31% | -2.39% | 63.16% | -0.12 |

## Signal Attribution

| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 168 | 105 | 63 | 7.33% | 29.00% | 0.04% |
| In Sample | 128 | 82 | 46 | 7.05% | 15.27% | 0.06% |
| Out Of Sample | 40 | 23 | 17 | 0.28% | 0.50% | 0.01% |

### Worst Signal Periods

| Period | Realized Delta | Est. Contribution | Main Negative |
| --- | ---: | ---: | --- |
| 2026-02-02 to 2026-03-02 | -0.70% | -0.71% | EWY underweight (-0.44%, asset 22.00%) |
| 2026-01-02 to 2026-02-02 | -0.48% | -0.48% | EWY underweight (-0.36%, asset 18.30%) |
| 2025-10-01 to 2025-11-03 | -0.46% | -0.47% | EWY underweight (-0.57%, asset 23.07%) |
| 2020-12-01 to 2021-01-04 | -0.37% | -0.37% | EWY underweight (-0.45%, asset 14.23%) |
| 2020-04-01 to 2020-05-01 | -0.26% | -0.26% | SPY underweight (-0.84%, asset 14.89%) |

### Best Signal Periods

| Period | Realized Delta | Est. Contribution | Main Positive |
| --- | ---: | ---: | --- |
| 2022-07-01 to 2022-08-01 | 0.74% | 0.74% | EWH underweight (0.37%, asset -4.83%) |
| 2022-11-01 to 2022-12-01 | 0.53% | 0.55% | EWH overweight (1.21%, asset 21.44%) |
| 2023-01-03 to 2023-02-01 | 0.48% | 0.49% | EWY overweight (0.67%, asset 17.46%) |
| 2022-10-03 to 2022-11-01 | 0.48% | 0.46% | EWH underweight (0.25%, asset -9.78%) |
| 2026-04-01 to 2026-04-29 | 0.42% | 0.41% | SPY overweight (0.70%, asset 8.60%) |

## Decision Quality

| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 839 | 436 | 403 | 51.97% | 250 | 187 | 0 | 7.33% |
| In Sample | 639 | 336 | 303 | 52.58% | 184 | 146 | 0 | 7.05% |
| Out Of Sample | 200 | 100 | 100 | 50.00% | 66 | 41 | 0 | 0.28% |

### Decision Quality By Symbol

| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EWY | 168 | 77 | 91 | 45.83% | 48 | 0 | -2.26% |
| EWJ | 168 | 80 | 88 | 47.62% | 69 | 0 | -0.34% |
| VGK | 168 | 83 | 85 | 49.40% | 67 | 0 | 1.13% |
| EWH | 168 | 89 | 79 | 52.98% | 54 | 0 | 3.38% |
| SPY | 167 | 107 | 60 | 64.07% | 12 | 0 | 5.42% |

### Worst False Exits

| Period | Symbol | Action | Asset Return | Est. Contribution |
| --- | --- | --- | ---: | ---: |
| 2020-04-01 to 2020-05-01 | SPY | underweight | 14.89% | -0.84% |
| 2025-10-01 to 2025-11-03 | EWY | underweight | 23.07% | -0.57% |
| 2020-12-01 to 2021-01-04 | EWY | underweight | 14.23% | -0.45% |
| 2026-02-02 to 2026-03-02 | EWY | underweight | 22.00% | -0.44% |
| 2020-11-02 to 2020-12-01 | EWY | underweight | 18.01% | -0.44% |

### Worst False Keeps

| Period | Symbol | Asset Return |
| --- | --- | ---: |