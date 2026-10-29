"""Full-pool directional HMM and online executable-outcome study."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import os
from pathlib import Path
import sys
for _name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_regime_entry as previous
from systematic_trading.research import entry_value as model
prior=previous.prior
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/entry-value-20261027-v1'
WORK=ROOT/'var/research/entry-value-20261027-v1'
write,clean=previous.write,previous.clean


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Full supported single-ETF pool. No overlays, portfolios or broker changes. Already-inspected development eras.',
        arms=dict(control='A exact previous fixed-policy original-detector control; not the adaptive incumbent.',
            hmm='B A with symmetric-directional Gaussian fast-slope HMM. Fixed original base policy0/thesis exit/stops.',
            value='C B with online forecast entry gate Rhat - log((1+fee)/(1-fee)) - .25 Dhat > 0. No forecast exit, pause or extra confirmation. Same exit/protection rules as B.'),
        hmm='x=fast Kalman slope/training daily sigma; means=(-a,0,a), a in[.2,2], shared directional variance in[.01,4], neutral variance in[.000025,.01]. Band .10 fixed. EM25 two starts .2/.4. Transition counts xi+.1+3I; diagonal .65..98. Training smoothing only; forward trading. log emission U/D odds=2ax/v. Persistent prior can still oppose a modest new slope; this is semantic consistency, not proven true regimes.',
        validation='For each ETF fit fast/slow Kalman and symmetric HMM on training prefix excluding final252 sessions. Prefix sigma as daily log-return sample std. Fix H=clip(round(1/(1-A_UU)),5,21) from prefix HMM. Forward validation predictions over final252, only labels matured by training cutoff. Select four forecast candidates by return MSE+.5 downside MSE, divided by sigma^2 H; ties intercept then longer memory. No evaluation selection. Refit final HMM on full training with parent full-training Kalman; replay forecast through training to seed evaluation. Final seed is fitted training calibration, not untouched forecast validation.',
        forecasts='Full10 inputs=(1,pU-pD,pR,fastSlope/sigma,slowSlope/sigma,(logP-fastLevel)/sigma,(logP-slowLevel)/sigma,slowUp-slowDown,pU*slowDown,log(rawVolume/EMA63(rawVolume))). Nonprobability covariates clipped[-3,3]. Alternative intercept only. Each uses memory half-life63 or252 sessions and ridge precision4I. At close t update label i=t-H-1: S=rho S+(1/H)xxT, B=rho B+(1/H)xyT, posterior mean=(4I+S)^-1 B. Targets scaled by sigma sqrtH. Discount each session from252. Fractional weight1/H acknowledges overlap, does not calibrate independence or confidence. All matured hypothetical labels update while flat or invested. Downside prediction floored0.',
        labels='R_i=log(O_(i+H+1)/O_(i+1)); D_i=max(0,-min(log(P/O_(i+1)))) over opens i+1..i+H+1 and closes i+1..i+H. Label matures at i+H+1. Sampled open/close adverse movement, not intraday loss or guaranteed stop. Forecast horizon fixed from prefix model; not a fixed trend window. Higher-cost gate adjusts exact roundtrip log fee; delayed execution tests use same next-open forecast without refit.',
        execution=json.loads((previous.OUT/'protocol.json').read_text())['execution'],
        diagnostics='Parent correlation/beta/annual intercept/HAC5/raw-state IC5, annual returns and conditional slow-context results; additionally return forecast rank IC, return/downside MSE, mean forecast vs realized, and same-memory intercept benchmark. Overlapping targets, repeated ETFs/eras and repeated inspection preclude significance or fresh OOS claims. Native checks frozen signals/accounting only.',
        assessment=json.loads((previous.OUT/'protocol.json').read_text())['assessment'].replace('Weakest C ETF','Weakest value-gated C ETF'),
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in (Path(__file__),ROOT/'src/systematic_trading/research/entry_value.py',ROOT/'tests/test_entry_value.py')})


def prepare():
    previous.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True,parents=True)
    p=clean(protocol());target=OUT/'protocol.json'
    if target.exists() and json.loads(target.read_text())!=p:raise ValueError('Frozen protocol changed')
    write(target,p);print('Frozen',prior.study.digest(target),flush=True)


def verified(require_fit=True):
    assert clean(protocol())==json.loads((OUT/'protocol.json').read_text())
    parents=previous.verified()
    if not require_fit:return parents
    fits=json.loads((OUT/'fits.json').read_text())
    assert json.loads((OUT/'fit-manifest.json').read_text())==dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json'))
    return (*parents,fits)


def fit_asset(job):
    symbol,saved,exits=job;full=prior.model.Features.build(prior.study.load_asset(symbol));result={}
    for era,cutoff,*_ in ERAS:
        if not saved[era]['available']:continue
        f=full.truncated(cutoff);f.hmm_models=saved[era]['hmms'];p=saved[era]['selected']['selected']['parameters'];rule=exits[era]['arms']['thesis']['rule']
        base=model.classification(f,p,rule);n=len(f.days);split=n-252
        prefix=full.truncated(str(f.days[split-1]));y=np.log(prefix.close)
        mm=dict(f.hmm_models,slow=model.parent.latent_slope.fit_filter(y,(1e-10,1e-6)),
            fast=model.parent.latent_slope.fit_filter(y,(1e-5,1e-2)),sigma=float(np.std(np.diff(y),ddof=1)))
        prefix.hmm_models=mm;pc=model.classification(prefix,p,rule)
        ph=model.fit_hmm(pc['fast_slope'][252:]/pc['sigma'])
        horizon=int(np.clip(round(1/(1-np.asarray(ph['transition'])[2,2])),5,21))
        vf=full.truncated(cutoff);vf.hmm_models=mm;vc=model.classification(vf,p,rule,ph)
        indices=np.arange(split,n-horizon-1);candidates=[]
        for kind in ('intercept','full'):
            for memory in (63,252):
                fc=model.forecast(vf,vc,horizon,memory,kind);metrics=model.forecast_metrics(fc,indices)
                score=(metrics['return_mse']+.5*metrics['downside_mse'])/(vc['sigma']**2*horizon)
                candidates.append(dict(kind=kind,memory=memory,score=score,metrics=metrics))
        chosen=min(candidates,key=lambda c:(c['score'],c['kind']!='intercept',-c['memory']))
        result[era]=dict(training_end=str(f.days[-1]),validation_start=str(f.days[split]),prefix_end=str(prefix.days[-1]),
            horizon=horizon,forecast=chosen,candidates=candidates,prefix_models=mm,prefix_hmm=ph,
            hmm=dict(model=model.fit_hmm(base['fast_slope'][252:]/base['sigma'])),exit_rule=rule)
    return symbol,result


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Frozen fits exist')
    market,_,_,exits,_=verified(False);result={}
    jobs=[(s,market[s],exits[s]) for s in sorted(market)]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol,value in pool.map(fit_asset,jobs):
            result[symbol]=value;write(WORK/'fit-progress.json',result);print('Fitted',symbol,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def replay(symbol,era,market,selected,cost=5,delay=0,arm='value'):
    _,_,first,last=next(e for e in ERAS if e[0]==era)
    f=prior.model.Features.build(prior.study.load_asset(symbol)).truncated(last);f.hmm_models=market[symbol][era]['hmms']
    p=market[symbol][era]['selected']['selected']['parameters'];q=selected[symbol][era]
    cl=model.classification(f,p,q['exit_rule'],None if arm=='control' else q['hmm']['model'])
    fc=model.forecast(f,cl,q['horizon'],q['forecast']['memory'],q['forecast']['kind']) if arm=='value' else None
    start=int(np.searchsorted(f.days,np.datetime64(first)))-1
    return f,cl,model.simulate(f,cl,start=start,cost_bp=cost,delay=delay,fc=fc),start


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Frozen evaluation exists')
    market,_,_,_,_,selected=verified();rows=[];charts={};control_error=ledger_error=0.;checks=0
    oldrows=json.loads((previous.OUT/'asset-results.json').read_text())
    oldlookup={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in oldrows if r['arm']=='control'}
    for symbol in sorted(market):
        full=prior.model.Features.build(prior.study.load_asset(symbol))
        for era,_,first,last in ERAS:
            if era not in selected[symbol]:continue
            f=full.truncated(last);f.hmm_models=market[symbol][era]['hmms'];p=market[symbol][era]['selected']['selected']['parameters'];q=selected[symbol][era]
            assert q['training_end']<first
            base=model.classification(f,p,q['exit_rule']);new=model.classification(f,p,q['exit_rule'],q['hmm']['model'])
            fc=model.forecast(f,new,q['horizon'],q['forecast']['memory'],q['forecast']['kind'])
            null=model.forecast(f,new,q['horizon'],q['forecast']['memory'],'intercept')
            lo=int(np.searchsorted(f.days,np.datetime64(first)));start=lo-1;idx=np.arange(start,len(f.days)-q['horizon']-1)
            forecast_stats=model.forecast_metrics(fc,idx);null_stats=model.forecast_metrics(null,idx)
            context=int(np.searchsorted(f.days,np.datetime64('2021-01-01' if era=='late' else first)))
            ar=f.close[lo:]/f.close[lo-1:-1]-1
            chart=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],evaluation_start=first,
                parameters=p,selection=q,slow_up=base['slow_probability'][context:,2],slow_down=base['slow_probability'][context:,0],
                normalized_slope=base['fast_slope'][context:]/base['sigma'],arms={})
            for cost,delay in FRICTIONS:
                for arm in model.ARMS:
                    cl=base if arm=='control' else new;sim=model.simulate(f,cl,start=start,cost_bp=cost,delay=delay,fc=fc if arm=='value' else None)
                    old=oldlookup[symbol,era,cost,delay]
                    if arm=='control':
                        ref=model.parent.simulate(f,cl,start=start,cost_bp=cost,delay=delay)
                        control_error=max(control_error,float(np.nanmax(np.abs(sim['nav']-ref['nav']))),abs(float(sim['nav'][-1]-1)-old['cumulative']));checks+=1
                    cash=1.;units=0.;fills={e['session']:e for e in sim['fills']}
                    for t in range(start,len(f.days)):
                        if t in fills:
                            e=fills[t];sign=1 if e['side']=='buy' else -1;cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
                        ledger_error=max(ledger_error,abs(sim['nav'][t]-cash-units*f.close[t]))
                    nav=sim['nav'][start:];s=prior.stats.nav_stats(nav);years=(len(nav)-1)/252
                    r=nav[1:]/nav[:-1]-1;closed=[e for e in sim['episodes'] if e['exit_index'] is not None]
                    daily_context=np.where(base['aligned'][start:-1],'up',np.where(base['counter'][start:-1],'down','uncertain'));regimes={}
                    for state in ('up','down','uncertain'):
                        mask=daily_context==state;tr=[e for e in closed if e['context']==state]
                        regimes[state]=dict(sessions=int(mask.sum()),exposure=float(sim['exposure'][lo:][mask].mean()) if mask.any() else None,
                            strategy_mean=float(r[mask].mean()) if mask.any() else None,asset_mean=float(ar[mask].mean()) if mask.any() else None,
                            closed=len(tr),losing=sum(e['net_return']<0 for e in tr),mean_trade=float(np.mean([e['net_return'] for e in tr])) if tr else None)
                    yearly={}
                    for year in sorted(set(str(d)[:4] for d in f.days[lo:])):
                        ix=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>=lo))
                        yearly[year]=float(sim['nav'][ix[-1]]/sim['nav'][ix[0]-1]-1)
                    rows.append(dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**s,cumulative=float(nav[-1]-1),
                        **model.parent.dependence(r,ar),ic5=model.parent.ic(f,cl,start,delay),closed_trades=len(closed),wins=sum(e['net_return']>0 for e in closed),
                        exposure=float(sim['exposure'][lo:].mean()),regimes=regimes,yearly=yearly,guard=q['forecast'] if arm=='value' else None,enabled=arm=='value',
                        blocked_sessions=int(sim['blocked'][lo:].sum()),forecast=forecast_stats,forecast_null=null_stats,horizon=q['horizon'],
                        turnover_annual=sum(e['units']*e['price']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years,
                        cost_bp_annual=sum(e['fee']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years*10000,
                        adaptive_incumbent_cumulative=old['adaptive_incumbent_cumulative'],adaptive_incumbent_sharpe=old['adaptive_incumbent_sharpe'],
                        incumbent_dependence=old['incumbent_dependence'],buyhold=old['buyhold']))
                    if cost==5 and delay==0:
                        def series(a):
                            z=np.asarray(a,float).copy();z[:lo]=np.nan;return z[context:]
                        a={k:series(sim[k]) for k in ('nav','stop','desired','blocked','gate')};a['nav']*=100
                        a.update(predicted_return=series(fc['prediction'][:,0]),predicted_downside=series(fc['prediction'][:,1]),
                            utility=series(model.gate(new,fc,cost)[1]),fast_up=series(cl['fast_probability'][:,2]),neutral=series(cl['fast_probability'][:,1]),fast_down=series(cl['fast_probability'][:,0]),
                            thesis_floor=series(cl['thesis_floor']),trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']])
                        chart['arms'][arm]=a
            charts[f'{symbol}_{era}']=chart
        print('Evaluated',symbol,flush=True)
    assert control_error<1e-12 and ledger_error<1e-12
    write(OUT/'asset-results.json',rows)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(OUT/'validation.json',dict(control_cases=checks,max_control_nav_error=control_error,max_independent_ledger_error=ledger_error,asset_cases=len(rows),chart_sha256=prior.study.digest(OUT/'chart-data.json.gz')))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[parser.parse_args().stage]()
