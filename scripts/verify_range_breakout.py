"""Independent engine checks for representative frozen range-breakout mappings."""
import importlib.util
from pathlib import Path
import sys
import shutil
import argparse

import numpy as np

ROOT = Path('var/research/range-breakout-20261018-v1')


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--only', choices=('all', 'trading'), default='all')
    args = parser.parse_args()
    ROOT = args.root
    spec = importlib.util.spec_from_file_location('frozen_range_runner', ROOT/'runner.py')
    study = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((ROOT/'source').resolve()))
    spec.loader.exec_module(study)
    study.verify(ROOT, 'input_manifest.json')
    study.verify(ROOT, 'signal_manifest.json')
    # The accepted native launcher resolves its deployment configuration relative
    # to the source root. Bind the exact existing configuration, including all
    # runtime/acceptance hashes; no guard or acceptance flag is changed.
    (ROOT/'config').mkdir(exist_ok=True)
    source_config = Path('config/native-runtime.json')
    target_config = ROOT/'config/native-runtime.json'
    if target_config.exists() and study.digest(target_config) != study.digest(source_config):
        raise ValueError('Native deployment configuration changed')
    if not target_config.exists():
        shutil.copyfile(source_config, target_config)
    study.write(ROOT/'native_config_receipt.json', dict(sha256=study.digest(target_config)))
    a, sig = dict(np.load(ROOT/'inputs.npz')), dict(np.load(ROOT/'signals.npz'))
    p, recipe = study.read(ROOT/'protocol.json'), study.read(ROOT/'recipe.json')
    replay = study.Replay(a, recipe, p['start'])
    mappings = study.mappings(ROOT, a, sig)
    from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity
    image = study.read('config/strategy-monitoring.json')['calculation']['image']
    quotes = {s: {str(d): {k: str(source[d][s]) for k, source in
                           (('open', replay.open), ('close', replay.close), ('reference', replay.reference))}
                  for d in replay.days} for s in replay.symbols}
    receipts = {}
    names = ('FR25__monthly', 'Ladaptive-V1-H1__trading__event', 'Ladaptive-V1-H1__tilt__event')
    if args.only == 'trading':
        names = ('Ladaptive-V1-H1__trading__event',)
    for name in names:
        mapping = mappings[name]
        rows = replay.decisions(mapping['weights'], mapping['indices'], 0)
        decisions = {str(d): dict(signal_session=str(d),
                     known_through=str(a['days'][list(a['days']).index(str(d))-1]),
                     targets=[t.model_dump(mode='json') for t in targets]) for d, targets in rows.items()}
        bundle = ROOT/'native_bundles'/name
        freeze_usd_bundle(bundle, ROOT, recipe, decisions, quotes, replay.day_strings.tolist(), 5)
        receipt = native_parity(bundle, ROOT/'native'/name, image, cpus='2')
        economic = study.read(ROOT/'native'/name/'economic.json')
        expected = np.load(ROOT/'paths'/(name+'__c5d0.npz'))['nav']
        actual = np.array([float(r['nav']) for r in economic['nav']])
        error = float(np.max(np.abs(actual-expected)))
        if error > .011:
            raise ValueError('Study / independent native NAV mismatch')
        receipts[name] = dict(status=receipt['status'], maximum_nav_error_usd=error,
                              bundle_manifest_sha256=study.digest(bundle/'manifest.json'),
                              parity=study.read(ROOT/'native'/name/'parity.json'))
        study.write(ROOT/'native_verification.json', receipts)
        print(name, 'native parity passed; maximum NAV error', error, flush=True)


if __name__ == '__main__':
    main()
