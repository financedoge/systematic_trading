from datetime import UTC, datetime

from systematic_trading.recorders import ib_end_datetime, market_session_state


def test_market_session_state_is_open_during_regular_weekday_session() -> None:
    state = market_session_state(datetime(2026, 7, 13, 14, 0, tzinfo=UTC))

    assert state.is_open is True
    assert state.reason == "regular_session"
    assert state.session_date == "2026-07-13"
    assert state.seconds_until_close > 0


def test_market_session_state_idles_on_weekend_and_after_close() -> None:
    weekend = market_session_state(datetime(2026, 7, 11, 14, 0, tzinfo=UTC))
    after_close = market_session_state(datetime(2026, 7, 13, 21, 5, tzinfo=UTC))

    assert weekend.is_open is False
    assert weekend.reason == "weekend"
    assert after_close.is_open is False
    assert after_close.reason == "after_market_close"


def test_ib_end_datetime_formats_for_tws_historical_requests() -> None:
    assert ib_end_datetime(datetime(2026, 7, 10, 20, 0, tzinfo=UTC)) == "20260710 16:00:00 US/Eastern"
