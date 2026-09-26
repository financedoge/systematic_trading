# Governed underlying price histories — 2026-09-26

This work pauses signal development to establish explicit price conventions,
source comparisons and reproducible per-symbol histories. It adds a research
data layer and a Governed Histories tab to Market Data. It does not replace the
production daily-bar reader or change a strategy, portfolio, approval policy or
broker setting.

## Frozen batch results

Batch `69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3`
inventories **5,340 symbols**. **4,537** have governed histories containing
**23,295,861 daily observations**; **803** remain unavailable or identity-blocked.
The observed range is January 2, 1962 through September 25, 2026.

| Coverage measure | Result |
| --- | ---: |
| Original source observations retained for comparison | 55,169,737 |
| Raw-price reconstructions supported | 17,825,179 |
| Raw-volume reconstructions supported | 14,828,552 |
| Histories without internal session gaps | 4,268 |
| Histories with raw prices throughout their observed span | 3,123 |
| Symbols using supplemental source observations | 4 |
| Selected supplemental source rows | 7 |
| Histories ending before the cutoff | 1,311 |
| Available symbols with historical issuer-name review | 153 |
| Available symbols with archived price disagreements | 2,411 |
| Original source observations quarantined before identity/start boundary | 772,141 |
| Symbols with such quarantined observations | 686 |

Fresh full-range downloads supply almost all selected history. Only seven
observations require supplemental sources after the stricter identity checks.
Compared with the rejected first build, 120,657 selected observations were
removed rather than assigned to an unverified earlier issuer era. The larger
772,141 quarantine count covers original observations across multiple sources,
including sources already excluded from joining.

All 12 current strategy ETFs (SPY, DBC, EWH, EWJ, EWY, GLD, HYG, IEF,
LQD, MCHI, TLT and VGK) have zero internal gaps, supported reconstructed raw
prices and volumes for every observed session, and an endpoint at the cutoff.
Their first observations range from SPY in January 1993 to MCHI in March 2011.
Ten retain review status because of disagreements with older inputs. This is
not a claim that every historical identity or listing episode is certified.

The source inventory contains 14,704 histories and 228,262 corporate-action
records. Action records preserve separate source vintages, so this is not a
count of unique economic events. Of 17,691 overlap-pair audits, 11,038 pass
joining thresholds and 6,653 fail. There are 51 distribution/split check
failures across source vintages, 74 unexplained raw-price-basis comparisons and
449 unexplained raw-volume-basis comparisons. The output retains these
restrictions instead of silently assuming compatible units.

Frozen outputs: `D:/systematic_trading_data/research/governed-prices-20260926-v2/`.
The complete inventory and work queue are `coverage.csv`, `unresolved.csv`
and `audits/{symbol}.json`. The separately frozen review report and examples
are in `D:/systematic_trading_data/research/governed-prices-audit-20260926-v2/`.

## Prior ETF inputs require a backtest rerun

The saved ETF snapshot used by the earlier flow and constituent studies mixes
source/adjustment vintages. Measured daily-return differences against the new
consistent vendor vintage are material:

| ETF / date | Old snapshot | Governed vintage | Difference |
| --- | ---: | ---: | ---: |
| HYG / 2026-05-26 | -1.6528% | +0.3379% | -1.9907 percentage points |
| LQD / 2026-05-26 | -1.1953% | +0.3783% | -1.5736 percentage points |
| SPY / 2026-05-26 | +0.1484% | +0.6639% | -0.5154 percentage points |
| EWH / 2026-04-30 | +0.0542% | +1.6717% | -1.6175 percentage points |

For HYG, LQD and SPY, the May 22/26 boundary coincides with saved provenance
changing from `sqlite_price_bars` to `platform_market_data_store`, while both
carry the ambiguous `provider_default` adjustment label. EWH's source labels
do not identify the same boundary, so its cause remains less certain. These
comparisons are evidence of inconsistent historical inputs, not independent
certification that the new provider is correct in every case.

Earlier research artifacts remain intact, but their absolute returns, Sharpe
ratios and incremental IRs are provisional. Rerun the baseline and candidates
on the same pinned governed inputs, with explicit corporate-action and
point-in-time handling, before discussing SOTA promotion. The production
strategy and its data reader have not been switched by this governance work.

## What the versions mean

| Version | Meaning | Limitations |
| --- | --- | --- |
| Original source | Immutable provider JSON/CSV and values as published | A column called Close does not mean unadjusted tape. |
| Dividend + split adjusted | Provider adjusted close, with the same daily factor applied to OHLC; accepted earlier segments rebased onto the selected source’s scale | This is a back-adjusted price series, not a separately constructed dividend-reinvestment total-return index. |
| Raw, reconstructed | Split-adjusted Yahoo OHLC multiplied by all strictly subsequent split ratios through that source vintage | Conditional on the supplied action ledger and provider convention; not exchange-certified tape. Unsupported values stay null. |
| Source volume | The source’s original volume units | Different vintages may have different split bases. Do not join this column as if all units were identical. |
| Raw volume, reconstructed | Source Yahoo share volume divided by the same subsequent-split product | For turnover comparisons, pair it with reconstructed raw prices. Stooq raw volume is not inferred. |

Yahoo’s [adjusted-close documentation](https://ca.help.yahoo.com/kb/SLN28256.html)
describes split and distribution adjustments. Its Close field is already split
adjusted. The [2017 Stooq archive](https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs/versions/3)
describes adjusted prices but supplies no separate raw series or action ledger.
The [2020 Yahoo archive](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset)
supplies both Close and Adj Close. Different adjustment vintages can therefore
have different levels while agreeing on returns. Raw prices cannot be obtained
by merely renaming one of these columns.

The reconstruction is `raw OHLC(t) = source OHLC(t) × product(split ratios with
t < ex-date ≤ source vintage)`. The split date itself is excluded. The dividend
factor is `source Adj Close / source Close`, multiplied by a documented scale
when an earlier source is accepted. Reported dividend and capital-gain events
are checked against changes in this factor. Unexplained changes and suspect
split-day discontinuities withhold raw reconstruction before the problematic
event. Known complex identities also withhold it pending review. These checks
do not prove the absence of an unreported merger, spinoff or corporate action.
Cross-vintage Yahoo Close scales are also checked against the intervening split
product. A 99th percentile unexplained error above 0.5% withholds raw prices for
the affected source; share-volume error above 5% withholds reconstructed raw
volume. Constant adjusted-price alignment alone is insufficient evidence for
raw reconstruction.

## Scope and identity

The inventory covers the dated ITOT/IVV stock constituents, existing archive
symbols, sector ETFs, the strategy ETFs and all 39 ETFs already in Market Bars.
The governed price cutoff is September 25, 2026, the last completed US session
before this collection. Earlier research snapshots retain their original dates.
Source-specific failures and rejected identities remain visible. Dated issuer
names retain their first/last observed holdings dates, rather than becoming an
undated ticker alias list. The provisional identity key is not a permanent
security-master identifier.

ACT includes historical Actavis and current Enact references; GE has corporate
reorganizations. Matching a ticker alone never authorizes stitching these
economic histories. Historical holdings cannot automatically consume a current
provider’s series merely because the symbol matches. Mergers, share classes,
spinoffs, ticker reuse and delistings remain explicit identity work items.

Policy v2 adds a listing-era boundary. A historical CSV can contain an old
issuer followed by a new company using the same ticker, yet match the new
company perfectly during their recent overlap. This occurred for NET, TXG,
WMS, DAL and others in the first build. The preferred provider's
`firstTradeDate` is now a conservative lower bound for **every** joined source,
including the preferred source itself. Earlier observations retain their
original values for inspection, with an explicit exclusion reason and no
aligned-price value. A provider start date is not independently certified IPO
or listing history; earlier continuity requires dated security evidence. If
all prices precede that boundary, the current identity has no governed history.
When listing metadata is absent, the first valid observation of the preferred
source becomes a conservative identity floor: another archive cannot extend
it into an unverified earlier issuer era. This floor is not asserted to be an
IPO date. Such archival series remain under identity review. For example,
Janus Henderson's 2017 archive cannot be extended back to 2000 solely because
an older ticker series agrees with it after 2017.

An older Yahoo CSV may borrow a matching source's split ledger only within
that source's observed price coverage and requested action window. Requesting
events from 1950 does not establish that a provider returned every event before
its own price history begins. Earlier raw values remain unresolved.

Corporate-action records retain original provider units and source vintages.
Reported dividend amounts may themselves be split-adjusted. They must not be
passed directly into a raw-price cash-dividend simulator without converting
their units and verifying the security episode. The provider-adjusted price
series is distinct from such a reconstructed cash-reinvestment simulation.

NET's corrected start is September 13, 2019, agreeing with
[Cloudflare's announcement](https://blog.cloudflare.com/how-cloudflare-and-wall-street-are-helping-encrypt-the-internet-today/).
WMS starts July 25, 2014, agreeing with
[Advanced Drainage Systems' SEC filing](https://www.sec.gov/Archives/edgar/data/1604028/000156459017011836/wms-10k_20170331.htm).
The earlier 1996/1981 observations are not assigned to those current issuers.
V1's partial database writes remain quarantined by the absence of its catalog
commit. A hash-verified incident record is retained in
`governance/quarantine/00eed508ed7a2a570bc3ba917f86ea09dac674306911e657c03e20bf6b12d07c`.
The publisher refuses policy v1 even if an old command is accidentally retried.
V2 reuses only the frozen source inventory, original source files and dated
name evidence, never v1's joined rows. Source IDs keep their original collection
names for lineage; the governed batch hash identifies the rebuilt output.

## Audit and joining rules

1. Preserve and hash source files; use exchange-local session dates.
2. Reject duplicate sessions, missing/nonpositive prices, invalid OHLC bounds
   and missing/negative volume. Zero volume is retained with a flag.
3. Audit sessions using the frozen XNYS calendar from
   [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars), pinned
   at 4.13.2. Keep the exact calendar snapshot with the batch.
   Explicitly evaluate regular holidays over the requested range: the pandas
   default begins in 1970 and otherwise creates false early-history gaps. The
   removed calendar artifacts are retained in the snapshot. Regression checks
   cover pre-1970 holidays, the 1968 paperwork closures and later emergency
   closures. Negative Unix dates use epoch arithmetic for Windows portability.
4. Prefer the new full-range Yahoo vintage, then prior Yahoo downloads, the
   2020 Yahoo archive and finally eligible 2017 Stooq histories. Unknown legacy
   `provider_default` bars remain comparison evidence and cannot fill governed
   gaps.
5. An older source must have compatible issuer identity, at least 60 common
   valid observations and 20 informative returns. Estimate the adjustment-scale
   ratio from overlap medians. Require median relative error ≤0.1%, 99th
   percentile relative error ≤0.5%, and 99th percentile log-return disagreement
   ≤1%. Record all pairwise audits among eligible sources, including rejected
   pairs. Volume disagreements are audited separately.
6. The preferred source wins overlaps. Only accepted sources may fill holes or
   extend history. Record every source transition and its return. Never average
   conflicting prices, infer dividends from scale alone, forward-fill missing
   sessions, or append an acquirer’s prices as a delisted target’s continuation.
7. Each output row retains its source ID, source-file hash, original record key,
   source vintage, factors, adjustment status and quality flags. Gaps and
   unresolved raw values remain explicit.

“No internal gaps” means the selected history contains the expected sessions
between its first and last observations. It does **not** certify complete
listing-to-delisting coverage, or coverage through the requested cutoff.
Endpoints short of the cutoff are labelled stale/delisted-unverified. No
delisting proceeds or missing terminal returns are fabricated.

The current dataset is a retrospective vendor vintage. Historical publication
and revision availability remain null. Retrieval time is not substituted for
historical availability. Price adjustments may reflect actions learned after a
past decision date. Subsequent LEAN exports must pin a batch and use explicit
bases, identity mappings and point-in-time corporate-action handling.

## Storage and workstation

`market_data.governed_daily` stores one versioned row per symbol/session.
`market_data.governance_comparisons` stores each original source series and its
accepted rebased comparison, if available. Both are scoped by workspace and
immutable batch. Corporate actions, complete audits, source documents,
calendars, code and manifests are retained in ClickHouse analytics tables.

A batch is visible only after exact row/document SHA256 readback and aggregate
count checks. The final `governance/catalog` publication commits the batch;
interrupted imports cannot expose a partly populated version. Retries use
stable keys and `FINAL` semantics. Original research publications remain intact.

The Market Data page has three views: Market Bars, Research Data and Governed
Histories. The governed view offers symbol/date/basis selection, complete-series
JSON export, source-scale and aligned comparisons, gap/identity audits,
corporate-action evidence and daily lineage. Null raw values remain gaps on the
chart. Original files are accessible from source inspection, with older
publications linked to the existing research browser.

Read-only APIs under `/api/v1/market-data/governed` expose `/catalog`, `/audit`,
`/series`, `/actions` and `/source`. Supply the returned batch for reproducible
reads. Catalog versions must already be committed. The maximum series response
is 25,000 sessions, with explicit pagination/truncation metadata.

## Interactive chart navigation

Governed Histories opens each underlying at the full available date range.
Drag horizontally in either chart to zoom into a period; reverse drags work
too. Choose **Pan**, or hold Shift while dragging, to move the selected window.
Both charts share the same dates, with price axes rescaled to visible values.
**Full history** restores the complete range. Changing an underlying resets
the range; changing a price basis or comparison source preserves it where the
new history supports it. Original source dates can extend the shared range.

From/Through also selects an exact date window. Navigation uses the loaded
history without fetching another page; displayed daily rows and the series
JSON export follow the selected range. Null prices and audited gaps remain
visible as missing observations. Focus either chart and use the arrow keys to
pan, Home to reset, or Esc to cancel an active drag.

Validation: 25 focused tests passed, including execution of the shipped
JavaScript pointer/keyboard handlers, window bounds, source synchronization,
null/gap rendering, date controls and stale-load protection. Receipt:
`var/research/governed-chart-tests.xml`. Browser verification:
`var/research/governed-chart-ui-verification.json`.

## Replay

```powershell
.\.venv\Scripts\python.exe scripts/fetch_governance_history.py --root D:/systematic_trading_data/research/governance-yahoo-20260926-v1
.\.venv\Scripts\python.exe scripts/fetch_governance_etfs.py
.\.venv\Scripts\python.exe scripts/build_governed_prices.py --fresh D:/systematic_trading_data/research/governance-yahoo-20260926-v1 --output D:/systematic_trading_data/research/governed-prices-20260926-v2 --workers 8
.\.venv\Scripts\python.exe scripts/publish_governed_prices.py --fresh D:/systematic_trading_data/research/governance-yahoo-20260926-v1 --root D:/systematic_trading_data/research/governed-prices-20260926-v2 --workers 8
.\.venv\Scripts\python.exe scripts/verify_governed_publication.py --root D:/systematic_trading_data/research/governed-prices-20260926-v2 --output var/research/governance-publication-verification.json
```

Frozen outputs reject overwriting. Use a new build root for a changed policy or
extractor. Imports of the same immutable batch resume safely. The policy and
code copied into the batch are the authoritative recipe.
The importer uses separate connections for disjoint symbol workers. Only the
parent publishes the global catalog, after all worker results and whole-batch
counts agree. An interrupted symbol can be replayed without exposing a partial
catalog or changing the immutable input batch.

## Spot checks and remaining work

Apple’s reconstruction gives approximately $645.57 on June 6, 2014 versus $93.70
on June 9, and $499.23 on August 28, 2020 versus $129.04 on August 31. These are
computed source values, not independently certified tape observations. The
effective split dates and ratios agree with the issuer’s
[dividend/split history](https://investor.apple.com/dividend-history/) and
[2020 announcement](https://www.apple.com/newsroom/2020/07/apple-reports-third-quarter-results/).
NVIDIA’s June 10, 2024 ex-date is documented in its
[SEC filing](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000144/nvda-20240607.htm).

The Apple pilot found close agreement between Yahoo vintages after scale
alignment, while the Stooq comparison retained approximately 9.38% price error
at the 99th percentile and substantial volume disagreement. This demonstrates
why raw archives must not be spliced by ticker/date alone.

The unresolved-data queue is part of the deliverable: unavailable/delisted
symbols, identity episodes, incompatible source histories, unsupported raw
periods, suspected action errors and internal gaps. Public sources do not
support a blanket claim that every underlying now has complete certified raw
and adjusted history. No strategy promotion should rely on that claim.


## Validation

The final policy-v2 full test run passed **643 tests**, with **51 optional
integration skips** and no failures. Nine final API checks also passed after
adding the corporate-action unit disclosure. The full-run receipt is
`var/research/governance-v2-full-tests.xml`; final API receipt:
`var/research/governance-v2-api-final-tests.xml`. Ruff passed on the governance
engine, storage/API/UI modules, acquisition/build/publication/review scripts
and focused tests. Runtime/dependency versions are frozen with the batch.

The initial real ClickHouse smoke test covered pre-1970 Date32 values, exact
payload hashes, null raw prices, committed-batch filtering and workspace
isolation. The final acceptance script independently checks whole-table and
evidence counts, API pagination, split reconstruction, historical-calendar
exclusions, source-document hashes and the reused-ticker exclusions. Its
receipt is written only after the committed batch passes every assertion.

The final batch committed successfully to ClickHouse. Independent readback
confirmed 23,295,861 daily rows across 4,537 symbols, 55,169,737 comparison rows
across 4,936 symbols, 228,262 action records, 20,310 per-symbol documents and
5,340 per-symbol publications. Full catalog: 5,340 symbols. Batch receipt:
`D:/systematic_trading_data/research/governed-prices-20260926-v2/clickhouse_receipt.json`.
Acceptance receipt: `var/research/governance-publication-verification.json`.

Browser verification checked Apple's 2020 raw split discontinuity against the
original split-adjusted Close, NET's 2019 start and 5,345 excluded earlier
observations, the 686/803 quarantine/unavailable filters, ASRT's empty history,
GE's intentionally empty raw chart, HYG's rejected legacy source, event-unit
disclosure and both existing Market Data views. No browser console errors.
Receipt: `var/research/governance-ui-verification.json`. The existing paper
approval file remains byte-identical. Open the
[Governed Histories view](http://127.0.0.1:8000/platform/market-data-audit?view=governed)
to inspect prices, source disagreements, lineage and the unresolved catalog.
