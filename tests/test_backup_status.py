from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from systematic_trading.storage import backup_status as module


NOW = datetime(2026, 10, 7, 4, 0, tzinfo=UTC)
SNAPSHOT = "a" * 64


def write(root, path, data):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data), encoding="utf8")


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_pid_is_running", lambda pid: pid == 123)
    write(tmp_path, "config/system-backup.json", dict(enabled=True,
        repository=r"\\unavailable-nas\backup", interval_seconds=3600, retry_seconds=300,
        required_paths=["src", "var"], password_file="var/private/never-read.txt"))
    write(tmp_path, "config/database-sync.json", dict(enabled=True, postgres=True,
        sqlite_paths=[], interval_seconds=300))
    write(tmp_path, "var/run/system_backup.health.json", dict(heartbeat_at=NOW.isoformat()))
    write(tmp_path, "var/run/system_backup.pid", 123)
    write(tmp_path, "var/run/database_sync.pid", 123)
    write(tmp_path, "var/run/system_backup.state.json", dict(status="complete", at=NOW.isoformat(),
        completed_at=NOW.isoformat(), captured_at=(NOW-timedelta(minutes=40)).isoformat(),
        snapshot=SNAPSHOT, summary=dict(backup_end=NOW.isoformat(),
            total_bytes_processed=63_000_000_000, total_files_processed=210_000, data_added_packed=22_000_000_000)))
    write(tmp_path, "var/run/database_sync.state.json", dict(ok=True, status="published_local",
        at=NOW.timestamp(), revision_at=NOW.isoformat(), head="c"*32, checkpoint="d"*32))
    return tmp_path


def update(root, **fields):
    path = "var/run/system_backup.state.json"
    state = json.loads((root/path).read_text())
    state.update(fields)
    write(root, path, state)


def progress_log(root, value, *, modified=NOW):
    path = root / "var/system-backup/command.stdout.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('x'*70000 + '\n' + json.dumps(value) + '\n{"partial":', encoding="utf8")
    os.utime(path, (modified.timestamp(), modified.timestamp()))


def test_complete_status_has_distinct_recovery_point_and_next_run(backup_root):
    result = module.backup_status(backup_root, now=NOW)
    full, db = result["full"], result["database"]
    assert full["status"] == "complete"
    assert full["stage"] == 4
    assert full["last_success"]["bytes_processed"] == 63_000_000_000
    assert full["next_at"] == (NOW + timedelta(minutes=20)).isoformat()
    assert full["progress"] is None
    assert db["nas_confirmed_at"] == NOW.isoformat()
    assert db["sqlite_count"] == 0


@pytest.mark.parametrize("phase,stage", [("capturing_postgres", 1), ("copying_clickhouse", 1), ("verifying", 3)])
def test_current_phase_never_uses_previous_upload_progress(backup_root, phase, stage):
    update(backup_root, status=phase)
    progress_log(backup_root, dict(message_type="status", bytes_done=100, total_bytes=100))
    full = module.backup_status(backup_root, now=NOW)["full"]
    assert full["stage"] == stage
    assert full["progress"] is None
    assert full["last_success"]["snapshot"] == SNAPSHOT


def test_candidate_summary_is_not_attached_to_old_completed_snapshot(backup_root):
    update(backup_root, status="verifying", summary=dict(backup_end=(NOW+timedelta(minutes=1)).isoformat(),
        total_bytes_processed=999, data_added_packed=222))
    full = module.backup_status(backup_root, now=NOW)["full"]
    assert full["last_success"]["bytes_processed"] is None
    assert full["last_success"]["snapshot"] == SNAPSHOT


def test_live_progress_reads_bounded_tail_and_omits_file_names(backup_root):
    update(backup_root, status="uploading")
    progress_log(backup_root, dict(message_type="status", bytes_done=25, total_bytes=100,
        files_done=8, current_files=["private-sensitive-file"], seconds_elapsed=12))
    result = module.backup_status(backup_root, now=NOW)
    assert result["full"]["progress"]["percent"] == 25
    assert "private-sensitive-file" not in json.dumps(result)
    assert not result["full"]["progress"]["stale"]


@pytest.mark.parametrize("old", [True, False])
def test_reused_command_log_and_summary_do_not_claim_upload_progress(backup_root, old):
    update(backup_root, status="uploading")
    value = dict(message_type="status" if old else "summary", bytes_done=100, total_bytes=100)
    progress_log(backup_root, value, modified=NOW-timedelta(seconds=1) if old else NOW)
    assert module.backup_status(backup_root, now=NOW)["full"]["progress"] is None


def test_stalled_progress_is_labelled_stale(backup_root):
    update(backup_root, status="uploading", at=(NOW-timedelta(minutes=5)).isoformat())
    progress_log(backup_root, dict(message_type="status", bytes_done=10, total_bytes=100),
                 modified=NOW-timedelta(minutes=2))
    assert module.backup_status(backup_root, now=NOW)["full"]["progress"]["stale"]


def test_worker_stopped_or_heartbeat_lost_cannot_show_active_progress(backup_root):
    update(backup_root, status="uploading")
    progress_log(backup_root, dict(message_type="status", bytes_done=20, total_bytes=100))
    write(backup_root, "var/run/system_backup.health.json", dict(heartbeat_at=(NOW-timedelta(minutes=6)).isoformat()))
    full = module.backup_status(backup_root, now=NOW)["full"]
    assert (full["status"], full["progress"], full["stage"]) == ("stale", None, None)
    (backup_root/"var/run/system_backup.pid").unlink()
    full = module.backup_status(backup_root, now=NOW)["full"]
    assert full["status"] == "stopped"
    assert full["last_success"]["snapshot"] == SNAPSHOT
    assert full["next_at"] is None


def test_offline_retry_uses_retained_capture_without_reading_nas_or_secrets(backup_root, monkeypatch):
    update(backup_root, status="deferred", error="TimeoutError: postgresql://user:secret@nas")
    write(backup_root, "var/system-backup/pending.json", dict(captured_at=NOW.isoformat(), capture=r"\\nas\never-read"))
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert not str(path).startswith("\\\\")
        assert "private" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = module.backup_status(backup_root, now=NOW)
    assert result["full"]["next_at"] == (NOW+timedelta(minutes=5)).isoformat()
    assert result["full"]["pending_capture_at"] == NOW.isoformat()
    assert "secret" not in json.dumps(result)
    assert "password_file" not in json.dumps(result)


@pytest.mark.parametrize("status", ["local_only", "newer_remote_pending_restart"])
def test_database_pending_is_never_current_even_with_previous_head(backup_root, status):
    write(backup_root, "var/run/database_sync.state.json", dict(status=status,
        ok=True, head="c"*32, at=NOW.timestamp()))
    db = module.backup_status(backup_root, now=NOW)["database"]
    assert db["nas_confirmed_at"] is None
    assert db["tone"] == "warning"


@pytest.mark.parametrize("data", ['{"status":', '[]', '{"status": {}}'])
def test_unreadable_or_invalid_status_is_unavailable(backup_root, data):
    (backup_root/"var/run/system_backup.state.json").write_text(data)
    assert module.backup_status(backup_root, now=NOW)["full"]["status"] == "unknown"


def test_disabled_and_explicit_pause_do_not_promise_retry(backup_root):
    (backup_root/"var/run/system_backup.paused").touch()
    full = module.backup_status(backup_root, now=NOW)["full"]
    assert full["status"] == "paused" and full["next_at"] is None
    write(backup_root, "config/system-backup.json", dict(enabled=False))
    assert module.backup_status(backup_root, now=NOW)["full"]["status"] == "disabled"


def test_backup_endpoint_and_system_page(backup_root, monkeypatch):
    from systematic_trading.web import platform
    monkeypatch.setattr(platform, "REPO_ROOT", backup_root)
    app = FastAPI()
    app.include_router(platform.router)
    with TestClient(app) as client:
        result = client.get("/api/v1/platform/backups")
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["full"]["last_success"]["snapshot"] == SNAPSHOT
        html = client.get("/platform").text
        assert html.index('id="backup-panel"') < html.index('class="layout"')
        assert "/api/v1/platform/backups" in html
        assert html.count('id="backup-panel"') == 1


def test_backup_panel_js_transitions_and_poll_failure():
    from systematic_trading.web.backup_panel import BACKUP_PANEL_HTML
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for UI behavior checks")
    result = subprocess.run([node, str(Path(__file__).with_name("backup_panel_checks.cjs"))],
        input=BACKUP_PANEL_HTML, text=True, encoding="utf8", capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
