"""Pinned, causal, bounded F3 pool/momentum study, separate from monitored strategies."""
from datetime import UTC, date, datetime
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, verify_usd_bundle, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.candidate_pool import POLICIES

ARMS=[f'{m}_{n}' for m in POLICIES for n in (12,14)]+['F3','RP12','RP14','URTH']
COMPARISONS=[('M0_14','M0_12')]+[(f'{m}_14','M0_14') for m in ('M1','M2','M3')]+[(f'{m}_14',f'{m}_12') for m in ('M1','M2','M3')]+[(f'{m}_12','M0_12') for m in ('M1','M2','M3')]+[('M0_12','F3')]
_DATA=None


def prepare(root):
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    from systematic_trading.research.candidate_pool import audited_bar
    from systematic_trading.research.strategy_catalog import defensive_cash_definition
    from systematic_trading.config import AppSettings
    from systematic_trading.storage.factory import create_trading_store
    from systematic_trading.portfolio.strategy_allocation import control_state
    if root.exists():raise FileExistsError('Preserve registered study')
    parent=Path('var/tracked_strategies/1ef8c43dd057b1a0ed3c38dd2b331528da54be174e9985860cbd5a704cf4617d/usd').resolve()
    previous=Path('var/research/energy-materials-universe-20261009-v1').resolve()
    checked_files(parent,'input_manifest.json');checked_files(previous,'input_manifest.json')
    worker=read_json(parent/'worker.json');old=read_json(previous/'data_receipt.json')
    bundle=parent/'bundles/research_fallback_f3_v1';spec=verify_usd_bundle(bundle)['spec']
    if spec.recipe!=defensive_cash_definition().to_dict():raise ValueError('F3 definition changed')
    settings=AppSettings(transactional_store_backend='postgres',market_data_store_backend='clickhouse')
    state=control_state(create_trading_store(settings))
    if state['sota_key']!='research_fallback_f3_v1':raise ValueError('SOTA changed')
    p=dict(version='candidate-pool-momentum-v1',registered_at=datetime.now(UTC).isoformat(),
        question='Do XLE/XLB improve F3 when competing for six slots; do three predeclared momentum changes help?',
        start='2016-01-04',evaluation_start='2021-01-04',end='2026-10-08',warmup_start='2012-01-05',
        arms=ARMS,policies=POLICIES,comparisons=COMPARISONS,comparison_family_size=len(COMPARISONS),
        primary_window='2021 onward chronological evaluation; history already inspected, not untouched holdout',
        calibration_window='2016–2020 descriptive only; no tuning after registration',
        initial_cash_usd='1000000',currency='USD',cash_interest='zero',risk_free='zero',
        additions=['XLE','XLB'],excluded={'XOP':'Unresolved issuer/provider listing boundary'},
        selection=dict(top_n=6,min_selected=4,trend_weight='.75',volume_weight='.25',horizon_weights=['.20','.35','.45'],
            positive_gate=True,fallback='Qualifying IEF/TLT/GLD at incoming weights; residual cash protected',mandatory_assets=[]),
        recipe=defensive_cash_definition().to_dict(),
        models='Shared F3 XGBoost architecture, monthly one-year causal refits per pool; shared USD U1 causal per-pool refits; one model schedule per pool reused by all momentum variants',
        data_basis='Audited adjusted OHLC returns; raw volume for activity features; audited raw close × raw volume for dollar turnover; adjusted price direction',
        cost_bps=[5,10,20],delayed_sessions=1,bootstrap_blocks=[3,6,12],bootstrap_replications=10000,seed=2026100903,
        retention_screen=dict(min_sharpe_gain=.05,min_calmar_gain=.05,max_cagr_sacrifice=.005,max_drawdown_worsening=.01),
        promotion_eligible=False,
        limitations=[
            'All periods are retrospective and previously inspected. The 2021 boundary is not an untouched holdout; no automatic promotion.',
            'Current ETF choice and identity do not establish historical point-in-time membership. Audited reconstructed vintages are not historical dissemination evidence.',
            'New arms use raw traded activity. Frozen legacy F3 uses its older adjusted-price/source-volume proxy. M0_12 versus F3 is a separate data-basis/refit bridge, not a pool effect.',
            'Selection ranking and model relative-return labels depend on the pool; adding candidates can change existing asset weights even when the new names are not held.',
            'F3 has a 45% cap on incoming inverse-volatility weights, but no final 45% cap after selection and overlays. The exact existing rule is preserved; final and held weights can exceed 45%.',
            'USD accounting, zero interest on cash, zero-reference Sharpe, 5/10/20bp per traded dollar. Spreads, taxes, market impact and certified USD/CNH conversion are not modeled.',
            'Raw prices/volume are audited reconstructions, not tape-certified observations. Adjusted units in replay are synthetic; missing inputs are rejected rather than filled.',
            'XOP excluded before testing. Holdings overlap, issuance and prospective issuer/EIA/CFTC data are unavailable for historical signals; broker identity is not trading permission.',
            'Eleven predeclared paired comparisons include the legacy bridge; Holm correction applied jointly. Ratio confidence intervals are marginal, not multiplicity-adjusted.',
        ])
    reader=GovernedInputs(Path('var/governance/research-2026-10-08-b1185e4ae091'),old['batch'])
    symbols=list(worker['bars']);all_symbols=sorted([*symbols,'XLE','XLB']);bars={};raw={}
    for s in all_symbols:
        rows=reader.rows(s,p['warmup_start'],p['end'])
        if s in worker['bars'] and [etf_bar(r) for r in rows]!=worker['bars'][s]:raise ValueError('Original adjusted history changed: '+s)
        bars[s]=[audited_bar(r) for r in rows];raw[s]=[audited_bar(r,raw=True) for r in rows]
    days=[r['trade_date'] for r in bars['SPY']]
    if any([r['trade_date'] for r in v]!=days for v in bars.values()):raise ValueError('Incomplete calendar')
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(Path(__file__).parents[3]/'scripts/run_candidate_pool.py',root/'runner.py')
    write_json(root/'protocol.json',p);write_json(root/'bars.json',bars);write_json(root/'raw.json',raw)
    write_json(root/'legacy_worker.json',worker);write_json(root/'control.json',read_json(bundle/'decisions.json'))
    write_json(root/'baseline_economic.json',read_json(parent/'python/research_fallback_f3_v1.json'))
    write_json(root/'urth.json',read_json(previous/'urth.json'))
    write_json(root/'data_receipt.json',dict(batch=reader.batch if hasattr(reader,'batch') else old['batch'],governed_files=reader.used,
        parent=str(parent),parent_input_sha256=sha256(parent/'input_manifest.json'),original_symbols=symbols,
        admission_evidence=old,control_state=state,image=old['image']))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/'protocol.json'),arms=ARMS)


def initialize(root, models=True):
    global _DATA
    from systematic_trading.domain.market import PriceBar
    root=Path(root);checked_files(root,'input_manifest.json')
    bars=read_json(root/'bars.json');raw=read_json(root/'raw.json')
    _DATA=dict(root=root,bars=bars,typed={s:[PriceBar.model_validate(r) for r in v] for s,v in bars.items()},
        raw={s:[PriceBar.model_validate(r) for r in v] for s,v in raw.items()},days=[r['trade_date'] for r in bars['SPY']],
        protocol=read_json(root/'protocol.json'),receipt=read_json(root/'data_receipt.json'))
    if models:
        checked_files(root,'model_manifest.json')
        _DATA['models']={n:read_json(root/'models'/f'{n}.json') for n in (12,14)}


def training_inputs(root, n):
    from systematic_trading.research.rolling_tracking import monthly_training_records,monthly_fit_dates
    from systematic_trading.research.usd_tracking import prepare_usd_schedule
    bars=read_json(root/'bars.json');symbols=read_json(root/'data_receipt.json')['original_symbols'] if n==12 else sorted(bars)
    bars={s:bars[s] for s in symbols};worker=read_json(root/'legacy_worker.json')
    records=monthly_training_records(bars,symbols)
    write_json(root/'training'/f'{n}.json',records)
    write_json(root/'training'/f'usd{n}.json',prepare_usd_schedule(bars,worker['usd']['snapshots']))
    return [(n,d) for d in monthly_fit_dates(bars,read_json(root/'protocol.json')['start'])]


def fit(job):
    from systematic_trading.research.rolling_models import fit_record
    from systematic_trading.signals.library import signal_feature_ids
    root,n,cutoff=job;root=Path(root)
    value=fit_record(read_json(root/'training'/f'{n}.json'),cutoff,1,signal_feature_ids(),'xgboost',seed=20260927)
    write_json(root/'fits'/str(n)/(cutoff+'.json'),value)
    return n,cutoff


def freeze_models(root):
    import importlib.metadata
    for n in (12,14):
        write_json(root/'models'/f'{n}.json',dict(rolling={p.stem:read_json(p) for p in sorted((root/'fits'/str(n)).glob('*.json'))},
            usd=read_json(root/'training'/f'usd{n}.json')))
    write_json(root/'model_versions.json',{k:importlib.metadata.version(k) for k in ('numpy','scikit-learn','xgboost')})
    write_json(root/'model_manifest.json',{f.relative_to(root).as_posix():sha256(f) for folder in ('training','fits','models') for f in (root/folder).rglob('*.json')} | {'model_versions.json':sha256(root/'model_versions.json')})


def decision(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.momentum_replay import usd_instruments
    from systematic_trading.research.strategy_catalog import defensive_cash_definition,instantiate_overlays
    from systematic_trading.research.rolling_tracking import select_rolling_model,RollingModelOverlay
    from systematic_trading.research.usd_tracking import UsdRidgeOverlay
    from systematic_trading.research.flow_concentration import ActivityConcentrationOverlay
    from systematic_trading.research.candidate_pool import CandidatePool,AuditedActivity
    d=_DATA;i=d['days'].index(day);asof=date.fromisoformat(day);out={};diagnostics={}
    for n in (12,14):
        symbols=d['receipt']['original_symbols'] if n==12 else sorted(d['bars'])
        histories={s:d['typed'][s][max(0,i-500):i] for s in symbols}
        raw={s:d['raw'][s][max(0,i-500):i] for s in symbols}
        model=select_rolling_model(d['models'][n]['rolling'],histories,asof)
        for policy in [*POLICIES,'RP']:
            overlays=instantiate_overlays(defensive_cash_definition()) if policy!='RP' else []
            if overlays:
                selector=CandidatePool(overlays[0],policy);overlays[0]=selector
                for j,o in enumerate(overlays):
                    if isinstance(o,RollingModelOverlay):o.model=model
                    elif isinstance(o,UsdRidgeOverlay):o.schedule=d['models'][n]['usd']
                    elif isinstance(o,ActivityConcentrationOverlay):overlays[j]=AuditedActivity(o.spec,raw)
            targets=_target_schedule(instruments={s:usd_instruments()[s] for s in symbols},bars_by_symbol=histories,
                trade_dates=[asof],rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),cash_reserve_weight=D('.02'),
                sleeve_name='candidate-pool-momentum-v1',target_overlays=overlays)[asof]
            arm=f'{policy}_{n}' if policy!='RP' else f'RP{n}'
            out[arm]=dict(signal_session=day,known_through=d['days'][i-1],targets=[t.model_dump(mode='json') for t in targets])
            if overlays:
                observation=selector.observation
                held=[t.symbol for t in targets if t.target_weight>0]
                if not set(held).issubset(observation['selected']):raise ValueError('Downstream overlay resurrected rejected candidate')
                if len(held)>6:raise ValueError('Top-six contract violated')
                diagnostics[arm]=dict(**observation,final_selected=held,final_weights={t.symbol:str(t.target_weight) for t in targets})
    return day,dict(decisions=out,diagnostics=diagnostics)


def freeze_decisions(root, records):
    from systematic_trading.domain.portfolio import AllocationTarget
    for arm in ARMS:
        if arm=='F3':value=read_json(root/'control.json')
        elif arm=='URTH':
            first=min(records);value={first:dict(signal_session=first,known_through=records[first]['decisions']['M0_12']['known_through'],targets=[
                AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=D(1),rationale='buy and hold').model_dump(mode='json')])}
        else:value={day:records[day]['decisions'][arm] for day in sorted(records)}
        write_json(root/'decisions'/(arm+'.json'),value)
    write_json(root/'selection.json',{day:records[day]['diagnostics'] for day in sorted(records)})
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in (root/'decisions').glob('*.json')} | {'selection.json':sha256(root/'selection.json')})


def jobs():
    return [(a,c,0,w) for a in ARMS for c in (5,10,20) for w in ('full','evaluation')]+[(a,5,1,w) for a in ARMS if a!='URTH' for w in ('full','evaluation')]


def job_name(job):return f'{job[0]}-cost{job[1]}-delay{job[2]}-{job[3]}'


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    d=_DATA;root=d['root'];arm,cost,delay,window=job
    checked_files(root,'decision_manifest.json');p=d['protocol']
    symbols=d['receipt']['original_symbols'] if arm.endswith('12') or arm=='F3' else sorted(d['bars'])
    bars={s:d['bars'][s] for s in symbols} if arm!='URTH' else {'URTH':read_json(root/'urth.json')}
    start=p['start'] if window=='full' else p['evaluation_start']
    quotes,sessions=quotes_for_data(bars,d['days'],start)
    decisions={s:v for s,v in read_json(root/'decisions'/(arm+'.json')).items() if s>=start}
    if arm=='URTH' and window=='evaluation':
        original=read_json(root/'decisions/URTH.json');record=dict(next(iter(original.values())))
        record.update(signal_session=sessions[0],known_through=d['days'][d['days'].index(sessions[0])-1]);decisions={sessions[0]:record}
    if delay:decisions={sessions[sessions.index(s)+delay]:v for s,v in decisions.items() if sessions.index(s)+delay<len(sessions)}
    name=job_name(job);bundle=root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(id=arm,window=window,delay_sessions=delay,policy=p['policies'].get(arm.split('_')[0])),decisions,quotes,sessions,cost)
    output=root/'python'/(name+'.json')
    if output.exists():raise FileExistsError('Preserve completed replay '+name)
    write_json(output,run_usd_reference(bundle));write_json(output.with_suffix('.receipt.json'),dict(sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json')))
    return name
