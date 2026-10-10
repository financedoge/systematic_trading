"""Pinned selection-stage research; never changes the monitored strategy registry."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import read_json,checked_files,freeze_usd_bundle,run_usd_reference
from systematic_trading.research.selection_blend import ARMS,CONTROLS,VARIANTS,MAIN,BLENDS,COMPARISONS,RATIO_COMPARISONS
from systematic_trading.research.expanded_economics import job_name

_DATA=None


def prepare(root,runner):
    candidate=Path('var/research/candidate-pool-momentum-20261009-v1').resolve()
    economic=Path('var/research/expanded-economics-20261010-v1').resolve()
    if root.exists():
        raise FileExistsError('Preserve frozen selection study')
    for folder,names in [(candidate,['input_manifest.json','model_manifest.json','decision_manifest.json']),
                         (economic,['input_manifest.json','feature_manifest.json','decision_manifest.json'])]:
        for name in names:
            checked_files(folder,name)
    cp=read_json(candidate/'protocol.json')
    ep=read_json(economic/'protocol.json')
    p=dict(version='selection-blend-v1',client_date='2026-10-10',
        question='Does moving momentum/XGBoost/ridge ranks into top-six selection improve net performance?',
        start=ep['start'],evaluation_start=ep['evaluation_start'],end=ep['end'],initial_cash_usd='1000000',
        arms=list(ARMS),variants=VARIANTS,blends=BLENDS,main=list(MAIN),comparisons=COMPARISONS,
        ratio_comparisons=RATIO_COMPARISONS,bootstrap_blocks=[3,6,12],bootstrap_replications=10000,seed=2026101002,
        selection='Full 14 pool; normalize M1 momentum/activity total, XGBoost forecast and economic ridge total-forecast into midrank scores [-1,1]. Convex blend canonicalized to18 decimals to remove arithmetic tie noise, alphabetic ties, positive126 momentum gate, top6/min4; original defensive IEF/TLT/GLD fallback.',
        weights='M1 score retains 75% momentum and 25% volume. 75/25 and 50/50 two-way blends, 50/25/25 and equal three-way blends. Context/financial only. Every ridge blend has a same-availability training-mean-only control.',
        downstream='Primary selection-only intervention keeps inverse-volatility budgets, XGBoost tilt, relative momentum, adaptive trend, audited raw activity, USD ridge, and explicit final45 cap. No economic weight tilt. CR/FR are frozen sizing-only controls.',
        move_controls='NX removes downstream XGBoost at original selection; CEQNX/FEQNX also use equal blended selection. Other downstream layers remain fixed. CEQG/FEQG match CP target gross proportionally within positive membership and45 cap; infeasible capacity stays cash and is explicitly counted, never forced.',
        missing='If required macro model unavailable, whole selection reverts exactly to M1 selector, with the arm-specific downstream contract. Mean controls use identical macro readiness. Missing XGBoost or candidate data fails closed.',
        models='Reuse pinned causal per-pool one-year XGBoost and expanding context/financial ridge alpha1. No model refitting, feature search, universe changes or future labels.',
        labels='Model training contracts unchanged: XGB relative next-month close return; ridge absolute next-rebalance open return. Rank diagnostic uses common next-rebalance open labels, completed labels only.',
        screen=dict(min_sharpe_gain=.05,min_calmar_gain=.05,max_cagr_sacrifice=.005,max_drawdown_worsening=.005),
        assessment='Main blend must pass effect-size/risk screen vs CP and M1, positive Sharpe/Calmar gains under10/20bp and one-session delay; ridge blends must beat matched mean-only controls on both risk ratios. Robust superiority additionally requires positive annualized mean-return CI and Holm p<.05 across the entire registered family at all block lengths. No automatic promotion.',
        cost_bps=[5,10,20],delayed_sessions=1,cash_interest='zero',currency='USD',risk_free='zero',
        retrospective='2016-2020 descriptive calibration; 2021 onward already inspected evaluation. No untouched holdout. Do not tune weights after these outcomes.',
        stability='Report every registered blend, chronological annual returns and equal-length2021-2023 /2024-end subperiods. Compare neighboring weights; no post-hoc winning-parameter-only inference.',
        limitations=list(dict.fromkeys(cp['limitations']+ep['limitations']+[
            'Selection changes portfolio composition and can change adaptive-trend gross exposure even with unchanged sizing logic; compare explicit equal-blend gross controls and report budgets.',
            'Reused models have different forecast label horizons; ranks normalize scales, not target economics. Repeated study design follows inspected evidence, so all results remain exploratory.',
            'No new data fetched. Price auditing does not establish historical publication availability or tradability of reconstructed adjusted units.'])),
        promotion_eligible=False,budget=dict(replays=len(ARMS)*8,native=len(ARMS),new_model_fits=0,main_blends=len(MAIN),family=len(COMPARISONS)))
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(runner,root/'runner.py')
    for name,source in [('bars.json',candidate/'bars.json'),('raw.json',candidate/'raw.json'),
                        ('urth.json',candidate/'urth.json'),('xgb_usd.json',candidate/'models/14.json'),
                        ('macro.json',economic/'models.json'),('parent_selection.json',candidate/'selection.json')]:
        shutil.copyfile(source,root/name)
    (root/'controls').mkdir()
    for a in CONTROLS:
        source=(economic/'decisions'/(a+'.json')) if a!='URTH' else candidate/'decisions/URTH.json'
        shutil.copyfile(source,root/'controls'/(a+'.json'))
    write_json(root/'protocol.json',p)
    write_json(root/'data_receipt.json',dict(candidate=str(candidate),economic=str(economic),
        price_batch=read_json(candidate/'data_receipt.json')['batch'],economic_pin=read_json(economic/'data_receipt.json')['economic_pin'],
        image=read_json(economic/'data_receipt.json')['image'],
        parents={str(folder/name):sha256(folder/name) for folder,names in [(candidate,['input_manifest.json','model_manifest.json','decision_manifest.json']),
        (economic,['input_manifest.json','decision_manifest.json','feature_manifest.json'])] for name in names}))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/'protocol.json'),budget=p['budget'])


def initialize(root):
    global _DATA
    from systematic_trading.domain.market import PriceBar
    root=Path(root)
    bars=read_json(root/'bars.json')
    _DATA=dict(root=root,bars=bars,typed={s:[PriceBar.model_validate(r) for r in rows] for s,rows in bars.items()},
        raw={s:[PriceBar.model_validate(r) for r in rows] for s,rows in read_json(root/'raw.json').items()},
        models=read_json(root/'xgb_usd.json'),macro=read_json(root/'macro.json'),
        days=[r['trade_date'] for r in bars['SPY']],protocol=read_json(root/'protocol.json'),
        controls={a:read_json(root/'controls'/(a+'.json')) for a in CONTROLS})


def decision(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.signals.base import SignalContext
    from systematic_trading.signals.library import compute_signal_features
    from systematic_trading.research.strategy_catalog import defensive_cash_definition,instantiate_overlays
    from systematic_trading.research.rolling_tracking import select_rolling_model,RollingModelOverlay
    from systematic_trading.research.usd_tracking import UsdRidgeOverlay
    from systematic_trading.research.flow_concentration import ActivityConcentrationOverlay
    from systematic_trading.research.candidate_pool import CandidatePool,AuditedActivity
    from systematic_trading.research.selection_blend import SelectionBlend,match_gross
    from systematic_trading.research.construction_controls import FinalWeightCapOverlay
    from systematic_trading.research.momentum_replay import usd_instruments
    d=_DATA
    i=d['days'].index(day)
    asof=date.fromisoformat(day)
    histories={s:rows[max(0,i-500):i] for s,rows in d['typed'].items()}
    raw={s:rows[max(0,i-500):i] for s,rows in d['raw'].items()}
    model=select_rolling_model(d['models']['rolling'],histories,asof)
    context=SignalContext(as_of=asof,instruments={},bars_by_symbol=histories,trade_dates=[])
    forecasts={s:model.predict(compute_signal_features(symbol=s,context=context)) for s in histories}
    out,diagnostics={},{}
    for arm,recipe in [('BRIDGE',dict(blend=None,group=None)),*VARIANTS.items()]:
        overlays=instantiate_overlays(defensive_cash_definition())
        fitted=d['macro'][day][recipe['group']] if recipe['group'] else dict(ready=False)
        if recipe['group'] and fitted['last_label_end'] and fitted['last_label_end']>fitted['known_through']:
            raise ValueError('Future ridge label')
        selector=SelectionBlend(overlays[0],recipe,forecasts,fitted) if recipe['blend'] else CandidatePool(overlays[0],'M1')
        overlays[0]=selector
        bound=[]
        for overlay in overlays:
            if isinstance(overlay,RollingModelOverlay):
                if recipe.get('remove_xgb'):
                    continue
                overlay.model=model
            elif isinstance(overlay,UsdRidgeOverlay):
                overlay.schedule=d['models']['usd']
            elif isinstance(overlay,ActivityConcentrationOverlay):
                overlay=AuditedActivity(overlay.spec,raw)
            bound.append(overlay)
        targets=_target_schedule(instruments={s:usd_instruments()[s] for s in histories},bars_by_symbol=histories,
            trade_dates=[asof],rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),cash_reserve_weight=D('.02'),
            sleeve_name='candidate-pool-momentum-v1',target_overlays=bound)[asof]
        uncapped={t.symbol:t.target_weight for t in targets}
        targets=FinalWeightCapOverlay().apply(targets,None)
        gross_control=None
        if recipe.get('match_gross'):
            total=sum((D(t['target_weight']) for t in d['controls']['CP'][day]['targets']),D(0))
            targets,gross_control=match_gross(targets,total)
        if arm=='BRIDGE':
            for control,current in [('M1',uncapped),('CP',{t.symbol:t.target_weight for t in targets})]:
                if current!={t['symbol']:D(t['target_weight']) for t in d['controls'][control][day]['targets']}:
                    raise ValueError('M1/cap replay no longer exact')
            continue
        held={t.symbol for t in targets if t.target_weight>0}
        if len(held)>6 or not held.issubset(selector.observation['selected']):
            raise ValueError('Downstream overlay changed selection contract')
        if any(t.target_weight>D('.45') or t.target_weight<0 for t in targets):
            raise ValueError('Cap/long-only violation')
        original=set(t['symbol'] for t in d['controls']['CP'][day]['targets'] if D(t['target_weight'])>0)
        out[arm]=dict(signal_session=day,known_through=d['days'][i-1],targets=[t.model_dump(mode='json') for t in targets])
        diagnostics[arm]=dict(selected=sorted(held),parent_selected=sorted(original),
            selected_before_downstream=selector.observation['selected'],eligible=selector.observation['eligible'],
            fallback=selector.observation['fallback'],abstained=getattr(selector,'abstained',False),
            rank_table=getattr(selector,'rank_table',None),gross=str(sum((t.target_weight for t in targets),D(0))),
            gross_control=gross_control,changes=len(held-original),
            parent_gross=str(sum((D(t['target_weight']) for t in d['controls']['CP'][day]['targets']),D(0))))
        if diagnostics[arm]['abstained'] and not recipe.get('remove_xgb') and not recipe.get('match_gross'):
            if {t.symbol:t.target_weight for t in targets}!={t['symbol']:D(t['target_weight']) for t in d['controls']['CP'][day]['targets']}:
                raise ValueError('Unavailable macro did not revert exactly to CP')
    return day,dict(decisions=out,diagnostics=diagnostics,xgb_forecasts=forecasts)


def freeze_decisions(root,records):
    for a in ARMS:
        rows=read_json(root/'controls'/(a+'.json')) if a in CONTROLS else {day:v['decisions'][a] for day,v in sorted(records.items())}
        write_json(root/'decisions'/(a+'.json'),rows)
    write_json(root/'selection.json',{day:v['diagnostics'] for day,v in sorted(records.items())})
    write_json(root/'forecasts.json',{day:v['xgb_forecasts'] for day,v in sorted(records.items())})
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in (root/'decisions').glob('*.json')}|
               {name:sha256(root/name) for name in ('selection.json','forecasts.json')})


def jobs():
    return [(a,c,delay,w) for a in ARMS for c,delay in ((5,0),(10,0),(20,0),(5,1)) for w in ('full','evaluation')]


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    root=_DATA['root']
    p=_DATA['protocol']
    arm,cost,delay,window=job
    name=job_name(job)
    bars=_DATA['bars'] if arm!='URTH' else {'URTH':read_json(root/'urth.json')}
    if arm=='F3':
        bars={s:r for s,r in bars.items() if s not in ('XLE','XLB')}
    start=p['start'] if window=='full' else p['evaluation_start']
    quotes,sessions=quotes_for_data(bars,_DATA['days'],start)
    decisions={s:v for s,v in read_json(root/'decisions'/(arm+'.json')).items() if s>=start}
    if arm=='URTH' and window=='evaluation':
        row=dict(next(iter(read_json(root/'decisions/URTH.json').values())))
        row.update(signal_session=sessions[0],known_through=_DATA['days'][_DATA['days'].index(sessions[0])-1])
        decisions={sessions[0]:row}
    if delay:
        decisions={sessions[sessions.index(s)+delay]:v for s,v in decisions.items() if sessions.index(s)+delay<len(sessions)}
    bundle=root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(id=arm,window=window,delay_sessions=delay,selection=VARIANTS.get(arm)),decisions,quotes,sessions,cost)
    output=root/'python'/(name+'.json')
    if output.exists():
        raise FileExistsError('Preserve completed economics')
    write_json(output,run_usd_reference(bundle))
    write_json(output.with_suffix('.receipt.json'),dict(sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json')))
    return name
