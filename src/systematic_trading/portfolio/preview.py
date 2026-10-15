"""Validated, side-effect-free risk-parity proposal previews."""

from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_CEILING
from pydantic import BaseModel, Field, model_validator
from systematic_trading.backtest.accounting import (
    FxConverter,
    PortfolioValuationService,
)
from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.execution import TradeProposal
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import (
    CashBalance,
    PortfolioPosition,
    PortfolioSnapshot,
)
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder


class LatestPriceQuote(BaseModel):
    symbol: str
    price: Decimal = Field(gt=0)


class VolatilityInput(BaseModel):
    symbol: str
    realized_volatility: Decimal = Field(gt=0)


class FXRateInput(BaseModel):
    currency: Currency
    rate_to_cnh: Decimal = Field(gt=0)


class ExistingPositionInput(BaseModel):
    symbol: str
    quantity: int = Field(ge=0)
    average_cost: Decimal = Field(ge=0)


class RiskParityPreviewRequest(BaseModel):
    as_of: date
    instruments: list[Instrument] = Field(min_length=1)
    prices: list[LatestPriceQuote] = Field(min_length=1)
    volatilities: list[VolatilityInput] = Field(min_length=1)
    fx_rates: list[FXRateInput]
    positions: list[ExistingPositionInput] = Field(default_factory=list)
    cash: list[CashBalance] = Field(default_factory=list)
    max_weight: Decimal | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def unique_inputs(self) -> RiskParityPreviewRequest:
        for field in ("instruments", "prices", "volatilities", "positions", "fx_rates"):
            key = "currency" if field == "fx_rates" else "symbol"
            identifiers = [getattr(item, key) for item in getattr(self, field)]
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"Duplicate {key} in {field}")
        if any(
            rate.currency == Currency.CNH and rate.rate_to_cnh != 1
            for rate in self.fx_rates
        ):
            raise ValueError("CNH rate_to_cnh must equal 1")
        return self


def build_risk_parity_preview(
    request_body: RiskParityPreviewRequest,
    environment: OrderEnvironment = OrderEnvironment.PAPER,
) -> tuple[TradeProposal, PortfolioSnapshot]:
    instrument_map = {
        instrument.symbol: instrument for instrument in request_body.instruments
    }
    price_map = {price.symbol: price.price for price in request_body.prices}
    volatility_map = {
        vol.symbol: vol.realized_volatility for vol in request_body.volatilities
    }
    fx_map: dict[Currency, Decimal] = {Currency.CNH: Decimal("1")}
    for rate_input in request_body.fx_rates:
        fx_map[rate_input.currency] = rate_input.rate_to_cnh

    missing_symbols = sorted(
        {
            *set(volatility_map) - set(instrument_map),
            *set(volatility_map) - set(price_map),
            *{position.symbol for position in request_body.positions}
            - set(instrument_map),
            *{position.symbol for position in request_body.positions} - set(price_map),
        }
    )
    if missing_symbols:
        raise ValueError(
            f"Missing instrument or price inputs for: {', '.join(missing_symbols)}"
        )

    required_symbols = set(volatility_map) | {
        position.symbol for position in request_body.positions
    }
    currencies = {instrument_map[symbol].quote_currency for symbol in required_symbols}
    currencies.update(balance.currency for balance in request_body.cash)
    missing_fx = sorted(
        currency.value for currency in currencies if currency not in fx_map
    )
    if missing_fx:
        raise ValueError(f"Missing FX rates for: {', '.join(missing_fx)}")

    beta_states = [
        BetaInstrumentState(
            instrument=instrument_map[symbol],
            realized_volatility=volatility,
        )
        for symbol, volatility in volatility_map.items()
    ]

    asset_count = Decimal(len(beta_states))
    minimum_workable_cap = (Decimal("1") / asset_count).quantize(
        Decimal("0.0001"), rounding=ROUND_CEILING
    )
    effective_max_weight = request_body.max_weight or max(
        Decimal("0.35"), minimum_workable_cap
    )
    if effective_max_weight * asset_count < Decimal("1"):
        raise ValueError(
            f"max_weight={effective_max_weight} is too low for {int(asset_count)} instruments. "
            f"Use at least {minimum_workable_cap}."
        )

    sleeve = RiskParityBetaSleeve(max_weight=effective_max_weight)
    targets = sleeve.generate_targets(beta_states)

    positions = [
        PortfolioPosition(
            symbol=position.symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            market_price=price_map[position.symbol],
            currency=instrument_map[position.symbol].quote_currency,
            country=instrument_map[position.symbol].country,
        )
        for position in request_body.positions
    ]
    cash = request_body.cash or [
        CashBalance(currency=Currency.CNH, amount=Decimal("0"))
    ]
    proposal = RebalanceProposalBuilder(environment=environment).build(
        as_of=request_body.as_of,
        sleeve=sleeve.name,
        positions=positions,
        cash=cash,
        instruments=instrument_map,
        prices=price_map,
        fx_to_cnh=fx_map,
        targets=targets,
    )
    snapshot = PortfolioValuationService.build_snapshot(
        as_of=request_body.as_of,
        positions=positions,
        cash=cash,
        converter=FxConverter(fx_map),
    )
    return proposal, snapshot
