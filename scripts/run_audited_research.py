"""Run exactly the predeclared audited-input matrix with native LEAN parity."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from run_constituent_research import verify_manifest
from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.runner import run_bundle
from systematic_trading.research.constituent_signals import ConstituentOverlaySpec
from systematic_trading.research.flow_concentration import FlowConcentrationSpec


def run(root, workers):
    verify_manifest(root,'input_manifest.json')
    def read(name):
        return json.loads((root/(name+'.json')).read_text(encoding='utf8'))
    protocol,bars,fx,features,old,models = [read(n) for n in ('protocol','bars','fx','features','old_features','base_tree_models')]
    provenance=dict(input_manifest=sha256(root/'input_manifest.json'),root=str(root),**read('provenance'))
    def trial(name,cfg):
        bundle,output=root/'datasets'/name,root/'runs'/name
        if (output/'run.json').exists():
            receipt=json.loads((output/'run.json').read_text())
            if receipt['status']!='succeeded':
                raise ValueError('Inspect failed immutable run: '+name)
            return name,receipt
        if not bundle.exists():
            options=dict(start_date=cfg.get('start',protocol['start']),end_date=protocol['end'],warmup_start=protocol['warmup_start'],
                strategy='sota_flow' if 'flow' in cfg else 'sota_constituents' if cfg.get('constituent') is not None else 'sota',
                mode='shared' if name in ('sota','early_signed','tree_joint','fixed_sota') else 'targets',
                fx_policy='legacy_carry_max7',base_tree_model_schedule=not cfg.get('fixed_model',False),limitations=[protocol['limitations'],protocol['etf_basis'],protocol['constituent_basis']],
                **cfg.get('stress',{}))
            if cfg.get('constituent') is not None:
                options['constituent_overlay']=ConstituentOverlaySpec(**cfg['constituent']).model_dump()
            if 'flow' in cfg:
                options['flow_overlay']=FlowConcentrationSpec(**cfg['flow']).model_dump()
            print('FREEZE',name,flush=True)
            freeze_bundle(root=bundle,bars=bars,fx=fx,provenance=provenance,spec_values=options,
                constituent_features=(old if cfg.get('feature_set')=='old' else features) if cfg.get('constituent') is not None else None,
                base_tree_models=models if options['base_tree_model_schedule'] else None)
        print('LEAN',name,flush=True)
        receipt=run_bundle(bundle=bundle,output=output,image=protocol['image'])
        print('PASS',name,round(receipt['elapsed_seconds'],1),flush=True)
        return name,receipt
    passed={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(trial,name,cfg) for name,cfg in protocol['trials'].items()]
        for future in as_completed(futures):
            name,receipt=future.result();passed[name]=receipt['economic_sha256']
            write_json(root/'progress.json',dict(complete=False,passed=passed))
    write_json(root/'progress.json',dict(complete=True,passed=passed))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    args=parser.parse_args();run(args.root,args.workers)
