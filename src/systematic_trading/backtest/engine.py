from __future__ import annotations

from collections import defaultdict
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
        daily_rebalance_prices: Mapping[date, Mapping[str, Decimal]] | None = None,
        daily_execution_prices: Mapping[date, Mapping[str, Decimal]] | None = None,
        decision_dates_by_trade_date: Mapping[date, date] | None = None,
        transaction_cost_bps: Decimal | str = Decimal("0"),
        sleeve: str = "beta-risk-parity",
    ) -> BacktestResult:
        ledger = CashLedger(initial_cash)
        positions: dict[str, PortfolioPosition] = {}
        proposals: list[TradeProposal] = []
        nav_series: list[DailyNavPoint] = []
        final_snapshot: PortfolioSnapshot | None = None
        cost_rate = Decimal(transaction_cost_bps) / Decimal("10000")

        for trade_date in sorted(trade_dates):
            price_map = daily_prices[trade_date]
            fx_map = daily_fx_to_cnh[trade_date]
            converter = FxConverter(fx_map)
            rebalance_price_map = (
                daily_rebalance_prices[trade_date]
                if daily_rebalance_prices is not None and trade_date in daily_rebalance_prices
                else price_map
            )
            execution_price_map = (
                daily_execution_prices[trade_date]
                if daily_execution_prices is not None and trade_date in daily_execution_prices
                else rebalance_price_map
            )

            for position in positions.values():
                position.market_price = Decimal(price_map[position.symbol])

            if trade_date in target_schedule:
                decision_date = (decision_dates_by_trade_date or {}).get(trade_date, trade_date)
                proposal = self._proposal_builder.build(
                    as_of=decision_date,
                    intended_trade_date=trade_date,
                    sleeve=sleeve,
                    positions=list(positions.values()),
                    cash=ledger.snapshot(),
                    instruments=instruments,
                    prices=rebalance_price_map,
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
                    execution_prices=execution_price_map,
                    transaction_cost_rate=cost_rate,
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
        execution_prices: Mapping[str, Decimal] | None = None,
        transaction_cost_rate: Decimal = Decimal("0"),
    ) -> None:
        ordered_orders = sorted(orders, key=lambda item: 0 if item.side == OrderSide.SELL else 1)
        buy_scale: Decimal | None = None
        for order in ordered_orders:
            fill_price = Decimal((execution_prices or {}).get(order.symbol, order.reference_price))
            quantity = order.quantity
            if order.side == OrderSide.BUY:
                if buy_scale is None:
                    buy_scale = self._buy_affordability_scale(
                        orders=ordered_orders,
                        ledger=ledger,
                        converter=converter,
                        execution_prices=execution_prices,
                        transaction_cost_rate=transaction_cost_rate,
                    )
                if buy_scale < Decimal("1"):
                    quantity = int(Decimal(order.quantity) * buy_scale)
                    if quantity < 1:
                        continue
            local_notional = quantize_money(Decimal(quantity) * fill_price)
            transaction_cost = quantize_money(local_notional * max(transaction_cost_rate, Decimal("0")))

            if order.side == OrderSide.BUY:
                ledger.fund_and_withdraw(order.currency, local_notional + transaction_cost, converter)
                existing = positions.get(order.symbol)
                if existing is None:
                    instrument = instruments[order.symbol]
                    positions[order.symbol] = PortfolioPosition(
                        symbol=order.symbol,
                        quantity=quantity,
                        average_cost=fill_price,
                        market_price=fill_price,
                        currency=order.currency,
                        country=instrument.country,
                    )
                    continue

                total_quantity = existing.quantity + quantity
                total_cost = (Decimal(existing.quantity) * existing.average_cost) + (
                    Decimal(quantity) * fill_price
                )
                existing.quantity = total_quantity
                existing.average_cost = quantize_money(total_cost / Decimal(total_quantity))
                existing.market_price = fill_price
                continue

            existing = positions.get(order.symbol)
            if existing is None or quantity > existing.quantity:
                raise ValueError(f"Invalid sell order for {order.symbol}")

            existing.quantity -= quantity
            existing.market_price = fill_price
            ledger.deposit(order.currency, max(Decimal("0.00"), local_notional - transaction_cost))
            if existing.quantity == 0:
                positions.pop(order.symbol, None)

    def _buy_affordability_scale(
        self,
        *,
        orders: Sequence[OrderRequest],
        ledger: CashLedger,
        converter: FxConverter,
        execution_prices: Mapping[str, Decimal] | None,
        transaction_cost_rate: Decimal,
    ) -> Decimal:
        required_by_currency: dict[Currency, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for order in orders:
            if order.side != OrderSide.BUY:
                continue
            fill_price = Decimal((execution_prices or {}).get(order.symbol, order.reference_price))
            local_notional = quantize_money(Decimal(order.quantity) * fill_price)
            transaction_cost = quantize_money(local_notional * max(transaction_cost_rate, Decimal("0")))
            required_by_currency[order.currency] += local_notional + transaction_cost

        required_cnh = Decimal("0.00")
        for currency, required in required_by_currency.items():
            if currency == Currency.CNH:
                required_cnh += required
                continue
            shortfall = quantize_money(required - ledger.balance(currency))
            if shortfall > 0:
                required_cnh += converter.convert(shortfall, currency, Currency.CNH)

        available_cnh = ledger.balance(Currency.CNH)
        if required_cnh <= available_cnh or required_cnh <= 0:
            return Decimal("1")
        return max(Decimal("0"), (available_cnh / required_cnh) * Decimal("0.9999"))
