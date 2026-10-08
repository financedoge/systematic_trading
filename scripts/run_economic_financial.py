"""Freeze and replay one bounded economic experiment with every logical CPU."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','calculate','native','analyze','report'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--parent',type=Path,default=Path('var/research/economic-response-20261007-v2'))
    parser.add_argument('--economic-pin',type=Path,default=Path('var/research/economic-financial-input-pin-20261007.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if args.stage!='prepare':sys.path.insert(0,str(root/'source'))
    from systematic_trading.research.economic_financial_study import (
        prepare,initialize,feature_decision,freeze_features,model_decision,freeze_decisions,jobs,economics,ARMS,COMPARISONS,job_name,summarize)
    from systematic_trading.research.momentum_replay import read_json,checked_files,native_parity
    from systematic_trading.lean.contracts import sha256,write_json
    if args.stage=='prepare':
        print(json.dumps(prepare(root,args.parent.resolve(),args.economic_pin.resolve(),Path(__file__).resolve())),flush=True)
        return
    checked_files(root,'input_manifest.json')
    if sha256(Path(__file__))!=sha256(root/'runner.py'):
        raise ValueError('Runner changed since freeze; use the frozen runner')
    p=read_json(root/'protocol.json');workers=os.cpu_count() or 1
    started=time.perf_counter();progress=dict(stage=args.stage,workers=workers,status='running',completed=[])
    path=root/(args.stage+'_progress.json');write_json(path,progress)
    try:
        if args.stage=='calculate':
            days=sorted(read_json(root/'controls/F0.json'))
            with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(str(root),)) as pool:
                features=dict(pool.map(feature_decision,days))
            freeze_features(root,features)
            print(json.dumps(dict(features=len(features),financial_ready=sum(r['financial_ready'] for r in features.values()),
                augmented_ready=sum(r['financial_ready'] and r['leading_ready'] and r['context_ready'] for r in features.values()))),flush=True)
            with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(str(root),)) as pool:
                models={}
                for future in as_completed([pool.submit(model_decision,d) for d in days]):
                    day,result=future.result();models[day]=result
                    if len(models)%20==0:print('Economic model decisions:',len(models),flush=True)
                freeze_decisions(root,models)
                progress['phase']='replaying';write_json(path,progress)
                for future in as_completed([pool.submit(economics,job) for job in jobs()]):
                    progress['completed'].append(future.result());write_json(path,progress)
                    if len(progress['completed'])%8==0:print('Portfolio replays:',len(progress['completed']),flush=True)
        elif args.stage=='native':
            from systematic_trading.research.compute import available_resources
            resource=available_resources(len(ARMS),'lean');lanes=resource['workers'];cpus=round(resource['usable_cpus']/lanes,6)
            image=read_json(root/'data_receipt.json')['image'];progress.update(resources=resource,lane_cpus=cpus)
            def run(arm):
                name=job_name((arm,5,0,'evaluation'))
                native_parity(root/'bundles'/name,root/'native'/name,image,cpus=str(cpus));return name
            with ThreadPoolExecutor(max_workers=lanes) as pool:
                for future in as_completed([pool.submit(run,arm) for arm in ARMS]):
                    name=future.result();progress['completed'].append(name);write_json(path,progress);print(name,flush=True)
        elif args.stage=='analyze':
            from systematic_trading.research.economic_financial_analysis import inference_job,finalize
            summarize(root)
            tasks=[(str(root),'means',b,0) for b in p['bootstrap_blocks']]+[(str(root),'ratios',b,i) for b in p['bootstrap_blocks'] for i in range(len(COMPARISONS))]
            with ProcessPoolExecutor(max_workers=workers) as pool:results=list(pool.map(inference_job,tasks))
            print(json.dumps(finalize(root,results)),flush=True)
            progress['completed']=[f'{a}/{b}' for a,b,_ in results]
        else:
            if args.output is None:raise ValueError('--output required')
            from systematic_trading.research.economic_financial_analysis import build_artifacts
            print(build_artifacts(root,args.output),flush=True)
        progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-started)
    except BaseException as exc:
        progress.update(status='failed',error=repr(exc),elapsed_seconds=time.perf_counter()-started)
        raise
    finally:write_json(path,progress)
    print(json.dumps(progress),flush=True)


if __name__=='__main__':main()
