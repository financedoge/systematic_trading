"""Finite frozen research; use every logical CPU, never broker authority."""
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
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if args.stage!='prepare':sys.path.insert(0,str(root/'source'))
    from systematic_trading.research.construction_study import prepare,initialize,decision,freeze_decisions,jobs,economics,ARMS,COMPARISONS,job_name,summarize
    from systematic_trading.research.momentum_replay import read_json,checked_files,native_parity
    from systematic_trading.lean.contracts import write_json
    if args.stage=='prepare':print(json.dumps(prepare(root)));return
    checked_files(root,'input_manifest.json');p=read_json(root/'protocol.json');workers=os.cpu_count() or 1
    if args.stage=='report':
        if args.output is None:raise ValueError('--output required')
        from systematic_trading.research.construction_analysis import build_artifacts
        print(build_artifacts(root,args.output));return
    started=time.perf_counter();progress=dict(stage=args.stage,workers=workers,status='running',completed=[])
    path=root/(args.stage+'_progress.json');write_json(path,progress)
    if args.stage=='calculate':
        from systematic_trading.research.momentum_signals import decision_sessions
        days=[r['trade_date'] for r in read_json(root/'parent/bars.json')['SPY']]
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(str(root),)) as pool:
            rows=dict(pool.map(decision,decision_sessions(days,p['calibration_start'],'monthly')))
            print(json.dumps(freeze_decisions(root,rows)),flush=True)
            for future in as_completed([pool.submit(economics,j) for j in jobs()]):
                progress['completed'].append(future.result());write_json(path,progress)
                if len(progress['completed'])%8==0:print('Replays complete:',len(progress['completed']),flush=True)
    elif args.stage=='native':
        from systematic_trading.research.compute import available_resources
        resource=available_resources(len(ARMS),'lean');lanes=resource['workers'];cpus=round(resource['usable_cpus']/lanes,6)
        image=read_json(root/'parent/data_receipt.json')['image']
        progress.update(resources=resource,lane_cpus=cpus)
        def run(arm):
            name=job_name((arm,5,0,'evaluation'))
            native_parity(root/'bundles'/name,root/'native'/name,image,cpus=str(cpus));return name
        with ThreadPoolExecutor(max_workers=lanes) as pool:
            for future in as_completed([pool.submit(run,a) for a in ARMS]):
                name=future.result();progress['completed'].append(name);write_json(path,progress);print(name,flush=True)
    else:
        from systematic_trading.research.construction_analysis import inference_job,finalize
        summarize(root)
        tasks=[(str(root),'means',b,0) for b in p['bootstrap_blocks']]+[(str(root),'ratios',b,i) for b in p['bootstrap_blocks'] for i in range(len(COMPARISONS))]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results=list(pool.map(inference_job,tasks))
        print(json.dumps(finalize(root,results)),flush=True)
        progress['completed']=[f'{a}/{b}' for a,b,_ in results]
    progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-started)
    write_json(path,progress);print(json.dumps(progress),flush=True)


if __name__=='__main__':main()
