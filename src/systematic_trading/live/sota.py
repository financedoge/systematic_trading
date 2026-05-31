from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from pydantic import BaseModel, Field

from systematic_trading.data.analytics import realized_volatility_from_bars
from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderType
from systematic_trading.domain.execution import TradeProposal
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance, PortfolioPosition
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder
from systematic_trading.research import current_sota_definition, instruments_for_definition, instantiate_overlays
from systematic_trading.signals.base import SignalContext, TargetOverlay
from systematic_trading.storage.sqlite import SQLiteStore


class AccountPositionInput(BaseModel):
    symbol: str
    quantity: int = Field(ge=0)
    average_cost: Decimal = Field(default=Decimal("0"), ge=0)


class LiveAccountSnapshotInput(BaseModel):
    as_of: date | None = None
    cash: list[CashBalance] = Field(default_factory=list)
    positions: list[AccountPositionInput] = Field(default_factory=list)


class SotaLiveRebalancePlan(BaseModel):
    strategy_key: str
    strategy_name: str
    decision_date: date
    intended_trade_date: date
    environment: OrderEnvironment
    eligible_symbols: list[str]
    target_count: int
    validation_issues: list[str] = Field(default_factory=list)
    queued: bool = False
    proposal: TradeProposal


def load_account_snapshot(path: Path) -> LiveAccountSnapshotInput:
    return LiveAccountSnapshotInput.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_sota_live_rebalance_plan(
    *,
    store: SQLiteStore,
    broker: InteractiveBrokersAdapter,
    account_snapshot: LiveAccountSnapshotInput,
    decision_date: date | None = None,
    intended_trade_date: date | None = None,
    environment: OrderEnvironment = OrderEnvironment.PAPER,
    order_type: OrderType = OrderType.TWAP,
    queue: bool = False,
    lookback_bars: int = 63,
    max_weight: Decimal = Decimal("0.45"),
    cash_reserve_weight: Decimal = Decimal("0.02"),
) -> SotaLiveRebalancePlan:
    definition = current_sota_definition()
    overlays = instantiate_overlays(definition)
    instruments = instruments_for_definition(definition)
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, end_date=decision_date or account_snapshot.as_of)
        for symbol in instruments
    }
    effective_decision_date = decision_date or account_snapshot.as_of or _latest_trade_date(bars_by_symbol)
    latest_available_trade_date = _latest_trade_date(bars_by_symbol)
    if decision_date is not None and latest_available_trade_date < effective_decision_date:
        raise ValueError(
            f"Latest SOTA market data is {latest_available_trade_date}; cannot build {effective_decision_date} "
            "live rebalance until market data is current."
        )
    bars_by_symbol = {
        symbol: [bar for bar in bars if bar.trade_date <= effective_decision_date]
        for symbol, bars in bars_by_symbol.items()
    }
    trade_dates = sorted({bar.trade_date for bars in bars_by_symbol.values() for bar in bars})
    if not trade_dates:
        raise ValueError("No stored price bars are available for the SOTA universe.")
    effective_intended_trade_date = intended_trade_date or _next_weekday(effective_decision_date)

    targets, eligible_symbols = _sota_targets_as_of(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        decision_date=effective_decision_date,
        sleeve_name=definition.sleeve_name,
        overlays=overlays,
        lookback_bars=lookback_bars,
        max_weight=max_weight,
        cash_reserve_weight=cash_reserve_weight,
    )
    prices = _latest_prices(bars_by_symbol, effective_decision_date)
    fx_to_cnh = _latest_fx_to_cnh(
        store=store,
        currencies=_required_currencies(instruments, account_snapshot),
        decision_date=effective_decision_date,
    )
    positions = _portfolio_positions(
        account_snapshot=account_snapshot,
        instruments=instruments,
        prices=prices,
    )
    cash = account_snapshot.cash or [CashBalance(currency=Currency.CNH, amount=Decimal("0"))]
    builder = RebalanceProposalBuilder(
        environment=environment,
        order_type=order_type,
        execution_start_time=broker.settings.execution_twap_start_time,
        execution_end_time=broker.settings.execution_twap_end_time,
    )
    proposal = builder.build(
        as_of=effective_decision_date,
        intended_trade_date=effective_intended_trade_date,
        sleeve=definition.sleeve_name,
        positions=positions,
        cash=cash,
        instruments=instruments,
        prices=prices,
        fx_to_cnh=fx_to_cnh,
        targets=targets,
    )
    validation_issues = broker.validate_orders(proposal.orders)
    queued = False
    if queue:
        if validation_issues:
            raise ValueError("Cannot queue proposal with validation issues: " + "; ".join(validation_issues))
        store.save_proposal(proposal)
        queued = True

    return SotaLiveRebalancePlan(
        strategy_key=definition.key,
        strategy_name=definition.name,
        decision_date=effective_decision_date,
        intended_trade_date=effective_intended_trade_date,
        environment=environment,
        eligible_symbols=eligible_symbols,
        target_count=len(targets),
        validation_issues=validation_issues,
        queued=queued,
        proposal=proposal,
    )


def write_sota_live_plan_artifacts(plan: SotaLiveRebalancePlan, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"sota_live_rebalance_{plan.decision_date.isoformat()}_{plan.proposal.proposal_id}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(plan.model_dump(mode="json"), indent=2), encoding="utf-8")
    markdown_path.write_text(_live_plan_markdown(plan), encoding="utf-8")
    return json_path, markdown_path


def _sota_targets_as_of(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    decision_date: date,
    sleeve_name: str,
    overlays: Sequence[TargetOverlay],
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
) -> tuple[list[AllocationTarget], list[str]]:
    max_required_history = max(
        [lookback_bars, *[getattr(overlay, "lookback_bars", lookback_bars) for overlay in overlays]]
    )
    states: list[BetaInstrumentState] = []
    for symbol, instrument in instruments.items():
        history = [bar for bar in bars_by_symbol.get(symbol, []) if bar.trade_date <= decision_date]
        if len(history) < max_required_history + 1:
            continue
        volatility = realized_volatility_from_bars(history[-(lookback_bars + 1) :])
        if volatility <= Decimal("0"):
            continue
        states.append(BetaInstrumentState(instrument=instrument, realized_volatility=volatility))
    if len(states) < 2:
        raise ValueError("At least two SOTA universe instruments need enough point-in-time history.")

    sleeve = RiskParityBetaSleeve(name=sleeve_name, max_weight=max_weight)
    investable_weight = Decimal("1") - cash_reserve_weight
    targets = [
        target.model_copy(update={"target_weight": target.target_weight * investable_weight})
        for target in sleeve.generate_targets(states)
    ]
    eligible_instruments = {state.instrument.symbol: state.instrument for state in states}
    context = SignalContext(
        as_of=decision_date,
        instruments=eligible_instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
    )
    for overlay in overlays:
        targets = overlay.apply(targets, context)
    return targets, sorted(eligible_instruments)


def _latest_trade_date(bars_by_symbol: Mapping[str, Sequence[PriceBar]]) -> date:
    dates = [bar.trade_date for bars in bars_by_symbol.values() for bar in bars]
    if not dates:
        raise ValueError("No stored price bars are available for the SOTA universe.")
    return max(dates)


def _latest_prices(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    decision_date: date,
) -> dict[str, Decimal]:
    prices: dict[str, Decimal] = {}
    for symbol, bars in bars_by_symbol.items():
        eligible = [bar for bar in bars if bar.trade_date <= decision_date]
        if eligible:
            prices[symbol] = eligible[-1].close
    return prices


def _required_currencies(
    instruments: Mapping[str, Instrument],
    account_snapshot: LiveAccountSnapshotInput,
) -> set[Currency]:
    currencies = {Currency.CNH}
    currencies.update(instrument.quote_currency for instrument in instruments.values())
    currencies.update(balance.currency for balance in account_snapshot.cash)
    return currencies


def _latest_fx_to_cnh(
    *,
    store: SQLiteStore,
    currencies: set[Currency],
    decision_date: date,
) -> dict[Currency, Decimal]:
    fx_to_cnh: dict[Currency, Decimal] = {Currency.CNH: Decimal("1")}
    for currency in sorted(currencies):
        if currency == Currency.CNH:
            continue
        rates = store.list_fx_rates(currency, end_date=decision_date)
        if not rates:
            raise ValueError(f"Missing {currency}/CNH FX rate on or before {decision_date}.")
        fx_to_cnh[currency] = rates[-1].rate
    return fx_to_cnh


def _portfolio_positions(
    *,
    account_snapshot: LiveAccountSnapshotInput,
    instruments: Mapping[str, Instrument],
    prices: Mapping[str, Decimal],
) -> list[PortfolioPosition]:
    positions: list[PortfolioPosition] = []
    for position in account_snapshot.positions:
        symbol = position.symbol.upper()
        if symbol not in instruments:
            raise ValueError(f"{symbol} is not in the SOTA all-weather ETF universe.")
        if symbol not in prices:
            raise ValueError(f"Missing latest price for existing position {symbol}.")
        instrument = instruments[symbol]
        positions.append(
            PortfolioPosition(
                symbol=symbol,
                quantity=position.quantity,
                average_cost=position.average_cost,
                market_price=prices[symbol],
                currency=instrument.quote_currency,
                country=instrument.country,
            )
        )
    return positions


def _next_weekday(value: date) -> date:
    candidate = value + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _live_plan_markdown(plan: SotaLiveRebalancePlan) -> str:
    orders = sorted(plan.proposal.orders, key=lambda order: (order.side.value, order.symbol))
    targets = sorted(plan.proposal.targets, key=lambda target: target.target_weight, reverse=True)
    lines = [
        "# SOTA Live Rebalance Plan",
        "",
        f"- Strategy: {plan.strategy_name}",
        f"- Decision date: {plan.decision_date}",
        f"- Intended trade date: {plan.intended_trade_date}",
        f"- Environment: {plan.environment.value}",
        f"- Proposal ID: {plan.proposal.proposal_id}",
        f"- Queued: {'yes' if plan.queued else 'no'}",
        f"- Eligible universe count: {len(plan.eligible_symbols)}",
        f"- Target count: {plan.target_count}",
        f"- Order count: {len(orders)}",
        "",
        "## Validation",
        "",
    ]
    if plan.validation_issues:
        lines.extend(f"- {issue}" for issue in plan.validation_issues)
    else:
        lines.append("- No local broker validation issues.")
    lines.extend(
        [
            "",
            "## Target Weights",
            "",
            "| Symbol | Target Weight | Rationale |",
            "| --- | ---: | --- |",
        ]
    )
    for target in targets:
        lines.append(f"| {target.symbol} | {_fmt_pct(target.target_weight)} | {target.rationale} |")
    lines.extend(
        [
            "",
            "## Paper Order Preview",
            "",
            "| Symbol | Side | Quantity | Type | Ref Price | Notional CNH |",
            "| --- | --- | ---: | --- | ---: | ---: |",
        ]
    )
    for order in orders:
        lines.append(
            f"| {order.symbol} | {order.side.value} | {order.quantity} | {order.order_type.value} | "
            f"{order.reference_price:.4f} | {order.notional_cnh:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Operating Notes",
            "",
            "- This artifact is a pre-trade plan. IB submission is intentionally separate from proposal generation.",
            "- Signals use the decision-date close; TWAP paper orders are intended for the next market session open window.",
            "- Paper routing should only be enabled after TWS or IB Gateway account, position, cash, and open-order reconciliation passes.",
            "- Live routing remains disabled until the paper process is stable and explicitly switched in configuration.",
        ]
    )
    return "\n".join(lines) + "\n"


def _fmt_pct(value: Decimal) -> str:
    return f"{value:.2%}"
