from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from systematic_trading.backtest.accounting import FxConverter, PortfolioValuationService, quantize_money
from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderSide, OrderType
from systematic_trading.domain.execution import OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance, PortfolioPosition


class RebalanceProposalBuilder:
    def __init__(
        self,
        *,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
        order_type: OrderType = OrderType.LIMIT,
        execution_start_time: str | None = None,
        execution_end_time: str | None = None,
    ) -> None:
        self.environment = environment
        self.order_type = order_type
        self.execution_start_time = execution_start_time
        self.execution_end_time = execution_end_time

    def build(
        self,
        *,
        as_of: date,
        sleeve: str,
        positions: Iterable[PortfolioPosition],
        cash: Iterable[CashBalance],
        instruments: Mapping[str, Instrument],
        prices: Mapping[str, Decimal | str],
        fx_to_cnh: Mapping[Currency | str, Decimal | str],
        targets: Iterable[AllocationTarget],
        intended_trade_date: date | None = None,
    ) -> TradeProposal:
        converter = FxConverter(fx_to_cnh)
        position_list = list(positions)
        target_list = list(targets)
        snapshot = PortfolioValuationService.build_snapshot(
            as_of=as_of,
            positions=position_list,
            cash=list(cash),
            converter=converter,
        )

        current_positions = {position.symbol: position for position in position_list}
        target_map = {target.symbol: target for target in target_list}
        symbols = sorted(set(current_positions) | set(target_map))
        orders: list[OrderRequest] = []

        for symbol in symbols:
            instrument = instruments[symbol]
            price_local = Decimal(prices[symbol])
            price_cnh = converter.convert(price_local, instrument.quote_currency, Currency.CNH)
            current_position = current_positions.get(symbol)
            current_quantity = current_position.quantity if current_position else 0
            current_value_cnh = quantize_money(Decimal(current_quantity) * price_cnh)

            target = target_map.get(symbol)
            target_weight = target.target_weight if target else Decimal("0")
            target_value_cnh = quantize_money(snapshot.nav_cnh * Decimal(target_weight))
            delta_cnh = quantize_money(target_value_cnh - current_value_cnh)
            if delta_cnh == Decimal("0.00") or price_cnh == Decimal("0.00"):
                continue

            share_count = int(abs(delta_cnh) / price_cnh)
            if share_count < 1:
                continue

            side = OrderSide.BUY if delta_cnh > 0 else OrderSide.SELL
            if side == OrderSide.SELL and current_position is not None:
                share_count = min(share_count, current_position.quantity)
                if share_count == 0:
                    continue

            rationale = (
                target.rationale
                if target is not None
                else "Target weight is zero because the symbol is no longer part of the active sleeve."
            )
            order_notional_cnh = quantize_money(Decimal(share_count) * price_cnh)
            orders.append(
                OrderRequest(
                    symbol=symbol,
                    side=side,
                    order_type=self.order_type,
                    quantity=share_count,
                    reference_price=price_local,
                    currency=instrument.quote_currency,
                    environment=self.environment,
                    notional_cnh=order_notional_cnh,
                    rationale=rationale,
                    intended_trade_date=intended_trade_date,
                    execution_start_time=self.execution_start_time,
                    execution_end_time=self.execution_end_time,
                )
            )

        buy_count = sum(1 for order in orders if order.side == OrderSide.BUY)
        sell_count = sum(1 for order in orders if order.side == OrderSide.SELL)
        if orders:
            summary = f"{sleeve} rebalance preview with {buy_count} buy orders and {sell_count} sell orders."
        else:
            summary = f"{sleeve} is within tolerance; no rebalance orders are required."

        top_targets = sorted(target_list, key=lambda item: item.target_weight, reverse=True)[:3]
        drivers = [f"{target.symbol}: {target.rationale}" for target in top_targets]

        return TradeProposal(
            as_of=as_of,
            intended_trade_date=intended_trade_date,
            sleeve=sleeve,
            summary=summary,
            targets=target_list,
            orders=orders,
            reasoning=ProposalReasoning(
                summary=(
                    f"Target weights were generated for {len(target_list)} instruments and translated into paper-order "
                    "previews using CNH as the reporting currency."
                ),
                drivers=drivers,
                invalidation_rules=[
                    "Do not route if required FX rates are stale or missing.",
                    "Do not route if the thesis owner has placed the watchlist item under review.",
                ],
            ),
        )
