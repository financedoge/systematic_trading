from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    model_config = ConfigDict(frozen=True)

    symbol: str
    period_end: date
    filing_date: date | None = None
    available_date: date
    source: str | None = None
    revenue_growth_yoy: Decimal | None = None
    eps_growth_yoy: Decimal | None = None
    gross_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    net_margin: Decimal | None = None
    return_on_equity: Decimal | None = None
    return_on_invested_capital: Decimal | None = None
    free_cash_flow_margin: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    earnings_yield: Decimal | None = None
    dividend_yield: Decimal | None = None
    free_cash_flow_yield: Decimal | None = None
    debt_to_equity: Decimal | None = None
    net_debt_to_ebitda: Decimal | None = None
    interest_coverage: Decimal | None = None
    current_ratio: Decimal | None = None
    analyst_eps_revision_90d: Decimal | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _support_legacy_as_of(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        values = dict(data)
        legacy_as_of = values.get("as_of")
        if values.get("period_end") is None and legacy_as_of is not None:
            values["period_end"] = legacy_as_of
        if values.get("available_date") is None:
            values["available_date"] = values.get("filing_date") or legacy_as_of or values.get("period_end")
        return values
