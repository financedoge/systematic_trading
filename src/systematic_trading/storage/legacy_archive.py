"""Lossless SQLite evidence archive, separate from the newer operational ledger."""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from psycopg.types.json import Jsonb


def _encode(value):
    if isinstance(value, bytes):
        return {"sqlite_blob_base64": base64.b64encode(value).decode("ascii")}
    return value


def read_snapshot(path: Path):
    """Read one consistent transaction; canonicalize without changing stored text."""
    tables = {}
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        for kind, name, _, ddl in schema:
            if kind != "table":
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [r[1] for r in db.execute(f"PRAGMA table_info({quoted})")]
            rows = sorted(json.dumps([_encode(v) for v in row], ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False)
                          for row in db.execute(f"SELECT * FROM {quoted}"))
            digest = hashlib.sha256()
            for row in rows:
                digest.update(row.encode() + b"\n")
            tables[name] = {"columns": columns, "ddl": ddl, "count": len(rows),
                            "sha256": digest.hexdigest(), "rows": rows}
    manifest = {"format_version": 1, "schema": schema,
                "tables": {k: {a: b for a, b in v.items() if a != "rows"} for k, v in tables.items()}}
    snapshot_id = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return snapshot_id, manifest, tables


def archive_snapshot(path: Path, connection):
    """Insert and read back every row in one transaction; safe to retry."""
    snapshot_id, manifest, tables = read_snapshot(path)
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("sqlite-archive",))
        existing = connection.execute("SELECT manifest FROM legacy.sqlite_snapshots WHERE snapshot_id=%s",
                                      (snapshot_id,)).fetchone()
        if not existing:
            connection.execute("INSERT INTO legacy.sqlite_snapshots(snapshot_id,source_name,manifest) VALUES (%s,%s,%s)",
                               (snapshot_id, path.name, Jsonb(manifest)))
            with connection.cursor().copy("COPY legacy.sqlite_rows(snapshot_id,table_name,ordinal,row_json) FROM STDIN") as copy:
                for name, table in tables.items():
                    for index, row in enumerate(table["rows"]):
                        copy.write_row((snapshot_id, name, index, row))
        stored = connection.execute("SELECT manifest FROM legacy.sqlite_snapshots WHERE snapshot_id=%s",
                                    (snapshot_id,)).fetchone()[0]
        if stored != json.loads(json.dumps(manifest)):
            raise ValueError("Archive manifest mismatch")
        for name, table in tables.items():
            rows = connection.execute("SELECT row_json FROM legacy.sqlite_rows WHERE snapshot_id=%s AND table_name=%s ORDER BY ordinal",
                                      (snapshot_id, name)).fetchall()
            if [r[0] for r in rows] != table["rows"]:
                raise ValueError(f"Archive verification failed: {name}")
        count = connection.execute("SELECT count(*) FROM legacy.sqlite_rows WHERE snapshot_id=%s", (snapshot_id,)).fetchone()[0]
        if count != sum(t["count"] for t in tables.values()):
            raise ValueError("Archive total row count mismatch")
    return {"snapshot_id": snapshot_id, "verified": True, "tables": manifest["tables"]}
