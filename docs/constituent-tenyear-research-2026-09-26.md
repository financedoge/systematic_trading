# Longer constituent evidence and the Market Data archive

This follow-up addresses two gaps: the prior constituent comparison only had
coverage-qualified signals from January 2023, and the application did not expose
the research histories already stored in ClickHouse. It does not promote a strategy.

## Results and assessment

**The longer evidence does not justify replacing SOTA.** Twenty-two long native
LEAN runs and four frozen-model companion runs passed the original target, fill,
cash and NAV parity tolerances. The table below uses the chronologically fitted
historical baseline over January 2016–September 2026, net of the declared costs.

| Variant | CAGR | Sharpe | IR versus matched baseline |
| --- | ---: | ---: | ---: |
| Historical SOTA recipe | 9.64% | 0.932 | — |
| Early signed stock activity | 9.68% | 0.936 | +0.158 |
| Early ETF-price control | 9.69% | 0.937 | +0.190 |
| Joint stock/price residual tree | 9.67% | 0.934 | +0.218 |
| Price-only residual tree | 9.67% | 0.934 | +0.203 |
| Concentration acceleration | 9.59% | 0.927 | −0.232 |

Early signed activity adds only **3.4 basis points of annual CAGR**. Its 63-session
block interval for annual arithmetic active return is −0.081 to +0.136 percentage
points; the current-family adjusted p-value is 0.813. Its direct IR against the
price control is −0.073. Earlier placement does not improve signed activity over
its late counterpart. Joint-tree stock information adds just 0.002 percentage
points of CAGR beyond the price-only tree, direct IR +0.039, adjusted p=0.900.
Selection changes only three decisions and slightly loses return.

The added history matters: early signed activity helps in 2020 (4.75% versus
4.41%), but worsens 2022 (−8.88% versus −8.59%). Its 2020–2022 CAGR/Sharpe is
0.81%/0.127 versus baseline 0.84%/0.130. High-cost and delayed execution retain
only a small gain and do not establish an advantage over the price control.

The separate **actual frozen-model** test, January 2023–September 2026, gives
SOTA 14.391% CAGR/1.264 Sharpe, early signed 14.486%/1.273, and price control
14.470%/1.272. Signed activity's IR is +0.429 versus SOTA but only +0.105 versus
price control; its gain-over-SOTA interval includes zero. This recent improvement
does not establish a stable constituent edge across the longer history.

The extended HHI scatter plots also remain weak: smoothed second-derivative
Pearson correlations with subsequent 20/60/120-session SPY returns are
+0.068/+0.015/+0.019. These are descriptive, overlapping observations, not
independent forecast trials or evidence of actual fund inflows.

- [Full results and controls](D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2/report.md)
- [Return, IR and coverage chart](D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2/results.png)
- [HHI and derivative scatter plots](D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2/hhi_scatter.png)

The next useful evidence is better ETF-specific identity/publication history and
prospective validation of fixed candidates. Neither a deeper tree nor further
tuning of this inspected sample is justified by these results.

## Why January 2023

The previous ITOT study required 95% of dated holding value and 70% of names to
have complete 211-session price/volume windows, after a modeled holdings-publication
lag. Missing delisted stocks, ticker changes and incomplete histories prevented
earlier dates from passing. The strategy then used its baseline allocation. A
longer chart of that portfolio would not be a longer test of the constituent signal.

The feature lookback is not a Hurst exponent: HHI is a concentration measure;
the features use an EMA and backward finite differences. Neither HHI nor signed
trading activity measures actual net capital flows.

## New public data

- Historical IVV issuer holdings: 170 accepted monthly snapshots from January
  2012 through August 2026, 85,050 equity rows. Six January–June 2017 month-end
  requests returned no holdings; their responses remain in the archive.
- Current Yahoo requests: 885 symbols, 637 successful responses (634 populated
  histories), 248 unavailable requests; 2,298,993 daily observations from 2011
  onward. Empty successes and failures are retained separately.
- Public historical archives: 666 Yahoo2020 stock CSVs and 507 Stooq2017 stock
  CSVs within the dated research universe, containing 7,595,897 observations.
  Original downloaded ZIPs remain on
  disk; the extracted research subset and exact CSV sources are in ClickHouse.
- IVV is a same-index constituent proxy for SPY. These inputs guide the SPY
  sleeve; they are not constituent histories for the other eleven ETFs or a
  census of the whole market.

Sources: [IVV issuer](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf),
[Yahoo2020 archive publisher](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset),
[Stooq2017 archive publisher](https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs/versions/3).

Historical publication and revision timestamps remain unknown. Observed dates,
retrieval timestamps and assumed 45-/60-day availability are distinct; unknown
historical `available_at` stays NULL. Holdings older than 140 days are rejected.
The same provider supplies each stock's entire 211-session feature window. The
preference is current Yahoo, archived Yahoo2020, then Stooq2017; price scales are
never spliced within a window. Missing stocks remain in coverage denominators.

Stooq's OHLC is dividend/split-adjusted. It supplies approximately 4.2% of holding
value in 2016 and 3.5% in 2017; the activity measure therefore mixes provider
conventions in those years. Yahoo-only sensitivity results use a separately
labeled 90% coverage rule. They do not certify the primary input or isolate every
effect of that provider difference. The primary 95% threshold is unchanged.

## Longer experiment

Native LEAN window: **2016-01-04 through 2026-09-24**, with ETF warmup beginning
2012-01-05. **122 of 129 monthly decisions qualify** under the primary rule,
starting 2016-02-01. Neutral decisions: 2016-01-04; 2017-06-01, 2017-07-03,
2017-08-01, 2017-09-01, 2017-12-01; and 2018-01-02. The 2020 and 2022 stress
periods now have constituent coverage. The residual tree becomes usable in
February 2018; its effective history is shorter than the complete backtest.

The deployed SOTA tree was fitted through 2022. Replaying that fitted model in
2016 would expose the historical baseline to future labels. The long comparison
therefore reconstructs the same allocation recipe with annual expanding base-tree
fits. Both base and residual models require labels completed strictly before the
fit date, and models must be available by the prior close. Hyperparameters,
universe and candidate selection still reflect previously inspected research:
chronological fitting is not an untouched holdout or certified point-in-time data.

The predeclared long family comprises 16 specifications (baseline plus 15
challengers/controls) and six matched cost/delay runs. Stages are late allocation,
before-tree allocation, pool selection and residual-tree forecast correction.
The primary follow-up is early signed activity. Controls include ETF momentum,
price-only residual trees, 60-day holdings lag, and Yahoo-only data. Target gross
is matched and active changes remain capped at 3 percentage points per ETF.
The cost stress uses 25bps fees plus 20bps slippage; the delay stress adds one
session. Both use their own matched baseline. A separate four-run comparison
uses the actual frozen production model from January 2023 onward, starting with
fresh CNH cash; its subperiod numbers are not directly interchangeable with the
old study's carried portfolio at January 2023.

## Market Data fix

The histories were in `analytics.observations`, but the application only queried
`market_data.daily_bars` and recorder captures. The new **Market Data → Research
Data** tab reads the existing committed research publications. It provides dataset,
data-type, symbol and date filters, paginated records, page downloads, a price
chart for one source series, and full source/quality/hash details through Inspect.
Stock prices, dated holdings, signals, models, training labels and study results
are discoverable without moving research data into production trading tables.

Open: <http://127.0.0.1:8000/platform/market-data-audit?view=research>.

The read-only endpoints are `/api/v1/market-data/research/datasets`, `/entities`
and `/rows`. Queries are workspace-scoped, restricted to the two research source
prefixes and bounded to 5,000 records per page. Pagination cursors bind to filters;
date and cursor validation prevent accidental cross-query continuation.

## Reproducible artifacts

- Protocol: `config/constituent-tenyear-v1.json` (internal version v2 corrects
  only the ETF warmup boundary; the initial v1 stopped before any native run).
- Long study: `D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2/`.
- Actual frozen-model companion: `D:/systematic_trading_data/lean/research/constituent-frozen-reference-20260926-v1/`.
- Issuer/current histories: `D:/systematic_trading_data/research/ivv-constituents-2012-2026-v1/`.
- Extracted archive: `D:/systematic_trading_data/research/ivv-public-archive-subset-20260926-v1/`.
- Original public ZIPs: `D:/systematic_trading_data/research/public-equity-archives-20260926/`.
- Feature audits: `D:/systematic_trading_data/research/ivv-archive-coverage-v1/`
  and `D:/systematic_trading_data/research/ivv-yahoo-archive-coverage-v1/`.

Each study retains input manifests, feature/model/training-label files, native
bundles and receipts, period summaries, exposure/coverage audits, paired block
intervals and report artifacts. Source and result publication requires exact
payload SHA256 readback before commit; native receipts remain research-only.

```powershell
.venv/Scripts/python.exe scripts/run_constituent_research.py --root D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2 --resume
.venv/Scripts/python.exe scripts/analyze_tenyear_constituents.py --root D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2
.venv/Scripts/python.exe scripts/analyze_constituent_frozen_reference.py --root D:/systematic_trading_data/lean/research/constituent-frozen-reference-20260926-v1
```

The archive importer can resume after local connection failures; committed
versions are not duplicated. Stooq CRLF sources preserve their exact bytes
through UTF-8 decoding. One native selection-price run stalled at the first
data step; its failed receipt/logs remain under `failed_attempts/`, and the same
immutable bundle passed on retry. No strategy parameter changed for recovery.

Validation: 616 full-suite tests passed, 51 optional integrations skipped; the
two dependency deprecation warnings predate this work. Ruff passed for the touched
research/LEAN/browser modules and tests. The charts were visually inspected;
browser checks verified old and new stock histories, dates, holdings, source
inspection, pagination controls and displayed return/Sharpe/IR values. The final
ClickHouse readback confirmed all 7,595,897 archive observations, NULL historical
availability, and exact Stooq source bytes. Approval-policy values, revisions and
history remained unchanged across the dashboard restart. Existing IB Gateway
health probes remained unavailable; no broker repair or order action was taken.

The generic legacy provenance sentence inside the native bundles still mentions
ITOT. The protocol, feature hashes and source receipts identify IVV. This wording
error is explicitly corrected in each study's `provenance_clarification.json`,
without changing any immutable input, model or economic result. Future bundles
use the protocol-specific description.
