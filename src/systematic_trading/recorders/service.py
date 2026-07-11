from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketSessionState:
    now: datetime
    session_date: str
    market_open: datetime
    market_close: datetime
    is_weekday: bool
    is_open: bool
    seconds_until_open: float
    seconds_until_close: float
    reason: str


def parse_hhmm(value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError(f"Expected HH:MM time, got {value!r}") from exc
    return time(hour=hour, minute=minute)


def market_session_state(
    now: datetime,
    *,
    timezone: str = "America/New_York",
    market_open: str = "09:30",
    market_close: str = "16:00",
) -> MarketSessionState:
    zone = ZoneInfo(timezone)
    local_now = _as_utc(now).astimezone(zone)
    open_time = parse_hhmm(market_open)
    close_time = parse_hhmm(market_close)
    session_open = datetime.combine(local_now.date(), open_time, tzinfo=zone)
    session_close = datetime.combine(local_now.date(), close_time, tzinfo=zone)
    if session_close <= session_open:
        raise ValueError("market_close must be after market_open")
    is_weekday = local_now.weekday() < 5
    if not is_weekday:
        reason = "weekend"
        is_open = False
    elif local_now < session_open:
        reason = "before_market_open"
        is_open = False
    elif local_now >= session_close:
        reason = "after_market_close"
        is_open = False
    else:
        reason = "regular_session"
        is_open = True
    return MarketSessionState(
        now=local_now,
        session_date=local_now.date().isoformat(),
        market_open=session_open,
        market_close=session_close,
        is_weekday=is_weekday,
        is_open=is_open,
        seconds_until_open=max((session_open - local_now).total_seconds(), 0.0),
        seconds_until_close=max((session_close - local_now).total_seconds(), 0.0),
        reason=reason,
    )


def ib_end_datetime(value: datetime, *, timezone: str = "America/New_York") -> str:
    local = _as_utc(value).astimezone(ZoneInfo(timezone))
    return local.strftime("%Y%m%d %H:%M:%S %Z").replace("EST", "US/Eastern").replace("EDT", "US/Eastern")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
