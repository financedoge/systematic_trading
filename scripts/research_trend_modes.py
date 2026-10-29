"""Predeclared per-ETF fitting/evaluation of separate trend-mode detectors."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import retest_postbreakout_trend as previous  # noqa: E402
from systematic_trading.research import trend_modes as model  # noqa: E402

study, stats, source = previous.study, previous.stats, previous.source
OUT = ROOT / "research/trend-modes-20261025-v1"
WORK = ROOT / "var/research/trend-modes-20261025-v1"
ERAS, FRICTIONS = previous.ERAS, study.FRICTIONS
FAMILIES = tuple(m + ("_volume" if v else "_price") for m in model.METHODS for v in (False, True))
VARIANTS = (*FAMILIES, "selected")
write, clean = previous.write, previous.clean


def grid(domain):
    """Same seeded independent-block search budget for every ETF/cutoff."""
    rng = np.random.default_rng(20261025 + (domain == "long"))
    lengths = model.LENGTHS[domain]
    result = []
    for method in model.METHODS:
        # Paired price and volume candidates share price parameters so volume's
        # conditional value is not confounded with unequal search budgets.
        candidates = []
        for i in range(64):
            choose = lambda values: values[int(rng.integers(len(values)))]
            r = dict(length=choose(lengths), drift=choose((.5, 1.5, 3.)), width=choose((4., 8., 12., 20.)),
                efficiency=choose((.25, .45, .65)), buffer=choose((0., .5, 1.)), confirm=choose((1, 2, 3)), activity=choose((.8, 1., 1.3, 1.6)))
            modes = {name: dict(length=choose(lengths), strength=choose((.5, 1., 2., 4.)),
                quality=choose((.1, .25, .4)), confirm=choose((1, 2, 3)), pressure=choose((0., .1, .2)),
                activity=choose((.7, .9, 1.1))) for name in ("up", "down")}
            if i == 0:
                r.update(length=lengths[1], drift=1.5, width=8., efficiency=.45, buffer=.5, confirm=2, activity=1.3)
                for p in modes.values():
                    p.update(length=lengths[1], strength=1., quality=.25, confirm=2, pressure=0., activity=.7)
            candidates.append(dict(method=method, range=r, **modes))
        for volume in (False, True):
            result.extend(dict(c, volume=volume, family=method + ("_volume" if volume else "_price")) for c in candidates)
    return result


def protocol():
    declared, fits = source.verified_fits()
    return dict(identity=OUT.name, version=model.VERSION, universe=sorted(fits),
        published_inputs=declared["data"], source_protocol_sha256=study.digest(source.OUTPUT / "protocol.json"),
        question="Can independently parameterized range/up/down detectors and a long-only transition latch retain consolidation and capture new uptrends?",
        range="Independent length, drift, central10/90% width/ATR, efficiency, persistence, box buffer and volume ceiling. Prior-day flat-range conditions/box; current close inside prior box +/- priorATR buffer overrides directional detectors on other timescales. No forced range label when evidence is absent.",
        direction="Independent up/down length, strength, quality, persistence and volume thresholds. Three methods: logOLS drift/ATR with R2; first/last-third rising/falling10/90% quantiles with price-path efficiency; fast/slow mean-log corridor with slow-mean direction and efficiency. All current-close features only, no future-confirmed pivots.",
        volume="Audited raw share volume divided by strictly prior21-session median, capped5x. Each direction: signed-return relative-volume pressure over max5/min63/Ldiv3, plus recent5-session participation. Range: prior5-session participation ceiling. Price-only paired configurations omit these conditions. This is signed price-volume evidence, not actual buyer/seller order flow; raw split/activity and historical-vintage limits remain.",
        resolution="Intact prior range box has priority. Otherwise one direction wins; conflicting up/down requires25% normalized strength/quality advantage, else unknown evidence. Unknown retains last confirmed mode; initial mode unknown. Track evidence and retained states separately.",
        trading="From warmup252, flat buys only on confirmed range/down -> up. Long holds through range or absent evidence; sells only on confirmed down, including up->range->down. Initial unknown->up does not buy. No stop, take-profit, time-exit or cooldown override. Desired state is an independent virtual latch; every target change fills at next open plus symmetric0/1 delay, binding FIFO. Cash earns0; costs funded without leverage.",
        grid={d:grid(d) for d in ("short", "long")},
        fit="384 independent-block candidates per ETF/domain/cutoff:64 per each of3 methods x price/volume, identical seed/grid per ETF. Each block's parameters are separate; they are jointly scored on realized training trading outcomes, not supervised hindsight trend labels. Top5 each family rescored across6 frictions. Prefer>=5 closed trades and>=5% exposure in all frictions; else choose best available and mark insufficient evidence. Maximize worst-friction full/3-block utility; select family winner and global winner on training only. No fallback to old strategy hides a poor new-mode result. Seal all fits before evaluation.",
        objective="Frozen45/40/15 excess CAGR/Sharpe/regularizedCalmar utility versus own buyhold; .5 full+.5 median of3 chronological blocks-.25 blockSD-.1 trade scarcity-.3 exposure scarcity. Regularized3% Calmar only in fitting; displayed Calmar actualDD.",
        evaluation="Two separate cutoffs: train through2022 evaluate2023-Jan3..2026-Oct16; train through2019 evaluate2020-Jan2..2022-Dec30. Require500 training sessions after252 warmup. Carry causal virtual state through evaluation; no boundary reset. Full52 pool, BIL separate cash reference. Both histories are previously inspected development evidence, not untouched holdouts. All6 frictions and all6 detector families plus train-selected global winner.",
        acceptance="Against existing individually fitted breakout baseline and buyhold: report all fits plus adequate-training subset; family requires higher median Sharpe/lower-quartileCAGR, >=90% within1pp CAGR and2pp DD guards vs prior baseline, both eras/all frictions. Descriptive alpha/IC with Holm adjustment per102 ETF/domain tests; no historical winning-subset gate.",
        portfolio="Train-selected modes only, same full52 liquidity-admitted six-slot98% momentum selector, union of short/long long-position latches, rank buffer8, BIL vacancies. Dynamic membership versus monthly. FR25 exposure overlay .5+.25short+.25long, diverted weight BIL; dynamic last-adopted cash-inclusiveL1>=.10+monthly versus monthly. Compare old baseline, ungated momentum, FR25; all6 frictions, both eras selector, later overlay throughOct12. Native representative dynamic/delayed checks. Higher Sharpe, CAGR loss<=1pp,no worseDD versus both matched baseline and FR25(late)/momentum(early).",
        authority="Research only. No service restart, allocation, funding, monitoring, broker, promotion or runtime changes.",
        code_hashes={str(p.relative_to(ROOT)).replace(chr(92),'/'):study.digest(p) for p in
            (Path(__file__), ROOT/'src/systematic_trading/research/trend_modes.py', ROOT/'scripts/run_fitted_breakout_portfolios.py', ROOT/'scripts/revisit_breakout_research.py')})


def prepare():
    p = clean(protocol())
    path = OUT / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != p:
        raise ValueError("Changed frozen protocol")
    write(path, p)
    print("Frozen", study.digest(path), flush=True)


def score(f, classified, cost=5, delay=0):
    sim = model.simulate(f, classified, cost_bp=cost, delay=delay)
    start, end = 252, len(f.days)
    bh = np.full(end, np.nan)
    bh[start:] = f.close[start:] / f.open[start] / (1 + cost / 10000)
    window = lambda a, lo, hi: stats.nav_stats(np.r_[1. if lo == start else a[lo - 1], a[lo:hi]])
    full, base = window(sim['nav'],start,end), window(bh,start,end)
    blocks = [study.old.utility(window(sim['nav'],a,b),window(bh,a,b)) for a,b in study.old.block_bounds(start,end)]
    closed = sum(e['exit_index'] is not None for e in sim['episodes'])
    exposure = float(sim['held'][start:].mean())
    value = (.5*study.old.utility(full,base)+.5*np.median(blocks)-.25*np.std(blocks)
             -.1*max(0,10-closed)/10-.3*max(0,.20-exposure)/.20)
    return dict(score=float(value),cagr=full['cagr'],sharpe=full['sharpe'],maxdd=full['maxdd'],closed=closed,exposure=exposure)


def fit_job(job):
    symbol, phash = job
    f = model.Features.build(study.load_asset(symbol))
    result = {}
    for domain in ('short','long'):
        choices = grid(domain)
        for era, cutoff, _, _ in ERAS:
            train = f.truncated(cutoff)
            if len(train.days)-252 < 500:
                result[domain+'_'+era] = dict(available=False,reason='Insufficient training history')
                continue
            base = [score(train,model.classify(train,c)) for c in choices]
            shortlists = {family:sorted([i for i,c in enumerate(choices) if c['family']==family],key=lambda i:(-base[i]['score'],i))[:5] for family in FAMILIES}
            finalists, selected = {}, {}
            for family, ix in shortlists.items():
                for i in ix:
                    classified = model.classify(train,choices[i])
                    rows = [base[i]]+[score(train,classified,c,d) for c,d in FRICTIONS[1:]]
                    finalists[i] = dict(parameters=choices[i],training=rows,worst=min(r['score'] for r in rows),
                        evidence=all(r['closed']>=5 and r['exposure']>=.05 for r in rows))
                adequate = [i for i in ix if finalists[i]['evidence']]
                best = min(adequate or ix,key=lambda i:(-finalists[i]['worst'],i))
                selected[family] = dict(index=best,**finalists[best])
            pool = [r['index'] for r in selected.values()]
            adequate = [i for i in pool if finalists[i]['evidence']]
            best = min(adequate or pool,key=lambda i:(-finalists[i]['worst'],i))
            selected['selected'] = dict(index=best,**finalists[best])
            result[domain+'_'+era] = dict(available=True,training_end=str(train.days[-1]),training_sessions=len(train.days)-252,
                selected=selected,base_scores=base,finalists=finalists)
    write(WORK/'fits'/f'{symbol}.json',dict(symbol=symbol,protocol_sha256=phash,fits=result))
    return symbol


def verified(require_fits=True):
    if clean(protocol()) != json.loads((OUT/'protocol.json').read_text()):
        raise ValueError("Protocol/input change")
    if not require_fits:
        return {}
    manifest=json.loads((OUT/'fit-manifest.json').read_text())
    if manifest['protocol_sha256']!=study.digest(OUT/'protocol.json'):
        raise ValueError('Fit protocol mismatch')
    result={}
    for name,h in manifest['files'].items():
        p=WORK/'fits'/name
        if study.digest(p)!=h:
            raise ValueError('Fit changed')
        r=json.loads(p.read_text());result[r['symbol']]=r['fits']
    if len(result)!=52:
        raise ValueError('Incomplete pool')
    return result


def fit():
    verified(False)
    symbols=json.loads((OUT/'protocol.json').read_text())['universe']
    h=study.digest(OUT/'protocol.json')
    jobs=[(s,h) for s in symbols if not (WORK/'fits'/f'{s}.json').exists()]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol in pool.map(fit_job,jobs):
            print('Fitted',symbol,flush=True)
    files={p.name:study.digest(p) for p in sorted((WORK/'fits').glob('*.json'))}
    if len(files)!=52 or any(json.loads((WORK/'fits'/p).read_text())['protocol_sha256']!=h for p in files):
        raise ValueError('Incomplete/mixed fit files')
    write(OUT/'fit-manifest.json',dict(protocol_sha256=h,files=files))


def evaluate():
    if (OUT/'asset-results.json').exists():
        raise ValueError('Preserve completed evidence')
    fits=verified();panel=study.frozen._load_panel();symbols=list(panel['symbols'])
    signals={f'{d}_{e}_selected':np.zeros(panel['close'].shape,bool) for d in ('short','long') for e,*_ in ERAS}
    billdata=study.load_asset('BIL');billix={str(d):i for i,d in enumerate(billdata['days'])}
    rows,choices,diagnostics=[],[],{}
    max_error=0.
    for symbol in sorted(fits):
        f=model.Features.build(study.load_asset(symbol));indices={str(d):i for i,d in enumerate(f.days)}
        panel_ix=[indices[str(d)] for d in panel['days']]
        bill={k:np.array([billdata[k][billix[str(d)]] if str(d) in billix else np.nan for d in f.days]) for k in ('open','close')}
        for domain in ('short','long'):
            for era,cutoff,first,last in ERAS:
                fit_=fits[symbol][domain+'_'+era]
                if not fit_['available']:
                    continue
                lo=int(np.flatnonzero(f.days>=np.datetime64(first))[0]);hi=int(np.flatnonzero(f.days<=np.datetime64(last))[-1])+1
                endf=f.truncated(last)
                cache={}
                for variant in VARIANTS:
                    chosen=fit_['selected'][variant];config=chosen['parameters'];index=chosen['index']
                    classified=model.classify(endf,config)
                    choices.append(dict(symbol=symbol,domain=domain,era=era,variant=variant,evidence=chosen['evidence'],parameters=config))
                    for cost,delay in FRICTIONS:
                        key=(index,cost,delay)
                        if key not in cache:
                            sim=model.simulate(endf,classified,cost_bp=cost,delay=delay)
                            turn,fees,error=previous.ledger(endf,sim,cost);max_error=max(max_error,error)
                            r=source.measure(endf,sim,sim['desired'],sim['held'],{k:v[:hi] for k,v in bill.items()},lo,hi)
                            r.update(cumulative=sim['nav'][-1]/sim['nav'][lo-1]-1,calmar=r['cagr']/abs(r['maxdd']) if abs(r['maxdd'])>1e-12 else None,
                                turnover_annual=float(turn[lo:hi].sum()*252/(hi-lo)),cost_bp_annual=float(fees[lo:hi].sum()*252/(hi-lo)*10000),
                                evidence_fraction=float((classified['evidence'][lo:hi]!=model.UNKNOWN).mean()),
                                state_fractions={str(s):float((classified['state'][lo:hi]==s).mean()) for s in (model.DOWN,model.RANGE,model.UP,model.UNKNOWN)})
                            if cost==5 and delay==0:
                                forward=stats.forward_returns(endf.open,endf.close,bill['open'][:hi],bill['close'][:hi],21)
                                r['ic21']=stats.rank_ic(sim['desired'][lo:hi],forward[lo:hi],21)
                                train=f.truncated(cutoff);trainclass=model.classify(train,config);trainpath=model.simulate(train,trainclass)
                                for field in ('nav','held','desired','state','evidence'):
                                    np.testing.assert_allclose(trainpath[field],sim[field][:len(train.days)],atol=1e-10,rtol=0,equal_nan=True)
                                rescored=score(train,trainclass)
                                for field in rescored:
                                    np.testing.assert_allclose(rescored[field],chosen['training'][0][field],atol=1e-10,rtol=0)
                            cache[key]=(r,sim)
                        r,sim=cache[key]
                        rows.append(dict(symbol=symbol,domain=domain,era=era,variant=variant,cost_bp=cost,delay=delay,training_evidence=chosen['evidence'],**r))
                        if variant=='selected' and cost==5 and delay==0:
                            # Full prefix is used only to map actual signal dates; early
                            # mapping is zero beyond its sealed evaluation cutoff.
                            mapped=np.zeros(len(panel_ix),bool)
                            for j,i in enumerate(panel_ix):
                                if i<hi:mapped[j]=sim['desired'][i]
                            signals[f'{domain}_{era}_selected'][:,symbols.index(symbol)]=mapped
                            if era=='late':
                                from build_etf_breakout_failure_report import interval_accounting
                                episodes=[]
                                for ep in sim['episodes']:
                                    a,x=ep['entry_index'],ep['exit_index']
                                    if x is not None and x<lo:continue
                                    mark=ep['exit_price'] if x is not None else f.close[hi-1]
                                    episodes.append(dict(entry=str(f.days[a]),exit=str(f.days[x]) if x is not None else None,
                                        entry_index=a,exit_index=x,entry_price=ep['entry'],exit_or_mark=mark,
                                        net_return=float(mark/ep['entry']*(.9995 if x is not None else 1)/1.0005-1),carried=a<lo))
                                diagnostics[symbol+'_'+domain]=dict(parameters=config,trades=episodes,accounting=interval_accounting(endf,sim,lo,hi),
                                    range_held_sessions=int(np.sum(sim['held'][lo:hi]&(sim['state'][lo:hi]==model.RANGE))))
        print('Evaluated',symbol,flush=True)
    for era,*_ in ERAS:
        for variant in VARIANTS:
            rr=[r for r in rows if r['era']==era and r['variant']==variant and r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL']
            for name,values in [('alpha_holm_p',[r['p'] for r in rr]),('ic21_holm_p',[r['ic21']['p'] for r in rr])]:
                for r,p in zip(rr,stats.holm(values),strict=True):r[name]=p
    write(OUT/'asset-results.json',rows);write(OUT/'selected-parameters.json',choices);write(OUT/'diagnostics.json',diagnostics)
    np.savez_compressed(WORK/'signals.npz',**signals)
    write(OUT/'validation.json',dict(asset_cases=len(rows),ledger_max_relative_error=max_error,training_prefix_and_scores_reproduced=True,
        all_fits_sealed_before_evaluation=True,signal_sha256=study.digest(WORK/'signals.npz')))


def portfolios():
    import run_fitted_breakout_portfolios as parent
    import revisit_breakout_research as control
    from retest_fr25_lifecycle_review import metrics
    verified()
    if (OUT/'portfolio-results.json').exists():raise ValueError('Preserve completed portfolio evidence')
    receipt=json.loads((OUT/'validation.json').read_text())
    if study.digest(WORK/'signals.npz')!=receipt['signal_sha256']:raise ValueError('Changed signals')
    with np.load(WORK/'signals.npz',allow_pickle=False) as a:signals={k:a[k] for k in a.files}
    previous.verified()
    with np.load(previous.WORK/'signals.npz',allow_pickle=False) as a:
        for k in a.files:
            if k.endswith('_baseline'):signals[k]=a[k]
    panel=study.frozen._load_panel();recipe=json.loads(study.frozen.RECIPE_PATH.read_text());scores=study.br.momentum_score(panel['close'])
    rows,native,paths=[],{},{}
    for era,_,first,last in ERAS:
        replay=study.frozen._Replay(panel,recipe,first)
        dates=[str(panel['days'][replay.indices[0]-1]),*map(str,replay.days)]
        end=next((i for i,d in enumerate(dates) if d>last),len(dates));monthly=control.monthly_indices(panel,first);n=len(panel['days'])
        scenarios={'FR25':(np.column_stack([panel['fr25'],np.zeros(n)]),study.frozen._monthly_indices(panel),None)} if era=='late' else {}
        for clock in ('dynamic','monthly'):
            scenarios['momentum_'+clock]=study.br.select_targets(panel,panel['admitted'],scores,monthly,clock=clock)
            for variant in ('baseline','selected'):
                s,l=signals[f'short_{era}_{variant}'],signals[f'long_{era}_{variant}']
                scenarios[f'{variant}_selection_{clock}']=study.br.select_targets(panel,panel['admitted']&(s|l),scores,monthly,clock=clock)
                if era=='late':scenarios[f'{variant}_overlay_{clock}']=parent.overlay_targets(panel,.5+.25*s+.25*l,clock)
        for name,(weights,indices,_) in scenarios.items():
            for cost,delay in FRICTIONS:
                result,fills=replay.run_result(weights,indices,cost,delay)
                payload=study.frozen.report_payload(replay,result,fills)
                nav=np.array([float(r['nav_cnh']) for r in payload['nav_series']])[:end]
                period=[fill for fill in fills if fill['date']<=last] if era=='early' else fills
                rows.append(dict(era=era,scenario=name,cost_bp=cost,delay=delay,**metrics(nav,dates[:end],period)))
                if era=='late' and name in {'selected_overlay_dynamic','selected_selection_dynamic'} and cost==5:
                    key=f'{name}_c{cost}d{delay}';native[key+'_weights'],native[key+'_indices']=weights,indices;paths[key]=nav
                print('Portfolio',era,name,cost,delay,flush=True)
    write(OUT/'portfolio-results.json',rows)
    np.savez_compressed(WORK/'native-mappings.npz',**native);np.savez_compressed(WORK/'native-nav.npz',**paths)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','fit','evaluate','portfolios'))
    {'prepare':prepare,'fit':fit,'evaluate':evaluate,'portfolios':portfolios}[parser.parse_args().stage]()
