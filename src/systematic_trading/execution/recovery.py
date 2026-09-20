"""Reviewed recovery of active paper execution history; no broker operations."""

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from systematic_trading.domain import BrokerExecutionFill, BrokerOrderRecord, PnLBaseline
from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment
from systematic_trading.domain.execution import ExecutionRecoveryAudit
from systematic_trading.execution.fills import _correction_family, merge_execution_fills


class ExecutionRecoveryRequest(BaseModel):
    local_order_id: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    account: str = Field(min_length=1)
    fills: list[BrokerExecutionFill] = Field(min_length=1)

    @field_validator("operator", "reason", "account", "local_order_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Recovery metadata cannot be blank.")
        return value.strip()


class ExecutionRecoveryPreview(BaseModel):
    review_token: str
    local_order_id: str
    previous_quantity: int
    recovered_quantity: int
    previous_average_price: str | None
    recovered_average_price: str
    execution_ids: list[str]
    warning: str = "Recovery does not submit orders. A new successful broker reconciliation is required before routing."


def preview_execution_recovery(
    record: BrokerOrderRecord, request: ExecutionRecoveryRequest, baseline: PnLBaseline | None,
) -> ExecutionRecoveryPreview:
    recovered = _validated_replacement(record, request, baseline)
    return ExecutionRecoveryPreview(
        review_token=_review_token(record, request, baseline), local_order_id=record.local_order_id,
        previous_quantity=record.filled_quantity, recovered_quantity=recovered.filled_quantity,
        previous_average_price=str(record.average_fill_price) if record.average_fill_price is not None else None,
        recovered_average_price=str(recovered.average_fill_price),
        execution_ids=[fill.execution_id for fill in recovered.execution_fills],
    )


def recover_execution_record(
    record: BrokerOrderRecord, request: ExecutionRecoveryRequest, baseline: PnLBaseline | None,
    *, review_token: str,
) -> BrokerOrderRecord:
    if review_token != _review_token(record, request, baseline):
        raise ValueError("Reviewed order, evidence or PnL baseline changed; generate a new preview.")
    recovered = _validated_replacement(record, request, baseline)
    audit = ExecutionRecoveryAudit(
        operator=request.operator, reason=request.reason, review_token=review_token,
        previous_fills=record.execution_fills, accepted_fills=recovered.execution_fills,
        previous_quantity=record.filled_quantity, previous_average_price=record.average_fill_price,
        previous_status=record.status, previous_issue=record.execution_sync_issue,
    )
    return recovered.model_copy(update={
        "execution_recoveries": [*record.execution_recoveries, audit],
        "updated_at": audit.recovered_at,
        "message": f"Audited paper execution recovery {audit.recovery_id}; fresh reconciliation required.",
    })


def _validated_replacement(record, request, baseline):
    if record.environment != OrderEnvironment.PAPER or record.order.environment != OrderEnvironment.PAPER:
        raise ValueError("Execution recovery is restricted to paper orders.")
    if record.broker != "interactive-brokers" or request.local_order_id != record.local_order_id:
        raise ValueError("Recovery request does not identify this IB order.")
    known_accounts = {fill.account for fill in record.execution_fills if fill.account}
    if known_accounts and known_accounts != {request.account}:
        raise ValueError("Recovery cannot change the broker account.")
    ids = [fill.execution_id for fill in request.fills]
    if any(not value or not value.strip() for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Recovery requires unique nonblank execution IDs.")
    if any(fill.account != request.account or fill.currency != record.order.currency
           or fill.cumulative_quantity is None for fill in request.fills):
        raise ValueError("Recovery requires the expected account, currency and cumulative quantity on every execution.")
    evidence = [*record.execution_fills, *request.fills]
    if any(fill.filled_at.tzinfo is None or fill.filled_at > datetime.now(UTC) for fill in evidence):
        raise ValueError("Recovery requires timezone-aware, non-future execution timestamps.")
    if baseline is not None:
        cutoff = _aware(baseline.cutoff_at)
        if (any(fill.filled_at <= cutoff for fill in evidence)
                or not record.execution_fills and record.filled_quantity
                and _aware(record.submitted_at or record.updated_at) <= cutoff):
            raise ValueError("Recovery could change an existing PnL baseline; an audited historical rebuild is required.")
    # Existing executions may only be retained or replaced by a newer correction
    # in the same IB execution family; unrelated evidence cannot be discarded.
    families = {_correction_family(fill.execution_id): fill for fill in request.fills}
    for old in record.execution_fills:
        replacement = families.get(_correction_family(old.execution_id))
        if replacement is None:
            raise ValueError(f"Recovery omits existing execution {old.execution_id}.")
        if replacement.execution_id == old.execution_id:
            if replacement.model_dump(exclude={"broker_order_id"}) != old.model_dump(exclude={"broker_order_id"}):
                raise ValueError("An existing execution ID cannot be rewritten; supply the broker correction ID.")
        elif int(replacement.execution_id.rsplit(".", 1)[1]) <= int(old.execution_id.rsplit(".", 1)[1]):
            raise ValueError("Recovery cannot replace an execution with an older correction revision.")
    seed = record.model_copy(update={
        "execution_fills": [], "execution_recoveries": [], "execution_sync_issue": None,
        "filled_quantity": 0, "average_fill_price": None,
        "status": record.status if record.status in {BrokerOrderStatus.CANCELLED, BrokerOrderStatus.REJECTED}
        else BrokerOrderStatus.SUBMITTED,
    })
    recovered = merge_execution_fills(seed, request.fills)
    if recovered.execution_sync_issue:
        raise ValueError(recovered.execution_sync_issue)
    return recovered


def _review_token(record, request, baseline):
    payload = {"record": record.model_dump(mode="json"), "request": request.model_dump(mode="json"),
               "baseline": baseline.model_dump(mode="json") if baseline else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
