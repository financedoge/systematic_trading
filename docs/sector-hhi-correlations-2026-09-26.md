# Sector-volume HHI and subsequent returns — 2026-09-26

The requested scatter plots show weak correlation between aggregate sector-ETF
volume concentration and subsequent SPY returns, and almost no correlation for
raw daily first and second differences. Smoothing does not establish a useful
second-derivative relationship. This descriptive study leaves current SOTA
unchanged.

## Artifacts and replay

Frozen bundle: `D:/systematic_trading_data/research/sector-hhi-20260926-v1/`.
Open `index.html` for a selector covering SPY, an equal-weight sector basket and
each sector's own return. The bundle contains 19 scatter grids, a time-series
plot, a sector correlation heatmap, `observations.csv`, `correlations.json`,
`report.md`, raw provider responses, protocol, provenance and SHA-256 manifests.
The plotting script and calculation module are copied into the bundle.

```powershell
.\.venv\Scripts\python.exe scripts/plot_sector_hhi_correlations.py --root D:/systematic_trading_data/research/sector-hhi-20260926-v1 --plot-deps D:/systematic_trading_data/lean/research/plot_dependencies
```

The fetch script requires a fresh output root to avoid replacing frozen data.

## Definitions and coverage

Data are daily Yahoo chart responses for SPY and XLB, XLC, XLE, XLF, XLI, XLK,
XLP, XLRE, XLU, XLV and XLY, mapped using the
[issuer's sector list](https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs).
All twelve series have 2,078 aligned observed sessions through September 24,
2026. The analysis begins in 2019, after all eleven sector ETFs existed.
All scatter panels use 1,823 signal dates from January 2, 2019 through April 2,
2026; each date has all three forward outcomes. The timeline retains later
dates and leaves unavailable future returns missing.

- HHI is `sum((sector ETF volume / total ETF volume)^2)` across the eleven ETFs.
- First difference is `H[t] - H[t-1]`; second is `H[t] - 2*H[t-1] + H[t-2]`.
- Smoothed sensitivity applies causal EMA(10), then lag-10 differences divided
  by 10 and 100 respectively. It was specified before calculating results.
- Dollar-volume sensitivity replaces volume with provider close times volume.
- Return is `adjusted_close[t+h] / adjusted_close[t] - 1`, in USD, for 20, 60
  and 120 trading sessions. The sector basket is equal capital at the signal
  date, held for the horizon. It is not rebalanced daily.

Rows in each scatter grid are HHI, first derivative and second derivative;
columns are the three horizons. Black lines are in-sample linear fits, orange
lines connect five equal-count bin means, and gray/teal marks signal dates
before/from 2023. The period split is a diagnostic, not an untouched holdout.

## Findings

Pearson correlations with subsequent SPY returns:

| Definition | Feature | 20 sessions | 60 sessions | 120 sessions |
| --- | --- | ---: | ---: | ---: |
| Raw share volume | HHI | +0.075 | +0.115 | +0.093 |
| Raw share volume | First difference | -0.012 | -0.002 | -0.001 |
| Raw share volume | Second difference | -0.011 | -0.004 | -0.005 |
| Smoothed share volume | HHI | +0.108 | +0.136 | +0.103 |
| Smoothed share volume | First difference | +0.018 | +0.077 | +0.083 |
| Smoothed share volume | Second difference | -0.012 | +0.026 | +0.024 |
| Raw dollar volume | HHI | +0.034 | +0.030 | -0.011 |

Raw share-volume HHI correlations before 2023 are +0.165/+0.252/+0.284;
from 2023 they are -0.058/+0.021/-0.053. The equal-weight sector basket's raw
level correlations are +0.083/+0.157/+0.168, with near-zero daily derivative
correlations. These results do not establish a stable acceleration signal.

Forward outcomes overlap, so daily sample size is not a count of independent
observations. The report gives exploratory 95% paired circular-block intervals
(240-session blocks, 1,000 replicates, seed 20260926). All SPY HHI-level
intervals span zero. Multiple-comparison adjustment is not applied. Full
statistics include rank correlations and one phase of nonoverlapping sampling.

This measures trading activity in a fixed ETF basket, not net subscriptions or
total trading of the underlying sectors. Share units, splits and ETF popularity
affect it. Provider historical close/volume adjustment and publication vintages
remain uncertified; dollar-volume results are a sensitivity check. Features
use only data through the signal date, but contemporaneous data availability
and same-close execution are not established by this chart study. This is not
a new LEAN backtest or a direct test of actual capital inflows.

Validation: eight focused calculation tests passed; Ruff passed. Raw/smoothed
main scatter grids, timeline and sector heatmap were visually inspected.
