"""Durable IB small-bar acquisition. Completion is not research certification."""
from __future__ import annotations

import calendar
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from systematic_trading.live.trading_calendar import us_equity_market_close
from systematic_trading.recorders.market_data import IBMarketDataMode
from systematic_trading.runtime_io import atomic_json


EXCHANGE_ZONE = ZoneInfo("America/New_York")


def retention_floor(now: datetime) -> datetime:
    """IB documents six calendar months for bars <=30 seconds."""
    now = now.astimezone(UTC)
    month = now.year * 12 + now.month - 1 - 6
    year, month = divmod(month, 12)
    month += 1
    return now.replace(year=year, month=month, day=min(now.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class RecoveryWindow:
    symbol: str
    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        return f"{self.symbol}/{self.start.isoformat()}/{self.end.isoformat()}"

    @property
    def expected_slots(self) -> int:
        return int((self.end - self.start).total_seconds()) // 5


def recovery_windows(symbols: list[str], start: date, now: datetime) -> list[RecoveryWindow]:
    """Fixed, nonoverlapping RTH hours; allow delayed HMDS data to settle."""
    cutoff = now.astimezone(UTC) - timedelta(minutes=20)
    day = start
    windows = []
    while day <= cutoff.astimezone(EXCHANGE_ZONE).date():
        close_time = us_equity_market_close(day)
        if close_time:
            cursor = datetime.combine(day, time(9, 30), EXCHANGE_ZONE).astimezone(UTC)
            close = datetime.combine(day, close_time, EXCHANGE_ZONE).astimezone(UTC)
            while cursor < close:
                end = min(cursor + timedelta(hours=1), close)
                if end <= cutoff:
                    windows.extend(RecoveryWindow(symbol, cursor, end) for symbol in symbols)
                cursor = end
        day += timedelta(days=1)
    return windows


class RecoveryLedger:
    """Single writer, protected by the worker's crash-released OS lock.

    Persist a request claim before IB access, and receipt before advancing.
    After a crash, replay the uncommitted window through deterministic raw IDs.
    Existing stream bars do not prove that an interval was fully acquired.
    """

    def __init__(self, path: Path, *, identity: dict, start_date: date | None = None,
                 spacing_seconds: float = 30):
        if spacing_seconds < 20:
            raise ValueError("Recovery spacing must be at least 20 seconds")
        self.path = path
        self.spacing_seconds = spacing_seconds
        self.start_date = start_date
        self.identity = identity
        self.data = json.loads(path.read_text(encoding="utf8")) if path.exists() else {
            "schema_version": 1, "identity": identity, "windows": {}, "sequence": 0,
            "next_request_at": None, "symbol_retry_at": {},
        }
        if self.data.get("schema_version") != 1 or self.data.get("identity") != identity:
            raise ValueError("Recovery checkpoint identity/schema mismatch; retain it and use a separate checkpoint")
        if not isinstance(self.data.get("windows"), dict):
            raise ValueError("Invalid recovery checkpoint")

    def save(self) -> None:
        atomic_json(self.path, self.data)

    def plan(self, symbols: list[str], now: datetime) -> list[RecoveryWindow]:
        if "start_date" not in self.data:
            self.data["start_date"] = (self.start_date or retention_floor(now).astimezone(EXCHANGE_ZONE).date()).isoformat()
        start = date.fromisoformat(self.data["start_date"])
        if self.start_date and self.start_date < start:
            start = self.start_date
            self.data["start_date"] = start.isoformat()
        windows = recovery_windows(symbols, start, now)
        floor = retention_floor(now)
        for window in windows:
            entry = self.data["windows"].get(window.key, {})
            if window.start < floor and entry.get("status") not in {"complete", "expired"}:
                self.data["windows"][window.key] = dict(entry, status="expired",
                    reason="Outside IB six-month small-bar retention; observations remain missing")
        return windows

    def next_window(self, symbols: list[str], now: datetime) -> RecoveryWindow | None:
        windows = self.plan(symbols, now)
        if self.data["next_request_at"] and now < datetime.fromisoformat(self.data["next_request_at"]):
            return None
        eligible = []
        for window in windows:
            entry = self.data["windows"].get(window.key, {})
            if entry.get("status") in {"complete", "expired"}:
                continue
            retry = entry.get("retry_at")
            symbol_retry = self.data["symbol_retry_at"].get(window.symbol)
            if any(value and now < datetime.fromisoformat(value) for value in (retry, symbol_retry)):
                continue
            eligible.append(window)
        if not eligible:
            return None
        # Alternate latest recovery and oldest still-retrievable history so a
        # bootstrap does not starve new outages or lose expiring observations.
        ordered = sorted(eligible, key=lambda w: (w.start, w.symbol))
        return ordered[-1] if self.data["sequence"] % 2 == 0 else ordered[0]

    def step(self, symbols: list[str], now: datetime, fetch: Callable,
             clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict:
        window = self.next_window(symbols, now)
        if window is None:
            self.save()
            return self.summary(symbols, now)
        previous = self.data["windows"].get(window.key, {})
        attempts = int(previous.get("attempts", 0)) + 1
        self.data["next_request_at"] = (now + timedelta(seconds=self.spacing_seconds)).isoformat()
        self.data["sequence"] += 1
        self.data["windows"][window.key] = dict(previous, status="in_progress", attempts=attempts,
            started_at=now.isoformat())
        self.save()
        try:
            result = fetch(window)
        except Exception as exc:
            result = {"completed": False, "slots": 0, "errors": [f"{type(exc).__name__}: {exc}"]}
        finished = clock()
        slots = int(result.get("slots", 0))
        complete = result.get("completed") is True and slots == window.expected_slots
        source_partial = result.get("completed") is True and 0 < slots < window.expected_slots
        delay = 86400 if source_partial else min(300, 60 * 2 ** min(attempts, 3))
        errors = result.get("errors", [])
        if any(f":{code}:" in str(error) for error in errors for code in (354, 10089, 10090, 10186)):
            delay = 3600
        if any("pacing" in str(error).lower() for error in errors):
            delay = max(delay, 600)
            self.data["next_request_at"] = (finished + timedelta(seconds=600)).isoformat()
        status = "complete" if complete else "source_partial" if source_partial else "retry"
        receipt = dict(result, window=window.key, status=status, attempts=attempts,
            expected_slots=window.expected_slots, missing_slots=max(0, window.expected_slots-slots),
            completed_at=finished.isoformat(), retry_at=None if complete else (finished+timedelta(seconds=delay)).isoformat())
        # Retain previous attempts, including warnings, timeouts and partial
        # writes. No failed attempt is upgraded merely because time advanced.
        with self.path.with_suffix(".attempts.jsonl").open("a", encoding="utf8") as stream:
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.data["windows"][window.key] = receipt
        if not complete and not source_partial:
            self.data["symbol_retry_at"][window.symbol] = receipt["retry_at"]
        else:
            self.data["symbol_retry_at"].pop(window.symbol, None)
        self.data["last_result"] = receipt
        self.save()
        return self.summary(symbols, finished)

    def summary(self, symbols: list[str], now: datetime) -> dict:
        windows = self.plan(symbols, now)
        counts = Counter(self.data["windows"].get(w.key, {}).get("status", "pending") for w in windows)
        return {
            "checkpoint_path": str(self.path), "start_date": self.data["start_date"],
            "retention_floor": retention_floor(now).isoformat(), "bar_size_seconds": 5,
            "symbols": symbols, "windows_total": len(windows), "windows_by_status": dict(counts),
            "pending_windows": sum(counts[s] for s in ("pending", "retry", "in_progress", "source_partial")),
            "recovered_slots": sum(self.data["windows"].get(w.key, {}).get("slots", 0) for w in windows),
            "next_request_at": self.data["next_request_at"], "last_result": self.data.get("last_result"),
            "research_approved": False,
        }


class WindowRecorder:
    """Validate timestamps/coverage while preserving the normal raw-first path."""

    def __init__(self, recorder, window: RecoveryWindow, *, event_batch=None):
        self.recorder = recorder
        self.window = window
        self.slots: set[datetime] = set()
        self.event_batch = event_batch

    def __getattr__(self, name):
        return getattr(self.recorder, name)

    def record_bar(self, bar):
        timestamp = bar.exchange_timestamp
        if (bar.symbol != self.window.symbol or timestamp is None
                or not self.window.start <= timestamp < self.window.end
                or timestamp.microsecond or int(timestamp.timestamp()) % 5 or bar.bar_size_seconds != 5):
            raise ValueError("IB returned a bar outside the requested symbol/window/5-second grid")
        flags = [*bar.quality_flags, "ib_historical_recovery", "ib_historical_filtered_trades"]
        bar = bar.model_copy(update={"market_data_mode": IBMarketDataMode.UNKNOWN, "quality_flags": flags})
        event = self.recorder.record_bar(bar)
        if self.event_batch is not None:
            self.event_batch.append_platform_event(event)
        self.slots.add(timestamp)
        return event


class RecoveryEventBatch:
    """Stage at most one acquisition window; raw/catalog are already durable.

    The caller must flush before committing coverage. A crash before flush
    leaves the window pending and deterministic event IDs make replay safe.
    """

    def __init__(self, store):
        self.store = store
        self.events = []

    def append_platform_event(self, event):
        if len(self.events) >= 720:
            raise ValueError("Historical recovery batch exceeds one hour")
        self.events.append(event)

    def flush(self):
        bulk = getattr(self.store, "append_platform_events", None)
        if bulk is not None:
            bulk(self.events)
        else:
            for event in self.events:
                self.store.append_platform_event(event)
        self.events.clear()
