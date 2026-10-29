"""Independent native Windows portfolio accounting for loss-feedback targets."""
from decimal import Decimal
import json
import shutil

import numpy as np

import research_loss_feedback as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    study.verified()
    if AppSettings().lean_runtime_backend != 'native':raise ValueError('Native Windows required')
    contract=study.WORK/'native-contract'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=[
            'USD adjusted-unit research, precomputed causal ETF-health targets, no broker authority']))
        study.write(contract/'input_manifest.json',dict(protocol_sha256=study.prior.study.digest(study.OUT/'protocol.json'),
            signal_sha256=study.prior.study.digest(study.WORK/'signals.npz')))
    parent=study.prior.study
    panel=parent.frozen._load_panel();recipe=json.loads(parent.frozen.RECIPE_PATH.read_text())
    replay=parent.frozen._Replay(panel,recipe,'2023-01-03')
    with np.load(study.WORK/'native-mappings.npz',allow_pickle=False) as a:mappings={k:a[k] for k in a.files}
    with np.load(study.WORK/'native-nav.npz',allow_pickle=False) as a:paths={k:a[k] for k in a.files}
    image=json.loads((study.ROOT/'config/strategy-monitoring.json').read_text())['calculation']['image']
    close=np.column_stack([panel['close'],panel['urth_close']]);receipts=[]
    for name,delay in (('severity_overlay_dynamic',0),('severity_overlay_dynamic',1),('severity_selection_dynamic',0)):
        key=f'{name}_c5d{delay}';weights,indices=mappings[key+'_weights'],mappings[key+'_indices']
        schedule=replay.decisions(weights,indices,delay)
        ix={str(panel['days'][t+1+delay]):int(t) for t in indices if t+1+delay<len(panel['days'])}
        decisions={str(day):dict(signal_session=str(panel['days'][ix[str(day)]]),known_through=str(panel['days'][ix[str(day)]]),
                   targets=[t.model_dump(mode='json') for t in targets]) for day,targets in schedule.items()}
        quotes={}
        for j,symbol in enumerate(replay.symbols):
            quotes[symbol]={}
            for day in replay.days:
                t=ix.get(str(day));ref=quantize_money(Decimal(str(close[t,j]))) if t is not None else replay.reference[day][symbol]
                quotes[symbol][str(day)]=dict(open=str(replay.open[day][symbol]),close=str(replay.close[day][symbol]),reference=str(ref))
        bundle,target=study.WORK/'native-bundles'/key,study.WORK/'native'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,list(map(str,replay.days)),5)
        receipt=native_parity(bundle,target,image,cpus='2')
        actual=json.loads((target/'economic.json').read_text())
        difference=float(np.max(np.abs(np.array([float(r['nav']) for r in actual['nav']])-paths[key][1:])))
        if difference>.011:raise ValueError('Native NAV mismatch')
        receipts.append(dict(scenario=key,max_nav_difference=difference,status=receipt['status'],
            bundle_sha256=parent.digest(bundle/'manifest.json'),receipt_sha256=parent.digest(target/'run.json')))
        study.write(study.OUT/'native-checks.json',receipts)
        print('Native verified',key,difference,flush=True)


if __name__=='__main__':main()
