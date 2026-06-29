from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from systematic_trading.domain.events import AnyPlatformEvent
from systematic_trading.storage.interfaces import PlatformEventOutboxStore


class PlatformEventPublisher(Protocol):
    def publish(self, event: AnyPlatformEvent, *, subject: str) -> None:
        ...


class EventOutboxDispatchFailure(BaseModel):
    event_id: str
    subject: str
    error: str


class EventOutboxDispatchResult(BaseModel):
    attempted: int = Field(default=0, ge=0)
    published: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    failures: list[EventOutboxDispatchFailure] = Field(default_factory=list)


class EventOutboxDispatcher:
    def __init__(self, store: PlatformEventOutboxStore, publisher: PlatformEventPublisher) -> None:
        self.store = store
        self.publisher = publisher

    def dispatch_pending(self, *, limit: int = 100) -> EventOutboxDispatchResult:
        records = self.store.list_pending_platform_events(limit=limit)
        failures: list[EventOutboxDispatchFailure] = []
        published = 0
        for record in records:
            try:
                self.publisher.publish(record.payload, subject=record.subject)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                self.store.record_platform_event_publish_failure(record.event_id, error)
                failures.append(
                    EventOutboxDispatchFailure(
                        event_id=record.event_id,
                        subject=record.subject,
                        error=error,
                    )
                )
                continue
            self.store.mark_platform_event_published(record.event_id)
            published += 1
        return EventOutboxDispatchResult(
            attempted=len(records),
            published=published,
            failed=len(failures),
            failures=failures,
        )


@dataclass(frozen=True)
class PublishedPlatformEvent:
    subject: str
    event: AnyPlatformEvent


@dataclass
class InMemoryPlatformEventPublisher:
    published: list[PublishedPlatformEvent] = field(default_factory=list)

    def publish(self, event: AnyPlatformEvent, *, subject: str) -> None:
        self.published.append(PublishedPlatformEvent(subject=subject, event=event))


@dataclass
class JsonlPlatformEventPublisher:
    path: Path

    def publish(self, event: AnyPlatformEvent, *, subject: str) -> None:
        output_path = Path(self.path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "published_at": datetime.now(tz=UTC).isoformat(),
            "subject": subject,
            "event": event.model_dump(mode="json"),
        }
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
