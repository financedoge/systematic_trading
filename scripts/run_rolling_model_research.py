"""Prepare and run a fixed, resumable rolling-model experiment on audited inputs."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, UTC
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, write_json, verify_bundle
from systematic_trading.lean.runner import run_bundle
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.market_data.golden import _sql_string
from systematic_trading.research import current_sota_definition, instruments_for_definition, instantiate_overlays
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
from systematic_trading.research.rolling_models import fit_record
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.library import compute_signal_features


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def atomic_json(path, payload):
    temporary = path.with_suffix('.tmp')
    write_json(temporary, payload)
    os.replace(temporary, path)


def verify_files(root, manifest):
    for name, expected in read(root/manifest).items():
        path = (root/name).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != expected:
            raise ValueError('Frozen study input changed: '+name)


def build_records(bars):
    typed = {s: [PriceBar.model_validate(r) for r in rows] for s, rows in bars.items()}
    days = [r['trade_date'] for r in bars['SPY']]
    starts = [d for i, d in enumerate(days) if i >= 379 and d[:7] != days[i-1][:7]]
    prices = {s: {r['trade_date']: float(r['close']) for r in rows} for s, rows in bars.items()}
    records = []
    for start, end in zip(starts, starts[1:]):
        known, label_end = days[days.index(start)-1], days[days.index(end)-1]
        # Deliberate physical truncation in addition to the feature service's date guard.
        context = SignalContext(as_of=date.fromisoformat(start), instruments={}, trade_dates=[],
            bars_by_symbol={s: [r for r in rows if str(r.trade_date) <= known] for s, rows in typed.items()})
        returns = {s: prices[s][label_end]/prices[s][known]-1 for s in bars}
        mean = sum(returns.values())/len(returns)
        for s in bars:
            records.append(dict(symbol=s, signal_session=start, known_through=known, label_end=label_end,
                                inputs=compute_signal_features(symbol=s, context=context),
                                relative_return=returns[s]-mean, role='training_only'))
    return records


def prepare(protocol_path):
    protocol = read(protocol_path)
    root = Path(protocol['root'])
    if (root/'inputs.json').exists():
        if sha256(protocol_path) != sha256(root/'protocol.json'):
            raise ValueError('Protocol changed; use a new version/root')
        verify_files(root, 'inputs.json')
        return root
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(protocol_path, root/'protocol.json')
    governed = GovernedInputs(Path(protocol['governed_root']), protocol['batch'])
    store = AnalyticsStore.from_settings(AppSettings())
    store.client.timeout_seconds = 120
    committed = store.query('SELECT version FROM analytics.publications FINAL WHERE workspace='
        +_sql_string(store.workspace)+" AND source_id='governance/catalog' AND version="+_sql_string(protocol['batch']))
    if not committed:
        raise ValueError('Audited batch is not committed in ClickHouse')
    days = [d for d in read(governed.checked('calendar.json'))['sessions']
            if protocol['warmup_start'] <= d <= protocol['end']]
    bars = {}
    for symbol in instruments_for_definition(current_sota_definition()):
        rows = governed.rows(symbol, protocol['warmup_start'], protocol['end'])
        if [r['trade_date'] for r in rows] != days:
            raise ValueError('Audited calendar coverage mismatch: '+symbol)
        bars[symbol] = [etf_bar(r) for r in rows]
    external = governed.rows('URTH', protocol['long_start'], protocol['end'])
    write_json(root/'urth.json', [dict(trade_date=r['trade_date'], open=str(r['adjusted_open']),
                                    close=str(r['adjusted_close'])) for r in external
                                if r['adjusted_open'] is not None and r['adjusted_close'] is not None])
    for key, target in [('legacy_fx', 'fx.json'), ('annual_models', 'annual_models.json')]:
        source = Path(protocol[key+'_path'])
        if sha256(source) != protocol[key+'_sha256']:
            raise ValueError('Pinned '+key+' changed')
        shutil.copyfile(source, root/target)
    if any(d not in read(root/'fx.json') for d in days):
        raise ValueError('Frozen FX scenario has missing sessions')
    write_json(root/'bars.json', bars)
    write_json(root/'training_records.json', build_records(bars))
    versions = {n: importlib.metadata.version(n) for n in ('numpy', 'scikit-learn', 'xgboost')}
    write_json(root/'provenance.json', dict(batch=protocol['batch'], files=governed.used,
        versions=versions, created_at=datetime.now(UTC).isoformat(), historical_available_at=None,
        etf_basis=protocol['etf_basis'], limitations=protocol['limitations']))
    source_root = Path(__file__).resolve().parents[1]/'src/systematic_trading'
    shutil.copytree(source_root, root/'preparation_source/systematic_trading', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(Path(__file__), root/Path(__file__).name)
    write_json(root/'inputs.json', {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*')) if p.is_file()})
    return root


def fit_schedules(root):
    verify_files(root, 'inputs.json')
    protocol, bars = [read(root/(n+'.json')) for n in ('protocol', 'bars')]
    days = [r['trade_date'] for r in bars['SPY']]
    cutoffs = [days[i-1] for i, d in enumerate(days) if d >= protocol['long_start'] and d[:7] != days[i-1][:7]]
    specs = {f'{family}_{years}y': (family, years, protocol['seed'], cutoffs)
             for family in protocol['families'] for years in protocol['window_years']}
    for family in ('forest', 'xgboost'):
        first_index = next(i for i, d in enumerate(days) if d >= protocol['start'])
        specs[family+'_frozen'] = (family, None, protocol['seed'], [days[first_index-1]])
        for years in protocol['window_years']:
            for seed in protocol['sensitivity_seeds']:
                specs[f'{family}_{years}y_seed{seed}'] = (family, years, seed, [d for d in cutoffs if d >= '2022-12-01'])
    (root/'models').mkdir(exist_ok=True)
    pending = {}
    for name, spec in specs.items():
        destination = root/'models'/(name+'.json')
        if destination.exists():
            if sha256(destination) != read(destination.with_suffix('.sha256.json'))['sha256']:
                raise ValueError('Model schedule changed: '+name)
        else:
            pending[name] = spec
    # Parallelize independent monthly fits; libraries within each process use one thread.
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    cores = os.cpu_count() or 1
    started = time.perf_counter()
    print('PARALLEL FIT', cores, 'logical cores', sum(len(v[3]) for v in pending.values()), 'fits', flush=True)
    schedules = {name: {} for name in pending}
    with ProcessPoolExecutor(max_workers=cores, initializer=initialize_fit_worker, initargs=(str(root),)) as pool:
        jobs = {pool.submit(fit_worker, family, years, seed, cutoff): (name, cutoff)
                for name, (family, years, seed, dates) in pending.items() for cutoff in dates}
        for index, future in enumerate(as_completed(jobs), 1):
            name, cutoff = jobs[future]
            schedules[name][cutoff] = future.result()
            if len(schedules[name]) == len(pending[name][3]):
                destination = root/'models'/(name+'.json')
                write_json(destination, schedules[name])
                write_json(destination.with_suffix('.sha256.json'), {'sha256': sha256(destination)})
                print('FITTED', name, len(schedules[name]), round(time.perf_counter()-started, 1), flush=True)
            if index % 100 == 0:
                print('FIT PROGRESS', index, '/', len(jobs), flush=True)
    write_json(root/'models.json', {p.relative_to(root).as_posix(): sha256(p) for p in sorted((root/'models').glob('*.json'))})


def initialize_fit_worker(root):
    global FIT_RECORDS, FIT_FEATURES
    FIT_RECORDS = read(Path(root)/'training_records.json')
    FIT_FEATURES = instantiate_overlays(current_sota_definition())[1].model.feature_names


def fit_worker(family, years, seed, cutoff):
    return fit_record(FIT_RECORDS, cutoff, years, FIT_FEATURES, family, seed=seed)


def trial_matrix(protocol):
    variants = [f'{f}_{y}y' for f in protocol['families'] for y in protocol['window_years']]
    trials = {'sota': {}, **{n: dict(model=n) for n in variants},
              'forest_frozen': dict(model='forest_frozen'), 'xgboost_frozen': dict(model='xgboost_frozen'),
              'no_tree': dict(no_tree=True), 'risk_parity': dict(benchmark=True)}
    trials['long_sota'] = dict(long=True)
    trials.update({'long_'+n: dict(model=n, long=True) for n in variants})
    trials['long_risk_parity'] = dict(long=True, benchmark=True)
    for stress, settings in [('cost45bps', dict(transaction_cost_bps='25', slippage_bps='20')),
                             ('delay1', dict(execution_delay_sessions=1))]:
        for n in ['sota', *variants]:
            trials[n+'__'+stress] = dict(model=n if n != 'sota' else None, stress=settings, comparator='sota__'+stress)
    for f in ('forest', 'xgboost'):
        for y in protocol['window_years']:
            for seed in protocol['sensitivity_seeds']:
                name = f'{f}_{y}y_seed{seed}'
                trials[name] = dict(model=name)
    return trials


def run_trial(root, name, cfg):
    protocol, bars, fx, annual, provenance = [read(root/(n+'.json')) for n in ('protocol', 'bars', 'fx', 'annual_models', 'provenance')]
    bundle, output = root/'datasets'/name, root/'runs'/name
    if (output/'run.json').exists():
        receipt = read(output/'run.json')
        if receipt['status'] != 'succeeded':
            raise ValueError('Inspect retained failed/interrupted run before retry: '+name)
        verify_bundle(bundle)
        if sha256(bundle/'manifest.json') != receipt['manifest_sha256']:
            raise ValueError('Completed run input manifest changed')
        for relative, expected in receipt['artifacts'].items():
            if sha256(output/relative) != expected:
                raise ValueError('Completed run artifact changed')
        return name, receipt
    if not bundle.exists():
        schedule = read(root/'models'/(cfg['model']+'.json')) if cfg.get('model') else annual if cfg.get('long') and not cfg.get('benchmark') else None
        options = dict(start_date=protocol['long_start'] if cfg.get('long') else protocol['start'],
            end_date=protocol['end'], warmup_start=protocol['warmup_start'],
            strategy='benchmark' if cfg.get('benchmark') else 'sota',
            mode='shared' if '__' not in name and 'seed' not in name else 'targets',
            fx_policy='legacy_carry_max7', base_tree_model_schedule=schedule is not None,
            limitations=[protocol['limitations'], protocol['etf_basis'], protocol['window_rule']], **cfg.get('stress', {}))
        if cfg.get('long') and not cfg.get('model') and not cfg.get('benchmark'):
            options['fixed_model_from'] = '2023-01-01'
        if cfg.get('no_tree'):
            definition = current_sota_definition().to_dict()
            definition['overlays'] = [s for s in definition['overlays'] if s['kind'] != 'decision_tree']
            definition.update(key='research_sota_no_tree_v1', name='Research: SOTA without tree',
                              state='research_candidate', promotedOn=None,
                              description='Fixed ablation removing only the tree rank tilt; no promotion authority.')
            options.update(strategy='registered', strategy_definition=definition)
        print('FREEZE', name, flush=True)
        freeze_bundle(root=bundle, bars=bars, fx=fx,
            provenance=dict(provenance, study_inputs=sha256(root/'inputs.json'), model_inputs=sha256(root/'models.json')),
            spec_values=options, base_tree_models=schedule)
    print('LEAN', name, flush=True)
    result = run_bundle(bundle=bundle, output=output, image=protocol['image'])
    print('PASS', name, round(result['elapsed_seconds'], 1), flush=True)
    return name, result


def run_trials(root, workers):
    verify_files(root, 'inputs.json')
    verify_files(root, 'models.json')
    protocol = read(root/'protocol.json')
    trials = trial_matrix(protocol)
    matrix_path = root/'trials.json'
    if matrix_path.exists() and read(matrix_path) != trials:
        raise ValueError('Trial matrix changed')
    write_json(matrix_path, trials)
    passed = {}
    failures = {}
    atomic_json(root/'progress.json', dict(complete=False, phase='backtests', total=len(trials), passed=passed, pid=os.getpid()))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(run_trial, root, n, c): n for n, c in trials.items()}
        for future in as_completed(jobs):
            try:
                name, receipt = future.result()
                passed[name] = receipt['economic_sha256']
            except Exception as exc:
                failures[jobs[future]] = str(exc)
                print('FAILED', jobs[future], str(exc), flush=True)
            atomic_json(root/'progress.json', dict(complete=False, phase='backtests', total=len(trials), passed=passed,
                                                  failures=failures, pid=os.getpid()))
    if failures:
        raise ValueError('Inspect retained failed runs: '+', '.join(failures))
    atomic_json(root/'progress.json', dict(complete=True, phase='backtests_complete', total=len(trials), passed=passed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=Path('config/rolling-model-research-v1.json'))
    parser.add_argument('--phase', choices=('prepare', 'fit', 'run', 'all'), default='all')
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=2)
    args = parser.parse_args()
    root = Path(read(args.protocol)['root'])
    # OS lock is released on a crash; no stale PID can grant a second writer.
    lock = root.parent/(root.name+'.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+b') as handle:
        import msvcrt
        handle.seek(0)
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if args.phase in ('prepare', 'all'):
                prepare(args.protocol)
            if args.phase in ('fit', 'all'):
                fit_schedules(root)
            if args.phase in ('run', 'all'):
                run_trials(root, args.workers)
        except BaseException as exc:
            if root.exists():
                atomic_json(root/'failure.json', dict(time=datetime.now(UTC).isoformat(), error=str(exc), pid=os.getpid()))
            raise


if __name__ == '__main__':
    main()
