"""App-owned optional full-system backup, status, scrub and safe file recovery."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.runtime_io import exclusive_lock
from systematic_trading.services.health import _pid_is_running
from systematic_trading.storage.nas_sync import read_json
from systematic_trading.storage.system_backup import SystemBackup, check_nas


def process_running(path):
    try:
        return _pid_is_running(int(path.read_text().strip()))
    except (OSError, ValueError):
        return False


def start_worker(root=ROOT, config_path=None, *, explicit=False):
    root = Path(root)
    config_path = Path(config_path or root / "config/system-backup.json")
    if not config_path.exists() or not read_json(config_path).get("enabled"):
        return
    run = root / "var/run"
    run.mkdir(parents=True, exist_ok=True)
    pause = run / "system_backup.paused"
    if explicit:
        pause.unlink(missing_ok=True)
    elif pause.exists():
        return
    if (run / "database_sync.stop").exists() or process_running(run / "system_backup.pid"):
        return
    with exclusive_lock(run / "system_backup.start.lock"):
        if process_running(run / "system_backup.pid"):
            return
        (run / "system_backup.stop").unlink(missing_ok=True)
        log = root / "var/log/system_backup.worker.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("ab") as output:
            subprocess.Popen([sys.executable, str(root / "scripts/system_backup.py"), "worker", "--config", str(config_path)],
                cwd=root, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def stop_worker(root=ROOT, *, explicit=False):
    run = Path(root) / "var/run"
    run.mkdir(parents=True, exist_ok=True)
    if explicit:
        (run / "system_backup.paused").touch()
    (run / "system_backup.stop").touch()
    # Network work is cancellable. This request never makes NAS a shutdown gate.
    deadline = time.monotonic()+45
    while process_running(run / "system_backup.pid") and time.monotonic() < deadline:
        time.sleep(.25)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["once", "worker", "start", "stop", "status", "verify", "restore-files"])
    parser.add_argument("--config", type=Path, default=ROOT / "config/system-backup.json")
    parser.add_argument("--snapshot")
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.action == "start":
        start_worker(config_path=args.config, explicit=True)
        return 0
    if args.action == "stop":
        stop_worker(explicit=True)
        return 0
    backup = SystemBackup(ROOT, read_json(args.config), AppSettings())
    if args.action == "status":
        print(json.dumps(backup.state, indent=2))
    elif args.action == "once":
        backup.once()
        print(json.dumps(backup.state, indent=2))
        return 0 if backup.state.get("status") == "complete" else 2
    elif args.action == "verify":
        check_nas(backup.repository)
        with exclusive_lock(backup.local / "capture.lock"):
            backup.restic("check", "--read-data")
        print("Complete repository data readback passed")
    elif args.action == "restore-files":
        if not args.snapshot or not args.target:
            parser.error("restore-files requires --snapshot and --target")
        print(backup.restore_files(args.snapshot, args.target))
    else:
        pid = backup.run_dir / "system_backup.pid"
        with exclusive_lock(backup.run_dir / "system_backup.worker.lock"):
            pid.write_text(str(os.getpid()))
            try:
                while not backup.stop_path.exists():
                    last = backup.state.get("captured_at")
                    due = not last or time.time()-datetime.fromisoformat(last).timestamp() >= backup.config["interval_seconds"]
                    if due or (backup.local / "pending.json").exists() or backup.state.get("status") == "deferred":
                        backup.once()
                    for _ in range(backup.config["retry_seconds"]):
                        if backup.stop_path.exists():
                            break
                        if _ % 30 == 0:
                            backup.heartbeat()
                        time.sleep(1)
            finally:
                backup.status("paused", error=None)
                pid.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
