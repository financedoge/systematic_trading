"""Storage admission protects retained evidence instead of evicting it."""
import json
import os
from pathlib import Path
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
    if not 0 < policy['generated_soft_gib'] <= policy['generated_admission_gib'] or policy['new_calculation_reserve_gib']<=0:
        raise ValueError('Artifact storage limits must be positive and ordered')
    measured=generated_footprint(settings.data_dir)
    used=measured['unique_content_bytes']/1024**3
    accepted=used+policy['new_calculation_reserve_gib']<=policy['generated_admission_gib']
    receipt=dict(**measured,measured_at=datetime.now(UTC).isoformat(),policy=policy,admitted=accepted,over_soft_limit=used>policy['generated_soft_gib'],
        basis='Unique file content lengths; canonical histories and broker evidence excluded')
    atomic_json(settings.data_dir/'run/artifact-budget.json',receipt)
    if not accepted:
        raise ValueError(f'Calculation deferred: generated artifacts use {used:.1f} GiB; '
            f'{policy["generated_admission_gib"]} GiB admission limit includes '
            f'{policy["new_calculation_reserve_gib"]} GiB for new work. Protected evidence retained; run guarded retention.')
    return receipt
