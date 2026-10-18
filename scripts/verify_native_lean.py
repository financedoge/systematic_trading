"""Replay retained USD/CNH strategies with only a portable-path adapter change."""
import argparse
from hashlib import sha256 as hash_bytes
import json
import os
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256,write_json,verify_bundle
from systematic_trading.lean.native_runner import run_native_bundle
from systematic_trading.lean.runner import compare_outputs
from systematic_trading.research.momentum_replay import verify_usd_bundle


def portable_copy(original,target,contract):
    verify=verify_usd_bundle if contract=='usd' else verify_bundle
    verify(original)
    adapter='source/systematic_trading/'+('research/momentum_lean.py' if contract=='usd' else 'lean/algorithm.py')
    if not target.exists():
        for path in original.rglob('*'):
            if not path.is_file():continue
            relative=path.relative_to(original);dest=target/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            if relative.as_posix() in (adapter,'spec.json','manifest.json'):shutil.copyfile(path,dest)
            else:os.link(path,dest)
        path=target/adapter
        text=path.read_text(encoding='utf8').replace('import json\n','import json\nimport os\n',1)
        text=text.replace("sys.path.insert(0, '/input/source')",
            "INPUT_ROOT=Path(os.environ['ST_LEAN_INPUT_ROOT'])\nOUTPUT_ROOT=Path(os.environ['ST_LEAN_OUTPUT_ROOT'])\nsys.path.insert(0,str(INPUT_ROOT/'source'))")
        text=text.replace("f'/input/quotes/{config.symbol.value.split(\".\")[0]}.csv'",
            "str(INPUT_ROOT/'quotes'/f'{config.symbol.value.split(\".\")[0]}.csv')")
        text=text.replace("Path('/input')","INPUT_ROOT")
        for name in ('resources.json','economic.json'):
            text=text.replace("Path('/output/"+name+"')","OUTPUT_ROOT/'"+name+"'")
        if '/input' in text or '/output' in text:raise ValueError('Unconverted frozen adapter paths')
        path.write_text(text,encoding='utf8')
        if contract=='cnh':
            spec=json.loads((target/'spec.json').read_text())
            h=hash_bytes()
            for p in sorted((target/'source').rglob('*')):
                if p.is_file():h.update(p.relative_to(target).as_posix().encode()+p.read_bytes())
            spec['source_hash']=h.hexdigest();write_json(target/'spec.json',spec)
        files={p.relative_to(target).as_posix():sha256(p)
            for p in sorted(target.rglob('*')) if p.is_file() and p.name!='manifest.json'}
        manifest=files if contract=='usd' else dict(json.loads((original/'manifest.json').read_text()),files=files)
        write_json(target/'manifest.json',manifest)
    verify(target)
    return dict(original_manifest_sha256=sha256(original/'manifest.json'),portable_manifest_sha256=sha256(target/'manifest.json'),
        adapter=adapter,original_adapter_sha256=sha256(original/adapter),portable_adapter_sha256=sha256(target/adapter),
        change='Path roots only; original strategy, decisions, market inputs and accounting retained')


def main(root,output):
    entries=[('m1_14','research_fr25_14_v1'),('m1_14','research_m1_14_v1'),('m1_14','research_fr25_alpha_tilt_5_v1'),
        ('usd','research_fallback_f3_v1'),('usd','research_economic_context_ridge_v1'),
        ('','research_etf_activity_lag20_v1_usd_v1'),('','research_rolling_xgboost_1y_lag20_v1_usd_v1')]
    results=[]
    for folder,key in entries:
        contract='usd' if folder else 'cnh'
        original=root/folder/('bundles' if folder else 'datasets')/key
        legacy=root/folder/'native'/key/'1' if folder else root/'runs'/key
        target=output/'datasets'/key;run=output/'runs'/key
        mapping=portable_copy(original,target,contract)
        if not (run/'run.json').exists():run_native_bundle(bundle=target,output=run,contract=contract,cpus='2',validation=True)
        receipt=json.loads((run/'run.json').read_text())
        if receipt['status']!='succeeded':raise ValueError('Retained native replay failed: '+key)
        spec=(verify_usd_bundle if folder else verify_bundle)(target)['spec']
        before=json.loads((legacy/'economic.json').read_text())
        after=json.loads((run/'economic.json').read_text())
        parity=compare_outputs(before,after,spec)
        if not parity['passed']:raise ValueError('Retained economic output changed: '+str(parity['differences'][:5]))
        results.append(dict(strategy=key,contract=contract,**mapping,parity=parity,
            run_receipt_sha256=sha256(run/'run.json'),legacy_economic_sha256=sha256(legacy/'economic.json')))
        write_json(output/'acceptance-progress.json',results)
        print(key+' matched retained economic output',flush=True)
    write_json(output/'acceptance.json',dict(status='passed',strategies=results,promotion_eligible=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--retained-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.retained_root.resolve(),a.output.resolve())
