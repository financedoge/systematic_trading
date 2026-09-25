from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderSide, OrderType
from systematic_trading.execution.twap_benchmark import TwapBenchmarkService, benchmark_window, calculate_twap
from test_execution_history import store

START = datetime(2026, 9, 25, 13, 35, tzinfo=UTC)
BARS = [{'at': (START + timedelta(minutes=i)).isoformat(), 'close': str(100+i)} for i in range(30)]


def record(store, side=OrderSide.BUY):
    r = store.list_broker_order_records()[0]
    return r.model_copy(update={'filled_quantity': 4, 'average_fill_price': Decimal('116'),
        'order': r.order.model_copy(update={'order_type': OrderType.TWAP, 'side': side,
            'intended_trade_date': START.date(), 'execution_start_time':'09:35', 'execution_end_time':'10:05'})})


def test_duration_weighted_observations_and_window(store):
    assert benchmark_window(record(store)) == (START, START+timedelta(minutes=30))
    assert calculate_twap(BARS, START, START+timedelta(minutes=30)) == (Decimal('114.5'), 30)
    # Partial first/last minutes are weighted by their duration.
    assert calculate_twap(BARS[:2], START+timedelta(seconds=30), START+timedelta(minutes=2)) == (Decimal('100.6666666666666666666666667'), 2)


@pytest.mark.parametrize('bars', [BARS[1:], BARS[:-1], BARS[:4]+BARS[5:],
    BARS+[{'at':START.isoformat(),'close':'999'}], BARS+[{'at':START.isoformat(),'close':'NaN'}],
    [{'at':START.replace(tzinfo=None).isoformat(),'close':'100'}]])
def test_incomplete_conflicting_or_invalid_evidence_is_not_a_benchmark(bars):
    with pytest.raises(ValueError):
        calculate_twap(bars, START, START+timedelta(minutes=30))


@pytest.mark.parametrize('side, expected', [(OrderSide.BUY, '6.0'), (OrderSide.SELL, '-6.0')])
def test_signed_slippage_uses_actual_fills_and_survives_restart(store, tmp_path, side, expected):
    class Provider:
        def fetch(self, *args):
            return BARS
    settings = AppSettings(data_dir=tmp_path)
    service = TwapBenchmarkService(settings, Provider())
    r = record(store, side)
    assert service.get(r, now=START)['status'] == 'waiting'
    assert service.get(r, now=START+timedelta(hours=1))['status'] == 'loading'
    service.pool.shutdown(wait=True)
    result = service.get(r, now=START+timedelta(hours=1))
    assert result['status'] == 'ready'
    assert result['price_cost'] == expected
    assert Decimal(result['slippage_bps']) == (Decimal(expected)/4/Decimal('114.5')*10000)
    assert result['coverage'] == '100%'
    restarted = TwapBenchmarkService(settings, Provider())
    assert restarted.get(r, now=START+timedelta(hours=1)) == result
    restarted.close()


def test_failed_provider_withholds_estimate_and_does_not_retry_immediately(store, tmp_path):
    class Provider:
        def fetch(self, *args):
            raise ValueError('No market data permission')
    service = TwapBenchmarkService(AppSettings(data_dir=tmp_path), Provider())
    r = record(store)
    service.get(r, now=START+timedelta(hours=1))
    service.pool.shutdown(wait=True)
    result = service.get(r, now=START+timedelta(hours=1))
    assert result['status'] == 'unavailable'
    assert 'twap_price' not in result
    assert result['average_fill_price'] == '116'
