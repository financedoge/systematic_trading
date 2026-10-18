"""One bounded offline worker prepares USD decisions and accounting outputs."""
from pathlib import Path
import sys
from uuid import uuid4

from systematic_trading.lean.contracts import write_json
from systematic_trading.research.momentum_replay import read_json,verify_usd_bundle


def prepare(root,*,start,cost,urth=None):
    from systematic_trading.lean.windows_worker import run
    root=root.resolve()
    output=root.with_name(root.name+'.preparation-'+uuid4().hex);output.mkdir()
    inputs=root.with_name(output.name+'.input');inputs.mkdir()
    request=inputs/'request.json'
    write_json(request,dict(root=str(root),start=start,cost=str(cost),urth=urth))
    source=Path(__file__).resolve().parents[2]
    run([sys.executable,'-B',str(Path(__file__).resolve()),str(request),str(output)],
        output=output,read_roots=[root,inputs,source,Path(sys.prefix),Path(sys.base_prefix)],
        environment={'PYTHONPATH':str(root/'source')},memory_bytes=4*1024**3,cpus=2,timeout=900)
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
    return results


def worker(request_path,output):
    from systematic_trading.research import usd_monitored as usd
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.research.momentum_replay import freeze_usd_bundle,run_usd_reference
    from systematic_trading.domain.portfolio import AllocationTarget
    from decimal import Decimal
    request=read_json(request_path);root=Path(request['root'])
    usd.worker_init(str(root));data=usd._WORK
    days=data['days'];start=request['start']
    quotes,sessions=quotes_for_data(data['bars'],days,start)
    rows=dict(usd.targets_worker(day) for day in decision_sessions(days,start,'monthly'))
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
    for bundle in (output/'bundles').iterdir():
        write_json(output/'python'/(bundle.name+'.json'),run_usd_reference(bundle))


if __name__=='__main__':worker(Path(sys.argv[1]),Path(sys.argv[2]))
