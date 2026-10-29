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
import research_trend_modes as parent  # noqa: E402
from systematic_trading.research import multiscale_modes as model  # noqa: E402

study, stats, source = parent.study, parent.stats, parent.source
write, clean = parent.write, parent.clean
OUT = ROOT/'research/multiscale-modes-20261025-v1'
WORK = ROOT/'var/research/multiscale-modes-20261025-v1'
ERAS, FRICTIONS = parent.ERAS, parent.FRICTIONS
COMPONENTS = ('fixed','adaptive','protected','stress','hmm','hmm_protected','hmm_stress')
FAMILIES = tuple(f'{name}_{v}' for name in COMPONENTS for v in ('price','volume'))
VARIANTS = (*FAMILIES, 'selected', 'baseline')


def grid():
    rng = np.random.default_rng(2026102502)
    common = []
    for i in range(32):
        pick = lambda a: a[int(rng.integers(len(a)))]
        common.append(dict(fast=pick(model.FAST), slow=pick(model.SLOW), margin=pick((0., .15)),
            up_strength=pick((.5, 1., 2.)), up_quality=pick((.1, .25)), up_confirm=pick((1, 2)),
            down_strength=pick((.5, 1., 2.)), down_quality=pick((.1, .25)), down_confirm=pick((1, 2)),
            slow_strength=pick((.5, 1.5)), counter=pick(('block','confirm')), range_length=pick(model.FAST),
            range_drift=pick((.5, 1.5)), range_width=pick((4., 8.)), entry_pressure=pick((0., .1)),
            stop_atr=pick((2., 3., 4.)), counter_atr=pick((1., 1.5)),
            vol_trigger=pick((1.25, 1.5)), volume_trigger=pick((1.5, 2.)), tighten=pick((.5, .75)),
            up_probability=pick((.55,.7)),down_probability=pick((.55,.7)),slow_probability=pick((.55,.7))))
    return [dict(p, family=family, volume=volume, label=family+('_volume' if volume else '_price'))
            for family in COMPONENTS for volume in (False, True) for p in common]


def protocol():
    declared, fits = source.verified_fits()
    parent.verified()
    return dict(identity=OUT.name,version=model.VERSION,universe=sorted(fits),published_inputs=declared['data'],
        parent_protocol=study.digest(parent.OUT/'protocol.json'),parent_fits=study.digest(parent.OUT/'fit-manifest.json'),
        question='Combine fast reversal evidence with slow context, adaptive windows, and separately attributable protective exits.',
        windows='Fixed control fits fast10/21/42/63 and slow63/126/189/252. Adaptive versions choose daily within the same banks by trailing21 completed one-step logOLS forecast absolute errors/priorATR, capped5, plus .15*(1-R2); require0 or15% improvement and5-session dwell. No future pivots or full-period best window.',
        regimes='Fast up/down have separate strength, quality and confirmation. Independently parameterized range geometry. Raw down overrides range and slow up; unknown fast evidence retained at most5 sessions, slow direction21. Slow context uses its own signed slope threshold and R2>=.1. No volume condition may veto a price down exit.',
        entries='Eligibility rising edge of fresh fast up. Under slow down, either block or require twice entry strength and close above prior selected fast90% box plus.5priorATR. Volume pair additionally requires signed-volume pressure0/.1 and relative volume>=.7. After exit wait for a new eligibility edge, not automatic re-entry on a stale up label.',
        exits='All versions sell on fresh fast down. Protected adds monotone peak-close trailing level:2/3/4 entryATR aligned,1/1.5 countertrend. Use min(entryATR,currentATR), never loosen. Stress variant additionally multiplies distance by.5/.75 when ATR/price versus strictly prior63median exceeds1.25/1.5 OR (volume variant only) current raw volume versus prior21median exceeds1.5/2. Up-volume alone may tighten but cannot trigger an exit without a price breach.',
        execution='Close-time tests only, fill next open or one extra session; no assumed intraday stop fill. Test previously adopted level before updating from current close/volume. Initial level uses actual entry open and priorATR. All pending target changes binding FIFO. Cash-funded fees, idle cash zero. Stops do not cap gap losses; paper/live contract unchanged.',
        hmm='Separate3-state fast/slow diagonal Gaussian HMMs per ETF/cutoff, coupled at trading decisions, not a fitted factorial HMM. Observe all4 horizon slope/ATR/sqrtL values, averageefficiency, logrelativevolatility; volume pair adds signedpressure and logrelativevolume. Train mean/std scaling and EM on training only:2 deterministic initializations,25iterations,variancefloor.05,sticky transition pseudocount3. Map extreme drift centroids todown/up only if means cross-/+.05; middle to range only ifabsmean<=.15,otherwiseunknown. Forward filtered probabilities only for signals, no Viterbi/backward smoothing. Probability thresholds.55/.7 independently fitted forfastup,fastdown,slowcontext. Model parameters fixed during each evaluation; no claim that unsupervised states necessarily match human regime labels.',
        search='Same32 base parameter vectors paired across7 components and2 volume settings=448 candidates/ETF/cutoff. Fit one multiscale strategy per ETF, no short/long split of results. Top3 per family tested at all6 frictions. Require5 closed training trades and5% exposure if possible, else flag. Training-only family/global selection by worst-friction utility; all fits sealed before evaluation.',
        objective='Same frozen45/40/15 excess CAGR/Sharpe/regularizedCalmar utility, .5full+.5median3blocks-.25blockSD-.1tradeScarcity-.3exposureScarcity. No evaluation selection or old-strategy fallback.',
        evaluation='Train through2022/test2023-Jan3..2026-Oct16 and separately through2019/test2020..2022.500 training sessions after252warmup. Full52 pool; BIL separate. Compare old individually fitted short/long and their causal desired-position union, plus buyhold. All14 families, selected, union control; all6 frictions. Inspected development history, not untouched holdout. HMM training scores condition on emissions fitted to the full training sample and are in-sample calibration, not walk-forward model-fit evidence.',
        acceptance='Against prior mode union: higher paired medianSharpe and lower-quartileCAGR, at least90% within1pp CAGR/2pp DD guards in both chronologies/all frictions. Report full distributions, individual failures, turnover, IC21/alpha Holm per51 risky ETF tests. Portfolio: higherSharpe,<=1pp CAGR loss,no worseDD vs matched prior mode union and FR25(late)/momentum(early).',
        portfolio='Same full52 six-slot momentum selection, rankbuffer8,BIL vacancies. Binary long latch gates admission. FR25 multiplier.5+.5latch, divert toBIL; prior mode control uses short/long union with identical multiplier. Dynamic membership and cash-inclusive last-adoptedL1>=.10+monthend overlay versusmonthly. Sixfrictions, both eras selector, lateroverlay. Three native checks.',
        authority='Research only; no allocation, service restart, monitoring, broker or promotion changes.',
        code_hashes={str(p.relative_to(ROOT)).replace(chr(92),'/'):study.digest(p) for p in
            (Path(__file__),ROOT/'src/systematic_trading/research/multiscale_modes.py',ROOT/'src/systematic_trading/research/trend_hmm.py',ROOT/'scripts/research_trend_modes.py',
             ROOT/'src/systematic_trading/research/trend_modes.py',ROOT/'scripts/run_fitted_breakout_portfolios.py',ROOT/'scripts/revisit_breakout_research.py')})


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
        train.hmm_models=model.trend_hmm.fit_models(train,model.FAST,model.SLOW)
        scores=[score(train,model.classify(train,p)) for p in choices]
        finalists,selected={},{}
        for family in FAMILIES:
            ix=sorted([i for i,p in enumerate(choices) if p['label']==family],key=lambda i:(-scores[i]['score'],i))[:3]
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
    union=np.zeros(len(f.days),bool)
    for domain in ('short','long'):
        p=fits[domain+'_'+era]['selected']['selected']['parameters']
        cl=parent.model.classify(f.base,p)
        union|=parent.model.desired_position(cl['state'])
    return parent.model.simulate(f.base,dict(state=np.where(union,model.UP,model.DOWN)),cost_bp=cost,delay=delay)


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
            endf=f.truncated(last);hi=len(endf.days);lo=int(np.flatnonzero(f.days>=np.datetime64(first))[0]);cache={}
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
                        turn,fees,error=parent.previous.ledger(endf,sim,cost);max_error=max(max_error,error)
                        r=source.measure(endf,sim,sim['desired'],sim['held'],{k:v[:hi] for k,v in bill.items()},lo,hi)
                        r.update(cumulative=sim['nav'][-1]/sim['nav'][lo-1]-1,calmar=r['cagr']/abs(r['maxdd']) if abs(r['maxdd'])>1e-12 else None,
                            turnover_annual=float(turn[lo:hi].sum()*252/(hi-lo)),cost_bp_annual=float(fees[lo:hi].sum()*252/(hi-lo)*10000))
                        if cost==5 and delay==0:
                            forward=stats.forward_returns(endf.open,endf.close,bill['open'][:hi],bill['close'][:hi],21)
                            r['ic21']=stats.rank_ic(sim['desired'][lo:hi],forward[lo:hi],21)
                            if chosen:
                                train=f.truncated(cutoff);train.hmm_models=fit_['hmms'];tc=model.classify(train,config);ts=model.simulate(train,tc)
                                for field in ('nav','held','desired','state','fast_length','slow_length','stop'):
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
                            fast_lengths={str(k):int(np.sum(sim['fast_length'][lo:hi]==k)) for k in model.FAST},
                            slow_lengths={str(k):int(np.sum(sim['slow_length'][lo:hi]==k)) for k in model.SLOW},
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
