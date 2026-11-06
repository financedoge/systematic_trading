"""Finite search for stable portfolio returns using previously frozen daily targets."""
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import shutil

import numpy as np
from scipy.stats import rankdata

import research_expanded_fr25_net as parent
import research_fr25_breadth as breadth
from research_cash_relative_retest import digest, gzwrite, metric, read, write
from run_range_breakout import Replay
from systematic_trading.research.target_change_rebalance import adoption_schedule

REPO=parent.REPO
OUT=REPO/'research/etf-stability-20261103-v1'
WORK=REPO/'var/research/etf-stability-20261103-v1'
ALPHA=REPO/'research/alpha101-net-20261031-v1'
ALPHA_WORK=REPO/'var/research/alpha101-net-20261031-v1'
ERAS={'IS':(parent.START,'2024-12-31'),'OOS':('2025-01-02',parent.END)}
HALVES={'first':(parent.START,'2022-12-30'),'second':('2023-01-03','2024-12-31')}
COSTS=[(c,d) for c in (5,10,20) for d in (0,1)]
GRID=[(f,a,4-f-a,t) for f in range(5) for a in range(5-f) for t in ('monthly','0.40')]


def name(spec):
    f,a,u,t=spec
    return f'F{f}A{a}U{u}_{t}'


def verify_parent(out,work):
    manifest=read(out/'artifact-manifest.json')
    for filename in ('protocol.json','signal-manifest.json','results.json'):
        if digest(out/filename)!=manifest[filename]:
            raise ValueError('Parent evidence changed: '+str(out/filename))
    frozen=read(out/'signal-manifest.json')
    target=work/'schedules.npz'
    if digest(target)!=frozen[target.relative_to(REPO).as_posix()]:
        raise ValueError('Parent targets changed')
    p=read(out/'protocol.json')
    inputs=work/'inputs.npz'
    if digest(inputs)!=p['artifacts'][inputs.relative_to(REPO).as_posix()]:
        raise ValueError('Parent quotes changed')
    return p


def prepare():
    if (OUT/'protocol.json').exists():
        raise FileExistsError('Protocol is already frozen')
    fr=verify_parent(parent.OUT,parent.WORK)
    alpha=verify_parent(ALPHA,ALPHA_WORK)
    assert fr['price_pin']==alpha['price_pin']
    with np.load(parent.WORK/'inputs.npz') as x,np.load(ALPHA_WORK/'inputs.npz') as y:
        for k in ('days','symbols','open','close','raw_close','raw_volume','urth_open','urth_close'):
            if not np.array_equal(x[k],y[k]):
                raise ValueError('Source calendars, instruments or prices differ: '+k)
    evidence=read(parent.OUT/'input-verification.json')
    root=Path(fr['price_pin']['root'])
    for rel,expected in evidence['verified_files'].items():
        if digest(root/rel)!=expected:
            raise ValueError('Published input changed: '+rel)
    p=dict(version=OUT.name,frozen_at=datetime.now(timezone.utc).isoformat(),price_pin=fr['price_pin'],
        code_sha256=digest(Path(__file__)),parents=[str(p.relative_to(REPO)) for p in (parent.WORK,ALPHA_WORK)],
        parent_hashes={p.relative_to(REPO).as_posix():digest(p) for folder in (ALPHA,parent.OUT)
                       for p in (folder/'protocol.json',folder/'signal-manifest.json',folder/'artifact-manifest.json')},
        free_disk_bytes=shutil.disk_usage(WORK.anchor).free,trial_count=len(GRID),cost_delay=COSTS,windows=ERAS,halves=HALVES,
        family='Daily theoretical targets of three full-supported-pool sleeves: FR25 6/4, standalone Alpha54, unranked inverse 63-session volatility. Every convex 25-point allocation in the three sleeves. Net combined targets in one USD 1m whole-unit portfolio. Monthly anchors and monthly plus L1>0.40 relative to last adopted target including cash.',
        objective='Choose using IS only. Among eligible candidates maximize the WORST midrank of four criteria: higher weaker-half Sharpe, higher weaker-half CAGR, smaller absolute half-Sharpe gap, smaller absolute half-CAGR gap. Rank among the full 30-arm grid. Tie by mean of these four ranks, weaker-half Sharpe, lower turnover, then lexical ID. No later gap enters selection.',
        eligibility='Positive net CAGR in each IS half, whole-IS CAGR at least the greater of BIL CAGR and expanded 6/4 CAGR minus 0.5pp, IS drawdown at most 2pp worse than expanded 6/4, positive IS CAGR with its three biggest IS risky contributors set to cash, positive IS CAGR at 20bp and one extra session. If none qualifies, identify the score leader as diagnostic only and preserve the failed search.',
        concentration='Rank risky ETF contributions net of fees / era-opening NAV, exclude cash/BIL/URTH. Report top three, their pp, share of positive contribution and of net gain if positive. Conditional withholding: remove targets for those ETFs on all dates, preserve the original adoption dates and remaining weights, put freed weight into zero-interest cash, replay NAV and costs. Separate first and top-three stress for each era, locked training leaders carried into OOS, direct SOXX/XLK and broader SOXX/XLK/EWY/EWT sensitivities. A regional or sector ETF exclusion is not causal identification of AI exposure. Ex-post era winners are stress diagnostics only.',
        evaluation='Before new later combination results, seal weights, timing, training-only metrics and grid fingerprint. Compare abs(IS-OOS) gaps for 252-session CAGR and zero-rate net Sharpe against both original and expanded 6/4. A smaller gap on BOTH metrics vs BOTH books, positive net CAGR after removing each era top three in both eras, and training eligibility are the stability checks. Separately report matched return/drawdown guards across six frictions. No fallback promotion or re-selection.',
        uncertainty='Paired cross-strategy circular 21-session blocks within each era, independent era draws, 4000 iterations, seed 20261103. Conditional intervals for signed later-minus-IS CAGR/Sharpe gaps; no lifetime search correction. Inspect calendar years and named split halves.',
        weakest='Lowest net contribution / era-opening NAV, selected 5bp/next-open book, risky ETFs excluding BIL/URTH, chart each era with price, raw volume, weights, fills, allocation protection and FIFO outcomes.',
        limits=fr['limitations']+['Both eras and parent strategies were previously inspected. Concentration may occur in repeated themes across ETFs and common shocks. Deleting names does not rerank the universe or simulate a world without AI.'])
    write(OUT/'protocol.json',p)
    write(WORK/'protocol.json',p)


def validate():
    p=read(OUT/'protocol.json')
    if digest(Path(__file__))!=p['code_sha256']:
        raise ValueError('Runner differs from freeze')
    return p


def init(train):
    global ARRAYS,ENGINE,SLEEVES,PARENT,MONTHS
    ARRAYS=breadth.input_arrays(train)
    n=len(ARRAYS['days'])
    ENGINE=Replay(ARRAYS,read(parent.WORK/'recipe.json'),parent.START)
    with np.load(parent.WORK/'schedules.npz') as f,np.load(ALPHA_WORK/'schedules.npz') as a:
        SLEEVES=[f['expanded-monthly_weights'][:n],a['alpha54-monthly_weights'][:n],f['unranked-monthly_weights'][:n]]
        PARENT=f['original-monthly_weights'][:n]
    MONTHS=breadth.monthly_indices(ARRAYS['days'])


def schedule(spec):
    weights=sum(f*w for f,w in zip(np.array(spec[:3])/4,SLEEVES,strict=True))
    if spec[3]=='monthly':
        return weights,MONTHS
    days=ARRAYS['days']
    # Use the shared Decimal adoption policy, including implicit residual cash.
    tape={str(days[i+1]):dict(signal_session=str(days[i+1]),known_through=str(days[i]),
            targets=[dict(symbol=s,target_weight=str(round(float(w),12))) for s,w in zip(ENGINE.symbols,weights[i],strict=True) if w>0])
          for i in range(MONTHS[0],len(days)-1)}
    decisions,_=adoption_schedule(tape,days[MONTHS+1].tolist(),spec[3])
    return weights,np.array([np.searchsorted(days,d)-1 for d in decisions],dtype=int)


def stats(values,windows):
    return {k:metric(ENGINE.day_strings,values['nav'],start,end,fees=values['fees'],
                     turnover=values['turnover'],exposure=values['exposure']) for k,(start,end) in windows.items()}


def attribution(values,start,end):
    days=ENGINE.day_strings
    idx=np.flatnonzero((days>=start)&(days<=end))
    base=values['nav'][idx[0]-1] if idx[0] else 1e6
    pnl=values['contribution'][idx].sum(axis=0)/base
    total=values['nav'][idx[-1]]/base-1
    if abs(pnl.sum()-total)>1e-8:
        raise ValueError('Contribution does not reconcile')
    by_symbol=dict(zip(ENGINE.symbols,pnl.tolist(),strict=True))
    names=sorted((s for s in by_symbol if s not in ('BIL','URTH') and by_symbol[s]>0),key=lambda s:(-by_symbol[s],s))
    top=names[:3]
    gain=sum(by_symbol[s] for s in top)
    positive=sum(v for v in by_symbol.values() if v>0)
    return dict(by_symbol=by_symbol,top=top,top_sum=gain,total=total,share_of_positive=gain/positive if positive else None,
                share_of_net=gain/total if total>0 else None)


def withheld(weights,names,symbols):
    adjusted=weights.copy()
    for s in set(names):
        adjusted[:,symbols.index(s)]=0.
    return adjusted


def train_one(spec):
    w,idx=schedule(spec)
    base=ENGINE.run(w,idx,5,0)[0]
    m=stats(base,{'IS':ERAS['IS'],**HALVES})
    top=attribution(base,*ERAS['IS'])['top']
    no_winners=ENGINE.run(withheld(w,top,ENGINE.symbols),idx,5,0)[0]
    stress=ENGINE.run(w,idx,20,1)[0]
    return dict(id=name(spec),spec=spec,metrics=m,top=top,
        withheld=stats(no_winners,{'IS':ERAS['IS']})['IS'],stressed=stats(stress,{'IS':ERAS['IS']})['IS'])


def select(rows,bill,reference):
    measures=[]
    for r in rows:
        x=r['metrics']['first'];y=r['metrics']['second'];whole=r['metrics']['IS']
        measures.append([min(x['sharpe'],y['sharpe']),min(x['cagr'],y['cagr']),
                         -abs(x['sharpe']-y['sharpe']),-abs(x['cagr']-y['cagr'])])
        r['checks']=dict(positive_halves=min(x['cagr'],y['cagr'])>0,
            cagr_guard=whole['cagr']>=max(bill,reference['cagr']-.005),
            drawdown_guard=whole['max_drawdown']<=reference['max_drawdown']+.02,
            top_three_stress=r['withheld']['cagr']>0,cost_delay_stress=r['stressed']['cagr']>0)
        r['eligible']=all(r['checks'].values())
    ranks=rankdata(np.round(np.asarray(measures),12),axis=0,method='average')
    for r,metrics,rank in zip(rows,measures,ranks,strict=True):
        r.update(measures=metrics,ranks=rank.tolist(),worst_rank=float(min(rank)),mean_rank=float(np.mean(rank)))
    qualified=[r for r in rows if r['eligible']]
    return min(qualified or rows,key=lambda r:(-r['worst_rank'],-r['mean_rank'],-r['measures'][0],
               r['metrics']['IS']['annual_turnover'],r['id'])),len(qualified)


def train():
    validate()
    if (OUT/'selection.json').exists():
        raise FileExistsError('Selection already sealed')
    with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=(True,)) as pool:
        rows=list(pool.map(train_one,GRID))
    # BIL guard is computed on the price calendar truncated to the historical training end.
    init(True)
    w=np.zeros_like(SLEEVES[0])
    w[:,ENGINE.symbols.index('BIL')]=1
    bill=stats(ENGINE.run(w,MONTHS[:1],5,0)[0],{'IS':ERAS['IS']})['IS']['cagr']
    ref=next(r for r in rows if r['id']=='F4A0U0_monthly')['metrics']['IS']
    winner,count=select(rows,bill,ref)
    write(OUT/'training.json',rows)
    write(OUT/'selection.json',dict(id=winner['id'],spec=winner['spec'],qualified=winner['eligible'],
        eligible_candidates=count,trials=len(rows),bill_cagr=bill,return_floor=max(bill,ref['cagr']-.005),
        selected_metrics=winner['metrics'],ranking=winner['ranks'],max_price_date=str(ENGINE.day_strings[-1]),
        sealed_at=datetime.now(timezone.utc).isoformat(),grid_sha256=digest(OUT/'training.json'),protocol_sha256=digest(OUT/'protocol.json')))


def evaluate():
    validate()
    choice=read(OUT/'selection.json')
    assert choice['grid_sha256']==digest(OUT/'training.json') and choice['max_price_date']==ERAS['IS'][1]
    init(False)
    spec=choice['spec']
    alternate=[*spec[:3],'monthly' if spec[3]!='monthly' else '0.40']
    recipes={'selected':schedule(spec),'alternate':schedule(alternate),'original':(PARENT,MONTHS),
             'expanded':(SLEEVES[0],MONTHS),'alpha54':(SLEEVES[1],MONTHS),'unranked':(SLEEVES[2],MONTHS)}
    with np.load(parent.WORK/'schedules.npz') as f:
        for key in ('momentum-monthly','cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
            recipes[key]=(f[key+'_weights'],f[key+'_indices'])
    outputs={};attributions={};stresses={};saved={}
    years={str(y):(f'{y}-01-01',min(parent.END,f'{y}-12-31')) for y in range(2021,2027)}
    windows={**ERAS,**HALVES,**years}
    (WORK/'paths').mkdir(exist_ok=True)
    for arm,(w,idx) in recipes.items():
        outputs[arm]={}
        for c,d in COSTS:
            detail=(c,d)==(5,0) and arm in ('selected','expanded','original')
            values,econ,_=ENGINE.run(w,idx,c,d,detailed=detail)
            outputs[arm][f'{c}-{d}']=stats(values,windows)
            if (c,d)==(5,0) or (arm=='alternate' and (c,d)==(20,1)):
                np.savez_compressed(WORK/'paths'/f'{arm}_c{c}d{d}.npz',**values)
            if detail:
                gzwrite(WORK/'detail'/f'{arm}.json.gz',econ)
                attributions[arm]={era:attribution(values,*dates) for era,dates in ERAS.items()}
        if arm not in attributions:
            continue
        saved[arm+'_weights']=w
        saved[arm+'_indices']=idx
        stresses[arm]={}
        cache={}
        for era in ERAS:
            leaders=attributions[arm][era]['top']
            tests={'top_one':leaders[:1],'top_three':leaders,'training_top_three':attributions[arm]['IS']['top'],
                   'direct_tech':['SOXX','XLK'],'tech_and_regional':['SOXX','XLK','EWY','EWT']}
            stresses[arm][era]={}
            for label,removed in tests.items():
                key=tuple(sorted(removed))
                if key not in cache:
                    masked=withheld(w,removed,ENGINE.symbols)
                    cache[key]=stats(ENGINE.run(masked,idx,5,0)[0],ERAS)
                stresses[arm][era][label]=dict(removed=removed,**cache[key][era])
    for arm,key in [('expanded','expanded-monthly'),('original','original-monthly')]:
        with np.load(parent.WORK/'paths'/f'{key}_c5d0.npz') as base,np.load(WORK/'paths'/f'{arm}_c5d0.npz') as new:
            assert np.array_equal(base['nav'],new['nav']),arm
    assert abs(outputs['selected']['5-0']['IS']['sharpe']-choice['selected_metrics']['IS']['sharpe'])<1e-12
    assert abs(stresses['selected']['IS']['top_three']['cagr']-next(r for r in read(OUT/'training.json') if r['id']==choice['id'])['withheld']['cagr'])<1e-12
    saved['alternate_weights'],saved['alternate_indices']=recipes['alternate']
    np.savez_compressed(WORK/'schedules.npz',**saved)
    write(OUT/'results.json',outputs)
    write(OUT/'attribution.json',attributions)
    write(OUT/'withholding.json',stresses)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','train','evaluate'))
    globals()[parser.parse_args().stage]()
