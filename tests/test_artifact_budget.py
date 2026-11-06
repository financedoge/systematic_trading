import json
import os
from types import SimpleNamespace

import pytest

from systematic_trading.storage.artifact_budget import admit, generated_footprint


def test_budget_counts_shared_content_once_and_excludes_canonical_evidence(tmp_path):
    research=tmp_path/'research'; research.mkdir()
    models=tmp_path/'tracked_models'; models.mkdir()
    data=research/'data'; data.write_bytes(b'12345')
    os.link(data,models/'linked')
    canonical=tmp_path/'governance';canonical.mkdir()
    (canonical/'audited').write_bytes(b'kept separately')
    assert generated_footprint(tmp_path)==dict(unique_content_bytes=5,unique_files=1)


def test_only_real_disk_headroom_defers_work_without_deleting_evidence(tmp_path,monkeypatch):
    root=tmp_path/'research';root.mkdir()
    evidence=root/'protected';evidence.write_bytes(b'12345')
    settings=SimpleNamespace(data_dir=tmp_path)
    policy=dict(generated_soft_gib=1/1024**3,new_calculation_reserve_gib=2/1024**3)
    monkeypatch.setattr('systematic_trading.storage.artifact_budget.shutil.disk_usage',lambda p:SimpleNamespace(free=1))
    with pytest.raises(ValueError,match='free disk is required'):
        admit(settings,policy=policy)
    assert evidence.read_bytes()==b'12345'
    receipt=json.loads((tmp_path/'run/artifact-budget.json').read_text())
    assert receipt['admitted'] is False and receipt['over_soft_limit'] is True
    assert receipt['disk_free_bytes']==1 and receipt['disk_required_bytes']==2
    assert (tmp_path/'run/research-retention.pending.json').exists()
    monkeypatch.setattr('systematic_trading.storage.artifact_budget.shutil.disk_usage',lambda p:SimpleNamespace(free=2))
    assert admit(settings,policy=policy)['admitted'] is True


def test_large_research_footprint_queues_cleanup_without_blocking_calculation(tmp_path,monkeypatch):
    monkeypatch.setattr('systematic_trading.storage.artifact_budget.generated_footprint',
        lambda p:dict(unique_content_bytes=500*1024**3,unique_files=123))
    monkeypatch.setattr('systematic_trading.storage.artifact_budget.shutil.disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    policy=dict(generated_soft_gib=20,new_calculation_reserve_gib=2)
    receipt=admit(SimpleNamespace(data_dir=tmp_path),policy=policy)
    assert receipt['admitted'] and receipt['over_soft_limit']
    assert receipt['admission_basis']=='free_disk_space'
    assert json.loads((tmp_path/'run/research-retention.pending.json').read_text())['unique_content_bytes']==500*1024**3


@pytest.mark.parametrize('value',[0,-1,float('inf'),float('nan'),True,'2'])
def test_invalid_headroom_policy_cannot_silently_disable_guard(tmp_path,value):
    with pytest.raises(ValueError,match='positive finite'):
        admit(SimpleNamespace(data_dir=tmp_path),policy=dict(generated_soft_gib=20,new_calculation_reserve_gib=value))
