"""Purge only recognized, already-retired backups from the configured NAS bin."""
from datetime import UTC, datetime
import errno
import os
from pathlib import Path, PureWindowsPath
import re

from systematic_trading.storage.nas_sync import write_json


def validate_recycle_mapping(root, repository):
    root, repository = PureWindowsPath(root), PureWindowsPath(repository)
    trash_share, live_share = root.drive.strip('\\').split('\\'), repository.drive.strip('\\').split('\\')
    if (len(trash_share) != 2 or len(live_share) != 2
            or trash_share[0].lower() != live_share[0].lower()
            or not trash_share[1].lower().startswith('recycle bin - volume_')
            or trash_share[1].lower() == live_share[1].lower()
            or len(root.parts) != 2 or len(repository.parts) != 3
            or root.name.lower() != repository.parent.name.lower()):
        raise ValueError('Recycle target must be this project in the same NAS recycle share')


def purge_recycled_backups(root, repository, receipt, *, progress=None):
    """Caller holds capture lock and has checked the retained live repository.

    Never empty a whole NAS bin. Unknown names and unrelated project data remain.
    Validate all paths before deletion; use individual unlinks and empty rmdir.
    """
    root, repository = Path(root), Path(repository).resolve()
    if root.is_symlink() or root.is_junction():
        raise ValueError('Linked recycle root is forbidden')
    root = root.resolve()
    if (root == repository or root.is_relative_to(repository) or repository.is_relative_to(root)
            or root.name != repository.parent.name):
        raise ValueError('Recycle target overlaps live storage or another project')
    if not root.exists():
        return dict(removed_files=0, removed_bytes=0, skipped=[])
    pattern = re.compile(
        re.escape(repository.name) + r'/(?:data/[0-9a-f]{2}/[0-9a-f]{64}|(?:index|snapshots|locks)/[0-9a-f]{64})'
        r'|snapshots/[0-9a-f]{32}/(?:manifest\.json|postgres\.sql(?:\.gz)?|sqlite-\d+\.db)'
        r'|latest\.json|operation\.lock/(?:Copy #[1-9][0-9]* of )?lease\.json|verification-smb-lock\.guard')
    planned, skipped = [], []
    for parent, directories, names in os.walk(root):
        for name in [*directories, *names]:
            path = Path(parent)/name
            if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root):
                raise ValueError('Unsafe recycled backup path: '+str(path))
        for name in names:
            path = Path(parent)/name
            relative = path.relative_to(root).as_posix()
            if pattern.fullmatch(relative):
                stat = path.stat()
                planned.append((path, relative, stat.st_size, stat.st_mtime_ns))
            else:
                skipped.append(relative)
        if progress:
            progress()
    removed, directories = [], set()

    def record():
        result = dict(at=datetime.now(UTC).isoformat(), root=str(root), repository=str(repository),
            planned_files=len(planned), removed_files=len(removed),
            removed_bytes=sum(row['bytes'] for row in removed), removed=removed, skipped=skipped)
        write_json(receipt, result)
        return result

    record()
    for path, relative, size, mtime in planned:
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (size, mtime) or path.is_symlink() or path.is_junction():
            raise ValueError('Recycled backup changed during cleanup: '+relative)
        path.unlink()
        removed.append(dict(path=relative, bytes=size))
        directories.update(p for p in path.parents if p != root and p.is_relative_to(root))
        if len(removed) % 100 == 0:
            record()
            if progress:
                progress()
    for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError as exc:
            if exc.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                raise
    return record()
