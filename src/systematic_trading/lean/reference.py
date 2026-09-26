"""Python oracle for the explicitly declared CNH-adjusted-unit scenario."""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.domain.enums import Currency, OrderSide
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
from systematic_trading.lean.contracts import verify_bundle, write_json
from systematic_trading.lean.resources import process_resources
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research import current_sota_definition, instruments_for_definition


def run_reference(root: Path) -> dict:
    started = time.perf_counter()
    spec = verify_bundle(root)['spec']
    sessions = json.loads((root / 'sessions.json').read_text())
    decisions = json.loads((root / 'decisions.json').read_text())
    if spec.mode == 'shared':
        bars = json.loads((root / 'bars.json').read_text())
        decisions = {day: dict(row, targets=[t.model_dump(mode='json') for t in targets_for_day(
            bars, date.fromisoformat(row['signal_session']), benchmark=spec.strategy == 'benchmark',
            lookback_bars=spec.lookback_bars)]) for day, row in decisions.items()}
    quotes = json.loads((root / 'quotes.json').read_text())
    days = [date.fromisoformat(d) for d in sessions]
    instruments = {key: value.model_copy(update={'quote_currency': Currency.CNH})
                   for key, value in instruments_for_definition(current_sota_definition()).items()}
    fills = []
    decision_days = iter(sorted(decisions))
    cost = Decimal(spec.transaction_cost_bps) / 10000
    slip = Decimal(spec.slippage_bps) / 10000

    class Engine(DailyBacktestEngine):
        def _apply_orders(self, **kwargs):
            day = next(decision_days)
            before = {symbol: row.quantity for symbol, row in kwargs['positions'].items()}
            prices = dict(kwargs['execution_prices'])
            for order in kwargs['orders']:
                prices[order.symbol] = quantize_money(prices[order.symbol] * (1 + slip if order.side == OrderSide.BUY else 1 - slip))
            kwargs['execution_prices'] = prices
            super()._apply_orders(**kwargs)
            after = {symbol: row.quantity for symbol, row in kwargs['positions'].items()}
            for symbol in sorted(set(before) | set(after)):
                quantity = after.get(symbol, 0) - before.get(symbol, 0)
                if quantity:
                    price = prices[symbol]
                    fills.append({'date': day, 'symbol': symbol, 'quantity': quantity, 'price': str(price),
                                  'fee': str(quantize_money(abs(quantity) * price * cost))})

    result = Engine().run(
        trade_dates=days, instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal(spec.initial_cash_cnh))],
        daily_prices={d: {s: Decimal(q[d.isoformat()]['close']) for s, q in quotes.items()} for d in days},
        daily_rebalance_prices={d: {s: Decimal(q[d.isoformat()]['reference']) for s, q in quotes.items()} for d in days},
        daily_execution_prices={d: {s: Decimal(q[d.isoformat()]['open']) for s, q in quotes.items()} for d in days},
        daily_fx_to_cnh={d: {} for d in days},
        target_schedule={date.fromisoformat(d): [AllocationTarget.model_validate(t) for t in row['targets']] for d, row in decisions.items()},
        transaction_cost_bps=spec.transaction_cost_bps,
    )
    return {'schema_version': 1, 'engine': 'python', 'complete': True,
            'decisions': decisions, 'fills': fills,
            'nav': [{'date': row.trade_date.isoformat(), 'nav': str(row.nav_cnh), 'cash': str(row.cash_cnh)} for row in result.nav_series],
            'final_positions': {p.symbol: p.quantity for p in result.final_snapshot.positions},
            'elapsed_seconds': time.perf_counter() - started,
            'resources': process_resources()}


if __name__ == '__main__':
    write_json(Path(sys.argv[2]), run_reference(Path(sys.argv[1])))
