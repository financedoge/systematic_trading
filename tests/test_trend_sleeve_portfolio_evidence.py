"""Read-only consistency checks on completed N15 evidence."""
import gzip
import json
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/trend-sleeve-portfolio-20261029-v1'


def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def compressed(name):return json.loads(gzip.decompress((OUT/name).read_bytes()))


def test_reproduced_shadows_and_real_warmup():
    v=read('shadow-validation.json')
    assert v['cases']==612 and v['max_cumulative_error']==0
    for era,m in v['eras'].items():
        assert m['start']>=252 and m['shadow_start']>m['train_end']
        assert m['first_fill']>m['first_signal']
    assert v['eras']['early']['first_signal']=='2020-12-31'
    assert v['eras']['late']['first_signal']=='2024-01-31'


def test_allocations_signals_and_net_contributions():
    d=compressed('detail.json.gz');a=read('attribution.json')
    for key,z in d.items():
        assert np.all(np.array(z['cash'])>=-1e-12)
        np.testing.assert_allclose(np.sum(z['holdings'],axis=1)+z['cash'],1,atol=1e-12)
        np.testing.assert_allclose(np.diff(z['nav']),np.sum(z['contribution'],axis=1)[1:],atol=1e-12)
        assert sum(row['pnl'] for row in a[key])==pytest.approx(z['nav'][-1]-1,abs=1e-12)
        for decision in z['decisions']:
            assert decision['date']<decision['execution_date']
            if '_all_' not in key:assert np.count_nonzero(decision['weights'])==15
            assert sum(decision['weights'])==pytest.approx(1)
            assert sum(decision['theoretical'])==pytest.approx(1)
            if decision['reason']=='target-change':assert decision['distance']>=.1-1e-12


def test_declared_case_counts_and_native_scope():
    assert len(read('results.json'))==106
    v=read('validation.json');assert v['independent_ledger_max_error']<1e-10
    n=read('native-checks.json');assert len(n)==3
    for row in n:
        assert row['status']=='succeeded' and row['max_native_reference_usd']<=.01
        assert 'oracle' in row['limitation']


def test_dynamic_decisions_use_last_adopted_not_future_target():
    for key,z in compressed('detail.json.gz').items():
        if 'dynamic' not in key:continue
        for decision in z['decisions']:
            adopted=[a for a in z['adoptions'] if a['date']<=decision['date']]
            last=np.array(adopted[-1]['theoretical']) if adopted else np.r_[np.zeros(len(z['symbols'])),1]
            assert np.abs(np.array(decision['theoretical'])-last).sum()==pytest.approx(decision['distance'])
