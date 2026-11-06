# P4.21 look-through constituent coverage — November 4, 2026

**Coverage assessment complete. Historical alpha replay remains blocked.** Among the 52 ETF candidates from the last full-pool study, 29 are equity funds. The application's direct issuer-holdings catalogs supplied **0 of 2,030 equity fund-months** at the prior market close for the 70 monthly decisions from January 2021 through October 2026. The other 23 funds are bills, bond or commodity exposures. An equity-constituent model needs a separately declared treatment of those sleeves.

## What is actually available

| Source | Dated holdings snapshots | Published holding rows | Rows with historical availability timestamp | Highest share of equity holding value matched to price status | Highest share of lines matched |
| --- | ---: | ---: | ---: | ---: | ---: |
| IVV, Jan 2012–Aug 2026 | 170 | 85,050 | 0 | 6.36% | 11.11% |
| ITOT, Oct 2018–Aug 2026 | 95 | 299,575 | 0 | 9.54% | 32.02% |

These are native PostgreSQL/Parquet publications. Every published holding row was checked against the source snapshot's date and raw-source hash. Both the stored availability field and the historical-availability payload field are null for all 384,625 rows. The September 2026 retrieval dates are real. The 45- and 60-day lags used in past sensitivity studies are assumptions. The retrieval timestamp provides documented evidence of local possession on that date. Earlier availability would require separate evidence.

IVV and ITOT are outside the frozen 52-fund pool. The earlier research treated IVV as a same-index proxy for SPY. A proxy leaves the actual fund's holdings, weights, revisions and security identity unresolved.

The percentage columns are optimistic status screens under the existing ticker mappings. Numerators require the pinned price catalog's `audited_with_limitations` status. Denominators retain published equity lines and the value of 534 excluded IVV lines and 288 excluded ITOT lines across snapshots. Source archive inspection was limited to verifying the historical exclusions and provenance. No provider prices entered this assessment. Name and value maxima are calculated separately. No snapshot reached the earlier diagnostic reference of 95% value and 70% names, even before enforcing security identity, window continuity, raw volume and formula-specific lookbacks. The earlier study's coverage under relaxed data and modeled availability is a different measure.

| Overlapping native catalog roles | Total symbols | Audited with limitations | Review | Unavailable |
| --- | ---: | ---: | ---: | ---: |
| IVV constituent history | 884 | 70 | 680 | 134 |
| Underlying-sector / ITOT history | 5,157 | 1,006 | 3,460 | 691 |

The frequently cited **680** is the count in review within the IVV role. Combining roles would double-count names. All 884 IVV-tagged catalog records lack a certified historical availability date and certified full listing history. A nonmissing adjusted close alone cannot resolve company changes, ticker reuse, mergers or delisted members.

## Direct issuer captures

| Fund | In study pool | Verified captures | Distinct holdings dates | First application capture | Nov 2 monthly check |
| --- | --- | ---: | ---: | --- | --- |
| XLE | Yes | 34 | 17 | Oct 8, 2026 UTC | Holdings-weight residual unresolved |
| XLB | Yes | 33 | 17 | Oct 8, 2026 UTC | Holdings-weight residual unresolved |
| XOP | No, identity hold | 33 | 17 | Oct 8, 2026 UTC | Holdings-weight residual unresolved |

The first captures followed the October 1 monthly decision. We also tested November 2 separately using the October 30 New York close. The application read the pinned capture available at that cutoff and enforced its own freshness, required-fields and weight-reconciliation checks. The November result is separate from the 70 historical dates. A first-seen timestamp can support subsequent decisions once the other gates pass. The complete per-fund/month counts and failure reasons are retained. [Monthly pool inventory](monthly-pool-coverage.json) · [Issuer details](issuer-coverage.json).

## A concrete route to an admissible history

An official XLE N-PORT-P filing illustrates the timing problem. The report covers December 31, 2024, but EDGAR records acceptance on February 27, 2025 at 12:20:41, 58 calendar days later. Its series is S000006410, class C000017596, accession 0001752724-25-043833. The investment schedule includes security identifiers and a futures position. A January 2025 decision could not have used this filing. Public dissemination and any later amendments must be recorded separately from the portfolio date. We checked the filing index and rendered investment schedule. Direct retrieval of the XML and index from this host returned HTTP 403, so this is source-feasibility evidence only. [SEC filing index](https://www.sec.gov/Archives/edgar/data/1064641/000175272425043833/0001752724-25-043833-index.html) · [Filed investment schedule](https://www.sec.gov/Archives/edgar/data/1064641/000175272425043833/xslFormNPORT-P_X01/primary_doc.xml) · [SEC dataset guide](https://www.sec.gov/files/nport_readme.pdf).

The next bounded item is a **single-reporting-quarter data qualification pilot**. Use the 29 equity funds as the inventory and December 2024 as the target reporting month. Establish the actual fund/series identifiers, applicable filings and gaps, including funds with different fiscal calendars. Retain the full portfolio, cash, derivatives, unmatched names, accession, as-of, first evidenced public availability and amendments. Never activate a revision before dissemination. A missing fund or reporting period stays missing.

Join the disclosed equities to effective-dated security identifiers, including exits and corporate actions, and measure how much weight and how many names have sufficient hash-verified published adjusted prices and raw activity at each decision. Reconcile weights and report the remaining coverage gaps before committing to a multiyear backfill. Holdings and price histories are separate gates. Dated VWAP, size and industry classifications also depend on the chosen formula. A common equity universe and rank denominator must be declared, followed by aggregation using each fund's actual available holdings. Hold non-equity sleeves to the declared control or abstention policy in any future experiment.

The previous ETF-level Alpha101 screens and tilt comparisons completed the earlier diagnostic work. They did not establish a constituent-level edge. No return, weakest-traded ETF, validated alpha or strategy-promotion claim arises from this coverage assessment. Stop here for discussion.

## Verification

The assessment pins the 5,356-entry November 3 price catalog, its verified parent, the two holdings source families and three issuer catalogs. It uses the pinned 52-fund protocol and class taxonomy. The data reader verified the catalog manifest and the issuer reader validated each capture. Native reads used specific source/version pairs. The runner can repeat the audit using the saved pins. [Assessment](assessment.json) · [Publication pins](pins.json) · [All 265 snapshot coverage rows](historical-snapshot-coverage.json).
