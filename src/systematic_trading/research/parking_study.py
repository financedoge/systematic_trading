"""Predeclared recorder-first F4 comparison against frozen published controls."""
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import write_json, sha256
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.parking_fallback import SPEC, park

ARMS = ['F0','F1','F3','F4','RP','URTH','BIL']
COMPARISONS = [('F4','F1'),('F4','F3'),('F4','F0')]
LABELS = dict(F0='Current SOTA · original fallback',F1='Qualifying ETFs + cash',F3='Qualifying defensive ETFs + cash',
              F4='Qualifying ETFs + capped BIL + cash',RP='Original 12 ETFs · risk parity',URTH='Global equities',BIL='Treasury bills · buy and hold')
_DATA = None


def prepare(root, parent):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    from systematic_trading.portfolio.strategy_allocation import control_state
    if root.exists():
        raise FileExistsError('Research freeze already exists')
    checked_files(parent,'input_manifest.json');checked_files(parent,'decision_manifest.json')
    old = read_json(parent/'protocol.json')
    settings=AppSettings();analytics=AnalyticsStore.from_settings(settings)
    # Match the established baseline key without changing promotion state.
    from systematic_trading.storage.factory import create_trading_store
    state=control_state(create_trading_store(settings))
    if state['sota_key'] != old['baseline']:
        raise ValueError('Current SOTA differs from the frozen parent')
    published=analytics.latest('governance/catalog')
    reader=GovernedInputs(Path(json.loads(published['provenance'])['root']),published['version'])
    original=read_json(parent/'bars.json');symbols=sorted(original)
    bars={s:[etf_bar(r) for r in reader.rows(s,old['warmup_start'],old['end'])] for s in [*symbols,'BIL']}
    if any(bars[s]!=original[s] for s in symbols):
        raise ValueError('Control prices changed; a new matched baseline replay is required')
    if [r['trade_date'] for r in bars['BIL']] != [r['trade_date'] for r in bars['SPY']]:
        raise ValueError('BIL needs a complete matched calendar; no fill or index splice')
    audit=reader.audit('BIL')
    if audit['status']!='audited_with_limitations' or not audit.get('research_recorder'):
        raise ValueError('Recorder-first BIL admission required')
    # URTH keeps precisely the same verified publication and conversion as the parent.
    urth=[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close']))
          for r in reader.rows('URTH',old['warmup_start'],old['end'])]
    if urth!=read_json(parent/'urth.json'):
        raise ValueError('Benchmark prices differ')
    p=dict(version='bill-parking-v1',baseline=old['baseline'],warmup_start=old['warmup_start'],start=old['start'],end=old['end'],
        initial_cash_usd='1000000',recipes={a:LABELS[a] for a in ARMS},parking=SPEC,cost_bps=[5,10,20],delay_sessions=1,
        comparisons=COMPARISONS,bootstrap_blocks=[3,6,12],bootstrap_replications=20000,seed=2026100703,
        hypothesis='After realistic turnover costs, capped BIL parking improves F1 cash economics without materially increasing drawdown.',
        failure='Reject advancement if primary net CAGR does not exceed F1 at 20bp or drawdown worsens by more than 0.5 percentage points.',
        comparison_budget='Seven primary arms, three declared paired contrasts, three cost assumptions, one-session delay for F0/F1/F3/F4. No cap/fund/trigger tuning.',
        promotion_eligible=False,limitations=[*old['limitations'],
            'BIL was chosen for mandate and history, not a performance search. Present fund identity is verified; full historical mandate/entitlement changes are not certified.',
            'BIL history is a single-provider reconstruction audited against its own action ledger, not independent historical price certification.',
            'BIL is an ETF with price, spread, settlement and liquidity risk; uninvested cash and broker interest are different.',
            'This is the previously inspected 2016–2026 sample with only three weak-breadth episodes. No untouched out-of-sample claim.',
            'The 45% cap applies to the BIL target at monthly rebalances; later price drift and inherited non-BIL concentration remain.',
            'Calendar-month block inference includes partial October 2026; ratio intervals are marginal, not familywise. Calmar bootstrap uses 252-session CAGR.',
        ])
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    write_json(root/'protocol.json',p);write_json(root/'bars.json',bars);write_json(root/'urth.json',urth)
    for arm in ['F0','F1','F3']:
        write_json(root/'controls'/(arm+'.json'),read_json(parent/'decisions'/(arm+'.json')))
    write_json(root/'data_receipt.json',dict(batch=published['version'],publication=published,governed_files=reader.used,
        parent=str(parent.resolve()),parent_input_sha256=sha256(parent/'input_manifest.json'),
        parent_decisions_sha256=sha256(parent/'decision_manifest.json'),control_state_revision=state['revision'],
        source_bil_audit=audit,image=read_json(parent/'data_receipt.json')['image'],baseline_price_parity=True))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in sorted(root.rglob('*')) if f.is_file()})
    return dict(root=str(root),batch=published['version'],protocol_sha256=sha256(root/'protocol.json'),arms=ARMS)


def initialize(root):
    global _DATA
    from systematic_trading.domain.market import PriceBar
    root=Path(root);checked_files(root,'input_manifest.json')
    bars=read_json(root/'bars.json')
    _DATA=dict(root=root,bars=bars,typed={s:[PriceBar.model_validate(r) for r in v] for s,v in bars.items()},
        days=[r['trade_date'] for r in bars['SPY']],protocol=read_json(root/'protocol.json'),
        controls={a:read_json(root/'controls'/(a+'.json')) for a in ['F0','F1','F3']})


def decision(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.domain.portfolio import AllocationTarget
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.research.fallback_protocol import definition
    data=_DATA;row=data['controls']['F1'][day]
    targets=park([AllocationTarget.model_validate(t) for t in row['targets']],fallback=row['diagnostic']['fallback'])
    f4=dict(row,targets=[t.model_dump(mode='json') for t in targets],diagnostic=dict(row['diagnostic'],
            target_cash=str(1-sum(t.target_weight for t in targets)),bil_weight=str(targets[-1].target_weight)))
    index=data['days'].index(day)
    histories={s:v[max(0,index-500):index] for s,v in data['typed'].items() if s!='BIL'}
    rp=_target_schedule(instruments=instruments_for_definition(definition('F0')),bars_by_symbol=histories,
        trade_dates=[date.fromisoformat(day)],rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),
        cash_reserve_weight=D('.02'),sleeve_name='risk-parity-control',target_overlays=[])[date.fromisoformat(day)]
    return day,dict(F4=f4,RP=dict(signal_session=day,known_through=row['known_through'],targets=[t.model_dump(mode='json') for t in rp]))


def freeze_decisions(root, rows):
    from systematic_trading.domain.portfolio import AllocationTarget
    values={a:read_json(root/'controls'/(a+'.json')) for a in ['F0','F1','F3']}
    values.update({a:{d:rows[d][a] for d in sorted(rows)} for a in ['F4','RP']})
    first=min(rows)
    for arm in ['URTH','BIL']:
        values[arm]={first:dict(signal_session=first,known_through=values['F0'][first]['known_through'],targets=[
            AllocationTarget(symbol=arm,sleeve='benchmark',target_weight=D(1),rationale='buy and hold').model_dump(mode='json')])}
    for arm,v in values.items():write_json(root/'decisions'/(arm+'.json'),v)
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in (root/'decisions').glob('*.json')})


def jobs():
    return [(a,c,0) for a in ARMS for c in [5,10,20]]+[(a,5,1) for a in ['F0','F1','F3','F4']]


def job_name(job):
    arm,cost,delay=job
    return f'{arm}-cost{cost}-delay{delay}'


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data=_DATA;root=data['root'];arm,cost,delay=job
    checked_files(root,'decision_manifest.json')
    bars=({'URTH':read_json(root/'urth.json')} if arm=='URTH' else {'BIL':data['bars']['BIL']} if arm=='BIL'
          else data['bars'] if arm=='F4' else {s:v for s,v in data['bars'].items() if s!='BIL'})
    quotes,sessions=quotes_for_data(bars,data['days'],data['protocol']['start'])
    decisions=read_json(root/'decisions'/(arm+'.json'))
    if delay:decisions={sessions[sessions.index(d)+delay]:r for d,r in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name=job_name(job);bundle=root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(id=arm,parking=SPEC if arm=='F4' else None,delay_sessions=delay),decisions,quotes,sessions,cost)
    output=root/'python'/(name+'.json')
    if output.exists():raise FileExistsError('Replay already exists: '+name)
    write_json(output,run_usd_reference(bundle))
    write_json(output.with_suffix('.receipt.json'),dict(sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json')))
    return name
