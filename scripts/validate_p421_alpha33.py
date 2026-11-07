"""Independent Windows-native LEAN verification of three frozen pilot cases."""
from pathlib import Path
import shutil

import numpy as np

import backtest_p421_alpha33 as b
import research_p421_alpha33 as s
from research_cash_relative_retest import verify
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    p=s.protocol()
    a,schedules,recipe,engine=b.inputs()
    if AppSettings().lean_runtime_backend!='native':
        raise ValueError('Native LEAN required')
    contract=s.WORK/'native-contract-v1'
    if not contract.exists():
        contract.mkdir()
        shutil.copytree(s.ROOT/'src/systematic_trading',contract/'source/systematic_trading',
            ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        s.write(contract/'protocol.json',dict(initial_cash_usd=1_000_000,limitations=p['limitations'],
            study_protocol_sha256=s.digest(s.OUT/'protocol.json')))
        s.write(contract/'input_manifest.json',{f.relative_to(contract).as_posix():s.digest(f) for f in sorted(contract.rglob('*')) if f.is_file()})
    verify(contract,'input_manifest.json')
    quotes={symbol:{str(day):dict(open=str(engine.open[day][symbol]),close=str(engine.close[day][symbol]),reference=str(engine.reference[day][symbol]))
        for day in engine.days} for symbol in engine.symbols}
    cases=[]
    for arm,cost,delay in [('constituent33-monthly',5,0),('etf33-monthly',5,0),('constituent33-0.40',20,1)]:
        key=f'{arm}_c{cost}d{delay}'
        indices=schedules[arm+'_indices']
        schedule=engine.decisions(schedules[arm+'_weights'],indices,delay)
        known={str(a['days'][i+1+delay]):str(a['days'][i]) for i in indices if i+1+delay<len(a['days'])}
        decisions={str(day):dict(signal_session=str(day),known_through=known[str(day)],targets=[t.model_dump(mode='json') for t in targets]) for day,targets in schedule.items()}
        bundle,output=s.WORK/'native-bundles-v1'/key,s.WORK/'native-v1'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,list(map(str,engine.days)),cost)
        receipt=native_parity(bundle,output,None,cpus='2')
        actual=s.read(output/'economic.json')
        expected=dict(np.load(s.WORK/'paths'/f'{key}.npz'))
        error=float(np.max(np.abs(np.array([float(r['nav']) for r in actual['nav']])-expected['nav'])))
        if error>.01:
            raise ValueError('Native NAV mismatch '+key)
        cases.append(dict(case=key,status=receipt['status'],max_nav_error_usd=error,
            output=str(output.relative_to(s.ROOT)),receipt_sha256=s.digest(output/'run.json')))
        print('Native verification',key,receipt['status'],'NAV error',error,flush=True)
    s.write(s.OUT/'native-validation.json',dict(cases=cases,validator_sha256=s.digest(Path(__file__)),
        scope='Independent order/fill/cash/NAV replay from frozen targets; not independent inference or an external alpha replication.'))


if __name__=='__main__':
    main()
