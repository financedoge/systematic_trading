# Project Log

## 2026-10-18 — Operator compaction and paper Gateway follow-up verified

The operator's Administrator compaction completed at 16:36 local time. DiskPart
returned zero and the measured receipt records 267,222,253,568 bytes before,
2,918,187,008 after, and 264,304,066,560 bytes reclaimed (246.15 GiB). This receipt's
starting size is below the earlier pre-compaction observation; no unmeasured
intervening reduction is attributed to this command. The current file size matches
the receipt. Exclusive access confirms it remains detached; Docker/WSL processes
are absent and Docker auto-start remains absent. D: had 848,615,383,040 bytes free
(790.33 GiB) at the 16:39 host check.

Gateway is now healthy. The operator had already enabled paper policy revision 19
at 16:37, with the same account, machine/broker binding, allocated strategy and
1,000,000 CNH cap as the pre-maintenance policy. No policy write was needed or made.
Fresh guarded reconciliation at 16:40 matched all six broker positions, with zero
position differences, unmatched local orders/fills or warnings; no broker reset
was applied. Allocation control exactly matches its migration baseline and live
routing remains disabled. All seven strategy reports still serve the accepted
native calculation, and PostgreSQL, NATS, analytics, dashboard, dispatcher,
trading management, backup and recovery are healthy.

Normal hourly backup supervision independently completed another incremental
snapshot at 16:09: `40cbff997b972b940ec7b3f8dd440ca379cca2e06c14ca27621c6fcfd730d656`.
Existing daily history acquisition/identity-review and execution-benchmark gaps
remain reported. Both automatically blocked restore-test directories are retained;
their deletion was not retried. Final receipts are
`var/maintenance/windows-cutover/operator-followup-acceptance.json`,
`post-compaction-host-verification.json` and the updated `final-cutover-summary.json`.

## 2026-10-18 — Native cutover accepted and legacy Docker resources retired

Application revision `b528d1061f7757f1bcc434529662beb20251fcd69748878e7870d91b43eeddc4`
published successfully. All seven monitored strategies and their rendered reports
are current through October 16. Twelve native LEAN runs matched the independent
Python oracle; final verification checked their artifact hashes, two-CPU/4-GiB
isolation receipts and unchanged allocation control. Peak measured engine Job
commit was 649,760,768 bytes. Paper approval remains paused: Gateway port 4002 is
offline and fresh broker reconciliation is still required.

The post-calculation native NAS snapshot is
`2d08c381db7938ac4c0c7a1dc2efdd34e67428239a832f8f11507ef96aebc289`.
It passed repository metadata checks, decrypted manifest readback and an additional
exact-identity/dependency readback verifying the newly published calculation. It
reused 1,287,668 files and added 124,934,927 packed bytes. The previous verified
native snapshot is its explicit parent. Normal hourly backup supervision resumed.
Refreshes deferred by the backup's file lock retain complete reports; a normal app
refresh was requested after the backup released that lock.
Analytics subsequently returned to healthy with no errors and no stale strategies.
Final full-source lint, 94-document/478-link validation and diff checks pass.

Targeted ownership-checked retirement removed the project ClickHouse container,
`clickhouse_clickhouse_data`, `nats_nats_jetstream_data`, and the exact legacy LEAN,
NATS and ClickHouse image IDs. Docker inventory is empty. Docker Desktop and its
only registered WSL distribution are stopped, auto-start is absent and exclusive
access confirms the Docker data VHDX is detached. Stale inference/secrets sockets
were preserved to allow this final maintenance startup; the app no longer starts
Docker. The disk-trim command completed with zero additional bytes reported.
The VHDX still measures 275,692,650,496 bytes; Administrator compaction was requested
and no shrink is claimed until its measured receipt exists.

Verified research retirement remains 97.73 GiB of exclusive file contents across
815 roots. Final `var/` inventory is 142,758,923,877 logical bytes / 1,146,952 files
(about 133 GiB, versus 477.32 GiB originally); hard-link accounting is distinct
from host free space. Automatic approval review blocked deletion of both disposable
restore-test directories, stating only "blocked by policy". They were not retried:
`var/system-backup/postgres-restore-drill/data` and
`D:/systematic_trading_data/native-restore-drill-20261018` remain. The latter has
36,220,447,218 logical bytes and preserved acceptance/logs. Active data, protected
research and broker evidence remain intact.

## 2026-10-18 — Native cold startup, backup identity and worker serialization

Docker-free cold startup passed: PostgreSQL, Parquet analytics, native NATS,
dispatcher and all seven monitored report endpoints respond with portfolio control
unchanged. Docker Desktop auto-start was removed; project containers/volumes remain
pending final calculation acceptance. The offline paper Gateway still prevents
fresh reconciliation and restoration of the previous paper approval.

The first native NAS backup completed upload, repository metadata checks and
decrypted manifest readback. Restic's per-path-group latest query incorrectly
reported the old October 10 snapshot. The exact tagged original candidate resolves
to `8e0658e40f3d0b0451ee9770eb8d4d8c9364c26bfbb3ce43048f1277c10e0de5`;
independent readback confirms the native capture and status is repaired with an
incident receipt. Backup completion now matches original candidate identity;
explicit parent selection preserves incremental comparison when publication paths
change. The real-restic changing-source-list restore test passes.

A fresh calculation exposed a report routing error: the 12-ETF family attempted
to calculate the 14-ETF FR25 SOTA without its audited raw-activity inputs. Families
now calculate their own strategies, then build cross-pool reports using the verified
same-batch/calendar SOTA bundle and matching comparison prices. Raw data checks and
independent engine validation remain mandatory. Focused routing/report tests pass.

Concurrent native worker ACL propagation also caused intermittent Python imports
and launches to fail. A real simultaneous-caller regression reproduced the failure;
a Windows mutex now serializes the complete isolated run and ACL lifecycle across
callers. All four real isolation checks pass after restarting the old app worker.
The 1,903-case broad run had one Docker-dependent test fixture failure; its fix and
backup regressions pass (21 cases), and lint passes. A new full app calculation is
running with these repairs.

The first complete set of 12 native engine replays passed but cross-pool report
publication correctly stopped: its new price check compared cent-rounded frozen
replay closes to full-precision audited closes. The comparison now uses the same
replay rounding and unrounded initial anchor. All 14 assets over 2,714 valuation
dates match the existing frozen benchmark quotes exactly; a fractional-price
regression catches mismatched bases without accepting a different price series.
Seventeen report/resource checks pass. USD replays also now consume the configured
two-CPU budget instead of the host CPU count. A fresh revision is required and the
previous complete publication remains visible until it succeeds.

Automatic approval review rejected deleting the disposable native restore drill
at `D:/systematic_trading_data/native-restore-drill-20261018`, stating only
"blocked by policy". No retry was made. Its 36,220,447,218 logical content bytes
remain, with acceptance/log copies under the cutover evidence directory; its test
PostgreSQL is stopped. This is separate from the earlier rejected old restore root.

## 2026-10-18 — Verified native data recovery and service-profile activation

The final 50,206-publication export and all 34,772 Parquet file hashes passed
verification, including seven monitored strategy API/report comparisons and current
publication pointers. All 328 selected obsolete governance projections were retired:
14,049,520,828 exclusive bytes, 11 protected roots/hashes unchanged and every local
receipt matched in PostgreSQL. Combined verified retirement is 97.73 GiB of exclusive
contents, distinct from host free-space growth.

The isolated restore loaded the SQL snapshot, matched table counts, verified all
immutable dependencies and publication pointers, and preserved portfolio control.
Its first queue check failed because the Python NATS `StreamState` type drops
`num_subjects`. The raw API comparison retains that assertion; a fresh queue restore
then passed with 3,278,425 messages, 4,253,536,843 bytes and seven subjects. The first
attempt's source and traceback establish that the database checks finished before
that queue-only failure. Its individual table-count values were not persisted by
the original tool; the recovered phase receipt says so explicitly. Future attempts
save a hash-pinned database phase before queue restore, allowing an explicit retry.

Activated the prepared native service manifest and environment, stopped the legacy
ClickHouse container, retained compact metadata for the obsolete October 10 pending
backup and started a fresh native capture. A backend identity check prevents old
ClickHouse captures from being published under native runtime settings. One-shot
backups and retirement now share an OS lock so cleanup cannot race a backup upload.
Native startup and full NAS backup acceptance remain in progress; project Docker
resources are still retained. The Gateway on port 4002 is offline, so prior paper
approval cannot yet be restored. No live routing or allocation authority changed.

The 1,892-case broad regression run had three failures: two retired historical
replays and an obsolete ClickHouse-default assertion. All were repaired; the
49-case affected suite has no failures and two explicit receipted skips. All 37
native service/API profile tests pass, as do raw NATS count comparisons and backup
backend/retirement-lock tests. Existing library deprecation warnings remain.

## 2026-10-18 — Disk retirement and native migration resumed

Verified retirement receipts cover 95 superseded tracked calculation directories
(33,711,157,335 exclusive content bytes), 34 completed-study leaves (31,350,394,995
bytes / 674,304 files), and 264 unreferenced model revisions (6,743,163,895 bytes).
An additional 94 completed-study leaves (19,079,215,319 bytes) were removed and
verified against their receipts, three protected active studies and retained
protocol/finding hashes. Total verified exclusive contents removed: 84.64 GiB.
The protected calculation/study/model roots remain present. These are removed file
contents, not a claim of equivalent Windows free-space growth: exports and runtime
installation consume space, and hard-linked governance names share contents.
Compact PostgreSQL retirement records accompany immutable local receipts. During
receipt synchronization an additional key format recorded the earlier 95 entries
again; those append-only audit rows remain, and subsequent synchronization deduplicates
by original path plus retirement manifest. Count distinct retirements, not raw rows.

Native NATS restarted with its restored stream. Native LEAN's retained seven-strategy
comparison, fixture stress cases and independent Python parity were accepted before
this interruption. Native model training exposed AppContainer's denial of the Python
process pool's global named pipes; keep isolation and train sequentially inside the
bounded worker. Two real fit dates matched the retained model output exactly. The three full-suite failures
were corrected (chart DOM fixture, obsolete Docker-NATS expectation, validation error
wording); focused checks and Ruff pass. Native PostgreSQL snapshot/publication tests
also pass. Full-suite result before those repairs: 1,881 cases, 3 failures, 60 skips.
The later native-selected suite ran 1,888 cases (25 failures, six skips). Eighteen
historical replay tests required intentionally retired outputs; they now skip only
with a matching retirement receipt, while compact findings and rule tests continue.
Six PostgreSQL broker tests lacked the strategy-control schema in their disposable
fixture, and one legacy orphan-container test needed an explicit Docker setting.
The affected 190-case suite passes with 19 skips. Optional NAS native handoff now
checks restored publication heads after loading SQL. Native USD run inventories
include their sidecar manifest, and native fragment recovery groups a snapshot
subtree instead of launching a separate restic process for every fragment.

After the host interruption PostgreSQL returned invalid-argument file reads and
permission errors. A normal service restart required Windows administrator rights;
the operator performed it and the 49,833 migrated publications became readable.
Docker Desktop could not reopen stale `dockerInference` / `engine.sock` endpoints.
Preserved the stopped, socket-only parent directories with unique names, stopped the
failed launch, and performed one controlled restart. Docker and the existing
ClickHouse source became healthy. The exporter now bypasses inherited proxy routing
for its local source and retries interrupted HTTP transport at most three times.
No Docker factory reset, volume deletion, PostgreSQL restore or live enablement.

Analytical cutover is still pending. The source-comparison export is continuing;
the final selection adds older catalogs and publication records pinned by operational
calculations (50,206 publications / 10,065 governed pairs). The app remains stopped and its prior paper
policy paused. Native backups now export a PostgreSQL snapshot shared by pg_dump and
the Parquet dependency inventory; only committed fragments enter the source list.
Next: finish and compare the export, retire verified duplicate governance projections,
complete native backup/restore and startup checks, reconcile, then restore the prior
approved paper policy without changing the allocation or live guards.

## 2026-10-17 — Retention policy changed and native Windows migration selected

The operator explicitly prioritizes memory/storage over recomputation time, asks
to remove artifacts for archived strategies, and no longer requires exact replay
copies for every completed exploratory study. Retain compact findings, definitions,
rerun recipes and retirement records; disposable bulk outputs do not need full
backups. Protect active/monitored/funded/pending strategies, current studies,
promotion inputs, canonical audited histories and operational evidence. An old
research registry row can be accompanied by an append-only artifact-retirement
record instead of keeping all its files forever; a later rerun on a new audited
batch is new evidence, not reproduction of the old metric.

After clarification that ClickHouse has no supported native Windows server, the
operator selected PostgreSQL for operations/publication metadata plus compressed
Parquet/native DuckDB analytics. Native NATS and a Docker-free calculation and
independent-validation path complete the requested architecture. The plan covers
the existing LEAN container dependency, restricted native worker execution, typed
store contracts, atomic publication, format/version/hash lineage, path-derived
workspace identity, bounded memory/spill, startup/recovery and native backups.
It does not substitute Python replay for independent engine validation or weaken
broker/reconciliation/promotion gates.

A fresh live API snapshot found 22 archived catalog entries (21 IDs) and seven
monitored strategies. FR25 is currently SOTA and 100% paper allocation, control
revision 7, with no pending allocation; the older F3 allocation note is historical.
Latest two complete tracked directories total approximately 0.89 GiB versus 58.20
GiB across all 239 revisions. Older calculation workspaces and completed scenario
outputs are the main artifact target; the 0.22 GiB legacy backtests alone are small.
Any deletion manifest must recheck these live controls and genuine dependencies.

Saved `docs/storage-retention-and-windows-native-plan.md` with retention classes,
three cleanup waves, seven implementation stages, code boundaries and acceptance
checks. Updated project rules/playbook and architecture indexes to distinguish the
selected target from the still-deployed ClickHouse/Docker system. Inventory:
`var/maintenance/retention-plan-20261017.json`; live evidence:
`var/maintenance/retention-live-catalog-20261017.json`. No data was deleted and no
service was migrated or reconfigured in this planning session. The earlier tool
rejection of the retired restore-test deletion was not retried or bypassed.

## 2026-10-17 — Storage inventory and Docker/service memory assessment

The operator asked whether most of `var/` can be deleted and why ClickHouse/NATS
require Docker. Read-only scans found 4,832,482 files / 477.32 GiB logical lengths.
Governance dominates the apparent size at 353.17 GiB, but an NTFS file-identity scan
found only 18.43 GiB of unique contents: 3,027,489 names in its subdirectories share
82,299 files. Allocated blocks/metadata/compression and cross-root sharing are not
measured. Tracked strategies are 58.20 GiB, research 53.53 GiB and models 6.77 GiB.
Do not promise hundreds of GiB reclaimed by deleting hard-linked governance waves.
The current cash-relative, class/volatility and expansion studies' common pinned
catalog manifest and publication were verified; the study protocols also retain
explicit parent-study dependencies. Old/unpublished directories are not automatically
unreferenced or disposable. Existing manifests require exact file inventories.

Outside `var/`, ClickHouse active system diagnostic parts total 82.53 GiB, mostly
processor profiling (61.00 GiB) and text logging (15.13 GiB). Routine processor
profiling is enabled; profiling retention is 30 days and query/text/trace logs have
no TTL. Analytical/market-data parts are separate. Docker's 42.5 GB reclaimable
image is the pinned LEAN runtime and was retained. The latest recorded completed
full-system snapshot is October 10; the current candidate is still `verifying`,
so there is no newly verified backup claim.

Docker reports much higher usage than process RSS: NATS itself reports 43.05 MiB,
ClickHouse about 1.05 GiB, with about 5.99 GiB of file cache in the ClickHouse cgroup.
Both containers are uncapped. The scheduler budgets from total Docker memory,
reserves only 2 GiB for services and permits three concurrent 4 GiB LEAN workers;
the recorded budget is 15.39 GiB. Model fitting can use all 16 host cores. NATS
stores 3.21M messages / 3.88 GiB, has zero consumers at the sampled instant and no
stream age/size retention within its 5 GiB server file-store limit. These observations
support P6.15 resource/retention work, not a claim that Docker caused every crash.
NATS can run natively on Windows; ClickHouse's supported Windows route uses WSL,
and LEAN still uses Docker. Deployment changes must preserve backup/recovery and
event/publication contracts. The JSONL publisher is an existing alternative to
review for a simpler local profile; stopping NATS alone leaves a configured NATS
dispatcher unable to deliver events.

The 3.586 GiB PostgreSQL restore-test cluster under
`var/system-backup/postgres-restore-drill/data` was verified stopped with a clean
October 7 shutdown, no PID file/listener, and a separate active service directory.
An attempt to remove only that disposable cluster while preserving its logs was
rejected before execution by automatic approval review: “blocked by policy”. No
files were deleted. No service, table, stream, trading control or calculation source
was changed. API, ClickHouse and NATS health endpoints returned 200.

Inventory and dependency receipts are in `var/maintenance/*review-20261017.json`
and `storage-dependency-checks-20261017.json`; the full assessment and ordered next
actions are in `docs/repository-maintenance.md`. Prioritize bounded diagnostic
retention/profiling, service/worker memory budgets, and verified dependency-aware
artifact deduplication/retention. Preserve paper-first/live-disabled behavior.

## 2026-10-17 — Incident: ChatGPT/Codex desktop app crashing while working in this repository

The operator reported repeated crashes of the ChatGPT/Codex desktop app while working on this
project. The crashes are in the OpenAI client process, not in this repository's code:
Crashpad retains ten crash reports, nine of them on 2026-10-17 (04:22:54, 11:51:12, 12:09:15,
13:57:37, 14:16:55, 14:24:41, 15:18:44, 16:39:55, 16:46:29 Asia/Shanghai), plus one on
2026-10-15 21:20:49. Every report is `ptype: browser`, i.e. the Electron main process, and each
one matches an abrupt end of the corresponding `codex-desktop` session log. The retained dump
for the 16:46:29 crash is `ChatGPT.exe` (version 26.1013.4894.0, pid 11524): exception
`0xC0000005` (access violation, write to null) at `chrome.dll+0x677fe40`, 3.15 GiB committed
across 15,917 memory regions at capture. The app also logged `ERR_WORKER_OUT_OF_MEMORY`
("Worker terminated due to reaching memory limit: JS heap out of memory") on 2026-10-17
15:28:56 and 2026-10-15 21:53:45, and Windows recorded an `AppHang` for `OpenAI.Codex`
26.930.3930.0 on 2026-10-09 (`HamTerminateHang.dmp`). Crashes occurred while a turn was
streaming and the app's remote "durable" connection was in a failed reconnect loop
(`wss://chatgpt.com/backend-api/wham/remote/control/server`; one session reached 143 retries,
~48 minutes). The app auto-updated from 26.1007.9446.0 to 26.1013.4894.0 between 11:45 and
12:00 that day, and 8 of the 9 same-day crashes followed the update. The machine was also
memory-constrained: 31.5 GB RAM, commit charge 40.1 GB against a 61.8 GB limit with
system-managed pagefile, and unrelated `postgres.exe` and OEM-service crashes on the same day.

**Workspace contribution.** The working tree is far larger than a desktop agent can index:
`var/` held 4,804,567 files and 485.36 GB at analysis time. Four generated trees account for
99.94% of what the app's file search sees: `var/governance` 3,015,248 files/351.78 GB (235
frozen `listed-*` candidate-pool snapshots, 209 `research-*` trees and 103 dated run dirs, each
holding per-symbol `sources/*.json` and `bars/*.jsonl.gz`), `var/research` 1,223,542
files/53.53 GB of per-study run artifacts, `var/tracked_strategies` 531,311 files/58.02 GB of
content-addressed strategy bundles (including copied source trees whose paths exceed
MAX_PATH, which makes git emit "Filename too long" warnings), and `var/tracked_models` 5,207
files/6.75 GB of model fits. Only 160 files under `var/` are tracked (159 reconciliation
evidence files and 1 live `.gitkeep`). Baseline: `rg --files` (the mechanism behind Codex file
search) enumerated 4,610,923 files in 4.0 s, and `git ls-files --others --exclude-standard`
(the turn-diff/snapshot view) enumerated 4,610,057 files in 19.0 s. The app's turn-diff
capture also repeatedly failed with `Git snapshot became stale` while running
`git add --sparse` over this tree.

**Containment applied.** Added the four generated data trees to `.gitignore`
(`var/governance/`, `var/research/`, `var/tracked_strategies/`, `var/tracked_models/`), with
the reason recorded inline. Measured after the change: `rg --files` 2,808 files in 0.1 s
(-99.94%, 1,642x fewer), git untracked view 1,948 files in 0.1 s (2,366x fewer),
`git status --porcelain` 0.10 s, and `git status -uall` 0.13 s. The tracked `var/` evidence is
unaffected: `git ls-files var` remains 160 and tracked reconciliation files are not ignored.
No file was moved or deleted; ignored data stays on disk and readable by explicit path.
Diagnostic scripts used for this investigation are in the gitignored `tmp/` directory
(`scan_var.py`, `count_views.py`, `analyze_logs.py`, `parse_minidump3.py`,
`inspect_appserver_logs.py`).

**Operator follow-ups.** Restart the desktop app so the new ignore view is loaded; prefer a
fresh thread over resuming the 11.16M-token thread (`01a14054-…`) while validating. Give the
machine commit headroom (explicitly sized pagefile, reduced Docker/WSL commit, no heavy
backtests in the same session), stabilise the VPN/proxy path to `chatgpt.com` or disconnect
remote-control enrollment, and reset a partly broken sandbox
(`C:\Users\defen\.codex\.sandbox\setup_error.json`: "read ACL run had errors"; local-executor
plugin `ENOENT`; DCOM 10016 denials for the `OpenAI.Codex` app container). Report the crash
timestamps and thread id to OpenAI; the dumps were uploaded automatically. Boundaries: no app
calculation source, monitoring, allocation, capital, broker or live setting changed.

## 2026-10-17 — Cash-relative momentum: improved class signal, still outside the cost gate

The user requested continuation after the October 16 class/volatility screen.
Registered a separate cash-relative hypothesis before outcomes: subtract the
126-session BIL return from ETF momentum before dividing by the same 63-session
volatility. Matched controls simply remove BIL from competition. Both retain the
positive raw-momentum gate; the new rule also requires positive excess momentum.
BIL supplies a measured return reference and receives zero target. All 52 candidate
records/50 supported histories are accounted for, including the BWX/CPER holds.
Published October 12 histories were re-read, hash-verified and reproduced exactly.
No direct provider prices, new market observations, macro or FX inputs were used.

The 24-class construction, overlap/duplicate constraints, inverse-volatility
sizing, 45% cap, unfilled-slot cash and 98% gross ceiling are unchanged. Pooled
and class-first variants under monthly and 0.10/0.40/0.80 policies make 16 mappings.
The 44 bp annual implied-cost ceiling and 3x mapping-IC/breakeven margin stay fixed.
All 16 fail the cost gate; the cheapest dynamic mapping costs 108.46 bp annually.

Class-first cash-relative monthly is the near miss: cost 45.6577 bp, calibration
mapping IC +0.02606 and margin 3.5882x, versus removal-only cost 45.3584 bp, IC
+0.01503 and margin 2.0829x. Its later mapping IC is +0.02639 versus -0.04467.
Pooled cash-relative monthly costs 51.7057 bp with a 1.1649x margin. All calibration
mapping family intervals still span zero; a heuristic margin pass is not confirmed
predictability. No gate exception or portfolio replay was granted.

Registered 1/5/10/21-session diagnostics distinguish selection-score IC, final-weight
mapping IC and static BIL-financed payoff. Subtracting the same future bill return
cannot change cross-sectional ranks; that identity is explicitly tested, not
presented as a new signal. At 21 sessions the candidate-minus-removal-only static
payoffs average +6.79/+4.80 bp in calibration and +97.69/+62.57 bp later for
pooled/class-first. Six-month-block family intervals span zero except the later
pooled contrast [+9.05, +180.93] bp. That contrast is already inspected, before-cost
and exposure-confounded (95.45% versus 83.33% invested), not exposure-matched alpha
or account PnL. Only two non-bill classes have sufficient class-first calibration
coverage and one has sufficient later coverage; no broad peer-comparability claim.

Verification: 72 focused tests, Ruff and immutable hash checks pass. Independent
arithmetic checks reproduce 5,800 target vectors, 165,674 scores, 16 policies,
5,698 adoptions, 128 turnover windows, 1,108 forward rows, 26,592 class rows and
554 paired payoff observations. Both normalized parent controls reproduce all
1,450 daily targets exactly. The finite runner composes a frozen parent target
builder; application source and running calculation revisions were not changed.

Evidence: `var/research/cash-relative-momentum-20261017-v1/` and compact artifacts
in `research/cash-relative-momentum-20261017-v1/`.
Registration SHA-256: `35f7731263cdf618294e1f4a8dd08ef4910e8ead55cb0988f626468cc2eb3aa4`.
Protocol: `da8e74c4004501b2ad9b6d81b8fe3b3bd312543af4df90202441ba1104e85b98`.
Input manifest: `46cfca8aba0ea62e30da2c9fb62988e5d7f8cb9836421e62638584c5f32ba69b`.
Analysis: `fd31124c83ee437027b43326e6f9ff25b190f9b9055799a18621b2de1206b673`.
Diagnostics: `0efe175cf479525159bca0aa9ff292f095479c35b58340f3ecbf92e11b089195`.
[Full findings](docs/cash-relative-momentum-findings.md).

The prospective design was reserved before results: 126 application-calendar
decision sessions October 19, 2026-April 20, 2027, with 21-session labels through
May 19, 2027. It stays inactive because no mapping qualifies; no scheduler,
automation, recurring agent work or monitored strategy was created. Future
calculations must be app-owned after their separate eligibility/replay review.
Next: review the cost constraint and decide whether to register a distinct
turnover mechanism with the signal fixed. Do not lower the gate or choose a
favorable horizon on inspected results. Historical membership/mandate/vintage
limitations and P6.15 remain open. No capital, broker or live setting changed.

## 2026-10-16 — P4.16d class/volatility construction screen: all 16 mappings rejected

Continued the agreed research plan after P4.22/P4.23 and the expanded-FR25
rejection. Registered a separate, transparent price-only construction family:
pooled/class-first selection crossed with raw 126-session momentum or momentum
divided by 63-session annualized volatility, each under monthly and 0.10/0.40/0.80
target-change adoption. No model fitting, FR25 retuning or overlay combination.
All 52 first-wave candidates are accounted for; 50 supported histories reproduce
exactly from the pinned published October 12 batch. BWX and CPER retain their
listing/raw-volume exclusions. Protocol, source and input hashes were frozen
before computing outcomes; no provider-price archives or online prices were used.

The 24-class map has 18 singleton classes in the supported pool. Fund identities
receive one primary class; duplicate representatives use prior raw-dollar volume;
declared parent/child conflicts avoid simultaneous broad/sub-fund selection.
Class scores use the actual members available after these exclusions. Unfilled
slots and the final 45% security cap leave cash. All inputs stop before each
next-open signal session. Current-cohort membership and proposed classification
history remain retrospective assumptions, not certified historical availability.

Result: **0/16 passes**. Fourteen mappings exceed the 44 bp annual cost ceiling.
Normalized monthly pooled/class mappings cost 24.84/38.15 bp but their mapping-IC
margins are 1.91x/0.55x, below 3x. Their 2025+ ICs are -0.04680/-0.08144. The pooled
normalized rule averages 45% BIL plus 41.64% cash later: low bill volatility drives
ranking and inverse-volatility sizing to the security cap, leaving excess cash.
The cheapest dynamic mapping costs 78.84 bp. All calibration family intervals
span zero under the registered 3/6/12-month bootstrap diagnostics.

This gate measures final-target-weight rank IC and security-target-change cost,
not FR25's latent-score IC or realized portfolio performance. All policies adopt
monthly, so the common monthly IC clock is identical within each arm; timing
affects gate costs, not those observations. No NAV, Sharpe, drawdown or native
portfolio replay was produced for rejected arms. Actual turnover/costs, delay
sensitivity, matched average exposure, SOTA/URTH and chronological performance
remain required before any future surviving mapping can qualify.

Verification: 57 focused tests and Ruff pass. Independent checks reproduce 5,800
daily target vectors, 179,940 scores, 16 policies, 4,485 adoptions, 128 turnover
windows and 2,144 IC observations; all constituent turnover totals reconcile.
The independent event calculation exposed last-context-digit Decimal summation
differences from set iteration, not adoption differences: tolerance 1e-24, with
every event verified farther than 1e-20 from its threshold. No shared app primitive
was changed. Research ran sequentially in finite scripts, so the running app's
calculation revision was not invalidated and no service restart was needed.

Evidence: `var/research/class-volatility-screen-20261016-v1/`; compact protocol,
summary, chart, receipt and complete attribution in
`research/class-volatility-screen-20261016-v1/`. Protocol SHA-256
`0176302c527659a923084dac14b3049577e20ffd01951e7053a417fbce31574d`;
input manifest `f1f9b039141a9e29a3d39b2392d7737659826c6f115eb5d55b523ab597d38f13`;
analysis `c2b5ff180071868de2f1e30cbbb50e322e66843b60380f5be721ba7644102f59`.
[Findings](docs/class-volatility-screen-findings.md).

Next: stop this item for review, as the plan requires. Consider a separately
registered cash-relative, peer-comparable momentum hypothesis with an explicit
horizon and prospective period; do not tune this failed family to rescue it.
Historical membership/mandate reconstruction and P6.15 remain unresolved.
No monitoring, allocation, paper approval, broker or live-routing setting changed.

## 2026-10-15 — Repair silent market-data staleness and empty intraday selector

The operator found AAPL ending September 25 and an empty intraday symbol list.
AAPL had never been included in the strategy/research-ETF recurring daily jobs;
new catalog timestamps masked inherited old endpoints. Intraday recordings were
present, but selector requests scanned 4.07 GB of manifests twice and timed out.
Process health also discarded successful-exit backfill warnings and did not
verify delivered-data freshness.

The operator selected automatic daily coverage for all currently listed symbols
with supported identities. Added an application-owned, resumable recorder using
the existing audit/publication pipeline, bounded batches of 64 before strategy
calculations, per-symbol retry/quarantine, and preserved prior historical conflict
evidence. Initial catalog classification admits 3,133 current-listing candidates;
2,223 missing/ended/unresolved histories remain held for review. Each new capture
must still prove supported identity and continuity. All strategy publication,
approval, reconciliation and broker-environment checks remain intact.

Added persisted incremental manifest summaries (raw hash checks remain enforced),
explicit selector errors, independent one-minute daily/intraday coverage checks,
a required System health row, persistent Market Data freshness warnings, and
durable background alerts. Email delivery is still unconfigured and is explicitly
shown as disabled. AAPL now has 11,552 daily rows through October 14; its original
2,771 archive-conflict dates remain review evidence. The first recovery wave
published 14 symbols; the running app independently acquired, validated and
published a further 60. At 14:52 UTC, 126/3,133 candidates were current and 3,007
were pending/stale, including six quarantines. Four intraday symbols had already
advanced through today's 14:30 UTC window and the fifth was recovering. Acquisition
and audit failures remain isolated for inspection/retry.
Final acceptance confirmed all five intraday symbols completed that window with
zero outstanding gaps. The selector took 6.23s during concurrent append/calculation
work (0.11s warm); the old full-manifest timeout was not reproduced.

132 focused tests passed with zero failures/skips, as did Ruff and whitespace
checks. Live browser checks showed AAPL current and five populated intraday ticker
choices with OHLCV charts. The deployed ticker endpoint returned in 0.11 seconds.
System correctly remains degraded for the broad daily backlog. Deployment used
the normal service scripts and a temporary paper-approval pause; restored the
original enabled policy and CNH 1,000,000 cap after fresh matched reconciliation
(policy revision 10). Live remains disabled. No new allocation or execution
authority was introduced. Evidence: `var/reviews/market-data-incident-20261015/`.

Remaining acceptance: broad catch-up must progress to the expected completed
session, quarantines and unsupported identities need explicit resolution, and
intraday windows must keep advancing. See
[incident record](docs/market-data-freshness-2026-10-15.md). Do not describe pending
or reviewed data as healthy or silently substitute provider archives for research.

## 2026-10-15 — Dynamic rebalancing becomes a standing research comparison

The operator requested that all future research explicitly check dynamic
rebalancing alongside fixed-time-interval rebalancing. Recorded this requirement
in `AGENTS.md`, the continuous-research playbook and current research-state rules.
Predeclare dynamic trigger/threshold candidates and retain a fixed-interval
control; compare net Sharpe with return/drawdown guards, actual turnover/costs,
execution delays and chronological robustness. The current top-six/monthly result
is local to its tested recipe and universe. Strategy adoption continues to use
latest theoretical versus last adopted targets, including cash; adopted versus
actual held remains Trading housekeeping. No new experiment or trading policy
was requested by this standing rule.

The operator also authorized committing and pushing the completed rebalance work.
Publication is scoped to its source, tests, protocols, findings, reference
provenance and compact acceptance receipts. Generated reports, replay bundles and
downloaded PDFs follow the existing local-storage/backup convention. Concurrent
market-data changes and broker snapshots belong to separate work.
Before staging, all six research source files matched their accepted frozen
versions. The existing 119-passed/one-skipped behavioral test receipt remains
applicable; this publication session changed governance/docs and compact evidence
only. Fresh Ruff, document links, accepted analysis/runner hashes and both compact
receipts passed verification. GitHub's `origin/master` was fetched successfully.

## 2026-10-15 — P4.23 completed: joint selection width and rebalance threshold

Completed the operator-authorized X=4/6/8/10/12/all by
n=.05/.10/.20/.40/.60/.80/1.00/monthly grid on the current FR25/14 and F3/12
universes. FR25 is the selection parent; F3 follows the selected calendar as a
legacy activity-basis sensitivity, without a separate parameter optimization.
Missing daily macro observations use the approved previous-monthly snapshot
with original dates. No new observations, model recipe, eligibility gate,
fallback, price basis, allocation or execution authority was introduced.

All three annual selectors and the final trailing-three-year selector retain
6/monthly. Top four/monthly passes the performance checks in the first two
windows, but lacks a passing immediate neighbor; later windows have no passing
pair. On the descriptive full sample at 5bp per traded side, FR25 monthly
X=6/8/12 gives Sharpe 1.190/1.048/0.830, CAGR 13.05%/10.08%/6.96%, and annual
gross turnover 8.05×/7.01×/5.85×. The highest-Sharpe intramonth fixed pair is
6/0.80, with Sharpe 1.108, CAGR 11.98% and turnover 24.92×; this is not a
walk-forward selection or global optimum. At n=.10, widening six to eight reduces
turnover 58.36× to 48.32× and entry/exit share 74.1% to 68.1%, but Sharpe falls
0.966 to 0.614. More ETFs reduce traded notional, without establishing better
net performance or fewer individual fills. Full-pool validation remains later.

Acceptance: 576 fixed-pair scenarios plus 12 continuous walk-forward scenarios,
USD100k size checks, six native LEAN/Python checks, 98 independently verified
adoption policies, all 1,453 top-six target evaluations per parent, and 60 exact
parent economic replay matches. Joint 20,000-replicate stationary bootstrap at
63/21/126-session mean blocks covers 96 contrasts; it remains conditional and
descriptive, not selector-aware formal superiority. Membership, rank/gate/fallback,
reversal, concentration and ex-post raw-dollar-volume diagnostics are retained.

Accepted evidence: `var/research/selection-width-timing-20261015-v1/`.
Input manifest SHA-256:
`5aca451cdae47ef3f080f7a7c9476d5c99a2b15103be28e30657eeb615afcd78`.
Analysis SHA-256:
`089d4bdb8fe2594ab0b685aa9b0515b0f5c5e02127ca301a1fa939b9056f1087`.
[Results, grid and shared detail reports](research/selection-width-timing-20261015-v1/results.md).
The original timing report's presentation-only revision now shows the actual
macro carry/adoption flow, USD caption and cash-anchor annualization convention;
its accepted economics remain unchanged. Focused checks: 119 passed, one optional
skip; Ruff and rendered report/figure checks passed. The original Gârleanu-Pedersen
PDF hash still matches its 32-page reference receipt. Paper/live settings and
application strategy calculations retain their existing defaults.

## 2026-10-15 — P4.22 completed; joint selection-width/timing study authorized

Executed the registered fixed-top-six timing study on the pinned audited price
batch through October 14. At the operator's direction, missing daily macro
snapshots use the previous completed monthly snapshot with original timestamps
and carry-age receipts; prices/activity still update daily. The initially started
macro backfill was stopped after 393 successful study-scoped publications. Those
captures remain evidence and are excluded from the pinned-parent backtest.

All three annual FR25 selectors and the final trailing-three-year selector choose
monthly. At 5bp, FR25 monthly versus n=0.10: Sharpe 1.189916 versus 0.966457,
CAGR 13.0454% versus 10.0494%, drawdown -8.6558% versus -13.1009%, annual gross
turnover 8.0475× versus 58.3570×, with 70 versus 769 rebalance dates.
The study completed 132 full-size replays, USD100k diagnostics, six native LEAN
parity checks, independent event checks and 20,000 joint stationary-bootstrap
replicates at each of 63/21/126 sessions. Inference is conditional/descriptive;
no selection-aware superiority claim. Both parents exactly reproduce 70 monthly
target decisions. F3 retains the current legacy adjusted-price/source-volume
activity proxy, so it is not audited raw-activity transfer confirmation.

The initial runner stopped on a path-assembly error before any performance run;
its frozen artifacts remain in the parent directory. Accepted artifacts are in
`var/research/target-change-rebalance-20261015-v1/run-02/`, with results and shared
SOTA-format reports in `research/target-change-rebalance-20261015-v1/`.
Focused implementation checks: 114 passed, one optional skip before P4.23.

The operator then requested joint optimization of **X = maximum selected ETFs**
and **n = intramonth target-change threshold**, explicitly confirming that meaning.
P4.23 registers X=4/6/8/10/12/all eligible and n=.05/.10/.20/.40/.60/.80/1.00/monthly
before joint performance results. Use the same net-Sharpe guards, annual causal
selector, cost/delay scenarios, retained account state and monthly macro rule.
Compare with top-six monthly and each same-X monthly control; attribute actual
membership entry/exit turnover without assuming every change is a rank crossing.
Current parent pools first; expanded-pool validation remains later and cannot
rescue the previously rejected expanded-FR25 arm. No funding, monitoring, broker,
approval or live setting changed.

## 2026-10-15 — Target-change threshold protocol and literature reference

Operator clarification supersedes the earlier review's proposed held-weight
strategy trigger: strategy change compares the latest theoretical target with
the **last adopted rebalance target**; Trading housekeeping compares the **latest
adopted target with actual held weights**. Both use absolute differences when
aggregated. Only the first belongs in this threshold study. The existing per-ETF
paper alignment tolerance and all approval/routing controls remain unchanged.

The operator selected **net Sharpe with return/drawdown guardrails** and explicitly
authorized the **current FR25/14 and F3/12 universes first, full-pool validation
later**. Recorded P4.22 in `docs/target-change-rebalance-plan.md` and the matching
`research/target-change-rebalance-20261015-v1/protocol.json`. Planned FR25 threshold
selection with F3 transfer check, eight preset thresholds, monthly/daily controls,
three-year causal selection and 2024-2026 validation, six cost/delay scenarios,
neighbor stability and a monthly fallback. Numerical guardrail tolerances are
declared design choices, not fitted results. Existing history is already inspected;
the final candidate must be frozen before prospective observation. The previous
expanded-FR25 rejection is not reversed by this scoped timing experiment.

Downloaded the published 32-page Gârleanu-Pedersen (2013) paper from the author's
NYU-hosted PDF to `research/references/supplemental/`, ID T01. Verified title,
authors, journal, DOI and rendered title page; read the introduction and selected
model/policy/conclusion pages. SHA-256
`b9b01f48bd7ff0ce0431615d88b76f8a076b6593cc1d7765bd6ec2eb617473ab`.
Provenance and reading scope are in the supplemental manifest and README. Its
quadratic-cost gradual-trading solution motivates the cost/persistence trade-off,
but does not derive this strategy's L1 band or its optimal threshold.

Plan and reference only: no backtest was run and no strategy, monitoring, funding,
broker or alignment setting changed. The recorded app price batch remains a
planning reference until preparation verifies every immutable input hash. Next:
freeze inputs/code/models, reproduce monthly controls and test independent event
semantics, then run the finite protocol and review all outcomes before follow-on work.
Validation: protocol JSON, declared pool/grid/fold/family consistency, PDF page
count/DOI/hash, local document links and whitespace checks passed. No behavioral
code changed, so the earlier test count is not presented as a new test run.

## 2026-10-15 — Daily target-distance rebalance review

The subsequent operator clarification and P4.22 entry above supersede this
review's recommendation to use held weights for the strategy trigger.

Reviewed the operator's proposal to recalculate theoretical holdings daily and
rebalance within the month when total absolute weight differences exceed a
backtested threshold (example 0.10). Source and running-app inspection distinguish
three contracts: latest indicative targets refresh with published observations;
strategy reports hold simulated shares between monthly events; paper alignment
compares marked broker holdings with existing approved monthly/handover targets
and can stage a correction at 0.02 absolute drift in any individual ETF. Cash is
in NAV but is not a separate row in that existing drift test. The current test is
neither a portfolio L1 threshold nor a daily signal adoption policy.

Read-only operational receipt at 20:54 Asia/Shanghai: control revision 6 has F3
at 100% active paper capital and an already-pending FR25 100% change effective
October 15 close. Paper alignment reports aligned, valuation October 14, approved
target date October 7. No control, proposal, approval or broker state was changed.
The published simulated F3 and FR25 reports, both valued through October 14,
have latest-target versus held-weight L1 distances including cash of 0.225823863
and 0.418602257. Their last scheduled rebalance is October 1 and next is November 2.
These snapshots show that a 0.10 rule would currently flag their monthly simulated
books; they are not broker holdings or a historical simulation of the new policy.
Evidence: `var/reviews/rebalance-20261015.json`, serving publication
`d6269697d1c44951042aa9aa953514cdcafe7bf7be5aaa4acaa967047d64620d`, price batch
`ad78b10e053829e5fd2d0d18fc82c2c572cb1901a1cc1bdecd01fb727bfa6472`.

Review conclusion: faster response is mechanically plausible; higher net returns
or better risk-adjusted performance are unestablished. A future registered study
should isolate rebalance timing from signal/model changes, compare monthly HOLD
and the existing paper drift policy separately, and add daily full and monthly
plus threshold variants. Measure distance from actual filled, marked holdings,
not yesterday's target; use absolute differences including cash. An L1 distance
of 0.10 corresponds to a 5% transfer between two assets (10% gross traded notional
when cash is unchanged), not a 10% one-way transfer. Evaluate costs on actual
noncash fills, next-session execution and delayed fills. Threshold selection must
be causal and stable, with costs/drawdowns/whipsaws and multiple comparisons
reported; already-inspected historical periods cannot become untouched holdouts.
Use app-owned versioned logic, pinned audited published histories and verified
hashes, explicitly adjusted-return versus raw-activity bases, the full supported
candidate pool and declared admission/membership/FX/vintage limitations. Existing
frozen-universe strategies remain controls. This is a recommendation, not a new
strategy implementation, research run or change to the existing research queue.

Do not use the old daily Alpha101 grids to reject or validate this different
proposal: the October 11 second review superseded their frequency/threshold
conclusions and did not rerun the full grid. Existing focused tests passed:
109 passed / one optional skip in monthly staging, initial allocation, tracked
runtime and research-review repairs. No new behavioral code was introduced.

## 2026-10-14 — Audited ETF expansion and frozen candidate rejection

Enabled the accepted 38-addition recorder wave after FR25 paper readiness.
Thirty-nine of 41 recorder entries published; BWX is now an evidence-bound
code-level hold (issuer listing October 2, 2007 versus provider October 11),
alongside the existing XOP hold. The study pins catalog
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
Fifty of 52 reviewed candidates have complete common-window observations;
CPER's zero raw volume on August 23, 2018 is unsupported by the current activity-model contract and excludes it from this study; the audited bar itself is present.
No missing data was filled or conflicting history spliced.

Frozen protocol `401c84e7e70d548343f02f9eea3d4afcb913d4048028ed0b30597598825c0d38`
compares the original and expanded FR25 logic on common history from June 2018,
with 70 monthly decisions from January 2021. Models are app-owned, with causal
features and completed training labels. Explicit eligibility masks preserve full
pool ranks and defensive cash. Current-cohort membership/mandates and historical
price-publication availability remain retrospective limitations.

Expanded FR25 fails: 67.73 bp implied annual cost exceeds 44 bp, and calibration
rank IC is −0.01463. Full expanded portfolio replay is withheld under the frozen
pre-test. The original control passes (43.17 bp, IC 0.03545); its 5/10 bp native
replays and URTH match Python accounting to the cent. No post-result tuning or
expanded-return claim. [Report and all-constituent attribution](docs/etf-expansion-findings-2026-10-14.md).
Next research requires a separate class/volatility-aware protocol; this result
does not establish that every larger-pool strategy will fail.

Also repaired nested governed-parent hash receipts, added explicit model-worker
bounds for finite research, and verified broker previews cannot submit executable
orders or accept a different account. Final deployment/regression acceptance is
recorded in the [execution session](docs/execution-readiness-2026-10-13.md).

Final acceptance: 1,713 full-suite tests passed with 55 optional skips, plus five
broker-preview/frozen-runner checks. The final 16:23 UTC deployment restored the
same paper policy at revision 8 after matched reconciliation; calculations
published revision `28d939b195f7a91c47ac1812c9a60ed27f54cacb60b9a28b916fc94c12e36b76`.
The refreshed FR25 preview at 16:34 UTC has no blockers or routing warnings and
unchanged target weights. Allocation remains F3 100%, no pending change, ledger
270 records. Final health review found stale event-dispatcher heartbeats during
successful large batches. Added progress heartbeats only after durable attempts,
retaining failure visibility and the 30-second stale check; 14 focused tests
passed, including one new test. Only that worker was restarted for this fix.

## 2026-10-13 — Execution generality implementation and admission preparation

The user accepted the inventory and authorized FR25 readiness, ETF expansion and
subsequent larger-pool backtesting. Implemented explicit strategy membership,
mixed-allocation union resolution, request-local audited-input reuse, complete
FR25 financial/raw-activity binding and account-bound conId routing admissions.
Research and paper targets match with financial forecasts and abstention. All 14
FR25 broker simulations succeeded without executable orders; all 38 additions
also matched issuer/ISIN contract discovery. Existing capital remains F3.

Reconciliation matched without warnings; a broker sync returned no open orders.
Historical partially filled ledger records are preserved. Guarded deployment
completed at approximately 15:45 UTC, matched post-restart reconciliation passed,
and the existing paper policy was restored without changing its capital cap.
App calculations caught up; the conditional 5% FR25 / 95% F3 preview has seven
net orders and no blockers or routing warnings. It was not activated. The
reviewed recorder configuration subsequently published 39 of 41 entries; BWX
and XOP retain listing-boundary holds. Evidence, limitations and acceptance:
[execution session](docs/execution-readiness-2026-10-13.md).

## 2026-10-13 — P4.16d stage 1 inventory delivered for review

Continued the agreed research sequence with reference inventory and admission
planning. Frozen bundle: `research/etf-universe-inventory-2026-10-13/`; report:
[ETF inventory and first wave](docs/etf-universe-inventory-2026-10-13.md).
299 symbol/regime records represent 298 provisional fund identities, with 181
proposed peer/overlap buckets (117 singleton buckets, not independent breadth).
Propose 38 additions alongside the existing 14; 23 additions already have
published histories (22 require refresh), and 15 need initial acquisition/audit.

Pinned committed catalog `38153d09e24666838a4737dfe32423fe9832b12c49132b0d41418c8e1355378f`,
with October 12 completed-session cutoff. Verified the catalog manifest plus all
52 matching audit/bar hashes. Inventory totals: 48 audited with limitations,
four review and 247 absent. Current Nasdaq/issuer snapshots are reference
metadata only; no issuer returns, yield, AUM or provider price archives entered
selection or a study. Unknown identifiers, currency, inception/closure and
historical classification remain explicit gaps. Permanent local candidate IDs
are not certified security-master identities. No runtime registry was changed.

Corrected a durable metadata error: the old P3.8 note called HYXU delisted in
2020. Primary issuer/SEC/OCC evidence establishes a 2025 name, ticker and mandate
transition to EUHY, with the exchange symbol effective November 3. Retained two
regimes under the same fund reference; stale HYXU history still ends April 1,
2020, and both regimes remain quarantined. No history splice, refreshed price
claim or audit promotion. Direct SEC/OCC byte capture returned 403; their web
retrieval and source URLs are disclosed, and the current issuer page is retained.
XOP's independent listing-boundary hold remains enforced.

Proposed rules are frozen before comparison: explicit adjusted versus raw input
basis, causal liquidity/spread checks, one representative per conservative
exposure bucket, dated mandate/membership rules and a separate risk-normalized
momentum comparison. No parameters were selected using strategy outcomes.
Five file samples and 52 compressed files support storage-density estimates:
about 14.9 MiB for 52 or 85.8 MiB for 299 daily histories at 15 years. These are
file-capacity scenarios, not measured LEAN memory or throughput. P6.15 remains
open; no concurrency or Docker limit changed.

Validation: 11 focused tests pass; offline deterministic rebuild and Ruff pass.
The source manifest binds all 16 inputs, including losslessly compressed
reference snapshots. Next: review the first-wave proposal/rules, complete its
identity metadata, then app-owned acquisition, audit and staged publication.
Stopped at the registered review boundary. No new strategy calculations,
allocation, orders, app restart or recurring agent job was initiated.

## 2026-10-12 — Repository restructuring, verified archives and maintenance fixes

Completed the authorized source/documentation cleanup without a trading-service
restart. Extracted six UTF-8 page/report templates from large Python literals into
packaged presentation resources, removed duplicate/unreachable templates, separated
API contracts and pure risk-parity preview construction, and removed eager API
initialization when importing web helpers. Historical import names and routes remain.
Wheels and frozen LEAN bundles include the resources; bundle hashes, serving
signatures and calculation source guards cover the new dependencies.

Fixed empty preview division-by-zero, silent duplicate input overwrites, missing-FX
server errors, invalid CNH base rates and risk-weight rounding that could exceed a
35% cap at 35.01%. Rounding now preserves both the total and cap, including invalid
volatility/precision checks. The baseline's only failing test referenced Alpha101's
old scratch PDF location; the retained reference has the exact original hash, now
enforced before formula extraction. No frozen study was rewritten or input source
substituted.

Five static page handlers preserve identical HTML and improve local composition
5.6–16.7 times (Trading 1.01 ms to 0.061 ms); live data remains per-request API data.
Streaming SHA-256 on a synthetic 32 MiB file reduced traced peak allocation from
32 MiB to 0.38 MiB and median time from 22.1 ms to 14.0 ms, preserving exact hashes.
These are scoped microbenchmarks, not claims about database or research throughput.

Five current memory/plan files shrank from approximately 941 KB to 138 KB before
this entry; complete byte-preserved originals occupy 339 KB in verified ZIPs under
`docs/archive/`. Added the documentation index, current code/maintenance and script
guides; corrected stale infrastructure status, superseded research conclusions and
missing rendered-report links. All open milestone IDs remain except redundant P7.5
Kanban reminders, retained in history; the start/end-session operating rule remains.
Generated reconciliation snapshots are ignored by Git while retained on disk.

Seven log files compressed from 92,751,016 to 6,275,459 bytes, with SHA-256 receipts
and decompression readback. Two Windows append logs were detached by atomic rename;
new operational appends were verified. No open stdout/stderr stream was truncated.
The explicit archive command rejects unsafe paths, open Windows writers, recent
closed files and changed contents; interrupted operations retain source evidence.
No recurring retention task, database change or market/broker evidence deletion.

Validation: baseline 1,640 passed / one stale-reference failure / 56 skips; final
full suite **1,691 passed / 55 optional skips**, two dependency deprecation warnings.
Ruff including additional bug-oriented rules and `git diff --check` pass. All 358
local links checked at close-out preparation resolve; both ZIP inventories/hashes,
all six extracted template values and five response bodies verify. The built wheel
renders outside the checkout, and a frozen bundle imports its own report resources
and rejects template tampering. Receipts and test XML: `var/maintenance/`.

Runtime inspection found paper auto-approval enabled, 270 stored orders including
ten marked partially filled, and the expected source-change calculation guard.
It also reported a ClickHouse archive INSERT timeout; no ambiguous write was
manually retried. Running services and approval/allocation policy were left intact.
**Next operational action:** a controlled guarded restart with current broker-order
review, then confirm source-guard recovery and analytics freshness. This is not a
claim of production deployment. No order was submitted/cancelled/resubmitted by
maintenance, and live controls remain unchanged. Existing execution/reference edits
were preserved; no commit or push was made.

Recent decisions and incidents. Earlier entries, including entries that were appended
out of chronological order, are retained in the verified
[history archive](docs/archive/README.md). Historical research conclusions may be
superseded; [research state](docs/research-state.md) is the current summary.

## 2026-10-12 — P4.19 retrospective execution comparison and full-session reference audits

Continued the next research item at the operator's request. Extended the app-owned collector to
original/routed regular sessions using the shared US calendar and existing bounded queue. Added
strict OHLC/volume/WAP checks and a separate `execution-reference-audits` publication. It verifies
the governed catalog, immutable input hashes, the correct per-symbol storage publication and row
readback. Known subsequent splits, unsupported raw basis, missing intervals and invalid WAP are
excluded. Provider quantity is not relabelled as shares; the common scale cancels in session VWAP.
Historical action-vintage, price reconstruction and filtered-feed limitations are explicit. This
publication is authorized only for retrospective execution diagnostics, not strategy input admission.

Guarded app deployment captured 30 full sessions, in addition to the existing 34 windows. All 64
captures match ClickHouse and their original source hashes. USO/DBB configured-contract gaps remain;
no XLE/XLB permission conclusion follows. Analytics and IB health are good, with no collection error.
The collector remains coverage-degraded for those explicit legacy gaps.

New frozen study `var/research/execution-references-20261012-v1/` matches 27 complete orders across
seven ETFs / five sessions; eighteen other filled orders lack execution details. Actual-fill cost is
1.228 bps versus original TWAP, 1.185 bps versus routed TWAP, 3.769 bps versus governed daily close,
and 9.471 bps versus full-session WAP/volume aggregation. Close leave-one-session-out results change
sign (-6.436 to 31.268 bps). No cross-date-delay sample exists. **Decision: retain current execution
policy; no achievable style effect is established.** The October 11 zero-coverage audit is untouched.
Report: `docs/execution-reference-findings.md`; updated plan, state, Kanban, architecture and contract.

Validation: 100 focused tests passed / one disposable-ClickHouse test skipped, seven final analysis
tests passed after the regular-session boundary check, Ruff passed, frozen analysis reproduced exactly.
Protocol SHA-256 `165bed086e866153b9c365947a4340aa83aa79dec5c1864a2ea12820c8f4a6f1`;
manifest `a6f38fa251b4652346a521d893109d28207110e0508d6ebbba3cf77a18193172`;
analysis `38539a975cb310321aed5f09c121c09158d24b42d46a78cc1f29a05ca2ad5b58`.
Deployment receipts: `var/research/benchmark-qualification-20261012-before.json` and `...-after.json`.
Paper control revision 5, F3 100%, no pending allocation and 270 orders / 45 filled all match before
and after. No order submission, live enablement, gate weakening, capital change, commit or push.
Preserved the prior reference-folder cleanup and runtime reconciliation changes.

Next: P4.16d candidate inventory/comparable peer groups, with P6.15 measured resource review before
large-scale calculations. P8 minimum paper execution contract and P5.11 intraday admission remain
separate prerequisites; this diagnostic does not unlock either.

## 2026-10-11 — P4.19a app-owned benchmark collection and verified publication

Following the operator's “go ahead”, implemented the next timing-study prerequisite. Added an app
lifecycle worker with a bounded shared IB data-request queue, separate original/routed windows,
contract identity checks, immutable request/response/audit attempts, restart-safe retry cooldowns,
source-hash and full-window validation, and an independently published coverage report. Its GET
endpoint only reads state; collection does not depend on opening the blotter. Publication validates
retained source captures before advancing the benchmark dataset. No missing observations are filled.
Price basis remains provider historical TRADES, explicitly not independently certified trading-time
raw units; `research_approved: false`. Volume/WAP is retained for later qualification.

During guarded deployment, IB returned complete older minute bars alongside warning 2188. The former
handler rejected them. Corrected this advisory handling only for windows ending at least 15 minutes
earlier, still requiring historicalDataEnd and complete coverage; current-window/actual permission
errors remain failures. Natural cooldown retries recovered supported windows. Failed and partial
attempts remain immutable evidence. At 14:28 UTC, all 34 captured windows validated against raw hashes
and were identical to their ClickHouse documents, covering 30 TWAP orders. Publication:
`e17de3ea798bd689908317e13e3a62116cd944072938da589e71dc47aa6ac132`.
Two other explicit windows are legacy USO/DBB orders with no configured IB instrument contract; ten
legacy TWAP orders have no explicit window. The coverage service remains degraded for these real
gaps. No new contract was admitted just to remove that status. Three filled limit orders are outside
this TWAP collector and 225 unfilled orders are not requested.

96 focused tests passed, one disposable-ClickHouse integration test skipped (no explicit disposable
workspace); Ruff and scoped whitespace checks passed. Tests cover app lifecycle/no HTTP dependency,
deduplication, original/routed dates, durable failure/restart, bounded queue/shutdown, tampering and
publication withholding, filtering and IB warning/permission behavior. Actual deployment publication
and readback were verified separately. Receipts/test XML and read-only verification script are under
`var/research/benchmark-collection-20261011-*` and `verify_benchmark_collection_20261011.py`.
Before/after allocation controls match exactly: revision 5, F3 100% paper capital, no pending allocation;
270 orders / 45 filled remain unchanged. Paper Gateway, Postgres and ClickHouse health passed.

The automatic research refresh after restart is separate from collection. At the publication check,
it was still replaying tracked strategies with no analytics errors, while serving the previous complete
publication current through October 9. Two IB SDK thread teardown traces (`serverVersion() is None`
during disconnect) appeared in the runtime log; captured source validation and Gateway health passed.
Retain this SDK lifecycle incident for the robustness review rather than treating it as a permission
failure or suppressing unrelated broker errors.

P4.19a is partial overall: the collector is delivered, but trading-time raw-unit, matched raw-close
and full-session VWAP qualification remain explicit prerequisites for P4.19. No execution-style ranking
or new return study uses these operational captures. The frozen v1 evidence audit is unchanged.
Updated the research plan, architecture, operations guide and Kanban with this distinction.
P6.15 worker-resource review remains queued; Docker and worker concurrency settings are unchanged.

## 2026-10-11 — P4.19 evidence audit and queued worker resource redesign

After accepting the revised research priorities, the operator requested the next research item.
P4.19 preflight disproved the assumed retained benchmark coverage. Froze the protocol, source and
read-only PostgreSQL/ClickHouse snapshot in `var/research/execution-timing-20261011-v1/`: 270 paper
orders, 45 with fills (42 TWAP), 27 with complete execution details, 134 individual executions across
five sessions, 32 explicit TWAP windows, zero published benchmarks. Eighteen orders lack detailed
execution history. All costs remain null; no style ranking is possible. Added an offline analyzer
using the existing benchmark-window/minute-price functions, validated hashes and original intent,
explicit missingness, and gross-notional signed aggregation. Frozen output reproduced without writes;
25 focused tests and Ruff passed. Full findings in `docs/execution-timing-findings.md`. P4.19 audit
complete; comparison blocked, with P4.19a app-owned collection/audit/publication registered as next
prerequisite. No broker requests, price downloads, database writes, app restart, allocation or orders.

The operator also questioned Docker-limited worker concurrency and separate memory. Read-only host/
Docker checks confirmed 16 CPUs, 31.55 GiB host RAM, 15.39 GiB Docker RAM, and ClickHouse around 2.53 GiB.
The scheduler uses a fixed 4 GiB/run and 2 GiB service reserve, limiting native LEAN to three runs;
model preparation and Python reference calculations already run on the host. Registered P6.15 to
measure actual working sets, duplication, stage serialization, whole-batch throughput and service
latency, then compare host-native LEAN and right-sized container scheduling. ClickHouse's columnar
disk storage/cache is not a shared Python/.NET heap. No Docker/WSL setting changed. Expanded-universe
planning now includes this scaling dependency; increasing Docker's cap is not preselected as the fix.

## 2026-10-11 — Agreed research priorities and substantial ETF-universe expansion

The operator accepted the second-review recommendations, asked to record them in the research plan,
and emphasized that the tradable ETF universe should expand substantially. Updated
`docs/signal-decay-and-alpha-plan.md` with the accepted order, the minimum paper-execution binding and
mixed-universe prerequisites, conditional 5% FR25 / 95% F3 paper preview, zero alpha allocation pending
incremental evidence, and fill-based exit/horizon requirements. Strengthened P4.16d into a staged
programme: inventory/taxonomy and gap matrix, audited publication waves, scalable app/paper contracts,
then controlled full-pool research. Hundreds of candidates is a capacity design direction, not an
admission quota. Candidate admission and portfolio allocation remain separate. Inventory planning can
proceed before publication; expanded-universe backtests cannot. Cross-linked the ETF roadmap and
research state. Documentation-only follow-up; no research runs, instrument admissions, allocation or
broker actions. Validation: reviewed the changed sections and checked local links/whitespace.

## 2026-10-11 — Second research review, repairs, paper-gate assessment and P4.18

The operator supplied the earlier DOCX review and requested code/research repairs, an assessment of
higher-frequency ETF alpha and TP/SL/breadth, paper allocation readiness, and the next executable
research item. Attached-document prose was treated as evidence, not instructions. Existing uncommitted
repairs by the other agent were preserved. The operator explicitly chose paper allocations first.

Implemented remaining monthly scheduling (including unchanged monthly targets), strict prior-close
exit proxy/entry timing, no stale-close substitution, reachable re-entry, shared audited raw price/volume
history wiring through studies and app workers, localized missing ADV windows, matched tilt payoff
and 3x incremental-cost hurdle, positive information for zero-cost mappings, and calendar-matched
turnover calibration. Retained and tested the other agent's funding-anchor, momentum-singleton,
hierarchical score population, tied-IC, alpha-43/53, 63-return sizing and LEAN cleanup repairs.
Screen verification no longer mutates frozen evidence. Daily event metadata is causal and its monthly
control is regenerated from the same raw activity inputs. Source snapshots and reviewed input/output
receipts are retained. Cost-screen presentation now reports matched payoff, not full-book IC margins.

Evidence: `alpha101-screen-20261011-v4` yields 0/16 standalone passes; `alpha101-tilt-20261011-v3`
yields 4/3/3 passes at 5/10/20%, replacing 12/12/5. `turnover-gate-20261011-v2` fixes CP/M1's
130-versus-70 calendar mismatch. `strategy-review-20261011-v3` holds the fixed FR25/5% monthly pair:
12 replays, all 70 target decisions reproduce the actual app worker, holdings/cash/fee equality, and
native LEAN parity for both headline arms. FR25 13.091% CAGR / 1.193 Sharpe / -8.656% maxDD versus
alpha 12.988% / 1.182 / -8.253%, on 2021-01-04–2026-10-08 at 5bp. Alpha trails on return and Sharpe
at all cost/delay scenarios. Its six-month paired interval spans zero. v1's cash-padded pre-2021 window
is withdrawn; v3 is canonical. Older P4.17c-f grids were not all rerun and are explicitly superseded.
Full-sample/hindsight, annual-frequency and Sharpe-difference claims were corrected in current docs.

P4.18 was preregistered in the plan before outcomes: monthly 10% annual-vol target, 63 prior daily
returns, no leverage, max 1pp CAGR sacrifice/min 2pp drawdown improvement, matched-average-exposure
control, 5/10/20bp and 0/1 delay. The shared app signal class implements the calculation. Eighteen
replays plus native parity completed in `volatility-target-20261011-v1`: 10.170% CAGR / 1.113 Sharpe /
-8.719% maxDD, worse than FR25 and the constant 87.404% scale control. All six scenarios fail the
risk/return hurdles. Close this fixed rule without parameter tuning; no strategy registration/promotion.

Paper gates: catalog/candidate list/backend now use a shared conservative execution-contract check.
The operator manually checked XLE/XLB and reported permission, then logged into Gateway. Read-only
probe at 13:12 UTC confirms the expected paper account at 127.0.0.1:4002; fresh reconciliation has
zero breaks, six positions, 38 broker fills, no unmatched fills/orders. Read-only ISIN lookup verifies
XLE conId 4215217 and XLB conId 4215200 (`strategy-review-20261011-ib-identity.json`). Permission
is not presumed denied and connection/reconciliation are no longer blockers. The remaining genuine
implementation gaps are FR25 financial-selection and audited activity binding in the paper target
builder, and combined-universe resolution/raw sizing/reconciliation in allocations. Do not just remove
the gate. The minimum same-venue 14-ETF contract is next; the entire multi-venue P8 vision need not
precede two US ETFs. No broker orders, proposals, promotions or capital changes were submitted.
F3 retains 100% paper strategy capital at control revision 5, with no pending change.

Validation: 307 focused regression tests plus 2 full frozen artifact reproduction tests passed (309).
Changed/new Python passed Ruff; `git diff --check` passed with Windows CR-at-EOL handling. Tests
were targeted, not the entire repository suite. Guarded dashboard restart loaded the repairs. App-owned
calculation revision `7b981dee475b11b9c849e0ed3efbf02847ca17f6fafaab742afafb6343a62d6d` completed.
One strategy-serving ClickHouse insert timed out; the last complete publication was retained and the
next app cycle succeeded without a manual INSERT retry. Final serving publication
`79570b6886586f0920823cee4ef8adae62da6f85461e630fd80deab18639796d` is current through 2026-10-09;
all seven monitored strategies have current app reports, analytics errors are empty, and routing warnings
are empty. Snapshot: `var/research/strategy-review-20261011-deployment.json`. No source changes
were committed. The full review is `docs/strategy-review-2026-10-11.md`.

Next actions: finish minimum 14-ETF paper execution parity before a proposed small FR25 pilot;
P4.19 from retained execution evidence; P4.16d audited comparable ETF breadth; preregister signal
horizon and incremental contribution before more alpha/TP/SL grids. Actual fill-based sleeve exits,
explicit risk units and gap/session treatment precede claims about tradable TP/SL. No positive
Alpha101 incremental edge is established, and no new alpha budget is recommended.

## 2026-10-11 — Peer review of the Alpha101 work: five findings, all confirmed, all fixed, studies re-run

The operator had a second agent check my work. It reported five implementation defects. I reproduced every one
against the code before touching anything, and **all five were real** — this entry records them, the fixes, the
re-runs and the one conclusion that reverses.

**The findings and what I reproduced.**

1. *The hold arms were not holding.* The daily and exit studies — and both of their controls — wrote a decision
   row every session with the same target weights, which rebalances back to those weights as prices drift. The exit
   study's HOLD arm wrote 1,448 rows where the monthly strategy has 70 decisions, so the arms were a daily
   rebalanced process, not the monthly strategy they were compared against. The reviewer was right that this makes
   the study measure something else.
2. *Re-entry was unreachable.* The branch sat behind an `elif held:` guard, and the exit had just set `held = {}`,
   so it could never fire. A synthetic run showed the book staying untilted while the signal re-aligned, and the
   211 "re-entries" the arm reported were re-tilts of a position that was still on.
3. *Look-ahead in the P&L exits.* `should_exit` read the close of the very session whose target it produced: a
   decision for today's open using today's close.
4. *Alpha 43.* It divided every historical volume by the **latest** 20-session average dollar volume rather than
   each date's own: 0.450000 against 0.600000 on a synthetic series. I audited all sixteen alphas against their
   published formulas; 43 was the only defective one, and it is the one the monitored strategy runs, so this was
   the finding that reached production.
5. *Rank IC ties.* `argsort(argsort(...))` gave tied values ordinal ranks in sorted-ticker order, so identical
   signal/return pairs scored 0.657143 or 0.371429 depending only on labels, and the statistic disagreed with
   textbook mid-rank Spearman (0.371429 against 0.441367).

**Fixes.** `rolling_adv` supplies alpha 43 with each date's own rolling window; `midranks` gives rank IC averaged
ties; both studies and both controls emit a row **only when the target changes**, so between events the engine
holds shares and drift trades nothing; re-entry is evaluated when no tilt is held; the P&L exits read only closes
strictly **before** the session they trade, with the entry base taken from the entry session's own close (known
before every later decision, so not look-ahead). Six regression tests pin these, including equality with the
published alpha-43 formula and label-invariance of rank IC. The audit cleared the other three `adv20` users and
confirmed `signal_decay.rank_ic`, which feeds the monitored decay panel, already averaged ties.

**Re-runs, because annotations would not have been enough.** The code changes invalidate the artifacts, so the
affected studies were re-frozen under **v2** roots whose protocols record the correction, with the cross-study
chain aligned: the measurement now reads the corrected screen, the surface reads the corrected replay, the daily
study reads the corrected surface. The v1 roots are kept and marked superseded. Screen v2: 0 pass, 15 reject, 1
insufficient — unchanged. Daily v2: the frontier is reproduced, 142.7bp at no band for 96.5% against 41.6bp at a
300% band for 103.9%, statistically the monthly arm at 41.7bp and 104.1% — unchanged. The monitored strategy
recalculated under revision `c519e86cd455` with **0 parity differences** on all five M1-family runs; its published
figures barely move (11.17%/1.1025/−20.28% against 11.18%/1.103/−20.28%), because one alpha of sixteen enters a
rank average, but the code behind them is now right.

**The conclusion that reverses.** *"Exiting early is worse than holding" is withdrawn.* With a working re-entry,
FR25's best in-sample arm on total return, CAGR and Sharpe is **X = 5% with flip-exit-and-re-enter** — 105.4% /
13.32% / 1.212 at 53.2bp — against **X = 5% held** at 105.0% / 13.28% / 1.207 / **1.609 Calmar** at 41.0bp and the
untouched book at 106.0% / 13.37% / 1.218 at 41.0bp. So the re-entering rule buys about +0.4pp of net return for
about +12bp/yr of cost, plain exiting without re-entry is still clearly worse (103.9% at 43.5bp), and the SOTA
still prefers holding outright. My earlier claim held only because the re-entry arm could not re-enter — an
error I shipped and the reviewer caught. *"5% HOLD is the best configuration" is qualified*: it remains the best
on Calmar and drawdown, and the corrected best on the other three metrics is 5% with re-entry. *Nothing is
established*: 0 of 20 family-adjusted contrasts differ from the untouched book on either base at Holm p < 0.05,
exactly as before.

**The monitored strategy keeps the operator's chosen recipe.** `research_fr25_alpha_tilt_5_v1` is still the X = 5%
held arm, still monitored, still `promotion_eligible=False`, `execution_enabled=False`, with the 14-ETF execution
contract reason. Its spec sheet already disclosed that the evidence was not established; it now also sits behind
this record, which states that it is no longer the single best in-sample arm on three of five metrics. Switching
the recipe is a one-line parameter change and the operator's decision — it is not made here, because the corrected
advantage carries no statistical support.

**Lesson worth keeping.** The frozen-study discipline did part of its job: the artifact tests failed the moment
the code changed. What it did not catch was a *modelling* error — a row schema that silently meant "rebalance
daily" rather than "hold", and a helper (`adv`) whose scalar return invited the wrong use in one of sixteen
alphas. The fixes add tests at that level: what a submitted target means, and each alpha against its published
formula.

Full record: `docs/alpha101-peer-review-corrections.md`.

## 2026-10-11 — Session committed and pushed (`80ff109`), with a GitHub routing workaround on the way

Committed the session's work and pushed it: `80ff109` — "Research: Alpha101 tilt promoted to monitoring, exit
rules, and faster calculations" — 71 files, +13,575/-38, on `master` and on `origin`. The full test suite was
green immediately before the commit.

**What was staged, and what was deliberately not.** `git status` reports about 15.5k untracked files in this
working copy: research reference PDFs, generated report directories, and the `var/` evidence roots. Committing
those as a side effect of "commit and push" would have been wrong, so I staged explicitly — `src`, `scripts`,
`tests`, `docs`, `config` and `log.md` — which is exactly the session's code, tests and records. The runtime
artifact `var/reconciliation/ib_paper_reconciliation_latest.json` (tracked, modified by the platform, not by me)
was left unstaged for the same reason. If those 15.5k files should be versioned, that is its own decision with
its own `.gitignore` discussion, not a rider on this commit.

**The push failed twice, for a network reason rather than a git one.** The first attempt died with
`RPC failed; curl 55 Send failure: Connection was reset`; retries then failed with `Failed to connect to
github.com:443`. Diagnosis: DNS resolves `github.com` to `20.205.243.166`, which does not accept connections
from this machine, while `140.82.121.4`, another GitHub edge, is reachable — and `github.com:22` and
`ssh.github.com:443` are reachable too, but no SSH key exists on this machine, so SSH was not an option. I had
already set `http.postBuffer` and `http.version=HTTP/1.1` as the usual transport mitigations, which did not help
because the problem was routing, not packet size.

**Workaround.** A temporary localhost-only CONNECT relay (`tmp/connect_relay.py`) that accepts the `CONNECT
github.com:443` git sends and dials the reachable edge instead. TLS, SNI and certificate verification are
untouched: git still believes it is talking to `github.com`, and the relay just forwards bytes. `git -c
http.proxy=http://127.0.0.1:8899 push origin master` then completed cleanly (`6a7e997..80ff109`). The relay was
stopped afterwards and both temporary git config knobs were reverted, so the repository configuration is
exactly as it was found. If this recurs, that is the recipe — and the durable fix is a hosts entry or a working
proxy on this machine, which needs the operator.

## 2026-10-11 — The 5%-HOLD tilt becomes a monitored strategy

The operator asked to build the measured best configuration into a proper strategy with a full spec sheet and
add it to the monitored set. It is done: **`research_fr25_alpha_tilt_5_v1` — "FR25 + 5% Alpha101 family tilt"**
is registered, calculated by the app's own services, published with the standard report and decision diagram,
and listed among the monitored strategies.

**How it is built.** The tilt is a real overlay rather than a frozen decision schedule:
`alpha101_tilt_overlay.Alpha101FamilyTiltOverlay` ranks only the names the book already holds by the
equal-weight mean of the sixteen registered alphas' rank scores, moves 5% of NAV from the bottom of that ranking
to the top, and shrinks as a whole so no name can breach the 45% cap or go negative. It is appended last in the
FR25 chain, preserves the symbol set and the gross that the defensive fallback protects, and is validated
against a single registered parameter set so no strategy can be registered with a budget, an alpha list or a cap
that was never measured. The spec-sheet diagram gained three steps describing exactly that.

**Verification.** LEAN and the reference engine execute the identical overlay: the native attempt **passed
parity with 0 differences**, and a test asserts the deployed rule reproduces the measured study rule bit for bit
— that test caught one missing diagnostic (the over-cap counter) during the build, which is the sort of drift it
exists to prevent. Nine focused tests cover the rule, the plugin registration, the tampering guard, the diagram
text, the fallback contracts and the monitoring config.

**Posture, stated precisely.** The strategy is monitored and carries `promotion_eligible=False`,
`execution_enabled=False`, and `allocation_ready=False` with the platform's own reason: *"Monitoring only; the
separate 14-ETF execution contract has not been approved."* That is the honest answer to the earlier question —
nothing forbids promoting it, but promotion and allocation are separate operator-gated acts, the research and
backtest contracts are typed `promotion_eligible: Literal[False]` and the registry refuses anything else, and
the 14-ETF execution contract has not been approved. The definition and spec sheet also carry the evidence
disclosure: **not established**, 0 of 20 family-adjusted contrasts, the 5% arm slightly below its control on
total return with a better Calmar and drawdown, and the budget an in-sample optimum.

**Integration lesson, recorded because it cost two failed batches.** A new 14-candidate recipe must join the
M1/14 family in five places: `tracked_runtime`'s family partition and its financial-input check,
`m1_monitoring`'s recipe guard and its financial requirement, and `strategy_lifecycle`'s USD-currency and
allocation-supported sets. The first attempt omitted them and the model fit died with "Training universe/order
differs from the versioned strategy" — the app was preparing a 14-symbol recipe against the 12-ETF pool. The
second attempt was clean, and the batch completed with the strategy calculated natively and published.

## 2026-10-11 — P4.17f: closing the tilt when the signal stops — holding still wins, and half the rules never fire

The operator pushed back on two things: the 44.0bp ceiling is not a law (the objective is the *optimum*, and
building whatever LEAN code is needed is acceptable), and holding the tilt to the next monthly rebalance is
obviously not optimal — test removing it whenever the signal disappears or stops. Built as P4.17f in
`var/research/alpha101-tilt-exit-20261011-v1/` (protocol `db40c5e1…`): FR25 and the current SOTA over the same
70 months and 1,448 sessions, 42 arms and 252 replays, monthly entry with declared intra-month exits, ranked on
outcomes net of the replay's 5bp cost with **no cost filter at all** — arms up to 84.3bp, nearly twice the
ceiling, were replayed and ranked, and the ceiling appears only as a column.

**Holding beats exiting.** FR25's best net configuration is **X = 5% held** (104.9% total return, 13.27% CAGR,
1.204 Sharpe, 1.598 Calmar, −8.30% maximum drawdown, 40.9bp) and the SOTA's is **X = 10% held** (77.3%, 10.46%,
0.922, 0.839, −12.46%, 38.3bp). Four of the six metric optima across the two books are plain HOLD arms; the two
exceptions are an EXIT-FADE arm that fired four times in five years — statistically a HOLD arm — and a re-entry
arm that buys 0.4pp of drawdown with 10pp of return.

**Half the declared exit rules never fire, and that is the answer to the question.** EXIT-NOSIG, which closes
when the signal stops ranking the held book, fires **zero times in 1,448 sessions**: this family always has a
spread across the names it holds, so "the signal disappears" does not happen. The −2% stop and the +1%
take-profit also never fire and the −0.5% stop fires once, because at a 5–20% tilt the tilt's own weighted
return does not travel that far inside a month — the P&L form of the idea has no traction at these sizes. What
does fire is the **flip: 61 exits**. Acting on it is worse than waiting: it forgoes the part of the tilt's edge
that has not been realised and pays a round trip, adding +2.4bp of cost at X = 5% and +4.6bp at X = 10% while
leaving Sharpe unchanged and Calmar lower; the variant that also re-enters inside the month costs +10 to +25bp
for the same or worse return.

**Why the incumbent wins.** The monthly design is not passive: it re-derives the tilt at every decision and
measured a flip on 54 of FR25's 70 decisions, with 2 closes and 2 opens. So the position rotates on a schedule
the rebalance already pays for, and closing it earlier converts that scheduled rotation into an extra trade
against an edge that has not finished. **Nothing is established either way:** 0 of 20 contrasts per book differ
from the untouched book at Holm p < 0.05, so every optimum on the surface is a selection on noise as much as on
signal.

**On rebuilding this as native LEAN code.** The daily arms are frozen as one target vector per session — exactly
what a strategy that rebalances daily submits to the engine — and the replay engine's LEAN parity is verified at
0 differences on this machine, so a new algorithm would reproduce the same NAV paths rather than produce
different numbers. What it would add is *native parity evidence*, which is a promotion-grade requirement rather
than a research one; it is the right artefact to build if a tilt is ever taken toward promotion, and I said so
plainly rather than spending the effort to re-derive the same answer.

**Verification.** 11 tests cover the arm registry and the two declared families, every exit rule's trigger
semantics, the re-entry condition, a synthetic run proving monthly entry with intra-month exit, and the frozen
study: all 42 arms present and replayed, the controls untilted, the signal rules firing as declared, an optimum
per metric, and — explicitly — that arms above the cost ceiling exist and were replayed rather than filtered.

Findings: `docs/alpha101-tilt-exit-findings.md`; report: `research/alpha101-tilt-exit-2026-10-11/index.html`.
Nothing was promoted and no monitoring, allocation, cap or cash reserve changed.

## 2026-10-11 — Tracked-calculation throughput: measured, one fix, and the honest remaining levers

The operator reported the research worker as "incredibly slow" with CPU around 40%. Measured the batch before
changing anything, on a 16-CPU host with 31.5 GiB RAM and Docker allocated 16.53 GB / 16 CPUs.

**Where the time went.** Model preparation 45.5s; native backtests 101.8s; reports 8s; the USD tail ~105s; the
M1/FR25 tail ~150–200s. The receipts showed the per-job cost exactly: `elapsed_seconds = lean_wall_seconds +
reference_wall_seconds` — 89.4s = 51.5s + 37.7s, 90.9s = 51.3s + 39.2s, 66.3s = 43.9s + 20.9s. The two engines
ran one after the other.

**Why the CPU was low, and why part of that is deliberate.** Every numerical engine here is pinned to a single
thread (`numerical_threads: 1` in the receipts, with OMP/OpenBLAS/MKL/NUMEXPR set to 1 in both the reference
runner and the preparation workers). Thread count changes floating-point summation order, so that pin is what
makes a fit reproducible from its revision identity — it is a determinism guarantee, not an oversight, and it
means the 5.33 CPUs allotted per LEAN run are unspendable because a LEAN backtest is single-threaded. The real
concurrency cap is Docker memory: `resource_plan` allows `min(jobs, budget//2, (docker_memory_gib-2)//4)` =
three concurrent runs at 4 GiB each against a 15.39 GiB Docker allocation, on a host with more than twice that
RAM. And the jobs within each analytics lane run sequentially, so the long batch also holds up `signal-decay`,
the recorders and serving publication behind it.

**The fix: run the two engines together.** `run_bundle` ran the Python reference and then the LEAN container,
but they are independent — LEAN writes `economic.json`, the oracle writes `reference.json`, and parity compares
them only once both exist — so every job was paying their sum instead of their maximum. The runner now spawns
both, waits for both, records each engine's own wall time, and keeps the failure semantics exactly: a non-zero
exit terminates its partner and raises `CalledProcessError`, a timeout terminates both and raises
`TimeoutExpired`. No input, thread count or code inside either engine changed, so no number changed.

**Measured on the real frozen bundle** (`risk_parity`, the live revision): 66.3s → **47.8s**, a 1.39× speedup
and 18.5s saved per job, with LEAN parity passing at **0 differences** and the economic artifact hash
**identical** to the published one. The two ~90s jobs save proportionally more because their reference leg is
38–39s. On the batch that followed the restart the native backtest stage fell from **101.8s to 81.4s**, the
batch completed with no error, all six monitored strategies republished through 2026-10-09, and platform and
analytics health returned to `ok`. Three tests pin the new contract: real overlap, partner termination on
failure, and termination of both on timeout.

**What is left, and what needs the operator.** (1) Docker Desktop's memory allocation is the cheapest big win
and it is a setting rather than code: the host has 31.5 GiB, Docker has 15.39 GiB, and raising it to about
24 GiB would allow 5–6 concurrent LEAN runs and shorten the M1/FR25 tail that now dominates the batch. I did not
change it — it is a desktop-wide resource setting, not a repository change. (2) Relaxing the single-thread pin
would change model fits, and the numerical thread count is **not** part of `calculation_revision` today: the
receipt records it but the revision identity does not, so it must enter the identity before it can be relaxed.
(3) `cpus_per_run` is a misleading label for LEAN and is worth correcting alongside the memory work. (4)
Parallelising the publication and report assembly around the M1 fan-out is the next code-level lever, and a
larger change than this one — worth doing deliberately.

Findings and measurements: `docs/calculation-performance.md`.

## 2026-10-11 — P4.17d/P4.17e: raising the tilt budget and raising the frequency both make it worse

Two operator-requested studies answered the two natural follow-ups to P4.17c — push the budget much higher, and
monitor daily instead of monthly with a threshold to control the trading frequency.

**P4.17d — the budget surface.** FR25 and the current SOTA tilted monthly at X ∈ {10, 20, 30, 50, 75, 100,
150}%, every arm replayed regardless of its gate verdict at the operator's instruction, in
`var/research/alpha101-tilt-surface-20261011-v1/` (protocol `99cd55a8…`), 16 arms and 96 replays. **There is no
higher-X regime.** On FR25 every measure degrades monotonically as the budget rises: untouched 106.0% total
return / 13.37% CAGR / 1.218 Sharpe / −8.66% max drawdown, X=10% 104.1% / 13.20% / 1.196 / −8.21%, X=50% 94.9% /
12.29% / 1.059, X=150% 96.2% / 12.42% / 1.028. On the SOTA the return peaks at X=10% while Sharpe, Calmar and
drawdown all worsen above it. **The tilt saturates at about half of NAV**: a declared 100% budget produces an
effective 50.6% and a declared 150% produces 50.7%, for identical cost to a tenth of a basis point, because one
shrink factor keeps every name inside the 45% cap and above zero and a six-name book can only move as much as
its smallest weight. Cost, measured but not binding by instruction: X ≤ 20% passes the 44.0bp ceiling, X ≥ 30% is
rejected (46.7bp at 30%, 56.5bp at 100%) — and the expensive arms are also the ones that degrade the portfolio,
so the deviation changes no conclusion. No optimal X is declared; the best X by any metric is an in-sample
maximum, and the honest reading is the smallest budget in the grid or none.

**P4.17e — daily, threshold-triggered.** The operator clarified the intent: not the monthly rebalance, but daily
monitoring with a re-tilt whenever the alpha signal moves, accepting high frequency to enhance the return, with
the threshold as the cost control. Built in `var/research/alpha101-tilt-daily-20261011-v1/` (protocol
`725aa02b…`): FR25 and the SOTA over 1,448 sessions each, X ∈ {5, 10, 20}%, band ∈ {daily, 50%, 100%, 200%,
300%} of the budget, plus the monthly arm as the frequency reference, 34 arms and 204 replays. **High frequency
destroys value.** Every daily arm is worse than doing nothing and costs 2–5.5× more: FR25 daily at 5/10/20%
returns 101.1% / 96.5% / 87.6% against the untouched 105.8%, with Sharpe 1.174 / 1.131 / 1.042 against 1.214, at
91.8 / 142.8 / 243.3bp of cost; the SOTA shows the same ordering (67.2% and 59.3% at 10% and 20% against 76.2%).

**The threshold works exactly as the operator proposed — and that is the problem.** Raising the band from daily
to 300% of the budget cuts re-tilts from 1,269 to 64 a year and cost from 91.8–243.3bp to 37–44bp. But fitting
the 44.0bp ceiling requires a band of 200–300%, and at that band the arm trades **64–86 times a year, which is
the monthly arm's own 70**. Daily monitoring behind a wide deadband is the monthly tilt with extra bookkeeping,
and every band arm that clears the ceiling is statistically indistinguishable from doing nothing: intervals
spanning zero, Holm p = 1.000, mean annual differences of ±0.3% at most. The mechanical reason is now recorded
in the study: the tilt is established on the first session it is computable and the band governs afterwards, and
because the distance from a zero tilt is only about one budget, a band of a whole budget or more can essentially
never open between strategy rebalances — so those arms re-derive the tilt almost only when the base book itself
rebalances.

**Why frequency hurts.** The family's information lives at the 21-session horizon — the P4.17 screen measured
21-session rank ICs of 0.05–0.075 — so daily re-tilting trades one-session signal changes that carry almost none
of it. Frequency multiplies the cost linearly while the information per trade falls towards zero. A genuinely
higher-frequency use would need a signal whose information is measured at one to five sessions, which is a
different study and would face the P4.15 gate first.

**Verification and defects.** Both studies read their base books from the frozen P4.14 Part B and P4.17c roots and
re-check them by hash; every tilted or daily row is checked against the zero floor and the 45% cap in the run
that produces it. The daily study required a shared `tilt_vector` refactor of the tested rule, and its
behaviour-preservation is proven by the earlier frozen artifacts still reproducing exactly. The test bench
caught two trigger defects before publication: the establishing re-tilt was not counted as a trade, and a band of
a whole budget could never open from a zero tilt on the first session. Both were fixed, the affected arms'
decisions and replays were regenerated, and the published frontier reflects the corrected rule. 5 new surface
tests and 11 new daily tests.

**Platform note, and the guard tripping a second time.** Five modules were added to
`src/systematic_trading/research/`, inside the tracked-calculation revision identity. The stack was
restarted through the documented path, but the fix to the daily study's trigger accounting landed *while
that batch was running*, so it failed at publication with "Calculation implementation changed before
publication" — the same guard as the earlier incident, now seen from both ends: it refuses to start with a
stale snapshot and refuses to publish a changed one. The stack was restarted again once the code was final,
and the recalculation completed cleanly under the new revision. The rule recorded earlier is unchanged and
is now demonstrated twice: **finish the code, then restart, never edit the calculation packages during a
batch.**

**Next: P4.18 volatility-targeted exposure.** The P4.17b–e line ends here: a monthly selection tilt is nearly
neutral, a larger budget saturates and degrades, and daily tilting is worse than doing nothing — so the drawdown
question P4.16 raised is exactly where it was. Nothing was promoted, and no monitoring, allocation, cap or cash
reserve changed. Findings: `docs/alpha101-tilt-surface-findings.md` and `docs/alpha101-tilt-daily-findings.md`.

## 2026-10-11 — P4.17c: baking the 10% tilt into the SOTA — nearly free, nearly neutral

The operator asked whether the tested alpha could be baked into the current SOTA with a 10% tilt and what the
final return, Sharpe, Calmar and max drawdown would be. Built as its own frozen study in
`var/research/alpha101-tilt-replay-20261011-v1/` (protocol `bb7dba31…`): three arms — the untouched SOTA
(`research_fallback_f3_v1`, built from its own registered definition and overlay chain), the same SOTA with a
10% tilt of alpha 53, and the same SOTA with a 10% tilt of the equal-weight family — 130 decisions each and 36
replays on the parent evidence root's own quotes, sessions, costs and windows. The gate ran on every arm
before any replay.

**The four numbers.** SOTA 76.4% total return / 10.36% CAGR / 0.916 Sharpe / 0.805 Calmar / −12.88% maxDD.
SOTA with the alpha-53 tilt: 77.0% / 10.42% / 0.913 / 0.818 / −12.75%, for +2.08bp of incremental cost. SOTA
with the family tilt: **77.5% / 10.48% / 0.922 / 0.840 / −12.47%**, for +1.53bp. Every measure moves the
right way; **none of it is established** — the annualised differences are +0.07% and +0.12% with 95% intervals
spanning zero at 3, 6 and 12 months and Holm p = 1.000 across the three registered contrasts. The tilt is
nearly free and nearly neutral: 1.5–2.1bp of cost for 7–12bp of return a year.

**Affordability was never the problem this time.** The SOTA's own drag is 7.03×/35.14bp against the 44.0bp
ceiling, leaving about 8.9bp of headroom, and the tilt uses a fifth of it. All three arms pass the gate with
IC margins of 15.9–16.8×. The tie-break that killed P4.17 — 44.7–76.5bp of turnover cost — does not arise,
which is what the tilt design was for.

**The family tilt beats the best-information single alpha at lower cost** (+0.12% for 1.53bp against +0.07%
for 2.08bp). Alpha 53 had the strongest measured information of the sixteen, so this is direct evidence that
its apparent superiority was in-sample noise, and it argues for tilting on the whole registered family rather
than on a selected alpha — a small but genuinely useful methodological result.

**Two implementation findings.** First, the SOTA's book can arrive at the tilt overlay already above the 45%
cap, because the final clamp runs after the chain; on 4–6 of 130 decisions a name was over the cap, and the
declared single-shrink-factor rule correctly shrank the tilt to a no-op rather than pushing an over-cap name
further above it, so the tilt applied on 115 of 130 decisions and the guarantee is "never worse" rather than
"always inside the cap". Second, three defects were found by running the study rather than reading it: the
ranking was originally computed over the *control's* holdings instead of the book actually being tilted, the
float arithmetic met the Decimal weights at the cap test, and a zero rank score for the median name of an odd
book divided by zero. All three are fixed, and the corrected rule is what the frozen artifact reflects.

**Why the effect is small, and expected to be.** A 10% budget moves each held weight by a few percent of NAV
against a forward rank IC of 0.05–0.075, so the expected edge is tens of basis points a year, not percent —
and the measured +7 to +12bp sits in exactly that range. P4.17b already found that 20% is where the cost
balance breaks, so there is no cheap way to make the tilt larger.

**Verification.** 13 tests covering the arm definitions and the declared selection disclosure, the rank rule's
refusal to rank an unrankable book, NAV-neutrality and the cap bound, the over-cap no-op, the zero-floor
shrink, the overlay preserving the symbol set the fallback protects, the composite averaging rank scores
rather than values whose scales differ by four orders of magnitude, and against the frozen artifact all 36
replays present once, the gate passing every arm before any replay, the incremental costs below 3bp, the
verdict inconclusive with directionally better return, Calmar and drawdown, and the analysis reproducing from
the replays. Every arm's decisions pass the cap, long-only, universe and protected-budget contracts in the
same run that produces them.

**Platform note.** Three modules were added to `src/systematic_trading/research/`, inside the
tracked-calculation revision identity, so the dashboard stack was restarted through the documented
`stop_operator_dashboard.ps1` / `start_operator_dashboard.ps1` path immediately afterwards and the
recalculation ran under the new revision — the workflow the earlier incident established.

**Next: P4.18 volatility-targeted exposure.** The SOTA remains `research_fallback_f3_v1`, monitored and
unchanged; nothing here re-tunes X, touches the 45% cap or the cash reserve, or creates promotion authority.
Findings: `docs/alpha101-tilt-replay-findings.md`; report: `research/alpha101-tilt-replay-2026-10-11/index.html`.

## 2026-10-11 — P4.17b: tipping the alpha in as a tilt, not a selector, changes the answer

The operator's response to P4.17's closure was to stop asking the alphas to choose the book and instead let
them **overweight and underweight the holdings that are already there**, with X% of NAV set aside for it, and
to find the balance between cost and alpha. Measured as its own frozen study in
`var/research/alpha101-tilt-20261011-v1/` (protocol `1fa318f9…`): 48 declared candidates — the sixteen
registered alphas at 5%, 10% and 20% — with the base book taken from the pinned pooled control's own
decisions, a NAV-neutral linear rank tilt, one per-decision shrink factor for the 45% cap and the zero floor,
and the P4.15 gate applied before any replay. No economics were produced.

**The operator's design solves what P4.17 could not.** At a 5% budget **12 of 16 alphas clear the gate for
0.00–0.48bp**, against the **3.65bp** of headroom between the monitored book's published 40.35bp drag and the
44.0bp ceiling — the worst candidate uses **13%** of the available room. At 10% it is still 12 of 16 for up to
1.69bp. At 20% the balance breaks the other way: the worst candidate costs 5.17bp, above the headroom itself,
and only 5 of 16 clear. So the cost/alpha balance sits at **5–10%**, and at those budgets cost stops being the
binding question. P4.17's mappings needed 44.7–76.5bp; the tilt needs a rounding error.

**The IC bar falls by two orders of magnitude, which is the second half of the operator's intuition.** The
breakeven IC goes from 0.0061–0.0122 for the full mappings to **0.00000–0.00008** at a 5% tilt, because the
breakeven scales with turnover. The operator expected a low IC threshold to be enough; it is, and it is a
consequence of the cheaper mapping rather than of relaxing the gate — the frozen 3× margin and the cost
ceiling are applied unchanged.

**The rejections are now information failures rather than cost failures**, the exact inversion of P4.17.
Alpha 101's tilt points the wrong way — its 21-session rank IC is −0.0749 with an interval excluding zero, so
a long tilt is a short signal — and alphas 23 and 12 are negative as well; alpha 7 remains degenerate under
the paper's dollar-volume-versus-share-volume quirk. The 45% cap interaction is measured rather than assumed:
the shrink factor averages 0.98–1.00 and binds on 2–7% of decisions, so a book at the cap shrinks the tilt
instead of breaching the limit.

**A false-pass defect was caught by the test bench and fixed before publication.** The first version of the
rule tilted a *constant* held cross-section on the alphabetical tie-break — arbitrary overweights — and
because such a tilt barely trades, its near-zero incremental cost then read as a pass. That is the same
false-pass class as P4.17's alpha 7, and it was fixed at the root with two rules frozen in the protocol: a
held cross-section with fewer than two distinct values cannot rank and is left untilted, and a candidate that
never ranked the book is reported *insufficient* rather than passed on a zero cost. Re-measured after the fix
the grid moved from 28 to 29 passes and the ternary alphas became cheaper, because days on which they express
no view about the held book no longer trade.

**Verification.** 12 tests covering the rank scores, NAV-neutrality and the exact budget spend, the cap and
zero-floor shrinks, the refusal to tilt a cross-section with no spread, the derivation of the headroom from
the published ceiling and drag, the unchanged 3× margin, and against the frozen artifact the whole
48-candidate grid with a reason on every verdict, the 0.13× headroom ceiling at 5%, the breakeven collapse,
the balance break at 20%, the negative-information rejections and exact reproduction with every input
re-checked by hash. The monitored drag is asserted against the published 40.4bp so a wrong arm or artifact
stops the study rather than silently changing the headroom.

**Platform note.** This work added two modules to `src/systematic_trading/research/`, which is inside the
tracked-calculation revision identity, so the dashboard stack was restarted through the documented
`stop_operator_dashboard.ps1` / `start_operator_dashboard.ps1` path immediately afterwards — the workflow the
earlier incident established: edit calculation code, then restart, never during a running batch.

**Next: P4.17c, the tilt replay** — the equal-weight tilt composite across the family at 5% and 10% (which
avoids selecting on the in-sample ICs), the matched untilted control, and the lowest-cost variant; replayed
through the engine with the cap and cash reserve unchanged, family-adjusted intervals, and judgement on
drawdown across episodes as well as return. If a tilt is ever monitored it enters the P4.13 decay
instrumentation like every other signal. Findings: `docs/alpha101-tilt-findings.md`; report:
`research/alpha101-tilt-2026-10-11/index.html`. Nothing was replayed, promoted, or changed in the monitored
book.

## 2026-10-11 — Incident: research edits aborted a live tracked-strategy calculation

The operator dashboard reported `tracked-strategies: Calculation source changed; restart the
application before calculating the new version`, with last complete results retained. It was not a
code fault: it was the calculation revision guard working exactly as designed, and the trigger was my
own research work.

**What happened.** The dashboard process started at 10:37:45 and loaded its code-hash snapshot then. A
tracked-strategy calculation began at 10:38:05 with revision `b1b8ceb7…`. Between 10:42 and 10:49 three
new modules landed under `src/systematic_trading/research/` (`alpha101.py`, `alpha101_screen.py`,
`alpha101_analysis.py`) as part of P4.17. At 11:07:59 the guard in
`research/tracked_runtime.calculation_revision` compared the on-disk hash of the calculation source
against the snapshot its process had loaded, found them different, and aborted the batch. The batch had
prepared and completed three jobs (risk parity and the two USD strategies); it never published, so the
previous complete publication stayed live and allocation and order checks stayed enforced.

**Why the guard is correct.** `CALCULATION_PACKAGES` hashes every `.py` under `research`, `lean`,
`signals`, `portfolio` and `backtest` plus `recorders/economics.py` and `runtime_io.py`, and the file
set is derived from package contents on purpose: a new calculation module must not be able to slip
outside the revision identity and silently fail to invalidate a published calculation. A published
number has to be reproducible from the code that produced it, so a mid-flight source change must
invalidate the batch rather than publish a mixed-identity result. The guard also re-checks before
publication, which is why the failure surfaced at the end of the run rather than the start.

**Resolution.** Verified the calculation path compiles (`compileall` clean across all five packages)
and that a fresh process imports `tracked_runtime`, hashes 141 files, and finds its loaded snapshot
equal to disk — so a restart would produce a self-consistent revision. Then used the documented
service path: `scripts/stop_operator_dashboard.ps1` (which pauses operator recovery and stops the
outbox dispatcher with the dashboard) followed by `scripts/start_operator_dashboard.ps1` (which pauses
and resumes recovery, health-gates the API, and restarts the dispatcher as a companion). Port
ownership matched the PID file, so the supervisor's process-identity checks passed. The dashboard came
back healthy on `http://127.0.0.1:8000/operator`, every platform service reported `ok`, and the
tracked-strategy calculation restarted and completed under revision `545d1129…` (three tracked reports, 46s preparation, 102s backtests); all six monitored strategies were republished through 2026-10-09 with reports available, and analytics health returned to `ok`, with `/operator`, `/strategies`, `/platform` and `/health` all serving 200 and no calculation error on any of them.

**Rule for future sessions.** While a tracked-strategy calculation is running, do not write to
`src/systematic_trading/research`, `lean`, `signals`, `portfolio`, `backtest`,
`src/systematic_trading/recorders/economics.py` or `src/systematic_trading/runtime_io.py`. Research
documentation, tests, `scripts/`, and new evidence roots are unaffected. If calculation code genuinely
must change mid-run, either wait for the batch to finish or restart the application afterwards: the
guard will abort the batch and retain the last complete results, which is the safe outcome but leaves
the dashboard showing a calculation error until the restart.

## 2026-10-11 — P4.17 Alpha101 screen: the information is real, the turnover is not payable

P4.17 is run as its own frozen, pre-registered study in `var/research/alpha101-screen-20261011-v1/`
(protocol `7865c485…`). The item's acceptance put the cost test before any portfolio work, so this is
a screen and not a backtest: no economics, no replay, no promotion.

**The library.** All sixteen registered pure time-series alphas are implemented from the paper's own
formulas, and the implementation is pinned against a hash-checked extraction of the paper copy
(sha256 `1f9c21af…`) character for character — a mismatch stops the study rather than being reported.
Every operator is point-in-time, the caller supplies only data up to the session before the decision,
and an unsupported window stays missing rather than being filled. A window-boundedness test across all
sixteen confirms that a value at one session cannot depend on how much earlier history is supplied.

**The result: none of the sixteen clears the P4.15 gate.** Fifteen are rejected and one cannot be
judged, because alpha 7 is a constant. Twelve fail the 44.0bp cost ceiling alone (51.7bp–76.5bp),
three fail both tests, and alpha 21 — the only alpha inside the ceiling at 38.1bp — fails the IC
margin at 2.22× against the required 3×.

**The failure is turnover, not information, and the information is the durable finding.** The monthly
top-six mappings turn over 7.62×–15.29× against the monitored book's 8.07×. P4.15 rejected the *daily*
archetypes by 5×–46×; at the decision frequency this programme actually trades, the gap is 1.0–1.9×.
Against that, alpha 53 shows 21-session rank IC +0.0747 with a 95% interval [+0.0016, +0.1522] and
alpha 26 shows +0.0572 with [+0.0106, +0.1052] — both excluding zero — and alpha 101 shows −0.0749
with [−0.1313, −0.0140], real information that is *inverted*, so a long-only mapping of it is a short
signal. This is the first evidence in this programme that a simple published formula carries
measurable forward rank IC on this universe, and it is recorded as such even though the family closes.

**Two disclosures.** First, the published formulas mix units: `adv{d}` is defined as average daily
*dollar* volume while `volume` is share volume, and three registered alphas compare the two directly.
Implemented verbatim — as the plan requires — alpha 7's condition never holds on this data and the
formula collapses to its constant branch, and alphas 21 and 43 have their volume comparisons distorted
by price level. That is reported rather than repaired: a dollar-volume-consistent variant is a
different, separately declared family. Second, the first run contained a wiring defect of exactly the
kind the gate exists to prevent: with no measurable IC for a constant cross-section, the gate judged
alpha 7 against the programme reference IC and reported it as **passing** with a 102.77× margin. Two
rules were added before publication and frozen in the protocol: a cross-section with fewer than two
distinct values cannot rank, so it forms no mapping; and a candidate with no measurable IC is reported
*insufficient* and is never judged against the programme reference IC. The correction only reclassifies
a non-measurable candidate — it cannot manufacture a pass — and the published artifact is the corrected
one. Pre-correction 1 pass / 15 reject; post-correction 0 pass / 15 reject / 1 insufficient.

**Verification.** 22 focused tests: the formula pinning, the operator definitions and missing-value
behaviour, hand-computed spot checks for nine alphas, the window-boundedness check for all sixteen,
the screen's point-in-time slicing, and exact reproduction of the frozen artifact with the pinned
P4.16 inputs and the paper re-checked by hash. Re-running the screen reproduced its artifact exactly
and the formula extraction reported no mismatches.

**Consequence.** The plan's next step for this item was conditional — *if anything survives, trade it
as a bounded 5–10% satellite sleeve* — and nothing survives, so there is no satellite, no model stage
and no promotion. Any follow-up must attack turnover rather than signal quality: a slower rebalance,
hold bands that suppress membership churn, or use as a feature inside an already-slower mapping, each
declared in advance and each measured against the P4.15 ceiling before any portfolio result. Findings:
`docs/alpha101-screen-findings.md`; report: `research/alpha101-screen-2026-10-11/index.html`.

**Next:** P4.18 volatility-targeted exposure, with a matched-average-exposure control and a declared
return-sacrifice budget, gated by P4.15 first. No monitoring, allocation or authority change.

## 2026-10-11 — Documentation encoding incident, and the recovery

An in-place text substitution I ran through PowerShell on five documentation files
(`log.md`, `docs/execution-kanban.md`, `docs/research-state.md`,
`docs/signal-decay-and-alpha-plan.md`, `docs/hierarchical-construction-findings.md`)
silently read them with the system ANSI codepage and wrote them back as UTF-8. Every
non-ASCII character was double-encoded, and each character whose GBK byte pair was
unassigned lost a byte to a `?` replacement — enough to destroy digits inside negative
figures such as drawdowns.

Recovery: the four tracked files were restored byte-exactly from `git HEAD`, which held
the session-start state (502 / 2,195 / 1,504 / 453 lines, matching the line counts seen at
the start of the session), and this session's records were re-added from the uncorrupted
findings documents and the frozen evidence artifacts rather than from the damaged text, so
no figure in the restored documentation is derived from a corrupted digit. The untracked
P4.16b findings document was rewritten from `analysis.json`. All documentation now
verifies as BOM-free UTF-8 with zero mojibake signatures.

Rule recorded for future sessions: **never edit repository text files through PowerShell
text cmdlets.** Use the file tools, which write UTF-8; if a bulk substitution is genuinely
needed, do it in Python with explicit `encoding='utf-8'` on both read and write.

## 2026-10-11 — P4.16b hierarchical construction: the operator's rule works, the risk does not move

The operator's response to P4.16 — *if an asset class is in a downtrend (bonds into a
rising-rate environment), forcing an allocation to that bucket is wrong; pick the top two
or three classes, then the top two or three inside them* — is registered and run as its own
frozen study in `var/research/hierarchical-construction-20261011-v1/` (protocol
`af9bb329…`), screened by the P4.15 gate before any replay. **The rule was proposed after
P4.16's outcome was known, so it is post-hoc on the inspected sample; the frozen protocol
states that in its own field.** No monitoring, allocation, funding, approval or
execution-authority change.

**Frozen rule.** A class qualifies only if at least one member passes the same positive
126-session momentum gate the pooled control uses; qualifying classes are scored by the
mean of their two best eligible members; the top K share the incoming gross equally; inside
each chosen class the top two eligible names split that class's budget by incoming
inverse-volatility weight; an unfilled slot, or a day with no qualifying class, is cash.
K=2 and K=3 are both declared, because choosing between them on this outcome would be
tuning. The selection stage is a thin subclass of the existing balanced-group overlay that
decides only *which* classes receive a budget, so the ranking, the weight arithmetic and
the never-force-an-ineligible-asset contract are the parent primitive's own code.

**The mechanism works exactly as the operator described.** Neither arm held a single
fixed-income instrument in any month of 2022; the fixed-income class is chosen 13% of the
time under K=2 against 46% under the pooled control, and 2022-10-03 was held entirely in
cash because no class qualified. Both properties are regression tests. Two qualifications:
**K=3 reverses part of the effect** — with three slots fixed income is chosen 64% of the
time, *more* often than pooled, because it frequently ranks third — and the price is
concentration.

**The return effect is the largest this programme has measured, and still not
established.** HIER-K2 returns 15.07% CAGR against the construction-matched pooled
control's 9.50% and the published control's 11.92%: **+5.32pp annualised with a 95%
interval excluding zero at 3, 6 and 12 months** ([+0.69%, +10.41%] at the 6-month block),
and both risk ratios improve against that control (Sharpe 0.941 vs 0.754, Calmar 0.680 vs
0.455). But the **family-adjusted Holm p is 0.164**, so the verdict is **inconclusive**.
HIER-K3 is +3.60pp with an interval spanning zero.

**Risk is orthogonal.** HIER-K2 holds **2.91 names** on average with two positions at the
45% cap; its maximum drawdown (−22.18%) is *worse* than the diversified arm it beats on
return (−20.89%) and far worse than the published control's (−8.31%), and its Sharpe
(0.941) is below the published control's (1.106). This reproduces P4.16's conclusion from
the other direction: the failing dimension is the exposure rule, not the selection rule.

**The gate ran first.** K=3 passes at 40.7bp of implied annual cost, cheaper than the
pooled control's 43.6bp; K=2 is a recorded boundary case at 45.5bp, replayed under P4.15's
published boundary rule with its verdict unchanged.

**Verification.** 14 focused tests in `tests/test_hierarchical_construction.py`, including
the 2022 no-bonds regression, the per-class slot contract, the long-only and 45% cap
contracts, the all-cash decision and the pinned-parent hash check; every pooled reference
replay reproduces the parent's published statistics to 1e-12; Ruff passes. Findings:
`docs/hierarchical-construction-findings.md`; report:
`research/hierarchical-construction-2026-10-11/index.html`.

## 2026-10-11 — P4.16d registered: granular asset classes, a wider ETF pool, volatility-aware ranking

The operator's comments after P4.16b are recorded in the plan as **P4.16d**, blocked on
universe admission and not run. Four asset classes are probably too coarse to differentiate
class performance; the operator suggests splitting equity by region (US, EU, Asia-ex-China,
China), differentiating fixed income regionally, and splitting commodities by complex (base
metals, energy, precious metals, agriculture, chemicals/industrial), with semiconductors
listed alongside them — recorded verbatim with a note that semiconductors are an equity
industry rather than a commodity complex. Boundary cases must be decided rather than
ignored: silver is both precious and industrial, and fund mandates can straddle or change
categories. The operator also requires **volatility control**: a raw top-performer ranking
is not acceptable, because the top performer is often simply the most volatile. The binding
prerequisite is a **much larger audited ETF pool**, admitted through the existing
qualification, audit and publication process — never by reading provider archives or online
prices into research inputs.

**P4.16c (hierarchical plus defensive fallback) is parked at the operator's request**,
because the class question is probably not answerable at this granularity. Registered so it
is not lost; it does not authorise any new instrument, any download into research inputs,
or any change to monitoring, allocation or the 45% cap.
