"""Pinned application calculations for a finite fallback study, never an executor."""
from datetime import date, timedelta
from decimal import Decimal as D
import json
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256, write_json, verify_bundle
from systematic_trading.research.fallback_protocol import BASELINE, POLICIES, definition, protocol
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference

_DATA = None


def prepare(root):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.live.trading_calendar import is_us_trading_day
    if root.exists():
        raise FileExistsError('Research freeze already exists')
    settings=AppSettings(); analytics=AnalyticsStore.from_settings(settings)
    published=analytics.latest('governance/catalog'); tracked=analytics.latest('tracked-strategies/calculations')
    provenance=json.loads(tracked['provenance'])
    if provenance['inputs']['batch']!=published['version']:
        raise ValueError('Published baseline and prices must share a batch')
    parent=settings.data_dir/'tracked_strategies'/tracked['version']/'datasets'/BASELINE
    verify_bundle(parent)
    spec=read_json(parent/'spec.json')
    if spec['strategy_definition']!=definition('F0').to_dict():
        raise ValueError('Published baseline definition differs')
    p=protocol(spec['end_date'])
    source=GovernedInputs(Path(json.loads(published['provenance'])['root']),published['version'])
    symbols=sorted(instruments_for_definition(definition('F0')))
    raw={s:source.rows(s,p['warmup_start'],p['end']) for s in [*symbols,'URTH']}
    audits={s:source.audit(s) for s in raw}
    bars={s:[etf_bar(r) for r in raw[s]] for s in symbols}
    first,last=date.fromisoformat(p['warmup_start']),date.fromisoformat(p['end'])
    days=[str(first+timedelta(days=i)) for i in range((last-first).days+1) if is_us_trading_day(first+timedelta(days=i))]
    if any([r['trade_date'] for r in rows]!=days for rows in bars.values()):
        raise ValueError('Incomplete aligned audited ETF histories')
    if bars!=read_json(parent/'bars.json'):
        raise ValueError('Baseline bars differ from published audited inputs')
    benchmark=[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close'])) for r in raw['URTH']]
    if [r['trade_date'] for r in benchmark if r['trade_date']>='2015-12-31']!=[d for d in days if d>='2015-12-31']:
        raise ValueError('Incomplete benchmark')
    # Verify the USD source publication and its archive independently of the model bundle.
    usd=provenance['inputs']['usd']
    usd_source=GovernedInputs(Path(usd['root']),usd['batch'])
    for name in usd['files']:
        usd_source.checked(name)
    root.mkdir(parents=True)
    write_json(root/'protocol.json',p)
    shutil.copytree(Path(__file__).parents[1],root/'source'/'systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,value in [('bars.json',bars),('urth.json',benchmark),('baseline_decisions.json',read_json(parent/'decisions.json')),
        ('rolling_models.json',read_json(parent/'base_tree_models.json')),('usd_models.json',read_json(parent/'usd_models.json'))]:
        write_json(root/name,value)
    write_json(root/'data_receipt.json',dict(batch=published['version'],publication=published,tracked_publication=tracked,
        governed_root=str(source.root),governed_files=source.used,usd_source=usd,usd_verified_files=usd_source.used,
        baseline_manifest_sha256=sha256(parent/'manifest.json'),baseline_path=str(parent.resolve()),
        models={n:sha256(parent/n) for n in ['base_tree_models.json','usd_models.json']},
        image=provenance['config']['calculation']['image'],fx='Excluded, not read as research input',
        coverage={s:dict(rows=len(v),first=v[0]['trade_date'],last=v[-1]['trade_date'],
            audit_status=audits[s].get('status'),missing_raw=sum(r.get('raw_close') is None or r.get('raw_volume') is None for r in v)) for s,v in raw.items()}))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in sorted(root.rglob('*')) if f.is_file()})
    return dict(root=str(root.resolve()),batch=published['version'],end=p['end'],recipes=list(POLICIES))


def initialize(root):
    global _DATA
    from systematic_trading.domain.market import PriceBar
    root=Path(root); checked_files(root,'input_manifest.json')
    values={k:read_json(root/(k+'.json')) for k in ['protocol','bars','rolling_models','usd_models']}
    values.update(root=root,typed={s:[PriceBar.model_validate(r) for r in v] for s,v in values['bars'].items()})
    values['days']=[r['trade_date'] for r in values['bars']['SPY']]
    _DATA=values


def calculate_decision(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research import instantiate_overlays, instruments_for_definition
    from systematic_trading.research.rolling_tracking import select_rolling_model
    data=_DATA; i=data['days'].index(day)
    histories={s:rows[max(0,i-500):i] for s,rows in data['typed'].items()}
    output={}
    eligible=sorted(s for s,b in histories.items() if b[-1].close/b[-253].close-1>0)
    for recipe in POLICIES:
        d=definition(recipe); overlays=list(instantiate_overlays(d))
        for o in overlays:
            if o.__class__.__name__=='RollingModelOverlay':
                o.model=select_rolling_model(data['rolling_models'],histories,date.fromisoformat(day))
            if o.__class__.__name__=='UsdRidgeOverlay':
                o.schedule=data['usd_models']
        targets=_target_schedule(instruments=instruments_for_definition(d),bars_by_symbol=histories,
            trade_dates=[date.fromisoformat(day)],rebalance_frequency='daily',lookback_bars=63,
            max_weight=D('.45'),cash_reserve_weight=D('.02'),sleeve_name=d.sleeve_name,target_overlays=overlays)[date.fromisoformat(day)]
        gross=sum(t.target_weight for t in targets)
        if gross>1+D('1e-20') or any(t.target_weight<0 for t in targets):
            raise ValueError('Invalid final allocation')
        output[recipe]=dict(signal_session=day,known_through=data['days'][i-1],
            targets=[t.model_dump(mode='json') for t in targets],diagnostic=dict(eligible=eligible,
            fallback=len(eligible)<4,target_cash=str(1-gross)))
    return day,output


def freeze_decisions(root, rows):
    parent=read_json(root/'baseline_decisions.json')
    decisions={k:{day:rows[day][k] for day in sorted(rows)} for k in POLICIES}
    if parent.keys()!=decisions['F0'].keys():
        raise ValueError('Baseline decision calendars differ')
    largest=D(0)
    for day,record in parent.items():
        a={t['symbol']:D(t['target_weight']) for t in record['targets']}
        b={t['symbol']:D(t['target_weight']) for t in decisions['F0'][day]['targets']}
        if a.keys()!=b.keys():
            raise ValueError('Baseline universe differs')
        largest=max(largest,max(abs(a[s]-b[s]) for s in a))
        if not decisions['F0'][day]['diagnostic']['fallback']:
            for recipe in ['F1','F2','F3']:
                c={t['symbol']:D(t['target_weight']) for t in decisions[recipe][day]['targets']}
                if any(abs(b[s]-c[s])>D('1e-20') for s in b):
                    raise ValueError('Fallback candidate changed a non-fallback decision')
    if largest>D('1e-8'):
        raise ValueError('Baseline target replay mismatch '+str(largest))
    (root/'decisions').mkdir()
    for recipe,value in decisions.items():
        write_json(root/'decisions'/(recipe+'.json'),value)
    write_json(root/'baseline_parity.json',dict(passed=True,maximum_weight_difference=str(largest),decisions=len(parent)))
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in (root/'decisions').glob('*.json')})


def calculate_economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.domain.portfolio import AllocationTarget
    data=_DATA;root=data['root'];p=data['protocol'];recipe,cost,delay=job
    checked_files(root,'decision_manifest.json')
    if recipe=='URTH':
        bars={'URTH':read_json(root/'urth.json')};first=next(d for d in data['days'] if d>=p['start'])
        decisions={first:dict(signal_session=first,known_through=data['days'][data['days'].index(first)-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='fallback-benchmark',target_weight=D(1),rationale='buy and hold').model_dump(mode='json')])}
    else:
        bars=data['bars'];decisions=read_json(root/'decisions'/(recipe+'.json'))
    quotes,sessions=quotes_for_data(bars,data['days'],p['start'])
    if delay:
        decisions={sessions[sessions.index(day)+delay]:row for day,row in decisions.items() if sessions.index(day)+delay<len(sessions)}
    name=f'{recipe}-cost{cost}-delay{delay}'
    bundle=root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(id=recipe,definition=p['recipes'].get(recipe),delay_sessions=delay),decisions,quotes,sessions,cost)
    output=root/'python'/(name+'.json');output.parent.mkdir(exist_ok=True)
    if output.exists():
        raise FileExistsError('Finite replay output already exists: '+name)
    write_json(output,run_usd_reference(bundle))
    write_json(output.with_suffix('.receipt.json'),dict(status='succeeded',sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json')))
    return name


def analyze(root):
    import numpy as np
    from systematic_trading.research.momentum_analysis import statistics, paired_bootstrap
    from systematic_trading.research.strategy_catalog import strategy_model_card, StrategyDefinition
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    p=read_json(root/'protocol.json');results={}
    for output in sorted((root/'python').glob('*.json')):
        if output.name.endswith('.receipt.json'):
            continue
        receipt=read_json(output.with_suffix('.receipt.json'))
        bundle=root/'bundles'/output.stem
        if receipt['sha256']!=sha256(output) or receipt['manifest_sha256']!=sha256(bundle/'manifest.json'):
            raise ValueError('Economic artifact changed')
        economic=read_json(output);stats=statistics(economic,read_json(bundle/'quotes.json'))
        drawdown=stats['max_drawdown'];stats['calmar']=stats['cagr']/abs(drawdown) if drawdown else None
        peak=float(p['initial_cash_usd']);duration=longest=cash_spell=max_cash_spell=0
        for row in economic['nav']:
            nav=float(row['nav']);duration=duration+1 if nav<peak else 0;peak=max(peak,nav);longest=max(longest,duration)
            cash_spell=cash_spell+1 if float(row['cash'])/nav>=.95 else 0;max_cash_spell=max(max_cash_spell,cash_spell)
        stats.update(max_drawdown_duration_sessions=longest,longest_95pct_cash_sessions=max_cash_spell,
            sessions_95pct_cash=sum(float(r['cash'])/float(r['nav'])>=.95 for r in economic['nav']))
        # These fixed calendar splits are retrospective diagnostics, never untouched OOS evidence.
        stats['periods']={}
        for label,a,b in [('2016-2022','2016','2023'),('2023-on','2023','9999')]:
            idx=[i for i,d in enumerate(stats['dates']) if a<=d<b]
            r=np.array(stats['daily_returns'])[idx];vol=r.std(ddof=1)
            nav=np.r_[1.,np.cumprod(1+r)];cagr=float(nav[-1]**(252/len(r))-1);dd=float(np.min(nav/np.maximum.accumulate(nav)-1))
            stats['periods'][label]=dict(cagr=cagr,sharpe=float(r.mean()/vol*np.sqrt(252)) if vol else None,
                max_drawdown=dd,calmar=cagr/abs(dd) if dd else None)
        results[output.stem]=stats
    expected={f'{r}-cost{c}-delay0' for r in [*POLICIES,'URTH'] for c in p['cost_bps']}|{f'{r}-cost5-delay1' for r in POLICIES}
    if set(results)!=expected:
        raise ValueError('Incomplete finite comparison')
    monthly={r:results[r+'-cost5-delay0']['monthly'] for r in POLICIES}
    months=sorted(monthly['F0'])
    matrix=np.array([[monthly[r][m]-monthly['F0'][m] for r in ['F1','F2','F3']] for m in months])
    inference={str(b):paired_bootstrap(matrix,block=b,replications=p['bootstrap_replications'],seed=p['seed']) for b in p['bootstrap_blocks']}
    decisions=read_json(root/'decisions'/'F0.json');days=sorted(decisions);episodes=[]
    for i,day in enumerate(days):
        if not decisions[day]['diagnostic']['fallback']:
            continue
        if not episodes or episodes[-1]['next_decision']!=day:
            episodes.append(dict(start=day,decisions=[],eligible_counts=[],next_decision=None))
        episode=episodes[-1];episode['decisions'].append(day)
        episode['eligible_counts'].append(len(decisions[day]['diagnostic']['eligible']))
        episode['next_decision']=days[i+1] if i+1<len(days) else None
    for ep in episodes:
        ep['returns']={r:float(np.prod([1+v for m,v in monthly[r].items() if ep['start'][:7]<=m<(ep['next_decision'] or '9999')[:7]])-1) for r in POLICIES}
    latest={r:read_json(root/'decisions'/(r+'.json'))[days[-1]] for r in POLICIES}
    report=dict(protocol=p,baseline_parity=read_json(root/'baseline_parity.json'),results=results,inference=inference,
        fallback_decisions=sum(d['diagnostic']['fallback'] for d in decisions.values()),fallback_episodes=episodes,
        latest_targets=latest,model_cards={r:strategy_model_card(StrategyDefinition.from_dict(v)) for r,v in p['recipes'].items()},
        promotion_eligible=False,limitations=p['limitations'],future_paper_required=True)
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(report_sha256=sha256(root/'report.json'),
        input_manifest_sha256=sha256(root/'input_manifest.json'),decision_manifest_sha256=sha256(root/'decision_manifest.json')))
    return {k:{n:v[n] for n in ['cagr','sharpe_zero_cash','calmar','max_drawdown','mean_cash_weight']} for k,v in results.items() if k.endswith('cost5-delay0')}
