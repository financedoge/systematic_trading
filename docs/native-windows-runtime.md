# Native Windows runtime

The selected runtime uses Windows PostgreSQL, immutable compressed Parquet queried
by DuckDB, native NATS, and an independently validated native LEAN worker. The
application remains paper-first and live routing remains disabled. Migration and
retirement receipts are under `var/maintenance/windows-cutover/`; consult the
execution Kanban for the current cutover/acceptance state.

The October 18 cutover and operator follow-up passed: all seven monitored reports
serve the accepted native calculation, paper broker reconciliation is matched and
the existing operator-enabled paper policy retains its prior cap and binding.
Project Docker resources are retired, Docker auto-start is absent, and measured
host compaction reduced its remaining VHDX to 2.72 GiB (246.15 GiB reclaimed by the
compaction command). Two disposable restore-test directories remain because
automatic approval review blocked their deletion; see the execution Kanban.

## Start and stop

```powershell
.\scripts\start_local_platform.ps1
.\scripts\stop_local_platform.ps1
```

The defaults are `ST_TRANSACTIONAL_STORE_BACKEND=postgres`,
`ST_MARKET_DATA_STORE_BACKEND=parquet`, and `ST_LEAN_RUNTIME_BACKEND=native`.
NATS starts as a hidden native process. PostgreSQL remains an external Windows
service. DuckDB has no separate server or service to start. The supervisor records
the selected profile for restart recovery. Docker/WSL are unnecessary for this
profile. The legacy ClickHouse launchers require explicit backend selection and
exist for migration/rollback inspection.

Startup treats the configured PostgreSQL Windows service as a managed
dependency. `scripts/start_local_platform.ps1` starts a stopped service; when the
current shell is not elevated it asks Windows for administrator permission once
through the standard UAC prompt rather than failing with access denied. If the
authenticated read probe fails, startup restarts the service once and re-probes
before it stays blocked. The service is `postgresql-x64-18` by default; override
it with `-PostgresServiceName` or `ST_POSTGRES_SERVICE_NAME`. Use
`-SkipPostgresServiceControl` to leave the service untouched, `-NoElevation` to
refuse the prompt instead of asking, and `-NoPostgresRestart` to stop after the
first failed probe. `scripts/watch_local_platform.ps1 -Repair` applies the same
bounded repair to its required PostgreSQL check. The helper is callable directly:
`postgres_service.ps1 -Action Ensure|Start|Restart|Status`.

The paper Gateway API is configured at `127.0.0.1:4002`. Log in through IB Gateway;
the app cannot perform its login/2FA. Restore prior paper approval only after a
fresh successful reconciliation through the existing guarded API. A storage
migration grants no order, promotion or live-trading authority.

## Storage and memory

### PostgreSQL read failures

Startup runs `scripts/probe_postgres_readiness.py` with the configured application
credentials before database preparation or research retention. It reads the
retention catalog view and bounded samples from transactional/publication tables
in a read-only session, with connection, statement, lock and transaction timeouts.
This is a readiness check, not a complete database integrity scan.
[`pg_isready`](https://www.postgresql.org/docs/18/app-pg-isready.html) checks
connection status; a successful TCP check or `SELECT 1` does not establish that
the application can read its stored relations.

On October 30, catalog `pg_class` (`base/16393/1259`) and native
`publication_heads` (`base/16393/34803`) returned `Invalid argument` after a
Windows sleep/resume. Both reads succeeded after the operator restarted the
PostgreSQL Windows service. The underlying cause is unconfirmed; this observation
does not prove or rule out persistent storage damage.

For the same error, keep application writers stopped. Startup now performs that
bounded restart itself: when the authenticated read probe fails it requests
administrator permission (UAC) if needed, restarts the configured service once,
and re-probes until `-PostgresRestartTimeoutSeconds` (default 60) expires. If the
restart is declined or the reads still fail, startup stays blocked with the
guidance below; it does not delete relation files, reset WAL, disable retention,
or overwrite the database. The manual equivalent, from Administrator PowerShell:

```powershell
Restart-Service -Name postgresql-x64-18
.\.venv\Scripts\python.exe .\scripts\probe_postgres_readiness.py
```

If the probe passes, retry `start_local_platform.ps1`; its normal backup and
retention checks still apply. If reads still fail, leave startup blocked and
inspect PostgreSQL/Windows storage logs and the verified recovery evidence before
any repair or restore. Do not delete relation files, reset WAL, disable retention
protection, or overwrite the production database to get past this error.

### Service PID files and recycled process IDs

Windows recycles process IDs. After an unclean stop a PID file can name an
unrelated program: on 2026-11-06 `var/run/market_data_recorder.pid` held PID 8052,
which by then was a PostgreSQL backend. Liveness-only checks made startup refuse
database preparation ("Stop local services first") and made the recorder stop
script try to stop PostgreSQL itself (access denied).

The launchers now prove process identity before acting. `service_process.ps1`'s
`Get-ServiceProcessState` checks the process name and, when readable, the command
line; the recorder start/stop scripts and the watchdog remove a proven-stale PID
file without touching the other process, and refuse to stop an unverified PID.
The Python guards (`services/health.py` `_pid_matches_platform_python`) apply the
same check to `sync_databases.py` prepare/release/guard/worker lifecycle, database
sync `stop-worker`, and local recovery, so a recycled PID can no longer block a
handoff or hide a dead service. Unknown identity (unreadable image name) stays
conservative and is still treated as running. Startup also resumes recorder
recovery after a normal platform start.

### Locations and limits

| Component | Location or limit |
| --- | --- |
| PostgreSQL 18.4 | Service `postgresql-x64-18`; `D:/systematic_trading_data/postgresql/18/data` |
| Analytical files | `D:/systematic_trading_data/analytics/parquet` |
| Analytical metadata | PostgreSQL `native_analytics` schema: immutable manifests/publications and mutable current pointers |
| Native NATS | `var/dependencies/nats/nats-server.exe`; loopback 4222/8222 |
| JetStream | `D:/systematic_trading_data/nats/jetstream`; 256 MiB memory store, 5 GiB file store |
| LEAN/.NET/Python | Pinned roots and checksums in `config/native-runtime.json` |
| Independent calculations | One isolated Job at a time; no default process/Job memory quota, Windows manages RAM and paging; host CPU budget available |
| Worker admission | No fixed free-RAM threshold; available RAM and estimated input copies guide parallel worker count, with at least one worker |
| DuckDB | In-memory connection per query, 1 GB engine memory, two threads, two concurrent queries, 10 GB temporary spill limit per query |

DuckDB's engine budget does not bound Python objects returned to the application.
Analytics currently run in the API/analytics process, with typed queries and
bounded fragments; a separate 3 GiB analytical process from the original plan is
not implemented. Do not describe the whole API as capped at 3 GiB. LEAN and native
model preparation/training have enforced process-tree limits. Windows model fits
and independent USD decisions/accounting replays use file IPC to parallelize
without granting global named-pipe access. Numerical libraries remain single
threaded per estimator. The input-size-aware pool uses current available RAM to
choose fan-out, without a fixed aggregate memory ceiling or 10 GiB admission
gate. Environment, network, input and process-tree restrictions are inherited;
explicit memory quotas remain available for intentionally bounded tests/recovery.
All native worker callers share a Windows mutex for the full isolated run,
including ACL grant and cleanup. This prevents concurrent inherited-ACL updates
from removing another worker's runtime access. Separate AppContainers remain
serialized; parallel children within a Job need no ACL changes. See
[calculation resources](app-calculation-resources.md) for the CPU/memory planner.

Parquet writes use compressed bounded row groups, independent readback, SHA-256
verification and atomic content-addressed file installation before the PostgreSQL
commit exposes them. Queries read the selected immutable manifests. Historical
versions remain pinned; a query cannot silently substitute a newer source.

## Research retention

The October 31 operator decision removed the initial 40 GiB cumulative admission
quota. `config/storage-retention.json` keeps 20 GiB as a housekeeping trigger,
not a calculation limit. Admission requires 2 GiB of actual free disk space on
the artifact drive for new work, regardless of retained research size. Receipts
record both unique artifact contents and actual free disk. Hard links count once;
canonical histories and broker evidence are excluded from exploratory cleanup.

A successful calculation queues a maintenance marker. The next stopped startup
runs `maintain_research_storage.ps1`, retiring unreferenced superseded calculations,
model caches and eligible explicitly closed study output folders through the same
guarded manifest/receipt path. Crossing the housekeeping threshold also queues
this maintenance without blocking calculations. It preserves the
latest two complete calculations, monitored/pending/operational references, current
model/FX pins and active research. New/unclassified studies' protocol, manifest,
provenance and recipe files protect their dependencies automatically. Completed
exploratory studies require explicit classification, compact findings, a retained
recipe and an immutable retirement receipt. Housekeeping runs with writers stopped;
it does not restart the app or delete concurrently with a calculation.

Deleting an output retires its exact replay; it does not delete the historical
finding or turn a later rerun into the same evidence. Research tests that require
retired files skip only when a matching retirement receipt exists. Compact-report,
strategy-rule, execution and safety tests still run.

## Backup and recovery

The SQL dump and analytical dependency inventory share one exported PostgreSQL
snapshot. Full backups include exactly the committed Parquet fragments from that
view, retained research/operational files, native engine provenance and a native
JetStream snapshot. Restore checks every pinned file and manifest, then checks
publication heads after loading SQL. It must not require old publication heads to
already exist in an empty destination database.

```powershell
.\.venv\Scripts\python.exe scripts/system_backup.py status
.\.venv\Scripts\python.exe scripts/system_backup.py start
.\.venv\Scripts\python.exe scripts/system_backup.py stop
```

Explicit pause persists across platform restarts. NAS availability never gates
local operation. A completed upload/readback is distinct from an isolated restore
drill or a full repository scrub. Do not restore onto running production stores.
`verify_native_restore.py` creates a new local directory and disposable native
PostgreSQL/NATS processes, copies and verifies Parquet files, restores SQL and queue
state, verifies table counts/publications/control, then stops both test services.
Its `acceptance.json` is written only after those checks pass.
After the database phase succeeds, its capture hashes and verification results are
saved separately. `--resume-queue` retries a queue restore only against that exact
capture. Raw server fields include the subject count even when the Python client's
typed response omits it. A pending capture from another analytics backend is rejected;
retire its compact pending record and create a fresh capture after a backend change.
Incremental backups explicitly use the last verified snapshot as their parent even
when new Parquet publications change the source list. Completed snapshot identities
are resolved from the candidate's preserved original ID after tagging, never from
the first result of restic's per-path-group `--latest` listing.

## Migration evidence and limitations

The retained export selects 50,206 publications and 10,065 governed batch/symbol
pairs. `native-analytics-verification.json` records verified file hashes and exact
strategy API/stored report comparisons for all seven monitored strategies. Native
LEAN acceptance records economic parity against independent Python and retained
results; the additional native model drill matched two retained fit dates.

These checks preserve existing research limitations. Migration does not create
missing audited observations, certify point-in-time availability of historical
vintages, or permit freshness/reconciliation checks to be bypassed. A stale strategy
must remain visibly stale until the app acquires, audits, publishes and calculates
new evidence normally.

Project Docker volumes and the legacy image may be retired only after native
startup, calculation/recording, backup and recovery acceptance. Unrelated Docker
projects and WSL installations are outside this migration. Free space reclaimed
inside Docker's filesystem is not necessarily reclaimed from its Windows VHDX;
host compaction is a separate verified maintenance operation.
The one-time `retire_legacy_docker.ps1` script validates the exact project container,
volumes and image identities, plus native restore/cold-start/backup/calculation
receipts, before removal. It does not run a global prune. After Docker shutdown,
`compact_retired_docker_disk.ps1` requires Administrator PowerShell and verifies
exclusive access to the recorded disk. It reports actual size reduction instead
of assuming deletion shrinks the host file. See Microsoft's
[VHD compaction requirements](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk).
