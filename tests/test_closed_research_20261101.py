"""Closed study classification preserves compact recipes and active protections."""
import json

import pytest

from systematic_trading.storage.artifact_retention import (
    active_research_metadata, fingerprint, inventory, validate_manifest,
)


@pytest.mark.parametrize('study,folder',[
    ('alpha101-net-20261031-v1','native-v1'),('alpha101-net-20261031-v1','paths'),
    ('cash-relative-net-20261031-v1','native-v2'),('cash-relative-net-20261031-v1','detail')])
def test_closed_generated_outputs_are_eligible_but_still_protectable(tmp_path,study,folder):
    root=tmp_path/'research';target=root/study/folder;target.mkdir(parents=True)
    (target/'generated.json').write_text(json.dumps({'diagnostic':1}))
    (target.parent/'protocol.json').write_text('{}')
    (root/'ongoing').mkdir();(root/'ongoing'/'protocol.json').write_text('{}')
    assert active_research_metadata(root)==[root/'ongoing'/'protocol.json']
    plan=dict(scope='closed_studies',guard={'revision':1},allowed_root=str(root),protected_paths=[],
        candidates=[dict(path=str(target),inventory=inventory(root,target))])
    plan['manifest_sha256']=fingerprint(plan)
    assert validate_manifest(plan,plan['guard'],root)
    plan['protected_paths']=[str(target.parent)]
    plan['manifest_sha256']=fingerprint({k:v for k,v in plan.items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='protected'):validate_manifest(plan,plan['guard'],root)
