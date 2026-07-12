from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain import (
    BrokerExecutionFill,
    BrokerOrderRecord,
    OrderEnvironment,
    OrderSide,
    PnLBaseline,
)
from systematic_trading.execution.broker import (
    IBExecutionSyncClient,
    IbApiExecutionSyncClient,
    InteractiveBrokersAdapter,
)
from systematic_trading.live.account_snapshot import AccountSnapshotClient, fetch_and_write_account_snapshot
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
    managed_accounts: list[str] = Field(default_factory=list)
    account_snapshot_path: str | None = None
    local_order_count: int
    local_filled_order_count: int
    ib_fill_count: int
    ib_position_count: int
    unmatched_local_orders: list[LocalUnmatchedOrder] = Field(default_factory=list)
    unmatched_ib_fills: list[IBUnmatchedFill] = Field(default_factory=list)
    position_differences: list[PositionDifference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    pnl_reset_baseline_id: str | None = None

    @property
    def has_breaks(self) -> bool:
        return bool(self.unmatched_local_orders or self.unmatched_ib_fills or self.position_differences)


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
        update={"client_id": settings.ib_execution_sync_client_id or settings.ib_client_id + 30}
    )
    fill_client = execution_client or IbApiExecutionSyncClient()
    ib_fills = fill_client.fetch_fills(profile)
    local_records = [
        record
        for record in store.list_broker_order_records()
        if record.environment == OrderEnvironment.PAPER
    ]
    local_filled_records = [
        record
        for record in local_records
        if record.filled_quantity > 0 or record.average_fill_price is not None
    ]
    unmatched_local, unmatched_ib = _match_fills(local_filled_records, ib_fills)
    position_differences = _position_differences(local_filled_records, snapshot_result.snapshot.positions)
    warnings = list(snapshot_result.warnings)
    suggested_actions = _suggested_actions(
        unmatched_local=unmatched_local,
        unmatched_ib=unmatched_ib,
        position_differences=position_differences,
        ib_position_count=len(snapshot_result.snapshot.positions),
    )
    baseline_id: str | None = None
    if record_pnl_reset_baseline:
        if not confirm_paper_reset:
            raise ValueError("--confirm-paper-reset is required before writing a PnL reset baseline.")
        if snapshot_result.snapshot.positions:
            raise ValueError("PnL reset baseline is only supported when the fetched IB paper account has zero positions.")
        baseline = PnLBaseline(
            cutoff_at=checked_at,
            source="ib_paper_reconciliation_reset",
            realized_pnl_cnh=Decimal("0"),
            realized_pnl_by_symbol_cnh={},
            open_lots=[],
            filled_trade_count=len(local_filled_records),
            warnings=[
                "Paper account reset baseline recorded from IB reconciliation. "
                "Local broker order records remain audit history and are ignored for PnL before this cutoff."
            ],
        )
        store.save_pnl_baseline(baseline)
        baseline_id = baseline.baseline_id
        suggested_actions.append(f"Recorded empty PnL reset baseline {baseline.baseline_id}.")

    return IBPaperReconciliationReport(
        checked_at=checked_at,
        managed_accounts=snapshot_result.managed_accounts,
        account_snapshot_path=str(snapshot_result.output_path),
        local_order_count=len(local_records),
        local_filled_order_count=len(local_filled_records),
        ib_fill_count=len(ib_fills),
        ib_position_count=len(snapshot_result.snapshot.positions),
        unmatched_local_orders=unmatched_local,
        unmatched_ib_fills=unmatched_ib,
        position_differences=position_differences,
        warnings=_dedupe(warnings),
        suggested_actions=_dedupe(suggested_actions),
        pnl_reset_baseline_id=baseline_id,
    )


def _match_fills(
    local_records: list[BrokerOrderRecord],
    ib_fills: list[BrokerExecutionFill],
) -> tuple[list[LocalUnmatchedOrder], list[IBUnmatchedFill]]:
    local_by_broker_order_id = {
        record.broker_order_id: record
        for record in local_records
        if record.broker_order_id is not None
    }
    local_by_order_ref = {record.order_ref: record for record in local_records if record.order_ref}
    matched_local_ids: set[str] = set()
    unmatched_ib: list[IBUnmatchedFill] = []
    for fill in ib_fills:
        record = None
        if fill.broker_order_id is not None:
            record = local_by_broker_order_id.get(fill.broker_order_id)
        if record is None and fill.order_ref:
            record = local_by_order_ref.get(fill.order_ref)
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


def _position_differences(local_records, ib_positions) -> list[PositionDifference]:
    local_quantities: dict[str, int] = {}
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
