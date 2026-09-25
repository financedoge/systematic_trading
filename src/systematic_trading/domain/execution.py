from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.domain.portfolio import AllocationTarget


class ProposalReasoning(BaseModel):
    summary: str
    drivers: list[str] = Field(default_factory=list)
    invalidation_rules: list[str] = Field(default_factory=list)


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(ge=1)
    reference_price: Decimal = Field(gt=0)
    currency: Currency
    environment: OrderEnvironment = OrderEnvironment.PAPER
    notional_cnh: Decimal = Field(gt=0)
    rationale: str
    intended_trade_date: date | None = None
    execution_start_time: str | None = None
    execution_end_time: str | None = None


class TradeProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    trigger: str = "scheduled_rebalance"
    automation_strategy_key: str | None = None
    target_as_of: date | None = None
    target_source_proposal_id: str | None = None
    as_of: date
    intended_trade_date: date | None = None
    status: ProposalStatus = ProposalStatus.PENDING
    execution_deadline_at: datetime | None = None
    missed_at: datetime | None = None
    missed_reason: str | None = None
    sleeve: str
    summary: str
    base_currency: Currency = Currency.CNH
    targets: list[AllocationTarget] = Field(default_factory=list)
    orders: list[OrderRequest] = Field(default_factory=list)
    reasoning: ProposalReasoning


class ApprovalDecision(BaseModel):
    proposal_id: str
    status: ProposalStatus
    decided_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    comment: str | None = None

    @model_validator(mode="after")
    def validate_terminal_status(self) -> "ApprovalDecision":
        if self.status not in {ProposalStatus.APPROVED, ProposalStatus.REJECTED}:
            raise ValueError("Approval decisions must resolve a proposal to approved or rejected.")
        return self


class BrokerExecutionFill(BaseModel):
    execution_id: str | None = None
    account: str | None = None
    broker_order_id: int | None = None
    order_ref: str | None = None
    symbol: str
    side: OrderSide
    quantity: int = Field(ge=1)
    average_price: Decimal = Field(gt=0)
    cumulative_quantity: int | None = Field(default=None, ge=1)
    filled_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    currency: Currency | None = None


class ExecutionRecoveryAudit(BaseModel):
    recovery_id: str = Field(default_factory=lambda: uuid4().hex)
    recovered_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    operator: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    review_token: str
    previous_fills: list[BrokerExecutionFill]
    accepted_fills: list[BrokerExecutionFill]
    previous_quantity: int
    previous_average_price: Decimal | None
    previous_status: BrokerOrderStatus
    previous_issue: str | None


class BrokerOrderRecord(BaseModel):
    local_order_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    proposal_id: str
    broker: str = "interactive-brokers"
    environment: OrderEnvironment = OrderEnvironment.PAPER
    order_index: int = Field(ge=0)
    order: OrderRequest
    order_ref: str
    broker_order_id: int | None = None
    status: BrokerOrderStatus = BrokerOrderStatus.PENDING_SUBMIT
    submitted_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    filled_quantity: int = Field(default=0, ge=0)
    remaining_quantity: int | None = Field(default=None, ge=0)
    average_fill_price: Decimal | None = Field(default=None, ge=0)
    message: str | None = None
    broker_observation: dict = Field(default_factory=dict)
    management_revision: int = 0
    pending_action: dict | None = None
    management_audit: list[dict] = Field(default_factory=list)
    # Append-only execution evidence, persisted in the existing order JSON payload.
    execution_fills: list[BrokerExecutionFill] = Field(default_factory=list)
    execution_sync_issue: str | None = None
    execution_recoveries: list[ExecutionRecoveryAudit] = Field(default_factory=list)


class BrokerSubmissionResult(BaseModel):
    proposal_id: str
    broker: str = "interactive-brokers"
    environment: OrderEnvironment
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    records: list[BrokerOrderRecord] = Field(default_factory=list)
    validation_issues: list[str] = Field(default_factory=list)


class BrokerFillSyncResult(BaseModel):
    broker: str = "interactive-brokers"
    environment: OrderEnvironment
    synced_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    fills_seen: int = Field(default=0, ge=0)
    records_updated: int = Field(default=0, ge=0)
    records: list[BrokerOrderRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
