# Storage and NAS recovery audit — November 8, 2026

## Decision and status

The operator wants recovery after catastrophic laptop disk failure: retrieve the
codebase from Git and restore the application's durable data from NAS. NAS is
not an archive for replaying the entire research history. Unbounded backup
generations and duplicated research workspaces do not serve this purpose.

This session completed a read-only storage/code audit and generated guarded
retirement plans. No data, backup generation, snapshot, database row, or lock was
deleted. Backup runtime configuration is **not yet changed**. The recovery-only
implementation and verified transition described below remain outstanding.

Measurements use decimal GB/TB. Directory sizes sum file lengths, not allocated
disk blocks. Hard links, cross-category shared content, compression and NAS
filesystem snapshots mean these figures must not be added as physical usage.
Services continued running, so successive inventories differ slightly.

## What the 3.76 TB means

The completed backup reports 3,763,618,717,274 source bytes processed across
29,940,031 file names. It added 1,507,956,122 compressed/encrypted bytes to restic.
Its source capture completed November 7 at 21:43 Shanghai time; verified backup
publication completed November 8 at 00:49. These figures came from
`var/run/system_backup.state.json`, not an estimate of network traffic.

The main cause is `var/governance`: approximately **3.601 TB of logical file
lengths and 29.13 million file names**, about 96% of the backup's processing
total. The whole D: volume used approximately **373 GB** at audit start.

There are approximately 2,770 governance directories. A later pass found 1,337
with manifests and 1,434 without manifests; a live producer created another
directory between passes. Directories without a manifest account for 1.619 TB
of logical lengths and 13.25 million names. Absence of a manifest alone is not
proof that an entire directory is disposable: classify failed/in-progress/legacy
roots and inspect current dependencies before retirement.

The refresh producer hard-links unchanged series into new snapshots. A sampled
KNX history file had **259 hard links**. The 1,337 complete manifests contain
15.88 million references but only 217,894 distinct declared content hashes,
representing 55.21 GB of content. This is manifest-based content accounting,
not an exhaustive measurement of physical space recoverable from all governance
directories. It excludes unmanifested content and filesystem metadata and does
not prove every equal-content file uses the same physical blocks.

`research/governed_refresh.py:inherit_series` creates the inherited tree before
fetching and validating the new symbols. Failures retain their output directories.
The producer therefore saves data blocks through hard links but still multiplies
directory entries, manifest work, scanning and recovery inventory cost. Backups
include the whole `var` tree, including obsolete and unfinished snapshots.

## NAS usage and recovery freshness

| NAS folder | File bytes | Finding |
| --- | ---: | --- |
| `systematic-trading/snapshots` | **764.53 GB** | 2,146 SQL handoff generation directories; no pruning policy |
| `systematic-trading/full-system-restic` | **157.65 GB** | Encrypted, deduplicated recovery repository; historical snapshots retained |
| Combined measured backup files | **922.18 GB** | Does not include NAS filesystem overhead or hidden device snapshots |

The SQL generation folder contains 457.74 GB of gzip SQL dumps, 202.28 GB of
plain SQL dumps, **38.10 GB across 905 legacy SQLite copies**, and **66.41 GB of
JSON manifests**. These are repeated database states, not 765 GB of distinct
stock observations. The current production configuration has no SQLite database.

`OptionalNasSync.transfer` writes a new immutable directory and changes
`latest.json` but never retires old generations. `SystemBackup.publish` similarly
does not forget/prune old restic snapshots. These two independent mechanisms
compound retention overhead.

The SQL `latest.json` points to a generation created **October 19 at 13:39
Shanghai time**, only 0.599 GB including its manifest. Current local sync status
is `local_only`, reporting `NAS operation.lock exists; another sync is running
or needs crash recovery`. That lock was not bypassed. The November 8 restic
recovery point is newer. Do not discard it on the assumption that the SQL
handoff copy alone is current. Do not infer the compressed size of today's
database from the smaller October 19 checkpoint.

## What is stored locally

| Component | Measured size | Interpretation |
| --- | ---: | --- |
| Current PostgreSQL database | **10.42 GB** | SQL-reported total including indexes and internal storage |
| Native analytical Parquet lake | **74.75 GB** | Approximately 243,459 files; includes historical versions/projections |
| Governance file tree | **3,600.95 GB logical** | Mostly repeated linked histories; not physical usage |
| Tracked strategy workspaces | **33.38 GB** | Latest, protected, and superseded calculations |
| Tracked model workspace | **4.49 GB** | Model schedules, versions and fits |
| Repository exploratory research | **9.65 GB** | Generated experiments, copied source, inputs and engine outputs |
| External research/source collection | **12.22 GB** | Mixed canonical parents, source archives and research inputs; not all disposable |
| October 18 restore drill workspace | **36.22 GB** | Restored analytics, PostgreSQL, queue copies and dump; retain compact acceptance evidence, review bulky copies |
| Full-backup staging | **28.12 GB** | Includes a 27.23 GB deliberately uncompressed custom PostgreSQL dump |
| Local SQL checkpoints | **34.36 GB at scan time** | Included a 27.49 GB in-progress plain SQL file and two approximately 3.26 GB gzip checkpoints |
| Older pre-migration backups | **6.04 GB** | Mainly an old ClickHouse tar archive; review against accepted migration evidence |
| Native NATS directory | **5.24 GB** | Current stream storage plus migration snapshot |
| Raw market-data hot spool | **8.53 GB** | Includes intraday data and manifests, not just daily OHLC |
| New reusable provider source archives | **0.017 GB** | WRDS/IBKR/Alpaca/Tushare captures; tiny relative to other burdens |

Temporary dump/checkpoint sizes were observed while workers were running; they
are not all permanently stale cleanup candidates. Likewise the remaining
3.02 GB Docker/WSL disk images are not an instruction to delete a global runtime.

PostgreSQL is dominated by the **6.81 GB event outbox** and **3.00 GB publication
table**. The outbox contains 3,716,263 `market_data.recorded` events; all were
marked published in the read-only query. Order/fill/approval/incident events are
separate small classes. Review delivered market-data retention and replay
requirements; never apply a blanket deletion policy to broker or approval events.

The Parquet catalog contains 45,437 governed-price versions with 254 million
versioned row occurrences and 45,299 comparison versions with 286 million row
occurrences. These counts are not distinct security/date observations. Logical
fragment references by family include 30.53 GB governed prices, 21.07 GB source
comparisons and 12.21 GB migration fingerprints. Families can reference the same
content-addressed file, so their sizes cannot be summed as reclaimable capacity.
The market daily-bars family occupies approximately 1.72 GB across 8,019 files.

## Format assessment

The operator's scale calculation is correct: 2,000 stocks × 252 sessions ×
30 years = 15.12 million rows. Four 64-bit OHLC values require **483.84 MB**
uncompressed. Volume, identifiers, dates, corporate actions, adjusted/raw
distinctions and provenance add storage, but do not explain terabytes of unique
daily-price information.

The current formats already compress data:

- Governed price files are gzip JSON Lines. Each row carries raw and adjusted
  OHLC, volume, source identity/hash/vintage, action factors and quality fields.
- The native Parquet writer uses Zstandard compression, content-addressed files
  and batches bounded by row count and approximately 8 MiB of records. Its eight
  columns are strings, including a JSON `record`; it is not a fully typed numeric
  OHLC layout. Small publications can create tiny files and repeat metadata.
- Restic deduplicates and compresses backups. The uncompressed staging dump
  preserves chunk-level deduplication opportunities but consumes local scratch
  space; compressing it blindly is not necessarily a NAS-space improvement.

A controlled in-memory test of ten evenly spaced symbols from the current
listed-stock bars directory retained all inferred fields and values:

| Representation, 41,620 rows | Bytes |
| --- | ---: |
| JSON text | 30,643,960 |
| Existing gzip JSON Lines | 2,800,715 |
| Typed Parquet with Zstandard | 2,485,030 |

That sample saves **11.3%** over gzip, not orders of magnitude; two short series
became larger. It is not a full migration benchmark or proof of identical
production schema semantics. Address repeated versions and generations first.
Typed/partitioned Parquet and metadata normalization are subsequent optimizations,
with immutable versions, hashes and point-in-time boundaries preserved.

## Concrete retirement findings

The existing guarded planner identified **58 superseded tracked revisions,
23.54 GB of exclusive file content**, while protecting 26 revision paths. It
also identified **115 superseded model schedules, 3.15 GB**, protecting 24 paths.
Together this is **26.69 GB** eligible under the planner's observed protection
state. Plans must be regenerated/revalidated immediately before application;
running calculations and publication changes invalidate stale plans.

The closed-study plan was deferred because the application held
`research-retention.lock`; the lock was respected. No blanket deletion verdict
was assigned to the remaining 9.65 GB of exploratory output. The restore-test
workspace and old migration backup are additional review targets, not verified
free-space promises. Hard-linked governance names require inode-aware group
accounting before making any physical reclamation claim.

The source archive root `D:/systematic_trading_data/source-archives` is absent
from the inspected full-backup source list and configured required roots. The
new WRDS captures are not guaranteed covered by that capture. Their local
retention remains required; include the tiny irreplaceable acquisition records
in the new recovery contract without retaining entire research replays.

## Recovery-only replacement contract

1. Recover committed code, tests, recipes and compact findings from Git. Record
   the required commit and verify it exists remotely. Do not use NAS to retain
   every source copy, environment, engine installation or experiment output.
2. Capture consistent PostgreSQL state and the exact external data required by
   that state: canonical audited Parquet/history inputs, relevant manifests,
   current protected strategy/model dependencies, and broker/approval/
   reconciliation evidence. Retain irreplaceable source captures such as WRDS.
   Reinstall runtimes and rebuild disposable views/caches after recovery.
3. Keep one current verified logical recovery set. During replacement, preserve
   the old complete set until the new one passes verification. Deduplicate shared
   data; do not accumulate a full SQL generation every five minutes or retain
   historical restic research snapshots indefinitely. Any extra historical
   recovery window must be explicitly scoped, not an unlimited default.
4. Size the backup against the actual durable data required for recovery, which
   currently spans PostgreSQL **and external files**, rather than the 3.76 TB
   sum of repeated names. Display recovery-set source size, actual repository
   size, newly stored bytes and oldest/current recovery dates separately.
5. Resolve the SQL sync lock only after checking both PCs, or retire that
   redundant NAS upload mechanism through a tested migration that preserves
   local checkpoints and any still-required handoff behavior.
6. Before pruning existing NAS history, restore the replacement into an isolated
   native environment, verify SQL state and all required file hashes, read the
   current strategy reports, and test restart/recovery guards. Then retire old
   SQL generations and obsolete restic snapshots using the supported tools.
   Keep the encryption recovery key separately. No live routing or test broker
   order is part of a restore drill.

Reducing local disk usage is a separate operation from reducing NAS retention.
Deleting a local file does not reclaim blocks retained by old restic snapshots.
Dropping backup coverage without adjusting restore dependency semantics could
create a small but unusable backup. Do not promise a final compressed footprint
before measuring the selected, restore-tested recovery set.

## Evidence

Local machine-readable inventories and proposed retirement manifests are under
`var/maintenance/storage-audit-20261108/`: `inventory.json`, `quick-trees.json`,
`governance.json`, `governance-tree.json`, `postgres.json`,
`catalog-analysis.json`, `data-composition.json`, `format-sample.json`,
`nas.json`, `nas-generations.json`, `nas-latest.json`,
`tracked-retention-plan.json` and `model-retention-plan.json`.
These remain local metadata, not provider rows committed to Git.

Verification: complete three-root filename/length inventory reported no access
errors or reparse-point skips; read-only PostgreSQL queries; NAS file inventory;
representative NTFS hard-link checks; source/format inspection; in-memory format
comparison; existing dependency validator passed all 15 registered contracts.
This audit did not run a full restic data scrub or a new restore drill.

## Implemented recovery transition — November 9

The follow-through replaced broad research replay coverage with the bounded
`recovery-v1` set, including the retained WRDS source archive. A real isolated
NAS restore passed on November8 at 23:01 Shanghai: 729,885 dependency hashes,
24 SQL table counts, portfolio controls, publication heads, 86 current report
documents and NATS stream/consumer state. The encryption key and acceptance
receipt were copied beside the repository with operator authorization and
hash verification. Code recovery records the remotely available Git base and
the working-tree patch/untracked source delta.

Pruning retired 145 superseded restic snapshots and 2,148 SQL generations
(770,124,353,124 bytes of SQL-generation files). This NAS sends deletions to a
separate recycle share; permanent cleanup therefore also removed recognized
retired backup objects from this project's recycle subtree after checking the
live repository. The final subtree is empty, with zero skipped files.

At 01:36 Shanghai on November9, project NAS files total **83,588,643,997 bytes
(83.59 GB)**, and actual NAS free space increased **844,657,397,760 bytes
(844.66 GB)** to **1,027,281,301,504 bytes**. The first hourly successor completed
at 00:35: 162.94 GB logical source, 831,832 files and 88.26 MB newly packed data.
Retention keeps one complete recovery point, preserving it until a successor
passes publication checks. The background scheduler resumed at 01:37.

The stale SQL handoff lane is retired in recovery-only mode. Local start/stop
checks for an interrupted restore without dumping SQL or waiting on NAS;
the exact startup command passed in seven seconds with production online.
The separate local 26.69 GB retention opportunity above was not applied. The
new temporary restore-test copy remains because automatic approval review
blocked deletion even after explicit operator approval, not because it is a
required recovery artifact. Its isolated test services are stopped.

Final receipts: `var/maintenance/recovery-pruning-20261108/acceptance.json`,
`fresh-complete.json`, `nas-final.json`, `recycle-retirement-main.json`,
`recycle-retirement-final.json` and `served-final.json`. Validation: 96 tests
passed, four environment-dependent skips, all 15 strategy dependency contracts
passed, and the final three scoped retention tests passed after the filename
classification adjustment.
