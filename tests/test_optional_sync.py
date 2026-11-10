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


def test_native_handoff_checks_publication_heads_only_after_restore(tmp_path,monkeypatch):
    from systematic_trading.storage import dependencies
    a,b=node(tmp_path,'source'),node(tmp_path,'destination')
    insert(a,'audited-event');a.prepare()
    directory,manifest=b.checkpoint()
    b.databases.settings=b.databases.settings.model_copy(update={'market_data_store_backend':'parquet'})
    checks=[]
    monkeypatch.setattr(dependencies,'verify_dependencies',
        lambda settings,receipt,*,verify_publications=True: checks.append(verify_publications))
    assert b.transfer(directory,manifest,restore=True)=='restored_newer_remote'
    assert checks==[False,False,True]
    assert values(b)==['audited-event']


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


def test_recovery_only_startup_never_snapshots_or_accesses_nas(tmp_path, monkeypatch):
    a = node(tmp_path, "recovery")
    a.config["recovery_only"] = True
    def forbidden(*args, **kwargs):
        pytest.fail("Recovery-only startup attempted backup or NAS IO")
    monkeypatch.setattr(a, "synchronize", forbidden)
    monkeypatch.setattr(a, "checkpoint", forbidden)
    monkeypatch.setattr(a, "check_connection", forbidden)
    assert a.prepare() == "local_ready"
    assert a.release() == "local_ready"
    a.save(phase="restoring")
    with pytest.raises(SyncConflict, match="Interrupted restore"):
        a.prepare()
    with pytest.raises(SyncConflict, match="Interrupted restore"):
        a.release()


def test_recovery_only_cli_prepare_allows_running_services_and_keeps_worker_pid(tmp_path, monkeypatch):
    main = load_cli(tmp_path, monkeypatch, 'prepare')
    path = tmp_path/'config.json'
    write_json(path, dict(read_json(path), optional=True, recovery_only=True, conflict_policy='latest_snapshot'))
    run = tmp_path/'var/run'
    run.mkdir(parents=True)
    (run/'database_sync.pid').write_text('123')
    (run/'database_sync.stop').touch()
    main.__globals__['assert_services_stopped'] = lambda: pytest.fail('Read-only startup must allow running services')
    assert main() == 0
    assert (run/'database_sync.pid').read_text() == '123'
    assert not (run/'database_sync.stop').exists()


def test_snapshot_retention_is_bounded_and_legacy_owner_does_not_block(tmp_path):
    a = node(tmp_path, "a")
    insert(a, "start")
    a.prepare()
    write_json(a.root/"owner.json", {"node":"legacy", "host":"other-laptop"})
    for i in range(4):
        insert(a, str(i))
        assert a.backup() == "published_local"
    assert len(list((a.local/"checkpoints").iterdir())) == 2


def test_retiring_sql_requires_recovery_proof_and_preserves_unknown_payloads(tmp_path):
    a = node(tmp_path, 'retire')
    insert(a, 'durable')
    a.prepare()
    generation = a.head()
    a.config['recovery_only'] = True
    proof = dict(passed=True, scope='recovery-v1', snapshot='a'*64,
                 repository=str(a.root/'full-system-restic'))
    with pytest.raises(SyncConflict, match='verified replacement'):
        a.retire_generations(dict(proof, passed=False), 'b'*64)
    assert a.head() == generation
    unknown = a.root/'snapshots'/('e'*32)
    unknown.mkdir()
    (unknown/'unrecognized.data').write_bytes(b'preserve')
    with a.local_lock(), a.lock():
        result = a.retire_generations(proof, 'b'*64)
    assert result['removed'] == 1 and result['removed_bytes'] > 0
    assert not (a.root/'latest.json').exists()
    assert read_json(a.root/'recovery.json')['snapshot'] == 'b'*64
    assert (unknown/'unrecognized.data').read_bytes() == b'preserve'


def test_nas_retains_only_verified_current_generation(tmp_path):
    a = node(tmp_path, 'bounded')
    a.config['retain_generations'] = 1
    insert(a, 'first')
    a.prepare()
    old = a.head()
    insert(a, 'second')
    assert a.backup() == 'published_local'
    assert not (a.root/'snapshots'/old).exists()
    assert [p.name for p in (a.root/'snapshots').iterdir()] == [a.head()]
    b = node(tmp_path, 'restore-bounded')
    assert b.prepare() == 'restored_newer_remote'
    assert values(b) == ['first', 'second']


def test_failed_upload_keeps_previous_nas_generation(tmp_path, monkeypatch):
    a = node(tmp_path, 'failure')
    a.config['retain_generations'] = 1
    insert(a, 'first'); a.prepare()
    previous = a.head()
    insert(a, 'second')
    def fail(*args):
        raise OSError('disconnected')
    monkeypatch.setattr('systematic_trading.storage.optional_sync.shutil.copyfile', fail)
    assert a.backup() == 'local_only'
    assert a.head() == previous
    assert (a.root/'snapshots'/previous/'sqlite-0.db').exists()


def test_retention_preserves_unknown_content_and_rejects_wrong_head(tmp_path):
    a = node(tmp_path, 'unknown')
    a.config['retain_generations'] = 1
    insert(a, 'first'); a.prepare()
    unknown = a.root/'snapshots'/('a'*32)
    unknown.mkdir(); (unknown/'unrelated.txt').write_text('preserve')
    with pytest.raises(SyncConflict, match='head changed'):
        a.prune_generations('b'*32)
    with a.lock():
        a.prune_generations(a.head())
    assert (unknown/'unrelated.txt').read_text() == 'preserve'


def test_verified_sqlite_retirement_accepts_frozen_peer_but_rejects_new_edits(tmp_path):
    from systematic_trading.storage.nas_sync import LocalDatabases
    from systematic_trading.config import AppSettings
    old = node(tmp_path, "old")
    insert(old, "already archived in Postgres")
    old.prepare()
    fingerprint = old.state["fingerprints"]["sqlite-0.db"]
    target = tmp_path / "retired"
    target.mkdir()
    config = dict(old.config, sqlite_paths=[], retired_sqlite_paths=["data.db"],
                  retired_sqlite_fingerprints={"sqlite-0.db":fingerprint})
    new = OptionalNasSync(target, config, LocalDatabases(target, config, AppSettings(_env_file=None)))
    manifest = new.download(old.head(), target/"verified")
    assert manifest["layout"]["sqlite_paths"] == [] and manifest["fingerprints"] == {}
    assert (target/"verified/sqlite-0.db").exists()  # Old bytes verified, not silently discarded.
    insert(old, "unarchived old-PC change")
    old.backup()
    with pytest.raises(SyncConflict, match="Retired SQLite changed"):
        new.download(old.head(), target/"rejected")
