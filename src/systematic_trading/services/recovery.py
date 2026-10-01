"""Local process recovery. Restart missing services, never bypass trading gates."""
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

from systematic_trading.services.health import _pid_is_running, write_service_state_file
from systematic_trading.runtime_io import atomic_json, exclusive_lock

SERVICES = ("nats", "clickhouse", "operator", "recorder", "backup")
PIDS = {"operator": "operator_dashboard.pid", "recorder": "market_data_recorder.pid", "backup": "database_sync.pid"}


def process_present(path):
    try:
        return _pid_is_running(int(path.read_text().strip()))
    except (OSError, ValueError):
        return False


class LocalRecovery:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.run = self.root / "var/run"
        self.profile_path = self.run / "local_recovery.profile.json"
        self.retries_path = self.run / "local_recovery.retries.json"
        self.started_at = datetime.now(UTC)
        self.details = {}
        self.retries = json.loads(self.retries_path.read_text()) if self.retries_path.exists() else {}

    def probe(self, service, profile):
        if service in PIDS:
            if process_present(self.run / PIDS[service]):
                if service == "operator" and not process_present(self.run / "event_outbox_dispatcher.pid"):
                    return "missing", "Dispatcher exited; guarded start will retain the running API."
                return "running", "Process present; application health owns data and worker freshness."
            if service == "recorder" and process_present(self.run / "market_data_recorder.child.pid"):
                return "waiting", "An existing capture child is still running; awaiting its bounded completion."
            return "missing", "Process absent."
        url = "http://127.0.0.1:8222/healthz?js-enabled-only=true" if service == "nats" else "http://127.0.0.1:8123/ping"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return ("running", "HTTP ready") if response.status == 200 else ("missing", "HTTP unavailable")
        except OSError as exc:
            return "missing", str(exc)

    def repair(self, service):
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            raise OSError("PowerShell unavailable for local recovery")
        logs = self.root / "var/log"; logs.mkdir(parents=True, exist_ok=True)
        with (logs / "local_recovery.actions.log").open("a", encoding="utf8") as stream:
            subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(self.root / "scripts/recover_local_service.ps1"), "-Service", service,
                "-ProfilePath", str(self.profile_path)], cwd=self.root, stdout=stream, stderr=subprocess.STDOUT,
                check=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def snapshot(self, *, running=True, error=None):
        try:
            write_service_state_file(self.run / "local_recovery.state.json", service_id="local_recovery",
                running=running, started_at=self.started_at, last_error=error,
                message="Local recovery checks desired services every 30 seconds.",
                details=dict(process_id=os.getpid(), services=self.details, retries=self.retries,
                             disk_free_bytes=shutil.disk_usage(self.root).free))
        except OSError:
            logging.getLogger(__name__).exception("Recovery status write failed; keeping recovery worker alive")

    def cycle(self, *, now=None):
        now = time.time() if now is None else now
        for service in SERVICES:
            # This lock serializes repair with explicit stop/pause commands.
            # The stop waits for an in-flight start, then suppresses future starts.
            with exclusive_lock(self.run / "local_recovery.control.lock"):
                if (self.run / "local_recovery.stop").exists():
                    break
                profile = json.loads(self.profile_path.read_text(encoding="utf-8-sig"))
                if not profile.get("enabled", {}).get(service) or (self.run / f"recovery-{service}.pause").exists():
                    self.details[service] = dict(status="disabled", message="Not requested or explicitly stopped.")
                    continue
                if service == "backup" and (self.run / "database_sync.stop").exists():
                    self.details[service] = dict(status="disabled", message="Backup explicitly stopped.")
                    continue
                state, message = self.probe(service, profile)
                self.details[service] = dict(status=state, message=message)
                previous = self.retries.get(service, {})
                if state == "running":
                    self.retries.pop(service, None)
                    continue
                if state != "missing" or now < previous.get("next_retry_at", 0):
                    continue
                if shutil.disk_usage(self.root).free < 2 * 1024**3:
                    self.details[service] = dict(status="blocked", message="Less than 2 GiB free; repair requires disk space.")
                    continue
                failures = previous.get("attempts", 0) + 1
                self.retries[service] = dict(attempts=failures, last_attempt_at=now,
                    next_retry_at=now+min(900, 30*2**min(failures-1, 5)))
                atomic_json(self.retries_path, self.retries)  # Survives supervisor/process failure.
                self.details[service] = dict(status="recovering", message="Starting through the normal guarded entry point.")
                self.snapshot()
                try:
                    self.repair(service)
                    state, message = self.probe(service, profile)
                    self.details[service] = dict(status=state, message=message)
                except Exception as exc:
                    self.details[service] = dict(status="error", message=f"{type(exc).__name__}: {exc}")
        atomic_json(self.retries_path, self.retries)
        problems = [s for s, item in self.details.items() if item["status"] not in {"running", "disabled"}]
        self.snapshot(error="Recovery pending: " + ", ".join(problems) if problems else None)

    def run_forever(self):
        with exclusive_lock(self.run / "local_recovery.worker.lock"):
            (self.run / "local_recovery.pid").write_text(str(os.getpid()))
            try:
                self.snapshot()
                while not (self.run / "local_recovery.stop").exists():
                    try:
                        self.cycle()
                    except PermissionError:
                        # Lifecycle control may briefly own the lock at startup
                        # or while pausing services; this is not service failure.
                        time.sleep(.2)
                        continue
                    except Exception as exc:
                        self.snapshot(error=f"Recovery check failed; retrying: {exc}")
                    for _ in range(30):
                        if (self.run / "local_recovery.stop").exists():
                            break
                        time.sleep(1)
            finally:
                self.snapshot(running=False)
                (self.run / "local_recovery.pid").unlink(missing_ok=True)


def control(root, action, service=None):
    root = Path(root).resolve(); run = root / "var/run"
    # A missing profile means no supervisor is configured; normal service
    # scripts continue to work in standalone/test setups.
    if action in {"pause", "resume"} and not (run / "local_recovery.profile.json").exists():
        return
    deadline = time.monotonic()+260
    while True:
        try:
            with exclusive_lock(run / "local_recovery.control.lock"):
                if action == "stop":
                    (run / "local_recovery.stop").touch()
                elif action in {"pause", "resume"}:
                    if service not in SERVICES:
                        raise ValueError("Unknown service")
                    path = run / f"recovery-{service}.pause"
                    path.touch() if action == "pause" else path.unlink(missing_ok=True)
                elif action == "start":
                    (run / "local_recovery.stop").unlink(missing_ok=True)
                    try:
                        with exclusive_lock(run / "local_recovery.worker.lock"):
                            pass
                    except OSError:
                        return
                    logs = root / "var/log"; logs.mkdir(parents=True, exist_ok=True)
                    with (logs/"local_recovery.out.log").open("a") as out, (logs/"local_recovery.err.log").open("a") as err:
                        launched_at = time.time()
                        subprocess.Popen([sys.executable, str(root/"scripts/local_recovery.py"), "run"], cwd=root,
                            stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    ready = time.monotonic()+10
                    pid_path = run / "local_recovery.pid"
                    while not (pid_path.exists() and pid_path.stat().st_mtime >= launched_at and process_present(pid_path)):
                        if time.monotonic() > ready:
                            raise RuntimeError("Recovery worker did not start; inspect var/log/local_recovery.err.log")
                        time.sleep(.1)
                else:
                    raise ValueError("Unknown recovery action")
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)
    if action == "stop":
        while process_present(run / "local_recovery.pid"):
            if time.monotonic() >= deadline:
                raise TimeoutError("Recovery worker did not stop")
            time.sleep(.2)
