"""Matched portfolio regression and independent native USD accounting checks."""
from decimal import Decimal
import json
import shutil
import sys

import numpy as np

import research_latent_slope as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    study.verified()
    old=study.parent
    receipt=json.loads((old.OUT/'validation.json').read_text())
    if study.study.digest(old.WORK/'signals.npz')!=receipt['signal_sha256']:
        raise ValueError('Old signal input changed')
    control=json.loads((old.OUT/'portfolio-results.json').read_text())
    lookup={(r['era'],r['scenario'],r['cost_bp'],r['delay']):r for r in control}
    rows=json.loads((study.OUT/'portfolio-results.json').read_text())
    count,error=0,0.
    for r in rows:
        if r['scenario'].startswith('selected_'):continue
        comparison=r['scenario'].replace('baseline_','selected_')
        b=lookup[r['era'],comparison,r['cost_bp'],r['delay']]
        for key in ('cagr','sharpe','max_drawdown','annual_turnover','annual_cost_bps'):
            error=max(error,abs(r[key]-b[key]))
        count+=1
    if error>1e-10:raise ValueError('Matched portfolio control changed')
    study.write(study.OUT/'control-validation.json',dict(cases=count,max_metric_error=error))
    assets=json.loads((study.OUT/'asset-results.json').read_text())
    prior_assets=json.loads((old.OUT/'asset-results.json').read_text())
    ai={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in prior_assets if r['variant']=='selected'}
    acount,aerror=0,0.
    for r in assets:
        if r['variant']!='baseline':continue
        b=ai[r['symbol'],r['era'],r['cost_bp'],r['delay']]
        for key in ('cumulative','cagr','sharpe','maxdd','exposure','turnover_annual','cost_bp_annual'):
            aerror=max(aerror,abs(r[key]-b[key]))
        acount+=1
    if aerror>1e-10:raise ValueError('Matched asset control changed')
    study.write(study.OUT/'asset-control-validation.json',dict(cases=acount,max_metric_error=aerror))
    if '--controls-only' in sys.argv:return
    if AppSettings().lean_runtime_backend!='native':raise ValueError('Native Windows LEAN required')
    contract=study.WORK/'native-contract'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=['USD adjusted-unit research only; precomputed causal targets; no broker authority.']))
        study.write(contract/'input_manifest.json',dict(protocol_sha256=study.study.digest(study.OUT/'protocol.json'),signal_sha256=study.study.digest(study.WORK/'signals.npz')))
    panel=study.study.frozen._load_panel();recipe=json.loads(study.study.frozen.RECIPE_PATH.read_text());replay=study.study.frozen._Replay(panel,recipe,'2023-01-03')
    with np.load(study.WORK/'native-mappings.npz',allow_pickle=False) as a:mappings={k:a[k] for k in a.files}
    with np.load(study.WORK/'native-nav.npz',allow_pickle=False) as a:paths={k:a[k] for k in a.files}
    image=json.loads((study.ROOT/'config/strategy-monitoring.json').read_text())['calculation']['image']
    close=np.column_stack([panel['close'],panel['urth_close']]);receipts=[]
    for name,delay in (('selected_overlay_dynamic',0),('selected_overlay_dynamic',1),('selected_selection_dynamic',0)):
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
            bundle_sha256=study.study.digest(bundle/'manifest.json'),receipt_sha256=study.study.digest(target/'run.json')))
        study.write(study.OUT/'native-checks.json',receipts)
        print('Native verified',key,difference,flush=True)


if __name__=='__main__':main()
