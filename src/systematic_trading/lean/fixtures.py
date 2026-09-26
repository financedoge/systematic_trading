"""Deterministic synthetic engineering data; never enters the market-data store."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.research import current_sota_definition, instruments_for_definition


def make_fixture_bundle(root: Path, *, mode='targets', cost_bps='5', slippage_bps='0', delay=0):
    bars = {s: [] for s in instruments_for_definition(current_sota_definition())}
    fx = {}
    day, end = date(2023, 1, 3), date(2025, 1, 15)
    index = 0
    while day <= end:
        if is_us_trading_day(day):
            index += 1
            fx[day.isoformat()] = str(Decimal('7') + Decimal(index % 25) / 100)
            for j, rows in enumerate(bars.values()):
                price = Decimal(100 + j) + Decimal(index * (j + 1)) / 100 + Decimal(index % 11) / 10
                rows.append(dict(trade_date=str(day), open=str(price - Decimal('0.1')),
                                 high=str(price + 1), low=str(price - 1), close=str(price), volume=100000 + index * 13))
        day += timedelta(days=1)
    return freeze_bundle(root=root, bars=bars, fx=fx, provenance={'source': 'deterministic synthetic fixture',
        'license': 'repository test data', 'availability': 'US completed-session time; generated fixture, not market observations'},
        spec_values=dict(start_date='2024-10-31', end_date='2025-01-15', warmup_start='2023-01-03',
                         mode=mode, certification='synthetic_fixture', transaction_cost_bps=cost_bps,
                         slippage_bps=slippage_bps, execution_delay_sessions=delay))
