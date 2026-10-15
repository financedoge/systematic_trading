# P4.16d stage 1 reference inventory

Start with the [review report](../../docs/etf-universe-inventory-2026-10-13.md).
This is an offline, dated planning artifact, not an application strategy registry.

- [Full gap matrix](gap-matrix.md): 299 symbol/regime rows.
- [Inventory](inventory.json): field-level metadata, proposed classes and gaps.
- [Candidate IDs and groups](candidate-seed.json), [taxonomy](taxonomy.json),
  [proposed screening protocol](protocol.json), [identity events](identity-events.json).
- [Input manifest](source-manifest.json) and [delivery receipt](receipt.json).

Large reference snapshots are losslessly compressed under `sources/`; the input
manifest records both compressed and original-byte SHA-256 hashes. The original
governed manifest binds the copied catalog; `governance-evidence.json` records
checked audit/bar hashes and file sizes. No provider price archive is an input.
The issuer snapshot contains unrelated website fields; the offline parser only
extracts ticker/name/product identity/inception. Returns, prices, yields and AUM
do not determine this inventory.

The direct SEC/OCC byte requests returned HTTP 403. Their records were read via
web retrieval; `identity-events.json` retains source URLs, access limitations and
the extracted factual event. No local copy is falsely claimed for those documents.

```powershell
.venv/Scripts/python.exe scripts/build_etf_inventory.py --check
.venv/Scripts/python.exe -m pytest tests/test_etf_inventory.py
```

Rebuilding requires only Python's standard library and local sources; no network,
database, app restart or broker connection. To revise the research design, create
a new version instead of modifying this frozen review bundle. Future ingestion
uses existing application-owned recorders and audited publication contracts.
