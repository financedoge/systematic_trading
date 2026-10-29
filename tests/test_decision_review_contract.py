import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/decision-review-20261028-v1'


def test_frozen_training_and_code():
    p=json.loads((OUT/'protocol.json').read_text());fits=json.loads((OUT/'fits.json').read_text())
    for name,digest in p['code'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    assert len(fits)==52
    assert sum(len(v) for v in fits.values())==102
    for v in fits.values():
        for era,fit in v.items():
            s=fit['seed'];assert s['last_origin']<s['last_maturity']<=s['cutoff']
            assert s['observations']<=756 and min(s['n'])>=20


def test_full_pool_controls_and_net_metrics():
    rows=json.loads((OUT/'asset-results.json').read_text());checks=json.loads((OUT/'validation.json').read_text())
    assert len(rows)==1836 and checks['control_cases']==612
    for k in ('max_control_error','max_disabled_review_error','max_independent_ledger_error'):assert checks[k]<1e-11
    assert len({(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']) for r in rows})==len(rows)
    for r in rows:
        assert r['cost_bp_annual']>=0 and r['stop_slippage_bp_annual']>=0
        assert r['recovery_closed']<=r['closed_trades']
        if r['forecast_brier'] is not None:assert 0<=r['forecast_brier']<=1 and -5<r['forecast_logscore']<0


def test_full_chart_inventory_and_execution_timing():
    charts=json.loads(gzip.decompress((OUT/'chart-data.json.gz').read_bytes()))
    assert len(charts)==102
    for c in charts.values():
        assert set(c['arms'])=={'baseline','stop','review'}
        for arm,a in c['arms'].items():
            assert len(a['nav'])==len(c['days'])
            for e in a['trades']:assert e['entry_index']==e['entry_signal']+1
            if arm!='baseline':
                w=np.array([v for v in a['recent_weight'] if v is not None]);assert np.all((w>=0)&(w<=1))
        for key in ('open','high','low','close','volume'):assert all(v>0 for v in c[key])
