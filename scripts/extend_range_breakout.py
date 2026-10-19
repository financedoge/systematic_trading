"""Operator-authorized USO extension; preserve the original 50-series experiment."""
from pathlib import Path
import shutil
import os
import subprocess
import sys

import numpy as np
import pandas as pd

from run_range_breakout import read, write, digest, verify, manifest

BASE = Path('var/research/range-breakout-20261018-v1')
ROOT = Path('var/research/range-breakout-uso-20261018-v1')


def prepare():
    if ROOT.exists():
        verify(ROOT, 'input_manifest.json')
        return
    verify(BASE, 'input_manifest.json')
    from systematic_trading.config import get_settings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.etf_expansion import load_published_pool
    from systematic_trading.research.etf_admission import admission_hold
    publication = AnalyticsStore.from_settings(get_settings()).latest('governance/catalog')
    provenance = read(BASE/'price_pin.json')
    import json
    price_root = Path(json.loads(publication['provenance'])['root'])
    reader = GovernedInputs(price_root, publication['version'])
    a = dict(np.load(BASE/'inputs.npz'))
    p = read(BASE/'protocol.json')
    inventory = read('research/etf-universe-inventory-2026-10-13/inventory.json')
    uso = next(f for f in inventory['candidates'] if f['symbol'] == 'USO')
    audit = reader.audit('USO')
    if (audit['name'] != 'United States Oil Fund, LP' or audit['status'] != 'audited_with_limitations'
            or audit['unresolved_historical_names'] or audit['internal_gaps'] or admission_hold('USO')):
        raise ValueError('USO identity/coverage is unresolved')
    # This is explicitly provider-identity retrospective research, like the
    # original legacy ETFs, not first-wave recorder or paper-trading admission.
    fund = dict(uso, requires_recorder=False)
    pool = load_published_pool(reader, [fund], through=p['through'], start=str(a['days'][0]))
    if 'USO' not in pool['bars'] or pool['calendar'] != a['days'].tolist():
        raise ValueError('USO cannot share the exact frozen calendar: '+str(pool['exclusions']))
    for field in ('open', 'high', 'low', 'close'):
        a[field] = np.column_stack([a[field], [float(r[field]) for r in pool['bars']['USO']]])
    for key, field in (('volume', 'volume'), ('raw_close', 'close')):
        a[key] = np.column_stack([a[key], [float(r[field]) for r in pool['raw_bars']['USO']]])
    dollar = pd.Series(a['raw_close'][:, -1]*a['volume'][:, -1])
    eligible = (dollar.rolling(63).median() >= 5e6) & (dollar.rolling(63).min() >= 5e5)
    eligible.iloc[:252] = False
    a['admitted'] = np.column_stack([a['admitted'], eligible.to_numpy()])
    a['fr25'] = np.column_stack([a['fr25'], np.zeros(len(a['days']))])
    a['symbols'] = np.concatenate([a['symbols'], np.array(['USO'])])
    construction = read(BASE/'construction.json')
    construction['classes']['commodity_crude_oil'] = ['USO']
    construction['overlap_parents']['DBC'].append('USO')
    recipe = read(BASE/'recipe.json')
    recipe['universeMembers'].append(dict(symbol='USO', name=audit['name'], asset_class='etf',
        exchange='NYSE', quote_currency='USD', country='US', sector='commodity_crude_oil'))
    p['version'] = 'range-breakout-lifecycle-uso-extension-v1'
    p['extension'] = dict(operator_requested=True, signal_parameters_changed=False,
        original_input_manifest_sha256=digest(BASE/'input_manifest.json'),
        description='Original 50 series unchanged plus USO from a separately pinned newer audited publication, truncated to the identical October 12 cutoff. No within-series splicing. All twelve variants, three uses, two clocks and six frictions repeated. Data extension inspected after original-pool results, not an untouched confirmatory replication.',
        identity='USO name/roles and no unresolved historical-name or coverage audit issues verified. Provider identity only; no security-master, historical mandate, broker or recorder admission claimed.',
        issuer_reference='https://www.uscfinvestments.com/uso',
        oil_basis='Oil-futures fund returns including fund implementation, not a spot oil price series.')
    ROOT.mkdir(parents=True)
    write(ROOT/'protocol.json', p)
    write(Path('research/range-breakout-20261018-v1/uso-extension-protocol.json'), p)
    write(ROOT/'construction.json', construction)
    write(ROOT/'recipe.json', recipe)
    write(ROOT/'candidates.json', read(BASE/'candidates.json')+[fund])
    np.savez_compressed(ROOT/'inputs.npz', **a)
    write(ROOT/'price_pin.json', dict(original=provenance, uso=dict(root=str(price_root), batch=reader.batch, through=p['through'])))
    receipt = read(BASE/'input_receipt.json')
    receipt.update(candidate_count=54, supported_count=51, symbols=a['symbols'].tolist(),
                   extension=p['extension'], uso_audit=audit, uso_verified_files=reader.used,
                   crude_oil_gap='Superseded by verified USO extension; DBO/BNO/USL/OILK lack published inputs.')
    receipt['case_studies']['USO'] = 'Crude-oil futures fund; provider-identity research limitation'
    write(ROOT/'input_receipt.json', receipt)
    shutil.copyfile(BASE/'fr25_decisions.json', ROOT/'fr25_decisions.json')
    shutil.copyfile(BASE/'runner.py', ROOT/'runner.py')
    shutil.copyfile(__file__, ROOT/'extension_runner.py')
    shutil.copytree(BASE/'source', ROOT/'source')
    manifest(ROOT, 'input_manifest.json', [f for f in ROOT.rglob('*') if f.is_file()])
    print('USO extension frozen: 51 supported / 54 reviewed; no changed signal parameters', flush=True)


if __name__ == '__main__':
    prepare()
    environment = dict(os.environ, PYTHONPATH=str((ROOT/'source').resolve()))
    for stage in ('signals', 'replay'):
        subprocess.run([sys.executable, '-B', str((ROOT/'runner.py').resolve()), stage,
                        '--root', str(ROOT.resolve())], env=environment, check=True)
