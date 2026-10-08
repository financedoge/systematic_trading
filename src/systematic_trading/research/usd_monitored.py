"""App-owned complete USD monitoring, with no uncertified historical FX inputs.

The shared reporting adapter retains legacy *_cnh field names internally;
accountingCurrency declares USD. Only cnh_nav_series is a CNH-valued series,
and it contains exclusively dates with published, verified observed FX.
"""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
import json
import math
import os
from pathlib import Path
import shutil
from statistics import stdev

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import encode
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference, native_parity
from systematic_trading.research.strategy_catalog import StrategyDefinition, risk_parity_definition

USD_KEYS = {'research_fallback_f3_v1', 'research_economic_context_ridge_v1'}
_WORK = None


def load_inputs(settings, analytics, config):
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    from systematic_trading.research import instruments_for_definition, current_sota_definition
    from systematic_trading.live.trading_calendar import is_us_trading_day
    p=config['calculation'];publication=analytics.latest('governance/catalog')
    if not publication:
        raise ValueError('Published audited prices are required')
    source=GovernedInputs(Path(json.loads(publication['provenance'])['root']),publication['version'])
    symbols=list(instruments_for_definition(current_sota_definition()))
    raw={s:source.rows(s,p['warmup_start'],str(date.today())) for s in [*symbols,'URTH']}
    if any(not v for v in raw.values()):
        raise ValueError('Incomplete published ETF history')
    end=min(v[-1]['trade_date'] for v in raw.values())
    from systematic_trading.daily_quality import completed_session
    if not completed_session(date.fromisoformat(end)):
        raise ValueError('USD endpoint is not a completed session')
    first,last=date.fromisoformat(p['warmup_start']),date.fromisoformat(end)
    calendar=[str(first+timedelta(days=i)) for i in range((last-first).days+1)
        if is_us_trading_day(first+timedelta(days=i))]
    bars={s:[etf_bar(r) for r in raw[s] if r['trade_date']<=end] for s in symbols}
    if any([r['trade_date'] for r in b]!=calendar for b in bars.values()):
        raise ValueError('Missing audited sessions; no gap filling is allowed')
    model_path=Path(p['base_models_path'])
    if sha256(model_path)!=p['base_models_sha256']:
        raise ValueError('Pinned base model changed')
    return dict(bars=bars,latest_bars=bars,models=read_json(model_path),
        urth=[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close']))
              for r in raw['URTH'] if r['trade_date']<=end],
        provenance=dict(batch=publication['version'],governed_files=source.used,price_through=end,valuation_through=end,
            accounting_currency='USD',price_basis='Audited dividend/split-adjusted OHLC; inherited source-volume proxy',
            historical_availability='Revised price vintages; historical publication availability uncertified',
            first_missing_fx=None,fx_policy='No FX used in USD backtest'))


def cnh_bridge(analytics, nav):
    """Never manufacture or carry FX; the bridge is separate from USD history."""
    publication=analytics.latest('governance/fx-usd-cnh')
    if not publication:
        return [],dict(status='unavailable',reason='No published observed USD/CNH')
    provenance=json.loads(publication['provenance'])
    for name,digest in provenance['files'].items():
        if sha256(Path(name))!=digest:
            raise ValueError('Published FX source file changed')
    records=analytics.observations('governance/fx-usd-cnh',family='validated_fx_observation',limit=100000)
    rates={r['point_key']:json.loads(r['payload'])['rate'] for r in records}
    if analytics.latest('governance/fx-usd-cnh')['version']!=publication['version']:
        raise ValueError('FX publication changed during conversion')
    rows=[dict(trade_date=r['trade_date'],nav_cnh=str(D(str(r['nav_cnh']))*D(rates[r['trade_date']])))
          for r in nav if r['trade_date'] in rates]
    return rows,dict(source='governance/fx-usd-cnh',version=publication['version'],files=provenance['files'],
        policy='Exact observed FX dates only; missing dates omitted, never filled')


def worker_init(path):
    global _WORK
    from systematic_trading.domain.market import PriceBar
    root=Path(path);checked_files(root,'input_manifest.json')
    data=read_json(root/'worker.json')
    data['root']=root
    data['typed']={s:[PriceBar.model_validate(r) for r in rows] for s,rows in data['bars'].items()}
    data['days']=[r['trade_date'] for r in data['bars']['SPY']]
    _WORK=data


def targets_worker(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research import instantiate_overlays, instruments_for_definition
    from systematic_trading.research.rolling_tracking import select_rolling_model
    from systematic_trading.research.chronological_tree import select_base_tree
    data=_WORK;i=data['days'].index(day);as_of=date.fromisoformat(day)
    history={s:b[max(0,i-500):i] for s,b in data['typed'].items()}
    output={}
    for value in data['definitions']:
        definition=StrategyDefinition.from_dict(value);overlays=instantiate_overlays(definition)
        for spec,o in zip(definition.overlays,overlays,strict=True):
            if spec.kind=='rolling_model':
                o.model=select_rolling_model(data['rolling'],history,as_of)
            elif spec.kind=='decision_tree' and day<'2023-01-01':
                o.model=select_base_tree(data['base_models'],data['days'][i-1])
            elif spec.kind=='usd_ridge':
                o.schedule=data['usd']
            elif spec.kind=='economic_ridge':
                o.schedule=data['economic']
        targets=_target_schedule(instruments=instruments_for_definition(definition),bars_by_symbol=history,
            trade_dates=[as_of],rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),cash_reserve_weight=D('.02'),
            sleeve_name=definition.sleeve_name,target_overlays=overlays)[as_of]
        output[definition.key]=dict(signal_session=day,known_through=data['days'][i-1],targets=[t.model_dump(mode='json') for t in targets])
    return day,output


def economics_worker(name):
    root=_WORK['root'];bundle=root/'bundles'/name
    result=run_usd_reference(bundle)
    path=root/'python'/(name+'.json');path.parent.mkdir(exist_ok=True)
    if path.exists():
        old=read_json(path)
        if {k:v for k,v in old.items() if k!='elapsed_seconds'}!={k:v for k,v in result.items() if k!='elapsed_seconds'}:
            raise ValueError('USD replay changed')
    else:
        write_json(path,result)
    return name,result


def calculate(settings, analytics, config, definitions, sota, root, code_hashes, economic_inputs=None):
    """Full-history replay also catches up every missed session after restore."""
    from systematic_trading.research.rolling_tracking import prepare_model_schedule
    from systematic_trading.research.usd_data import load_usd, refresh_usd
    from systematic_trading.research.usd_tracking import prepare_usd_schedule
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.domain.portfolio import AllocationTarget
    from systematic_trading.research.compute import available_resources
    inputs=load_inputs(settings,analytics,config);p=config['calculation'];root=root/'usd'
    risk=replace(risk_parity_definition(),universe_key='multi_asset')
    comparisons={d.key:d for d in [risk,sota,*definitions]}
    snapshots,_=load_usd(analytics)
    from systematic_trading.live.trading_calendar import next_us_trading_day
    days=[r['trade_date'] for r in inputs['bars']['SPY']]
    needed={d for d in days if d>='2019-02-28' and next_us_trading_day(date.fromisoformat(d)).month!=date.fromisoformat(d).month}
    needed.add(days[-1]);known={r['known_through'] for r in snapshots}
    for day in sorted(needed-known):
        refresh_usd(settings,analytics,day)
    snapshots,inputs['provenance']['usd']=load_usd(analytics)
    usd=prepare_usd_schedule(inputs['bars'],snapshots)
    rolling,model_receipt=prepare_model_schedule(settings,inputs,definitions[0],p['start'],code_hashes)
    economic_models = None
    if any(o.kind=='economic_ridge' for d in comparisons.values() for o in d.overlays):
        from systematic_trading.research.economic_tracking import prepare_schedule
        if economic_inputs is None:
            raise ValueError('Economic monitoring requires pinned published inputs')
        if root.exists():
            checked_files(root,'input_manifest.json')
            economic_models = read_json(root/'worker.json').get('economic')
            if not economic_models or economic_models['provenance'] != economic_inputs['provenance']:
                raise ValueError('Economic inputs changed within immutable revision')
        else:
            economic_models = prepare_schedule(economic_inputs,inputs['bars'])
        inputs['provenance']['economic'] = economic_inputs['provenance']
    if not root.exists():
        root.mkdir(parents=True)
        shutil.copytree(Path(__file__).parents[1],root/'source'/'systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        write_json(root/'protocol.json',dict(initial_cash_usd=p['initial_cash_cnh'],limitations=[
            'USD cash earns zero. No historical CNH exchange rate is used in this backtest.',
            'Revised audited price vintages, not certified historical publication vintages; retrospective selection.',
            'Inherited source-volume activity is not raw traded turnover or ETF flows.'],config=config))
        write_json(root/'worker.json',dict(bars=inputs['bars'],rolling=rolling,base_models=inputs['models'],usd=usd,economic=economic_models,
            definitions=[d.to_dict() for d in comparisons.values()]))
        write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    checked_files(root,'input_manifest.json')
    saved=read_json(root/'worker.json')
    if saved['bars']!=inputs['bars'] or saved['usd']!=usd or saved['rolling']!=rolling or saved.get('economic')!=economic_models:
        raise ValueError('USD inputs changed within an immutable revision')
    quotes,sessions=quotes_for_data(inputs['bars'],days,p['start'])
    benchmark_quotes,_=quotes_for_data({'URTH':inputs['urth']},days,p['start'])
    workers=os.cpu_count() or 1
    for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[variable]='1'
    with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(root.resolve()),)) as pool:
        rows=dict(pool.map(targets_worker,decision_sessions(days,p['start'],'monthly')))
        for key in comparisons:
            decisions={d:rows[d][key] for d in sorted(rows)}
            freeze_usd_bundle(root/'bundles'/key,root,comparisons[key].to_dict(),decisions,quotes,sessions,p['transaction_cost_bps'])
        urth={sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=D(1),rationale='Buy and hold benchmark').model_dump(mode='json')])}
        freeze_usd_bundle(root/'bundles'/'URTH',root,dict(id='URTH'),urth,benchmark_quotes,sessions,p['transaction_cost_bps'])
        economics=dict(pool.map(economics_worker,[*comparisons,'URTH']))
    receipts={}
    if p.get('engine','lean')=='lean':
        resources=available_resources(len(economics),'lean');n=min(resources['workers'],len(economics))
        cpus=str(round(resources['usable_cpus']/n,6))
        def native(key):
            for i in range(1,4):
                output=root/'native'/key/str(i)
                if output.exists() and (not (output/'run.json').exists() or read_json(output/'run.json')['status']!='succeeded'):
                    continue
                return key,dict(native_parity(root/'bundles'/key,output,p['image'],cpus=cpus),artifact_path=str(output.resolve()))
            raise ValueError('Three native attempts failed; inspect retained evidence')
        with ThreadPoolExecutor(max_workers=n) as pool:
            receipts=dict(pool.map(native,economics))
    else:
        receipts={k:dict(engine='python',status='succeeded',validation='Python only; no native parity claim') for k in economics}
    return build_reports(settings,analytics,config,definitions,sota,root,inputs,comparisons,economics,quotes,
                         rolling,model_receipt,usd,receipts,workers,economic_models)


def build_reports(settings,analytics,config,definitions,sota,root,inputs,comparisons,economics,quotes,rolling,model_receipt,usd,receipts,workers,economic_models=None):
    from systematic_trading.research.tracked_runtime import report_result,latest_allocation
    from systematic_trading.backtest.reporting import build_backtest_report_data
    from systematic_trading.backtest.comparison import build_signal_diagnostics
    from systematic_trading.research.strategy_diagram import decision_diagrams
    from systematic_trading.research.rolling_report import rolling_model_report
    from systematic_trading.research.usd_tracking import usd_prediction
    from systematic_trading.domain.market import PriceBar
    from systematic_trading.research.compute import frozen_input
    p=config['calculation'];days=[r['trade_date'] for r in inputs['bars']['SPY']]
    anchor=days[days.index(min(economics[definitions[0].key]['decisions']))-1]
    results={k:report_result(v,read_json(root/'bundles'/k/'quotes.json'),p['initial_cash_cnh'],anchor) for k,v in economics.items()}
    prices={s:{d:float(q['close']) for d,q in rows.items()} for s,rows in quotes.items()}
    for s in prices:
        prices[s][anchor]=float(next(r['close'] for r in inputs['bars'][s] if r['trade_date']==anchor))
    documents=[];observations=[];end=inputs['provenance']['price_through']
    usd_receipt=frozen_input(root/'usd.models.json',usd)
    economic_receipt=frozen_input(root/'economic.models.json',economic_models) if economic_models else None
    for d in definitions:
        key=d.key;economic=economics[key]
        has_economic = any(o.kind=='economic_ridge' for o in d.overlays)
        diagnostics=build_signal_diagnostics(baseline=results[sota.key],candidate=results[key],
            prices_by_symbol={s:{date.fromisoformat(day):v for day,v in rows.items()} for s,rows in prices.items()},
            split_date=date(2023,1,1),signal_name='Economic ridge, final cap and defensive cash' if has_economic else 'Defensive ETF and cash fallback')
        report,warnings=build_backtest_report_data(result=results[key],result_path=root/'python'/(key+'.json'),
            split_date='2023-01-01',benchmark_name='Risk parity · matched USD accounting',benchmark_nav_series=results['risk_parity']['nav_series'],
            extra_benchmarks=[dict(id='urth',name='URTH · USD',nav_series=results['URTH']['nav_series']),
                dict(id='sota',name='Current SOTA · matched USD accounting',nav_series=results[sota.key]['nav_series'])],
            market_prices=prices,market_fx_rates={day:1. for day in [anchor,*next(iter(quotes.values()))]},signal_diagnostics=diagnostics)
        allocation=latest_allocation(d,inputs,economic,quotes,rolling,usd_models=usd,economic_models=economic_models)
        allocation['currency_exposure_cnh']={'USD':allocation['gross_exposure_cnh']}
        generation=config.get('monitoring_generations',{}).get(key,0)
        history,fx=cnh_bridge(analytics,results[key]['nav_series'])
        provenance=dict(inputs['provenance'],fx_bridge=fx,usd_replay_receipts=receipts,workers=workers)
        report.update(title=d.name,accountingCurrency='USD',database='Published audited continuous histories',
            allocationSource='Daily holdings reconstructed from simulated next-session orders and audited USD closes.',
            strategyDefinition=d.to_dict(),currentAllocation=allocation,decisionDiagrams=decision_diagrams(d,accounting_currency='USD'),
            modelRegime='Monthly one-year XGBoost refits; independent USD ridge; defensive cash fallback'+('; final cap and expanding economic ridge' if has_economic else ''),splitLabel='Retrospective comparison boundary',
            sampleLabels={'in_sample':'2016–2022 reconstruction','out_of_sample':'2023 onward reconstruction'},
            monitoring=dict(lifecycle='monitored',generation=generation,method='app_usd_full_replay',artifactEndDate=end,monitoredThrough=end,
                calculationOwner='application',computedAt=datetime.now(UTC).isoformat(),priceThrough=end,
                revision=root.parent.name,prospectiveStart='2026-10-08',prospectiveObservations=sum(day>='2026-10-08' for day in days),engine=p.get('engine','lean')),
            modelTraining=rolling_model_report(d,inputs,rolling,model_receipt,allocation,usd_models=usd,economic_models=economic_models),
            warnings=[*warnings,*read_json(root/'protocol.json')['limitations'],allocation['notes'],
                ('Final ETF targets capped at 45%; held weights may drift between rebalances.' if has_economic else '45% is a base cap, not a final holdings cap. Cash fallbacks preserve selection and the reduced gross budget.'),
                'Only three historical fallback episodes were observed; return differences were statistically inconclusive. Monitoring grants no trading authority.'])
        if has_economic:
            from systematic_trading.research.economic_tracking import prediction as economic_prediction, PARAMETERS
            history_typed={s:[PriceBar.model_validate(r) for r in rows] for s,rows in inputs['bars'].items()}
            current=economic_prediction(economic_models,history_typed,allocation['target_session'])
            report['economicModel']=dict(parameters=PARAMETERS,receipt=economic_receipt,pin=economic_models['pin'],
                latest=current,provenance=economic_models['provenance'],
                historical_ready=sum(r['ready'] for day,r in economic_models['models'].items() if day in economic['decisions']),
                historical_decisions=len(economic['decisions']),
                status='Economic forecasts available' if current['ready'] else 'Economic model abstains; using capped defensive/cash targets',
                explanation='Exact frozen CR model; thirteen features from eleven series; per-ETF ridge alpha 1, expanding original-vintage training, 36 completed monthly labels minimum. Model changes deferred until ETF-universe expansion.')
            report['warnings'] += ['Economic return gains are small and inconclusive after multiple-comparison adjustment; full-history Calmar is weaker than the capped parent.',
                'Historical economic availability assumes end-of-day ALFRED archives. From October 8, 2026 require actual app capture before the decision cutoff; late catch-up inputs abstain.']
            if not current['ready']:
                report['warnings'].append(report['economicModel']['status']+': '+current['reason'])
        histories={s:[PriceBar.model_validate(r) for r in rows] for s,rows in inputs['bars'].items()}
        prediction=usd_prediction(usd,histories,date.fromisoformat(allocation['target_session']))
        report['usdModel']=dict(version=usd['version'],**prediction,receipt=usd_receipt,batch=inputs['provenance']['usd']['batch'],
            explanation='Monthly expanding per-ETF ridge; release-vintage inputs; causal completed labels. Preserves fallback cash budget.')
        summary=report['summary'];nav=[float(r['nav_cnh']) for r in results[key]['nav_series']]
        detail=dict(strategy_id=key,name=d.name,is_sota=key==sota.key,lifecycle='monitored',app_tracking=True,
            monitoring_generation=generation,accounting_currency='USD',report_available=True,report_url=f'/api/v1/strategies/{key}/report',
            artifact_path=str(root),artifact_end_date=end,start_date=p['start'],end_date=end,observations=len(economic['nav']),
            initial_nav_cnh=float(p['initial_cash_cnh']),final_nav_cnh=allocation['nav_cnh'],total_return=summary['totalReturn'],
            annualized_return=summary['annualizedReturn'],annualized_volatility=stdev([b/a-1 for a,b in zip(nav,nav[1:])])*math.sqrt(252),
            sharpe=summary['sharpe'],max_drawdown=summary['maxDrawdown'],calmar=summary['annualizedReturn']/abs(summary['maxDrawdown']) if summary['maxDrawdown'] else None,
            current_allocation=allocation,allocation=allocation['holdings'],holdings=allocation['holdings'],
            nav_series=results[key]['nav_series'],cnh_nav_series=history,benchmark_series=results['risk_parity']['nav_series'],
            warnings=report['warnings'],input_provenance=provenance,strategy_definition=d.to_dict(),
            promotion_eligible=False,execution_enabled=False,economic_model=report.get('economicModel'))
        documents += [dict(point_key='detail/'+key,media_type='application/json',payload=encode(detail)),
                      dict(point_key='report/'+key,media_type='application/json',payload=encode(report))]
        observations += [dict(point_key='allocation/'+key,family='tracked_strategy_allocation',entity=key,
            observed_at=end,available_at=datetime.now(UTC).isoformat(),payload=encode(allocation))]
    return documents,observations,inputs['provenance']
