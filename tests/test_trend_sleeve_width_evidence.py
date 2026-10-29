import gzip
import json
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/trend-sleeve-width-20261029-v1'
BASE=ROOT/'research/trend-sleeve-portfolio-20261029-v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def gz(p):return json.loads(gzip.decompress(p.read_bytes()))


def test_same_chronology_inputs_and_all_declared_cases():
    rows=read(OUT/'results.json');old=read(BASE/'results.json');assert len(rows)==120
    assert read(OUT/'validation.json')['shadows']==read(BASE/'validation.json')['shadows']
    for r in rows:
        b=next(b for b in old if b['era']==r['era'] and b['arm']==r['arm'] and b['cost_bp']==r['cost_bp'] and b['delay']==r['delay'])
        assert (r['first_signal'],r['last'],r['sessions'])==(b['first_signal'],b['last'],b['sessions'])
        assert r['n'] in (20,30)


def test_width_membership_and_cash_accounting():
    attrs=read(OUT/'attribution.json')
    for key,z in gz(OUT/'detail.json.gz').items():
        n=int(key.split('_n')[1].split('_')[0])
        for d in z['decisions']:assert np.count_nonzero(d['weights'])==n
        np.testing.assert_allclose(np.array(z['holdings']).sum(axis=1)+z['cash'],1,atol=1e-12)
        np.testing.assert_allclose(np.diff(z['nav']),np.array(z['contribution']).sum(axis=1)[1:],atol=1e-12)
        assert sum(a['pnl'] for a in attrs[key])==pytest.approx(z['nav'][-1]-1,abs=1e-12)


def test_wider_native_fixtures_and_comparison_guard_counts():
    native=read(OUT/'native-checks.json');assert len(native)==2
    assert all(r['status']=='succeeded' and r['max_native_reference_usd']<=.01 for r in native)
    rows=read(OUT/'assessment.json')
    a=[r for r in rows if r['n']==30 and r['arm']=='equal' and r['control']=='N15']
    b=[r for r in rows if r['n']==30 and r['arm']=='equal' and r['control']=='all']
    assert len(a)==len(b)==12 and sum(r['passed'] for r in a)==8 and not any(r['passed'] for r in b)
