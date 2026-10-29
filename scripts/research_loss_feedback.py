"""Three-arm, full-pool loss-feedback experiment on pinned fitted signals."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
import research_latent_slope as prior  # noqa:E402
from systematic_trading.research import loss_feedback as model  # noqa:E402

OUT = ROOT/'research/loss-feedback-20261026-v1'
WORK = ROOT/'var/research/loss-feedback-20261026-v1'
write, clean = prior.write, prior.clean
ERAS, FRICTIONS = prior.ERAS, prior.FRICTIONS


def protocol():
    prior.verified()
    return dict(identity=OUT.name, version=model.VERSION, arms=list(model.ARMS),
        question='Does a single-large-loss/losing-stop warning improve changed actual trades beyond3/4-loss feedback?',
        parent_protocol=prior.study.digest(prior.OUT/'protocol.json'),
        parent_fits=prior.study.digest(prior.OUT/'fit-manifest.json'),
        published_inputs=json.loads((prior.OUT/'protocol.json').read_text())['published_inputs'],
        calibration='Per ETF/cutoff use frozen training-selected policy, completed training trades,5bp/side nextopen. sigma_g=sample std(ddof1) of positive net trade returns;>=5winners else unavailable, no proxy. tau=max(sigma_g,2*evaluation fee,1e-6). This is loss magnitude relative to winner dispersion, not a Gaussian surprise probability. Fits/calibrations sealed before evaluation; training distributions are in-sample and may be optimistic.',
        start='Each era freshly funded, flat and normal health; first close decision is the session before evaluation. No carry-in positions. Thus baseline can differ from old carried-position headline. All three controls share this start.',
        fixed='Same frozen per-ETF policy. No health feedback. Exact regression against existing simulator under the new flat start.',
        streak='Actual3 net losses->half-risk defensive;4->pause/review. Defensive/probation halve initial/trailing distance and fast-down threshold at most.6; never loosen adopted level. Frozen reference continues;4 fresh post-pause shadow trades >=3wins positive sumR and compound net->quarter-risk probation.3actual probation trades >=2wins positive totals->normal;2losses->pause. Defensive2consecutivewins positive phase totals->normal.',
        severity='All streak rules plus close-marked net liquidation loss<-tau requests next-open exit. On actual exit, loss<-tau or exit triggered by mark threshold->pause/review. Any other losing protective exit->defensive if currently normal. Profitable protective exit alone does not warn. Trigger loss/gap remains in P&L. No immediate parameter refit; this isolates monitoring and predetermined defensive policy/recovery.',
        accounting='Fractional adjusted units, cash-funded fees5/10/20bp each side; close decisions next open or extra1session, binding queue. Half/quarter entry notional, residual idle cash0; no daily resizing within a position. Outcome net unit return and known initial risk govern health, not smaller portfolio P&L. Exit-day open loss known at close, subsequent effects next allowed open. No intraday fill assumption.',
        evaluations=[list(e) for e in ERAS], frictions=[list(f) for f in FRICTIONS],
        controls='Cash0, matched fresh buyhold, fixed policy, streak policy; no evaluation-based per-ETF model selection. Primary severity comparison5bp,nextopen. Report weakest risky ETF for each arm/era; severity primary, BIL excluded. All historical dates already inspected development evidence.',
        portfolio='Full supported52ETF pool; same6slot126momentum/63vol/rankbuffer8,BILvacancies. Health from theoretical stand-alone ETF ledger, not portfolio fills. Selection scales slots by desired exposure, residualBIL. Later FR25 overlay keeps half original and scales experimental half by desired exposure. Dynamic cash-inclusive theoretical vs last-adopted L1>=.10 or monthly anchors; fixed monthly control. Cost/delay-specific health paths. Benchmark FR25 and simple momentum/cash/BH. USD only.',
        assessment='Both eras/allfrictions; report paired netSharpe/CAGR/DD, winners sacrificed, exposures, costs, pause/recovery/review counts and yearly stability. Useful improvement requires medianSharpe/lowerquartileCAGR improvement and >=90%risky assets within1ppCAGR/2ppDD of fixed; compare severity versus streak separately. Portfolio netSharpe with <=1ppCAGR loss and nonworseDD; FR25 is empirical comparator. No annual cost ceiling.',
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):prior.study.digest(p) for p in
              (Path(__file__),ROOT/'src/systematic_trading/research/loss_feedback.py',
               ROOT/'src/systematic_trading/research/strategy_health.py',ROOT/'tests/test_loss_feedback.py')})


def prepare():
    OUT.mkdir(exist_ok=True); WORK.mkdir(parents=True,exist_ok=True)
    p=clean(protocol()); path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text()) != p:
        raise ValueError('Changed frozen loss-feedback protocol')
    write(path,p)
    print('Frozen',prior.study.digest(path),flush=True)


def verified():
    if clean(protocol()) != json.loads((OUT/'protocol.json').read_text()):
        raise ValueError('Protocol/input/code changed')
    calibration=json.loads((OUT/'calibration.json').read_text())
    receipt=json.loads((OUT/'calibration-manifest.json').read_text())
    if receipt != dict(protocol=prior.study.digest(OUT/'protocol.json'),
                       calibration=prior.study.digest(OUT/'calibration.json')):
        raise ValueError('Calibration changed')
    return prior.verified(),calibration


def calibrate():
    if (OUT/'calibration.json').exists(): raise ValueError('Preserve sealed calibrations')
    if clean(protocol()) != json.loads((OUT/'protocol.json').read_text()): raise ValueError('Protocol changed')
    fits=prior.verified(); results={}
    for symbol in sorted(fits):
        full=prior.model.Features.build(prior.study.load_asset(symbol));results[symbol]={}
        for era,cutoff,*_ in ERAS:
            fit=fits[symbol][era]
            if not fit['available']: continue
            train=full.truncated(cutoff);train.hmm_models=fit['hmms']
            p=fit['selected']['selected']['parameters']
            results[symbol][era]=model.calibrate(train,prior.model.classify(train,p))
        print('Calibrated',symbol,flush=True)
    write(OUT/'calibration.json',results)
    write(OUT/'calibration-manifest.json',dict(protocol=prior.study.digest(OUT/'protocol.json'),
          calibration=prior.study.digest(OUT/'calibration.json')))


def risk_targets(panel, theory, multiplier, monthly, clock):
    n,m=panel['close'].shape;bill=list(panel['symbols']).index('BIL')
    weights=np.zeros((n,m+1));adopted=np.zeros(m+1);indices=[];anchors=set(map(int,monthly))
    for t in range(int(monthly[0]),n):
        desired=theory[t].copy();desired[:m]*=multiplier[t]
        desired[bill]+=theory[t].sum()-desired.sum()
        distance=np.abs(desired-adopted).sum()+abs(desired.sum()-adopted.sum())
        if t in anchors or (clock=='dynamic' and distance >= .10-1e-12):
            weights[t]=desired;adopted=desired.copy();indices.append(t)
    return weights,np.array(indices,int),None


def evaluate():
    if (OUT/'asset-results.json').exists(): raise ValueError('Preserve completed results')
    fits,calibration=verified();panel=prior.study.frozen._load_panel()
    symbols=list(panel['symbols']);paneldays=np.array(panel['days'],dtype='datetime64[D]')
    signals={f'{era}_{arm}_c{cost}d{delay}':np.zeros(panel['close'].shape) for era,*_ in ERAS
             for arm in model.ARMS for cost,delay in FRICTIONS}
    rows,charts=[],{};control_error=ledger_error=0.;checks=0
    for symbol in sorted(fits):
        full=prior.model.Features.build(prior.study.load_asset(symbol))
        for era,_,first,last in ERAS:
            fit=fits[symbol][era]
            if not fit['available']:continue
            f=full.truncated(last);f.hmm_models=fit['hmms'];p=fit['selected']['selected']['parameters']
            cl=prior.model.classify(f,p);lo=int(np.searchsorted(f.days,np.datetime64(first)));start=lo-1
            if calibration[symbol][era]['training_end'] >= first:raise ValueError('Calibration leakage')
            context=int(np.searchsorted(f.days,np.datetime64('2021-01-01' if era=='late' else '2020-01-01')))
            ix=np.searchsorted(f.days,paneldays);valid=ix<len(f.days)
            valid[valid]&=f.days[ix[valid]]==paneldays[valid]
            basekey=f'{symbol}_{era}'
            charts[basekey]=dict(days=f.days[context:].astype(str),close=f.close[context:],volume=f.volume[context:],
                evaluation_start=first,parameters=p,calibration=calibration[symbol][era],
                fast_up=cl['fast_probability'][context:,2],slow_down=cl['slow_probability'][context:,0],arms={})
            for cost,delay in FRICTIONS:
                base=prior.model.simulate(f,cl,start=start,cost_bp=cost,delay=delay)
                for arm in model.ARMS:
                    sim=model.simulate(f,cl,calibration[symbol][era],start=start,arm=arm,cost_bp=cost,delay=delay)
                    if arm=='fixed':
                        control_error=max(control_error,float(np.nanmax(np.abs(sim['nav']-base['nav']))));checks+=1
                    cash,units=1.,0.;fills={r['session']:r for r in sim['fills']}
                    for t in range(start,len(f.days)):
                        if t in fills:
                            z=fills[t];direction=1 if z['side']=='buy' else -1
                            cash-=direction*z['units']*z['price']+z['fee'];units+=direction*z['units']
                        ledger_error=max(ledger_error,abs(cash+units*f.close[t]-sim['nav'][t]))
                    nav=sim['nav'][start:];stats=prior.stats.nav_stats(nav);stats['calmar']=stats['cagr']/abs(stats['maxdd']) if stats['maxdd'] else None
                    years=(len(nav)-1)/252
                    turnover=sum(z['units']*z['price']/sim['nav'][max(start,z['session']-1)] for z in sim['fills'])/years
                    fees=sum(z['fee']/sim['nav'][max(start,z['session']-1)] for z in sim['fills'])/years*10000
                    closed=[e for e in sim['episodes'] if e['exit_index'] is not None]
                    years_data={}
                    for year in sorted(set(str(d)[:4] for d in f.days[lo:])):
                        j=np.flatnonzero(np.array([str(d).startswith(year) for d in f.days])&(np.arange(len(f.days))>=lo))
                        years_data[year]=float(sim['nav'][j[-1]]/sim['nav'][j[0]-1]-1)
                    rows.append(dict(symbol=symbol,era=era,arm=arm,cost_bp=cost,delay=delay,**stats,
                        cumulative=float(nav[-1]/nav[0]-1),exposure=float(np.mean(sim['exposure'][lo:])),
                        turnover_annual=turnover,cost_bp_annual=fees,closed_trades=len(closed),
                        wins=sum(e['net_return']>0 for e in closed),pause_sessions=int(np.sum(sim['modes'][lo:]=='paused')),
                        reviews=sum(e['review_requested'] for e in sim['health_events']),
                        threshold=sim['threshold'],yearly=years_data,
                        buyhold=float(f.close[-1]/f.open[lo]/(1+cost/10000)-1)))
                    key=f'{era}_{arm}_c{cost}d{delay}'
                    signals[key][valid,symbols.index(symbol)]=sim['desired'][ix[valid]]
                    if cost==5 and delay==0:
                        def series(a):
                            a=np.asarray(a,float).copy();a[:lo]=np.nan;return a[context:]
                        trades=[]
                        for e in sim['episodes']:
                            e=dict(e);e.update(entry_date=str(f.days[e['entry_index']]),
                                exit_date=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None)
                            trades.append(e)
                        charts[basekey]['arms'][arm]=dict(nav=series(sim['nav']*100),stop=series(sim['stop']),
                            modes=sim['modes'][context:].tolist(),desired=series(sim['desired']),trades=trades,
                            health_events=sim['health_events'])
        print('Evaluated',symbol,flush=True)
    if control_error>1e-10 or ledger_error>1e-10:raise ValueError('Accounting/control mismatch')
    write(OUT/'asset-results.json',rows)
    np.savez_compressed(WORK/'signals.npz',**signals)
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(clean(charts),separators=(',',':'),allow_nan=False).encode(),mtime=0))
    write(OUT/'validation.json',dict(control_cases=checks,max_control_nav_error=control_error,
          max_independent_ledger_error=ledger_error,asset_cases=len(rows),
          signal_sha256=prior.study.digest(WORK/'signals.npz'),chart_sha256=prior.study.digest(OUT/'chart-data.json.gz')))


def portfolios():
    import run_fitted_breakout_portfolios as portfolio
    import revisit_breakout_research as control
    from retest_fr25_lifecycle_review import metrics
    if (OUT/'portfolio-results.json').exists():raise ValueError('Preserve portfolio evidence')
    verified();receipt=json.loads((OUT/'validation.json').read_text())
    if prior.study.digest(WORK/'signals.npz')!=receipt['signal_sha256']:raise ValueError('Signals changed')
    with np.load(WORK/'signals.npz',allow_pickle=False) as a:signals={k:a[k] for k in a.files}
    panel=prior.study.frozen._load_panel();recipe=json.loads(prior.study.frozen.RECIPE_PATH.read_text())
    scores=prior.study.br.momentum_score(panel['close']);rows=[];native={};paths={}
    for era,_,first,last in ERAS:
        replay=prior.study.frozen._Replay(panel,recipe,first)
        dates=[str(panel['days'][replay.indices[0]-1]),*map(str,replay.days)]
        end=next((i for i,d in enumerate(dates) if d>last),len(dates))
        monthly=control.monthly_indices(panel,first);n=len(panel['days'])
        for cost,delay in FRICTIONS:
            scenarios={'FR25':(np.column_stack([panel['fr25'],np.zeros(n)]),prior.study.frozen._monthly_indices(panel),None)} if era=='late' else {}
            for clock in ('dynamic','monthly'):
                scenarios['momentum_'+clock]=prior.study.br.select_targets(panel,panel['admitted'],scores,monthly,clock=clock)
                for arm in model.ARMS:
                    pos=signals[f'{era}_{arm}_c{cost}d{delay}']
                    _,_,theory=prior.study.br.select_targets(panel,panel['admitted']&(pos>0),scores,monthly,clock=clock)
                    scenarios[arm+'_selection_'+clock]=risk_targets(panel,theory,pos,monthly,clock)
                    if era=='late':scenarios[arm+'_overlay_'+clock]=portfolio.overlay_targets(panel,.5+.5*pos,clock)
            for name,(weights,indices,_) in scenarios.items():
                result,fills=replay.run_result(weights,indices,cost,delay)
                payload=prior.study.frozen.report_payload(replay,result,fills)
                nav=np.array([float(r['nav_cnh']) for r in payload['nav_series']])[:end]
                period=[r for r in fills if r['date']<=last]
                row=dict(era=era,scenario=name,cost_bp=cost,delay=delay,**metrics(nav,dates[:end],period),yearly={})
                for year in sorted(set(d[:4] for d in dates[1:end])):
                    ix=[i for i,d in enumerate(dates[:end]) if i>0 and d.startswith(year)]
                    row['yearly'][year]=float(nav[ix[-1]]/nav[ix[0]-1]-1)
                rows.append(row)
                if era=='late' and cost==5 and name in ('severity_overlay_dynamic','severity_selection_dynamic'):
                    key=f'{name}_c{cost}d{delay}';native[key+'_weights']=weights;native[key+'_indices']=indices;paths[key]=nav
            print('Portfolio',era,cost,delay,flush=True)
    write(OUT/'portfolio-results.json',rows)
    np.savez_compressed(WORK/'native-mappings.npz',**native);np.savez_compressed(WORK/'native-nav.npz',**paths)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','calibrate','evaluate','portfolios'))
    {'prepare':prepare,'calibrate':calibrate,'evaluate':evaluate,'portfolios':portfolios}[p.parse_args().stage]()
