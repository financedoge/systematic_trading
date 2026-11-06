"""Finite expanded FR25 net replay, using app-owned signals and audited publications."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
import time
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import pandas as pd
from research_cash_relative_retest import clean, digest, gzwrite, gzread, metric, passes, read, write
from research_alpha101_net import portfolio
from run_range_breakout import Replay
from systematic_trading.research.target_change_rebalance import adoption_schedule
from systematic_trading.research.strategy_catalog import StrategyDefinition, fr25_definition, m1_14_definition
from systematic_trading.research import instruments_for_definition, instantiate_overlays
REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'research/expanded-fr25-net-20261102-v1'
WORK=REPO/'var/research/expanded-fr25-net-20261102-v1'
START,END='2021-01-04','2026-10-30'
POLICIES=('monthly','0.10','0.40','0.80')
MAIN=('original','expanded','m1')
WINDOWS={'calibration':(START,'2024-12-31'),'later':('2025-01-01',END),'full':(START,END),
         **{str(y):(f'{y}-01-01',min(END,f'{y}-12-31')) for y in range(2021,2027)}}

def read_json_text(text): return json.loads(text)

def definitions(members):
    base=fr25_definition()
    expanded=replace(base,key='expanded_fr25_net_v1',name='Expanded FR25 research',state='research',
        universe_key='frozen_supported_pool',universe_members=tuple(members),
        description='Frozen full supported-pool FR25 research comparison; original overlays, finite admission and timing protocol; no authority.')
    m1=replace(expanded,key='expanded_m1_capped_net_v1',name='Expanded M1 matched control',
        description='Expanded FR25 with only the selector replaced by M1; same final cap and downstream sizing; no authority.',
        overlays=(m1_14_definition().overlays[0],*expanded.overlays[1:]))
    return {'original':base,'expanded':expanded,'m1':m1}

def prepare():
    if (OUT/'protocol.json').exists():
        raise FileExistsError('Preserve frozen protocol')
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.etf_expansion import load_published_pool, admission_for_day
    from systematic_trading.domain.market import Instrument
    pub = AnalyticsStore.from_settings(AppSettings()).latest('governance/catalog')
    pin = dict(root=read_json_text(pub['provenance'])['root'], batch=pub['version'])
    reader = GovernedInputs(Path(pin['root']), pin['batch'])
    original = read(REPO/'var/research/etf-expansion-20261014-v1/candidates.json')
    pack = read(REPO/'src/systematic_trading/research/broadtrend_models_v1.json')
    config = read(REPO/'config/research-etf-recorders.json')['funds']
    inventory = read(REPO/'research/etf-universe-inventory-2026-10-13/inventory.json')['candidates']
    candidates = {c['symbol']: c for c in original}
    for fund in config:
        symbol=fund['symbol']
        if symbol not in candidates:
            matches=[c for c in inventory if c['symbol']==symbol]
            candidates[symbol]=dict(matches[0] if matches else {}, **fund)
    for symbol, m in pack['models'].items():
        if symbol not in candidates:
            candidates[symbol]=dict(next(c for c in inventory if c['symbol']==symbol), isin=m['isin'], requires_recorder=bool(m['isin']))
    for s,c in candidates.items():
        c.setdefault('candidate_id',s); c.setdefault('duplicate_review_group',s)
    candidates=list(candidates.values())
    # Existing admitted support origins, chosen before any return results.
    support_start=max(m['history_start'] for m in pack['models'].values())
    pool=load_published_pool(reader,candidates,through=END,start=support_start)
    bench=load_published_pool(reader,[dict(symbol='URTH',requires_recorder=False)],through=END,start=pool['common_start'])
    symbols,days=sorted(pool['bars']),pool['calendar']
    a={field:np.array([[float(pool['bars'][s][i][field]) for s in symbols] for i in range(len(days))])
       for field in ('open','high','low','close')}
    for field in ('close','volume'):
        a['raw_'+field]=np.array([[float(pool['raw_bars'][s][i][field]) for s in symbols] for i in range(len(days))])
    a.update(symbols=np.array(symbols),days=np.array(days),
        urth_open=np.array([float(r['open']) for r in bench['bars']['URTH']]),
        urth_close=np.array([float(r['close']) for r in bench['bars']['URTH']]))
    dollars=pd.DataFrame(a['raw_close']*a['raw_volume'])
    med,minimum=dollars.rolling(63).median().to_numpy(),dollars.rolling(63).min().to_numpy()
    metadata={c['symbol']:c for c in candidates};admitted=np.zeros_like(a['close'],bool)
    for t in range(252,len(days)):
        groups={}
        for j,s in enumerate(symbols):
            if med[t,j]>=5e6 and minimum[t,j]>=5e5:
                groups.setdefault(metadata[s]['duplicate_review_group'],[]).append(j)
        for group in groups.values():
            j=min(group,key=lambda k:(-med[t,k],metadata[symbols[k]]['candidate_id']));admitted[t,j]=True
    for t in (252,503,len(days)-2):
        assert sorted(np.array(symbols)[admitted[t]].tolist())==admission_for_day(pool['records'],candidates,days[t+1])['admitted']
    a['admitted']=admitted
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(WORK/'inputs.npz',**a)
    recipe=dict(id='expanded_fr25_net_v1',universeKey='published_full_pool',universeMembers=[
        Instrument(symbol=s,name=s,asset_class='etf',exchange='NYSE',quote_currency='USD',country='US',sector='research').model_dump(mode='json') for s in symbols+['URTH']])
    write(WORK/'recipe.json',recipe);write(WORK/'candidates.json',candidates)
    gzwrite(WORK/'pool.json.gz',dict(bars=pool['bars'],raw_bars=pool['raw_bars'],provenance=pool['provenance']))
    from systematic_trading.research.fr25_tracking import economic_inputs
    from systematic_trading.research.usd_data import load_usd
    analytics=AnalyticsStore.from_settings(AppSettings())
    financial=economic_inputs(analytics,pool['bars'],pool['common_start'])
    usd,usd_receipt=load_usd(analytics)
    write(WORK/'financial-inputs.json',financial);write(WORK/'usd.json',usd)
    write(OUT/'input-verification.json',dict(price_pin=pin,verified_files=reader.used,
        usd=usd_receipt,financial=financial,exclusions=pool['exclusions'],common_start=pool['common_start']))
    defs=definitions(recipe['universeMembers'][:-1])
    write(OUT/'definitions.json',{k:d.to_dict() for k,d in defs.items()})
    code=[Path(__file__),*[REPO/'scripts'/s for s in ('research_alpha101_net.py','research_cash_relative_retest.py',
        'run_range_breakout.py','run_class_volatility_screen.py')],
        *[f for f in (REPO/'src/systematic_trading').rglob('*') if f.suffix in ('.py','.json')]]
    files=[WORK/n for n in ('inputs.npz','recipe.json','candidates.json','pool.json.gz','financial-inputs.json','usd.json')]
    files += [OUT/'definitions.json',OUT/'input-verification.json']
    p=dict(version='expanded-fr25-net-v1',registered_at=datetime.now(timezone.utc).isoformat(),
        price_pin=pin,symbols=symbols,supported_count=len(symbols),candidate_count=len(candidates),
        exclusions=pool['exclusions'],common_start=pool['common_start'],windows=WINDOWS,
        policies=list(POLICIES),frictions=[[c,d] for c in (5,10,20) for d in (0,1)],
        hypothesis='Expanding the FR25 candidate universe improves realized net performance versus original14 and expanded M1; replay without retired cost/IC exclusion.',
        construction='Original14 and full supported pool share common warmup and are separately refitted. FR25 exact 75% M1/25% financial rank, positive126 gate, top6/minimum4, defensive IEF/TLT/GLD cash fallback; same causal rolling XGBoost sizing, relative/adaptive trend, audited raw activity, USD ridge and final45% cap. Expanded M1 replaces only the financial selector; cap/downstream layers unchanged. Expanded BIL remains an eligible candidate as in original expansion; it is excluded only from weakest-risky diagnostics. Admission:253 observations, prior63 raw-dollar median>=5m/min>=0.5m, one duplicate representative. Models/ranks use full declared pool.',
        controls='Original14 FR25; expanded M1 with identical downstream layers; simple126 momentum top6 inverse63-vol/98% budget/45% cap and unranked inverse-vol, both excluding BIL as risky rank; cash, BIL, URTH, risky-pool equal-weight buyhold.',
        timing='Daily prior-close theoretical targets; monthly first-session control and strict L1>0.10/0.40/0.80 versus last adopted target including cash, plus monthly adoption. Financial forecast held from causal monthly decision. USD exact daily snapshot when published, otherwise original previous-month snapshot with <=35-day carry; original timestamps retained. Monthly fitting unchanged. Delay0 next open, delay1 one further session. Shared USD1m whole adjusted-unit accounting, sizing prior execution close, 5/10/20bp per traded notional; no terminal exit.',
        selection='Expanded FR25 highest calibration2021-2024 primary5bp/delay0 net Sharpe, alphabetical policy tie. Carry fixed into later2025-2026; compare same-policy original14, M1, simple momentum and unranked. Strict Sharpe improvement, CAGR sacrifice<=0.5pp and DD worsening<=2pp; no later rescue or cost/IC veto. Report independently training-selected controls as diagnostics.',
        uncertainty='Paired circular21-session bootstrap4000 draws seed20261102; ordinary and Bonferroni family95% intervals for4policies x4controls=16 contrasts. Approximate dependent/reused-sample diagnostics, not formal adaptive-holdout guarantees.',
        decay='FR25 daily combined selection-score rank IC at1/5/10/21/63 next-open horizons, endpoints confined to each era;21-session block-bootstrap uncertainty1000 draws. No horizon selection. Nonmonotone/unstable curves imply unidentifiable half-life; annual net contrasts are primary stability evidence.',
        weakest='Lowest actual net contribution divided by era-opening portfolio NAV for selected expanded FR255bp/delay0 in each era, excluding BIL/URTH/cash. Also show every ETF buyhold return. Dated adjusted price/raw volume, theoretical/adopted/held weights, states, fills, protection and FIFO outcomes.',
        limitations=['Reconstructed audited revised price history and current candidate cohort; historical publication/membership availability uncertified. Both eras previously inspected; retrospective development evidence, not untouched OOS.',
            'Archived financial/USD vintages have original-vintage semantics but historical first dissemination not fully certified. Financial daily forecasts are carried monthly; USD carry retains source date. Missing financial models abstain to M1. No online acquisition.',
            'Raw volume supports liquidity/activity; adjusted prices/whole adjusted units are synthetic. Zero cash interest, no FX, taxes, measured spreads or impact. Liquidity participation is diagnostic.',
            'One earlier expansion screen plus many prior strategy searches;16 declared contrasts do not account for the entire historical search. New prospective evidence would require a frozen future trial.',
            'No monitoring, promotion, allocation or broker authority; finite research only.'],
        code={f.relative_to(REPO).as_posix():digest(f) for f in code},
        artifacts={f.relative_to(REPO).as_posix():digest(f) for f in files})
    write(OUT/'protocol.json',p)
    print('Frozen protocol',digest(OUT/'protocol.json'),'supported',len(symbols),'exclusions',p['exclusions'],flush=True)


def validate():
    p=read(OUT/'protocol.json')
    for relative,expected in {**p['code'],**p['artifacts']}.items():
        if digest(REPO/relative)!=expected:raise ValueError('Frozen input/source changed: '+relative)
    return p


def models(workers=4):
    p=validate()
    from systematic_trading.config import AppSettings
    from systematic_trading.research.rolling_tracking import prepare_model_schedule
    from systematic_trading.research.fr25_tracking import prepare_schedule
    from systematic_trading.research.usd_tracking import prepare_usd_schedule
    data=gzread(WORK/'pool.json.gz')
    for arm in ('original','expanded'):
        dest=WORK/'models'/arm
        if (dest/'complete.json').exists():
            check_manifest(dest/'complete.json');continue
        definition=StrategyDefinition.from_dict(read(OUT/'definitions.json')[arm])
        bars={s:data['bars'][s] for s in instruments_for_definition(definition)}
        # Isolate finite research model artifacts from monitored-strategy cache.
        settings=AppSettings().model_copy(update={'data_dir':WORK/'model-cache'/arm})
        rolling,receipt=prepare_model_schedule(settings,dict(latest_bars=bars,provenance=data['provenance']),
            definition,START,p['code'],max_workers=workers)
        print('Rolling models prepared',arm,flush=True)
        financial=prepare_schedule(read(WORK/'financial-inputs.json'),bars,max_workers=workers)
        usd=prepare_usd_schedule(bars,read(WORK/'usd.json'))
        for name,value in dict(rolling=rolling,receipt=receipt,financial=financial,usd=usd).items():
            write(dest/(name+'.json'),value)
        write(dest/'complete.json',{f.relative_to(REPO).as_posix():digest(f) for f in dest.glob('*.json')})
        print('Models complete',arm,flush=True)
    write(OUT/'model-manifest.json',{f.relative_to(REPO).as_posix():digest(f) for f in (WORK/'models').rglob('*.json')})


def check_manifest(path):
    for relative,expected in read(path).items():
        if digest(REPO/relative)!=expected:raise ValueError('Changed artifact: '+relative)


def target_init(arm):
    global DATA,DEFINITION,TYPED,RAW,MODEL,ADMISSION,DAYS
    from systematic_trading.domain.market import PriceBar
    DATA=gzread(WORK/'pool.json.gz')
    DEFINITION=StrategyDefinition.from_dict(read(OUT/'definitions.json')[arm])
    members=instruments_for_definition(DEFINITION)
    TYPED={s:[PriceBar.model_validate(r) for r in DATA['bars'][s]] for s in members}
    RAW={s:[PriceBar.model_validate(r) for r in DATA['raw_bars'][s]] for s in members}
    MODEL={k:read(WORK/'models'/('original' if arm=='original' else 'expanded')/(k+'.json')) for k in ('rolling','financial','usd')}
    a=dict(np.load(WORK/'inputs.npz'));DAYS=a['days'].tolist()
    ADMISSION=None if arm=='original' else {d:frozenset(a['symbols'][a['admitted'][i-1]]) for i,d in enumerate(DAYS) if i}


def target_job(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.rolling_tracking import select_rolling_model
    from systematic_trading.research.candidate_pool import CandidatePool
    i=DAYS.index(day);as_of=date.fromisoformat(day)
    history={s:b[max(0,i-500):i] for s,b in TYPED.items()}
    overlays=list(instantiate_overlays(DEFINITION));selector=None
    for j,(spec,o) in enumerate(zip(DEFINITION.overlays,overlays,strict=True)):
        if spec.kind=='asset_pool_filter':o=CandidatePool(o,'M1');overlays[j]=o
        if spec.kind in ('asset_pool_filter','financial_rank_selection'):
            selector=o
            if ADMISSION is not None:o.admitted_symbols=ADMISSION[day]
        if spec.kind in ('usd_ridge','financial_rank_selection'):o.allow_monthly_fallback=True
        if spec.kind=='rolling_model':o.model=select_rolling_model(MODEL['rolling'],history,as_of)
        elif spec.kind=='usd_ridge':o.schedule=MODEL['usd']
        elif spec.kind=='financial_rank_selection':
            o.schedule=MODEL['financial'];o.rolling_schedule=MODEL['rolling']
        elif spec.kind=='audited_etf_activity':o.raw={s:b[max(0,i-500):i] for s,b in RAW.items()}
    targets=_target_schedule(instruments=instruments_for_definition(DEFINITION),bars_by_symbol=history,
        trade_dates=[as_of],rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),
        cash_reserve_weight=D('.02'),sleeve_name=DEFINITION.sleeve_name,target_overlays=overlays)[as_of]
    if ADMISSION is not None and any(t.target_weight>0 and t.symbol not in ADMISSION[day] for t in targets):
        raise ValueError('Inadmissible downstream target')
    known=DAYS[i-1];cutoff=max(d for d in DAYS[:i] if d[:7]<day[:7])
    financial=MODEL['financial']['models'];source=day if day in financial else next(d for d,r in financial.items() if d<=day and r['known_through']==cutoff)
    usd_dates={r['known_through'] for r in MODEL['usd']['snapshots']}
    return day,dict(signal_session=day,known_through=known,targets=[t.model_dump(mode='json') for t in targets],
        selection=selector.observation,ranks=getattr(selector,'rank_table',None),
        financial_ready=financial[source]['ready'],financial_known_through=financial[source]['known_through'],
        usd_known_through=known if known in usd_dates else cutoff)


def signals(workers=4):
    validate();check_manifest(OUT/'model-manifest.json')
    if (OUT/'signal-manifest.json').exists():raise FileExistsError('Signals already frozen')
    a=dict(np.load(WORK/'inputs.npz'));days=a['days'];symbols=a['symbols'].tolist();n=len(days)
    first=int(np.searchsorted(days,START))-1
    monthly=[str(days[t+1]) for t in range(first,n-1) if t==first or days[t][:7]!=days[t+1][:7]]
    schedules={};counts={};score=np.full_like(a['close'],np.nan)
    for arm in MAIN:
        dest=WORK/'targets'/(arm+'.json.gz')
        if dest.exists():tape=gzread(dest)
        else:
            tape={};begin=time.perf_counter()
            with ProcessPoolExecutor(max_workers=workers,initializer=target_init,initargs=(arm,)) as pool:
                for j,(d,row) in enumerate(pool.map(target_job,days[first+1:].tolist(),chunksize=8),1):
                    tape[d]=row
                    if j%100==0:print('Targets',arm,j,'seconds',round(time.perf_counter()-begin),flush=True)
            gzwrite(dest,tape)
        w=np.zeros((n,len(symbols)+1))
        for day,row in tape.items():
            t=int(np.searchsorted(days,day))-1
            if row['known_through']!=days[t]:raise ValueError('Causal target mismatch')
            for target in row['targets']:w[t,symbols.index(target['symbol'])]=float(target['target_weight'])
            if arm=='expanded':
                for s,r in row['selection']['scores'].items():score[t,symbols.index(s)]=float(r['total'])
        for policy in POLICIES:
            adopted,ledger=adoption_schedule(tape,monthly,policy);key=arm+'-'+policy
            schedules[key+'_weights']=w;schedules[key+'_indices']=np.array([int(np.searchsorted(days,d))-1 for d in adopted],int)
            counts[key]=dict(adoptions=len(adopted),threshold_events=sum('threshold' in r['reasons'] for r in ledger))
    vol=pd.DataFrame(a['close']).pct_change(fill_method=None).rolling(63).std(ddof=1).to_numpy()
    momentum=np.full_like(a['close'],np.nan);momentum[126:]=a['close'][126:]/a['close'][:-126]-1
    eligible=a['admitted'].copy();eligible[:,symbols.index('BIL')]=False
    for arm,values in [('momentum',momentum),('unranked',np.ones_like(momentum))]:
        w=np.zeros((n,len(symbols)+1))
        for t in range(first,n):w[t,:-1]=portfolio(values[t],vol[t],eligible[t],symbols,unranked=arm=='unranked')
        tape={str(days[t+1]):dict(signal_session=str(days[t+1]),known_through=str(days[t]),targets=[dict(symbol=s,target_weight=str(round(float(x),12))) for s,x in zip(symbols,w[t,:-1],strict=True) if x>0]) for t in range(first,n-1)}
        for policy in POLICIES:
            adopted,ledger=adoption_schedule(tape,monthly,policy);key=arm+'-'+policy
            schedules[key+'_weights']=w;schedules[key+'_indices']=np.array([int(np.searchsorted(days,d))-1 for d in adopted],int)
            counts[key]=dict(adoptions=len(adopted),threshold_events=sum('threshold' in r['reasons'] for r in ledger))
    for key in ('cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
        w=np.zeros((n,len(symbols)+1))
        if key=='BIL_buyhold':w[:,symbols.index('BIL')]=1
        if key=='URTH_buyhold':w[:,-1]=1
        if key=='pool_buyhold':
            for j,s in enumerate(symbols):
                if s!='BIL':w[:,j]=1/(len(symbols)-1)
        schedules[key+'_weights']=w;schedules[key+'_indices']=np.array([first])
    np.savez_compressed(WORK/'schedules.npz',**schedules)
    np.savez_compressed(WORK/'signals.npz',score=score,momentum=momentum,volatility=vol)
    write(OUT/'adoptions.json',counts)
    files=[WORK/'schedules.npz',WORK/'signals.npz',OUT/'adoptions.json',*(WORK/'targets').glob('*')]
    write(OUT/'signal-manifest.json',{f.relative_to(REPO).as_posix():digest(f) for f in files})
    print('Signals frozen',len(schedules)//2,'arms',flush=True)


def select(rows):
    primary={r['arm']:r['windows']['calibration'] for r in rows if r['cost_bp']==5 and r['delay']==0}
    chosen={arm:sorted(POLICIES,key=lambda p:(-primary[arm+'-'+p]['sharpe'],p))[0] for arm in (*MAIN,'momentum','unranked')}
    policy=chosen['expanded']
    return dict(selected='expanded-'+policy,per_model=chosen,window='calibration',
        guards={c:passes(primary['expanded-'+policy],primary[c+'-'+policy]) for c in ('original','m1','momentum','unranked')},
        rule='Highest expanded FR25 calibration5bp/delay0 Sharpe, policy-name tie; later data never select policy.')


def init_worker():
    global ENGINE,ARRAYS,SCHEDULES
    ARRAYS=dict(np.load(WORK/'inputs.npz'));SCHEDULES=dict(np.load(WORK/'schedules.npz'))
    ENGINE=Replay(ARRAYS,read(WORK/'recipe.json'),START)


def job(payload):
    arm,cost,delay=payload;key=f'{arm}_c{cost}d{delay}'
    compact,economic,count=ENGINE.run(SCHEDULES[arm+'_weights'],SCHEDULES[arm+'_indices'],cost,delay,detailed=True)
    stats={name:metric(ENGINE.day_strings,compact['nav'],a,b,fees=compact['fees'],turnover=compact['turnover'],exposure=compact['exposure']) for name,(a,b) in WINDOWS.items()}
    np.savez_compressed(WORK/'paths'/f'{key}.npz',**compact)
    if cost==5 and delay==0:gzwrite(WORK/'detail'/f'{key}.json.gz',economic)
    return dict(key=key,arm=arm,cost_bp=cost,delay=delay,fills=count,windows=stats)


def evaluate(workers=4):
    p=validate();check_manifest(OUT/'signal-manifest.json')
    if (OUT/'results.json').exists():raise FileExistsError('Results already frozen')
    for f in ('paths','detail'):(WORK/f).mkdir(exist_ok=True)
    with np.load(WORK/'schedules.npz') as z:arms=sorted(k[:-8] for k in z.files if k.endswith('_weights'))
    with ProcessPoolExecutor(max_workers=workers,initializer=init_worker) as pool:
        rows=list(pool.map(job,[(a,c,d) for a in arms for c,d in p['frictions']]))
    validate();write(OUT/'results.json',clean(rows));write(OUT/'selection.json',select(rows))
    write(OUT/'result-manifest.json',{f.relative_to(REPO).as_posix():digest(f) for f in sorted((WORK/'paths').glob('*'))+sorted((WORK/'detail').glob('*'))})
    print('Completed',len(rows),'cases',read(OUT/'selection.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['prepare','models','signals','evaluate','verify'])
    parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage=='verify':validate();print('Verified')
    else:globals()[args.stage](args.workers)
