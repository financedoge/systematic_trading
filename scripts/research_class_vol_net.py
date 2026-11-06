"""Full net replay of the four predeclared class/volatility constructions."""
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import importlib.util
import shutil

import numpy as np

import research_expanded_fr25_net as parent
import research_fr25_breadth as breadth
from research_cash_relative_retest import digest, gzwrite, metric, read, write
from run_range_breakout import Replay
from systematic_trading.research.target_change_rebalance import adoption_schedule

REPO=parent.REPO
OUT=REPO/'research/class-vol-net-20261103-v1'
WORK=REPO/'var/research/class-vol-net-20261103-v1'
OLD=REPO/'var/research/class-volatility-screen-20261016-v1'
HISTORY=REPO/'research/class-volatility-screen-20261016-v1'
CASH=REPO/'var/research/cash-relative-net-20261031-v1'
ARMS=('pooled_raw','pooled_risk','class_raw','class_risk')
TIMES=('monthly','0.10','0.40','0.80')
KEYS=[a+'-'+t for a in ARMS for t in TIMES]
COSTS=[(c,d) for c in (5,10,20) for d in (0,1)]
HALVES={'first':(parent.START,'2022-12-30'),'second':('2023-01-03','2024-12-31')}


def checked(root,hashes):
    for rel,h in hashes.items():
        if digest(root/rel)!=h:raise ValueError('Hash mismatch: '+str(root/rel))


def prepare():
    if (OUT/'protocol.json').exists():raise FileExistsError('Protocol already frozen')
    current=read(parent.OUT/'protocol.json')
    old=read(CASH/'protocol.json')
    exact=read(HISTORY/'receipt.json')
    checked(HISTORY,{'protocol.json':exact['protocol_sha256']})
    checked(OLD,{'input_manifest.json':exact['input_manifest_sha256'],'result_manifest.json':exact['result_manifest_sha256']})
    for source,names in [('input_manifest.json',['runner.py','price_pin.json']),('result_manifest.json',
            [f'targets/{a}.json' for a in ARMS]+[f'adoptions/{key}.json' for key in KEYS])]:
        manifest=read(OLD/source)
        checked(OLD,{name:manifest[name] for name in names})
    checked(parent.OUT,{'protocol.json':read(parent.OUT/'artifact-manifest.json')['protocol.json']})
    archive=REPO/'research/cash-relative-net-20261031-v1'
    checked(archive,{'protocol.json':read(archive/'artifact-manifest.json')['protocol.json']})
    assert digest(archive/'protocol.json')==digest(CASH/'protocol.json')
    for p,folder in [(current,parent.WORK),(old,CASH)]:
        for name in ('inputs.npz','recipe.json'):
            file=folder/name
            assert digest(file)==p['artifacts'][file.relative_to(REPO).as_posix()]
    v=read(parent.OUT/'input-verification.json')
    checked(Path(current['price_pin']['root']),v['verified_files'])
    checked(Path(old['price_pin']['root']),old['input_files'])
    assert read(OLD/'price_pin.json')==old['price_pin']
    base=read(HISTORY/'protocol.json')
    base['classes']['commodity_energy']=['USO']
    base['overlap_parents']['DBC'].append('USO')
    write(OUT/'construction.json',dict(classes=base['classes'],overlap_parents=base['overlap_parents'],
          score=base['score'],construction=base['construction'],arms=list(ARMS)))
    p=dict(version=OUT.name,frozen_at=datetime.now(timezone.utc).isoformat(),code_sha256=digest(Path(__file__)),
        construction_sha256=digest(OUT/'construction.json'),old_runner_sha256=digest(OLD/'runner.py'),
        parent_paths=[str(p.relative_to(REPO)) for p in (parent.WORK,CASH,OLD)],
        price_pin=current['price_pin'],historical_pin=old['price_pin'],free_disk_bytes=shutil.disk_usage(REPO).free,
        limitations=current['limitations'],windows=parent.WINDOWS,halves=HALVES,frictions=COSTS,
        arms=ARMS,policies=TIMES,retrospective='Retired proxy gate originally withheld all 16 books. Replay original 50-fund schedules through Oct12 and separately test all 16 on the 52-fund Oct30 batch. BWX/XOP held. Common primary universe and dates match recent studies. CPER uses existing metals class, USO gets an energy-futures class and an explicit DBC conflict.',
        rule='Frozen positive 126-session raw momentum filter. Rank by raw momentum or divided by annualized 63-session volatility. Pooled six slots or best three granular classes with two slots each. Inverse-vol weighting, 98% max gross, 45% name cap, unfilled slots/excess stay cash, BIL remains eligible. Enforce historical overlap edges and prior-close liquidity/duplicate admission.',
        adoption='Monthly first session plus strict L1 theoretical vs last adopted, including cash, at 0.10/0.40/0.80. Shared USD1m whole adjusted units. Execution next open or one session later. Net costs 5/10/20bp per actual traded notional.',
        select='Training ends 2024-12-31. Among the 12 challengers (all except pooled_raw), require higher full IS net Sharpe than pooled_raw at identical timing, CAGR >= max(BIL CAGR, matched control CAGR minus 0.5pp), DD <= matched control DD + 2pp, both two-year IS halves profitable, positive full IS CAGR after placing its own three largest training winners in cash, positive 20bp/delay1 IS CAGR. Rank eligible challengers by higher weaker-half net Sharpe, then weaker-half CAGR, then full IS Sharpe, then lower turnover and lexical ID. If none qualifies, retain top-ranked challenger for diagnostics, label failure. Seal before later portfolio evaluation. No OOS rescue.',
        evaluation='Report all 16 x 6 cases on each batch. Separate paired changes from class choice and volatility division at matched timing/frictions. Later window already inspected. Quantify IS/OOS CAGR and Sharpe gaps, actual risky/BIL/cash exposure, fees, turnover and guarded comparisons. Cash/BIL/URTH/equal risky pool, simple momentum/unranked, FR25 original/expanded and Alpha54 references.',
        stress='Top one and three risky ETFs by net P&L / era-opening NAV. Withhold their weights into zero-interest cash, leaving other weights and dates intact. Carry training leaders into evaluation separately. Same-protocol incumbent results may be reused only with verified hashes.',
        uncertainty='Paired circular 21-session blocks, 4000 draws seed 20261103. Conditional 95% intervals for Sharpe and CAGR differences vs matched pooled_raw, plus Bonferroni intervals across the 12 challenger-versus-pooled contrasts. Descriptive weight/forward-open-return rank IC at 1/5/10/21/63 within each era. No lifetime threshold or IC veto.',
        weakest='Lowest risky net contribution / era-opening NAV, primary 5bp/next-open IS-selected timing, excluding BIL/URTH/cash. Inspect both eras with dated price/volume, targets, held weights, fills, protection and FIFO lots.')
    write(OUT/'protocol.json',p)
    write(WORK/'protocol.json',p)
    write(OUT/'inputs.json',dict(current=current['price_pin'],historical=old['price_pin'],current_files=v['verified_files'],
         historical_files=old['input_files'],source_receipt=exact,exclusions=current['exclusions']))


def validate():
    p=read(OUT/'protocol.json')
    if digest(Path(__file__))!=p['code_sha256'] or digest(OLD/'runner.py')!=p['old_runner_sha256'] or digest(OUT/'construction.json')!=p['construction_sha256']:
        raise ValueError('Frozen recipe changed')
    return p


def load_arrays(historical=False,train=False):
    if not historical:return breadth.input_arrays(train)
    with np.load(CASH/'inputs.npz') as z:return dict(z)


def build():
    validate()
    if (OUT/'target-receipt.json').exists():raise FileExistsError('Targets already frozen')
    spec=importlib.util.spec_from_file_location('frozen_class_screen',OLD/'runner.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p=read(OUT/'construction.json')
    a=load_arrays()
    days=a['days'];symbols=a['symbols'].tolist()
    metadata=read(parent.WORK/'candidates.json')
    ids={r['symbol']:r['candidate_id'] for r in metadata}
    mapping={s:group for group,members in p['classes'].items() for s in members}
    assert set(symbols)<=mapping.keys() and sum(s in symbols for group in p['classes'].values() for s in group)==len(symbols)
    monthly=days[breadth.monthly_indices(days)+1].tolist()
    schedules={};observations={};adoptions={}
    for arm in ARMS:
        w=np.zeros((len(days),len(symbols)+1));tape={}
        for i in range(np.searchsorted(days,parent.START),len(days)):
            momentum,vol=module.features(a['close'],i)
            admitted=a['symbols'][a['admitted'][i-1]].tolist()
            weights,detail=module.build_targets(symbols,momentum,vol,admitted,mapping,ids,p,arm)
            w[i-1,:-1]=[float(weights[s]) for s in symbols]
            assert all(s in admitted for s in detail['selected'])
            tape[str(days[i])]=dict(signal_session=str(days[i]),known_through=str(days[i-1]),
                targets=[dict(symbol=s,target_weight=str(weights[s])) for s in detail['selected']])
        for timing in TIMES:
            adopted,_=adoption_schedule(tape,monthly,timing)
            key=arm+'-'+timing
            schedules[key+'_weights']=w
            schedules[key+'_indices']=np.array([np.searchsorted(days,d)-1 for d in adopted],int)
            adoptions[key]=len(adopted)
    np.savez_compressed(WORK/'current.npz',**schedules)
    a=load_arrays(True);days=a['days'];symbols=a['symbols'].tolist();old_schedules={}
    for arm in ARMS:
        tape=read(OLD/'targets'/f'{arm}.json')
        w=np.zeros((len(days),len(symbols)+1))
        for day,row in tape.items():
            i=int(np.searchsorted(days,day))
            assert days[i]==day and days[i-1]==row['known_through']
            targets={t['symbol']:float(t['target_weight']) for t in row['targets']}
            w[i-1,:-1]=[targets.get(s,0) for s in symbols]
        for timing in TIMES:
            key=arm+'-'+timing
            ledger=read(OLD/'adoptions'/f'{key}.json')
            ix=[int(np.searchsorted(days,r['signal_session']))-1 for r in ledger if r['adopted']]
            old_schedules[key+'_weights']=w
            old_schedules[key+'_indices']=np.array(ix,int)
            observations[key]=len(ix)
    assert sum(observations.values())==read(HISTORY/'receipt.json')['verified_adoptions']
    np.savez_compressed(WORK/'historical.npz',**old_schedules)
    write(OUT/'target-receipt.json',dict(schedules={k:digest(WORK/(k+'.npz')) for k in ('current','historical')},
        current_adoptions=adoptions,historical_adoptions=observations,original_vectors=sum(len(read(OLD/'targets'/f'{arm}.json')) for arm in ARMS)))


def init(batch,train=False):
    global ENGINE,SCHEDULES
    historical=batch=='historical'
    arrays=load_arrays(historical,train)
    ENGINE=Replay(arrays,read((CASH if historical else parent.WORK)/'recipe.json'),parent.START)
    file=WORK/(batch+'.npz')
    assert digest(file)==read(OUT/'target-receipt.json')['schedules'][batch]
    with np.load(file) as z:SCHEDULES=dict(z)


def payload(key):
    return SCHEDULES[key+'_weights'][:len(ENGINE.a['days'])],SCHEDULES[key+'_indices'][SCHEDULES[key+'_indices']+1<len(ENGINE.a['days'])]


def measures(v,windows):
    return {name:metric(ENGINE.day_strings,v['nav'],lo,hi,fees=v['fees'],turnover=v['turnover'],exposure=v['exposure'])
            for name,(lo,hi) in windows.items()}


def attribution(v,era):
    lo,hi=parent.WINDOWS[era]
    ix=np.flatnonzero((ENGINE.day_strings>=lo)&(ENGINE.day_strings<=hi))
    base=v['nav'][ix[0]-1] if ix[0] else 1e6
    pnl=v['contribution'][ix].sum(axis=0)/base
    assert abs(pnl.sum()-(v['nav'][ix[-1]]/base-1))<1e-8
    by=dict(zip(ENGINE.symbols,pnl.tolist(),strict=True))
    top=sorted((s for s in by if s not in ('BIL','URTH') and by[s]>0),key=lambda s:(-by[s],s))[:3]
    gain=sum(by[s] for s in top);pos=sum(max(0,value) for value in by.values())
    return dict(top=top,top_pp=100*gain,by_symbol=by,share_positive=gain/pos if pos else None,
        share_net=gain/pnl.sum() if pnl.sum()>0 else None)


def remove(w,idx,names):
    new=w.copy()
    for s in names:new[:,ENGINE.symbols.index(s)]=0
    return ENGINE.run(new,idx,5,0)[0]


def train_one(key):
    w,idx=payload(key)
    v=ENGINE.run(w,idx,5,0)[0]
    windows={'calibration':parent.WINDOWS['calibration'],**HALVES}
    m=measures(v,windows);leaders=attribution(v,'calibration')['top']
    return dict(key=key,metrics=m,leaders=leaders,withheld_cagr=measures(remove(w,idx,leaders),windows)['calibration']['cagr'],
        stressed_cagr=measures(ENGINE.run(w,idx,20,1)[0],windows)['calibration']['cagr'])


def choose(rows,bill):
    lookup={r['key']:r for r in rows};challengers=[]
    for r in rows:
        arm,timing=r['key'].split('-')
        if arm=='pooled_raw':continue
        x=r['metrics']['calibration'];base=lookup['pooled_raw-'+timing]['metrics']['calibration']
        r['checks']=dict(sharpe=x['sharpe']>base['sharpe'],return_floor=x['cagr']>=max(bill,base['cagr']-.005),
            dd=x['max_drawdown']<=base['max_drawdown']+.02,positive_halves=min(r['metrics'][h]['cagr'] for h in HALVES)>0,
            winner_stress=r['withheld_cagr']>0,cost_delay=r['stressed_cagr']>0)
        r['eligible']=all(r['checks'].values());challengers.append(r)
    valid=[r for r in challengers if r['eligible']]
    def order(r):
        return (-min(r['metrics'][h]['sharpe'] for h in HALVES),-min(r['metrics'][h]['cagr'] for h in HALVES),
            -r['metrics']['calibration']['sharpe'],r['metrics']['calibration']['annual_turnover'],r['key'])
    return min(valid or challengers,key=order),len(valid)


def train():
    validate()
    if (OUT/'selection.json').exists():raise FileExistsError('Selection sealed')
    with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=('current',True)) as ex:
        rows=list(ex.map(train_one,KEYS))
    init('current',True)
    w=np.zeros_like(payload(KEYS[0])[0]);w[:,ENGINE.symbols.index('BIL')]=1.
    bill=measures(ENGINE.run(w,breadth.monthly_indices(ENGINE.a['days'])[:1],5,0)[0],{'IS':parent.WINDOWS['calibration']})['IS']['cagr']
    selected,n=choose(rows,bill)
    write(OUT/'training.json',rows)
    write(OUT/'selection.json',dict(selected=selected['key'],eligible=n,qualified=selected['eligible'],checks=selected['checks'],
        bill_cagr=bill,cutoff=str(ENGINE.day_strings[-1]),sealed_at=datetime.now(timezone.utc).isoformat(),
        training_sha256=digest(OUT/'training.json'),protocol_sha256=digest(OUT/'protocol.json')))


def net_job(args):
    batch,key,c,d=args
    w,idx=payload(key)
    detail=batch=='current' and (c,d)==(5,0)
    v,econ,count=ENGINE.run(w,idx,c,d,detailed=detail)
    if batch=='current' and ((c,d)==(5,0) or (key=='class_risk-0.10' and (c,d)==(20,1))):
        label=f'{key}_c{c}d{d}'
        np.savez_compressed(WORK/'paths'/(label+'.npz'),**v)
        if detail:gzwrite(WORK/'detail'/(label+'.json.gz'),econ)
    return dict(arm=key,cost_bp=c,delay=d,fills=count,windows=measures(v,{**parent.WINDOWS,**HALVES}))


def evaluate():
    validate();choice=read(OUT/'selection.json')
    assert choice['training_sha256']==digest(OUT/'training.json') and choice['cutoff']=='2024-12-31'
    for sub in ('paths','detail'):(WORK/sub).mkdir(exist_ok=True)
    for batch in ('current','historical'):
        with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=(batch,False)) as ex:
            rows=list(ex.map(net_job,[(batch,key,c,d) for key in KEYS for c,d in COSTS],chunksize=2))
        write(OUT/(batch+'-results.json'),rows)
    init('current');key=choice['selected'];control='pooled_raw-'+key.split('-')[1];out={};stress={}
    for arm in (key,control):
        w,idx=payload(arm)
        with np.load(WORK/'paths'/f'{arm}_c5d0.npz') as z:v=dict(z)
        out[arm]={e:attribution(v,e) for e in ('calibration','later')}
        stress[arm]={}
        for e in ('calibration','later'):
            stress[arm][e]={}
            for flag,names in [('top1',out[arm][e]['top'][:1]),('top3',out[arm][e]['top']),('is_top3',out[arm]['calibration']['top'])]:
                stress[arm][e][flag]=dict(names=names,**measures(remove(w,idx,names),{e:parent.WINDOWS[e]})[e])
    write(OUT/'attribution.json',out);write(OUT/'withholding.json',stress)
    ref=next(r for r in read(OUT/'training.json') if r['key']==key)
    assert abs(stress[key]['calibration']['top3']['cagr']-ref['withheld_cagr'])<1e-12
    print('Completed 192 net cases. Training selection:',key,'qualified',choice['qualified'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','build','train','evaluate'])
    globals()[parser.parse_args().stage]()
