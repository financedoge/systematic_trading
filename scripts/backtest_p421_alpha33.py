"""Replay the frozen P4.21 pilot through the application's accounting engine."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

import research_p421_alpha33 as s
from research_alpha101_net import portfolio
from research_cash_relative_retest import clean, gzwrite, metric
from run_range_breakout import Replay
from systematic_trading.config import AppSettings
from systematic_trading.domain.market import Instrument
from systematic_trading.market_data.analytics_store import AnalyticsStore, encode
from systematic_trading.research.etf_expansion import load_published_pool
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.target_change_rebalance import adoption_schedule


class PilotReplay(Replay):
    def decisions(self,weights,indices,delay):
        result=super().decisions(weights,indices,delay)
        for targets in result.values():
            for target in targets:
                target.sleeve='p421-alpha33-pilot'
                target.rationale='Frozen P4.21 constituent-rank feasibility experiment'
        return result


def aggregate(holdings, ranks, min_value=.95, min_names=.70):
    total=sum(r['value_usd'] for r in holdings)
    observed=[r for r in holdings if r['permno'] in ranks]
    covered=sum(r['value_usd'] for r in observed)
    value_fraction=covered/total if total else 0.
    name_fraction=len(observed)/len(holdings) if holdings else 0.
    ok=value_fraction>=min_value and name_fraction>=min_names
    score=sum(r['value_usd']*ranks[r['permno']] for r in observed)/covered if ok and covered else np.nan
    return score,dict(value_fraction=value_fraction,name_fraction=name_fraction,
        observed=len(observed),total=len(holdings),eligible=ok)


def prepare():
    p=s.protocol()
    if (s.OUT/'input-manifest.json').exists():
        raise FileExistsError('Backtest inputs already frozen')
    pub=s.read(s.OUT/'publication.json')
    store=AnalyticsStore.from_settings(AppSettings())
    records=store.pinned_rows('observations',pub['source_id'],pub['version'],limit=300000)
    hashes={r['point_key']:sha256(r['payload'].encode()).hexdigest() for r in records}
    if len(records)!=pub['rows'] or sha256(encode(hashes).encode()).hexdigest()!=pub['row_payload_root']:
        raise ValueError('Published projection changed')
    holdings,stock=defaultdict(list),defaultdict(dict)
    for row in records:
        r=json.loads(row['payload'])
        if row['family']=='p421_public_holding':
            holdings[r['fund']].append(r)
        elif row['family']=='p421_audited_price':
            stock[r['date']][r['permno']]=r['adjusted_open']/r['adjusted_close']-1
    old=s.read(s.ROOT/'research/alpha101-net-20261031-v1/protocol.json')
    candidate_path='var/research/alpha101-net-20261031-v1/candidates.json'
    candidates=s.read(s.checked(s.ROOT/candidate_path,old['artifacts'][candidate_path]))
    prior_unsupported=sorted({r['symbol'] for r in candidates}-set(p['full_candidate_pool']))
    candidates=[r for r in candidates if r['symbol'] in p['full_candidate_pool']]
    if {r['symbol'] for r in candidates}!=set(p['full_candidate_pool']):
        raise ValueError('Candidate pool mismatch')
    reader=GovernedInputs(Path(p['price_pin']['root']),p['price_pin']['batch'])
    pool=load_published_pool(reader,candidates,through=s.END,start='2023-01-03')
    bench=load_published_pool(reader,[dict(symbol='URTH',requires_recorder=False)],through=s.END,start=pool['common_start'])
    days,symbols=pool['calendar'],sorted(pool['bars'])
    a={f:np.array([[float(pool['bars'][symbol][i][f]) for symbol in symbols] for i in range(len(days))])
        for f in ('open','high','low','close')}
    for f in ('close','volume'):
        a['raw_'+f]=np.array([[float(pool['raw_bars'][symbol][i][f]) for symbol in symbols] for i in range(len(days))])
    a.update(symbols=np.array(symbols),days=np.array(days),
        urth_open=np.array([float(r['open']) for r in bench['bars']['URTH']]),
        urth_close=np.array([float(r['close']) for r in bench['bars']['URTH']]))
    dollars=pd.DataFrame(a['raw_close']*a['raw_volume'])
    median,minimum=dollars.rolling(63).median().to_numpy(),dollars.rolling(63).min().to_numpy()
    meta={c['symbol']:c for c in candidates}
    admitted=np.zeros_like(a['close'],bool)
    for t in range(252,len(days)):
        groups=defaultdict(list)
        for j,symbol in enumerate(symbols):
            if symbol!='BIL' and median[t,j]>=5e6 and minimum[t,j]>=5e5:
                groups[meta[symbol]['duplicate_review_group']].append(j)
        for group in groups.values():
            j=min(group,key=lambda k:(-median[t,k],meta[symbols[k]]['candidate_id']))
            admitted[t,j]=True
    volatility=pd.DataFrame(a['close']).pct_change(fill_method=None).rolling(63).std().to_numpy()
    momentum=pd.DataFrame(a['close']).pct_change(126,fill_method=None).to_numpy()
    scores=np.full_like(a['close'],np.nan)
    coverage=[]
    for t,day in enumerate(days):
        if day<p['signal_start']:
            continue
        ranks=pd.Series(stock.get(day,{}),dtype=float).rank(method='average',pct=True).to_dict()
        for j,symbol in enumerate(symbols):
            score,cov=aggregate(holdings.get(symbol,[]),ranks,p['coverage']['min_equity_value'],p['coverage']['min_equity_names'])
            scores[t,j]=score
            coverage.append(dict(date=day,symbol=symbol,**cov))
    eligible=admitted & np.isfinite(scores)
    a['admitted'],a['eligible']=admitted,eligible
    sig={}
    for name,values in [('constituent33',scores),('etf33',a['open']/a['close']-1),('momentum126',momentum),('unranked',np.ones_like(scores))]:
        w=np.zeros((len(days),len(symbols)+1))
        for t in range(len(days)):
            w[t,:-1]=portfolio(values[t],volatility[t],eligible[t],symbols,unranked=name=='unranked')
        sig[name]=w
    first=days.index(s.START)-1
    schedules,adoptions={},{}
    for name,w in sig.items():
        tape={days[t+1]:dict(signal_session=days[t+1],known_through=days[t],
            targets=[dict(symbol=symbol,target_weight=round(float(weight),12))
                     for symbol,weight in zip(symbols+['URTH'],w[t],strict=True) if weight>0])
            for t in range(first,len(days)-1)}
        monthly=[day for i,day in enumerate(tape) if i==0 or day[:7]!=list(tape)[i-1][:7]]
        for policy in p['policies']:
            selected,ledger=adoption_schedule(tape,monthly,policy)
            key=name+'-'+policy
            schedules[key+'_weights']=w
            schedules[key+'_indices']=np.array([days.index(d)-1 for d in selected],int)
            adoptions[key]=ledger
    for name,mask in [('covered-buyhold',eligible[first]),('full-pool-buyhold',admitted[first])]:
        w=np.zeros((len(days),len(symbols)+1))
        if not mask.any():
            raise ValueError('No initial covered pool')
        w[:,np.flatnonzero(mask)]=.98/mask.sum()
        schedules[name+'_weights'],schedules[name+'_indices']=w,np.array([first])
    for name in ('BIL','URTH','cash'):
        w=np.zeros((len(days),len(symbols)+1))
        if name!='cash':
            w[:,(symbols+['URTH']).index(name)]=.98
        schedules[name+'_weights'],schedules[name+'_indices']=w,np.array([first])
    frpath='var/research/alpha101-net-20261031-v1/fr25-decisions.json'
    fr=s.read(s.checked(s.ROOT/frpath,old['artifacts'][frpath]))
    w=np.zeros((len(days),len(symbols)+1))
    indices=[]
    for day,row in sorted(fr.items()):
        if s.START<=day<=s.END:
            if row['known_through']>=day or day not in days:
                raise ValueError('Incumbent timing invalid')
            t=days.index(day)-1
            for target in row['targets']:
                w[t,(symbols+['URTH']).index(target['symbol'])]=float(target['target_weight'])
            indices.append(t)
    if not indices or indices[0]!=first:
        raise ValueError('Incumbent lacks initial monthly target')
    schedules['FR25-reference_weights'],schedules['FR25-reference_indices']=w,np.array(indices)
    recipe=dict(id='p421_alpha33_pilot_v1',universeKey='published_full_pool',universeMembers=[
        Instrument(symbol=x,name=x,asset_class='etf',exchange='NYSE',quote_currency='USD',country='US',sector='research').model_dump(mode='json') for x in symbols+['URTH']])
    np.savez_compressed(s.WORK/'inputs.npz',**a)
    np.savez_compressed(s.WORK/'signals.npz',constituent_scores=scores,volatility=volatility,**sig)
    np.savez_compressed(s.WORK/'schedules.npz',**schedules)
    s.write(s.WORK/'recipe.json',recipe)
    gzwrite(s.WORK/'adoptions.json.gz',adoptions)
    gzwrite(s.WORK/'coverage.json.gz',coverage)
    summary={symbol:dict(eligible_sessions=sum(r['eligible'] for r in coverage if r['symbol']==symbol),
        minimum_value_coverage=min((r['value_fraction'] for r in coverage if r['symbol']==symbol),default=0),
        initial_value_coverage=next((r['value_fraction'] for r in coverage if r['symbol']==symbol),0)) for symbol in symbols}
    s.write(s.OUT/'coverage.json',dict(funds=summary,full_candidate_count=len(candidates),supported_price_count=len(symbols),
        older_candidate_file_excluded_outside_supported_pool=prior_unsupported,
        price_exclusions=pool['exclusions'],initial_eligible=np.array(symbols)[eligible[first]].tolist(),
        minimum_daily_eligible=int(eligible[first:-1].sum(axis=1).min()),maximum_daily_eligible=int(eligible[first:-1].sum(axis=1).max()),
        eligibility_changes=[dict(date=days[t],eligible=np.array(symbols)[eligible[t]].tolist()) for t in range(first+1,len(days)-1) if not np.array_equal(eligible[t],eligible[t-1])]))
    files=[s.WORK/name for name in ('inputs.npz','signals.npz','schedules.npz','recipe.json','adoptions.json.gz','coverage.json.gz')]
    code=[Path(__file__),s.ROOT/'scripts/research_alpha101_net.py',s.ROOT/'scripts/run_range_breakout.py',s.ROOT/'scripts/research_cash_relative_retest.py',
        *sorted((s.ROOT/'src/systematic_trading/backtest').glob('*.py')),
        *[s.ROOT/('src/systematic_trading/research/'+x+'.py') for x in ('target_change_rebalance','etf_expansion','governed_inputs')]]
    s.write(s.OUT/'input-manifest.json',dict(protocol_sha256=s.digest(s.OUT/'protocol.json'),publication_sha256=s.digest(s.OUT/'publication.json'),
        price_files=reader.used,files={str(f.relative_to(s.ROOT)).replace('\\','/'):s.digest(f) for f in files+code},
        inherited_inputs={candidate_path:old['artifacts'][candidate_path],frpath:old['artifacts'][frpath]},
        frozen_before_performance=True))
    print('Inputs frozen; initial eligible',np.array(symbols)[eligible[first]].tolist(),'minimum daily',int(eligible[first:-1].sum(axis=1).min()),flush=True)


def inputs():
    s.protocol()
    m=s.read(s.OUT/'input-manifest.json')
    for name,h in m['files'].items():
        s.checked(s.ROOT/name,h)
    s.checked(s.OUT/'protocol.json',m['protocol_sha256'])
    s.checked(s.OUT/'publication.json',m['publication_sha256'])
    a=dict(np.load(s.WORK/'inputs.npz'))
    schedules=dict(np.load(s.WORK/'schedules.npz'))
    recipe=s.read(s.WORK/'recipe.json')
    return a,schedules,recipe,PilotReplay(a,recipe,s.START)


def evaluate():
    if (s.OUT/'results.json').exists():
        raise FileExistsError('Results already sealed')
    p=s.protocol()
    a,schedules,recipe,engine=inputs()
    (s.WORK/'paths').mkdir(exist_ok=True)
    rows=[]
    windows=dict(full=(s.START,s.END),march=(s.START,'2025-03-31'),april=('2025-04-01','2025-04-30'),may=('2025-05-01',s.END))
    arms=sorted(k[:-8] for k in schedules if k.endswith('_weights'))
    for arm in arms:
        for cost in p['costs_bps']:
            for delay in p['delays']:
                compact,economic,fills=engine.run(schedules[arm+'_weights'],schedules[arm+'_indices'],cost,delay,detailed=True)
                key=f'{arm}_c{cost}d{delay}'
                np.savez_compressed(s.WORK/'paths'/f'{key}.npz',**compact)
                if cost==5 and delay==0 or (arm=='constituent33-0.40' and cost==20 and delay==1):
                    gzwrite(s.WORK/'paths'/f'{key}.json.gz',economic)
                metrics={name:metric(engine.day_strings,compact['nav'],start,end,fees=compact['fees'],turnover=compact['turnover'],exposure=compact['exposure']) for name,(start,end) in windows.items()}
                rows.append(dict(arm=arm,cost_bps=cost,delay=delay,fills=fills,windows=metrics))
        print('Replayed',arm,flush=True)
    s.write(s.OUT/'results.json',clean(dict(protocol_sha256=s.digest(s.OUT/'protocol.json'),input_manifest_sha256=s.digest(s.OUT/'input-manifest.json'),
        cases=rows,selection=None,primary='constituent33-monthly',status='development_feasibility_evidence_not_promotion')))
    print('Completed',len(rows),'new backtests',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','evaluate'])
    args=parser.parse_args()
    (prepare if args.stage=='prepare' else evaluate)()
