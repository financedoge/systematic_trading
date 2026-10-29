"""Causal single-ETF hard-reset experiment; no portfolio stage."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_online_policy as previous
from systematic_trading.research import reset_policy as model

prior=previous.prior
OUT=ROOT/'research/reset-policy-20261026-v1'
WORK=ROOT/'var/research/reset-policy-20261026-v1'
ERAS,FRICTIONS=prior.ERAS,prior.FRICTIONS
write,clean=prior.write,prior.clean


def protocol():
    previous.verified()
    return dict(identity=OUT.name,version=model.VERSION,arms=list(model.ARMS),
        parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        initial_sha256=prior.study.digest(previous.OUT/'initial.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],
        question='Does deleting learned policy evidence after loss/drawdown or a confirmed HMM transition outperform continuous forgetting?',
        scope='Single ETFs/full supported pool only. No portfolio/overlay/rebalancing. Frozen parent market fits and nine-policy grid retained. This is NOT full HMM/Kalman refitting or a structural changepoint detector.',
        continuous='Exact parent bayes arm: training evidence cap4, daily decay2^(-1/126), Normal(0,1/4) payoff prior, Gaussian unitvariance likelihood over completed shadowtrade netROI/(sigma*sqrt(duration)) clipped[-3,3]. Separate Beta win diagnostic. Scores mean-.25sd, switchmargin.05. Candidate needs one fresh outcome. No warning acceleration.',
        loss_reset='Actual3rd/4th consecutive netloss, firstmarked loss<-tau perposition, realizedloss<-tau, or account DD since last reset >=max(.10,2tau) triggers hardreset with20session cooldown. tau is parent trainingwinner SD with5winnerminimum or unavailable; if missing use10% DD, no sigma proxy. Ordinary losingstop alone does not reset. On reset N=S=W=fresh=0 for all9policy posteriors, retain proper neutral priors and current policy until new evidence supports changing. Lossstreak and accountpeak reset; pendingorders/protection/currentposition are preserved.',
        freshness='After reset at close r, admit only shadow trades whose entry fill index>r; discard entire straddling trades and their costs/outcomes. Same-close outcomes are discarded. No hindsight split or imported training payoff. Trading continues under current policy while beliefs are uninformative; not a health pause. A new fixed policy does not force rearming.',
        regime_reset='Same as loss_reset plus fastHMM state transition event. J_t(i,j) proportional alpha_(t-1)(i) A(i,j) L_t(j); q_t=1-trace(J_t). Flag q>=.8 and max alpha_t>=.9, then require same highestprob state>=.9 for3 consecutive closes includingflagday. Trigger on3rd close; no retrospective action. Additional HMM-trigger cooldown63sessions; shared anyreset cooldown20sessions. HMM from existing ETF training fit, observed filtered fast slope/sigma even for Gaussian-slope selected policies. Ordinary state transitions do not prove structural parameter drift; probabilities are not calibrated confidence.',
        protections='Reset changes policy beliefs only. Old adopted stop cannot loosen; current stop tested before nextclose tightening. Actual warnings are not additionally counted as payoff observations. Close decisions execute nextopen plusdelay0/1, binding pendingorders. Full entry allocation or cash0; reset does not force liquidation or a new trade.',
        assessment='Same fresh-start eras and6frictions as parent. Three main algorithms; frozen pre-learning policy included as numeric comparator. Primary regime_reset5bp,nextopen. Both eras: medianSharpe/lowerquartileCAGR improve and>=90%risky ETFs within1ppCAGR/2ppDD of continuous; also compare frozen. State effectivecount, reset count, discarded straddling outcomes, no-new-evidence sessions, costs/turnover/yearly outcomes, weakest risky netreturn excludingBIL. No evaluation-based tuning. All dates already inspected development evidence.',
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in
              (Path(__file__),ROOT/'src/systematic_trading/research/reset_policy.py',ROOT/'tests/test_reset_policy.py')})


def prepare():
    OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True,parents=True)
    p=clean(protocol());path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=p:raise ValueError('Frozen protocol changed')
    write(path,p);print('Frozen',prior.study.digest(path),flush=True)


def verified():
    if clean(protocol())!=json.loads((OUT/'protocol.json').read_text()):raise ValueError('Code/input changed')
    return previous.verified()


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Preserve completed evaluation')
    fits,calibration,initial=verified();rows=[];charts={};control_error=ledger_error=0.;checks=0
    for symbol in sorted(fits):
        full=prior.model.Features.build(prior.study.load_asset(symbol))
        for era,_,first,last in ERAS:
            fit=fits[symbol][era]
            if not fit['available']:continue
            f=full.truncated(last);f.hmm_models=fit['hmms'];p=fit['selected']['selected']['parameters']
            cl=prior.model.classify(f,p);lo=int(np.searchsorted(f.days,np.datetime64(first)));start=lo-1
            seed=initial[symbol][era]
            if seed['training_end']>=first:raise ValueError('Training leakage')
            context=int(np.searchsorted(f.days,np.datetime64('2021-01-01' if era=='late' else first)))
            regimes=model.regime_signals(f)
            chart=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],
                evaluation_start=first,parameters=p,grid=model.grid(p),calibration=calibration[symbol][era],
                fast_up=cl['fast_probability'][context:,2],slow_down=cl['slow_probability'][context:,0],hmm_change=regimes['change'][context:],hmm_confirmed=regimes['confirmed'][context:],arms={})
            for cost,delay in FRICTIONS:
                shadows=[prior.model.simulate(f,model.classification(cl,q),start=start,cost_bp=cost,delay=delay) for q in model.grid(p)]
                old=previous.model.simulate(f,cl,seed['states'],calibration[symbol][era],start=start,arm='bayes',cost_bp=cost,delay=delay,shadows=shadows)
                frozen=prior.stats.nav_stats(shadows[0]['nav'][start:])
                for arm in model.ARMS:
                    sim=model.simulate(f,cl,seed['states'],calibration[symbol][era],start=start,arm=arm,cost_bp=cost,delay=delay,shadows=shadows,regimes=regimes)
                    if arm=='continuous':
                        control_error=max(control_error,float(np.nanmax(np.abs(sim['nav']-old['nav']))));checks+=1
                    cash=1.;units=0.;fills={z['session']:z for z in sim['fills']}
                    for t in range(start,len(f.days)):
                        if t in fills:
                            z=fills[t];sgn=1 if z['side']=='buy' else -1
                            cash-=sgn*z['units']*z['price']+z['fee'];units+=sgn*z['units']
                        ledger_error=max(ledger_error,abs(sim['nav'][t]-cash-units*f.close[t]))
                    nav=sim['nav'][start:];stats=prior.stats.nav_stats(nav);years=(len(nav)-1)/252
                    closed=[e for e in sim['episodes'] if e['exit_index'] is not None]
                    yearly={}
                    for year in sorted(set(str(d)[:4] for d in f.days[lo:])):
                        ix=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>=lo))
                        yearly[year]=float(sim['nav'][ix[-1]]/sim['nav'][ix[0]-1]-1)
                    rows.append(dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**stats,
                        cumulative=float(nav[-1]/nav[0]-1),
                        closed_trades=len(closed),wins=sum(e['net_return']>0 for e in closed),
                        exposure=float(np.mean(sim['exposure'][lo:])),pause_sessions=0,
                        turnover_annual=sum(z['units']*z['price']/sim['nav'][max(start,z['session']-1)] for z in sim['fills'])/years,
                        cost_bp_annual=sum(z['fee']/sim['nav'][max(start,z['session']-1)] for z in sim['fills'])/years*10000,
                        changes=sum(e['changed'] for e in sim['events']),accelerations=sum(e['accelerated'] for e in sim['events']),
                        threshold=sim['threshold'],yearly=yearly,reset_count=sim['reset_count'],rejected_outcomes=sim['rejected_outcomes'],empty_evidence_sessions=int(sim['empty_evidence'][lo:].sum()),frozen_cumulative=float(shadows[0]['nav'][-1]-1),frozen_metrics=frozen,buyhold=float(f.close[-1]/f.open[lo]/(1+cost/10000)-1)))
                    if cost==5 and delay==0:
                        def series(a):
                            a=np.asarray(a,float).copy();a[:lo]=np.nan;return a[context:]
                        trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']]
                        chart['arms'][arm]={k:series(sim[k]) for k in ('nav','stop','desired','policy','entry_threshold','exit_threshold','distance','posterior_mean','win_probability','effective_count','reset_age','empty_evidence')}
                        chart['arms'][arm].update(trades=trades,events=sim['events']);chart['arms'][arm]['nav']*=100
            charts[f'{symbol}_{era}']=chart
        print('Evaluated',symbol,flush=True)
    if control_error>1e-10 or ledger_error>1e-10:raise ValueError('Ledger/control error')
    write(OUT/'asset-results.json',rows)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(OUT/'validation.json',dict(control_cases=checks,max_control_nav_error=control_error,
        max_independent_ledger_error=ledger_error,asset_cases=len(rows),chart_sha256=prior.study.digest(OUT/'chart-data.json.gz')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','evaluate'))
    {'prepare':prepare,'evaluate':evaluate}[p.parse_args().stage]()
