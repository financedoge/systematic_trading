"""Single-ETF online policy learning. Deliberately no portfolio stage."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_loss_feedback as previous
from systematic_trading.research import online_policy as model

prior=previous.prior
OUT=ROOT/'research/online-policy-20261026-v1'
WORK=ROOT/'var/research/online-policy-20261026-v1'
ERAS,FRICTIONS=prior.ERAS,prior.FRICTIONS
write,clean=prior.write,prior.clean


def protocol():
    previous.verified()
    return dict(identity=OUT.name,version=model.VERSION,arms=list(model.ARMS),
        parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],
        scope='Single ETF only, full supported pool. Operator explicitly defers ALL portfolio/overlay/rebalancing tests. Research only.',
        question='Can continuously learned trading parameters replace lengthy health pauses while preserving profitable ETFs?',
        fixed='Existing per-ETF training-selected market policy; flat funded era start, no health pause.',
        grid='Nine candidates around ETF-selected policy: entry delta -0.1/0/+0.1, protection multiplier0.5/1/1.5; baseline index0. Entry clipped[.5,.9]. Down exit shifted +.2*(multiplier-1), clipped[.45,.9]; aligned context exit .85 shifted similarly clipped[.65,.95]. Initial/trailing wide/tight distances multiply. Reset remains.5. This learns trading thresholds, not latent HMM/Kalman parameters or independently fitted range geometry.',
        learning='Each candidate runs a causal independent shadow ledger. At completed exit only, y=clip(netROI/(training daily sigma*sqrt(held sessions)),-3,3). Per-policy Normal prior mu~N(0,1/4), powered unit-variance Gaussian likelihood: N,S,W decay daily rho=2^(-1/126), then N+=1,S+=y,W+=I(win). Posterior mu=S/(4+N),sd=(4+N)^(-.5). Beta(1+W,1+N-W) win probability is diagnostic only. No pooling of nine correlated policy outcomes as independent common observations. Posterior precision is a working-model heuristic, not calibrated confidence. No Thompson sampling or regret-guarantee claim.',
        initial='Training completed candidate trades at5bp/side; recency weights rho^(trainingEnd-exit), total weight capped4. Priors sealed before evaluation; reward magnitudes in-sample because parent filters fitted full training. Both frictions use same seed. Baseline selected initially; other candidates require >=1fresh evaluation shadow close.',
        adoption='Each close, select largest mu-.25sd only if >current score+.05. Pending orders bind; no parameter switch while any earlier queued order outstanding. Otherwise changes apply to subsequent close decisions, including current position. Existing stop never widens; test old stop before raising next-close level. Hybrid actual trading path differs from fixed-policy shadow path. Full position on eligible entry; otherwise zero-interest cash. No health-driven pause or mandatory trade. A new policy does not force rearming.',
        warning='Same learning as B; actual3rd/4th consecutive net loss, realizedloss<-tau, firstmarkedloss<-tau perposition, or negativeprotectiveexit requests acceleratedforgetting. tau=max(trainingwinnerSD,2fee,1e-6),>=5trainingwinners else unavailable. Minimum20sessions between acceleration. Multiply OLD N,S,W by.25 before new closes; same-day new evidence kept. Warnings alone neither force exit nor force a different parameter. Actual outcomes only drive warnings: never add actual and matching shadow return twice. No risk-size reduction, no health pause.',
        execution='Adjusted prices/fractional cash-funded units. Close decisions execute lateropen t+1+delay.5/10/20bp per side; delay0/1. Stop not intraday or guaranteed gap limit. Fresh flat start one close before first evaluation session. Marked terminal position, no invented final exit. Cash0 and matched buyhold, fixed baseline. All data are published audited, historical availability limitations remain.',
        assessment='Primary warning arm5bp,nextopen; both eras and six frictions. MedianSharpe/lowerquartileCAGR improve and >=90%risky assets within1ppCAGR/2ppDD of fixed. Compare CvsB to isolate acceleration. Identify weakest by lowest primary net cumulative return eachera excludingBIL. Yearly results, actual costs/turnover, return/DD, parameterchanges, warnings, exposure. Already inspected eras are development evidence, not fresh prospective validation. No evaluation tuning.',
        eras=ERAS,frictions=FRICTIONS,
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in
              (Path(__file__),ROOT/'src/systematic_trading/research/online_policy.py',ROOT/'tests/test_online_policy.py')})


def prepare():
    OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True,parents=True)
    p=clean(protocol());path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=p:raise ValueError('Frozen protocol changed')
    write(path,p);print('Frozen',prior.study.digest(path),flush=True)


def verified():
    if clean(protocol())!=json.loads((OUT/'protocol.json').read_text()):raise ValueError('Code/input changed')
    initial=json.loads((OUT/'initial.json').read_text());receipt=json.loads((OUT/'initial-manifest.json').read_text())
    if receipt!=dict(protocol=prior.study.digest(OUT/'protocol.json'),initial=prior.study.digest(OUT/'initial.json')):
        raise ValueError('Initial learning state changed')
    fits,calibration=previous.verified()
    return fits,calibration,initial


def calibrate():
    if (OUT/'initial.json').exists():raise ValueError('Preserve sealed initial states')
    if clean(protocol())!=json.loads((OUT/'protocol.json').read_text()):raise ValueError('Protocol changed')
    fits,_=previous.verified();initial={}
    for symbol in sorted(fits):
        full=prior.model.Features.build(prior.study.load_asset(symbol));initial[symbol]={}
        for era,cutoff,*_ in ERAS:
            fit=fits[symbol][era]
            if not fit['available']:continue
            f=full.truncated(cutoff);f.hmm_models=fit['hmms']
            cl=prior.model.classify(f,fit['selected']['selected']['parameters'])
            initial[symbol][era]=dict(training_end=str(f.days[-1]),states=model.initialize(f,cl))
        print('Initialized',symbol,flush=True)
    write(OUT/'initial.json',initial)
    write(OUT/'initial-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),initial=prior.study.digest(OUT/'initial.json')))


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
            chart=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],
                evaluation_start=first,parameters=p,grid=model.grid(p),calibration=calibration[symbol][era],
                fast_up=cl['fast_probability'][context:,2],slow_down=cl['slow_probability'][context:,0],arms={})
            for cost,delay in FRICTIONS:
                shadows=[prior.model.simulate(f,model.classification(cl,q),start=start,cost_bp=cost,delay=delay) for q in model.grid(p)]
                for arm in model.ARMS:
                    sim=model.simulate(f,cl,seed['states'],calibration[symbol][era],start=start,arm=arm,cost_bp=cost,delay=delay,shadows=shadows)
                    if arm=='fixed':
                        control_error=max(control_error,float(np.nanmax(np.abs(sim['nav']-shadows[0]['nav']))));checks+=1
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
                        threshold=sim['threshold'],yearly=yearly,buyhold=float(f.close[-1]/f.open[lo]/(1+cost/10000)-1)))
                    if cost==5 and delay==0:
                        def series(a):
                            a=np.asarray(a,float).copy();a[:lo]=np.nan;return a[context:]
                        trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']]
                        chart['arms'][arm]={k:series(sim[k]) for k in ('nav','stop','desired','policy','entry_threshold','exit_threshold','distance','posterior_mean','win_probability','effective_count')}
                        chart['arms'][arm].update(trades=trades,events=sim['events']);chart['arms'][arm]['nav']*=100
            charts[f'{symbol}_{era}']=chart
        print('Evaluated',symbol,flush=True)
    if control_error>1e-10 or ledger_error>1e-10:raise ValueError('Ledger/control error')
    write(OUT/'asset-results.json',rows)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(OUT/'validation.json',dict(control_cases=checks,max_control_nav_error=control_error,
        max_independent_ledger_error=ledger_error,asset_cases=len(rows),chart_sha256=prior.study.digest(OUT/'chart-data.json.gz')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','calibrate','evaluate'))
    {'prepare':prepare,'calibrate':calibrate,'evaluate':evaluate}[p.parse_args().stage]()
