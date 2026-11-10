import importlib.util
from pathlib import Path
import sys

import pytest

from systematic_trading.storage.recovery_checks import validate_recovery_coverage


def test_restore_cannot_accept_a_new_uncaptured_root(tmp_path):
    config = dict(required_paths=['durable'], input_manifests=[], exclude=[])
    manifest = dict(sources=[str(tmp_path/'durable')], excludes=[])
    validate_recovery_coverage(manifest, config, tmp_path)
    config['required_paths'].append('new-required-data')
    with pytest.raises(ValueError, match='not captured'):
        validate_recovery_coverage(manifest, config, tmp_path)


def restore_module():
    scripts = Path(__file__).resolve().parents[1]/'scripts'
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location('restore_recovery_test', scripts/'verify_recovery_restore.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_restored_mapping_never_falls_back_to_existing_source(tmp_path):
    module = restore_module()
    original = tmp_path/'production'
    original.mkdir()
    payload = original/'required'
    payload.write_text('exists only in production')
    with pytest.raises(ValueError, match='absent from restored'):
        module.mapped_path(payload, [])
    restored = tmp_path/'restored'
    mapping = [dict(original=str(original), restored=str(restored), type='dir')]
    assert module.mapped_path(payload, mapping) == restored/'required'
    assert not module.mapped_path(payload, mapping).exists()


def test_file_mapping_and_more_specific_root(tmp_path):
    module = restore_module()
    original = tmp_path/'original'
    mapping = [dict(original=str(original), restored=str(tmp_path/'root'), type='dir'),
               dict(original=str(original/'file.json'), restored=str(tmp_path/'file-root'), type='file')]
    assert module.mapped_path(original/'file.json', mapping) == tmp_path/'file-root/file.json'


def test_restore_corrects_only_explicitly_excluded_known_runtime_pins(tmp_path):
    module = restore_module()
    original = tmp_path/'tracked_strategies'/('a'*64)/'datasets/worker.lock'
    empty_hash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    dependencies = dict(files={str(original):empty_hash}, governed_roots=[])
    with pytest.raises(ValueError, match='absent from restored'):
        module.verify_files(dependencies, [])
    ignored = []
    assert module.verify_files(dependencies, [], excludes=['**/*.lock'], ignored=ignored) == 0
    assert ignored == [dict(path=str(original), sha256=empty_hash, reason='empty strategy worker lock')]
    for name, checksum in [('broker.lock', empty_hash), (str(original), 'f'*64), ('data.tmp', empty_hash)]:
        with pytest.raises(ValueError, match='absent from restored'):
            module.verify_files(dict(files={name:checksum}, governed_roots=[]), [], excludes=['**/*.lock', '**/*.tmp'])


def test_restore_never_excuses_excluded_sealed_artifact(tmp_path):
    import json
    module = restore_module()
    folder = tmp_path/'tracked_models'/('b'*64)
    folder.mkdir(parents=True)
    name = 'request.json.'+'c'*32+'.tmp'
    manifest = folder/'manifest.json'
    manifest.write_text(json.dumps({'files':{name:'f'*64}}))
    mapping = [dict(original=str(tmp_path), restored=str(tmp_path), type='dir')]
    dependencies = dict(files={str(manifest):module.file_hash(manifest)}, governed_roots=[])
    with pytest.raises(FileNotFoundError):
        module.verify_files(dependencies, mapping, excludes=['**/*.tmp'])
