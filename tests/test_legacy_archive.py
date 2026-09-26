import json
import sqlite3
import runpy
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from systematic_trading.storage.legacy_archive import archive_snapshot, read_snapshot
from test_execution_recovery import isolated_postgres


def source(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE evidence (id INTEGER PRIMARY KEY, payload TEXT, raw BLOB, value REAL)')
        db.executemany('INSERT INTO evidence VALUES (?,?,?,?)',
                       [(1, '{"quantity":"1.00000000000001"}', b'\x00\xff', 1.25),
                        (2, None, b'', None)])
        db.execute('CREATE TABLE empty (key TEXT PRIMARY KEY) WITHOUT ROWID')
    return path


def test_missing_source_never_creates_database(tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(sqlite3.OperationalError):
        read_snapshot(path)
    assert not path.exists()


def test_old_bootstrap_refuses_an_existing_ledger(tmp_path, monkeypatch):
    from systematic_trading.config import AppSettings
    from systematic_trading.storage.postgres import PostgresStore

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            assert query.startswith("SELECT 1 FROM ")
            return self

        def fetchone(self):
            return {"exists": 1}

    class ExistingStore:
        def initialize(self):
            pass

        def _connect(self):
            return Connection()

    monkeypatch.setattr(PostgresStore, "from_settings", lambda _: ExistingStore())
    script = runpy.run_path("scripts/sync_sqlite_transactional_to_postgres.py")
    with pytest.raises(ValueError, match="empty, stopped target"):
        script["sync_sqlite_transactional_state"](sqlite_database=source(tmp_path), settings=AppSettings())


def test_archive_retains_types_schema_and_exact_payload_text(tmp_path):
    _, manifest, tables = read_snapshot(source(tmp_path))
    row = json.loads(tables['evidence']['rows'][0])
    assert row == [1, '{"quantity":"1.00000000000001"}',
                   {'sqlite_blob_base64': 'AP8='}, 1.25]
    assert manifest['tables']['empty']['count'] == 0
    assert 'WITHOUT ROWID' in manifest['tables']['empty']['ddl']


def test_postgres_archive_retry_and_corruption_detection(tmp_path, isolated_postgres):
    name = 'archive_' + uuid4().hex[:12]
    with psycopg.connect(**isolated_postgres, dbname='postgres', autocommit=True) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    path = source(tmp_path)
    with psycopg.connect(**isolated_postgres, dbname=name) as db:
        db.execute(Path('deploy/postgres/migrations/002_legacy_sqlite_archive.sql').read_text())
        first = archive_snapshot(path, db)
        assert archive_snapshot(path, db) == first
        assert db.execute('SELECT count(*) FROM legacy.sqlite_rows').fetchone()[0] == 2
        db.execute("UPDATE legacy.sqlite_rows SET row_json='[]' WHERE ordinal=0")
        with pytest.raises(ValueError, match='verification failed'):
            archive_snapshot(path, db)
