"""Read-only serial/parallel target benchmark on a verified retained app input.

Does not publish, fit new models, contact providers, or touch broker state.
"""
import argparse
import json
from pathlib import Path
import sys
import time

REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/'src'))


def worker(request_path,output):
    from systematic_trading.research.file_pool import file_process_map
    from systematic_trading.research import usd_monitored as usd
    request=json.loads(request_path.read_text(encoding='utf8'))
    started=time.perf_counter()
    result=file_process_map(usd.targets_worker,request['days'],directory=output/'pool',
        workers=request['workers'],initializer=usd.worker_init,initargs=(request['root'],))
    (output/'results.json').write_text(json.dumps(result),encoding='utf8')
    (output/'timing.json').write_text(json.dumps(dict(workers=request['workers'],
        seconds=time.perf_counter()-started)),encoding='utf8')


def benchmark(root,output,months):
    from systematic_trading.lean.windows_worker import run
    from systematic_trading.lean.contracts import sha256
    from systematic_trading.research.momentum_replay import checked_files
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.file_pool import worker_count
    root=root.resolve();output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    checked_files(root,'input_manifest.json')
    data=json.loads((root/'worker.json').read_text(encoding='utf8'))
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf8'))
    days=decision_sessions([r['trade_date'] for r in data['bars']['SPY']],protocol['config']['calculation']['start'],'monthly')[-months:]
    workers=worker_count(len(days),input_bytes=(root/'worker.json').stat().st_size)
    results={};summary=dict(input_manifest_sha256=sha256(root/'input_manifest.json'),root=str(root),days=days,
        code_sha256={name:sha256(REPO_ROOT/'src/systematic_trading/research'/name)
            for name in ('file_pool.py','usd_monitored.py','momentum_replay.py')})
    for name,count in [('serial',1),('parallel',workers)]:
        inputs=output/(name+'-input');inputs.mkdir()
        request=inputs/'request.json'
        request.write_text(json.dumps(dict(root=str(root),days=days,workers=count)),encoding='utf8')
        target=output/name;target.mkdir()
        started=time.perf_counter()
        receipt=run([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(request),str(target)],
            output=target,read_roots=[root,inputs,REPO_ROOT/'src',Path(__file__).resolve(),Path(sys.prefix),Path(sys.base_prefix)],
            environment={'PYTHONPATH':str(REPO_ROOT/'src')},cpus=__import__('os').cpu_count() or 1,timeout=900)
        results[name]=json.loads((target/'results.json').read_text(encoding='utf8'))
        summary[name]=dict(**json.loads((target/'timing.json').read_text()),
            isolated_wall_seconds=time.perf_counter()-started,peak_job_commit_bytes=receipt['peak_job_commit_bytes'])
    if results['serial']!=results['parallel']:
        raise ValueError('Serial and parallel target outputs differ')
    summary.update(identical=True,speedup=summary['serial']['seconds']/summary['parallel']['seconds'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    if sys.argv[1:2]==['--worker']:
        worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('root',type=Path)
        parser.add_argument('output',type=Path)
        parser.add_argument('--months',type=int,default=24)
        args=parser.parse_args()
        if args.months<1:parser.error('months must be positive')
        benchmark(args.root,args.output,args.months)
