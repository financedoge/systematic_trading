"""Joint pre-2023 fitting, 2023 variant selection, sealed 2024+ evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from scipy.stats import qmc, rankdata

from calibrate_range_breakout import SingleReplay, load_asset, selected_signal, summary_path
from run_range_breakout import read, write, digest, verify, manifest
from systematic_trading.research.range_calibration import transitions
from systematic_trading.research.range_breakout import metrics
from systematic_trading.research.range_joint import (
    History, PARAMETERS, BOUNDS, INTEGRAL, canonical, v1_anchor,
    screen_stats, risk_stats, objective_components,
)

ROOT=Path('var/research/range-breakout-20261018-v3')
PUBLIC=Path('research/range-breakout-20261018-v3')
PARENT=Path('var/research/range-breakout-20261018-v2')
FRICTIONS=((5,0),(10,0),(5,1))
NAMES=('raw','weak','moderate','strong','stable')
COMPLEXITY=('shared','shrinkage','local_stability','stable','strong','moderate','weak','raw','v2','v1')


def asset(symbol, end=None):
    a=load_asset(PARENT,symbol)
    if end:
        a={k:v[a['days']<=end] for k,v in a.items()}
    return a


def prepare(root):
    if (root/'input_manifest.json').exists():
        check(root)
        return
    verify(PARENT,'input_manifest.json');verify(PARENT,'selection_manifest.json')
    root.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(PUBLIC/'protocol.json',root/'protocol.json')
    shutil.copyfile(__file__,root/'runner.py')
    for name in ('run_range_breakout.py','calibrate_range_breakout.py'):
        shutil.copyfile(Path('scripts')/name,root/name)
    shutil.copytree('src/systematic_trading',root/'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    write(root/'bounds.json',[dict(name=p[0],lower=p[1],upper=p[2],integer=p[3]) for p in PARAMETERS])
    import scipy, numba, llvmlite
    write(root/'parent.json',dict(path=str(PARENT.resolve()),input_sha256=digest(PARENT/'input_manifest.json'),
        selection_sha256=digest(PARENT/'selection_manifest.json'),assets=read(PARENT/'input_receipt.json')['assets'],
        versions=dict(numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,numba=numba.__version__,llvmlite=llvmlite.__version__)))
    manifest(root,'runtime_manifest.json',[p for p in (root/'runtime').rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.nbc','.nbi')])
    manifest(root,'input_manifest.json',[p for p in root.rglob('*') if p.is_file() and 'runtime' not in p.parts
             and '__pycache__' not in p.parts and p.name!='input_manifest.json'])
    print('Prepared joint study; no post-2022 fitting inputs',flush=True)


def check(root):
    verify(root,'input_manifest.json')
    pin=read(root/'parent.json')
    if digest(PARENT/'input_manifest.json')!=pin['input_sha256'] or digest(PARENT/'selection_manifest.json')!=pin['selection_sha256']:
        raise ValueError('Parent pin changed')
    verify(PARENT,'input_manifest.json');verify(PARENT,'selection_manifest.json')
    for name in ('range_joint.py','range_calibration.py','range_breakout.py'):
        if digest(Path('src/systematic_trading/research')/name)!=digest(root/'source/systematic_trading/research'/name):
            raise ValueError('Research source differs from sealed input: '+name)
    if digest(Path(__file__))!=digest(root/'runner.py'):
        raise ValueError('Runner differs from sealed source')


def v2_anchor(symbol):
    ident=read(PARENT/'selection.json')['selections'][symbol]['id']
    p=v1_anchor()
    if ident=='v1':
        return p
    g=read(PARENT/'grid.json')[int(ident)];r,e=g['range'],g['exit']
    p[0 if r['basis']=='absolute' else 1]=r['threshold'];p[2]=int(r['basis']!='absolute')
    p[3:5]=[0,8];p[6]=r['drift'];p[14]=int(g['volume']);p[17]=e['initial_atr']
    p[18]=e['range_buffer'] if e['range_buffer'] is not None else -1;p[19]=-1
    p[20]=2 if e['trail_basis']=='percent' else 0;p[22 if p[20]==2 else 21]=e['trail']
    p[24]=int(e['heat_multiplier']<1);p[28]=e['heat_multiplier'];p[30]=0
    return canonical(p)


def key(p):
    return hashlib.sha256(np.round(canonical(p),12).tobytes()).hexdigest()[:16]


def stats_exact(path,a,start,closed):
    first=int(np.flatnonzero(a['days']>=start)[0]);nav=path['nav'];prev=np.r_[1e6,nav[:-1]]
    r=nav/prev-1;ar=a['close'][first:]/a['close'][first-1:-1]-1;n=len(nav)
    result=[]
    for ids in [np.arange(n),*[np.flatnonzero(np.minimum(2,np.arange(n)*3//n)==i) for i in range(3)]]:
        if not len(ids):
            result.append([0.]*7);continue
        initial=prev[ids[0]];v=nav[ids];rr=r[ids];aa=ar[ids]
        cagr=(v[-1]/initial)**(252/len(ids))-1
        dd=float(np.min(v/np.maximum.accumulate(np.r_[initial,v])[1:]-1));sd=np.std(rr,ddof=1)
        corr=np.corrcoef(rr,aa)[0,1] if sd>1e-12 and np.std(aa)>1e-12 else 0.
        result.append([cagr,float(np.mean(rr)/sd*np.sqrt(252)) if sd>1e-12 else 0.,
            cagr/max(.03,-dd),dd,float(np.mean(path['exposure'][ids])),float(corr),int(np.sum(closed[ids]))])
    return np.array(result)


def adopt_state(sig,days,start,policy,delay):
    idx=transitions(sig,days,start,policy);changes={i+1+delay:bool(sig[i]) for i in idx if i+1+delay<len(days)}
    state=np.zeros(len(days),bool);held=False
    for t in range(len(days)):
        held=changes.get(t,held);state[t]=held
    closed=np.r_[False,state[:-1]&~state[1:]]
    return idx,closed


def exact_candidate(a,s,tape,start,policy,frictions,benchmarks,runner=None):
    runner=runner or SingleReplay(a,s,start);first=int(np.flatnonzero(a['days']>=start)[0])
    risk=risk_stats(tape,a['open'],first,len(a['days']));rows={};paths={}
    for cost,delay in frictions:
        idx,closed=adopt_state(tape['active'],a['days'],start,policy,delay)
        path,_,fills=runner.run(.98*tape['active'][:,None],idx,cost,delay)
        st=stats_exact(path,a,start,closed[first:]);bm=benchmarks[f'{cost}:{delay}']['stats']
        component=objective_components(st,np.array(bm),risk);m=summary_path(path,runner)
        m['calmar']=m['cagr']/abs(m['max_drawdown']) if m['max_drawdown']<0 else None
        rows[f'{cost}:{delay}']=dict(metrics=m,stats=st.tolist(),components=component,risk=risk.tolist(),fills=fills,
            guard_pass=bool(st[0,0]>=max(0,bm[0][0]-.02) and st[0,3]>=bm[0][3]-.05))
        paths[f'{cost}:{delay}']=path
    return dict(scenarios=rows,guard_pass=all(r['guard_pass'] for r in rows.values())),paths


def benchmarks_for(a,s,start,frictions,runner):
    sig=np.ones(len(a['days']),bool);result={}
    for cost,delay in frictions:
        idx,closed=adopt_state(sig,a['days'],start,'event',delay)
        path,_,_=runner.run(.98*sig[:,None],idx,cost,delay)
        result[f'{cost}:{delay}']=dict(stats=stats_exact(path,a,start,closed[len(a['days'])-len(path['nav']):]).tolist())
    return result


def fit_one(root,s):
    a=asset(s,'2022-12-31');n=len(a['days']);h=History.build(a)
    if n-252<1260:
        write(root/'fits'/f'{s}.json',dict(symbol=s,known_through=str(a['days'][-1]),insufficient=True,variants={}))
        return
    start=str(a['days'][252]);bh=screen_stats(a['close'],a['open'],np.ones(n,bool),252,n)
    cache={}
    def evaluate(p):
        p=canonical(p);ident=key(p)
        if ident not in cache:
            t=h.signals(p);st=screen_stats(a['close'],a['open'],t['active'],252,n)
            risk=risk_stats(t,a['open'],252,n);components=objective_components(st,bh,risk)
            cache[ident]=dict(id=ident,parameters=p.tolist(),stats=st.tolist(),risk=risk.tolist(),components=components,
                             evidence=bool(st[0,6]>=4 and st[0,4]>=.05))
        return cache[ident]
    trajectories=[];config=read(root/'protocol.json')['optimizer']
    for objective in config['objectives']:
        for seed in config['seeds']:
            initial=qmc.Sobol(len(PARAMETERS),scramble=True,seed=seed).random_base2(7)
            initial=BOUNDS[:,0]+initial*(BOUNDS[:,1]-BOUNDS[:,0]);initial[0]=v1_anchor();initial[1]=v2_anchor(s)
            history=[]
            def fitness(p):
                r=evaluate(p)
                return -r['components'][objective] if r['evidence'] else 1000-r['stats'][0][6]-r['stats'][0][4]
            def callback(x,convergence):
                history.append(float(-fitness(x)))
                return False
            r=differential_evolution(fitness,BOUNDS,strategy='best1bin',maxiter=config['generations'],init=initial,
                mutation=(.5,1.),recombination=.7,polish=False,workers=1,tol=0,atol=0,
                integrality=INTEGRAL,rng=seed,callback=callback)
            trajectories.append(dict(objective=objective,seed=seed,generations=r.nit,evaluations=r.nfev,
                success=bool(r.success),message=str(r.message),best=evaluate(r.x)['id'],score=float(-r.fun),trajectory=history))
    feasible=[r for r in cache.values() if r['evidence']]
    if not feasible:
        write(root/'fits'/f'{s}.json',dict(symbol=s,known_through=str(a['days'][-1]),insufficient=True,variants={},trajectories=trajectories))
        return
    leaders={name:sorted(feasible,key=lambda r:(-r['components'][name],r['id']))[:3] for name in NAMES}
    local_leaders={r['id']:r for name in ('moderate','stable') for r in sorted(feasible,key=lambda r:-r['components'][name])[:6]}
    local={};rng=np.random.default_rng(20261018)
    for ident,r in local_leaders.items():
        scores=[]
        for _ in range(16):
            p=np.array(r['parameters']);q=p+rng.uniform(-.05,.05,len(p))*(BOUNDS[:,1]-BOUNDS[:,0])
            q[INTEGRAL]=p[INTEGRAL]+rng.choice([-1,0,1],int(INTEGRAL.sum()),p=[.1,.8,.1])
            rr=evaluate(q);scores.append(rr['components']['moderate'] if rr['evidence'] else -10.)
        local[ident]=dict(score=float(np.median(scores)-.5*np.std(scores)),median=float(np.median(scores)),std=float(np.std(scores)),values=scores)
    finalists={r['id']:r for rows in leaders.values() for r in rows}
    local_ids=sorted(local,key=lambda ident:(-local[ident]['score'],ident))[:3]
    finalists.update({i:cache[i] for i in local_ids})
    runner=SingleReplay(a,s,start);bench=benchmarks_for(a,s,start,FRICTIONS,runner);exact={}
    for ident,r in finalists.items():
        exact[ident],_=exact_candidate(a,s,h.signals(r['parameters']),start,'event',FRICTIONS,bench,runner)
    variants={}
    for name in (*NAMES,'local_stability'):
        ids=local_ids if name=='local_stability' else [r['id'] for r in leaders[name]]
        def score(i):
            rows=exact[i]['scenarios']
            if name=='raw':
                return rows['5:0']['components']['raw']
            sc=min(r['components']['moderate' if name=='local_stability' else name] for r in rows.values())
            if name=='local_stability':
                sc-=max(0.,cache[i]['components']['moderate']-local[i]['score'])
            return sc
        ident=max(ids,key=lambda i:(score(i),i));variants[name]=dict(id=ident,parameters=cache[ident]['parameters'],score=score(ident),
            guard_pass=exact[ident]['guard_pass'],exact=exact[ident])
    write(root/'fits'/f'{s}.json',dict(symbol=s,first=str(a['days'][0]),fit_start=start,known_through=str(a['days'][-1]),
        sessions=n-252,insufficient=False,unique_evaluations=len(cache),trajectories=trajectories,variants=variants,
        archive={i:dict(finalists[i],exact=exact[i]) for i in finalists},local=local,buyhold=bench))
    print(json.dumps(dict(stage='fit',symbol=s,trials=len(cache),raw=variants['raw']['score'],moderate=variants['moderate']['score'],
                         feasible=len(feasible))),flush=True)


def fit(root,only=None):
    check(root);symbols=read(root/'parent.json')['assets']
    order=['GLD','USO','SOXX']+sorted(set(symbols)-{'GLD','USO','SOXX'})
    for s in order:
        if only and s not in only:
            continue
        if not (root/'fits'/f'{s}.json').exists():
            fit_one(root,s)


def shared(root):
    check(root)
    if (root/'variants_manifest.json').exists():
        verify(root,'variants_manifest.json');return
    fits={s:read(root/'fits'/f'{s}.json') for s in read(root/'parent.json')['assets']}
    candidates={v['id']:v['parameters'] for f in fits.values() if not f['insufficient']
                for name,v in f['variants'].items() if name in ('raw','moderate','stable')}
    ids=sorted(candidates);ranks=[]
    for s,f in fits.items():
        if f['insufficient']:
            continue
        a=asset(s,'2022-12-31');h=History.build(a);n=len(a['days']);bh=screen_stats(a['close'],a['open'],np.ones(n,bool),252,n)
        scores=[]
        for ident in ids:
            tape=h.signals(candidates[ident]);st=screen_stats(a['close'],a['open'],tape['active'],252,n)
            scores.append(objective_components(st,bh,risk_stats(tape,a['open'],252,n))['moderate'])
        ranks.append(rankdata(scores)/len(scores))
    median=np.median(ranks,axis=0);ident=ids[int(np.argmax(median))];p=np.array(candidates[ident]);variants={}
    for s,f in fits.items():
        vv={name:dict(parameters=v['parameters'],IS=v['exact'],id=v['id']) for name,v in f['variants'].items()}
        a=asset(s,'2022-12-31');h=History.build(a);start=str(a['days'][252]);runner=SingleReplay(a,s,start)
        bench=benchmarks_for(a,s,start,FRICTIONS,runner)
        for name,q in [('shared',p),('shrinkage',canonical(np.where(INTEGRAL,np.array(vv['moderate']['parameters']),
                           .5*(np.array(vv['moderate']['parameters'])+p))))] if vv else [('shared',p)]:
            ex,_=exact_candidate(a,s,h.signals(q),start,'event',FRICTIONS,bench,runner)
            vv[name]=dict(parameters=q.tolist(),IS=ex,id=key(q))
        variants[s]=vv
    write(root/'variants.json',dict(fit_end='2022-12-31',sealed_utc=pd.Timestamp.now(tz='UTC').isoformat(),
        shared_id=ident,shared_parameters=p.tolist(),shared_candidates=len(ids),median_rank=float(max(median)),variants=variants))
    manifest(root,'variants_manifest.json',[root/'variants.json',*sorted((root/'fits').glob('*.json'))])
    print('Sealed all numeric variants before 2023 selection',flush=True)


def control_tape(a,s,name,h):
    if name=='v1':
        return h.signals(v1_anchor())
    if name in ('buyhold','sma200'):
        active=np.ones(len(a['days']),bool) if name=='buyhold' else a['close']>pd.Series(a['close']).rolling(200).mean().to_numpy()
        return dict(active=active,stop=np.full(len(active),np.nan),risk=np.zeros((len(active),2)))
    ident=read(PARENT/'selection.json')['selections'][s]['id']
    if ident=='v1':
        return h.signals(v1_anchor())
    tape=selected_signal(a,ident,details=True);active=tape['active'];stops=tape['stop'].copy()
    # Preserve v2 timing exactly; reconstruct causal planned risk, never episode future maxima.
    g=read(PARENT/'grid.json')[int(ident)];buffer=g['exit']['range_buffer']
    if buffer is not None:
        stops=np.fmax(stops,tape['upper']-buffer*tape['entry_atr'])
    risk=np.full((len(active),2),np.nan);peak=0.
    for t in range(1,len(active)):
        if active[t-1] and not (t>1 and active[t-2]):
            peak=a['open'][t];initial=max(0.,peak-g['exit']['initial_atr']*tape['entry_atr'][t-1])
            if buffer is not None:
                initial=max(initial,tape['upper'][t-1]-buffer*tape['entry_atr'][t-1])
            risk[t,0]=max(0.,(peak-initial)/peak)
        if active[t-1]:
            peak=max(peak,a['close'][t]);risk[t,1]=max(0.,(peak-stops[t])/peak) if np.isfinite(stops[t]) else np.nan
    return dict(active=active,stop=stops,risk=risk)


def validate(root,only=None):
    check(root);verify(root,'variants_manifest.json');variants=read(root/'variants.json')['variants']
    for s,vv in variants.items():
        if only and s not in only:
            continue
        if (root/'validation'/f'{s}.json').exists():
            continue
        a=asset(s,'2023-12-31');h=History.build(a);start='2023-01-01';runner=SingleReplay(a,s,start)
        bench=benchmarks_for(a,s,start,FRICTIONS,runner);rows={}
        for name in (*vv,'v2','v1'):
            tape=h.signals(vv[name]['parameters']) if name in vv else control_tape(a,s,name,h)
            for policy in ('event','monthly'):
                ex,_=exact_candidate(a,s,tape,start,policy,FRICTIONS,bench,runner)
                ex.update(score=min(r['components']['moderate'] for r in ex['scenarios'].values()),name=name,policy=policy)
                rows[name+'_'+policy]=ex
        passing={k:r for k,r in rows.items() if r['guard_pass']};pool=passing or rows;best=max(r['score'] for r in pool.values())
        chosen=min((k for k,r in pool.items() if r['score']>=best-.03),key=lambda k:(COMPLEXITY.index(rows[k]['name']),
            rows[k]['scenarios']['5:0']['metrics']['annual_turnover'],k))
        write(root/'validation'/f'{s}.json',dict(known_through='2023-12-29',selected=chosen,guard_pass=bool(passing),rows=rows,buyhold=bench))
        print('2023 selection',s,chosen,round(rows[chosen]['score'],3),'guard',bool(passing),flush=True)


def seal(root):
    if (root/'selection_manifest.json').exists():
        verify(root,'selection_manifest.json');return
    check(root);verify(root,'variants_manifest.json');variants=read(root/'variants.json')['variants'];choices={}
    for s,vv in variants.items():
        v=read(root/'validation'/f'{s}.json');r=v['rows'][v['selected']]
        choices[s]=dict(variant=r['name'],policy=r['policy'],validation_score=r['score'],guard_pass=v['guard_pass'],
                       parameters=vv[r['name']]['parameters'] if r['name'] in vv else None)
    write(root/'selection.json',dict(fit_end='2022-12-31',selection_end='2023-12-31',oos_start='2024-01-01',
        sealed_utc=pd.Timestamp.now(tz='UTC').isoformat(),variants_sha256=digest(root/'variants_manifest.json'),choices=choices))
    manifest(root,'selection_manifest.json',[root/'selection.json',*sorted((root/'validation').glob('*.json'))])
    print('SEALED before OOS:',digest(root/'selection.json'),flush=True)


def evaluate(root,only=None):
    check(root);verify(root,'variants_manifest.json');verify(root,'selection_manifest.json')
    variants=read(root/'variants.json')['variants'];choices=read(root/'selection.json')['choices']
    order=['GLD','USO','SOXX']+sorted(set(choices)-{'GLD','USO','SOXX'})
    frictions=tuple((c,d) for c in (5,10,20) for d in (0,1))
    for s in order:
        if only and s not in only:
            continue
        dest=root/'evaluation'/s
        if (dest/'manifest.json').exists():
            verify(dest,'manifest.json');continue
        a=asset(s);h=History.build(a);start='2024-01-01';runner=SingleReplay(a,s,start)
        bench=benchmarks_for(a,s,start,frictions,runner);vv=variants[s];choice=choices[s]
        tapes={name:h.signals(v['parameters']) for name,v in vv.items()}
        tapes.update({name:control_tape(a,s,name,h) for name in ('v1','v2','buyhold','sma200')})
        result={};dest.mkdir(parents=True,exist_ok=True)
        for name,tape in tapes.items():
            for policy in ('event','monthly'):
                ex,paths=exact_candidate(a,s,tape,start,policy,frictions,bench,runner)
                for friction,path in paths.items():
                    c,d=friction.split(':');k=f'{name}_{policy}_c{c}d{d}';row=ex['scenarios'][friction]
                    row['years']={str(y):metrics(**{k:path[k] for k in ('nav','turnover','fees','exposure')},
                        days=runner.day_strings,start=f'{y}-01-01',end=f'{y}-12-31') for y in range(2024,2027)}
                    result[k]=row
                    # Compact paths retained only at primary friction; stresses retain exact metrics.
                    if friction=='5:0':
                        np.savez_compressed(dest/f'{name}_{policy}.npz',**path)
        tape=tapes[choice['variant']]
        np.savez_compressed(dest/'signal.npz',**tape,days=a['days'])
        selected_key=f"{choice['variant']}_{choice['policy']}_c5d0"
        write(dest/'metrics.json',dict(selected_key=selected_key,rows=result))
        manifest(dest,'manifest.json',[p for p in dest.iterdir() if p.is_file()])
        print(json.dumps(dict(stage='oos',symbol=s,choice=selected_key,result=result[selected_key]['metrics'])),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','fit','shared','validate','seal','evaluate'))
    p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--only',nargs='*');args=p.parse_args();t=time.perf_counter()
    if args.stage in ('fit','validate','evaluate'):
        globals()[args.stage](args.root,args.only)
    else:
        globals()[args.stage](args.root)
    print('Elapsed seconds',round(time.perf_counter()-t,2),flush=True)


if __name__=='__main__':
    main()
