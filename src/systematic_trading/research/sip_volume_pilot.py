"""Field-only SIP audit contract; never substitutes an active strategy input."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
import math
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")


def aware(value):
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None:
        raise ValueError("Availability and source timestamps must be timezone-aware")
    return instant


def activity_day(bar):
    local = aware(bar["t"]).astimezone(NY)
    if local.time() != time(0):
        raise ValueError("Daily bar must begin at New York midnight")
    return local.date().isoformat()


def audit_bars(bars, symbols, sessions):
    """Validate complete literal-symbol coverage without manufacturing any rows."""
    expected = {(s, d) for s in symbols for d in sessions}
    indexed, last = {}, {}
    for bar in bars:
        symbol, day = bar["symbol"], activity_day(bar)
        key = symbol, day
        if key not in expected or key in indexed:
            raise ValueError("Unexpected or duplicate stock-day")
        if day <= last.get(symbol, ""):
            raise ValueError("Source dates are not strictly ordered")
        for field in ("o", "h", "l", "c", "v", "n"):
            value = bar[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Invalid numeric source value")
            if field in ("v", "n"):
                if value < 0 or value != int(value):
                    raise ValueError("Activity must be nonnegative integral shares/trades")
            elif value <= 0:
                raise ValueError("Nonpositive source price")
        if bar["h"] < max(bar["o"], bar["c"], bar["l"]) or bar["l"] > min(bar["o"], bar["c"]):
            raise ValueError("Inconsistent source OHLC")
        indexed[key] = bar
        last[symbol] = day
    if set(indexed) != expected:
        raise ValueError(f"Incomplete frozen window: {len(expected - set(indexed))} missing stock-days")
    return indexed


def audit_pair(bar, published, broker, lineage, identity, prior_audit, *, close_diagnostic=0.005):
    day = activity_day(bar)
    if (bar["symbol"], day) != (published["symbol"], published["trade_date"]) or broker["date"] != day:
        raise ValueError("Activity and comparison dates/identities differ")
    if identity["symbol"] != bar["symbol"]:
        raise ValueError("Frozen identity differs")
    raw_close = published["raw_close"]
    old_volume = published["raw_volume"]
    if any(v is None or not math.isfinite(v) or v <= 0 for v in (raw_close, old_volume)):
        raise ValueError("Missing supported comparison price or activity")
    start = datetime.combine(datetime.fromisoformat(day).date(), time(0), NY)
    end = datetime.combine(start.date() + timedelta(days=1), time(0), NY)
    captured = aware(lineage["captured_at"])
    if captured < end:
        raise ValueError("Source capture precedes completed reporting day")
    close_delta = float(Decimal(str(bar["c"])) - Decimal(str(raw_close)))
    volume_delta = float(Decimal(str(bar["v"])) - Decimal(str(old_volume)))
    flags = ["historical_identity_uncertified", "historical_vintage_uncertified",
             "correction_timing_unknown", "full_day_not_same_close_available"]
    if prior_audit["status"] != "audited_with_limitations":
        flags.append("prior_series_review_retained")
    if abs(close_delta) > close_diagnostic:
        flags.append("close_difference_requires_review")
    if published["split_multiplier"] != 1:
        flags.append("split_basis_requires_review")
    if not bar["v"] or not bar["n"]:
        flags.append("zero_activity_requires_review")
    return dict(symbol=bar["symbol"], activity_date=day,
                sip_raw_volume=int(bar["v"]), source_daily_close=bar["c"],
                paired_published_raw_close=raw_close, published_raw_volume=old_volume,
                published_split_multiplier=published["split_multiplier"],
                raw_close_times_sip_volume=raw_close * bar["v"],
                volume_delta_shares=volume_delta, volume_delta_percent=100 * volume_delta / old_volume,
                close_delta_usd=close_delta,
                ibkr_rth_close=broker["broker_trade_close"],
                close_delta_vs_ibkr_usd=float(Decimal(str(bar["c"])) - Decimal(str(broker["broker_trade_close"]))),
                session_start=start.isoformat(), session_end_exclusive=end.isoformat(),
                historical_published_at=None, first_captured_at=captured.isoformat(),
                historical_strategy_eligible=False, identity=identity, flags=flags,
                source=lineage, published_price_source_id=published["source_id"],
                published_price_source_hash=published["source_hash"])


def eligible_at(row, cutoff, pilot_published_at):
    """Fail closed: capture time or a one-day lag never certifies an old vintage."""
    if not row.get("historical_strategy_eligible") or row.get("flags"):
        return False
    try:
        end, original, captured, audited, decision = map(aware, (
            row["session_end_exclusive"], row["historical_published_at"],
            row["first_captured_at"], pilot_published_at, cutoff))
    except (KeyError, TypeError, ValueError):
        return False
    return end <= original <= captured <= audited <= decision
