import json
import os

import pytest

from systematic_trading.storage.artifact_retention import (
    fingerprint, inventory, record_retirement, retirement_for_path, validate_manifest,
)


def candidate(tmp_path):
    root = tmp_path / 'tracked_strategies'
    target = root / ('a' * 64)
    target.mkdir(parents=True)
    (target / 'run.json').write_text(json.dumps({'run_id': 'historical', 'status': 'succeeded'}))
    (target / 'data.bin').write_bytes(b'payload')
    row = dict(path=str(target), reason='Superseded complete calculation', inventory=inventory(root, target))
    manifest = dict(guard={'revision': 7}, allowed_root=str(root), protected_paths=[], candidates=[row])
    manifest['manifest_sha256'] = fingerprint(manifest)
    return root, target, manifest


def test_stale_controls_and_changed_files_prevent_deletion(tmp_path):
    root, target, plan = candidate(tmp_path)
    assert validate_manifest(plan, {'revision': 7}, root)
    with pytest.raises(ValueError, match='state changed'):
        validate_manifest(plan, {'revision': 8}, root)
    (target / 'data.bin').write_bytes(b'new content')
    with pytest.raises(ValueError, match='target changed'):
        validate_manifest(plan, {'revision': 7}, root)


def test_protected_nested_model_and_tampered_manifest_rejected(tmp_path):
    root, target, plan = candidate(tmp_path)
    plan['protected_paths'] = [str(target / 'model')]
    with pytest.raises(ValueError, match='manifest changed'):
        validate_manifest(plan, plan['guard'], root)
    plan['manifest_sha256'] = fingerprint({k:v for k,v in plan.items() if k != 'manifest_sha256'})
    with pytest.raises(ValueError, match='protected'):
        validate_manifest(plan, plan['guard'], root)


def test_cross_root_and_linked_directory_rejected(tmp_path):
    root, target, plan = candidate(tmp_path)
    outside = tmp_path / 'unrelated'
    outside.mkdir()
    with pytest.raises(ValueError, match='inside'):
        inventory(root, outside)
    try:
        (target / 'escape').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks unavailable for this Windows identity')
    with pytest.raises(ValueError, match='Reparse'):
        inventory(root, target)


def test_hard_link_contents_not_counted_as_exclusively_reclaimable(tmp_path):
    root, target, plan = candidate(tmp_path)
    os.link(target / 'data.bin', tmp_path / 'retained.bin')
    summary = inventory(root, target)
    assert summary['exclusive_content_bytes'] == summary['logical_bytes'] - len(b'payload')
    assert summary['receipts'][0]['payload']['run_id'] == 'historical'


def test_receipt_cannot_claim_existing_target_deleted_and_lookup_is_explicit(tmp_path):
    root, target, plan = candidate(tmp_path)
    row = plan['candidates'][0]
    record_retirement(tmp_path, plan, row, status='intent')
    assert retirement_for_path(tmp_path, str(target / 'run')) is None
    with pytest.raises(ValueError, match='still exists'):
        record_retirement(tmp_path, plan, row, status='retired')
    for path in target.iterdir():
        path.unlink()
    target.rmdir()
    receipt = record_retirement(tmp_path, plan, row, status='retired')
    before = receipt.read_bytes()
    record_retirement(tmp_path, plan, row, status='retired')
    assert receipt.read_bytes() == before
    assert retirement_for_path(tmp_path, str(target / 'model'))['reason'] == row['reason']


def test_closed_study_scope_cannot_retire_protocol_or_active_study(tmp_path):
    root=tmp_path/'research'
    target=root/'selection-width-timing-20261015-v1'/'bundles';target.mkdir(parents=True)
    (target/'blob').write_bytes(b'disposable')
    row=dict(path=str(target),inventory=inventory(root,target))
    plan=dict(scope='closed_studies',guard={'revision':1},allowed_root=str(root),protected_paths=[],candidates=[row])
    plan['manifest_sha256']=fingerprint(plan)
    assert validate_manifest(plan,plan['guard'],root)
    plan['protected_paths']=[str(target.parent)]
    plan['manifest_sha256']=fingerprint({k:v for k,v in plan.items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='protected'):validate_manifest(plan,plan['guard'],root)
    plan['protected_paths']=[]
    (target.parent/'protocol').mkdir()
    plan['candidates']=[dict(path=str(target.parent/'protocol'),inventory=inventory(root,target.parent/'protocol'))]
    plan['manifest_sha256']=fingerprint({k:v for k,v in plan.items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='allowlisted'):validate_manifest(plan,plan['guard'],root)


def test_governance_receipt_seals_manifest_without_copying_large_inventory(tmp_path):
    root=tmp_path/'governance'
    target=root/'research-2026-10-12-0123456789ab'
    target.mkdir(parents=True)
    (target/'manifest.json').write_text(json.dumps({'data.csv':'a'*64}))
    (target/'data.csv').write_text('published')
    summary=inventory(root,target,receipt_payload=False)
    assert summary['receipts'][0]['sha256']
    assert 'payload' not in summary['receipts'][0]
    plan=dict(scope='governance',guard={'export':'verified'},allowed_root=str(root),
        protected_paths=[],candidates=[dict(path=str(target),inventory=summary)])
    plan['manifest_sha256']=fingerprint(plan)
    assert validate_manifest(plan,plan['guard'],root)
    plan['protected_paths']=[str(target)]
    plan['manifest_sha256']=fingerprint({k:v for k,v in plan.items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='protected'):
        validate_manifest(plan,plan['guard'],root)


def test_model_scope_cannot_delete_shared_fit_cache(tmp_path):
    root=tmp_path/'tracked_models'
    target=root/'fits';target.mkdir(parents=True)
    (target/'fit.json').write_text('{}')
    plan=dict(scope='models',guard={},allowed_root=str(root),protected_paths=[],
        candidates=[dict(path=str(target),inventory=inventory(root,target))])
    plan['manifest_sha256']=fingerprint(plan)
    with pytest.raises(ValueError,match='revision'):
        validate_manifest(plan,{},root)
