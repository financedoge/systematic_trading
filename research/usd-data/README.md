# Broad US dollar index data

Collected on 2026-10-01 following the user's request. The selected series is the
Federal Reserve **Nominal Broad US Dollar Index, DTWEXBGS**. Higher levels mean
dollar appreciation. It measures a broad trading-partner basket; it is distinct
from USD/CNH and the narrower ICE DXY basket.

## Downloads

- [Revised daily history](broad-dollar-latest-history.csv), also in
  [JSON](broad-dollar-latest-history.json): 5,410 dated rows from 2006-01-02
  through 2026-09-25. Missing source values remain blank/null. This is the
  current revised snapshot, retained for source inspection; it was not used as
  historical point-in-time input.
- [Download manifest](download-manifest.json): 92 monthly ALFRED vintage files
  under `archives/`, with URLs, retrieval times, requested vintage, decision
  cutoff and SHA-256 hashes. They cover the monthly decisions March 2019 through
  October 2026. The October snapshot is collected but outside the September-end
  backtest.
- [Published batch receipt](published-batch.json): 92 accepted snapshots,
  verified in the application's analytics store after audit. Immutable batch
  `ddb5624ba023c71b9ca41ff0571318eb48f390ad4131ab20858d7eaafdae006b` is stored at
  `D:/projects/systematic_trading/var/governance/usd-broad-20261001-v1`.

## Availability and basis

The goods-and-services index was introduced in February 2019; earlier
goods-only history is not silently joined to it. The June 2019 re-indexing
and later weight revisions can change historical levels. Each 21/63-observation
change therefore uses values entirely within **one ALFRED vintage**.

For a month-end signal, the requested vintage is the preceding calendar day.
Availability is conservatively placed at the end of that vintage day, before
the signal close. This uses ALFRED's daily archival evidence; independently
certified intraday publication timestamps are unavailable. Auditing does not
remove the separate vintage limitations in ETF prices.

Audit checks cover series/vintage identity, ordered unique dates, no future
observations, finite positive levels, at least 64 valid observations, no more
than 14 days of release staleness, at most 105 days across a 63-observation
window, and no unexplained adjacent change above 5%. Source missing values
are retained. Horizons count valid published observations and do not imply
21/63 exchange sessions. These limits were checked before USD performance.

Research reads the published, hash-verified snapshots, not the downloaded
archives. Details and the predictive ablation are in the
[research results](../momentum-results-2026-10-01.md).

## Primary sources

- [Fed broad-dollar history](https://www.federalreserve.gov/releases/h10/summary/jrxwtfb_nb.htm)
- [Fed release timing and unrevised weekly archives](https://www.federalreserve.gov/releases/h10/about.htm)
- [2019 methodology and index-base changes](https://www.federalreserve.gov/releases/h10/h10_technical_qa.htm)
- [ALFRED series](https://alfred.stlouisfed.org/series?seid=DTWEXBGS)
- [ALFRED vintage-date definition](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html)
