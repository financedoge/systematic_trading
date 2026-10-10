"""Run one fixed economic-response study; no recurring calculation or trading authority."""
import argparse
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor,as_completed
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','calculate','native','analyze','finalize','report'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if args.stage in ('calculate','native'):sys.path.insert(0,str(root/'source'))
    from systematic_trading.research import expanded_economics as study
    from systematic_trading.research.momentum_replay import checked_files,read_json,native_parity
    from systematic_trading.lean.contracts import write_json,sha256
    if args.stage=='prepare':print(study.prepare(root,Path(__file__)));return
    checked_files(root,'input_manifest.json')
    if args.stage in ('calculate','native') and sha256(Path(__file__))!=sha256(root/'runner.py'):raise ValueError('Use frozen runner')
    start=time.perf_counter();progress=dict(stage=args.stage,status='running',workers=os.cpu_count(),completed=[])
    def save(value=None):
        if value is not None:progress['completed'].append(value);print(value,flush=True)
        write_json(root/(args.stage+'_progress.json'),progress)
    save()
    try:
        if args.stage=='calculate':
            days=sorted(read_json(root/'controls/M1.json'))
            with ProcessPoolExecutor(max_workers=os.cpu_count(),initializer=study.initialize,initargs=(str(root),)) as pool:
                study.freeze_features(root,dict(pool.map(study.feature_decision,days)))
            print('Published features reproduced for all monthly decisions',flush=True)
            with ProcessPoolExecutor(max_workers=os.cpu_count(),initializer=study.initialize,initargs=(str(root),)) as pool:
                rows={}
                for f in as_completed([pool.submit(study.model_decision,d) for d in days]):
                    day,value=f.result();rows[day]=value
                    if len(rows)%20==0:print('Model decisions',len(rows),flush=True)
                study.freeze_decisions(root,rows)
                for f in as_completed([pool.submit(study.economics,j) for j in study.jobs()]):save(f.result())
        elif args.stage=='native':
            from systematic_trading.research.compute import available_resources
            resources=available_resources(len(study.ARMS),'lean');progress['resources']=resources;save()
            def run(a):
                name=study.job_name((a,5,0,'full'));native_parity(root/'bundles'/name,root/'native'/name,read_json(root/'data_receipt.json')['image'],cpus=str(resources['cpus_per_run']));return name
            with ThreadPoolExecutor(max_workers=resources['workers']) as pool:
                for f in as_completed([pool.submit(run,a) for a in study.ARMS]):save(f.result())
        elif args.stage=='analyze':
            from systematic_trading.research.expanded_economic_analysis import summarize,inference_job
            summarize(root);p=read_json(root/'protocol.json');values=[]
            tasks=[(str(root),kind,b,i) for b in p['bootstrap_blocks'] for kind,i in [('means',0)]+[('ratios',i) for i in range(len(study.COMPARISONS))]]
            with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
                for f in as_completed([pool.submit(inference_job,t) for t in tasks]):
                    v=f.result();values.append(v);save(v[:2])
            write_json(root/'inference.json',values)
        elif args.stage=='finalize':
            from systematic_trading.research.expanded_economic_analysis import finalize
            print(finalize(root),flush=True)
        else:
            from systematic_trading.research.expanded_economic_analysis import artifacts
            if args.output is None:raise ValueError('--output required')
            print(artifacts(root,args.output),flush=True)
        progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-start)
    except BaseException as exc:
        progress.update(status='failed',error=repr(exc),elapsed_seconds=time.perf_counter()-start);raise
    finally:save()


if __name__=='__main__':main()
