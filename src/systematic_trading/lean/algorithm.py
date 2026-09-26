"""Loaded only inside pinned LEAN. Actual fills and holdings belong to LEAN."""
from AlgorithmImports import *  # noqa: F403
import json
import sys
from datetime import datetime
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, '/input/source')

from systematic_trading.lean.contracts import verify_bundle, write_json
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research.strategy_catalog import StrategyDefinition
from systematic_trading.lean.resources import process_resources
from systematic_trading.backtest.accounting import CashLedger, FxConverter
from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.domain.portfolio import CashBalance, PortfolioPosition, AllocationTarget
from systematic_trading.domain.enums import Currency
from systematic_trading.portfolio.proposals import RebalanceProposalBuilder
from systematic_trading.research import current_sota_definition, instruments_for_definition


def money(value):
    return D(str(value)).quantize(D('0.01'), rounding=ROUND_HALF_UP)


class FrozenQuote(PythonData):  # noqa: F405
    def get_source(self, config, date, is_live):
        return SubscriptionDataSource(f'/input/quotes/{config.symbol.value.split(".")[0]}.csv', SubscriptionTransportMedium.LOCAL_FILE)  # noqa: F405

    def reader(self, config, line, date, is_live):
        stamp, value, phase = line.split(',')
        item = FrozenQuote()
        item.symbol = config.symbol
        item.time = datetime.fromisoformat(stamp)
        item.end_time = item.time
        item.value = float(value)
        item['phase'] = 1 if phase == 'open' else 2
        return item


class DeclaredFee(FeeModel):  # noqa: F405
    def __init__(self, bps, slippage_bps):
        self.rate = D(bps) / 10000
        self.slip = D(slippage_bps) / 10000

    def get_order_fee(self, parameters):
        price = money(D(str(parameters.security.price)) * (1 + self.slip if parameters.order.quantity > 0 else 1 - self.slip))
        value = money(abs(D(str(parameters.order.quantity))) * price * self.rate)
        return OrderFee(CashAmount(float(value), 'CNH'))  # noqa: F405


class DeclaredFill(ImmediateFillModel):  # noqa: F405
    def __init__(self, bps):
        self.slip = D(bps) / 10000

    def market_fill(self, asset, order):
        result = super().market_fill(asset, order)
        if result.status == OrderStatus.FILLED:  # noqa: F405
            result.fill_price = float(money(D(str(asset.price)) * (1 + self.slip if order.quantity > 0 else 1 - self.slip)))
        return result


class FrozenPortfolioAlgorithm(QCAlgorithm):  # noqa: F405
    def initialize(self):
        self.root = Path('/input')
        self.spec = verify_bundle(self.root)['spec']
        self.sessions = json.loads((self.root / 'sessions.json').read_text())
        self.expected_decisions = json.loads((self.root / 'decisions.json').read_text())
        self.quotes = json.loads((self.root / 'quotes.json').read_text())
        self.rows = json.loads((self.root / 'bars.json').read_text())
        self.constituent_features = json.loads((self.root / 'constituent_features.json').read_text()) if self.spec.constituent_overlay else None
        self.base_tree_models = json.loads((self.root / 'base_tree_models.json').read_text()) if self.spec.base_tree_model_schedule else None
        self.instruments = {k: v.model_copy(update={'quote_currency': Currency.CNH}) for k, v in
                            instruments_for_definition(current_sota_definition()).items()}
        self.set_time_zone(TimeZones.NEW_YORK)  # noqa: F405
        self.set_start_date(datetime.fromisoformat(self.spec.start_date))
        self.set_end_date(datetime.fromisoformat(self.spec.end_date))
        self.set_account_currency('CNH')
        self.set_cash(float(self.spec.initial_cash_cnh))
        self.set_benchmark(lambda stamp: 1.0)
        self.symbols_by_name = {}
        for name in sorted(self.quotes):
            properties = SymbolProperties(name, 'CNH', 1, 0.01, 1, name)  # noqa: F405
            hours = SecurityExchangeHours.always_open(TimeZones.NEW_YORK)  # noqa: F405
            security = self.add_data(FrozenQuote, name, properties, hours, Resolution.MINUTE, False, 1)  # noqa: F405
            security.set_fee_model(DeclaredFee(self.spec.transaction_cost_bps, self.spec.slippage_bps))
            security.set_fill_model(DeclaredFill(self.spec.slippage_bps))
            security.set_buying_power_model(SecurityMarginModel(1))  # noqa: F405
            self.symbols_by_name[name] = security.symbol
        self.nav_rows, self.fills, self.decisions = [], [], {}
        self.processed = set()
        self.flow_state = {}

    def on_data(self, data):
        day = self.time.date().isoformat()
        present = [data[s] for s in self.symbols_by_name.values() if data.contains_key(s)]
        if not present:
            return
        phase = int(present[0]['phase'])
        key = (day, phase)
        if key in self.processed:
            return
        if len(present) != len(self.symbols_by_name) or any(int(p['phase']) != phase for p in present):
            raise ValueError(f'Incomplete synchronized data slice {day}')
        self.processed.add(key)
        if phase == 1 and day in self.expected_decisions:
            expected = self.expected_decisions[day]
            if self.spec.mode == 'shared':
                targets = targets_for_day(self.rows, datetime.fromisoformat(expected['signal_session']).date(),
                                          benchmark=self.spec.strategy == 'benchmark', lookback_bars=self.spec.lookback_bars,
                                          flow_overlay=self.spec.flow_overlay, flow_state=self.flow_state,
                                          constituent_overlay=self.spec.constituent_overlay,
                                          constituent_features=self.constituent_features, base_tree_models=self.base_tree_models,
                                          fixed_model_from=self.spec.fixed_model_from,
                                          definition=StrategyDefinition.from_dict(self.spec.strategy_definition) if self.spec.strategy_definition else None)
            else:
                targets = [AllocationTarget.model_validate(t) for t in expected['targets']]
            self.decisions[day] = dict(expected, targets=[t.model_dump(mode='json') for t in targets])
            positions = [PortfolioPosition(symbol=name, quantity=int(self.portfolio[symbol].quantity),
                          average_cost=D(str(self.portfolio[symbol].average_price)),
                          market_price=D(self.quotes[name][day]['reference']), currency=Currency.CNH,
                          country=self.instruments[name].country)
                         for name, symbol in self.symbols_by_name.items() if self.portfolio[symbol].quantity]
            cash = [CashBalance(currency=Currency.CNH, amount=money(self.portfolio.cash))]
            proposal = RebalanceProposalBuilder().build(as_of=self.time.date(), intended_trade_date=self.time.date(),
                sleeve='lean-research', positions=positions, cash=cash, instruments=self.instruments,
                prices={s: D(q[day]['reference']) for s, q in self.quotes.items()}, fx_to_cnh={}, targets=targets)
            orders = sorted(proposal.orders, key=lambda o: o.side.value != 'sell')
            scale = None
            for order in orders:
                if order.side.value == 'buy' and scale is None:
                    prices = {s: money(D(q[day]['open']) * (1 + D(self.spec.slippage_bps) / 10000)) for s, q in self.quotes.items()}
                    scale = DailyBacktestEngine()._buy_affordability_scale(orders=orders,
                        ledger=CashLedger([CashBalance(currency=Currency.CNH, amount=money(self.portfolio.cash))]),
                        converter=FxConverter({}), execution_prices=prices,
                        transaction_cost_rate=D(self.spec.transaction_cost_bps) / 10000)
                quantity = int(order.quantity * scale) if order.side.value == 'buy' else -order.quantity
                if quantity:
                    ticket = self.market_order(self.symbols_by_name[order.symbol], quantity)
                    if ticket.status != OrderStatus.FILLED:  # noqa: F405
                        raise ValueError(f'Unfilled research order: {ticket.status}')
        elif phase == 2:
            self.nav_rows.append({'date': day, 'nav': str(money(self.portfolio.total_portfolio_value)),
                                  'cash': str(money(self.portfolio.cash))})

    def on_order_event(self, event):
        if event.status == OrderStatus.FILLED:  # noqa: F405
            name = next(name for name, symbol in self.symbols_by_name.items() if symbol == event.symbol)
            self.fills.append({'date': self.time.date().isoformat(), 'symbol': name,
                              'quantity': int(event.fill_quantity), 'price': str(money(event.fill_price)),
                              'fee': str(money(event.order_fee.value.amount))})

    def on_end_of_algorithm(self):
        if [r['date'] for r in self.nav_rows] != self.sessions or set(self.decisions) != set(self.expected_decisions):
            raise ValueError('Partial LEAN output; missing session/decision')
        write_json(Path('/output/resources.json'), dict(process_resources(),
                   input_events=len(self.processed) * len(self.symbols_by_name), order_events=len(self.fills)))
        write_json(Path('/output/economic.json'), {'schema_version': 1, 'engine': 'lean', 'complete': True,
            'nav': self.nav_rows, 'fills': self.fills, 'decisions': self.decisions,
            'final_positions': {name: int(self.portfolio[s].quantity) for name, s in self.symbols_by_name.items() if self.portfolio[s].quantity}})
