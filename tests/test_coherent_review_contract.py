import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/coherent-review-20261028-v1'


def test_frozen_sources_folds_and_activation():
    p=json.loads((OUT/'protocol.json').read_text());fits=json.loads((OUT/'fits.json').read_text())
    for path,digest in p['code'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    assert len(fits)==52 and sum(map(len,fits.values()))==102
    for eras in fits.values():
        for era,f in eras.items():
            assert f['training_end']==('2022-12-30' if era=='late' else '2019-12-31')
            for kind,a in f['models'].items():
                assert a['first_origin']<a['last_origin']<a['last_maturity']<=f['training_end']
                s=a['selection'];assert len(s['folds'])==3
                for fold in s['folds']:assert fold['training_last_maturity']<fold['first']<=fold['last']<a['last_maturity']
                chosen=min(s['candidates'],key=lambda r:(r['loss'],r['ridge'] is not None,-(r['ridge'] or 0)))
                assert chosen['ridge']==s['chosen']==a['model']['ridge']
                assert a['enabled']==(chosen['ridge'] is not None and s['relative_loss_gain']>.005 and s['fold_wins']>=2)
                assert len(a['model']['beta'])==(6 if kind=='price' else 9)
                assert a['margin']==.05 and a['change']==.10


def test_full_pool_accounting_and_uniqueness():
    v=json.loads((OUT/'validation.json').read_text());rows=json.loads((OUT/'asset-results.json').read_text())
    assert v['control_cases']==612 and len(rows)==1836
    for k in ('max_control_error','max_disabled_review_error','max_independent_ledger_error'):assert v[k]<1e-11
    assert len(json.loads((OUT/'diagnostics.json').read_text()))==816
    assert len({(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']) for r in rows})==len(rows)
    assert len(json.loads((OUT/'forecast-diagnostics.json').read_text()))==204


def test_every_review_action_needs_changed_evidence():
    charts=json.loads(gzip.decompress((OUT/'chart-data.json.gz').read_bytes()));assert len(charts)==102
    for c in charts.values():
        offset=next(t['entry_index']-c['days'].index(t['entry_date']) for a in c['arms'].values() for t in a['trades']) if any(a['trades'] for a in c['arms'].values()) else 0
        for arm,kind in [('stop','price'),('review','volume')]:
            a=c['arms'][arm];fit=c['training']['models'][kind]
            if not fit['enabled']:
                np.testing.assert_allclose(np.array(a['nav'],float),np.array(c['arms']['baseline']['nav'],float),equal_nan=True,atol=1e-11)
            for t in a['trades']:
                assert t['entry_index']==t['entry_signal']+1
                if t['exit_reason']=='entry_invalidated':
                    i=t['exit_signal']-offset;assert a['shared_score'][i]<-.05
                    assert a['shared_score'][i]<t['entry_score']-.10
            for i,signal in enumerate(a['review_signal']):
                if signal:
                    assert fit['enabled'] and a['recover_value'][i]>.05
                    assert a['shared_score'][i]>a['decision_anchor'][i]+.10
                    assert a['shared_score'][i]>0  # cannot simultaneously meet learned exit
