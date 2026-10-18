"""Finite P4.16d construction screen using pinned published application inputs.

Prepare freezes this runner and the app primitives it uses. Run always delegates
to that verified copy. No models, strategy registrations or broker calls occur.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal as D
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy.stats import spearmanr

ROOT = Path('var/research/class-volatility-screen-20261016-v1')
PROTOCOL = Path('research/class-volatility-screen-20261016-v1/protocol.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def verify(root, name):
    root = Path(root).resolve()
    for relative, expected in read(root / name).items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or digest(path) != expected:
            raise ValueError('Frozen input hash mismatch: ' + relative)


def manifest(root, name, files):
    write(root / name, {p.relative_to(root).as_posix(): digest(p) for p in sorted(files)})


def class_map(protocol, symbols):
    pairs = [(s, group) for group, members in protocol['classes'].items() for s in members]
    if len(pairs) != len({s for s, _ in pairs}):
        raise ValueError('Each candidate must have exactly one primary class')
    mapping = dict(pairs)
    if set(mapping) != set(symbols):
        raise ValueError('Class map must account for every candidate and no others')
    for parent, children in protocol['overlap_parents'].items():
        if parent not in mapping or not set(children) <= mapping.keys() or parent in children:
            raise ValueError('Invalid overlap policy')
    return mapping


def prepare(root):
    if root.exists():
        raise FileExistsError('Preserve the existing study; verify or resume it')
    protocol = read(PROTOCOL)
    parent = Path(protocol['parent'])
    verify(parent, 'input_manifest.json')
    verify(parent, 'result_manifest.json')
    candidates = read(parent / 'candidates.json')
    class_map(protocol, [c['symbol'] for c in candidates])
    # Re-read the actual published batch, not only the prior study's derived copy.
    from systematic_trading.research.etf_expansion import load_published_pool
    from systematic_trading.research.governed_inputs import GovernedInputs
    pin = read(parent / 'price_pin.json')
    reader = GovernedInputs(Path(pin['root']), pin['batch'])
    pool = load_published_pool(reader, candidates, through=protocol['through'])
    old = read(parent / 'pool.json')
    if pool != old:
        raise ValueError('Pinned publication no longer reproduces the parent pool')
    if len(candidates) != 52 or len(pool['bars']) != 50:
        raise ValueError('First-wave scope changed; declare a new protocol')
    root.mkdir(parents=True)
    shutil.copyfile(PROTOCOL, root / 'protocol.json')
    for name in ('pool.json', 'candidates.json', 'price_pin.json'):
        shutil.copyfile(parent / name, root / name)
    shutil.copytree('src/systematic_trading', root / 'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(__file__, root / 'runner.py')
    write(root / 'source_receipt.json', dict(
        parent=str(parent.resolve()), parent_input_manifest_sha256=digest(parent / 'input_manifest.json'),
        parent_result_manifest_sha256=digest(parent / 'result_manifest.json'),
        published_batch=pin['batch'], rederived_pool_matches_parent=True,
        verified_publication_files=reader.used,
        parent_gate_reference={a: read(parent / 'gates' / (a + '.json'))
                              for a in ('original14', 'expanded')},
        dependencies=dict(python=sys.version, numpy=np.__version__,
                          scipy=__import__('scipy').__version__)))
    manifest(root, 'input_manifest.json', [p for p in root.rglob('*') if p.is_file()])
    print(json.dumps(dict(stage='frozen', protocol_sha256=digest(root / 'protocol.json'),
                         input_manifest_sha256=digest(root / 'input_manifest.json'),
                         candidates=52, supported=50, exclusions=pool['exclusions'])), flush=True)


def features(close, index):
    """Index is the next-open session; never inspect it or any subsequent bar."""
    if index < 253:
        raise ValueError('Insufficient warmup')
    prior = np.asarray(close[index-127:index], dtype=float)
    if prior.shape[0] != 127 or not np.isfinite(prior).all() or (prior <= 0).any():
        raise ValueError('Unsupported adjusted history')
    momentum = prior[-1] / prior[0] - 1
    daily = prior[-63:] / prior[-64:-1] - 1
    volatility = daily.std(axis=0, ddof=1) * math.sqrt(252)
    return momentum, volatility


def conflicts(symbol, selected, edges):
    return any(frozenset((symbol, other)) in edges for other in selected)


def build_targets(symbols, momentum, volatility, admitted, mapping, ids, protocol, arm):
    if arm not in protocol['arms']:
        raise ValueError('Unregistered arm')
    if not set(admitted) <= set(symbols):
        raise ValueError('Unknown admitted instrument')
    raw = dict(zip(symbols, momentum, strict=True))
    vols = dict(zip(symbols, volatility, strict=True))
    eligible = [s for s in admitted if np.isfinite(raw[s]) and raw[s] > 0
                and np.isfinite(vols[s]) and vols[s] > 0]
    scores = {s: float(raw[s] / vols[s] if arm.endswith('_risk') else raw[s]) for s in eligible}
    edges = {frozenset((p, c)) for p, cs in protocol['overlap_parents'].items() for c in cs}

    def ranked_members(candidates, held=(), limit=2):
        picked = []
        for symbol in sorted(candidates, key=lambda s: (-scores[s], ids[s])):
            if not conflicts(symbol, [*held, *picked], edges):
                picked.append(symbol)
            if len(picked) == limit:
                break
        return picked

    selected, classes, budgets = [], [], []
    if arm.startswith('pooled_'):
        selected = ranked_members(eligible, limit=6)
        budgets.append((selected, D('.98') * D(len(selected)) / 6))
    else:
        available = {mapping[s] for s in eligible}
        while available and len(classes) < 3:
            choices = []
            for group in sorted(available):
                members = ranked_members([s for s in eligible if mapping[s] == group], selected)
                if members:
                    score = sum(scores[s] for s in members) / len(members)
                    choices.append((-score, group, members))
            if not choices:
                break
            negative_score, group, members = min(choices)
            classes.append(dict(group=group, members=members, score=-negative_score))
            budgets.append((members, D('.98') / 3 * D(len(members)) / 2))
            selected.extend(members)
            available.remove(group)
    weights = {s: D(0) for s in symbols}
    for members, budget in budgets:
        inverse = {s: D(1) / D(str(vols[s])) for s in members}
        total = sum(inverse.values())
        for s in members:
            weights[s] = min(D('.45'), budget * inverse[s] / total)
    # All unused budgets and final cap reductions remain literal cash.
    if sum(weights.values()) > D('.98') + D('1e-24'):
        raise ValueError('Cash reserve violated')
    return weights, dict(selected=selected, classes=classes, eligible=sorted(eligible),
                         scores=scores, gross=float(sum(weights.values())))


def turnover(decisions, start, end):
    """Security-target changes; cash belongs to the trigger, never a fee leg."""
    previous, moved, per_symbol, events = {}, 0., {}, 0
    for day, row in decisions.items():
        current = {t['symbol']: float(t['target_weight']) for t in row['targets']}
        if start <= day <= end:
            events += 1
            for symbol in current.keys() | previous.keys():
                value = abs(current.get(symbol, 0.) - previous.get(symbol, 0.))
                per_symbol[symbol] = per_symbol.get(symbol, 0.) + value
                moved += value
        previous = current
        if day > end:
            break
    years = (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25
    if years <= 0:
        raise ValueError('Invalid turnover window')
    return dict(annual_turnover=moved/years, total_target_change=moved, years=years,
                adoption_events=events, by_symbol={s: v/years for s, v in per_symbol.items()})


def ic_rows(tape, admitted_by_day, monthly, days, opens, symbols, start, end):
    rows = []
    indices = {d: i for i, d in enumerate(days)}
    columns = {s: i for i, s in enumerate(symbols)}
    for day in monthly:
        i = indices[day]
        if day < start or day > end or i+21 >= len(days) or days[i+21] > end:
            continue
        universe = admitted_by_day[day]
        weights = {t['symbol']: float(t['target_weight']) for t in tape[day]['targets']}
        x = [weights[s] for s in universe]
        y = [float(opens[i+21, columns[s]]/opens[i, columns[s]]-1) for s in universe]
        valid = len(x) >= 4 and np.ptp(x) > 0 and np.ptp(y) > 0
        rows.append(dict(day=day, label_end=days[i+21], count=len(x),
                         ic=float(spearmanr(x, y).statistic) if valid else None,
                         unavailable_reason=None if valid else 'Insufficient or constant cross-section',
                         forward_returns=y if valid else []))
    return rows


def evaluate_gate(costs, observations):
    from systematic_trading.research.turnover_gate import legacy_screen as screen
    values = [r['ic'] for r in observations if r['ic'] is not None]
    returns = [v for r in observations for v in r['forward_returns']]
    if len(values) < 12 or len(returns) < 2:
        return dict(status='insufficient', annual_cost_bps=costs['annual_turnover']*5,
                    candidate_ic=None, ic_margin=None,
                    reasons=['Fewer than twelve nondegenerate monthly mapping ICs; no default IC substitution'])
    return screen(costs['annual_turnover'], sigma=float(np.std(returns, ddof=1)),
                  candidate_ic=float(np.mean(values)))


def bootstrap(interval_rows, protocol):
    """Paired month draws for all arms, with conservative family intervals."""
    keys = sorted(interval_rows)
    dates = sorted({r['day'] for rows in interval_rows.values() for r in rows})
    if not dates:
        raise ValueError('No monthly observations')
    table = []
    for key in keys:
        observations = {r['day']: r['ic'] for r in interval_rows[key]}
        table.append([np.nan if observations.get(d) is None else observations[d] for d in dates])
    table = np.asarray(table).T
    out = {}
    spec = protocol['uncertainty']
    for block in spec['mean_block_months']:
        rng = np.random.default_rng(spec['seed'] + block)
        indices = rng.integers(0, len(dates), size=(spec['replications'], len(dates)))
        restart = rng.random(indices.shape) < 1/block
        for t in range(1, len(dates)):
            indices[:, t] = np.where(restart[:, t], indices[:, t], (indices[:, t-1]+1) % len(dates))
        for j, key in enumerate(keys):
            samples = table[indices, j]
            counts = np.isfinite(samples).sum(axis=1)
            means = np.nansum(samples, axis=1)[counts > 0] / counts[counts > 0]
            tails = .05 / (2 * len(keys))
            out.setdefault(key, {})[str(block)] = dict(
                individual_95=np.quantile(means, [.025, .975]).tolist() if len(means) else None,
                family_95_bonferroni=np.quantile(means, [tails, 1-tails]).tolist() if len(means) else None,
                valid_draws=len(means))
    return out


def run(root):
    verify(root, 'input_manifest.json')
    if (root / 'result_manifest.json').exists():
        verify(root, 'result_manifest.json')
        print('Verified completed screen; no overwrite', flush=True)
        return
    from systematic_trading.research.etf_expansion import admission_for_day
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.research.target_change_rebalance import adoption_schedule
    p, pool, funds = read(root/'protocol.json'), read(root/'pool.json'), read(root/'candidates.json')
    symbols, days = sorted(pool['bars']), pool['calendar']
    mapping = class_map(p, [f['symbol'] for f in funds])
    ids = {f['symbol']: f['candidate_id'] for f in funds}
    closes = np.array([[float(pool['bars'][s][i]['close']) for s in symbols] for i in range(len(days))])
    opens = np.array([[float(pool['bars'][s][i]['open']) for s in symbols] for i in range(len(days))])
    monthly = decision_sessions(days, p['start'], 'monthly')
    tapes = {a: {} for a in p['arms']}
    admission, admissions, unavailable = {}, {}, {}
    for i, day in enumerate(days):
        if day < p['start']:
            continue
        observed = admission_for_day(pool['records'], funds, day)
        admission[day] = observed
        admissions[day] = observed['admitted']
        momentum, volatility = features(closes, i)
        unavailable[day] = [s for j, s in enumerate(symbols) if not np.isfinite(volatility[j]) or volatility[j] <= 0]
        for arm in p['arms']:
            weights, detail = build_targets(symbols, momentum, volatility, admissions[day], mapping, ids, p, arm)
            tapes[arm][day] = dict(signal_session=day, known_through=days[i-1],
                targets=[dict(symbol=s, target_weight=str(weights[s])) for s in symbols], detail=detail)
        if len(admission) % 250 == 0:
            print('Daily target/admission sessions', len(admission), flush=True)
    write(root/'admissions.json', admission)
    write(root/'unavailable_volatility.json', unavailable)
    intervals, analysis, files = {}, {}, [root/'admissions.json', root/'unavailable_volatility.json']
    years = [(str(y), max(p['start'], f'{y}-01-01'), min(p['through'], f'{y}-12-31'))
             for y in range(2021, 2027)]
    windows = [('calibration', p['start'], p['calibration_end']),
               ('later', p['later_start'], p['through']), *years]
    for arm, tape in tapes.items():
        path = root/'targets'/(arm+'.json')
        write(path, tape)
        files.append(path)
        for policy in p['policies']:
            key = arm+'-'+policy
            decisions, ledger = adoption_schedule(tape, monthly, policy)
            weights = {}
            daily_weights = []
            for day in tape:
                if day in decisions:
                    weights = {t['symbol']: float(t['target_weight']) for t in decisions[day]['targets']}
                daily_weights.append(dict(day=day, weights=weights))
            item = dict(arm=arm, policy=policy, windows={})
            for label, start, end in windows:
                costs = turnover(decisions, start, end)
                obs = ic_rows(tape, admissions, monthly, days, opens, symbols, start, end)
                values = [r['ic'] for r in obs if r['ic'] is not None]
                if label == 'calibration':
                    item['gate'] = evaluate_gate(costs, obs)
                    intervals[key] = obs
                wrows = [r['weights'] for r in daily_weights if start <= r['day'] <= end]
                gross = [sum(r.values()) for r in wrows]
                mean_gross = float(np.mean(gross))
                item['windows'][label] = dict(**costs, annual_cost_bps=costs['annual_turnover']*5,
                    ic=float(np.mean(values)) if values else None, ic_months=len(values),
                    missing_ic_months=len(obs)-len(values), mean_adopted_gross=mean_gross,
                    annual_cost_at_98pct_gross_diagnostic=costs['annual_turnover']*5*.98/mean_gross if mean_gross else None,
                    mean_adopted_bill_weight=float(np.mean([r.get('BIL', 0.) for r in wrows])),
                    mean_selected=float(np.mean([sum(v > 0 for v in r.values()) for r in wrows])),
                    mean_effective_holdings=float(np.mean([sum(r.values())**2/sum(v*v for v in r.values())
                                                          if sum(r.values()) else 0 for r in wrows])),
                    max_target_weight=max(max(r.values()) for r in wrows),
                    observations=obs,
                    constituents={s: dict(mean_adopted_weight=float(np.mean([r[s] for r in wrows])),
                        selected_sessions=sum(r[s] > 0 for r in wrows),
                        annual_target_turnover=costs['by_symbol'].get(s, 0.), group=mapping[s]) for s in symbols})
            item['adoption_events'] = len(decisions)
            item['intramonth_events'] = sum('threshold' in r['reasons'] and 'monthly' not in r['reasons'] for r in ledger)
            path = root/'adoptions'/(key+'.json')
            write(path, ledger)
            files.append(path)
            analysis[key] = item
            print(key, item['gate']['status'], round(item['gate']['annual_cost_bps'], 3), flush=True)
    uncertainty = bootstrap(intervals, p)
    for key, item in analysis.items():
        item['calibration_ic_intervals'] = uncertainty[key]
    result = dict(protocol_sha256=digest(root/'protocol.json'), input_manifest_sha256=digest(root/'input_manifest.json'),
        published_batch=pool['provenance']['batch'], candidates=52, supported=len(symbols),
        exclusions=pool['exclusions'], daily_sessions=len(admission), monthly_sessions=len(monthly),
        supported_classes=len({mapping[s] for s in symbols}), results=analysis,
        replay_candidates=[key for key, item in analysis.items() if item['gate']['status'] == 'pass'],
        interpretation='Screen only; target turnover and IC are not realized costs or performance. No strategy acceptance.',
        monthly_ic_shared_across_policies='All policies adopt at monthly anchors; IC uses that common clock. Timing changes costs here, not monthly information observations.')
    write(root/'analysis.json', result)
    files.append(root/'analysis.json')
    verify(root, 'input_manifest.json')
    manifest(root, 'result_manifest.json', files)
    print(json.dumps(dict(stage='complete', replay_candidates=result['replay_candidates'],
                         analysis_sha256=digest(root/'analysis.json'))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'run', 'verify'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.stage == 'prepare':
        prepare(root)
    elif args.stage == 'verify':
        verify(root, 'input_manifest.json')
        verify(root, 'result_manifest.json')
        print('Input, source and result hashes verified')
    else:
        verify(root, 'input_manifest.json')
        runner = root/'runner.py'
        if Path(__file__).resolve() != runner:
            raise SystemExit(subprocess.call([sys.executable, '-B', str(runner), 'run', '--root', str(root)],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0))
        # Frozen application primitives take precedence over the editable checkout.
        sys.path.insert(0, str(root/'source'))
        run(root)


if __name__ == '__main__':
    main()
