"""Freeze and replay cash reserve / stress / loser-basket research contracts."""
from datetime import UTC,date,datetime
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import read_json,checked_files,freeze_usd_bundle,run_usd_reference,usd_instruments
from systematic_trading.research.cash_stress import RULES,COMPARISONS,signal_rows,StressPolicy

_DATA=None


def prepare(root):
    from systematic_trading.research.governed_inputs import GovernedInputs,etf_bar
    from systematic_trading.research.strategy_catalog import defensive_cash_definition
    if root.exists():raise FileExistsError('Preserve frozen cash study')
    previous=Path('var/research/candidate-pool-momentum-20261009-v1').resolve()
    checked_files(previous,'input_manifest.json');checked_files(previous,'decision_manifest.json')
    receipt=read_json(previous/'data_receipt.json');definition=defensive_cash_definition().to_dict()
    if definition!=read_json(previous/'protocol.json')['recipe']:raise ValueError('Parent definition changed')
    p=dict(version='cash-stress-losers-v1',registered_at=datetime.now(UTC).isoformat(),
        start='2016-01-04',evaluation_start='2021-01-04',end='2026-10-08',warmup_start='2012-01-05',
        initial_cash_usd='1000000',currency='USD',rules=RULES,comparisons=COMPARISONS,
        comparison_family_size=len(COMPARISONS)*2,parking_modes=['ZERO','BIL'],
        question='Do bounded stress purchases repay cash drag; do bottom-ranked ETFs rebound more than winners or SPY?',
        primary='R2 minus R1 in 2021+; joint family includes all declared contrasts under both parking treatments',
        parent=definition,parent_decisions_sha256=sha256(previous/'decisions/F3.json'),
        rules_common=dict(decisions='monthly, previous completed close; next session open',operational_cash_floor='.02',
            stage_a_budget='min(20% of NAV, parent cash above 2%); lock dollar budget at first >=1% available cash in cycle',
            stage_b_budget='10% / 20% NAV separate reserve, parent targets scaled 90% / 80%; lock available dollar budget at cycle funding',
            stress='SPY adjusted close below trailing 252-session peak by 10%, 20%, 30%; once active, fixed entry peak anchors the cycle',
            tranches='One third of locked budget per level; multiple crossed levels may deploy together; clipped portions stay cash; never reuse spent stages',
            confirm='Adjusted SPY close above 63-session SMA and positive 21-session return; remember breached stress levels until exit',
            basket='Market=SPY; losers/winners=bottom/top 3 of original 12 ETFs by 20/35/45% rank blend of 63/126/252-session adjusted returns; no volume term or positive gate',
            permission='User explicitly authorized a separate sleeve that can buy when F3 rejects assets; parent membership remains unchanged',
            holding='Freeze basket on first deployment; hold sleeve quantities, no monthly top-up; trim only for funding/concentration or exit',
            exit='Monthly close at 95% of fixed episode peak or after 12 monthly intervals; expired episodes cannot re-arm before 95% recovery',
            scheduled_control='R1 starts when parent cash above 2% reaches 1% NAV, buys equal tranches over three monthly decisions, exits after 12 intervals or funding crowd-out; no stress-based exit',
            replenishment='Exit proceeds return to the same cash/parking pool; one-cycle budget and no repeated threshold buys. Parent re-entry has funding priority.',
            concentration='No sleeve addition above max(45%, parent ETF weight); inherited parent overweights preserved, never increased. BIL capped at 45%, remainder cash.',
            parking='ZERO residual cash earns zero; BIL allocates residual above 2% to audited adjusted BIL at monthly decisions, capped at 45%. BIL is not broker cash interest.',
            ownership='Fractional attribution quantities partition actual whole-unit aggregate holdings. Shared accounting alone creates assets/cash/fills; sleeve ownership never exceeds actual quantities.',
            delay='One-session execution delay with original signal and target-weight information cutoff; sizing NAV uses signal-close holdings, not later close information'),
        cost_bps=[5,10,20],delayed_sessions=1,bootstrap_blocks=[3,6,12],bootstrap_replications=10000,seed=2026100904,
        risk_control='XRM: fixed URTH+cash/BIL weight=min(.98, 2016–2020 R2/ZERO net daily volatility / URTH adjusted daily volatility); freeze before 2021 evaluation; no pre-2021 result',
        retention_screen=dict(min_cagr_gain=.005,min_sharpe_gain=.05,min_calmar_gain=.05,max_drawdown_worsening=.01,
            protection_min_drawdown_gain=.02,protection_max_cagr_sacrifice=.005),promotion_eligible=False,
        assessment='Effect-size screen is descriptive: return branch requires CAGR +0.5pp, Sharpe +0.05, Calmar +0.05 and drawdown worsening <=1pp; protection branch requires drawdown improvement >=2pp and CAGR sacrifice <=0.5pp. Robust return evidence additionally requires positive mean-return CI and Holm p<.05 across the 46 contrasts at every block length, and the return screen under 10/20bp and delayed execution. Protection is assessed separately and is not claimed to have positive-return significance.',
        limitations=[
            'Previously inspected retrospective history, not untouched out-of-sample evidence. 2021+ starts from cash; current constituent choice is not historical point-in-time membership.',
            'Only published audited adjusted histories are used. Revised/reconstructed vintages do not establish original publication availability; no source archives, filling, FX substitution or broker interest assumptions.',
            'Parent F3 targets are frozen legacy evidence with inherited activity/model limitations. New sleeve features use adjusted prices only; parent is reproduced exactly in ZERO R0.',
            'Bottom/top ranks span equities, duration, credit, gold and commodities. A loser-basket result may reflect asset-class exposure, not stock-level reversal. No individual securities are traded.',
            'Monthly decision frequency can miss brief selloffs or enter after the rebound. There is no bottom detector; losses after buying and unfinished episodes remain in results.',
            'Stress sleeves deliberately bypass the parent momentum gate only under the separately authorized finite research specification. No strategy, allocation or broker authority changes.',
            'BIL adjusted returns include fund expenses/distribution adjustments; do not add distributions or broker interest again. 5/10/20bp costs include every traded dollar; taxes and separate spread/impact are not modeled.',
            'Parent re-entry and concentration can trim a sleeve or leave tranches unfilled. Spent stages are not replenished during the same episode; sleeve quantities cannot be increased without a new permitted tranche.',
            'Dollar PnL differences reconcile terminal wealth across disjoint calendar phases; additive daily return differences do not equal compounded CAGR. Virtual sleeve attribution is not a separate broker account.',
            'Excess-BIL Sharpe uses audited BIL returns as a tradable cash proxy, not a certified risk-free or broker-cash rate. ZERO-reference Sharpe is also shown.',
            'XRM is an executable fixed-risk control calibrated only on 2016–2020; it uses URTH and does not replicate the parent asset mix. Its results start in 2021.',
            'Small crisis counts and overlapping purchases limit inference. Joint block-bootstrap family adjustment, leave-episode-out diagnostics and open cycles must accompany point estimates.',
        ])
    reader=GovernedInputs(Path('var/governance/research-2026-10-08-b1185e4ae091'),receipt['batch'])
    original=receipt['original_symbols'];bars={s:[etf_bar(r) for r in reader.rows(s,p['warmup_start'],p['end'])] for s in original}
    legacy=read_json(previous/'legacy_worker.json')['bars']
    if bars!=legacy:raise ValueError('Parent prices changed before cash-study freeze')
    extras={s:[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close']))
        for r in reader.rows(s,p['warmup_start'],p['end'])] for s in ('BIL','URTH')}
    days=[r['trade_date'] for r in bars['SPY']];anchor=days[days.index(p['start'])-1]
    for s,rows in extras.items():
        required=[d for d in days if d>=anchor]
        if [r['trade_date'] for r in rows if r['trade_date']>=anchor]!=required:raise ValueError('Cash/benchmark coverage gap: '+s)
        if any(D(r[k])<=0 or not D(r[k]).is_finite() for r in rows for k in ('open','close')):raise ValueError('Unsupported cash/benchmark prices')
    parent=read_json(previous/'decisions/F3.json');signals=signal_rows(bars,parent)
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(Path(__file__).parents[3]/'scripts/run_cash_stress.py',root/'runner.py')
    write_json(root/'protocol.json',p);write_json(root/'bars.json',dict(bars,**extras));write_json(root/'parent.json',parent)
    write_json(root/'signals.json',signals);write_json(root/'baseline_economic.json',read_json(previous/'python/F3-cost5-delay0-full.json'))
    write_json(root/'risk_parity.json',read_json(previous/'decisions/RP12.json'))
    write_json(root/'data_receipt.json',dict(batch=receipt['batch'],governed_files=reader.used,parent_study=str(previous),
        parent_input_sha256=sha256(previous/'input_manifest.json'),original_symbols=original,image=receipt['image']))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/'protocol.json'),arms=list(RULES),paired_family=len(COMPARISONS)*2)


def initialize(root):
    global _DATA
    root=Path(root);checked_files(root,'input_manifest.json')
    bars=read_json(root/'bars.json')
    _DATA=dict(root=root,bars=bars,days=[r['trade_date'] for r in bars['SPY']],p=read_json(root/'protocol.json'),
        parent=read_json(root/'parent.json'),signals=read_json(root/'signals.json'))


def job_name(job):return f'{job[0]}-{job[1]}-cost{job[2]}-delay{job[3]}-{job[4]}'


def jobs():
    return [(a,park,c,delay,w) for a in RULES for park in ('ZERO','BIL') for c,delay in ((5,0),(10,0),(20,0),(5,1)) for w in ('full','evaluation')]


def simulate(job):
    from systematic_trading.backtest.engine import DailyBacktestEngine
    from systematic_trading.backtest.accounting import quantize_money
    from systematic_trading.portfolio.proposals import RebalanceProposalBuilder
    from systematic_trading.domain.enums import Currency
    from systematic_trading.domain.portfolio import AllocationTarget,CashBalance
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data=_DATA;root=data['root'];p=data['p'];arm,parking,cost,delay,window=job
    start=p['start'] if window=='full' else p['evaluation_start']
    quotes,sessions=quotes_for_data(data['bars'],data['days'],start)
    signal_days=[d for d in data['parent'] if d>=start]
    mapping={sessions[sessions.index(d)+delay]:d for d in signal_days if sessions.index(d)+delay<len(sessions)}
    risk_weight=read_json(root/'risk_control.json')['weight'] if arm=='XRM' else None
    policy=StressPolicy(arm,parking,data['signals'],data['parent'],quotes,risk_weight)
    decisions={};fills=[];cost_rate=D(cost)/10000
    class Builder(RebalanceProposalBuilder):
        def build(self,**kw):
            actual=str(kw['intended_trade_date']);signal=mapping[actual]
            positions={r.symbol:r.quantity for r in kw['positions']};cash=sum(r.amount for r in kw['cash'])
            weights=policy.plan(signal,actual,positions,cash)
            targets=[AllocationTarget(symbol=s,sleeve=arm,target_weight=w,rationale='Frozen cash/stress policy '+arm) for s,w in sorted(weights.items())]
            decisions[actual]=dict(signal_session=signal,known_through=data['signals'][signal]['known_through'],targets=[r.model_dump(mode='json') for r in targets])
            return super().build(**dict(kw,targets=targets))
    class Engine(DailyBacktestEngine):
        def _apply_orders(self,**kw):
            before={s:v.quantity for s,v in kw['positions'].items()};super()._apply_orders(**kw)
            after={s:v.quantity for s,v in kw['positions'].items()};fees={};day=policy.pending['trade_day']
            for s in sorted(set(before)|set(after)):
                quantity=after.get(s,0)-before.get(s,0)
                if quantity:
                    price=kw['execution_prices'][s];fee=quantize_money(quantize_money(abs(quantity)*price)*cost_rate);fees[s]=fee
                    fills.append(dict(date=day,symbol=s,quantity=quantity,price=str(price),fee=str(fee)))
            policy.filled(day,before,after,kw['execution_prices'],fees)
    days=[date.fromisoformat(d) for d in sessions]
    result=Engine(proposal_builder=Builder()).run(trade_dates=days,instruments={s:usd_instruments()[s] for s in quotes},
        initial_cash=[CashBalance(currency=Currency.USD,amount=D(p['initial_cash_usd']))],
        daily_prices={d:{s:D(q[str(d)]['close']) for s,q in quotes.items()} for d in days},
        daily_rebalance_prices={d:{s:D(q[str(d)]['reference']) for s,q in quotes.items()} for d in days},
        daily_execution_prices={d:{s:D(q[str(d)]['open']) for s,q in quotes.items()} for d in days},
        daily_fx_to_cnh={d:{Currency.USD:D(1)} for d in days},
        target_schedule={date.fromisoformat(d):[] for d in mapping},transaction_cost_bps=D(cost))
    economic=dict(schema_version=1,engine='python',accounting_currency='USD',complete=True,decisions=decisions,fills=fills,
        nav=[dict(date=str(r.trade_date),nav=str(r.nav_cnh),cash=str(r.cash_cnh)) for r in result.nav_series],
        final_positions={p.symbol:p.quantity for p in result.final_snapshot.positions})
    name=job_name(job);bundle=root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(arm=arm,parking=parking,delay_sessions=delay,window=window),decisions,quotes,sessions,cost)
    reference=run_usd_reference(bundle)
    for key in ('nav','fills','final_positions'):
        if economic[key]!=reference[key]:raise ValueError('Dynamic policy / frozen replay mismatch: '+name+' '+key)
    if job==('R0','ZERO',5,0,'full'):
        old=read_json(root/'baseline_economic.json')
        for key in ('nav','fills','final_positions'):
            if economic[key]!=old[key]:raise ValueError('Exact F3 parent changed: '+key)
    out=root/'python'/(name+'.json')
    if out.exists():raise FileExistsError('Preserve completed cash replay')
    write_json(out,economic);write_json(root/'events'/(name+'.json'),policy.events)
    write_json(out.with_suffix('.receipt.json'),dict(sha256=sha256(out),manifest_sha256=sha256(bundle/'manifest.json'),
        events_sha256=sha256(root/'events'/(name+'.json')),dynamic_frozen_parity=True))
    return name


def calibrate_risk_control(root):
    import numpy as np
    e=read_json(root/'python'/('R2-ZERO-cost5-delay0-full.json'));bars=read_json(root/'bars.json')['URTH']
    prices={r['trade_date']:float(r['close']) for r in bars};days=sorted(prices);previous=1e6;a=[];b=[]
    for r in e['nav']:
        nav=float(r['nav']);day=r['date']
        if day<'2021-01-01':a.append(nav/previous-1);b.append(prices[day]/prices[days[days.index(day)-1]]-1)
        previous=nav
    ratio=float(np.std(a,ddof=1)/np.std(b,ddof=1))
    write_json(root/'risk_control.json',dict(weight=min(.98,ratio),unclipped_ratio=ratio,training_end='2020-12-31',
        training_sessions=len(a),policy='Fixed URTH weight; monthly rebalance; evaluation only',source_sha256=sha256(root/'python/R2-ZERO-cost5-delay0-full.json')))
