from __future__ import annotations

import json
import re
from datetime import UTC, date, timedelta
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from systematic_trading.backtest.accounting import FxConverter, PortfolioValuationService, quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.data.analytics import realized_volatility_from_bars
from systematic_trading.data.providers import DataSourceManifest, ProviderRegistry
from systematic_trading.domain import (
    ApprovalDecision,
    BrokerOrderRecord,
    BrokerOrderStatus,
    BrokerFillSyncResult,
    BrokerSubmissionResult,
    PnLBaseline,
    PnLSnapshot,
    ProposalStatus,
    ThesisMemo,
    TradeProposal,
    WatchlistEntry,
)
from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderSide, OrderType
from systematic_trading.domain.market import FXRate, Instrument, PriceBar
from systematic_trading.domain.portfolio import CashBalance, PortfolioPosition, PortfolioSnapshot
from systematic_trading.execution.broker import (
    BrokerConnectionProfile,
    InteractiveBrokersAdapter,
    InteractiveBrokersExecutionSynchronizer,
    InteractiveBrokersOrderRouter,
)
from systematic_trading.live import (
    LiveAccountSnapshotInput,
    SotaLiveRebalancePlan,
    TradingServiceStatus,
    build_dashboard_pnl_snapshot,
    build_pnl_baseline,
    build_reference_pnl_snapshot,
    fetch_and_write_account_snapshot,
    load_trading_service_status,
)
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.sqlite import SQLiteStore

router = APIRouter(prefix="/api/v1")
FAILED_RESUBMIT_STATUSES = {BrokerOrderStatus.REJECTED, BrokerOrderStatus.CANCELLED}
ACCOUNT_SNAPSHOT_PATTERN = re.compile(r"ib_paper_account_snapshot_(\d{8})(?:_\d{6})?\.json$")


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


class ProposalApprovalSubmitInput(BaseModel):
    comment: str | None = None


class BrokerSubmissionInput(BaseModel):
    environment: OrderEnvironment = OrderEnvironment.PAPER
    allow_resubmit: bool = False
    failed_only: bool = False
    route_order_type: OrderType | None = None
    confirm_submit: bool = False


class ProposalApprovalSubmissionResult(BaseModel):
    proposal: TradeProposal
    broker_submission: BrokerSubmissionResult


class DashboardSeriesPoint(BaseModel):
    trade_date: date
    nav_cnh: Decimal
    index: Decimal


class DashboardPerformance(BaseModel):
    strategy_name: str
    strategy_source: str | None = None
    latest_strategy_data_date: date | None = None
    latest_market_data_date: date | None = None
    strategy_extension_count: int = 0
    account_source_count: int = 0
    latest_strategy_nav_cnh: Decimal | None = None
    latest_account_nav_cnh: Decimal | None = None
    strategy_total_return: Decimal | None = None
    account_total_return: Decimal | None = None
    strategy: list[DashboardSeriesPoint] = Field(default_factory=list)
    account: list[DashboardSeriesPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DashboardHoldingDiff(BaseModel):
    symbol: str
    account_quantity: int | None = None
    account_value_cnh: Decimal | None = None
    account_weight: Decimal | None = None
    strategy_weight: Decimal = Decimal("0")
    target_value_cnh: Decimal | None = None
    weight_diff: Decimal | None = None
    trade_side: str | None = None
    trade_quantity: int | None = None
    currency: Currency | None = None
    price: Decimal | None = None


class DashboardHoldings(BaseModel):
    as_of: date | None = None
    account_snapshot_source: str | None = None
    strategy_source: str | None = None
    strategy_proposal_id: str | None = None
    account_nav_cnh: Decimal | None = None
    rows: list[DashboardHoldingDiff] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DashboardAccountSnapshotRefresh(BaseModel):
    output_path: str
    as_of: date | None = None
    cash_count: int
    position_count: int
    managed_accounts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DashboardPnlCollapseInput(BaseModel):
    cutoff_date: date


class DashboardPnlComparisonPoint(BaseModel):
    as_of: datetime
    actual_pnl_cnh: Decimal
    theoretical_pnl_cnh: Decimal
    execution_gain_cnh: Decimal


class DashboardSlippagePoint(BaseModel):
    trade_date: date
    daily_slippage_cnh: Decimal
    cumulative_slippage_cnh: Decimal
    daily_slippage_bps: Decimal | None = None


class DashboardExecutionSlippageRow(BaseModel):
    local_order_id: str
    proposal_id: str
    order_index: int
    symbol: str
    side: OrderSide
    filled_quantity: int
    reference_price: Decimal
    average_fill_price: Decimal
    currency: Currency
    reference_notional_cnh: Decimal | None = None
    actual_notional_cnh: Decimal | None = None
    execution_gain_cnh: Decimal | None = None
    execution_gain_bps: Decimal | None = None
    filled_at: datetime


class DashboardExecutionQuality(BaseModel):
    as_of: datetime
    actual_pnl_cnh: Decimal
    theoretical_pnl_cnh: Decimal
    execution_gain_cnh: Decimal
    execution_gain_bps: Decimal | None = None
    filled_notional_cnh: Decimal = Decimal("0")
    filled_trade_count: int = 0
    history: list[DashboardPnlComparisonPoint] = Field(default_factory=list)
    slippage: list[DashboardSlippagePoint] = Field(default_factory=list)
    rows: list[DashboardExecutionSlippageRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


@router.get("/automation/status", response_model=TradingServiceStatus)
def automation_status(request: Request) -> TradingServiceStatus:
    service = getattr(request.app.state, "trading_management_service", None)
    if service is not None:
        return service.status()
    return load_trading_service_status(_settings(request))


@router.get("/data-sources", response_model=list[DataSourceManifest])
def list_data_sources(request: Request) -> list[DataSourceManifest]:
    return _provider_registry(request).manifests()


@router.get("/execution/interactive-brokers/profiles", response_model=list[BrokerConnectionProfile])
def broker_profiles(request: Request) -> list[BrokerConnectionProfile]:
    return _broker(request).connection_profiles()


@router.get("/execution/interactive-brokers/orders", response_model=list[BrokerOrderRecord])
def list_broker_order_records(
    request: Request,
    proposal_id: str | None = Query(default=None),
) -> list[BrokerOrderRecord]:
    return _store(request).list_broker_order_records(proposal_id=proposal_id)


@router.post("/execution/interactive-brokers/proposals/{proposal_id}/submit", response_model=BrokerSubmissionResult)
def submit_proposal_to_ib(
    proposal_id: str,
    submission: BrokerSubmissionInput,
    request: Request,
) -> BrokerSubmissionResult:
    store = _store(request)
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposal: {proposal_id}")
    return _submit_proposal_to_ib(proposal=proposal, submission=submission, request=request)


def _submit_proposal_to_ib(
    *,
    proposal: TradeProposal,
    submission: BrokerSubmissionInput,
    request: Request,
) -> BrokerSubmissionResult:
    store = _store(request)
    route_proposal = _proposal_with_route_order_type(proposal, submission.route_order_type, _settings(request))
    order_indexes: set[int] | None = None
    allow_resubmit = submission.allow_resubmit
    if submission.failed_only:
        order_indexes = _retryable_order_indexes(
            route_proposal,
            store.list_broker_order_records(route_proposal.proposal_id),
        )
        if not order_indexes:
            raise HTTPException(
                status_code=400,
                detail=f"{route_proposal.proposal_id}: no failed or missing broker order records to resubmit.",
            )
        allow_resubmit = True
    client = getattr(request.app.state, "ib_order_client", None)
    order_router = InteractiveBrokersOrderRouter(_settings(request), client=client)
    validation_issues = order_router.validate_proposal_for_submission(
        proposal=route_proposal,
        store=store,
        environment=submission.environment,
        allow_resubmit=allow_resubmit,
        order_indexes=order_indexes,
    )
    if not submission.confirm_submit:
        return BrokerSubmissionResult(
            proposal_id=route_proposal.proposal_id,
            environment=submission.environment,
            records=[],
            validation_issues=validation_issues + ["confirm_submit is required before routing orders to IB."],
        )
    result = order_router.submit_approved_proposal(
        proposal=route_proposal,
        store=store,
        environment=submission.environment,
        allow_resubmit=allow_resubmit,
        order_indexes=order_indexes,
    )
    if result.validation_issues:
        raise HTTPException(status_code=400, detail=result.validation_issues)
    return result


@router.get("/dashboard/performance", response_model=DashboardPerformance)
def dashboard_performance(request: Request) -> DashboardPerformance:
    settings = _settings(request)
    store = _store(request)
    warnings: list[str] = []
    definition = current_sota_definition()
    strategy_path = _strategy_result_path(settings)
    strategy_payload = _load_json(strategy_path, warnings)
    strategy_base_date: date | None = None
    strategy_extension_count = 0
    if strategy_payload is not None:
        strategy_raw, strategy_base_date, strategy_extension_count = _strategy_nav_points(strategy_payload, store, warnings)
    else:
        strategy_raw = []
    account_raw = _account_nav_points(settings, store, warnings)
    strategy_series = _indexed_series(strategy_raw)
    account_series = _indexed_series(account_raw)
    latest_market_data_date = _latest_market_data_date(store)
    return DashboardPerformance(
        strategy_name=definition.name,
        strategy_source=str(strategy_path) if strategy_path.exists() else None,
        latest_strategy_data_date=strategy_base_date,
        latest_market_data_date=latest_market_data_date,
        strategy_extension_count=strategy_extension_count,
        account_source_count=len(account_raw),
        latest_strategy_nav_cnh=strategy_series[-1].nav_cnh if strategy_series else None,
        latest_account_nav_cnh=account_series[-1].nav_cnh if account_series else None,
        strategy_total_return=_series_return(strategy_series),
        account_total_return=_series_return(account_series),
        strategy=strategy_series,
        account=account_series,
        warnings=warnings,
    )


@router.get("/dashboard/holdings", response_model=DashboardHoldings)
def dashboard_holdings(request: Request) -> DashboardHoldings:
    settings = _settings(request)
    store = _store(request)
    warnings: list[str] = []
    account_source, account_snapshot = _latest_account_snapshot(settings, warnings)
    strategy_source, strategy_proposal = _latest_strategy_proposal(settings, store, warnings)
    if account_snapshot is None and strategy_proposal is None:
        return DashboardHoldings(warnings=warnings)

    as_of = _dashboard_as_of(account_source, account_snapshot, strategy_proposal)
    account_snapshot_model = account_snapshot or LiveAccountSnapshotInput(as_of=as_of)
    valuation, position_values, price_map = _value_account_snapshot(
        store=store,
        account_snapshot=account_snapshot_model,
        as_of=as_of,
        warnings=warnings,
    )
    account_nav = valuation.nav_cnh if valuation is not None else None
    account_quantities = {
        position.symbol.upper(): position.quantity
        for position in account_snapshot_model.positions
    }
    target_weights = {
        target.symbol.upper(): Decimal(target.target_weight)
        for target in (strategy_proposal.targets if strategy_proposal is not None else [])
    }
    order_by_symbol = {
        order.symbol.upper(): order
        for order in (strategy_proposal.orders if strategy_proposal is not None else [])
    }
    target_cash_weight = max(Decimal("0"), Decimal("1") - sum(target_weights.values(), Decimal("0")))
    symbols = set(account_quantities) | {symbol for symbol, weight in target_weights.items() if weight != 0} | set(order_by_symbol)
    rows: list[DashboardHoldingDiff] = []
    for symbol in sorted(symbols):
        account_value = position_values.get(symbol)
        account_weight = _weight(account_value, account_nav)
        strategy_weight = target_weights.get(symbol, Decimal("0"))
        target_value = quantize_money(account_nav * strategy_weight) if account_nav is not None else None
        order = order_by_symbol.get(symbol)
        rows.append(
            DashboardHoldingDiff(
                symbol=symbol,
                account_quantity=account_quantities.get(symbol),
                account_value_cnh=account_value,
                account_weight=account_weight,
                strategy_weight=_quantize_weight(strategy_weight),
                target_value_cnh=target_value,
                weight_diff=_weight_diff(strategy_weight, account_weight),
                trade_side=order.side.value if order is not None else None,
                trade_quantity=order.quantity if order is not None else None,
                currency=order.currency if order is not None else None,
                price=price_map.get(symbol),
            )
        )
    if account_nav is not None or target_cash_weight != 0:
        cash_value = quantize_money(account_nav - valuation.gross_exposure_cnh) if account_nav is not None and valuation is not None else None
        cash_weight = _weight(cash_value, account_nav)
        rows.append(
            DashboardHoldingDiff(
                symbol="CASH",
                account_value_cnh=cash_value,
                account_weight=cash_weight,
                strategy_weight=_quantize_weight(target_cash_weight),
                target_value_cnh=quantize_money(account_nav * target_cash_weight) if account_nav is not None else None,
                weight_diff=_weight_diff(target_cash_weight, cash_weight),
            )
        )
    rows.sort(key=_holding_sort_key)
    return DashboardHoldings(
        as_of=as_of,
        account_snapshot_source=str(account_source) if account_source is not None else None,
        strategy_source=str(strategy_source) if strategy_source is not None else None,
        strategy_proposal_id=strategy_proposal.proposal_id if strategy_proposal is not None else None,
        account_nav_cnh=account_nav,
        rows=rows,
        warnings=warnings,
    )


@router.post("/dashboard/account-snapshot/refresh", response_model=DashboardAccountSnapshotRefresh)
def refresh_dashboard_account_snapshot(request: Request) -> DashboardAccountSnapshotRefresh:
    client = getattr(request.app.state, "ib_account_snapshot_client", None)
    try:
        result = fetch_and_write_account_snapshot(
            settings=_settings(request),
            client=client,
            as_of=date.today(),
            sota_universe_only=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not refresh IB account snapshot: {exc}") from exc
    return DashboardAccountSnapshotRefresh(
        output_path=str(result.output_path),
        as_of=result.snapshot.as_of,
        cash_count=len(result.snapshot.cash),
        position_count=len(result.snapshot.positions),
        managed_accounts=result.managed_accounts,
        warnings=result.warnings,
    )


@router.post("/dashboard/fills/refresh", response_model=BrokerFillSyncResult)
def refresh_dashboard_fills(
    request: Request,
    environment: OrderEnvironment = Query(default=OrderEnvironment.PAPER),
) -> BrokerFillSyncResult:
    client = getattr(request.app.state, "ib_execution_sync_client", None)
    synchronizer = InteractiveBrokersExecutionSynchronizer(_settings(request), client=client)
    try:
        return synchronizer.sync_order_fills(store=_store(request), environment=environment)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not refresh IB fills: {exc}") from exc


@router.get("/dashboard/pnl", response_model=PnLSnapshot)
def dashboard_pnl(
    request: Request,
    as_of: date | None = Query(default=None),
) -> PnLSnapshot:
    return build_dashboard_pnl_snapshot(_store(request), as_of=as_of)


@router.get("/dashboard/execution-quality", response_model=DashboardExecutionQuality)
def dashboard_execution_quality(
    request: Request,
    as_of: date | None = Query(default=None),
    history_limit: int = Query(default=60, ge=1, le=1000),
) -> DashboardExecutionQuality:
    store = _store(request)
    actual = build_dashboard_pnl_snapshot(store, as_of=as_of)
    theoretical = build_reference_pnl_snapshot(store, as_of=as_of)
    rows, slippage_warnings = _execution_slippage_rows(store, as_of=actual.as_of.date())
    filled_notional = sum(
        (row.reference_notional_cnh for row in rows if row.reference_notional_cnh is not None),
        Decimal("0"),
    )
    row_gain = sum(
        (row.execution_gain_cnh for row in rows if row.execution_gain_cnh is not None),
        Decimal("0"),
    )
    execution_gain = quantize_money(actual.total_pnl_cnh - theoretical.total_pnl_cnh)
    gain_bps = _quantize_bps((row_gain / filled_notional) * Decimal("10000")) if filled_notional > 0 else None
    history = _pnl_comparison_history(store, history_limit)
    return DashboardExecutionQuality(
        as_of=actual.as_of,
        actual_pnl_cnh=actual.total_pnl_cnh,
        theoretical_pnl_cnh=theoretical.total_pnl_cnh,
        execution_gain_cnh=execution_gain,
        execution_gain_bps=gain_bps,
        filled_notional_cnh=quantize_money(filled_notional),
        filled_trade_count=len(rows),
        history=history,
        slippage=_daily_slippage_points(rows),
        rows=rows,
        warnings=_dedupe_messages([*actual.warnings, *theoretical.warnings, *slippage_warnings]),
    )


@router.post("/dashboard/pnl/snapshots", response_model=PnLSnapshot)
def save_dashboard_pnl_snapshot(
    request: Request,
    as_of: date | None = Query(default=None),
) -> PnLSnapshot:
    snapshot = build_dashboard_pnl_snapshot(_store(request), as_of=as_of)
    return _store(request).save_pnl_snapshot(snapshot)


@router.get("/dashboard/pnl/snapshots", response_model=list[PnLSnapshot])
def list_dashboard_pnl_snapshots(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[PnLSnapshot]:
    return _store(request).list_pnl_snapshots(limit=limit)


@router.post("/dashboard/pnl/collapse", response_model=PnLBaseline)
def collapse_dashboard_pnl_history(
    request_body: DashboardPnlCollapseInput,
    request: Request,
) -> PnLBaseline:
    baseline = build_pnl_baseline(_store(request), cutoff_date=request_body.cutoff_date)
    return _store(request).save_pnl_baseline(baseline)


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


@router.post("/proposals/{proposal_id}/approve-and-submit", response_model=ProposalApprovalSubmissionResult)
def approve_and_submit_proposal(
    proposal_id: str,
    approval: ProposalApprovalSubmitInput,
    request: Request,
) -> ProposalApprovalSubmissionResult:
    store = _store(request)
    try:
        proposal = store.apply_decision(
            ApprovalDecision(proposal_id=proposal_id, status=ProposalStatus.APPROVED, comment=approval.comment)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown proposal: {proposal_id}") from exc
    broker_submission = _submit_proposal_to_ib(
        proposal=proposal,
        submission=BrokerSubmissionInput(
            environment=OrderEnvironment.PAPER,
            confirm_submit=True,
            route_order_type=OrderType.TWAP,
        ),
        request=request,
    )
    return ProposalApprovalSubmissionResult(proposal=proposal, broker_submission=broker_submission)


def _retryable_order_indexes(proposal: TradeProposal, records: list[BrokerOrderRecord]) -> set[int]:
    latest_by_index: dict[int, BrokerOrderRecord] = {}
    for record in records:
        current = latest_by_index.get(record.order_index)
        if current is None or record.updated_at >= current.updated_at:
            latest_by_index[record.order_index] = record
    retryable = {
        order_index
        for order_index, record in latest_by_index.items()
        if record.status in FAILED_RESUBMIT_STATUSES
    }
    if not latest_by_index and proposal.status == ProposalStatus.APPROVED and proposal.orders:
        return set(range(len(proposal.orders)))
    if latest_by_index:
        retryable.update(
            index
            for index, _order in enumerate(proposal.orders)
            if index not in latest_by_index
        )
    return retryable


def _proposal_with_route_order_type(
    proposal: TradeProposal,
    route_order_type: OrderType | None,
    settings: AppSettings,
) -> TradeProposal:
    intended_trade_date = proposal.intended_trade_date or _next_weekday(proposal.as_of)
    return proposal.model_copy(
        update={
            "intended_trade_date": intended_trade_date,
            "orders": [
                order.model_copy(
                    update={
                        "order_type": route_order_type or order.order_type,
                        "intended_trade_date": order.intended_trade_date or intended_trade_date,
                        "execution_start_time": order.execution_start_time or settings.execution_twap_start_time,
                        "execution_end_time": order.execution_end_time or settings.execution_twap_end_time,
                    }
                )
                for order in proposal.orders
            ]
        }
    )


def _next_weekday(value: date) -> date:
    candidate = value + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _strategy_result_path(settings: AppSettings) -> Path:
    return settings.data_dir / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"


def _load_json(path: Path, warnings: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        warnings.append(f"Missing dashboard source: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not read {path}: {exc}")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"{path} did not contain a JSON object.")
        return None
    return payload


def _strategy_nav_points(
    payload: dict[str, Any],
    store: SQLiteStore,
    warnings: list[str],
) -> tuple[list[tuple[date, Decimal]], date | None, int]:
    points: list[tuple[date, Decimal]] = []
    for item in payload.get("nav_series", []):
        if not isinstance(item, dict):
            continue
        try:
            trade_date = date.fromisoformat(str(item["trade_date"]))
            nav = Decimal(str(item["nav_cnh"]))
        except (KeyError, ValueError):
            continue
        if nav > 0:
            points.append((trade_date, nav))
    points.sort(key=lambda item: item[0])
    if not points:
        warnings.append("Current SOTA strategy result has no NAV series.")
        return points, None, 0
    source_end_date = points[-1][0]
    extension = _strategy_mark_to_market_extension(payload, points, store, warnings)
    return [*points, *extension], source_end_date, len(extension)


def _strategy_mark_to_market_extension(
    payload: dict[str, Any],
    points: list[tuple[date, Decimal]],
    store: SQLiteStore,
    warnings: list[str],
) -> list[tuple[date, Decimal]]:
    if not points:
        return []
    source_end_date = points[-1][0]
    raw_snapshot = payload.get("final_snapshot")
    if not isinstance(raw_snapshot, dict):
        warnings.append(
            f"Strategy NAV source ends on {source_end_date}; no final strategy snapshot is available for mark-to-market extension."
        )
        return []
    try:
        snapshot = PortfolioSnapshot.model_validate(raw_snapshot)
    except ValueError as exc:
        warnings.append(f"Strategy NAV source ends on {source_end_date}; final snapshot could not be read: {exc}")
        return []
    positions = [position for position in snapshot.positions if position.quantity > 0]
    if not positions:
        return []

    bars_by_symbol = {
        position.symbol.upper(): [
            bar for bar in store.list_price_bars(position.symbol.upper(), start_date=source_end_date) if bar.trade_date > source_end_date
        ]
        for position in positions
    }
    trade_dates = sorted({bar.trade_date for bars in bars_by_symbol.values() for bar in bars})
    if not trade_dates:
        latest_bar_date = _latest_market_data_date_for_symbols(store, [position.symbol for position in positions])
        if latest_bar_date is None or latest_bar_date <= source_end_date:
            warnings.append(
                f"Strategy NAV source ends on {source_end_date}; stored market data for current strategy holdings also ends on "
                f"{latest_bar_date or source_end_date}, so the theoretical strategy line cannot extend toward today."
            )
        return []

    prices = {position.symbol.upper(): position.market_price for position in positions}
    bars_by_date: dict[date, list[tuple[str, PriceBar]]] = {}
    for symbol, bars in bars_by_symbol.items():
        for bar in bars:
            bars_by_date.setdefault(bar.trade_date, []).append((symbol, bar))
    currencies = {balance.currency for balance in snapshot.cash} | {position.currency for position in positions}
    extension: list[tuple[date, Decimal]] = []
    for trade_date in trade_dates:
        for symbol, bar in bars_by_date.get(trade_date, []):
            prices[symbol] = bar.close
        fx_to_cnh = _fx_to_cnh(store, currencies, trade_date, warnings)
        if fx_to_cnh is None:
            continue
        marked_positions = [
            position.model_copy(update={"market_price": prices[position.symbol.upper()]})
            for position in positions
        ]
        valuation = PortfolioValuationService.build_snapshot(
            as_of=trade_date,
            positions=marked_positions,
            cash=snapshot.cash,
            converter=FxConverter(fx_to_cnh),
        )
        extension.append((trade_date, valuation.nav_cnh))
    if extension:
        warnings.append(
            f"Strategy NAV was extended from {source_end_date} to {extension[-1][0]} by marking the final saved strategy holdings; "
            "rerun the full strategy artifact to include new rebalance decisions."
        )
    return extension


def _account_nav_points(
    settings: AppSettings,
    store: SQLiteStore,
    warnings: list[str],
) -> list[tuple[date, Decimal]]:
    points: list[tuple[date, Decimal]] = []
    for snapshot_path, snapshot in _account_snapshots(settings, warnings):
        as_of = snapshot.as_of or _account_snapshot_date(snapshot_path)
        if as_of is None:
            warnings.append(f"Could not infer account snapshot date for {snapshot_path}.")
            continue
        valuation, _, _ = _value_account_snapshot(
            store=store,
            account_snapshot=snapshot,
            as_of=as_of,
            warnings=warnings,
        )
        if valuation is not None and valuation.nav_cnh > 0:
            points.append((as_of, valuation.nav_cnh))
    deduped = {trade_date: nav for trade_date, nav in points}
    return sorted(deduped.items(), key=lambda item: item[0])


def _indexed_series(points: list[tuple[date, Decimal]]) -> list[DashboardSeriesPoint]:
    if not points:
        return []
    base_nav = points[0][1]
    if base_nav <= 0:
        return []
    return [
        DashboardSeriesPoint(
            trade_date=trade_date,
            nav_cnh=quantize_money(nav),
            index=_quantize_index((nav / base_nav) * Decimal("100")),
        )
        for trade_date, nav in points
    ]


def _series_return(series: list[DashboardSeriesPoint]) -> Decimal | None:
    if len(series) < 2:
        return None
    first_nav = series[0].nav_cnh
    if first_nav <= 0:
        return None
    return _quantize_weight((series[-1].nav_cnh / first_nav) - Decimal("1"))


def _account_snapshots(
    settings: AppSettings,
    warnings: list[str],
) -> list[tuple[Path, LiveAccountSnapshotInput]]:
    snapshot_dir = settings.data_dir / "live" / "account_snapshots"
    if not snapshot_dir.exists():
        warnings.append(f"Missing account snapshot directory: {snapshot_dir}")
        return []
    snapshots: list[tuple[Path, LiveAccountSnapshotInput]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            snapshots.append((path, LiveAccountSnapshotInput.model_validate_json(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as exc:
            warnings.append(f"Could not read account snapshot {path}: {exc}")
    return snapshots


def _latest_account_snapshot(
    settings: AppSettings,
    warnings: list[str],
) -> tuple[Path | None, LiveAccountSnapshotInput | None]:
    snapshots = _account_snapshots(settings, warnings)
    if not snapshots:
        return None, None
    snapshots.sort(key=lambda item: item[1].as_of or _account_snapshot_date(item[0]) or date.min)
    return snapshots[-1]


def _account_snapshot_date(path: Path) -> date | None:
    match = ACCOUNT_SNAPSHOT_PATTERN.match(path.name)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def _latest_strategy_proposal(
    settings: AppSettings,
    store: SQLiteStore,
    warnings: list[str],
) -> tuple[Path | None, TradeProposal | None]:
    live_plan_dir = settings.data_dir / "live" / "sota_rebalance"
    if live_plan_dir.exists():
        plan_paths = sorted(live_plan_dir.glob("sota_live_rebalance_*.json"), key=lambda item: item.stat().st_mtime)
        for path in reversed(plan_paths):
            try:
                plan = SotaLiveRebalancePlan.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                warnings.append(f"Could not read SOTA live plan {path}: {exc}")
                continue
            return path, plan.proposal

    stored_proposals = store.list_proposals()
    if stored_proposals:
        return None, stored_proposals[0]

    strategy_payload = _load_json(_strategy_result_path(settings), warnings)
    if strategy_payload is None:
        return None, None
    proposals = strategy_payload.get("proposals", [])
    if isinstance(proposals, list) and proposals:
        try:
            return _strategy_result_path(settings), TradeProposal.model_validate(proposals[-1])
        except ValueError as exc:
            warnings.append(f"Could not read latest strategy proposal from SOTA result: {exc}")
    return None, None


def _dashboard_as_of(
    account_source: Path | None,
    account_snapshot: LiveAccountSnapshotInput | None,
    strategy_proposal: TradeProposal | None,
) -> date:
    if account_snapshot is not None:
        snapshot_date = account_snapshot.as_of or (account_source and _account_snapshot_date(account_source))
        if snapshot_date is not None:
            return snapshot_date
    if strategy_proposal is not None:
        return strategy_proposal.as_of
    return date.today()


def _value_account_snapshot(
    *,
    store: SQLiteStore,
    account_snapshot: LiveAccountSnapshotInput,
    as_of: date,
    warnings: list[str],
) -> tuple[PortfolioSnapshot | None, dict[str, Decimal], dict[str, Decimal]]:
    positions: list[PortfolioPosition] = []
    position_values: dict[str, Decimal] = {}
    price_map: dict[str, Decimal] = {}
    currencies = {balance.currency for balance in account_snapshot.cash}
    instruments = instruments_for_definition(current_sota_definition())
    for input_position in account_snapshot.positions:
        symbol = input_position.symbol.upper()
        instrument = instruments.get(symbol)
        if instrument is None:
            warnings.append(f"{symbol}: account position is outside the configured SOTA universe and was not valued.")
            continue
        price = _latest_price(store, symbol, as_of)
        if price is None:
            if input_position.average_cost > 0:
                price = input_position.average_cost
                warnings.append(f"{symbol}: missing market price on or before {as_of}; average cost was used for valuation.")
            else:
                warnings.append(f"{symbol}: missing market price on or before {as_of}; position was not valued.")
                continue
        currencies.add(instrument.quote_currency)
        price_map[symbol] = price
        positions.append(
            PortfolioPosition(
                symbol=symbol,
                quantity=input_position.quantity,
                average_cost=input_position.average_cost,
                market_price=price,
                currency=instrument.quote_currency,
                country=instrument.country,
            )
        )

    fx_to_cnh = _fx_to_cnh(store, currencies, as_of, warnings)
    if fx_to_cnh is None:
        return None, position_values, price_map
    converter = FxConverter(fx_to_cnh)
    valuation = PortfolioValuationService.build_snapshot(
        as_of=as_of,
        positions=positions,
        cash=account_snapshot.cash,
        converter=converter,
    )
    for position in positions:
        local_value = Decimal(position.quantity) * position.market_price
        position_values[position.symbol] = converter.convert(local_value, position.currency)
    return valuation, position_values, price_map


def _latest_price(store: SQLiteStore, symbol: str, as_of: date) -> Decimal | None:
    bars = store.list_price_bars(symbol, end_date=as_of)
    return bars[-1].close if bars else None


def _fx_to_cnh(
    store: SQLiteStore,
    currencies: set[Currency],
    as_of: date,
    warnings: list[str],
) -> dict[Currency, Decimal] | None:
    rates: dict[Currency, Decimal] = {Currency.CNH: Decimal("1")}
    for currency in sorted(currencies):
        if currency == Currency.CNH:
            continue
        stored_rates = store.list_fx_rates(currency, end_date=as_of)
        if not stored_rates:
            warnings.append(f"Missing {currency}/CNH FX rate on or before {as_of}; account NAV was not valued.")
            return None
        rates[currency] = stored_rates[-1].rate
    return rates


def _latest_market_data_date(store: SQLiteStore) -> date | None:
    return _latest_market_data_date_for_symbols(store, instruments_for_definition(current_sota_definition()).keys())


def _latest_market_data_date_for_symbols(store: SQLiteStore, symbols: Iterable[str]) -> date | None:
    dates: list[date] = []
    for symbol in symbols:
        bars = store.list_price_bars(str(symbol).upper())
        if bars:
            dates.append(bars[-1].trade_date)
    return max(dates) if dates else None


def _execution_slippage_rows(
    store: SQLiteStore,
    *,
    as_of: date,
) -> tuple[list[DashboardExecutionSlippageRow], list[str]]:
    warnings: list[str] = []
    rows: list[DashboardExecutionSlippageRow] = []
    for record in store.list_broker_order_records():
        if record.filled_quantity <= 0 or record.average_fill_price is None:
            continue
        filled_at = _record_trade_time(record)
        if filled_at.date() > as_of:
            continue
        quantity = Decimal(record.filled_quantity)
        currency = record.order.currency
        fx = _single_fx_to_cnh(store, currency, filled_at.date(), warnings)
        reference_notional = None
        actual_notional = None
        execution_gain = None
        execution_gain_bps = None
        if fx is not None:
            reference_notional = record.order.reference_price * quantity * fx
            actual_notional = record.average_fill_price * quantity * fx
            if record.order.side == OrderSide.BUY:
                execution_gain = (record.order.reference_price - record.average_fill_price) * quantity * fx
            else:
                execution_gain = (record.average_fill_price - record.order.reference_price) * quantity * fx
            if reference_notional > 0:
                execution_gain_bps = _quantize_bps((execution_gain / reference_notional) * Decimal("10000"))
        rows.append(
            DashboardExecutionSlippageRow(
                local_order_id=record.local_order_id,
                proposal_id=record.proposal_id,
                order_index=record.order_index,
                symbol=record.order.symbol.upper(),
                side=record.order.side,
                filled_quantity=record.filled_quantity,
                reference_price=record.order.reference_price,
                average_fill_price=record.average_fill_price,
                currency=currency,
                reference_notional_cnh=quantize_money(reference_notional) if reference_notional is not None else None,
                actual_notional_cnh=quantize_money(actual_notional) if actual_notional is not None else None,
                execution_gain_cnh=quantize_money(execution_gain) if execution_gain is not None else None,
                execution_gain_bps=execution_gain_bps,
                filled_at=filled_at,
            )
        )
    rows.sort(key=lambda row: (row.filled_at, row.local_order_id))
    return rows, _dedupe_messages(warnings)


def _single_fx_to_cnh(store: SQLiteStore, currency: Currency, as_of: date, warnings: list[str]) -> Decimal | None:
    if currency == Currency.CNH:
        return Decimal("1")
    stored_rates = store.list_fx_rates(currency, end_date=as_of)
    if not stored_rates:
        warnings.append(f"Missing {currency}/CNH FX rate on or before {as_of}; execution slippage was not valued.")
        return None
    return stored_rates[-1].rate


def _record_trade_time(record: BrokerOrderRecord) -> datetime:
    value = record.submitted_at or record.updated_at
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _pnl_comparison_history(store: SQLiteStore, limit: int) -> list[DashboardPnlComparisonPoint]:
    points: list[DashboardPnlComparisonPoint] = []
    for actual in store.list_pnl_snapshots(limit=limit):
        theoretical = build_reference_pnl_snapshot(store, as_of=actual.as_of.date())
        points.append(
            DashboardPnlComparisonPoint(
                as_of=actual.as_of,
                actual_pnl_cnh=actual.total_pnl_cnh,
                theoretical_pnl_cnh=theoretical.total_pnl_cnh,
                execution_gain_cnh=quantize_money(actual.total_pnl_cnh - theoretical.total_pnl_cnh),
            )
        )
    points.sort(key=lambda point: point.as_of)
    return points


def _daily_slippage_points(rows: list[DashboardExecutionSlippageRow]) -> list[DashboardSlippagePoint]:
    daily_gain: dict[date, Decimal] = {}
    daily_notional: dict[date, Decimal] = {}
    for row in rows:
        trade_date = row.filled_at.date()
        daily_gain.setdefault(trade_date, Decimal("0"))
        daily_notional.setdefault(trade_date, Decimal("0"))
        if row.execution_gain_cnh is not None:
            daily_gain[trade_date] += row.execution_gain_cnh
        if row.reference_notional_cnh is not None:
            daily_notional[trade_date] += row.reference_notional_cnh
    cumulative = Decimal("0")
    points: list[DashboardSlippagePoint] = []
    for trade_date in sorted(daily_gain):
        daily = quantize_money(daily_gain[trade_date])
        cumulative = quantize_money(cumulative + daily)
        notional = daily_notional.get(trade_date, Decimal("0"))
        points.append(
            DashboardSlippagePoint(
                trade_date=trade_date,
                daily_slippage_cnh=daily,
                cumulative_slippage_cnh=cumulative,
                daily_slippage_bps=_quantize_bps((daily / notional) * Decimal("10000")) if notional > 0 else None,
            )
        )
    return points


def _weight(value: Decimal | None, nav: Decimal | None) -> Decimal | None:
    if value is None or nav is None or nav <= 0:
        return None
    return _quantize_weight(value / nav)


def _weight_diff(strategy_weight: Decimal, account_weight: Decimal | None) -> Decimal | None:
    if account_weight is None:
        return None
    return _quantize_weight(strategy_weight - account_weight)


def _holding_sort_key(row: DashboardHoldingDiff) -> tuple[Decimal, str]:
    magnitude = abs(row.weight_diff or row.strategy_weight or row.account_weight or Decimal("0"))
    return (-magnitude, row.symbol)


def _quantize_weight(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _quantize_index(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _quantize_bps(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _dedupe_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        deduped.append(message)
    return deduped
