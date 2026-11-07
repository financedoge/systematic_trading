# System health incident — November 7, 2026

The operator reported several degraded services. These were a mixture of
operational failures, a calculation restart requirement and genuine historical
data/evidence gaps. The native infrastructure was available; this was not a
database or queue outage.

## Findings and repairs

- The running application rejected tracked calculations after calculation source
  files changed. Restarted through the normal guarded operator launcher, with
  dependency pins verified and previous complete publications preserved.
- IB had reported server/farm disconnections and execution-query timeouts. The
  paper API recovered and the application obtained a matched reconciliation.
  Routing still requires fresh reconciliation and matching calculation inputs.
- Listed-history acquisition put temporary TLS/timeouts/rate limits into the
  same six-hour quarantine cooldown as audit failures. It now preserves a typed
  acquisition error and retries wholly transient host failures after 15 minutes.
  Certificate failures, permanent HTTP errors and identity/return-path audit
  rejections retain the conservative path. No partial response is admitted.
- A 64-symbol acquisition pass could delay strategy calculations for many
  minutes. Each pass now stops starting acquisitions after 120 seconds, finishes
  its current read/audit, publishes accepted peers atomically and leaves the
  remaining symbols in the fair application queue. Publication still precedes
  calculation, preserving the common-batch gate.
- With the operator process stopped, requeued 82 pre-existing transient failures
  whose attempts were at least 15 minutes old. Retained every previous receipt in
  `var/maintenance/health-20261107/transport-retry-receipt.json`. This only requests
  new acquisitions; it does not mark histories current or release audit holds.
- Post-trade benchmark health previously displayed a generic description beside
  a degraded badge. The served message now includes coverage counts and reasons,
  and unavailable full-session references also keep it degraded. The collector
  reports unknown until its first coverage check, rather than premature success.

## Outstanding evidence and external configuration

- Ten historical filled paper orders have no recorded explicit TWAP window.
  Another two orders lack execution admission for USO/DBB. Retain these gaps;
  inventing historical windows or widening execution admission is not a repair.
- The serving-history recorder still reports HYXU security-definition failure.
  Its HYXU/EUHY identity/mandate transition remains a separate governed-data
  problem. No ticker substitution or historical splice was made.
- Broad daily coverage includes source outages, historical return revisions,
  identity/listing changes, incomplete histories and insufficient overlap. Audit
  failures remain quarantined. The separate 2,223 histories already held for
  listing/identity review are not silently admitted.
- Email alert delivery is disabled because recipient and SMTP configuration are
  absent. No outbound test message or new alert channel was authorized or sent.
- A previous delayed quote capture recorded IB 10197 (competing live session).
  Historical recovery nevertheless covers all five configured symbols through
  the November 6 close, with no outstanding recovery windows. Weekend idleness
  does not establish that next-session streaming entitlement will succeed.

## Verification

Authenticated PostgreSQL reads, the native watchdog, strategy dependency and
asset pins, NATS, dispatcher heartbeats and publication storage passed. The
dispatcher reports no failed delivery in its current cycle. More than 570 GiB of
disk headroom was available. The last backup completed at 21:24 Shanghai time,
with repository metadata verification and decrypted manifest readback; a new
upload was in progress. The October 18 isolated native restore acceptance was
retained and inspected; no new restore onto production was performed.

Focused tests cover transient/permanent acquisition classification, certificate
failures, cooldowns, unchanged audit rejection after retry, bounded acquisition
and queue continuation, benchmark coverage, existing recorder transport,
governed publication and broker health. Test batches passed (67, then 44 with
overlap after adding the acquisition budget, and 27 broker/benchmark checks).
Ruff and whitespace checks passed. Native Windows PostgreSQL, Parquet and LEAN
remain selected; paper port is 4002 and live routing remains disabled in code.

Runtime receipts are under `var/maintenance/health-20261107/`; they remain local.
No strategy selection, allocation, approval, broker evidence or audit threshold
was changed by the repairs.

At the last recorded runtime check, core infrastructure and the paper API were
healthy, reconciliation was matched, and the calculation-source exception was
absent. The app was still performing its conservative replay; finished
publication and cleared trading readiness were not yet verified. Daily coverage
was 2,728/3,133 (405 stale/pending; 157 acquisition/audit failures), versus
2,644/3,133 at initial inspection. Reclassifying/requeuing a transport failure is
not counted as publishing current data. Overall health therefore remains
degraded. The related [invalidation review](calculation-invalidation-review-2026-11-07.md)
records why unrelated catalog changes can recreate the catch-up state.
