"""Shared target computation for the reference and LEAN, using only prior bars."""
from datetime import date
from decimal import Decimal

from systematic_trading.backtest.stored import _target_schedule
from systematic_trading.domain.market import PriceBar
from systematic_trading.research import current_sota_definition, instruments_for_definition, instantiate_overlays


def targets_for_day(rows: dict, day: date, *, benchmark: bool = False, lookback_bars: int = 63):
    definition = current_sota_definition()
    instruments = instruments_for_definition(definition)
    histories = {
        symbol: [PriceBar.model_validate(row) for row in values if date.fromisoformat(row['trade_date']) < day]
        for symbol, values in rows.items()
    }
    if min(len(bars) for bars in histories.values()) < 253:
        raise ValueError(f'Insufficient warmup before {day}; 253 prior observations required')
    return _target_schedule(
        instruments=instruments, bars_by_symbol=histories, trade_dates=[day],
        rebalance_frequency='daily', lookback_bars=lookback_bars, max_weight=Decimal('0.45'),
        cash_reserve_weight=Decimal('0.02'), sleeve_name=definition.sleeve_name,
        target_overlays=() if benchmark else instantiate_overlays(definition),
    )[day]
