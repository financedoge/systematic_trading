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

## Storage and memory review — October 17, 2026

The read-only inventory found **4,832,482 files / 477.32 GiB of logical file
lengths** under `var/`. These are not allocated-disk or reclaimable-space figures.
The streaming scanner followed no reparse points and reported no read errors.

| Tree | Logical GiB | Meaning and cleanup decision |
| --- | ---: | --- |
| `var/governance` | 353.17 | Audited publication history and quarantine evidence. A separate NTFS identity scan found only **18.43 GiB / 82,299 unique files** across 3,027,489 file names in its subdirectories; 2,974,066 names are hard linked. Do not equate removing a snapshot with reclaiming its displayed size. |
| `var/tracked_strategies` | 58.20 | 239 revision directories containing frozen inputs, source bundles and runs; historical publications and PostgreSQL run receipts can reference them. Requires dependency-aware retention. |
| `var/research` | 53.53 | 62 study trees. The width/timing study alone is 13.39 GiB. Preserve registered inputs, code, native parity and corrected/superseded evidence; deduplicate immutable repeated blobs before considering study retirement. |
| `var/tracked_models` | 6.77 | 273 model directories; fitted schedules are pinned by calculation provenance. Not a disposable cache by directory name. |
| `var/system-backup` | 4.15 | Includes a stopped 3.586 GiB PostgreSQL restore-test cluster and an active backup cache. Only the retired test cluster was selected for removal. |
| `var/database-sync` | 1.09 | Current recovery checkpoints; retain. |
| Other trees/files | 0.41 | Broker, reconciliation, logs, runtime, legacy SQLite and small artifacts. Little potential gain; preserve durable evidence and recovery keys. |

The unique-file measure excludes allocation rounding, metadata and compression;
external hard links may share those identities. It does not establish exact physical
usage for the whole `var/` tree. Repeated source/input contents in research and
strategy bundles remain a separate deduplication opportunity, not measured savings.

There are 340 local published governance roots, 203 incomplete/quarantine roots
and five roots with an unpublished manifest. Unpublished is not synonymous with
safe to delete: failed runs can have partial database publications and retained
incident evidence. The current cash-relative, class/volatility and ETF-expansion
studies all pin `research-2026-10-12-8f374b4464a3`, batch
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
Its manifest hash and catalog publication were checked. The cash-relative protocol
also explicitly depends on the earlier class/volatility study, which depends on
ETF expansion. Latest-catalog-only retention would therefore be incorrect.

### Clear cleanup candidates and limits

- The disposable `var/system-backup/postgres-restore-drill/data` cluster contains
  3.586 GiB. `pg_ctl status` reports no server, `pg_controldata` reports a clean
  shutdown on October 7, no PID file or listener on its recorded port 49690 exists,
  and the active PostgreSQL Windows service uses
  `D:/systematic_trading_data/postgresql/18/data`. Preserve the four drill logs and
  record its removal. **Automatic approval review rejected the attempted removal
  with “blocked by policy”; no deletion command executed.**
- Outside `var/`, active ClickHouse parts contain **82.53 GiB of system diagnostic
  logs**, including 61.00 GiB of `processors_profile_log` and 15.13 GiB of `text_log`.
  These are distinct from the 48.76 GiB of active analytical/market-data parts.
  The profiling table has a 30-day TTL; query/text/trace tables have none. Normal
  queries enable processor profiling and one-second CPU/wall-clock sampling.
  Retaining recent diagnostics, reducing routine profiling and applying a bounded
  log-retention policy is the largest clear cleanup opportunity. No log table was
  truncated or altered during this review. Reclaiming space inside Docker's Linux
  filesystem does not necessarily shrink its Windows VHDX immediately.
- Docker labels a **42.5 GB LEAN image** reclaimable because no container currently
  uses it. Its digest is pinned by tracked strategy configuration; keep it.
- The last recorded completed full-system snapshot is October 10; the October 17
  attempt remains `verifying`. A current verified backup/restore cannot be assumed
  from the presence of a NAS destination or an uploaded candidate snapshot.

### Docker versus native services

ClickHouse serves versioned analytical publications, governed histories and reports.
NATS carries the PostgreSQL event outbox through JetStream. Docker already runs both
locally; it provides packaging and lifecycle management, not their storage contracts.
NATS can run as a native Windows executable. ClickHouse's supported Windows path is
Linux under WSL, so removing its container would retain a Linux VM. The pinned LEAN
worker also uses Docker. A migration must include start/stop/recovery, health checks,
native backup/restore and retained database/stream state, not only new executables.
The existing JSONL publisher is a possible simpler local mode, but selecting it
changes event delivery/replay semantics and must include dispatcher/recovery tests.
Merely stopping NATS while leaving the dispatcher configured for NATS is incorrect.

At inspection, Docker reported 5.07 GiB for ClickHouse and 3.75 GiB for NATS, while
the NATS server reported only **43.05 MiB** process memory and ClickHouse reported
about **1.05 GiB** resident memory. ClickHouse cgroup accounting included about
5.99 GiB of file cache and 0.61 GiB anonymous memory. These samples were taken at
different instants and cannot be summed as independent host memory use. Container
usage, process RSS and WSL working set measure different things; the NATS discrepancy
is consistent with container/file-cache accounting, not evidence of a 3.75 GiB Go heap.

Both containers have no explicit memory limits. ClickHouse reports a 12.85 GiB server
memory allowance, 5 GiB mark-cache capacity and 7.70 GiB uncompressed-cache capacity;
these are limits/capacities, not current allocations. No user `.wslconfig` was found.
The tracked-calculation scheduler sees a 15.39 GiB Docker budget and reserves only
2 GiB before allowing **three concurrent 4 GiB LEAN workers**. It does not measure
current service/host pressure, and model fitting can use all 16 host cores. This is
a concrete capacity-planning gap, although these snapshots do not prove the cause
of every reported memory incident.

NATS holds 3.21 million messages / 3.88 GiB, with zero consumers at the inspection
instant. The stream has no age/message/byte retention limit, within the server's
5 GiB file-store ceiling. Define replay/backup retention before changing those limits;
unbounded growth can eventually stop publication even though the process is small.

Recommended follow-up order:

1. Bound diagnostic retention/profiling and complete the explicitly blocked retired
   restore-test cleanup when permitted; retain recent incident diagnostics.
2. Test an explicit service budget plus **one LEAN worker initially**, retaining
   host headroom; adjust using measured peak calculations and backup workloads.
   Configure WSL/container limits together, not by imposing an arbitrary low VM cap.
3. Build a reference graph from all retained study manifests, model/run registries,
   current/previous strategy publications, governance parents and paper evidence.
   Verify backup readback, hash-check immutable duplicates, deduplicate without
   changing manifest bytes/paths, then retire only proven unreachable artifacts.
4. Consider native NATS or a supported simpler publisher profile after the measured
   storage/memory issues are fixed. Native ClickHouse in WSL is optional deployment
   work, not an established memory fix.

Evidence: `var/maintenance/storage-review-20261017.json`,
`governance-physical-review-20261017.json`, `governance-publication-review-20261017.json`,
`storage-service-review-20261017.json` and `storage-dependency-checks-20261017.json`.
The API, ClickHouse and NATS health endpoints returned HTTP 200. No calculation source,
runtime service configuration, database table, stream or data file was changed.

Official deployment references: [NATS Windows installation](https://docs.nats.io/concepts/getting-started/),
[ClickHouse Windows/WSL installation](https://clickhouse.com/docs/get-started/setup/self-managed/clickhousectl),
[Docker WSL memory guidance](https://docs.docker.com/desktop/features/wsl/).

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
