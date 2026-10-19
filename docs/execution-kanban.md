# Execution Kanban

Current work and unresolved acceptance gates, consolidated 2026-10-12. Update at the
start and end of each implementation session. Completed rows and historical sessions
are preserved byte-for-byte in the [history archive](archive/README.md).
Use [research state](research-state.md) for accepted conclusions and the
[research plan](signal-decay-and-alpha-plan.md) for the ordered research programme.

## Tracked-calculation/backup lock collision — 2026-10-18

**Complete — false "Strategy calculation error" removed and artifact locks
decoupled:** the hourly recovery backup shared
`var/run/research-retention.lock` with every tracked-strategy refresh, so while
a backup uploaded/verified, the calculation's non-blocking Windows lock acquire
failed and surfaced as a bare `[Errno 13] Permission denied`; a wedged NAS
upload kept that state for the whole long command timeout. The backup now holds
only `var/system-backup/capture.lock` (already probed by research-retention
maintenance), while calculations keep the artifact lock, and overlapping
contention is reported as a transient waiting warning with an explicit heading
instead of an error/alert. Restic commands now fail after
`stall_timeout_seconds` (900 s) without output, `unlock` is bounded to 120 s,
and System → Backups flags a transfer stage with no progress for 30 minutes.
224 focused tests (one optional skip) and Ruff pass; live restart/publication
and backup behavior are recorded in `log.md`. No allocation, order, approval,
funding or broker change.

## GLD daily behavior drill-down — 2026-10-18

**In progress — confirmation / patience experiment:** Operator requests repair
of the February–March 2024 late entry and early time exit. GLD daily only;
jointly enumerate confirmation count and progress deadline, keep range/ATR/
price stops/required progress/all other parameters fixed. Numeric fitting
pre2023, 2023 regularization/model selection, then a sealed 2024+ development
retest with entry-only and holding-only ablations. Preserve the v1 diagnostic
and provide the same daily range/entry/exit calculation detail for the revision.

**Diagnostic complete; numerical repairs remain open:** Operator restricts work
to GLD first and explicitly replaces calendar execution with daily trading for
this study. Future fitting and 2023 variant selection must compare daily rules
only. Daily completed-close decisions execute at the next session open; no
calendar rebalancing. Keep inherited v3 numerical parameters fixed for this
first diagnostic, without claiming they are a newly selected daily optimum.

Interactive dated ranges, rejected window criteria, crossings/confirmations,
actual fills, daily initial/range/trailing/time levels and retained fitting
records now cover 5,512 sessions. Seven 2024+ entries, six time-rule exits;
latest trailing activation $431.98 was never reached (peak $428.07), effective
stop $357.45. Daily baseline CAGR −1.84%, Sharpe −0.229, DD −11.99%.
23 focused tests and report source/control checks pass. Independent native
daily replay matches all 13 fills and 701 NAV observations with zero error.
Browser policy blocked local-file visual QA; no browser-rendering pass claimed.
No new fit, other-ETF study, promotion, monitoring or broker action.
Next: inspect the five-session progress test and change one GLD rule at a time.
[Daily drill-down](../research/gld-breakout-drilldown-20261018-v1/index.html).

## Joint lifecycle optimization v3 — 2026-10-18

**Complete — joint search does not validate a general breakout strategy:**
33 mixed parameters, 1,100,502 unique pre-2023 evaluations across 50 qualified
ETFs; two short histories use shared parameters. Scaled net-return/Sharpe/Calmar
45/40/15 objective, soft near-buy-hold and wide-stop penalties, two seeds,
chronological/local stability, shared/shrunk variants. Calendar 2023 selects
frozen variants/clocks; all 52 choices sealed before 2024+ replay.

Selected OOS CAGR GLD −0.19%, USO −4.11%, SOXX 42.72%, versus buy-hold
27.75%/36.67%/40.83%. Gold's fitted five-session time exit misses the rally;
all three cases failed 2023 return/drawdown guards. Only 5/52 beat buy-hold
CAGR; no positive family-adjusted bound versus buy-hold. Equal-budget sleeves
7.24% event /8.39% monthly trail matched momentum 10.11%/11.94%.
7,320 individual OOS scenarios, 204 pool scenarios, 63 focused tests and five
exact Windows-native checks pass. Report includes all variants, parameters,
seed/local diagnostics, costs/delays, attribution and failed selections.
No strategy promotion, tracking, funding or execution change.
[Report](../research/range-breakout-20261018-v3/index.html),
[recipe and interpretation](range-breakout-calibration-v2.md#joint-lifecycle-v3-follow-up).

## Range-breakout individual-asset calibration v2 — 2026-10-18

**Complete — no general validation or promotion:** 52 supported /54 reviewed ETFs,
full individual histories, 1,080 range/exit/volume choices per ETF fitted strictly
before 2023. 47 individual fits,46 passing IS guards; five shared-rule fallbacks.
2023–October16 OOS CAGR: GLD20.10%,USO−3.21%,SOXX32.11%, versus v1
3.27%/3.38%/−0.46% and buy-hold23.48%/24.71%/46.95%. Wider holding captures
gold/semiconductor rallies but raises drawdowns; oil fails OOS. Only2/52 beat
buy-hold CAGR and15/52 beat the shared rule. One positive family bound is BIL,
not a risky breakout. BIL/cash dominates standalone portfolio construction.
56,160 fractional screens,1,536 exact IS replays,1,872 individual OOS and156 pool
replays;47 tests, scoped lint and five exact native LEAN checks pass. Compact
study footprint94.65MiB. [Definition/results](range-breakout-calibration-v2.md),
[report](../research/range-breakout-20261018-v2/index.html).

## Range-breakout lifecycle factor research — 2026-10-18

**Complete — research prototype, no promotion:** Implemented adaptive 42–756-session
compression, frozen-range three-close confirmation, optional raw-volume support,
holding, heat-sensitive trailing exits, false-break stops and reset states.
Fixed 252/504-session controls remain. Reviewed 53 existing-pool candidates and
tested 50; after explicit operator steering, added a separately pinned audited USO
history for 51 supported / 54 reviewed without changing the original 50 inputs or
FR25 control. Tested selection, standalone trading and a 20% FR25 sleeve under
monthly/event timing and six cost/delay cases: 972 fixed and 36 continuous
walk-forward replays across the two pools. Four native LEAN checks match exactly;
37 focused tests and scoped lint pass. About 164 MiB of artifacts, with one source
snapshot per pool and compact scenario paths.

Primary extended-pool trading: 2024+ CAGR 9.23%, Sharpe 1.413, drawdown −4.63%,
46.45% exposure; full-period CAGR 4.76%, Sharpe 0.764. The 20% tilt earns 17.00%
versus matched FR25's 19.37%; its construction-matched blend earns 15.99% with
higher Sharpe. Zero family-adjusted positive contrasts; one-session delay and
20 bp costs materially erode trading performance. Includes GLD/USO/SOXX/XLE case
charts and losers/missed trends. No monitoring/allocation/broker policy changed.
[Definition, findings and next work](range-breakout-factor.md);
[full report](../research/range-breakout-20261018-v1/index.html).

## Disk retention and Windows native migration implementation — 2026-10-18

**Complete — native cutover, research retirement, host compaction and broker follow-up.**
Final follow-up acceptance passed at 16:40 local time on October 18. Administrator
compaction reclaimed 246.15 GiB in its measured receipt; the Docker VHDX is now
2.72 GiB. Gateway is healthy and fresh reconciliation matched all six positions,
with no warnings or unmatched orders/fills. The operator already enabled paper
policy revision 19; its prior account, binding, strategy and 1,000,000 CNH cap are
unchanged. No additional policy revision was written. Live routing stays disabled.
Retired 815 selected roots: 95 superseded calculations, 128 completed-study leaves,
264 unreferenced model revisions and 328 governance projections. Verified exclusive
file contents removed total 97.73 GiB. Findings, recipes and retirement receipts
remain; protected active studies, canonical audited histories and broker evidence
passed checks. The final inventory measured about 133 GiB logical contents in `var/`,
down from 477.32 GiB; hard links make this distinct from physical reclaimed space.

Native PostgreSQL/Parquet migration verified 50,206 publications, 10,065 governed
pairs and 34,772 unique fragment hashes. Native NATS restore/reliability checks,
independent native LEAN parity, restricted-worker tests, isolated database/queue
restore and Docker-free cold startup passed. The final app revision is
`b528d1061f7757f1bcc434529662beb20251fcd69748878e7870d91b43eeddc4`:
12 native runs and artifact hashes passed; all seven monitored strategy reports
are served through October 16. Allocation control is unchanged. Worker runs are
serialized, limited to two CPUs and 4 GiB, with no network capability.

The exact first native NAS snapshot is
`8e0658e40f3d0b0451ee9770eb8d4d8c9364c26bfbb3ce43048f1277c10e0de5`.
A fresh post-calculation incremental backup completed and passed exact identity,
manifest and dependency readback, including the newly published calculation:
`2d08c381db7938ac4c0c7a1dc2efdd34e67428239a832f8f11507ef96aebc289`.
It reused 1,287,668 files and added 124,934,927 packed bytes; normal hourly supervision
has resumed. Snapshot selection now
resolves the tagged original candidate and explicitly selects its incremental parent.
The final 1,903-case broad run had one Docker-dependent test fixture failure; its
repair and backup regressions pass (21 cases). Four real isolation tests, 17 final
report/resource tests and 15 final backup tests pass; documentation links and lint
pass. Earlier retired-replay skips and repaired failures are recorded in the log.

Removed the exact project ClickHouse container, both legacy Docker data volumes
and all three images, with ownership checks and a retirement receipt. Docker and
its only WSL distribution are stopped, Docker auto-start is absent and the VHDX
is detached. Operator-run compaction and a subsequent exclusive-access check passed;
the receipt records 267,222,253,568 bytes before and 2,918,187,008 after. D: had
790.33 GiB free at the final host check. Automatic approval review blocked
removal of both disposable restore-test roots; they remain with compact evidence:
`var/system-backup/postgres-restore-drill/data` and
`D:/systematic_trading_data/native-restore-drill-20261018`.
`operator-followup-acceptance.json` verifies unchanged allocation control, paper
policy, reconciliation, seven served reports and healthy core native services.
The first resumed hourly backup also completed (snapshot
`40cbff997b972b940ec7b3f8dd440ca379cca2e06c14ca27621c6fcfd730d656`).
Existing daily coverage/acquisition and execution-benchmark gaps remain visible;
neither migration nor reconciliation waives their data-quality checks.

## Disk retention and Windows native migration plan — 2026-10-17

**Done — plan and durable policy; implementation queued:** The operator prioritizes
memory/storage over recomputation and explicitly permits retiring bulky archived
research artifacts without exact replay copies. Selected replacement: native Windows
PostgreSQL metadata/operations, compressed Parquet/native DuckDB, native NATS and a
Docker-free calculation/independent-validation path. The live catalog has 22 archived
entries (21 IDs) and seven monitored strategies; FR25 is SOTA and 100% paper allocation
at control revision 7. Latest two complete calculation directories total about
0.89 GiB versus 58.20 GiB for 239 revisions. Savings remain subject to active and
paper-evidence pins and hard-link accounting. Compact summaries and retirement
records replace an unconditional keep-every-experiment rule; no full backup of
deliberately disposable output is required. [Implementation plan](storage-retention-and-windows-native-plan.md)
covers seven ordered stages, exact code boundaries, native engine isolation/parity,
atomic publication, cutover/delta rollback, backup/restore and cleanup acceptance.
Next: stage 1 retention records/summary serving and guarded deletion manifest, then
diagnostic cleanup. No data deletion, service migration or runtime change in this
planning session; the earlier automatic-review deletion rejection remains recorded.

## Storage and service resource review — 2026-10-17

**Done — assessment; cleanup/resource policy remains follow-up:** `var/` contains
4.83M files / 477.32 GiB logical lengths. The apparent 353.17 GiB governance tree
has only 18.43 GiB of unique file contents because of existing hard links; blanket
deletion would overstate savings and break pinned research evidence. Current study
batch hashes/publications verified. Tracked bundles (58.20 GiB), study artifacts
(53.53 GiB) and models (6.77 GiB) require dependency-aware retention/deduplication.
Outside `var/`, ClickHouse holds 82.53 GiB of diagnostic logs. NATS process memory
is about 43 MiB despite a much larger Docker-accounted figure; ClickHouse's cgroup
is dominated by file cache. Neither service has a container cap; the scheduler
allows three 4 GiB LEAN workers with only 2 GiB reserved for services. Native NATS
is possible, while ClickHouse still needs WSL on Windows and LEAN still uses Docker.
Removal of a verified stopped 3.586 GiB restore-test cluster was rejected by
automatic approval review (“blocked by policy”). **No files were deleted and no
runtime settings changed.** Next: diagnostic retention, measured service/worker
budgets (P6.15), verified backup completion and dependency-aware artifact retention.
See [the storage review](repository-maintenance.md#storage-and-memory-review--october-17-2026).

## Codex desktop crash investigation and workspace-view fix — 2026-10-17

**Done — containment applied; app-side crash handed to OpenAI:** Operator reported
repeated ChatGPT/Codex desktop crashes while working in this repository. Ten Crashpad
reports are retained (nine on 2026-10-17), with the latest Electron main-process crash an
access violation `0xC0000005` in `chrome.dll`, `ERR_WORKER_OUT_OF_MEMORY` worker events,
and 4.8M-file/476 GB `var/` data trees feeding the app's file search and turn-diff
snapshots. `.gitignore` now excludes the four bulk local data trees (`var/governance/`,
`var/research/`, `var/tracked_strategies/`, `var/tracked_models/`): the repository view
fell from 4,610,923 to 2,808 files for file search and from 4,610,057 to 1,948 untracked
files for git snapshots, with enumeration from 4.0 s/19.0 s to 0.1 s. Tracked `var/`
evidence is unchanged (160 files). The crash itself is in the OpenAI client (dumps were
uploaded via Crashpad); environment follow-ups (memory/pagefile headroom, sandbox reset,
network reconnects, app version) are recorded in [log.md](../log.md). No app calculation
source, monitoring, capital, broker or live setting changed.

## Remove the annual research cost ceiling — 2026-10-17

**Done — policy and audit; retest In Progress:** The operator removed the 44 bp annual-cost rejection rule.
Evaluate incremental returns after incremental trading costs, with net Sharpe,
return/drawdown guards, cost/delay sensitivity and chronological validation.
The executable diagnostic and historical-reproduction entry points are separated;
162 focused tests and Ruff pass. Seven cost-only withheld cases are identified
([audit](research-cost-policy-review-2026-10-17.md)). Guarded restart and fresh matched
reconciliation passed; the prior paper policy/cap was restored. Existing raw-input
coverage issues remain independent of this change. Next: replay the fixed 16-arm
cash-relative family against SOTA and monitored strategies and report Sharpe/Calmar
before another item. Frozen evidence and promotion controls remain separate.

## Historical cash-relative screen — superseded interpretation, 2026-10-17

**Done — 16/16 rejected; class-first candidate misses the cost ceiling:** the
registered cash-relative score is compared with merely removing BIL, under pooled
and class-first construction and monthly/0.10/0.40/0.80 adoption. Class-first monthly
clears the heuristic information margin (3.59x versus 3x), but costs 45.66 bp
against the unchanged 44 bp ceiling. All dynamic mappings cost at least 108.46 bp.
Later static payoff improvements are before costs, exposure-sensitive and already
inspected; no replay admission or promotion follows. Comparable-class evidence is
sparse. [Full findings](cash-relative-momentum-findings.md).
All 52 candidates/50 published histories are accounted for; BIL is a measured
reference with zero target. 72 tests, Ruff and independent checks of 5,800 targets,
16 policies, 5,698 adoptions and 554 paired payoffs pass; 2,900 parent targets
reproduce exactly. Inputs, code and results are hash-verified. The reserved
October 19-April 20 prospective design remains inactive after rejection.
Next: review the cost constraint and whether a separately frozen turnover mechanism
is justified with the signal fixed; no threshold/holding-period tuning or ceiling
relaxation. No app source, monitoring, capital, broker or live setting changed.

## Historical class and volatility screen — 2026-10-16

**Done — 16/16 mappings rejected; ready for review:** the frozen 50-fund
construction screen compares pooled/class-first selection, raw/volatility-normalized
126-session momentum and monthly/0.10/0.40/0.80 target adoption. Fourteen mappings
exceed the 44 bp cost ceiling. The two normalized monthly mappings cost 24.84/38.15
bp but have information margins of only 1.91x/0.55x versus the required 3x.
Their later-period mapping ICs turn negative; the pooled version averages 45% BIL
plus 41.64% cash. No mapping qualifies for portfolio replay.
[Findings, chart and full attribution](class-volatility-screen-findings.md).
57 focused tests and Ruff pass; independent checks reproduce 5,800 daily targets,
16 policies, 4,485 adoptions, 128 turnover windows and 2,144 IC observations.
The protocol, published inputs and source/result hashes are frozen. Stop this
item for review before another hypothesis; no retuning or FR25 rescue. Historical
membership/mandate limitations and P6.15 remain open. App calculation source,
monitoring, allocation and trading settings were not changed.

## Market-data freshness incident — 2026-10-15

**Repair deployed; broad catch-up running:** AAPL is audited/published through
October 14. The intraday selector now returns its five recorded symbols in 0.11s
(previously a 4.07 GB manifest scan exceeded a 45s timeout), and charts load.
The application owns automatic daily refresh for supported current-listing
candidates, with per-symbol quarantine/retry and retained historical conflicts.
Independent freshness checks now make missing/stale daily data and intraday gaps
degrade System health and create durable alerts, including when child processes
exit successfully with warnings. Market Data displays these warnings directly.
132 regression tests, Ruff and live API/browser checks passed. The original paper
approval policy/cap was restored after matched reconciliation; live remains disabled.
**Open:** catch up the broad daily backlog, investigate quarantines and unsupported
identities, and configure an external alert channel if required (SMTP is currently
unconfigured). Do not call broad coverage recovered until actual endpoints pass.
[Incident and recovery details](market-data-freshness-2026-10-15.md).

## Rebalance mechanism review — 2026-10-15

**Standing rule and publication checks complete:** Future research must evaluate
dynamic rebalancing alongside fixed-interval controls; this is recorded in
`AGENTS.md`, the continuous-research playbook and research-state rules. The operator
authorized commit/push of P4.22/P4.23 source, tests, findings and compact acceptance
receipts. Research source matches the accepted frozen versions; Ruff, document
links and receipt hashes pass. Concurrent market-data work is a separate change.

**P4.22 and P4.23 completed; top-six monthly retained:** The 132-scenario
fixed-top-six study retained monthly in all three annual selection windows and
the final trailing-three-year window. Both parents reproduce 70 monthly decisions;
six native LEAN/Python checks pass, including the 0.10 intramonth policies.
[Results](../research/target-change-rebalance-20261015-v1/results.md).
The joint (X, n) study completed 588 full-size scenarios: X is maximum selected
ETF count and n is the target-change threshold. All three annual selections and
the final trailing-three-year selection retain 6/monthly. Wider selection lowers
traded notional but reduces net return and Sharpe in this current FR25 pool.
Top four/monthly passes performance guards in two early windows, but fails the
registered neighbor-stability requirement; no pair passes in the later windows.
The 6-by-8 grid, Sharpe/return/drawdown guards and cost/delay scenarios were frozen
before joint results. [Joint findings](../research/selection-width-timing-20261015-v1/results.md). Trading settings
and live-disabled posture stay unchanged. The operator distinguishes strategy
change (`latest theoretical - last adopted target`) from trading alignment
(`latest adopted target - actual held`). Only strategy change is optimized;
housekeeping remains in Trading. This supersedes the initial review's proposal
to use held weights in the strategy trigger and include paper drift in the grid.

[Registered protocol](target-change-rebalance-plan.md): current FR25/14 primary,
F3/12 transfer check, full-pool validation later by explicit operator choice.
Monthly plus eight target-distance thresholds competes with monthly and daily
controls. Net Sharpe selection has fixed return/drawdown guardrails, chronological
three-year selection windows, neighbor stability, six cost/delay scenarios and
an explicit monthly fallback. Pin published inputs and verify all used hashes
before running; retain existing model cadence and full account-level accounting.
Existing historical periods are inspected evidence, not untouched holdouts.
The operator explicitly authorized last-monthly macro fallback when an exact
daily snapshot is absent; retain source timestamps and carry-age diagnostics.
F3 preserves its current legacy adjusted-price/source-volume activity proxy and
is a sensitivity comparison, not raw-activity transfer confirmation.
The [joint X/n protocol](../research/selection-width-timing-20261015-v1/protocol.json)
now has membership-turnover attribution, independent checks of 98 adoption
policies and six native LEAN/Python parity checks. All 1,453 top-six daily targets
per parent and 60 common parent economic replays match exactly. Expanded-pool
validation remains later, conditional on a separately qualified parent.
The downloaded Gârleanu-Pedersen journal paper
has verified identity, 32 pages and a provenance/hash record in references.

The initial review verified daily indicative targets, monthly backtests and the
existing paper individual-ETF 0.02 alignment policy. Its 109 passed / one skipped
focused checks remain dated review evidence. P4.22 implementation checks passed
114 tests with one optional skip before the joint-study extension. The joint
extension passed 119 tests with one optional skip; Ruff, report rendering and
artifact/input hashes pass.
[Snapshot](../var/reviews/rebalance-20261015.json) and [log](../log.md).
No strategy, funding, threshold or routing setting changed.

## Repository restructuring and maintenance — 2026-10-12

**Done — source and local maintenance:** Separated presentation assets, API
contracts and pure preview construction; repaired invalid preview inputs, cap
rounding and the relocated Alpha101 reference. Static page rendering and streaming
hash verification have measured improvements. Consolidated current docs and
preserved complete originals; compressed seven verified logs from 92.8 MB to 6.3 MB.
**Validation:** 1,691 passed / 55 optional skips; Ruff, local links, whitespace,
isolated wheel rendering, frozen bundle resources and archive hashes pass.
[Scope, measurements and recovery](repository-maintenance.md); receipts in
`var/maintenance/`. Existing uncommitted execution work and all trading/data gates
are preserved. **Deployed October 13:** guarded restart, matched reconciliation,
existing paper policy restored and application catch-up verified. Historical
partially filled orders remain in the ledger. Later source changes require their
own guarded restart; the source-identity check remains enforced.

## Execution readiness and ETF expansion — 2026-10-13

**Delivered — execution and first-wave study; research rejection ready for review:** scalable paper execution
contracts and FR25 readiness (P8.1-P8.5), then the accepted P4.16d first admission
wave, then reproducible full-admitted-pool backtests. Stage 1 inventory/rules were
reviewed and the operator instructed continuation. Preserve existing allocation
approval, reconciliation and live-disabled controls. Deliver a concrete conditional
5% FR25 / 95% F3 preview after readiness; tradability itself does not fund a strategy.
Baseline blockers: unbound FR25 financial/raw-activity inputs, first-component-only
instrument resolution and no execution contract registry. Record fresh operational
and parity evidence before calling FR25 paper-ready.

Source implementation and focused parity checks now pass; the immutable 14-ETF
execution registry contains fresh issuer/IB identities and successful account-bound
paper previews. All 38 proposed additions also have verified broker identities.
Deployment, app catch-up and the conditional allocation preview passed on October
13; allocation remains F3 100%. Recorder publication now covers 39 of 41 entries.
The October 14 retrospective study pins the completed catalog, reviews all 52
candidates and supports 50 common-window histories (BWX held, CPER zero-volume limitation).
Expanded FR25 failed the registered pre-test (67.73 bp implied cost versus 44 bp; IC −0.01463), so its portfolio replay was withheld. Original-pool 5/10 bp controls and URTH passed native parity. [Full findings](etf-expansion-findings-2026-10-14.md). Final acceptance: 1,713 full-suite tests passed / 55 optional skips, five additional preview/frozen-runner checks and 14 dispatcher regression checks (one new). App catch-up and refreshed FR25 preview passed, reconciliation matched, and the same F3 policy was restored. Final platform health is OK. Funding remains F3 100%; there is no pending allocation.
See [session evidence and acceptance](execution-readiness-2026-10-13.md).

## Current priorities

**2026-10-17 research session — Review:** P4.16d stage 1 accepted: 299
symbol/regime records (298 provisional fund references), proposed taxonomy and
complete gap matrix, 38-addition first wave alongside the original 14, frozen
proposed screening rules and file-density/capacity estimates. All 16 input
snapshots and the pinned catalog hashes verify; 11 inventory tests pass.
[Inventory report](etf-universe-inventory-2026-10-13.md). Research ingestion is
enabled; expanded FR25, class/volatility and the cash-relative follow-up all failed
their pre-tests. The cash-relative class-first rule clears the heuristic IC margin
but misses cost admission. [Latest findings](cash-relative-momentum-findings.md).
No allocation change. The HYXU closure claim is corrected
from primary sources; its legacy history and new EUHY regime remain quarantined.

- P4.19 retrospective execution references complete; retain current execution policy.
  [Findings](execution-reference-findings.md). Missing fills/contracts and raw-unit
  limitations remain; this does not qualify continuous intraday research inputs.
- P4.16d: substantial ETF candidate inventory, dated taxonomy and comparable groups,
  followed by audited admission, app readiness and full-pool research.
- P6.15: measure worker memory and scheduling before expanding concurrency.
- P8.1–P8.5: minimum 14-ETF paper execution acceptance passed; broader registry
  migration and market support remain separate work.
- Last recorded paper allocation: F3 100%, revision 5, no pending change (2026-10-12
  acceptance receipt). This is historical context; consult app state before acting.

## Operating Rule

Before starting work:

1. Read `docs/industrial-platform-plan.md`, `docs/execution-kanban.md`, and `log.md`.
2. Pick the highest-priority `Pending` or `Review` item that is not blocked.
3. Move it to `In Progress`.
4. Record assumptions or blockers in the item notes.

After finishing work:

1. Move completed items to `Done` only after tests or equivalent verification pass.
2. Add evidence paths, commands, or reports.
3. Update dependent items if their status changed.
4. Add a concise entry to `log.md`.

## P0: Project Memory And Governance

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P0.7 | Pending | Decision log discipline | Every architecture or production-control decision gets a dated `log.md` entry. | Ongoing habit, not a one-time task. |

## P3: Market Data Recording And Data Quality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P3.4a | In Progress | Pilot raw-data proving and audit loop | Record a small ETF pilot, audit raw/catalog coverage, inspect gaps/duplicates/freshness/disk use, and only then scale. | Pilot capture and historical recovery are implemented. Delayed quote samples remain inspection-only; paid real-time entitlement and admitted continuous intraday coverage remain unresolved. See [intraday recovery](intraday-recovery.md). Historical receipts remain in the archive. |
| P3.4 | In Progress | Normalized bar/quote pipeline | Convert raw records and external daily loaders into columnar golden daily/intraday tables with quality flags. | Daily serving and governed research publications exist. Remaining: normalized intraday serving, explicit source precedence/disagreement and comprehensive gap/freshness panels. Old row counts and repair receipts are historical; see [data governance](price-governance-2026-09-26.md). |
| P3.4c | In Progress | Migrate strategy, rebalance, PnL, and backtest market-data reads to ClickHouse | Signal generation, portfolio rebalance proposal generation, dashboard valuation/PnL, and stored backtests read daily bars from ClickHouse `market_data.daily_bars` instead of SQLite `price_bars`; SQLite price endpoints are either deprecated or explicitly marked legacy. | PostgreSQL/ClickHouse are the active store defaults; SQLite is explicit offline test/recovery only. App strategy decisions consume pinned governed publications. Remaining: intraday serving and full migration/soak acceptance. See [analytics migration](analytics-migration.md). |
| P3.5 | Pending | Data freshness checks | Detect stale bars, missing FX, source gaps, duplicates, and clock drift. | Alerts must be generated. |
| P3.6 | Pending | Replay a trading day | Reconstruct a paper-trading day from recorded data and compare to stored decisions. | Phase 2 exit criterion. |
| P3.7 | Blocked | Paid/primary market-data vendor | Source-of-record vendor choice and credentials are not settled. | Use IB/Yahoo/Tushare only as current interim sources. |
| P3.8 | Pending | Promote `review` series to `audited_with_limitations` | Investigate the `review` population, fix the fixable gaps, and stop conflating "fixable data gap" with "never certified". Acceptance: every reviewed series is either promoted with evidence or reclassified under an explicit permanent limitation; the decision gate in `portfolio/decision_inputs.py` then reflects a meaningful distinction. | **Deferred by the user 2026-10-10:** leave the gate as it is for now and spend effort later on promotion. Triage of batch `b02d9372…` (5,341 series; 1,056 `audited_with_limitations`, 3,482 `review`, 803 `unavailable`): all 3,482 `review` series carry the same four certification gaps (`identity_not_certified`, `raw_tape_not_certified`, `listing_boundary_not_certified`, `listing_history_not_certified`), and 3,471 also carry at least one data gap. By research role the population is `underlying-sector-hhi-20260926-v1` (3,460) and `ivv-constituents-2012-2026-v1` (680, partly overlapping), i.e. research-only constituent stocks. **Only 4 `review` series are ETFs, and none is in the trading universe: IVV (1,014 cross-source conflicts), XLF (890), XLRE (2 volume conflicts), HYXU (stale 2020 tail, 1,304 conflicts; **2026-10-13 correction:** name/symbol and mandate changed to EUHY in 2025, not a proven 2020 closure; [evidence](etf-universe-inventory-2026-10-13.md#corrected-hyxu-identity)).** Suggested tiers: (1) the four ETFs, including separately auditing HYXU/EUHY dated identity and mandate regimes; retain `review` until evidence qualifies; (2) the two data-gap classes across the constituent population — `volume_conflicts` 2,818 and `cross_source_conflicts` 2,401 — which likely share a few systemic root causes (provider volume conventions, source precedence) and so may flip in bulk from one rule fix; (3) identity and tape certification, which needs a security master and is blocked on the same access gap as P3.7/CRSP. |

## P4: Research, Backtest, And Promotion Registry

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P4.1 | Pending | Strategy spec schema | Versioned strategy spec includes universe, data, features, schedule, risk, execution, and artifacts. | Required before registry. |
| P4.2 | Pending | Strategy promotion registry | Persist state transitions from idea to retired with evidence and approval. | Should emit promotion events. |
| P4.3 | Review | LEAN integration design | Document how current strategy definitions map into LEAN or LEAN-equivalent runs. | LEAN design is implemented; reconcile the original milestone with [worker contract](lean-backtesting.md) and remaining promotion requirements. |
| P4.4 | Review | LEAN smoke backtest | One current SOTA or simplified strategy runs through LEAN path with reproducible artifacts. | Native smoke and long-history parity passed in [validation evidence](lean-validation-2026-09-26.md); do not treat historical data as certified for promotion. |
| P4.5 | Review | Backtest artifact hashes | Reports, inputs, configs, and outputs are hashed and linked to strategy versions. | Frozen bundle and output hashes plus registry exist; acceptance now concerns coverage of the broader promotion contract. |
| P4.6 | Pending | Overfit/stability gate | Promotion requires split, benchmark, turnover, fee, stress, and parameter stability checks. | Extend current SOTA workflow. |
| P4.7 | Review | LEAN runtime/dependency setup | Requires installing/configuring LEAN runtime or choosing equivalent deployment path. | Pinned local container runtime is installed and used. Prior setup blocker is superseded; P6.15 resource review remains open. |
| P4.22 | Done; monthly retained | Target-change threshold rebalance study | Latest theoretical versus last adopted target; independent of account holdings; causal selection, guards, cost/delay stress and native parity. | [Results](../research/target-change-rebalance-20261015-v1/results.md). 132 scenarios, six native checks. Explicit monthly macro fallback; F3 legacy-basis sensitivity. |
| P4.23 | Done; 6/monthly retained | Joint selection-width X and target-change threshold n | Frozen 6-by-8 grid; 588 full-size scenarios, six native checks and 98 independent adoption checks. Wider selections reduce turnover but do not qualify under FR25 selection guards/stability. | [Results](../research/selection-width-timing-20261015-v1/results.md). F3 is legacy-basis sensitivity; expanded-pool validation later. No monitoring or trading changes. |
| P4.16d | Review: expanded FR25 and subsequent class/volatility screen rejected | Substantial tradable ETF expansion, granular classes and volatility-aware ranking *(operator reaffirmed 2026-10-11)* | Versioned candidate inventory, dated taxonomy and data/contract gap matrix; staged audited admission; scalable app and paper-execution contracts; then controlled full-pool comparisons. Design capacity for hundreds of candidates, with duplicate-exposure controls and risk-normalized class ranking. | [299-record inventory](etf-universe-inventory-2026-10-13.md), 38-addition recorder wave and [50-fund FR25 diagnostic](etf-expansion-findings-2026-10-14.md) completed. The separate [October 16 construction screen](class-volatility-screen-findings.md) rejects all 16 raw/risk-normalized, pooled/class and monthly/dynamic mappings. No expanded candidate qualifies for replay. Review the cash/bill concentration and incomparable-payoff issue before a new hypothesis; historical membership reconstruction remains open. Published pinned inputs only; admission never mandates allocation. **P4.16c remains parked.** [Plan](signal-decay-and-alpha-plan.md). |
| P4.20 | Pending | Decay-based promotion gate | Require any new signal to demonstrate a minimum estimated half-life and sub-period IC stability before it can enter a monitored recipe. | Registered October 10; depends on P4.13. Structural protection against the survivor-selection problem described in the plan's Appendix A. Governance only. |
| P4.21 | Pending | Look-through constituent alpha | Compute the structurally cross-sectional alphas on the constituent cross-section (680 IVV constituent series plus issuer holdings and sector data) and aggregate holdings-weighted to ETF scores. | Registered October 10 and deferred. The only honest route to the 76 structurally cross-sectional alphas, which need breadth that 14 ETFs cannot supply. Carries three disclosed caveats: index-membership history is a survivorship trap, issuer holdings snapshots are prospective-only from October 2026, and the constituent series are the `review`-status population from P3.8. Blocked on the constituent-coverage assessment; do not start before P4.16 answers whether the cross-sectional premise holds. |

## P5: Portfolio Blotter And Execution Controls

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P5.1 | Pending | Rebalance blotter domain model | Model current, target, proposed orders, expected cash, FX, fees, residuals, and constraints. | Stronger than current proposal preview. |
| P5.2 | Pending | Pre-trade check engine | Checks stale data, missing FX, price bands, buying power, duplicate orders, open orders, turnover, concentration, and live caps. | Must block routing. |
| P5.3 | Pending | Blotter API | Dashboard/API can show proposal, constraints, violations, and operator decision actions. | Current dashboard can be extended. |
| P5.4 | Pending | Resize/defer workflow | Operator can approve, reject, resize, defer, or cancel generated orders. | Must persist audit events. |
| P5.5 | In Progress | IB connection health gate | Confirm server time, account, managed accounts, next valid id, and profile before routing. | Read-only recurring broker health, failure backoff and reconnect wakeups exist. Preserve fresh environment/account readiness before every route; ongoing hardening and external Gateway login remain operational dependencies. |
| P5.6 | In Progress | Broker reconciliation gate | Compare IB positions, cash, open orders, fills, and commissions before routing. | Routing and EOD enforce fresh broker reconciliation; durable individual executions and reviewed recovery exist. Broader open-order/commission reconciliation acceptance remains open. See [trading operations](trading-operations.md). |
| P5.7 | Pending | Live kill switch | A hard config/runtime switch prevents live order routing immediately. | Must be tested in paper. |
| P5.8 | Pending | Live capital caps | Per-account, per-strategy, per-symbol, per-order, turnover, and drawdown caps. | Required before Phase 5. |
| P5.9 | Blocked | Live account enablement | Requires explicit human approval, credentials, account id, and proven paper evidence. | Keep live disabled. |
| P5.11 | Blocked | Intraday signal activation and stop-loss execution | Publish audited intraday bars usable for research, then add intraday routing, broker-side or monitored stops, intraday pre-trade risk checks and intraday reconciliation. Until both exist, any stop-loss research is limited to a daily-resolution approximation (a stop fills when the session low breaches it), and that approximation must be disclosed because it flatters stops in gap-down markets. | Registered 2026-10-10 from the [signal decay and alpha plan](signal-decay-and-alpha-plan.md). This is a **platform** workstream, not research: there are no intraday tables in ClickHouse, the recorder holds only raw five-second sampled quotes for five ETFs from 2026-04-04 flagged `research_approved: false`, and routing is a single monthly TWAP window. Blocked on intraday data publication plus P5.1-P5.4. |

## P6: Observability, Alerts, And Incidents

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P6.15 | Pending | Research worker deployment and resource budgets | Benchmark real host/container memory, CPU, startup/data-copy costs and whole-batch latency; compare host-native LEAN, right-sized containers and multicore scheduling. | Operator requested October 11. Fixed 4 GiB/run plus 2 GiB headroom caps LEAN at three jobs on 15.39 GiB Docker, despite 31.55 GiB host RAM. Preserve parity, resource headroom and operator/ClickHouse latency. [Plan](calculation-performance.md#p615--worker-deployment-and-resource-budget-review). |
| P6.1 | Pending | Metrics contract | Define service, data, queue, strategy, portfolio, execution, and reconciliation metrics. | Prometheus/OpenTelemetry compatible. |
| P6.2 | Pending | Local metrics endpoint | API/service exposes metrics for scraping or dashboard display. | Start with FastAPI endpoint if needed. |
| P6.3 | Pending | Grafana dashboard plan | Dashboard panels defined for data freshness, queue lag, broker state, PnL, exposure, and alerts. | Implementation depends on metrics path. |
| P6.5 | Pending | Desktop popup alert channel | Local machine popup for trading-critical warnings/errors. | Windows implementation required. |
| P6.6 | Pending | Incident registry | Alerts can open/update/resolve incidents with durable status. | Links to event ids. |
| P6.7 | Pending | Alert delivery audit | Track which channels received each alert and whether delivery failed. | Required before live. |
| P6.8 | Blocked | SMS/push provider | Requires provider choice and credentials. | Email exists; urgent channel pending. |

## P7: Daily Operating Loops

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P7.1 | Pending | Daily post-trade report | Generate PnL, attribution, slippage, fills, reconciliation, and alert summary. | Uses `.agents/skills/daily-post-trade-analysis.md`. |
| P7.2 | Pending | Continuous research report | Daily/weekly challenger report updates research state and candidate status. | Uses `.agents/skills/continuous-research-loop.md`. |
| P7.3 | Pending | Robustness review report | Weekly service/data/queue/broker/alert health review. | Uses `.agents/skills/system-robustness-review.md`. |
| P7.4 | Pending | Promotion review report | Formal approve/reject/defer/retire artifact for strategy transitions. | Uses `.agents/skills/strategy-promotion-control.md`. |
| P7.6 | Pending | Disaster recovery drill | Backup and restore check for trading-critical local state. | Required before live. |

## P8: Execution Generality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P8.1 | Done for the reviewed US-listed USD ETF boundary | Contract identity registry | IB `reqContractDetails` captured raw, audited and published as an immutable hash-versioned registry carrying `conId`, `secType`, `localSymbol`, exchanges, currency, multiplier, `minTick` and trading class. Ambiguity fails closed. Re-derivable from retained raw evidence. | Foundation for everything else. Uses the existing raw-first, audit, publish discipline rather than a new pattern. |
| P8.2 | Done for the reviewed US-listed USD ETF boundary | Symbol to contract resolution | Resolution requires explicit disambiguation keys (ISIN, or exchange plus currency hint) and rejects ambiguity instead of guessing. Deterministic and recorded per decision. | The hard correctness problem: `BHP` is an ADR on NYSE and a listing on LSE and ASX. A ticker-only lookup is the failure being retired and must not return as the new default. |
| P8.3 | Partial: frozen membership and component unions implemented | Registry-backed universe selectors | Universes become declared selectors over the registry plus explicit membership, replacing the literal `Instrument` dicts in `research/etf_universe.py`, `all_weather_universe.py` and `stock_universe.py`. Existing universes resolve identically to today. | A new instrument then costs a registry entry, not a code edit. Research definitions keep their frozen membership. |
| P8.4 | Done for the reviewed US-listed USD ETF boundary | Instrument admission gate | A contract is tradable only when identity is verified, an audited price history exists, a CNH FX path exists, IB reports it tradable for this account, and its market rules are registered. Admission is an immutable event and every instrument can answer "why not tradable". | Admission stays narrow and reviewed; capability is what generalises. |
| P8.5 | Done for the reviewed US-listed USD ETF boundary | Capability check replacing the hard-coded allocation gate | The shared conservative execution-contract check is extended to verified instrument capabilities: a strategy is allocation-supported when every instrument in its resolved universe is admitted for execution and its execution contract is registered. FR25 and M1/14 become allocatable by admitting XLE and XLB, with no code change. | 2026-10-13: UI/backend share the registry-backed check; FR25/M1 admission and the conditional FR25 preview passed. First customer is deliberately XLE/XLB, which are US-listed USD ETFs, so P8.1-P8.5 need no FX, calendar or data widening. |
| P8.6 | Blocked | Per-currency CNH FX path | Non-USD instruments valued and reconciled in CNH with point-in-time discipline and a declared authoritative source per pair. | **Blocked on data, not engineering:** FX is a documented unresolved input class. Until it is resolved, "any IB tradable" silently means "any USD tradable". |
| P8.7 | Pending | Per-venue calendars and execution windows | Each listing venue has its own session calendar and an execution window in its own timezone, with a defined convention for asynchronous sessions and an explicit valuation date. | `exchange-calendars` is already a dependency. Today routing assumes US sessions only (`live/sota.py:113,281`). |
| P8.8 | Pending | Lot size, tick and minimum-size enforcement | HKEX board lots and TSE hundred-share lots cannot produce an invalid quantity; venue tick regimes enforced at sizing. | The US ETF registry validates whole-share support and cent ticks. Board-lot multiples, non-US tick regimes and broader multipliers remain unsupported. |
| P8.9 | Blocked | Multi-currency governed price lane | Non-USD and non-ETF series admitted through the existing audit and publication process, with per-venue sources, retention rights, basis and corporate-action coverage. | **Blocked on source and licence decisions.** `research/governed_refresh.py:144` currently requires `currency == "USD"` and `instrumentType == "ETF"`. |
| P8.10 | Pending | Generalised exposure, staleness and reporting | Country and currency aggregation, staleness checks and reports correct across venues and calendars. | Reconciliation itself matches on `order_ref` and is already symbol-agnostic, so this is mostly free. |

## Next Recommended Work Order

Revised after the 2026-10-11 second review. The research queue is now governed by the
[signal decay and alpha plan](signal-decay-and-alpha-plan.md); the items below
are the cross-cutting platform work that runs alongside it.

**Research, one item at a time with a review between items.** The second review and the
fixed P4.18 experiment and the scoped P4.19 retrospective comparison are complete. Next
complete the **P4.16d cash-relative net retest** with the signal fixed
([scope and audit](research-cost-policy-review-2026-10-17.md)); compare Sharpe and
Calmar against SOTA and monitored strategies, then stop for the operator report.
Register horizon, peer-group, incremental payoff and actual fill-based exit
contracts before any new budget/TP/SL grid. See the current priorities at the top of the plan.

**Platform, in parallel:** the new **P8** execution-generality phase
([plan](execution-generality-plan.md)) removes the 12-ETF assumption. Its critical
path P8.1–P8.5 is deliberately narrow — XLE and XLB are US-listed USD ETFs, so
opening the 14-ETF allocation gate needs no FX, calendar or data widening — and
it replaces the hard-coded strategy gate so the next strategy needs no code edit.

Platform and data work, in parallel:

1. Qualify original-release sector and energy history — the standing prerequisite for any new feature block. Historical EIA/CFTC/issuer observations are captured prospectively and are not admissible for earlier decisions; this remains unresolved and blocks new feature blocks that depend on it.
2. Resolve the IB market-data entitlement blocker (IB 10089/420 for `reqRealTimeBars`) so live capture can move off the delayed sampled channel, which is inspection evidence and not complete interval OHLCV. This is a precondition for P5.11.
3. P3.8: promote `review` series where the gaps are fixable, starting with the four ETFs (IVV, XLF, XLRE, and resolving the HYXU/EUHY mandate transition without splicing the stale series), then the two data-gap classes that likely share systemic root causes.
4. P3.4: add ClickHouse source-observation tables, source precedence, cross-source disagreement checks and the daily gap/source-disagreement panels.
5. P4.1: define the versioned strategy spec schema, then P6.1 metrics and P5.1 the stronger rebalance blotter domain model.
6. Register the remaining governed-data cleanups as small items: the two private-name couplings between `research_etfs` and `governed_refresh`, and the absence of a published-batch list route in `web/governed_data.py`.

**Deferred / not started by this plan:** P4.21 (look-through constituent alpha)
until the next look-through research design and required published inputs are accepted; P5.11 (intraday activation and stops) until audited intraday
data is published and an intraday execution stack exists.
