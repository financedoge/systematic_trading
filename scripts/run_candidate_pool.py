"""Execute the predeclared candidate-pool study without strategy promotion."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','train','calculate','native','analyze','report'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if args.stage not in ('prepare','analyze','report'):sys.path.insert(0,str(root/'source'))
    from systematic_trading.research import candidate_pool_study as study
    from systematic_trading.research.momentum_replay import checked_files,read_json,native_parity
    from systematic_trading.lean.contracts import write_json
    if args.stage=='prepare':
        print(json.dumps(study.prepare(root)));return
    checked_files(root,'input_manifest.json');started=time.perf_counter()
    progress=dict(stage=args.stage,workers=os.cpu_count(),status='running',completed=[])
    def completed(name):
        progress['completed'].append(name);write_json(root/(args.stage+'_progress.json'),progress);print(name,flush=True)
    if args.stage=='train':
        tasks=[]
        for n in (12,14):tasks.extend((str(root),*v) for v in study.training_inputs(root,n));completed('training inputs '+str(n))
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            for f in as_completed([pool.submit(study.fit,j) for j in tasks]):completed(f.result())
        study.freeze_models(root)
    elif args.stage=='calculate':
        with ProcessPoolExecutor(max_workers=os.cpu_count(),initializer=study.initialize,initargs=(str(root),)) as pool:
            records={}
            for f in as_completed([pool.submit(study.decision,d) for d in sorted(read_json(root/'control.json'))]):
                day,value=f.result();records[day]=value;completed(day)
            study.freeze_decisions(root,records)
            for f in as_completed([pool.submit(study.economics,j) for j in study.jobs()]):completed(f.result())
    elif args.stage=='native':
        from systematic_trading.research.compute import available_resources
        resource=available_resources(len(study.ARMS),'lean');progress['resources']=resource
        def run(arm):
            name=study.job_name((arm,5,0,'full'));native_parity(root/'bundles'/name,root/'native'/name,
                read_json(root/'data_receipt.json')['image'],cpus=str(resource['cpus_per_run']));return name
        with ThreadPoolExecutor(max_workers=resource['workers']) as pool:
            for f in as_completed([pool.submit(run,a) for a in study.ARMS]):completed(f.result())
    elif args.stage=='analyze':
        from systematic_trading.research.candidate_pool_analysis import summarize,inference_job,finalize
        summarize(root);p=read_json(root/'protocol.json')
        jobs=[(str(root),kind,b,i) for b in p['bootstrap_blocks'] for kind,i in [('means',0)]+[('ratios',i) for i in range(len(study.COMPARISONS))]]
        values=[]
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            for f in as_completed([pool.submit(inference_job,j) for j in jobs]):
                v=f.result();values.append(v);completed(v[:2])
        write_json(root/'inference.json',values)
        print(json.dumps(finalize(root,values)),flush=True)
    else:
        from systematic_trading.research.candidate_pool_analysis import artifacts
        if args.output is None:raise ValueError('--output required')
        print(artifacts(root,args.output),flush=True)
    progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-started)
    write_json(root/(args.stage+'_progress.json'),progress);print(json.dumps(progress),flush=True)


if __name__=='__main__':main()
