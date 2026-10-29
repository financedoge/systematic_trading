"""Training-selected thesis exits, full supported ETF pool; no overlays."""
import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_reset_policy as previous
from systematic_trading.research import thesis_exit as model

prior=previous.prior
OUT=ROOT/'research/thesis-exit-20261027-v1'
WORK=ROOT/'var/research/thesis-exit-20261027-v1'
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
write,clean=previous.write,previous.clean


def protocol():
    previous.verified()
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],
        question='Can abandoning a failed upward thesis, then resolving shallow declines hidden in HMM neutral states, improve single-ETF outcomes without sacrificing strong ETFs?',
        scope='Full supported pool; three arms. No portfolios, overlays, monthly rebalancing, funding or broker changes. Prior results and strategy remain frozen.',
        arms=dict(control='Exact preceding regime_reset arm.',
            thesis='Parent plus persistent up-probability failure and nonpositive current fast slope. Exit floor q and count k fit per ETF; q/2 and k+2 during slow-up probability >=.7, even where parent context=false. Other entry, stop and rearm rules unchanged.',
            directional='Thesis plus effective down = HMM down + HMM neutral * Phi((-0.02*sigma-fastSlope)/sqrt(fastSlopeVariance)). Exit when effective down exceeds current original down-exit threshold. Gaussian-slope family is already directional and is not repaired twice. This is a heuristic fusion, not a new HMM posterior or full refit. Independently select the same six exit tuples; comparison to thesis includes changed selection/seeds.'),
        grid=model.exit_grid(),
        fitting='Use original ETF/era market fit and trading parameters. Score each new exit tuple using fixed parent base policy over final 756 training return sessions (funded flat start one close earlier, minimum index252). All market fits use the full pre-evaluation training period, so this is in-sample selection, not nested validation. Require >=3 closed trades, net Sharpe > training control, CAGR >= control-1pp and max drawdown >= control-2pp. Select highest Sharpe, then CAGR, then smaller floor and longer count. If none qualify, disable entire addition for this ETF/arm. No evaluation tuning or force-enable INDA.',
        learning='After choosing an exit rule, initialize nine discounted payoff priors from full training shadow trades with that same exit; cap effective evidence at4. Evaluation shadows and actual trades use the same exit definition. Keep original winner-sigma warning calibration and original market fits. Existing hard resets, freshness/cooldowns and policy adoption unchanged. Disabled additions reuse exact parent seed.',
        persistence='Consecutive daily observations below that day\'s context floor; require current fast slope<=0. Counts include all observed closes. Entry requires high up probability, naturally clearing the run. Context changes may change required count causally. Exit event priority: protection, original fast_down, thesis_failed, shallow_decline.',
        execution='Close decisions execute next open plus delay0/1; 5/10/20bp each side. Pending orders bind. Existing stops cannot loosen. Reset and re-entry as parent; thesis failure below.3 permits later rearm below.5 and a new eligible upswing. No new hard risk cap or support stop in this component test. Idle cash0, fractional cash-funded adjusted units, terminal holdings marked.',
        assessment='Same two inspected development eras. Primary directional 5bp nextopen, weakest risky ETF each era by net cumulative return excluding BIL. Compare each arm to control; both eras/all six frictions require median Sharpe and lower-quartile CAGR improvement and >=90% within1pp CAGR/2pp DD. Report train-enable coverage, yearly stability, costs/turnover, selected thresholds, actual trades/reasons, GLD/WEAT/TLT/INDA and weakest charts. Costs have no absolute ceiling. No fresh OOS claim.',
        eras=ERAS,frictions=FRICTIONS,
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in
            (Path(__file__),ROOT/'src/systematic_trading/research/thesis_exit.py',ROOT/'tests/test_thesis_exit.py')})


def prepare():
    OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True,parents=True)
    p=clean(protocol());target=OUT/'protocol.json'
    if target.exists() and json.loads(target.read_text())!=p:raise ValueError('Frozen protocol changed')
    write(target,p);print('Frozen',prior.study.digest(target),flush=True)


def verified(require_fit=True):
    if clean(protocol())!=json.loads((OUT/'protocol.json').read_text()):raise ValueError('Code/input changed')
    parents=previous.verified()
    if not require_fit:return parents
    fits=json.loads((OUT/'fits.json').read_text());receipt=json.loads((OUT/'fit-manifest.json').read_text())
    assert receipt==dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json'))
    return (*parents,fits)


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Preserve selected fits')
    market,calibration,initial=verified(False);result={}
    for symbol in sorted(market):
        full=prior.model.Features.build(prior.study.load_asset(symbol));result[symbol]={}
        for era,cutoff,*_ in ERAS:
            saved=market[symbol][era]
            if not saved['available']:continue
            f=full.truncated(cutoff);f.hmm_models=saved['hmms']
            cl=prior.model.classify(f,saved['selected']['selected']['parameters'])
            p=model.grid(cl['parameters'])[0];start=max(252,len(f.days)-757)
            baseline=model.coupled_trends.simulate(f,model.classification(cl,p),start=start)
            b=prior.stats.nav_stats(baseline['nav'][start:]);arms={}
            for arm in ('thesis','directional'):
                candidates=[]
                for rule in model.exit_grid():
                    sim=model.coupled_trends.simulate(f,model.classification(cl,p,rule,arm=='directional'),start=start)
                    s=prior.stats.nav_stats(sim['nav'][start:]);closed=sum(e['exit_index'] is not None for e in sim['episodes'])
                    ok=closed>=3 and s['sharpe']>b['sharpe']+1e-10 and s['cagr']>=b['cagr']-.01 and s['maxdd']>=b['maxdd']-.02
                    candidates.append(dict(rule=rule,metrics=s,closed=closed,eligible=bool(ok)))
                eligible=[x for x in candidates if x['eligible']]
                chosen=max(eligible,key=lambda x:(x['metrics']['sharpe'],x['metrics']['cagr'],-x['rule']['floor'],x['rule']['count'])) if eligible else None
                rule=chosen['rule'] if chosen else dict(enabled=False)
                if chosen:
                    shadows=[model.coupled_trends.simulate(f,model.classification(cl,z,rule,arm=='directional')) for z in model.grid(cl['parameters'])]
                    seed=model.seed_from_shadows(f,cl,shadows)
                else:seed=initial[symbol][era]['states']
                arms[arm]=dict(rule=rule,seed=seed,candidates=candidates)
            result[symbol][era]=dict(training_end=str(f.days[-1]),selection_start=str(f.days[start]),baseline=b,arms=arms)
        print('Fitted exits',symbol,flush=True)
    write(OUT/'fits.json',result)
    write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Preserve completed evaluation')
    market,calibration,initial,selected=verified();rows=[];charts={};control_error=ledger_error=0.;checks=0
    parent_rows=json.loads((previous.OUT/'asset-results.json').read_text())
    parent_lookup={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in parent_rows if r['arm']=='regime_reset'}
    for symbol in sorted(market):
        full=prior.model.Features.build(prior.study.load_asset(symbol))
        for era,_,first,last in ERAS:
            saved=market[symbol][era]
            if not saved['available']:continue
            f=full.truncated(last);f.hmm_models=saved['hmms']
            p=saved['selected']['selected']['parameters'];cl=prior.model.classify(f,p)
            lo=int(np.searchsorted(f.days,np.datetime64(first)));start=lo-1
            assert selected[symbol][era]['training_end']<first
            regimes=model.regime_signals(f);context=int(np.searchsorted(f.days,np.datetime64('2021-01-01' if era=='late' else first)))
            chart=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],evaluation_start=first,
                parameters=p,grid=model.grid(p),calibration=calibration[symbol][era],selection=selected[symbol][era],
                fast_up=cl['fast_probability'][context:,2],fast_down=cl['fast_probability'][context:,0],
                neutral=cl['fast_probability'][context:,1],slow_up=cl['slow_probability'][context:,2],
                slow_down=cl['slow_probability'][context:,0],fast_slope=cl['fast_slope'][context:],arms={})
            for cost,delay in FRICTIONS:
                old=previous.model.simulate(f,cl,initial[symbol][era]['states'],calibration[symbol][era],start=start,arm='regime_reset',cost_bp=cost,delay=delay,regimes=regimes)
                for arm in model.ARMS:
                    choice=selected[symbol][era]['arms'].get(arm)
                    rule=choice['rule'] if choice else None;seed=choice['seed'] if choice else initial[symbol][era]['states']
                    sim=model.simulate(f,cl,seed,calibration[symbol][era],start=start,arm=arm,rule=rule,cost_bp=cost,delay=delay,regimes=regimes)
                    if arm=='control':
                        control_error=max(control_error,float(np.nanmax(np.abs(old['nav']-sim['nav']))));checks+=1
                        assert abs(sim['nav'][-1]-1-parent_lookup[symbol,era,cost,delay]['cumulative'])<1e-12
                    cash=1.;units=0.;fills={e['session']:e for e in sim['fills']}
                    for t in range(start,len(f.days)):
                        if t in fills:
                            e=fills[t];sign=1 if e['side']=='buy' else -1;cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
                        ledger_error=max(ledger_error,abs(sim['nav'][t]-cash-units*f.close[t]))
                    nav=sim['nav'][start:];s=prior.stats.nav_stats(nav);years=(len(nav)-1)/252
                    closed=[e for e in sim['episodes'] if e['exit_index'] is not None]
                    yearly={}
                    for year in sorted(set(str(d)[:4] for d in f.days[lo:])):
                        ix=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>=lo))
                        yearly[year]=float(sim['nav'][ix[-1]]/sim['nav'][ix[0]-1]-1)
                    reference=parent_lookup[symbol,era,cost,delay]
                    rows.append(dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**s,cumulative=float(nav[-1]/nav[0]-1),
                        closed_trades=len(closed),wins=sum(e['net_return']>0 for e in closed),
                        exposure=float(np.mean(sim['exposure'][lo:])),yearly=yearly,rule=rule,
                        enabled=bool(rule and rule['enabled']),
                        turnover_annual=sum(e['units']*e['price']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years,
                        cost_bp_annual=sum(e['fee']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years*10000,
                        changes=sum(e['changed'] for e in sim['events']),reset_count=sim['reset_count'],
                        empty_evidence_sessions=int(sim['empty_evidence'][lo:].sum()),
                        exit_reasons={reason:sum(e['exit_reason']==reason for e in closed) for reason in ('protection','fast_down','thesis_failed','shallow_decline')},
                        frozen_cumulative=reference['frozen_cumulative'],buyhold=reference['buyhold']))
                    if cost==5 and delay==0:
                        def series(a):
                            a=np.asarray(a,float).copy();a[:lo]=np.nan;return a[context:]
                        chart['arms'][arm]={k:series(sim[k]) for k in ('nav','stop','desired','policy','entry_threshold','exit_threshold','distance','posterior_mean','win_probability','effective_count','reset_age','empty_evidence','thesis_floor','thesis_count','bad_run','effective_down')}
                        chart['arms'][arm]['nav']*=100
                        chart['arms'][arm].update(trades=[dict(e,entry_date=str(f.days[e['entry_index']]),exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None) for e in sim['episodes']],events=sim['events'])
            charts[f'{symbol}_{era}']=chart
        print('Evaluated exits',symbol,flush=True)
    assert control_error<1e-12 and ledger_error<1e-12
    write(OUT/'asset-results.json',rows)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(OUT/'validation.json',dict(control_cases=checks,max_control_nav_error=control_error,max_independent_ledger_error=ledger_error,
        asset_cases=len(rows),chart_sha256=prior.study.digest(OUT/'chart-data.json.gz')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','fit','evaluate'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate}[p.parse_args().stage]()
