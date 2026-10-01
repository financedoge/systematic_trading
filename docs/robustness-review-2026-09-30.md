# Platform recovery review — 2026-09-30

The user's requirement is application-owned calculation and recovery after
ordinary process, network and storage interruptions. This review follows
`.agents/skills/system-robustness-review.md`. It covers service lifecycle, audited
data/FX ingestion, calculation evidence, publication, broker reconciliation,
event delivery, recorder recovery, backup state and operator visibility.

## Reproduced gaps and repairs

| Gap | Resulting behavior | Verification |
| --- | --- | --- |
| Unexpected trading-loop exception terminated its thread while API remained alive | Iteration failures remain visible and retry with capped backoff; health reads actual thread liveness. Normal reconciliation, proposal idempotency and approval checks still apply. | Injected both database failure and status-write failure, then verified the next iteration recovered. |
| Broker recovery callback failure could kill health monitoring or consume the recovery edge | Health iterations survive exceptions and retry the pending notification. | Failed first callback, successful second callback. |
| Failed/running native receipt permanently blocked the same input revision | Retry transient failures in separate immutable attempts with persisted backoff and an OS lock. Reuse verified successes. Wait for an existing LEAN container; never kill it or reuse its output. | Interrupted run, timeout/backoff/retry, concurrent lock, active orphan and changed-artifact tests. |
| Interrupted preparation left an incomplete final bundle directory | Build in a unique staging directory, verify it, then atomically rename into place. Interrupted staging evidence remains available. | Partial write followed by successful retry; partial evidence retained. |
| Status and native receipt files could be truncated during a crash or observed mid-write | Write/fsync a unique temporary file and atomically replace the committed document. | Failed replacement retains the previous complete document. |
| Manual watchdog could not recover a dead service | Local recovery worker starts with the platform. It checks desired services every 30 seconds, uses guarded startup, and persists restart backoff capped at 15 minutes. | Isolated process death/recovery; actual dispatcher crash recovered with unchanged API PID. |
| Windows PID existence confused exited processes with active ones | Use correctly sized process handles and check `STILL_ACTIVE`; access denied stays conservative. | Real terminated child with a retained process handle. |
| Backup worker could not restart after a stale PID file | Crash-released worker lock serializes startup; a dead PID can be replaced while a live legacy worker stays protected. | Lock tests and deployed backup-worker restart; offline checkpoint lifecycle passed. |
| Event connection/publish/drain could block too long; lost acknowledgements could duplicate events | Bounded network operations, no internal reconnect loop, bounded dispatch batches and stable `Nats-Msg-Id`. Outbox rows stay pending until acknowledged. | Timeout/close, headers, bounded batch and existing outbox retry tests. Deduplication remains bounded by JetStream's configured window. |
| Recorder acquisition children had no wall-clock deadline; daily acquisition failures waited six hours | Capture deadline is requested duration + 120 seconds; historical/daily jobs have a 900-second deadline. Stop only the owned acquisition process tree on timeout. Failed daily backfill retries within five minutes. | Timeout/process-tree and failed-backfill scheduling tests. |
| FX file acquisition could succeed before a database outage, then never repair the missing normalized rows | Reconcile supported saved observations into the FX store even when source acquisition is already complete. Avoid repeated writes/refetches when values match. | Evidence-present/database-failed recovery and no-refetch/idempotency tests. |
| A living analytical thread could mask stalled progress | Expose job start times and research staleness, with a longer budget for native calculations. | Runtime status plus independent operations/freshness regressions. |
| Historical archive imports delayed native retries and daily freshness | Dedicated archive worker, separate from both strategy and account workers; five-minute archive interval and independent progress/error reporting. | Blocked archive thread while strategy refresh and account publication completed; runtime drill exposed this delay. |
| Manual watchdog treated HTTP 200 as application readiness | Include embedded calculation/trading/recovery status from the health response. | Executed PowerShell pure-function tests for degraded workers and malformed health responses. |

Integrity failures are deliberately different from transient failures. Changed
manifests, changed committed receipts/artifacts and failed native parity retain
the last complete publication and require review. Retrying never promotes partial
results or switches providers/price bases silently.

## Lifecycle contract

`start_local_platform.ps1` saves the requested service profile under
`var/run/local_recovery.profile.json` and starts `scripts/local_recovery.py`.
The profile preserves operator store/publisher settings and recorder settings.
`-SkipRecovery` omits the worker. It is a local application process, not a Codex
automation, and does not perform strategy calculations itself.

Recovery starts missing NATS/ClickHouse through their existing Compose scripts;
operator/dispatcher and recorder through their normal startup checks; and a
missing backup worker through the existing backup command. It does not reset
databases, replace a running database from NAS, change strategy selection,
approve orders or log in to IB. Existing recorder children finish before another
recorder parent is started. Low disk capacity blocks restart attempts visibly.

Explicit stop scripts pause the relevant recovery target before stopping it.
The control lock waits for an in-flight startup before applying a stop, preventing
a stop/restart race. Normal starts resume that target. Full platform shutdown
stops recovery first. Directly killing a process is treated as a crash.

Recovery reports its own heartbeat and per-service outcomes on System health.
A living but unresponsive process is not forcibly killed by this worker: normal
job timeouts and iteration retries cover known bounded work; an unexplained hang
is reported for investigation. The supervisor itself starts with the platform,
not automatically at Windows boot. Laptop sleep/power loss still suspends work.

## Incident trend and remaining risk register

The September 30 incident chain combined unavailable NAS, provider HTTP failures,
Gateway server loss, missing observed FX and misleading stale report/error state.
Logs also contain recorder entitlement/delayed-feed messages; these do not confer
real-time data entitlement. Earlier deployment interruptions left native runs
requiring manual recovery. This change removes those retry traps while retaining
their evidence and quality boundaries.

| Remaining condition | Owner / response |
| --- | --- |
| Gateway login/2FA, external network and missing market-data entitlement | Operator/provider. App retries after recovery; it cannot manufacture connectivity or permission. |
| SMTP host/recipient are unconfigured | Operator. In-app health and durable logs remain available; external alert delivery is explicitly disabled. Unattended/live readiness is not established. No email was configured or sent. |
| NAS is currently unreachable | Optional remote backup remains deferred. Verified local checkpoints continue; monitor local storage and arrange remote copies when connected. |
| Complete second-machine restore of ClickHouse/raw/governed prerequisites is unproven | Operator/platform owner. Perform the documented recovery drill before disaster-recovery or live-readiness claims. Local transactional restore regression evidence is separate. |
| Audited historical price vintages, legacy FX and cash-event residual limitations | Data/accounting owner. Preserve existing disclosures and broker statement evidence; do not substitute or reset balances to hide differences. |
| Hung external Postgres/OS or an unexplained in-process deadlock | Operator/OS supervisor. Health exposes failure; this release does not kill a live process, restart an arbitrary Windows service or change system permissions. |
| Exceptional exchange closure or clock error | Operator/data owner. Existing calendar and timestamp checks remain; no external clock/holiday override is inferred. |

These conditions retain the playbook's stop conditions for live promotion and
claims of fully unattended operation. They do not prevent repair and testing of
the existing paper platform.

## Evidence

- Full suite: 759 passed / 52 optional integration skips, zero failures.
- Subsequent recorder/lifecycle fault checks: 46 passed; final data recovery checks: 40 passed.
- Archive isolation/application regressions: 48 passed / one optional integration skipped; final lifecycle/readiness checks: 15 passed.
- Whole-project Ruff and PowerShell parsing passed.
- Offline shutdown/startup succeeded with local checkpoints and NAS deferred.
- Actual dispatcher crash: recovery replaced its PID while the API PID and in-flight calculations remained intact.
- Actual NATS duplicate-ack drill: two publishes with the same event ID produced one message in a temporary isolated stream; test stream removed.
- A native LEAN container stalled during acceptance. It was deliberately stopped as a failure drill (not described as an automatic timeout). The app retained its failed receipt, selected a separate attempt, reused four completed runs and automatically retried the missing run. Native timeout behavior is covered separately by fault injection. All five completed runs passed parity and match prior economic hashes under revision `db180b3312c8906fae94d0101656cbd7b8190206e05a08085573a9d759056652`. The retry completed in 69.06 seconds of backtest wall time. No failed result was published.
- Final runtime: all required services healthy; three strategy reports and account EOD through September 29; empty EOD backlog; fresh matched broker reconciliation; local checkpoint file hashes verified; paper approval policy byte-identical.
- Receipts: `var/research/self-healing-full-suite.xml`, `self-healing-recovery-tests.xml`, `self-healing-final-extra.xml`, `self-healing-data-recovery.xml`, `self-healing-dispatcher-drill.json` and `self-healing-runtime.json`.
