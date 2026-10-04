"""Reproducible staged CPU-parallel research; no recurring or broker actions."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import time

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, native_parity
from systematic_trading.research.momentum_calculation import initialize_worker, make_feature_chunk, calculate_job


def run(root,workers,stage):
    checked_files(root,'input_manifest.json')
    p=read_json(root/'protocol.json')
    if not (root/'source').exists():
        source=Path(__file__).resolve().parents[1]/'src'
        shutil.copytree(source,root/'source',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
        write_json(root/'source_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in (root/'source').rglob('*.py')})
    checked_files(root,'source_manifest.json')
    # Refuse a mixed-code rerun. Frozen scripts and Python version accompany outputs.
    for rel,h in read_json(root/'source_manifest.json').items():
        local=Path(__file__).resolve().parents[1]/'src'/Path(rel).relative_to('source')
        if sha256(local)!=h:
            raise ValueError('Code changed since freeze: '+str(local))
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    progress=dict(stage=stage,logical_cpus=os.cpu_count(),workers=workers,completed=[],started=time.time())
    write_json(root/('progress-'+stage+'.json'),progress)
    if stage=='features':
        if (root/'features.json').exists():
            checked_files(root,'feature_manifest.json');return
        bars=read_json(root/'bars.json');days=[r['trade_date'] for r in bars['SPY']]
        indices=[i for i,d in enumerate(days) if d>=p['start']]
        chunks=[indices[i:i+64] for i in range(0,len(indices),64)]
        features={}
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,initargs=(root,)) as pool:
            for result in pool.map(make_feature_chunk,chunks):
                features.update(result)
        write_json(root/'features.json',dict(sorted(features.items())))
        write_json(root/'feature_manifest.json',{'features.json':sha256(root/'features.json')})
        progress['completed']=[len(features)]
    elif stage in ('python','transfer'):
        jobs=[j for j in p['recipes'] if not j.get('prerequisite')]
        jobs += [dict(id='risk-M',recipe='risk',cadence='monthly'),dict(id='urth',recipe='urth',cadence='monthly')]
        if stage=='transfer':
            jobs=[j for j in read_json(root/'transfer_registration.json')['jobs'] if not j['recipe'].startswith('U')]
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,initargs=(root,)) as pool:
            futures={pool.submit(calculate_job,j):j['id'] for j in jobs}
            for f in as_completed(futures):
                result=f.result();progress['completed'].append(result)
                write_json(root/('progress-'+stage+'.json'),progress)
                print(result,flush=True)
    elif stage=='native':
        image=read_json(root/'data_receipt.json')['image']
        names=[f.stem for f in (root/'python').glob('*-cost5.json')]
        def native(name):
            output=root/'native'/name
            attempt=0
            while output.exists() and read_json(output/'run.json')['status']!='succeeded':
                prior=read_json(output/'run.json')
                if 'parity failed' in prior.get('error',''):
                    raise ValueError('Economic parity failure requires investigation; no automatic retry')
                attempt+=1
                if attempt>3:raise ValueError('Native retries exhausted')
                output=root/'native'/(name+'-retry'+str(attempt))
            result=native_parity(root/'bundles'/name,output,image)
            return dict(id=name,status=result['status'],elapsed_seconds=result['elapsed_seconds'],output=str(output.resolve()))
        # 3 x 4GiB containers + 2GiB reserve fit the 15.4GiB Docker VM.
        with ThreadPoolExecutor(max_workers=min(workers,3)) as pool:
            for result in pool.map(native,names):
                progress['completed'].append(result);write_json(root/('progress-'+stage+'.json'),progress)
                print(result,flush=True)
    progress.update(status='succeeded',elapsed_seconds=time.time()-progress['started'])
    write_json(root/('progress-'+stage+'.json'),progress)
    print(progress['elapsed_seconds'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=os.cpu_count())
    parser.add_argument('--stage',choices=['features','python','transfer','native'],required=True)
    args=parser.parse_args()
    run(args.root,args.workers,args.stage)
