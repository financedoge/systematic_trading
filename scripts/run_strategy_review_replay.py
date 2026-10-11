"""Frozen, fixed-recipe FR25/5% HOLD repair acceptance. No selection or broker writes.

Uses the parent's verified audited inputs and causal frozen model schedules.
Regenerates targets with the app worker, independently applies the research HOLD
rule, compares holdings/fills/cash, and runs cost/delay and native parity checks.
"""
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from decimal import Decimal as D
import argparse
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import numpy as np

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import alpha101_tilt_study as rule
from systematic_trading.research.alpha101_tilt_exit_study import simulate
from systematic_trading.research.alpha101_tilt_overlay import Alpha101FamilyTiltOverlay
from systematic_trading.research.alpha101_tilt_replay_analysis import metrics_from
from systematic_trading.research.fr25_tracking import PARAMETERS
from systematic_trading.research.momentum_analysis import statistics, paired_bootstrap
from systematic_trading.research.momentum_calculation import quotes_for_data
from systematic_trading.research.momentum_replay import (
    checked_files, freeze_usd_bundle, native_parity, read_json, run_usd_reference,
)
from systematic_trading.research.strategy_catalog import fr25_definition, alpha101_tilt_definition
from systematic_trading.research.usd_monitored import worker_init, targets_worker
from systematic_trading.signals.base import SignalContext


PARENT = Path('var/research/fr25-placebo-20261010-v1')
ROOT = Path('var/research/strategy-review-20261011-v2')
KEYS = {'FR25': fr25_definition().key, 'HOLD5': alpha101_tilt_definition().key}


def weights(row):
    return {t['symbol']: D(t['target_weight']) for t in row['targets']}


def replay_job(payload):
    root, arm, cost, delay, start, window = payload
    root = Path(root)
    bars = read_json(root / 'bars.json')
    quotes, sessions = quotes_for_data(bars, [r['trade_date'] for r in bars['SPY']], start)
    decisions = {d: r for d, r in read_json(root / 'decisions' / (arm + '.json')).items() if d >= start}
    if not sessions or not decisions or min(decisions) != sessions[0]:
        raise ValueError('Replay must begin at the first supported decision; no cash-only padding')
    if delay:
        decisions = {sessions[sessions.index(d) + delay]: r for d, r in decisions.items()
                     if sessions.index(d) + delay < len(sessions)}
    name = f'{arm}-cost{cost}-delay{delay}-{window}'
    bundle = root / 'bundles' / name
    freeze_usd_bundle(bundle, root, dict(arm=arm, delay_sessions=delay, window=window),
                      decisions, quotes, sessions, cost)
    result = run_usd_reference(bundle)
    write_json(root / 'python' / (name + '.json'), result)
    write_json(root / 'python' / (name + '.receipt.json'),
               dict(sha256=sha256(root / 'python' / (name + '.json')),
                    manifest_sha256=sha256(bundle / 'manifest.json')))
    metrics = metrics_from(result['nav'], initial_capital=1_000_000)
    ledger = statistics(result, quotes)
    assert abs(metrics['sharpe_zero_cash'] - ledger['sharpe_zero_cash']) < 1e-12
    assert abs(metrics['max_drawdown'] - ledger['max_drawdown']) < 1e-12
    metrics.update(annual_cost_bps=ledger['annual_cost_bps'], annual_turnover=ledger['annual_turnover'],
                   fees=ledger['total_fees_usd'], fills=len(result['fills']), decisions=len(decisions))
    return name, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if root.exists():
        raise FileExistsError('Preserve review attempts; use a new root')
    parent = PARENT.resolve()
    checked_files(parent, 'input_manifest.json')
    checked_files(parent, 'decision_manifest.json')
    receipt = read_json(parent / 'data_receipt.json')
    p = read_json(parent / 'protocol.json')
    bars, raw, models, macro = [read_json(parent / n) for n in
                               ('bars.json', 'raw.json', 'xgb_usd.json', 'macro.json')]
    original = read_json(parent / 'decisions/FR25.json')
    days = sorted(original)
    definitions = [fr25_definition(), alpha101_tilt_definition()]
    root.mkdir(parents=True)
    protocol = dict(version='strategy-review-fixed-pair-v2', initial_cash_usd=1_000_000,
        parent=str(parent), price_batch=receipt['price_batch'], definitions=[d.to_dict() for d in definitions],
        windows=dict(evaluation=p['evaluation_start']), end=p['end'], costs=[5, 10, 20],
        delays=[0, 1], primary='HOLD5 minus FR25, evaluation window, 5bp, no extra delay',
        bootstrap=dict(blocks=[3, 6, 12], replications=10000, seed=20261011),
        decision='No optimisation. Fixed 5% recipe is retained for observation only; no promotion from this rerun.',
        limitations=p['limitations'] + [
            'Inspected-sample correction, not untouched validation or broker PnL.',
            'Adjusted return units; audited raw close and raw volume for activity. USD accounting, no historical FX.',
            'Revised audited prices do not establish historical publication availability.',
            'Frozen expanding financial/model schedules are reused, with strict per-decision cutoff checks.',
            'No exit optimisation; research HOLD must match the app monthly schedule including identical targets.'])
    assert days[0] == protocol['windows']['evaluation']
    write_json(root / 'protocol.json', protocol)
    shutil.copytree(Path('src/systematic_trading'), root / 'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('bars.json', 'raw.json', 'data_receipt.json'):
        shutil.copyfile(parent / name, root / name)
    write_json(root / 'parent_hashes.json', {name: sha256(parent / name) for name in
        ('input_manifest.json', 'decision_manifest.json', 'protocol.json', 'bars.json', 'raw.json',
         'macro.json', 'xgb_usd.json', 'decisions/FR25.json')})
    economic = dict(parameters=PARAMETERS, models={day: macro[day]['financial'] for day in days})
    write_json(root / 'worker.json', dict(bars=bars, raw_bars=raw, rolling=models['rolling'],
        base_models={}, usd=models['usd'], economic=economic, definitions=[d.to_dict() for d in definitions]))
    write_json(root / 'input_manifest.json', {f.relative_to(root).as_posix(): sha256(f)
               for f in root.rglob('*') if f.is_file()})
    for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[variable] = '1'
    print('Frozen protocol', sha256(root / 'protocol.json'), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=worker_init, initargs=(str(root),)) as pool:
        computed = dict(pool.map(targets_worker, days))
    for day in days:
        assert weights(computed[day][KEYS['FR25']]) == weights(original[day]), day
    for arm, key in KEYS.items():
        write_json(root / 'decisions' / (arm + '.json'), {d: computed[d][key] for d in days})
    # Independent research rule and state machine, versus actual app-worker outputs.
    books, desired = {}, {}
    current, wanted = None, None
    for day in [r['trade_date'] for r in bars['SPY'] if r['trade_date'] >= days[0]]:
        if day in computed:
            base = computed[day][KEYS['FR25']]
            targets = [AllocationTarget.model_validate(t) for t in base['targets']]
            typed = {s: [PriceBar.model_validate(r) for r in rows if r['trade_date'] < day][-260:]
                     for s, rows in bars.items()}
            raw_typed = {s: [PriceBar.model_validate(r) for r in rows if r['trade_date'] < day][-260:]
                         for s, rows in raw.items()}
            context = SignalContext(as_of=date.fromisoformat(day), instruments={}, bars_by_symbol=typed, trade_dates=[])
            instance = Alpha101FamilyTiltOverlay(raw=raw_typed)
            per_alpha = instance.values_for([t.symbol for t in targets if t.target_weight > 0], context)
            scores, _ = rule.composite_scores([t.symbol for t in targets if t.target_weight > 0], per_alpha)
            adjusted, _ = rule.tilt_targets(targets, scores or {}, D('.05'))
            assert {t.symbol: t.target_weight for t in adjusted} == weights(computed[day][KEYS['HOLD5']]), day
            current = {t.symbol: float(t.target_weight) for t in targets}
            wanted = {t.symbol: float(t.target_weight) - current[t.symbol] for t in adjusted}
        books[day], desired[day] = current, wanted
    research_rows, _ = simulate(books, set(days), .05, 'HOLD', desired, {})
    assert sorted(research_rows) == days
    for day, actual in research_rows.items():
        expected = weights(computed[day][KEYS['HOLD5']])
        assert all(abs(D(str(actual.get(s, 0))) - w) < D('1e-12') for s, w in expected.items())
    print('Exact FR25 control and monthly research/app target parity:', len(days), flush=True)
    jobs = [(str(root), arm, cost, delay, start, window) for arm in KEYS for cost in (5, 10, 20)
            for delay in (0, 1) for window, start in protocol['windows'].items()]
    results = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for name, metrics in pool.map(replay_job, jobs):
            results[name] = metrics
            print(name, round(metrics['total_return'], 6), flush=True)
    # Same HOLD schedule through the actual accounting engine, not only target equality.
    control_name = 'HOLD5-cost5-delay0-evaluation'
    bundle = root / 'bundles' / control_name
    q, sessions = read_json(bundle / 'quotes.json'), read_json(bundle / 'sessions.json')
    original_hold = read_json(root / 'decisions/HOLD5.json')
    research = {d: dict(original_hold[d], targets=[dict(t, target_weight=str(research_rows[d].get(t['symbol'], 0)))
                 for t in original_hold[d]['targets']]) for d in days if d in sessions}
    check = root / 'bundles/research-HOLD5-parity'
    freeze_usd_bundle(check, root, dict(arm='research-HOLD5-parity'), research, q, sessions, 5)
    replay = run_usd_reference(check)
    expected = read_json(root / 'python' / (control_name + '.json'))
    for key in ('fills', 'nav', 'final_positions'):
        assert replay[key] == expected[key], key
    write_json(root / 'research_hold_parity.json', dict(passed=True, decisions=len(research),
        fills=len(replay['fills']), nav=len(replay['nav']), quantities_cash_fees_equal=True))
    inference = {}
    for window in protocol['windows']:
        base, candidate = [results[f'{arm}-cost5-delay0-{window}']['monthly'] for arm in KEYS]
        assert set(base) == set(candidate)
        matrix = np.array([[candidate[m] - base[m]] for m in sorted(base)])
        inference[window] = {str(block): paired_bootstrap(matrix, block, 10000, 20261011)[0]
                             for block in (3, 6, 12)}
    write_json(root / 'analysis.json', dict(protocol=protocol, metrics=results, contrasts=inference,
                                           promotion_eligible=False))
    native = {}
    if args.native:
        for arm in KEYS:
            name = f'{arm}-cost5-delay0-evaluation'
            native[arm] = native_parity(root / 'bundles' / name, root / 'native' / name,
                                       receipt['image'], cpus='2')
            print('Native parity', arm, native[arm]['status'], flush=True)
    checked_files(parent, 'input_manifest.json')
    checked_files(parent, 'decision_manifest.json')
    checked_files(root, 'input_manifest.json')
    write_json(root / 'acceptance.json', dict(status='passed', app_decisions=len(days),
        matched_replays=len(results), monthly_hold_parity=True, parent_hashes_verified=True,
        native={k: v['status'] for k, v in native.items()}, protocol_sha256=sha256(root / 'protocol.json'),
        analysis_sha256=sha256(root / 'analysis.json')))
    print('Acceptance:', root / 'acceptance.json', flush=True)


if __name__ == '__main__':
    main()
