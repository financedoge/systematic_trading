import sqlite3

import pytest

from systematic_trading.storage.optional_sync import OptionalNasSync
from systematic_trading.storage.nas_sync import SyncConflict, read_json, write_json
from test_nas_sync import make_sync, insert, values, load_cli


def node(tmp_path, name):
    strict = make_sync(tmp_path, name)
    return OptionalNasSync(strict.workspace, strict.config, strict.databases)


def test_offline_start_stop_and_reconnect_preserve_local_edits(tmp_path):
    a = node(tmp_path, "a")
    insert(a, "approval")
    connected = a.root
    a.root = tmp_path / "unavailable" / "nas"
    assert a.prepare() == "local_only"
    a.guard()
    insert(a, "offline-fill")
    assert a.release() == "local_only" and a.state["phase"] == "clean"
    checkpoint = a.local / "checkpoints" / a.state["checkpoint"]
    with sqlite3.connect(checkpoint / "sqlite-0.db") as db:
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 2
    a.root = connected
    assert a.prepare() == "published_local"
    b = node(tmp_path, "b")
    assert b.prepare() == "restored_newer_remote"
    assert values(b) == ["approval", "offline-fill"]


def test_latest_revision_wins_and_unchanged_backups_do_not_become_newer(tmp_path):
    a, b = node(tmp_path, "a"), node(tmp_path, "b")
    insert(a, "a")
    a.prepare()
    b.prepare()
    revision = a.state["revision_at"]
    insert(b, "b")
    b.release()
    head = b.head()
    assert a.backup() == "newer_remote_pending_restart"
    assert a.head() == head and a.state["revision_at"] == revision
    assert values(a) == ["a"]  # A running database is never replaced.
    a.prepare()
    assert values(a) == ["a", "b"] and list(a.local.glob("before-restore-*"))
    insert(a, "newest")
    assert a.backup() == "published_local"
    b.prepare()
    assert values(b) == ["a", "b", "newest"]


def test_corrupt_remote_and_busy_nas_do_not_block_local_services(tmp_path):
    a, b = node(tmp_path, "a"), node(tmp_path, "b")
    insert(a, "remote")
    a.prepare()
    (a.root / "snapshots" / a.head() / "sqlite-0.db").write_bytes(b"bad")
    assert b.prepare() == "local_only"
    assert "checksum" in b.state["sync_error"]
    b.guard()
    assert not (b.workspace / "data.db").exists()
    (a.root / "operation.lock").mkdir()
    assert a.backup() == "local_only"
    assert values(a) == ["remote"]


def test_partial_restore_still_blocks_start_and_retains_rollback(tmp_path, monkeypatch):
    a, b = node(tmp_path, "a"), node(tmp_path, "b")
    insert(a, "remote")
    a.prepare()
    def fail(*args):
        raise RuntimeError("partial database restore")
    monkeypatch.setattr(b.databases, "restore", fail)
    with pytest.raises(SyncConflict, match="Interrupted restore"):
        b.prepare()
    assert list(b.local.glob("before-restore-*"))
    with pytest.raises(SyncConflict, match="Interrupted restore"):
        b.guard()


def test_cli_optional_prepare_and_guard_without_nas_or_worker(tmp_path, monkeypatch):
    main = load_cli(tmp_path, monkeypatch, "prepare")
    path = tmp_path / "config.json"
    write_json(path, dict(read_json(path), optional=True, conflict_policy="latest_snapshot", root=str(tmp_path/"offline"/"nas")))
    assert main() == 0
    monkeypatch.setattr("sys.argv", ["sync_databases.py", "guard", "--config", str(path)])
    assert main() == 0
    monkeypatch.setattr("sys.argv", ["sync_databases.py", "release", "--config", str(path)])
    assert main() == 0


def test_snapshot_retention_is_bounded_and_legacy_owner_does_not_block(tmp_path):
    a = node(tmp_path, "a")
    insert(a, "start")
    a.prepare()
    write_json(a.root/"owner.json", {"node":"legacy", "host":"other-laptop"})
    for i in range(4):
        insert(a, str(i))
        assert a.backup() == "published_local"
    assert len(list((a.local/"checkpoints").iterdir())) == 2
