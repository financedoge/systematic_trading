"""Finite cash/stress research runner. No app scheduling or execution authority."""
import argparse
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor,as_completed
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','calculate','native','analyze','finalize','report'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if args.stage in ('calculate','native'):sys.path.insert(0,str(root/'source'))
    from systematic_trading.research import cash_stress_study as study
    from systematic_trading.research.cash_stress import RULES,COMPARISONS
    from systematic_trading.research.momentum_replay import checked_files,read_json,native_parity
    from systematic_trading.lean.contracts import write_json
    if args.stage=='prepare':print(study.prepare(root));return
    checked_files(root,'input_manifest.json');start=time.perf_counter()
    progress=dict(stage=args.stage,status='running',completed=[],workers=os.cpu_count())
    def completed(value):
        progress['completed'].append(value);write_json(root/(args.stage+'_progress.json'),progress);print(value,flush=True)
    if args.stage=='calculate':
        with ProcessPoolExecutor(max_workers=os.cpu_count(),initializer=study.initialize,initargs=(str(root),)) as pool:
            for f in as_completed([pool.submit(study.simulate,j) for j in study.jobs()]):completed(f.result())
            study.calibrate_risk_control(root)
            for f in as_completed([pool.submit(study.simulate,('XRM',p,c,d,'evaluation')) for p in ('ZERO','BIL') for c,d in ((5,0),(10,0),(20,0),(5,1))]):completed(f.result())
    elif args.stage=='native':
        from systematic_trading.research.compute import available_resources
        jobs=[(a,p,5,0,'full') for a in RULES for p in ('ZERO','BIL')]+[('XRM',p,5,0,'evaluation') for p in ('ZERO','BIL')]
        resources=available_resources(len(jobs),'lean');progress['resources']=resources
        def run(j):
            name=study.job_name(j);native_parity(root/'bundles'/name,root/'native'/name,read_json(root/'data_receipt.json')['image'],cpus=str(resources['cpus_per_run']));return name
        with ThreadPoolExecutor(max_workers=resources['workers']) as pool:
            for f in as_completed([pool.submit(run,j) for j in jobs]):completed(f.result())
    elif args.stage=='analyze':
        from systematic_trading.research.cash_stress_analysis import summarize,inference_job,finalize
        summarize(root);p=read_json(root/'protocol.json')
        jobs=[(str(root),kind,b,i) for b in p['bootstrap_blocks'] for kind,i in [('means',0)]+[('ratios',i) for i in range(len(COMPARISONS)*2)]]
        values=[]
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            for f in as_completed([pool.submit(inference_job,j) for j in jobs]):
                v=f.result();values.append(v);completed(v[:2])
        write_json(root/'inference.json',values)
        native_progress=root/'native_progress.json'
        if native_progress.exists() and read_json(native_progress).get('status')=='succeeded':print(finalize(root,values),flush=True)
        else:print('Inference saved; finalize after native verification completes.',flush=True)
    elif args.stage=='finalize':
        from systematic_trading.research.cash_stress_analysis import finalize
        print(finalize(root,read_json(root/'inference.json')),flush=True)
    else:
        from systematic_trading.research.cash_stress_analysis import artifacts
        if args.output is None:raise ValueError('--output required')
        print(artifacts(root,args.output),flush=True)
    progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-start)
    write_json(root/(args.stage+'_progress.json'),progress)
    print(args.stage,'succeeded',len(progress['completed']),'items',round(progress['elapsed_seconds'],1),'seconds',flush=True)


if __name__=='__main__':main()
