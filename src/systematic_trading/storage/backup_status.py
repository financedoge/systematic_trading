"""Read-only backup telemetry. Never contact the NAS or start backup work here."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import math
from pathlib import Path
import re

from systematic_trading.services.health import _pid_is_running


PHASES = {
    "connecting": (0, "Connecting to NAS"),
    "inventorying_sources": (1, "Checking source coverage"),
    "capturing_postgres": (1, "Capturing PostgreSQL"),
    "capturing_clickhouse": (1, "Capturing ClickHouse"),
    "copying_clickhouse": (1, "Copying ClickHouse capture locally"),
    "capturing_queue": (1, "Capturing NATS streams"),
    "hashing_capture": (1, "Checking capture hashes"),
    "uploading": (2, "Uploading to NAS"),
    "verifying": (3, "Verifying NAS snapshot"),
    "complete": (4, "Backup complete"),
    "deferred": (None, "Waiting to retry"),
    "paused": (None, "Paused"),
    "disabled": (None, "Disabled"),
}


def _read(path: Path, limit=131072):
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            return None
        value = json.loads(data.decode("utf-8-sig"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _date(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, UTC)
        stamp = datetime.fromisoformat(value)
        return stamp.astimezone(UTC) if stamp.tzinfo else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _iso(value):
    stamp = _date(value)
    return stamp.isoformat() if stamp else None


def _number(value):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and value >= 0) else None


def _interval(value, default):
    number = _number(value)
    return int(number) if number and 1 <= number <= 604800 else default


def _id(value, length):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) else None


def _running(path):
    try:
        with path.open() as stream:
            pid = int(stream.read(32))
        return pid > 0 and _pid_is_running(pid)
    except (OSError, ValueError):
        return False


def _issue(error):
    # Child exception text can contain connection strings. Expose categories,
    # never command output, credentials, URLs or arbitrary exception contents.
    if not error:
        return None
    value = str(error).lower()
    if "recovery key" in value:
        return "The existing backup recovery key is required. Check the local worker log."
    if "timeout" in value or "timed out" in value:
        return "The NAS connection or backup operation timed out; automatic retry is pending."
    if "nas" in value or "winerror" in value or "connection" in value:
        return "The NAS operation could not finish; automatic retry is pending."
    return "The backup attempt could not finish. Check the local worker log for the cause."


def _progress(root, state, now):
    """Bounded tail of restic JSON, only for this active upload phase.

    The command log is reused by other native commands, so phase, modification
    time and a second state read guard against showing a previous run's 100%.
    No filenames or command output are returned to the browser.
    """
    started = _date(state.get("at"))
    if state.get("status") != "uploading" or not started:
        return None
    try:
        with (root / "var/system-backup/command.stdout.log").open("rb") as stream:
            import os
            info = os.fstat(stream.fileno())
            updated = datetime.fromtimestamp(info.st_mtime, UTC)
            if updated < started or updated > now + timedelta(seconds=5):
                return None
            stream.seek(max(0, info.st_size - 65536))
            lines = stream.read(65536).decode("utf8", errors="replace").splitlines()
        latest = _read(root / "var/run/system_backup.state.json") or {}
        if (latest.get("status"), latest.get("at")) != ("uploading", state.get("at")):
            return None
        for line in reversed(lines):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if not isinstance(value, dict) or value.get("message_type") != "status":
                continue
            result = {key: _number(value.get(key)) for key in
                      ("bytes_done", "total_bytes", "files_done", "total_files", "seconds_elapsed")}
            if result["bytes_done"] is None:
                continue
            total = result["total_bytes"]
            result.update(percent=min(100, 100 * result["bytes_done"] / total) if total else None,
                          updated_at=updated.isoformat(), stale=(now - updated).total_seconds() > 90)
            return result
    except OSError:
        pass
    return None


def backup_status(root: Path, *, now=None):
    root = Path(root)
    now = now or datetime.now(UTC)
    run = root / "var/run"
    config = _read(root / "config/system-backup.json")
    state_record = _read(run / "system_backup.state.json")
    state = state_record or {}
    health = _read(run / "system_backup.health.json") or {}
    pending = _read(root / "var/system-backup/pending.json")
    settings = config or {}
    interval = _interval(settings.get("interval_seconds"), 3600)
    retry = _interval(settings.get("retry_seconds"), 300)
    running = _running(run / "system_backup.pid")
    heartbeat = _date(health.get("heartbeat_at"))
    fresh = bool(heartbeat and -5 <= (now - heartbeat).total_seconds() <= 300)
    phase = state.get("status", "unknown")
    phase = phase if isinstance(phase, str) else "unknown"
    step, label = PHASES.get(phase, (None, "Status unavailable"))
    display, tone = phase, "active"
    if config is None or state_record is None or phase not in PHASES:
        display, label, tone = "unknown", "Status unavailable", "warning"
    elif not settings.get("enabled"):
        display, label, tone = "disabled", "Disabled", "muted"
    elif (run / "system_backup.paused").exists() or phase == "paused":
        display, label, tone = "paused", "Paused", "warning"
    elif not running:
        display, label, tone = "stopped", "Worker stopped", "warning"
    elif not fresh:
        display, label, tone = "stale", "Heartbeat delayed", "warning"
    elif phase == "deferred":
        tone = "warning"
    elif phase == "complete":
        tone = "good"
    active = display == phase and phase in PHASES and step is not None and step < 4
    completed = _date(state.get("completed_at"))
    snapshot = _id(state.get("snapshot"), 64)
    last_success = None
    if snapshot and completed:
        summary = state.get("summary")
        summary = summary if isinstance(summary, dict) else {}
        summary_end = _date(summary.get("backup_end"))
        # A new candidate overwrites summary before it passes verification.
        # Do not attach that candidate's sizes to the previous complete snapshot.
        if not summary_end or summary_end > completed:
            summary = {}
        last_success = dict(snapshot=snapshot, completed_at=completed.isoformat(),
            captured_at=_iso(state.get("captured_at")),
            bytes_processed=_number(summary.get("total_bytes_processed")),
            files_processed=_number(summary.get("total_files_processed")),
            bytes_added_packed=_number(summary.get("data_added_packed")),
            verification="Repository metadata and decrypted capture manifest checked. Full data scrub and restore testing are separate.")
    next_at, next_kind = None, None
    if display == "deferred" and _date(state.get("at")):
        next_at = (_date(state["at"]) + timedelta(seconds=retry)).isoformat()
        next_kind = "retry"
    elif display == "complete" and _date(state.get("captured_at")):
        next_at = (_date(state["captured_at"]) + timedelta(seconds=interval)).isoformat()
        next_kind = "capture"
    cfg_db = _read(root / "config/database-sync.json") or {}
    db = _read(run / "database_sync.state.json") or {}
    db_phase = db.get("status") if isinstance(db.get("status"), str) else "unknown"
    db_running = _running(run / "database_sync.pid")
    db_at = _date(db.get("at"))
    db_interval = _interval(cfg_db.get("interval_seconds"), 300)
    confirmed = db.get("ok") is True and db_phase in {"published_local", "current", "restored_newer_remote"}
    db_labels = {"published_local": "Published to NAS", "current": "NAS copy is current",
        "restored_newer_remote": "Restored newer NAS copy", "local_only": "Local only · NAS retry pending",
        "newer_remote_pending_restart": "Newer NAS copy awaits safe restart"}
    db_label = db_labels.get(db_phase, "Status unavailable")
    db_tone = "good" if confirmed else "warning"
    if cfg_db.get("enabled") is False:
        db_label, db_tone = "Disabled", "muted"
    elif not db_running:
        db_label, db_tone = "Worker stopped", "warning"
    elif db_at and (now - db_at).total_seconds() > max(900, db_interval * 3):
        db_label, db_tone = "Status delayed", "warning"
    roots = settings.get("required_paths", [])
    roots = [item for item in roots if isinstance(item, str)] if isinstance(roots, list) else []
    return dict(checked_at=now.isoformat(), full=dict(
        status=display, phase=phase if phase in PHASES else "unknown", label=label, tone=tone,
        stage=step if active or display == "complete" else None,
        phase_at=_iso(state.get("at")), worker_running=running,
        heartbeat_at=_iso(health.get("heartbeat_at")), heartbeat_fresh=fresh,
        progress=_progress(root, state, now) if active else None,
        pending_capture_at=_iso(pending.get("captured_at")) if pending else None,
        last_success=last_success, next_at=next_at, next_kind=next_kind,
        interval_seconds=interval, retry_seconds=retry,
        repository=str(settings.get("repository", "Not configured")),
        source_roots=roots, issue=_issue(state.get("error"))),
        database=dict(label=db_label, tone=db_tone, worker_running=db_running,
            result=db_phase if db_phase in db_labels else "unknown",
            checked_at=_iso(db.get("at")), revision_at=_iso(db.get("revision_at")),
            nas_confirmed_at=db_at.isoformat() if confirmed and db_at else None,
            checkpoint=_id(db.get("checkpoint"), 32), nas_generation=_id(db.get("head"), 32),
            interval_seconds=db_interval, postgres=cfg_db.get("postgres") is True,
            sqlite_count=len(cfg_db.get("sqlite_paths", [])) if isinstance(cfg_db.get("sqlite_paths"), list) else 0,
            issue=_issue(db.get("error"))))
