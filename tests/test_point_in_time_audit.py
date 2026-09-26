from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from systematic_trading.daily_quality import completed_session, captured_before_close
from systematic_trading.domain.market import PriceBar
from systematic_trading.market_data.golden import daily_bar_row
from systematic_trading.signals.base import SignalContext
from systematic_trading.backtest.stored import _open_prices_by_date, _latest_rate


def bar(day, close='100'):
    return PriceBar(trade_date=day, open=close, high=close, low=close, close=close, volume=100)


def test_signal_context_cannot_access_execution_day_or_future():
    days = [date(2026, 9, n) for n in (23, 24, 25)]
    context = SignalContext(as_of=days[1], instruments={},
                            bars_by_symbol={'SPY': [bar(d) for d in days]}, trade_dates=days)
    assert [b.trade_date for b in context.bars_by_symbol['SPY']] == days[:1]
    assert list(context.trade_dates) == days[:1]


def test_missing_session_cannot_fill_at_prior_close_and_fx_has_age_limit():
    first, second = date(2026, 9, 23), date(2026, 9, 24)
    prices = _open_prices_by_date({'SPY': [bar(first)]}, [first, second])
    assert 'SPY' not in prices[second]
    with pytest.raises(ValueError, match='Stale'):
        _latest_rate({first: Decimal('7')}, date(2026, 10, 5))


def test_completed_daily_bars_observe_dst_early_close_and_closures():
    assert not completed_session(date(2026, 9, 25), datetime(2026, 9, 25, 18, tzinfo=UTC))
    assert completed_session(date(2026, 9, 25), datetime(2026, 9, 25, 20, 20, tzinfo=UTC))
    assert not completed_session(date(2026, 11, 27), datetime(2026, 11, 27, 18, 19, tzinfo=UTC))
    assert completed_session(date(2026, 11, 27), datetime(2026, 11, 27, 18, 20, tzinfo=UTC))
    assert not completed_session(date(2012, 10, 29))
    assert not completed_session(date(2025, 1, 9))
    assert captured_before_close({'trade_date': '2026-09-25', 'ingested_at': '2026-09-25 13:32:00'})


def test_import_time_does_not_claim_historical_availability():
    captured = datetime(2026, 9, 25, 21, tzinfo=UTC)
    row = daily_bar_row(symbol='SPY', bar=bar(date(2012, 1, 3)), source_name='legacy', ingested_at=captured)
    assert row['available_at'] == '2026-09-25T21:00:00.000Z'
    assert 'availability_unverified' in row['quality_flags']


def test_next_open_funding_cannot_use_future_close_fx():
    from systematic_trading.backtest.engine import DailyBacktestEngine
    from systematic_trading.domain.enums import Currency
    from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
    from systematic_trading.research import MULTI_ASSET_ETF_UNIVERSE
    first, second = date(2026, 9, 23), date(2026, 9, 24)
    result = DailyBacktestEngine().run(
        trade_dates=[first, second], instruments={'SPY': MULTI_ASSET_ETF_UNIVERSE['SPY']},
        initial_cash=[CashBalance(currency=Currency.CNH, amount=700)],
        daily_prices={d: {'SPY': Decimal('100')} for d in [first, second]},
        daily_fx_to_cnh={first: {'USD': '7'}, second: {'USD': '14'}},
        daily_execution_fx_to_cnh={second: {'USD': '7'}},
        decision_dates_by_trade_date={second: first},
        target_schedule={second: [AllocationTarget(symbol='SPY', target_weight=1, sleeve='test', rationale='test')]},
    )
    assert result.final_snapshot.positions[0].quantity == 1
    assert result.final_snapshot.nav_cnh == Decimal('1400')


def test_fiscal_period_end_is_not_a_publication_date():
    from systematic_trading.domain.market import FundamentalSnapshot
    with pytest.raises(ValueError):
        FundamentalSnapshot(symbol='AAPL', period_end=date(2025, 12, 31))


def test_training_label_cannot_end_on_first_holdout_day():
    from systematic_trading.signals.decision_tree import build_forward_return_samples
    first, split = date(2025, 12, 1), date(2026, 1, 2)
    assert build_forward_return_samples(symbols=['SPY', 'GLD'],
        bars_by_symbol={s: [bar(first), bar(split, '110')] for s in ['SPY', 'GLD']},
        trade_dates=[first, split], rebalance_dates=[first, split], split_date=split) == []


def test_missing_entire_opening_price_day_does_not_fall_back_to_close():
    from systematic_trading.backtest.engine import DailyBacktestEngine
    from systematic_trading.domain.enums import Currency
    from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
    from systematic_trading.research import MULTI_ASSET_ETF_UNIVERSE
    day = date(2026, 9, 24)
    with pytest.raises(ValueError, match='Missing execution prices'):
        DailyBacktestEngine().run(trade_dates=[day], instruments={'SPY': MULTI_ASSET_ETF_UNIVERSE['SPY']},
            initial_cash=[CashBalance(currency=Currency.CNH, amount=700)],
            daily_prices={day: {'SPY': Decimal('100')}}, daily_fx_to_cnh={day: {'USD': '7'}},
            daily_execution_prices={}, target_schedule={day: [AllocationTarget(
                symbol='SPY', target_weight=1, sleeve='test', rationale='test')]})


def test_common_calendar_does_not_silently_drop_missing_interior_quotes():
    from systematic_trading.backtest.stored import _common_price_dates
    days = [date(2026, 9, n) for n in (23, 24, 25)]
    with pytest.raises(ValueError, match='silently drop'):
        _common_price_dates({'SPY': [bar(d) for d in days], 'GLD': [bar(days[0]), bar(days[-1])]})


def test_held_position_requires_a_current_valuation_even_without_rebalance():
    from systematic_trading.backtest.engine import DailyBacktestEngine
    from systematic_trading.domain.enums import Currency
    from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
    from systematic_trading.research import MULTI_ASSET_ETF_UNIVERSE
    first, second = date(2026, 9, 23), date(2026, 9, 24)
    with pytest.raises(ValueError, match='Missing valuation price for held SPY'):
        DailyBacktestEngine().run(trade_dates=[first, second], instruments={'SPY': MULTI_ASSET_ETF_UNIVERSE['SPY']},
            initial_cash=[CashBalance(currency=Currency.CNH, amount=700)],
            daily_prices={first: {'SPY': Decimal('100')}, second: {}},
            daily_fx_to_cnh={d: {'USD': '7'} for d in [first, second]},
            target_schedule={first: [AllocationTarget(symbol='SPY', target_weight=1, sleeve='test', rationale='test')]})
