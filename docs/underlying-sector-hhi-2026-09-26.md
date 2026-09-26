# Underlying-stock sector concentration research

The ETF-only study cannot establish a relationship for the underlying stock
market. This follow-up uses historical monthly constituent lists from the
[issuer's ITOT holdings archive](https://www.blackrock.com/ae/intermediaries/products/239724/ishares-core-sp-total-us-stock-market-etf)
to identify a broad US equity sample, then aggregates the stocks' own volume
and returns. Fund prices and volumes are not used in these sector aggregates.

## Reproducible inputs

Bundle: `D:/systematic_trading_data/research/underlying-sector-hhi-20260926-v1/`.
The 95 dated monthly snapshots run from October 2018 through August 2026 and
contain 5,156 distinct requested symbols. Daily stock history comes from Yahoo,
October 2018 through September 24, 2026. Raw holdings CSVs, raw chart responses,
download failures, source URLs, retrieval times and hashes are retained.

Each monthly snapshot activates after 45 calendar days. This is a conservative
modeling assumption, not evidence of its actual publication time. Historical
revision vintages remain unknown. Stock identities are screened against provider
names; obvious mismatches and ambiguous multiple-sector matches are excluded
from calculated values while retained in coverage denominators. This catches
some ticker reuse, but cannot replace a permanent security identifier.

The user explicitly chose available public data. Missing delisted-stock histories
remain a material limitation. A high fraction of portfolio value covered does
not bound the fraction of trading volume missing. ITOT is a broad index sample,
not an exact exchange-wide census.

## Calculation contract

- Sector share volume sums observed constituent shares traded. Primary sector
  dollar turnover sums provider close times shares traded. No fund trading is
  used and no missing stock volume is invented.
- Across-sector HHI sums squared sector shares of total observed activity.
  Within-sector HHI separately sums squared stock shares of sector activity.
  These are different questions; plot titles identify which one is shown.
- Daily sector returns average observed constituent adjusted-close returns,
  weighted by portfolio values from the lagged snapshot. The market aggregate
  uses all observed constituent stocks. An equal-stock-weight sensitivity is
  also calculated. These are observed-subset portfolios, not replicas of an
  official sector index; snapshot weights do not equal daily float market caps.
- Raw backward derivatives use lag 1; smoothed derivatives use causal EMA(10)
  and lag-10 differences. Each derivative stencil uses the same dated cohort
  to avoid mechanical concentration changes when monthly membership changes.
- Forward returns compound the next 20, 60 or 120 daily aggregate returns.
  No incomplete forward horizon is filled. All panels within a grid use the
  same signal dates. Labels overlap and are not independent observations.
- Coverage-qualified plots require at least 95% of each sector's lagged
  portfolio value and 70% of its constituent names. The rules apply through
  the backward feature window and each relevant future return day. Separate
  observed-subset plots show lower-coverage dates with explicit labels.

The frozen protocol precedes correlation results. Neither this pilot nor its
coverage-qualified subset is certified point-in-time strategy evidence. Volume
measures trading activity, not net capital inflow. The existing LEAN comparison
and SOTA remain unchanged.

## Results and coverage

There are 3,267 populated stock histories containing 5,923,052 daily records.
Another 32 provider responses were accepted but contained no observations in
the requested interval; their zero coverage is retained.
The archive also retains 5,157 endpoint-status records and 299,575 holding rows
across 95 snapshots. The endpoint total includes the additional HEICO class-A
normalization; original failed ticker requests remain in the audit. There are
1,858 unavailable/rejected endpoint histories. Issuer-verified supplementary
renames are frozen in `symbol_aliases.json` with their supporting sources.

Only 259 of the 1,943 analysis sessions satisfy both volume-coverage rules
across all eleven sectors. Requiring complete 120-session forward outcomes
leaves **139 common signal dates, September 15, 2025–April 2, 2026**. This
short, overlapping sample cannot establish a stable market-wide relationship.

Pearson correlations for underlying-stock dollar-volume HHI and the aggregated
underlying-stock return:

| Sample | Signal | 20 sessions | 60 sessions | 120 sessions |
| --- | --- | ---: | ---: | ---: |
| Coverage-qualified, n=139 | HHI | +0.038 | +0.250 | -0.117 |
| Coverage-qualified, n=139 | First difference | -0.002 | -0.014 | -0.009 |
| Coverage-qualified, n=139 | Second difference | +0.019 | +0.014 | +0.027 |
| All observed subsets, n=1,823 | HHI | -0.083 | -0.051 | +0.009 |
| All observed subsets, n=1,823 | First difference | +0.007 | -0.007 | +0.001 |
| All observed subsets, n=1,823 | Second difference | +0.005 | -0.000 | -0.000 |

The longer sample includes substantial missing history. Median portfolio-value
coverage is about 86% in Energy, 87% in Real Estate and 90% in Industrials;
median name coverage is about 61% in Health Care and 66% in Energy. Correlation
on these changing observed subsets is not a full-market estimate. Smoothing
raises the qualified 60-session HHI correlation to +0.542, but its short sample
and overlapping labels prevent a reliable significance or stability claim.
The corresponding smoothed second-difference correlations remain small
(+0.093/-0.017/-0.009). No result justifies promoting a new strategy.

The gallery contains 43 PNG figures covering
market and sector returns, dollar/share volume, raw/smoothed differences,
within-sector stock concentration, coverage and time series. Main raw grids
and coverage figures were visually inspected. The calculated sector CSV and
reports are archived separately in ClickHouse; forward labels have their own
family rather than being mixed into signal-feature rows.

## ClickHouse archive

The user requested persistent ClickHouse storage of the downloaded history.
Completed source import: **6,227,784 observations and 8,696 exact source
documents**, plus the dataset publication manifest. Computed analysis adds
21,373 aggregate observations, 64,119 forward labels and four report documents.
The earlier ETF dataset adds 24,936 bars and its original sources. Exact hashes
are verified before publication; final family counts and an AAPL historical
query matched source expectations. Eighteen focused tests and Ruff passed.
Import/readback receipts are under `var/research/*clickhouse*.json`.

The importer uses existing `analytics.observations`, `analytics.documents` and
`analytics.publications` contracts, with exact row/document hash readback before
publication. It does not overwrite `market_data.daily_bars` or operational
classifications. Source files are retained as replay and recovery evidence.

Dataset source prefixes:

- `sector-research/sector-hhi-20260926-v1/` — previous ETF study.
- `sector-research/underlying-sector-hhi-20260926-v1/` — dated holdings and stock history.

Families are `research_equity_daily_bar`, `research_sector_constituent` and
`research_download_status`. Computed histories use `research_sector_aggregate`
and `research_forward_return_label` under the dataset's `/analysis` source.
Original historical availability remains NULL;
retrieval timestamps and the modeled holdings availability are separate fields.
Unknown/invalid fields are nullable and quality-flagged; raw source documents
include corporate actions and all original provider fields.

Query only committed source versions via `analytics.current_observations`,
and filter `workspace` using the value in the import receipt when multiple
workspaces share the server. For example:

```sql
SELECT entity,
       JSONExtractString(payload, 'date') AS trade_date,
       JSONExtract(payload, 'close', 'Nullable(Float64)') AS provider_close,
       JSONExtract(payload, 'adjusted_close', 'Nullable(Float64)') AS adjusted_close,
       JSONExtract(payload, 'volume', 'Nullable(Float64)') AS volume,
       available_at
FROM analytics.current_observations
WHERE startsWith(source_id,
      'sector-research/underlying-sector-hhi-20260926-v1/bars/')
  AND family = 'research_equity_daily_bar'
  AND entity = 'NVDA'
ORDER BY trade_date;
```

Import/replay commands:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_underlying_sector_data.py --root D:/systematic_trading_data/research/underlying-sector-hhi-20260926-v1 --stage all
.\.venv\Scripts\python.exe scripts/analyze_underlying_sectors.py --root D:/systematic_trading_data/research/underlying-sector-hhi-20260926-v1 --plot-deps D:/systematic_trading_data/lean/research/plot_dependencies
.\.venv\Scripts\python.exe scripts/import_sector_research_clickhouse.py --root D:/systematic_trading_data/research/underlying-sector-hhi-20260926-v1 --receipt var/research/underlying-sector-clickhouse-receipt.json
```

The fetch command resumes existing observations rather than replacing captures.
Use a fresh root for a new provider vintage. ClickHouse remains on the D: Docker
volume; normal PostgreSQL NAS snapshots do not transport this data. Retained
source bundles can rebuild these verified projections after a PC handoff.

## Data needed for a definitive test

Complete delisted-stock price/return histories, permanent security IDs, splits
and other corporate actions, dated sector classification changes, historical
daily eligibility and publication/revision timestamps are still required.
For LEAN, the documented
[US Fundamental Data](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/morningstar/us-fundamental-data)
and [US Equity Security Master](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-security-master)
provide the relevant interfaces for fundamentals, sector codes and security
events; access and dataset-version quality would need verification before use.
