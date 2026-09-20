# Dashboard performance

The Trading dashboard compares the saved strategy NAV history with daily account observations. Strategy values use the left index axis; account values use the right CNH axis. The first shared observation on or after the account first holds a position establishes the alignment. Selecting another period does not change that alignment. The Tracking preset starts at the alignment date, or the first available account observation if no shared date exists.

Hover, tap or focus the chart and use the arrow keys to inspect dates and values. Drag within the plot to select a period; Escape restores All. Date inputs and presets update the summary values and statistics to the selected observations. Month/year presets clamp to the last valid day of the destination month. Dense history retains all line and hover observations while reducing visible markers. Empty and single-series views remain usable, and chart geometry follows the available width.

## Account history and reset boundaries

- New broker snapshots retain an explicit UTC `captured_at` timestamp, separate from the declared valuation date. The last captured observation wins within each valuation date.
- Confirmed broker resets retain `account_reset_at` and `account_snapshot_path` in the PnL baseline. Later PnL collapses preserve these fields while keeping execution-state validation in force.
- Performance excludes earlier snapshots and retains the referenced reset snapshot. Legacy broker-reset baselines can resolve the original snapshot from immutable reconciliation reports. Missing or malformed reports do not fail the dashboard request.
- Old filename-only capture timestamps use the workstation-local convention that wrote those files; date-only snapshots cannot establish a precise intraday boundary. No historical audit files are rewritten.
- Non-strategy whole-share holdings are included using their recorded currency. Missing market prices can use a disclosed positive average-cost estimate. An unpriced holding with no valid estimate prevents a partial cash-only NAV from being presented as the full account value. Missing FX also prevents valuation.

Account NAV changes include deposits and withdrawals. They are not cash-flow-adjusted investment returns; the dashboard labels this distinction. Statistics use available observations, so short and sparse histories require care. Unsupported positions excluded by the existing broker snapshot contract cannot be reconstructed by this view.

## Strategy history and data gaps

The saved backtest remains immutable. After its end date, the existing monitoring view marks its final holdings using stored prices and FX; it does not simulate new rebalance decisions. Missing US sessions, carried holding prices, stale FX and cost-based estimates appear in the warnings. No missing NAV observations are interpolated. Gaps longer than seven calendar days break the plotted line. Provider-backed data repair and backtest regeneration remain separate operations.

The performance API adds optional reset, tracking and alignment fields while retaining existing response fields. Invalid/non-finite strategy NAV entries are skipped and duplicate dates resolve to the last valid observation.

## Verification

Run `tests/test_dashboard_performance.py`, `tests/test_ib_account_snapshot.py` and `tests/test_ib_reconciliation.py` for history, valuation, metadata and chart regressions. The chart behavior test runs the shipped JavaScript using Node.js when available. Browser verification uses a separate synthetic preview with no broker requests or operational service restart.
