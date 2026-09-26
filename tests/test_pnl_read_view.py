from collections import Counter
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from systematic_trading.domain import Currency, FXRate, PriceBar
from systematic_trading.live.pnl import PnlReadView, build_dashboard_pnl_snapshot, build_reference_pnl_snapshot
from test_execution_history import fill, store, sync  # noqa: F401


def test_sliced_fills_share_reads_but_new_calculations_refresh(store):
    sync(store, [fill(f'slice-{i}.01', 1, str(100 + i)) for i in range(10)])
    day = date(2026, 8, 3)
    store.upsert_fx_rate(FXRate(rate_date=day, base_currency=Currency.USD, rate=Decimal(7)))
    store.upsert_price_bar('SPY', PriceBar(trade_date=day, open=120, high=120, low=120, close=120, volume=100))
    counts = Counter()
    def count(name):
        original = getattr(store, name)
        def read(*args, **kwargs):
            counts[name] += 1
            return original(*args, **kwargs)
        return read
    view = PnlReadView(SimpleNamespace(**{name: count(name) for name in (
        'latest_pnl_baseline', 'list_broker_order_records', 'list_price_bars', 'list_fx_rates', 'list_pnl_snapshots'
    )}))
    actual = build_dashboard_pnl_snapshot(view, as_of=day)
    reference = build_reference_pnl_snapshot(view, as_of=day)
    assert actual.total_pnl_cnh == Decimal('1085')
    assert reference.total_pnl_cnh == Decimal('1400')
    assert counts == dict(latest_pnl_baseline=1, list_broker_order_records=1, list_price_bars=1, list_fx_rates=1)
    # Date bounds must remain part of the read key (no later marks in earlier history).
    assert view.list_fx_rates(Currency.USD, end_date=date(2026, 8, 2)) == []
    assert counts['list_fx_rates'] == 2
    store.upsert_price_bar('SPY', PriceBar(trade_date=day, open=130, high=130, low=130, close=130, volume=100))
    assert build_dashboard_pnl_snapshot(store, as_of=day).total_pnl_cnh == Decimal('1785')
