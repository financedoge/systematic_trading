"""Independent Windows-native LEAN accounting checks for the fixed net retest."""
from pathlib import Path
import shutil

import numpy as np

import research_cash_relative_retest as study
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    p = study.validate()
    if AppSettings().lean_runtime_backend != 'native':
        raise ValueError('This study requires native Windows LEAN')
    study.init_worker()
    engine = study.ENGINE
    selected = study.read(study.OUT/'selection.json')['selected']
    cases = [(selected, 5, 0), (selected.replace('_cash_relative_', '_remove_bill_'), 5, 0),
             ('class_cash_relative_risk-0.10', 20, 1)]
    contract = study.WORK/'native-contract-v2'
    if not contract.exists():
        contract.mkdir()
        shutil.copytree(study.REPO/'src/systematic_trading', contract/'source/systematic_trading',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        study.write(contract/'protocol.json', dict(initial_cash_usd=1_000_000, limitations=p['limitations'],
                    study_protocol_sha256=study.digest(study.OUT/'protocol.json')))
        study.write(contract/'input_manifest.json', {f.relative_to(contract).as_posix(): study.digest(f)
                    for f in sorted(contract.rglob('*')) if f.is_file()})
    study.verify(contract, 'input_manifest.json')
    quotes = {s: {str(d): dict(open=str(engine.open[d][s]), close=str(engine.close[d][s]),
                              reference=str(engine.reference[d][s])) for d in engine.days}
              for s in engine.symbols}
    recipe = study.read(study.WORK/'recipe.json')
    records = []
    for arm, cost, delay in cases:
        key = f'{arm}_c{cost}d{delay}'
        schedule = engine.decisions(study.SCHEDULES[arm+'_weights'], study.SCHEDULES[arm+'_indices'], delay)
        known = {str(study.ARRAYS['days'][i+1+delay]): str(study.ARRAYS['days'][i])
                 for i in study.SCHEDULES[arm+'_indices'] if i+1+delay < len(study.ARRAYS['days'])}
        decisions = {str(d): dict(signal_session=str(d), known_through=known[str(d)],
                     targets=[t.model_dump(mode='json') for t in targets]) for d, targets in schedule.items()}
        bundle, output = study.WORK/'native-bundles-v2'/key, study.WORK/'native-v2'/key
        freeze_usd_bundle(bundle, contract, recipe, decisions, quotes, list(map(str, engine.days)), cost)
        receipt = native_parity(bundle, output, None, cpus='2')
        actual = study.read(output/'economic.json')
        with np.load(study.WORK/'paths'/f'{key}.npz') as z:
            error = float(np.max(np.abs(np.array([float(r['nav']) for r in actual['nav']])-z['nav'])))
        if error > .01:
            raise ValueError('Native accounting differs from portfolio replay: '+key)
        records.append(dict(case=key, status=receipt['status'], max_nav_error_usd=error,
                            output=str(output.relative_to(study.REPO)),
                            receipt_sha256=study.digest(output/'run.json')))
        print(key, receipt['status'], error, flush=True)
    study.write(study.OUT/'native-validation.json', dict(cases=records,
        scope='Independent native LEAN orders/fills/cash/NAV validation on frozen targets, not independent policy inference.',
        validator_sha256=study.digest(Path(__file__))))


if __name__ == '__main__':
    main()
