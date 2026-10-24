"""Versioned operator API request/response contracts; no routing or I/O."""

from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from systematic_trading.domain import (
    TradeProposal,
    BrokerSubmissionResult,
    ProposalStatus,
)
from systematic_trading.domain.enums import (
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
)


class PlatformManifest(BaseModel):
    project: str
    base_currency: Currency
    default_environment: OrderEnvironment
    supported_regions: list[str]
    features: dict[str, bool]


class RealizedVolatilityEstimate(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    observation_count: int
    periods_per_year: int
    realized_volatility: Decimal


class RebalanceCancellationInput(BaseModel):
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


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
    switch_anchor: bool = False
    is_theoretical: bool = False
    break_before: bool = False
    return_break: bool = False
    period_start: str | None = None
    period_growth: Decimal | None = None
    allocation_version: str = "legacy"
    allocation_label: str = "Legacy / unverified strategy assignment"
    trade_date: date
    nav_cnh: Decimal
    index: Decimal


class DashboardPerformance(BaseModel):
    spot_basis: dict = Field(default_factory=dict)
    theoretical_contract: str | None = None
    theoretical_base_nav_cnh: Decimal | None = None
    strategy_comparison_start_date: date | None = None
    theoretical_periods: list[dict] = Field(default_factory=list)
    theoretical_sources: dict = Field(default_factory=dict)
    strategy_actual_rebased: list[DashboardSeriesPoint] = Field(default_factory=list)
    allocation_timeline: list[dict] = Field(default_factory=list)
    allocation_revision: str | None = None
    comparison_label: str = "Standalone strategy comparison"
    account_return_basis: str = "NAV change; external cash flows are not classified"
    portfolio_context: dict = Field(default_factory=dict)
    strategy_name: str
    strategy_source: str | None = None
    latest_strategy_data_date: date | None = None
    latest_market_data_date: date | None = None
    strategy_extension_count: int = 0
    account_source_count: int = 0
    account_reset_at: datetime | None = None
    account_tracking_start_date: date | None = None
    account_alignment_date: date | None = None
    account_alignment_nav_cnh: Decimal | None = None
    account_alignment_strategy_index: Decimal | None = None
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
    strategy_weight: Decimal | None = None
    target_value_cnh: Decimal | None = None
    weight_diff: Decimal | None = None
    trade_side: str | None = None
    trade_quantity: int | None = None
    currency: Currency | None = None
    price: Decimal | None = None


class DashboardHoldings(BaseModel):
    portfolio_context: dict = Field(default_factory=dict)
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


class BrokerPortfolioResetInput(BaseModel):
    confirm_reset_to_ib: bool = False


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
    allocation_label: str = "Legacy / unverified strategy assignment"
    allocation_version: str = "legacy"
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


class DashboardMissedOrderRow(BaseModel):
    proposal_id: str
    order_index: int
    symbol: str
    side: OrderSide
    quantity: int
    reference_notional_cnh: Decimal
    missed_at: datetime
    reason: str | None = None


class DashboardExecutionQuality(BaseModel):
    allocation_timeline: list[dict] = Field(default_factory=list)
    as_of: datetime
    portfolio_context: dict = Field(default_factory=dict)
    valuation_complete: bool = True
    filled_order_count: int = 0
    actual_pnl_cnh: Decimal | None
    theoretical_pnl_cnh: Decimal | None
    execution_gain_cnh: Decimal | None
    execution_gain_bps: Decimal | None = None
    execution_rows_gain_cnh: Decimal = Decimal("0")
    execution_reconciliation_difference_cnh: Decimal | None = None
    filled_notional_cnh: Decimal = Decimal("0")
    filled_trade_count: int = 0
    missed_order_count: int = 0
    missed_notional_cnh: Decimal = Decimal("0")
    missed_rows: list[DashboardMissedOrderRow] = Field(default_factory=list)
    history: list[DashboardPnlComparisonPoint] = Field(default_factory=list)
    slippage: list[DashboardSlippagePoint] = Field(default_factory=list)
    rows: list[DashboardExecutionSlippageRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OrderAnalyticsInput(BaseModel):
    local_order_ids: list[str] = Field(max_length=100)


from systematic_trading.portfolio.preview import (
    LatestPriceQuote as LatestPriceQuote,
    VolatilityInput as VolatilityInput,
    FXRateInput as FXRateInput,
    ExistingPositionInput as ExistingPositionInput,
    RiskParityPreviewRequest as RiskParityPreviewRequest,
)
