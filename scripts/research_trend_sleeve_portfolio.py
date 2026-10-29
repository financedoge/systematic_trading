"""N=15 frozen-policy portfolio experiment; prepare before evaluate."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_entry_value as study
from systematic_trading.research import trend_sleeve_portfolio as model
from systematic_trading.research import fr25_lifecycle_conditional as frozen
OUT=ROOT/'research/trend-sleeve-portfolio-20261029-v1'
WORK=ROOT/'var/research/trend-sleeve-portfolio-20261029-v1'
SYNTH=ROOT/'research/trend-sleeve-synthesis-20261029-v1'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(study.clean(x),indent=2,allow_nan=False)+'\n',encoding='utf-8')
def gzwrite(p,x):p.write_bytes(gzip.compress(json.dumps(study.clean(x),separators=(',',':'),allow_nan=False).encode(),mtime=0))


def protocol():
    return dict(identity=OUT.name,N=15,algorithm='symmetric-trend-sleeve-v1 / entry-value B',
        parent_protocol=digest(study.OUT/'protocol.json'),selected_models=digest(SYNTH/'selected-models.json'),
        data=read(study.OUT/'protocol.json')['published_inputs'],fr25=frozen.verified_input_provenance(),
        chronologies=study.ERAS,frictions=study.FRICTIONS,
        hypothesis='Can monthly ranking of continuously maintained single-ETF strategy returns improve a diversified portfolio versus unranked sleeves and raw ETF momentum?',
        rank='Average four cross-sectional average-tie percentile ranks: compounded net strategy return and arithmetic mean/sample-SD Sharpe over 63 and252 completed sessions. Ties by ticker. BIL excluded. Full aligned252post-fit returns, >=2nonzero returns, positive sample SD both windows. No positive-return gate. If fewer15eligible use all, if zero hold cash.',
        warmup='Each frozen strategy starts flat at its original evaluation anchor. First portfolio decision is first month-end close after252post-fit observations (common to every arm and friction). Execute at open t+1+delay. No fit-period NAV ranking. Last partial month is not month-end.',
        variants={'equal':'N15 monthly equal sleeve capital','risk':'N15 monthly covariance equal-risk contribution',
            'all':'All supported risky ETF sleeves, equal monthly capital'},
        risk='252net strategy-account daily returns incl cash; covariance*252;50%diagonal shrinkage;5%annualvol diagonal floor. Positive convex risk-budget solution, normalize to1. No leverage/cap; concentration reported.',
        cash='Zero yield uninvested USD sleeve cash; capital drifts between allocations. Signals do not renormalize funded active ETFs. Shadow accounts evolve even when excluded. New members join existing desired state/protection; pending exits dominate. Leaving sells but shadow continues.',
        execution='Fractional adjusted units. At allocation open solve Vpost=Vpre-fee*sum(abs(w*active*Vpost-oldnotional)); net orders. Otherwise each sleeve uses its own cash/units for daily shadow signal changes. Same delayed strategy replay for cost/delay. Fees once, no shadow-NAV compounding into actual portfolio. Terminal mark, no forced liquidation.',
        dynamic='Separate EW/ERC arms: month-end OR L1(latest theoretical asset exposure plus cash,last actually adopted theoretical target)>=.10. Theoretical budgets re-ranked daily and multiplied by close desired state. Orders immutable in transit; at most one pending allocation, no overlapping new trigger until execution. Daily signal trading continues. Actual drift never enters trigger.',
        controls='All-pool strategy sleeves; same 63/252four-rank raw adjusted ETF returns, N15EWmonthly always invested; equal initial capital full risky pool buy/hold; BILbuy/hold netentryfee; zero cash. FR25frozen monthly targets only later, USDsameaudit/fee/delay fractional ledger, compatible dates throughOct12. FR25has own smaller effective universe/risk architecture; not a matched rank-only ablation.',
        secondary='EW/ERC21/126rank sensitivity at5bp/noextra delay, same252warmup. N fixed15; no widthsearch.',
        assessment='Compare primary net Sharpe, CAGR, drawdown vs unranked sleeves and raw momentum; retention guard no more1pp CAGR loss/2pp drawdown worsening. Both eras/allfrictions; report failures, no posthoc parameter tuning. Dynamic versus corresponding monthly sameguard. Descriptive annual returns, cash/concentration, costs/turnover and attribution; not promotion.',
        diagnostics='Spearman monthly rank score versus next21shadowstrategy returns, full labels only. Attribution sums actual overnight+intradaymark PnL-fees byETF, no capital transfers inP&L. Weakest full-pool shadow on matched post-warmup window perera plus worstcontributor ofeachmainportfolio. Both eras inspected manytimes: development evidence, not freshOOS.',
        limitations=['Retrospective supported cohort; no historical publication-vintage proof.','USD adjusted synthetic unit research; no tax, FX, bid/ask or intraday liquidity simulation.',
            'Zero cash interest; BIL separate reference. Rank windows may reward noise, overlapping assets and fee-adjusted past beta.',
            'Models and inherited policy fit frozen, not jointly optimized. Closing stop executes later open and cannot cap gap loss.',
            'Risk parity is ex-ante on full strategy accounts, not guaranteed on currently invested exposures. No portfolio weight cap.',
            'No recurring tracking, broker, funding, live or promotion changes.'],
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):digest(p) for p in [Path(__file__),
            ROOT/'src/systematic_trading/research/trend_sleeve_portfolio.py',ROOT/'tests/test_trend_sleeve_portfolio.py']})


def prepare():
    study.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True,parents=True)
    p=study.clean(protocol())
    if (OUT/'protocol.json').exists() and read(OUT/'protocol.json')!=p:raise ValueError('Frozen protocol changed')
    write(OUT/'protocol.json',p);print('Frozen protocol',digest(OUT/'protocol.json'),flush=True)


def verify():
    if study.clean(protocol())!=read(OUT/'protocol.json'):raise ValueError('Protocol changed')


def shadows():
    verify();market,_,_,_,_,selected=study.verified()
    old={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r['cumulative'] for r in read(study.OUT/'asset-results.json') if r['arm']=='hmm'}
    arrays={};metadata={};error=0.;checks=0
    for era,cutoff,first,last in study.ERAS:
        symbols=[s for s in sorted(market) if era in selected[s]]
        pieces=[];calendar=None
        for symbol in symbols:
            f,cl,_,start=study.replay(symbol,era,market,selected,arm='hmm')
            days=f.days[start:].astype(str)
            if calendar is None:calendar=days
            if not np.array_equal(calendar,days):raise ValueError('Unaligned published calendar')
            raw=study.prior.study.load_asset(symbol)
            part={k:np.asarray(raw[k])[start:len(f.days)] for k in ('open','high','low','close','volume')}
            for k,v in [('fast_up',cl['fast_probability'][:,2]),('fast_down',cl['fast_probability'][:,0]),
                        ('neutral',cl['fast_probability'][:,1]),('slow_up',cl['slow_probability'][:,2]),('slow_down',cl['slow_probability'][:,0])]:part[k]=v[start:]
            for cost,delay in study.FRICTIONS:
                sim=study.model.simulate(f,cl,start=start,cost_bp=cost,delay=delay,fc=None)
                error=max(error,abs(sim['nav'][-1]-1-old[symbol,era,cost,delay]));checks+=1
                for k in ('nav','desired','held','stop'):part[f'{k}_c{cost}d{delay}']=sim[k][start:]
            pieces.append(part)
            print('Shadow',era,symbol,flush=True)
        for k in pieces[0]:arrays[era+'_'+k]=np.column_stack([p[k] for p in pieces])
        arrays[era+'_days']=calendar;arrays[era+'_symbols']=np.array(symbols)
        start=next(t for t in range(252,len(calendar)-1) if calendar[t][:7]!=calendar[t+1][:7])
        metadata[era]=dict(symbols=symbols,train_end=cutoff,shadow_start=first,first_signal=str(calendar[start]),
            first_fill=str(calendar[start+1]),last=str(calendar[-1]),start=start,risky=len(symbols)-1)
    if error>1e-12:raise ValueError('Frozen B reproduction failed')
    np.savez_compressed(WORK/'shadows.npz',**arrays)
    write(OUT/'shadow-validation.json',dict(cases=checks,max_cumulative_error=float(error),eras=metadata,
        protocol=digest(OUT/'protocol.json'),shadows=digest(WORK/'shadows.npz')))
    print('Reproduced',checks,'cases',error,flush=True)


def load():
    verify();v=read(OUT/'shadow-validation.json')
    if digest(WORK/'shadows.npz')!=v['shadows']:raise ValueError('Changed shadows')
    with np.load(WORK/'shadows.npz',allow_pickle=False) as z:arrays=dict(z)
    return arrays,v


def ledger_check(result,opens,closes,days,symbols,start):
    cash=1.;units=np.zeros(len(symbols));by={}
    for f in result['fills']:by.setdefault(f['date'],[]).append(f)
    error=0.
    for t in range(start,len(days)):
        for f in by.get(str(days[t]),[]):
            j=symbols.index(f['symbol']);q=f['units']*(1 if f['side']=='buy' else -1)
            units[j]+=q;cash-=q*f['price']+f['fee']
        error=max(error,abs(cash+units@closes[t]-result['nav'][t-start]))
    if error>1e-10:raise ValueError('Independent global cash/share ledger failed')
    return error


def evaluate():
    if (OUT/'results.json').exists():raise ValueError('Preserve completed results')
    arrays,validation=load();rows=[];paths={};detail={};attribution={};weak=[];ic=[];ledger=0.;erc=0.
    from scipy.stats import spearmanr
    for era,meta in validation['eras'].items():
        symbols=arrays[era+'_symbols'].tolist();js=[j for j,s in enumerate(symbols) if s!='BIL'];risky=[symbols[j] for j in js]
        days=arrays[era+'_days'];op=arrays[era+'_open'][:,js];cl=arrays[era+'_close'][:,js];start=meta['start']
        paths[era+'_days']=days[start:].tolist()
        for cost,delay in study.FRICTIONS:
            suffix=f'_c{cost}d{delay}';nav=arrays[era+'_nav'+suffix][:,js]
            desired=arrays[era+'_desired'+suffix][:,js];held=arrays[era+'_held'+suffix][:,js]
            specs=[('equal',{}),('risk',dict(kind='risk')),('all',dict(source='all')),
                ('equal_dynamic',dict(clock='dynamic')),('risk_dynamic',dict(kind='risk',clock='dynamic')),
                ('raw_momentum',dict(source='raw')),('buyhold',dict(source='all',clock='buyhold'))]
            if cost==5 and delay==0:specs += [('equal_short',dict(short=21,long=126)),('risk_short',dict(kind='risk',short=21,long=126))]
            for name,kw in specs:
                active=np.ones_like(held) if name in ('raw_momentum','buyhold') else held
                wants=np.ones_like(desired) if name in ('raw_momentum','buyhold') else desired
                result=model.run(days,risky,op,cl,nav,wants,active,start=start,cost_bp=cost,delay=delay,**kw)
                key=f'{era}_{name}{suffix}'
                stats=model.metrics(result);yearly={}
                nn=result['nav'];dd=np.array(result['days'])
                for year in sorted(set(d[:4] for d in result['days'][1:])):
                    ix=np.flatnonzero(np.char.startswith(dd,year)&(np.arange(len(dd))>0))
                    yearly[year]=float(nn[ix[-1]]/nn[ix[0]-1]-1)
                rows.append(dict(era=era,arm=name,cost_bp=cost,delay=delay,**stats,yearly=yearly))
                paths[key]=result['nav']
                ledger=max(ledger,ledger_check(result,op,cl,days,risky,start));erc=max(erc,result['erc_error'])
                if cost==5 and ((delay==0 and name in ('equal','risk','all','equal_dynamic','risk_dynamic')) or (delay==1 and name=='equal')):
                    detail[key]=result
                    a=[dict(symbol=s,pnl=float(result['contribution'][:,j].sum()),
                        fee=float(result['costs'][:,j].sum()),average_weight=float(result['holdings'][1:,j].mean()),
                        selected_days=int(np.sum(result['sleeves'][1:,j]>1e-12)),fills=sum(f['symbol']==s for f in result['fills'])) for j,s in enumerate(risky)]
                    a.sort(key=lambda r:(r['pnl'],r['symbol']));attribution[key]=a
                if cost==5 and delay==0 and name=='equal':
                    for rank in result['ranks']:
                        t=int(np.searchsorted(days,rank['date']))
                        if t+21>=len(days):continue
                        rs=rank['rows'];future=[nav[t+21,r['index']]/nav[t,r['index']]-1 for r in rs]
                        ic.append(dict(era=era,date=rank['date'],ic=float(spearmanr([r['score'] for r in rs],future).statistic),eligible=len(rs)))
                print('Portfolio',key,round(stats['cumulative']*100,2),round(stats['sharpe'] or 0,3),flush=True)
            # Fully invested BIL reference, isolated from the risky universe.
            j=symbols.index('BIL');bop=arrays[era+'_open'][:,j:j+1];bcl=arrays[era+'_close'][:,j:j+1];active=np.ones_like(bop,bool)
            z=model.run(days,['BIL'],bop,bcl,bcl,active,active,start=start,source='all',clock='buyhold',cost_bp=cost,delay=delay)
            rows.append(dict(era=era,arm='BIL',cost_bp=cost,delay=delay,**model.metrics(z)))
            paths[f'{era}_BIL{suffix}']=z['nav']
        nav=arrays[era+'_nav_c5d0'][:,js]
        perf=nav[-1]/nav[start]-1;j=int(np.argmin(perf))
        weak.append(dict(era=era,symbol=risky[j],cumulative=float(perf[j]),first=str(days[start]),last=str(days[-1]),
            definition='Continuously running shadow account on portfolio evaluation window; may carry existing position at boundary.'))
    # FR25 retains its own frozen universe/target rule; same research ledger.
    panel=frozen._load_panel();days=panel['days'].astype(str);symbols=panel['symbols'].tolist()
    start=int(np.searchsorted(days,validation['eras']['late']['first_signal']))
    op,cl=panel['open'],panel['close'];active=np.ones_like(op,bool)
    for cost,delay in study.FRICTIONS:
        z=model.run(days,symbols,op,cl,cl,active,active,start=start,source='fixed',fixed_targets=panel['fr25'],cost_bp=cost,delay=delay)
        rows.append(dict(era='late',arm='FR25',cost_bp=cost,delay=delay,**model.metrics(z)))
        paths[f'late_FR25_c{cost}d{delay}']=z['nav'];paths['FR25_days']=z['days']
        ledger=max(ledger,ledger_check(z,op,cl,days,symbols,start))
    # Explicit matched-date metrics, so FR25's earlier cutoff is never hidden.
    matched=[];end=str(days[-1])
    for row in rows:
        if row['era']!='late':continue
        key=f"late_{row['arm']}_c{row['cost_bp']}d{row['delay']}";nav=np.array(paths[key])
        ds=paths['FR25_days'] if row['arm']=='FR25' else paths['late_days']
        n=sum(d<=end for d in ds);x=nav[:n];r=x[1:]/x[:-1]-1;dd=1-x/np.maximum.accumulate(x)
        matched.append(dict(arm=row['arm'],cost_bp=row['cost_bp'],delay=row['delay'],first=ds[0],last=end,
            cumulative=float(x[-1]-1),cagr=float(x[-1]**(252/len(r))-1),sharpe=float(r.mean()/r.std(ddof=1)*np.sqrt(252)),max_drawdown=float(dd.max())))
    write(OUT/'results.json',rows);gzwrite(OUT/'paths.json.gz',paths);gzwrite(OUT/'detail.json.gz',detail)
    write(OUT/'attribution.json',attribution);write(OUT/'weakest.json',weak);write(OUT/'rank-ic.json',ic);write(OUT/'fr25-matched.json',matched)
    write(OUT/'validation.json',dict(portfolio_cases=len(rows),independent_ledger_max_error=ledger,erc_max_error=erc,
        contribution_max_error=max(abs(sum(r['pnl'] for r in a)-(detail[k]['nav'][-1]-1)) for k,a in attribution.items()),
        protocol=digest(OUT/'protocol.json'),shadows=validation['shadows'],results=digest(OUT/'results.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','shadows','evaluate'))
    globals()[parser.parse_args().stage]()
