from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.recorders import (
    IBMarketDataMode,
    load_recorder_source_policy,
    market_session_state,
)
from systematic_trading.services import OperationalLogger, default_operational_log_path, write_service_state_file


SERVICE_ID = "market_data_recorder"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the market-data recorder as an always-on scheduled service.")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to SPY unless --use-seed-universe is passed.")
    parser.add_argument("--use-seed-universe", action="store_true")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--market-data-mode", choices=[item.value for item in IBMarketDataMode if item != IBMarketDataMode.UNKNOWN], default=IBMarketDataMode.LIVE.value)
    parser.add_argument(
        "--intraday-feed",
        choices=["delayed-trades", "historical-live", "realtime"],
        default="delayed-trades",
        help="IB feed channel. delayed-trades retains sampled quotes; complete OHLCV comes from recovery.",
    )
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--timezone", default="America/New_York", help="Timezone of the configured capture window; calendar dates follow New York.")
    parser.add_argument("--market-open", default="09:30", help="Capture window start; cannot extend the US equity core session.")
    parser.add_argument("--market-close", default="16:00", help="Capture window end; capped at the scheduled US equity close, including early closes.")
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--realtime-chunk-seconds", type=float, default=300.0)
    parser.add_argument("--gap-fill-lookback-minutes", type=int, default=60)
    parser.add_argument("--gap-fill-interval-minutes", type=int, default=15)
    parser.add_argument("--gap-fill-max-bars-per-symbol", type=int, default=2000)
    parser.add_argument("--disable-intraday-recovery", action="store_true")
    parser.add_argument("--recovery-client-id", type=int, default=221)
    parser.add_argument("--recovery-start-date", default=None)
    parser.add_argument("--historical-bar-size", default="5 secs")
    parser.add_argument("--historical-live-initial-duration", default="3600 S")
    parser.add_argument("--historical-live-write-lookback-seconds", type=int, default=60)
    parser.add_argument("--what-to-show", default="TRADES")
    parser.add_argument("--disable-daily-backfill", action="store_true")
    parser.add_argument("--daily-backfill-symbols", default=None, help="Comma-separated daily symbols. Defaults to stored symbols plus registered benchmarks.")
    parser.add_argument("--daily-backfill-lookback-days", type=int, default=14)
    parser.add_argument("--daily-backfill-interval-minutes", type=int, default=360)
    parser.add_argument("--daily-backfill-start-date", default=None)
    parser.add_argument("--daily-backfill-provider", choices=["yahoo", "ib", "tushare"], default="yahoo")
    parser.add_argument("--daily-backfill-fallback-provider", choices=["none", "yahoo", "ib", "tushare"], default="ib")
    parser.add_argument("--daily-backfill-refresh-existing", action="store_true")
    parser.add_argument("--source-policy", default="config/market-data-recorder-sources.json")
    parser.add_argument("--state-path", default=None)
    parser.add_argument("--pid-path", default=None)
    parser.add_argument("--operation-log", default=None)
    args = parser.parse_args(argv)

    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be positive")
    if args.realtime_chunk_seconds <= 0:
        raise SystemExit("--realtime-chunk-seconds must be positive")
    if args.gap_fill_lookback_minutes <= 0:
        raise SystemExit("--gap-fill-lookback-minutes must be positive")
    if args.daily_backfill_lookback_days < 0:
        raise SystemExit("--daily-backfill-lookback-days must be non-negative")
    if args.daily_backfill_interval_minutes <= 0:
        raise SystemExit("--daily-backfill-interval-minutes must be positive")
    if not args.disable_intraday_recovery and (args.historical_bar_size != "5 secs" or args.what_to_show != "TRADES"):
        raise SystemExit("Automatic recovery supports 5 secs TRADES; disable recovery for a different capture contract")

    settings = AppSettings()
    source_policy = load_recorder_source_policy(_resolve_repo_path(args.source_policy))
    symbols = _resolve_symbols(args, source_policy)
    source_policy.validate_line_budget(symbols)
    state_path = _resolve_path(args.state_path, settings.data_dir / "run" / "market_data_recorder.state.json")
    pid_path = _resolve_path(args.pid_path, settings.data_dir / "run" / "market_data_recorder.pid")
    child_state_path = state_path.with_name("market_data_recorder.child.state.json")
    child_pid_path = pid_path.with_name("market_data_recorder.child.pid")
    operation_log_path = _resolve_path(args.operation_log, default_operational_log_path(settings))
    logger = OperationalLogger(path=operation_log_path, service_id=SERVICE_ID)
    _write_pid(pid_path)
    last_gap_fill_at: datetime | None = None
    last_daily_backfill_at: datetime | None = None
    last_child_status: dict[str, object] | None = None
    last_daily_backfill_status: dict[str, object] | None = None
    recovery_process = None
    last_recovery_start = None
    logger.info(
        "recorder_service_started",
        message="Market data recorder service started.",
        symbols=symbols,
        market_data_mode=args.market_data_mode,
        intraday_feed=args.intraday_feed,
        timezone=args.timezone,
        market_open=args.market_open,
        market_close=args.market_close,
        gap_fill_lookback_minutes=args.gap_fill_lookback_minutes,
        daily_backfill_enabled=not args.disable_daily_backfill,
        daily_backfill_provider=args.daily_backfill_provider,
        daily_backfill_fallback_provider=args.daily_backfill_fallback_provider,
        realtime_chunk_seconds=args.realtime_chunk_seconds,
    )
    try:
        while True:
            now = datetime.now(tz=UTC)
            if recovery_process is not None and recovery_process.poll() is None and last_recovery_start:
                if _recovery_worker_stale(state_path, now, last_recovery_start):
                    _stop_process_tree(recovery_process)
                    recovery_process.wait(timeout=15)
            if not args.disable_intraday_recovery and (
                recovery_process is None or recovery_process.poll() is not None
            ) and _should_gap_fill(now, last_recovery_start, 1):
                recovery_process = _start_recovery_worker(args, symbols, state_path)
                last_recovery_start = now
            session = market_session_state(
                now,
                timezone=args.timezone,
                market_open=args.market_open,
                market_close=args.market_close,
            )
            if not args.disable_daily_backfill and _should_gap_fill(
                now,
                last_daily_backfill_at,
                min(5, args.daily_backfill_interval_minutes)
                if last_daily_backfill_status and last_daily_backfill_status.get("returncode") != 0
                else args.daily_backfill_interval_minutes,
            ):
                _write_state(
                    state_path,
                    running=True,
                    mode="daily_backfill",
                    message="Market data recorder service running daily database backfill.",
                    symbols=symbols,
                    session=session,
                    last_gap_fill_at=last_gap_fill_at,
                    last_daily_backfill_at=last_daily_backfill_at,
                    last_child_status=last_child_status,
                    last_daily_backfill_status=last_daily_backfill_status,
                )
                last_daily_backfill_status = _run_daily_backfill_child(
                    symbols=args.daily_backfill_symbols,
                    lookback_days=args.daily_backfill_lookback_days,
                    start_date=args.daily_backfill_start_date,
                    provider=args.daily_backfill_provider,
                    fallback_provider=args.daily_backfill_fallback_provider,
                    refresh_existing=args.daily_backfill_refresh_existing,
                    logger=logger,
                )
                last_daily_backfill_at = datetime.now(tz=UTC)
                # Backfill can cross the open, close, or exchange-date boundary.
                now = last_daily_backfill_at
                session = market_session_state(
                    now,
                    timezone=args.timezone,
                    market_open=args.market_open,
                    market_close=args.market_close,
                )
            if not session.is_open:
                _write_state(
                    state_path,
                    running=True,
                    mode="idle",
                    message=f"Market data recorder service idle: {session.reason}.",
                    symbols=symbols,
                    session=session,
                    last_gap_fill_at=last_gap_fill_at,
                    last_daily_backfill_at=last_daily_backfill_at,
                    last_child_status=last_child_status,
                    last_daily_backfill_status=last_daily_backfill_status,
                )
                time.sleep(args.poll_seconds)
                continue

            # Historical recovery is a separate, paced process. Never pause the
            # prospective stream to drain an outage or a bootstrap backlog.
            chunk_seconds = min(args.realtime_chunk_seconds, session.seconds_until_close)
            _write_state(
                state_path,
                running=True,
                mode="recording",
                message=(
                    "Market data recorder service running IB historical live-update 5-second feed."
                    if args.intraday_feed == "historical-live"
                    else "Recording incomplete delayed quote samples; IB OHLCV recovery runs separately."
                    if args.intraday_feed == "delayed-trades"
                    else "Market data recorder service running IB realtime 5-second feed."
                ),
                symbols=symbols,
                session=session,
                last_gap_fill_at=last_gap_fill_at,
                last_daily_backfill_at=last_daily_backfill_at,
                last_child_status=last_child_status,
                last_daily_backfill_status=last_daily_backfill_status,
                intraday_feed=args.intraday_feed,
            )
            last_child_status = _run_child(
                mode=args.intraday_feed,
                symbols=symbols,
                market_data_mode=args.market_data_mode,
                client_id=args.client_id,
                duration_seconds=chunk_seconds,
                historical_duration=(
                    args.historical_live_initial_duration
                    if args.intraday_feed == "historical-live"
                    else None
                ),
                historical_bar_size=(
                    args.historical_bar_size if args.intraday_feed == "historical-live" else None
                ),
                historical_live_write_lookback_seconds=(
                    args.historical_live_write_lookback_seconds
                    if args.intraday_feed == "historical-live"
                    else None
                ),
                what_to_show=args.what_to_show,
                child_state_path=child_state_path,
                child_pid_path=child_pid_path,
                logger=logger,
            )
            if last_child_status.get("returncode") != 0:
                _write_state(
                    state_path,
                    running=True,
                    mode="degraded",
                    message="Market data recorder feed failed; historical recovery is scheduled.",
                    symbols=symbols,
                    session=session,
                    last_gap_fill_at=last_gap_fill_at,
                    last_daily_backfill_at=last_daily_backfill_at,
                    last_child_status=last_child_status,
                    last_daily_backfill_status=last_daily_backfill_status,
                    intraday_feed=args.intraday_feed,
                )
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        logger.warning("recorder_service_interrupted", message="Market data recorder service interrupted by operator.")
        return 130
    finally:
        if recovery_process is not None and recovery_process.poll() is None:
            _stop_process_tree(recovery_process)
        _remove_pid(pid_path)
        _write_state(
            state_path,
            running=False,
            mode="stopped",
            message="Market data recorder service stopped.",
            symbols=symbols,
            session=None,
            last_gap_fill_at=last_gap_fill_at,
            last_daily_backfill_at=last_daily_backfill_at,
            last_child_status=last_child_status,
            last_daily_backfill_status=last_daily_backfill_status,
        )
        logger.info("recorder_service_stopped", message="Market data recorder service stopped.")


def _start_recovery_worker(args, symbols, state_path):
    settings = AppSettings()
    occupied = {value for key, value in settings.model_dump().items() if "client_id" in key and value is not None}
    occupied.add(args.client_id or settings.ib_market_data_client_id or settings.ib_client_id + 20)
    if args.recovery_client_id in occupied:
        raise ValueError("Recovery must use a separate IB client ID from other configured broker clients")
    command = [sys.executable, str(REPO_ROOT / "scripts/recover_ib_intraday.py"),
        "--symbols", ",".join(symbols), "--client-id", str(args.recovery_client_id),
        "--parent-pid", str(os.getpid()),
        "--checkpoint", str(state_path.with_name("market_data_recorder.recovery.json")),
        "--state-path", str(state_path.with_name("market_data_recorder.recovery.state.json")),
        "--pid-path", str(state_path.with_name("market_data_recorder.recovery.pid"))]
    if args.recovery_start_date:
        command.extend(["--start-date", args.recovery_start_date])
    log_path = state_path.with_name("market_data_recorder.recovery.worker.log")
    with log_path.open("a", encoding="utf8") as output:
        return subprocess.Popen(command, cwd=REPO_ROOT, stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, start_new_session=os.name != "nt")


def _recovery_worker_stale(state_path, now, started):
    if (now - started).total_seconds() < 600:
        return False
    try:
        state = json.loads(state_path.with_name("market_data_recorder.recovery.state.json").read_text(encoding="utf8"))
        heartbeat = datetime.fromisoformat(state["heartbeat_at"])
        return (now - heartbeat).total_seconds() > 600
    except (OSError, ValueError, KeyError, TypeError):
        return True


def _stop_process_tree(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       timeout=15, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)


def _run_child(
    *,
    mode: str,
    symbols: list[str],
    market_data_mode: str,
    client_id: int | None,
    child_state_path: Path,
    child_pid_path: Path,
    logger: OperationalLogger,
    what_to_show: str,
    duration_seconds: float | None = None,
    historical_duration: str | None = None,
    historical_bar_size: str | None = None,
    historical_end_datetime: str | None = None,
    max_bars_per_symbol: int | None = None,
    historical_live_write_lookback_seconds: int | None = None,
) -> dict[str, object]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "record_ib_market_data.py"),
        "--mode",
        mode,
        "--symbols",
        ",".join(symbols),
        "--market-data-mode",
        market_data_mode,
        "--state-path",
        str(child_state_path),
        "--pid-path",
        str(child_pid_path),
        "--what-to-show",
        what_to_show,
    ]
    if client_id is not None:
        command.extend(["--client-id", str(client_id)])
    if duration_seconds is not None:
        command.extend(["--duration-seconds", str(round(duration_seconds, 3))])
    if historical_duration is not None:
        command.extend(["--historical-duration", historical_duration])
    if historical_bar_size is not None:
        command.extend(["--historical-bar-size", historical_bar_size])
    if historical_end_datetime is not None:
        command.extend(["--historical-end-datetime", historical_end_datetime])
    if max_bars_per_symbol is not None:
        command.extend(["--max-bars-per-symbol", str(max_bars_per_symbol)])
    if historical_live_write_lookback_seconds is not None:
        command.extend(
            [
                "--historical-live-write-lookback-seconds",
                str(historical_live_write_lookback_seconds),
            ]
        )
    started_at = datetime.now(tz=UTC)
    logger.info("recorder_service_child_starting", message="Starting recorder child capture.", mode=mode, symbols=symbols)
    result = _bounded_child(command, timeout_seconds=(duration_seconds + 120) if duration_seconds is not None else 900)
    completed_at = datetime.now(tz=UTC)
    status = {
        "mode": mode,
        "returncode": result.returncode,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }
    for line in reversed(result.stdout.splitlines()):
        try:
            status["child_result"] = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    level = logger.info if result.returncode == 0 else logger.error
    level(
        "recorder_service_child_completed",
        message="Recorder child capture completed.",
        **status,
    )
    return status


def _run_daily_backfill_child(
    *,
    symbols: str | None,
    lookback_days: int,
    start_date: str | None,
    provider: str,
    fallback_provider: str,
    refresh_existing: bool,
    logger: OperationalLogger,
) -> dict[str, object]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "backfill_clickhouse_daily_bars.py"),
        "--lookback-days",
        str(lookback_days),
        "--provider",
        provider,
        "--fallback-provider",
        fallback_provider,
    ]
    if symbols:
        command.extend(["--symbols", symbols])
    if start_date:
        command.extend(["--start-date", start_date])
    if refresh_existing:
        command.append("--refresh-existing")
    started_at = datetime.now(tz=UTC)
    logger.info(
        "recorder_service_daily_backfill_starting",
        message="Starting ClickHouse daily market-data backfill.",
        provider=provider,
        fallback_provider=fallback_provider,
        symbols=symbols,
        lookback_days=lookback_days,
        start_date=start_date,
        refresh_existing=refresh_existing,
    )
    result = _bounded_child(command, timeout_seconds=900)
    completed_at = datetime.now(tz=UTC)
    status = {
        "mode": "daily_backfill",
        "returncode": result.returncode,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-2000:],
    }
    level = logger.info if result.returncode == 0 else logger.error
    level(
        "recorder_service_daily_backfill_completed",
        message="ClickHouse daily market-data backfill completed.",
        **status,
    )
    return status


def _bounded_child(command, *, timeout_seconds):
    """Bound acquisition children, including Windows virtualenv descendants."""
    process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, start_new_session=os.name != "nt")
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        _stop_process_tree(process)
        stdout, stderr = process.communicate(timeout=15)
        return subprocess.CompletedProcess(command, 124, stdout,
            stderr + f"\nAcquisition exceeded {timeout_seconds}s; child stopped and retry scheduled.")


def _write_state(
    path: Path,
    *,
    running: bool,
    mode: str,
    message: str,
    symbols: list[str],
    session,
    last_gap_fill_at: datetime | None,
    last_daily_backfill_at: datetime | None,
    last_child_status: dict[str, object] | None,
    last_daily_backfill_status: dict[str, object] | None,
    intraday_feed: str | None = None,
) -> None:
    details = {
        "service_mode": mode,
        "symbols_active": symbols,
        "last_gap_fill_at": last_gap_fill_at.isoformat() if last_gap_fill_at else None,
        "last_daily_backfill_at": last_daily_backfill_at.isoformat() if last_daily_backfill_at else None,
        "last_child_status": last_child_status,
        "last_daily_backfill_status": last_daily_backfill_status,
        "intraday_feed": intraday_feed,
    }
    recovery_path = path.with_name("market_data_recorder.recovery.state.json")
    if recovery_path.exists():
        try:
            details["intraday_recovery"] = json.loads(recovery_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            details["intraday_recovery"] = {"last_error": str(exc), "running": False}
    if session is not None:
        details.update(
            {
                "session_date": session.session_date,
                "session_reason": session.reason,
                "market_open": session.market_open.isoformat(),
                "market_close": session.market_close.isoformat(),
                "seconds_until_open": round(session.seconds_until_open, 3),
                "seconds_until_close": round(session.seconds_until_close, 3),
            }
        )
    write_service_state_file(
        path,
        service_id=SERVICE_ID,
        running=running,
        heartbeat_at=datetime.now(tz=UTC),
        last_error=_child_last_error(last_child_status, last_daily_backfill_status),
        message=message,
        details=details,
    )


def _child_last_error(
    last_child_status: dict[str, object] | None,
    last_daily_backfill_status: dict[str, object] | None,
) -> str | None:
    for label, status in (
        ("Daily ClickHouse backfill", last_daily_backfill_status),
        ("IB recorder child", last_child_status),
    ):
        if not status:
            continue
        returncode = status.get("returncode")
        if returncode not in (None, 0):
            stderr = str(status.get("stderr_tail") or "").strip()
            child_result = status.get("child_result")
            run = child_result.get("run") if isinstance(child_result, dict) else None
            errors = run.get("errors") if isinstance(run, dict) else None
            source_error = str(errors[-1]) if isinstance(errors, list) and errors else ""
            detail = stderr or source_error
            suffix = f": {detail[-300:]}" if detail else ""
            return f"{label} failed with return code {returncode}{suffix}"
    return None


def _should_gap_fill(now: datetime, last_gap_fill_at: datetime | None, interval_minutes: int) -> bool:
    if last_gap_fill_at is None:
        return True
    return (now - last_gap_fill_at).total_seconds() >= interval_minutes * 60


def _resolve_symbols(args: argparse.Namespace, source_policy) -> list[str]:
    if args.use_seed_universe:
        symbols = source_policy.seed_symbols
    elif args.symbols:
        symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    else:
        symbols = ["SPY"]
    if args.max_symbols is not None:
        if args.max_symbols < 1:
            raise SystemExit("--max-symbols must be positive")
        symbols = symbols[: args.max_symbols]
    if not symbols:
        raise SystemExit("No symbols configured.")
    return symbols


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _resolve_path(value: str | None, default: Path) -> Path:
    path = Path(value) if value else Path(default)
    return path if path.is_absolute() else REPO_ROOT / path


def _write_pid(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="ascii")


def _remove_pid(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
