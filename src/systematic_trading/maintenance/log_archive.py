"""Lossless local log compression with readback receipts.

Only explicitly named closed logs are accepted. On Windows, a short-lived append
log can first be renamed atomically: an open writer prevents the rename, so a
successful rename detaches the old file before a later append recreates its path.
No copy/truncate fallback is permitted. Long-held stdout/stderr files need a
stopped owner and are intentionally not eligible for online rotation.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from systematic_trading.runtime_io import atomic_json, exclusive_lock

ROTATABLE_LOGS = frozenset({"platform_operations.jsonl", "intraday_recovery.jsonl"})
CLOSED_LOGS = frozenset({
    "intraday-recovery-probe.jsonl", "postgres-relocation-recovery.log",
    "order_ui_preview.out.log", "order_ui_preview.err.log",
})


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_log(log_dir: Path, name: str, *, rotate: bool = False) -> dict:
    """Compress one authorized log, verify every byte, then remove only its copy.

    Refuse traversal, symlinks, changed sources, overwrites and active files. A
    failure after rotation retains the detached source for explicit recovery.
    """
    root = Path(log_dir).resolve(strict=True)
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Expected a log basename")
    source = root / name
    if source.is_symlink() or source.resolve().parent != root or not source.is_file():
        raise ValueError("Expected a regular log directly inside the log directory")
    if rotate:
        if os.name != "nt" or name not in ROTATABLE_LOGS:
            raise ValueError("Online rotation is limited to Windows append-only application logs")
    elif name not in CLOSED_LOGS and not re.search(r"(?<!\d)20\d{6}(?!\d)", name):
        raise ValueError("Closed logs must have a dated name or be a recognized retired log")
    elif datetime.now(UTC).timestamp() - source.stat().st_mtime < 7 * 86400:
        raise ValueError("Closed logs must have been inactive for at least seven days")

    archive = root / "archive"
    if archive.is_symlink() or archive.resolve().parent != root:
        raise ValueError("Archive directory must stay inside the log directory")
    archive.mkdir(exist_ok=True)
    with exclusive_lock(archive / ".maintenance.lock"):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
        if rotate:
            detached = archive / f"{name}.{stamp}.uncompressed"
            source.rename(detached)  # Fails closed if a Windows writer holds it.
            source.touch(exist_ok=True)
            source = detached
        target = archive / f"{name}.{stamp}.gz"
        receipt_path = target.with_suffix(target.suffix + ".json")
        before = source.stat()
        signature = (before.st_size, before.st_mtime_ns, before.st_ino)
        # Exclusive creation means a retry never overwrites retained evidence.
        with target.open("xb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
                with source.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, compressed, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        digest = file_hash(source)
        with gzip.open(target, "rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError(f"Archive readback mismatch; source retained at {source}")
        after = source.stat()
        if signature != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError(f"Log changed during compression; source retained at {source}")
        receipt = dict(schema_version=1, original_name=name, rotated=rotate,
                       source=str(source), archive=str(target), source_bytes=before.st_size,
                       archive_bytes=target.stat().st_size, source_sha256=digest,
                       archive_sha256=file_hash(target), archived_at=datetime.now(UTC).isoformat(),
                       source_removed=False)
        atomic_json(receipt_path, receipt)
        source.unlink()
        receipt["source_removed"] = True
        atomic_json(receipt_path, receipt)
        return receipt
