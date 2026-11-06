"""Independent Windows-native LEAN accounting checks for the ETF stability study."""
from pathlib import Path
import shutil

import numpy as np

import research_etf_stability as study
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    p = study.validate()
    if AppSettings().lean_runtime_backend != 'native':
        raise ValueError('This study requires native Windows LEAN')
    arrays = study.breadth.input_arrays()
    schedules = dict(np.load(study.WORK/'schedules.npz'))
    recipe = study.read(study.parent.WORK/'recipe.json')
    engine = study.Replay(arrays, recipe, study.parent.START)
    cases = [('selected', 5, 0), ('expanded', 5, 0), ('alternate', 20, 1)]
    contract = study.WORK/'native-contract-v1'
    if not contract.exists():
        contract.mkdir()
        shutil.copytree(study.REPO/'src/systematic_trading', contract/'source/systematic_trading',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        study.write(contract/'protocol.json', dict(initial_cash_usd=1_000_000, limitations=p['limits'],
                    study_protocol_sha256=study.digest(study.OUT/'protocol.json')))
        study.write(contract/'input_manifest.json', {f.relative_to(contract).as_posix(): study.digest(f)
                    for f in sorted(contract.rglob('*')) if f.is_file()})
    from research_cash_relative_retest import verify
    verify(contract, 'input_manifest.json')
    quotes = {s: {str(d): dict(open=str(engine.open[d][s]), close=str(engine.close[d][s]),
                              reference=str(engine.reference[d][s])) for d in engine.days}
              for s in engine.symbols}
    records = []
    for arm, cost, delay in cases:
        key = f'{arm}_c{cost}d{delay}'
        schedule = engine.decisions(schedules[arm+'_weights'], schedules[arm+'_indices'], delay)
        known = {str(arrays['days'][i+1+delay]): str(arrays['days'][i])
                 for i in schedules[arm+'_indices'] if i+1+delay < len(arrays['days'])}
        decisions = {str(d): dict(signal_session=str(d), known_through=known[str(d)],
                     targets=[t.model_dump(mode='json') for t in targets]) for d, targets in schedule.items()}
        bundle, output = study.WORK/'native-bundles-v1'/key, study.WORK/'native-v1'/key
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
