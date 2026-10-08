"""Finite leading/context experiment on verified published inputs and frozen parents."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
import json
from pathlib import Path
import shutil

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import us_equity_market_close
from systematic_trading.recorders.economics import EconomicInputs, NY
from systematic_trading.research.economic_leading_features import SPEC as FEATURE_SPEC, panel
from systematic_trading.research.economic_response import SPEC, GROUPS, fit_predict, tilt
from systematic_trading.research.construction_controls import FinalWeightCapOverlay, gross
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference

VARIANTS = dict(LT=('leading','tree'), LR=('leading','linear'), MT=('matched','tree'),
                MR=('matched','linear'), CT=('combined','tree'), CR=('combined','linear'))
STRATEGIES = ['F0','F3','P3',*VARIANTS]
ARMS = [*STRATEGIES,'RP','URTH']
LABELS = dict(F0='Current SOTA reference',F3='Qualifying defensive ETFs + cash',P3='Defensive cash + 45% final target cap',
    LT='Leading indicators / ETF trees',LR='Leading indicators / ETF ridge',
    MT='Leading trees / context-matched sample',MR='Leading ridge / context-matched sample',
    CT='Leading + context / ETF trees',CR='Leading + context / ETF ridge',RP='Original ETF risk parity',URTH='Global equities')
COMPARISONS = [('LT','P3'),('LR','P3'),('LT','LR'),('CT','MT'),('CR','MR'),('CT','CR'),('CT','P3'),('CR','P3'),('P3','F3')]
_DATA = None


def jobs():
    return ([(a,c,0,'evaluation') for a in ARMS for c in [5,10,20]]
        +[(a,5,1,'evaluation') for a in STRATEGIES]+[(a,5,0,'full') for a in STRATEGIES])


def job_name(job):
    arm,cost,delay,period = job
    return f'{arm}-{period}-cost{cost}-delay{delay}'


def prepare(root, parent, economic_pin, runner):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.storage import create_trading_store
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    if root.exists():
        raise FileExistsError('Frozen study already exists; preserve evidence')
    checked_files(parent,'input_manifest.json'); checked_files(parent,'decision_manifest.json')
    old = read_json(parent/'protocol.json')
    settings = AppSettings(transactional_store_backend='postgres',market_data_store_backend='clickhouse')
    analytics = AnalyticsStore.from_settings(settings); state = control_state(create_trading_store(settings))
    if state['sota_key'] not in {old['baseline'],'research_fallback_f3_v1'}:
        raise ValueError('Unanticipated SOTA change; review the experiment comparators')
    publication = analytics.latest('governance/catalog')
    reader = GovernedInputs(Path(json.loads(publication['provenance'])['root']),publication['version'])
    original = read_json(parent/'bars.json'); symbols = sorted(set(original)-{'BIL'})
    bars = {s:[etf_bar(r) for r in reader.rows(s,old['warmup_start'],old['end'])] for s in symbols}
    if any(bars[s] != original[s] for s in symbols):
        raise ValueError('Published prices differ from frozen parent')
    urth = [dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close']))
        for r in reader.rows('URTH',old['warmup_start'],old['end'])]
    if urth != read_json(parent/'urth.json'):
        raise ValueError('Published benchmark differs from parent')
    pin = read_json(economic_pin); macro = EconomicInputs(pin['root'],pin['batch'])
    if macro.catalog['completed'] != macro.catalog['expected']:
        raise ValueError('Economic publication is incomplete')
    controls = {a:read_json(parent/'decisions'/(a+'.json')) for a in ['F0','F3','RP']}
    protocol = dict(version='leading-economic-response-v1',registered_at=datetime.now(UTC).isoformat(),
        baseline=old['baseline'],primary_parent='P3',control_revision=state['revision'],
        scheduled_allocation=(state.get('pending') or {}).get('change',{}).get('allocations'),
        calibration_start='2016-01-04',calibration_end='2020-12-31',evaluation_start='2021-01-04',end=old['end'],
        warmup_start=old['warmup_start'],initial_cash_usd='1000000',accounting_currency='USD',cash_interest='zero',
        feature_rule=FEATURE_SPEC,model_rule=SPEC,arms=LABELS,comparisons=COMPARISONS,
        numerical_contract='Round calculated positive weights down at 24 decimal places, then assign the exact parent-budget residual within cap; fails closed below supported precision. Corrects the retained v1 pre-replay 1e-28 allocation-sum failure, without economic/model changes.',
        hypothesis='Do ex-ante per-ETF nonlinear economic responses improve Sharpe and Calmar beyond capped defensive-cash targets and same-input linear models? Does payroll/inflation/output context help after matching training and decision availability?',
        controls='P3 clips F3 final targets at 45% and leaves removed capital in cash. All economic tilts preserve P3 gross, eligibility and membership, with 45% final caps. MT/MR match CT/CR training rows AND decisions exactly, isolating context features from missingness.',
        robustness='5/10/20bp costs, one extra execution session, 2016 onward causal warm-up context, annual and 2021–2022 / 2023 onward descriptive subperiods.',
        cost_bps=[5,10,20],family_size=len(COMPARISONS),bootstrap_blocks=[3,6,12],bootstrap_replications=20000,seed=2026100705,
        screen=dict(rule='At 5bp LT must improve Sharpe and Calmar versus P3 and LR; CT must improve both versus P3, MT and CR. Ridge arms require both above P3; CR also above MR. At 20bp CAGR sacrifice versus P3 <=0.5pp, primary maximum drawdown worsening <=0.5pp; delayed Sharpe and Calmar must both exceed delayed P3. No automatic promotion. F0/F3 remain reported stronger reference hurdles.',
            max_cagr_sacrifice=.005,max_drawdown_worsening=.005),
        budget=dict(primary_arms=len(ARMS),replays=len(jobs()),paired_comparisons=len(COMPARISONS),native_checks=len(ARMS),search=False),
        promotion_eligible=False,limitations=[*old['limitations'],*macro.catalog['limitations'],
            'Seven leading candidates and six context features from four series; GDP excluded. Regional Philadelphia expectations are not national PMI; no consensus-surprise data.',
            'Every ETF receives a separate US-factor model. These are conditional associations, not each country’s domestic fundamentals or identified causal shock effects.',
            'Training uses expanding original-vintage monthly rows, with complete open-to-open return labels ending before the prior-close cutoff; the current decision open is never read during fitting.',
            'Previously inspected 2016–2026 history provides retrospective walk-forward evidence, not an untouched holdout. Adding features does not add independent months.',
            'Unavailable features cause group-wide abstention to P3; no imputation or latest-vintage replacement. Matched leading controls isolate context missingness.',
            'The capped parent is a research risk control, not a promoted change. F0/F3 are unchanged historical references and can have larger inherited target weights. All economic candidates cap final targets at 45%; subsequent holding drift remains possible.',
            'Economic models reweight only already eligible positive parent positions. Beneficiaries outside the parent basket cannot be added by this experiment.',
            'Original-window availability relies on an explicit ALFRED daily-archive assumption; actual recorder first capture remains October 2026, not historical real-time app observation.',
            'Nine paired mean-return contrasts use Holm adjustment within each predeclared block sensitivity. Ratio intervals are marginal, use 252-session CAGR and include partial October.',
            'No new data feed, instrument, single stock, monitoring recipe or execution authority. Existing recorded inputs suffice for this finite test.'])
    root.mkdir(parents=True)
    write_json(root/'protocol.json',protocol)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(runner,root/'runner.py')
    write_json(root/'bars.json',bars);write_json(root/'urth.json',urth)
    for arm,rows in controls.items(): write_json(root/'controls'/(arm+'.json'),rows)
    vintages = {str(date.fromisoformat(r['known_through'])-timedelta(days=1)) for r in controls['F0'].values()}
    locations = []
    for entry in macro.catalog['snapshots']:
        if entry['vintage'] not in vintages: continue
        macro.snapshot(entry['series'],entry['vintage'])
        destination = root/'economic'/entry['series']/entry['vintage'];destination.mkdir(parents=True)
        for name in [*read_json(Path(entry['root'])/'manifest.json'),'manifest.json']:
            shutil.copy2(Path(entry['root'])/name,destination/name)
        locations.append(dict(entry,root=str(destination.resolve())))
    write_json(root/'economic_catalog.json',macro.catalog);write_json(root/'economic_locations.json',locations)
    write_json(root/'data_receipt.json',dict(price_batch=publication['version'],publication=publication,governed_files=reader.used,
        parent=str(parent.resolve()),parent_input_sha256=sha256(parent/'input_manifest.json'),
        parent_decision_sha256=sha256(parent/'decision_manifest.json'),baseline_price_parity=True,
        economic_pin=dict(root=pin['root'],batch=pin['batch']),economic_pin_file_sha256=sha256(economic_pin),
        image=read_json(parent/'data_receipt.json')['image']))
    write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in sorted(root.rglob('*')) if p.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/'protocol.json'),budget=protocol['budget'])


def initialize(root):
    global _DATA
    root = Path(root);checked_files(root,'input_manifest.json')
    reader = object.__new__(EconomicInputs);reader.catalog = read_json(root/'economic_catalog.json')
    original = {(r['series'],r['vintage']):r for r in reader.catalog['snapshots']}
    locations = read_json(root/'economic_locations.json')
    for row in locations:
        prior = original[(row['series'],row['vintage'])]
        if {k:v for k,v in row.items() if k!='root'} != {k:v for k,v in prior.items() if k!='root'}:
            raise ValueError('Frozen economic locator changed publication identity')
    reader.catalog = dict(reader.catalog,snapshots=locations)
    reader.batch = read_json(root/'data_receipt.json')['economic_pin']['batch']
    _DATA = dict(root=root,protocol=read_json(root/'protocol.json'),bars=read_json(root/'bars.json'),reader=reader,
        controls={a:read_json(root/'controls'/(a+'.json')) for a in ['F0','F3','RP']})
    _DATA['opens'] = {s:{r['trade_date']:r['open'] for r in rows} for s,rows in _DATA['bars'].items()}
    if (root/'features.json').exists():
        checked_files(root,'feature_manifest.json');_DATA['features'] = read_json(root/'features.json')


def feature_decision(day):
    known = _DATA['controls']['F0'][day]['known_through']
    if any(_DATA['controls'][a][day]['known_through'] != known for a in ['F3','RP']):
        raise ValueError('Control decision clocks differ')
    known = date.fromisoformat(known)
    return day,panel(_DATA['reader'],str(known-timedelta(days=1)),datetime.combine(known,us_equity_market_close(known),NY))


def freeze_features(root, rows):
    write_json(root/'features.json',rows)
    write_json(root/'feature_manifest.json',{'features.json':sha256(root/'features.json')})


def model_decision(day):
    data = _DATA
    models = {g:fit_predict(day,data['controls']['F0'][day]['known_through'],data['features'],data['opens'],g) for g in GROUPS}
    if models['matched']['sample_sha256'] != models['combined']['sample_sha256'] or models['matched']['ready'] != models['combined']['ready']:
        raise ValueError('Context comparison samples differ')
    parent = data['controls']['F3'][day]
    capped = FinalWeightCapOverlay().apply([AllocationTarget.model_validate(t) for t in parent['targets']],None)
    decisions = dict(P3=dict(parent,targets=[t.model_dump(mode='json') for t in capped]))
    for arm,(group,kind) in VARIANTS.items():
        targets = tilt(capped,models[group],kind)
        if gross(targets) != gross(capped):raise ValueError('Changed parent invested budget')
        decisions[arm] = dict(parent,targets=[t.model_dump(mode='json') for t in targets],economic=dict(group=group,kind=kind,
            ready=models[group]['ready'],reason=models[group]['reason'],training_rows=models[group]['training_rows'],
            training_sha256=models[group]['training_sha256'],last_label_end=models[group]['last_label_end']))
    return day,dict(models=models,decisions=decisions)


def freeze_decisions(root, rows):
    for arm in ['F0','F3','RP']:
        write_json(root/'decisions'/(arm+'.json'),read_json(root/'controls'/(arm+'.json')))
    for arm in ['P3',*VARIANTS]:
        write_json(root/'decisions'/(arm+'.json'),{d:rows[d]['decisions'][arm] for d in sorted(rows)})
    write_json(root/'models.json',{d:rows[d]['models'] for d in sorted(rows)})
    paths = [*sorted((root/'decisions').glob('*.json')),root/'models.json']
    write_json(root/'decision_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in paths})


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data = _DATA;root = data['root'];p = data['protocol'];arm,cost,delay,period = job
    checked_files(root,'decision_manifest.json')
    start = p['calibration_start'] if period=='full' else p['evaluation_start']
    bars = {'URTH':read_json(root/'urth.json')} if arm=='URTH' else data['bars']
    days = [r['trade_date'] for r in data['bars']['SPY']]
    quotes,sessions = quotes_for_data(bars,days,start)
    if arm=='URTH':
        decisions = {sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],
            targets=[AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=D(1),rationale='buy and hold').model_dump(mode='json')])}
    else:decisions = {d:r for d,r in read_json(root/'decisions'/(arm+'.json')).items() if d>=start}
    if delay:decisions = {sessions[sessions.index(d)+delay]:r for d,r in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name = job_name(job);bundle = root/'bundles'/name
    freeze_usd_bundle(bundle,root,dict(id=arm,name=LABELS[arm],period=period,delay_sessions=delay,version=p['version'],model=SPEC),decisions,quotes,sessions,cost)
    path = root/'python'/(name+'.json')
    if path.exists():raise FileExistsError('Replay already exists: '+name)
    write_json(path,run_usd_reference(bundle))
    write_json(path.with_suffix('.receipt.json'),dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')))
    return name


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    results = {}
    for job in jobs():
        name = job_name(job);path = root/'python'/(name+'.json');receipt = read_json(path.with_suffix('.receipt.json'))
        if receipt['sha256'] != sha256(path) or receipt['manifest_sha256'] != sha256(root/'bundles'/name/'manifest.json'):
            raise ValueError('Changed replay output')
        result = read_json(path);stats = statistics(result,read_json(root/'bundles'/name/'quotes.json'))
        stats.update(calmar=stats['cagr']/abs(stats['max_drawdown']) if stats['max_drawdown'] else None,
            trades=len(result['fills']),maximum_target=max(float(t['target_weight']) for row in result['decisions'].values() for t in row['targets']))
        results[name] = stats
    write_json(root/'statistics.json',results)
    write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    return results
