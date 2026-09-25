from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.recorders import (
    IBMarketDataMode,
    IbApiMarketDataRecorderClient,
    MarketDataRecorder,
    RawDataCatalog,
    RawMarketDataWriter,
    load_recorder_source_policy,
    load_storage_policy,
)
from systematic_trading.services import OperationalLogger, default_operational_log_path
from systematic_trading.storage import create_transactional_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record Interactive Brokers paper market data to immutable raw JSONL.")
    parser.add_argument(
        "--mode",
        choices=["realtime", "delayed-trades", "historical-live", "historical-smoke"],
        default="realtime",
    )
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to SPY unless --use-seed-universe is passed.")
    parser.add_argument("--use-seed-universe", action="store_true", help="Use the ETF seed list from config/market-data-recorder-sources.json.")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit symbols after resolving the configured list.")
    parser.add_argument("--duration-seconds", type=float, default=60.0, help="Runtime for realtime mode.")
    parser.add_argument("--historical-duration", default="1 D", help="IB duration string for historical-smoke mode.")
    parser.add_argument("--historical-bar-size", default="5 secs", help="IB bar size for historical-smoke mode.")
    parser.add_argument(
        "--historical-live-write-lookback-seconds",
        type=int,
        default=60,
        help="Initial HMDS tail to persist before prospective live updates.",
    )
    parser.add_argument("--historical-end-datetime", default="", help="IB endDateTime. Empty means now per TWS.")
    parser.add_argument("--max-bars-per-symbol", type=int, default=10, help="Bound historical-smoke writes per symbol.")
    parser.add_argument("--market-data-mode", choices=[item.value for item in IBMarketDataMode if item != IBMarketDataMode.UNKNOWN], default=IBMarketDataMode.LIVE.value)
    parser.add_argument("--what-to-show", default="TRADES")
    parser.add_argument("--include-outside-rth", action="store_true", help="Request data outside regular trading hours.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--database", default=None, help="SQLite database path. Defaults to ST_DATABASE_PATH or settings.")
    parser.add_argument("--storage-policy", default=None, help="Defaults to ST_MARKET_DATA_STORAGE_POLICY_PATH.")
    parser.add_argument("--source-policy", default="config/market-data-recorder-sources.json")
    parser.add_argument("--state-path", default=None)
    parser.add_argument("--pid-path", default=None)
    parser.add_argument("--request-spacing-seconds", type=float, default=None)
    parser.add_argument("--request-rate-per-second", type=float, default=None)
    parser.add_argument("--request-burst", type=int, default=None)
    parser.add_argument("--operation-log", default=None, help="JSONL operational log path. Defaults to var/log/platform_operations.jsonl.")
    parser.add_argument("--log-every-records", type=int, default=100, help="Write a recorder progress log every N records.")
    args = parser.parse_args(argv)

    settings = AppSettings()
    source_policy = load_recorder_source_policy(_resolve_repo_path(args.source_policy))
    storage_policy = load_storage_policy(_resolve_repo_path(args.storage_policy or settings.market_data_storage_policy_path))
    symbols = _resolve_symbols(args, source_policy)
    source_policy.validate_line_budget(symbols)
    database_path = _resolve_path(args.database, settings.database_path)
    state_path = _resolve_path(args.state_path, settings.data_dir / "run" / "market_data_recorder.state.json")
    pid_path = _resolve_path(args.pid_path, settings.data_dir / "run" / "market_data_recorder.pid")
    operation_log_path = _resolve_path(args.operation_log, default_operational_log_path(settings))
    if args.log_every_records < 1:
        raise SystemExit("--log-every-records must be positive")
    logger = OperationalLogger(path=operation_log_path, service_id="market_data_recorder")
    store = create_transactional_store(settings, database_path=database_path)
    store.initialize()
    writer = RawMarketDataWriter(storage_policy.hot_spool_root)
    catalog = RawDataCatalog(storage_policy.hot_spool_root)
    recorder = MarketDataRecorder(
        writer=writer,
        catalog=catalog,
        event_store=store,
        state_path=state_path,
        environment=OrderEnvironment.PAPER,
        operation_logger=logger,
        log_every_records=args.log_every_records,
    )
    client = IbApiMarketDataRecorderClient()
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER).model_copy(
        update={
            "host": args.host or settings.ib_host,
            "port": args.port or settings.ib_paper_port,
            "client_id": args.client_id or settings.ib_market_data_client_id or settings.ib_client_id + 20,
        }
    )
    market_data_mode = IBMarketDataMode(args.market_data_mode)
    request_spacing_seconds = (
        args.request_spacing_seconds
        if args.request_spacing_seconds is not None
        else (
            source_policy.historical_request_spacing_seconds
            if args.mode in {"historical-live", "historical-smoke"}
            else 0.25
            if args.mode == "delayed-trades"
            else source_policy.realtime_subscription_spacing_seconds
        )
    )
    request_rate_per_second = args.request_rate_per_second or source_policy.request_rate_per_second
    request_burst = args.request_burst or source_policy.request_burst

    _write_pid(pid_path)
    logger.info(
        "recorder_run_starting",
        message="IB market data recorder run starting.",
        mode=args.mode,
        symbols=symbols,
        market_data_mode=market_data_mode.value,
        what_to_show=args.what_to_show,
        use_rth=not args.include_outside_rth,
        profile=profile,
        database_path=database_path,
        state_path=state_path,
        pid_path=pid_path,
        hot_spool_root=storage_policy.hot_spool_root,
        request_spacing_seconds=request_spacing_seconds,
        request_rate_per_second=request_rate_per_second,
        request_burst=request_burst,
    )
    recorder.write_state(
        running=True,
        message=f"IB market data recorder starting in {args.mode} mode.",
    )
    exit_code = 0
    try:
        if args.mode == "historical-smoke":
            result = client.record_historical_bars(
                profile=profile,
                symbols=symbols,
                recorder=recorder,
                duration=args.historical_duration,
                bar_size=args.historical_bar_size,
                end_datetime=args.historical_end_datetime,
                market_data_mode=market_data_mode,
                what_to_show=args.what_to_show,
                use_rth=not args.include_outside_rth,
                request_spacing_seconds=request_spacing_seconds,
                request_rate_per_second=request_rate_per_second,
                request_burst=request_burst,
                max_bars_per_symbol=args.max_bars_per_symbol,
            )
        elif args.mode == "historical-live":
            result = client.record_historical_live_bars(
                profile=profile,
                symbols=symbols,
                recorder=recorder,
                duration_seconds=args.duration_seconds,
                initial_duration=args.historical_duration,
                initial_write_lookback_seconds=args.historical_live_write_lookback_seconds,
                bar_size=args.historical_bar_size,
                market_data_mode=market_data_mode,
                what_to_show=args.what_to_show,
                use_rth=not args.include_outside_rth,
                request_spacing_seconds=request_spacing_seconds,
                request_rate_per_second=request_rate_per_second,
                request_burst=request_burst,
            )
        elif args.mode == "delayed-trades":
            result = client.record_delayed_trade_bars(
                profile=profile,
                symbols=symbols,
                recorder=recorder,
                duration_seconds=args.duration_seconds,
                request_spacing_seconds=request_spacing_seconds,
                request_rate_per_second=request_rate_per_second,
                request_burst=request_burst,
            )
        else:
            result = client.record_realtime_bars(
                profile=profile,
                symbols=symbols,
                recorder=recorder,
                duration_seconds=args.duration_seconds,
                market_data_mode=market_data_mode,
                what_to_show=args.what_to_show,
                use_rth=not args.include_outside_rth,
                request_spacing_seconds=request_spacing_seconds,
                request_rate_per_second=request_rate_per_second,
                request_burst=request_burst,
            )
        exit_code = 0 if result.completed_successfully else 1
        failed_message = (
            f"No usable intraday data for: {', '.join(result.failed_symbols)}."
            if result.failed_symbols
            else None
        )
        completion_message = (
            "IB market data recorder completed."
            if result.completed_successfully
            else "IB market data recorder completed with missing symbol coverage."
        )
        recorder.write_state(
            running=False,
            last_error=failed_message,
            message=completion_message,
        )
        log = logger.info if result.completed_successfully else logger.error
        log(
            "recorder_run_completed" if result.completed_successfully else "recorder_run_degraded",
            message=completion_message,
            run=result,
            summary=recorder.summary(),
            state_path=state_path,
            database_path=database_path,
        )
        print(
            json.dumps(
                {
                    "status": "completed" if result.completed_successfully else "degraded",
                    "profile": profile.model_dump(mode="json"),
                    "run": result.model_dump(mode="json"),
                    "recorder": recorder.summary().model_dump(mode="json"),
                    "state_path": str(state_path),
                    "database_path": str(database_path),
                },
                sort_keys=True,
            )
        )
    except KeyboardInterrupt:
        exit_code = 130
        logger.warning(
            "recorder_run_interrupted",
            message="IB market data recorder interrupted by operator.",
            summary=recorder.summary(),
        )
        recorder.write_state(
            running=False,
            last_error="Interrupted by operator.",
            message="IB market data recorder interrupted.",
        )
    except Exception as exc:
        exit_code = 1
        last_error = f"{type(exc).__name__}: {exc}"
        logger.error(
            "recorder_run_failed",
            message=last_error,
            summary=recorder.summary(),
            state_path=state_path,
            database_path=database_path,
        )
        recorder.write_state(
            running=False,
            last_error=last_error,
            message="IB market data recorder stopped after failure.",
        )
        print(json.dumps({"status": "error", "error": last_error}, sort_keys=True))
    finally:
        _remove_pid(pid_path)
        logger.info(
            "recorder_pid_removed",
            message="IB market data recorder PID file removed.",
            pid_path=pid_path,
            exit_code=exit_code,
        )
    return exit_code


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
