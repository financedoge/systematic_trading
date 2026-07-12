from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.messaging import EventOutboxDispatcher, JsonlPlatformEventPublisher, NatsJetStreamPublisher
from systematic_trading.messaging.outbox import EventOutboxDispatchResult
from systematic_trading.services import OperationalLogger, default_operational_log_path, write_service_state_file
from systematic_trading.storage import create_transactional_store

SERVICE_ID = "event_outbox_dispatcher"


def dispatch_once(
    *,
    database_path: Path,
    output_path: Path,
    limit: int,
    settings: AppSettings | None = None,
    publisher: object | None = None,
) -> EventOutboxDispatchResult:
    store = create_transactional_store(settings or AppSettings(), database_path=database_path)
    store.initialize()
    dispatcher = EventOutboxDispatcher(store, publisher or JsonlPlatformEventPublisher(output_path))
    return dispatcher.dispatch_pending(limit=limit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch pending platform events from the local outbox.")
    parser.add_argument("--database", default=None, help="SQLite database path. Defaults to ST_DATABASE_PATH or settings.")
    parser.add_argument("--output", default=None, help="JSONL output path. Defaults to var/events/platform_events.jsonl.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum events to dispatch per batch.")
    parser.add_argument("--loop", action="store_true", help="Keep polling instead of dispatching one batch.")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="Polling interval for --loop mode.")
    parser.add_argument("--max-iterations", type=int, default=None, help="Optional loop iteration cap for controlled runs.")
    parser.add_argument("--state-path", default=None, help="Service heartbeat state path. Defaults to var/run/event_outbox_dispatcher.state.json.")
    parser.add_argument("--publisher", choices=["jsonl", "nats"], default="jsonl", help="Publish target for drained outbox events.")
    parser.add_argument("--nats-url", default="nats://127.0.0.1:4222", help="NATS server URL used when --publisher nats.")
    parser.add_argument("--operation-log", default=None, help="JSONL operational log path. Defaults to var/log/platform_operations.jsonl.")
    parser.add_argument(
        "--log-heartbeat-every-iterations",
        type=int,
        default=12,
        help="Write a dispatcher heartbeat log every N loop iterations when no events are dispatched.",
    )
    args = parser.parse_args(argv)

    settings = AppSettings()
    database_path = _resolve_path(args.database, settings.database_path)
    output_path = _resolve_path(args.output, settings.data_dir / "events" / "platform_events.jsonl")
    state_path = _resolve_path(args.state_path, settings.data_dir / "run" / "event_outbox_dispatcher.state.json")
    operation_log_path = _resolve_path(args.operation_log, default_operational_log_path(settings))
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be positive")
    if args.log_heartbeat_every_iterations < 1:
        raise SystemExit("--log-heartbeat-every-iterations must be positive")

    started_at = datetime.now(tz=UTC)
    iterations = 0
    last_result: EventOutboxDispatchResult | None = None
    exit_code = 0
    logger = OperationalLogger(path=operation_log_path, service_id=SERVICE_ID)
    publisher = _build_publisher(args, output_path)
    logger.info(
        "dispatcher_started",
        message="Event outbox dispatcher started.",
        database_path=database_path,
        output_path=output_path,
        publisher=args.publisher,
        nats_url=args.nats_url if args.publisher == "nats" else None,
        loop=args.loop,
        interval_seconds=args.interval_seconds,
        limit=args.limit,
    )
    _write_dispatcher_state(
        state_path=state_path,
        started_at=started_at,
        running=True,
        database_path=database_path,
        output_path=output_path,
        publisher_name=args.publisher,
        nats_url=args.nats_url,
        message="Event outbox dispatcher started.",
    )
    try:
        while True:
            try:
                last_result = dispatch_once(
                    database_path=database_path,
                    output_path=output_path,
                    limit=args.limit,
                    settings=settings,
                    publisher=publisher,
                )
                last_error = _dispatch_error(last_result)
                print(json.dumps(last_result.model_dump(mode="json"), sort_keys=True))
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                print(json.dumps({"error": last_error}, sort_keys=True))
                logger.error(
                    "dispatch_failed",
                    message=last_error,
                    iteration=iterations,
                    publisher=args.publisher,
                    nats_url=args.nats_url if args.publisher == "nats" else None,
                )
                if not args.loop:
                    exit_code = 1
                    _write_dispatcher_state(
                        state_path=state_path,
                        started_at=started_at,
                        running=False,
                        database_path=database_path,
                        output_path=output_path,
                        publisher_name=args.publisher,
                        nats_url=args.nats_url,
                        last_error=last_error,
                        message="Event outbox dispatcher stopped after dispatch failure.",
                    )
                    break
            else:
                exit_code = 1 if last_result.failed else 0
                if _should_log_dispatch_result(
                    last_result,
                    iteration=iterations,
                    heartbeat_every=args.log_heartbeat_every_iterations,
                ):
                    level = "error" if last_result.failed else "info"
                    logger.write(
                        level,
                        "dispatch_batch",
                        message="Event outbox dispatch batch completed.",
                        details={
                            "iteration": iterations,
                            "publisher": args.publisher,
                            "nats_url": args.nats_url if args.publisher == "nats" else None,
                            "result": last_result.model_dump(mode="json"),
                        },
                    )

            _write_dispatcher_state(
                state_path=state_path,
                started_at=started_at,
                running=True,
                database_path=database_path,
                output_path=output_path,
                publisher_name=args.publisher,
                nats_url=args.nats_url,
                last_result=last_result,
                last_error=last_error,
                message="Event outbox dispatcher heartbeat.",
            )
            iterations += 1
            if not args.loop:
                _write_dispatcher_state(
                    state_path=state_path,
                    started_at=started_at,
                    running=False,
                    database_path=database_path,
                    output_path=output_path,
                    publisher_name=args.publisher,
                    nats_url=args.nats_url,
                    last_result=last_result,
                    last_error=last_error,
                    message="Event outbox dispatcher completed one-shot dispatch.",
                )
                logger.info(
                    "dispatcher_completed",
                    message="Event outbox dispatcher completed one-shot dispatch.",
                    iteration=iterations,
                    last_result=last_result,
                    last_error=last_error,
                )
                break
            if args.max_iterations is not None and iterations >= args.max_iterations:
                _write_dispatcher_state(
                    state_path=state_path,
                    started_at=started_at,
                    running=False,
                    database_path=database_path,
                    output_path=output_path,
                    publisher_name=args.publisher,
                    nats_url=args.nats_url,
                    last_result=last_result,
                    last_error=last_error,
                    message="Event outbox dispatcher reached max iterations.",
                )
                logger.info(
                    "dispatcher_max_iterations",
                    message="Event outbox dispatcher reached max iterations.",
                    iterations=iterations,
                    last_result=last_result,
                    last_error=last_error,
                )
                break
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        logger.warning(
            "dispatcher_interrupted",
            message="Event outbox dispatcher interrupted by operator.",
            iteration=iterations,
            last_result=last_result,
        )
        _write_dispatcher_state(
            state_path=state_path,
            started_at=started_at,
            running=False,
            database_path=database_path,
            output_path=output_path,
            publisher_name=args.publisher,
            nats_url=args.nats_url,
            last_result=last_result,
            last_error="Interrupted by operator.",
            message="Event outbox dispatcher stopped.",
        )
        return 130
    return exit_code


def _resolve_path(value: str | None, default: Path) -> Path:
    path = Path(value) if value else Path(default)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _dispatch_error(result: EventOutboxDispatchResult) -> str | None:
    if not result.failed:
        return None
    return f"{result.failed} platform event publish failure(s)."


def _should_log_dispatch_result(
    result: EventOutboxDispatchResult,
    *,
    iteration: int,
    heartbeat_every: int,
) -> bool:
    if result.attempted or result.failed:
        return True
    return iteration % heartbeat_every == 0


def _build_publisher(args: argparse.Namespace, output_path: Path) -> object:
    if args.publisher == "nats":
        return NatsJetStreamPublisher(servers=[args.nats_url])
    return JsonlPlatformEventPublisher(output_path)


def _write_dispatcher_state(
    *,
    state_path: Path,
    started_at: datetime,
    running: bool,
    database_path: Path,
    output_path: Path,
    publisher_name: str,
    nats_url: str,
    last_result: EventOutboxDispatchResult | None = None,
    last_error: str | None = None,
    message: str,
) -> None:
    write_service_state_file(
        state_path,
        service_id=SERVICE_ID,
        running=running,
        started_at=started_at,
        heartbeat_at=datetime.now(tz=UTC),
        last_error=last_error,
        message=message,
        details={
            "process_id": os.getpid(),
            "database_path": str(database_path),
            "output_path": str(output_path),
            "publisher": publisher_name,
            "nats_url": nats_url if publisher_name == "nats" else None,
            "last_dispatch": last_result.model_dump(mode="json") if last_result is not None else None,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
