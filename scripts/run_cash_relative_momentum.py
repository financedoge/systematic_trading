"""Frozen cash-relative hypothesis composed with the prior verified screen.

Only the target-builder callback changes. The parent feature, admission, adoption,
cost and mapping-IC primitives remain byte-identical and are pinned in this study.
"""
import argparse
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy.stats import spearmanr

from run_class_volatility_screen import digest, read, verify, write, manifest

ROOT = Path('var/research/cash-relative-momentum-20261017-v1')
REGISTRATION = Path('research/cash-relative-momentum-20261017-v1/registration.json')


def helper(root):
    spec = importlib.util.spec_from_file_location('frozen_construction_screen', root/'parent_screen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_targets(original, symbols, momentum, volatility, admitted, mapping, ids, protocol, arm):
    if arm not in protocol['arms']:
        raise ValueError('Unregistered cash-relative arm')
    if 'BIL' not in symbols:
        raise ValueError('Published BIL reference required')
    values = np.asarray(momentum, dtype=float)
    bill = values[symbols.index('BIL')]
    if not np.isfinite(bill):
        raise ValueError('Unsupported BIL reference')
    admissible = [s for s in admitted if s != 'BIL' and values[symbols.index(s)] > 0]
    adjusted = values-bill if '_cash_relative_' in arm else values
    weights, detail = original(symbols, adjusted, volatility, admissible, mapping, ids, protocol, arm)
    detail.update(reference_symbol='BIL', reference_momentum=float(bill),
                  raw_momentum={s: float(v) for s, v in zip(symbols, values, strict=True)},
                  momentum_basis='excess_over_BIL' if '_cash_relative_' in arm else 'raw_remove_BIL')
    assert weights['BIL'] == 0
    return weights, detail


def prospective_calendar():
    from systematic_trading.live.trading_calendar import is_us_trading_day
    day, days = date(2026, 10, 19), []
    while len(days) < 147:
        if is_us_trading_day(day):
            days.append(str(day))
        day += timedelta(days=1)
    return dict(sessions=days, first=days[0], last_signal=days[125], last_label=days[146])


def prepare(root):
    if root.exists():
        raise FileExistsError('Preserve the frozen study')
    r = read(REGISTRATION)
    parent = Path(r['parent'])
    for file, key in [('protocol.json', 'parent_protocol_sha256'),
                      ('input_manifest.json', 'parent_input_manifest_sha256'),
                      ('analysis.json', 'parent_analysis_sha256')]:
        if digest(parent/file) != r[key]:
            raise ValueError('Registered parent changed: '+file)
    verify(parent, 'input_manifest.json')
    verify(parent, 'result_manifest.json')
    # Use the parent's pinned application reader to reproduce the publication.
    sys.path.insert(0, str((parent/'source').resolve()))
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.etf_expansion import load_published_pool
    pin = read(parent/'price_pin.json')
    reader = GovernedInputs(Path(pin['root']), pin['batch'])
    rebuilt = load_published_pool(reader, read(parent/'candidates.json'), through=pin['through'])
    if rebuilt != read(parent/'pool.json'):
        raise ValueError('Published pool changed')
    schedule = prospective_calendar()
    if (schedule['first'] != r['prospective']['earliest_signal_session']
            or schedule['last_signal'] != r['prospective']['planned_last_signal_session']
            or schedule['last_label'] != r['prospective']['planned_last_21_session_label']):
        raise ValueError('Prospective calendar differs from registration')
    p = read(parent/'protocol.json')
    p.update(version=r['version'], registered_on=r['registered_on'], parent=str(parent),
             question=r['question'], arms=r['arms'], policies=r['policies'],
             score=r['score'], pretest={**p['pretest'], **r['pretest']},
             limitations=r['limitations'], registration=r)
    p['uncertainty']['seed'] = 20261017
    p['construction']['downstream'] = 'Inherited price-only construction; only registered score/gate and BIL role change'
    root.mkdir(parents=True)
    for name in ('pool.json', 'candidates.json', 'price_pin.json'):
        shutil.copyfile(parent/name, root/name)
    shutil.copytree(parent/'source', root/'source')
    shutil.copyfile(parent/'runner.py', root/'parent_screen.py')
    shutil.copyfile(parent/'runner.py', root/'run_class_volatility_screen.py')
    shutil.copyfile(__file__, root/'runner.py')
    shutil.copyfile(REGISTRATION, root/'registration.json')
    shutil.copyfile(parent/'analysis.json', root/'parent_analysis.json')
    shutil.copyfile(parent/'protocol.json', root/'parent_protocol.json')
    for arm in ('pooled_risk', 'class_risk'):
        dest = root/'parent_targets'/(arm+'.json')
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(parent/'targets'/(arm+'.json'), dest)
    write(root/'protocol.json', p)
    write(root/'prospective_calendar.json', schedule)
    write(root/'publication_receipt.json', dict(batch=pin['batch'], verified_files=reader.used,
        reconstructed_parent_pool=True, parent_result_manifest_sha256=digest(parent/'result_manifest.json'),
        parent_helper_sha256=digest(parent/'runner.py')))
    manifest(root, 'input_manifest.json', [f for f in root.rglob('*') if f.is_file()])
    print(json.dumps(dict(stage='frozen', protocol_sha256=digest(root/'protocol.json'),
                         registration_sha256=digest(root/'registration.json'),
                         input_manifest_sha256=digest(root/'input_manifest.json'))), flush=True)


def rank_ic(x, y, minimum=4):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < minimum or not np.isfinite(x).all() or not np.isfinite(y).all() or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(spearmanr(x, y).statistic)


def forward_diagnostics(tapes, pool, admission, monthly, protocol):
    symbols, days = sorted(pool['bars']), pool['calendar']
    columns = {s: i for i, s in enumerate(symbols)}
    indices = {d: i for i, d in enumerate(days)}
    opens = np.array([[float(pool['bars'][s][i]['open']) for s in symbols] for i in range(len(days))])
    result, pairs = {}, {}
    for label, start, end in [('calibration', protocol['start'], protocol['calibration_end']),
                              ('later', protocol['later_start'], protocol['through'])]:
        result[label], pairs[label] = {}, {}
        for horizon in protocol['registration']['diagnostics']['horizons_sessions']:
            rows, paired = {arm: [] for arm in tapes}, {shape: [] for shape in ('pooled', 'class')}
            for day in monthly:
                i = indices[day]
                if day < start or day > end or i+horizon >= len(days) or days[i+horizon] > end:
                    continue
                returns = opens[i+horizon]/opens[i]-1
                bill = float(returns[columns['BIL']])
                excess = returns-bill
                universe = admission[day]['admitted']
                payoffs = {}
                for arm, tape in tapes.items():
                    target = tape[day]
                    w = {t['symbol']: float(t['target_weight']) for t in target['targets']}
                    score = target['detail']['scores']
                    raw_ic = rank_ic([w[s] for s in universe], [returns[columns[s]] for s in universe])
                    excess_ic = rank_ic([w[s] for s in universe], [excess[columns[s]] for s in universe])
                    if raw_ic is not None and (excess_ic is None or abs(raw_ic-excess_ic) > 1e-12):
                        raise ValueError('Common-cash rank invariance failed')
                    signal_ic = rank_ic(list(score.values()), [returns[columns[s]] for s in score])
                    class_rows = {}
                    for group, members in protocol['classes'].items():
                        names = [s for s in members if s in universe and s != 'BIL']
                        ic = rank_ic([w[s] for s in names], [returns[columns[s]] for s in names], minimum=3)
                        class_rows[group] = dict(count=len(names), ic=ic,
                            reason=None if ic is not None else 'Fewer than three names or constant cross-section')
                    payoff = sum(w[s]*float(excess[columns[s]]) for s in symbols)
                    payoffs[arm] = payoff
                    rows[arm].append(dict(day=day, label_end=days[i+horizon], mapping_ic=raw_ic,
                        excess_mapping_ic=excess_ic, signal_ic=signal_ic, bill_return=bill,
                        static_excess_contribution=payoff, class_conditioning=class_rows))
                for shape in paired:
                    primary = shape+'_cash_relative_risk'
                    control = shape+'_remove_bill_risk'
                    paired[shape].append(dict(day=day, label_end=days[i+horizon],
                        value=payoffs[primary]-payoffs[control]))
            result[label][str(horizon)] = rows
            for shape in paired:
                pairs[label][shape+'-'+str(horizon)] = paired[shape]
    return dict(diagnostics=result, paired_static_excess_contribution=pairs)


def extras(root, base):
    if (root/'diagnostic_manifest.json').exists():
        verify(root, 'diagnostic_manifest.json')
        return
    p, pool = read(root/'protocol.json'), read(root/'pool.json')
    admission = read(root/'admissions.json')
    tapes = {arm: read(root/'targets'/(arm+'.json')) for arm in p['arms']}
    from systematic_trading.research.momentum_signals import decision_sessions
    monthly = decision_sessions(pool['calendar'], p['start'], 'monthly')
    detailed = forward_diagnostics(tapes, pool, admission, monthly, p)
    uncertainty = {}
    for window, contrasts in detailed['paired_static_excess_contribution'].items():
        data = {key: [dict(day=r['day'], ic=r['value']) for r in rows] for key, rows in contrasts.items()}
        uncertainty[window] = base.bootstrap(data, p)
    detailed['paired_intervals'] = uncertainty
    write(root/'diagnostics.json', detailed)
    # Recompute every normalized parent target through the original primitive.
    ids = {f['symbol']: f['candidate_id'] for f in read(root/'candidates.json')}
    original_p = read(root/'registration.json')
    parent_p = read(root/'parent_protocol.json')
    if digest(root/'parent_protocol.json') != original_p['parent_protocol_sha256']:
        raise ValueError('Parent protocol changed')
    mapping = base.class_map(parent_p, ids)
    symbols, days = sorted(pool['bars']), pool['calendar']
    closes = np.array([[float(pool['bars'][s][i]['close']) for s in symbols] for i in range(len(days))])
    counts = {}
    for arm in ('pooled_risk', 'class_risk'):
        old = read(root/'parent_targets'/(arm+'.json'))
        count = 0
        for i, day in enumerate(days):
            if day not in old:
                continue
            m, v = base.features(closes, i)
            weights, _ = base.build_targets(symbols, m, v, admission[day]['admitted'], mapping, ids, parent_p, arm)
            if weights != {t['symbol']: base.D(t['target_weight']) for t in old[day]['targets']}:
                raise ValueError('Normalized parent target failed reproduction')
            count += 1
        counts[arm] = count
    write(root/'parent_reproduction.json', dict(targets=counts, exact=True))
    verify(root, 'input_manifest.json')
    manifest(root, 'diagnostic_manifest.json', [root/'diagnostics.json', root/'parent_reproduction.json'])


def run(root):
    verify(root, 'input_manifest.json')
    base = helper(root)
    original = base.build_targets
    # A finite, explicit target-builder callback. No application class is patched.
    base.build_targets = lambda *args: candidate_targets(original, *args)
    try:
        base.run(root)
    finally:
        base.build_targets = original
    extras(root, base)
    print('Cash-relative screen and fixed diagnostic family complete', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'run', 'verify'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.stage == 'prepare':
        prepare(root)
    elif args.stage == 'verify':
        for filename in ('input_manifest.json', 'result_manifest.json', 'diagnostic_manifest.json'):
            verify(root, filename)
        print('All input/source/result/diagnostic hashes verified')
    else:
        verify(root, 'input_manifest.json')
        if Path(__file__).resolve() != root/'runner.py':
            raise SystemExit(subprocess.call([sys.executable, '-B', str(root/'runner.py'), 'run', '--root', str(root)],
                stdout=sys.stdout, stderr=sys.stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0))
        sys.path.insert(0, str(root/'source'))
        run(root)
