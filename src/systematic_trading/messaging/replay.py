from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Iterator

from pydantic import BaseModel, Field

from systematic_trading.domain.events import (
    AnyPlatformEvent,
    PlatformEventType,
    decode_platform_event,
)
from systematic_trading.storage.interfaces import PlatformEventOutboxReplayStore


class EventReplaySource(StrEnum):
    JSONL = "jsonl"
    OUTBOX = "outbox"


class EventReplayError(ValueError):
    pass


class ReplayedPlatformEvent(BaseModel):
    source: EventReplaySource
    subject: str
    event: AnyPlatformEvent
    published_at: datetime | None = None
    outbox_event_id: str | None = None
    publish_attempts: int | None = None
    last_error: str | None = None
    line_number: int | None = None


class EventReplaySummary(BaseModel):
    total: int = Field(ge=0)
    by_event_type: dict[str, int] = Field(default_factory=dict)
    by_subject: dict[str, int] = Field(default_factory=dict)


def iter_jsonl_platform_events(
    path: Path | str,
    *,
    event_type: PlatformEventType | None = None,
) -> Iterator[ReplayedPlatformEvent]:
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        return
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                event = decode_platform_event(payload["event"])
                subject = str(payload.get("subject") or event.subject)
                published_at = _datetime_from_iso(payload.get("published_at"))
            except Exception as exc:
                raise EventReplayError(f"{jsonl_path}:{line_number}: could not replay event: {exc}") from exc
            if event_type is not None and event.event_type != event_type:
                continue
            yield ReplayedPlatformEvent(
                source=EventReplaySource.JSONL,
                subject=subject,
                event=event,
                published_at=published_at,
                line_number=line_number,
            )


def replay_jsonl_platform_events(
    path: Path | str,
    *,
    limit: int | None = None,
    event_type: PlatformEventType | None = None,
) -> list[ReplayedPlatformEvent]:
    events: list[ReplayedPlatformEvent] = []
    for event in iter_jsonl_platform_events(path, event_type=event_type):
        events.append(event)
        if limit is not None and len(events) >= limit:
            break
    return events


def replay_outbox_platform_events(
    store: PlatformEventOutboxReplayStore,
    *,
    limit: int = 1000,
    published: bool | None = None,
    event_type: PlatformEventType | None = None,
) -> list[ReplayedPlatformEvent]:
    records = store.list_platform_event_outbox_records(
        limit=limit,
        published=published,
        event_type=event_type,
    )
    return [_replayed_from_outbox(record) for record in records]


def summarize_replayed_events(events: Iterable[ReplayedPlatformEvent]) -> EventReplaySummary:
    by_event_type: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    total = 0
    for record in events:
        total += 1
        event_type = record.event.event_type.value
        by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
        by_subject[record.subject] = by_subject.get(record.subject, 0) + 1
    return EventReplaySummary(
        total=total,
        by_event_type=dict(sorted(by_event_type.items())),
        by_subject=dict(sorted(by_subject.items())),
    )


def _replayed_from_outbox(record: PlatformEventOutboxRecord) -> ReplayedPlatformEvent:
    return ReplayedPlatformEvent(
        source=EventReplaySource.OUTBOX,
        subject=record.subject,
        event=record.payload,
        published_at=record.published_at,
        outbox_event_id=record.event_id,
        publish_attempts=record.publish_attempts,
        last_error=record.last_error,
    )


def _datetime_from_iso(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("datetime value must be an ISO string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime value must be timezone-aware")
    return parsed.astimezone(UTC)
