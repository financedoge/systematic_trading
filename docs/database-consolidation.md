# Database consolidation and D: storage

Scope: 2026-09-25. PostgreSQL for operational state; ClickHouse for market data,
as explicitly selected by the operator. SQLite is retired from default application,
research, multiprocessing worker and reporting paths. Explicit SQLite backends
remain for deterministic offline tests and legacy recovery.

## Inventory and migration evidence

| Store | Location / disposition |
| --- | --- |
| Legacy SQLite | `D:/projects/systematic_trading/var/systematic_trading.db`, 42,094,592 bytes; retained rollback artifact. |
| PostgreSQL 18 | Windows service `postgresql-x64-18` still uses `C:/Program Files/PostgreSQL/18/data`; relocation awaits administrator access. |
| ClickHouse and NATS volumes | Docker Desktop WSL disk moved through the supported Resources / Advanced UI to `D:/systematic_trading_data/docker/DockerDesktopWSL/disk/docker_data.vhdx`. |
| Docker distro disk | `D:/systematic_trading_data/docker/DockerDesktopWSL/main/ext4.vhdx`. |
| Raw recorder / ClickHouse logs | Existing D: storage remains selected. |

The source SQLite has 12 tables including its internal sequence table, and
145,836 rows. `scripts/archive_sqlite_to_postgres.py` preserved all rows and
schema metadata in `legacy.sqlite_snapshots` / `legacy.sqlite_rows`, including
exact JSON text, numeric SQL values, nulls, blobs, empty tables and sequence state.
The archive uses a consistent SQLite read transaction, integrity validation,
content-derived identity and a single PostgreSQL transaction. Retry verifies the
existing archive rather than overwriting it. Every archived row was read back and
compared. Snapshot ID:
`a7235fb109d493339812617b3d9895929fc053258b61ec3af28433716506f7c7`.

The operational ledger already held all 39 legacy instruments, 38 proposals,
7 approval payloads, 16 broker order identities and 37 P&L snapshot identities.
It has newer approvals/orders/fills and must not be replaced with the old SQLite
payloads. Legacy recorder events absent from the active outbox are preserved in
the archive without republishing historical events. Empty legacy thesis,
fundamental and baseline tables require no operational import. Archive evidence
is intentionally separate from executable operational state.

ClickHouse key coverage verified all 140,686 legacy price bars and 3,790 FX rates,
with no missing symbol/date or currency-pair/date keys. It also contains newer
records. Coverage is not a claim of equal values: corrections and source-priority
selection can change current golden values. The PostgreSQL archive retains the
exact source versions for historical inspection; neither archival preservation nor
current key coverage certifies point-in-time research provenance.

Evidence: `var/migration/sqlite-archive-verification.json`,
`var/migration/sqlite-active-coverage.json`, and
`var/migration/sqlite-clickhouse-coverage.json`. PostgreSQL archive migration is
`deploy/postgres/migrations/002_legacy_sqlite_archive.sql`. The standard NAS final
snapshot includes this schema. The old bootstrap script now refuses nonempty
operational targets to prevent stale approval/order replay.

## Runtime changes

`AppSettings` and `.env.example` default to PostgreSQL/ClickHouse. Research and
backfill scripts, including subprocess workers, use the storage factory. Report
benchmark data comes from configured market data, even if no SQLite file exists.
Passing a different `--database` file cannot silently redirect PostgreSQL.
For an explicitly isolated legacy experiment, set both backend environment
variables to `sqlite` and use a separate database path.

Legacy Yahoo/Tushare download commands require `--skip-fx` against server stores;
their CNY proxy must not be relabelled as observed CNH. Stock replacement research
requires `--skip-fetch` with the shared golden store. Trend comparison no longer
implicitly downloads unadjusted benchmark data into ClickHouse. The first-backtest
example consumes golden data rather than seeding unadjusted prices and proxy FX.

Do not delete the original SQLite file or remove it from the existing NAS layout
unilaterally. It is a retained recovery artifact, not an active application store.
The two-PC backup protocol still transports it for layout compatibility. Removing
it from NAS snapshots is a separate coordinated layout-version transition on both
PCs; all current guards remain enabled.

## Storage relocation and rollback

Docker volume backups were created with application writers stopped and containers
stopped, as tar archives so Linux symlinks survive without Windows symlink privileges.
They are under `D:/systematic_trading_data/backups/20260925-pre-docker-move/`.
The manifest records SHA-256, bytes and readable tar entry counts. A failed initial
Windows directory extraction was superseded by the complete tar archives; use
the `.tar` files and manifest for recovery. Never reset Docker or remove volumes.
[Docker's WSL storage setting](https://docs.docker.com/desktop/features/wsl/).

The current Codex process is a non-elevated Windows token. Its read-only service
access check for change/start/stop returned Windows error 5 (Access denied), so
PostgreSQL's physical relocation has **not** run. A bounded relocation script is
ready for an administrator:

```powershell
cd D:\projects\systematic_trading
.\scripts\move_postgres_data_to_d.ps1
```

Run that command in an elevated PowerShell. It checks the exact service/source
mapping, D: target scope/free space, external path overrides, reparse points and
clean NAS handoff. It stops the PostgreSQL service, copies without deleting the
source, preserves ACLs, hashes every copied file, changes the service directory,
checks the new server PID/data path and restarts through the standard platform
launcher. Target: `D:/systematic_trading_data/postgresql/18/data`. Evidence is
written to `var/migration/postgres-relocation.json`. The script has been parsed
but not executed under administrator access on this PC.

Before application restart, a service/copy failure restores the old service path.
After new operational writes, the retained C: copy is stale and cannot be selected
as an automatic rollback. Stop writers, preserve current D: state and reconcile
before recovery. PostgreSQL binaries may stay on C:; only durable data must move.
[PostgreSQL file-location semantics](https://www.postgresql.org/docs/18/runtime-config-file-locations.html).

The LEAN work sequence is in [the backtest integration plan](lean-backtest-integration-plan.md).


### Administrator-shell NAS access (2026-09-25 follow-up)

A relocation attempt stopped application services but failed its final NAS backup.
PostgreSQL remained running on C:; no data copy or service retarget occurred.
The normal session could read the matching NAS head/owner. An elevated SMB-session
access difference is suspected, not proven; a transient NAS outage is also possible.
The platform was restored through the standard launcher and all services/reconciliation
verified healthy. The relocation script now runs `sync_databases.py preflight`
in its own elevated process before stopping anything. This checks share access,
lock creation and matching ownership/history/layout, without changing handoff state.
A later network failure can still block the final backup, as intended.

In the same Administrator PowerShell used for relocation, connect to the NAS:

```powershell
net use \\192.168.1.32\Public /persistent:no
.\.venv\Scripts\python.exe .\scripts\sync_databases.py preflight
```

If authentication is needed, use your NAS account in that shell (`net use` supports
`/user:YOUR_NAS_USERNAME *` to prompt for the password). Once preflight succeeds,
rerun `scripts/move_postgres_data_to_d.ps1`. Do not disable NAS coordination, remove
ownership records or change Windows security policy to work around this failure.
[Microsoft's elevated-session network-drive guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/mapped-drives-not-available-from-elevated-command).


### Windows PowerShell service-command repair (2026-09-26)

The first copy completed but `sc.exe config` rejected the quoted binary/data path
under Windows PowerShell. The service remained on C:. The script now uses
structured `Win32_Service.Change` arguments, checks its return code and reads
back the full command. Rollback uses the same API and is armed before mutation.
[Microsoft service Change API](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/change-method-in-class-win32-service).

The stopped D: copy was verified as the same PostgreSQL cluster and preserved as
`D:/systematic_trading_data/postgresql/18/data.failed-sc-20260926`. The target
`data` directory is absent and the platform was restored on C:, so the same
relocation command can perform a fresh final backup/copy on retry. The helper's
quote/error/rollback tests pass under both Windows PowerShell 5.1 and PowerShell 7;
actual elevated relocation remains to be verified. Do not reuse the failed copy
as current state after the C: service resumes writes.
