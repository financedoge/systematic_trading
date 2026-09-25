"""NAS snapshot lifecycle used by the local platform launchers."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.storage.nas_sync import LocalDatabases, NasSync, SyncConflict, read_json, write_json


def process_exists(pid: int):
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            kernel.CloseHandle(handle)
            return True
        return ctypes.get_last_error() == 5
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def assert_services_stopped():
    for name in ("operator_dashboard", "event_outbox_dispatcher", "market_data_recorder", "market_data_recorder.child"):
        path = ROOT / "var/run" / (name + ".pid")
        if path.exists():
            value = path.read_text().strip()
            if value and process_exists(int(value)):
                raise SyncConflict(f"Stop local services first: {name} PID is running")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "backup", "release", "worker", "stop-worker", "status", "guard"])
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
    if settings.database_path.resolve() not in databases.sqlite_paths:
        raise SyncConflict("Configured ST_DATABASE_PATH is missing from sqlite_paths")
    sync = NasSync(ROOT, config, databases)
    run = ROOT / "var/run"
    run.mkdir(parents=True, exist_ok=True)
    pid_path, stop_path = run / "database_sync.pid", run / "database_sync.stop"
    if args.action == "status":
        print(json.dumps({"local": sync.state, "nas_head": sync.head(), "nas_owner": sync.owner()}, indent=2))
    elif args.action == "guard":
        with sync.lock():
            sync.require_owner()
            if sync.state["phase"] != "active" or not pid_path.exists() or not process_exists(int(pid_path.read_text())):
                raise SyncConflict("Use start_local_platform.ps1 to prepare NAS sync and start its backup worker")
    elif args.action == "stop-worker":
        stop_path.touch()
        deadline = time.monotonic() + 330
        while pid_path.exists() and process_exists(int(pid_path.read_text())):
            if time.monotonic() > deadline:
                raise SyncConflict("Backup worker has not stopped; NAS ownership retained")
            time.sleep(0.5)
    elif args.action == "worker":
        # Exclusive local worker startup; stale PID files require explicit review.
        with pid_path.open("x") as stream:
            stream.write(str(os.getpid()))
        try:
            next_backup = time.monotonic() + config["interval_seconds"]
            while not stop_path.exists():
                if time.monotonic() >= next_backup:
                    try:
                        sync.backup()
                        write_json(run / "database_sync.state.json", {"ok": True, "head": sync.state["head"], "at": time.time()})
                    except Exception as error:
                        write_json(run / "database_sync.state.json", {"ok": False, "error": str(error), "at": time.time()})
                    next_backup = time.monotonic() + config["interval_seconds"]
                time.sleep(1)
        finally:
            pid_path.unlink(missing_ok=True)
    else:
        if args.action in ("prepare", "release"):
            assert_services_stopped()
            if pid_path.exists() and process_exists(int(pid_path.read_text())):
                raise SyncConflict("Stop database sync worker before handoff")
            pid_path.unlink(missing_ok=True)
            if args.action == "prepare":
                stop_path.unlink(missing_ok=True)
        getattr(sync, args.action)()
        print(f"NAS database {args.action} complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Database sync stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
