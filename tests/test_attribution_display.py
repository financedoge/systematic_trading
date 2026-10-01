"""Daily attribution remains useful before the next session's marks exist."""
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from systematic_trading.domain import FXRate, PriceBar
from systematic_trading.live.management_service import scheduled_rebalance_dates
from systematic_trading.live.pnl import build_dashboard_pnl_snapshot, build_reference_pnl_snapshot
from systematic_trading.live.trading_calendar import latest_completed_us_session
from systematic_trading.web.api import dashboard_execution_quality, dashboard_pnl
from test_execution_history import store, fill, sync  # noqa: F401


@pytest.mark.parametrize("timestamp,expected", [
    ("2026-09-28T13:26:00+00:00", "2026-09-25"),
    ("2026-09-28T19:59:59+00:00", "2026-09-25"),
    ("2026-09-28T20:00:00+00:00", "2026-09-28"),
    ("2026-09-27T18:00:00+00:00", "2026-09-25"),
    ("2026-11-27T17:59:59+00:00", "2026-11-25"),
    ("2026-11-27T18:00:00+00:00", "2026-11-27"),
    ("2026-12-25T19:00:00+00:00", "2026-12-24"),
])
def test_completed_session_obeys_close_weekends_holidays_and_early_close(timestamp, expected):
    assert latest_completed_us_session(datetime.fromisoformat(timestamp)) == date.fromisoformat(expected)


@pytest.mark.parametrize("today,decision,trade", [
    ("2026-09-28", "2026-09-30", "2026-10-01"),
    ("2026-09-30", "2026-09-30", "2026-10-01"),
    ("2026-10-01", "2026-09-30", "2026-10-01"),
    ("2026-10-02", "2026-10-30", "2026-11-02"),
])
def test_visible_schedule_includes_current_execution_day(today, decision, trade):
    assert scheduled_rebalance_dates(date.fromisoformat(today)) == (date.fromisoformat(decision), date.fromisoformat(trade))


def test_default_daily_attribution_uses_completed_session_but_explicit_missing_date_stays_unavailable(store, monkeypatch):
    from systematic_trading.live import trading_calendar
    day = date(2026, 8, 3)
    store.upsert_price_bar("SPY", PriceBar(trade_date=day, open=120, high=120, low=120, close=120, volume=100))
    store.upsert_fx_rate(FXRate(base_currency="USD", rate_date=day, rate=7))
    sync(store, [fill(quantity=10, price="101")])
    saved = build_dashboard_pnl_snapshot(store, as_of=day)
    saved.reference_total_pnl_cnh = build_reference_pnl_snapshot(store, as_of=day).total_pnl_cnh
    store.save_pnl_snapshot(saved)
    # Incomplete legacy snapshots must not become a fallback point.
    store.save_pnl_snapshot(saved.model_copy(update=dict(snapshot_id="incomplete", valuation_complete=False,
        as_of=datetime(2026, 8, 4, 22, tzinfo=UTC))))
    monkeypatch.setattr(trading_calendar, "latest_completed_us_session", lambda: day)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))
    result = dashboard_execution_quality(request, as_of=None, history_limit=10)
    assert result.valuation_complete and result.as_of.date() == day
    assert result.actual_pnl_cnh == Decimal(1330)
    assert result.theoretical_pnl_cnh == Decimal(1400)
    assert result.execution_gain_cnh == Decimal(-70)
    assert dashboard_pnl(request, as_of=None).as_of.date() == day
    missing = dashboard_execution_quality(request, as_of=date(2026, 8, 4), history_limit=10)
    assert not missing.valuation_complete
    assert missing.actual_pnl_cnh is missing.theoretical_pnl_cnh is missing.execution_gain_cnh is None
    assert missing.execution_gain_bps is missing.execution_reconciliation_difference_cnh is None
    assert len(missing.history) == len(missing.rows) == len(missing.slippage) == 1
    assert missing.history[0].actual_pnl_cnh == Decimal(1330)
    assert missing.slippage[0].daily_slippage_cnh == Decimal(-70)
    assert not dashboard_pnl(request, as_of=date(2026, 8, 4)).valuation_complete
