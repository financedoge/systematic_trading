import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/trained-review-20261028-v1'


def test_frozen_training_and_activation_guards():
    p = json.loads((OUT / 'protocol.json').read_text())
    fits = json.loads((OUT / 'fits.json').read_text())
    for name, digest in p['code'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert len(fits) == 52 and sum(map(len, fits.values())) == 102
    for eras in fits.values():
        for era, f in eras.items():
            assert f['training_start'] < f['validation_start'] < f['training_end']
            assert f['training_end'] == ('2022-12-30' if era == 'late' else '2019-12-31')
            for kind, family in f['models'].items():
                assert kind in ('price', 'volume')
                assert family['margin'] in (None, 0, .25, .5)
                control = family['validation_control']
                admissible = []
                for c in family['validation_candidates']:
                    passed = (c['sharpe'] > control['sharpe'] + .01
                              and c['return'] >= control['return'] - .005
                              and c['maxdd'] >= control['maxdd'] - .01)
                    assert c['passed'] == passed
                    if passed:
                        admissible.append(c)
                chosen = max(admissible, key=lambda c: (c['sharpe'], c['return'], c['margin'])) if admissible else None
                assert family['margin'] == (chosen['margin'] if chosen else None)
                for task, m in family['models'].items():
                    assert task in ('hold', 'recover')
                    d = 11 if kind == 'price' else 14
                    assert np.asarray(m['beta']).shape == (d, 2)
                    assert np.isfinite(m['beta']).all() and min(m['scale']) >= .1
                    assert m['ridge'] in (None, 1, 10, 100)
                    s = family['selection'][task]
                    assert m['ridge'] == s['ridge']
                    assert s['validation_loss'] == min(c['loss'] for c in s['candidates'])


def test_full_pool_controls_and_diagnostics():
    rows = json.loads((OUT / 'asset-results.json').read_text())
    checks = json.loads((OUT / 'validation.json').read_text())
    assert len(rows) == 1836 and checks['control_cases'] == 612
    assert len(json.loads((OUT / 'diagnostics.json').read_text())) == 612
    for k in ('max_control_error', 'max_disabled_review_error', 'max_independent_ledger_error'):
        assert checks[k] < 1e-11
    assert len({(r['symbol'], r['era'], r['arm'], r['cost_bp'], r['delay']) for r in rows}) == len(rows)
    for r in rows:
        assert r['cost_bp_annual'] >= 0 and r['stop_slippage_bp_annual'] >= 0
        assert r['recovery_wins'] <= r['recovery_closed'] <= r['closed_trades']
        assert r['resets'] == r['changes'] == 0
    forecasts = json.loads((OUT / 'forecast-diagnostics.json').read_text())
    assert len(forecasts) == 204
    for r in forecasts:
        for task in ('hold', 'recover'):
            if r[task]['count']:
                assert all(r[task][k]['loss'] >= 0 for k in ('fixed', 'shadow', 'constant'))


def test_full_chart_inventory_execution_and_disabled_identity():
    charts = json.loads(gzip.decompress((OUT / 'chart-data.json.gz').read_bytes()))
    assert len(charts) == 102
    for c in charts.values():
        assert set(c['arms']) == {'baseline', 'stop', 'review'}
        for arm, a in c['arms'].items():
            assert len(a['nav']) == len(c['days'])
            for e in a['trades']:
                assert e['entry_index'] == e['entry_signal'] + 1
                if e['exit_reason'] == 'entry_invalidated':
                    assert e['exit_index'] == e['exit_signal'] + 1
            if arm != 'baseline':
                assert set(a['reviewer_owned']) <= {None, False, True}  # pre-evaluation padding is missing
                kind = 'price' if arm == 'stop' else 'volume'
                if c['training']['models'][kind]['margin'] is None:
                    np.testing.assert_allclose(np.array(a['nav'], float), np.array(c['arms']['baseline']['nav'], float), equal_nan=True, atol=1e-11)
        for key in ('open', 'high', 'low', 'close', 'volume'):
            assert all(v > 0 for v in c[key])
