import json
from pathlib import Path
import sqlite3

import psycopg
import pytest
from psycopg import sql

from systematic_trading.config import AppSettings
from systematic_trading.storage.nas_sync import LocalDatabases, NasSync, SyncConflict, read_json, write_json
from test_execution_recovery import isolated_postgres


def make_sync(tmp_path, node, postgres=False, settings=None):
    workspace = tmp_path / node
    workspace.mkdir(exist_ok=True)
    config = {"root": str(tmp_path / "nas"), "sqlite_paths": ["data.db"], "postgres": postgres,
              "postgres_bin": __import__("os").environ.get("ST_TEST_POSTGRES_BIN", "")}
    return NasSync(workspace, config, LocalDatabases(workspace, config, settings or AppSettings(_env_file=None)))


def insert(sync, value):
    with sqlite3.connect(sync.workspace / "data.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS audit (value TEXT)")
        db.execute("INSERT INTO audit VALUES (?)", (value,))


def values(sync):
    with sqlite3.connect(sync.workspace / "data.db") as db:
        return [r[0] for r in db.execute("SELECT value FROM audit")]


def test_two_pc_roundtrip_and_competing_owner(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "approval")
    a.prepare()
    with pytest.raises(SyncConflict, match="owned"):
        b.prepare()
    insert(a, "fill")
    a.backup()
    a.release()
    b.prepare()
    assert values(b) == ["approval", "fill"]
    insert(b, "reconciliation")
    b.release()
    a.prepare()
    assert values(a) == ["approval", "fill", "reconciliation"]
    assert list(a.local.glob("before-restore-*"))


def test_preflight_preserves_active_and_clean_handoffs(tmp_path):
    a = make_sync(tmp_path, "a")
    insert(a, "audit")
    a.prepare()
    for phase in ("active", "clean"):
        if phase == "clean":
            a.release()
        before = (dict(a.state), a.owner(), a.head())
        a.preflight()
        assert (a.state, a.owner(), a.head()) == before
        assert not (a.root / "operation.lock").exists()
        assert values(a) == ["audit"]


def test_preflight_rejects_other_owner_and_unavailable_share(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "audit")
    a.prepare()
    a.release()
    b.prepare()
    with pytest.raises(SyncConflict, match="ownership/history changed"):
        a.preflight()
    owner = b.owner()
    b.root = tmp_path / "disconnected" / "share"
    with pytest.raises(SyncConflict, match="NAS unavailable"):
        b.preflight()
    assert a.owner() == owner
    assert not b.root.exists()


def test_offline_edits_preserved(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "approval")
    a.prepare()
    a.release()
    b.prepare()
    b.release()
    insert(a, "offline")
    with pytest.raises(SyncConflict, match="changed after handoff"):
        a.prepare()
    assert values(a) == ["approval", "offline"]


def test_unmanaged_local_database_not_overwritten(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "remote")
    a.prepare()
    a.release()
    insert(b, "local")
    with pytest.raises(SyncConflict, match="Unmanaged"):
        b.prepare()
    assert values(b) == ["local"]


def test_corrupt_snapshot_blocks_restore(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "audit")
    a.prepare()
    a.release()
    snapshot = a.root / "snapshots" / a.head()
    (snapshot / "sqlite-0.db").write_bytes(b"corrupt")
    with pytest.raises(SyncConflict, match="checksum"):
        b.prepare()
    assert not (b.workspace / "data.db").exists()
    assert b.owner() is None


def test_failed_upload_preserves_head_and_ownership(tmp_path, monkeypatch):
    a = make_sync(tmp_path, "a")
    insert(a, "audit")
    a.prepare()
    head = a.head()
    def fail(*args):
        raise OSError("NAS unavailable")
    monkeypatch.setattr("systematic_trading.storage.nas_sync.shutil.copyfile", fail)
    with pytest.raises(OSError):
        a.release()
    assert a.head() == head
    assert a.owner()["node"] == a.state["node"]
    assert a.state["phase"] == "active"


def test_interrupted_restore_stays_blocked(tmp_path, monkeypatch):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    insert(a, "audit")
    a.prepare()
    a.release()
    def fail(*args):
        raise RuntimeError("restore failed")
    monkeypatch.setattr(b.databases, "restore", fail)
    with pytest.raises(RuntimeError):
        b.prepare()
    assert b.state["phase"] == "restoring"
    with pytest.raises(SyncConflict, match="Interrupted restore"):
        b.prepare()
    with pytest.raises(SyncConflict, match="incomplete restore"):
        b.backup()


def test_wal_commits_are_backed_up(tmp_path):
    a = make_sync(tmp_path, "a")
    with sqlite3.connect(a.workspace / "data.db") as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE audit (value TEXT)")
        db.execute("INSERT INTO audit VALUES ('committed')")
        db.commit()
        a.prepare()
        backup = a.root / "snapshots" / a.head() / "sqlite-0.db"
        with sqlite3.connect(backup) as copy:
            assert copy.execute("SELECT value FROM audit").fetchone() == ("committed",)


def test_operation_lock_and_missing_share_fail_closed(tmp_path):
    a = make_sync(tmp_path, "a")
    a.root.mkdir()
    (a.root / "operation.lock").mkdir()
    with pytest.raises(SyncConflict, match="operation.lock"):
        a.prepare()
    a.root = tmp_path / "absent-share" / "nas"
    with pytest.raises(SyncConflict, match="NAS unavailable"):
        a.prepare()
    assert not a.root.parent.exists()


def test_remote_history_change_blocks_publish(tmp_path):
    a = make_sync(tmp_path, "a")
    a.prepare()
    write_json(a.root / "latest.json", "a" * 32)
    with pytest.raises(SyncConflict, match="history changed"):
        a.backup()


def test_missing_nas_head_is_not_reseeded_from_old_pc(tmp_path):
    a = make_sync(tmp_path, "a")
    a.prepare()
    a.release()
    (a.root / "latest.json").unlink()
    with pytest.raises(SyncConflict, match="history is missing"):
        a.prepare()


def test_layout_change_does_not_drop_databases_from_backups(tmp_path):
    a = make_sync(tmp_path, "a")
    a.prepare()
    a.databases.config["sqlite_paths"] = ["different.db"]
    with pytest.raises(SyncConflict, match="layout changed"):
        a.backup()


def test_sqlite_version_change_is_a_local_conflict(tmp_path):
    a = make_sync(tmp_path, "a")
    insert(a, "audit")
    a.prepare()
    a.release()
    with sqlite3.connect(a.workspace / "data.db") as db:
        db.execute("PRAGMA user_version=42")
    with pytest.raises(SyncConflict, match="changed after handoff"):
        a.prepare()


def test_manifest_path_escape_rejected(tmp_path):
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    a.prepare()
    a.release()
    manifest_path = a.root / "snapshots" / a.head() / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["../escape"] = "bad"
    write_json(manifest_path, manifest)
    with pytest.raises(SyncConflict, match="Unexpected"):
        b.prepare()


def load_cli(tmp_path, monkeypatch, action):
    import runpy
    module = runpy.run_path("scripts/sync_databases.py", run_name="nas_sync_test")
    main = module["main"]
    main.__globals__["ROOT"] = tmp_path
    monkeypatch.setenv("ST_DATABASE_PATH", str(tmp_path / "data.db"))
    config = tmp_path / "config.json"
    write_json(config, {"enabled": True, "root": str(tmp_path / "nas"), "postgres": False,
                        "sqlite_paths": ["data.db"], "interval_seconds": 30})
    monkeypatch.setattr("sys.argv", ["sync_databases.py", action, "--config", str(config)])
    # main changes cwd; have pytest restore it after the test.
    monkeypatch.chdir(tmp_path)
    return main


def test_cli_prepare_clears_old_stop_signal(tmp_path, monkeypatch):
    main = load_cli(tmp_path, monkeypatch, "prepare")
    run = tmp_path / "var/run"
    run.mkdir(parents=True)
    (run / "database_sync.stop").touch()
    assert main() == 0
    assert not (run / "database_sync.stop").exists()


def test_worker_honors_stop_already_requested(tmp_path, monkeypatch):
    main = load_cli(tmp_path, monkeypatch, "worker")
    run = tmp_path / "var/run"
    run.mkdir(parents=True)
    (run / "database_sync.stop").touch()
    assert main() == 0
    assert not (run / "database_sync.pid").exists()
    assert (run / "database_sync.stop").exists()


def test_cli_refuses_handoff_with_running_service(tmp_path, monkeypatch):
    import os
    main = load_cli(tmp_path, monkeypatch, "prepare")
    run = tmp_path / "var/run"
    run.mkdir(parents=True)
    (run / "operator_dashboard.pid").write_text(str(os.getpid()))
    with pytest.raises(SyncConflict, match="Stop local services"):
        main()


def test_real_postgres_handoff_and_restore_rollback(tmp_path, isolated_postgres):
    cfg = isolated_postgres
    names = ["nas_a", "nas_b"]
    with psycopg.connect(**cfg, dbname="postgres", autocommit=True) as db:
        db.execute("CREATE ROLE nas_owner NOLOGIN")
        db.execute(sql.SQL("CREATE ROLE nas_migrator LOGIN PASSWORD {}").format(sql.Literal(cfg["password"])))
        db.execute("CREATE ROLE nas_app NOLOGIN")
        db.execute("GRANT nas_owner TO nas_migrator")
        for name in names:
            db.execute(sql.SQL("CREATE DATABASE {} OWNER nas_owner").format(sql.Identifier(name)))
    settings = [AppSettings(_env_file=None, postgres_host=cfg["host"], postgres_port=cfg["port"],
                            postgres_database=name, postgres_migrator_user="nas_migrator",
                            postgres_migrator_password=cfg["password"], postgres_owner_role="nas_owner") for name in names]
    a, b = [make_sync(tmp_path, node, True, setting) for node, setting in zip(["a", "b"], settings)]
    # Real PCs have identical database names on different servers. Use a shared
    # logical layout here while the fixture uses two databases on one server.
    b.databases.settings = settings[1]
    with a.databases.connection() as db:
        db.execute("CREATE TABLE audit (id integer PRIMARY KEY, value text)")
        db.execute("INSERT INTO audit VALUES (1, 'approved')")
        db.execute("GRANT SELECT ON audit TO nas_app")
    a.prepare()
    first = a.state["fingerprints"]
    a.backup()
    assert a.state["fingerprints"] == first
    a.release()
    manifest_path = a.root / "snapshots" / a.head() / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["layout"]["database"] = "nas_b"
    write_json(manifest_path, manifest)
    b.prepare()
    with b.databases.connection() as db:
        assert db.execute("SELECT value FROM audit").fetchone() == ("approved",)
        assert db.execute("SELECT has_table_privilege('nas_app', 'audit', 'SELECT')").fetchone() == (True,)
        db.execute("CREATE TABLE obsolete (id integer)")
    b.databases.restore(manifest_path.parent, manifest)
    with b.databases.connection() as db:
        assert db.execute("SELECT to_regclass('public.obsolete')").fetchone() == (None,)
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "postgres.sql").write_text("DROP TABLE audit; SELECT no_such_column;", encoding="utf-8")
    with pytest.raises(RuntimeError, match="psql failed"):
        b.databases.restore(bad, {"files": {"postgres.sql": "unused"}})
    with b.databases.connection() as db:
        assert db.execute("SELECT value FROM audit").fetchone() == ("approved",)


def test_real_nas_handoff(tmp_path):
    import os
    from uuid import uuid4
    share = os.environ.get("ST_TEST_NAS_ROOT")
    if not share:
        pytest.skip("Set ST_TEST_NAS_ROOT for an actual SMB handoff smoke test")
    a, b = make_sync(tmp_path, "a"), make_sync(tmp_path, "b")
    root = Path(share) / ("systematic-trading-sync-smoke-" + uuid4().hex)
    a.root = b.root = root
    insert(a, "SMB smoke: no production data")
    a.prepare()
    a.release()
    b.prepare()
    assert values(b) == ["SMB smoke: no production data"]
    b.release()
    # Retain this tiny isolated test artifact; never delete existing NAS content.
    print(f"NAS smoke evidence: {root}")
