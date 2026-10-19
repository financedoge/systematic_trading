"""GLD-only daily entry/holding experiment: fit, select, seal, then evaluate."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import numpy as np
from run_joint_breakout import (ROOT as PARENT,asset,check,read,write,digest,verify,manifest,
    SingleReplay,exact_candidate,benchmarks_for,transitions)
from systematic_trading.research.range_joint import History
from systematic_trading.research.gld_confirmation import candidates,candidate_id,fit_variants,scores,select_validation

ROOT=Path('var/research/gld-confirmation-patience-20261018-v1')
PUBLIC=Path('research/gld-confirmation-patience-20261018-v1')
FRICTIONS=((5,0),(10,0),(5,1))
BASELINE=candidate_id(8,5)
SOURCES=('scripts/run_gld_confirmation.py','src/systematic_trading/research/gld_confirmation.py')


def audit():
    check(PARENT);verify(ROOT,'input_manifest.json')
    for s in SOURCES:
        if digest(Path(s))!=read(ROOT/'source_hashes.json')[s]:raise ValueError('Sealed fit source changed')


def prepare():
    check(PARENT)
    if (ROOT/'input_manifest.json').exists():audit();return
    ROOT.mkdir(parents=True,exist_ok=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    base=read(PARENT/'selection.json')['choices']['GLD']['parameters']
    protocol=dict(scope='GLD only; daily close decisions, following-open fills; numerical changes only to confirmation count and time deadline.',
        periods=dict(fit_end='2022-12-31',selection_start='2023-01-01',selection_end='2023-12-31',evaluation_start='2024-01-01'),
        confirmations=[1,2,3,4,5,6,8],time_deadlines=[5,10,20,42,63,126,0],grid_size=49,
        fixed='All other 31 parameters including range, buffers, initial/range/trailing stops, time gain hurdle and cooldown. Zero deadline disables only the time exit.',
        objective='45/40/15 scaled net return/Sharpe/Calmar versus matched buy-hold, original soft hold/stop penalties; no cost ceiling.',
        fit='Exact whole-share replay for all49 points under5bp,10bp,5bp+one-extra-session delay. Require4 completed IS trades and5% exposure. Prefer original return/DD guard passes; if none, label fallback.',
        IS_variants=['raw','moderate','strong','stable','neighbor'],
        neighbor='Median minus0.5std of worst-friction moderate scores at self and four immediate grid neighbors. Deadline order5,10,20,42,63,126,off. Unsupported neighbor receives-10.',
        validation='Only baseline and deduplicated pre2023 winners. Rank worst-friction moderate utility; prefer guard passes. Within.03 of best choose lower5bp turnover, disabled time rule, shorter confirmation, longer deadline, key. Label fallback if no guards pass.',
        evaluation='Seal selected vector first. Evaluate selected, original baseline, entry-only selected confirmation, holding-only selected deadline, and predeclared1-close/no-time control; no OOS ranking or refitting.',
        frictions=FRICTIONS,initial_cash_usd=1e6,target=.98,cash_yield=0,
        limitations=['2024+ motivating episode was already inspected; this is a chronological development retest, not fresh unseen OOS.',
            '2023 has been reused for model selection. Remaining parameters inherit earlier IS fit/2023 selection; this is a conditional repair, not an independent discovery.',
            'Pinned audited adjusted OHLC/raw volume; revised vintage and retrospective identity limitations persist.',
            'Close-based stops can gap beyond levels; no intraday stop execution. No monitoring,promotion,funding or broker action.'])
    write(ROOT/'protocol.json',protocol);write(ROOT/'grid.json',candidates(base))
    write(ROOT/'parents.json',dict(v3_manifest_sha256=digest(PARENT/'input_manifest.json'),selection_sha256=digest(PARENT/'selection.json'),
        GLD_sha256=digest(Path('var/research/range-breakout-20261018-v2/assets/GLD.npz'))))
    write(ROOT/'source_hashes.json',{s:digest(Path(s)) for s in SOURCES})
    for s in SOURCES:shutil.copyfile(s,ROOT/Path(s).name)
    manifest(ROOT,'input_manifest.json',[p for p in ROOT.iterdir() if p.is_file()])
    print('Prepared49 combinations before evaluation',flush=True)


def fit():
    audit();a=asset('GLD','2022-12-31');h=History.build(a);start=str(a['days'][252]);runner=SingleReplay(a,'GLD',start)
    bench=benchmarks_for(a,'GLD',start,FRICTIONS,runner);rows={}
    for j,(ident,g) in enumerate(read(ROOT/'grid.json').items()):
        tape=h.signals(g['parameters']);exact,_=exact_candidate(a,'GLD',tape,start,'event',FRICTIONS,bench,runner)
        st=exact['scenarios']['5:0']['stats'][0]
        rows[ident]=dict(**g,exact=exact,scores=scores(exact),evidence=bool(st[6]>=4 and st[4]>=.05))
        if (j+1)%7==0:print('IS exact grid',j+1,'/49',flush=True)
    variants=fit_variants(rows)
    write(ROOT/'fit.json',dict(first=start,known_through=str(a['days'][-1]),rows=rows,buyhold=bench,**variants))
    manifest(ROOT,'fit_manifest.json',[ROOT/'fit.json'])
    print('IS variants',variants,flush=True)


def select():
    audit();verify(ROOT,'fit_manifest.json');f=read(ROOT/'fit.json');grid=read(ROOT/'grid.json')
    a=asset('GLD','2023-12-31');h=History.build(a);runner=SingleReplay(a,'GLD','2023-01-01')
    bench=benchmarks_for(a,'GLD','2023-01-01',FRICTIONS,runner);rows={}
    for ident in sorted(set(f['variants'].values())|{BASELINE}):
        tape=h.signals(grid[ident]['parameters'])
        exact,_=exact_candidate(a,'GLD',tape,'2023-01-01','event',FRICTIONS,bench,runner)
        exact['score']=min(s['components']['moderate'] for s in exact['scenarios'].values());rows[ident]=exact
    chosen=select_validation(rows,grid)
    write(ROOT/'selection.json',dict(**chosen,parameters=grid[chosen['selected']]['parameters'],rows=rows,buyhold=bench,
        known_through=str(a['days'][-1]),fit_sha256=digest(ROOT/'fit.json'),input_sha256=digest(ROOT/'input_manifest.json')))
    manifest(ROOT,'selection_manifest.json',[ROOT/'selection.json'])
    print('2023 sealed selection',chosen,'parameters',grid[chosen['selected']],flush=True)


def evaluate():
    audit();verify(ROOT,'fit_manifest.json');verify(ROOT,'selection_manifest.json')
    selection=read(ROOT/'selection.json');grid=read(ROOT/'grid.json');selected=grid[selection['selected']]
    roles=dict(baseline=BASELINE,selected=selection['selected'],entry_only=candidate_id(selected['confirmation'],5),
               holding_only=candidate_id(8,selected['deadline']),fast_no_time=candidate_id(1,0))
    a=asset('GLD');h=History.build(a);runner=SingleReplay(a,'GLD','2024-01-01')
    bench=benchmarks_for(a,'GLD','2024-01-01',FRICTIONS,runner);results={}
    for ident in sorted(set(roles.values())):
        tape=h.signals(grid[ident]['parameters']);exact,paths=exact_candidate(a,'GLD',tape,'2024-01-01','event',FRICTIONS,bench,runner)
        dest=ROOT/'evaluation'/ident;dest.mkdir(parents=True,exist_ok=True)
        for friction,path in paths.items():np.savez_compressed(dest/(friction.replace(':','_')+'.npz'),**path)
        np.savez_compressed(dest/'signal.npz',**tape)
        idx=transitions(tape['active'],a['days'],'2024-01-01','event')
        _,economic,_=runner.run(.98*tape['active'][:,None],idx,5,0,detailed=True)
        write(dest/'economic.json',economic);results[ident]=exact
        print('Evaluation',ident,exact['scenarios']['5:0']['metrics'],flush=True)
    write(ROOT/'evaluation.json',dict(roles=roles,results=results,buyhold=bench,selection_sha256=digest(ROOT/'selection.json'),through=str(a['days'][-1])))
    manifest(ROOT,'evaluation_manifest.json',[ROOT/'evaluation.json',*[p for p in (ROOT/'evaluation').rglob('*') if p.is_file()]])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','fit','select','evaluate']);args=parser.parse_args()
    globals()[args.stage]()
