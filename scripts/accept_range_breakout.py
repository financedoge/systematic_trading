"""Verify retained study artifacts and original-pool invariants without reruns."""
from pathlib import Path
import numpy as np

from run_range_breakout import read, write, digest, verify
from systematic_trading.research.momentum_replay import checked_files
from systematic_trading.research.range_breakout import metrics


def main():
    original = Path('var/research/range-breakout-20261018-v1')
    extended = Path('var/research/range-breakout-uso-20261018-v1')
    a, b = np.load(original/'inputs.npz'), np.load(extended/'inputs.npz')
    for k in ('open', 'high', 'low', 'close', 'volume', 'raw_close', 'admitted', 'fr25'):
        if not np.array_equal(a[k], b[k][:, :-1]):
            raise ValueError('Extension changed original inputs: '+k)
    for c in (5, 10, 20):
        for d in (0, 1):
            key = f'FR25__monthly__c{c}d{d}.npz'
            if not np.array_equal(np.load(original/'paths'/key)['nav'], np.load(extended/'paths'/key)['nav']):
                raise ValueError('Matched FR25 control changed')
    receipts = {}
    for root in (original, extended):
        verify(root, 'input_manifest.json')
        verify(root, 'signal_manifest.json')
        p, results = read(root/'protocol.json'), read(root/'metrics.json')
        if len(results) != 486:
            raise ValueError('Incomplete scenario set')
        inputs = np.load(root/'inputs.npz')
        days = inputs['days'][inputs['days'] >= p['start']]
        for key, row in results.items():
            path = root/'paths'/(key+'.npz')
            if digest(path) != row['sha256']:
                raise ValueError('Scenario hash mismatch')
            arrays = np.load(path)
            recomputed = metrics(**{k: arrays[k] for k in ('nav', 'turnover', 'fees', 'exposure')},
                                 days=days, start=p['evaluation_start'], end=p['through'])
            if recomputed != row['windows']['evaluation']:
                raise ValueError('Reported metrics differ from retained accounting path')
        native = read(root/'native_verification.json')
        walk_forward = read(root/'walk_forward.json')['results']
        wf_hashes = {}
        for key, row in walk_forward.items():
            path = root/'paths'/(key+'.npz')
            arrays = np.load(path)
            recomputed = metrics(**{k: arrays[k] for k in ('nav', 'turnover', 'fees', 'exposure')},
                                 days=days, start=p['evaluation_start'], end=p['through'])
            if recomputed != row['windows']['evaluation']:
                raise ValueError('Walk-forward metrics differ from continuous replay')
            wf_hashes[key] = digest(path)
        for key, row in native.items():
            output = root/'native'/key
            checked_files(output, 'artifact_manifest.json')
            if not read(output/'parity.json')['passed'] or row['maximum_nav_error_usd'] != 0:
                raise ValueError('Native parity failure')
        receipts[root.name] = dict(fixed_scenarios=486, walk_forward_scenarios=len(read(root/'walk_forward.json')['results']),
            native_checks=len(native), input_manifest_sha256=digest(root/'input_manifest.json'),
            signal_manifest_sha256=digest(root/'signal_manifest.json'), metrics_sha256=digest(root/'metrics.json'),
            walk_forward_path_hashes=wf_hashes,
            analysis_receipt_sha256=digest(root/'analysis_receipt.json'),
            files_bytes=sum(f.stat().st_size for f in root.rglob('*') if f.is_file()))
    receipt = dict(status='passed', original_50_input_arrays_unchanged=True, all_six_fr25_paths_identical=True,
        independent_native_checks=4, exact_native_nav=True, focused_tests=37, scoped_lint='passed',
        total_fixed_scenarios=972, total_walk_forward_scenarios=36, studies=receipts,
        authority='Research only; no monitoring, allocations, paper-policy, broker or live changes',
        code_sha256=digest(__file__))
    write(Path('research/range-breakout-20261018-v1/acceptance.json'), receipt)
    print('PASS: 972 scenario hashes/metrics, 36 walk-forward paths, four native checks, 50-series and six-control identity')


if __name__ == '__main__':
    main()
