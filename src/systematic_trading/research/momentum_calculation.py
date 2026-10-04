"""Application-owned batch calculation of the registered research strategies."""
from datetime import date
from decimal import Decimal as D
import os
from pathlib import Path
import time

from systematic_trading.backtest.stored import _target_schedule
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import instruments_for_definition, instantiate_overlays
from systematic_trading.research.strategy_catalog import legacy_sota_definition as current_sota_definition
from systematic_trading.research.strategy_catalog import etf_activity_lag20_definition, rolling_xgboost_1y_definition
from systematic_trading.research.chronological_tree import select_base_tree
from systematic_trading.research.rolling_tracking import select_rolling_model
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.momentum_signals import feature_frame, decision_sessions, Membership, FixedSelection

_DATA = None


def initialize_worker(root):
    global _DATA
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    root=Path(root)
    checked_files(root,'input_manifest.json')
    data={k:read_json(root/(k+'.json')) for k in ('protocol','bars','base_models','rolling_models')}
    data.update(root=root,typed={s:[PriceBar.model_validate(r) for r in rows] for s,rows in data['bars'].items()})
    data['days']=[r['trade_date'] for r in data['bars']['SPY']]
    if (root/'features.json').exists():
        checked_files(root,'feature_manifest.json')
        data['features']=read_json(root/'features.json')
    _DATA=data


def make_feature_chunk(indices):
    data=_DATA
    return {data['days'][i]:feature_frame({s:b[max(0,i-400):i] for s,b in data['typed'].items()}, data['days'][i]) for i in indices}


def build_decisions(job):
    data=_DATA
    p=data['protocol']; days=data['days']
    recipe,cadence=job['recipe'],job['cadence']
    parent=job.get('parent','sota')
    definition={'sota':current_sota_definition,'activity':etf_activity_lag20_definition,'rolling':rolling_xgboost_1y_definition}[parent]()
    scheduled=set(decision_sessions(days,p['start'],cadence))
    state=Membership(recipe) if recipe.startswith('C') else None
    instruments=instruments_for_definition(definition)
    decisions={}
    for i,day in enumerate(days):
        if day<p['start']:
            continue
        frame=data['features'][day]
        diag={}
        if state is not None:
            selected,diag=state.update(frame,day in scheduled)
        elif recipe in ('parent','risk'):
            selected=None
        else:
            q=frame['scores'][recipe]
            ranked=sorted(frame['eligible'],key=lambda s:(-D(q[s]),s))
            selected=set(ranked[:6]) if len(ranked)>=4 else None
            diag=dict(selected=sorted(selected) if selected is not None else None, fallback=selected is None)
        if day not in scheduled:
            continue
        # Finite trailing feature windows, identical to the parent library.
        histories={s:b[max(0,i-500):i] for s,b in data['typed'].items()}
        overlays=list(instantiate_overlays(definition)) if recipe!='risk' else []
        if overlays:
            if recipe!='parent':
                overlays[0]=FixedSelection(selected)
            if parent=='rolling':
                overlays[1].model=select_rolling_model(data['rolling_models'],histories,date.fromisoformat(day))
            elif day<'2023-01-01':
                overlays[1].model=select_base_tree(data['base_models'],days[i-1])
        targets=_target_schedule(instruments=instruments,bars_by_symbol=histories,trade_dates=[date.fromisoformat(day)],
            rebalance_frequency='daily',lookback_bars=63,max_weight=D('.45'),cash_reserve_weight=D('.02'),
            sleeve_name=definition.sleeve_name,target_overlays=overlays)[date.fromisoformat(day)]
        if min(t.target_weight for t in targets)<0 or sum(t.target_weight for t in targets)>D(1)+D('1e-20'):
            raise ValueError('Invalid long-only target constraints')
        decisions[day]=dict(signal_session=day,known_through=days[i-1],targets=[t.model_dump(mode='json') for t in targets],
                            diagnostic=dict(membership=diag,regime=frame['regime'],short_weight=frame['short_weights'].get(recipe),
                                            positive_target_count=sum(t.target_weight>0 for t in targets)))
    return decisions


def baseline_target_parity(decisions):
    baseline=read_json(_DATA['root']/'baseline_decisions.json')
    if decisions.keys()!=baseline.keys():
        raise ValueError('Parent decision dates differ from monitored baseline')
    maximum=D(0)
    for day,row in baseline.items():
        a={t['symbol']:D(t['target_weight']) for t in row['targets']}
        b={t['symbol']:D(t['target_weight']) for t in decisions[day]['targets']}
        if a.keys()!=b.keys():
            raise ValueError('Parent symbols differ')
        maximum=max(maximum,max(abs(a[s]-b[s]) for s in a))
    if maximum>D('1e-8'):
        raise ValueError('Research parent differs from monitored targets: '+str(maximum))
    return dict(passed=True,maximum_weight_difference=str(maximum),decision_count=len(decisions))


def quotes_for_data(bars,days,start):
    sessions=[d for d in days if d>=start]
    result={}
    for s,rows in bars.items():
        by_day={r['trade_date']:r for r in rows}
        result[s]={}
        for day in sessions:
            prior=days[days.index(day)-1]
            result[s][day]={k:str(quantize_money(D(by_day[day if k!='reference' else prior][k if k!='reference' else 'close']))) for k in ('open','close','reference')}
    return result,sessions


def calculate_job(job):
    started=time.perf_counter()
    data=_DATA;root=data['root'];p=data['protocol']
    if job['recipe']=='urth':
        from systematic_trading.domain.portfolio import AllocationTarget
        bars={'URTH':read_json(root/'urth.json')}
        first=next(d for d in data['days'] if d>=p['start'])
        decisions={first:dict(signal_session=first,known_through=data['days'][data['days'].index(first)-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='momentum-research',target_weight=D(1),rationale='buy and hold benchmark').model_dump(mode='json')])}
    else:
        bars=data['bars']
        decisions=build_decisions(job)
    if job['id']=='parent-M':
        write_json(root/'baseline_parity.json',baseline_target_parity(decisions))
    quotes,sessions=quotes_for_data(bars,data['days'],p['start'])
    decision_path=root/'decisions'/(job['id']+'.json')
    decision_path.parent.mkdir(exist_ok=True)
    if decision_path.exists() and read_json(decision_path)!=decisions:
        raise ValueError('Research decisions changed across rerun')
    write_json(decision_path,decisions)
    outputs=[]
    for cost in p['cost_bps']:
        name=job['id']+'-cost'+str(cost)
        bundle=root/'bundles'/name
        freeze_usd_bundle(bundle,root,job,decisions,quotes,sessions,cost)
        output=root/'python'/(name+'.json')
        if output.exists():
            receipt=read_json(output.with_suffix('.receipt.json'))
            if sha256(output)!=receipt['sha256'] or sha256(bundle/'manifest.json')!=receipt['manifest_sha256']:
                raise ValueError('Research replay changed')
        else:
            output.parent.mkdir(exist_ok=True)
            write_json(output,run_usd_reference(bundle))
            write_json(output.with_suffix('.receipt.json'),dict(sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json'),status='succeeded'))
        outputs.append(name)
    return dict(id=job['id'],elapsed_seconds=time.perf_counter()-started,outputs=outputs)
