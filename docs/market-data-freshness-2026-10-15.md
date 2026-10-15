# Market-data freshness incident — 2026-10-15

The operator found AAPL daily history ending September 25 and an empty Intraday
Bars selector. Recorder process health did not establish that the expected data
had actually been delivered. This was a monitoring defect as well as a coverage
and page-performance defect.

## Evidence and causes

- The governed catalog contained 5,356 symbols, but recurring daily acquisition
  covered strategy/research ETFs. Republishing that catalog kept inheriting the
  September 25 AAPL history. A new catalog publication timestamp did not mean
  every symbol had new observations.
- The intraday recovery recorder had complete five-second OHLCV windows for
  SPY, QQQ, TLT, GLD and IWM through October 14's close. The selector scanned
  approximately 4.07 GB of manifests twice. One scan took 129.53 seconds and the
  HTTP request exceeded a 45-second timeout. The empty selector did not prove
  those recordings were missing.
- Daily backfill could exit successfully with per-symbol acquisition warnings;
  recorder health discarded those warnings. Process heartbeats did not compare
  persisted daily endpoints or completed intraday windows with the exchange
  calendar. Other analytics problems could independently degrade overall health.

## Repair

The application now owns a resumable daily recorder for all current-listing
candidates with supported identities, as requested by the operator. Admission
requires an existing supported history and listing boundary, no unresolved issuer
identity, and no explicit admission hold. Fresh captures must match the symbol,
USD currency, US exchange timezone, supported equity/ETF type and listing boundary.
The normal historical continuity, price-revision, hash-verification and publication
checks still apply. Acquisition failures and unsupported revisions are quarantined
per symbol with retry receipts; they cannot block successful peers indefinitely.
Batches contain at most 64 symbols and run before native strategy calculations in
the same research worker. The existing common-batch calculation and trading checks
remain enforced while each publication catches up; no stale model is rebound to a
new batch by changing its receipt.

This initial scope contains 3,133 candidates. The other 2,223 catalog rows include
missing, ended and unresolved histories that require identity/listing review.
Candidate classification is not certification that every security remains listed;
each fresh capture still has to pass its identity and coverage checks. No symbol
is added to a strategy or granted execution authority by recorder admission.

Successful observations enter immutable governed publications before research can
consume them. Older conflict evidence remains visible: AAPL's original archive
conflicts are not cleared merely because a new capture passes revision checks.
Inherited immutable artifacts use hard links on a compatible volume, with a copy
fallback, so broad catalog refreshes do not repeatedly duplicate all histories.

Intraday symbol lookup now uses disposable per-manifest summaries and date pruning.
Unchanged manifests reuse a checksummed summary; appended records update its suffix;
rewrites, truncations and damaged summaries rebuild. Raw bar reads still verify
their original envelopes. Delayed quote samples remain separate from complete
historical OHLCV. Empty or failed symbol requests now show an actionable message.

An independent application watchdog checks actual per-symbol daily endpoints and
intraday completed-window receipts every minute, including calendar/grace rules,
worker liveness and unresolved gaps. System includes this as a required health
check; Market Data displays aggregate and selected-symbol freshness warnings.
Unknown and stale monitoring cannot report healthy. Warnings enter the existing
durable alert path without requiring an open browser. SMTP delivery remains
unconfigured; the change does not invent an external notification destination.

## Recovery and remaining work

AAPL has been reacquired, audited and published through **2026-10-14**, the latest
completed US session at repair time, with 11,552 daily rows. The first recovery
wave published 14 symbols; AAMI and AAOI were quarantined after provider SSL
acquisition failures. They remain visible and retryable. The broader backlog is
being processed by the application and must not be represented as fully recovered.
At 14:52 UTC, the application had independently published another 60 symbols:
126/3,133 candidates were current, 3,007 remained pending/stale, and six had explicit
quarantines (including provider acquisition failures, insufficient overlap and
an adjustment/identity audit failure). Today's intraday recovery was also advancing:
four symbols had completed the 14:30 UTC window and one remained in progress.
The final acceptance receipt confirms all five completed that window, with zero
unresolved windows.

The Intraday Bars page was verified with all five ticker choices, loaded OHLCV and
a rendered candlestick chart. Its deployed ticker endpoint returned in 0.11s when
warm and 6.23s during the later append/recalculation verification, both below the
previous timeout.
132 regression tests passed, with no failures or skips; Ruff and whitespace checks
also passed. Coverage health correctly reports the daily backlog.
Existing paper approval was temporarily paused during deployment and restored
after fresh matched reconciliation, with the same CNH 1,000,000 cap (revision 10).
Broker environment, reconciliation and data-to-model publication checks remain enforced.
Live remains disabled. Deployment receipts are stored locally under
`var/reviews/market-data-incident-20261015/`.

Follow-up acceptance is data based: supported daily histories reach the latest
completed session or display an explicit quarantine; intraday windows advance
after the acquisition grace period; freshness warnings clear only when those
conditions are met. Unsupported identities require investigation, not silent
provider substitution. External alert delivery requires a configured channel.
