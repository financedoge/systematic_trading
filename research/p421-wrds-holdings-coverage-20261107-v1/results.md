# Historical holdings coverage and MDY filing comparison

CRSP has candidate holdings histories for all 29 equity ETFs in the existing
supported cohort. The retained coverage extract contains 2,012 distinct
portfolio/report-date snapshots between December 2020 and September 2026.
This improves source coverage substantially; it is not yet qualified historical
decision coverage for P4.21.

All 238 fund-name intervals and 29 portfolio mappings are retained locally.
Every returned coverage group maps uniquely through dated vendor fund-name and
fund/portfolio intervals. Current headers and ticker-only lookups do not certify
historical fund identity. The 29-fund by 70-month report grid has 18 absent
snapshots; none was filled. MDY has 67 report dates, SPY 68 and VGK 66. The
[assessment](assessment.json) retains counts for every fund.

There are 2,518 report/receipt-date groups for those 2,012 snapshots, so some
portfolios contain multiple receipt dates. Receipt lags range from 5 to 69 days,
with an eight-day median across groups. These are descriptive vendor-receipt
lags, not execution delays or a proposed availability rule. The snapshot cannot
be declared available from the earliest receipt of one holding. Rank ties occur
in 1,103 groups; ties alone do not establish duplicated holdings.

The predeclared MDY December 31, 2024 control contains 402 CRSP rows and 401 filed
positions. Matching only unique filed CUSIPs or CUSIPs embedded in US ISINs gives
382 pairs. All 382 agree exactly on both share count and USD market value, without
rescaling or normalizing weights. The other filed positions comprise 18 foreign
ISINs without a retained CUSIP bridge and one unmatched US CUSIP. CRSP also has a
cash row. Row-level comparisons and all unmatched source records remain in the
local licensed archive; none is silently joined by ticker.

The unmatched US identifier appears for VNOM: the filed CUSIP differs from the
CRSP holding's CUSIP. The old/new security identity needs dated resolution before
using that row. The foreign group includes FLEX; this cross-source snapshot
does not itself close FLEX's required identifier bridge.

MDY's CRSP receipt date is February 8, 2025. The retained SEC filing was accepted
on February 27, 2025 at 12:07:37 New York. Those are different observations about
information flow. CRSP defines the effective date as receipt from its vendor;
neither the earlier date nor today's matching values prove that this exact
database vintage was available to a historical user on February 8.
[CRSP field definitions](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Mutual_Funds_Guide_SAS_ASCII_R.pdf) ·
[Retained SEC filing receipt](../p421-quarter-20261104-v1/filings/0001752724-25-043691.json).

Five query responses, exact SQL/parameters, hashes, source types and executed code
are stored locally outside Git, including the 402-row snapshot. No active
publication or strategy replay occurred; historical available_at remains null.
Fifteen focused tests cover access scope, integral identifiers, dated mappings,
missing intervals and conflicting/foreign identifiers; Ruff passes. Preserve
these archives as active qualification evidence. This data-only check has no
weakest-ETF performance chart.

Remaining work is dated identity resolution for the unmatched positions,
portfolio completeness across receipt groups, vendor dissemination/revision
semantics and broader price/activity qualification. No investment or strategy
choice follows from this coverage check.

[Protocol](protocol.json) · [Audit plan](audit-plan.json) · [Capture](capture.json) ·
[Assessment](assessment.json) · [Acceptance](acceptance.json) ·
[Artifact hashes](artifact-manifest.json).
