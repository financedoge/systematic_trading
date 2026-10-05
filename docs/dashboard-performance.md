# Dashboard performance

## Allocation theoretical comparison (2026-10-05)

Recorded trading allocation periods now compare actual account P&L with the
capital-weighted NAVs calculated by the app's strategy service. Each strategy's
switch-close NAV buys a fixed number of virtual units; the outgoing allocation
earns the return through that close and the new allocation earns later returns.
For weights `w`, period growth is `1 - sum(w) + sum(w * NAV(date) / NAV(switch))`.
Capital weights drift until the next allocation switch; residual capital is flat
CNH cash. Strategy NAV already includes its own scheduled rebalances and modeled
costs. This comparison does not add handover costs or model the execution book's
monthly capital resets. It is separate from the holdings/reference-fill ledger.

The **Rebase at allocation switches** selector has two modes:

- **Theoretical value · continuous** carries the previous period's theoretical
  closing value into the next allocation. The first period starts at actual capital.
- **Actual portfolio value · each switch** starts each period at that switch's
  observed account value (or its recorded opening valuation). A line break marks
  the reset. Rescaling is excluded from Strategy Return and return statistics.

Both lines use the same CNH P&L scale and original starting capital, fixed during
zooming. The allocation-period table shows matched-date actual NAV changes,
strategy returns and period P&L. Actual NAV changes still include external flows.
An opening-only period reports 0% with an explicit pending-first-session note;
volatility and risk ratios remain unavailable until sufficient observations exist.

Only app-calculated strategy documents with audited batch/file lineage are used.
The dashboard publication pins the strategy publication version, document hashes
and original input provenance. Missing components or exact switch-close NAVs stay
unavailable; missing sessions stop a period, with no price fallback or interpolation.
Missing handovers stop continuous compounding, while a later fully supported
actual-rebased period can restart independently. Historical FX and publication
availability limitations remain visible. Earlier unverified allocation history
is not reconstructed from today's SOTA.

## Reset history and intraday endpoints (2026-10-05 follow-up)

Cumulative theoretical and account NAVs start at the confirmed P&L reset opening.
An allocation switch never resets the headline cumulative return. The display-only
legacy timeline uses registered strategy identity in retained executed proposals,
with account-scoped fill evidence; pending proposals and today's SOTA cannot assign
past history. Daily comparisons use the close before first execution and disclose
that intraday switch timing and handover costs are approximated. If a reset occurs
after an explicit allocation activation, its opening clips that active period.
Unknown history remains unavailable rather than assigned retrospectively.

The original pre-USD SOTA has a full app-calculated NAV as the exact named parent
benchmark in its monitored USD report. This source is pinned by calculation
publication, report/lineage document hashes, and audited input provenance. It is
not a provider archive or a manually rerun study. The confirmed reset opening is the shared 0% starting point. The recovered pre-switch daily path carries into the later explicit allocation handover.

The two-second broker P&L refresh supplies an optional **provisional** current-day
endpoint. The background analytics worker prepares verified prior-close raw prices,
held strategy weights (not latest signal targets), drifted capital shares, dated FX,
and the latest observed account holdings/cash. The HTTP request only reads caches. Startup warms this cache from a validated publication before the slower capture import, then republishes after that import.
A spot mark is IB position market value / quantity. Holding Daily % is that mark /
previous audited raw close - 1, in contract currency; it is not daily P&L divided
by position value and excludes dividends. Stale callbacks retain their stale label.

Strategy spot growth is the capital-weighted change in its published held assets;
CNH reserve and FX are fixed at the prior close. The account endpoint revalues its
captured cash plus holdings with the same dated FX and current broker marks. A
lightweight application worker checks the latest app-written broker snapshot every
five seconds, retaining its document hash and capture time independently of the
slower historical import. This reads observed holdings/cash only, not price archives. It
requires matching quantities, an identified account, cash captured within ten
minutes, unambiguous USD equity contracts and fresh callbacks. A missing required
mark, mismatched publication/day, overdue scheduled strategy rebalance or stale
connection withholds the affected endpoint. Unsupported currencies remain missing.
New cash flows since capture, dividends, fees, corporate actions and intraday FX
are not modeled by this provisional price preview; completed publications remain
authoritative. Callback freshness is not exchange quote age or data entitlement.
The preview is restricted to regular US trading hours, including early closes.

After a brief callback pause, the last valid same-session endpoint remains visible with a stale label and its original timestamp; it is never called current or carried into a new session.

Provisional values replace just the final current-day chart point and update
cumulative totals and the current allocation row. They never rewrite daily NAVs,
signals, accounting, allocation events, approvals or orders. The rebasing selector
still controls period levels; the headline theoretical NAV/return stays cumulative.

## Daily attribution and diagnostics

The Trading page defaults stored PnL and reference-fill attribution to the latest
completed US session, using the shared holiday and early-close calendar. For
example, during September 28's session the daily totals remain explicitly dated
September 25. Live broker PnL continues to use its separate broker stream.
An explicit `as_of` request retains strict dated mark/FX checks; incomplete
attribution totals are null. Missing new valuations retain the last complete
dated chart/summary and observed execution slippage. The chart requests up to
100 saved snapshots and renders dots even when only the first session exists.

Research limitations and performance data checks are available in a collapsed,
scrollable disclosure. Backdated account captures are still excluded; their count
and three examples replace hundreds of repeated lines. Original snapshots remain
available as audit evidence. These messages describe data exclusions and research
assumptions; broker connection failures remain in the operational status panels.

The proposal queue shows the registered monthly decision and execution dates plus
the current portfolio-alignment result. Automatic approval acts on eligible
proposals; it does not change the monthly schedule or the drift threshold.

With the default ClickHouse backend, Strategy catalog/detail/reports and account
performance are prepared in the background and read from verified publications.
They are not recalculated on each page load. Reports show calculation time;
refresh errors retain the last complete result with a warning. Account resets
invalidate an incompatible saved performance chart immediately. The
[analytical migration guide](analytics-migration.md) lists coverage and rollback.

Before dated allocation records exist, the Trading dashboard compares the standalone saved strategy NAV history with daily account observations. In that legacy view, strategy values use the left index axis; account values use the right CNH axis. The first shared observation on or after the account first holds a position establishes the alignment. Selecting another period does not change that alignment. The Tracking preset starts at the alignment date, or the first available account observation if no shared date exists.

Hover, tap or focus the chart and use the arrow keys to inspect dates and values. Drag within the plot to select a period; Escape restores All. Date inputs and presets update the chart and selected-period statistics. Headline NAVs and cumulative returns remain anchored to the reset across zoom and rebasing changes. Month/year presets clamp to the last valid day of the destination month. Dense history retains all line and hover observations while reducing visible markers. Empty and single-series views remain usable, and chart geometry follows the available width.

## Account history and reset boundaries

- New broker snapshots retain an explicit UTC `captured_at` timestamp, separate from the declared valuation date. The last captured observation wins within each valuation date.
- Confirmed broker resets retain `account_reset_at` and `account_snapshot_path` in the PnL baseline. Later PnL collapses preserve these fields while keeping execution-state validation in force.
- Performance excludes earlier snapshots and retains the referenced reset snapshot. Legacy broker-reset baselines can resolve the original snapshot from immutable reconciliation reports. Missing or malformed reports do not fail the dashboard request.
- Old filename-only capture timestamps use the workstation-local convention that wrote those files; date-only snapshots cannot establish a precise intraday boundary. No historical audit files are rewritten.
- Non-strategy whole-share holdings are included using their recorded currency. Missing market prices can use a disclosed positive average-cost estimate. An unpriced holding with no valid estimate prevents a partial cash-only NAV from being presented as the full account value. Missing FX also prevents valuation.

Account NAV changes include deposits and withdrawals. They are not cash-flow-adjusted investment returns; the dashboard labels this distinction. Statistics use available observations, so short and sparse histories require care. Unsupported positions excluded by the existing broker snapshot contract cannot be reconstructed by this view.

## Strategy history and data gaps

The recorder's recurring daily backfill includes registered benchmarks even if they
are absent from ClickHouse. URTH coverage is checked from 2012-01-12 and AOR from
the research horizon's 2012-01-03 start. Without an explicit start-date override,
the fetch window expands to the first missing completed session, so a recent
lookback cannot strand older holes. Missing provider observations return a
nonzero child status and an explicit benchmark coverage error; the next cycle
retries. Stored provider observations feed monitored Strategy reports on reload.
Archived reports remain frozen. Historical repairs retain ingestion/provenance
metadata and do not certify historical point-in-time availability.

The saved backtest remains immutable. After its end date, the existing monitoring view marks its final holdings using stored prices and FX; it does not simulate new rebalance decisions. Missing US sessions, carried holding prices, stale FX and cost-based estimates appear in the warnings. No missing NAV observations are interpolated. Gaps longer than seven calendar days break the plotted line. Provider-backed data repair and backtest regeneration remain separate operations.

The performance API adds optional reset, tracking and alignment fields while retaining existing response fields. Invalid/non-finite strategy NAV entries are skipped and duplicate dates resolve to the last valid observation.

## Verification

Run `tests/test_allocation_performance.py`, `tests/test_spot_performance.py`, `tests/test_broker_pnl.py`, `tests/test_dashboard_performance.py`, `tests/test_ib_account_snapshot.py` and `tests/test_ib_reconciliation.py` for history, valuation, metadata and chart regressions. The chart behavior test runs the shipped JavaScript using Node.js when available. Browser verification uses a separate synthetic preview with no broker requests or operational service restart.
