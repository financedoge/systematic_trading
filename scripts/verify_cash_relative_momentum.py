"""Independent target, trigger, gate and forward-diagnostic acceptance."""
import argparse
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from run_class_volatility_screen import read, write, digest, verify


def close_enough(a, b, tolerance=1e-12):
    if a is None or b is None:
        assert a is b
    else:
        assert abs(a-b) < tolerance, (a, b)


def correlation(x, y, minimum=4):
    if len(x) < minimum or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def expected_targets(raw, vol, admitted, ids, p, arm):
    eligible = {s for s in admitted if s != 'BIL' and raw[s] > 0 and vol[s] > 0}
    score = {s: (raw[s]-raw['BIL'] if '_cash_relative_' in arm else raw[s])/vol[s] for s in eligible}
    score = {s: x for s, x in score.items() if x > 0}
    overlaps = {frozenset([s, c]) for s, children in p['overlap_parents'].items() for c in children}
    groups = {s: g for g, members in p['classes'].items() for s in members}
    held, budgets, selected_groups = [], [], set()

    def pick(names, n):
        found = []
        for s in sorted(names, key=lambda s: (-score[s], ids[s])):
            if not any(frozenset([s, other]) in overlaps for other in held+found):
                found.append(s)
                if len(found) == n:
                    break
        return found

    if arm.startswith('pooled'):
        held = pick(score, 6)
        budgets = [(held, .98*len(held)/6)]
    else:
        for _ in range(3):
            candidates = []
            for group in sorted(set(groups.values())-selected_groups):
                chosen = pick([s for s in score if groups[s] == group], 2)
                if chosen:
                    candidates.append((-float(np.mean([score[s] for s in chosen])), group, chosen))
            if not candidates:
                break
            _, group, chosen = sorted(candidates)[0]
            held += chosen
            selected_groups.add(group)
            budgets.append((chosen, .98/3*len(chosen)/2))
    weights = {s: 0. for s in raw}
    for members, budget in budgets:
        if members:
            inverse = np.array([1/vol[s] for s in members])
            for s, w in zip(members, budget*inverse/inverse.sum(), strict=True):
                weights[s] = min(.45, float(w))
    return weights, score


def check(root):
    for name in ('input_manifest.json', 'result_manifest.json', 'diagnostic_manifest.json'):
        verify(root, name)
    p, pool = read(root/'protocol.json'), read(root/'pool.json')
    result, detail = read(root/'analysis.json'), read(root/'diagnostics.json')
    admissions = read(root/'admissions.json')
    symbols, days = sorted(pool['bars']), pool['calendar']
    index = {d: i for i, d in enumerate(days)}
    column = {s: i for i, s in enumerate(symbols)}
    opens = np.array([[float(pool['bars'][s][i]['open']) for s in symbols] for i in range(len(days))])
    closes = np.array([[float(pool['bars'][s][i]['close']) for s in symbols] for i in range(len(days))])
    ids = {f['symbol']: f['candidate_id'] for f in read(root/'candidates.json')}
    target_count = score_count = adoption_count = window_count = forward_count = peer_count = pair_count = 0
    tapes = {}
    for arm in p['arms']:
        tape = read(root/'targets'/(arm+'.json'))
        tapes[arm] = tape
        for day, row in tape.items():
            i = index[day]
            raw = dict(zip(symbols, closes[i-1]/closes[i-127]-1, strict=True))
            changes = np.diff(closes[i-64:i], axis=0)/closes[i-64:i-1]
            vol = dict(zip(symbols, np.sqrt(((changes-changes.mean(axis=0))**2).sum(axis=0)*252/62), strict=True))
            expected, scores = expected_targets(raw, vol, admissions[day]['admitted'], ids, p, arm)
            actual = {r['symbol']: float(r['target_weight']) for r in row['targets']}
            assert row['known_through'] == days[i-1] and row['signal_session'] == day
            assert set(actual) == set(symbols) and actual['BIL'] == 0
            for s in symbols:
                close_enough(actual[s], expected[s])
            assert set(scores) == set(row['detail']['scores'])
            for s in scores:
                close_enough(scores[s], row['detail']['scores'][s], 1e-10)
                score_count += 1
            target_count += 1
    for key, r in result['results'].items():
        tape = tapes[r['arm']]
        events = read(root/'adoptions'/(key+'.json'))
        assert [e['signal_session'] for e in events] == list(tape)
        previous, month, adoption_days, movements = None, None, [], []
        for e in events:
            day = e['signal_session']
            w = {t['symbol']: D(t['target_weight']) for t in tape[day]['targets']}
            w['CASH'] = 1-sum(w.values())
            gap = sum(abs(w[s]-previous[s]) for s in w) if previous else None
            triggered = previous is None or month != day[:7] or (
                r['policy'] != 'monthly' and gap > D(r['policy']))
            assert e['adopted'] == triggered
            if gap is not None:
                assert abs(D(e['distance'])-gap) < D('1e-24')
                if r['policy'] != 'monthly':
                    assert abs(gap-D(r['policy'])) > D('1e-20')
            if triggered:
                adoption_days.append(day)
                movements.append([abs(float(w[s])-float(previous[s])) if previous else float(w[s]) for s in symbols])
                previous = w
            month = day[:7]
        movements = np.asarray(movements)
        for label, window in r['windows'].items():
            start, end = ((p['start'], p['calibration_end']) if label == 'calibration' else
                          (p['later_start'], p['through']) if label == 'later' else
                          (max(p['start'], label+'-01-01'), min(p['through'], label+'-12-31')))
            years = (date.fromisoformat(end)-date.fromisoformat(start)).days/365.25
            selected = [i for i, d in enumerate(adoption_days) if start <= d <= end]
            totals = movements[selected].sum(axis=0)/years
            close_enough(float(totals.sum()), window['annual_turnover'], 1e-10)
            for j, s in enumerate(symbols):
                close_enough(float(totals[j]), window['constituents'][s]['annual_target_turnover'], 1e-10)
            window_count += 1
        cal = r['windows']['calibration']
        ic = np.mean([o['ic'] for o in cal['observations'] if o['ic'] is not None])
        dispersion = np.std([y for o in cal['observations'] for y in o['forward_returns']], ddof=1)
        ratio = ic/(cal['annual_turnover']*.0005*21/252/dispersion)
        close_enough(float(ratio), r['gate']['ic_margin'])
        status = 'pass' if cal['annual_turnover']*5 <= 44 and ic > 0 and ratio >= 3 else 'reject'
        assert status == r['gate']['status']
        adoption_count += len(adoption_days)
    payoff = {}
    for window, horizons in detail['diagnostics'].items():
        start, end = (p['start'], p['calibration_end']) if window == 'calibration' else (p['later_start'], p['through'])
        for horizon, arms in horizons.items():
            for arm, rows in arms.items():
                for row in rows:
                    day, i = row['day'], index[row['day']]
                    assert start <= day <= days[i+int(horizon)] == row['label_end'] <= end
                    returns = opens[i+int(horizon)]/opens[i]-1
                    excess = returns-returns[column['BIL']]
                    w = {t['symbol']: float(t['target_weight']) for t in tapes[arm][day]['targets']}
                    universe = admissions[day]['admitted']
                    raw_ic = correlation([w[s] for s in universe], [returns[column[s]] for s in universe])
                    excess_ic = correlation([w[s] for s in universe], [excess[column[s]] for s in universe])
                    close_enough(raw_ic, row['mapping_ic'])
                    close_enough(excess_ic, row['excess_mapping_ic'])
                    value = float(np.dot([w[s] for s in symbols], excess))
                    close_enough(value, row['static_excess_contribution'])
                    payoff[window, horizon, arm, day] = value
                    for group, group_row in row['class_conditioning'].items():
                        members = [s for s in p['classes'][group] if s in universe and s != 'BIL']
                        expected = correlation([w[s] for s in members], [returns[column[s]] for s in members], 3)
                        close_enough(expected, group_row['ic'])
                        assert group_row['count'] == len(members)
                        peer_count += 1
                    forward_count += 1
    for window, contrasts in detail['paired_static_excess_contribution'].items():
        for key, rows in contrasts.items():
            shape, horizon = key.split('-')
            for row in rows:
                primary = payoff[window, horizon, shape+'_cash_relative_risk', row['day']]
                control = payoff[window, horizon, shape+'_remove_bill_risk', row['day']]
                close_enough(primary-control, row['value'])
                pair_count += 1
    assert target_count == 5800
    return dict(analysis_sha256=digest(root/'analysis.json'), diagnostics_sha256=digest(root/'diagnostics.json'),
        input_manifest_sha256=digest(root/'input_manifest.json'),
        verified_daily_targets=target_count, verified_scores=score_count, verified_policies=len(result['results']),
        verified_adoptions=adoption_count, verified_turnover_windows=window_count,
        verified_forward_rows=forward_count, verified_class_rows=peer_count, verified_paired_payoffs=pair_count,
        parent_targets_reproduced=read(root/'parent_reproduction.json'),
        gate_passes=sum(r['gate']['status'] == 'pass' for r in result['results'].values()),
        verifier_sha256=digest(Path(__file__)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('var/research/cash-relative-momentum-20261017-v1'))
    args = parser.parse_args()
    receipt = check(args.root)
    write(args.root/'acceptance.json', receipt)
    print(json.dumps(receipt, indent=2))
