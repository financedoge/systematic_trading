"""Completed US-equity sessions and provider OHLC integrity."""
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo



@lru_cache(maxsize=8192)
def session_available_at(day: date) -> datetime | None:
    from systematic_trading.live.trading_calendar import us_equity_market_close
    close = us_equity_market_close(day)
    return datetime.combine(day, close, ZoneInfo('America/New_York')).astimezone(UTC) + timedelta(minutes=20) if close else None


def completed_session(day: date, now: datetime | None = None) -> bool:
    available = session_available_at(day)
    return available is not None and available <= (now or datetime.now(UTC))


def valid_ohlc(bar) -> bool:
    return bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high


def captured_before_close(row: dict) -> bool:
    """Legacy ingestion during a session cannot establish a completed daily bar."""
    if not row.get('ingested_at'):
        return False
    available = session_available_at(date.fromisoformat(str(row['trade_date'])))
    captured = datetime.fromisoformat(str(row['ingested_at']).replace('Z', '+00:00'))
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    return available is not None and captured < available
