from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from systematic_trading.domain.enums import AssetClass, Currency, Exchange


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    asset_class: AssetClass
    exchange: Exchange
    quote_currency: Currency
    country: str
    sector: str | None = None


class PriceBar(BaseModel):
    model_config = ConfigDict(frozen=True)

    trade_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)


class FXRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    rate_date: date
    base_currency: Currency
    quote_currency: Currency = Currency.CNH
    rate: Decimal = Field(gt=0)


class FundamentalSnapshot(BaseModel):
    symbol: str
    as_of: date
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    dividend_yield: Decimal | None = None
    free_cash_flow_yield: Decimal | None = None
    notes: str | None = None
