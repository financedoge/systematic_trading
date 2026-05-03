from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderSide, OrderType, ProposalStatus
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


class TradeProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    as_of: date
    status: ProposalStatus = ProposalStatus.PENDING
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
        if self.status == ProposalStatus.PENDING:
            raise ValueError("Approval decisions must resolve a proposal to approved or rejected.")
        return self
