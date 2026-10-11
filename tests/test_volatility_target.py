from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.volatility_target import VolatilityTargetOverlay


def fixture(vol=.02):
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(65)]
    closes = 100 * np.cumprod([1] + [1 + vol * (-1)**i for i in range(64)])
    bars = [PriceBar(symbol='SPY', trade_date=d, currency='USD', open=str(p), high=str(p),
                    low=str(p), close=str(p), volume=100) for d, p in zip(days, closes)]
    context = SignalContext(as_of=days[-1], instruments={}, bars_by_symbol={'SPY': bars}, trade_dates=days)
    target = AllocationTarget(symbol='SPY', target_weight=Decimal('.8'), sleeve='test', rationale='base')
    return [target], context, bars


def test_no_leverage_and_cash_is_preserved():
    targets, context, _ = fixture(.001)
    overlay = VolatilityTargetOverlay()
    assert overlay.scale(targets, context)[0] == 1
    assert overlay.apply(targets, context)[0].target_weight == targets[0].target_weight
    empty = [targets[0].model_copy(update={'target_weight': Decimal(0)})]
    assert overlay.scale(empty, context) == (1, 0)


def test_portfolio_volatility_includes_existing_cash_and_reaches_declared_target():
    targets, context, _ = fixture()
    overlay = VolatilityTargetOverlay()
    scale, vol = overlay.scale(targets, context)
    assert vol == pytest.approx(np.std([.8 * .02 * (-1)**i for i in range(63)], ddof=1) * np.sqrt(252))
    assert scale * vol == pytest.approx(.1)
    assert overlay.apply(targets, context)[0].target_weight < Decimal('.8')


def test_execution_day_and_future_price_cannot_affect_scale():
    targets, context, bars = fixture()
    bars[-1] = bars[-1].model_copy(update={'close': Decimal('1000000')})
    poisoned = SignalContext(as_of=context.as_of, instruments={}, bars_by_symbol={'SPY': bars},
                             trade_dates=[b.trade_date for b in bars])
    assert VolatilityTargetOverlay().scale(targets, context) == VolatilityTargetOverlay().scale(targets, poisoned)


def test_missing_session_fails_instead_of_shortening_window():
    targets, context, _ = fixture()
    missing = SignalContext(as_of=context.as_of, instruments={}, trade_dates=context.trade_dates,
                            bars_by_symbol={'SPY': context.bars_by_symbol['SPY'][:-1]})
    with pytest.raises(ValueError, match='Missing'):
        VolatilityTargetOverlay().apply(targets, missing)
