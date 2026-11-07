# WRDS connection setup and archive retention — November 7, 2026

**Complete, verified at 17:12 Asia/Shanghai.** The password file was saved and
read-only reconnects succeeded with verified TLS. Actual reads pass for CRSP
annual daily prices and historical security identities. The requested TAQ trade
and master views explicitly deny access.

| Tested object | Observed access |
| --- | --- |
| `crsp_a_stock.dsf_v2` | Read passes; 50 columns inspected, including daily price, returns and volume |
| `crsp_a_stock.dsenames` | Read passes; 21 columns inspected |
| `crsp_a_stock.stksecurityinfohist` | Read passes; 36 columns inspected |
| `taqm_2024`, `taqm_2025` | Schema usage is false |
| `taqmsec.ctm_20250224`, `taqmsec.mastm_20250224` | Views are visible but actual reads fail: insufficient privilege, SQLSTATE 42501 |

The view tests matter: visible metadata/table grants alone do not establish
access. No denied-access workaround was attempted. Read checks returned a
constant with `LIMIT 1`; no market observation rows were extracted.

The [WRDS Python guide](https://wrds-www.wharton.upenn.edu/pages/support/programming-wrds/programming-python/python-from-your-computer/)
creates a password file locally after an initial login. On Windows the standard
location is `%APPDATA%\postgresql\pgpass.conf`; the file is now saved there.
The helper uses the existing psycopg driver and the same libpq format,
with masked local entry and file access restricted to the user and SYSTEM. It
does not overwrite an existing file or log credentials. The WRDS package's older
pandas dependency was not installed into the platform environment.

The initial direct login failed and saved no password. Subsequent direct TCP
probes timed out. The existing loopback HTTP proxy successfully reached WRDS,
verified its TLS certificate and elicited the PostgreSQL password request. The
temporary local relay preserves end-to-end TLS and the original hostname/port
for passfile matching; no global network settings change. The operator completed
authentication on the phone. The initial login and file save succeeded; reconnect
failures were retained before later saved-file checks passed.
[WRDS database MFA](https://wrds-www.wharton.upenn.edu/pages/about/log-in-to-wrds-using-two-factor-authentication/)
requires a Duo Mobile push when further MFA is needed; a saved password is not an
MFA bypass.

**Still open:** requested date coverage and exact field/session definitions.
No market observation data has been downloaded, qualified, published or used by
a strategy. Fourteen focused tests pass; Ruff is clean. Nine query-result payloads
and two denied-query receipts are archived locally with exact queries, parameters,
capture times, column types, row counts, checksums and executed runners. All
payload hashes/counts and the executed probe hash pass.
[Compact acceptance](acceptance.json) identifies the retained archive.

The operator requires a local copy of every WRDS extract. The prepared archive
root is `D:\systematic_trading_data\source-archives\wrds`. Retain lossless source
rows with exact queries/parameters, capture times, table/release versions when
supplied (unknown otherwise), identifiers, row counts and SHA-256 hashes.
Identical captures may share a verified payload while retaining separate receipts.
The sole source copy is protected from disposable-study cleanup. Licensed rows
and credentials stay outside Git. New source copies require audit and publication
before strategy use; current capture does not establish past availability.

Next: perform the bounded CRSP sample comparison and verify field definitions.
CRSP daily volume is useful independent evidence; it does not by itself supply
the missing intraday session/trade-condition decomposition. TAQ access remains
necessary for that source-specific check. The existing
[50-stock-day request](../p421-volume-contract-20261107-v1/source-request.json)
remains frozen in [protocol.json](protocol.json); [retention.json](retention.json)
records the archive contract. Stop for discussion after the access check before
expanding the data acquisition.
