from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from pydantic import BaseModel

from systematic_trading.backtest.accounting import CashLedger, FxConverter, PortfolioValuationService, quantize_money
from systematic_trading.domain.enums import Currency, OrderSide
from systematic_trading.domain.execution import OrderRequest, TradeProposal
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance, PortfolioPosition, PortfolioSnapshot
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder


class DailyNavPoint(BaseModel):
    trade_date: date
    nav_cnh: Decimal
    gross_exposure_cnh: Decimal
    cash_cnh: Decimal


class BacktestResult(BaseModel):
    nav_series: list[DailyNavPoint]
    proposals: list[TradeProposal]
    final_snapshot: PortfolioSnapshot


class DailyBacktestEngine:
    def __init__(self, proposal_builder: RebalanceProposalBuilder | None = None) -> None:
        self._proposal_builder = proposal_builder or RebalanceProposalBuilder()

    def run(
        self,
        *,
        trade_dates: Sequence[date],
        instruments: Mapping[str, Instrument],
        initial_cash: Iterable[CashBalance],
        daily_prices: Mapping[date, Mapping[str, Decimal]],
        daily_fx_to_cnh: Mapping[date, Mapping[Currency | str, Decimal | str]],
        target_schedule: Mapping[date, Sequence[AllocationTarget]],
        sleeve: str = "beta-risk-parity",
    ) -> BacktestResult:
        ledger = CashLedger(initial_cash)
        positions: dict[str, PortfolioPosition] = {}
        proposals: list[TradeProposal] = []
        nav_series: list[DailyNavPoint] = []
        final_snapshot: PortfolioSnapshot | None = None

        for trade_date in sorted(trade_dates):
            price_map = daily_prices[trade_date]
            fx_map = daily_fx_to_cnh[trade_date]
            converter = FxConverter(fx_map)

            for position in positions.values():
                position.market_price = Decimal(price_map[position.symbol])

            if trade_date in target_schedule:
                proposal = self._proposal_builder.build(
                    as_of=trade_date,
                    sleeve=sleeve,
                    positions=list(positions.values()),
                    cash=ledger.snapshot(),
                    instruments=instruments,
                    prices=price_map,
                    fx_to_cnh=fx_map,
                    targets=target_schedule[trade_date],
                )
                proposals.append(proposal)
                self._apply_orders(
                    orders=proposal.orders,
                    positions=positions,
                    ledger=ledger,
                    instruments=instruments,
                    converter=converter,
                )

            for position in positions.values():
                position.market_price = Decimal(price_map[position.symbol])

            final_snapshot = PortfolioValuationService.build_snapshot(
                as_of=trade_date,
                positions=positions.values(),
                cash=ledger.snapshot(),
                converter=converter,
            )
            nav_series.append(
                DailyNavPoint(
                    trade_date=trade_date,
                    nav_cnh=final_snapshot.nav_cnh,
                    gross_exposure_cnh=final_snapshot.gross_exposure_cnh,
                    cash_cnh=ledger.total_in_cnh(converter),
                )
            )

        if final_snapshot is None:
            raise ValueError("At least one trade date is required.")

        return BacktestResult(nav_series=nav_series, proposals=proposals, final_snapshot=final_snapshot)

    def _apply_orders(
        self,
        *,
        orders: Sequence[OrderRequest],
        positions: dict[str, PortfolioPosition],
        ledger: CashLedger,
        instruments: Mapping[str, Instrument],
        converter: FxConverter,
    ) -> None:
        ordered_orders = sorted(orders, key=lambda item: 0 if item.side == OrderSide.SELL else 1)
        for order in ordered_orders:
            local_notional = quantize_money(Decimal(order.quantity) * order.reference_price)

            if order.side == OrderSide.BUY:
                ledger.fund_and_withdraw(order.currency, local_notional, converter)
                existing = positions.get(order.symbol)
                if existing is None:
                    instrument = instruments[order.symbol]
                    positions[order.symbol] = PortfolioPosition(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        average_cost=order.reference_price,
                        market_price=order.reference_price,
                        currency=order.currency,
                        country=instrument.country,
                    )
                    continue

                total_quantity = existing.quantity + order.quantity
                total_cost = (Decimal(existing.quantity) * existing.average_cost) + (
                    Decimal(order.quantity) * order.reference_price
                )
                existing.quantity = total_quantity
                existing.average_cost = quantize_money(total_cost / Decimal(total_quantity))
                existing.market_price = order.reference_price
                continue

            existing = positions.get(order.symbol)
            if existing is None or order.quantity > existing.quantity:
                raise ValueError(f"Invalid sell order for {order.symbol}")

            existing.quantity -= order.quantity
            existing.market_price = order.reference_price
            ledger.deposit(order.currency, local_notional)
            if existing.quantity == 0:
                positions.pop(order.symbol, None)
