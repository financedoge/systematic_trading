"""Dependency-free atomic state and crash-released locks, also usable in LEAN."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from uuid import uuid4


class LockUnavailable(OSError):
    """The OS lock is held by another process.

    Callers may treat this as transient where the lock only serializes
    independent jobs. It inherits ``OSError`` so existing handlers that treat
    any lock failure as an error keep working.
    """


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path):
    """Never steal a lock by timestamp/PID; the OS releases it after a crash.

    Raises ``LockUnavailable`` when another process owns the lock, so callers
    can distinguish transient contention from a real filesystem permission
    problem. The OS still releases the lock after a crash.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LockUnavailable(f"{path.name} is locked by another process") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
