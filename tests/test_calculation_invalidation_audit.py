import importlib.util
from pathlib import Path
import json
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location('invalidation_audit', Path(__file__).parents[1] / 'scripts/audit_calculation_invalidation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_appends_revisions_and_historical_inserts_are_distinct():
    old = [dict(trade_date='2026-01-02', close=100, volume=20)]
    assert module.row_changes(old, old)['kind'] == 'identical_rows'
    appended = old + [dict(trade_date='2026-01-05', close=101, volume=21)]
    assert module.row_changes(old, appended)['kind'] == 'append_only'
    assert module.row_changes(old, [dict(old[0], volume=21)])['changed_fields'] == {'volume': 1}
    assert module.row_changes(old, [dict(old[0], close=100.000001)])['kind'] == 'revised_or_removed'
    assert module.row_changes(old, [])['removed'] == ['2026-01-02']
    assert module.row_changes(old, [dict(trade_date='2025-12-31', close=99)] + old)['kind'] == 'historical_insertion'
    with pytest.raises(ValueError, match='Duplicate'):
        module.row_changes(old, old + old)


def test_scopes_follow_recorded_nested_dependencies():
    inputs = dict(governed_files={'bars/SPY.jsonl.gz': 'one'},
                  m1_14=dict(governed_files={'bars/XLE.jsonl.gz': 'two'}),
                  independent=dict(capture='not a price dependency'))
    assert [name for name, _ in module.input_scopes(inputs)] == ['base', 'm1_14']


def test_independent_frozen_scope_is_not_compared_to_current_catalog(tmp_path, monkeypatch):
    catalog = tmp_path / 'catalog.json'
    catalog.write_text('[]')
    monkeypatch.setattr(module, 'GovernedInputs', lambda root, batch: SimpleNamespace(checked=lambda name: catalog))
    publication = dict(version='old', provenance=json.dumps(dict(root=str(tmp_path))))
    calculation = dict(version='calculation', provenance=json.dumps(dict(inputs=dict(
        batch='old', governed_files={},
        frozen=dict(batch='independent', governed_files={'bars/SPY.jsonl.gz': 'frozen'})))))
    result = module.audit(SimpleNamespace(publication=lambda *args: publication), calculation,
                          dict(publication, version='new'))
    assert result['scope_comparison']['frozen']['status'] == 'independently_pinned_scope_not_compared_to_current_catalog'
    assert result['authority'] == 'diagnostic_only'


def test_changed_original_evidence_fails_instead_of_claiming_equivalence(tmp_path, monkeypatch):
    artifact = tmp_path / 'bars'
    artifact.write_bytes(b'changed')
    monkeypatch.setattr(module, 'GovernedInputs', lambda root, batch: SimpleNamespace(checked=lambda name: artifact))
    publication = dict(version='old', provenance=json.dumps(dict(root=str(tmp_path))))
    calculation = dict(version='calculation', provenance=json.dumps(dict(inputs=dict(
        batch='old', governed_files={'bars/SPY.jsonl.gz': 'expected-original-hash'}))))
    with pytest.raises(ValueError, match='Original calculation artifact differs'):
        module.audit(SimpleNamespace(publication=lambda *args: publication), calculation,
                     dict(publication, version='new'))
