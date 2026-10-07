"""NAS snapshot lifecycle used by the local platform launchers."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.storage.nas_sync import LocalDatabases, NasSync, SyncConflict, read_json, write_json
from systematic_trading.storage.optional_sync import OptionalNasSync
from systematic_trading.runtime_io import exclusive_lock


def process_exists(pid: int):
    from systematic_trading.services.health import _pid_is_running
    return _pid_is_running(pid)


def assert_services_stopped():
    for name in ("operator_dashboard", "event_outbox_dispatcher", "market_data_recorder", "market_data_recorder.child"):
        path = ROOT / "var/run" / (name + ".pid")
        if path.exists():
            value = path.read_text().strip()
            if value and process_exists(int(value)):
                raise SyncConflict(f"Stop local services first: {name} PID is running")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "backup", "release", "worker", "stop-worker", "status", "guard", "preflight"])
    parser.add_argument("--config", type=Path, default=ROOT / "config/database-sync.json")
    args = parser.parse_args()
    config = read_json(args.config)
    if not config["enabled"]:
        print("NAS database sync disabled")
        return 0
    if config["interval_seconds"] < 30:
        raise ValueError("Sync interval must be at least 30 seconds")
    os.chdir(ROOT)
    settings = AppSettings()
    databases = LocalDatabases(ROOT, config, settings)
    if settings.transactional_store_backend.strip().lower() == "sqlite" and settings.database_path.resolve() not in databases.sqlite_paths:
        raise SyncConflict("Configured ST_DATABASE_PATH is missing from sqlite_paths")
    optional = config.get("optional", False)
    if optional and config.get("conflict_policy") != "latest_snapshot":
        raise ValueError("Optional NAS sync requires conflict_policy=latest_snapshot")
    sync = (OptionalNasSync if optional else NasSync)(ROOT, config, databases)
    run = ROOT / "var/run"
    run.mkdir(parents=True, exist_ok=True)
    pid_path, stop_path = run / "database_sync.pid", run / "database_sync.stop"
    if args.action == "status":
        try:
            if optional:
                sync.check_connection()
            remote = {"nas_head": sync.head(), "nas_owner": sync.owner()}
        except (OSError, SyncConflict) as exc:
            remote = {"nas_error": str(exc)}
        print(json.dumps({"local": sync.state, **remote}, indent=2))
    elif args.action == "guard":
        if optional:
            sync.guard()
        else:
            with sync.lock():
                sync.require_owner()
                if sync.state["phase"] != "active" or not pid_path.exists() or not process_exists(int(pid_path.read_text())):
                    raise SyncConflict("Use start_local_platform.ps1 to prepare NAS sync and start its backup worker")
    elif args.action == "stop-worker":
        stop_path.touch()
        from system_backup import stop_worker
        stop_worker(ROOT)
        deadline = time.monotonic() + 330
        while pid_path.exists() and process_exists(int(pid_path.read_text())):
            if time.monotonic() > deadline:
                raise SyncConflict("Backup worker has not stopped; NAS ownership retained")
            time.sleep(0.5)
    elif args.action == "worker":
        # Acquire the crash-released OS lock before replacing a stale PID.
        # Respect a live legacy worker that predates this lock contract.
        if pid_path.exists() and process_exists(int(pid_path.read_text())):
            raise SyncConflict("Backup worker is already running")
        worker_lock = exclusive_lock(run / "database_sync.worker.lock")
        worker_lock.__enter__()
        pid_path.write_text(str(os.getpid()))
        try:
            next_backup = time.monotonic() + config["interval_seconds"]
            next_system_check = 0
            while not stop_path.exists():
                if config.get("system_backup_config") and time.monotonic() >= next_system_check:
                    try:
                        from system_backup import start_worker
                        start_worker(ROOT, ROOT / config["system_backup_config"])
                    except Exception as error:
                        print(f"Optional system backup worker startup deferred: {error}", file=sys.stderr, flush=True)
                    next_system_check = time.monotonic() + 30
                if time.monotonic() >= next_backup:
                    try:
                        sync.backup()
                        if not optional:
                            write_json(run / "database_sync.state.json", {"ok": True, "head": sync.state["head"], "at": time.time()})
                    except Exception as error:
                        write_json(run / "database_sync.state.json", {"ok": False, "error": str(error), "at": time.time()})
                    next_backup = time.monotonic() + config["interval_seconds"]
                time.sleep(1)
        finally:
            if config.get("system_backup_config"):
                (run / "system_backup.stop").touch()
            pid_path.unlink(missing_ok=True)
            worker_lock.__exit__(None, None, None)
    else:
        if args.action in ("prepare", "release"):
            assert_services_stopped()
            if pid_path.exists() and process_exists(int(pid_path.read_text())):
                raise SyncConflict("Stop database sync worker before handoff")
            pid_path.unlink(missing_ok=True)
            if args.action == "prepare":
                stop_path.unlink(missing_ok=True)
        result = getattr(sync, args.action)()
        print(f"Database {args.action}: {result or 'complete'}")
        if optional and sync.state.get("sync_error"):
            print(f"Optional NAS backup deferred; local services may run: {sync.state['sync_error']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Database sync stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
