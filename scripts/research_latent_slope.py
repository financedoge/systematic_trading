"""Frozen full-pool multiscale/adaptive/protection component experiment."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
import research_multiscale_modes as parent  # noqa: E402
from systematic_trading.research import latent_slope as model  # noqa: E402

study, stats, source = parent.study, parent.stats, parent.source
write, clean = parent.write, parent.clean
OUT = ROOT/'research/latent-slope-20261025-v1'
WORK = ROOT/'var/research/latent-slope-20261025-v1'
ERAS, FRICTIONS = parent.ERAS, parent.FRICTIONS
FAMILIES = ('slope','switch','context')
VARIANTS = (*FAMILIES, 'selected', 'baseline')


def grid():
    return [dict(family=family,label=family,entry=entry,exit=exit_,tight=distance,
                 wide=2*distance,reset=.5,context=family=='context')
            for family in FAMILIES for entry in (.6,.75) for exit_ in (.6,.75) for distance in (3.,5.)]


def protocol():
    declared,fits=source.verified_fits();parent.verified()
    return dict(identity=OUT.name,version=model.VERSION,universe=sorted(fits),published_inputs=declared['data'],
        parent_protocol=study.digest(parent.OUT/'protocol.json'),parent_fits=study.digest(parent.OUT/'fit-manifest.json'),
        question='Learn continuous slow price slope and a fast switching rebound process; preserve returns of good ETFs.',
        observation='y_t=log adjusted close. Two separate local linear filters j in slow/fast: y_t=ell_j,t+epsilon_j,t; ell_j,t=ell_j,t-1+b_j,t-1; b_j,t=b_j,t-1+zeta_j,t. R_j=Var(epsilon), Q_j=diag(0,lambda_j R_j). No fixed rolling trend windows. These are parallel estimators of the same price, not additive latent factors.',
        filtering='F=[[1,1],[0,1]],H=[1,0]. Initial mean=(y0,0),P0=R*I. Standard forward Kalman update. No smoothing in evaluation. Per ETF and cutoff, fit each lambda by scalar bounded profile likelihood of completed one-step innovations after252warmup; R=mean(e_t^2/S_t^unit), floor1e-12. Slow lambda1e-10..1e-6,fast1e-5..1e-2; optimize log lambda xatol.15 max18iter and compare endpoints. Fixed learned noise per evaluation; gains adapt through covariance, no claims of unconstrained timescale or online parameter learning.',
        directional_probabilities='delta=.02*training daily log-return sigma. Down=P(b<-delta),range=P(-delta<=b<=delta),up=P(b>delta), computed from filtered Gaussian slope mean/variance; disjoint. Confirm slow up/down at70%. Intermediate states unknown, not automatically range. Plot slopes and95%conditional intervals plus levels.',
        fast_hmm='Observe x_t=filtered fast slope / training daily return sigma from session252. Three-state shared-variance Gaussian HMM, means constrained down[-2,-.005],range0,up[.005,2],variancefloor.0001. Two initial amplitudes .05/.2,25EMiterations,diagonalprior3/allcells.1,stayprobability.65.. .98. Training-only likelihood+prior selection. Standard exact3state forward inference for trading; training backward smoothing only estimates parameters. Derived slope observations are serially correlated, so probabilities are model outputs, not calibrated confidence. This is a two-stage filter/classifier, not joint switching-Kalman inference.',
        main_models={'slope':'A: Continuous price slopes; Gaussian fast-slope direction and uniform exit.',
                     'switch':'B: Same continuous slopes; fast HMM direction and uniform exit.',
                     'context':'C: Same fast HMM; slow-up context raises exit threshold and doubles trailing distance.'},
        trading='Buy when armed and fast up probability>=.6/.75 and fast mean slope>0; slow down never vetoes a rebound. Rearm after an exit requires fast up<.5. Exit fast down probability>=.6/.75; C raises threshold to.85 when slow up>=.7. Hold through range unless protective exit. At entry initial level=open-k*sigma*open, with known signal-day k. Trail=max(old,peakclose-k*sigma*entryopen). A/B k=3/5. C k=6/10 in confirmed slow up,3/5 otherwise. Never widen adopted levels; old level tested before next-close tightening. No current volatility/volume-spike tightening in this isolation test.',
        execution='Cash-funded fees5/10/20bp per side; close decisions fill next open or extra1session, bindingFIFO. Idle cash zero. Protection not intraday or gap-loss guarantee. Preserve parent carried-position evaluation; not a fresh-funded deployment at boundary.',
        search='Eight paired policies per3models=24/ETF/cutoff. Top2 per model rescored atall6frictions, prefer>=5closedtrades/5%exposure elseflag. Worst-friction training utility selects each model parameters and overall strategy; retain full results. Models A/B/C are the only main report choices, and every available ETF/era/model gets a graph. Per-ETF recommended badge uses training only, never evaluation winner.',
        objective='Frozen45/40/15 excessCAGR/Sharpe/regularizedCalmar utility, block stability and scarcity penalties. Full training filter/HMM calibration is in-sample, not rolling-refit validation.',
        evaluation='Full52pool inclBIL; train<=2022/test2023Jan3..2026Oct16 and train<=2019/test2020..2022;500trainingafter252warmup. Prior multiscale selected is the matched strong baseline. Both histories already inspected development data. TLT diagnostics intervalsSep2023-Jan2024 andJun-Oct2024 predeclared; no optimizing on event dates.',
        illustrative_intervals=[['2023-09-01','2024-01-31'],['2024-06-01','2024-10-31']],
        acceptance='Both eras/all6frictions: medianSharpe and lowerquartileCAGR improve,>=90%adequatefits within1ppCAGR/2ppDD guards vs prior multiscale selected. Portfolio higherSharpe,<=1ppCAGRloss,no worseDD versus both matchedbaseline and FR25late/momentumearly.',
        portfolio='Existing52ETF6slot126momentum/63vol,rankbuffer8,BILvacancies. Globaltrainingwinner binarygate,FR25.5+.5positionoverlay. Dynamicmembership versusmonthly; overlaylast-adoptedcashinclusiveL1>=.10+monthend versusmonthly. All6frictions; no annualcostcap.',
        report='Three model choices A/B/C with explicit equations and actual fitted numbers, all306ETF/era/model charts, date selection and trade reasons. Previous naming decoded with exact independent/coupled transition and price/volume observation equations; no cryptic list of variants. Neither overall-selected nor baseline is an extra model selector.',
        authority='Research only; no runtime, funding, monitoring, broker or approval changes.',
        code_hashes={str(p.relative_to(ROOT)).replace(chr(92),'/'):study.digest(p) for p in
                    (Path(__file__),ROOT/'src/systematic_trading/research/latent_slope.py',
                     ROOT/'src/systematic_trading/research/coupled_trends.py',ROOT/'src/systematic_trading/research/trend_hmm.py',
                     ROOT/'scripts/research_multiscale_modes.py')})


def prepare():
    p=clean(protocol());path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=p:raise ValueError('Changed frozen protocol')
    write(path,p);print('Frozen',study.digest(path),flush=True)


def score(f, cl, cost=5, delay=0):
    sim=model.simulate(f,cl,cost_bp=cost,delay=delay)
    start,end=252,len(f.days);bh=np.full(end,np.nan);bh[start:]=f.close[start:]/f.open[start]/(1+cost/10000)
    window=lambda a,lo,hi:stats.nav_stats(np.r_[1. if lo==start else a[lo-1],a[lo:hi]])
    full,base=window(sim['nav'],start,end),window(bh,start,end)
    blocks=[study.old.utility(window(sim['nav'],a,b),window(bh,a,b)) for a,b in study.old.block_bounds(start,end)]
    closed=sum(e['exit_index'] is not None for e in sim['episodes']);exposure=float(sim['held'][start:].mean())
    value=.5*study.old.utility(full,base)+.5*np.median(blocks)-.25*np.std(blocks)-.1*max(0,10-closed)/10-.3*max(0,.2-exposure)/.2
    return dict(score=float(value),cagr=full['cagr'],sharpe=full['sharpe'],maxdd=full['maxdd'],closed=closed,exposure=exposure)


def fit_job(job):
    symbol,phash=job;f=model.Features.build(study.load_asset(symbol));result={};choices=grid()
    for era,cutoff,_,_ in ERAS:
        train=f.truncated(cutoff)
        if len(train.days)-252<500:
            result[era]=dict(available=False,reason='Insufficient training history');continue
        train.hmm_models=model.fit_models(train)
        scores=[score(train,model.classify(train,p)) for p in choices]
        finalists,selected={},{}
        for family in FAMILIES:
            ix=sorted([i for i,p in enumerate(choices) if p['label']==family],key=lambda i:(-scores[i]['score'],i))[:2]
            for i in ix:
                cl=model.classify(train,choices[i]);rr=[scores[i]]+[score(train,cl,c,d) for c,d in FRICTIONS[1:]]
                finalists[i]=dict(parameters=choices[i],training=rr,worst=min(r['score'] for r in rr),evidence=all(r['closed']>=5 and r['exposure']>=.05 for r in rr))
            adequate=[i for i in ix if finalists[i]['evidence']]
            best=min(adequate or ix,key=lambda i:(-finalists[i]['worst'],i));selected[family]=dict(index=best,**finalists[best])
        pool=[r['index'] for r in selected.values()];adequate=[i for i in pool if finalists[i]['evidence']]
        best=min(adequate or pool,key=lambda i:(-finalists[i]['worst'],i));selected['selected']=dict(index=best,**finalists[best])
        result[era]=dict(available=True,training_end=str(train.days[-1]),selected=selected,base_scores=scores,finalists=finalists,hmms=train.hmm_models)
    write(WORK/'fits'/f'{symbol}.json',dict(symbol=symbol,protocol_sha256=phash,fits=result));return symbol


def verified(require_fits=True):
    if clean(protocol())!=json.loads((OUT/'protocol.json').read_text()):raise ValueError('Changed protocol/input')
    if not require_fits:return {}
    manifest=json.loads((OUT/'fit-manifest.json').read_text());result={}
    if manifest['protocol_sha256']!=study.digest(OUT/'protocol.json'):raise ValueError('Protocol mismatch')
    for name,h in manifest['files'].items():
        p=WORK/'fits'/name
        if study.digest(p)!=h:raise ValueError('Changed fit')
        r=json.loads(p.read_text());result[r['symbol']]=r['fits']
    if len(result)!=52:raise ValueError('Incomplete fit pool')
    return result


def fit():
    verified(False);h=study.digest(OUT/'protocol.json');symbols=json.loads((OUT/'protocol.json').read_text())['universe']
    jobs=[(s,h) for s in symbols if not (WORK/'fits'/f'{s}.json').exists()]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for s in pool.map(fit_job,jobs):print('Fitted',s,flush=True)
    files={p.name:study.digest(p) for p in sorted((WORK/'fits').glob('*.json'))}
    if len(files)!=52 or any(json.loads((WORK/'fits'/p).read_text())['protocol_sha256']!=h for p in files):raise ValueError('Incomplete/mixed fits')
    write(OUT/'fit-manifest.json',dict(protocol_sha256=h,files=files))


def union_control(f, fits, era, cost=5, delay=0):
    # Retain the helper name for the common evaluator; reference is prior selected.
    if not hasattr(f,'old_control'):
        f.old_control=parent.model.Features.build(study.load_asset(f.symbol)).truncated(str(f.days[-1]))
    old=f.old_control
    old.hmm_models=fits[era]['hmms']
    p=fits[era]['selected']['selected']['parameters']
    return parent.model.simulate(old,parent.model.classify(old,p),cost_bp=cost,delay=delay)


def evaluate():
    if (OUT/'asset-results.json').exists():raise ValueError('Preserve completed evidence')
    fits=verified();oldfits=parent.verified();panel=study.frozen._load_panel();symbols=list(panel['symbols'])
    signals={f'{era}_{variant}':np.zeros(panel['close'].shape,bool) for era,*_ in ERAS for variant in ('selected','baseline')}
    billdata=study.load_asset('BIL');billix={str(d):i for i,d in enumerate(billdata['days'])}
    rows,choices,details=[],[],{};max_error=0.
    for symbol in sorted(fits):
        f=model.Features.build(study.load_asset(symbol));indices={str(d):i for i,d in enumerate(f.days)};panel_ix=[indices[str(d)] for d in panel['days']]
        bill={k:np.array([billdata[k][billix[str(d)]] if str(d) in billix else np.nan for d in f.days]) for k in ('open','close')}
        for era,cutoff,first,last in ERAS:
            fit_=fits[symbol][era]
            if not fit_['available']:continue
            endf=f.truncated(last);endf.symbol=symbol;hi=len(endf.days);lo=int(np.flatnonzero(f.days>=np.datetime64(first))[0]);cache={}
            endf.hmm_models=fit_['hmms']
            for variant in VARIANTS:
                chosen=fit_['selected'][variant] if variant!='baseline' else None
                if chosen:
                    config=chosen['parameters'];classified=model.classify(endf,config)
                    choices.append(dict(symbol=symbol,era=era,variant=variant,evidence=chosen['evidence'],parameters=config))
                for cost,delay in FRICTIONS:
                    key=(chosen['index'] if chosen else -1,cost,delay)
                    if key not in cache:
                        sim=model.simulate(endf,classified,cost_bp=cost,delay=delay) if chosen else union_control(endf,oldfits[symbol],era,cost,delay)
                        turn,fees,error=parent.parent.previous.ledger(endf,sim,cost);max_error=max(max_error,error)
                        r=source.measure(endf,sim,sim['desired'],sim['held'],{k:v[:hi] for k,v in bill.items()},lo,hi)
                        r.update(cumulative=sim['nav'][-1]/sim['nav'][lo-1]-1,calmar=r['cagr']/abs(r['maxdd']) if abs(r['maxdd'])>1e-12 else None,
                            turnover_annual=float(turn[lo:hi].sum()*252/(hi-lo)),cost_bp_annual=float(fees[lo:hi].sum()*252/(hi-lo)*10000))
                        if cost==5 and delay==0:
                            forward=stats.forward_returns(endf.open,endf.close,bill['open'][:hi],bill['close'][:hi],21)
                            r['ic21']=stats.rank_ic(sim['desired'][lo:hi],forward[lo:hi],21)
                            if chosen:
                                train=f.truncated(cutoff);train.hmm_models=fit_['hmms'];tc=model.classify(train,config);ts=model.simulate(train,tc)
                                for field in ('nav','held','desired','state','fast_probability','slow_probability','stop'):
                                    np.testing.assert_allclose(ts[field],sim[field][:len(train.days)],atol=1e-10,rtol=0,equal_nan=True)
                                for k,v in score(train,tc).items():np.testing.assert_allclose(v,chosen['training'][0][k],atol=1e-10,rtol=0)
                        cache[key]=r,sim
                    r,sim=cache[key]
                    rows.append(dict(symbol=symbol,era=era,variant=variant,cost_bp=cost,delay=delay,training_evidence=chosen['evidence'] if chosen else True,**r))
                    if variant in ('selected','baseline') and cost==5 and delay==0:
                        for j,i in enumerate(panel_ix):
                            if i<hi:signals[f'{era}_{variant}'][j,symbols.index(symbol)]=sim['desired'][i]
                    if variant=='selected' and cost==5 and delay==0:
                        from build_etf_breakout_failure_report import interval_accounting
                        trades=[]
                        for ep in sim['episodes']:
                            a,x=ep['entry_index'],ep['exit_index']
                            if x is not None and x<lo:continue
                            mark=ep['exit_price'] if x is not None else f.close[hi-1]
                            trades.append(dict(entry=str(f.days[a]),exit=str(f.days[x]) if x is not None else None,entry_index=a,exit_index=x,
                                entry_price=ep['entry'],exit_or_mark=mark,reason=ep['exit_reason'],net_return=float(mark/ep['entry']*(.9995 if x is not None else 1)/1.0005-1),carried=a<lo))
                        details[symbol+'_'+era]=dict(parameters=config,trades=trades,accounting=interval_accounting(endf,sim,lo,hi),
                            countertrend_sessions=int(np.sum(sim['held'][lo:hi]&sim['counter'][lo:hi])))
        print('Evaluated',symbol,flush=True)
    for era,*_ in ERAS:
        for variant in VARIANTS:
            rr=[r for r in rows if r['era']==era and r['variant']==variant and r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL']
            for name,values in [('alpha_holm_p',[r['p'] for r in rr]),('ic21_holm_p',[r['ic21']['p'] for r in rr])]:
                for r,p in zip(rr,stats.holm(values),strict=True):r[name]=p
    write(OUT/'asset-results.json',rows);write(OUT/'selected-parameters.json',choices);write(OUT/'diagnostics.json',details)
    np.savez_compressed(WORK/'signals.npz',**signals)
    write(OUT/'validation.json',dict(asset_cases=len(rows),ledger_max_relative_error=max_error,training_prefix_and_scores_reproduced=True,
        all_fits_sealed_before_evaluation=True,signal_sha256=study.digest(WORK/'signals.npz')))


def portfolios():
    import run_fitted_breakout_portfolios as portfolio
    import revisit_breakout_research as control
    from retest_fr25_lifecycle_review import metrics
    verified()
    if (OUT/'portfolio-results.json').exists():raise ValueError('Preserve portfolio evidence')
    receipt=json.loads((OUT/'validation.json').read_text())
    if study.digest(WORK/'signals.npz')!=receipt['signal_sha256']:raise ValueError('Changed signals')
    with np.load(WORK/'signals.npz',allow_pickle=False) as a:signals={k:a[k] for k in a.files}
    panel=study.frozen._load_panel();recipe=json.loads(study.frozen.RECIPE_PATH.read_text());scores=study.br.momentum_score(panel['close'])
    rows,native,paths=[],{},{}
    for era,_,first,last in ERAS:
        replay=study.frozen._Replay(panel,recipe,first);dates=[str(panel['days'][replay.indices[0]-1]),*map(str,replay.days)]
        end=next((i for i,d in enumerate(dates) if d>last),len(dates));monthly=control.monthly_indices(panel,first);n=len(panel['days'])
        scenarios={'FR25':(np.column_stack([panel['fr25'],np.zeros(n)]),study.frozen._monthly_indices(panel),None)} if era=='late' else {}
        for clock in ('dynamic','monthly'):
            scenarios['momentum_'+clock]=study.br.select_targets(panel,panel['admitted'],scores,monthly,clock=clock)
            for variant in ('baseline','selected'):
                pos=signals[f'{era}_{variant}']
                scenarios[f'{variant}_selection_{clock}']=study.br.select_targets(panel,panel['admitted']&pos,scores,monthly,clock=clock)
                if era=='late':scenarios[f'{variant}_overlay_{clock}']=portfolio.overlay_targets(panel,.5+.5*pos,clock)
        for name,(weights,indices,_) in scenarios.items():
            for cost,delay in FRICTIONS:
                result,fills=replay.run_result(weights,indices,cost,delay);payload=study.frozen.report_payload(replay,result,fills)
                nav=np.array([float(r['nav_cnh']) for r in payload['nav_series']])[:end]
                period=[fill for fill in fills if fill['date']<=last] if era=='early' else fills
                rows.append(dict(era=era,scenario=name,cost_bp=cost,delay=delay,**metrics(nav,dates[:end],period)))
                if era=='late' and name in {'selected_overlay_dynamic','selected_selection_dynamic'} and cost==5:
                    key=f'{name}_c{cost}d{delay}';native[key+'_weights'],native[key+'_indices']=weights,indices;paths[key]=nav
                print('Portfolio',era,name,cost,delay,flush=True)
    write(OUT/'portfolio-results.json',rows);np.savez_compressed(WORK/'native-mappings.npz',**native);np.savez_compressed(WORK/'native-nav.npz',**paths)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','fit','evaluate','portfolios'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate,'portfolios':portfolios}[p.parse_args().stage]()
