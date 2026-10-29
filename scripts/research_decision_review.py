"""Frozen, full-pool independent decision review study."""
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
import research_stop_review as previous
from systematic_trading.research import decision_review as model
prior=previous.prior
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/decision-review-20261028-v1'
WORK=ROOT/'var/research/decision-review-20261028-v1'
write,clean,setup=previous.write,previous.clean,previous.setup


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Single ETF full supported 52 late/50 early, same published adjusted OHLC and raw volume. Repeatedly inspected development periods, not untouched OOS. No overlay, promotion or execution authority changes.',
        arms=dict(baseline='A: frozen B standing protection (prior B1), exact matched control.',
            stop='B: A plus independent entry/exit review using fixed per-ETF price/volume likelihood model.',
            review='C: B plus established/recent predictive-model averaging and warning-driven forgetting.'),
        features='Clip each coordinate [-4,4]. Six jointly modeled features: daily log return/sigma; three-day log return/(sigma sqrt3); 2 close-location-1; three-day signed raw volume pressure; log(current raw volume / mean previous20 volume); change in daily low / prior ATR20. Sigma frozen per ETF training. Shared Gaussian covariance shrunk50% toward training diagonal plus .05 I. Correlations modeled jointly; remaining serial dependence not calibrated away.',
        fit='Per ETF/era latest at most756 matured origins after warmup252. Label positive if log(O[t+6]/O[t+1])>0, value scaled by sigma sqrt5. Training origins require t+6<=cutoff. Gaussian feature means per class, shared within-class covariance, empirical class priors and conditional return means. No net-return threshold search; log4 evidence threshold and other constants predeclared. This is fitted training, not nested validation.',
        evidence='p=weighted sum of expert conditional up probabilities; pi=weighted class base rate; ell=clip(logit(p)-logit(pi),-2,2). Gup=max(0,Gup+ell-.1) while watching exit; Gdown=max(0,Gdown-ell-.1) while held. G resets at fills. This is CUSUM-style accumulation of dependent forecast evidence, not a valid independent-observation likelihood test, calibrated 80% confidence, or guaranteed false-alarm control.',
        entry_review='Additional exit when Gdown>=log4, p<.5, expected5day log return<0, close<previousclose and close<=running prior peak-.5 current ATR. Next open+delay. Original HMM/thesis and protection exits remain. This review challenges an upward thesis independent of HMM probability.',
        exit_review='Watch1..20 sessions after exit. Gup>=log4,p>.5, predicted5day log return>2fee+stop_slip; exitfill*(1+2fee)<=close<=exitfill+1.5 prior-session ATR at exit; close>open and previousclose; close location>=.6; signedvolume>=0. No HMM gate. Recovery order at next open+delay, cancelled if opening price outside [exitfill,exitfill+1.5ATR]. No same-day recovery. Full position and inherited B risk distances; no relaxed stop.',
        adaptive='Established Gaussian model frozen. Recent expert starts with same moments scaled to effective40 observations; updates only newly matured five-session outcomes, half-life63. Predict then observe: store both forecasts and origin weights; at label maturity log weights=.98 log weights+clip(centered Bernoulli logscore,-2,2)/5, normalize. Clip scored p [.01,.99]. Divide5 tempers overlapping labels but is not proof of independence. Latest mixture value uses conditional class mean returns. Scores update in cash too. No HMM/Kalman refit and no BOCPD claim.',
        warnings='Large closed loss beyond prior study per-ETF training winner dispersion threshold, 3rd/4th consecutive loss, entry invalidation exit or qualified exit reversal: weights proportional sqrt(weights); recent-model half-life10 for next21 sessions. No automatic switch; no permanent trading halt. Opening-price cancellation is logged but not a refit alarm. Stops never loosen.',
        execution=json.loads((previous.OUT/'protocol.json').read_text())['execution'],
        diagnostics='Exact disabled-review path versus A across612 cases; primary entry-only, exit-only, C without warning acceleration; all three at50bp additional stop slippage. Six main fee/delay combinations per era. Retain prior original close-stop B0 metrics as separate historical anchor.',
        assessment='Against A in each12 era/friction cases: higher median Sharpe and lower-quartile CAGR; >=90% ETFs within1pp CAGR/2pp maxDD. Exclude BIL from acceptance. Show chronology, net outcomes, costs, turnover, dependence, shared raw-HMM IC and new forecast IC/Brier/logscore. These are descriptive repeated development tests. Weakest C by primary cumulative return per era plus CPER2025-03-04..09-04 and IWM2024-07-01..12-01.',
        sources=['https://doi.org/10.1093/biomet/41.1-2.100','https://pubmed.ncbi.nlm.nih.gov/20607102/','https://arxiv.org/abs/0710.3742','https://proceedings.mlr.press/v202/altamirano23a.html'],
        code={p.relative_to(ROOT).as_posix():prior.study.digest(p) for p in (Path(__file__),ROOT/'src/systematic_trading/research/decision_review.py',ROOT/'tests/test_decision_review.py')})


def prepare():
    previous.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    p=clean(protocol());target=OUT/'protocol.json'
    if target.exists() and json.loads(target.read_text())!=p:raise ValueError('Protocol frozen')
    write(target,p);print('Frozen',prior.study.digest(target),flush=True)


def verified(require_fit=True):
    assert clean(protocol())==json.loads((OUT/'protocol.json').read_text())
    parents=previous.verified()
    if not require_fit:return parents
    fits=json.loads((OUT/'fits.json').read_text())
    assert json.loads((OUT/'fit-manifest.json').read_text())==dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json'))
    return (*parents,fits)


def fit_asset(job):
    symbol,market,selected,oldfits=job;out={}
    for era,cutoff,*_ in ERAS:
        if era not in selected[symbol]:continue
        f,cl,rule=setup(symbol,era,market,selected,cutoff)
        out[era]=dict(seed=model.fit(f,cl['sigma']),loss_threshold=oldfits[symbol][era]['loss_threshold'])
    return symbol,out


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Fits frozen')
    market,_,_,_,_,selected,oldfits=verified(False);result={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for s,v in pool.map(fit_asset,[(s,{s:market[s]},{s:selected[s]},{s:oldfits[s]}) for s in sorted(market)]):
            result[s]=v;print('Fitted',s,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def metrics(f,cl,sim,start,symbol,era,arm,cost,delay):
    from scipy.stats import spearmanr
    r=previous.metrics(f,cl,sim,start,symbol,era,arm,cost,delay)
    scores=sim.get('scores',[])
    r.update(entry_invalidations=sum(e.get('exit_reason')=='entry_invalidated' for e in sim['episodes']),
        cancelled_recoveries=sum('recovery_open_cancelled' in e['reasons'] for e in sim.get('events',[])))
    if scores:
        y=np.array([s['label'] for s in scores]);p=np.clip([s['mixture_p'] for s in scores],.01,.99)
        ix=np.array([s['origin'] for s in scores]);returns=f.open[ix+6]/f.open[ix+1]-1
        r.update(forecast_brier=float(np.mean((p-y)**2)),forecast_logscore=float(np.mean(y*np.log(p)+(1-y)*np.log(1-p))),
            forecast_ic=float(spearmanr(p,returns).statistic) if np.std(p)>0 else None,
            recent_weight_mean=float(np.nanmean(sim['recent_weight'][start:])))
    else:r.update(forecast_brier=None,forecast_logscore=None,forecast_ic=None,recent_weight_mean=None)
    return r


def evaluate_asset(job):
    symbol,market,selected,fits,oldrows=job;rows=[];diagnostics=[];charts={};checks=[]
    for era,_,first,last in ERAS:
        if era not in selected[symbol]:continue
        f,cl,rule=setup(symbol,era,market,selected,last);training=fits[symbol][era];start=int(np.searchsorted(f.days,np.datetime64(first)))-1
        context=max(0,start-1);q=model.activity(f)
        chart=dict(days=f.days[context:].astype(str),evaluation_start=first,selection=selected[symbol][era],training=training,
            **{k:getattr(f,k)[context:] for k in ('open','high','low','close','volume')},parameters=cl['parameters'],
            slow_up=cl['slow_probability'][context:,2],slow_down=cl['slow_probability'][context:,0],
            fast_up=cl['fast_probability'][context:,2],fast_down=cl['fast_probability'][context:,0],neutral=cl['fast_probability'][context:,1],
            atr=q['atr'][context:],pressure=q['pressure'][context:],arms={})
        for cost,delay in FRICTIONS:
            common=dict(start=start,cost_bp=cost,delay=delay,rule=rule,**training)
            sims={a:model.simulate(f,cl,arm=a,**common) for a in model.ARMS}
            disabled=model.simulate(f,cl,arm='stop',entry_review=False,exit_review=False,**common)
            checks.append(dict(symbol=symbol,era=era,cost=cost,delay=delay,
                control_error=abs(sims['baseline']['nav'][-1]-1-oldrows[era,cost,delay]['cumulative']),
                disabled_review_error=float(np.nanmax(abs(disabled['nav']-sims['baseline']['nav']))),
                ledger_error=max(previous.ledger_error(f,s,start) for s in sims.values())))
            def export(sim):
                a={}
                for k in ('nav','stop','held','policy','review_signal','reset','probability','forecast','evidence','recent_weight','up_evidence','down_evidence'):
                    v=np.asarray(sim.get(k,np.full(len(f.days),np.nan)),float).copy();v[:start]=np.nan;a[k]=v[context:]
                a['nav']*=100
                a.update(trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']],
                    fills=[dict(e,day=str(f.days[e['session']])) for e in sim['fills']],events=sim.get('events',[]))
                return a
            for arm,sim in sims.items():
                sim['slippage_factor']=.9995;rows.append(metrics(f,cl,sim,start,symbol,era,arm,cost,delay))
                if cost==5 and delay==0:chart['arms'][arm]=export(sim)
            if cost==5 and delay==0:
                options=[('entry_only',dict(arm='stop',exit_review=False)),('exit_only',dict(arm='stop',entry_review=False)),
                    ('no_warning',dict(arm='review',warning_updates=False))]+[(a+'_slip50',dict(arm=a,slip_bp=50)) for a in model.ARMS]
                for label,args in options:
                    sim=model.simulate(f,cl,**common,**args);sim['slippage_factor']=1-args.get('slip_bp',5)/10000
                    checks[-1]['ledger_error']=max(checks[-1]['ledger_error'],previous.ledger_error(f,sim,start))
                    diagnostics.append(metrics(f,cl,sim,start,symbol,era,label,cost,delay))
                    chart.setdefault('diagnostics',{})[label]=dict(nav=sim['nav'][context:]*100)
        charts[symbol+'_'+era]=chart
    return rows,diagnostics,charts,checks


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Evaluation frozen')
    market,_,_,_,_,selected,_,fits=verified();rows=[];diagnostics=[];charts={};checks=[]
    old=json.loads((previous.OUT/'asset-results.json').read_text());jobs=[]
    for s in sorted(market):
        lookup={(r['era'],r['cost_bp'],r['delay']):r for r in old if r['symbol']==s and r['arm']=='stop'}
        jobs.append((s,{s:market[s]},{s:selected[s]},{s:fits[s]},lookup))
    with ProcessPoolExecutor(max_workers=2) as pool:
        for rr,dd,cc,vv in pool.map(evaluate_asset,jobs):
            rows+=rr;diagnostics+=dd;charts.update(cc);checks+=vv;print('Evaluated',rr[0]['symbol'],flush=True)
    validation=dict(control_cases=len(checks),asset_cases=len(rows),max_control_error=max(c['control_error'] for c in checks),
        max_disabled_review_error=max(c['disabled_review_error'] for c in checks),max_independent_ledger_error=max(c['ledger_error'] for c in checks))
    write(WORK/'checks.json',checks)
    assert max(validation[k] for k in ('max_control_error','max_disabled_review_error','max_independent_ledger_error'))<1e-11,validation
    write(OUT/'asset-results.json',rows);write(OUT/'diagnostics.json',diagnostics)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    validation['chart_sha256']=prior.study.digest(OUT/'chart-data.json.gz');write(OUT/'validation.json',validation)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[parser.parse_args().stage]()
