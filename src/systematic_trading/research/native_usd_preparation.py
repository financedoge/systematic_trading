"""One isolated offline worker prepares USD decisions and accounting outputs."""
from pathlib import Path
import os
import sys
import time
from uuid import uuid4

from systematic_trading.lean.contracts import write_json
from systematic_trading.research.momentum_replay import read_json,verify_usd_bundle


def prepare(root,*,start,cost,urth=None,max_workers=None,receipt=None):
    from systematic_trading.lean.windows_worker import run
    root=root.resolve()
    output=root.with_name(root.name+'.preparation-'+uuid4().hex);output.mkdir()
    inputs=root.with_name(output.name+'.input');inputs.mkdir()
    request=inputs/'request.json'
    write_json(request,dict(root=str(root),start=start,cost=str(cost),urth=urth,max_workers=max_workers))
    source=Path(__file__).resolve().parents[2]
    run([sys.executable,'-B','-m','systematic_trading.research.native_usd_preparation',str(request),str(output)],
        output=output,read_roots=[root,inputs,source,Path(sys.prefix),Path(sys.base_prefix)],
        environment={'PYTHONPATH':str(root/'source')},
        cpus=getattr(os,'process_cpu_count',os.cpu_count)() or 1,timeout=900)
    results={}
    for bundle in (output/'bundles').iterdir():
        verify_usd_bundle(bundle)
        target=root/'bundles'/bundle.name;target.parent.mkdir(exist_ok=True)
        result=read_json(output/'python'/(bundle.name+'.json'))
        previous=root/'python'/(bundle.name+'.json');previous.parent.mkdir(exist_ok=True)
        if target.exists():
            verify_usd_bundle(target)
            if read_json(target/'manifest.json')!=read_json(bundle/'manifest.json'):
                raise ValueError('Prepared USD bundle differs from retained inputs')
        else:bundle.rename(target)
        if previous.exists():
            old=read_json(previous)
            if {k:v for k,v in old.items() if k!='elapsed_seconds'}!={k:v for k,v in result.items() if k!='elapsed_seconds'}:
                raise ValueError('Prepared USD accounting changed')
        else:(output/'python'/(bundle.name+'.json')).rename(previous)
        results[target.name]=result
    if receipt is not None:
        receipt.update(read_json(output/'preparation.json'))
    return results


def replay_bundle(path):
    from systematic_trading.research.momentum_replay import run_usd_reference
    bundle=Path(path)
    result=run_usd_reference(bundle)
    write_json(bundle.parent.parent/'python'/(bundle.name+'.json'),result)
    return bundle.name


def worker(request_path,output):
    from systematic_trading.research.file_pool import file_process_map, worker_count
    from systematic_trading.research import usd_monitored as usd
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.research.momentum_replay import freeze_usd_bundle
    from systematic_trading.domain.portfolio import AllocationTarget
    from decimal import Decimal
    started=time.perf_counter()
    request=read_json(request_path);root=Path(request['root'])
    usd.worker_init(str(root));data=usd._WORK
    days=data['days'];start=request['start']
    quotes,sessions=quotes_for_data(data['bars'],days,start)
    decisions_days=decision_sessions(days,start,'monthly')
    input_bytes=(root/'worker.json').stat().st_size
    workers=worker_count(len(decisions_days),input_bytes=input_bytes,max_workers=request.get('max_workers'))
    rows=dict(file_process_map(usd.targets_worker,decisions_days,directory=output/'targets-pool',
        workers=workers,initializer=usd.worker_init if workers>1 else None,initargs=(str(root),)))
    target_seconds=time.perf_counter()-started
    for definition in data['definitions']:
        # Frozen definitions use the public JSON contract's id field.
        key=usd.StrategyDefinition.from_dict(definition).key
        decisions={day:rows[day][key] for day in sorted(rows)}
        freeze_usd_bundle(output/'bundles'/key,root,definition,decisions,quotes,sessions,request['cost'])
    if request.get('urth'):
        benchmark,_=quotes_for_data({'URTH':request['urth']},days,start)
        decision={sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=Decimal(1),rationale='Buy and hold benchmark').model_dump(mode='json')])}
        freeze_usd_bundle(output/'bundles'/'URTH',root,dict(id='URTH'),decision,benchmark,sessions,request['cost'])
    (output/'python').mkdir()
    bundles=sorted((output/'bundles').iterdir())
    replay_workers=worker_count(len(bundles),input_bytes=input_bytes,max_workers=request.get('max_workers'))
    before=time.perf_counter()
    file_process_map(replay_bundle,[str(bundle) for bundle in bundles],directory=output/'replay-pool',workers=replay_workers)
    write_json(output/'preparation.json',dict(workers=workers,replay_workers=replay_workers,
        decisions=len(decisions_days),bundles=len(bundles),input_bytes=input_bytes,
        targets_wall_seconds=target_seconds,replay_wall_seconds=time.perf_counter()-before,
        elapsed_seconds=time.perf_counter()-started,transport='files',aggregate_memory_limit_bytes=None,
        memory_policy='windows_managed'))


if __name__=='__main__':worker(Path(sys.argv[1]),Path(sys.argv[2]))
