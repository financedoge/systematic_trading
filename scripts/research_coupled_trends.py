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
from systematic_trading.research import coupled_trends as model  # noqa: E402

study, stats, source = parent.study, parent.stats, parent.source
write, clean = parent.write, parent.clean
OUT = ROOT/'research/coupled-trends-20261025-v1'
WORK = ROOT/'var/research/coupled-trends-20261025-v1'
ERAS, FRICTIONS = parent.ERAS, parent.FRICTIONS
COMPONENTS = ('independent_uniform','independent_context','coupled_uniform','coupled_context')
FAMILIES = tuple(f'{name}_{v}' for name in COMPONENTS for v in ('price','volume'))
VARIANTS = (*FAMILIES, 'selected', 'baseline')


def grid():
    common=[dict(entry=e,exit=x,aligned_exit=.65,reset=.35,tight=t,wide=2*t)
            for e in (.35,.4,.5) for x in (.35,.5) for t in (2.,3.,4.)]
    return [dict(p,coupled=c,context=k,volume=v,label=('coupled' if c else 'independent')+
                 ('_context' if k else '_uniform')+('_volume' if v else '_price'))
            for c in (False,True) for k in (False,True) for v in (False,True) for p in common]


def protocol():
    declared,fits=source.verified_fits();parent.verified()
    return dict(identity=OUT.name,version=model.VERSION,universe=sorted(fits),published_inputs=declared['data'],
        parent_protocol=study.digest(parent.OUT/'protocol.json'),parent_fits=study.digest(parent.OUT/'fit-manifest.json'),
        question='Capture TLT countertrend rallies with interacting latent daily trends; preserve full-pool returns.',
        observations='Daily adjusted log return; volume pair adds log change of audited raw volume. Train-standard-deviation scaling preserving zero, clip emissions at +/-5 only. No rolling trend windows, moving averages or retrospective pivots. Return and volume changes have shared diagonal variance across states.',
        model='Nine joint states: L,S in down/range/up. Return mean additive L+S, range component zero, signed component magnitudes fitted by constrained weighted least squares .015..1.5 training daily standard deviations. Joint volume means free. Exact forward/backward EM20iterations with two initial short magnitudes .18/.4. Train-only selection by likelihood plus persistence prior; no evaluation refitting.',
        interaction='Coupled transition P(Lt|Lprev,Sprev)*P(St|Sprev,Lt); independent control pools away cross-factor dependencies. Slow stay probability .98.. .999 (conditional geometric durations50..1000 sessions); fast .65.. .97 (2.86..33.3). These are declared persistence constraints, not learned arbitrary timescales or fixed observation windows. Priors slow30,fast3,allcells .1. Both factors share observed return; decomposition may be weakly identified.',
        decision='Buy when forward P(short up)>=.35/.4/.5 and one-step expected return>0; slow down is no veto. Exit when P(short down)>=.35/.5. Context policy raises down threshold to.65 and doubles trailing distance when P(slow up)>=.55; otherwise short policy dominates. Compare uniform policy at same candidate budgets.',
        protection='Peak-close trail2/3/4 times entry open times fitted training daily return sigma, doubled4/6/8 under slow up in context policy. Monotone: never widen adopted level. Test old level then tighten for following close; initial level uses actual fill and lagged known context. No volatility-adaptive distance or volume-spike rule in this isolation test. No intraday fill promise.',
        reentry='Rearm only after P(short up)<.35 following exit; next qualifying positive-drift up permits new position. All close decisions binding FIFO, next open or extra1session;5/10/20bp per side, zero idle cash. Hold through range unless protective exit.',
        search='18 identical policy vectors per8 independent/coupled x uniform/context x price/volume families=144/ETF/cutoff. Top2 per family rescored at6frictions; require5closedtrades/5%exposure if possible else flag. Global training winner, no old-strategy fallback.',
        objective='Frozen45/40/15 excess CAGR/Sharpe/regularizedCalmar utility; full/block stability and scarcity penalties, worst friction finalist choice. HMM training fit scores are in-sample calibration, not rolling-fit validation.',
        evaluation='Full52, BIL separate; train<=2022/test2023-Jan3..2026-Oct16 and train<=2019/test2020..2022. Require500training after252warmup. Previous multiscale training-selected model as matched baseline. Both histories previously inspected development evidence. No optimization to TLT event dates.',
        illustrative_intervals=[['2023-09-01','2024-01-31'],['2024-06-01','2024-10-31']],
        acceptance='Both eras/all6frictions: medianSharpe and lowerquartileCAGR improve;>=90%fits within1ppCAGR/2ppDD guard. Portfolio higherSharpe <=1ppCAGRloss no worseDD vs matched prior and FR25late/momentumearly.',
        portfolio='Existing52ETF6slot positive126momentum/63vol rankbuffer8 BILvacancies. Position gate and FR25.5+.5position overlay. Dynamic membership and last-adopted cash-inclusiveL1>=.10+monthend overlay vs monthly. No changes to portfolio construction or costs.',
        authority='Research only; no deployment, allocation, recurring calculation, broker or approval changes.',
        code_hashes={str(p.relative_to(ROOT)).replace(chr(92),'/'):study.digest(p) for p in
                    (Path(__file__),ROOT/'src/systematic_trading/research/coupled_trends.py',
                     ROOT/'src/systematic_trading/research/trend_hmm.py',ROOT/'scripts/research_multiscale_modes.py')})


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
