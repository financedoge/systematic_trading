# Application recovery backups

The platform uses PostgreSQL for relational/operational state and ClickHouse for
time series and analytical publications. SQLite is an explicit offline test and
legacy inspection backend, not a production service. All 145,836 legacy rows
were reverified in the PostgreSQL archive on October 7, 2026. The original SQLite
file is retained as evidence and included in file backups.

## Coverage and consistency

`config/system-backup.json` configures an application-owned worker, supervised
through the existing database backup worker. It captures:

- A native PostgreSQL custom dump of all schemas, including approvals, orders,
  reconciliation, registry, outbox and the legacy archive. Frequent SQL handoff
  checkpoints continue separately with gzip compression and no active SQLite.
- Native backups of every non-system ClickHouse database, including all retained
  `market_data` and `analytics` versions, table definitions and views. System
  diagnostic logs are excluded. No running database volume is copied.
- Native NATS JetStream snapshots of all streams, configurations and consumer
  positions, with message checksum checking.
- Project source/configuration/docs/tests/research and durable `var` state:
  models, strategies, broker/account evidence, reconciliation, governance,
  benchmarks, audit records and reports, including uncommitted source files.
  Explicit pre-restore rollback copies are preserved; routine checkpoint copies,
  transfer scratch space and PC-specific sync identity are excluded.
- External D: research/provider archives, governed histories, LEAN inputs/results,
  the configured raw hot spool and any existing local archive. Dependency receipts
  add externally located pinned model/FX files and governed roots to coverage.

Provider archives remain inspection/replay evidence; backing them up does not
make them audited research inputs or establish historical availability.

This is application recovery, not a Windows disk image. Reinstall OS/software and
package environments. Caches, runtime PID/lock files, ClickHouse diagnostic logs,
`.env*`, named token/key files and private/secrets directories are excluded.
Effective non-secret environment settings are saved in `runtime-settings.json`;
password/key/token fields are omitted and listed for reprovisioning.
Reprovision credentials separately. Source files are included; Git history is
available separately from the Git remote.

Each native database/stream snapshot is consistent, but the recorded capture
interval is not a global cross-service transaction. Live file roots are read
during upload. Versioned immutable artifacts remain recovery evidence. Validate
input/publication dependencies and reconcile with the broker before execution.
No full-system snapshot is automatically restored onto a running database.

## Offline behavior and verification

Full captures are hourly while the platform runs, with failed/offline retries
every five minutes. A two-second SMB connection probe and a cancellable,
30-second filesystem probe precede capture. This also handles a NAS that answers
TCP but hangs on SMB metadata. The separate worker keeps uploads out of local startup,
trading and checkpoint paths. Shutdown cancels network subprocesses; native
ClickHouse work may finish locally and is cleaned up on retry. Missing workers
are restarted by the existing application supervisor chain.

The first backup transfers the complete set; later restic snapshots compress and
deduplicate content. Interrupted uploads retain their capture and reuse uploaded
blocks on reconnect. After a delayed capture completes, an hourly-due fresh
capture follows. Missed timer ticks do not need individual recreation.
`deferred` preserves the last complete snapshot ID and its timestamp.

Native files have SHA-256 inventories. Partial/unreadable-source restic results
never become complete. Publication requires success, a repository metadata check
and independent decrypted manifest readback; only then is it tagged
`system-complete`. This is distinct from a full data scrub or restore drill.

```powershell
.\.venv\Scripts\python.exe scripts/system_backup.py status
.\.venv\Scripts\python.exe scripts/system_backup.py verify
```

`verify` reads/authenticates all repository data and requires the capture lock;
defer it while a backup is active. Status and progress are in
`var/run/system_backup.state.json`, the optional platform health entry,
`var/log/system_backup.worker.log` and `var/system-backup/command.stdout.log`.
Subprocess diagnostics are in `command.stderr.log`.

### System dashboard

Open **System → Backups** (`/platform#backup-panel`). The panel refreshes every
five seconds and shows connection, native capture, transfer and verification
stages; the last completed NAS snapshot and capture time; protected source size
and newly stored compressed/encrypted bytes; PostgreSQL checkpoint results;
the next capture/retry; and configured coverage and destination.

The read-only `/api/v1/platform/backups` endpoint reads bounded local records and
the upload log tail. It never probes the NAS, opens database connections or
starts a backup. An unreachable NAS cannot block this panel. Missing/stopped
workers, stale heartbeats, pauses and failed refreshes are shown explicitly.
Upload percentage measures source bytes processed, not bytes transmitted;
source totals can grow during scanning. Transfer completion remains separate
from verified publication. A previous successful recovery point stays visible
during new captures and retries; a new unverified candidate's sizes are never
attributed to the previous completed snapshot. The completion record is the
worker's last verified observation, not a fresh repository scrub on each visit.

Use `system_backup.py stop` to explicitly pause only this worker; automatic
supervision honors that pause. `system_backup.py start` resumes it. Ordinary
platform shutdown/startup preserves this explicit choice.

No automatic snapshot deletion is enabled. Existing SQL generations are retained.
Review NAS capacity before choosing a separate retention policy. The worker uses
only restic's stale-lock removal; never use `unlock --remove-all` to bypass a
writer. Local staging is a dedicated, validated path outside all source roots.

## Encryption and recovery key

The official pinned restic 0.18.1 installer verifies the release SHA-256. Its
encrypted/authenticated repository is at:

`\\192.168.1.32\Public\systematic-trading\full-system-restic`

The generated key is `var/private/system-backup-recovery-key.txt`, excluded from
backups and Git. **Save a separate copy in a password manager or another safe
device. Losing the laptop and this key makes the encrypted backup unrecoverable.**
An existing repository without its key fails closed rather than being recreated.

## Recovery

1. Provision compatible PostgreSQL, ClickHouse and NATS on a recovery machine,
   retrieve this code, and run `scripts/install_restic.py`. Put the saved key in
   its configured private path. Recreate database roles and credentials separately;
   role passwords are not in PostgreSQL dumps. Keep application writers stopped.
2. Select the exact 64-character `system-complete` snapshot ID and extract into
   a separate empty directory:

   ```powershell
   .\.venv\Scripts\python.exe scripts/system_backup.py restore-files `
       --snapshot EXACT_COMPLETE_SNAPSHOT_ID --target D:/systematic_trading_recovery
   ```

   Extracted contents are verified. `restore-map.json` maps neutral `root-NNN`
   directories to original paths without copying Windows system-ancestor ACLs.
   Locate the capture's `manifest.json`, `postgres.dump`, `clickhouse/.backup`,
   `nats/streams.json` and stream snapshots.
3. Recover files to the recorded paths on the clean machine; analytical workspace
   identities depend on them. Restore PostgreSQL with compatible `pg_restore`,
   `--exit-on-error` and `--single-transaction` into a new empty dedicated database.
   Never replay old SQLite approvals/orders over current PostgreSQL state.
4. Copy the native ClickHouse directory to its allowed backup path and use
   `RESTORE DATABASE ... FROM File(...)` for the listed databases on an empty
   instance. Reprovision users locally. Restore NATS stream files using the native
   JetStream restore API/CLI with saved configuration/state and consumers.
5. Compare native hashes, row identities/counts and dependency receipts; verify
   governed publications and model/run inputs. Apply normal stopped-service
   restore guards and fresh broker reconciliation before execution. Review the
   captured paper policy; live remains disabled by default. Retain original data
   until the recovery drill passes.

Both PCs must upgrade before another handoff. The retirement bridge accepts only
the exact archived SQLite fingerprint; new old-PC SQLite edits block the bridge.
Old code does not understand compressed PostgreSQL snapshots or the new layout.

References: [restic backup/partial-exit contract](https://restic.readthedocs.io/en/stable/040_backup.html),
[ClickHouse native backup](https://github.com/ClickHouse/clickhouse-docs/blob/main/docs/operations_/backup_restore/00_overview.md),
[NATS snapshot/restore API](https://github.com/nats-io/nats-server/blob/main/server/jetstream_api.go).
