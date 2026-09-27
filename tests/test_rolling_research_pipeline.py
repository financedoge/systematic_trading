from copy import deepcopy
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('rolling_study_test', SCRIPTS/'run_rolling_model_research.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_complete_trial_family_and_matched_stresses():
    protocol = study.read(SCRIPTS.parent/'config/rolling-model-research-v1.json')
    matrix = study.trial_matrix(protocol)
    assert len(matrix) == 41
    for family in protocol['families']:
        for years in (1, 2):
            name = f'{family}_{years}y'
            assert matrix[name]['model'] == name
            assert matrix['long_'+name]['model'] == name
            for stress in ('cost45bps', 'delay1'):
                assert matrix[name+'__'+stress]['stress'] == matrix['sota__'+stress]['stress']
                assert matrix[name+'__'+stress]['comparator'] == 'sota__'+stress


def test_feature_context_cannot_observe_future_rows(monkeypatch):
    days = [str(date(2020, 1, 1)+timedelta(days=i)) for i in range(700)]
    bars = {s: [dict(trade_date=d, open=str(p+i), high=str(p+i+1), low=str(p+i-1),
                     close=str(p+i), volume=100) for i, d in enumerate(days)] for s, p in [('SPY', 100), ('TLT', 200)]}
    def observed_feature(*, symbol, context):
        assert all(r.trade_date < context.as_of for rows in context.bars_by_symbol.values() for r in rows)
        return {'last_close': float(context.bars_by_symbol[symbol][-1].close)}
    monkeypatch.setattr(study, 'compute_signal_features', observed_feature)
    before = study.build_records(bars)
    changed = deepcopy(bars)
    for rows in changed.values():
        for row in rows:
            if row['trade_date'] >= before[0]['signal_session']:
                row['close'] = str(float(row['close'])*10)
    after = study.build_records(changed)
    assert before[0]['inputs'] == after[0]['inputs']
    assert before[0]['relative_return'] != after[0]['relative_return']
    assert before[0]['known_through'] < before[0]['label_end']


def test_study_manifest_rejects_modified_files_and_escape(tmp_path):
    study.write_json(tmp_path/'data.json', {'value': 1})
    study.write_json(tmp_path/'inputs.json', {'data.json': study.sha256(tmp_path/'data.json')})
    study.verify_files(tmp_path, 'inputs.json')
    study.write_json(tmp_path/'data.json', {'value': 2})
    with pytest.raises(ValueError, match='changed'):
        study.verify_files(tmp_path, 'inputs.json')
    study.write_json(tmp_path/'inputs.json', {'../escape': 'unused'})
    with pytest.raises(ValueError, match='changed'):
        study.verify_files(tmp_path, 'inputs.json')
