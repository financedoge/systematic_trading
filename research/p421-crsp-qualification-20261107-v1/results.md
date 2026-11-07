# Dated CRSP identity and daily comparison

WRDS access succeeded. The bounded extract retained 2,783 daily rows for eleven
candidate securities, covering the ten requested tickers over February 27, 2024
through February 28, 2025. Original rows, SQL, parameters, PostgreSQL types,
timestamps and hashes remain in the local licensed source archive outside Git.

Nine securities have unique dated ticker/trading-symbol/CUSIP matches to their
existing ISIN identities: CASY, CSL, FIX, MANH, RPM, RS, UTHR, WSO and XPO. Their
2,277 stock-days have complete coverage. WSO Class A and WSOB Class B were
disambiguated by dated identifiers, preserving all 253 Class B rows separately.
The other 253 rows, for FLEX, remain unjoined: its Singapore ISIN requires a
retained CUSIP bridge. The attempted SEC document download returned HTTP 403;
a search snippet is not accepted as identifier evidence.

All 2,277 matched closes are within the previously declared half-cent diagnostic
of the pinned published raw closes. CRSP cash-distribution dates and amounts
match all 24 events in the published ledger. This corroborates these fields over
the bounded window; it does not clear older review findings or certify every
corporate action or the historical availability of this vendor vintage.

Volume matches the SIP pilot exactly on 1,479 days and the existing published
history on only 14. The median absolute CRSP/SIP difference is zero, with a
38.952484% maximum. CASY, MANH and UTHR have no exact daily volume matches to SIP
in this window. These are diagnostics rather than newly invented tolerances.

CRSP agrees with IBKR on both independently investigated FIX days. It disagrees
with the equal Alpaca/IBKR totals for the UTHR July 3 early-close control. Therefore
it is independent evidence, not a universal replacement or tie-breaking rule.
[Five-case comparison](../p421-large-volume-20261107-v1/results.md) ·
[Early-close control](../p421-crsp-early-close-20261107-v1/results.md).

The isolated native publication contains 2,277 observations and two documents
under `governance/pilots/p421-crsp-daily-v1`. All payloads read back with exact
hashes; every historical available_at remains null. Licensed row-level comparison
details stay local. There is no active catalog admission or strategy replay.
Effective identifier intervals are not evidence of when historical users could
obtain the current vendor extract. The older legacy name table ends in 2024;
the dated CIZ intervals, not current header data, support the 2025 joins.

Retain the extract and compact findings as active qualification evidence. The
remaining gates are the FLEX bridge, field-specific source discrepancies,
decision-time availability, historical holdings/membership and sufficient
qualified lookback coverage. A weakest-ETF chart is inapplicable: no strategy or
portfolio result was calculated.

[Protocol](protocol.json) · [Assessment](assessment.json) ·
[Publication receipt](publication.json) · [Acceptance](acceptance.json) ·
[Artifact hashes](artifact-manifest.json).
