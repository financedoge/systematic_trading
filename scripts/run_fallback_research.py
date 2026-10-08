"""Run the finite fallback study with all logical CPUs and immutable artifacts."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','calculate','native','analyze'])
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    if args.stage!='prepare':
        sys.path.insert(0,str(root/'source'))
    from systematic_trading.research.fallback_study import prepare,initialize,calculate_decision,freeze_decisions,calculate_economics,analyze
    from systematic_trading.research.momentum_replay import read_json,checked_files,native_parity
    from systematic_trading.lean.contracts import write_json
    if args.stage=='prepare':
        print(json.dumps(prepare(root)));return
    checked_files(root,'input_manifest.json');p=read_json(root/'protocol.json');workers=os.cpu_count() or 1
    if args.stage=='analyze':
        print(json.dumps(analyze(root)));return
    started=time.perf_counter();progress=dict(stage=args.stage,workers=workers,completed=[],status='running')
    write_json(root/(args.stage+'_progress.json'),progress)
    if args.stage=='calculate':
        from systematic_trading.research.momentum_signals import decision_sessions
        bars=read_json(root/'bars.json');days=[r['trade_date'] for r in bars['SPY']]
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(str(root),)) as pool:
            rows=dict(pool.map(calculate_decision,decision_sessions(days,p['start'],'monthly')))
            freeze_decisions(root,rows)
            print(json.dumps(dict(decisions=len(rows),baseline_parity=read_json(root/'baseline_parity.json'))),flush=True)
            jobs=[(r,c,0) for r in [*p['recipes'],'URTH'] for c in p['cost_bps']]+[(r,5,1) for r in p['recipes']]
            for future in as_completed([pool.submit(calculate_economics,j) for j in jobs]):
                name=future.result();progress['completed'].append(name)
                write_json(root/'calculate_progress.json',progress);print(name,flush=True)
    else:
        from systematic_trading.research.compute import available_resources
        resources=available_resources(4,'lean')
        workers=min(3,int((resources['docker_memory_gib']-2)//4),resources['usable_cpus'])
        if workers<1:
            raise ValueError('Insufficient Docker memory')
        budget=resources['usable_cpus'];lanes=[budget//workers+(i<budget%workers) for i in range(workers)]
        names=[f'{r}-cost5-delay0' for r in p['recipes']]
        progress.update(workers=workers,total_cpu_budget=budget,lane_cpus=lanes)
        image=read_json(root/'data_receipt.json')['image']
        def lane(index):
            done=[]
            for name in names[index::workers]:
                native_parity(root/'bundles'/name,root/'native'/name,image,cpus=str(lanes[index]));done.append(name)
            return done
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for completed in pool.map(lane,range(workers)):
                progress['completed'].extend(completed)
                write_json(root/'native_progress.json',progress);print(json.dumps(completed),flush=True)
    progress.update(status='succeeded',elapsed_seconds=time.perf_counter()-started)
    write_json(root/(args.stage+'_progress.json'),progress)
    print(json.dumps(progress))


if __name__=='__main__':
    main()
