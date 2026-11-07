# WRDS holdings access

The school subscription permits actual reads from `crsp_q_mutualfunds.holdings`,
dated fund names, fund headers, fund summary and dated fund/portfolio mappings.
This was tested with bounded constant-row queries, not inferred from visible
table grants. No holdings observations were extracted in this access check.

Eight responses are retained locally with queries, parameters, PostgreSQL types,
capture times, hashes and executed code. They include 29 table descriptions and
399 column descriptions. The connection remained read-only with verified TLS and
the existing protected passfile. No credentials appear in the evidence folder.

The holdings table exposes `report_dt` and `eff_dt`. CRSP distinguishes the
portfolio's report date from the date it received information from its vendor.
Vendor receipt is not automatically proof of end-user dissemination or of the
historical availability of every value in today's revised database.
[CRSP documentation](https://www.crsp.org/crsp_pdf/crsp-survivor-bias-free-us-mutual-fund-database-guide-crspsift/).

Four focused tests verify the fixed schema/table scope and constant-row query;
Ruff passes. The asset search found no existing holdings strategy asset. This
inspection reuses the WRDS access helper and introduces no new strategy input.
The subsequent [29-fund coverage check](../p421-wrds-holdings-coverage-20261107-v1/results.md)
is separately frozen. No portfolio calculation or weakest-ETF chart applies.

[Protocol](protocol.json) · [Assessment](assessment.json) ·
[Acceptance](acceptance.json) · [Artifact hashes](artifact-manifest.json).
