# Project Log

## 2026-09-25 - Fill prices, TWAP estimates, paper automatic approval and opening P&L reset

- Final UI hardening keeps the reviewed policy revision fixed while its dialog is open, binds policy to the configured environment, and labels the P&L cutoff explicitly in New York time. Follow-up policy/UI checks: 21 passed, 1 skipped (Postgres already covered by the full/focused runs); final UI checks: 9 passed. Final dashboard/dispatcher PIDs 37548/35860.

- Added retained average fill prices beside quantities in the blotter, plus full-window duration-weighted 1-minute TRADES TWAP estimates, coverage/window provenance, buy/sell signed slippage bps and quote-currency price cost. Positive is adverse; fees/commissions are excluded. Estimates require complete observed data and completed windows. The read-only client defaults to ID 191 and caches raw minute bars locally; unavailable requests retry after five minutes while viewed. Actual IB requests reported the US historical-data farm `ushmds` disconnected; local delayed aggregates covered only 184 of the expected 360 five-second intervals for SPY/GLD in today's window. No substitute benchmark is published. Next: restore IB historical-data connectivity/permissions and verify all six full-window benchmarks.
- Added an audited optional paper policy, left OFF. The UI explicitly enables approval plus submission of new current-strategy TWAP proposals under an operator-set gross CNH cap. Existing queues are excluded. Policy is bound to machine/workspace/environment/broker/strategy; single verified DU account, fresh matched reconciliation, exact latest daily data/FX, sizing/target limits, liabilities, local/broker working/uncertain orders and regular-session deadlines gate routing. A durable attempt claim precedes atomic pending-to-approved approval and normal router handoff; interrupted/partial/failed attempts require manual review. SQLite/PostgreSQL decisions support expected status, and manual API decisions/routing share the order lock. Existing live prohibition is unchanged. Policy revisions/attempts survive restart; switch events enter the outbox. First automatic paper cycle still needs operator enablement and observation.
- User explicitly requested restarting live P&L before today after resetting the paper account. Verified matched flat snapshot `ib_paper_account_snapshot_20260925_193904.json` held HKD 1,018,123.95 at 11:39:04 UTC before all today's fills. Applied baseline `d229466e93af`, cutoff `2026-09-25T03:59:59.999999Z` (immediately before Sep 25 New York), zero carried P&L/lots/trade count. Saved an explicitly derived prior-close opening cash reference retaining the actual capture time and source path. All 48 current executions and six holdings match and remain active; 244 order records and earlier baselines/snapshots remain immutable audit history. Audit: `var/live/pnl_opening_reset_d229466e93af.json`. Active P&L snapshot/comparison history excludes prior reset episodes without deleting records.
- Validation: full suite 522 passed, 1 skipped in 303.27s; 38 focused tests after cache/metadata hardening passed. Includes SQLite/Postgres approval status gates, automatic-mode eligibility and no retries, TWAP coverage/sign/persistence failures, opening reset holdings/provenance, preserved history and real JavaScript columns. Dashboard/dispatcher restarted; real browser shows six full fills and prices, Manual/off policy with review dialog, Sep 24 account opening reference, and Matched reconciliation. No broker order or automatic-mode enablement was performed during implementation.

## 2026-09-25 - Blotter date filters and completed TWAP visibility

- Confirmed the initial six TWAP orders fully filled: DBC 586, EWH 1161, EWJ 209, EWY 29, GLD 40, SPY 52 shares, across 48 executions. Reconciliation matched six holdings. Orders were retained in both the local ledger and Gateway completed snapshots; the previous default Working filter hid them after completion.
- Default is now Today plus All statuses. Added Last 7 days, inclusive Date range and All dates alongside Filled, Working, Needs attention, Completed / closed and Missed filters. Missed is separate from completed orders. Dates use the intended New York session or legacy actual submission date, never bulk update time. Submission/update timestamps display the browser's named local timezone. Newest dates/submissions first; counts and audit details follow filters. Current unlinked working orders stay visible with unknown dates, and a notice identifies working local orders outside the date range.
- Real browser verification found completed callbacks with quantity zero, previously displayed as filled/0. Display now falls back to the retained order quantity and prioritizes durable full-fill evidence over stale working observations. Order actions remain disabled for filled records. No history, approval, broker order or baseline was changed.
- Verification: nine UI/Node tests passed, including date boundaries/DST, legacy missed updates, completed-order retention, sort order, status combinations, invalid ranges, external unknown dates and completed quantity/action handling. Browser Today + All statuses displayed six filled rows with correct totals and timestamps; All dates + Missed exposed 220 historical records; restored Today + All statuses. Dashboard/dispatcher restarted to 39140/32936, recorder/Gateway/NAS retained, reconciliation remained matched. Guide updated at `docs/trading-operations.md`.

## 2026-09-25 - Active TWAP reconciliation synchronization repair

- Operator's retry successfully sent all six initial TWAP orders (broker IDs 20–25). The reported history-review warning was transient: reports around 13:46–13:50 UTC contained only `broker executions await durable synchronization`, while the underlying records had no durable execution issues. Periodic fill sync and subsequent reconciliation queried different execution batches during active slicing; the page retained its own older warning after management reconciliation had caught up.
- Added explicit `sync_new_fills` reconciliation mode for API/management operations. Persist each matching order's exact freshly queried batch through the existing atomic fill validation/audit/outbox path, then obtain the account snapshot and compare holdings. Diagnostic callers retain explicit sync semantics. No execution IDs, quantities, corrections, or account identities are guessed; existing durable conflicts stay blocked and cannot be removed through reset.
- Added a separate report `execution_sync_pending` field/status for benign pending persistence. This still blocks routing and resets. UI labels it as synchronization, explains that existing broker orders continue, polls latest reconciliation every 15 seconds, and ignores older asynchronous results. The real history-review warning remains for durable conflicts.
- Tests: affected execution/reconciliation/recovery/service/API/UI suites 95 passed; 10 new SQLite/PostgreSQL tests verify exact-batch persistence, replay idempotency, correction/gap handling and route/reset blocking; UI suite 7 passed including actual JavaScript rendering and stale-response rejection. Restarted dashboard/dispatcher to 6512/31132; Gateway, recorder and NAS worker preserved. At 13:57:06 UTC a fresh runtime check matched 30 executions and six positions with zero execution issues, pending sync or position differences. DBC 350/586, EWH 700/1161, EWJ 140/209, EWY 20/29, GLD 30/40, SPY 40/52 filled at that observation; orders still in progress. No agent broker action or baseline reset. Next: verify final broker fills and reconciliation after the execution window.

## 2026-09-25 - Proposal readiness and post-handoff approval repair

- Traced the empty initial queue to missing HKD/CNH refresh, stale USD/CNH, repeated legacy zero-volume repairs delaying EOD, and undated historical approvals. Operational FX now uses observed IB USD/CNH midpoint daily closes and matched-date USD/CNH / USD/HKD crosses, retaining source observations under ignored `var/market_data/fx_observations/`. No onshore CNY substitution or stale carry-forward. Reject unclosed FX sessions. Refreshed September 24 USD/CNH 6.71595 and HKD/CNH 0.8563532036978004; September 24 EOD completed.
- Old PyPI SDK negotiated protocol 157 and failed Gateway FX requests with 10285. Installed official IB API 10.45.1 from its pinned vendor archive via `scripts/install_ib_api.py`; SHA-256 checked. Added old/new error callback and cancellation compatibility, cash/IDEALPRO midpoint historical contracts and dedicated FX client 181. Updated installation docs and protobuf dependency. Restarted dashboard/dispatcher and recorder; Gateway/NAS ownership preserved.
- Automatic alignment refreshes all required currencies before readiness checks. Normal EOD restricts zero-volume repair to the current target; explicit historical refresh keeps historical repair enabled. Treat legacy undated approvals as history only when all attempts are covered by the reconciled baseline; uncertain/missing/new attempts still block. No historical approvals or broker states rewritten. Queue and readiness refresh every 15 seconds.
- Generated initial proposal `initial-9f6f68b03399-20260925`: DBC/EWH/EWJ/EWY/GLD/SPY TWAP buys for 09:35–10:05 New York / 21:35–22:05 Shanghai, based on September 24 completed data. Operator clicked approval while verification was in progress. Approval persisted but the first database reservation failed: Gateway returned ID 1 already present in NAS-restored history (local maximum 19). Trace retained in ignored `var/log/operator_dashboard.approval-id-collision-20260925.err.log`.
- Routing now selects max(Gateway next ID, highest retained local ID + 1), preserves the database uniqueness/intent guards, and stops with a structured operator message on connection/reservation/persistence failure. Partial batches retain their recorded legs; uncertain outcomes still block retry. No automatic retry or approval rollback. Verified against both SQLite and disposable PostgreSQL with a reset/larger Gateway sequence and first/second-leg reservation failures.
- Verification: full suite 465 passed, 1 skipped before the ID fix; final focused FX/UI/API/routing/management/regression suite 128 passed. Whitespace check passed. Final dashboard/dispatcher PIDs 6216/33364. At 13:42 UTC fresh Gateway snapshot had zero orders, and this approved proposal had zero broker records; EOD through September 24, heartbeat current, no service error. Agent did not submit/amend/cancel broker orders. Next: operator review and **Resubmit Failed/Missing** before 14:05 UTC; validate broker acknowledgements/fills and reconciliation after the operator sends. Live remains disabled; approval and 2 percentage point drift policy unchanged.

## 2026-09-25 - Docker socket recovery and platform startup

- Reproduced Docker Desktop 4.79.0 failure replacing stale Windows AF_UNIX sockets. Preserved `%LOCALAPPDATA%/Docker/run` as timestamped `run.stale-*` directories and the socket-only `%LOCALAPPDATA%/docker-secrets-engine` as a timestamped sibling. Each rename occurred with Docker stopped; no container volumes or settings were deleted. A failed intermediate startup recreated an inference socket, so its runtime folder also needed preservation.
- Docker engine 29.5.3 now responds. Standard platform startup completed with PostgreSQL, ClickHouse, NATS, dashboard, dispatcher, recorder and NAS backup worker. `/operator` and `/platform` return 200.
- ClickHouse SQLite import: 140,686 daily bars and 3,790 FX rates. Default 5,000-row batch exceeded the ClickHouse partition-per-insert limit; the documented 1,000-row batch succeeded. Final daily count 140,816 across 39 symbols, latest 2026-09-24, including fresh provider backfill. This is not a full copy of source-machine ClickHouse or raw intraday history.
- Paper TWS 7497 remains unavailable; trading-management loop is degraded. Recorder daily backfill succeeded and service is idle before market open, but E:/Z: recorder storage paths are absent on this PC and need local configuration before intraday capture. Paper/live and approval checks remain intact.
- Explicit post-start NAS backup remains pending on NAS I/O after producing local PostgreSQL/SQLite snapshots. SMB port is reachable, but an independent latest.json read also stalls. Preserve active ownership and operation lock; do not switch PCs before a successful clean handoff. Runtime health verified independently.

## 2026-09-25 - PostgreSQL provisioning and receiving-PC restore

- NAS authentication now works; verified both SHA-256 hashes of source snapshot `218c1db999494848abcfaf47944e5a35`.
- Operator provided local administrator credentials. Created dedicated empty `systematic_trading` database, `st_owner` NOLOGIN, and non-superuser `st_app`, `st_migrator`, `st_readonly` roles with generated passwords in ignored `.env`. Granted migrator owner-role membership, restricted database connections and set UTC timezone.
- Standard NAS prepare completed. App login and all 14 PostgreSQL source table counts verified; restored SQLite integrity passed.
- Docker cannot initialize its stale `dockerInference` socket. Rename failed; automatic approval review rejected socket removal. Existing storage contract rejected PostgreSQL plus SQLite market data, leaving dashboard unstarted. Clean stop completed; final NAS backup published and ownership released. No storage contract or broker gate weakened.
- Next: recover Docker, start standard stack, seed ClickHouse and verify service health. Paper TWS API is also unavailable.

## 2026-09-25 - Receiving-PC handoff preflight

- User requested NAS database restore and local service startup. Verified Python dependencies (including psycopg, FastAPI, NATS, IB API and timezone data) and running PostgreSQL 18.
- Restore blocked: `192.168.1.32:445` unreachable, Windows NAS neighbor unresolved, and no local PostgreSQL credentials configured. Passwordless connections require authentication. Requested NAS address/connectivity and local credential setup from the operator.
- Created ignored `.env` from the template with paper mode and PostgreSQL/ClickHouse backends. Requested Docker Desktop startup; Linux engine remained unavailable during preflight. Paper TWS API port 7497 is closed.
- Network retry restored TCP access to NAS SMB, but Windows share enumeration returns system error 5 (access denied). Docker logs identify startup failure initializing the `dockerInference` Unix socket. NAS authentication, PostgreSQL credentials and Docker recovery remain outstanding.
- No database restore or NAS ownership mutation performed; application services remain unstarted. Resume with the standard handoff/startup scripts after prerequisites are available; verify snapshot integrity, local data, periodic backup and service health before claiming completion.

## 2026-09-25 - Publish NAS handoff and verify the real backup

- Refreshed PostgreSQL and SQLite snapshots on WD My Cloud and released the source workstation's ownership. Current NAS generation: `218c1db999494848abcfaf47944e5a35`, under `\\192.168.1.32\Public\systematic-trading\snapshots`. Local state is clean; no owner or operation lock remains. Source application services remain stopped for handoff.
- Downloaded and verified SHA-256 checksums from the NAS, restored the real dump into a disposable PostgreSQL cluster, and compared row counts and normalized content hashes across all 14 tables. Restored SQLite passed integrity and logical-content checks across its 12 tables. PostgreSQL dump text itself differs across server timezone/default-schema-comment settings, so the restore comparison uses normalized row content instead of treating dump formatting as data loss. The local production databases were not restored or rewritten.
- Saved the verification report on the NAS at `verification/218c1db999494848abcfaf47944e5a35.json`. Backup sizes: SQLite 42,094,592 bytes; PostgreSQL 25,296,202 bytes. Added the new-PC checklist to `docs/database-sync.md`; infrastructure, private credentials, ClickHouse and raw-data migration remain explicit prerequisites/exclusions.
- Published migration commit `48e49d0108b774a7ed0c4e9a3a24bc8dc150f2de` to `origin/master`; verified the remote SHA equals the local tested commit. Unrelated backfill edits, WSL/research notes and runtime reconciliation files remain outside the commit. Git HTTPS fetch worked with command-local Schannel, but subsequent push connections timed out. Published the identical blobs/tree/commit through the authenticated GitHub Git Data API and advanced the branch without force; no persistent Git settings changed.
- Validation: exact staged-code regression **356 passed, 1 skipped in 253.22s** from an isolated index export. PowerShell launcher parsing and staged whitespace checks passed. The skipped optional network smoke test is separate from the successful real-backup restore drill above. The next action is new-PC provisioning followed by normal platform startup; keep the source PC stopped until handoff completes.

## 2026-09-21 - NAS database handoff between PCs

- Implemented `config/database-sync.json`, `storage/nas_sync.py` and `scripts/sync_databases.py`, integrated into standard local platform start/stop and guarded standalone dashboard startup. Default target is `\\192.168.1.32\Public\systematic-trading`; backups run every 300 seconds while active.
- Chose a persistent single-workspace owner and immutable verified snapshots rather than merging trading databases. PostgreSQL logical dumps preserve grants and audit state; SQLite online backup includes committed WAL contents. Startup restores only new/clean local databases. Final stopped-service backup releases ownership. Missing/divergent history, changed layout, corrupt uploads, offline edits and interrupted restores fail closed.
- PostgreSQL restore replaces user schemas in one transaction so deletions also propagate. A real disposable cluster verified non-superuser migrator/owner permissions, application grants, stable fingerprints, obsolete-object removal and rollback on SQL failure. Pre-restore local copies remain available; cross-database partial restoration stays blocked for reviewed recovery.
- Fixed an existing storage import cycle exposed by the standalone sync CLI by making the recovery request import type-checking-only. Approval, broker environment and reconciliation behavior is unchanged.
- Full regression run: **350 passed, 1 skipped in 251.98s**. Final focused sync/storage/launcher tests after additional safeguards: **25 passed, 1 skipped**. Separate real NAS and disposable PostgreSQL smoke run: **12 passed**; tiny synthetic NAS evidence retained at `\\192.168.1.32\Public\systematic-trading-sync-smoke-4120c99563bb47b9b88412265decb7e0`. PowerShell parser, Python compilation and `git diff --check` passed.
- Documented first-time roles/credentials setup, stopped-service switching, conflict recovery, unbounded snapshot retention and excluded ClickHouse/NATS/raw/research data in `docs/database-sync.md`. New-PC infrastructure and ClickHouse migration remain separate setup steps. Use the next clean standard platform restart to activate; no production database replacement, service restart, broker action, commit or push occurred. Existing unrelated backfill and runtime changes were preserved.

## 2026-09-20 - Dashboard performance repair

- Completed reset-aware account history, UTC snapshot capture metadata and reset provenance retained through PnL collapse. Legacy report lookup tolerates malformed evidence; history selection uses capture time without rewriting audit files. Include non-SOTA holdings in their recorded currency and refuse incomplete NAV when a holding cannot be priced.
- Completed the interactive dual-axis performance chart: fixed alignment, Tracking preset, hover/tap and keyboard inspection, drag selection, selected-period statistics, empty/single-series handling, month-end range clamping and responsive geometry. Account changes explicitly include cash flows; missing strategy sessions/marks are disclosed and long chart gaps remain visible.
- Focused verification: **15 passed** for performance, reconciliation and snapshot behavior, including Node.js checks. Synthetic browser preview verified keyboard inspection, drag selection, Escape-to-All, empty/single-series cases and a 390px viewport with no document overflow or console errors. No operational services were restarted and no broker was contacted.
- Exact staged-snapshot full suite: **339 passed in 220.72s**, including real disposable Postgres and Node.js behavior checks. Syntax and staged `git diff --check` passed. The verified dashboard snapshot is ready for the authorized commit/push. Unrelated backfill, WSL/research and runtime changes remain outside this batch.

## 2026-09-20 - Publish completed review repairs

- Prepare a single commit containing the execution-history/recovery, monthly scheduling, recorder calendar and local Docker binding repairs. Preserve unrelated performance-dashboard, account metadata, backfill and research changes in the working tree; exclude runtime reconciliation artifacts.
- Exact staged-snapshot verification: **331 passed in 224.17s**, including real disposable Postgres; syntax parsed for 179 Python files and staged `git diff --check` passed. The verified repair snapshot is ready for the authorized commit/push to `origin/master`.

## 2026-09-20 - Recorder calendar and local Docker bindings

- Recorder capture now uses the same US holiday calendar as proposal scheduling, with recurring 13:00 New York early closes verified against the [NYSE calendar](https://www.nyse.com/trade/hours-calendars). Configured windows can narrow the equity core session, and exchange dates remain New York dates even when another display/window timezone is selected. Exceptional closures and emergency halts remain outside this static calendar.
- Re-evaluate session state after synchronous daily and gap backfills, including jobs crossing the open or close. Limit capture chunks to the remaining session time without extending sub-second windows to one second. Child startup latency still prevents treating this as a hard shutdown deadline; delayed-feed draining after close remains separate work.
- Bind the NATS client/monitor and ClickHouse HTTP/native published ports to `127.0.0.1`. Resolved Docker Compose JSON confirmed all four bindings without printing resolved credentials. Existing containers were not recreated, so runtime bindings have not been changed by this edit.
- Focused recorder/calendar/operator checks: **42 passed**. Full suite with disposable Postgres enabled: **331 passed in 235.31s**. Python syntax parsed successfully for 179 files; `git diff --check` passed.
- Preserve earlier uncommitted execution-recovery and unrelated local work. No service restart, broker access, trading-data migration, commit or push. Next review priorities remain golden-source selection/availability semantics and evidence-backed handling of historical execution corrections.

## 2026-09-20 - Reviewed paper execution recovery

- Added preview-first recovery for active paper execution histories. The review token binds the current order, replacement evidence, operator/reason and PnL baseline; apply validates again inside the same transaction as audit, order and outbox writes. No recovery has been applied to the operator's database in this session.
- Store before/after execution evidence in the order's recovery audit. Preserve it against stale order updates and ignore verified superseded executions on later broker-history replay. Require reconciliation started after the most recent recovery before routing.
- Refuse live orders, account changes, missing or rewritten execution identities, incomplete cumulative evidence, overfills and changes affecting saved PnL baselines. Zero-fill busts and historical baseline rebuilds remain follow-up work.
- Added execution-state and parent-baseline checks to PnL collapse/reset persistence, with a shared Postgres transaction advisory lock for broker-record/baseline mutations. A calculation made stale by recovery fails instead of overwriting the ledger. API collapse conflicts return HTTP 409.
- Added a disposable Postgres test fixture using the locally installed binaries and a separate password-protected loopback cluster. Fixed a Windows subprocess-pipe hang in the test launcher. Focused verification: **31 passed**, exercising SQLite and real Postgres recovery, stale reviews, reservation races, concurrent fill accumulation and atomic outbox rollback. Full suite with disposable Postgres enabled: **302 passed in 228.85s**. Final CLI checks after rejecting an ambiguous SQLite-path/Postgres combination: **2 passed**. Python syntax and `git diff --check` passed; disposable test clusters stopped successfully.
- Existing services, broker accounts, databases and historical artifacts were not changed. No broker submissions, deployment, commit or push occurred in this batch.

## 2026-09-20 - Durable executions and monthly staging

- Committed and pushed the first review repair batch as `8913ff1` on `origin/master`. All 240 tests passed against a separate export of the exact staged snapshot (221.05s). Unrelated dashboard, recorder and backfill edits remain local.
- Added individual execution evidence to the existing broker-order JSON payload. SQLite immediate transactions and Postgres row locks serialize accumulation and commit the order and outbox together. Duplicate/short-window responses retain prior evidence; delayed placement acknowledgments cannot erase synchronized fills. No schema migration is required.
- Capture IB execution IDs, account, individual execution price and cumulative quantity. Match by stable local order reference, reject conflicting identities and overfills, and preserve partial cancellation status. Complete broker cumulative evidence can bootstrap legacy aggregates; incomplete legacy history and corrections require audited recovery. Persistent execution issues block routing and PnL collapse, including after an empty history response or broker reset.
- PnL and reconciliation now apply individual execution timestamps across baseline boundaries. Reconciliation accepts persisted evidence outside the broker query window, still compares broker positions, and detects unsynchronized or conflicting new executions. Execution-sync failure invalidates EOD reconciliation readiness.
- Automatic staging honors the registered static monthly scheduler at the final US session before the new month. Daily EOD reporting continues on other sessions, with data and reconciliation gates intact. Live plans and default API execution dates now share the US session calendar. Manual proposal generation remains available; unsupported automatic schedulers fail closed.
- Added regression tests for restarts, overlapping/duplicate broker responses, concurrent fill writers, atomic outbox rollback, cumulative gaps, legacy bootstrap, corrections, reused numeric order IDs, per-execution pricing, baseline boundaries, month-end/holiday scheduling and off-cycle EOD gating. Full suite: **271 passed in 197.10s**. Final targeted API/operator/history/scheduler checks: **64 passed**; JavaScript reconciliation rendering passed three states (execution issue, position break, matched). Syntax and `git diff --check` passed. New batch remains local and uncommitted.
- No services were restarted, broker orders submitted, migrations applied, or existing historical records rewritten. Isolated Postgres/IB paper integration evidence and an audited execution correction/recovery command remain follow-up work.

## 2026-09-19 - Review-driven execution and accounting repairs

- Preserved the pre-existing working-copy changes and implemented the first repair batch from the codebase review. No services were restarted, broker orders submitted, migrations applied, or historical trading/research data rewritten.
- The submission CLI now uses the configured trading-store factory; unsupported Postgres/SQLite combinations fail before database access. Shared router validation requires recent, successful paper reconciliation, including for CLI calls.
- SQLite uses an immediate transaction and Postgres uses a transaction-scoped advisory lock to reserve each proposal/order intent before placement. Uncertain placement outcomes retain the durable pending claim and block subsequent routing; only confirmed unfilled failures can be retried. Pending claims are not reclassified as missed by deadline expiry.
- Backtest sizing now uses decision-date holding marks and FX. Affordability simulates whole-share purchases with native cash, conversion rounding and fees. Existing backtest artifacts must be regenerated and re-audited before relying on their results.
- PnL collapse advances the existing baseline instead of replaying pre-reset history; broker-reset lots and realized PnL survive subsequent collapses, and backwards cutoffs are rejected.
- Removed synthetic price/FX writes from the refresh path. Legacy carry-forward settings are accepted but cannot make stale observations current. Zero-volume bars are retried and cannot establish current trading prices; EOD readiness requires current FX too. Legacy synthetic FX has no reliable provenance and needs a separate provider-backed historical repair.
- Added isolated test defaults and regression coverage for concurrent routing, lost acknowledgments, invalid reconciliation, partial cancellations, future-price/FX independence, native cash affordability, repeated outages, and broker-reset baseline preservation.
- Validation: final full suite **240 passed in 189.33s** (`.venv/Scripts/python.exe -B -m pytest -o addopts='' -q -p no:cacheprovider --durations=5`), including 23 new regression cases; Python syntax checks and repository-configured `git diff --check` passed. SQLite concurrency is exercised with real transactions. Postgres reservation SQL and IB behavior have not been tested against external services in this session.


## 2026-07-14 - Current Full Report For Monitored Strategies

- Changed Monitored strategy clicks to open the complete backtest report directly instead of the simplified strategy detail page. Archived rows retain the existing detail fallback, including the 67 discovered artifacts without generated HTML reports.
- The report is rendered from an in-memory monitored copy of the artifact. It extends NAV and the risk-parity benchmark through current golden data, reads current market prices/FX for holdings and contribution analysis, and does not overwrite immutable JSON/HTML artifacts.
- Added explicit artifact-end, monitored-through, lifecycle, and monitoring-method provenance. The report retains full period metrics, largest drawdowns, two benchmark choices, holdings contribution, and signal attribution, and now shares the operational navigation header.
- Live browser verification clicked the monitored SOTA directly into the full report: artifact end `2026-04-29`, monitored through `2026-07-14`, 8 summary metrics, 2 benchmark choices, 15 yearly rows, 1,348 monthly contribution rows, signal attribution visible, and no horizontal overflow. An archived strategy still opened its existing detail page.
- Verification: focused reporting/API/UI tests passed (`32 passed`); full suite passed (`217 tests`); compile and `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Broker-Authoritative Portfolio Reconciliation

- Diagnosed the paper-account reset against live TWS: IB reported zero positions and HKD cash while the local fill-derived ledger implied six positions; the pre-change report contained 18 local filled records, 10 IB executions, and six position differences.
- Made IB positions/cash authoritative for active holdings. The Trading page refreshes reconciliation before rendering and the trading-management loop repeats it on the execution-sync cadence with a dedicated client id (`ST_IB_RECONCILIATION_CLIENT_ID`, default 161).
- Persisted timestamped and latest reconciliation reports, emitted a durable `alert.raised` on a new break signature, disabled operator approval/resubmission, blocked EOD PnL/rebalance staging, and server-blocked IB routing when reconciliation is missing, stale, or broken.
- Added `Reset local to IB` with a server-enforced confirmation. It creates an empty or populated broker-derived PnL baseline while preserving all earlier local orders/fills as immutable audit history.
- Fixed IB execution timestamps without an explicit suffix: TWS supplies them in workstation-local time, so they are now localized before UTC conversion instead of being mislabeled as UTC.
- During live verification an operator-confirmed empty baseline `bed6ac19a652` was created. Final state: reconciliation `matched`, IB positions `0`, HKD cash `1,015,927.30`, zero active open lots, total PnL `0.00`, and the unattended management loop reporting zero breaks.
- Verification: focused reconciliation/execution/management/API/UI suite passed (`60 passed`); full suite passed (`216 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Explicit Market Data Symbol Selection

- Diagnosed the apparent SPY-only Market Data page as a UI discovery failure, not missing data: the datalist held all symbols but rendered only the current SPY value until browser-native suggestions were opened.
- Replaced the datalist text input with an explicit symbol dropdown that visibly repopulates for the selected store and intraday session range.
- Live latest-session Intraday Bars exposed the active pilot `GLD/IWM/QQQ/SPY/TLT`; QQQ loaded 223 delayed 5-second bars. The broader raw catalog also contains AAPL from an earlier smoke partition, for six raw symbols overall.
- Daily Bars exposed all 39 converted symbols. AOR was selected and loaded 3,643 rows from `2012-01-03` through `2026-07-13`, proving the non-SPY converted-store path.
- Verification: focused market-data API/UI tests passed (`11 passed`); full suite passed (`212 passed`); browser checks had zero desktop overflow; `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Multi-Session Intraday Market Data

- Extended the raw audit and symbol-discovery APIs with inclusive `recorder_start_date` and `recorder_end_date` filters while retaining the existing exact `recorder_date` contract.
- Added `1D`, `5D`, `10D`, and `All` intraday presets plus explicit start/end session inputs. Presets select the latest available recorder partitions, so weekends and recorder gaps do not create artificial empty sessions.
- Multi-session reads scan newest matching catalog evidence first when a limit applies, then return bars and rows chronologically for the chart and audit table. Exact duplicate event ids remain excluded only from the main series and retained in Raw Evidence.
- Live verification found recorder partitions `2026-06-27`, `2026-07-11`, and `2026-07-13`. `1D` selected the latest partition; `5D` and `10D` selected all three. The final 5D SPY view loaded 198 unique delayed 5-second bars with zero desktop overflow; the active recorder continued increasing the count. Daily Bars remained available with 3,651 SPY rows.
- Verification: focused market-data API/UI tests passed (`11 passed`); full suite passed (`212 passed`); `git diff --check` passed apart from existing line-ending warnings. The in-app viewport override remained at 1280px, so no new 390px runtime claim was made.

## 2026-07-13 - First-Class Intraday Market Data Workspace

- Promoted raw intraday recorder bars from the secondary Raw Evidence form into the primary Market Data store selector; `/platform/market-data-audit` now opens on Intraday Bars.
- Extended raw symbol discovery with available/latest recorder dates. The UI automatically selects the latest date, limits symbols to that partition, defaults to 5-second stream bars, and exposes capture mode, delayed/live provenance, quality flags, and raw references.
- Kept raw audit semantics explicit: the main OHLCV series removes exact duplicate raw event ids, while Raw Evidence retains every immutable record and duplicate/hash diagnostics.
- Live browser verification on `2026-07-13` loaded `GLD/IWM/QQQ/SPY/TLT`, 52 unique SPY bars, 57 raw rows, five duplicate ids, and `IB delayed`. Daily Bars remained selectable and loaded 3,651 ClickHouse rows. Desktop/full-width table and 390px compact layouts had no horizontal overflow.
- Verification: focused market-data API/UI tests passed (`10 passed`); full suite passed (`211 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Five-Symbol IB Intraday Recorder Recovery

- Diagnosed the scheduled recorder as process-live but data-degraded: `reqRealTimeBars` failed for all pilot symbols with IB 10089/420 API entitlement errors, historical gap-fill timed out inside the slow raw-write callback after SPY, and the stop script left the child holding client id 121.
- Added independent historical-request timeouts so one symbol cannot abort later symbols, a buffered `reqHistoricalData(..., keepUpToDate=True)` recovery channel, and a timestamped delayed trade stream using TWS delayed last/size/timestamp plus delayed RTVolume callbacks.
- The active testing feed aggregates delayed trades into raw 5-second bars and always records `ib_market_data_mode_delayed` plus `ib_delayed_trade_aggregate`. It is explicitly barred from signals and execution. Paid `reqRealTimeBars` remains selectable after API subscriptions are enabled.
- Kept the initial runtime universe at `SPY/QQQ/TLT/GLD/IWM`; it is a recorder pilot, not the investible universe. Prospective capture now starts before synchronous recovery, and historical gap-fill runs only after a failed stream chunk.
- Hardened service operations: parent state identifies the actual intraday channel and stores parsed child results; degraded children return nonzero; recorder shutdown stops both supervisor and child; health staleness allows the configured 300-second capture chunk plus startup margin.
- Live evidence: bounded canary wrote 25 valid bars in 40 seconds, five per pilot symbol. The first supervised chunk wrote 32 bars (`SPY 7`, `QQQ 6`, `TLT 7`, `GLD 6`, `IWM 6`) with all five symbols covered, raw/catalog/outbox parity, and zero hash mismatches. Timestamps were about 15 minutes delayed, matching IB mode 3.
- A later normal-service restart completed daily ClickHouse backfill, then IB began returning 10197 `No market data during competing live session` for all five subscriptions. The child now fails fast and the parent immediately reports `service_mode=degraded`, the exact source error, and scheduled historical recovery. Clear the competing IB live/TWS session before expecting prospective capture to resume.
- Verification: focused recorder/service/script tests passed (`18 passed`); full suite passed (`211 passed`); PowerShell parsing, service-manifest JSON validation, and `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Monitored Strategy Workspace

- Renamed global navigation to `Trading / Strategies / System / Market Data` across operational pages.
- Added `config/strategy-monitoring.json` and split the registry into Monitored and Archived views. Current SOTA is always monitored; additional strategy ids can be added to the config.
- Monitored strategies extend their audited artifact NAV through current golden daily bars using final audited holdings. The UI explicitly distinguishes artifact end from data-through date and discloses that this is mark-to-market, not full signal/rebalance replay.
- Added click-through strategy detail pages and APIs with NAV versus benchmark, full/in-sample/OOS comparison metrics, holdings, leverage, country/currency exposures, attribution context, and generated rich-report access.
- Live verification: 1 monitored SOTA, 89 archived; SOTA artifact end `2026-04-29`, monitored through `2026-07-10` with 49 extension points; detail rendered 8 metrics, 6 holdings, 3 comparison windows, 2 chart series, and the full report link.
- Verification: full suite passed (`207 tests`); focused catalog/API/UI tests passed (`36 passed`); platform health remained `ok`.

## 2026-07-13 - Rebalance Execution Window And Missed Attribution

- Added a configurable next-open execution deadline using `ST_EXECUTION_REBALANCE_TIMEOUT_MINUTES` (default 30) after `ST_EXECUTION_TWAP_START_TIME` in `ST_AUTOMATION_TIMEZONE`.
- Added durable `missed` proposal and broker-order states. Pending proposals and approved proposals with failed/missing orders expire; broker-accepted orders remain active.
- Approval, direct submission, resubmission, and lower-level IB routing all reject expired proposals. Missed orders store their remaining quantity, reference notional, deadline, timestamp, and reason without inventing a fill price.
- Operator proposal rows are grey when missed, decisions/resubmission are disabled, and deadline/reason are visible. Execution-quality analysis reports missed count, reference notional, and detailed missed orders.
- Live queue cleanup marked 32 stale proposals and 192 orders missed while preserving 6 approved proposals with routed activity. Browser verification confirmed 32 grey rows with disabled Approve/Reject controls.
- Reduced the operator's legacy PnL-comparison history request from 60 recomputed points to 1 so missed analysis is not held behind a multi-minute historical recalculation.
- Verification: full suite passed (`207 tests`); focused API/domain/router/UI tests passed (`48 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Unified Operational Header

- Standardized Operator, Strategies, Platform Health, and Market Data headers on the same ordered navigation: Operator, Strategies, Health, Market Data.
- Removed page-specific controls from the global header. Health Refresh/status now live in Service Status; market-data refresh/status live in filter toolbars; operator connection state lives in Automation.
- Added a regression test that compares the header link contract across all primary pages and rejects header buttons or status widgets.
- Browser verification confirmed identical Health and Strategies navigation with zero header buttons/status elements; focused UI/script tests passed (`7 passed`).
- Updated dispatcher startup to store the child process id reported by its state file, preventing orphaned dispatcher processes during dashboard restarts.

## 2026-07-13 - Primary Strategy Navigation

- The strategy catalog existed at `/strategies`, but its only Operator entry point was buried inside the Performance panel and was not discoverable from the global page header.
- Added a persistent `Strategies` destination to the Operator, Platform Health, and Market Data headers.
- Browser verification clicked Strategies from Platform Health, opened `/strategies`, loaded 90 strategy runs, and displayed the current SOTA detail.
- Replaced supervisor command-line inspection with privilege-independent identity checks: operator PID must own port 8000, while the dispatcher publishes its process id in the service state file.
- Verification: focused operator UI/script tests passed (`6 passed`); dispatcher script compiled; live `/platform` and `/strategies` browser checks passed.

## 2026-07-13 - Operator Startup Blocked By Recycled PID

- `start_local_platform.ps1` reported completion but `127.0.0.1:8000` had no listener because `var/run/operator_dashboard.pid` contained stale PID `31312`, which Windows had reassigned to Microsoft Edge.
- Hardened `scripts/start_operator_dashboard.ps1` so operator and dispatcher PID files are trusted only when the process command line contains the expected service script; a mismatched live PID is treated as stale.
- Hardened `scripts/stop_operator_dashboard.ps1` with the same identity check so stale PID reuse cannot terminate an unrelated process.
- Live recovery preserved Edge, started Uvicorn as PID `36112`, and restored `/platform` with HTTP 200. Browser verification reported overall `ok`, 7/7 required services healthy, and 0 errors/degraded services.
- Verification: `tests/test_operator_scripts.py` passed; live startup and browser smoke passed; `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-12 - Strategy Catalog And Theoretical Versus Actual Attribution

- Added a read-only strategy artifact catalog over `var/backtests`, exposed through `GET /api/v1/strategies` and `/strategies`.
- The catalog pins the canonical current SOTA, normalizes comparable backtest metrics, exposes artifact provenance and final allocation, and discovers 90 distinct usable strategy runs in current local artifacts.
- Clarified the operator performance contract: indexed SOTA backtest NAV is theoretical strategy performance and account NAV is actual performance; reference-fill PnL remains a separate execution-quality counterfactual.
- Recorded the alpha-factory direction in `docs/research-state.md`: versioned factor identities, theoretical and realized contribution, covariance-aware weighting, capacity/cost controls, and promotion discipline are required before factor risk-parity allocation.
- Verification: focused strategy/operator/API tests passed (`35 passed`); full suite passed (`200 passed`).

This file records durable project decisions, operating status, incidents, and next actions. Keep entries concise, dated, and useful for future agents and human review.

## 2026-07-12

### TWS Health, Docker Preflight, And Paper Reset Reconciliation

- Operator reported three operational gaps: TWS was not monitored as a critical dependency, `start_local_platform.ps1` failed opaquely when Docker Desktop Linux engine was not running, and the IB paper account reset can diverge from local trade records.
- Added Docker daemon preflight: `scripts/assert_docker_ready.ps1` now runs before NATS and ClickHouse Docker Compose startup. It attempts to start Docker Desktop and wait for the daemon when used by the NATS/ClickHouse startup scripts. Local Docker-down smoke returned a concise Docker Desktop/Linux engine remediation message and suggested `-SkipNats -SkipClickHouse` for partial startup.
- Added TWS/API health monitoring: `systematic_trading.execution.ib_health`, `scripts/probe_ib_tws_health.py`, and service manifest entry `ib_tws_api`. Startup and watchdog runs refresh `var/run/ib_tws_api.state.json`; platform health reads the state file.
- Local TWS probe on 2026-07-12 reported `running=false`: TWS/API was not reachable at `127.0.0.1:7497`, and no `nextValidId` arrived for health client id `151`. This is now visible as a platform health error instead of a silent dependency failure.
- Added report-first IB paper reconciliation: `systematic_trading.execution.reconciliation`, API endpoint `POST /api/v1/dashboard/reconciliation/interactive-brokers`, and CLI `scripts/reconcile_ib_paper_account.py`.
- Reconciliation compares local broker order records with IB paper executions and the fetched IB account snapshot. It reports unmatched local orders, unmatched IB fills, and position differences.
- For confirmed IB paper-account resets with zero broker positions, the CLI can explicitly write an empty PnL reset baseline with `--record-pnl-reset-baseline --confirm-paper-reset`. Local broker order records remain audit history and are not deleted or mutated automatically.
- Current remaining gate work: make order routing and live recorder capture require fresh IB health plus no unresolved reconciliation breaks before proceeding; include broker open orders and commissions in reconciliation; persist reconciliation runs in Postgres.
- Verification: focused tests passed (`30 passed`); compile pass passed for `src`, `scripts/probe_ib_tws_health.py`, and `scripts/reconcile_ib_paper_account.py`.

## 2026-07-11

### Postgres Transactional Store Migration

- Completed the first Postgres transactional runtime migration slice after ClickHouse market-data routing was verified.
- Added versioned migration tooling: `deploy/postgres/migrations/001_initial_transactional_store.sql` and `scripts/apply_postgres_migrations.py`.
- Added `PostgresStore` and factory support for `ST_TRANSACTIONAL_STORE_BACKEND=postgres`. The Python settings default remains SQLite for isolated tests/fallback, but local startup scripts now default to Postgres transactional state and ClickHouse market data.
- Added compatibility settings for existing local password names in `.env` (`ST_APP_POSTGRE_DB_PASSWORD`, `ST_MIGRATOR_POSTGRE_DB_PASSWORD`, and related aliases) plus cleaner `ST_POSTGRES_*` settings for future deployments.
- Added one-way migration tooling from SQLite transactional state to Postgres: `scripts/sync_sqlite_transactional_to_postgres.py`. The script intentionally does not copy SQLite price bars or FX rates because daily bars and FX belong in ClickHouse.
- Applied migration `001_initial_transactional_store` to local Postgres.
- Postgres adapter smoke passed: wrote/read a synthetic instrument, thesis, fundamental snapshot, proposal, approval, filled broker order, PnL baseline/snapshot, and outbox rows through `PostgresStore`, then cleaned up.
- Synced current SQLite transactional state into Postgres: 39 instruments, 38 proposals, 7 approval decisions, 16 broker order records, 37 PnL snapshots, and 955 copied outbox events.
- Fixed a migration-safety issue: copying through store methods briefly recreated 44 deterministic proposal/order/fill events that were not in the original SQLite outbox. Updated the sync script to treat SQLite outbox ids as authoritative during migration and delete migration-generated synthetic events. Final Postgres outbox count is 955 with 0 pending copied events.
- Runtime smoke with `ST_TRANSACTIONAL_STORE_BACKEND=postgres` and `ST_MARKET_DATA_STORE_BACKEND=clickhouse` passed. `/health`, `/api/v1/proposals`, and `/api/v1/market-data/bars/SPY?start_date=2026-06-01&end_date=2026-06-01` returned HTTP 200; the SPY bar came from ClickHouse with close `756.5908203125` and volume `43634900`.
- Verification: focused storage/script tests passed (`19 passed`), full suite passed (`194 passed`), and final affected script/manifest/storage tests passed (`14 passed`).
- Current posture: Postgres is the recommended local transactional runtime; ClickHouse is the market-data runtime; SQLite remains a legacy fallback/migration source until a short operational soak and legacy research-script cleanup are complete.

### Live Market-Data Subscription Shakedown

- Operator reported IB market-data subscription is now active.
- Started a P3.4a foundation shakedown: bring up NATS, Postgres, ClickHouse, operator dashboard, dispatcher, and then run a bounded IB paper market-data recorder canary in live mode.
- Guardrail: keep recorder opt-in and canary-sized until raw writes, catalog coverage, health state, and disk impact are verified.
- First startup attempt failed because Docker Desktop's Linux engine was not running. Launched Docker Desktop, then `scripts/start_local_platform.ps1` completed.
- Core services verified: watchdog reported required NATS JetStream, Postgres, ClickHouse, and operator dashboard `ok`; service graph endpoint returned 7 nodes; ClickHouse smoke returned `smoke_rows=2`; Docker showed NATS and ClickHouse containers running.
- Initial `/health` degraded because TWS was not logged in, causing IB automation `nextValidId` timeouts and opening the IB automation circuit until `2026-07-11T03:45:31Z`. After TWS login, standalone IB paper API smoke passed with `next_valid_order_id=20`.
- Recorder proof is still blocked by IB market-data entitlements/session state. Historical SPY live-mode smoke wrote 0 bars and returned IB 162: `Trading TWS session is connected from a different IP address`. Follow-up tests with explicit `20260710 16:00:00 US/Eastern` end time failed the same way for 5-second live, 5-second delayed, and 1-day live historical bars. Realtime live canaries wrote 0 bars: AAPL/MSFT/QQQ/TLT returned IB 420 for `ISLAND STK`; SPY/IWM/GLD returned IB 420 for `AMEX STK`. Delayed AAPL realtime canary returned IB 10089 requiring an additional API market-data subscription.
- Raw-data audit after the blocked canaries: recorder state shows 0 records written, 0 catalog entries appended, and the E hot spool remains about 0.006 MB with only the previous 3 SPY historical-smoke records from 2026-06-27.
- Next action: verify IB Account Management/TWS Market Data Connections for API-enabled US equity/ETF streaming on the paper session, eliminate the different-IP session conflict, then rerun a 1-symbol live ETF canary during market hours before scaling.
- Started follow-up debug specifically for the IB historical-data failure path to separate local request-construction issues from IB entitlement, paper/live sharing, and session-IP causes.
- Historical-data debug result: IB contract-detail probes resolved SPY to conId `756733` primary `ARCA`, AAPL to `265598` primary `NASDAQ`, and QQQ to `320227571` primary `NASDAQ`; contract resolution is not the historical blocker.
- Direct IB API historical probes succeeded for SPY daily bars across SMART/no-primary, SMART+ARCA, conId, ARCA direct, AMEX direct, MIDPOINT, and AAPL daily variants.
- Recorder historical path then succeeded: 3 SPY daily bars, 5 SPY 5-second bars, and 6 multi-symbol 5-second bars for SPY/QQQ/AAPL were written under the E hot spool for recorder date 2026-07-11 and appended to the raw catalog/outbox.
- Catalog/replay audit: `scripts/catalog_market_data_raw.py --date 2026-07-11` reported 14 entries, 0 invalid records, and 0 duplicate raw refs. `scripts/replay_market_data_raw.py --symbol SPY --date 2026-07-11` read 10 valid records with 0 payload-hash mismatches and 2 duplicate deterministic raw event ids caused by repeated smoke pulls of the same bars.
- Updated diagnosis: the earlier historical IB 162 looks like transient TWS market-data session readiness or stale different-IP ownership immediately after login, not a local recorder request-construction bug. Live realtime streaming remains separately blocked: a SPY/AAPL realtime canary wrote 0 bars and returned IB 10089 requiring additional API market-data subscription.
- Started first-party market-data audit portal implementation. Decision: use the existing operator/platform portal for raw/historical audit drilldown, with Grafana/Superset reserved for broader monitoring and ad-hoc BI later.
- Completed first market-data audit portal slice. Added `/api/v1/market-data/audit` for raw catalog queries with raw JSONL dereference, payload-hash verification, duplicate raw-event-id counting, and chart/table-ready rows. Added `/platform/market-data-audit` with filters, summary metrics, OHLC SVG chart, raw-record table, and audit details.
- Fixed the IB historical recorder to persist the requested historical bar size because IB historical `BarData` did not provide a `barSize` attribute; the audit UI leaves bar-size blank by default so older records with null bar size remain visible.
- Clarified market-data environment semantics: raw records keep capture environment as provenance, but canonical historical market data should not be keyed as paper versus live. Updated the audit API/UI so capture environment is optional/default-all and labelled as `Capture Env`.
- Added a raw-catalog symbol discovery endpoint and wired the audit page symbol input to a searchable dropdown. Live `/api/v1/market-data/audit/symbols?recorder_date=2026-07-11` returned `AAPL`, `QQQ`, and `SPY`.
- Unified the top navigation across `/operator`, `/platform`, and `/platform/market-data-audit` with quick links to Operator, Health, and Market Data so the major platform functions are reachable from each page.
- Added safe restart controls to the health page. `/api/v1/platform/service-actions` marks NATS JetStream and ClickHouse restartable through fixed local script mappings, while Postgres, the operator API itself, dispatcher, and embedded trading loop show disabled reasons. The health page renders restart buttons only for supported services.
- Live verification after dashboard restart: `/platform/market-data-audit` returned HTTP 200 and `/api/v1/market-data/audit?symbol=SPY&recorder_date=2026-07-11&limit=20` returned 10 rows/bars, 0 hash mismatches, 0 invalid records, and 2 duplicate deterministic raw event ids from repeated smoke pulls.
- Verification passed: focused audit/UI/recorder tests `11 passed`; full suite `175 passed`.
- Changed the recorder operating model from opt-in one-shot pilot to always-on scheduled service. Added `scripts/run_market_data_recorder_service.py` and `scripts/start_market_data_recorder_service.ps1`; `scripts/start_local_platform.ps1` now starts the recorder service by default unless `-SkipMarketDataRecorder` is used.
- Recorder service behavior: stays running and writes health state while idle outside regular US equity hours/weekends, runs a historical lookback gap-fill before live capture after startup/restart during the session, then records in bounded realtime chunks. Current v0 uses weekday/time windows and does not yet include exchange holiday calendar logic.
- Health smoke after starting the service on Saturday 2026-07-11: recorder process PID existed, state showed `service_mode=idle` and `session_reason=weekend`, `/health` reported overall `ok`, and `market_data_recorder` reported `ok` with message `Market data recorder service idle: weekend.`
- Health restart controls updated: `market_data_recorder` is now restartable through fixed stop/start scripts.
- Verification passed after scheduled-recorder changes: focused service/script/manifest/action tests `10 passed`; full suite `181 passed`.
- Corrected market-data architecture direction after operator review: the raw audit page is not enough and should not be the main market-data workstation. Added `docs/market-data-golden-source.md` defining raw evidence, future source observations, and ClickHouse golden daily/intraday tables.
- Added `systematic_trading.market_data.golden` and `scripts/sync_sqlite_daily_bars_to_clickhouse.py` as the first bridge from existing SQLite `price_bars` into ClickHouse golden daily bars.
- Ran the initial ClickHouse sync from SQLite: `market_data.daily_bars` now has 140,686 golden daily rows after `OPTIMIZE FINAL`, covering 39 symbols from 2012-01-03 through 2026-07-10.
- ClickHouse golden client query smoke returned 7 SPY rows for 2026-07-01 through 2026-07-10 from `market_data.daily_bars`.
- Verification passed after golden-source changes: focused tests `5 passed`; full suite `182 passed`.
- Next correction for the market-data page: switch the main view from raw recorder audit to ClickHouse golden historical bars with symbol search, date range, zoomable OHLC/volume chart, table, and optional drilldown from golden bar to source observations/raw refs.
- Completed the golden-market-data workstation slice. Added `/api/v1/market-data/golden/daily-symbols` and `/api/v1/market-data/golden/daily-bars` around the ClickHouse golden daily table, with uppercased symbol normalization and chart/table-ready response summaries.
- Replaced the primary `/platform/market-data-audit` workflow with golden daily history: searchable golden symbol dropdown, full-history default range, date range filters, 1M/3M/YTD/1Y/5Y/All buttons, pan/zoom controls, OHLCV chart with volume pane, and golden-bar table. Raw recorder audit remains available as secondary raw evidence on the same page.
- Live platform smoke after operator dashboard restart: `/health` returned overall `ok`; golden symbol endpoint returned 39 symbols; `/api/v1/market-data/golden/daily-bars?symbol=SPY&start_date=2026-07-01&end_date=2026-07-10&limit=100` returned 7 bars from `sqlite_price_bars`; page HTML returned 200 and included the golden endpoints.
- Browser verification: desktop loaded SPY full history with 3,652 bars, one chart SVG, 3,652 table rows, no console warnings/errors; the 1Y range control narrowed to 254 bars; compact 390px viewport rendered without horizontal overflow.
- Verification passed: focused market-data/API/UI tests `9 passed`; full suite `184 passed`.
- Next action for P3.4: add ClickHouse source-observation tables and explicit source precedence/disagreement checks, then add intraday golden bars and gap/staleness panels.
- Operator challenged the implementation on three points: visible SPY gaps, overuse of `Golden` in the interface, and whether the database is truly unified or still glued together.
- Correction: the platform is not fully unified yet. Daily historical bars are in ClickHouse `market_data.daily_bars` and are now the preferred serving source, but SQLite `price_bars` remains for legacy research/backtest/automation paths, raw recorder JSONL remains the immutable evidence archive, and intraday bars are not yet normalized into ClickHouse.
- Added direct ClickHouse daily backfill: `systematic_trading.market_data.backfill` plus `scripts/backfill_clickhouse_daily_bars.py`. The job compares provider-returned dates with ClickHouse dates and inserts only missing rows by default, with `--refresh-existing` available for deliberate source refresh. Providers supported: Yahoo adjusted daily, IB historical daily fallback, and explicit Tushare.
- Wired the always-on market-data recorder service to run the ClickHouse daily backfill child job on startup and on interval, including after-hours/weekends. Recorder health state now records daily-backfill status and degrades via `last_error` if the child fails. `/health` now preserves state-file detail payloads.
- Removed visible `Golden` wording from the market-data UI. The page now calls plain aliases `/api/v1/market-data/daily-symbols` and `/api/v1/market-data/daily-bars`; existing `/golden/...` aliases remain for compatibility.
- SPY backfill smoke: 2026-07-01 through 2026-07-10 returned Yahoo provider bars=7, existing ClickHouse dates=7, inserted=0. Full SPY 2012-01-01 through 2026-07-10 returned existing dates=3,652, Yahoo provider bars=3,650, inserted=0. Conclusion: the visible issue is not a simple Yahoo-visible missing-date gap; next UI/data-quality slice needs explicit trading-calendar/source-disagreement panels.
- Restarted the market-data recorder service to load the new daily-backfill behavior. Startup backfill completed with returncode 0, returned the service to weekend idle, and increased ClickHouse daily rows from 140,686 to 140,920 by filling recent stale symbols. SPY/TLT/VGK already had the recent 9 provider dates and inserted 0. HYXU remains stale at 2026-05-22 because Yahoo returned no recent bars and the IB adjusted-last fallback rejected the end-date request; track this as a source-specific quality issue.
- Live verification after dashboard restart: `/health` overall `ok`, `/api/v1/market-data/daily-symbols` returned 39 symbols, SPY July slice returned 7 rows, page HTML returned 200, visible `Golden Daily` text was absent, browser reload rendered SPY with 3,652 rows and no console warnings/errors.
- Verification passed: focused backfill/API/UI/script/health tests `20 passed`; full suite `186 passed`.
- Operator reported SPY still had no usable bars in May/June 2026. Debug showed the API did return rows, but many were stale SQLite carry-forward artifacts: flat OHLC, volume 0, source `sqlite_price_bars`. Example: 2026-06-01 stored as flat 745.70/0 volume while Yahoo adjusted data returned close 756.5908203125 with volume 43,634,900.
- Root cause: the new backfill inserted only absent dates, so stale existing rows blocked provider replacement. Fixed `backfill_clickhouse_daily_bars` to repair flat zero-volume carry-forward rows when provider bars exist and to delete flat zero-volume rows absent from provider calendars.
- SPY May/June repair result: first pass inserted/repaired 23 Yahoo adjusted rows from 2026-05-26 through 2026-06-26. Second pass deleted two stale holiday artifacts: 2026-05-25 and 2026-06-19. Final API check for 2026-05-01 through 2026-06-30 returned 41 rows, 0 flat zero-volume rows, and valid Yahoo bars for 2026-05-29, 2026-06-01, and 2026-06-15.
- Ran the same 60-day repair over all 39 symbols. It inserted/repaired 884 rows, then deleted stale holiday artifacts across affected symbols. Final ClickHouse daily total is 141,512 rows.
- Verification passed after stale-row repair: focused tests `9 passed`; full suite `188 passed`.
- Audited whether signal, portfolio rebalance, trade generation, dashboard valuation, and backtests have moved to ClickHouse. Result: not yet. The market-data page/API and direct daily backfill use ClickHouse, but active strategy/rebalance/PnL/backtest paths still read `store.list_price_bars`, which is backed by SQLite through the current `storage.factory`.
- Active SQLite-dependent paths include `live/sota.py` SOTA rebalance plan generation, `web/api.py` dashboard mark-to-market/account valuation helpers, `live/pnl.py` unrealized PnL valuation, `backtest/stored.py` and `backtest/stock_replacement.py`, `live/market_data.py` after-close refresh/carry-forward, and multiple research scripts. `scripts/run_sota_live_rebalance.py` explicitly instantiates `SQLiteStore`.
- Verified the risk: SQLite still has bad SPY May/June 2026 data after ClickHouse was repaired. SQLite query returned 43 SPY rows from 2026-05-01 through 2026-06-30, with 25 flat zero-volume rows including 2026-05-29, 2026-06-01, 2026-06-15, and the holiday artifacts 2026-05-25/2026-06-19. Therefore current rebalance/signal output would still see stale prices unless migrated or explicitly repaired.
- Added P3.4c to the Kanban as the next safety-critical work item: migrate strategy, rebalance, dashboard valuation/PnL, and stored backtest daily-bar reads from SQLite to ClickHouse before trusting new rebalance output.
- Started P3.4c migration. Added `ClickHouseMarketDataStore`, `MarketDataRoutedTradingStore`, and `create_trading_store` so active runtime code can use ClickHouse for daily bars and FX while delegating transactional state to SQLite.
- Added `ST_MARKET_DATA_STORE_BACKEND`; the operator startup script defaults to `clickhouse`, so dashboard, SOTA rebalance, PnL, and legacy market-data API calls route `list_price_bars`/`list_fx_rates` to ClickHouse in the local platform runtime.
- Added `market_data.fx_rates` ClickHouse table support and synced 3,790 SQLite FX rows into ClickHouse with `scripts/sync_sqlite_fx_rates_to_clickhouse.py`.
- Live routed-store smoke: `store.list_price_bars("SPY", 2026-06-01)` returned ClickHouse close 756.5908203125 and volume 43,634,900; `store.list_fx_rates(USD, end_date=2026-06-01)` returned latest USD/CNH 6.794000148773193.
- Restarted dashboard with ClickHouse market-data backend. Legacy `/api/v1/market-data/bars/SPY?start_date=2026-06-01&end_date=2026-06-01` returned the repaired ClickHouse bar, matching `/api/v1/market-data/daily-bars`.
- SOTA rebalance CLI smoke succeeded for decision date 2026-07-10 and intended trade date 2026-07-13 without queuing orders, producing artifacts in `var/tmp/sota_clickhouse_smoke/`.
- Remaining SQLite scope: transactional state still uses SQLite until the Postgres adapter is implemented, and older research scripts that instantiate `SQLiteStore` directly are not fully migrated.
- Verification passed after routed-store migration: focused tests `40 passed`; full suite `190 passed`.

## 2026-06-29

### Recorder/VPN/TWS Incident And Hardening

- Operator reported a one-day recorder run with multiple failures: external VPN was switched off or idled, NATS/ClickHouse became unavailable, and IB TWS later logged out and produced repeated API failures that required manual relogin.
- Local evidence showed a repeated automation alert storm from IB execution/account snapshot tasks. Messages progressed from IB farm disconnects to repeated `Timed out waiting for IB nextValidId callback for client_id 131/141`.
- The 2026-06-29 delayed 5-symbol recorder pilot for `SPY`, `QQQ`, `TLT`, `GLD`, and `IWM` wrote 0 records and received IB 420 market-data-permission errors for AMEX/ISLAND ETF contracts. Delayed mode remains useful for tiny experiments, but it is not sufficient proof that the 5-second streaming recorder can run before live subscriptions are enabled.
- Decision: do not rely on an external idle-sensitive VPN as part of the critical local trading platform network path. For 24x7 operation, move required infrastructure and IB Gateway toward a supervised server/native-service path.
- Decision: keep IB live-data subscriptions planned for July 2026 as the gating event for real intraday streaming. After subscriptions are enabled, run live-mode entitlement smoke tests before scaling from 1 symbol to 5 symbols and then to 30-40 ETFs.
- Added an IB automation circuit breaker to the trading management loop. After repeated IB failures, automation backs off execution/account-snapshot retries, records circuit state in `var/live/trading_management_service_state.json`, and exposes it through platform health details.
- Added automation alert deduplication so repeated identical warning/error events do not flood `var/log/automation_alerts.jsonl` or the platform outbox.
- Added `scripts/watch_local_platform.ps1` for local health checks and optional repair. It checks NATS, Postgres, ClickHouse, the operator API, and recorder state; `-Repair` recreates NATS/ClickHouse through Docker Compose and restarts the operator dashboard if needed. It does not auto-start the recorder.
- Hardened SOTA automation against account snapshots that include holdings outside the current SOTA universe. Non-SOTA positions such as `DBB` and `USO` are filtered with warnings for SOTA proposal staging instead of failing the trading management loop.
- Updated platform health semantics so an optional service with `running=false`, such as the intentionally stopped recorder, reports `disabled` rather than stale/degraded.
- Ran the watchdog after repair: required services were `ok` for NATS JetStream, Postgres, ClickHouse, and operator dashboard. The recorder was explicitly stopped and reported as optional/disabled.
- Verification passed: full suite `173 passed`; focused watchdog smoke returned required-service status `ok`; final `GET /health` returned overall `ok` with NATS, Postgres, ClickHouse, operator dashboard, event dispatcher, and trading management loop all `ok`, and the optional recorder `disabled`.

## 2026-06-27

### Foundation Proving Session

- Started P6.0 after the operator chose to prove the current foundation before expanding market-data recording or normalization.
- Scope: add a recommended local startup path, monitor NATS/Postgres/ClickHouse/operator/dispatcher/recorder health, expose a web portal with a service connection chart, and keep market-data recording opt-in to protect disk space.
- P3.4a was added as the next market-data step: a small ETF raw-data recording and audit loop before broad normalized-bar ingestion.
- Completed P6.0 foundation proving.
- Added `scripts/start_local_platform.ps1` as the recommended local startup path. It starts NATS JetStream, configures the `ST_EVENTS` stream, verifies Postgres, starts ClickHouse, starts the operator dashboard and event dispatcher, and leaves market-data recording opt-in behind `-StartMarketDataRecorder`.
- Added `scripts/stop_local_platform.ps1` and `scripts/stop_market_data_recorder.ps1`; the stop path does not stop external Postgres.
- Promoted NATS, Postgres, and ClickHouse into active health-monitored services in `config/service-manifest.json`.
- Added TCP health checks for Postgres and a service graph contract at `/api/v1/platform/service-graph`.
- Added the platform health portal at `/platform`; it shows summary health, per-service cards, detail rows, and a manifest-derived service connection chart.
- Local smoke after startup reported required services `ok`: NATS JetStream, Postgres, ClickHouse, operator dashboard, event outbox dispatcher, and embedded trading management loop. Optional market-data recorder was degraded because it was intentionally not started.
- Browser check of `/platform` showed 7 service cards, 7 detail rows, an in-bounds SVG graph, overall `ok`, and no console errors.
- Verification passed: full test suite `166 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.
- Next action remains P3.4a: run a small ETF raw-data pilot and data audit before broad normalization.
- Started P3.4a pilot operation. First live-mode IB recorder attempt reached TWS but failed with IB error 420: no live market-data permissions for AMEX STK.
- Decision: default local recorder pilots to IB delayed market data until live exchange subscriptions are explicitly enabled. Added `-RecorderMarketDataMode` to `scripts/start_local_platform.ps1`; default is `delayed`, with `live`, `frozen`, and `delayed_frozen` available.

### Observability Logs

- Completed P6.0a structured operational logs v0.
- Added `systematic_trading.services.operational_log` with `OperationalLogger`, JSONL append helpers, UTC timestamps, level/event/message/details fields, and redaction for obvious secret keys such as passwords, tokens, credentials, secrets, and API keys.
- Standard operational log path is `var/log/platform_operations.jsonl`.
- `scripts/start_local_platform.ps1` now logs local supervisor startup requests, NATS/ClickHouse/Postgres readiness steps, operator startup, recorder opt-in decisions, recorder pilot process start, completion, and startup failures.
- `scripts/start_operator_dashboard.ps1` passes the shared operational log path to `scripts/dispatch_event_outbox.py`.
- `scripts/dispatch_event_outbox.py` now logs dispatcher start, dispatch batches with activity or periodic heartbeat, publish failures, max-iteration stops, one-shot completion, and operator interruption.
- Operator API lifespan logs are emitted by `systematic_trading.app`: API startup/shutdown plus embedded automation loop start/stop.
- Market-data recorder logs now include run start/completion/failure/interruption, PID removal, initialization, subscriptions/request starts, IB market-data mode callbacks, pacing sleeps, first/periodic bar writes, source errors, and disconnects.
- `scripts/stop_market_data_recorder.ps1` now rewrites the recorder state file as stopped and appends operational log events for normal stops, stale PID cleanup, empty PID cleanup, and no-PID cases.
- Smoke check wrote `dispatcher_started`, `dispatch_batch`, and `dispatcher_completed` rows to `var/log/dispatch_smoke_operations.jsonl`.
- Verification passed: focused observability suite `31 passed`; full suite `169 passed`; final focused script/log/recorder suite `9 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.

### Execution Process

- Added `docs/execution-kanban.md` as the durable Kanban-style execution tracker.
- Future sessions must update the Kanban before starting and after completing implementation work.
- Status values are `Done`, `In Progress`, `Pending`, `Blocked`, and `Review`.
- `AGENTS.md`, `README.md`, and `docs/industrial-platform-plan.md` now point future agents to the tracker.

### Direction

- Reframed the project target from a local Python research toolkit into a 24x7 industrial systematic trading platform.
- Target architecture now requires micro-services, message queue, columnar analytics storage, transactional order state, live market-data recording, LEAN-compatible backtesting, Interactive Brokers execution, Grafana-class monitoring, strong rebalance blotter, and explicit research-to-paper-to-live promotion controls.
- Python remains the default for research, APIs, reports, and orchestration. Go, Rust, or C++ should be introduced only at measured bottlenecks or reliability-critical service boundaries.

### Decisions

- Keep the existing FastAPI, SQLite, dashboard, and paper-routing implementation as the v0 control plane.
- Treat `docs/industrial-platform-plan.md` as the target-state architecture and execution schedule.
- Treat `docs/research-state.md` as the current strategy research memory and SOTA promotion reference.
- Treat `docs/live-rollout.md` as the current paper-to-live operating path.
- Live trading remains blocked until paper execution, reconciliation, alerts, monitoring, market-data recording, and rollback procedures are proven.

### Next Actions

1. Select the initial local queue and storage stack: NATS JetStream or Redpanda for events, Postgres for transactional state, ClickHouse or Parquet-first warehouse for columnar analytics.
2. Define event schemas for market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
3. Add a market-data recorder service that writes immutable raw data before publishing normalized events.
4. Add a strategy promotion registry with artifact hashes and explicit state transitions.
5. Build the strong rebalance blotter model and dashboard workflow.
6. Add Grafana-class metrics and dashboards for data, services, portfolio, and execution.
7. Add daily post-trade, continuous research, and robustness review reports.

### Open Risks

- SQLite is not a sufficient target-state system of record for 24x7 trading operations.
- Current backtesting is useful but must be supplemented with LEAN or a proven equivalent before production promotion.
- Current alerting is not broad enough for live trading because urgent SMS, push, desktop popup, dashboard, and incident workflows are not complete.
- Live market-data recording is not yet a first-class always-on service.

### Implementation Progress

- Added initial versioned platform event contracts in `systematic_trading.domain.events`.
- Covered market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
- Added tests for event subjects, JSON round trips, typed decoding, timezone-aware timestamps, positive trading quantities, and strict payload fields.
- Full test suite passed: 123 tests.
- Added durable SQLite platform event outbox with append, pending-list, publish-success, and publish-failure recording.
- Added queue-agnostic event outbox dispatcher and in-memory publisher in `systematic_trading.messaging.outbox`.
- Added tests for idempotent event append, pending order, publish marking, failure retention, retry, and successful dispatch.
- Wired transactional event producers into SQLite storage for proposal creation, approval decisions, broker order status changes, and aggregate fill records.
- Added tests proving real storage mutations append the expected outbox events without duplicate proposal or fill events on repeated saves.
- Added local JSONL platform event publisher and `scripts/dispatch_event_outbox.py`.
- The dispatch script can run once or poll continuously with `--loop`; default output is `var/events/platform_events.jsonl`.
- Integrated the event outbox dispatcher into `scripts/start_operator_dashboard.ps1` and `scripts/stop_operator_dashboard.ps1`.
- Start script now launches `dispatch_event_outbox.py --loop` unless `-DisableEventDispatcher` is passed.
- Stop script now stops both the event outbox dispatcher and the dashboard.
- Smoke tested the operator stack on port 8765: dashboard health returned `{"status":"ok"}`, dispatcher PID existed, and stop removed both processes.
- Added `docs/service-supervisor.md` and `config/service-manifest.json`.
- Added `systematic_trading.services.manifest` loader and validation models.
- Service manifest currently covers the operator dashboard, event outbox dispatcher, embedded trading management loop, and planned market data recorder.
- Corrected execution ordering after review: P1.6 event replay and P1.7 queue selection should come before P2.3 health-check work.
- Marked P1.8 real queue publisher adapter as blocked until P1.7 selects a queue and a local/server runtime is available.
- Added platform event replay support for JSONL and SQLite outbox records in `systematic_trading.messaging.replay`.
- Added `scripts/replay_platform_events.py` for event replay summaries and detailed event inspection.
- Selected NATS JetStream as the initial real queue adapter target; rationale and adapter contract are documented in `docs/queue-adapter-selection.md`.
- P1.8 remains blocked until a local/server NATS JetStream runtime path and Python client dependency are available.
- Added the P2.3 service health contract in `systematic_trading.services.health`.
- `GET /health` now returns normalized platform health with per-service status, heartbeat, running state, and last error while preserving HTTP 200 for API liveness.
- The event outbox dispatcher now writes `var/run/event_outbox_dispatcher.state.json` heartbeats via `--state-path`.
- Updated `config/service-manifest.json`, `docs/service-supervisor.md`, and `docs/data-contracts.md` for the health contract.
- Full test suite passed: 144 tests.
- Added the P6.4 alert event producer.
- `AutomationAlertNotifier` now accepts an optional event store and appends typed `alert.raised` platform events for automation warnings and errors.
- `TradingManagementService` passes its SQLite store to the default alert notifier, so automation alerts enter the durable outbox without changing existing JSONL/email behavior.
- Alert outbox append failures are logged to `automation_alert_event_errors.log` and do not suppress existing alert logging.
- Full test suite passed: 146 tests.
- Added the P3.1 market data recorder contract in `docs/market-data-recorder-contract.md`.
- The contract defines raw-before-publish rules, the raw JSONL envelope, storage layout, normalized `market_data.recorded` mapping, replay behavior, quality flags, and service-health state requirements.
- Linked the contract from `README.md`, `docs/data-contracts.md`, and `docs/service-supervisor.md`.
- `git diff --check` passed after the documentation update.
- Accepted Docker Compose as the recommended NATS JetStream runtime path.
- Added `deploy/nats/docker-compose.yml`, `deploy/nats/nats-server.conf`, `scripts/start_nats_jetstream.ps1`, `scripts/stop_nats_jetstream.ps1`, and `scripts/configure_nats_stream.py`.
- Added optional queue dependency `nats-py` and `systematic_trading.messaging.NatsJetStreamPublisher`.
- `scripts/dispatch_event_outbox.py` now supports `--publisher nats --nats-url nats://127.0.0.1:4222`.
- Added `nats_jetstream` to `config/service-manifest.json` as a planned Docker Compose service.
- Docker CLI is not installed on this machine, so live NATS startup/stream smoke remains blocked under P2.8.
- Full test suite passed: 147 tests.
- Attempted live NATS smoke after operator reported Docker installation.
- `docker --version` and `docker compose version` are still unavailable in this shell; standard Docker Desktop paths were not present.
- `winget list --name Docker` showed `Docker.sbx`, not Docker Desktop or a visible Docker CLI/engine.
- Installed the queue optional dependency into `.venv`; `nats-py` imports successfully.
- Focused queue tests passed after dependency install: `tests/test_nats_publisher.py` and `tests/test_event_outbox.py`.
- Docker became visible in the shell: Docker version 29.5.3 and Docker Compose v5.1.4.
- Started NATS JetStream through `scripts/start_nats_jetstream.ps1`; NATS health returned `{"status":"ok"}` and container `systematic-trading-nats` is running.
- Created JetStream stream `ST_EVENTS` with subject `systematic_trading.events.v1.>`.
- Published smoke event `evt-nats-smoke-20260627-001` through `scripts/dispatch_event_outbox.py --publisher nats`; dispatcher result was `attempted=1`, `published=1`, `failed=0`.
- Verified SQLite outbox marked the event published with no pending records and JetStream stream state shows one message.
- Added the P2.4 Postgres transactional store design in `docs/postgres-transactional-store-design.md`.
- The design covers schema families for core, strategy, portfolio, execution, ops, and events; transaction boundaries; indexes; outbox locking; migration stages; and operational controls.
- Linked the Postgres design from `README.md` and `docs/data-contracts.md`.
- Full test suite passed after NATS smoke and script fix: 147 tests.
- Inspected local storage for market-data recording: D has 600.25 GB free, E has 308.15 GB free, and Z is a network drive at `\\WDMYCLOUDMIRROR\Public` with 1138.21 GB free.
- Added `config/market-data-storage.json` with a tiered policy: E hot spool, D local archive, Z asynchronous backup.
- Updated `docs/market-data-recorder-contract.md` to keep bulk market data outside the git repo and to enforce free-space watermarks before recorder implementation.
- Completed P2.5 SQLite-to-Postgres adapter boundary.
- Added protocol contracts in `systematic_trading.storage.interfaces` for watchlist, proposals, broker orders, market data, PnL, event append, outbox dispatch, and outbox replay.
- Added `systematic_trading.storage.create_transactional_store` and `ST_TRANSACTIONAL_STORE_BACKEND`; SQLite is the only implemented backend today and unsupported backends fail explicitly until the Postgres adapter is built.
- Routed FastAPI app composition and the event dispatch/replay scripts through the transactional store factory.
- Replaced production package type dependencies on `SQLiteStore` with storage protocols; direct SQLite imports remain only in the concrete storage package and local research/CLI scripts.
- Added `tests/test_storage_factory.py`.
- Full test suite passed: 151 tests.
- Validated local Postgres runtime for P2.8 after operator reported it installed and running.
- PostgreSQL service `postgresql-x64-18` is running with automatic startup; installer registry reports PostgreSQL `18.4-2`, base directory `C:\Program Files\PostgreSQL\18`, and data directory `C:\Program Files\PostgreSQL\18\data`.
- Port `5432` is listening on IPv4 and IPv6; `pg_isready -h 127.0.0.1 -p 5432` returned accepting connections.
- `psql` authenticated SQL check was blocked because no project password, `.env` DSN, or `pgpass.conf` is configured; next Postgres implementation work needs a project role/database/DSN before adapter or migration smoke tests.
- P2.8 remains blocked overall because ClickHouse is still pending.
- Ran authenticated Postgres role smoke after operator configured local project roles/database and supplied current-session credentials.
- `st_app`, `st_migrator`, and `st_readonly` all connect to database `systematic_trading`; timezone is UTC.
- Expected schemas exist: `core`, `strategy`, `portfolio`, `execution`, `ops`, and `events`.
- `st_migrator` can `SET ROLE st_owner` and create DDL inside a rolled-back transaction.
- `st_app` is correctly denied schema DDL.
- No project application tables are present yet; table creation should come from versioned migration tooling, not manual setup.
- Passwords were not written into repo files or durable logs.
- Completed P2.6 columnar store target design.
- Selected ClickHouse as the serving analytical store, Parquet as the immutable archive/interchange layer, and DuckDB as the local/offline Parquet research reader.
- Added `docs/columnar-store-target-design.md`, `config/columnar-store.json`, `deploy/clickhouse/docker-compose.yml`, `scripts/start_clickhouse.ps1`, `scripts/stop_clickhouse.ps1`, and `scripts/smoke_clickhouse_columnar_store.ps1`.
- Linked the columnar target from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, `docs/industrial-platform-plan.md`, and `docs/service-supervisor.md`.
- Added ClickHouse to `config/service-manifest.json` as the planned local columnar store service.
- Focused verification passed: JSON validation for `config/service-manifest.json` and `config/columnar-store.json`; `pytest tests/test_service_manifest.py tests/test_operator_scripts.py`; `git diff --check`.
- Attempted ClickHouse data storage on `E:/systematic_trading_runtime/clickhouse/data`; health and table creation worked, but MergeTree inserts failed because the Windows bind mount denied atomic part renames.
- Switched the local Windows ClickHouse runtime to Docker volume `clickhouse_clickhouse_data` for `/var/lib/clickhouse`; ClickHouse logs remain on `D:/systematic_trading_data/clickhouse/logs`.
- Completed P2.8 external service runtime smoke: NATS JetStream container is running and healthy, Postgres `pg_isready` reports `127.0.0.1:5432` accepting connections, and ClickHouse container `systematic-trading-clickhouse` is healthy.
- ClickHouse smoke passed through `scripts/smoke_clickhouse_columnar_store.ps1`: created a MergeTree smoke table, inserted one row, and queried `smoke_rows=1`.
- Keep the durable market-data lake on D with async Z backup; ClickHouse is a rebuildable serving store until server/native-disk deployment is validated.
- Completed P2.7 schema registry convention.
- Added `systematic_trading.schemas` as the code-based schema registry for the current single-repo phase.
- Registered current platform event schemas and core data schemas with stable schema ids, owners, statuses, JSON Schema export, and compatibility modes.
- Event schemas remain strict by default because current event models reject extra fields; core data schemas start with backward compatibility.
- Added compatibility checks for Pydantic models and JSON Schema snapshots; optional additions can be backward-compatible, while required additions, field removals, and type changes are flagged.
- Added `docs/schema-registry-convention.md` and linked it from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, and `docs/industrial-platform-plan.md`.
- Focused verification passed: `pytest tests/test_schema_registry.py tests/test_events.py tests/test_event_replay.py tests/test_nats_publisher.py`; `git diff --check`.
- P2 Service Foundation is now complete on the Kanban; next recommended work starts P3.2 IB paper market-data recorder v0.
- Completed P3.2a recorder source and capacity spec before implementing the IB recorder.
- Added `docs/market-data-recorder-source-plan.md` to define two recorder lanes: a low-frequency daily reference recorder and an intraday IB recorder.
- Documented IBKR capacity assumptions for P3.2: default 100 market-data lines, reserve 20 lines, record 5-second real-time bars for the 40-symbol ETF seed, keep top-of-book optional, keep tick-by-tick to a 3-symbol default canary set with hard cap 5, and keep Level 2 out of scope.
- Added `config/market-data-recorder-sources.json` as the machine-readable lane, pacing, ETF seed, and secondary-source policy.
- Secondary intraday candidates for later validation are IB delayed mode, Alpaca, Alpha Vantage Premium, Massive/Polygon, and Wind intraday if local entitlement/storage rights allow it.
- Verification passed: `python -m json.tool config\market-data-recorder-sources.json`, 40 unique seed symbols, and `git diff --check`.
- Started and completed P3.2 IB paper market-data recorder v0 after the operator logged into IB TWS paper and enabled the API.
- Added `systematic_trading.recorders` with raw JSONL envelope writing, deterministic raw/event ids, source-policy capacity validation, token-bucket pacing, recorder state-file updates, and raw replay dry-run validation.
- Added `scripts/record_ib_market_data.py` for IB realtime recording and bounded `historical-smoke` tests, plus `scripts/replay_market_data_raw.py` for one-symbol/day raw validation.
- Updated the service manifest so `market_data_recorder` is an implemented optional worker with state-file health, PID path, and manual startup command.
- Smoke-tested the running IB TWS paper connection: `scripts/test_ib_paper_connection.py --timeout-seconds 15` connected to `127.0.0.1:7497` and received `nextValidId=1`.
- Ran a bounded SPY historical-smoke request ending at the 2026-06-26 US market close: wrote 3 raw 5-second bar records under `E:/systematic_trading_runtime/market-data/hot/...`, appended 3 `market_data.recorded` events to `var/systematic_trading.db`, and wrote `var/run/market_data_recorder.state.json`.
- Raw replay dry-run for `SPY` on recorder partition date `2026-06-27` read 3 records, validated 3 records, and found 0 payload-hash mismatches.
- Verification passed: focused recorder/service/event tests, full test suite `162 passed in 172.62s`, JSON validation for recorder and service config, and `git diff --check`.
- Started and completed P3.3 raw data catalog.
- Added append-only raw manifest entries under `<root>/raw/_manifest/date=<YYYY-MM-DD>.jsonl` with source, environment, data kind, symbol, recorder date, raw schema version, raw ref, byte offset, byte count, payload hash, timestamps, capture mode, request id, and quality flags.
- Recorder write order is now raw JSONL first, raw catalog entry second, and `market_data.recorded` outbox event third.
- Added query and rebuild helpers in `systematic_trading.recorders.market_data` and `scripts/catalog_market_data_raw.py` for operator-level discovery and manifest recovery from existing raw partitions.
- Rebuilt and queried the existing IB SPY smoke data in the E hot spool: 3 catalog entries, 0 invalid records, 0 duplicate raw refs; query filters covered source `interactive-brokers`, environment `paper`, data kind `bar`, date `2026-06-27`, symbol `SPY`, and raw schema version 1.
- Verification passed: focused recorder/service/event suite `38 passed`, full test suite `163 passed in 173.86s`, JSON validation for service/recorder/storage configs, and `git diff --check`.

### 2026-09-25 IB Gateway cutover and engine assessment

Moved this PC's shared paper broker profile to Gateway 127.0.0.1:4002 (live port configured as 4001 but live remains disabled). Coordinated platform stop/start preserved NAS ownership/backup handling. Order connection, execution sync, account snapshots, health and reconciliation use distinct clients on the same login; paper reconciliation matched, with no order submitted. Local external D: storage policy now feeds recorder/catalog/replay CLIs consistently; explicit CLI overrides still work. Fixed IB warning 2176 prematurely ending capture: retain warning, mark affected bars ib_fractional_volume_rounded, and preserve fatal handling for other request failures and delayed-data labels. Historical canary: 60 bars/five symbols; corrected 45-second delayed stream: 16 new bars/five symbols. SPY replay: 16 valid, zero hash mismatches/duplicates. Dashboard audit exposes the new raw bars. Tests: 365 passed, 1 skipped; existing two deprecation warnings.

Documented operation and official-source engine assessment. Decision: retain control plane/approval/audit/reconciliation and evaluate LEAN first in a frozen-data backtest pilot for monthly ETFs; no engine installed or migrated. Nautilus remains a candidate for future intraday execution requirements. Next: check Gateway Read-Only API before first approved paper order; session/restart soak; official API compatibility upgrade; implement raw NAS backup separately. EOD September 24 remains incomplete because USD/CNH is latest September 23; slow serial EOD work temporarily staled the loop heartbeat, which recovered with fresh matched reconciliation. Do not weaken data freshness checks or claim continuous/order-path validation from connectivity alone.


### 2026-09-25 Gateway trading operations workspace

Deployed a redesigned `/operator` with a broker order blotter, working/attention/history filters, order review dialogs, audit details and IB positions/native cash. Visible pages poll Gateway order snapshots every 15 seconds; portfolio sync still uses persisted account snapshots and reconciliation without resetting the PnL baseline. Added paper-only same-client cancel, plain-limit amendments within approved exposure/price, and zero-fill confirmed-cancellation resubmission. Operator/reason and an exact review token are recorded. Atomic DB claims survive crashes/timeouts; concurrent fills are preserved; both normal routing and reservations block nonzero or unknown broker fill evidence before execution sync. The installed IB API completed-order callback omits API order/client IDs, so completed histories require a previously observed permanent ID. External/unlinked orders remain view-only. Unchanged executions are not republished as new fill events during lifecycle updates. Resubmission retains the same local identity and prior-attempt audit.

Validation: final full suite 406 passed, 1 skipped in 170.91s with disposable PostgreSQL; existing two deprecation warnings. Synthetic browser amendment flow and desktop/mobile layout checks passed with no console errors. Real Gateway snapshot and portfolio sync succeeded: zero current broker orders/positions and matched reconciliation. Kept 238 historical local records, including ten with unconfirmed terminal status; no invented cancellations or historical rewrites. Restarted only dashboard/dispatcher, preserving running recorder and NAS backup ownership. No real broker placement, amendment or cancellation performed. Next: review a fresh small paper proposal and perform supervised submit/amend/cancel/resubmit checks. Amend currently supports plain limits; algorithm changes/new exposure require a new proposal. Restart/reconnect soak and unresolved-action recovery remain follow-ups. Operating guide: docs/trading-operations.md.

### 2026-09-25 initial allocation and portfolio drift maintenance

Implemented the user's empty-portfolio TWAP trigger and subsequent instruction to monitor IB holdings against strategy targets. User explicitly chose 2 percentage points per holding. The management loop now evaluates portfolio alignment independently of the month-end queue. An empty, verified, freshly reconciled single paper account can stage an initial allocation. Existing holdings are valued using completed daily prices and same-date FX; a threshold breach stages a portfolio TWAP rebalance. Target weights come from an approved proposal in the current monthly period or a point-in-time reconstruction of the latest scheduled month-end targets. Proposal metadata preserves trigger, target date and source proposal. Monthly signals remain unchanged, and monthly staging waits for unexpired alignment proposals.

Fresh broker open-order snapshots and local pending/uncertain states block duplicates. Historical records covered by a reconciled baseline are retained without falsely cancelling them. Deterministic account/target/position/execution episodes plus atomic SQLite/Postgres insert-once prevent restarts and competing workers from overwriting approvals or repeatedly creating the same proposal. Rejections pause unchanged attempts; expired windows cannot be reused. TWAP uses the configured duration, regular/early-close calendars and a short intraday review lead, or the next session. No approval, route, environment or reconciliation checks were weakened; the service only stages pending proposals. The operator page displays target/actual weights, drift, valuation dates and readiness blockers. Initial intraday and drift turnover are separately tagged paper execution policies, not validated additions to the existing monthly backtest benchmark.

Validation: 451 passed, 1 skipped in the full suite (disposable PostgreSQL enabled); final affected service/allocation checks 54 passed and the added monthly-conflict/UI checks 2 passed. Two existing dependency deprecation warnings remain. Restarted dashboard (PID 37504) and dispatcher (PID 10036); recorder and NAS ownership retained. Runtime API confirms running, threshold 0.02 and matched IB reconciliation. Observed readiness blocker: September 24 FX required; USD/CNH latest September 23, HKD/CNH latest April 29. The current EOD refresh covers USD only; cash-currency FX needs repair, and its existing CNY proxy semantics warrant correction rather than fabricating CNH rates. No stale-rate carry-forward, broker order placement, amendment or cancellation was performed. Next: restore verified observed FX coverage, then review the generated pending allocation and conduct supervised paper execution/cost checks.
