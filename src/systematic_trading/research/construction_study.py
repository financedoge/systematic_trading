"""Finite fallback attribution and cap study over pinned published inputs."""
from datetime import date, datetime, UTC
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import write_json, sha256
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.construction_controls import (
    gross, ConstantExposureOverlay, FinalWeightCapOverlay, ForecastRankPool, match_gross, calibrate_exposure,
)

RANK_ARMS = ['P8','P10','N6','N8','N10','X6','X8','X10']
STRATEGIES = ['F0', 'F3', 'E0', 'E1', 'C0', 'C3', *RANK_ARMS]
ARMS = [*STRATEGIES,'RP','URTH']
COMPARISONS = [('F3', 'E0'), ('F3', 'E1'), ('E1', 'E0'), ('C0', 'F0'), ('C3', 'F3'),
    ('X6','F3'),('X8','P8'),('X10','P10'),('X6','N6'),('X8','N8'),('X10','N10'),
    ('P8','F3'),('P10','F3'),('X8','X6'),('X10','X6')]
LABELS = dict(F0='Existing fallback', F3='Qualifying defensive ETFs + cash',
    E0='Constant exposure, calibrated on 2016–2020', E1='F0 basket with F3 monthly invested budget',
    C0='Existing fallback + 45% final target cap', C3='Defensive cash + 45% final target cap',
    RP='Risk parity', URTH='URTH buy and hold')
LABELS.update({a:f'Price/volume top {a[1:]} + XGBoost tilt' for a in ['P8','P10']})
LABELS.update({a:f'Price/volume top {a[1:]} without XGBoost tilt' for a in ['N6','N8','N10']})
LABELS.update({a:f'XGBoost ranking top {a[1:]} without XGBoost tilt' for a in ['X6','X8','X10']})
_DATA = None


def prepare(root):
    from systematic_trading.research.fallback_study import prepare as prepare_parent
    from systematic_trading.config import AppSettings
    from systematic_trading.storage.factory import create_trading_store
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.research.fallback_protocol import BASELINE
    if root.exists():
        raise FileExistsError('A frozen study cannot be overwritten')
    settings = AppSettings()
    state = control_state(create_trading_store(settings))
    if state['sota_key'] != BASELINE:
        raise ValueError('SOTA changed; register a new comparison against the actual hurdle')
    root.mkdir(parents=True)
    parent = prepare_parent(root/'parent')
    p = read_json(root/'parent/protocol.json')
    protocol = dict(version='fallback-ranking-construction-v1', registered_at=datetime.now(UTC).isoformat(),
        question='Test XGBoost ranking versus tilting at top 6/8/10; isolate fallback exposure and final concentration.',
        baseline=p['baseline'], baseline_control_revision=state['revision'], end=p['end'],
        calibration_start='2016-01-04', calibration_end='2020-12-31', evaluation_start='2021-01-04',
        initial_cash_usd='1000000', accounting_currency='USD', cash_interest='zero',
        arms=LABELS, comparisons=[dict(candidate=a, control=b) for a,b in COMPARISONS], family_size=len(COMPARISONS),
        cost_bps=[5,10,20], delay_sessions=[0,1], bootstrap_blocks=[3,6,12], bootstrap_replications=20000,
        seed=2026100702, final_target_cap='.45', cap_excess='cash, no redistribution', drift_rebalancing=False,
        calibration='E0 scale = mean F3 target gross / mean F0 target gross over 2016–2020 monthly decisions. Frozen thereafter.',
        matched_budget='E1 applies the same-date F3 gross budget to F0 composition; both use only the prior completed close.',
        jobs='Sixteen arms × three costs in evaluation; fourteen strategy arms with one additional execution-session delay; F0/F3/C0/C3 full-history context at 5bp: 66 replays.',
        native_jobs='All sixteen primary evaluation arms at 5bp and no extra delay.',
        ranking=dict(baskets=[6,8,10],training='Unchanged pinned monthly one-year XGBoost models; no refits or parameter search.',
            prediction_target='Next-month adjusted USD return minus the universe mean; a relative-return forecast, not a new momentum label.',
            eligibility='Same positive 252-session momentum gate; at least four qualifiers or F3 defensive/cash fallback.',
            ordering='Descending forecast, alphabetical ties; never force selection of ineligible assets to fill N slots.',
            weights='Same incoming inverse-volatility weights, pool gross-up, later relative/adaptive/activity/USD layers; no separate XGBoost tilt in X/N arms.',
            controls='P: original price/volume rank plus XGBoost tilt. N: same rank without XGBoost tilt. X: forecast ranking without XGBoost tilt. P6 is exactly F3.',
            constraints='Inherited final weights for all ranking arms. Do not combine cap and ranking winners in this family.'),
        resource_policy='All logical CPUs for independent jobs; native lanes share all CPUs with memory headroom.',
        economic_screen=dict(min_sharpe_gain=.05,min_calmar_gain=.05,min_drawdown_reduction=.02,max_cagr_sacrifice=.005,
            meaning='Research screen for F3 versus E0, not an operator risk tolerance or promotion approval.'),
        decision_rule='Report all fifteen registered contrasts, cost/delay consistency and uncertainty. No tuning, automatic combination or promotion. Caps are assessed as concentration controls even without return gains.',
        limitations=[*[s for s in p['limitations'] if '45% cap' not in s],
            '2021 onward was already inspected. This is chronological calibration/evaluation, not untouched out-of-sample evidence.',
            'Constant exposure is matched on training target budgets, not realized future risk or average holdings.',
            'E1 is an attribution control, not an independent alpha model; different composition can cause different realized risk.',
            'Final target caps do not constrain held weights between monthly rebalances or after execution gaps.',
            'Evaluation restarts all arms with USD 1m in cash; full-history context has different opening positions.',
            'Only one 2022–23 fallback episode is present after calibration; daily observations are not independent crises.',
            'Ratio bootstrap intervals are marginal, not simultaneous familywise bounds. Paired mean-return tests use Holm correction across all fifteen registered contrasts.',
            'Ranking/exposure/cap variants are finite research only and are not selectable for monitoring or execution.'],
        promotion_eligible=False)
    write_json(root/'protocol.json', protocol)
    shutil.copytree(root/'parent/source', root/'source')
    write_json(root/'input_manifest.json', {f.relative_to(root).as_posix():sha256(f)
        for f in sorted(root.rglob('*')) if f.is_file()})
    return dict(root=str(root.resolve()),parent=parent,protocol_sha256=sha256(root/'protocol.json'),replays=len(jobs()))


def initialize(root):
    global _DATA
    from systematic_trading.research import fallback_study
    root = Path(root)
    checked_files(root, 'input_manifest.json')
    fallback_study.initialize(str(root/'parent'))
    _DATA = dict(root=root,protocol=read_json(root/'protocol.json'),bars=read_json(root/'parent/bars.json'))


def decision(day):
    from systematic_trading.research import fallback_study
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.research.fallback_protocol import definition
    day, rows = fallback_study.calculate_decision(day)
    data = fallback_study._DATA
    index = data['days'].index(day)
    histories = {s:bars[max(0,index-500):index] for s,bars in data['typed'].items()}
    targets = _target_schedule(instruments=instruments_for_definition(definition('F0')), bars_by_symbol=histories,
        trade_dates=[date.fromisoformat(day)], rebalance_frequency='daily',lookback_bars=63,
        max_weight=D('.45'),cash_reserve_weight=D('.02'),sleeve_name='risk-parity-control',target_overlays=[])[date.fromisoformat(day)]
    rows['RP'] = dict(signal_session=day,known_through=data['days'][index-1],targets=[t.model_dump(mode='json') for t in targets])
    from systematic_trading.research import instantiate_overlays
    from systematic_trading.research.rolling_tracking import select_rolling_model
    from systematic_trading.signals.base import SignalContext
    from systematic_trading.signals.library import compute_signal_features
    model=select_rolling_model(data['rolling_models'],histories,date.fromisoformat(day))
    context=SignalContext(as_of=date.fromisoformat(day),instruments=instruments_for_definition(definition('F3')),
        bars_by_symbol=histories,trade_dates=[])
    forecasts={s:model.predict(compute_signal_features(symbol=s,context=context)) for s in histories}
    original_pool=instantiate_overlays(definition('F3'))[0]
    rows['pv_scores']={s:str(v.total) for s,v in original_pool._selection_scores(targets,context).items()}
    for arm in RANK_ARMS:
        d=definition('F3');overlays=list(instantiate_overlays(d));overlays[0].top_n=int(arm[1:])
        if arm.startswith('X'):
            overlays[0]=ForecastRankPool(overlays[0],forecasts)
        if not arm.startswith('P'):
            overlays=[o for o in overlays if o.__class__.__name__!='RollingModelOverlay']
        for overlay in overlays:
            if overlay.__class__.__name__=='RollingModelOverlay':
                overlay.model=model
            if overlay.__class__.__name__=='UsdRidgeOverlay':
                overlay.schedule=data['usd_models']
        targets=_target_schedule(instruments=instruments_for_definition(d),bars_by_symbol=histories,
            trade_dates=[date.fromisoformat(day)],rebalance_frequency='daily',lookback_bars=63,
            max_weight=D('.45'),cash_reserve_weight=D('.02'),sleeve_name=d.sleeve_name,target_overlays=overlays)[date.fromisoformat(day)]
        gross(targets)
        rows[arm]=dict(signal_session=day,known_through=data['days'][index-1],targets=[t.model_dump(mode='json') for t in targets],
            diagnostic=dict(fallback=overlays[0].cash_budget_active,eligible=rows['F3']['diagnostic']['eligible'],
                top_n=int(arm[1:]),selection='xgboost' if arm.startswith('X') else 'price_volume',
                selected=[t.symbol for t in targets if t.target_weight>0],target_cash=str(1-gross(targets))))
    rows['forecasts']=forecasts
    return day, rows


def freeze_decisions(root, rows):
    from systematic_trading.research.fallback_study import freeze_decisions as freeze_parent
    from systematic_trading.signals.base import apply_target_overlays
    freeze_parent(root/'parent',rows)
    p = read_json(root/'protocol.json')
    decisions = {k:{day:rows[day][k] for day in sorted(rows)} for k in ['F0','F3','RP',*RANK_ARMS]}
    calibration = calibrate_exposure(decisions['F0'],decisions['F3'],evaluation_start=p['evaluation_start'])
    decisions.update({k:{} for k in ['E0','E1','C0','C3']})
    diagnostics = []
    for day in sorted(rows):
        f0,f3 = ([AllocationTarget.model_validate(t) for t in rows[day][k]['targets']] for k in ['F0','F3'])
        transformed = dict(E1=match_gross(f0,f3),
            C0=apply_target_overlays(f0,[FinalWeightCapOverlay()],None),
            C3=apply_target_overlays(f3,[FinalWeightCapOverlay()],None))
        if day>=p['evaluation_start']:
            transformed['E0']=apply_target_overlays(f0,[ConstantExposureOverlay(D(calibration['scale']))],None)
        for key, targets in transformed.items():
            decisions[key][day] = dict(signal_session=day,known_through=rows[day]['F0']['known_through'],
                targets=[t.model_dump(mode='json') for t in targets],
                diagnostic=dict(target_cash=str(1-gross(targets)),control=key))
        diagnostics.append(dict(day=day,fallback=rows[day]['F3']['diagnostic']['fallback'],
            f0_gross=str(gross(f0)),f3_gross=str(gross(f3)),e1_gross=str(gross(transformed['E1'])),
            f0_capped=[t.symbol for t in f0 if t.target_weight>D('.45')],
            f3_capped=[t.symbol for t in f3 if t.target_weight>D('.45')]))
        if abs(gross(f3)-gross(transformed['E1']))>D('1e-20'):
            raise ValueError('Matched target budgets differ')
    for key, value in decisions.items():
        write_json(root/'decisions'/(key+'.json'),value)
    write_json(root/'calibration.json',calibration)
    write_json(root/'decision_diagnostics.json',diagnostics)
    write_json(root/'forecasts.json',{d:rows[d]['forecasts'] for d in sorted(rows)})
    write_json(root/'price_volume_scores.json',{d:rows[d]['pv_scores'] for d in sorted(rows)})
    paths = [*sorted((root/'decisions').glob('*.json')),root/'calibration.json',root/'decision_diagnostics.json',
             root/'parent/baseline_parity.json',root/'forecasts.json',root/'price_volume_scores.json']
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in paths})
    return dict(calibration=calibration,baseline_parity=read_json(root/'parent/baseline_parity.json'))


def jobs():
    return ([(a,c,0,'evaluation') for a in ARMS for c in [5,10,20]]
        +[(a,5,1,'evaluation') for a in STRATEGIES]+[(a,5,0,'full') for a in ['F0','F3','C0','C3']])


def job_name(job):
    arm,cost,delay,period = job
    return f'{arm}-{period}-cost{cost}-delay{delay}'


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    root = _DATA['root'];p=_DATA['protocol']
    checked_files(root,'decision_manifest.json')
    arm,cost,delay,period = job
    start = p['calibration_start'] if period=='full' else p['evaluation_start']
    days = [r['trade_date'] for r in _DATA['bars']['SPY']]
    bars = {'URTH':read_json(root/'parent/urth.json')} if arm=='URTH' else _DATA['bars']
    quotes,sessions = quotes_for_data(bars,days,start)
    if arm=='URTH':
        decisions = {sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=D(1),rationale='buy and hold').model_dump(mode='json')])}
    else:
        decisions = {d:r for d,r in read_json(root/'decisions'/(arm+'.json')).items() if d>=start}
    if delay:
        decisions = {sessions[sessions.index(d)+delay]:r for d,r in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name = job_name(job)
    recipe = dict(id=arm,name=LABELS[arm],period=period,delay=delay,
        parent=read_json(root/'parent/protocol.json')['recipes'].get('F3' if arm in ['F3','C3',*RANK_ARMS] else 'F0'),
        control_version=p['version'],ranking=p['ranking'] if arm in RANK_ARMS else None,
        top_n=int(arm[1:]) if arm in RANK_ARMS else None,
        calibration=read_json(root/'calibration.json') if arm=='E0' else None)
    bundle = freeze_usd_bundle(root/'bundles'/name,root,recipe,decisions,quotes,sessions,cost)
    path = root/'python'/(name+'.json')
    if path.exists():
        raise FileExistsError('Research output exists; preserve the original attempt')
    write_json(path,run_usd_reference(bundle))
    write_json(path.with_suffix('.receipt.json'),dict(status='succeeded',sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')))
    return name


def summarize(root):
    import numpy as np
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    results={}
    for job in jobs():
        name=job_name(job);path=root/'python'/(name+'.json')
        receipt=read_json(path.with_suffix('.receipt.json'))
        if receipt['sha256']!=sha256(path) or receipt['manifest_sha256']!=sha256(root/'bundles'/name/'manifest.json'):
            raise ValueError('Changed replay output')
        economic=read_json(path);quotes=read_json(root/'bundles'/name/'quotes.json')
        stats=statistics(economic,quotes)
        stats['calmar']=stats['cagr']/abs(stats['max_drawdown']) if stats['max_drawdown'] else None
        nav=np.array([1e6]+[float(r['nav']) for r in economic['nav']])
        underwater=nav<np.maximum.accumulate(nav);longest=current=0
        for below in underwater:
            current=current+1 if below else 0;longest=max(longest,current)
        returns=np.array(stats['daily_returns']);threshold=np.quantile(returns,.05)
        stats.update(max_underwater_sessions=longest,expected_shortfall_daily_95=float(returns[returns<=threshold].mean()),
            trades=len(economic['fills']),sessions_95pct_cash=sum(float(r['cash'])/float(r['nav'])>=.95 for r in economic['nav']),
            maximum_target=max(float(t['target_weight']) for r in economic['decisions'].values() for t in r['targets']))
        results[name]=stats
    write_json(root/'statistics.json',results)
    write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    return results
