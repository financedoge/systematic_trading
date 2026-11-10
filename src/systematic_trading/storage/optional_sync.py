"""Optional, local-first snapshots with latest-observed-revision handoff.

Whole verified generations win; database rows are never merged. Unchanged
backups retain their revision time, so copying an old PC cannot make it newer.
NAS operations serialize under the existing cross-machine publication lock.
Incoming restores only run while local application services are stopped.
"""
from contextlib import contextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
import re
import shutil
import socket
from uuid import uuid4

from systematic_trading.storage.nas_sync import NasSync, SyncConflict, file_hash, read_json, write_json


class OptionalNasSync(NasSync):
    def prune_generations(self, verified_head):
        """Called under the NAS lock, only after head bytes have been verified.

        Unknown directories/files and links fail closed. The default remains
        no pruning for older configurations; recovery-only installations opt in.
        """
        if self.config.get("retain_generations") != 1:
            return
        if not re.fullmatch(r"[0-9a-f]{32}", verified_head or "") or self.head() != verified_head:
            raise SyncConflict("Verified NAS head changed before retention")
        return self._remove_generations(keep=verified_head)

    def retire_generations(self, proof, snapshot):
        """Retire the redundant SQL lane after a complete recovery restore passed.

        Caller validates the current restic snapshot and holds local/NAS locks.
        This method is never called by legacy handoff or routine SQL transfer.
        """
        self.publish_recovery_locator(proof, snapshot)
        (self.root/'latest.json').unlink(missing_ok=True)
        return self._remove_generations(keep=None)

    def publish_recovery_locator(self, proof, snapshot):
        if (not self.config.get('recovery_only') or not proof.get('passed')
                or proof.get('scope') != 'recovery-v1'
                or not re.fullmatch(r'[0-9a-f]{64}', snapshot or '')
                or not re.fullmatch(r'[0-9a-f]{64}', proof.get('snapshot', ''))
                or Path(proof.get('repository', '')).resolve().parent != self.root.resolve()):
            raise SyncConflict('A verified replacement recovery repository is required')
        # Publish the replacement locator before withdrawing the legacy pointer.
        write_json(self.root/'recovery.json', dict(repository=proof['repository'],
            snapshot=snapshot, restore_verified_snapshot=proof['snapshot'], scope='recovery-v1'))

    def _remove_generations(self, *, keep):
        root = (self.root / "snapshots").resolve()
        if root != self.root.resolve()/'snapshots' or (self.root/'snapshots').is_junction():
            raise SyncConflict('Unsafe NAS snapshots root')
        removed, skipped = [], []
        receipt = self.local / "retention" / (uuid4().hex + ".json")
        def record_receipt():
            write_json(receipt, dict(at=datetime.now(UTC).isoformat(), root=str(root), kept=keep,
                removed=removed, skipped_unknown=skipped,
                removed_bytes=sum(r['bytes'] for r in removed)))
        for path in root.iterdir():
            if path.name == keep or not re.fullmatch(r"[0-9a-f]{32}", path.name):
                continue
            if (path.is_symlink() or path.is_junction() or not path.is_dir()
                    or path.resolve().parent != root):
                raise SyncConflict("Unsafe NAS generation path")
            files = list(path.iterdir())
            if any(p.is_symlink() or p.is_junction() or not p.is_file()
                   or p.resolve().parent != path.resolve()
                   or not re.fullmatch(r"manifest\.json|postgres\.sql(?:\.gz)?|sqlite-\d+\.db", p.name)
                   for p in files):
                skipped.append(path.name)
                continue
            record = dict(generation=path.name, bytes=sum(p.stat().st_size for p in files))
            for file in files:
                file.unlink()
            path.rmdir()
            removed.append(record)
            if len(removed) % 25 == 0:
                record_receipt()
        if removed or skipped:
            record_receipt()
        return dict(removed=len(removed), removed_bytes=sum(r['bytes'] for r in removed), skipped=skipped)

    def guard(self):
        self.state = read_json(self.state_path)
        if self.state["phase"] == "restoring":
            raise SyncConflict("Interrupted restore: recover the local rollback snapshot before starting services")

    def preflight(self):
        self.guard()  # Local database safety only; NAS is never a service dependency.

    @contextmanager
    def local_lock(self):
        # OS locks are released on process death; no stale PID/lock takeover.
        with (self.local / "snapshot.lock").open("a+b") as stream:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def checkpoint(self):
        self.guard()
        generation = uuid4().hex
        directory = self.local / "checkpoints" / generation
        observed_at = datetime.now(UTC).isoformat()
        manifest = self.databases.snapshot(directory)
        previous = self.state.get("checkpoint")
        unchanged = manifest["fingerprints"] == self.state.get("fingerprints")
        revision_at = self.state.get("revision_at") if unchanged else observed_at
        if self.databases.empty():
            revision_at = "1970-01-01T00:00:00+00:00"
        # A legacy clean snapshot has no local revision timestamp. Its baseline
        # sorts before a dated remote snapshot; newly observed edits sort now.
        revision_at = revision_at or "1970-01-01T00:00:00+00:00"
        manifest.update(schema_version=2, node=self.state["node"], parent=self.state.get("head"),
                        created_at=observed_at, revision_at=revision_at)
        write_json(directory / "manifest.json", manifest)
        self.save(checkpoint=generation, fingerprints=manifest["fingerprints"], revision_at=revision_at)
        # Retain the last two local checkpoints, plus all explicit rollback copies.
        for old in directory.parent.iterdir():
            if old.name not in {generation, previous} and old.is_dir() and old.resolve().parent == directory.parent.resolve():
                shutil.rmtree(old)
        return directory, manifest

    @staticmethod
    def revision(manifest):
        stamp = datetime.fromisoformat(manifest.get("revision_at", manifest["created_at"]))
        if stamp.tzinfo is None:
            raise SyncConflict("Snapshot revision requires a UTC offset")
        return stamp, manifest["node"]

    def check_connection(self):
        # Bound the common disconnected-Wi-Fi case before Windows SMB path IO.
        root = str(self.root)
        if root.startswith("\\\\"):
            host = root[2:].split("\\", 1)[0]
            with socket.create_connection((host, 445), timeout=2):
                pass

    def transfer(self, directory, manifest, *, restore):
        self.check_connection()
        with self.lock():
            head = self.head()
            remote = None
            if head:
                # Validate the ID, layout and every byte before considering it.
                import tempfile
                with tempfile.TemporaryDirectory(dir=self.local) as temporary:
                    from pathlib import Path
                    incoming = Path(temporary) / "incoming"
                    remote = self.download(head, incoming)
                    if remote["fingerprints"] == manifest["fingerprints"]:
                        self.save(head=head, revision_at=remote.get("revision_at", remote["created_at"]))
                        self.prune_generations(head)
                        return "current"
                    if self.revision(remote) > self.revision(manifest):
                        if not restore:
                            return "newer_remote_pending_restart"
                        if hasattr(self.databases, "settings"):
                            from systematic_trading.storage.dependencies import verify_dependencies
                            verify_dependencies(self.databases.settings, remote.get("dependencies"),
                                verify_publications=self.databases.settings.market_data_store_backend!='parquet')
                        self.databases.assert_quiet()
                        rollback = self.local / ("before-restore-" + uuid4().hex)
                        shutil.copytree(directory, rollback)
                        self.save(phase="restoring", rollback=str(rollback))
                        self.databases.restore(incoming, remote)
                        self.save(phase="active", head=head, fingerprints=remote["fingerprints"],
                                  revision_at=remote.get("revision_at", remote["created_at"]))
                        return "restored_newer_remote"
            generation = uuid4().hex
            destination = self.root / "snapshots" / generation
            destination.mkdir(parents=True)
            for name, expected in manifest["files"].items():
                shutil.copyfile(directory / name, destination / name)
                if file_hash(destination / name) != expected:
                    raise SyncConflict("NAS write verification failed")
            write_json(destination / "manifest.json", dict(manifest, parent=head))
            write_json(self.root / "latest.json", generation)
            self.save(head=generation)
            self.prune_generations(generation)
            return "published_local"

    def synchronize(self, *, restore=False, closing=False):
        self.guard()
        acquired = False
        try:
            with self.local_lock():
                acquired = True
                directory, manifest = self.checkpoint()
                result = self.transfer(directory, manifest, restore=restore)
                self.save(phase="clean" if closing else "active", sync_status=result, sync_error=None)
        except Exception as exc:
            # An interrupted database replacement is a local integrity problem,
            # not an optional-backup failure. Never launch over a partial restore.
            self.guard()
            if not acquired:
                # Another local writer owns the state; do not race its restore
                # phase or checkpoint commit just to record an optional error.
                return "local_backup_busy"
            result = "local_only"
            self.save(phase="clean" if closing else "active", sync_status=result, sync_error=str(exc))
        write_json(self.workspace / "var/run/database_sync.state.json", dict(
            ok=result != "local_only", optional=True, status=result, head=self.state.get("head"),
            checkpoint=self.state.get("checkpoint"), error=self.state.get("sync_error"),
            revision_at=self.state.get("revision_at"), at=datetime.now(UTC).timestamp()))
        return result

    def prepare(self):
        if self.config.get("recovery_only", False):
            # Disaster recovery is an explicit restore. Ordinary startup must
            # never wait for a full dump, SMB IO, or replace the local database.
            self.guard()
            return "local_ready"
        return self.synchronize(restore=True)

    def backup(self):
        return self.synchronize()

    def release(self):
        if self.config.get("recovery_only", False):
            self.guard()
            return "local_ready"
        return self.synchronize(closing=True)
