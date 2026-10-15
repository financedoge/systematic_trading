"""Frozen joint (maximum selection count, target-change threshold) study."""
from concurrent.futures import ProcessPoolExecutor
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path('var/research/selection-width-timing-20261015-v1')
PARENT=Path('var/research/target-change-rebalance-20261015-v1/run-02')
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='1'
sys.path.insert(0,str(Path(os.environ['ST_TARGET_CHANGE_FROZEN_ROOT'])/'source')
    if os.environ.get('ST_TARGET_CHANGE_FROZEN_ROOT') else str(Path(__file__).resolve().parents[1]/'src'))

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import checked_files,read_json,native_parity
from systematic_trading.research.target_change_rebalance import target_weights,window_metrics
from systematic_trading.research.selection_timing import select_pair,mixed_tape

_HELPER=None
_MACRO=None


def helper(root):
    global _HELPER
    if _HELPER is None:
        spec=importlib.util.spec_from_file_location('frozen_timing_helper',root/'timing_runner.py')
        _HELPER=importlib.util.module_from_spec(spec);spec.loader.exec_module(_HELPER)
    return _HELPER


def variant(parent,width):
    return parent+'_X'+width


def key(parent,width,n,cost=5,delay=0,initial=1_000_000):
    return f'{variant(parent,width)}-{n}-c{cost}-d{delay}-n{initial}'


def freeze(root):
    if (root/'input_manifest.json').exists():
        checked_files(root,'input_manifest.json');return
    checked_files(PARENT,'input_manifest.json')
    for arm in ('FR25','F3'):checked_files(PARENT,'target_manifest_'+arm+'.json')
    p=read_json(Path('research/selection-width-timing-20261015-v1/protocol.json'))
    p.update(initial_cash_usd=1_000_000,limitations=read_json(PARENT/'protocol.json')['limitations'],
        parent_root=str(PARENT.resolve()),parent_input_manifest_sha256=sha256(PARENT/'input_manifest.json'),
        parent_acceptance_sha256=sha256(PARENT/'acceptance.json'))
    write_json(root/'protocol.json',p)
    shutil.copytree(Path('src/systematic_trading'),root/'source/systematic_trading',
        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__),root/'runner.py')
    shutil.copyfile(PARENT/'runner.py',root/'timing_runner.py')
    for arm in ('FR25','F3'):
        shutil.copytree(PARENT/'workers'/arm,root/'workers'/arm)
        shutil.copyfile(PARENT/'targets'/(arm+'.json'),root/'workers'/arm/'parent_targets.json')
        monthly=read_json(PARENT/'monthly'/(arm+'.json'))
        for width in [*p['widths'],'WF']:
            label=variant(arm,width);dest=root/'parents'/label;dest.mkdir(parents=True)
            for filename in ('quotes.json','sessions.json'):
                shutil.copyfile(PARENT/'parents'/arm/filename,dest/filename)
            spec=read_json(PARENT/'parents'/arm/'spec.json')
            spec['recipe'].update(selection_width=width,research_variant=label,
                selection_width_contract='override_only_top_n_preserve_eligibility_fallback_and_sizing_v1')
            write_json(dest/'spec.json',spec)
            write_json(root/'monthly'/(label+'.json'),monthly)
    write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p)
        for p in sorted(root.rglob('*')) if p.is_file()})
    print('Joint study frozen',sha256(root/'input_manifest.json'),flush=True)


def target_init(root,parent):
    global _MACRO
    root=Path(root);h=helper(root);h.target_init(str(root/'workers'/parent))
    _MACRO=read_json(root/'workers'/parent/'parent_targets.json')


def target_job(payload):
    from systematic_trading.research import usd_monitored as m
    day,width=payload
    count=len(m._WORK['bars']) if width=='all' else int(width)
    rows=m.targets_worker(day,allow_monthly_fallback=True,selection_top_n=count,selection_diagnostics=True)[1]
    row=next(iter(rows.values()));row['macro_sources']=_MACRO[day]['macro_sources']
    return width,day,row


def targets(root,workers):
    p=read_json(root/'protocol.json')
    for parent in ('FR25','F3'):
        manifest='target_manifest_'+parent+'.json'
        if (root/manifest).exists():checked_files(root,manifest);continue
        old=read_json(root/'workers'/parent/'parent_targets.json');days=list(old)
        jobs=[(day,width) for width in p['widths'] for day in days]
        tapes={width:{} for width in p['widths']}
        with ProcessPoolExecutor(max_workers=workers,initializer=target_init,initargs=(str(root),parent)) as pool:
            for i,(width,day,row) in enumerate(pool.map(target_job,jobs,chunksize=8),1):
                tapes[width][day]=row
                if i%500==0:print('Joint targets',parent,i,'/',len(jobs),flush=True)
        for day in days:
            if target_weights(tapes['6'][day])!=target_weights(old[day]):
                raise ValueError('Top-six parent mismatch: '+parent+'/'+day)
        if parent=='F3' and any(target_weights(tapes['12'][d])!=target_weights(tapes['all'][d]) for d in days):
            raise ValueError('F3 all and 12 must be identical')
        files={}
        for width,tape in tapes.items():
            path=root/'targets'/(variant(parent,width)+'.json');write_json(path,tape)
            files[path.relative_to(root).as_posix()]=sha256(path)
        write_json(root/manifest,files)
        print('Complete daily top-six parity',parent,len(days),flush=True)


def replay_init(root):
    helper(Path(root))


def replay_job(payload):
    name,m=_HELPER.replay_job(payload)
    summary={k:m[k] for k in ('sharpe','cagr','max_drawdown','annual_turnover','decisions','fills')}
    summary.update({k:m['statistics'][k] for k in ('annual_cost_bps','total_fees_usd','mean_held_count','mean_effective_holdings','maximum_weight')})
    return name,summary


def replay(root,workers):
    p=read_json(root/'protocol.json');h=helper(root)
    for parent in ('FR25','F3'):checked_files(root,'target_manifest_'+parent+'.json')
    for n in ('monthly','0.10'):
        label,m=h.replay_job((str(root),variant('FR25','8'),n,5,0,1_000_000))
        print('Joint pilot',label,round(m['sharpe'],4),flush=True)
    jobs=[(str(root),variant(parent,width),n,c,d,1_000_000) for parent in ('FR25','F3')
        for width in p['widths'] for n in p['thresholds'] for c in (5,10,20) for d in (0,1)]
    results={}
    with ProcessPoolExecutor(max_workers=workers,initializer=replay_init,initargs=(str(root),)) as pool:
        for i,(label,m) in enumerate(pool.map(replay_job,jobs),1):
            results[label]=m
            if i%12==0:print('Joint replay',i,'/',len(jobs),label,round(m['sharpe'],4),flush=True)
    write_json(root/'grid_summary.json',results)
    parent=Path(p['parent_root'])
    for arm in ('FR25','F3'):
        for n in ('monthly','0.05','0.10','0.20','0.40'):
            for c in (5,10,20):
                for d in (0,1):
                    old=read_json(parent/'python'/f'{arm}-{n}-c{c}-d{d}-n1000000.json')
                    new=read_json(root/'python'/(key(arm,'6',n,c,d)+'.json'))
                    if any(old[k]!=new[k] for k in ('fills','nav','final_positions')):
                        raise ValueError('Top-six economics changed '+arm+'/'+n)
    windows=[(f['train_start'],f['train_end']) for f in p['folds']]+[tuple(p['final_candidate_window'])]
    scores=[{} for _ in windows]
    for width in p['widths']:
        for n in p['thresholds']:
            pair=width+'/'+n
            for score in scores:score[pair]={}
            for c,d in ((5,0),(10,0),(5,1)):
                label=key('FR25',width,n,c,d)
                eco=read_json(root/'python'/(label+'.json'));m=read_json(root/'metrics'/(label+'.json'))
                for score,(start,end) in zip(scores,windows,strict=True):
                    score[pair][f'{c}-{d}']=window_metrics(eco,start,end,turnover_by_day=m['turnover_by_day'])
    selection=[];pair_switches={};n_switches={}
    monthly=read_json(root/'monthly/FR25_X6.json')
    for i,(score,(start,end)) in enumerate(zip(scores,windows,strict=True)):
        r=dict(select_pair(p['widths'],p['thresholds'],score),start=start,end=end)
        if i<3:
            r['activation']=min(d for d in monthly if d>=p['folds'][i]['validate_start'])
            pair_switches[r['activation']]=r['selected'];n_switches[r['activation']]=r['selected'].split('/')[1]
        selection.append(r);print('Joint selection',start,end,r['selected'],flush=True)
    write_json(root/'selections.json',dict(folds=selection[:3],candidate=selection[3],pair_switches=pair_switches,switches=n_switches))
    for arm in ('FR25','F3'):
        tapes={width:read_json(root/'targets'/(variant(arm,width)+'.json')) for width in p['widths']}
        write_json(root/'targets'/(variant(arm,'WF')+'.json'),mixed_tape(tapes,pair_switches))
    jobs=[(str(root),variant(arm,'WF'),'walk_forward',c,d,1_000_000) for arm in ('FR25','F3') for c in (5,10,20) for d in (0,1)]
    with ProcessPoolExecutor(max_workers=workers,initializer=replay_init,initargs=(str(root),)) as pool:
        for label,m in pool.map(replay_job,jobs):results[label]=m;print('Joint WF',label,round(m['sharpe'],4),flush=True)
    write_json(root/'grid_summary.json',results)
    width,n=selection[3]['selected'].split('/')
    for arm in ('FR25','F3'):
        for x,threshold in dict.fromkeys([('6','monthly'),('WF','walk_forward'),(width,n)]):
            label,m=h.replay_job((str(root),variant(arm,x),threshold,5,0,100_000))
            print('Joint size diagnostic',label,round(m['sharpe'],4),flush=True)
    write_json(root/'replay_validation.json',dict(top_six_targets_each_parent=1453,
        exact_parent_economics=60,full_size_replays=len(results),input_manifest_sha256=sha256(root/'input_manifest.json')))


def native(root):
    r=read_json(root/'selections.json');width,n=r['candidate']['selected'].split('/')
    image='quantconnect/lean@sha256:27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59'
    receipts={}
    for arm in ('FR25','F3'):
        for x,threshold in dict.fromkeys([('6','monthly'),('WF','walk_forward'),('8','0.10'),(width,n)]):
            label=key(arm,x,threshold)
            receipts[label]=native_parity(root/'bundles'/label,root/'native'/label,image,cpus='2')
            print('Joint native',label,receipts[label]['status'],flush=True)
    checked_files(root,'input_manifest.json')
    write_json(root/'native_summary.json',receipts)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['freeze','targets','replay','native','all'])
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    args=parser.parse_args();root=args.root.resolve()
    if args.stage in ('freeze','all'):freeze(root)
    if args.stage!='freeze' and not os.environ.get('ST_TARGET_CHANGE_FROZEN_ROOT'):
        checked_files(root,'input_manifest.json')
        raise SystemExit(subprocess.call([sys.executable,str(root/'runner.py'),args.stage,'--root',str(root),
            '--workers',str(args.workers)],env=dict(os.environ,ST_TARGET_CHANGE_FROZEN_ROOT=str(root))))
    if args.stage in ('targets','all'):targets(root,args.workers)
    if args.stage in ('replay','all'):replay(root,args.workers)
    if args.stage in ('native','all'):native(root)
