"""Optional application recovery backups. No live database restore or remote dependency.

Native consistent DB/queue snapshots plus all durable file roots go into restic.
Only fully readable, checked candidates are tagged system-complete. Interrupted
uploads keep their capture and reuse already uploaded content on reconnect.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from uuid import uuid4

from systematic_trading.runtime_io import exclusive_lock
from systematic_trading.storage.nas_sync import LocalDatabases, file_hash, read_json, write_json


class BackupStopped(RuntimeError):
    pass


def check_nas(repository: Path):
    value = str(repository)
    if value.startswith("\\\\"):
        with socket.create_connection((value[2:].split("\\", 1)[0], 445), timeout=2):
            pass
        # Windows SMB metadata calls can hang even with port 445 reachable.
        # Probe those in the cancellable child below, never on the worker thread.
        return
    if not repository.parent.is_dir():
        raise OSError("NAS backup parent is unavailable")


async def snapshot_nats(url, directory):
    import nats
    connection = await nats.connect(servers=[url], name="system-backup", connect_timeout=3,
                                    allow_reconnect=False)
    try:
        offset, streams = 0, []
        while True:
            response = json.loads((await connection.request("$JS.API.STREAM.NAMES",
                json.dumps({"offset": offset}).encode(), timeout=10)).data)
            if response.get("error"):
                raise RuntimeError("NATS stream inventory failed")
            names = response.get("streams", [])
            streams.extend(names)
            offset += len(names)
            if offset >= response.get("total", 0):
                break
            if not names:
                raise RuntimeError("Incomplete NATS stream inventory")
        directory.mkdir(parents=True, exist_ok=True)
        inventory = {}
        for name in streams:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ValueError("Unsupported NATS stream name")
            subject = connection.new_inbox()
            subscription = await connection.subscribe(subject, pending_bytes_limit=32*1024**2)
            try:
                response = json.loads((await connection.request(f"$JS.API.STREAM.SNAPSHOT.{name}",
                    json.dumps(dict(deliver_subject=subject, no_consumers=False,
                                    chunk_size=131072, jsck=True)).encode(), timeout=120)).data)
                if response.get("error"):
                    raise RuntimeError(f"NATS snapshot failed: {name}")
                with (directory / (name + ".snapshot")).open("wb") as output:
                    while True:
                        message = await subscription.next_msg(timeout=120)
                        if not message.data:
                            break
                        output.write(message.data)
                        if message.reply:
                            await message.respond(b"")
                inventory[name] = response
            finally:
                await subscription.unsubscribe()
        write_json(directory / "streams.json", inventory)
        return inventory
    finally:
        await connection.close()


class SystemBackup:
    def __init__(self, workspace, config, settings):
        self.workspace = Path(workspace).resolve()
        self.config, self.settings = config, settings
        self.local = self.workspace / "var/system-backup"
        self.local.mkdir(parents=True, exist_ok=True)
        self.run_dir = self.workspace / "var/run"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.stop_path = self.run_dir / "system_backup.stop"
        self.state_path = self.run_dir / "system_backup.state.json"
        self.state = read_json(self.state_path) if self.state_path.exists() else {}
        self.repository = Path(config["repository"])
        self.stage = Path(config["staging_root"]).resolve()
        # Never permit cleanup to target a drive, the workspace, or a source root.
        sources = [self.resolve(p) for p in config["required_paths"]]
        if len(self.stage.parts) < 3 or any(p == self.stage or p.is_relative_to(self.stage) for p in sources):
            raise ValueError("Unsafe backup staging root")
        if any(self.stage.is_relative_to(p) for p in sources):
            raise ValueError("Backup staging must be outside all source roots")
        self.password = self.resolve(config["password_file"])
        if not self.password.is_relative_to(self.workspace / "var/private"):
            raise ValueError("Recovery key must stay in excluded var/private")
        self.binary = self.resolve(config["restic_binary"])

    def resolve(self, path):
        return (self.workspace / path).resolve()

    def status(self, status, **fields):
        self.state.update(status=status, at=datetime.now(UTC).isoformat(), **fields)
        write_json(self.state_path, self.state)
        self.heartbeat()

    def heartbeat(self):
        from systematic_trading.services.health import write_service_state_file
        status = self.state.get("status", "starting")
        write_service_state_file(self.run_dir / "system_backup.health.json", service_id="system_backup",
            running=status not in {"disabled", "paused"}, last_error=self.state.get("error"),
            message="Full recovery backup: " + status, details=self.state)

    def command(self, args, *, env=None, timeout=None):
        """Bounded child process; shutdown cancels work, never waits for NAS upload."""
        output = self.local / "command.stdout.log"
        errors = self.local / "command.stderr.log"
        with output.open("wb") as stdout, errors.open("wb") as stderr:
            process = subprocess.Popen(list(map(str, args)), cwd=self.workspace, env=env,
                stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            deadline = time.monotonic() + (timeout or self.config.get("command_timeout_seconds", 21600))
            next_heartbeat = 0
            try:
                while process.poll() is None:
                    if self.stop_path.exists():
                        raise BackupStopped("Backup paused for local shutdown")
                    if time.monotonic() > deadline:
                        raise TimeoutError("Backup command timed out; retry will reuse uploaded content")
                    if time.monotonic() >= next_heartbeat:
                        self.heartbeat()
                        next_heartbeat = time.monotonic()+30
                    time.sleep(.25)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
        if process.returncode:
            # A restic exit 3 creates an incomplete snapshot. Never tag it complete.
            raise RuntimeError(f"{Path(args[0]).name} failed (exit {process.returncode}); inspect var/system-backup/command.stderr.log")
        return output.read_text(encoding="utf8", errors="replace")

    def restic(self, *args):
        env = os.environ.copy()
        env.update(RESTIC_REPOSITORY=str(self.repository), RESTIC_PASSWORD_FILE=str(self.password),
                   RESTIC_CACHE_DIR=str(self.local / "cache"))
        return self.command([self.binary, "--json", *args], env=env)

    def initialize_repository(self):
        if not self.binary.is_file():
            raise RuntimeError("Run scripts/install_restic.py to provision verified restic")
        probe = json.loads(self.command([sys.executable, "-c",
            "import json,sys; from pathlib import Path; p=Path(sys.argv[1]); "
            "print(json.dumps(dict(parent=p.parent.is_dir(), configured=(p/'config').is_file(), "
            "nonempty=p.exists() and any(p.iterdir()))))", self.repository], timeout=30))
        if not probe["parent"]:
            raise OSError("NAS backup parent is unavailable")
        if probe["configured"]:
            if not self.password.is_file():
                raise RuntimeError("Existing backup requires its recovery key; never generate a replacement")
            return
        if probe["nonempty"]:
            raise RuntimeError("Backup repository contains data but has no config; preserve it for repair")
        # Provision once, retaining the same key if initialization is interrupted.
        if not self.password.exists():
            self.password.parent.mkdir(parents=True, exist_ok=True)
            with self.password.open("x", encoding="ascii") as stream:
                stream.write(secrets.token_urlsafe(48) + "\n")
        self.restic("init", "--repository-version", "2")

    def source_paths(self):
        paths = [self.resolve(p) for p in self.config["required_paths"]]
        paths.append(self.settings.market_data_storage_policy_path.resolve())
        policy = read_json(self.settings.market_data_storage_policy_path)
        paths.append(Path(policy["hot_spool_root"]).resolve())
        archive = policy.get("local_archive_root")
        if archive and Path(archive).exists():
            paths.append(Path(archive).resolve())
        # Explicit model/FX inputs and governed roots may be outside configured
        # machine defaults. The dependency inventory defines required coverage.
        from systematic_trading.storage.dependencies import dependency_receipt
        dependencies = dependency_receipt(self.settings)
        paths.extend(Path(p).resolve() for p in dependencies.get("files", {}))
        paths.extend(Path(item["root"]).resolve() for item in dependencies.get("governed_roots", []))
        unique = sorted(set(paths), key=lambda p: (len(p.parts), str(p)))
        roots = []
        for path in unique:
            if not path.exists():
                raise FileNotFoundError(f"Required recovery source missing: {path}")
            if path == self.stage or path.is_relative_to(self.stage):
                raise ValueError("Recovery source cannot be inside staging")
            if not any(path.is_relative_to(parent) for parent in roots):
                roots.append(path)
        return roots, dependencies

    def clickhouse(self, query):
        return json.loads(self.command(["docker", "exec", self.config["clickhouse_container"],
            "clickhouse-client", "--query", query + " FORMAT JSON"], timeout=120))

    def capture_clickhouse(self, target):
        container = self.config["clickhouse_container"]
        previous = self.state.get("native_backup")
        previous_id = self.state.get("native_backup_id", "")
        if previous and re.fullmatch(r"/var/lib/clickhouse/backups/system-[0-9a-f]{32}", previous) and re.fullmatch(r"[0-9a-f-]{36}", previous_id):
            active = self.clickhouse(f"SELECT status FROM system.backups WHERE id='{previous_id}'")["data"]
            if active and active[0]["status"] == "CREATING_BACKUP":
                raise RuntimeError("Previous native capture is still running; retry after it completes")
            # Only our generated, recorded native capture may be removed. A
            # crash between native capture and docker cp must not leak 25+ GiB
            # on every automatic retry. The pending manifest is created later.
            self.command(["docker", "exec", container, "rm", "-rf", "--", previous], timeout=60)
        identifier = "system-" + uuid4().hex
        native = "/var/lib/clickhouse/backups/" + identifier
        # Installation is repeatable and does not restart the server. Compose
        # mounts the same reviewed configuration on future container creation.
        # A future Compose-created container mounts this read-only. Only install
        # the file into an older container that predates that mount.
        configured = self.command(["docker", "exec", container, "sh", "-c",
            "if test -f /etc/clickhouse-server/config.d/system-backup.xml; then cat /etc/clickhouse-server/config.d/system-backup.xml; fi"], timeout=30)
        expected = (self.workspace / "deploy/clickhouse/backup.xml").read_text(encoding="utf8")
        if configured.strip() != expected.strip():
            self.command(["docker", "cp", self.workspace / "deploy/clickhouse/backup.xml",
                          container + ":/etc/clickhouse-server/config.d/system-backup.xml"], timeout=30)
        self.command(["docker", "exec", container, "clickhouse-client", "--query", "SYSTEM RELOAD CONFIG"], timeout=30)
        databases = [r["name"] for r in self.clickhouse("SELECT name FROM system.databases")['data']
                     if r["name"] not in {"system", "INFORMATION_SCHEMA", "information_schema"}]
        if not {"analytics", "market_data"}.issubset(databases):
            raise RuntimeError("Essential ClickHouse databases are missing")
        identifiers = ", ".join("DATABASE `" + name.replace("`", "``") + "`" for name in databases)
        response = self.clickhouse(f"BACKUP {identifiers} TO File('{native}') ASYNC")
        backup_id = response["data"][0]["id"]
        self.status("capturing_clickhouse", native_backup=native, native_backup_id=backup_id)
        deadline = time.monotonic()+3600
        while True:
            result = self.clickhouse(f"SELECT status, error FROM system.backups WHERE id='{backup_id}'")["data"]
            if not result:
                raise RuntimeError("ClickHouse backup status missing")
            status = result[0]["status"]
            if status == "BACKUP_CREATED":
                break
            if status != "CREATING_BACKUP" or time.monotonic() > deadline:
                raise RuntimeError("ClickHouse native backup failed or timed out")
            if self.stop_path.exists():
                raise BackupStopped("Native backup continues locally; upload deferred")
            time.sleep(1)
        target.mkdir()
        self.status("copying_clickhouse", error=None)
        self.command(["docker", "cp", container + ":" + native + "/.", target])
        if not (target / ".backup").is_file():
            raise RuntimeError("ClickHouse backup metadata missing after copy")
        # Fixed validated generated child, never a user-controlled shell path.
        self.command(["docker", "exec", container, "rm", "-rf", "--", native], timeout=60)
        return dict(databases=databases, version=self.clickhouse("SELECT version() AS version")["data"][0]["version"])

    def capture(self):
        self.status("inventorying_sources", error=None)
        sources, dependencies = self.source_paths()
        if self.stop_path.exists():
            raise BackupStopped("Backup inventory paused for local shutdown")
        self.stage.mkdir(parents=True, exist_ok=True)
        marker = self.stage / ".system-backup-staging"
        if any(self.stage.iterdir()) and not marker.exists():
            raise ValueError("Refusing to replace unrecognized staging contents")
        marker.touch()
        capture = self.stage / "capture"
        if capture.exists():
            # Resolved, dedicated child checked before recursive removal.
            if capture.is_symlink() or capture.resolve().parent != self.stage:
                raise ValueError("Unsafe capture cleanup path")
            shutil.rmtree(capture)
        capture.mkdir()
        started = datetime.now(UTC).isoformat()
        self.status("capturing_postgres", error=None)
        databases = LocalDatabases(self.workspace, {"postgres": True, "sqlite_paths": []}, self.settings)
        databases.pg("pg_dump", "--no-password", "--format=custom", "--compress=0", "--no-owner",
                     "--file", capture / "postgres.dump")
        databases.pg("pg_restore", "--list", capture / "postgres.dump")
        postgres_at = datetime.now(UTC).isoformat()
        self.status("capturing_clickhouse")
        clickhouse = self.capture_clickhouse(capture / "clickhouse")
        self.status("capturing_queue")
        streams = asyncio.run(snapshot_nats(self.config["nats_url"], capture / "nats"))
        write_json(capture / "dependencies.json", dependencies)
        self.status("hashing_capture")
        files = {}
        for path in capture.rglob("*"):
            if self.stop_path.exists():
                raise BackupStopped("Capture hashing paused for local shutdown")
            if path.is_file():
                files[str(path.relative_to(capture)).replace("\\", "/")] = dict(sha256=file_hash(path), bytes=path.stat().st_size)
        manifest = dict(schema_version=1, captured_from=started, postgres_at=postgres_at,
            captured_to=datetime.now(UTC).isoformat(), host=socket.gethostname(),
            workspace=str(self.workspace), postgres_database=self.settings.postgres_database,
            clickhouse=clickhouse, nats_streams=list(streams), files=files,
            sources=list(map(str, sources)), excludes=self.config["exclude"],
            consistency="Each database/stream is native-consistent; live files are read during upload. Not a global transaction or disk image. Reconcile before execution after restore.",
            credentials="Reprovision private credentials and retain the separate restic recovery key.")
        write_json(capture / "manifest.json", manifest)
        write_json(self.local / "pending.json", dict(capture=str(capture), manifest_sha256=file_hash(capture/"manifest.json"),
                                                      captured_at=manifest["captured_to"], sources=list(map(str, sources))))
        return read_json(self.local / "pending.json")

    def publish(self, pending):
        capture = Path(pending["capture"])
        if capture != self.stage / "capture" or file_hash(capture / "manifest.json") != pending["manifest_sha256"]:
            raise ValueError("Pending capture identity changed")
        # Preserve effective non-secret .env settings (ports, identities, paths,
        # feature flags) without putting private credentials on the NAS.
        raw_settings = self.settings.model_dump(mode="json")
        omitted = [name for name in raw_settings if any(word in name.lower()
                   for word in ("password", "secret", "token", "api_key"))]
        runtime_settings = self.stage / "runtime-settings.json"
        profile_path = self.run_dir / "local_recovery.profile.json"
        launch_profile = json.loads(profile_path.read_text(encoding="utf-8-sig")) if profile_path.exists() else None
        write_json(runtime_settings, dict(settings={name: value for name, value in raw_settings.items() if name not in omitted},
            launch_profile=launch_profile, reprovision_fields=omitted, backup_excludes=self.config["exclude"],
            note="Review restored environment and paper policy before starting services."))
        paths = [capture, runtime_settings, *map(Path, pending["sources"])]
        if any(not p.exists() for p in paths):
            raise FileNotFoundError("A required pending backup source is missing")
        paths_file = self.local / "sources.txt"
        paths_file.write_text("\n".join(map(str, paths))+"\n", encoding="utf8")
        exclude_file = self.local / "exclude.txt"
        exclude_file.write_text("\n".join(self.config["exclude"])+"\n", encoding="utf8")
        self.status("uploading", error=None, capture_at=pending["captured_at"])
        self.restic("unlock")  # Only restic-proven stale locks; never --remove-all.
        output = self.restic("backup", "--tag", "system-candidate", "--host", socket.gethostname(),
            "--files-from-verbatim", str(paths_file), "--iexclude-file", str(exclude_file))
        summaries = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        summary = next((item for item in reversed(summaries) if item.get("message_type") == "summary"), None)
        if not summary or not summary.get("snapshot_id"):
            raise RuntimeError("Backup command did not return a snapshot identity")
        snapshot = summary["snapshot_id"]
        self.status("verifying", candidate_snapshot=snapshot, summary=summary)
        self.restic("check")
        # Decrypt/read the manifest independently from the NAS and compare bytes.
        # Windows absolute paths appear under /D/... in restic snapshots.
        manifest_path = "/" + str(capture / "manifest.json").replace("\\", "/").replace(":", "")
        restored = self.restic("dump", snapshot, manifest_path)
        if json.loads(restored) != read_json(capture / "manifest.json"):
            raise RuntimeError("NAS manifest readback mismatch")
        self.restic("tag", "--add", "system-complete", "--remove", "system-candidate", snapshot)
        # Tag changes the snapshot ID. Resolve the resulting immutable identity.
        snapshots = json.loads(self.restic("snapshots", "--tag", "system-complete", "--host", socket.gethostname(), "--latest", "1"))
        final_id = snapshots[0]["id"]
        self.status("complete", error=None, snapshot=final_id, completed_at=datetime.now(UTC).isoformat(),
                    captured_at=pending["captured_at"], candidate_snapshot=None,
                    verification="restic repository metadata check and decrypted manifest readback; full data scrub/restore is separate")
        (self.local / "pending.json").unlink()
        return final_id

    def once(self):
        if not self.config.get("enabled"):
            self.status("disabled", error=None)
            return None
        with exclusive_lock(self.local / "capture.lock"):
            try:
                self.status("connecting", error=None)
                check_nas(self.repository)  # Before expensive capture or NAS filesystem operations.
                self.initialize_repository()
                pending_path = self.local / "pending.json"
                pending = read_json(pending_path) if pending_path.exists() else self.capture()
                return self.publish(pending)
            except BackupStopped:
                self.status("paused", error=None)
                return None
            except Exception as exc:
                self.status("deferred", error=f"{type(exc).__name__}: {exc}")
                return None

    def restore_files(self, snapshot, target):
        with exclusive_lock(self.local / "capture.lock"):
            return self._restore_files(snapshot, target)

    def _restore_files(self, snapshot, target):
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot):
            raise ValueError("Use an exact complete snapshot ID")
        target = Path(target).resolve()
        if target.exists() and any(target.iterdir()):
            raise ValueError("Restore requires an empty target; never restore onto running databases")
        protected = [self.workspace, self.stage, self.repository, *[self.resolve(p) for p in self.config["required_paths"]]]
        if any(target == p or target.is_relative_to(p) or p.is_relative_to(target) for p in protected):
            raise ValueError("Restore target overlaps source, staging or backup storage")
        check_nas(self.repository)
        snapshots = json.loads(self.restic("snapshots", snapshot))
        if len(snapshots) != 1 or "system-complete" not in snapshots[0].get("tags", []):
            raise ValueError("Snapshot is not a verified complete candidate")
        # Restore each original root under a neutral directory. Recreating parent
        # C:/Users ACL/readonly attributes breaks non-admin Windows restores.
        # A mapping retains exact original locations without inheriting those
        # ancestors or ever overwriting production paths.
        target.mkdir(parents=True, exist_ok=True)
        mapping = []
        for index, source in enumerate(snapshots[0]["paths"]):
            source_path = Path(source)
            restic_path = "/" + source.replace("\\", "/").replace(":", "")
            item = target / f"root-{index:03d}"
            # Determine directory/file from the authenticated snapshot, not the
            # current PC (the original disk may no longer exist).
            listing = [json.loads(line) for line in self.restic("ls", snapshot, restic_path).splitlines() if line.startswith("{")]
            node = next((row for row in listing if row.get("path") == restic_path), None)
            if node is None:
                # Configured excluded roots (e.g. .env.example) are intentionally absent.
                continue
            if node.get("type") == "dir":
                self.restic("restore", snapshot + ":" + restic_path, "--target", str(item), "--verify")
            else:
                parent, name = restic_path.rsplit("/", 1)
                self.restic("restore", snapshot + ":" + parent, "--include", "/" + name,
                            "--target", str(item), "--verify")
            mapping.append(dict(original=str(source_path), restored=str(item), type=node.get("type")))
        write_json(target / "restore-map.json", mapping)
        return target
