# Two-PC database handoff through the NAS

The standard local platform launchers use `config/database-sync.json` and
`\\192.168.1.32\Public\systematic-trading`. PostgreSQL and the configured SQLite
files stay on local disks. The NAS holds immutable snapshots, checksums, the
current snapshot pointer and a persistent owner record. Only one workspace may
own the handoff. This is sequential PC switching, not multi-master replication.

## First use and switching PCs

### Prepared handoff: 2026-09-25

The WD My Cloud holds a verified PostgreSQL/SQLite snapshot at
`\\192.168.1.32\Public\systematic-trading\snapshots\218c1db999494848abcfaf47944e5a35`.
The current `latest.json` points to it, and ownership was released for the next
PC. A disposable PostgreSQL restore matched all 14 source tables by row counts
and normalized content hashes; SQLite's 12 tables passed integrity and logical
content checks. The verification report is at
`\\192.168.1.32\Public\systematic-trading\verification\218c1db999494848abcfaf47944e5a35.json`.
Use `latest.json` rather than hard-coding this historical snapshot for subsequent
handoffs. The old PC's application services remain stopped.

On the new Windows PC, pull this code and create a local environment if needed:

```powershell
git pull --ff-only
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ib,queue]" tzdata
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Provision PostgreSQL and its roles as described below, configure local `.env`
credentials, install/start Docker Desktop, and configure paper TWS/IB Gateway.
Then run `scripts/start_local_platform.ps1`. The snapshot restores automatically
into an empty local PostgreSQL database and the configured SQLite path. This
backup does not include ClickHouse: follow the separate market-data migration
notes below before expecting complete charts or paper-execution readiness.

1. On the existing PC, stop the platform with `scripts/stop_local_platform.ps1
   -KeepInfrastructure`, then start with `scripts/start_local_platform.ps1`.
   Close other database clients and research scripts first. The first start
   publishes the existing local databases when the NAS has no history.
2. Before switching PCs, run `scripts/stop_local_platform.ps1 -KeepInfrastructure`
   and wait for success. This stops application writers and the backup worker,
   publishes a final verified snapshot, and releases NAS ownership.
3. On the other PC, clone the same code revision, install the Python dependencies
   and local infrastructure, configure its local `.env`, then run
   `scripts/start_local_platform.ps1`. A new empty database receives the latest
   snapshot before application services start. A previously used workspace is
   updated only if its databases still match its last clean handoff.

Do not copy `var/database-sync` or `var/run` between PCs. They contain local
identity, checkpoints and process state. Credentials and `.env` are never copied
to the NAS. Both PCs must use the same database name and SQLite path list. Add
additional SQLite files explicitly to `sqlite_paths`; files are not discovered
from arbitrary directories. The configured `ST_DATABASE_PATH` must be included.

### PostgreSQL provisioning on a new PC

Install a compatible PostgreSQL server and clients (the same major version as
the source is recommended). Create an **empty dedicated** `systematic_trading`
database owned by `st_owner`; create the project roles `st_app`, `st_migrator`
and `st_readonly`, with `st_migrator` allowed to `SET ROLE st_owner`. Configure
their local passwords securely. Set `ST_POSTGRES_MIGRATOR_PASSWORD` and
`ST_POSTGRES_APP_PASSWORD` in the local `.env` (legacy password aliases also work).
The sync uses the migrator with the owner role for dump/restore. Database roles,
passwords and PostgreSQL server installation are not part of a database dump.
Do not initialize application tables on the new PC before the first restore.

`pg_dump`/`psql` are discovered on PATH or under `C:/Program Files/PostgreSQL`;
set `postgres_bin` in the sync config for another install location. PostgreSQL
must be local. Its database name is part of the snapshot layout contract.
Restores replace **all user schemas** in this dedicated database, including
objects deleted on the other PC, in one transaction. Restore errors roll back
that transaction. Existing unmanaged databases are refused before any restore.

## Backups and operational behavior

- A background worker snapshots every 300 seconds. Configure `interval_seconds`
  to change the interval (minimum 30 seconds).
- SQLite uses its online backup API, including committed WAL contents, followed
  by an integrity check. PostgreSQL uses a consistent logical `pg_dump`.
- Each snapshot is copied from local staging, read back and checked with SHA-256.
  `latest.json` advances only after all files and the manifest are complete.
- Online PostgreSQL and SQLite backups are individually consistent; they are not
  one distributed transaction. The final stopped-service snapshot is the handoff.
- Existing data is snapshotted under `var/database-sync/before-restore-*` before
  replacement. An interrupted multi-database restore stays blocked for recovery.
- Snapshots are retained without automatic deletion. Plan NAS capacity for full
  snapshots at the selected interval; archive/prune older generations deliberately,
  keeping `latest.json`'s target and any generation needed for recovery.
- NAS unavailability blocks startup and clean handoff. During an active session,
  failed periodic backups record an error and retry on the next interval. Local
  services continue and ownership remains reserved; the other PC cannot take over.
- Ownership never expires automatically. A crashed/disconnected PC cannot cause
  a second PC to silently start from an old snapshot.

Inspect status and the backup worker's last result:

```powershell
.\.venv\Scripts\python.exe scripts/sync_databases.py status
Get-Content var/run/database_sync.state.json
```

The worker logs are in `var/log/database_sync.*.log`. Use the standard platform
start/stop scripts for handoffs. The standalone dashboard launcher verifies NAS
ownership and the worker; direct Python/research commands are not a distributed
lock enforcement boundary. Never run writers on the inactive PC. Stop/restart
through the platform scripts after changing the sync configuration.

For a deliberately independent installation, set `enabled` to `false` in the
sync config **only after a clean handoff**. Disabling it bypasses NAS coordination
and does not make concurrent trading safe. Paper/live gates are unchanged.

## Conflicts and crash recovery

A changed local database, another owner, changed NAS history, corrupt snapshot,
layout mismatch or interrupted restore blocks automatic replacement. Keep both
copies and inspect them; there is no last-write-wins or row merge for approvals,
orders or audit records. Logical fingerprints can conservatively flag differences
after a PostgreSQL version change or physical row reordering.

If the owner PC restarts after an ordinary crash, stop any remaining local
services and backup worker, then use the normal startup. It resumes its local
active databases without restoring over newer changes. A stale `operation.lock`
requires operator review: verify no sync process is running on either PC before
removing that empty lock directory. Never delete `owner.json` just because a PC
is unreachable. Recover the owner and complete a clean stop whenever possible.

If a restore was interrupted (`phase: restoring`) or the NAS head advanced but
the local checkpoint could not be saved, startup remains blocked. Preserve the
NAS snapshot and local `before-restore-*` copies and reconcile the checkpoints
with the actual database contents before resetting state. Cross-database rollback
and forced takeover are intentionally not automatic.

## What still needs separate migration

This feature covers PostgreSQL and the listed SQLite databases. ClickHouse,
NATS streams, raw recorder files, untracked research artifacts and local broker
configuration are not included. Git transfers tracked strategy configuration;
TWS/IB Gateway and credentials must be configured on each PC.

ClickHouse can be seeded from the restored SQLite data using the existing
`scripts/sync_sqlite_daily_bars_to_clickhouse.py` and
`scripts/sync_sqlite_fx_rates_to_clickhouse.py` commands after starting ClickHouse.
Provider backfill can repair newer daily bars. This does not reproduce data found
only in the original ClickHouse instance, its full provenance, or raw intraday
history; preserve those separately before decommissioning a PC. The recorder's
normal startup backfill is not a complete ClickHouse migration. Fresh broker
reconciliation and current market data remain required for paper execution.

Implementation references: [PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
and [SQLite online backup API](https://www.sqlite.org/backup.html).
