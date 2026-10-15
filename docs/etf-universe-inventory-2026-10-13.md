# ETF expansion: candidate inventory and admission plan

P4.16d stage 1, October 13, 2026. **Outcome at delivery: ready for review before ingestion.**
The operator subsequently accepted this wave. See the October 14
[publication and study findings](etf-expansion-findings-2026-10-14.md) for current
status; the inventory and frozen bundle below retain their original as-of scope.
The inventory contains **299 symbol/regime records, representing 298 provisional
fund identities**, with 298 observed current listings and one legacy symbol.
Propose **38 additions alongside the existing 14**, giving a 52-candidate first
wave. These are candidates for qualification, not 52 approved instruments or
positions. No performance experiment, ingestion, strategy membership, allocation
or broker change was made.

The full [gap matrix](../research/etf-universe-inventory-2026-10-13/gap-matrix.md)
and [machine-readable inventory](../research/etf-universe-inventory-2026-10-13/inventory.json)
contain every candidate's venue, identity evidence, inception where known,
proposed peer/overlap bucket, price status and unresolved checks.
The [frozen protocol](../research/etf-universe-inventory-2026-10-13/protocol.json)
specifies the proposed admission, liquidity and duplicate rules.

## Question and failure modes

Can a substantially wider ETF pool add economically distinct opportunities to
the unchanged strategy while remaining auditable and executable? This stage
tests whether there is a credible candidate set and a feasible qualification
path. It does **not** test whether the expanded strategy improves returns.

The main failure modes are counting substitutes as independent opportunities,
backdating today's surviving funds, treating stale or renamed symbols as closed
funds, mixing equity producers with physical commodities, and calling price
publication equivalent to broker or strategy eligibility. The candidate list was
chosen for exposure coverage and available reference evidence, without screening
on issuer-page returns, yields or fund size. It is not an exhaustive census or
an unbiased historical universe: issuer coverage favors iShares, with other
issuers added for existing contracts, alternatives and missing exposures.

## Evidence and current gaps

Reference discovery uses the captured [Nasdaq directory](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt)
and [iShares product directory](https://www.ishares.com/us/products/etf-investments).
The first contains 5,761 non-test ETF listings; the issuer ETF table contains 482
products. Only reference names, product IDs and inception dates are extracted
from the issuer table. The directory's round lot is a quotation reference, not
a broker minimum order quantity. [Directory field definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs).

The app's committed catalog was pinned at batch
`38153d09e24666838a4737dfe32423fe9832b12c49132b0d41418c8e1355378f`,
published October 13 at 12:46:39 UTC, with completed-session cutoff October 12.
Its manifest and catalog hashes were checked; all 52 matching candidate audits
and compressed bar files were verified through the inherited manifest chain.
Only audit metadata, hashes and file density are used here, not returns or
provider price archives. Snapshots and verification receipts are retained under
the [source manifest](../research/etf-universe-inventory-2026-10-13/source-manifest.json).

| Pinned catalog evidence | Records | Interpretation |
| --- | ---: | --- |
| Audited with limitations | 48 | Price evidence exists; identity, vintage and execution requirements still apply. |
| Review | 4 | IVV, XLF, XLRE and legacy HYXU remain unqualified. |
| Absent | 247 | Acquisition, audit and publication required before price research. |
| Prices through October 12 | 16 | Existing 14, BIL and benchmark URTH; included in the totals above. |
| Published but older tail | 36 | Require refreshed audit/publication; no forward fill. |

Among the first 52, 37 have audited-with-limitations histories and 15 are absent.
Of the 38 additions, 23 have existing published histories: BIL is current and the
other 22 end September 25. None of the four `review` series is in this first wave.
Missing history remains missing; a current-looking fund page cannot qualify it.

Identity completeness is deliberately separate. Across all 299 records, 209 have
issuer-backed inception dates, while only five records have a retained ISIN or
CUSIP (HYXU and EUHY share one CUSIP). The rest need external identity resolution.
Only BIL/XLE/XLB have quote currency verified by the retained issuer-recorder
publication; USD is the **intended** first-wave listing currency elsewhere and
must be confirmed. First-wave inception is supported for 32 of 52 records.
Inception does not prove the first tradable session, historical availability or
an unchanged mandate. Unknown closure dates remain null, not “still open forever.”

### Corrected HYXU identity

The backlog's “delisted in 2020” statement was wrong. The issuer announced a
change from HYXU to EUHY, including a new index and USD hedge, in August 2025.
The old mandate covered non-US developed-market high-yield bonds in multiple
currencies; the new mandate selects euro-denominated high-yield debt and hedges
to USD. Issuer domicile is not the selection criterion.
[SEC prospectus supplement](https://www.sec.gov/Archives/edgar/data/930667/000119312525192804/R2.htm).

OCC specifies November 3, 2025 for the name/symbol transition and CUSIP
464286210. [OCC notice 57452](https://infomemo.theocc.com/infomemos?number=57452).
The [current issuer page](https://www.ishares.com/us/products/239550/ishares-euro-high-yield-corporate-bond-usd-hedged-etf)
confirms EUHY's identity and April 3, 2012 inception. The prospectus's approximate
mandate-change date and the exchange-symbol effective date are stored separately.

The stale catalog series ending April 1, 2020 is therefore incomplete evidence,
not proof of liquidation. HYXU and EUHY share a fund reference but retain separate
regime records and remain on hold; no price splice or audit-status promotion was
performed. SEC/OCC documents were read through web retrieval; direct byte capture
returned HTTP 403, recorded in the event evidence. The current issuer page is
archived byte-for-byte. Old immutable catalog/history receipts remain unchanged.

## Taxonomy and comparable groups

| Exposure family | Records | Important distinctions |
| --- | ---: | --- |
| Equity | 211 | Region/country, size/style, broad sector and narrow industry; hedging/benchmark history still requires review. |
| Real-estate equity | 8 | Property REITs, mortgage REITs and non-US property are separate. |
| Sovereign rates | 15 | US duration bands, bills, non-US short/broad sovereign exposure. |
| Inflation-linked | 4 | Short versus broad TIPS; not interchangeable with nominal Treasuries. |
| Aggregate bonds | 8 | Mixed exposures, region and currency hedge; not a pure sovereign class. |
| Credit | 26 | Currency, credit quality, maturity, floating rate and emerging-market sovereign/corporate risk. |
| Securitized | 5 | Agency debt, agency mortgages and commercial mortgages. |
| Hybrid credit | 1 | Preferred securities kept outside ordinary investment-grade debt. |
| Commodities | 21 | Physical precious metals, futures energy/base metals/agriculture and mixed commodity baskets. |

There are **181 proposed peer/overlap buckets, 117 with only one candidate**.
These counts describe the taxonomy; they do not establish independent breadth
or enough observations for within-peer alpha ranking. The first 52 occupy 51
buckets: IGOV/BWX are conservative alternatives in one bucket. Comparable
mandates, hedge policy, duration, quality and holdings must be verified before
the proposed groups become accepted research classifications.

Boundary rules:

- Semiconductors and metal miners are equities. XME, PICK and gold/silver miners
  do not substitute for physical metal or futures funds.
- Silver has one primary precious-metal bucket and an industrial-demand tag;
  it does not get a second selection vote. Agriculture producers remain equities.
- Asia ex-Japan can include China. AAXJ/EEMA/AIA are explicitly labelled that way,
  and EWH retains a Hong Kong exposure rather than inheriting mainland China.
- Fund listing currency, underlying asset currency and CNH accounting are
  separate. A USD-listed foreign bond fund can retain substantial currency risk.
- Broad materials is not pure chemicals exposure. Chemicals/industrial feedstock
  lacks a qualified clean proxy in this inventory and remains an explicit gap.
- Multi-region and global parents overlap with country/sector funds. One primary
  bucket plus look-through exposure controls is required; more labels do not
  create independent capital budgets.

Classifications are observed/proposed **October 13, 2026**. Historical validity
is null unless later supported by dated source evidence. Index, mandate, hedge
or legal-wrapper changes split the applicable regimes and restart qualification;
ordinary name changes require evidence rather than inferred return continuity.
The [taxonomy](../research/etf-universe-inventory-2026-10-13/taxonomy.json)
and permanent local candidate IDs are frozen. These local IDs are not a
substitute for a certified security master.

## Proposed first admission wave

Retain the existing 14 as the baseline. Qualify the following 38 additions by
exposure coverage and evidence readiness, with a report at each publication
stage. No candidate is added to an active config by this document.

| Qualification lane | Candidates | Reason |
| --- | --- | --- |
| Reuse and refresh existing publications: cash/rates | BIL, SHY, TIP, IGOV, BWX, IBND | Cash destination, short duration, inflation and non-US fixed income. |
| Reuse and refresh: equity breadth | MDY, IWM, EWT | US size and Taiwan exposure. |
| Reuse and refresh: broad sectors | XLC, XLI, XLK, XLP, XLU, XLV, XLY | Complete additional broad-sector coverage without releasing XLF/XLRE review holds. |
| Reuse and refresh: commodities | SLV, PPLT, DBB, CPER, DBA, CORN, WEAT | Separate precious metals, industrial metals and agriculture. |
| New acquisition/publication: regions | EFA, EEM, EWA, EWC, EWG, EWU, INDA | Developed/emerging, country and regional comparison coverage. |
| New acquisition/publication: industries | SOXX, IBB, ITA, IAT | Semiconductors, biotech, aerospace/defense and regional banks. |
| New acquisition/publication: bonds | AGG, MBB, EMB, LEMB | Aggregate, agency mortgage, USD and local-currency emerging debt. |

This 52-candidate wave is an engineering/admission slice, not the endpoint of
the expansion. The other 244 reserve records remain visible. XOP retains its
issuer/provider listing-boundary hold; HYXU and EUHY have the identity-transition
hold. Commodity trusts/futures wrappers need their own broker/tax/roll checks;
an ETF directory flag is insufficient. Broader industry alternatives and more
duration/credit/country funds follow after these shared contracts are proven.

## Proposed rules frozen before inspecting outcomes

Admission requires issuer/security-master identity, approved wrapper and venue,
dated mandate, complete published adjusted lookbacks and separately supported
raw activity. Require 252 supported sessions within the relevant regime for
the first comparison. Preserve corporate actions and genuine gaps; never append
index returns before fund inception. Price audits retain their disclosed tape,
publication-vintage and legacy-FX limitations.

Proposed liquidity screen: 63 complete prior sessions, median audited raw dollar
volume at least $5 million and minimum session value at least $0.5 million.
Proposed orders must be no more than 0.5% of that median daily value. Paper
readiness additionally requires at least 20 observed regular-session spread
days with median spread no greater than 20 bp, plus fresh broker checks. These
are proposed operating thresholds, not calibrated profitability findings.
Historical dollar activity is a liquidity proxy, not evidence of historical
spreads. No pass is inferred from today's AUM or one published quote.

Select one representative per conservative overlap bucket using prior-63-session
audited liquidity, then contemporaneously known fee when both are available,
then permanent ID. Never choose the representative by return. Changes occur
only on scheduled rebalances and incur full turnover. Holdings-overlap review
must address country/global and broad-sector/narrow-industry duplication across
buckets; the provisional buckets alone are not a complete exposure risk model.

For a later separate risk-normalized arm, the frozen proposal is the mean of
21/63/126-session log momentum divided by prior-63-session daily log-return
standard deviation times the square root of each horizon. Require complete
causal inputs and positive finite volatility. Each eligible representative gets
one vote, with equal bucket weights within a class. Keep the positive-126-session
gate, monthly schedule, fallback and 45% cap unchanged until a separately
reviewed protocol says otherwise. This normalization has not been calculated.

First compare the unchanged recipe on its original pool and the full newly
admitted pool. Only then isolate the risk-normalization effect; alpha changes
are a separate hypothesis. Apply the existing [P4.15 gate](turnover-gate.md)
before every replay; missing IC/dispersion is insufficient evidence. Freeze the
actual split, group/time holdouts, family tests and costs before that experiment.
The already inspected historical sample is not an untouched holdout. A current
survivor list cannot be backdated; closed funds and historical membership require
separate reconstruction, otherwise use prospectively admitted membership.

## Capacity estimate and refresh plan

Measured file density across 52 verified governed files is a median **79.6
compressed bytes per row**. Five sampled files give **739.6 uncompressed JSON
bytes per row**. The following are planning scenarios at 15 years × 252 sessions,
not actual history coverage or measured worker memory.

| Scope | Daily rows | Compressed files | Uncompressed JSON | Dense 10-field float64 array |
| --- | ---: | ---: | ---: | ---: |
| First 52 | 196,560 | 14.9 MiB | 138.6 MiB | 15.0 MiB |
| Capacity for 299 records | 1,130,220 | 85.8 MiB | 797.2 MiB | 86.2 MiB |

Use a provisional four-times storage allowance for replicas, snapshots and
staging: approximately 60/343 MiB on the compressed-file estimate. This excludes
raw provider evidence, actions, issuer holdings, fundamentals, intraday data,
models and reports; database encoding and immutable snapshot accumulation can
change it materially. The 299-record scenario is a conservative capacity bound
and does not splice or double-ingest the two HYXU/EUHY regime records.

A one-request-per-symbol full refresh implies 52 or 299 requests. At an assumed
2–10 seconds each, serial acquisition alone would take 1.7–8.7 or 10–49.8 minutes,
before retries/audit/publication. This is a sensitivity estimate, not measured
throughput. At most one new daily row per eligible instrument is expected per
session, but dividends/splits can require full adjusted-history verification.
Reusing unchanged inherited artifacts and publishing waves avoids copying the
entire 5,341-series catalog's price history for every candidate.

Do not translate array size into a LEAN worker budget. Python objects, model
copies, frozen bundles, reports, native engine startup and ClickHouse contention
remain unmeasured. [P6.15](calculation-performance.md#p615--worker-deployment-and-resource-budget-review)
is still required before increasing worker concurrency. No resource limit changed.

## Verification and next decision

The offline builder validates snapshot hashes, pinned catalog identity, audit
agreement, unique local identities and issuer-table schema. Tests reject
tampering, unsafe paths and schema drift; verify that issuer performance fields
cannot affect metadata; preserve XOP's hold; and prevent HYXU/EUHY price merging
or inferred fund closure. It grants no strategy or execution authority.

Reproduce without network, databases or broker access:

```powershell
.venv/Scripts/python.exe scripts/build_etf_inventory.py --check
.venv/Scripts/python.exe -m pytest tests/test_etf_inventory.py
```

**Next review:** accept or revise the 38-addition wave and screening rules, then
complete its reference identities and admit it through the app-owned recorder,
audit and publication workflow. Keep research-ready and paper-ready statuses
separate. P8's existing minimum 14-ETF execution work remains a parallel backlog
dependency; the conditional FR25 pilot is not enabled by this inventory.

This closes the first reviewable P4.16d deliverable, not the entire expansion.
