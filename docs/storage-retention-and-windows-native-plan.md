# Disk cleanup and native Windows migration

## Decision and scope

On October 17, 2026, the operator chose storage and memory efficiency over preserving
every historical experiment. Archived research may retain its findings and rerun
recipe while discarding bulky generated artifacts. The selected deployment target
is native Windows PostgreSQL, compressed Parquet queried by native DuckDB, and
native NATS. ClickHouse is being replaced: its supported Windows installation uses
WSL. Docker and WSL must not remain dependencies of the completed platform.

This is the implementation plan, not a completed migration or deletion receipt.
The [native runtime guide](native-windows-runtime.md) records implemented defaults,
actual budgets and remaining differences from this initial design; the execution
Kanban and immutable maintenance receipts record acceptance and measured cleanup.
The current ClickHouse/NATS containers continue serving the app until replacement
validation and cutover. Existing paper/live authority, reconciliation and input
quality checks remain in force.

The operator accepts loss of exact historical reproduction for retired research.
A rerun after its original inputs have been retired is a new study result on a
new pinned audited input batch. Preserved historical metrics remain labelled as
historical findings; they cannot become fresh promotion evidence without a new
validated run. Do not require full backups of artifacts deliberately designated
disposable merely to recreate the same storage burden elsewhere.

## Current protection set

The live API snapshot has 29 catalog rows: 22 archived entries representing 21
strategy IDs, and seven monitored strategies. Control revision 7 has FR25 as SOTA
and at 100% paper allocation, with no pending allocation. Older F3 allocation notes
are historical. Re-read these controls immediately before any cleanup or cutover.

Protect the current calculations and dependencies of:

- `research_fr25_14_v1`.
- `research_fallback_f3_v1`.
- `research_m1_14_v1`.
- `research_fr25_alpha_tilt_5_v1`.
- `research_economic_context_ridge_v1`.
- `research_etf_activity_lag20_v1_usd_v1`.
- `research_rolling_xgboost_1y_lag20_v1_usd_v1`.

Also protect active/pending allocations, retained promotion candidates, running jobs,
the current cash-relative retest and its required class/volatility and ETF-expansion
inputs, and evidence supporting broker decisions and reconciliation. Cleanup does
not archive additional strategies or change monitoring membership by itself.

The current and preceding complete strategy publications occupy approximately
0.89 GiB together, against 58.20 GiB across 239 revision directories. This makes
superseded revisions the principal application-artifact target. The difference is
an upper bound before additional protected dependencies and shared blocks, not
guaranteed reclaimed capacity. The small legacy `var/backtests` tree totals only
0.22 GiB; deleting archived dashboard entries alone will not solve the problem.

## Retention policy

| Artifact class | Retain | Retire |
| --- | --- | --- |
| Monitored calculation | Latest complete revision, preceding complete rollback revision, active attempt, exact model/data dependencies | Older unused preparations, bundles, source copies and full run output after compact receipts are retained |
| Archived strategy | Definition/version, findings, compact last report/metrics, source commit or compact source patch, rerun command, retirement record | Study-only inputs, repeated source trees, full NAV/event grids, model fits and verbose engine logs unless protected elsewhere |
| Completed exploratory study | Hypothesis, declared variants, result/limitations, correction history, concise summary, runner/config | Per-scenario bundles, intermediate arrays, repeated input copies, rendered duplicates and full outputs after extracting the summary |
| Active research or promotion | Complete required input/code/result evidence until disposition | Unreferenced failed attempts under the failed-job rule |
| Failed attempt | Failure summary and last useful diagnostic; allow 7 days for investigation | Older failed workspaces without a retry lease or incident hold |
| Governed data | One canonical audited history across the full supported pool; required vintages, raw/adjusted distinctions, source/audit lineage and pinned batch dependencies | Repeated snapshot directories and unreferenced obsolete versions after equivalent canonical storage is verified |
| Paper and broker evidence | Orders, fills, approvals, allocation history, decision inputs, reconciliation, audit events and recovery keys | No deletion under the exploratory-research policy |
| Operational diagnostics | 7 days routine logs; explicitly pinned incidents; concise errors and metrics | Routine processor traces beyond 24 hours and other logs beyond the configured window |

Historical research registry rows remain immutable. Record artifact retirement in
a separate append-only table/manifest keyed by run ID, original hashes and path.
A historical registry reference or documentation hyperlink does not by itself pin
all retired research blobs forever. An execution/promotion dependency does.

The archived strategy UI and report routes must read the compact retained summary,
show that detailed artifacts were retired, and offer the supported rerun path.
They must not return a broken report, silently recreate deleted artifacts during
an ordinary refresh, or claim that an exact historical rerun remains available.
Unsupported legacy strategies retain a recipe/source note without promising a
working one-click restore.

The initial generated-artifact budget is 20 GiB soft / 40 GiB admission limit,
excluding canonical histories, operational evidence and backup recovery points.
Protected dependencies take precedence: exceeding the limit queues new heavy work
and reports the protected footprint instead of deleting required evidence. These
are initial engineering budgets to validate, not measured steady-state sizes.

## Cleanup waves

### Wave 1 Remove disposable diagnostics and test state

1. Retain recent incident/error diagnostics and set bounded logging before clearing
   old ClickHouse system logs. The previous inventory measured 82.53 GiB across
   those diagnostic tables, separate from analytical/market data. Avoid expensive
   full-table deletion mutations; choose partition retirement or a controlled
   truncate after extracting the retained diagnostic window. Do not migrate system
   logs into the new analytical store.
2. Remove the stopped 3.586 GiB PostgreSQL restore-test data directory, keeping its
   validation logs and disposal receipt. The earlier attempt was rejected before
   execution by automatic approval review; this plan does not bypass that rejection.
3. Retire scratch and completed export workspaces after checking active job leases.
   Do not make a second full local quarantine copy. Preserve only compact receipts.

### Wave 2 Retire archived and superseded research artifacts

Build a dry-run manifest using live lifecycle/control state, job leases and the
retention policy. Each candidate records its owner, reason, exact resolved path,
content identity, retained summary and dependencies that prevent deletion.
Calculate savings from unique NTFS file identities and allocated blocks; deleting
one hard link does not reclaim the shared file.

First candidates include old tracked calculation revisions and superseded Alpha101
daily/exit/surface run directories. Completed width/timing (13.39 GiB) and
target-change (4.02 GiB) experiment trees can lose their large scenario bundles
after retaining findings and any inputs used by current work. FR25 model artifacts
must be traced before pruning selection-blend/economic studies because the active
recipe can depend on their fits. Do not select by directory age alone.

At apply time, obtain the shared maintenance/writer lock; recheck control and
publication revisions, running jobs, path containment, file identity and reparse
points. Delete only manifest-selected generated paths and emit per-path outcomes.
If any protected revision changed, regenerate the plan. Preserve unrelated tracked
files and uncommitted source. Afterward, load all monitored reports, resolve their
data/model pins and verify the current paper control state is unchanged.

### Wave 3 Compact the data layout and prevent recurrence

Move bulk storage to `D:/systematic_trading_data/`, leaving only small runtime state
and maintenance receipts under repository `var/`. Use these logical roots:

- `analytics/parquet/` for committed columnar fragments.
- `analytics/documents/` for compressed large report/source blobs.
- `analytics/staging/` and `analytics/scratch/` for bounded temporary work.
- `research/artifacts/` for retained calculation/model outputs.
- `nats/jetstream/` for native NATS persistence.

The apparent 353.17 GiB governance tree contains only 18.43 GiB of unique contents;
its main problem is millions of repeated names. Replace inherited directory copies
with small manifests referencing shared immutable fragments. Do not copy every
historical version into a new full snapshot. Avoid excessive tiny Parquet files:
use bounded symbol/date partitions and compact row groups with measured sizes.

Use one content-addressed source bundle per code version and shared input fragments
across scenarios. A new unrelated catalog wave must not force duplicate data/source
storage for every strategy. Preserve complete provenance while deriving computation
identity from the inputs that the strategy actually consumes.

Integrate retention into app-owned maintenance after successful publication and at
startup, with the same locks and protection rules. A failed refresh must retain the
last complete result and must not trigger its deletion. Do not create Codex jobs
or agents to perform recurring strategy calculations or cleanup.

## Native analytical architecture

PostgreSQL remains the transactional authority and additionally stores publication
metadata, committed manifests, fragment references, logical row counts/hashes,
current-version pointers and artifact retirement records. Large observations and
documents belong in compressed files, not duplicated JSON rows in PostgreSQL.

DuckDB reads immutable Parquet from native Windows processes. There is no shared
writable DuckDB database file and no additional database server to administer.
Readers pin a committed manifest once per operation. Writers serialize per dataset
using PostgreSQL advisory locks and use compare-and-swap publication revisions.

Publication is: write staging fragments, close/flush them, independently verify
rows and hashes, atomically rename on the same volume, then commit all manifest
references/current pointers in one PostgreSQL transaction. Readers cannot observe
partial publication. A crash before commit leaves reclaimable staging/orphan files;
cleanup respects writer leases and reader pins before reclaiming them.

Replace ClickHouse-specific SQL callers with typed store methods for:

- Current and pinned daily bars/FX, preserving source precedence and timestamps.
- Governed daily rows and source comparisons by batch/symbol/date.
- Versioned observations/documents and atomic publication/readback.
- Research archive, charts, execution benchmark qualification and report lookup.

Preserve canonical payload bytes/hashes, missing values, decimal precision, UTC
availability times, identity checks and current point-in-time limitations. Do not
translate ClickHouse `FINAL`, `argMax` or JSON SQL with blind string substitutions.
Deduplication/replacement ordering must be explicit and covered by contract tests.

Physical Parquet hashes will differ from legacy gzip/JSON manifests. Create a new
storage-format publication with a migration receipt linking old IDs, row hashes
and new fragment hashes; do not overwrite an old immutable manifest or claim its
file hash survived conversion. Keep the necessary legacy pins until replacement
calculations pass parity and publish under their new identities. Preserve the
existing workspace key explicitly when moving bulk paths; it currently derives
from the absolute `data_dir`, so changing that path blindly would orphan lookup.

Initial resource settings: one heavy analytics/export/backtest job at a time,
two DuckDB threads, 1 GiB DuckDB buffer limit and 10 GiB spill limit. Stream exports
instead of loading all rows into Python/pandas. DuckDB's buffer limit is not a full
process limit; use Windows Job Objects for native worker process-tree limits
(initially 3 GiB analytics/export, 4 GiB LEAN), bounded queues and timeouts. Queue
new heavy work when host available memory falls below 6 GiB. Keep the API/recorder
outside a disposable worker's kill boundary. Measure peak process and host commit,
not only RSS; tune budgets with retained representative workloads.

## Native NATS and LEAN

### NATS

Install a pinned, checksum-verified official Windows `nats-server.exe`. Keep client
port 4222 and monitoring port 8222 on loopback, use the native storage path above,
and adapt the guarded supervisor or Windows Service Control Manager lifecycle.
Preserve the existing stream subjects, message IDs, acknowledgment semantics and
health gates. Process ownership checks must use executable/config identity, not
an unverified PID file.

At cutover, stop the outbox dispatcher, take a final native JetStream snapshot,
stop the container, restore into the native server and verify stream sequences,
messages/checksums and consumer state before resuming delivery. Native snapshot
and restore remain the backup mechanism; do not copy an active data directory.
Any machine-wide service installation step is separate from preparing/testing the
scripts and must use the permissions actually available on this machine.

Start with the existing 5 GiB file-store ceiling. Set a bounded replay window only
after verifying that the PostgreSQL outbox/audit is authoritative for historical
events and no consumer needs older messages. An initial 7-day/2 GiB stream policy
is a candidate, not permission to silently discard unconsumed execution evidence.
Test lost acknowledgments, reconnects, deduplication, full-store backpressure and
restart recovery. Native deployment does not itself fix unbounded event retention.

### LEAN

The existing default still executes the pinned LEAN Docker image; removing only
ClickHouse/NATS containers would not meet the operator's requirement. Use the
existing native Python frozen-bundle runner for routine app calculation only after
matched input/output comparison with retained completed runs. Reports must identify
the engine honestly; Python replay is not new independent LEAN parity evidence.

Provide a pinned native Windows LEAN build for independent validation, including
its .NET/Python runtime, source commit and dependency manifest. Run the existing
shared-strategy/target, fill, fee, cash, holdings and NAV scenarios without widening
tolerances. Keep promotion requiring independent validated evidence; if native
LEAN cannot pass, promotion remains blocked rather than substituting Python for
both sides of the same check. Investigate the native engine build early so it
cannot become a surprise at final Docker retirement.

Replace container isolation with a restricted Windows worker identity/permissions,
an allowlisted environment, read-only input/source access, a dedicated writable
output/scratch root, denied broker/network access and Job Object limits. Hiding a
console window or omitting credentials from the environment is not equivalent to
the current container restrictions. Do not remove the LEAN image before accepted
native validation and a recoverable engine provenance record exist.

## Implementation sequence and acceptance

| Stage | Deliverable | Completion check |
| --- | --- | --- |
| 1 | Retention registry, compact archived summaries, protected-root inventory and deletion CLI | Dry-run/apply/recheck tests; stale revisions, links, active jobs and paper pins block deletion; retired reports render honestly |
| 2 | Diagnostic cleanup and selected archived artifact retirement | Receipts and measured free-space change; seven monitored reports and control revision unchanged; no recreation loop |
| 3 | PostgreSQL manifest schema and native Parquet/DuckDB adapters | Storage contract tests, interrupted publication/concurrent writer tests, tamper rejection, bounded memory and row/hash parity |
| 4 | Native NATS supervisor and snapshot migration; native LEAN proof | Restart/outbox/replay recovery; native engine passes declared economics and isolation checks |
| 5 | Bounded analytical export and dual-reader comparison | Retained sources only; equal logical row identities/hashes, API/report values, held/target weights, benchmark and decision outputs |
| 6 | Coordinated native cutover, backups and recovery | Stop writers, copy final delta, switch backend, reconcile broker, refresh strategies, restore prior approved paper policy after gates; restore drill passes |
| 7 | Project Docker/WSL retirement and final cleanup | Cold start, calculation, recorder, backup and recovery with Docker stopped; no launcher attempts Docker/WSL; remove only project-owned containers/volumes/image when permitted |

The migration export is scoped by the retention manifest, not by copying the
entire 131 GiB of active ClickHouse parts. Preserve all required operational and
current research data. Do not fetch fresh provider prices to replace retained
published inputs. Export in restartable bounded chunks and validate every retained
dataset; a partial or unverified export is not a cutover candidate.

During final cutover, preserve the exact paper-control policy/cap and pending work,
pause routing through the existing guarded procedure, stop writers, export the
final delta and verify the replacement. Start native services, validate health,
reconciliation, publication freshness and matching results, then restore the same
approved paper policy. Do not enable live execution, change capital allocation or
submit a test broker order as a migration check.

Keep the old stores stopped through a finite acceptance window: one successful
recording/calculation cycle, restart/recovery checks and a verified backup/restore
of the retained native state. Resume from a recorded migration watermark if the
native side accepted new writes; an old container is not an automatically current
rollback database. Keep failed cutovers fail-closed until those writes are replayed
or reconciled. Then retire old volumes and the project LEAN image. Do not uninstall
Docker/WSL globally or delete unrelated distributions/projects under this plan.

Backups must capture a consistent PostgreSQL manifest set plus every referenced
immutable fragment/document and native NATS snapshot. Exclude retired outputs,
regenerable cache and staging. Old restic snapshots are a separate retention task;
deleting local artifacts does not reclaim historical deduplicated backup blocks.
Space freed inside Docker's filesystem may not return to the Windows host until
the project data are retired and the disk image is compacted through supported tools.

## Code boundaries

- Storage: `market_data/analytics_store.py`, `market_data/governance_store.py`,
  `market_data/golden.py`, `storage/factory.py`, new typed contracts and PostgreSQL
  migrations. Audit `FINAL`/`argMax`/`JSONExtract` callers in web/execution/scripts.
- Calculation: `research/tracked_runtime.py`, `research/compute.py`,
  `research/governed_inputs.py`, `lean/runner.py`, registry/retirement integration.
  Respect the running calculation source-revision guard and restart normally.
- Lifecycle/UI: `research/strategy_lifecycle.py`, strategy catalog/report routes;
  distinguish archived summary from available full replay artifacts.
- Operations: `start_local_platform.ps1`, NATS launchers, operator/recorder launchers,
  `local_recovery.py`, health dependencies, runtime config and `.env.example`.
- Backup: `storage/system_backup.py`, `storage/nas_sync.py`,
  `scripts/sync_databases.py`, backup configuration, restore mapping and dependency
  inventories. Remove container-copy assumptions.
- Verification: storage/publication, lifecycle, outbox, recovery, backup/restore,
  calculation parity, memory-pressure and fail-closed broker contract tests.

## Evidence and references

Local measurements: [storage review](repository-maintenance.md#storage-and-memory-review--october-17-2026).
The exact archived entries and protection snapshot are recorded in
`var/maintenance/retention-plan-20261017.json` and
`var/maintenance/retention-live-catalog-20261017.json`.

Technical references: [ClickHouse Windows support](https://clickhouse.com/docs/get-started/setup/self-managed/clickhousectl),
[DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency),
[DuckDB memory and spill behavior](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads),
[NATS Windows installation](https://docs.nats.io/concepts/getting-started/),
[LEAN source](https://github.com/QuantConnect/Lean).
