# Repository maintenance

The October 12, 2026 restructuring keeps trading and calculation contracts in
their existing packages. It separates presentation resources and request contracts,
reduces duplicate project memory and adds explicit local maintenance commands.

## Code map and compatibility

| Boundary | Location | Contract |
| --- | --- | --- |
| Request/response schemas | `src/systematic_trading/web/contracts.py` | Existing API names re-exported from `web.api`; routes and response shapes remain stable. |
| Pure risk-parity preview | `src/systematic_trading/portfolio/preview.py` | Validated inputs, no broker/store I/O. Web adapter translates domain errors to HTTP 400; malformed inputs are 422. |
| HTML templates | `src/systematic_trading/presentation/assets/` | UTF-8 package resources included in wheels and frozen LEAN bundles. Template bytes are part of bundle verification and serving revision inputs. |
| Page composition | `web/operator.py`, `web/platform.py` | Cache only static HTML per process. Every request creates a fresh response; live values continue to load from APIs. |
| Report calculation | `backtest/reporting.py` | Existing accounting/report functions and import names retained; rendering loads the packaged template. |
| Log maintenance | `maintenance/log_archive.py`, `scripts/archive_logs.py` | Explicit file selection, hash/readback receipts, no scheduled deletion or trading authority. |

The old duplicate Strategies template and unreachable raw Market Data template
were removed. No broad routing or storage rewrite was attempted: `web/api.py`
still owns its existing order/approval orchestration. Splitting those handlers
requires explicit dependency seams and execution-contract coverage, not file moves
that invalidate monkeypatching or introduce circular imports.

## Demonstrated fixes

- Empty preview lists no longer divide by zero. Duplicate symbol/currency inputs
  are rejected before dictionary construction. Missing FX yields an actionable
  error without queuing a proposal; the CNH base rate must equal one.
- Inverse-volatility rounding preserves a total of one without exceeding the
  concentration cap. Zero, negative and non-finite volatility and caps that cannot
  be represented at four decimal places fail explicitly. This is limited to the
  beta risk-parity helper, not a rewrite of registered strategy recipes.
- Alpha101 paper verification uses the retained reference location and preserves
  the original SHA-256 pin. Formula extraction rejects altered documents.

## Measurements — October 12, 2026

- Five page handlers: median of five batches of 50 calls, warmed in one process.
  Static composition improved 5.6–16.7 times (Trading approximately 1.01 ms to
  0.061 ms); all five HTTP bodies remained byte-identical. This measures Python
  rendering overhead, not database latency, browser work or strategy calculations.
- SHA-256 verification: seven repeats on a synthetic 32 MiB file. Median time
  fell from 22.1 ms to 14.0 ms; traced peak Python allocation fell from 32 MiB
  to 0.38 MiB. Streaming preserves the exact hash and handles chunk boundaries.
- Seven log archives: 92,751,016 source bytes to 6,275,459 compressed bytes, with
  per-file hashes and decompression readback. The operational log resumed appends.
- Five current memory/plan files: approximately 941 KB to 138 KB before this
  session's closing entry, plus 339 KB of verified compressed originals. All open
  milestone IDs remain except redundant P7.5 (agent Kanban reminders), retired into
  history because the start/end session rule already governs tracker upkeep.

Local receipts are under `var/maintenance/`: `web-before.json`, `web-after.json`,
`template-extraction.json`, `hash-benchmark.json`, `docs-size.json`,
`archive-verification.json` and `package-verification.json`. Log archive receipts
remain beside their gzip files. Large research-worker budgeting is still P6.15;
these measurements do not establish a new concurrency limit.

## Checks

Run from the repository root:

```powershell
.venv/Scripts/ruff.exe check src tests scripts
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe scripts/check_docs.py
git diff --check
```

The suite uses isolated application defaults. Database integration cases require
their explicitly disposable test environments; do not point them at production.
New regressions cover preview validation and cap invariants, static response
isolation, frozen resource packaging/tampering, paper hashes and log archival.

Final October 12 validation: **1,691 passed, 55 optional skips**, with two existing
test-client dependency deprecation warnings. Ruff and whitespace checks passed;
the documentation checker verified local links and both ZIP manifests. The wheel
rendered from outside the checkout and the frozen bundle resource/tampering tests
passed. `var/maintenance/final-tests.xml` records the complete suite.

## Log compression and recovery

Preview an explicit closed-file selection, then apply it:

```powershell
.venv/Scripts/python.exe scripts/archive_logs.py worker-20260101.log
.venv/Scripts/python.exe scripts/archive_logs.py worker-20260101.log --apply
```

Closed files require dated names (or recognized retired probe filenames) and at
least seven days without modification. Receipts and `.gz` files go to
`var/log/archive/`. The original is removed only after decompression/hash
verification and a stable size/mtime/identity check. Archives are never overwritten.
Failure leaves the original or detached source for inspection; a gzip without
a successful receipt is not accepted archival evidence.

Windows short-lived append writers support atomic rotation of exactly these two
logs. The OS refuses the rename while a writer has the file open; retry later if
that happens. There is no copy-and-truncate fallback.

```powershell
.venv/Scripts/python.exe scripts/archive_logs.py platform_operations.jsonl intraday_recovery.jsonl --rotate --apply
```

Later appends use a fresh file at the same configured path. Long-held stdout/stderr
handles cannot use this online operation. Other platforms must stop the owner and
use a dated closed file. No recurring retention policy is enabled by this command.

To recover a log, decompress to a **different** path and verify its SHA-256 against
the adjacent JSON receipt. Never replace an actively written log. Preserve the
gzip/receipt pair together under `var/log/archive`. The current full-system
backup configuration includes `var`; this session verified local archive readback,
not a new off-machine backup or restore.

## Documentation and evidence

[Archive guide](archive/README.md) describes byte-preserved project memory and
registered research protocols. Current docs link to retained findings and label
missing rendered reports as unavailable in this checkout. None was regenerated
from provider archives. The archive is reviewable separately, not disposable
execution or research evidence.

Generated reconciliation snapshots and maintenance receipts are ignored by Git,
but remain on disk; already tracked files remain tracked. No raw market data,
broker records, database or frozen study evidence was deleted.

## Deployment boundary

The maintenance source was deployed by a guarded restart on October 13, 2026.
The existing paper policy was paused, reconciliation passed after restart, and
the same policy and capital cap were restored. Application calculations caught
up through October 12. Further calculation source changes still require a normal
guarded restart; do not disable the source-identity checks to avoid it. Package
resources are immutable for the process lifetime.
This maintenance does not approve allocations, submit orders or enable live mode.

At close-out inspection, paper auto-approval was enabled and ten stored orders were
marked partially filled. The running process reported the expected source-change
guard and a ClickHouse archive INSERT timeout. Services were left running with
their existing policy; deployment/recovery requires a controlled restart and fresh
operational review. Existing ambiguous database writes were not manually retried.
