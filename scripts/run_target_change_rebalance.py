"""Replay the registered target-change study with explicit monthly macro fallback."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(os.environ['ST_TARGET_CHANGE_FROZEN_ROOT'])/'source')
    if os.environ.get('ST_TARGET_CHANGE_FROZEN_ROOT') else str(Path(__file__).resolve().parents[1]/'src'))
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='1'

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import (
    checked_files, freeze_usd_bundle, native_parity, read_json, run_usd_reference,
)
from systematic_trading.research.momentum_analysis import statistics
from systematic_trading.research.target_change_rebalance import (
    adoption_schedule, execution_schedule, select_threshold, target_weights, window_metrics,
)

ROOT=Path('var/research/target-change-rebalance-20261015-v1/run-02')
KEYS={'FR25':'research_fr25_14_v1','F3':'research_fallback_f3_v1'}
IMAGE='quantconnect/lean@sha256:27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59'


def freeze(root):
    if (root/'input_manifest.json').exists():
        checked_files(root,'input_manifest.json')
        return
    checked_files(root,'preflight_manifest.json')
    p=read_json(root/'registered_protocol.json')
    p.update(initial_cash_usd=1_000_000,limitations=p['inputs']['unresolved_limitations']+[
        'Explicit operator-authorized monthly macro fallback; original vintage timestamps retained.',
        'F3 retains legacy source-volume activity basis; cannot establish raw-activity transfer confirmation.',
        'Retrospectively chosen strategies; walk-forward is not an untouched holdout.'],
        execution_amendment=read_json(Path('research/target-change-rebalance-20261015-v1/execution-amendment.json')))
    write_json(root/'protocol.json',p)
    shutil.copytree(Path('src/systematic_trading'),root/'source/systematic_trading',
        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__),root/'runner.py')
    for arm,key in KEYS.items():
        worker=read_json(root/'parents'/arm/'worker.json')
        worker['definitions']=[d for d in worker['definitions'] if d['key']==key]
        destination=root/'workers'/arm
        write_json(destination/'worker.json',worker)
        write_json(destination/'input_manifest.json',{'worker.json':sha256(destination/'worker.json')})
    frozen=[root/'protocol.json',root/'runner.py',root/'registered_protocol.json',root/'preflight_manifest.json']
    frozen += [p for folder in ('source','workers') for p in (root/folder).rglob('*') if p.is_file()]
    write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in sorted(frozen)})
    print('Frozen study',sha256(root/'input_manifest.json'),flush=True)


def target_init(path):
    from systematic_trading.research import usd_monitored as m
    from systematic_trading.live.trading_calendar import next_us_trading_day
    m.worker_init(path)
    m._WORK['days'].append(str(next_us_trading_day(date.fromisoformat(m._WORK['days'][-1]))))


def target_job(day):
    from systematic_trading.research import usd_monitored as m
    result=m.targets_worker(day,allow_monthly_fallback=True)[1]
    row=next(iter(result.values()))
    data=m._WORK
    known=row['known_through']
    cutoff=max(d for d in data['days'] if d[:7]<day[:7])
    snapshots={r['known_through']:r for r in data['usd']['snapshots']}
    usd_source=known if known in snapshots else cutoff
    financial=data.get('economic',{}).get('models',{})
    financial_source=day if day in financial else next((d for d,r in financial.items()
        if d<=day and r['known_through']==cutoff),None)
    row['macro_sources']=dict(usd_used=known>='2024-03-28',usd_known_through=usd_source,
        usd_carried=known!=usd_source,usd_age_days=(date.fromisoformat(known)-date.fromisoformat(usd_source)).days,
        financial_decision=financial_source if 'research_fr25_14_v1' in result else None,
        financial_known_through=financial[financial_source]['known_through'] if financial_source and 'research_fr25_14_v1' in result else None,
        financial_carried=financial_source!=day if 'research_fr25_14_v1' in result else False)
    return day,row


def targets(root,workers):
    checked_files(root,'input_manifest.json')
    from systematic_trading.live.trading_calendar import next_us_trading_day
    for arm in KEYS:
        path=root/'targets'/(arm+'.json')
        if path.exists():
            checked_files(root,'target_manifest_'+arm+'.json')
            continue
        data=read_json(root/'workers'/arm/'worker.json')
        days=[r['trade_date'] for r in data['bars']['SPY'] if r['trade_date']>='2021-01-04']
        days.append(str(next_us_trading_day(date.fromisoformat(days[-1]))))
        started=time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers,initializer=target_init,
                initargs=(str(root/'workers'/arm),)) as pool:
            tape={}
            for i,(day,row) in enumerate(pool.map(target_job,days,chunksize=4),1):
                tape[day]=row
                if i%100==0:
                    print('Targets',arm,i,'/',len(days),'seconds',round(time.perf_counter()-started),flush=True)
        old=read_json(root/'parents'/arm/'decisions.json')
        monthly=[d for d in old if d in tape]
        for d in monthly:
            if target_weights(tape[d])!=target_weights(old[d]):
                raise ValueError('Monthly parent target mismatch: '+arm+'/'+d)
        write_json(path,tape)
        write_json(root/'monthly'/(arm+'.json'),monthly)
        write_json(root/('target_manifest_'+arm+'.json'),{
            path.relative_to(root).as_posix():sha256(path),
            'monthly/'+arm+'.json':sha256(root/'monthly'/(arm+'.json'))})
        print('Exact monthly target parity',arm,len(monthly),flush=True)


def turnover_series(result,quotes,initial):
    positions={s:0 for s in quotes};cash=float(initial);out={}
    fills={}
    for f in result['fills']:
        fills.setdefault(f['date'],[]).append(f)
    for r in result['nav']:
        day=r['date']
        opening=cash+sum(q*float(quotes[s][day]['open']) for s,q in positions.items())
        out[day]=sum(abs(f['quantity'])*float(f['price']) for f in fills.get(day,[]))/opening
        for f in fills.get(day,[]):
            positions[f['symbol']]+=f['quantity']
            cash-=f['quantity']*float(f['price'])+float(f['fee'])
        if abs(cash-float(r['cash']))>.02:
            raise ValueError('Turnover ledger cash mismatch')
    return out


def replay_job(payload):
    root,arm,policy,cost,delay,initial=payload
    root=Path(root)
    name=f'{arm}-{policy}-c{cost}-d{delay}-n{initial}'
    result_path=root/'python'/(name+'.json')
    receipt_path=root/'receipts'/(name+'.json')
    if receipt_path.exists():
        receipt=read_json(receipt_path)
        for relative,digest in receipt['files'].items():
            if sha256(root/relative)!=digest:
                raise ValueError('Changed replay '+relative)
        return name,read_json(root/'metrics'/(name+'.json'))
    tape=read_json(root/'targets'/(arm+'.json'))
    monthly=read_json(root/'monthly'/(arm+'.json'))
    switches=read_json(root/'selections.json')['switches'] if policy=='walk_forward' else None
    decisions,ledger=adoption_schedule(tape,monthly,'monthly' if switches is not None else policy,switches=switches)
    all_quotes=read_json(root/'parents'/arm/'quotes.json')
    sessions=[d for d in read_json(root/'parents'/arm/'sessions.json') if d>='2021-01-04']
    quotes={s:{d:q[d] for d in sessions} for s,q in all_quotes.items()}
    executed,pending=execution_schedule(decisions,sessions,delay)
    study=root
    if initial!=1_000_000:
        study=root/'size_diagnostic'
        if not (study/'protocol.json').exists():
            study.mkdir(exist_ok=True)
            p=read_json(root/'protocol.json');p['initial_cash_usd']=initial
            write_json(study/'protocol.json',p)
            shutil.copyfile(root/'input_manifest.json',study/'input_manifest.json')
            shutil.copytree(root/'source',study/'source')
    bundle=root/'bundles'/name
    recipe=dict(read_json(root/'parents'/arm/'spec.json')['recipe'],
        study_arm=arm,timing_policy=policy,extra_delay=delay)
    freeze_usd_bundle(bundle,study,recipe,executed,quotes,sessions,cost)
    # A reused bundle must describe these arguments, not merely pass its own hash.
    if (read_json(bundle/'decisions.json')!=executed or read_json(bundle/'quotes.json')!=quotes
            or read_json(bundle/'spec.json')['initial_cash_usd']!=initial):
        raise ValueError('Bundle identity collision')
    result=run_usd_reference(bundle)
    stats=statistics(result,quotes,initial)
    turnover=turnover_series(result,quotes,initial)
    metrics=window_metrics(result,sessions[0],sessions[-1],initial=initial,turnover_by_day=turnover)
    metrics.update(statistics=stats,decisions=len(executed),logical_adoptions=len(decisions),fills=len(result['fills']),
        pending=len(pending),turnover_by_day=turnover)
    events_path=root/'events'/(name+'.json')
    metrics_path=root/'metrics'/(name+'.json')
    write_json(result_path,result)
    write_json(events_path,dict(ledger=ledger,pending=pending))
    write_json(metrics_path,metrics)
    write_json(receipt_path,dict(files={p.relative_to(root).as_posix():sha256(p) for p in
        (result_path,events_path,metrics_path,bundle/'manifest.json')},protocol_sha256=sha256(root/'protocol.json')))
    return name,metrics


def replay(root,workers):
    p=read_json(root/'protocol.json');grid=p['thresholds']
    for arm in KEYS:
        checked_files(root,'target_manifest_'+arm+'.json')
    # Bounded pilot before scheduling the full surface.
    for policy in ('monthly','0.10'):
        name,m=replay_job((str(root),'FR25',policy,5,0,1_000_000))
        print('Pilot',name,'Sharpe',round(m['sharpe'],4),'seconds ledger reconciled',flush=True)
    jobs=[(str(root),arm,policy,cost,delay,1_000_000) for arm in KEYS
        for policy in ['monthly','daily',*grid] for cost in (5,10,20) for delay in (0,1)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,(name,m) in enumerate(pool.map(replay_job,jobs),1):
            print('Replay',i,'/',len(jobs),name,round(m['sharpe'],4),flush=True)
    selections=[];switches={}
    monthly=read_json(root/'monthly/FR25.json')
    windows=[(f['train_start'],f['train_end']) for f in p['walk_forward']['folds']]+[('2023-10-16','2026-10-14')]
    for i,(start,end) in enumerate(windows):
        metrics={}
        for policy in ['monthly',*grid]:
            metrics[policy]={}
            for cost,delay in [(5,0),(10,0),(5,1)]:
                name=f'FR25-{policy}-c{cost}-d{delay}-n1000000'
                eco=read_json(root/'python'/(name+'.json'))
                stored=read_json(root/'metrics'/(name+'.json'))
                metrics[policy][f'{cost}-{delay}']=window_metrics(eco,start,end,turnover_by_day=stored['turnover_by_day'])
        receipt=dict(select_threshold(grid,metrics),start=start,end=end)
        if i<3:
            fold=p['walk_forward']['folds'][i]
            activation=min(d for d in monthly if d>=fold['validate_start'])
            switches[activation]=receipt['selected'];receipt['activation']=activation
        selections.append(receipt)
        print('Selection',start,end,receipt['selected'],flush=True)
    write_json(root/'selections.json',dict(folds=selections[:3],candidate=selections[3],switches=switches))
    jobs=[(str(root),arm,'walk_forward',cost,delay,1_000_000) for arm in KEYS for cost in (5,10,20) for delay in (0,1)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name,m in pool.map(replay_job,jobs):
            print('Walk-forward',name,round(m['sharpe'],4),flush=True)
    # Size runs are sequential to avoid simultaneous creation of their source bundle.
    for arm in KEYS:
        for policy in ('monthly','walk_forward',selections[3]['selected']):
            name,m=replay_job((str(root),arm,policy,5,0,100_000))
            print('Size diagnostic',name,round(m['sharpe'],4),flush=True)
    checked_files(root,'input_manifest.json')


def native(root):
    receipts={}
    for arm in KEYS:
        for policy in ('monthly','walk_forward'):
            name=f'{arm}-{policy}-c5-d0-n1000000'
            receipts[name]=native_parity(root/'bundles'/name,root/'native'/name,IMAGE,cpus='2')
            print('Native',name,receipts[name]['status'],flush=True)
    write_json(root/'native_summary.json',receipts)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['freeze','targets','replay','native','all'])
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    args=parser.parse_args();root=args.root.resolve()
    if args.stage in ('freeze','all'):freeze(root)
    if args.stage != 'freeze' and not os.environ.get('ST_TARGET_CHANGE_FROZEN_ROOT'):
        checked_files(root,'input_manifest.json')
        environment=dict(os.environ,ST_TARGET_CHANGE_FROZEN_ROOT=str(root))
        raise SystemExit(subprocess.call([sys.executable,str(root/'runner.py'),args.stage,
            '--root',str(root),'--workers',str(args.workers)],env=environment))
    if args.stage in ('targets','all'):targets(root,args.workers)
    if args.stage in ('replay','all'):replay(root,args.workers)
    if args.stage in ('native','all'):native(root)
