from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from systematic_trading.domain.enums import Currency


class CashBalance(BaseModel):
    currency: Currency
    amount: Decimal


class PortfolioPosition(BaseModel):
    symbol: str
    quantity: int = Field(ge=0)
    average_cost: Decimal = Field(ge=0)
    market_price: Decimal = Field(ge=0)
    currency: Currency
    country: str


class AllocationTarget(BaseModel):
    symbol: str
    target_weight: Decimal = Field(ge=0)
    sleeve: str
    rationale: str
    hold_horizon_months: int = Field(default=12, ge=1)


class PortfolioSnapshot(BaseModel):
    as_of: date
    base_currency: Currency = Currency.CNH
    cash: list[CashBalance]
    positions: list[PortfolioPosition]
    nav_cnh: Decimal
    gross_exposure_cnh: Decimal
    country_exposure_cnh: dict[str, Decimal]
    currency_exposure_cnh: dict[Currency, Decimal]
