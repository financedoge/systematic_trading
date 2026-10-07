# CRSP cross-reference: access pending

On October 4, 2026 the operator requested the full CRSP US stock history on D:
and in ClickHouse as an additional comparison source, then confirmed they do
not have CRSP access. No CRSP data was downloaded or imported. A subscription
or a licensed export is required before acquisition can proceed. Public demos
are not a substitute for the requested history.

CRSP lists daily/monthly data, active/inactive securities, corporate actions,
permanent PERMNO/PERMCO identifiers and CIZ flat-file delivery. Direct delivery
uses MOVEit; WRDS and Snowflake are other access routes. Flat-file availability
does not make the database a free public download.

Official references:

- [CRSP US Stock Databases and delivery formats](https://www.crsp.org/research__trashed/crsp-us-stock-databases/?activetab=docs)
- [WRDS CRSP download tutorial: subscription required](https://wrds-www.wharton.upenn.edu/pages/classroom/accessing-data-via-the-wrds-api-and-excel/)

When access is supplied, retain the licensed release and its checksums outside
Git, proposed at `D:/systematic_trading_data/research/crsp/<release>/`.
Inspect the actual release/schema before choosing an importer. Preserve CRSP
identifiers, dated ticker mappings, missing/quote indicators, adjustment factors,
returns and delisting information. Do not equate ticker strings across eras or
compare differently adjusted prices as though they used the same basis.

Load provenance-bearing observations into the existing source/governance flow,
verify ClickHouse readback and publication hashes, and expose comparable fields
in the Debug source comparison view. Addition as a cross-reference does not
authorize changing the selected published research history or strategy inputs.
This is a recorded next step, not an implemented or validated CRSP importer.
