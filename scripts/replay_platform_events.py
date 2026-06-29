from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.events import PlatformEventType
from systematic_trading.messaging import (
    ReplayedPlatformEvent,
    replay_jsonl_platform_events,
    replay_outbox_platform_events,
    summarize_replayed_events,
)
from systematic_trading.storage import create_transactional_store


def replay_once(
    *,
    source: str,
    jsonl_path: Path,
    database_path: Path,
    limit: int,
    settings: AppSettings | None = None,
    event_type: PlatformEventType | None = None,
    published: bool | None = None,
) -> list[ReplayedPlatformEvent]:
    if source == "jsonl":
        return replay_jsonl_platform_events(jsonl_path, limit=limit, event_type=event_type)
    if source == "outbox":
        store = create_transactional_store(settings or AppSettings(), database_path=database_path)
        store.initialize()
        return replay_outbox_platform_events(store, limit=limit, published=published, event_type=event_type)
    raise ValueError(f"unsupported replay source: {source}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay platform events from JSONL or the local outbox.")
    parser.add_argument("--source", choices=["jsonl", "outbox"], default="jsonl")
    parser.add_argument("--jsonl", default=None, help="JSONL path. Defaults to var/events/platform_events.jsonl.")
    parser.add_argument("--database", default=None, help="SQLite database path. Defaults to ST_DATABASE_PATH or settings.")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--event-type", choices=[item.value for item in PlatformEventType], default=None)
    parser.add_argument("--published", choices=["all", "published", "pending"], default="all")
    parser.add_argument("--details", action="store_true", help="Print replayed events instead of only a summary.")
    args = parser.parse_args(argv)

    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    settings = AppSettings()
    jsonl_path = _resolve_path(args.jsonl, settings.data_dir / "events" / "platform_events.jsonl")
    database_path = _resolve_path(args.database, settings.database_path)
    event_type = PlatformEventType(args.event_type) if args.event_type else None
    published = _published_filter(args.published)
    events = replay_once(
        source=args.source,
        jsonl_path=jsonl_path,
        database_path=database_path,
        limit=args.limit,
        settings=settings,
        event_type=event_type,
        published=published,
    )
    output = events if args.details else summarize_replayed_events(events)
    print(json.dumps(_dump(output), sort_keys=True))
    return 0


def _published_filter(value: str) -> bool | None:
    if value == "published":
        return True
    if value == "pending":
        return False
    return None


def _resolve_path(value: str | None, default: Path) -> Path:
    path = Path(value) if value else Path(default)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _dump(value: object) -> object:
    if isinstance(value, list):
        return [item.model_dump(mode="json") for item in value]
    return value.model_dump(mode="json")


if __name__ == "__main__":
    raise SystemExit(main())
