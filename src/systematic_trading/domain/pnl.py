from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field

from systematic_trading.domain.enums import Currency


class PnLOpenLot(BaseModel):
    symbol: str
    quantity: int
    cost_price: Decimal = Field(gt=0)
    cost_fx_to_cnh: Decimal = Field(gt=0)
    currency: Currency
    opened_at: datetime
    source_order_id: str


class SymbolPnL(BaseModel):
    symbol: str
    quantity: int
    currency: Currency | None = None
    market_price: Decimal | None = None
    cost_basis_cnh: Decimal = Decimal("0")
    market_value_cnh: Decimal | None = None
    realized_pnl_cnh: Decimal = Decimal("0")
    unrealized_pnl_cnh: Decimal | None = None


class PnLSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    as_of: datetime
    source: str = "broker_order_records"
    baseline_id: str | None = None
    baseline_cutoff_at: datetime | None = None
    realized_pnl_cnh: Decimal = Decimal("0")
    unrealized_pnl_cnh: Decimal = Decimal("0")
    total_pnl_cnh: Decimal = Decimal("0")
    open_cost_basis_cnh: Decimal = Decimal("0")
    open_market_value_cnh: Decimal = Decimal("0")
    filled_trade_count: int = Field(default=0, ge=0)
    open_lot_count: int = Field(default=0, ge=0)
    valuation_complete: bool = True
    symbols: list[SymbolPnL] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class PnLBaseline(BaseModel):
    baseline_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    cutoff_at: datetime
    source: str = "broker_order_records"
    realized_pnl_cnh: Decimal = Decimal("0")
    realized_pnl_by_symbol_cnh: dict[str, Decimal] = Field(default_factory=dict)
    open_lots: list[PnLOpenLot] = Field(default_factory=list)
    filled_trade_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
