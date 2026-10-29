"""Full-pool HMM/entry component study, pinned audited histories only."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_thesis_exit as previous
from systematic_trading.research import regime_entry as model
prior=previous.prior
ERAS,FRICTIONS=previous.ERAS,previous.FRICTIONS
OUT=ROOT/'research/regime-entry-20261027-v1'
WORK=ROOT/'var/research/regime-entry-20261027-v1'
write,clean=previous.write,previous.clean


def protocol():
    return dict(identity=OUT.name,version=model.VERSION,parent_protocol=prior.study.digest(previous.OUT/'protocol.json'),
        published_inputs=json.loads((previous.OUT/'protocol.json').read_text())['published_inputs'],eras=ERAS,frictions=FRICTIONS,
        scope='Full supported single-ETF pool; no portfolios/overlay or execution authority. Two already-inspected development eras.',
        arms=dict(control='A: parent thesis B market model and selected thesis exit, fixed base policy0. Bayesian policy adaptation disabled in all three arms. This is NOT the previous adaptive incumbent; show its observed results separately.',
            hmm='B: A with a newly fitted three-state fast-slope HMM for every ETF, including those previously using Gaussian slope probabilities. Existing fast/slow Kalman models, base trading thresholds, thesis rule, stop distances and rearming stay fixed.',
            guarded='C: B plus stronger evidence in slow-up probability<.7, or following a losing trade. In those cases up>=max(.8,base entry), positive fast slope, k consecutive flat opportunity closes, and log price advance from preceding close of this sequence >=a*training daily sigma+2*fee. After any loss also require a fresh up<.5 observation after the actual exit and k+1 closes. A nonlosing closed trade clears the loss flag. Strong slow-up entries otherwise retain A/B rules. No permanent pause.'),
        hmm='x=fast Kalman slope/training daily sigma. Gaussian emissions with separate state variances. mu_down in[-2,-2b],mu_range=0,mu_up in[2b,2]; variance in[.000025,4],range variance<=b^2. b in[.05,.10]. EM25 with two starts .15/.4; transition pseudo counts .1+3I and diagonal bound .65..98. Fit on training slopes before final252, select b by forward predictive slope log likelihood over final252, then refit chosen b on full training. Existing Kalman/trading fits see full training: HMM-only holdback, not nested pipeline validation. Slopes are serially correlated and probabilities are uncalibrated model scores.',
        guard_grid=model.guard_grid(),
        guard_selection='Final756 training returns with full-training models. Compare four k/a rules to B, require >=3 closed trades, greater net Sharpe, CAGR>=B-1pp,maxDD>=B-2pp. Highest Sharpe then CAGR then smaller k/a. Disable if none qualify. Same HMM in B/C. No evaluation selection. Fixed policy0 isolates entry/exit signal effects from shadow learning.',
        execution='Daily close decisions, fills at open t+1+delay; delay0/1 and5/10/20bp each side. Pending target changes bind. Fractional cash-funded shares, cash interest0, adjusted prices; terminal positions marked, no forced terminal sale. Same nonloosening peak-price stops as parent; no new independent hard-risk stop. Raw audited volume descriptive only.',
        diagnostics='Daily arithmetic return correlation and OLS beta/252*intercept vs ETF, zero cash benchmark; HAC5 t diagnostic with finite sample correction. Not causal alpha and no multiplicity-adjusted significance claim. Five-session score Spearman IC from earliest executable open, overlapping windows descriptive. Slow context at prior close for conditional exposure/return. Entry-context closed-trade win/loss/mean; failed breakout defined net losing completed trade, not latent ground truth. Compare current adaptive incumbent separately. Native checks frozen signals/accounting only.',
        assessment='Primary5bp delay0. Risky ETF excludes BIL. Each of12 era/friction cases requires higher median Sharpe, higher lower-quartile CAGR and >=90% ETF preservation within1pp CAGR/2pp drawdown against matched fixed A; also display C vs B, cumulative return, cost/turnover, exposure, yearly robustness. No cost ceiling, no optimize for low correlation. Weakest C ETF each era by primary net return gets chart.',
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in
              (Path(__file__),ROOT/'src/systematic_trading/research/regime_entry.py',ROOT/'tests/test_regime_entry.py')})


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


def fit():
    if (OUT/'fits.json').exists():raise ValueError('Frozen fits exist')
    market,_,_,exits=verified(False);result={}
    for symbol in sorted(market):
        full=prior.model.Features.build(prior.study.load_asset(symbol));result[symbol]={}
        for era,cutoff,*_ in ERAS:
            saved=market[symbol][era]
            if not saved['available']:continue
            f=full.truncated(cutoff);f.hmm_models=saved['hmms'];p=saved['selected']['selected']['parameters']
            rule=exits[symbol][era]['arms']['thesis']['rule'];base=model.classification(f,p,rule)
            selected=model.select_hmm(base['fast_slope'][252:]/base['sigma'])
            cl=model.classification(f,p,rule,selected['model']);start=max(252,len(f.days)-757)
            b=prior.stats.nav_stats(model.simulate(f,cl,start=start)['nav'][start:]);candidates=[]
            for g in model.guard_grid():
                sim=model.simulate(f,cl,start=start,guard=g);s=prior.stats.nav_stats(sim['nav'][start:])
                closed=sum(e['exit_index'] is not None for e in sim['episodes'])
                ok=closed>=3 and s['sharpe']>b['sharpe']+1e-10 and s['cagr']>=b['cagr']-.01 and s['maxdd']>=b['maxdd']-.02
                candidates.append(dict(guard=g,metrics=s,closed=closed,eligible=bool(ok)))
            good=[c for c in candidates if c['eligible']]
            best=max(good,key=lambda c:(c['metrics']['sharpe'],c['metrics']['cagr'],-c['guard']['count'],-c['guard']['advance'])) if good else None
            result[symbol][era]=dict(training_end=str(f.days[-1]),selection_start=str(f.days[start]),hmm=selected,
                guard=best['guard'] if best else dict(enabled=False),guard_candidates=candidates,baseline=b,exit_rule=rule)
        write(WORK/'fit-progress.json',result);print('Fitted',symbol,flush=True)
    write(OUT/'fits.json',result);write(OUT/'fit-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),fits=prior.study.digest(OUT/'fits.json')))


def replay(symbol,era,market,selected,cost=5,delay=0,arm='guarded'):
    _,_,first,last=next(e for e in ERAS if e[0]==era)
    f=prior.model.Features.build(prior.study.load_asset(symbol)).truncated(last);f.hmm_models=market[symbol][era]['hmms']
    p=market[symbol][era]['selected']['selected']['parameters'];q=selected[symbol][era]
    cl=model.classification(f,p,q['exit_rule'],None if arm=='control' else q['hmm']['model'])
    start=int(np.searchsorted(f.days,np.datetime64(first)))-1
    sim=model.simulate(f,cl,start=start,cost_bp=cost,delay=delay,guard=q['guard'] if arm=='guarded' else None)
    return f,cl,sim,start


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Frozen evaluation exists')
    market,_,_,_,selected=verified();rows=[];charts={};control_error=ledger_error=0.;checks=0
    oldcharts=json.loads(gzip.decompress((previous.OUT/'chart-data.json.gz').read_bytes()))
    oldrows=json.loads((previous.OUT/'asset-results.json').read_text())
    oldlookup={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in oldrows if r['arm']=='thesis'}
    for symbol in sorted(market):
        full=prior.model.Features.build(prior.study.load_asset(symbol))
        for era,_,first,last in ERAS:
            if era not in selected[symbol]:continue
            f=full.truncated(last);f.hmm_models=market[symbol][era]['hmms'];p=market[symbol][era]['selected']['selected']['parameters']
            q=selected[symbol][era];assert q['training_end']<first
            base=model.classification(f,p,q['exit_rule']);new=model.classification(f,p,q['exit_rule'],q['hmm']['model'])
            lo=int(np.searchsorted(f.days,np.datetime64(first)));start=lo-1
            context=int(np.searchsorted(f.days,np.datetime64('2021-01-01' if era=='late' else first)))
            ar=f.close[lo:]/f.close[lo-1:-1]-1
            old=oldcharts[f'{symbol}_{era}'];oldnav=np.array([1.]+[v/100 for d,v in zip(old['days'],old['arms']['thesis']['nav']) if d>=first])
            assert len(oldnav)==len(ar)+1
            incumbent=model.dependence(oldnav[1:]/oldnav[:-1]-1,ar)
            chart=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],evaluation_start=first,
                parameters=p,selection=q,slow_up=base['slow_probability'][context:,2],slow_down=base['slow_probability'][context:,0],arms={})
            for cost,delay in FRICTIONS:
                for arm in model.ARMS:
                    cl=base if arm=='control' else new;g=q['guard'] if arm=='guarded' else None
                    sim=model.simulate(f,cl,start=start,cost_bp=cost,delay=delay,guard=g)
                    if arm=='control':
                        reference=model.thesis_exit.coupled_trends.simulate(f,cl,start=start,cost_bp=cost,delay=delay)
                        control_error=max(control_error,float(np.nanmax(np.abs(sim['nav']-reference['nav']))));checks+=1
                    cash=1.;units=0.;fills={e['session']:e for e in sim['fills']}
                    for t in range(start,len(f.days)):
                        if t in fills:
                            e=fills[t];sign=1 if e['side']=='buy' else -1;cash-=sign*e['units']*e['price']+e['fee'];units+=sign*e['units']
                        ledger_error=max(ledger_error,abs(sim['nav'][t]-cash-units*f.close[t]))
                    nav=sim['nav'][start:];s=prior.stats.nav_stats(nav);years=(len(nav)-1)/252
                    r=nav[1:]/nav[:-1]-1;closed=[e for e in sim['episodes'] if e['exit_index'] is not None]
                    daily_context=np.where(base['aligned'][start:-1],'up',np.where(base['counter'][start:-1],'down','uncertain'))
                    regimes={}
                    for state in ('up','down','uncertain'):
                        mask=daily_context==state;tr=[e for e in closed if e['context']==state]
                        regimes[state]=dict(sessions=int(mask.sum()),exposure=float(sim['exposure'][lo:][mask].mean()) if mask.any() else None,
                            strategy_mean=float(r[mask].mean()) if mask.any() else None,asset_mean=float(ar[mask].mean()) if mask.any() else None,
                            closed=len(tr),losing=sum(e['net_return']<0 for e in tr),mean_trade=float(np.mean([e['net_return'] for e in tr])) if tr else None)
                    yearly={}
                    for year in sorted(set(str(d)[:4] for d in f.days[lo:])):
                        ix=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>=lo))
                        yearly[year]=float(sim['nav'][ix[-1]]/sim['nav'][ix[0]-1]-1)
                    oldrow=oldlookup[symbol,era,cost,delay]
                    rows.append(dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**s,cumulative=float(nav[-1]-1),
                        **model.dependence(r,ar),ic5=model.ic(f,cl,start,delay),closed_trades=len(closed),wins=sum(e['net_return']>0 for e in closed),
                        exposure=float(sim['exposure'][lo:].mean()),regimes=regimes,yearly=yearly,guard=g,enabled=bool(g and g['enabled']),
                        blocked_sessions=int(sim['blocked'][lo:].sum()),turnover_annual=sum(e['units']*e['price']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years,
                        cost_bp_annual=sum(e['fee']/sim['nav'][max(start,e['session']-1)] for e in sim['fills'])/years*10000,
                        adaptive_incumbent_cumulative=oldrow['cumulative'],adaptive_incumbent_sharpe=oldrow['sharpe'],
                        incumbent_dependence=incumbent if cost==5 and delay==0 else None,buyhold=oldrow['buyhold']))
                    if cost==5 and delay==0:
                        def series(a):
                            z=np.asarray(a,float).copy();z[:lo]=np.nan;return z[context:]
                        a={k:series(sim[k]) for k in ('nav','stop','desired','required','run','advance','anchor','blocked','gate')};a['nav']*=100
                        a.update(fast_up=series(cl['fast_probability'][:,2]),neutral=series(cl['fast_probability'][:,1]),fast_down=series(cl['fast_probability'][:,0]),
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
