"""One preregistered P4.18 rule and its exposure-matched diagnostic. No broker writes."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import checked_files, read_json, native_parity
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.volatility_target import VolatilityTargetOverlay
from run_strategy_review_replay import replay_job


ROOT = Path('var/research/volatility-target-20261011-v1')
PARENT = Path('var/research/fr25-placebo-20261010-v1')


def main():
    if ROOT.exists():
        raise FileExistsError('Preserve completed or interrupted attempts')
    checked_files(PARENT, 'input_manifest.json')
    checked_files(PARENT, 'decision_manifest.json')
    ROOT.mkdir(parents=True)
    parent_protocol = read_json(PARENT / 'protocol.json')
    receipt = read_json(PARENT / 'data_receipt.json')
    protocol = dict(version='volatility-target-review-v1', initial_cash_usd=1_000_000,
        start=parent_protocol['evaluation_start'], end=parent_protocol['end'], price_batch=receipt['price_batch'],
        arms=['FR25', 'VOL10', 'MATCHED'], target=.10, lookback=63, cadence='base monthly',
        costs=[5, 10, 20], delays=[0, 1], matched='constant scale matching time-weighted target gross; ex-post diagnostic',
        thresholds=dict(max_cagr_sacrifice=.01, min_drawdown_improvement=.02,
                        sharpe_not_lower=True, beat_matched_drawdown_and_sharpe=True, drag_at_5bp_max=44),
        retention='all cost/delay scenarios must pass; no retuning on failure',
        limitations=parent_protocol['limitations'] + ['Inspected sample, not untouched validation.',
            'Historical revised vintages; no historical FX or publication-availability certification.',
            'USD adjusted-unit research, zero cash interest, monthly decisions; not raw-share paper execution.',
            'Matched exposure scalar uses the full study window and is diagnostic only.',
            'No promotion or paper capital change; the shared app overlay is not a registered monitored strategy.'])
    write_json(ROOT / 'protocol.json', protocol)
    shutil.copytree('src/systematic_trading', ROOT / 'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(__file__, ROOT / 'runner.py')
    shutil.copyfile(Path(__file__).with_name('run_strategy_review_replay.py'), ROOT / 'replay_runner.py')
    for file in ('bars.json', 'data_receipt.json'):
        shutil.copyfile(PARENT / file, ROOT / file)
    shutil.copyfile('docs/signal-decay-and-alpha-plan.md', ROOT / 'registered_plan.md')
    write_json(ROOT / 'parent_hashes.json', {f: sha256(PARENT / f) for f in
        ('input_manifest.json', 'decision_manifest.json', 'decisions/FR25.json', 'bars.json', 'protocol.json')})
    write_json(ROOT / 'input_manifest.json', {p.relative_to(ROOT).as_posix(): sha256(p)
               for p in ROOT.rglob('*') if p.is_file()})
    print('Frozen protocol', sha256(ROOT / 'protocol.json'), flush=True)
    bars = {s: [PriceBar.model_validate(r) for r in rows] for s, rows in read_json(ROOT / 'bars.json').items()}
    sessions = [r.trade_date for r in bars['SPY']]
    base = read_json(PARENT / 'decisions/FR25.json')
    overlay = VolatilityTargetOverlay()
    candidate, diagnostics = {}, {}
    for day, row in sorted(base.items()):
        cutoff = date.fromisoformat(day)
        context = SignalContext(as_of=cutoff, instruments={}, trade_dates=sessions,
            bars_by_symbol={s: [r for r in rows if r.trade_date < cutoff][-64:] for s, rows in bars.items()})
        targets = [AllocationTarget.model_validate(t) for t in row['targets']]
        scale, vol = overlay.scale(targets, context)
        candidate[day] = dict(row, targets=[t.model_dump(mode='json') for t in overlay.apply(targets, context)])
        diagnostics[day] = dict(scale=scale, volatility=vol, gross=float(sum(t.target_weight for t in targets)))
    base_gross = candidate_gross = 0.0
    current = None
    for session in sessions:
        day = session.isoformat()
        if day in diagnostics:
            current = diagnostics[day]
        if current is not None:
            base_gross += current['gross']
            candidate_gross += current['gross'] * current['scale']
    multiplier = candidate_gross / base_gross if base_gross else 1.0
    matched = {day: dict(row, targets=[dict(t, target_weight=str(Decimal(t['target_weight']) * Decimal(str(multiplier))))
                for t in row['targets']]) for day, row in base.items()}
    for name, rows in (('FR25', base), ('VOL10', candidate), ('MATCHED', matched)):
        write_json(ROOT / 'decisions' / (name + '.json'), rows)
    write_json(ROOT / 'decision_manifest.json', {p.relative_to(ROOT).as_posix(): sha256(p)
               for p in (ROOT / 'decisions').glob('*.json')})
    write_json(ROOT / 'diagnostics.json', dict(monthly=diagnostics, matched_scale=multiplier))
    jobs = [(str(ROOT), arm, cost, delay, protocol['start'], 'evaluation')
            for arm in protocol['arms'] for cost in protocol['costs'] for delay in protocol['delays']]
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(replay_job, jobs))
    comparisons = []
    for cost in protocol['costs']:
        for delay in protocol['delays']:
            b, v, m = [results[f'{arm}-cost{cost}-delay{delay}-evaluation'] for arm in protocol['arms']]
            checks = dict(drawdown=v['max_drawdown'] - b['max_drawdown'] >= .02,
                return_sacrifice=b['cagr'] - v['cagr'] <= .01,
                sharpe=v['sharpe_zero_cash'] >= b['sharpe_zero_cash'],
                matched_drawdown=v['max_drawdown'] > m['max_drawdown'],
                matched_sharpe=v['sharpe_zero_cash'] > m['sharpe_zero_cash'],
                cost=cost != 5 or v['annual_cost_bps'] <= 44)
            comparisons.append(dict(cost=cost, delay=delay, checks=checks, passed=all(checks.values())))
    native = native_parity(ROOT / 'bundles/VOL10-cost5-delay0-evaluation', ROOT / 'native', receipt['image'], cpus='2')
    write_json(ROOT / 'analysis.json', dict(metrics=results, comparisons=comparisons,
        retain=all(r['passed'] for r in comparisons), promotion_eligible=False))
    checked_files(ROOT, 'input_manifest.json')
    checked_files(ROOT, 'decision_manifest.json')
    write_json(ROOT / 'acceptance.json', dict(replays=len(results), native=native['status'],
        protocol_sha256=sha256(ROOT / 'protocol.json'), analysis_sha256=sha256(ROOT / 'analysis.json')))
    print('Complete', ROOT, 'retain', all(r['passed'] for r in comparisons), 'native', native['status'], flush=True)


if __name__ == '__main__':
    main()
