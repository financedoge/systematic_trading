"""Finite, frozen full-pool study using application-owned models and replay.

Run prepare, models, then replay. No provider prices, strategy registration,
allocation changes or broker order methods are reachable from this runner.
"""
import argparse
from dataclasses import replace
from datetime import date
from pathlib import Path
import json
import shutil
import time
import subprocess
import sys

# Resume with the exact frozen runner and package, not whatever source happens
# to be checked out later. The script directory also pins package imports.
if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] in {'prepare','models','replay'}:
    resume = argparse.ArgumentParser(add_help=False)
    resume.add_argument('stage', choices=['prepare','models','replay'])
    resume.add_argument('--root', type=Path, default=Path('var/research/etf-expansion-20261014-v1'))
    known, _ = resume.parse_known_args()
    frozen_runner = (known.root/'source/run_etf_expansion.py').resolve()
    if known.stage != 'prepare' and frozen_runner.exists() and Path(__file__).resolve() != frozen_runner:
        # Verify source and inputs before executing or importing frozen code.
        import hashlib
        study_root = known.root.resolve()
        frozen_files = json.loads((study_root/'input_manifest.json').read_text(encoding='utf8'))
        for relative, expected in frozen_files.items():
            path = (study_root/relative).resolve()
            if not path.is_relative_to(study_root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('Frozen research input hash mismatch: ' + relative)
        raise SystemExit(subprocess.call([sys.executable, '-B', str(frozen_runner),
            known.stage, '--root', str(known.root.resolve())],
            stdout=sys.stdout, stderr=sys.stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0))

import numpy as np
from scipy.stats import spearmanr

from systematic_trading.config import get_settings
from systematic_trading.domain.market import Instrument
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research import instruments_for_definition, BENCHMARK_INSTRUMENTS
from systematic_trading.research.etf_expansion import load_published_pool, admission_for_day
from systematic_trading.research.fr25_tracking import economic_inputs, prepare_schedule
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.momentum_analysis import statistics, paired_bootstrap
from systematic_trading.research.momentum_calculation import quotes_for_data
from systematic_trading.research.momentum_replay import checked_files, freeze_usd_bundle, native_parity
from systematic_trading.research.momentum_signals import decision_sessions
from systematic_trading.research.rolling_tracking import prepare_model_schedule
from systematic_trading.research.strategy_catalog import fr25_definition, StrategyDefinition
from systematic_trading.research.turnover_gate import implied_turnover, legacy_screen as screen
from systematic_trading.research.usd_data import load_usd
from systematic_trading.research.usd_tracking import prepare_usd_schedule


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def manifest(root, name, files):
    write_json(root/name,{p.relative_to(root).as_posix():sha256(p) for p in sorted(files)})


def prepare(root):
    if root.exists():
        checked_files(root,'input_manifest.json')
        return
    settings=get_settings();analytics=AnalyticsStore.from_settings(settings)
    pin=read(Path('var/research/execution-expansion-20261013-v1/expanded-price-pin.json'))
    inventory=read(Path('research/etf-universe-inventory-2026-10-13/inventory.json'))
    metadata={r['symbol']:r for r in inventory['candidates']}
    config=read(Path('config/research-etf-recorders.json'))
    base=fr25_definition();original=instruments_for_definition(base)
    funds={f['symbol']:dict(metadata[f['symbol']],**f) for f in config['funds'] if f['symbol']!='XOP'}
    for symbol in original:
        if symbol not in funds:
            funds[symbol]=dict(metadata[symbol],requires_recorder=False)
    assert len(funds)==52
    reader=GovernedInputs(Path(pin['root']),pin['batch'])
    pool=load_published_pool(reader,list(funds.values()),through=pin['through'])
    if not set(original)<=set(pool['bars']):
        raise ValueError('Original control histories incomplete')
    members=dict(original)
    for symbol in pool['bars']:
        if symbol not in members:
            members[symbol]=Instrument(symbol=symbol,name=funds[symbol]['name'],asset_class='etf',
                exchange='NASDAQ' if funds[symbol].get('primary_exchange') in {'NASDAQ','ISLAND'}
                    or funds[symbol].get('listing_exchange_code')=='Q' else 'NYSE',
                quote_currency='USD',country='US',sector=funds[symbol]['duplicate_review_group'])
    expanded=replace(base,key='research_fr25_expanded_retrospective_v1',
        name='FR25 expanded current-cohort diagnostic',universe_key='frozen_expansion_20261014',
        universe_members=tuple(members[s].model_dump(mode='json') for s in sorted(pool['bars'])))
    benchmark=load_published_pool(reader,[dict(symbol='URTH',requires_recorder=False)],
        through=pin['through'],start=pool['common_start'])
    if 'URTH' not in benchmark['bars']:raise ValueError('Audited benchmark unavailable')
    usd,usd_receipt=load_usd(analytics)
    financial=economic_inputs(analytics,pool['bars'],pool['common_start'])
    protocol=dict(version='etf-expansion-retrospective-v1',registered_on='2026-10-14',
        start='2021-01-04',through=pin['through'],common_warmup_start=pool['common_start'],
        calibration_end='2024-12-31',later_comparison_start='2025-01-01',
        initial_cash_usd='100000',cost_bps=[5,10],slippage_bps=0,
        arms=['original14','expanded'],candidate_count=52,supported_count=len(pool['bars']),
        image=read(settings.strategy_monitoring_config_path)['calculation']['image'],
        admission=dict(prior_observations=253,liquidity_sessions=63,median_usd=5_000_000,
            minimum_usd=500_000,duplicate_rule='highest prior median dollar volume, then permanent candidate ID',
            maximum_order_adv_fraction=.005),
        pretest=dict(annual_cost_ceiling_bps=44,ic_margin=3,period_sessions=21,
            ic='Mean monthly cross-sectional Spearman of FR25 selector scores and next 21-session open returns; admissible pool; calibration only',
            sigma='Pooled calibration forward-return standard deviation',
            expanded_replay_requires='pass',original_control='Registered recipe, report gate without changing control'),
        inference=dict(comparisons=1,block_months=6,replications=20000,seed=20261014),
        limits=dict(model_workers=4,native_cpus=2,native_memory_gib=4,simultaneous_native_runs=1),
        limitations=[
            'Retrospective current-cohort diagnostics, with survivorship and historical mandate/membership limitations; not promotion evidence.',
            'Price vintages are published, audited and hash verified, but historical publication availability is not certified.',
            'Raw prices and volumes are audited reconstructions, not tape-certified. Unsupported common-window observations exclude the fund; no filling.',
            'Common history begins with the youngest supported fund. Models are retrained on this common history; the control may differ from full-history monitoring.',
            'Economic archive vintages before 2026-10-10 use conservative daily availability assumptions; actual first-seen evidence is required thereafter.',
            '2025 onward is a later chronological comparison, not an untouched holdout for the previously researched FR25 recipe.',
            'No historical spreads, historical fees or complete historical mandate ledger. Prior dollar volume is not proof of execution quality.',
            'USD adjusted units and next-session open execution; zero cash interest, no modeled spread/slippage/impact. Costs are sensitivity assumptions.',
            'Admission changes eligibility only. Features/ranks use the declared full candidate pool; no class normalization or parameter search.',
            'Financial information abstention retains the registered M1 fallback. No macro or FX prices are filled; USD accounting requires no FX conversion.'
        ])
    root.mkdir(parents=True)
    shutil.copytree('src/systematic_trading',root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(__file__,root/'source/run_etf_expansion.py')
    for name,obj in dict(protocol=protocol,price_pin=pin,pool=pool,candidates=list(funds.values()),
            definitions=dict(original14=base.to_dict(),expanded=expanded.to_dict()),
            usd=usd,usd_receipt=usd_receipt,financial_inputs=financial,benchmark=benchmark).items():
        write_json(root/(name+'.json'),obj)
    manifest(root,'input_manifest.json',[p for p in root.rglob('*') if p.is_file()])
    print(json.dumps(dict(stage='prepared',supported=len(pool['bars']),exclusions=pool['exclusions'],
        common_start=pool['common_start'],batch=pin['batch'],protocol_sha256=sha256(root/'protocol.json'))),flush=True)


def models(root):
    checked_files(root,'input_manifest.json')
    if (root/'model_manifest.json').exists():
        checked_files(root,'model_manifest.json');return
    settings=get_settings();p=read(root/'protocol.json');data=read(root/'pool.json')
    codes={str(f.relative_to(root/'source')):sha256(f) for f in (root/'source').rglob('*.py')}
    for arm,recipe in read(root/'definitions.json').items():
        target=root/'models'/arm
        if (target/'complete.json').exists():
            checked_files(target,'complete.json');continue
        definition=StrategyDefinition.from_dict(recipe)
        bars={s:data['bars'][s] for s in instruments_for_definition(definition)}
        started=time.perf_counter()
        rolling,receipt=prepare_model_schedule(settings,dict(latest_bars=bars,provenance=data['provenance']),
            definition,p['start'],codes,max_workers=p['limits']['model_workers'])
        financial=prepare_schedule(read(root/'financial_inputs.json'),bars,max_workers=p['limits']['model_workers'])
        usd=prepare_usd_schedule(bars,read(root/'usd.json'))
        for name,obj in dict(rolling=rolling,rolling_receipt=receipt,financial=financial,usd=usd).items():
            write_json(target/(name+'.json'),obj)
        write_json(target/'timing.json',dict(seconds=time.perf_counter()-started,workers=p['limits']['model_workers']))
        manifest(target,'complete.json',list(target.glob('*.json')))
        print(json.dumps(dict(stage='models',arm=arm,seconds=time.perf_counter()-started)),flush=True)
    manifest(root,'model_manifest.json',[f for f in (root/'models').rglob('*') if f.is_file()])


def decisions_and_gate(root,arm,definition):
    p=read(root/'protocol.json');data=read(root/'pool.json');funds=read(root/'candidates.json')
    symbols=instruments_for_definition(definition)
    bars={s:data['bars'][s] for s in symbols};raw={s:data['raw_bars'][s] for s in symbols}
    records={s:data['records'][s] for s in symbols};days=data['calendar']
    model={name:read(root/'models'/arm/(name+'.json')) for name in ('rolling','financial','usd')}
    decisions={};ics=[];forward=[]
    for day in decision_sessions(days,p['start'],'monthly'):
        admission=admission_for_day(records,funds,day)
        diagnostic={}
        targets=targets_for_day(bars,date.fromisoformat(day),definition=definition,raw_rows=raw,
            base_tree_models=model['rolling'],economic_models=model['financial'],usd_models=model['usd'],
            admitted_symbols=set(admission['admitted']) if arm=='expanded' else None,diagnostics=diagnostic)
        i=days.index(day)
        decisions[day]=dict(signal_session=day,known_through=days[i-1],
            targets=[t.model_dump(mode='json') for t in targets],diagnostic=dict(diagnostic,admission=admission))
        if i+21<len(days) and days[i+21]<=p['calibration_end']:
            selected=admission['admitted'] if arm=='expanded' else sorted(symbols)
            scores=diagnostic['selection'][0]['observation']['scores']
            values=[float(bars[s][i+21]['open'])/float(bars[s][i]['open'])-1 for s in selected]
            q=[float(scores[s]['total']) for s in selected]
            if len(q)>=4 and np.std(q)>0 and np.std(values)>0:
                ics.append(dict(day=day,ic=float(spearmanr(q,values).statistic),count=len(q)))
                forward.extend(values)
    calibration={d:{t['symbol']:t['target_weight'] for t in r['targets']}
                 for d,r in decisions.items() if d<=p['calibration_end']}
    turnover=implied_turnover(calibration)
    if len(ics)<12 or len(forward)<2:
        gate=dict(status='insufficient',reason='Candidate-specific IC or dispersion unavailable')
    else:
        gate=screen(turnover['annual_turnover'],sigma=float(np.std(forward,ddof=1)),
            candidate_ic=float(np.mean([r['ic'] for r in ics])))
    gate.update(calibration_end=p['calibration_end'],ic_observations=ics,turnover=turnover,
        promotion_eligible=False)
    return decisions,gate,bars


def replay(root):
    checked_files(root,'input_manifest.json');checked_files(root,'model_manifest.json')
    if (root/'result_manifest.json').exists():
        checked_files(root,'result_manifest.json');return
    p=read(root/'protocol.json');data=read(root/'pool.json');results={};gates={}
    recipes=read(root/'definitions.json')
    for arm,recipe in recipes.items():
        decisions,gate,bars=decisions_and_gate(root,arm,StrategyDefinition.from_dict(recipe))
        write_json(root/'decisions'/(arm+'.json'),decisions)
        write_json(root/'gates'/(arm+'.json'),gate);gates[arm]=gate
        print(json.dumps(dict(stage='pretest',arm=arm,status=gate['status'],ic=gate.get('candidate_ic'),
            annual_cost=gate.get('annual_cost_bps'),margin=gate.get('ic_margin'))),flush=True)
        if arm=='expanded' and gate['status']!='pass':continue
        results[arm]={}
        for cost in p['cost_bps']:
            quotes,sessions=quotes_for_data(bars,data['calendar'],p['start'])
            bundle=freeze_usd_bundle(root/'bundles'/f'{arm}-{cost}',root,recipe,decisions,quotes,sessions,cost)
            output=root/'native'/f'{arm}-{cost}'
            native_parity(bundle,output,p['image'],cpus=str(p['limits']['native_cpus']))
            stats=statistics(read(output/'economic.json'),quotes,initial=float(p['initial_cash_usd']))
            # Generic attribution: the legacy helper's 12-symbol asset-class map
            # is replaced with the frozen classification for every constituent.
            metadata={f['symbol']:f for f in read(root/'candidates.json')}
            groups={}
            for s,v in stats['asset_pnl_usd'].items():
                group=metadata[s]['duplicate_review_group'];groups[group]=groups.get(group,0)+v
            stats['group_pnl_usd']=groups
            stats.pop('mean_equity_weight');stats.pop('mean_bond_weight')
            fills=read(output/'economic.json')['fills'];participation=[]
            for fill in fills:
                obs=decisions[fill['date']]['diagnostic']['admission']['observations'][fill['symbol']]
                fraction=abs(fill['quantity'])*float(fill['price'])/float(obs['median_dollar_volume'])
                participation.append(dict(date=fill['date'],symbol=fill['symbol'],fraction=fraction))
            stats['order_liquidity']=dict(max_fraction=max((r['fraction'] for r in participation),default=0),
                violations=[r for r in participation if r['fraction']>.005],basis='Adjusted-unit USD order notional / prior raw-dollar median')
            results[arm][str(cost)]=stats
            write_json(root/'results'/f'{arm}-{cost}.json',stats)
            print(json.dumps(dict(stage='replay',arm=arm,cost=cost,cagr=stats['cagr'],drawdown=stats['max_drawdown'])),flush=True)
    # Audited world-equity benchmark, separate from the candidate selection pool.
    from systematic_trading.domain.portfolio import AllocationTarget
    from decimal import Decimal
    bars=read(root/'benchmark.json')['bars'];quotes,sessions=quotes_for_data(bars,data['calendar'],p['start'])
    recipe=dict(universeKey='benchmark',universeMembers=[BENCHMARK_INSTRUMENTS['URTH'].model_dump(mode='json')])
    decision={sessions[0]:dict(signal_session=sessions[0],known_through=data['calendar'][data['calendar'].index(sessions[0])-1],
        targets=[AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=Decimal(1),rationale='Buy and hold').model_dump(mode='json')])}
    bundle=freeze_usd_bundle(root/'bundles/URTH-5',root,recipe,decision,quotes,sessions,5)
    output=root/'native/URTH-5';native_parity(bundle,output,p['image'],cpus='2')
    benchmark=statistics(read(output/'economic.json'),quotes,initial=float(p['initial_cash_usd']))
    write_json(root/'results/URTH-5.json',benchmark)
    comparisons={}
    if 'expanded' in results:
        a,b=results['expanded']['5'],results['original14']['5']
        for name,start in [('all',p['start'][:7]),('later',p['later_comparison_start'][:7])]:
            months=[m for m in sorted(a['monthly']) if m>=start and m<p['through'][:7]]
            matrix=[[a['monthly'][m]-b['monthly'][m]] for m in months]
            comparisons[name]=paired_bootstrap(matrix,block=6,replications=20000,seed=20261014)[0]
    write_json(root/'summary.json',dict(protocol_sha256=sha256(root/'protocol.json'),price_batch=data['provenance']['batch'],
        supported=sorted(data['bars']),exclusions=data['exclusions'],gates={k:{x:v for x,v in g.items() if x not in {'ic_observations','turnover'}} for k,g in gates.items()},
        completed=list(results),comparisons=comparisons,promotion_eligible=False))
    manifest(root,'result_manifest.json',[f for folder in ('results','gates','decisions') for f in (root/folder).rglob('*.json')]+[root/'summary.json'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','models','replay'])
    parser.add_argument('--root',type=Path,default=Path('var/research/etf-expansion-20261014-v1'))
    args=parser.parse_args()
    {'prepare':prepare,'models':models,'replay':replay}[args.stage](args.root.resolve())
