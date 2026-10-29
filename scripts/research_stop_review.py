"""Frozen full-pool research of standing stops and reversed-decision learning."""
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
import research_entry_value as previous
from systematic_trading.research import stop_review as model
prior=previous.prior
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/stop-review-20261027-v1'
WORK=ROOT/'var/research/stop-review-20261027-v1'
write,clean=previous.write,previous.clean


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Full supported single-ETF pool; B from entry-value is baseline. Already-inspected development eras; no fresh holdout or overlay. No broker/runtime changes.',
        arms=dict(baseline='B0 exact frozen symmetric-HMM fixed-policy B. Close protection then next open.',
            stop='B1 same policy and stop levels, standing OHLC stop with gap-aware fill and 5bp additional stop slippage.',
            review='B2 B1 plus near-exit recovery and three-policy discounted shadow learning; reversed decisions/large losses/3-4 loss streak reset evidence to recent21 observed shadow returns.'),
        execution='Signal close t fills open t+1+delay; delay0/1. Standing stop is active independently of signal delay, including immediately after opening buy. Low<=previous active stop: sell min(open,stop)*(1-stop_slip), plus normal per-side fee. Stop set from completed closes only; today high cannot ratchet today stop. Opening scheduled exit precedes intraday test. Protective fill cancels stale pending exits. Never rebuy on sale day. Fractional shares, cash interest0, terminal mark. Gap-through uses open but intraday discontinuity/market impact not observable from daily bars.',
        recovery='For 1..10 sessions after any exit, exit_price*(1+2fee)<=close<=exit_price+ATR_at_exit_signal; pUp>=.55,pDown<=.35; fast slope positive or improving; close>previous close and open; close location>=.6; three-session signed volume pressure>=0. All conditions at completed close; next executable open can gap beyond band. Recovery bypasses normal rearm/entry threshold, not future knowledge. ATR is Wilder20 true range; pressure=sum(sign(delta close)*rawVolume)/sum(rawVolume).',
        policies='Anchored per-ETF B policy, faster and more patient. Entry/down/aligned-down thresholds delta(0,-.05,+.05), clipped respectively [.5,.9]/[.45,.9]/[.65,.95]; stop multipliers scale(1,.75,1.25); selected thesis consecutive count delta(0,-1,+1), floor1. HMM, Kalman, sigma and thesis probability floor frozen. Held position retains its entry policy; stop never loosens.',
        learning='Three independent fixed-policy recovery-enabled shadow strategies, same costs/delay/execution. Their fully observed daily net NAV returns update even while actual strategy cash. Normalize by training daily sigma. rho=2^(-1/63), n=rho*n+1,s_j=rho*s_j+r_j/sigma, mu=s/(4+n). Neutral prior precision4, initial training discounted evidence capped20. Policy changes while flat and no pending order, dwell5 sessions unless warning; challenger mean must exceed current by .02. Equal candidate counts make the shared uncertainty penalty cancel in ranking. This is shrinkage/discounted working-Gaussian evidence, not calibrated independent posterior or actual market regime detection.',
        warnings='Negative closed trade <=10 sessions: quick_failed_buy; realized return < -max(training winner std,2fee): large_loss; consecutive losses count3 or4: loss_streak; qualified near-exit recovery: exit_reversed. Reset replaces learned evidence with last21 completed evaluation shadow daily returns (or available shorter history), weighted same rho. Proper prior remains. No forced switch/no permanent pause. Signals arising during holdings update evidence; policy change waits until flat.',
        training='Frozen B market/policy fits per ETF and era. At cutoff replay last756 training sessions of B1 and three fixed recovery policies using full-training models: fitted in-sample calibration, no nested validation. Seed from training shadow daily returns/sigma with cap20. Large-loss threshold sample std of positive completed B1 trade returns if >=3 wins; otherwise sigma*sqrt21. Fit at5bp/delay0; replay unchanged under other frictions. No performance-based selection among new rule candidates or evaluation tuning.',
        diagnostics='Full frictions: fixed recovery without learning, adaptive learning without warning reset. Primary only: low-touch then same-day-close (conditional unverified auction execution), stop slippage20/50bp, conservative min(open,stop,close) fill. These are attribution/stress diagnostics, not additional main algorithms. Do not treat daily bar close as guaranteed executable after observing its full low. Additional delay affects signal orders, not an already-standing protective order.',
        metrics='Net return, CAGR, Sharpe zero cash rate, Calmar, maxDD, realized trade returns, close exposure and any-session exposure, turnover, fees and modeled stop slippage; annual outcomes, correlation/beta/annual arithmetic regression intercept/HAC5, raw-state executable five-session Spearman IC. IC is identical across main arms because market detector is unchanged. Overlapping/correlated inputs and repeated inspections preclude significance claims.',
        assessment='BIL shown but excluded from pool medians. Require higher median Sharpe and lower-quartile CAGR and >=90% ETF preservation within1pp CAGR/2pp drawdown against B0, in each of12 era/friction cases. Compare B2 vs B1 too. Weakest B2 by primary cumulative return each era gets chart, plus user CPER2025-03-04..09-04 and IWM2024-07-01..12-01. No annual cost ceiling.',
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in (Path(__file__),ROOT/'src/systematic_trading/research/stop_review.py',ROOT/'tests/test_stop_review.py')})


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


def setup(symbol,era,market,selected,last):
    f=model.Features.build(prior.study.load_asset(symbol)).truncated(last);f.hmm_models=market[symbol][era]['hmms']
    p=market[symbol][era]['selected']['selected']['parameters'];q=selected[symbol][era]
    cl=previous.model.classification(f,p,q['exit_rule'],q['hmm']['model'])
    return f,cl,q['exit_rule']


def fit_asset(job):
    symbol,market,selected=job;out={}
    for era,cutoff,*_ in ERAS:
        if era not in selected[symbol]:continue
        f,cl,rule=setup(symbol,era,market,selected,cutoff);start=max(252,len(f.days)-757)
        shadows=model.shadow_returns(f,cl,rule,start=start)
        sim=model.simulate(f,cl,start=start,rule=rule)
        wins=[e['net_return'] for e in sim['episodes'] if e['exit_index'] is not None and e['net_return']>0]
        tau=float(np.std(wins,ddof=1)) if len(wins)>=3 else float(cl['sigma']*np.sqrt(21))
        out[era]=dict(training_end=str(f.days[-1]),start=str(f.days[start]),seed=model.seed_from_returns(shadows/cl['sigma'],start),
            loss_threshold=tau,wins=len(wins),fallback=len(wins)<3,parameters=[c['parameters'] for c in model.policies(cl,rule)])
    return symbol,out


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Frozen fits exist')
    market,_,_,_,_,selected=verified(False);result={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol,value in pool.map(fit_asset,[(s,{s:market[s]},{s:selected[s]}) for s in sorted(market)]):
            result[symbol]=value;write(WORK/'fit-progress.json',result);print('Fitted',symbol,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def metrics(f,cl,sim,start,symbol,era,arm,cost,delay):
    nav=sim['nav'][start:];r=nav[1:]/nav[:-1]-1;ar=f.close[start+1:]/f.close[start:-1]-1;years=len(r)/252
    closed=[e for e in sim['episodes'] if e['exit_index'] is not None];q=[e for e in closed if e.get('entry_reason')=='exit_review']
    yearly={}
    for year in sorted(set(str(d)[:4] for d in f.days[start+1:])):
        ix=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>start))
        yearly[year]=float(sim['nav'][ix[-1]]/sim['nav'][ix[0]-1]-1)
    slip=sum(e['units']*(e['price']/sim.get('slippage_factor',1)-e['price'])/sim['nav'][max(start,e['session']-1)] for e in sim['fills'] if e.get('phase') in ('intraday_stop','open_gap','conditional_close','conservative_stop'))
    return dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**prior.stats.nav_stats(nav),cumulative=float(nav[-1]-1),
        **previous.model.parent.dependence(r,ar),ic5=previous.model.parent.ic(f,cl,start,delay),closed_trades=len(closed),wins=sum(e['net_return']>0 for e in closed),
        exposure=float(sim['exposure'][start+1:].mean()),any_session_exposure=float(sim.get('invested_session',np.r_[False,sim['held'][:-1]]|sim['held'])[start+1:].mean()),
        yearly=yearly,turnover_annual=sum(e['units']*e['price']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years,
        cost_bp_annual=sum(e['fee']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years*10000,stop_slippage_bp_annual=slip/years*10000,
        recovery_closed=len(q),recovery_wins=sum(e['net_return']>0 for e in q),recovery_mean=float(np.mean([e['net_return'] for e in q])) if q else None,
        warnings=sum(bool(e['reasons']) for e in sim.get('events',[])),resets=sum(e['reset'] for e in sim.get('events',[])),changes=sum(e['changed'] for e in sim.get('events',[])),
        stop_fills=sum(e.get('phase') in ('intraday_stop','open_gap') for e in sim['fills']),buyhold=float(f.close[-1]/f.close[start]-1))


def ledger_error(f,sim,start):
    cash=1.;units=0.;cursor=0;err=0.
    for t in range(start,len(f.days)):
        while cursor<len(sim['fills']) and sim['fills'][cursor]['session']==t:
            e=sim['fills'][cursor];sign=1 if e['side']=='buy' else -1
            cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units'];cursor+=1
            assert cash>=-1e-11 and units>=-1e-11
        err=max(err,abs(sim['nav'][t]-cash-units*f.close[t]))
    assert cursor==len(sim['fills'])
    return err


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
            normalized_slope=cl['fast_slope'][context:]/cl['sigma'],atr=q['atr'][context:],pressure=q['pressure'][context:],arms={})
        for cost,delay in FRICTIONS:
            common=dict(start=start,cost_bp=cost,delay=delay,rule=rule,seed=training['seed'],loss_threshold=training['loss_threshold'])
            shadows=model.shadow_returns(f,cl,rule,start=start,cost_bp=cost,delay=delay)
            sims=dict(baseline=model.simulate(f,cl,mode='baseline',**common),stop=model.simulate(f,cl,**common),
                review=model.simulate(f,cl,recovery=True,adaptive=True,shadows=shadows,**common))
            close=model.simulate(f,cl,mode='close_next',**common)
            checks.append(dict(symbol=symbol,era=era,cost=cost,delay=delay,
                control_error=abs(sims['baseline']['nav'][-1]-1-oldrows[era,cost,delay]['cumulative']),
                close_engine_error=float(np.nanmax(abs(close['nav']-sims['baseline']['nav']))),
                ledger_error=max(ledger_error(f,s,start) for s in sims.values())))
            for arm,sim in sims.items():
                sim['slippage_factor']=.9995
                rows.append(metrics(f,cl,sim,start,symbol,era,arm,cost,delay))
                if cost==5 and delay==0:
                    def series(a):
                        a=np.asarray(a,float).copy();a[:start]=np.nan;return a[context:]
                    a={k:series(sim.get(k,np.zeros(len(f.days)))) for k in ('nav','stop','held','policy','review_signal','reset')};a['nav']*=100
                    a.update(trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']],
                        fills=[dict(e,day=str(f.days[e['session']])) for e in sim['fills']],events=sim.get('events',[]))
                    chart['arms'][arm]=a
            options=[('recovery_fixed',dict(recovery=True)),('learning_no_reset',dict(recovery=True,adaptive=True,reset=False,shadows=shadows))]
            if cost==5 and delay==0:options += [('conditional_touch_close',dict(mode='touch_close')),('stop_slip20',dict(slip_bp=20)),('stop_slip50',dict(slip_bp=50)),('conservative_stop',dict(mode='stop_close_stress'))]
            for label,args in options:
                sim=model.simulate(f,cl,**common,**args);sim['slippage_factor']=1-args.get('slip_bp',5)/10000
                checks[-1]['ledger_error']=max(checks[-1]['ledger_error'],ledger_error(f,sim,start))
                diagnostics.append(metrics(f,cl,sim,start,symbol,era,label,cost,delay))
                if cost==5 and delay==0:
                    chart.setdefault('diagnostics',{})[label]=dict(nav=series(sim['nav'])*100,
                        trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']])
        charts[symbol+'_'+era]=chart
    return rows,diagnostics,charts,checks


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Frozen evaluation exists')
    market,_,_,_,_,selected,fits=verified();rows=[];diagnostics=[];charts={};checks=[]
    old=json.loads((previous.OUT/'asset-results.json').read_text());jobs=[]
    for s in sorted(market):
        lookup={(r['era'],r['cost_bp'],r['delay']):r for r in old if r['symbol']==s and r['arm']=='hmm'}
        jobs.append((s,{s:market[s]},{s:selected[s]},{s:fits[s]},lookup))
    with ProcessPoolExecutor(max_workers=2) as pool:
        for rr,dd,cc,vv in pool.map(evaluate_asset,jobs):
            rows+=rr;diagnostics+=dd;charts.update(cc);checks+=vv;print('Evaluated',rr[0]['symbol'],flush=True)
    validation=dict(control_cases=len(checks),asset_cases=len(rows),max_control_error=max(c['control_error'] for c in checks),
        max_close_engine_error=max(c['close_engine_error'] for c in checks),max_independent_ledger_error=max(c['ledger_error'] for c in checks))
    write(WORK/'checks.json',checks)
    assert max(validation[k] for k in ('max_control_error','max_close_engine_error','max_independent_ledger_error'))<1e-11,validation
    write(OUT/'asset-results.json',rows);write(OUT/'diagnostics.json',diagnostics)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    validation['chart_sha256']=prior.study.digest(OUT/'chart-data.json.gz');write(OUT/'validation.json',validation)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[parser.parse_args().stage]()
