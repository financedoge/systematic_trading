"""Conservative single-writer handoff through immutable NAS snapshots.

Databases always run on local disks. No mtime-based merging, expiring leases,
credential copying, or automatic takeover of an unreachable workstation.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from uuid import uuid4

import psycopg

from systematic_trading.config import AppSettings


class SyncConflict(RuntimeError):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def file_hash(path: Path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sqlite_snapshot(source: Path, destination: Path):
    deadline = time.monotonic() + 120

    def progress(*_):
        if time.monotonic() > deadline:
            raise TimeoutError("SQLite backup exceeded 120 seconds")

    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst, pages=1024, progress=progress)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SyncConflict("SQLite integrity check failed")


def sqlite_fingerprint(path: Path):
    digest = hashlib.sha256()
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for pragma in ("user_version", "application_id"):
            digest.update(f"{pragma}={db.execute('PRAGMA ' + pragma).fetchone()[0]}\n".encode())
        for line in db.iterdump():
            digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def postgres_fingerprint(path: Path):
    # PG17+ random psql restriction tokens change on every dump. Everything else,
    # including grants, schema and rows, participates in conflict detection.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line in stream:
            if line.startswith((b"\\restrict ", b"\\unrestrict ")):
                continue
            digest.update(line)
    return digest.hexdigest()


class LocalDatabases:
    def __init__(self, workspace: Path, config: dict, settings: AppSettings):
        self.workspace, self.config, self.settings = workspace, config, settings
        self.sqlite_paths = []
        for value in config["sqlite_paths"]:
            path = (workspace / value).resolve()
            if not path.is_relative_to(workspace.resolve()):
                raise ValueError("SQLite paths must be inside the workspace")
            self.sqlite_paths.append(path)
        if len(set(self.sqlite_paths)) != len(self.sqlite_paths):
            raise ValueError("Duplicate SQLite paths")
        if config["postgres"] and settings.postgres_host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("NAS handoff only supports a local PostgreSQL server")

    @property
    def layout(self):
        return {"postgres": self.config["postgres"], "sqlite_paths": self.config["sqlite_paths"],
                "database": self.settings.postgres_database if self.config["postgres"] else None}

    def pg_env(self):
        s = self.settings
        env = os.environ.copy()
        env.update(PGHOST=s.postgres_host, PGPORT=str(s.postgres_port), PGDATABASE=s.postgres_database,
                   PGUSER=s.postgres_migrator_user, PGSSLMODE=s.postgres_sslmode,
                   PGCONNECT_TIMEOUT="10", PGAPPNAME="systematic-trading-nas-sync")
        password = s.postgres_migrator_password or s.migrator_postgre_db_password
        if password:
            env["PGPASSWORD"] = password
        role = s.postgres_owner_role
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", role):
            raise ValueError("Invalid PostgreSQL owner role")
        env["PGOPTIONS"] = f"-c role={role}"
        return env

    def pg(self, program: str, *args):
        configured = self.config.get("postgres_bin")
        binary = str(Path(configured) / program) if configured else shutil.which(program)
        if not binary and os.name == "nt":
            candidates = list(Path("C:/Program Files/PostgreSQL").glob(f"*/bin/{program}.exe"))
            if candidates:
                binary = str(sorted(candidates, key=lambda p: int(p.parents[1].name))[-1])
        if not binary:
            raise RuntimeError(f"Install PostgreSQL client tools or set postgres_bin ({program} missing)")
        result = subprocess.run([binary, *map(str, args)], env=self.pg_env(), capture_output=True,
                                timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            # Do not leak SQL payloads or credentials through tool stderr.
            raise RuntimeError(f"{program} failed (exit {result.returncode}); check local DB roles, version and permissions")

    def connection(self):
        env = self.pg_env()
        return psycopg.connect(host=env["PGHOST"], port=env["PGPORT"], dbname=env["PGDATABASE"],
                               user=env["PGUSER"], password=env.get("PGPASSWORD"),
                               sslmode=env["PGSSLMODE"], connect_timeout=10, options=env["PGOPTIONS"])

    def assert_quiet(self):
        if self.config["postgres"]:
            with self.connection() as db:
                count = db.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                   "AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()[0]
                if count:
                    raise SyncConflict("Close all PostgreSQL clients before database handoff")

    def empty(self):
        if any(p.exists() for p in self.sqlite_paths):
            return False
        if self.config["postgres"]:
            with self.connection() as db:
                return not db.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                      "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
                                      "AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','S','v','m') LIMIT 1").fetchone()
        return True

    def snapshot(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        files, fingerprints = {}, {}
        for index, source in enumerate(self.sqlite_paths):
            name = f"sqlite-{index}.db"
            fingerprints[name] = None
            if source.exists():
                target = directory / name
                sqlite_snapshot(source, target)
                files[name] = file_hash(target)
                fingerprints[name] = sqlite_fingerprint(target)
        if self.config["postgres"]:
            target = directory / "postgres.sql"
            self.pg("pg_dump", "--no-password", "--clean", "--if-exists", "--no-owner", "--file", target)
            files[target.name] = file_hash(target)
            fingerprints[target.name] = postgres_fingerprint(target)
        return {"files": files, "fingerprints": fingerprints, "layout": self.layout}

    def restore(self, directory: Path, manifest: dict):
        self.assert_quiet()
        for index, target in enumerate(self.sqlite_paths):
            if f"sqlite-{index}.db" not in manifest["files"] and target.exists():
                raise SyncConflict("Remote SQLite file missing; local file preserved")
        if self.config["postgres"]:
            # pg_dump --clean alone leaves objects deleted on the other PC behind.
            # Clear user schemas and restore within ONE transaction on this dedicated DB.
            clear_schemas = """DO $$ DECLARE item record; BEGIN
                FOR item IN SELECT nspname FROM pg_namespace
                    WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
                LOOP EXECUTE format('DROP SCHEMA %I CASCADE', item.nspname); END LOOP;
                END $$;
                CREATE SCHEMA public AUTHORIZATION pg_database_owner;
                GRANT USAGE ON SCHEMA public TO PUBLIC;"""
            self.pg("psql", "--no-password", "-X", "--single-transaction", "--set", "ON_ERROR_STOP=1",
                    "--command", clear_schemas, "--file", directory / "postgres.sql")
        for index, target in enumerate(self.sqlite_paths):
            name = f"sqlite-{index}.db"
            if name not in manifest["files"]:
                if target.exists():
                    raise SyncConflict("Remote SQLite file missing; local file preserved")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # The destination must be quiescent. Backup API handles WAL instead of
            # replacing a main file underneath old -wal/-shm sidecars.
            sqlite_snapshot(directory / name, target)


class NasSync:
    def __init__(self, workspace: Path, config: dict, databases: LocalDatabases):
        self.workspace, self.config, self.databases = workspace, config, databases
        self.root = Path(config["root"])
        self.local = workspace / "var/database-sync"
        self.local.mkdir(parents=True, exist_ok=True)
        self.state_path = self.local / "state.json"
        if not self.state_path.exists():
            write_json(self.state_path, {"node": uuid4().hex, "host": socket.gethostname(), "phase": "new", "head": None})
        self.state = read_json(self.state_path)

    def save(self, **values):
        self.state.update(values)
        write_json(self.state_path, self.state)

    @contextmanager
    def lock(self):
        # Never create the share's parent (a disconnected mount must not silently
        # turn into a local directory). mkdir is the cross-PC exclusion primitive.
        if not self.root.parent.is_dir():
            raise SyncConflict("NAS unavailable; startup/handoff blocked")
        self.root.mkdir(exist_ok=True)
        lock = self.root / "operation.lock"
        try:
            lock.mkdir()
        except FileExistsError:
            raise SyncConflict("NAS operation.lock exists; another sync is running or needs crash recovery") from None
        try:
            self.state = read_json(self.state_path)
            yield
        finally:
            lock.rmdir()

    def head(self):
        path = self.root / "latest.json"
        return read_json(path) if path.exists() else None

    def owner(self):
        path = self.root / "owner.json"
        return read_json(path) if path.exists() else None

    def require_owner(self):
        owner = self.owner()
        if not owner or owner["node"] != self.state["node"]:
            raise SyncConflict("This workspace does not own the NAS handoff")
        if self.head() != self.state["head"]:
            raise SyncConflict("NAS history changed; refusing to overwrite it")
        if self.state["head"]:
            manifest = read_json(self.root / "snapshots" / self.state["head"] / "manifest.json")
            if manifest["layout"] != self.databases.layout:
                raise SyncConflict("Database layout changed while NAS history exists")

    def download(self, head: str, destination: Path):
        if not re.fullmatch(r"[0-9a-f]{32}", head):
            raise SyncConflict("Invalid snapshot ID")
        source = self.root / "snapshots" / head
        manifest = read_json(source / "manifest.json")
        if manifest["layout"] != self.databases.layout:
            raise SyncConflict("Database layout differs from NAS snapshot")
        allowed = {f"sqlite-{i}.db" for i in range(len(self.databases.sqlite_paths))}
        if self.config["postgres"]:
            allowed.add("postgres.sql")
            if "postgres.sql" not in manifest["files"]:
                raise SyncConflict("PostgreSQL snapshot missing")
        if not set(manifest["files"]).issubset(allowed):
            raise SyncConflict("Unexpected snapshot file")
        destination.mkdir()
        for name, expected in manifest["files"].items():
            shutil.copyfile(source / name, destination / name)
            if file_hash(destination / name) != expected:
                raise SyncConflict(f"Snapshot checksum mismatch: {name}")
        return manifest

    def prepare(self):
        with self.lock():
            owner, head = self.owner(), self.head()
            if not head and self.state["head"]:
                raise SyncConflict("NAS history is missing; refusing to recreate it from a possibly stale PC")
            if owner and owner["node"] != self.state["node"]:
                raise SyncConflict(f"NAS owned by {owner['host']}; stop that PC cleanly first")
            if self.state["phase"] == "restoring":
                raise SyncConflict("Interrupted restore: inspect local rollback snapshot before recovery")
            if owner:
                self.require_owner()
                if self.state["phase"] == "active":
                    return  # Same workspace restart after failure; never replace dirty data.
            if self.state["phase"] == "active":
                raise SyncConflict("Active local history lost NAS ownership; manual recovery required")
            self.databases.assert_quiet()
            with tempfile.TemporaryDirectory(dir=self.local) as temporary:
                temporary = Path(temporary)
                if self.state["phase"] == "clean":
                    current = self.databases.snapshot(temporary / "current")
                    if current["fingerprints"] != self.state["fingerprints"]:
                        raise SyncConflict("Local databases changed after handoff; preserved for manual reconciliation")
                elif head and not self.databases.empty():
                    raise SyncConflict("Unmanaged local databases exist; preserved instead of overwritten")
                manifest = self.download(head, temporary / "remote") if head else None
                write_json(self.root / "owner.json", {"node": self.state["node"], "host": self.state["host"]})
                if head and head != self.state["head"]:
                    rollback = self.local / ("before-restore-" + uuid4().hex)
                    self.databases.snapshot(rollback)
                    self.save(phase="restoring", rollback=str(rollback))
                    self.databases.restore(temporary / "remote", manifest)
                self.save(phase="active", head=head)
            self._publish()

    def _publish(self):
        if self.state["phase"] != "active":
            raise SyncConflict("Cannot publish incomplete restore")
        self.require_owner()
        with tempfile.TemporaryDirectory(dir=self.local) as temporary:
            temporary = Path(temporary)
            manifest = self.databases.snapshot(temporary)
            generation = uuid4().hex
            manifest.update(schema_version=1, node=self.state["node"], parent=self.state["head"],
                            created_at=datetime.now(UTC).isoformat())
            destination = self.root / "snapshots" / generation
            destination.mkdir(parents=True)
            for name, expected in manifest["files"].items():
                shutil.copyfile(temporary / name, destination / name)
                if file_hash(destination / name) != expected:
                    raise SyncConflict("NAS write verification failed")
            write_json(destination / "manifest.json", manifest)
            # Only advertise a generation after every file is complete and verified.
            write_json(self.root / "latest.json", generation)
            self.save(head=generation, fingerprints=manifest["fingerprints"])
            return generation

    def backup(self):
        with self.lock():
            return self._publish()

    def release(self):
        with self.lock():
            if self.state["phase"] in ("new", "clean") and not self.owner():
                return
            self.require_owner()
            self.databases.assert_quiet()
            self._publish()
            self.save(phase="clean")
            (self.root / "owner.json").unlink()
