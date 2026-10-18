"""Retirement receipts for generated research; never erase operational evidence.

Inventory and validation are independent of the deletion mechanism. Windows
deletion is performed by the guarded PowerShell entry point, using literal paths.
"""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from systematic_trading.runtime_io import atomic_json

REVISION = re.compile(r"^[a-f0-9]{64}$")
CLOSED_STUDIES = {
    'selection-width-timing-20261015-v1','target-change-rebalance-20261015-v1',
    *{f'alpha101-tilt-{kind}-20261011-v{version}' for kind in ('daily','exit','surface','replay') for version in (1,2)},
    'selection-blend-20261010-v1','fr25-placebo-20261010-v1',
    'cash-stress-losers-20261009-v1','expanded-economics-20261010-v1',
    'candidate-pool-momentum-20261009-v1','ranking-construction-20261007-v1',
    'economic-financial-20261007-v1','economic-response-20261007-v2',
    *{f'momentum-20261001-v1{v}' for v in ('a','b')},
    *{f'sleeve-construction-20261010-v{v}' for v in (1,2)},
    *{f'hierarchical-construction-20261011-v{v}' for v in (1,2)},
}
DISPOSABLE_STUDY_FOLDERS = {'bundles','python','native','runs','workers','source','analysis_sources','size_diagnostic','run-02',
    'controls','decisions','events','monthly','targets','parents','parent','reproduction','usd_preparation_attempts',
    'economic','original_economics','fits','models','training','completion_source','followup'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value):
    return sha256(canonical(value).encode()).hexdigest()


def contained_directory(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    if path == root or not path.is_relative_to(root):
        raise ValueError("Retirement target must be strictly inside its allowed root")
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Reparse points/symlinks cannot be retired: " + str(item))
    if not path.is_dir() or path.resolve() != path:
        raise ValueError("Retirement target is not an ordinary resolved directory")
    return path


def inventory(root, path, *, receipt_payload=True):
    """Bounded memory inventory with NTFS identity accounting and mutation seal."""
    path = contained_directory(root, path)
    seal = sha256()
    identities = {}
    files = logical = 0
    receipts = []
    for folder, dirs, names in os.walk(path, followlinks=False):
        dirs.sort(); names.sort()
        for name in dirs + names:
            p = Path(folder) / name
            s = p.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
                raise ValueError("Reparse points/symlinks cannot be retired: " + str(p))
            relative = p.relative_to(path).as_posix()
            seal.update(canonical([relative, s.st_dev, s.st_ino, s.st_size,
                                   s.st_mtime_ns, s.st_mode, s.st_nlink]).encode())
            if not stat.S_ISREG(s.st_mode):
                continue
            files += 1; logical += s.st_size
            identity = (s.st_dev, s.st_ino)
            entry = identities.setdefault(identity, [s.st_size, s.st_nlink, 0])
            entry[2] += 1
            if name in {"run.json", "manifest.json", "compute.json"}:
                data = p.read_bytes()
                receipt=dict(path=relative, sha256=sha256(data).hexdigest())
                if receipt_payload:receipt['payload']=json.loads(data)
                receipts.append(receipt)
    return dict(path=str(path), seal=seal.hexdigest(), file_count=files,
                logical_bytes=logical, unique_content_bytes=sum(v[0] for v in identities.values()),
                exclusive_content_bytes=sum(v[0] for v in identities.values() if v[1] == v[2]),
                receipts=receipts)


def validate_manifest(manifest, current_guard, allowed_root):
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if manifest.get("manifest_sha256") != fingerprint(body):
        raise ValueError("Retirement manifest changed")
    if manifest["guard"] != current_guard:
        raise ValueError("Protection/publication/control state changed; regenerate the manifest")
    root = Path(allowed_root).resolve()
    if Path(manifest["allowed_root"]) != root:
        raise ValueError("Retirement root changed")
    protected = {str(Path(p).resolve()) for p in manifest["protected_paths"]}
    for row in manifest["candidates"]:
        p = contained_directory(root, row["path"])
        if manifest.get('scope','tracked')=='closed_studies':
            if p.parent.parent!=root or p.parent.name not in CLOSED_STUDIES or p.name not in DISPOSABLE_STUDY_FOLDERS:
                raise ValueError('Only allowlisted completed study output folders may be retired')
        elif manifest.get('scope')=='governance':
            if p.parent!=root or not re.fullmatch(r'(listed|research)-\d{4}-\d{2}-\d{2}-[a-f0-9]{12}',p.name):
                raise ValueError('Only complete versioned governance projections may be retired')
        elif p.parent != root or not REVISION.fullmatch(p.name):
            raise ValueError("Only complete tracked revision directories may be retired")
        if any(Path(v).is_relative_to(p) or p.is_relative_to(Path(v)) for v in protected):
            raise ValueError("Candidate overlaps protected evidence")
        current = inventory(root, p,receipt_payload=manifest.get('scope')!='governance')
        if current != row["inventory"]:
            raise ValueError("Retirement target changed: " + str(p))
    return manifest["candidates"]


def retirement_for_path(data_dir, artifact_path):
    if not artifact_path:
        return None
    target = Path(artifact_path).resolve()
    directory = Path(data_dir) / "maintenance/retirements"
    if not directory.exists():
        return None
    for ancestor in (target, *target.parents):
        for receipt in directory.glob(fingerprint(str(ancestor)) + ".*.retired.json"):
            record = json.loads(receipt.read_text(encoding="utf8"))
            if record.get("status") == "retired" and target.is_relative_to(Path(record["path"])):
                return {k: record[k] for k in ("path", "at", "reason", "manifest_sha256")}
    return None


def record_retirement(data_dir, manifest, row, *, status):
    """One immutable outcome per target and manifest; original run rows stay intact."""
    if status not in {"retired", "intent"}:
        raise ValueError("Unsupported retirement outcome")
    if status == "retired" and Path(row["path"]).exists():
        raise ValueError("Target still exists; cannot record successful retirement")
    receipt = dict(schema_version=1, status=status, at=datetime.now(UTC).isoformat(),
                   path=row["path"], reason=row["reason"], manifest_sha256=manifest["manifest_sha256"],
                   inventory=row["inventory"], guard=manifest["guard"],
                   reproduction="retired; rerun on a newly pinned audited batch is new evidence")
    destination = Path(data_dir) / "maintenance/retirements" / (fingerprint(row['path']) + "." + manifest['manifest_sha256'] + "." + status + ".json")
    if destination.exists():
        prior = json.loads(destination.read_text(encoding="utf8"))
        if {k:v for k,v in prior.items() if k != 'at'} != {k:v for k,v in receipt.items() if k != 'at'}:
            raise ValueError("Immutable retirement receipt changed")
        return destination
    atomic_json(destination, receipt)
    return destination
