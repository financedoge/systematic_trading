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


def test_budget_defers_work_without_deleting_evidence(tmp_path):
    root=tmp_path/'research';root.mkdir()
    evidence=root/'protected';evidence.write_bytes(b'12345')
    settings=SimpleNamespace(data_dir=tmp_path)
    policy=dict(generated_soft_gib=1/1024**3,generated_admission_gib=6/1024**3,new_calculation_reserve_gib=2/1024**3)
    with pytest.raises(ValueError,match='Calculation deferred'):
        admit(settings,policy=policy)
    assert evidence.read_bytes()==b'12345'
    receipt=json.loads((tmp_path/'run/artifact-budget.json').read_text())
    assert receipt['admitted'] is False and receipt['over_soft_limit'] is True
    policy['generated_admission_gib']=7/1024**3
    assert admit(settings,policy=policy)['admitted'] is True
