import json
from types import SimpleNamespace

import pytest

from systematic_trading.lean.contracts import sha256
from systematic_trading.storage.dependencies import directory_pins, verify_dependencies


def test_receipt_includes_published_usd_files_outside_current_price_root(tmp_path):
    from systematic_trading.storage.dependencies import dependency_receipt
    usd = tmp_path/'usd'
    usd.mkdir()
    payload = usd/'snapshots.json'
    payload.write_text('[]')
    (usd/'manifest.json').write_text(json.dumps({'snapshots.json':sha256(payload)}))
    analytics = SimpleNamespace(workspace='test', publication_index=lambda _: {},
        latest=lambda key: {'provenance':json.dumps({'root':str(usd)})} if key=='governance/usd-broad-index' else None)
    settings = SimpleNamespace(market_data_store_backend='clickhouse',
        strategy_monitoring_config_path=tmp_path/'absent.json', data_dir=tmp_path)
    receipt = dependency_receipt(settings, analytics=analytics)
    assert str(usd/'manifest.json') in receipt['files']
    verify_dependencies(SimpleNamespace(), receipt)


def test_native_backup_reads_only_publication_head_identities():
    from contextlib import nullcontext
    from systematic_trading.storage.dependencies import publication_versions
    calls = []
    class Connection:
        def execute(self, query, params):
            calls.append((query, params))
            return [dict(source_id='governance/catalog', version='pinned')]
    analytics = SimpleNamespace(workspace='workspace', catalog=SimpleNamespace(connect=lambda: nullcontext(Connection())),
        publication_index=lambda _: pytest.fail('Must not load large publication provenance'))
    assert publication_versions(analytics, native=True) == {'governance/catalog':'pinned'}
    assert calls[0][1] == ('workspace',)


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


def test_loose_runtime_pins_are_narrowly_classified(tmp_path):
    locks = tmp_path/'tracked_strategies'/('a'*64)/'datasets'
    locks.mkdir(parents=True)
    empty = locks/'worker.lock'
    empty.touch()
    worker = locks/('strategy.worker-'+'d'*32)
    worker.mkdir()
    (worker/'bundle.lock').touch()
    nonempty = locks/'data.lock'
    nonempty.write_text('durable payload')
    models = tmp_path/'tracked_models'/('b'*64)
    models.mkdir(parents=True)
    temporary = models/('request.json.'+'c'*32+'.tmp')
    temporary.write_text('uncommitted')
    durable = models/'data.tmp'
    durable.write_text('required')
    broker = tmp_path/'broker.lock'
    broker.touch()
    pins = directory_pins(tmp_path)
    assert set(pins) == {str(nonempty), str(durable), str(broker)}


def test_sealed_runtime_named_artifact_remains_required(tmp_path):
    folder = tmp_path/'tracked_models'/('b'*64)
    folder.mkdir(parents=True)
    payload = folder/('request.json.'+'c'*32+'.tmp')
    payload.write_text('declared artifact')
    manifest = folder/'manifest.json'
    manifest.write_text(json.dumps({'files':{payload.name:sha256(payload)}}))
    receipt = dict(files=directory_pins(tmp_path))
    assert set(receipt['files']) == {str(manifest)}
    payload.unlink()
    with pytest.raises(FileNotFoundError):
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
