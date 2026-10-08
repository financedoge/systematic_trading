"""Keep completed US sessions in native replays, including same-day closes."""
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
import runpy
from zoneinfo import ZoneInfo


@lru_cache(maxsize=1)
def _calendar():
    # Use the same frozen pure calendar without importing live/__init__, whose
    # database/broker dependencies are deliberately absent from offline LEAN.
    return runpy.run_path(str(Path(__file__).resolve().parents[1]/'live/trading_calendar.py'))


def set_completed_end_date(algorithm, root, end, symbols, *, now=None):
    closing_time = _calendar()['us_equity_market_close'](end.date())
    if closing_time is None:
        raise ValueError(f'Native replay end {end.date()} is not a US market session.')
    close = datetime.combine(end.date(), closing_time, ZoneInfo('America/New_York'))
    if (now or datetime.now(UTC)) < close:
        raise ValueError(f'Native replay requires a completed US market session: {close.isoformat()}.')
    for symbol in symbols:
        final = (root / 'quotes' / (symbol+'.csv')).read_text().splitlines()[-1].split(',')
        if final[2] != 'close' or datetime.fromisoformat(final[0]) != close.replace(tzinfo=None):
            raise ValueError(f'Native replay final quote for {symbol} differs from requested close {close.isoformat()}.')
    # LEAN clamps to yesterday in the algorithm timezone. UTC+14 has already
    # advanced to tomorrow at every supported US close. Restore New York before
    # subscriptions; no signal, quote, fill or NAV timestamps change.
    algorithm.set_time_zone('Pacific/Kiritimati')
    try:
        algorithm.set_end_date(end)
    finally:
        algorithm.set_time_zone('America/New_York')
    if algorithm.end_date.date() != end.date():
        raise ValueError(f'Native replay truncated requested end {end.date()} to {algorithm.end_date.date()}.')
