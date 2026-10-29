"""Shared application reports for the BroadTrend fractional sleeve contract."""
from datetime import UTC, datetime, date
import json
import numpy as np

from systematic_trading.backtest.reporting import build_backtest_report_data
from systematic_trading.market_data.analytics_store import encode
from . import broadtrend as b
from .trend_sleeve_portfolio import run, metrics


def current_allocation(result, arrays, states, initial):
    from systematic_trading.live.trading_calendar import next_us_trading_day
    last=result['days'][-1]; next_day=next_us_trading_day(date.fromisoformat(last))
    monthly=next_day.month!=date.fromisoformat(last).month
    budget=np.ones(len(states))/len(states) if monthly else result['sleeves'][-1]
    intent=budget*arrays['desired'][-1]
    nav=float(result['nav'][-1]*initial);holdings=[];targets=[]
    last_scheduled=result['adoptions'][-1]['theoretical']
    for j,s in enumerate(result['symbols']):
        weight=float(result['holdings'][-1,j]);qty=weight*nav/arrays['close'][-1,j]
        holdings.append(dict(symbol=s,quantity=qty,value_cnh=weight*nav,weight=weight,
            target_weight=float(intent[j]),scheduled_weight=float(last_scheduled[j])))
        targets.append(dict(symbol=s,target_weight=float(intent[j]),sleeve=b.KEY,
            rationale='Next-open sleeve exposure intent; exact quantities use its available cash and execution price'))
    holdings.append(dict(symbol='Cash',quantity=None,value_cnh=float(result['cash'][-1]*nav),
        weight=float(result['cash'][-1]),target_weight=float(1-intent.sum()),scheduled_weight=float(last_scheduled[-1])))
    rebalance=next_day
    while rebalance.month==date.fromisoformat(last).month:rebalance=next_us_trading_day(rebalance)
    return dict(holdings=holdings,targets=targets,valuation_date=last,target_known_through=last,
        target_session=str(next_day),last_rebalance=result['adoptions'][-1]['date'],next_rebalance=str(rebalance),
        nav_cnh=nav,cash_cnh=float(result['cash'][-1]*nav),gross_exposure_cnh=float((1-result['cash'][-1])*nav),
        country_exposure_cnh={},currency_exposure_cnh={'USD':nav},states=states,
        next_action='monthly capital and daily signals' if monthly else 'daily signals only',
        notes='Targets are prior-close exposure intents, not broker orders. Unchanged sleeves retain shares; buys spend only their cash. Monthly budgets reset to 1/51. All monetary values are USD despite legacy field names.')


def calculate(settings, config, root, inputs, peer_documents=()):
    initial=float(config['calculation']['initial_cash_cnh']);cost=float(config['calculation']['transaction_cost_bps'])
    result,arrays,states=b.replay(inputs,cost_bp=cost)
    days=result['days'];n=len(days);start=len(arrays['open'])-n;symbols=result['symbols']
    closes=arrays['close'][start:]; opens=arrays['open'][start:]
    nav_rows=[dict(trade_date=d,nav_cnh=float(v*initial),cash_cnh=float(v*c*initial),
        gross_exposure_cnh=float(v*(1-c)*initial)) for d,v,c in zip(days,result['nav'],result['cash'])]
    by_day={}
    for f in result['fills']:by_day.setdefault(f['date'],[]).append(f)
    proposals=[]
    for t,d in enumerate(days[1:],1):
        if d not in by_day:continue
        monthly=any(a['date']==d for a in result['adoptions'])
        budget=np.ones(len(symbols))/len(symbols) if monthly else result['sleeves'][t-1]
        intent=budget*arrays['desired'][start+t-1]
        proposals.append(dict(as_of=days[t-1],known_through=days[t-1],intended_trade_date=d,
            targets=[dict(symbol=s,target_weight=float(w)) for s,w in zip(symbols,intent)],
            orders=[dict(symbol=f['symbol'],side=f['side'],quantity=f['units']*initial) for f in by_day[d]]))
    current=current_allocation(result,arrays,states,initial)
    payload=dict(nav_series=nav_rows,proposals=proposals,final_snapshot=dict(nav_cnh=current['nav_cnh'],
        positions=[dict(symbol=r['symbol'],quantity=r['quantity'],market_price=float(closes[-1,j]))
            for j,r in enumerate(current['holdings'][:-1]) if r['quantity']>0]))
    folder=root/'broadtrend';folder.mkdir(parents=True,exist_ok=True)
    (folder/'result.json').write_text(encode(payload),encoding='utf8')
    (folder/'inputs.json').write_text(encode(inputs['provenance']),encoding='utf8')
    active=np.ones_like(closes,bool)
    benchmark=run(np.array(days),symbols,opens,closes,closes,active,active,start=0,source='all',clock='buyhold',cost_bp=cost)
    bench=[dict(trade_date=d,nav_cnh=float(v*initial)) for d,v in zip(days,benchmark['nav'])]
    extra=[]
    for doc in peer_documents:
        if doc['point_key']=='detail/research_fr25_14_v1':
            peer=json.loads(doc['payload']);rows={r['trade_date']:r for r in peer['nav_series']}
            if all(d in rows for d in days) and peer.get('accounting_currency')=='USD':
                base=float(rows[days[0]]['nav_cnh'])
                extra.append(dict(id='fr25',name='FR25 · rebased matched USD dates (existing account)',
                    nav_series=[dict(trade_date=d,nav_cnh=float(rows[d]['nav_cnh'])/base*initial) for d in days]))
    prices={s:{d:float(closes[t,j]) for t,d in enumerate(days)} for j,s in enumerate(symbols)}
    report,warnings=build_backtest_report_data(result=payload,result_path=folder/'result.json',
        split_date=b.model_pack()['prospective_start'],benchmark_nav_series=bench,
        benchmark_name='Same 51 ETFs · equal initial capital buy-and-hold',extra_benchmarks=extra,
        market_prices=prices,market_fx_rates={d:1. for d in days})
    warnings += ['Historical periods were repeatedly inspected; they are development evidence. Prospective monitoring begins 2026-10-30.',
        'Fractional adjusted USD units, 5 bp per side by default, zero cash interest; no tax, FX, bid/ask or intraday liquidity model.',
        'Closing stops execute next open. Neither the stop nor an HMM score guarantees a loss limit or calibrated probability.',
        'Frozen 2022 per-ETF models and inherited policy thresholds; no online parameter learning or automatic refit.',
        'Retrospective supported 51-ETF cohort; overlapping exposures are not 51 independent risks. No historical publication-vintage proof.',
        'Native accounting fixtures validate a whole-share execution-open oracle only; they do not independently validate policy inference or this fractional strategy.',
        'Monitoring uses a dedicated daily-signal/monthly-capital adapter. Broker allocation for this contract remains unavailable.',
        current['notes']]
    if len(set(inputs['provenance']['latest_by_symbol'].values()))>1:
        warnings.append('Full-pool calculation ends at the last common complete session; later observations of individual ETFs are not substituted.')
    generation=config.get('monitoring_generations',{}).get(b.KEY,0)
    monitoring=dict(lifecycle='monitored',method='app_broadtrend_fractional_usd_v1',calculationOwner='application',
        computedAt=datetime.now(UTC).isoformat(),engine='python',priceThrough=days[-1],artifactEndDate=days[-1],
        monitoredThrough=days[-1],revision=root.name,generation=generation,currentSignalAvailable=True,
        prospectiveStart=b.model_pack()['prospective_start'],prospectiveObservations=sum(d>=b.model_pack()['prospective_start'] for d in days[1:]))
    report.update(title=b.NAME,accountingCurrency='USD',database='Published audited continuous histories',
        modelRegime='Frozen per-ETF Kalman filters + symmetric fast HMM; equal monthly sleeve capital and daily signals',
        splitLabel='Prospective monitoring begins',sampleLabels={'in_sample':'Inspected historical development','out_of_sample':'Prospective monitoring'},
        decisionDiagrams=b.diagram(),strategyDefinition=b.definition().to_dict(),monitoring=monitoring,
        currentAllocation=current,warnings=warnings)
    stats=metrics(result)
    detail=dict(strategy_id=b.KEY,name=b.NAME,is_sota=False,lifecycle='monitored',accounting_currency='USD',app_tracking=True,
        current_signal_available=True,monitoring_generation=generation,report_available=True,
        report_url=f'/api/v1/strategies/{b.KEY}/report',artifact_path=str(folder.resolve()),artifact_end_date=days[-1],
        start_date=days[0],end_date=days[-1],observations=len(days)-1,initial_nav_cnh=initial,final_nav_cnh=current['nav_cnh'],
        total_return=stats['cumulative'],annualized_return=stats['cagr'],annualized_volatility=stats['volatility'],
        sharpe=stats['sharpe'],max_drawdown=-stats['max_drawdown'],calmar=stats['calmar'],
        allocation=current['holdings'],holdings=current['holdings'],current_allocation=current,
        monitoring_method=monitoring['method'],monitoring_notes=current['notes'],promotion_eligible=False,execution_enabled=False,
        strategy_definition=b.definition().to_dict(),nav_series=nav_rows,benchmark_series=bench,warnings=warnings,
        input_provenance=inputs['provenance'],lean_receipts={},model_training=dict(model_sha256=b.PACK_SHA256,training_end='2022-12-30'),usd_model=None)
    documents=[dict(point_key=kind+'/'+b.KEY,media_type='application/json',payload=encode(value)) for kind,value in [('detail',detail),('report',report)]]
    observations=[dict(point_key=b.KEY+'/'+r['trade_date'],family='tracked_strategy_nav',entity=b.KEY,
        observed_at=r['trade_date'],available_at=monitoring['computedAt'],payload=encode(r)) for r in nav_rows]
    observations.append(dict(point_key=b.KEY+'/allocation',family='tracked_strategy_allocation',entity=b.KEY,
        observed_at=days[-1],available_at=monitoring['computedAt'],payload=encode(current)))
    (folder/'validation.json').write_text(encode(dict(metrics=stats,independent_ledger=b.independent_ledger(result,closes))),encoding='utf8')
    return documents,observations,inputs['provenance']
