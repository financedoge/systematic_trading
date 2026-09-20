from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from systematic_trading.config import AppSettings
from systematic_trading.domain import (
    BrokerExecutionFill,
    BrokerOrderRecord,
    Currency,
    OrderEnvironment,
    OrderSide,
    PnLBaseline,
    PnLOpenLot,
)
from systematic_trading.execution.broker import (
    IBExecutionSyncClient,
    IbApiExecutionSyncClient,
    InteractiveBrokersAdapter,
)
from systematic_trading.live.account_snapshot import AccountSnapshotClient, fetch_and_write_account_snapshot
from systematic_trading.live.sota import AccountPositionInput
from systematic_trading.execution.fills import match_execution, merge_execution_fills, execution_state_token
from systematic_trading.storage.interfaces import TradingStore


class IBUnmatchedFill(BaseModel):
    symbol: str
    broker_order_id: int | None = None
    order_ref: str | None = None
    quantity: int
    average_price: Decimal
    filled_at: datetime


class LocalUnmatchedOrder(BaseModel):
    local_order_id: str
    proposal_id: str
    symbol: str
    broker_order_id: int | None = None
    order_ref: str
    filled_quantity: int
    status: str


class PositionDifference(BaseModel):
    symbol: str
    local_quantity: int
    ib_quantity: int
    difference: int


class IBPaperReconciliationReport(BaseModel):
    environment: OrderEnvironment = OrderEnvironment.PAPER
    checked_at: datetime
    report_path: str | None = None
    managed_accounts: list[str] = Field(default_factory=list)
    account_snapshot_path: str | None = None
    broker_cash: list[dict[str, str]] = Field(default_factory=list)
    broker_positions: list[AccountPositionInput] = Field(default_factory=list)
    local_order_history_count: int
    local_order_count: int
    local_filled_order_count: int
    ib_fill_count: int
    ib_position_count: int
    unmatched_local_orders: list[LocalUnmatchedOrder] = Field(default_factory=list)
    unmatched_ib_fills: list[IBUnmatchedFill] = Field(default_factory=list)
    position_differences: list[PositionDifference] = Field(default_factory=list)
    execution_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    pnl_reset_baseline_id: str | None = None
    reset_applied: bool = False

    @computed_field(return_type=bool)
    @property
    def has_breaks(self) -> bool:
        return bool(self.execution_issues) or not self.reset_applied and bool(
            self.unmatched_local_orders or self.unmatched_ib_fills or self.position_differences
        )

    @computed_field(return_type=bool)
    @property
    def requires_operator_confirmation(self) -> bool:
        return self.has_breaks

    @computed_field(return_type=str)
    @property
    def status(self) -> str:
        if self.execution_issues:
            return "break"
        if self.reset_applied:
            return "reset_to_broker"
        return "break" if self.has_breaks else "matched"


def reconcile_ib_paper_account(
    *,
    settings: AppSettings,
    store: TradingStore,
    execution_client: IBExecutionSyncClient | None = None,
    account_snapshot_client: AccountSnapshotClient | None = None,
    as_of: date | None = None,
    record_pnl_reset_baseline: bool = False,
    confirm_paper_reset: bool = False,
) -> IBPaperReconciliationReport:
    checked_at = datetime.now(tz=UTC)
    snapshot_result = fetch_and_write_account_snapshot(
        settings=settings,
        client=account_snapshot_client,
        as_of=as_of or checked_at.date(),
        sota_universe_only=False,
    )
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER).model_copy(
        update={"client_id": settings.ib_reconciliation_client_id or settings.ib_client_id + 60}
    )
    fill_client = execution_client or IbApiExecutionSyncClient()
    ib_fills = fill_client.fetch_fills(profile)
    all_history = store.list_broker_order_records()
    local_history = [
        record
        for record in all_history
        if record.environment == OrderEnvironment.PAPER
    ]
    baseline = store.latest_pnl_baseline()
    baseline_cutoff = _aware(baseline.cutoff_at) if baseline is not None else None
    execution_issues = [f"{record.order_ref}: {record.execution_sync_issue}"
                        for record in local_history if record.execution_sync_issue]
    # Reconciliation also detects newly changed evidence when called without a
    # preceding sync. It does not silently import fills or clear an existing block.
    evidence_by_record: dict[str, list[BrokerExecutionFill]] = {}
    for fill in ib_fills:
        record = match_execution(local_history, fill)
        if record is not None and record.execution_fills:
            evidence_by_record.setdefault(record.local_order_id, []).append(fill)
    for record in local_history:
        evidence = evidence_by_record.get(record.local_order_id)
        if evidence:
            checked = merge_execution_fills(record, evidence)
            if checked.execution_sync_issue:
                store.apply_broker_execution_fills(record.local_order_id, evidence)
                execution_issues.append(f"{record.order_ref}: {checked.execution_sync_issue}")
            elif checked.execution_fills != record.execution_fills:
                execution_issues.append(f"{record.order_ref}: broker executions await durable synchronization.")
    local_records = []
    for record in local_history:
        if record.execution_fills:
            active = [fill for fill in record.execution_fills
                      if baseline_cutoff is None or _aware(fill.filled_at) > baseline_cutoff]
            if active:
                local_records.append(record.model_copy(update={
                    "execution_fills": active,
                    "filled_quantity": sum(fill.quantity for fill in active),
                }))
        elif baseline_cutoff is None or _record_time(record) > baseline_cutoff:
            local_records.append(record)
    if baseline_cutoff is not None:
        ib_fills = [fill for fill in ib_fills if _aware(fill.filled_at) > baseline_cutoff]
    local_filled_records = [
        record
        for record in local_records
        if record.filled_quantity > 0 or record.average_fill_price is not None
    ]
    unmatched_local, unmatched_ib = _match_fills(local_filled_records, ib_fills)
    local_filled_history = [
        record
        for record in local_history
        if record.filled_quantity > 0 or record.average_fill_price is not None
    ]
    position_differences = _position_differences(
        local_filled_records,
        snapshot_result.snapshot.positions,
        baseline=baseline,
    )
    warnings = list(snapshot_result.warnings)
    suggested_actions = _suggested_actions(
        unmatched_local=unmatched_local,
        unmatched_ib=unmatched_ib,
        position_differences=position_differences,
        ib_position_count=len(snapshot_result.snapshot.positions),
    )
    if execution_issues:
        warnings.extend(execution_issues)
        suggested_actions = [action for action in suggested_actions if action != "No reconciliation breaks detected."]
        suggested_actions.append("Resolve execution-history issues through audited recovery; resetting positions does not clear them.")
    baseline_id: str | None = None
    reset_applied = False
    if record_pnl_reset_baseline:
        if not confirm_paper_reset:
            raise ValueError("--confirm-paper-reset is required before writing a PnL reset baseline.")
        if execution_issues:
            raise ValueError("Resolve execution-history issues before resetting the PnL baseline.")
        parent_baseline_id = baseline.baseline_id if baseline else None
        baseline = _broker_pnl_baseline(
            store=store,
            checked_at=checked_at,
            valuation_date=snapshot_result.snapshot.as_of or checked_at.date(),
            positions=snapshot_result.snapshot.positions,
            filled_trade_count=len(local_filled_history),
        )
        baseline.execution_state_token = execution_state_token(all_history)
        baseline.parent_baseline_id = parent_baseline_id
        store.save_pnl_baseline(baseline)
        baseline_id = baseline.baseline_id
        reset_applied = True
        suggested_actions.append(f"Reset active portfolio/PnL state to IB snapshot via baseline {baseline.baseline_id}.")

    report = IBPaperReconciliationReport(
        checked_at=checked_at,
        managed_accounts=snapshot_result.managed_accounts,
        account_snapshot_path=str(snapshot_result.output_path),
        broker_cash=[
            {"currency": balance.currency.value, "amount": str(balance.amount)}
            for balance in snapshot_result.snapshot.cash
        ],
        broker_positions=snapshot_result.snapshot.positions,
        local_order_history_count=len(local_history),
        local_order_count=len(local_records),
        local_filled_order_count=len(local_filled_records),
        ib_fill_count=len(ib_fills),
        ib_position_count=len(snapshot_result.snapshot.positions),
        unmatched_local_orders=unmatched_local,
        unmatched_ib_fills=unmatched_ib,
        position_differences=position_differences,
        execution_issues=_dedupe(execution_issues),
        warnings=_dedupe(warnings),
        suggested_actions=_dedupe(suggested_actions),
        pnl_reset_baseline_id=baseline_id,
        reset_applied=reset_applied,
    )
    return _persist_report(settings, report)


def _match_fills(
    local_records: list[BrokerOrderRecord],
    ib_fills: list[BrokerExecutionFill],
) -> tuple[list[LocalUnmatchedOrder], list[IBUnmatchedFill]]:
    # Persisted executions remain evidence even after falling out of IB's query
    # window. Position comparison still catches broker account resets/divergence.
    matched_local_ids = {record.local_order_id for record in local_records if record.execution_fills}
    unmatched_ib: list[IBUnmatchedFill] = []
    for fill in ib_fills:
        record = match_execution(local_records, fill)
        if record is not None and (fill.symbol.upper() != record.order.symbol.upper()
                                   or fill.side != record.order.side
                                   or fill.currency is not None and fill.currency != record.order.currency):
            record = None
        if record is None:
            unmatched_ib.append(
                IBUnmatchedFill(
                    symbol=fill.symbol,
                    broker_order_id=fill.broker_order_id,
                    order_ref=fill.order_ref,
                    quantity=fill.quantity,
                    average_price=fill.average_price,
                    filled_at=fill.filled_at,
                )
            )
        else:
            matched_local_ids.add(record.local_order_id)

    unmatched_local = [
        LocalUnmatchedOrder(
            local_order_id=record.local_order_id,
            proposal_id=record.proposal_id,
            symbol=record.order.symbol,
            broker_order_id=record.broker_order_id,
            order_ref=record.order_ref,
            filled_quantity=record.filled_quantity,
            status=record.status.value,
        )
        for record in local_records
        if record.local_order_id not in matched_local_ids
    ]
    return unmatched_local, unmatched_ib


def _position_differences(local_records, ib_positions, *, baseline: PnLBaseline | None) -> list[PositionDifference]:
    local_quantities: dict[str, int] = {}
    if baseline is not None:
        for lot in baseline.open_lots:
            symbol = lot.symbol.upper()
            local_quantities[symbol] = local_quantities.get(symbol, 0) + lot.quantity
    for record in local_records:
        signed_quantity = record.filled_quantity if record.order.side == OrderSide.BUY else -record.filled_quantity
        local_quantities[record.order.symbol.upper()] = local_quantities.get(record.order.symbol.upper(), 0) + signed_quantity
    ib_quantities = {position.symbol.upper(): position.quantity for position in ib_positions}
    differences: list[PositionDifference] = []
    for symbol in sorted(set(local_quantities) | set(ib_quantities)):
        local_quantity = local_quantities.get(symbol, 0)
        ib_quantity = ib_quantities.get(symbol, 0)
        if local_quantity != ib_quantity:
            differences.append(
                PositionDifference(
                    symbol=symbol,
                    local_quantity=local_quantity,
                    ib_quantity=ib_quantity,
                    difference=ib_quantity - local_quantity,
                )
            )
    return differences


def _broker_pnl_baseline(
    *,
    store: TradingStore,
    checked_at: datetime,
    valuation_date: date,
    positions: list[AccountPositionInput],
    filled_trade_count: int,
) -> PnLBaseline:
    open_lots: list[PnLOpenLot] = []
    for position in positions:
        if position.quantity <= 0:
            continue
        if position.average_cost <= 0:
            raise ValueError(f"Cannot reset {position.symbol} to IB; broker average cost is not positive.")
        fx_to_cnh = _fx_to_cnh(store, position.currency, valuation_date)
        if fx_to_cnh is None:
            raise ValueError(
                f"Cannot reset {position.symbol} to IB; missing {position.currency.value}/CNH FX on or before "
                f"{valuation_date}."
            )
        open_lots.append(
            PnLOpenLot(
                symbol=position.symbol.upper(),
                quantity=position.quantity,
                cost_price=position.average_cost,
                cost_fx_to_cnh=fx_to_cnh,
                currency=position.currency,
                opened_at=checked_at,
                source_order_id=f"ib-portfolio-reset:{position.symbol.upper()}:{checked_at.isoformat()}",
            )
        )
    return PnLBaseline(
        cutoff_at=checked_at,
        source="ib_broker_authoritative_reset",
        realized_pnl_cnh=Decimal("0"),
        realized_pnl_by_symbol_cnh={},
        open_lots=open_lots,
        filled_trade_count=filled_trade_count,
        warnings=[
            "Active portfolio/PnL state was reset to an operator-confirmed IB account snapshot. "
            "Earlier local broker records remain immutable audit history and are ignored before this cutoff."
        ],
    )


def _fx_to_cnh(store: TradingStore, currency: Currency, as_of: date) -> Decimal | None:
    if currency == Currency.CNH:
        return Decimal("1")
    rates = store.list_fx_rates(currency, end_date=as_of)
    return rates[-1].rate if rates else None


def latest_reconciliation_report_path(settings: AppSettings) -> Path:
    return settings.data_dir / "reconciliation" / "ib_paper_reconciliation_latest.json"


def load_latest_ib_reconciliation(settings: AppSettings) -> IBPaperReconciliationReport | None:
    path = latest_reconciliation_report_path(settings)
    if not path.exists():
        return None
    try:
        return IBPaperReconciliationReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def submission_reconciliation_issues(
    settings: AppSettings, *, now: datetime | None = None, required_after: datetime | None = None,
) -> list[str]:
    report = load_latest_ib_reconciliation(settings)
    if report is None:
        return ["Order routing is blocked until a fresh IB portfolio reconciliation succeeds."]
    if report.environment != OrderEnvironment.PAPER or report.has_breaks:
        return ["Order routing is blocked by an unresolved IB portfolio reconciliation break."]
    if required_after is not None and _aware(report.checked_at) <= _aware(required_after):
        return ["Order routing requires a new successful reconciliation after execution recovery."]
    age = (_aware(now or datetime.now(tz=UTC)) - _aware(report.checked_at)).total_seconds()
    if age < -5 or age > 180:
        return ["Order routing is blocked because the latest IB portfolio reconciliation is older than 180 seconds or future-dated."]
    return []


def _persist_report(settings: AppSettings, report: IBPaperReconciliationReport) -> IBPaperReconciliationReport:
    output_dir = settings.data_dir / "reconciliation"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.checked_at.strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_dir / f"ib_paper_reconciliation_{stamp}.json"
    report = report.model_copy(update={"report_path": str(output_path)})
    payload = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
    output_path.write_text(payload, encoding="utf-8")
    latest_reconciliation_report_path(settings).write_text(payload, encoding="utf-8")
    return report


def _record_time(record: BrokerOrderRecord) -> datetime:
    return _aware(record.submitted_at or record.updated_at)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _suggested_actions(
    *,
    unmatched_local: list[LocalUnmatchedOrder],
    unmatched_ib: list[IBUnmatchedFill],
    position_differences: list[PositionDifference],
    ib_position_count: int,
) -> list[str]:
    actions: list[str] = []
    if unmatched_ib:
        actions.append("Run fill sync, then inspect unmatched IB fills before generating new proposals.")
    if unmatched_local or position_differences:
        actions.append("Do not trust local PnL/exposure until reconciliation breaks are reviewed.")
    if ib_position_count == 0 and any(diff.local_quantity != 0 for diff in position_differences):
        actions.append(
            "IB paper account appears reset or empty while local records have exposure. "
            "After operator confirmation, run the reconciliation script with --record-pnl-reset-baseline --confirm-paper-reset."
        )
    if not actions:
        actions.append("No reconciliation breaks detected.")
    return actions


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
