"""Train decision-specific ETF reviewers, then freeze and evaluate the full pool."""
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
import research_decision_review as previous
from systematic_trading.research import trained_review as model
prior=previous.prior
base=previous.previous
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/trained-review-20261028-v1'
WORK=ROOT/'var/research/trained-review-20261028-v1'
write,clean,setup=previous.write,previous.clean,previous.setup


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Full52 late/50 early ETF pool. Single ETF, cash-funded long only. Pinned audited adjusted OHLC/raw volume. Already inspected development eras, not a fresh holdout. No overlay or live changes.',
        arms=dict(baseline='A exact standing-protection control, prior B1.',stop='B per-ETF trained price-only continuation/recovery reviewer.',
            review='C per-ETF trained price+volume continuation/recovery reviewer. No online changes to traded models; adaptation is diagnostic shadow only.'),
        sample='Baseline replay over final756 training returns, cash initial. Held rows at completed closes with position, desired target and no scheduled exit. Recovery rows when flat/no pending entry, 1..20 sessions after sale, until next buy. Augment held rows with states from hypothetical recoveries at these same opportunities. Within each task, rows from a real held episode or one originating exit episode share total weight1, including overlapping hypothetical paths. Price/volume models fit separately for each ETF and each task.',
        labels='For close t, compare protected continuation against selling at O[t+1], or hypothetical recovery purchase at O[t+1]. Follow at most10 complete bars, terminal O[t+11]. Use same fixed entry-risk unit, context-dependent ratcheting protection, gap-aware stop slip5bp and ordinary next-open HMM/thesis exits. Recovery paths are reviewer-owned until eligible-up confirmation, then parent exit logic applies. No future reviewer decisions inside labels. Record gross incremental return R and sampled adverse excursion D up to modeled exit; after a stop, do not count later bar lows. Withhold all labels until t+11 even if exit earlier. Recovery open more than1 current ATR from signal close: cancel, target zero. This is a counterfactual continuation label, not realized alpha or an assumption that actual positions close after10 days.',
        features='Price: intercept plus10 bounded coordinates: daily log return/(ATR/close); three-day log return/(sqrt3 ATR/close); (close-EMA10close)/ATR; (EMA10close-EMA60close)/ATR; 2 close-location-1; (close-reference)/ATR; (peak-close)/ATR; min(age,60)/20; (close-active-next-stop)/ATR; reviewer-owned flag. Reference=entry price while held, last sale price while watching. Add3 volume coordinates for C: log(rawVolume/EMA20volume), three-session signed volume pressure, close-location times log relative volume. Nonintercept coordinates clipped[-5,5]. Normalize features by weighted training mean/std, std floor.1. ATR divisor floor close*.0001. HMM trend windows unchanged; EMAs are reviewer covariates, not new hard regime rules.',
        regression='Two-output weighted ridge predicting R/(ATR/close),D/(ATR/close), separately for hold/recover. Candidates intercept-only or ridge1,10,100. Intercept unpenalized except1e-8 numerical ridge. Choose lowest weighted validation return MSE+.25 downside MSE; ties intercept then stronger ridge. Full features eligible only if prefix has >=8 distinct source groups. Refit selected family/penalty on full training. Price-only is not a guarantee of fewer degrees of freedom than support permits.',
        validation='Last252 training sessions reserved for reviewer calibration; prefix rows must have full label maturity strictly before split. Feature scaling and reviewer coefficients prefix-only; validation labels mature by outer cutoff. Parent HMM/filter/policy are the already-fitted outer-training snapshot, fixed for this conditional reviewer calibration. This is not fully nested validation of parent strategy selection. No outer evaluation observations or labels used. Margins [disabled,0,.25,.5] in ATR-return units selected on matched validation strategy replay: require Sharpe > control+.01, total return >=control-.005, maxDD>=control-.01. Rank Sharpe then return then larger margin; otherwise disable review. Refit coefficients after selection; do not refit on evaluation.',
        policy='U_hold=Rhat-.25max(Dhat,0). U_recover=(1+Rhat)*(1-fee)/(1+fee)-1-.25max(Dhat,0). Divide by ATR/close. Additional exit if U_hold < -selected margin; recovery if U_recover > margin. No accumulated evidence, HMM entry gate, close-location requirement, signed-volume requirement or exit-price band. Ordinary entries have priority if they already qualify. Recovery order cancelled if abs(next executable open-signalclose)>signalATR. A recovery remains protected and reviewer-owned until original eligible-up confirmation; then old HMM/thesis exit authority resumes. No automatic time exit. Original entries keep all original exits. Stops never widen.',
        shadow='No online predictor influences trades. After replay, sequentially score stored fixed and shadow predictions at t+11 maturity on actual decision contexts. Shadow linear sufficient statistics start S=20I,B=20 beta_fixed in training-standardized coordinates, discount each session by2^(-1/63), add xxT/10 and xyT/10 only at maturity; solve with1e-6 I numerical ridge. Forecasts stored before their labels. Overlap and endogenous decision samples preclude independent-posterior/significance claims. Compare frozen, shadow and constant training-intercept forecasts.',
        execution=json.loads((previous.OUT/'protocol.json').read_text())['execution'],
        diagnostics='Primary: fixed price+volume with entry-review disabled, recovery disabled, or immediate old-HMM exit authority for recoveries (no handoff). All three main arms with50bp extra stop slippage. Exact disabled-review path versus A under all612 asset/era/frictions. Forecast diagnostics on primary actual decision contexts; full cost5/10/20bp x delay0/1 main replay. Retain previous original close-stop anchor.',
        assessment='Each12 era/friction cases: higher median Sharpe and lower-quartile CAGR than A, >=90% risky ETFs within1pp CAGR/2pp drawdown. Exclude BIL from pool acceptance. Weakest training-selected C by primary cumulative return each era; charts for all ETFs plus CPER/IWM nominated intervals and prior failures. No retrospective rule changes. Multiple selection and reused development eras disclosed.',
        code={p.relative_to(ROOT).as_posix():prior.study.digest(p) for p in (Path(__file__),ROOT/'src/systematic_trading/research/trained_review.py',ROOT/'tests/test_trained_review.py')})


def prepare():
    previous.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    p=clean(protocol());path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=p:raise ValueError('Protocol frozen')
    write(path,p);print('Frozen',prior.study.digest(path),flush=True)


def verified(require_fit=True):
    assert clean(protocol())==json.loads((OUT/'protocol.json').read_text());parents=previous.verified()
    if not require_fit:return parents
    fits=json.loads((OUT/'fits.json').read_text())
    assert json.loads((OUT/'fit-manifest.json').read_text())==dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json'))
    return (*parents,fits)


def fit_asset(job):
    symbol,market,selected=job;out={}
    for era,cutoff,*_ in ERAS:
        if era not in selected[symbol]:continue
        f,cl,rule=setup(symbol,era,market,selected,cutoff);start=max(252,len(f.days)-757);split=len(f.days)-252
        data,_=model.dataset(f,cl,rule,start);result={}
        control=model.simulate(f,cl,start=split-1,rule=rule);a=prior.stats.nav_stats(control['nav'][split-1:]);a['return']=control['nav'][-1]-1
        for kind in ('price','volume'):
            final,prefix=model.fit_family(data,kind,split);candidates=[]
            for margin in (0.,.25,.5):
                trial=dict(prefix,margin=margin);sim=model.simulate(f,cl,start=split-1,rule=rule,arm='stop',fit=trial)
                stats=prior.stats.nav_stats(sim['nav'][split-1:]);stats['return']=sim['nav'][-1]-1
                okay=stats['sharpe']>a['sharpe']+.01 and stats['return']>=a['return']-.005 and stats['maxdd']>=a['maxdd']-.01
                candidates.append(dict(margin=margin,passed=bool(okay),**stats))
            passed=[r for r in candidates if r['passed']]
            chosen=max(passed,key=lambda r:(r['sharpe'],r['return'],r['margin'])) if passed else None
            final.update(margin=chosen['margin'] if chosen else None,validation_control=a,validation_candidates=candidates)
            result[kind]=final
        out[era]=dict(training_end=str(f.days[-1]),training_start=str(f.days[start]),validation_start=str(f.days[split]),
            rows=len(data),matured_through=max(r['maturity'] for r in data) if data else None,models=result)
    return symbol,out


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Fits frozen')
    parents=verified(False);market,selected=parents[0],parents[5];result={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol,value in pool.map(fit_asset,[(s,{s:market[s]},{s:selected[s]}) for s in sorted(market)]):
            result[symbol]=value;write(WORK/'fit-progress.json',result);print('Fitted',symbol,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def forecast_metrics(scores,fit):
    from scipy.stats import spearmanr
    out={}
    for task in ('hold','recover'):
        a=[s for s in scores if s['task']==task]
        if not a:out[task]=dict(count=0);continue
        y=np.array([r['y'] for r in a]);out[task]=dict(count=len(a))
        for name in ('fixed','shadow','constant'):
            pred=np.tile(fit['models'][task]['beta'][0],(len(a),1)) if name=='constant' else np.array([r[name] for r in a])
            err=pred-y;out[task][name]=dict(loss=float(np.mean(err[:,0]**2+.25*err[:,1]**2)),
                ic=float(spearmanr(pred[:,0],y[:,0]).statistic) if np.std(pred[:,0])>1e-10 else None,
                predicted_return_units=float(pred[:,0].mean()),actual_return_units=float(y[:,0].mean()))
    return out


def evaluate_asset(job):
    symbol,market,selected,fits,oldrows=job;rows=[];diagnostics=[];charts={};checks=[];forecast=[]
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
            for arm,kind in [('stop','price'),('review','volume')]:
                sims[arm]=model.simulate(f,cl,arm=arm,fit=training['models'][kind],record=cost==5 and delay==0,**common)
            disabled=model.simulate(f,cl,arm='review',fit=training['models']['volume'],force_disabled=True,**common)
            checks.append(dict(symbol=symbol,era=era,cost=cost,delay=delay,control_error=abs(sims['baseline']['nav'][-1]-1-oldrows[era,cost,delay]['cumulative']),
                disabled_review_error=float(np.nanmax(abs(disabled['nav']-sims['baseline']['nav']))),ledger_error=max(base.ledger_error(f,s,start) for s in sims.values())))
            for arm,sim in sims.items():
                sim['slippage_factor']=.9995;r=base.metrics(f,cl,sim,start,symbol,era,arm,cost,delay)
                r.update(enabled=False if arm=='baseline' else training['models']['price' if arm=='stop' else 'volume']['margin'] is not None,
                    entry_invalidations=sum(e.get('exit_reason')=='entry_invalidated' for e in sim['episodes']),
                    handoffs=sum(e.get('handoff_index') is not None for e in sim['episodes']),
                    cancelled_recoveries=sum('recovery_open_cancelled' in e['reasons'] for e in sim.get('events',[])))
                rows.append(r)
                if cost==5 and delay==0:
                    a={}
                    for k in ('nav','stop','held','policy','review_signal','reset','hold_value','recover_value','reviewer_owned'):
                        v=np.asarray(sim.get(k,np.full(len(f.days),np.nan)),float).copy();v[:start]=np.nan;a[k]=v[context:]
                    a['nav']*=100
                    a.update(trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']],
                        fills=[dict(e,day=str(f.days[e['session']])) for e in sim['fills']],events=sim.get('events',[]))
                    chart['arms'][arm]=a
                    if arm!='baseline':
                        fit=training['models']['price' if arm=='stop' else 'volume'];scores=model.shadow_diagnostics(f,cl,sim,fit)
                        forecast.append(dict(symbol=symbol,era=era,arm=arm,**forecast_metrics(scores,fit)))
            if cost==5 and delay==0:
                options=[('entry_only',dict(arm='review',exit_review=False)),('recovery_only',dict(arm='review',entry_review=False)),
                    ('no_handoff',dict(arm='review',handoff=False))]+[(a+'_slip50',dict(arm=a,slip_bp=50)) for a in model.ARMS]
                for label,args in options:
                    fitted=training['models']['price' if args['arm']=='stop' else 'volume']
                    sim=model.simulate(f,cl,fit=fitted,**common,**args);sim['slippage_factor']=1-args.get('slip_bp',5)/10000
                    checks[-1]['ledger_error']=max(checks[-1]['ledger_error'],base.ledger_error(f,sim,start))
                    diagnostics.append(base.metrics(f,cl,sim,start,symbol,era,label,cost,delay))
                    chart.setdefault('diagnostics',{})[label]=dict(nav=sim['nav'][context:]*100)
        charts[symbol+'_'+era]=chart
    return rows,diagnostics,charts,checks,forecast


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Evaluation frozen')
    parents=verified();market,selected,fits=parents[0],parents[5],parents[-1]
    rows=[];diagnostics=[];charts={};checks=[];forecast=[];jobs=[]
    old=json.loads((previous.OUT/'asset-results.json').read_text())
    for s in sorted(market):
        lookup={(r['era'],r['cost_bp'],r['delay']):r for r in old if r['symbol']==s and r['arm']=='baseline'}
        jobs.append((s,{s:market[s]},{s:selected[s]},{s:fits[s]},lookup))
    with ProcessPoolExecutor(max_workers=2) as pool:
        for rr,dd,cc,vv,ff in pool.map(evaluate_asset,jobs):
            rows+=rr;diagnostics+=dd;charts.update(cc);checks+=vv;forecast+=ff;print('Evaluated',rr[0]['symbol'],flush=True)
    validation=dict(control_cases=len(checks),asset_cases=len(rows),max_control_error=max(c['control_error'] for c in checks),
        max_disabled_review_error=max(c['disabled_review_error'] for c in checks),max_independent_ledger_error=max(c['ledger_error'] for c in checks))
    write(WORK/'checks.json',checks);assert max(validation[k] for k in ('max_control_error','max_disabled_review_error','max_independent_ledger_error'))<1e-11,validation
    write(OUT/'asset-results.json',rows);write(OUT/'diagnostics.json',diagnostics);write(OUT/'forecast-diagnostics.json',forecast)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    validation['chart_sha256']=prior.study.digest(OUT/'chart-data.json.gz');write(OUT/'validation.json',validation)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[parser.parse_args().stage]()
