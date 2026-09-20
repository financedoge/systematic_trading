import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("day", [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-12-24",
])
def test_recorder_idles_on_exchange_holidays(day) -> None:
    state = market_session_state(datetime.fromisoformat(f"{day}T15:00:00+00:00"))
    assert not state.is_open
    assert state.is_weekday
    assert state.reason == "market_holiday"
    assert state.seconds_until_open == state.seconds_until_close == 0


@pytest.mark.parametrize("close", [
    "2026-11-27T18:00:00+00:00", "2026-12-24T18:00:00+00:00",
    "2028-07-03T17:00:00+00:00",
])
def test_recorder_stops_at_scheduled_early_close(close) -> None:
    end = datetime.fromisoformat(close)
    before = market_session_state(end - timedelta(seconds=1))
    at_close = market_session_state(end)
    assert before.is_open
    assert before.seconds_until_close == 1
    assert before.market_close.hour == 13
    assert not at_close.is_open
    assert at_close.reason == "after_market_close"


@pytest.mark.parametrize("day", ["2026-07-02", "2027-07-02", "2027-12-31"])
def test_sessions_adjacent_to_observed_holidays_keep_regular_close(day) -> None:
    state = market_session_state(datetime.fromisoformat(f"{day}T19:00:00+00:00"))
    assert state.is_open
    assert state.market_close.hour == 16


@pytest.mark.parametrize("day,open_hour", [("2026-03-06", 14), ("2026-03-09", 13), ("2026-11-02", 14)])
def test_session_open_tracks_new_york_daylight_saving(day, open_hour) -> None:
    opening = datetime.fromisoformat(f"{day}T{open_hour}:30:00+00:00")
    assert not market_session_state(opening - timedelta(seconds=1)).is_open
    assert market_session_state(opening).is_open


def test_custom_window_can_narrow_but_not_extend_core_session() -> None:
    now = datetime(2026, 11, 27, 18, tzinfo=UTC)
    late = market_session_state(now, market_open="04:00", market_close="20:00")
    narrow = market_session_state(now - timedelta(hours=1), market_close="12:00")
    empty = market_session_state(now, market_open="14:00", market_close="16:00")
    assert not late.is_open
    assert late.market_open.hour == 9
    assert late.market_close.hour == 13
    assert not narrow.is_open
    assert narrow.market_close.hour == 12
    assert not empty.is_open
    assert empty.reason == "outside_regular_session"


def test_configured_timezone_cannot_shift_exchange_date_or_early_close() -> None:
    state = market_session_state(
        datetime(2026, 11, 27, 17, 59, tzinfo=UTC),
        timezone="America/Los_Angeles", market_open="06:30", market_close="13:00",
    )
    assert state.is_open
    assert state.market_close.hour == 10
    assert state.seconds_until_close == 60
    holiday = market_session_state(datetime(2026, 1, 2, 0, tzinfo=UTC), timezone="UTC")
    assert holiday.session_date == "2026-01-01"
    assert holiday.reason == "market_holiday"


@pytest.mark.parametrize("start,backfill_seconds,expected_duration", [
    ("2026-11-27T17:59:50+00:00", 20, None),
    ("2026-11-27T14:29:50+00:00", 20, 300),
    ("2026-11-27T17:59:50+00:00", 5, 5),
    ("2026-11-27T17:59:59.750000+00:00", 0, 0.25),
])
def test_service_rechecks_session_after_daily_backfill(monkeypatch, tmp_path, start, backfill_seconds, expected_duration) -> None:
    service, clock, args, states = _service_harness(monkeypatch, tmp_path, start)
    captures = []

    def backfill(**kwargs):
        clock.value += timedelta(seconds=backfill_seconds)
        return {"returncode": 0}

    def capture(**kwargs):
        captures.append(kwargs["duration_seconds"])
        raise KeyboardInterrupt

    monkeypatch.setattr(service, "_run_daily_backfill_child", backfill)
    monkeypatch.setattr(service, "_run_child", capture)
    monkeypatch.setattr(service.time, "sleep", _interrupt)
    assert service.main(args) == 130
    assert captures == ([] if expected_duration is None else [expected_duration])
    if expected_duration is None:
        idle = [state for state in states if state["mode"] == "idle"]
        assert idle[-1]["session"].reason == "after_market_close"


@pytest.mark.parametrize("recovery_seconds,expected_durations", [(40, [30]), (25, [30, 5])])
def test_service_rechecks_session_after_gap_recovery(monkeypatch, tmp_path, recovery_seconds, expected_durations) -> None:
    service, clock, args, states = _service_harness(monkeypatch, tmp_path, "2026-11-27T17:59:30+00:00")
    captures = []
    recoveries = []

    def capture(**kwargs):
        if kwargs["mode"] == "historical-smoke":
            recoveries.append(kwargs)
            clock.value += timedelta(seconds=recovery_seconds)
            return {"returncode": 0}
        captures.append(kwargs["duration_seconds"])
        if len(captures) > 1:
            raise KeyboardInterrupt
        return {"returncode": 1}

    def sleep(seconds):
        if states[-1]["mode"] == "idle":
            raise KeyboardInterrupt

    monkeypatch.setattr(service, "_run_child", capture)
    monkeypatch.setattr(service.time, "sleep", sleep)
    assert service.main([*args, "--disable-daily-backfill"]) == 130
    assert captures == expected_durations
    assert len(recoveries) == 1


def _interrupt(*args):
    raise KeyboardInterrupt


def _service_harness(monkeypatch, tmp_path, start):
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_market_data_recorder_service.py"
    spec = importlib.util.spec_from_file_location("recorder_service_under_test", script)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)

    class Clock:
        value = datetime.fromisoformat(start)

        @classmethod
        def now(cls, tz=None):
            return cls.value.astimezone(tz)

    states = []

    def write_state(path, **kwargs):
        states.append(kwargs)
        assert len(states) < 20, "Service failed to idle or start the expected capture"

    monkeypatch.setattr(service, "datetime", Clock)
    monkeypatch.setattr(service, "_write_state", write_state)
    args = [
        "--state-path", str(tmp_path / "state.json"),
        "--pid-path", str(tmp_path / "service.pid"),
        "--operation-log", str(tmp_path / "operations.jsonl"),
        "--symbols", "SPY",
    ]
    return service, Clock, args, states
