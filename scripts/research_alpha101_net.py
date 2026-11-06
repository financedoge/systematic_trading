"""Finite full-pool Alpha101 retest. No data acquisition or operational writes."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from research_cash_relative_retest import clean, digest, gzwrite, metric, passes, read, verify, write
from run_range_breakout import Replay
from systematic_trading.research.alpha101 import FORMULAS, History, value
from systematic_trading.research.target_change_rebalance import adoption_schedule

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'research/alpha101-net-20261031-v1'
WORK = REPO/'var/research/alpha101-net-20261031-v1'
START, END = '2021-01-04', '2026-10-30'
ALPHAS = ('24', '26', '46', '49', '53', '54')
POLICIES = ('monthly', '0.10', '0.40', '0.80')
WINDOWS = {'calibration': (START, '2024-12-31'), 'later': ('2025-01-01', END),
    'full': (START, END), **{str(y): (f'{y}-01-01', min(END, f'{y}-12-31')) for y in range(2021, 2027)}}


def portfolio(scores, volatility, eligible, symbols, *, unranked=False):
    """Original top-six score order, 63-return inverse vol; explicit final cap."""
    valid = eligible & np.isfinite(scores) & np.isfinite(volatility) & (volatility > 0)
    ix = np.flatnonzero(valid)
    out = np.zeros(len(scores))
    if len(ix) < 6 or (not unranked and len(set(np.round(scores[ix], 12))) < 2):
        return out
    chosen = ix if unranked else sorted(ix, key=lambda j: (-scores[j], symbols[j]))[:6]
    inv = 1/volatility[chosen]
    out[chosen] = np.minimum(.45, .98*inv/inv.sum())
    return out


def alpha_column(payload):
    symbol, days, fields = payload
    result = np.full((len(days), len(ALPHAS)), np.nan)
    for i in range(252, len(days)):
        for j, name in enumerate(ALPHAS):
            # Minimum complete suffix avoids recomputing irrelevant rolling prefixes.
            lookback = {'24': 201, '26': 12, '46': 21, '49': 21, '53': 10, '54': 2}[name]
            h = History(symbol, str(days[i]), **{k: v[max(0, i-lookback+1):i+1] for k,v in fields.items()})
            x = value(name, h)
            if x is not None:
                result[i,j] = x
    return result


def select(rows):
    primary = {r['arm']: r['windows']['calibration'] for r in rows if r['cost_bp']==5 and r['delay']==0}
    per_alpha = {a: sorted((f'alpha{a}-{p}' for p in POLICIES), key=lambda k: (-primary[k]['sharpe'], k))[0] for a in ALPHAS}
    selected = sorted(per_alpha.values(), key=lambda k: (-primary[k]['sharpe'], k))[0]
    policy = selected.split('-')[1]
    return dict(selected=selected, per_alpha=per_alpha, window='calibration',
        eligible_vs_controls=passes(primary[selected],primary['momentum-'+policy]) and passes(primary[selected],primary['unranked-'+policy]),
        rule='Highest training 5bp/delay0 net Sharpe; deterministic arm-name tie. Selection is diagnostic, not acceptance. No later-period selection.')


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
    admitted[:,symbols.index('BIL')]=False
    a['admitted']=admitted
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(WORK/'inputs.npz',**a)
    recipe=dict(id='alpha101_net_research_v1',universeKey='published_full_pool',universeMembers=[
        Instrument(symbol=s,name=s,asset_class='etf',exchange='NYSE',quote_currency='USD',country='US',sector='research').model_dump(mode='json') for s in symbols+['URTH']])
    write(WORK/'recipe.json',recipe);write(WORK/'candidates.json',candidates)
    # Read current app-owned incumbent decisions, then replay these on study quotes.
    doc=requests.get('http://127.0.0.1:8000/api/v1/strategies/research_fr25_14_v1',timeout=30).json()
    root=REPO/doc['artifact_path'];bundle=root/'bundles/research_fr25_14_v1'
    verify(bundle,'manifest.json')
    decisions=read(bundle/'decisions.json')
    write(WORK/'fr25-decisions.json',decisions)
    write(OUT/'incumbent-provenance.json',dict(artifact_path=str(root),bundle_sha256=digest(bundle/'manifest.json'),
        input_provenance=doc['input_provenance'],definition=doc['strategy_definition'],
        note='Frozen current app decisions; same study price/cost/whole-unit replay, but incumbent signal inputs/model warmup differ. Not a matched alpha ablation.'))
    paper=REPO/'research/references/alpha101/101_formulaic_alphas.pdf'
    if digest(paper)!='1f9c21afe32dcb3ee77b31548acdaea00451fbfa1c0ee10c907867bcc736fce9':
        raise ValueError('Paper hash mismatch')
    code=[Path(__file__),REPO/'scripts/research_cash_relative_retest.py',REPO/'scripts/run_range_breakout.py',
          REPO/'scripts/run_class_volatility_screen.py',*sorted((REPO/'src/systematic_trading/backtest').glob('*.py')),
          *[REPO/('src/systematic_trading/research/'+f+'.py') for f in ('alpha101','target_change_rebalance','etf_expansion','candidate_pool','etf_admission','governed_inputs')]]
    p=dict(version='alpha101-net-v1',registered_at=datetime.now(timezone.utc).isoformat(),price_pin=pin,
        verified_files=reader.used, candidate_count=len(candidates),supported_count=len(symbols),symbols=symbols,
        exclusions=pool['exclusions'],common_start=pool['common_start'],windows=WINDOWS,
        alphas=list(ALPHAS),formulas={k:FORMULAS[k] for k in ALPHAS},paper_sha256=digest(paper),
        policies=list(POLICIES),frictions=[[c,d] for c in (5,10,20) for d in (0,1)],
        hypothesis='The six signals excluded only by the retired annual-cost proxy may deliver useful realized net performance. Each is standalone; no FR25 tilt blend.',
        construction='All supported candidates evaluated daily. Prior 253 observations and 63-session raw-dollar liquidity: median>=5m/min>=0.5m, one duplicate representative. Exclude BIL from risky ranks. Highest six finite alpha scores, alphabetic tie break inherited from corrected screen; all-equal or <6 scores => cash. 63 daily-return sample volatility, weights proportional inverse volatility, 98% budget, final per-name45% cap with excess cash. No alpha sign gate, stops, leverage or hidden FR25 overlay.',
        controls='126-session return rank with same six-name/inverse-vol/cap rule; unranked inverse volatility with identical eligibility and policy; cash; BIL/URTH/full-risky-pool initial equal-weight buy-and-hold; frozen current FR25 decisions repriced on study inputs.',
        timing='Daily completed-close theoretical target. Monthly first-session next-open control; thresholds strict L1 >0.10/0.40/0.80 versus last logically adopted target including cash, plus monthly adoption. Delay0 is next open; delay1 is one further session, including for original delay-0 paper formulas53/54. Sizing at execution-prior-close. Shared whole adjusted-unit USD1m accounting. 5/10/20bp per actual traded notional, no terminal liquidation.',
        selection='2021-2024 only: highest primary5bp/delay0 net Sharpe per alpha and globally, arm-name tie. Compare selected against matching momentum and unranked controls with strict higher Sharpe, CAGR loss<=0.5pp, DD worsening<=2pp. No cost/IC veto. No later rescue. Annual training stability reported; fixed selected policy carried into2025-2026.',
        diagnostics='Primary21-session forward next-open-to-open rank IC; auxiliary1/5/10, no horizon selection. Paired circular21-session bootstrap4000 draws seed20261031, family-adjusted95% intervals across24 alpha-policy contrasts against matched momentum; approximate dependence/repeated-use caveat.',
        weakest='Lowest actual net contribution/opening portfolio NAV, selected policy5bp/delay0, each chronological era, excluding BIL/URTH/cash; chosen explicitly for changing portfolio allocations. Also show all individual buy-and-hold returns. Inspect prices/raw volume/theoretical-adopted-held states/fills/no-protection/FIFO outcomes.',
        limitations=['Reconstructed audited revised histories; historical dissemination and cohort/membership availability uncertified; retrospective development evidence, not prospective OOS.',
            'Adjusted price terms and raw share volume; cross-ETF absolute price scales affect original formulas24/46/49. Tied scores use inherited ticker order, not independent evidence.',
            'Dollar volume does not establish spreads/impact; whole adjusted units are synthetic, not broker raw-share execution. Zero cash interest, no taxes/FX/spreads/impact.',
            '46 and49 are related formulas;24policy trials are correlated, repeatedly inspected history. No promotion, monitoring, funding or operational changes.'],
        code={f.relative_to(REPO).as_posix():digest(f) for f in code},
        artifacts={f.relative_to(REPO).as_posix():digest(f) for f in (WORK/'inputs.npz',WORK/'recipe.json',WORK/'candidates.json',WORK/'fr25-decisions.json',OUT/'incumbent-provenance.json')})
    write(OUT/'protocol.json',p)
    print('Frozen',digest(OUT/'protocol.json'),'supported',len(symbols),'exclusions',p['exclusions'],flush=True)


def read_json_text(text):
    import json
    return json.loads(text)


def validate():
    p=read(OUT/'protocol.json')
    for relative,expected in {**p['code'],**p['artifacts']}.items():
        if digest(REPO/relative)!=expected:
            raise ValueError('Frozen input/source changed: '+relative)
    return p


def signals(workers=4):
    validate()
    if (OUT/'signal-manifest.json').exists():
        raise FileExistsError('Signals already frozen')
    a=dict(np.load(WORK/'inputs.npz'));symbols=a['symbols'].tolist();days=a['days'];n=len(days)
    jobs=[(s,days,dict(open=a['open'][:,j],high=a['high'][:,j],low=a['low'][:,j],close=a['close'][:,j],
        volume=a['raw_volume'][:,j],raw_close=a['raw_close'][:,j])) for j,s in enumerate(symbols)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        cube=np.stack(list(pool.map(alpha_column,jobs)),axis=1)
    returns=pd.DataFrame(a['close']).pct_change(fill_method=None)
    vol=returns.rolling(63).std(ddof=1).to_numpy()
    momentum=np.full_like(a['close'],np.nan);momentum[126:]=a['close'][126:]/a['close'][:-126]-1
    scores={**{'alpha'+x:cube[:,:,j] for j,x in enumerate(ALPHAS)},'momentum':momentum,'unranked':np.ones_like(momentum)}
    schedules={}; counts={};first=int(np.searchsorted(days,START))-1
    monthly=[str(days[t+1]) for t in range(first,n-1) if t==first or days[t][:7]!=days[t+1][:7]]
    for arm,score in scores.items():
        w=np.zeros((n,len(symbols)+1))
        for t in range(first,n):
            w[t,:-1]=portfolio(score[t],vol[t],a['admitted'][t],symbols,unranked=arm=='unranked')
        tape={str(days[t+1]):dict(signal_session=str(days[t+1]),known_through=str(days[t]),
            targets=[dict(symbol=s,target_weight=str(round(float(x),12))) for s,x in zip(symbols,w[t,:-1],strict=True) if x>0]) for t in range(first,n-1)}
        for policy in POLICIES:
            adopted,ledger=adoption_schedule(tape,monthly,policy)
            key=arm+'-'+policy
            ix=np.array([int(np.searchsorted(days,d))-1 for d in adopted],int)
            schedules[key+'_weights']=w;schedules[key+'_indices']=ix
            counts[key]=dict(adoptions=len(ix),threshold_events=sum('threshold' in r['reasons'] for r in ledger),
                empty_targets=int(np.sum(w[first:-1].sum(axis=1)==0)))
    fr=np.zeros((n,len(symbols)+1));indices=[]
    for day,row in read(WORK/'fr25-decisions.json').items():
        if START<=day<=END:
            t=int(np.searchsorted(days,day))-1
            if str(days[t])!=row['known_through']:
                raise ValueError('FR25 causal alignment failed')
            for target in row['targets']:
                if target['symbol'] not in symbols:raise ValueError('Unsupported incumbent member')
                fr[t,symbols.index(target['symbol'])]=float(target['target_weight'])
            indices.append(t)
    schedules['FR25_weights']=fr;schedules['FR25_indices']=np.array(indices,int)
    for key in ('cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
        w=np.zeros_like(fr)
        if key=='BIL_buyhold':w[:,symbols.index('BIL')]=1
        if key=='URTH_buyhold':w[:,-1]=1
        if key=='pool_buyhold':
            for j,s in enumerate(symbols):
                if s!='BIL':w[:,j]=1/(len(symbols)-1)
        schedules[key+'_weights']=w;schedules[key+'_indices']=np.array([first])
    np.savez_compressed(WORK/'signals.npz',alpha=cube,volatility=vol,momentum=momentum)
    np.savez_compressed(WORK/'schedules.npz',**schedules)
    write(OUT/'adoptions.json',counts)
    write(OUT/'signal-manifest.json',{f.relative_to(REPO).as_posix():digest(f) for f in (WORK/'signals.npz',WORK/'schedules.npz',OUT/'adoptions.json')})
    print('Frozen signals and schedules',len([k for k in schedules if k.endswith('_weights')]),flush=True)


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
    p=validate()
    for relative,expected in read(OUT/'signal-manifest.json').items():
        assert digest(REPO/relative)==expected
    if (OUT/'results.json').exists():raise FileExistsError('Results already exist')
    for f in ('paths','detail'):(WORK/f).mkdir(exist_ok=True)
    with np.load(WORK/'schedules.npz') as z:arms=sorted(k[:-8] for k in z.files if k.endswith('_weights'))
    with ProcessPoolExecutor(max_workers=workers,initializer=init_worker) as pool:
        rows=list(pool.map(job,[(a,c,d) for a in arms for c,d in p['frictions']]))
    validate();write(OUT/'results.json',clean(rows));write(OUT/'selection.json',select(rows))
    write(OUT/'result-manifest.json',{f.relative_to(REPO).as_posix():digest(f) for f in sorted((WORK/'paths').glob('*'))+sorted((WORK/'detail').glob('*'))})
    print('Completed',len(rows),'cases',read(OUT/'selection.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['prepare','signals','evaluate','verify'])
    parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage=='signals':signals(args.workers)
    elif args.stage=='evaluate':evaluate(args.workers)
    else:validate();print('Frozen code/inputs verified')
