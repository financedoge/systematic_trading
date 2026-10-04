"""App-owned, resumable RTH 5-second recovery, independent of streaming."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.recorders import (
    IbApiMarketDataRecorderClient, MarketDataRecorder, RawDataCatalog, RawMarketDataWriter, load_storage_policy,
)
from systematic_trading.recorders.recovery import RecoveryEventBatch, RecoveryLedger, WindowRecorder
from systematic_trading.runtime_io import exclusive_lock
from systematic_trading.services import OperationalLogger, write_service_state_file
from systematic_trading.services.health import _pid_is_running
from systematic_trading.storage import create_transactional_store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="SPY,QQQ,TLT,GLD,IWM")
    parser.add_argument("--client-id", type=int, default=221)
    parser.add_argument("--checkpoint", default="var/run/market_data_recorder.recovery.json")
    parser.add_argument("--state-path", default="var/run/market_data_recorder.recovery.state.json")
    parser.add_argument("--pid-path", default="var/run/market_data_recorder.recovery.pid")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--spacing-seconds", type=float, default=30)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--max-requests", type=int, help="Finite acquisition canary; normal service runs continuously")
    args = parser.parse_args(argv)
    settings = AppSettings()
    symbols = sorted(set(s.strip().upper() for s in args.symbols.split(",") if s.strip()))
    if not symbols:
        parser.error("At least one symbol is required")
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER).model_copy(
        update={"client_id": args.client_id})
    if not profile.enabled:
        raise RuntimeError("Paper broker profile disabled")
    policy = load_storage_policy(settings.market_data_storage_policy_path)
    root = policy.hot_spool_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checkpoint, state_path, pid_path = (Path(v).resolve() for v in (args.checkpoint, args.state_path, args.pid_path))
    identity = {"source": "interactive-brokers", "environment": "paper", "host": profile.host,
                "port": profile.port, "root": str(root), "bar_size": "5 secs", "what_to_show": "TRADES", "use_rth": True}
    logger = OperationalLogger(path=settings.data_dir / "log/intraday_recovery.jsonl", service_id="intraday_recovery")
    with exclusive_lock(checkpoint.with_suffix(".lock")):
        ledger = RecoveryLedger(checkpoint, identity=identity, start_date=args.start_date, spacing_seconds=args.spacing_seconds)
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="ascii")
        store = create_transactional_store(settings)
        store.initialize()
        attempts = 0

        def fetch(window):
            stop_gb = float(policy.watermarks.get("hot_spool_stop_free_gb", 60))
            if shutil.disk_usage(root).free < stop_gb * 1024**3:
                raise RuntimeError(f"Raw spool free space below {stop_gb} GiB recovery watermark")
            batch = RecoveryEventBatch(store)
            recorder = MarketDataRecorder(writer=RawMarketDataWriter(root, part_id=f"recovery-{uuid4().hex}"), catalog=RawDataCatalog(root),
                event_store=None, state_path=state_path.with_name("market_data_recorder.recovery.capture.state.json"),
                environment=OrderEnvironment.PAPER, operation_logger=None, state_interval_seconds=5)
            checked = WindowRecorder(recorder, window, event_batch=batch)
            result = IbApiMarketDataRecorderClient(historical_timeout_seconds=30).record_historical_bars(
                profile=profile, symbols=[window.symbol], recorder=checked,
                duration=f"{int((window.end-window.start).total_seconds())} S", bar_size="5 secs",
                end_datetime=window.end.strftime("%Y%m%d-%H:%M:%S"),
                max_bars_per_symbol=None, what_to_show="TRADES", use_rth=True)
            event_count = len(batch.events)
            batch.flush()
            recorder.events_appended = event_count
            recorder.write_state(running=False, message="Historical window persisted.")
            return {"completed": result.completed_successfully and result.requests_completed == 1,
                    "slots": len(checked.slots), "bars_written": recorder.records_written,
                    "errors": result.errors, "last_raw_ref": recorder.last_raw_ref,
                    "last_catalog_ref": recorder.last_catalog_ref,
                    "first_timestamp": min(checked.slots).isoformat() if checked.slots else None,
                    "last_timestamp": max(checked.slots).isoformat() if checked.slots else None}

        try:
            while not args.parent_pid or _pid_is_running(args.parent_pid):
                now = datetime.now(UTC)
                before = ledger.data["sequence"]
                summary = ledger.summary(symbols, now)
                write_service_state_file(state_path, service_id="intraday_recovery", running=True,
                    heartbeat_at=now, message="Checking durable intraday recovery backlog.", details=summary)
                summary = ledger.step(symbols, now, fetch)
                attempted = ledger.data["sequence"] != before
                last_result = summary.get("last_result") or {}
                last_error = "; ".join(last_result.get("errors", [])[-2:]) if last_result.get("status") == "retry" else None
                if not last_error and summary["windows_by_status"].get("retry"):
                    last_error = "Historical windows remain pending retry; see recovery attempt receipts."
                write_service_state_file(state_path, service_id="intraday_recovery", running=True,
                    heartbeat_at=datetime.now(UTC), last_error=last_error,
                    message=f"Historical recovery: {summary['pending_windows']} windows outstanding.", details=summary)
                if attempted:
                    attempts += 1
                    logger.info("intraday_recovery_attempt", message="Historical window acquisition finished.", **last_result)
                if args.max_requests and attempts >= args.max_requests:
                    print(json.dumps(summary))
                    return 0 if last_result.get("status") == "complete" else 1
                time.sleep(5)
        finally:
            pid_path.unlink(missing_ok=True)
            write_service_state_file(state_path, service_id="intraday_recovery", running=False,
                heartbeat_at=datetime.now(UTC), message="Historical recovery worker stopped; checkpoint retained.",
                details=ledger.summary(symbols, datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
