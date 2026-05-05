# Parameter Robustness

- Cases: 4
- Ranked by: out_of_sample_delta_return

| Rank | Strategy | Lookback | Threshold | Mode | Tilt | Max Depth | Min Leaf | OOS Alpha | OOS Delta Sharpe | OOS Delta Max DD | Full Alpha | In-Sample Alpha |
| ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | decision-tree-signal-d3-tilt-0p2 | 378 | 0.00% | decision-tree | 0.20 | 3 | 25 | 0.50% | 0.01 | 0.08% | 29.00% | 15.47% |
| 2 | decision-tree-signal-d3-tilt-0p16 | 378 | 0.00% | decision-tree | 0.16 | 3 | 25 | 0.15% | 0.01 | 0.08% | 22.95% | 12.55% |
| 3 | decision-tree-signal-d3-tilt-0p12 | 378 | 0.00% | decision-tree | 0.12 | 3 | 25 | -0.16% | 0.00 | 0.09% | 16.79% | 9.52% |
| 4 | decision-tree-signal-d3-tilt-0p08 | 378 | 0.00% | decision-tree | 0.08 | 3 | 25 | -0.55% | -0.00 | 0.10% | 10.70% | 6.61% |