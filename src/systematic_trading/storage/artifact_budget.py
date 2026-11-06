"""Queue artifact housekeeping; admit calculations against actual disk headroom."""
import json
import math
import os
from pathlib import Path
import shutil
import stat
from datetime import UTC, datetime

from systematic_trading.runtime_io import atomic_json


def generated_footprint(data_dir):
    seen=set();total=0;files=0
    for name in ('tracked_strategies','tracked_models','research'):
        root=Path(data_dir)/name
        if root.exists() and (root.is_symlink() or getattr(root.lstat(),'st_file_attributes',0) & 0x400):
            raise ValueError('Generated artifact budget cannot follow a reparse root')
        for parent,dirs,names in os.walk(root,followlinks=False):
            for directory in dirs:
                p=Path(parent)/directory
                if p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError('Generated artifact budget cannot follow a reparse directory')
            for name in names:
                info=(Path(parent)/name).stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):continue
                identity=(info.st_dev,info.st_ino)
                if identity in seen:continue
                seen.add(identity);files+=1;total+=info.st_size
    return dict(unique_content_bytes=total,unique_files=files)


def admit(settings, *, policy=None):
    policy=policy if policy is not None else json.loads((Path(__file__).resolve().parents[3]/'config/storage-retention.json').read_text())
    for key in ('generated_soft_gib','new_calculation_reserve_gib'):
        value=policy[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Artifact cleanup threshold and free-disk reserve must be positive finite numbers')
    measured=generated_footprint(settings.data_dir)
    used=measured['unique_content_bytes']/1024**3
    disk=shutil.disk_usage(settings.data_dir)
    required=math.ceil(policy['new_calculation_reserve_gib']*1024**3)
    accepted=disk.free>=required
    receipt=dict(**measured,measured_at=datetime.now(UTC).isoformat(),policy=policy,admitted=accepted,over_soft_limit=used>policy['generated_soft_gib'],
        admission_basis='free_disk_space',disk_free_bytes=disk.free,disk_required_bytes=required,
        basis='Unique file content lengths; canonical histories and broker evidence excluded')
    atomic_json(settings.data_dir/'run/artifact-budget.json',receipt)
    if receipt['over_soft_limit'] or not accepted:
        atomic_json(settings.data_dir/'run/research-retention.pending.json',dict(
            queued_at=receipt['measured_at'],reason='Generated artifacts need guarded housekeeping at the next stopped startup',
            unique_content_bytes=measured['unique_content_bytes'],disk_free_bytes=disk.free))
    if not accepted:
        raise ValueError(f'Calculation deferred: artifact drive has {disk.free/1024**3:.1f} GiB free; '
            f'{policy["new_calculation_reserve_gib"]} GiB of free disk is required for new work. '
            'Guarded cleanup is queued; protected evidence retained.')
    return receipt
