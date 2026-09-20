"""Execution identity matching and deterministic accumulation of broker evidence."""

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from systematic_trading.domain import BrokerExecutionFill, BrokerOrderRecord
from systematic_trading.domain.enums import BrokerOrderStatus


def match_execution(
    records: list[BrokerOrderRecord], fill: BrokerExecutionFill,
) -> BrokerOrderRecord | None:
    # Client-scoped IB order numbers can be reused. Our order reference is the
    # stable identity; never fall back to a number when the reference disagrees.
    candidates = [record for record in records if fill.order_ref and record.order_ref == fill.order_ref]
    return candidates[0] if len(candidates) == 1 else None


def merge_execution_fills(
    record: BrokerOrderRecord, incoming: list[BrokerExecutionFill],
) -> BrokerOrderRecord:
    """Reject ambiguous evidence as a durable routing block; never guess history."""
    if record.execution_sync_issue:
        return record
    try:
        return _merge(record, incoming)
    except ValueError as exc:
        return record.model_copy(update={"execution_sync_issue": str(exc)})


def _merge(record: BrokerOrderRecord, incoming: list[BrokerExecutionFill]) -> BrokerOrderRecord:
    executions = {fill.execution_id: fill for fill in record.execution_fills}
    for fill in incoming:
        if not fill.execution_id or not fill.execution_id.strip():
            raise ValueError("Broker execution has no execution ID; cumulative quantity cannot be inferred safely.")
        if (fill.order_ref != record.order_ref or fill.symbol.upper() != record.order.symbol.upper()
                or fill.side != record.order.side
                or fill.currency is not None and fill.currency != record.order.currency):
            raise ValueError(f"Execution {fill.execution_id} conflicts with the local order identity.")
        if fill.filled_at.tzinfo is None:
            raise ValueError(f"Execution {fill.execution_id} has no timezone.")
        previous = executions.get(fill.execution_id)
        if previous is not None:
            # Order numbers may change when TWS binds an order to a new client.
            if previous.model_dump(exclude={"broker_order_id"}) != fill.model_dump(exclude={"broker_order_id"}):
                raise ValueError(f"Execution {fill.execution_id} was replayed with conflicting evidence.")
            continue
        superseded = [old for audit in record.execution_recoveries for old in audit.previous_fills
                      if old.execution_id == fill.execution_id and old.execution_id not in executions]
        if superseded:
            if fill.model_dump(exclude={"broker_order_id"}) != superseded[-1].model_dump(exclude={"broker_order_id"}):
                raise ValueError(f"Superseded execution {fill.execution_id} was replayed with conflicting evidence.")
            continue
        if any(_correction_family(old_id) == _correction_family(fill.execution_id) for old_id in executions):
            raise ValueError(f"Execution correction {fill.execution_id} requires audited recovery before routing.")
        if executions and any(old.account != fill.account for old in executions.values()):
            raise ValueError(f"Execution {fill.execution_id} changes the broker account for this order.")
        executions[fill.execution_id] = fill
    if len(executions) == len(record.execution_fills):
        return record
    fills = sorted(executions.values(), key=lambda fill: (fill.filled_at, fill.execution_id))
    quantity = sum(fill.quantity for fill in fills)
    complete_cumulative_evidence = all(fill.cumulative_quantity is not None for fill in fills)
    if complete_cumulative_evidence:
        accumulated = 0
        for fill in sorted(fills, key=lambda fill: fill.cumulative_quantity):
            accumulated += fill.quantity
            if accumulated != fill.cumulative_quantity:
                raise ValueError("Broker cumulative quantities expose a gap or overlap in execution history; audited recovery is required.")
    if record.filled_quantity and not record.execution_fills and (
        not complete_cumulative_evidence or quantity < record.filled_quantity
    ):
        raise ValueError("Legacy aggregate fills require an audited execution-history backfill before further sync.")
    if quantity > record.order.quantity:
        raise ValueError(f"Execution total {quantity} exceeds ordered quantity {record.order.quantity}.")
    average = sum((fill.average_price * fill.quantity for fill in fills), Decimal(0)) / quantity
    status = BrokerOrderStatus.FILLED if quantity == record.order.quantity else BrokerOrderStatus.PARTIALLY_FILLED
    if quantity < record.order.quantity and record.status in {BrokerOrderStatus.CANCELLED, BrokerOrderStatus.REJECTED}:
        status = record.status
    return record.model_copy(update={
        "execution_fills": fills,
        "filled_quantity": quantity,
        "remaining_quantity": record.order.quantity - quantity,
        "average_fill_price": average.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "status": status,
        "updated_at": max(_aware(record.updated_at), *(fill.filled_at for fill in fills)),
        "message": f"Accumulated {len(fills)} unique IB execution(s).",
    })


def preserve_execution_evidence(previous: BrokerOrderRecord, update: BrokerOrderRecord) -> BrokerOrderRecord:
    """A delayed placement acknowledgment must not erase concurrent fill sync."""
    if update.execution_recoveries != previous.execution_recoveries:
        update = update.model_copy(update={"execution_recoveries": previous.execution_recoveries,
                                           "execution_sync_issue": previous.execution_sync_issue})
    if previous.execution_sync_issue:
        update = update.model_copy(update={"execution_sync_issue": previous.execution_sync_issue})
    previous_ids = {fill.execution_id for fill in previous.execution_fills}
    update_ids = {fill.execution_id for fill in update.execution_fills}
    if previous_ids and not previous_ids < update_ids:
        fields = {name: getattr(previous, name) for name in (
            "execution_fills", "filled_quantity", "remaining_quantity", "average_fill_price",
        )}
        if update.status not in {BrokerOrderStatus.CANCELLED, BrokerOrderStatus.REJECTED} or previous.remaining_quantity == 0:
            fields["status"] = previous.status
        fields["updated_at"] = max(_aware(previous.updated_at), _aware(update.updated_at))
        update = update.model_copy(update=fields)
    return update


def _correction_family(execution_id: str) -> str:
    prefix, separator, revision = execution_id.rpartition(".")
    return prefix if separator and revision.isdigit() else execution_id


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def execution_state_token(records: list[BrokerOrderRecord]) -> str:
    payload = [record.model_dump(mode="json") for record in sorted(records, key=lambda record: record.local_order_id)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_baseline_state(baseline, records, previous) -> None:
    if baseline.execution_state_token is not None and (
        baseline.execution_state_token != execution_state_token(records)
        or baseline.parent_baseline_id != (previous.baseline_id if previous else None)
    ):
        raise ValueError("Execution history or PnL baseline changed during calculation; rebuild the baseline.")
