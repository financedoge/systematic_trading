from pathlib import Path

import pytest

from systematic_trading.storage.recovery_retention import purge_recycled_backups, validate_recycle_mapping


def test_recycle_mapping_rejects_other_project_host_or_live_share():
    repo = r'\\nas\Public\project\full-system-restic'
    validate_recycle_mapping(r'\\nas\Recycle Bin - Volume_1\project', repo)
    for root in [r'\\other\Recycle Bin - Volume_1\project', r'\\nas\Public\project',
                 r'\\nas\Recycle Bin - Volume_1', r'\\nas\Recycle Bin - Volume_1\other']:
        with pytest.raises(ValueError, match='same NAS recycle share'):
            validate_recycle_mapping(root, repo)


def test_only_recognized_retired_files_are_deleted_and_live_bytes_remain(tmp_path):
    root = tmp_path/'trash/project'
    live = tmp_path/'live/project/full-system-restic'
    relative = Path('full-system-restic/data/ab')/('ab'+'c'*62)
    for base in [root, live.parent]:
        p = base/relative
        p.parent.mkdir(parents=True)
        p.write_text('backed-up bytes')
    sql = root/'snapshots'/('d'*32)/'postgres.sql.gz'
    sql.parent.mkdir(parents=True)
    sql.write_text('retired SQL')
    unknown = root/'recovery-key.txt'
    unknown.write_text('keep')
    copied_lease = root/'operation.lock/Copy #8 of lease.json'
    copied_lease.parent.mkdir()
    copied_lease.write_text('old lease')
    result = purge_recycled_backups(root, live, tmp_path/'receipt.json')
    assert result['removed_files'] == 3
    assert result['removed_bytes'] == 35
    assert result['skipped'] == ['recovery-key.txt']
    assert unknown.read_text() == 'keep' and (live.parent/relative).read_text() == 'backed-up bytes'
    assert not sql.exists() and not (root/relative).exists()
    assert purge_recycled_backups(root, live, tmp_path/'retry.json')['removed_files'] == 0


def test_purge_refuses_live_root_and_linked_descendant(tmp_path, monkeypatch):
    root = tmp_path/'trash/project'
    live = tmp_path/'live/project/full-system-restic'
    root.mkdir(parents=True)
    live.mkdir(parents=True)
    with pytest.raises(ValueError, match='overlaps'):
        purge_recycled_backups(live.parent, live, tmp_path/'receipt.json')
    linked = root/'snapshots'
    linked.mkdir()
    original = Path.is_junction
    monkeypatch.setattr(Path, 'is_junction', lambda self: self == linked or original(self))
    with pytest.raises(ValueError, match='Unsafe'):
        purge_recycled_backups(root, live, tmp_path/'receipt.json')
