"""Frozen full-pool test of a shared market forecast and evidence-change review."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import os
from pathlib import Path
import sys
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_trained_review as previous
from systematic_trading.research import coherent_review as model
prior,base=previous.prior,previous.base
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/coherent-review-20261028-v1'
WORK=ROOT/'var/research/coherent-review-20261028-v1'
write,clean,setup=previous.write,previous.clean,previous.setup


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Full52 later/50 earlier ETF pool; single-ETF long-only research. BIL cash reference excluded from acceptance. Historical eras repeatedly inspected; not fresh OOS. No overlay, promotion or live changes.',
        arms=dict(baseline='A exact standing protection',stop='B shared price forecast + evidence-change review',review='C shared price/volume forecast + evidence-change review'),
        hypothesis='Shared market-state predictions eliminate independent buy/hold contradictions; evidence changes prevent unconditional means from reversing every position. Predictive selection may correctly abstain without producing a performance improvement.',
        target='At close t forecast Y_t=(O[t+2]/O[t+1]-1)/(ATR_t/C_t), maturity open t+2. Common one-session underlying asset return for both holding and recovery, independent of position state and later review decisions. No multi-day policy-dependent counterfactual labels. This is a market forecast, not a Bellman value or an estimate of actual stop-clipped PnL; standing protection remains separate. Additional delay is execution stress with unchanged forecast horizon.',
        features='Intercept + five price features: daily log-return/a, three-day log-return/(sqrt3*a), (close-EMA10close)/ATR, (EMA10close-EMA60close)/ATR, 2close-location-1. C adds log(rawVolume/EMA20volume), three-session signed-volume pressure, relative-volume times centered close location. Same feature vector regardless of held/cash/recovery state. Causal EMAs; Wilder20 ATR; a=max(ATR/close,.0001). Clip nonintercept coordinates[-5,5]. No HMM features or trading-state fields.',
        fitting='Each ETF/era separately. Last756 fully matured origins after252warmup, excluding final2 closes. Three rolling validation blocks, width=min126,floor(sample_size/5), minimum50; initial training then expands. Prefix training maturity strictly before validation first origin. Refit scaler and intercept/ridge1/10/100 in each fold. Feature SD floor.1; intercept unscaled and only numerical1e-8 penalty. Minimize average normalized return MSE across three equal-width folds, ties intercept then strongest ridge. Activate only nonconstant model with >.5% pooled MSE reduction versus rolling training-mean control and improvement in >=2/3 folds. Otherwise abstain. Final selected model refitted all mature training. No PnL selection or parent-HMM fit inside reviewer calibration; the reviewer learning problem is independent of the parent pipeline. The parent remains its frozen outer-training model, with its existing selection limitations.',
        policy='Fixed engineering margin m=.05 ATR-return units, new-evidence delta=.10, not optimized on evaluation. Shared score u=predicted normalized one-session return. Added exit when u<-m AND u<entry_signal_score-delta. Recovery within1..20 sessions after any sale when ((1+a*u)*(1-fee)/(1+fee)-1)/a>m AND u>sale_day_close_score+delta. Same-score entry and exit rules are disjoint; unchanged evidence cannot trigger either reversal. Original HMM entries/exits retained; ordinary entry priority. Buy anchor is its signal-close score, sale anchor is completed sale-day-close score (first used on later closes). Recovery next-open deviation >1 signal ATR cancels. Recovery HMM handoff waits for eligible up confirmation, including while delayed recovery buy pending. Protection always active, stops never widen. No online coefficient changes, resets or permanent pause.',
        execution=json.loads((previous.OUT/'protocol.json').read_text())['execution'],
        diagnostics='Primary C: exits-only, recoveries-only, no change-since-decision requirement, no HMM handoff, fixed every5sessions review instead of daily event review. All three arms at50bp stop slippage. These are attribution/stress controls, not selectable alternatives. Main5/10/20bp x extra delay0/1;612 exact parent/disabled comparisons. Forecast evaluation uses all matured evaluation origins, same target and training-mean comparator; constant IC undefined.',
        assessment='Each12 era/friction settings: higher median net Sharpe and lower-quartile CAGR than A, >=90% risky ETFs within1pp CAGR/2pp maxDD of A. No annual cost ceiling. Show all ETFs, buyhold/cash, annual and cost/delay outcomes. Weakest C per era ranked by primary cumulative return. Include WEAT/MCHI/GLD/DBA/SLV and CPER/IWM nominated intervals. Preserve earlier close-stop anchor and previous trained result as historical evidence, no post-result retuning.',
        code={p.relative_to(ROOT).as_posix():prior.study.digest(p) for p in (Path(__file__),ROOT/'src/systematic_trading/research/coherent_review.py',ROOT/'tests/test_coherent_review.py')})


def prepare():
    previous.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    p=clean(protocol());path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=p:raise ValueError('Frozen protocol changed')
    write(path,p);print('Frozen',prior.study.digest(path),flush=True)


def verified(require_fit=True):
    assert clean(protocol())==json.loads((OUT/'protocol.json').read_text());parents=previous.verified()
    if not require_fit:return parents
    fits=json.loads((OUT/'fits.json').read_text())
    assert json.loads((OUT/'fit-manifest.json').read_text())==dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json'))
    return (*parents,fits)


def fit_asset(job):
    symbol,selected=job;out={};full=model.Features.build(prior.study.load_asset(symbol))
    for era,cutoff,*_ in ERAS:
        if era not in selected:continue
        f=full.truncated(cutoff)
        out[era]=dict(training_end=str(f.days[-1]),models={kind:model.fit_family(f,kind) for kind in ('price','volume')})
    return symbol,out


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Fits frozen')
    parents=verified(False);market,selected=parents[0],parents[5];result={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol,value in pool.map(fit_asset,[(s,selected[s]) for s in sorted(market)]):
            result[symbol]=value;write(WORK/'fit-progress.json',result);print('Fitted',symbol,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def forecast_metrics(f,fit,start):
    from scipy.stats import spearmanr
    q=model.inputs(f);ix=np.arange(start,len(f.days)-2);y=(f.open[ix+2]/f.open[ix+1]-1)/q['scale'][ix]
    pred=model.predict(fit['model'],q[fit['kind']+'_x'][ix]);constant=fit['model']['constant']
    return dict(count=len(ix),enabled=fit['enabled'],fixed_mse=float(np.mean((pred-y)**2)),constant_mse=float(np.mean((constant-y)**2)),
        ic=float(spearmanr(pred,y).statistic) if np.std(pred)>1e-10 else None,forecast_mean=float(pred.mean()),actual_mean=float(y.mean()))


def evaluate_asset(job):
    symbol,market,selected,fits,oldrows=job;rows=[];diags=[];charts={};checks=[];forecast=[]
    for era,_,first,last in ERAS:
        if era not in selected[symbol]:continue
        f,cl,rule=setup(symbol,era,market,selected,last);training=fits[symbol][era];start=int(np.searchsorted(f.days,np.datetime64(first)))-1
        context=max(0,start-1);q=model.inputs(f)
        chart=dict(days=f.days[context:].astype(str),evaluation_start=first,selection=selected[symbol][era],training=training,
            **{k:getattr(f,k)[context:] for k in ('open','high','low','close','volume')},parameters=cl['parameters'],
            slow_up=cl['slow_probability'][context:,2],slow_down=cl['slow_probability'][context:,0],fast_up=cl['fast_probability'][context:,2],
            fast_down=cl['fast_probability'][context:,0],neutral=cl['fast_probability'][context:,1],atr=q['atr'][context:],pressure=q['pressure'][context:],arms={})
        for cost,delay in FRICTIONS:
            common=dict(start=start,cost_bp=cost,delay=delay,rule=rule)
            sims={'baseline':model.simulate(f,cl,**common)}
            for arm,kind in [('stop','price'),('review','volume')]:sims[arm]=model.simulate(f,cl,arm=arm,fit=training['models'][kind],**common)
            disabled=model.simulate(f,cl,arm='review',fit=training['models']['volume'],force_disabled=True,**common)
            checks.append(dict(symbol=symbol,era=era,cost=cost,delay=delay,
                control_error=abs(sims['baseline']['nav'][-1]-1-oldrows[era,cost,delay]['cumulative']),
                disabled_review_error=float(np.nanmax(abs(disabled['nav']-sims['baseline']['nav']))),ledger_error=max(base.ledger_error(f,s,start) for s in sims.values())))
            for arm,sim in sims.items():
                sim['slippage_factor']=.9995;r=base.metrics(f,cl,sim,start,symbol,era,arm,cost,delay)
                r.update(enabled=False if arm=='baseline' else training['models']['price' if arm=='stop' else 'volume']['enabled'],
                    entry_invalidations=sum(e.get('exit_reason')=='entry_invalidated' for e in sim['episodes']),
                    handoffs=sum(e.get('handoff_index') is not None for e in sim['episodes']),
                    one_session_trades=sum(e['exit_index'] is not None and e['exit_index']-e['entry_index']==1 for e in sim['episodes']),
                    cancelled_recoveries=sum('recovery_open_cancelled' in e['reasons'] for e in sim.get('events',[])))
                rows.append(r)
                if cost==5 and delay==0:
                    a={}
                    for k in ('nav','stop','held','policy','review_signal','reset','hold_value','recover_value','reviewer_owned','shared_score','decision_anchor'):
                        v=np.asarray(sim.get(k,np.full(len(f.days),np.nan)),float).copy();v[:start]=np.nan;a[k]=v[context:]
                    a['nav']*=100
                    a.update(trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']],
                        fills=[dict(e,day=str(f.days[e['session']])) for e in sim['fills']],events=sim.get('events',[]))
                    chart['arms'][arm]=a
                    if arm!='baseline':forecast.append(dict(symbol=symbol,era=era,arm=arm,**forecast_metrics(f,training['models']['price' if arm=='stop' else 'volume'],start)))
            if cost==5 and delay==0:
                options=[('entry_only',dict(arm='review',exit_review=False)),('recovery_only',dict(arm='review',entry_review=False)),
                    ('no_change',dict(arm='review',require_change=False)),('no_handoff',dict(arm='review',handoff=False)),
                    ('weekly_review',dict(arm='review',review_interval=5))]+[(a+'_slip50',dict(arm=a,slip_bp=50)) for a in model.ARMS]
                for label,args in options:
                    fitted=training['models']['price' if args['arm']=='stop' else 'volume'];sim=model.simulate(f,cl,fit=fitted,**common,**args)
                    sim['slippage_factor']=1-args.get('slip_bp',5)/10000;checks[-1]['ledger_error']=max(checks[-1]['ledger_error'],base.ledger_error(f,sim,start))
                    diags.append(base.metrics(f,cl,sim,start,symbol,era,label,cost,delay));chart.setdefault('diagnostics',{})[label]=dict(nav=sim['nav'][context:]*100)
        charts[symbol+'_'+era]=chart
    return rows,diags,charts,checks,forecast


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Evaluation frozen')
    parents=verified();market,selected,fits=parents[0],parents[5],parents[-1]
    rows=[];diags=[];charts={};checks=[];forecast=[];jobs=[];old=json.loads((previous.OUT/'asset-results.json').read_text())
    for s in sorted(market):
        lookup={(r['era'],r['cost_bp'],r['delay']):r for r in old if r['symbol']==s and r['arm']=='baseline'}
        jobs.append((s,{s:market[s]},{s:selected[s]},{s:fits[s]},lookup))
    with ProcessPoolExecutor(max_workers=2) as pool:
        for rr,dd,cc,vv,ff in pool.map(evaluate_asset,jobs):
            rows+=rr;diags+=dd;charts.update(cc);checks+=vv;forecast+=ff;print('Evaluated',rr[0]['symbol'],flush=True)
    validation=dict(control_cases=len(checks),asset_cases=len(rows),max_control_error=max(c['control_error'] for c in checks),
        max_disabled_review_error=max(c['disabled_review_error'] for c in checks),max_independent_ledger_error=max(c['ledger_error'] for c in checks))
    write(WORK/'checks.json',checks);assert max(validation[k] for k in ('max_control_error','max_disabled_review_error','max_independent_ledger_error'))<1e-11,validation
    write(OUT/'asset-results.json',rows);write(OUT/'diagnostics.json',diags);write(OUT/'forecast-diagnostics.json',forecast)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    validation['chart_sha256']=prior.study.digest(OUT/'chart-data.json.gz');write(OUT/'validation.json',validation)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[parser.parse_args().stage]()
