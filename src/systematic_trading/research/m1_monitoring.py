"""Application-owned exact M1/14 calculations on a separately versioned pool.

Uses the shared training, target, accounting and report services. It neither
changes SOTA nor imports finite-study decisions as live calculation inputs.
"""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
import json
import os
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.etf_admission import admission_hold
from systematic_trading.research.momentum_replay import read_json,checked_files,freeze_usd_bundle,verify_usd_bundle

KEY='research_m1_14_v1'


def validate_calendars(records,calendar,start,symbols):
    if any([r['trade_date'] for r in records[s]]!=calendar for s in symbols):
        raise ValueError('M1/14 missing audited sessions; no filling')
    first=next(i for i,d in enumerate(calendar) if d>=start)
    if first<1:raise ValueError('Benchmark needs a prior-close anchor')
    required=calendar[first-1:]
    if [r['trade_date'] for r in records['URTH'] if r['trade_date']>=required[0]]!=required:
        raise ValueError('M1/14 benchmark missing audited valuation sessions; no filling')


def load_inputs(settings,analytics,config):
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.candidate_pool import audited_bar
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.research.strategy_catalog import m1_14_definition
    from systematic_trading.live.trading_calendar import is_us_trading_day
    from systematic_trading.daily_quality import completed_session
    publication=analytics.latest('governance/catalog')
    if not publication:raise ValueError('M1/14 requires published audited histories')
    reader=GovernedInputs(Path(json.loads(publication['provenance'])['root']),publication['version'])
    p=config['calculation'];symbols=list(instruments_for_definition(m1_14_definition()))
    records={s:reader.rows(s,p['warmup_start'],str(date.today())) for s in [*symbols,'URTH']}
    if any(not v for v in records.values()):raise ValueError('Incomplete M1/14 history')
    end=min(v[-1]['trade_date'] for v in records.values())
    if not completed_session(date.fromisoformat(end)):raise ValueError('M1/14 endpoint is not complete')
    first,last=date.fromisoformat(p['warmup_start']),date.fromisoformat(end)
    calendar=[str(first+timedelta(days=i)) for i in range((last-first).days+1) if is_us_trading_day(first+timedelta(days=i))]
    records={s:[r for r in v if r['trade_date']<=end] for s,v in records.items()}
    # URTH began after the strategy warmup start. It needs complete anchor and
    # valuation dates, not fictitious pre-inception signal-training bars.
    validate_calendars(records,calendar,p['start'],symbols)
    registry=read_json(settings.research_etf_recorder_config_path)
    for s in ('XLE','XLB'):
        fund=next(f for f in registry['funds'] if f['symbol']==s);audit=reader.audit(s)
        if admission_hold(s, fund.get('admission_hold')) or audit['status']!='audited_with_limitations' or audit.get('research_recorder',{}).get('isin')!=fund['isin']:
            raise ValueError('M1/14 constituent admission incomplete: '+s)
    bars={s:[audited_bar(r) for r in records[s]] for s in symbols}
    raw={s:[audited_bar(r,raw=True) for r in records[s]] for s in symbols}
    return dict(bars=bars,latest_bars=bars,raw_bars=raw,
        urth=[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close'])) for r in records['URTH']],
        provenance=dict(batch=publication['version'],governed_files=reader.used,price_through=end,valuation_through=end,
            universe=symbols,accounting_currency='USD',
            price_basis='Audited adjusted OHLC returns; audited raw volume; raw close × raw volume activity; adjusted direction',
            historical_availability='Reconstructed price vintages; historical publication availability uncertified',
            fx_policy='No FX used in USD backtest',raw_activity_contract='raw_dollar_adjusted_direction_v1'))


def calculate(settings,analytics,config,definitions,sota,root,code_hashes,inputs):
    from systematic_trading.research.rolling_tracking import prepare_model_schedule
    from systematic_trading.research.usd_data import load_usd
    from systematic_trading.research.usd_tracking import prepare_usd_schedule
    from systematic_trading.research.strategy_catalog import risk_parity_definition, m1_14_definition, OverlaySpec
    from systematic_trading.research.fr25_tracking import KEY as FR25_KEY, prepare_schedule
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.compute import available_resources
    from systematic_trading.research.usd_monitored import worker_init,targets_worker,economics_worker,native_attempt,build_reports
    if not definitions or any(d.key not in {KEY,FR25_KEY} for d in definitions):raise ValueError('M1/14 calculator received a different recipe')
    d=definitions[0];p=config['calculation'];parent=root/'usd';root=root/'m1_14'
    checked_files(parent,'input_manifest.json')
    snapshots,usd_provenance=load_usd(analytics)
    inputs=dict(inputs,provenance=dict(inputs['provenance'],usd=usd_provenance))
    usd=prepare_usd_schedule(inputs['bars'],snapshots)
    rolling,model_receipt=prepare_model_schedule(settings,inputs,d,p['start'],code_hashes)
    risk=replace(risk_parity_definition(),universe_key='multi_asset_14')
    comparisons={v.key:v for v in [risk,*definitions]}
    economic_models=None
    if any(v.key==FR25_KEY for v in definitions):
        if 'financial' not in inputs:raise ValueError('FR25 requires pinned economic inputs')
        if root.exists():
            checked_files(root,'input_manifest.json')
            economic_models=read_json(root/'worker.json').get('economic')
            if not economic_models or economic_models['provenance']!=inputs['financial']['provenance']:
                raise ValueError('FR25 economic inputs changed within immutable revision')
        else:
            economic_models=prepare_schedule(inputs['financial'],inputs['bars'])
        base=m1_14_definition()
        capped=replace(base,key='fr25_cap_control',name='M1/14 + 45% final cap',
            overlays=(*base.overlays,OverlaySpec('final_weight_cap',{'cap':'0.45'})))
        comparisons.update({base.key:base,capped.key:capped})
    payload=dict(bars=inputs['bars'],raw_bars=inputs['raw_bars'],rolling=rolling,base_models={},usd=usd,
        economic=economic_models,definitions=[v.to_dict() for v in comparisons.values()])
    if not root.exists():
        root.mkdir(parents=True)
        shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        write_json(root/'protocol.json',dict(initial_cash_usd=p['initial_cash_cnh'],config=config,definition=d.to_dict(),limitations=[
            'USD cash earns zero; no uncertified historical FX used.',
            'Revised audited histories do not establish historical publication availability; retrospective candidate selection.',
            'Audited raw price × raw volume is trading activity, not net fund flows; raw values are reconstructions, not tape certified.']))
        write_json(root/'worker.json',payload)
        write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    checked_files(root,'input_manifest.json')
    if read_json(root/'worker.json')!=payload:raise ValueError('M1/14 inputs changed within immutable revision')
    days=[r['trade_date'] for r in inputs['bars']['SPY']]
    quotes,sessions=quotes_for_data(inputs['bars'],days,p['start'])
    workers=os.cpu_count() or 1
    for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[v]='1'
    with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(root.resolve()),)) as pool:
        rows=dict(pool.map(targets_worker,decision_sessions(days,p['start'],'monthly')))
        for definition in comparisons.values():
            decisions={day:rows[day][definition.key] for day in sorted(rows)}
            freeze_usd_bundle(root/'bundles'/definition.key,root,definition.to_dict(),decisions,quotes,sessions,p['transaction_cost_bps'])
        economics=dict(pool.map(economics_worker,comparisons))
    receipts={}
    if p.get('engine','lean')=='lean':
        resource=available_resources(len(economics),'lean')
        with ThreadPoolExecutor(max_workers=resource['workers']) as pool:
            receipts=dict(pool.map(lambda k:native_attempt(root,k,p['image'],str(resource['cpus_per_run'])),economics))
    else:receipts={k:dict(engine='python',status='succeeded',validation='Python only') for k in economics}
    for key in (sota.key,'URTH'):
        bundle=parent/'bundles'/key;spec=verify_usd_bundle(bundle)['spec']
        if spec.end_date!=inputs['provenance']['price_through'] or spec.start_date!=p['start']:
            raise ValueError('M1/14 benchmark window mismatch')
        economics[key]=read_json(parent/'python'/(key+'.json'))
        # Each benchmark comes from this same atomic app calculation and already
        # passed native checks. Copy its verified bundle for shared report readers.
        if not (root/'bundles'/key).exists():shutil.copytree(bundle,root/'bundles'/key)
        verify_usd_bundle(root/'bundles'/key)
        if p.get('engine','lean')=='lean':receipts[key]=native_attempt(parent,key,p['image'],'2')[1]
        else:receipts[key]=dict(engine='python',status='succeeded')
    inputs['provenance']['parent_benchmark_manifest']={k:sha256(parent/'bundles'/k/'manifest.json') for k in (sota.key,'URTH')}
    comparisons[sota.key]=sota
    return build_reports(settings,analytics,config,definitions,sota,root,inputs,comparisons,
        economics,quotes,rolling,model_receipt,usd,receipts,workers,economic_models)
