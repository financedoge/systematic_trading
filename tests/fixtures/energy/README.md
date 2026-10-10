# EIA parser fixtures

Shortened October 7/8, 2026 official releases, captured during source qualification.
These files are deterministic parser fixtures, not historical research inputs.

- `balance.csv`: official `https://ir.eia.gov/wpsr/table1.csv`, Windows-1252.
- `estimates.csv`: header/utilization row from `https://ir.eia.gov/wpsr/table9.csv`.
- `stocks.json`: U.S. series and last three rows of `https://ir.eia.gov/wpsr/psw00.json`;
  fixture start-date metadata shortened to match.
- `storage.json`: Lower 48 series from `https://ir.eia.gov/ngs/wngsr.json`.
- `release.html`: release date/time/period excerpt from `https://ir.eia.gov/ngs/ngs.html`.

Tests mutate these fixtures to exercise missing data, mixed dates, revisions,
failed publication, pre-capture decisions and tamper detection.
