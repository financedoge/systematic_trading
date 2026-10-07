from pathlib import Path
import shutil
import sys
import threading
import time

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage.nas_sync import file_hash, read_json, write_json
from systematic_trading.storage.system_backup import BackupStopped, SystemBackup, snapshot_nats


@pytest.fixture
def backup(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "source").mkdir(parents=True)
    (workspace / "source/data.txt").write_text("durable market evidence\n")
    (workspace / "source/.env").write_text("secret-must-not-be-copied")
    (workspace / "source/.env.production").write_text("another-secret")
    repository = tmp_path / "nas/repo"
    repository.parent.mkdir()
    binary = Path("var/dependencies/restic/restic.exe").resolve()
    config = dict(enabled=True, repository=str(repository), staging_root=str(tmp_path / "staging"),
        password_file="var/private/recovery.txt", restic_binary=str(binary), required_paths=["source"],
        exclude=["**/.env", "**/.env.*", "**/private/**"], command_timeout_seconds=30)
    return SystemBackup(workspace, config, AppSettings(_env_file=None))


def fake_capture(backup):
    capture = backup.stage / "capture"
    capture.mkdir(parents=True, exist_ok=True)
    (capture / "postgres.dump").write_bytes(b"fake-test-dump")
    write_json(capture / "manifest.json", {"files": {"postgres.dump": {"sha256": file_hash(capture/"postgres.dump")}}})
    pending = dict(capture=str(capture), manifest_sha256=file_hash(capture/"manifest.json"),
                   captured_at="2026-10-07T02:00:00+00:00", sources=[str(backup.workspace/"source")])
    write_json(backup.local / "pending.json", pending)
    return pending


def test_offline_is_deferred_before_capture_and_recovers_pending_generation(backup, monkeypatch):
    original = backup.repository
    backup.repository = original / "offline/child"
    monkeypatch.setattr(backup, "capture", lambda: pytest.fail("Must not capture when disconnected"))
    assert backup.once() is None
    assert backup.state["status"] == "deferred"
    assert not (backup.local / "pending.json").exists()
    backup.repository = original
    pending = fake_capture(backup)
    monkeypatch.setattr(backup, "initialize_repository", lambda: None)
    monkeypatch.setattr(backup, "publish", lambda item: "resumed" if item == pending else pytest.fail("Lost pending capture"))
    assert backup.once() == "resumed"


def test_incomplete_snapshot_does_not_replace_last_complete_and_retries(backup, monkeypatch):
    fake_capture(backup)
    backup.state.update(snapshot="prior-complete", status="complete")
    monkeypatch.setattr(backup, "initialize_repository", lambda: None)
    calls = []
    def incomplete(*args):
        calls.append(args)
        if args[0] == "backup":
            raise RuntimeError("restic exit 3: unreadable source")
        return ""
    monkeypatch.setattr(backup, "restic", incomplete)
    assert backup.once() is None
    assert backup.state["snapshot"] == "prior-complete"
    assert backup.state["status"] == "deferred"
    assert (backup.local / "pending.json").exists()
    assert not any(c[0] == "tag" for c in calls)


def test_existing_repository_without_key_cannot_be_reinitialized(backup):
    backup.repository.mkdir()
    (backup.repository / "config").write_text("existing encrypted repository")
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    with pytest.raises(RuntimeError, match="recovery key"):
        backup.initialize_repository()
    assert not backup.password.exists()


def test_pending_manifest_tampering_fails_before_upload(backup):
    pending = fake_capture(backup)
    (backup.stage / "capture/manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="identity changed"):
        backup.publish(pending)


def test_reachable_but_hung_smb_metadata_is_bounded_and_deferred(backup, monkeypatch):
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    calls = []
    def hung(args, **kwargs):
        calls.append(kwargs)
        raise TimeoutError("SMB metadata hung")
    monkeypatch.setattr(backup, "command", hung)
    assert backup.once() is None
    assert calls == [{"timeout":30}]
    assert backup.state["status"] == "deferred"
    assert not (backup.local / "pending.json").exists()


def test_nonempty_damaged_repository_is_not_reinitialized(backup):
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    backup.repository.mkdir()
    (backup.repository/"irreplaceable-data").write_bytes(b"preserve")
    with pytest.raises(RuntimeError, match="contains data"):
        backup.initialize_repository()
    assert not backup.password.exists()


def test_restore_cannot_overwrite_sources_or_accept_abbreviated_id(backup):
    with pytest.raises(ValueError, match="exact complete"):
        backup.restore_files("12345678", backup.workspace / "source")
    with pytest.raises(ValueError, match="empty target"):
        backup.restore_files("a"*64, backup.workspace / "source")
    with pytest.raises(ValueError, match="overlaps"):
        backup.restore_files("a"*64, backup.workspace / "source/new-child")


def test_staging_cannot_contain_source_or_be_inside_source(backup):
    for target in [backup.workspace, backup.workspace/"source/nested"]:
        config = dict(backup.config, staging_root=str(target))
        with pytest.raises(ValueError, match="staging"):
            SystemBackup(backup.workspace, config, backup.settings)


def test_shutdown_cancels_slow_network_child(backup):
    timer = threading.Timer(.5, backup.stop_path.touch)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(BackupStopped):
            backup.command([sys.executable, "-c", "import time; time.sleep(60)"])
    finally:
        timer.join()
    assert time.monotonic()-started < 5


def test_explicit_worker_pause_is_honored_by_automatic_supervision(backup, monkeypatch):
    import runpy
    module = runpy.run_path("scripts/system_backup.py")
    config = backup.workspace / "backup-config.json"
    write_json(config, backup.config)
    module["stop_worker"](backup.workspace, explicit=True)
    assert (backup.run_dir/"system_backup.paused").exists()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: pytest.fail("Explicit pause must suppress automatic start"))
    module["start_worker"](backup.workspace, config)


def test_real_restic_backup_readback_restore_and_incremental_catchup(backup, monkeypatch, tmp_path):
    if not backup.binary.exists():
        pytest.skip("Pinned restic binary not provisioned")
    backup.config["exclude"] = read_json(Path("config/system-backup.json"))["exclude"]
    rollback = backup.workspace / "source/var/database-sync/before-restore-test/rollback.txt"
    rollback.parent.mkdir(parents=True)
    rollback.write_text("retain divergent historical state")
    checkpoint = backup.workspace / "source/var/database-sync/checkpoints/old/redundant.txt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("routine checkpoint")
    write_json(backup.workspace / "source/var/database-sync/state.json", {"node":"old-machine-identity"})
    monkeypatch.setattr(backup, "capture", lambda: fake_capture(backup))
    first = backup.once()
    assert first, backup.state
    assert backup.state["status"] == "complete"
    assert not (backup.local / "pending.json").exists()
    target = tmp_path / "restored"
    backup.restore_files(first, target)
    assert [p.read_text() for p in target.rglob("data.txt")] == ["durable market evidence\n"]
    assert not list(target.rglob(".env*"))
    assert not list(target.rglob("recovery.txt"))
    assert len(list(target.rglob("rollback.txt"))) == 1
    assert not list(target.rglob("redundant.txt"))
    assert not list(target.rglob("state.json"))
    settings_file = next(target.rglob("runtime-settings.json"))
    saved_settings = read_json(settings_file)
    assert "postgres_port" in saved_settings["settings"]
    assert "clickhouse_password" not in saved_settings["settings"]
    assert "postgres_app_password" in saved_settings["reprovision_fields"]
    (backup.workspace / "source/data.txt").write_text("offline-change\n")
    original = backup.repository
    backup.repository = original / "offline/child"
    assert backup.once() is None
    backup.repository = original
    second = backup.once()
    assert second and second != first, backup.state
    backup.restore_files(second, tmp_path / "restored-second")
    assert [p.read_text() for p in (tmp_path/"restored-second").rglob("data.txt")] == ["offline-change\n"]
    backup.restic("check", "--read-data")


def test_queue_native_snapshot_includes_consumers_and_acks_chunks(tmp_path, monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    ack = []
    requests = []
    class Message:
        def __init__(self, data, reply="ack"):
            self.data, self.reply = data, reply
        async def respond(self, data):
            ack.append(data)
    class Subscription:
        messages = iter([Message(b"part1"), Message(b"part2"), Message(b"", "")])
        async def next_msg(self, **kwargs):
            return next(self.messages)
        async def unsubscribe(self):
            pass
    class Connection:
        async def request(self, subject, data, **kwargs):
            requests.append((subject, json.loads(data)))
            payload = dict(streams=["ST_EVENTS"], total=1) if subject.endswith("NAMES") else dict(config={"name":"ST_EVENTS"}, state={"messages":2})
            return SimpleNamespace(data=json.dumps(payload).encode())
        def new_inbox(self):
            return "_INBOX.test"
        async def subscribe(self, *args, **kwargs):
            return Subscription()
        async def close(self):
            pass
    async def connect(**kwargs):
        return Connection()
    monkeypatch.setattr("nats.connect", connect)
    result = asyncio.run(snapshot_nats("nats://localhost:4222", tmp_path))
    assert (tmp_path/"ST_EVENTS.snapshot").read_bytes() == b"part1part2"
    assert requests[1][1]["no_consumers"] is False
    assert requests[1][1]["jsck"] is True and ack == [b"", b""]
    assert result["ST_EVENTS"]["state"]["messages"] == 2
