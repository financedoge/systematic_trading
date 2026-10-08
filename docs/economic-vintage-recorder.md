# Economic vintage recorder

The expanded panel contains sixteen US series: seven leading candidates, four
separately labelled context series, and five financial-condition series. GDP is excluded. It is available under
**Market Data → Economic Data**. Each observation belongs to an explicitly dated
ALFRED snapshot; the app never replaces an earlier snapshot with today's revised
history. This is a data foundation, not evidence of a profitable economic signal.

| Indicator | Role | Source and measurement |
| --- | --- | --- |
| ICSA | Leading labor deterioration | [FRED / US Employment and Training Administration](https://fred.stlouisfed.org/series/ICSA); weekly claims ending Saturday, seasonally adjusted number. |
| PERMIT | Leading housing activity | [FRED / Census and HUD](https://fred.stlouisfed.org/series/PERMIT); monthly housing permits, thousands of units at a seasonally adjusted annual rate. |
| IPMAN | Coincident business activity confirmation | [FRED / Federal Reserve](https://fred.stlouisfed.org/series/IPMAN); monthly seasonally adjusted manufacturing production index. Index bases change across vintages; compare growth within each vintage. |
| AWHMAN | Leading labor adjustment candidate | [BLS via FRED](https://fred.stlouisfed.org/series/AWHMAN); hours of manufacturing production/nonsupervisory employees, reported monthly. |
| TEMPHELPS | Leading hiring candidate | [BLS via FRED](https://fred.stlouisfed.org/series/TEMPHELPS); temporary employment; structural changes can weaken the relationship. |
| NEWORDER | Leading investment demand | [Census via FRED](https://fred.stlouisfed.org/series/NEWORDER); nondefense capital orders excluding aircraft; nominal dollars. |
| NOFDFSA066MSFRBPHI | Forward demand expectations | [Philadelphia Fed via FRED](https://fred.stlouisfed.org/series/NOFDFSA066MSFRBPHI); six-month future orders diffusion index; regional manufacturing, not national PMI. |
| NEFDFSA066MSFRBPHI | Forward hiring intentions | [Philadelphia Fed via FRED](https://fred.stlouisfed.org/series/NEFDFSA066MSFRBPHI); six-month future employment diffusion index; regional manufacturing, not national PMI. |
| PAYEMS | Coincident employment confirmation | [BLS via FRED](https://fred.stlouisfed.org/series/PAYEMS); total nonfarm payroll level and original-vintage changes. |
| CPIAUCSL | Lagging inflation / policy context | [BLS via FRED](https://fred.stlouisfed.org/series/CPIAUCSL); seasonally adjusted headline consumer prices. |
| CPILFESL | Lagging inflation / policy context | [BLS via FRED](https://fred.stlouisfed.org/series/CPILFESL); consumer prices excluding food and energy. |
| T10Y3M | Treasury curve slope | [FRED](https://fred.stlouisfed.org/series/T10Y3M); daily 10-year minus 3-month yield, percentage points. |
| T10Y2Y | Treasury curve slope | [FRED](https://fred.stlouisfed.org/series/T10Y2Y); daily 10-year minus 2-year yield, percentage points. |
| NFCICREDIT | Credit conditions | [Chicago Fed via FRED](https://fred.stlouisfed.org/series/NFCICREDIT); Friday weekly standardized composite, positive means tighter than average; not a corporate spread. |
| DRTSCILM | Bank credit supply | [Federal Reserve via FRED](https://fred.stlouisfed.org/series/DRTSCILM); quarterly net percentage tightening C&I lending standards to large/medium firms. |
| DRTSCIS | Bank credit supply | [Federal Reserve via FRED](https://fred.stlouisfed.org/series/DRTSCIS); quarterly net percentage tightening C&I lending standards to small firms. |

Leading describes a business-cycle hypothesis, not proven ability to forecast
asset returns. Payrolls, CPI and IPMAN are not labelled leading. The Philadelphia
surveys measure expectations six months ahead; zero and negative values are valid.

The registry is `config/economic-recorders.json`. These sources do not require a
new credential for the bounded public CSV acquisition used here. Source citations
remain attached; no paid-data entitlement or redistribution license is inferred.
The current definitions were checked against the publishers on October 7, 2026.
Historical methodology and source metadata are not independently reconstructed.

## What is recorded

The initial plan covers the 130 first-session monthly decisions from January 2016
through October 2026, plus the latest completed New York calendar day. There are
393 combinations at the original launch and 1,441 in the first expansion (131 per
series). The financial-condition extension additionally captures the vintage for
the latest indicative signal, producing 2,112 combinations (132 per series) on
October 7, 2026. All were published and hash-verified; the original 1,441 entries
remain byte-for-byte identical. Each snapshot requests observations
from January 2006, preserving the original frequency and missing values. This is
not 2,112 independent economic events or a complete release calendar.

For each monthly decision, the archive cutoff is the calendar day before the
prior US trading close's date. That conservative rule matches the existing USD
research convention. Daily snapshots from October 6, 2026 onward accrue in the
app, including catch-up after downtime. The latest day is prioritized over the
oldest unfinished historical work. Future studies must verify their exact decision
schedule against the pinned catalog; there is no nearest-vintage substitution.

`recorders/economics.py` is called by the app analytics research lane after
strategy publication, independent of execution and approvals. Each pass allows
six captures, with at most three simultaneous external requests and a 25-second
request timeout. Failed identities retry after five minutes; successful source
commits recover after interruption even if their catalog update did not finish.
The one-shot `scripts/run_economic_recorder.py --cycles N` drains a finite number
of the same app-owned passes. It is not a separate strategy worker.

Original CSV, request/retrieval receipt, registry copy and normalized snapshot are
retained under `var/governance/economic-captures/`. Failed audits retain their
evidence. Audits check the exact series/vintage header, dates and frequency,
chronological uniqueness, complete internal calendar, initial history coverage,
finite domain values and endpoint age. Missing observations remain null. Stale or
missing endpoints can be published for inspection but fail the decision reader.
Weekday daily, Friday weekly and quarterly calendars are validated separately.
The Treasury histories begin January 3, 2006; the source omits the initial closed
January 2 holiday. That date is recorded as an unsupported prefix, never inserted
or assigned a value. Missing initial open days and internal calendar gaps still
fail audit. The initial rejected captures remain retained; normal retries passed
after this explicit boundary repair.
The broad value bounds accommodate pandemic observations; they are schema checks,
not a filter against unusual economics.

The existing AnalyticsStore verifies exact ClickHouse payload hashes before
committing each snapshot publication. Only committed snapshots enter the catalog;
the catalog reports incomplete capture coverage explicitly. Catalog and snapshot
manifests bind original bytes, normalized values and receipts. A changed registry
requires an explicit versioned migration; it cannot silently reinterpret past
data. No active ETF price catalog, strategy recipe or capital control is altered.

Version `us-leading-context-v2` explicitly admits the original registry hash
`5226e9a5057982aba788f6df35f9969a73682c04683615db93ef197050676f83`.
The additive migration verifies the old manifest-bound registry and receipt,
requires a larger series set and a different version, and rejects changed
existing definitions, history start or decision/prospective schedules. Capture
roots, hashes and first-seen times remain identical. Removing or redefining an
existing series still needs a separate migration contract.

Version `us-financial-conditions-v3` also admits v2 registry hash
`bed4b2774e170aa71b0faaf3ec69043a16d4fc689b70521610bb36bf89d90e92`.
The original eleven definitions are unchanged. Economic batch
`9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4`
pins the completed financial extension. Market Data includes source attribution
links and all sixteen selectors. Corporate-spread access remains a separate gap
because the reviewed BAA10Y source notes restrict storage and reproduction;
NFCICREDIT is not relabelled as a bond spread.

The monitored context ridge uses only its frozen original eleven-series recipe.
The separate financial challenger contract uses Treasury endpoint levels,
NFCICREDIT level/four-week difference and SLOOS levels/one-quarter differences.
Its all-five-series group has eight features; adding the original thirteen gives
21. Null endpoints or incomplete required windows abstain, without imputation.
Both feature combinations have paired fixed-capacity ridge/tree fits; a matched
original-context control isolates availability effects. See the completed study
in `research/economic-financial-2026-10-07/` and its frozen v1 artifacts.

## Availability contract

ALFRED's [vintage documentation](https://alfred.stlouisfed.org/help) distinguishes
historical versions but can assign source, provider or first-FRED dates. It is not
a certified intraday dissemination feed. The recorder retains:

- `vintage`: the requested daily archive date.
- `archive_available_at`: end of that date in America/New_York, converted to UTC.
- `first_seen_at`: after the app received the actual response.
- Original observation period, acquisition URL, hashes and capture/audit code version.

`EconomicInputs(root, batch)` reads only a pinned, verified published catalog and
checks every requested snapshot's complete manifest. Decision reads default to
actual first-seen availability. A retrospective study must explicitly select
`availability="archive_daily"` and report that limitation. The decision timestamp
must be later than the chosen boundary, the endpoint must be fresh, and the exact
requested vintage must exist. Historical acquisition today never becomes an
actual historical app observation. AnalyticsStore's generic availability field
uses actual first-seen time, preventing accidental historical use by generic
as-of consumers.

The display can inspect any published vintage without implying a trading decision.
Changing the selector changes the entire same-vintage history; chart lines break
at missing values. Exports contain publication identity and provenance.

## Expanded feature and research contract

The user broadened the scope before the three-series experiment was frozen or run.
`economic_leading_features.py` defines leading-only and separate context groups,
with thirteen numeric features from eleven series. The audit in
`scripts/audit_leading_economic_panel.py` pins published inputs, verifies every
snapshot and the unchanged original 393 captures, and computes readiness on the
130 frozen monthly decisions. It does not read returns or select a model.

- Claims: four-week mean / thirteen-week mean minus one.
- Permits, temporary employment, core capital orders and manufacturing output:
  latest three-month sum / preceding three-month sum minus one.
- Manufacturing hours: change between latest and preceding three-month means,
  in hours. Payrolls: average monthly change over three months, in thousands.
- Regional forward surveys: three-month mean / 100; never percentage growth
  across zero or an invented national PMI.
- Headline/core CPI: three-month annualized and twelve-month changes, each from
  the same archived vintage. No later seasonal revisions enter earlier forecasts.

The groups have independent readiness. Every observation in a feature window is
required; stale/missing observations are absent, not zero-filled. Corruption,
unpublished snapshots, identity errors and future archives abort. Before outcome
inspection, specify neutral parent behavior for optional unavailable groups.
Do not relax freshness limits to improve a backtest.

Compare small, separate decision trees for each ETF with regularized linear
models using the same inputs and completed labels. First compare leading-only
models with SOTA/F3 parents, then add context as a separately counted ablation.
Models can increase predicted beneficiaries and cut weaker assets, preserving
parent eligibility and invested budget. Do not hard-code the same economic sign
for every asset. US indicators are global-factor candidates, not complete
country-specific coverage. Train chronologically with original vintage features,
training-only preprocessing, and returns whose entire holding period finishes
before the prediction cutoff. Freeze costs, delays, model capacity, allocation,
benchmarks and multiplicity controls before running on all available cores.
Previously inspected history is retrospective, not untouched out-of-sample data.

The unfinished `economic_overlay.py`, `economic_models.py` and `economic_study.py`
are the earlier three-series draft. They have no runner, registered strategy,
completed experiment or performance result. They are not the expanded experiment;
wire the new groups and complete shared reports before evaluating a candidate.

## Remaining sources

National manufacturing and services PMI remains a priority, including new orders,
orders/inventories, prices paid and employment. FRED
[removed all ISM series in June 2016](https://news.research.stlouisfed.org/2016/06/institute-for-supply-management-data-to-be-removed-from-fred/).
Current [ISM publication terms](https://www.ismworld.org/globalassets/pub/research-and-surveys/rob/pmi/f3dz202604pmi.pdf)
restrict copying/archiving beyond permitted use. S&P Global describes
[PMI history as a subscription dataset](https://pages.marketintelligence.spglobal.com/Release-Memos-Investment-Management.html).
Obtain a permitted feed/export with dated original releases and flash/final
identities before its recorder. No subscription was purchased, permission
inferred, or unofficial history spliced into the public panel. This gap is visible
in Economic Data; the regional Fed surveys are separate inputs.

The user confirmed no existing data subscription on October 7. Continue the
current recorder work with public sources. A paid PMI/consensus acquisition needs
a concrete permitted source and separately agreed spending; it is not assumed.

Next public-source tranche: yield-curve slope, credit spreads and bank lending
standards, with their own daily/quarterly calendars and publication lags. Forward
inflation expectations and survey prices paid are candidates; CPI is historical
inflation context. Country PMI/orders and sector data need separate admission.

A release-event study requires a timestamped release calendar, pre-release
consensus distribution, original first print, later revisions and actual first
capture. A monthly change is not a consensus surprise. Record these before using
a surprise model. ALFRED daily snapshots support the conservative monthly clock,
not certified intraday announcement reactions.

Prospective issuer holdings/shares/NAV, country vintages, EIA energy fundamentals,
CFTC positions and constituent financial normalization remain separate workstreams.
This recorder does not supply ETF flows, valuation or company financial statements.
