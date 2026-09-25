"""Audited opening P&L reset from a verified, flat pre-trade paper snapshot."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta

from systematic_trading.domain import PnLBaseline
from systematic_trading.domain.enums import OrderEnvironment, OrderSide
from systematic_trading.execution.fills import execution_state_token
from systematic_trading.execution.locks import serialized_orders
from systematic_trading.live.pnl import _broker_record_fills
from systematic_trading.live.sota import LiveAccountSnapshotInput
from systematic_trading.live.trading_calendar import previous_us_trading_day
from systematic_trading.live.initial_allocation import NY


@serialized_orders
def reset_paper_pnl_before_session(*, settings, store, trade_date, opening_report_path, operator, reason):
    from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, load_latest_ib_reconciliation, submission_reconciliation_issues
    if not operator.strip() or not reason.strip():
        raise ValueError("Operator and reset reason are required.")
    issues = submission_reconciliation_issues(settings)
    current = load_latest_ib_reconciliation(settings)
    if issues or current is None or current.warnings:
        raise ValueError("A fresh, matched and warning-free reconciliation is required.")
    opening = IBPaperReconciliationReport.model_validate_json(opening_report_path.read_text(encoding="utf-8"))
    if (opening.status != "matched" or opening.warnings or opening.execution_issues or opening.broker_positions
            or opening.ib_position_count or len(opening.managed_accounts) != 1
            or not opening.managed_accounts[0].startswith("DU") or opening.managed_accounts != current.managed_accounts):
        raise ValueError("Opening evidence must be a matched, flat snapshot of the same paper account.")
    from pathlib import Path
    source = Path(opening.account_snapshot_path)
    snapshot = LiveAccountSnapshotInput.model_validate_json(source.read_text(encoding="utf-8"))
    if snapshot.positions or not snapshot.cash or any(b.amount < 0 for b in snapshot.cash):
        raise ValueError("Opening snapshot must contain nonnegative cash and no positions.")
    cutoff = datetime.combine(trade_date, time.min, NY).astimezone(UTC) - timedelta(microseconds=1)
    captured = snapshot.captured_at
    if captured is None or captured.astimezone(NY).date() != trade_date or opening.checked_at.astimezone(NY).date() != trade_date:
        raise ValueError("Opening evidence must have been captured before trading in the requested session.")
    records = store.list_broker_order_records()
    if any(r.execution_sync_issue or r.pending_action for r in records):
        raise ValueError("Resolve execution or management issues before resetting P&L.")
    if any(r.environment != OrderEnvironment.PAPER and r.filled_quantity for r in records):
        raise ValueError("A mixed live/paper ledger cannot use a paper P&L reset.")
    fills = [f for f in _broker_record_fills(store, [], records=records) if f.traded_at > cutoff]
    if not fills or captured >= min(f.traded_at for f in fills) or opening.checked_at >= min(f.traded_at for f in fills):
        raise ValueError("The opening snapshot must precede every retained execution.")
    quantities = defaultdict(int)
    for fill in fills:
        quantities[fill.symbol] += fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
    expected = {s:q for s,q in quantities.items() if q}
    if expected != {p.symbol:p.quantity for p in current.broker_positions if p.quantity}:
        raise ValueError("Retained executions do not explain current IB holdings from a flat opening.")
    previous = store.latest_pnl_baseline()
    if previous and previous.cutoff_at >= cutoff:
        raise ValueError("The existing baseline already covers this cutoff; review instead of replacing it.")
    baseline = PnLBaseline(cutoff_at=cutoff, account_reset_at=cutoff,
        source="operator_confirmed_paper_opening_reset", execution_state_token=execution_state_token(records),
        parent_baseline_id=previous.baseline_id if previous else None,
        warnings=[f"Operator reset before {trade_date} using a verified flat opening paper snapshot. Earlier experiments remain in audit history."])
    # This is an explicit opening reference, not a fabricated earlier broker observation.
    reference = snapshot.model_copy(update={"as_of": previous_us_trading_day(trade_date)})
    reference_path = settings.data_dir / "live" / "account_snapshots" / f"pnl_opening_{trade_date}_{baseline.baseline_id}.json"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text(json.dumps({**reference.model_dump(mode="json"), "reference_for_session":str(trade_date),
        "observed_snapshot_path":str(source), "note":"Opening cash reference assigned to previous close; captured_at retains actual observation time."},indent=2),encoding="utf-8")
    baseline.account_snapshot_path = str(reference_path)
    audit_path = settings.data_dir / "live" / f"pnl_opening_reset_{baseline.baseline_id}.json"
    audit = dict(operator=operator, reason=reason, opening_report_path=str(opening_report_path),
        opening_snapshot_path=str(source), previous_baseline=previous.model_dump(mode="json") if previous else None,
        baseline=baseline.model_dump(mode="json"), retained_execution_count=len(fills), holdings=expected, status="prepared")
    audit_path.write_text(json.dumps(audit,indent=2),encoding="utf-8")
    store.save_pnl_baseline(baseline)  # Atomic ledger token and parent-baseline check.
    audit["status"] = "applied"
    audit_path.write_text(json.dumps(audit,indent=2),encoding="utf-8")
    return baseline
