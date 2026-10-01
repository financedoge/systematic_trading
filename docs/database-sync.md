# Optional NAS backups and PC handoff

The platform runs on local PostgreSQL, ClickHouse and local files. NAS access is
optional. Standard start/stop scripts work away from home; the dashboard launcher
checks local restore safety without contacting NAS or requiring a backup worker.

`config/database-sync.json` selects `optional: true` and
`conflict_policy: latest_snapshot`. The destination remains
`\\192.168.1.32\Public\systematic-trading`. Set `enabled: false` to disable backups.
Old configurations without `optional` retain strict single-owner behavior; update
both PCs to the same policy/code.

## Daily operation

```powershell
.\scripts\start_local_platform.ps1
.\scripts\stop_local_platform.ps1 -KeepInfrastructure
```

Preparation, five-minute backups and shutdown first create a local checkpoint.
When NAS is unavailable, services continue and the next backup retries. UNC paths
receive a two-second SMB TCP connection probe before filesystem access. A backup
worker startup failure is a warning in optional mode.

Two recent checkpoints remain under `var/database-sync/checkpoints`. Explicit
`before-restore-*` rollback copies and immutable NAS generations are retained
separately. Inspect `var/run/database_sync.state.json` and worker logs. `local_only`
means NAS has not confirmed the local state; its checkpoint/error fields distinguish
successful local checkpoints from local backup failures. The original local
database remains available in either case.

```powershell
.\.venv\Scripts\python.exe scripts/sync_databases.py status
Get-Content var/run/database_sync.state.json
```

## Latest revision wins

The newer complete database generation wins as requested by the operator. Revision
time is the UTC time when the snapshot process observes a changed logical database
fingerprint. Unchanged backups retain that time; copying an old PC does not make
unchanged data newer. Equal times are ordered by node ID. Keep PC clocks synchronized.
These are observed snapshot revisions, not per-row transaction timestamps.

An empty new workspace receives the verified NAS generation. Newer local changes
publish on reconnect. Newer remote changes restore during startup while local
services are stopped. A running worker never replaces an active database: it
records `newer_remote_pending_restart`. Local changes observed subsequently receive
a new revision under the same policy.

There is no row-level merge. The losing local generation is retained before
replacement; previous NAS generations remain available. The cross-PC
`operation.lock` serializes comparison/publication and a local OS file lock
serializes checkpoint writers. Busy/stale NAS locks defer sync without preventing
local operation. Latest-generation selection does not make simultaneous trading
on disconnected PCs safe: operate one trading PC at a time and retain normal
broker reconciliation and approval checks.

Do not copy `var/database-sync` or `var/run` between PCs: these hold local identity,
checkpoints and process state. Credentials and `.env` never go to NAS. Both PCs
must use the same database name and SQLite path list. `ST_DATABASE_PATH` must
remain included in `sqlite_paths`.

## Verification and recovery

SQLite uses its online backup API, including committed WAL data, plus integrity
checks. PostgreSQL uses a consistent logical `pg_dump`. These are individually
consistent; final checkpoints run after application writers stop. SHA-256 readback
precedes atomic publication of `latest.json`. Snapshot IDs, layout, allowed files
and analytical prerequisites are verified before restore. Failed verification
defers sync and preserves local data.

PostgreSQL restore replaces all user schemas in the dedicated database inside
one transaction. Interrupted multi-database restore remains a hard local integrity
block (`phase: restoring`). Preserve rollback copies and recover local databases
before starting services; never bypass it by deleting checkpoint state.

NAS generations are not automatically pruned. Plan capacity for full snapshots.
A stale NAS `operation.lock` may be removed only after verifying neither PC is
synchronizing; removal is unnecessary for offline operation. Legacy `owner.json`
is not an authority gate under the optional latest policy.

## New PC prerequisites

Install compatible PostgreSQL server/client tools and a dedicated
`systematic_trading` database with roles `st_owner`, `st_app`, `st_migrator` and
`st_readonly`. Configure local passwords and allow the migrator to assume the owner
role. Roles/passwords are not in SQL dumps. `pg_dump`/`psql` are discovered on PATH
or under `C:/Program Files/PostgreSQL`; `postgres_bin` can select another location.
Install Docker and paper Gateway separately.

SQL snapshots do not contain ClickHouse or immutable model/market-data artifacts.
Manifests retain hashes of governed roots, model/FX inputs, tracked outputs and
ClickHouse publications. Restore these dependencies separately at the recorded
paths before incoming SQL restore can succeed. Missing prerequisites defer that
restore; they neither replace local data nor establish trading readiness. See
[analytical migration](analytics-migration.md) and
[database consolidation](database-consolidation.md).

The administrator-only PostgreSQL directory move uses the same local restore
safety check and clean shutdown. NAS availability is no longer a prerequisite;
its stopped-server, copy-hash and rollback checks remain mandatory.
