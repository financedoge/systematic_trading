from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from systematic_trading.backtest.accounting import FxConverter, PortfolioValuationService
from systematic_trading.config import AppSettings
from systematic_trading.data.analytics import realized_volatility_from_bars
from systematic_trading.data.providers import DataSourceManifest, ProviderRegistry
from systematic_trading.domain import ApprovalDecision, ProposalStatus, ThesisMemo, TradeProposal, WatchlistEntry
from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.market import FXRate, Instrument, PriceBar
from systematic_trading.domain.portfolio import CashBalance, PortfolioPosition
from systematic_trading.execution.broker import BrokerConnectionProfile, InteractiveBrokersAdapter
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder
from systematic_trading.storage.sqlite import SQLiteStore

router = APIRouter(prefix="/api/v1")


class PlatformManifest(BaseModel):
    project: str
    base_currency: Currency
    default_environment: OrderEnvironment
    supported_regions: list[str]
    features: dict[str, bool]


class LatestPriceQuote(BaseModel):
    symbol: str
    price: Decimal = Field(gt=0)


class VolatilityInput(BaseModel):
    symbol: str
    realized_volatility: Decimal = Field(gt=0)


class RealizedVolatilityEstimate(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    observation_count: int
    periods_per_year: int
    realized_volatility: Decimal


class FXRateInput(BaseModel):
    currency: Currency
    rate_to_cnh: Decimal = Field(gt=0)


class ExistingPositionInput(BaseModel):
    symbol: str
    quantity: int = Field(ge=0)
    average_cost: Decimal = Field(ge=0)


class RiskParityPreviewRequest(BaseModel):
    as_of: date
    instruments: list[Instrument]
    prices: list[LatestPriceQuote]
    volatilities: list[VolatilityInput]
    fx_rates: list[FXRateInput]
    positions: list[ExistingPositionInput] = Field(default_factory=list)
    cash: list[CashBalance] = Field(default_factory=list)
    max_weight: Decimal | None = Field(default=None, gt=0)


class ProposalDecisionInput(BaseModel):
    status: ProposalStatus
    comment: str | None = None


def _settings(request: Request) -> AppSettings:
    return request.app.state.settings


def _store(request: Request) -> SQLiteStore:
    return request.app.state.store


def _provider_registry(request: Request) -> ProviderRegistry:
    return request.app.state.provider_registry


def _broker(request: Request) -> InteractiveBrokersAdapter:
    return request.app.state.broker


def _build_risk_parity_artifacts(
    request_body: RiskParityPreviewRequest,
    settings: AppSettings,
) -> tuple[TradeProposal, object]:
    instrument_map = {instrument.symbol: instrument for instrument in request_body.instruments}
    price_map = {price.symbol: price.price for price in request_body.prices}
    volatility_map = {vol.symbol: vol.realized_volatility for vol in request_body.volatilities}
    fx_map: dict[Currency, Decimal] = {Currency.CNH: Decimal("1")}
    for fx_rate in request_body.fx_rates:
        fx_map[fx_rate.currency] = fx_rate.rate_to_cnh

    missing_symbols = sorted(
        {
            *set(volatility_map) - set(instrument_map),
            *set(volatility_map) - set(price_map),
            *{position.symbol for position in request_body.positions} - set(instrument_map),
            *{position.symbol for position in request_body.positions} - set(price_map),
        }
    )
    if missing_symbols:
        raise HTTPException(status_code=400, detail=f"Missing instrument or price inputs for: {', '.join(missing_symbols)}")

    beta_states = [
        BetaInstrumentState(
            instrument=instrument_map[symbol],
            realized_volatility=volatility,
        )
        for symbol, volatility in volatility_map.items()
    ]

    asset_count = Decimal(len(beta_states))
    minimum_workable_cap = (Decimal("1") / asset_count).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    effective_max_weight = request_body.max_weight or max(Decimal("0.35"), minimum_workable_cap)
    if effective_max_weight * asset_count < Decimal("1"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"max_weight={effective_max_weight} is too low for {int(asset_count)} instruments. "
                f"Use at least {minimum_workable_cap}."
            ),
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
    cash = request_body.cash or [CashBalance(currency=Currency.CNH, amount=Decimal("0"))]
    proposal = RebalanceProposalBuilder(environment=settings.default_environment).build(
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


@router.get("/platform/manifest", response_model=PlatformManifest)
def platform_manifest(request: Request) -> PlatformManifest:
    settings = _settings(request)
    return PlatformManifest(
        project=settings.app_name,
        base_currency=settings.base_currency,
        default_environment=settings.default_environment,
        supported_regions=["US", "Europe", "HK", "Japan", "Korea"],
        features={
            "watchlist_first": True,
            "ai_assisted_research": True,
            "manual_trade_approval": True,
            "paper_trading_enabled": True,
            "live_trading_enabled": False,
        },
    )


@router.get("/data-sources", response_model=list[DataSourceManifest])
def list_data_sources(request: Request) -> list[DataSourceManifest]:
    return _provider_registry(request).manifests()


@router.get("/execution/interactive-brokers/profiles", response_model=list[BrokerConnectionProfile])
def broker_profiles(request: Request) -> list[BrokerConnectionProfile]:
    return _broker(request).connection_profiles()


@router.put("/watchlist/instruments/{symbol}", response_model=Instrument)
def upsert_watchlist_instrument(symbol: str, instrument: Instrument, request: Request) -> Instrument:
    if symbol != instrument.symbol:
        raise HTTPException(status_code=400, detail="Path symbol must match the instrument symbol.")
    return _store(request).upsert_instrument(instrument)


@router.put("/watchlist/theses/{symbol}", response_model=ThesisMemo)
def upsert_watchlist_thesis(symbol: str, thesis: ThesisMemo, request: Request) -> ThesisMemo:
    if symbol != thesis.symbol:
        raise HTTPException(status_code=400, detail="Path symbol must match the thesis symbol.")
    if thesis.symbol not in {instrument.symbol for instrument in _store(request).list_instruments()}:
        raise HTTPException(status_code=404, detail=f"Instrument {thesis.symbol} is not yet in the watchlist.")
    return _store(request).upsert_thesis(thesis)


@router.get("/watchlist", response_model=list[WatchlistEntry])
def list_watchlist(request: Request) -> list[WatchlistEntry]:
    return _store(request).list_watchlist()


@router.put("/market-data/bars/{symbol}", response_model=PriceBar)
def upsert_price_bar(symbol: str, bar: PriceBar, request: Request) -> PriceBar:
    return _store(request).upsert_price_bar(symbol, bar)


@router.get("/market-data/bars/{symbol}", response_model=list[PriceBar])
def list_price_bars(
    symbol: str,
    request: Request,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> list[PriceBar]:
    return _store(request).list_price_bars(symbol, start_date=start_date, end_date=end_date)


@router.get("/market-data/volatility/{symbol}", response_model=RealizedVolatilityEstimate)
def estimate_realized_volatility(
    symbol: str,
    request: Request,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    periods_per_year: int = Query(default=252, ge=1),
) -> RealizedVolatilityEstimate:
    bars = _store(request).list_price_bars(symbol, start_date=start_date, end_date=end_date)
    if len(bars) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"At least 3 price bars are required to estimate realized volatility for {symbol}.",
        )

    return RealizedVolatilityEstimate(
        symbol=symbol,
        start_date=bars[0].trade_date,
        end_date=bars[-1].trade_date,
        observation_count=len(bars) - 1,
        periods_per_year=periods_per_year,
        realized_volatility=realized_volatility_from_bars(bars, periods_per_year=periods_per_year),
    )


@router.put("/market-data/fx-rates", response_model=FXRate)
def upsert_fx_rate(rate: FXRate, request: Request) -> FXRate:
    return _store(request).upsert_fx_rate(rate)


@router.get("/market-data/fx-rates", response_model=list[FXRate])
def list_fx_rates(
    base_currency: Currency,
    request: Request,
    quote_currency: Currency = Query(default=Currency.CNH),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> list[FXRate]:
    return _store(request).list_fx_rates(
        base_currency,
        quote_currency=quote_currency,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/proposals/risk-parity-preview")
def preview_risk_parity(request_body: RiskParityPreviewRequest, request: Request) -> dict[str, object]:
    proposal, snapshot = _build_risk_parity_artifacts(request_body, _settings(request))
    return {"proposal": proposal, "snapshot": snapshot}


@router.post("/proposals/risk-parity-queue")
def queue_risk_parity(request_body: RiskParityPreviewRequest, request: Request) -> dict[str, object]:
    proposal, snapshot = _build_risk_parity_artifacts(request_body, _settings(request))
    issues = _broker(request).validate_orders(proposal.orders)
    if issues:
        raise HTTPException(status_code=400, detail=issues)
    _store(request).save_proposal(proposal)
    return {"proposal": proposal, "snapshot": snapshot, "queued": True}


@router.get("/proposals", response_model=list[TradeProposal])
def list_proposals(request: Request, status: ProposalStatus | None = Query(default=None)) -> list[TradeProposal]:
    return _store(request).list_proposals(status)


@router.post("/proposals/{proposal_id}/decisions", response_model=TradeProposal)
def decide_proposal(proposal_id: str, decision: ProposalDecisionInput, request: Request) -> TradeProposal:
    if decision.status == ProposalStatus.PENDING:
        raise HTTPException(status_code=400, detail="A decision must approve or reject the proposal.")
    try:
        return _store(request).apply_decision(
            ApprovalDecision(proposal_id=proposal_id, status=decision.status, comment=decision.comment)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown proposal: {proposal_id}") from exc
