import json
from types import SimpleNamespace

import pytest

from systematic_trading.lean.contracts import sha256
from systematic_trading.storage.dependencies import directory_pins, verify_dependencies


def test_checkpoint_pins_inventory_but_restore_checks_all_bytes(tmp_path):
    folder = tmp_path / 'bundle'
    folder.mkdir()
    payload = folder / 'data'
    payload.write_bytes(b'audited bytes')
    manifest = folder / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version':1, 'files':{'data':sha256(payload)}}))
    loose = tmp_path / 'preparation.json'
    loose.write_text('{}')
    pins = directory_pins(tmp_path)
    assert set(pins) == {str(manifest), str(loose)}
    receipt = dict(files=pins)
    verify_dependencies(SimpleNamespace(), receipt)
    payload.write_bytes(b'changed')
    with pytest.raises(ValueError, match='prerequisite changed'):
        verify_dependencies(SimpleNamespace(), receipt)


def test_restore_rejects_unexpected_bundle_file(tmp_path):
    data = tmp_path / 'data'
    data.write_text('known')
    manifest = tmp_path / 'run.json'
    manifest.write_text(json.dumps({'artifacts':{'data':sha256(data)}}))
    receipt = dict(files=directory_pins(tmp_path))
    (tmp_path / 'extra').write_text('unrecorded')
    with pytest.raises(ValueError, match='inventory changed'):
        verify_dependencies(SimpleNamespace(), receipt)


def test_native_usd_run_restores_and_checks_sidecar_and_nested_outputs(tmp_path):
    from systematic_trading.lean.native_runner import seal_run
    from systematic_trading.research.momentum_replay import checked_files
    nested = tmp_path/'native'
    nested.mkdir()
    payload = nested/'economic.json'
    payload.write_text('{"value": 100}')
    seal_run(tmp_path, {'status':'succeeded'}, contract='usd')
    receipt = dict(files=directory_pins(tmp_path))
    verify_dependencies(SimpleNamespace(), receipt)
    assert set(checked_files(tmp_path, 'artifact_manifest.json')) == {'native/economic.json'}
    assert 'artifact_manifest.json' in json.loads((tmp_path/'run.json').read_text())['artifacts']
    payload.write_text('{"value": 101}')
    with pytest.raises(ValueError, match='prerequisite changed'):
        verify_dependencies(SimpleNamespace(), receipt)
