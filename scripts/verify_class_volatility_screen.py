"""Independent arithmetic/causality acceptance for the finite construction screen."""
from collections import Counter
from datetime import date
from decimal import Decimal as D
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from run_class_volatility_screen import digest, read, verify, write


def check(root):
    verify(root, 'input_manifest.json')
    verify(root, 'result_manifest.json')
    p, result = read(root/'protocol.json'), read(root/'analysis.json')
    pool = read(root/'pool.json')
    symbols = sorted(pool['bars'])
    days = pool['calendar']
    indices = {d: i for i, d in enumerate(days)}
    close = np.array([[float(pool['bars'][s][i]['close']) for s in symbols] for i in range(len(days))])
    opens = np.array([[float(pool['bars'][s][i]['open']) for s in symbols] for i in range(len(days))])
    admissions = read(root/'admissions.json')
    group_of = {s: g for g, members in p['classes'].items() for s in members}
    metadata = {f['symbol']: f for f in read(root/'candidates.json')}
    conflict_pairs = [(s, c) for s, children in p['overlap_parents'].items() for c in children]
    target_count = 0
    score_count = 0
    annual_count = 0
    observation_count = 0
    tapes = {}
    for arm in p['arms']:
        tape = read(root/'targets'/(arm+'.json'))
        tapes[arm] = tape
        for day, row in tape.items():
            i = indices[day]
            assert row['known_through'] == days[i-1] and row['signal_session'] == day
            weights = {r['symbol']: D(r['target_weight']) for r in row['targets']}
            assert set(weights) == set(symbols)
            assert all(D(0) <= w <= D('.45') for w in weights.values())
            assert sum(weights.values()) <= D('.98') + D('1e-24')
            held = {s for s, w in weights.items() if w > 0}
            assert held == set(row['detail']['selected']) and len(held) <= 6
            assert held <= set(admissions[day]['admitted'])
            assert all(not ({a, b} <= held) for a, b in conflict_pairs)
            assert len({metadata[s]['duplicate_review_group'] for s in held}) == len(held)
            period_return = close[i-1]/close[i-127]-1
            changes = np.diff(close[i-64:i], axis=0)/close[i-64:i-1]
            vol = np.sqrt(np.sum((changes-changes.mean(axis=0))**2, axis=0)/62*252)
            scores = {}
            for j, s in enumerate(symbols):
                if s in admissions[day]['admitted'] and period_return[j] > 0 and vol[j] > 0:
                    scores[s] = period_return[j]/vol[j] if arm.endswith('_risk') else period_return[j]
            assert set(scores) == set(row['detail']['scores'])
            for s, score in scores.items():
                assert abs(score-row['detail']['scores'][s]) < 1e-10
                score_count += 1
            assert held <= set(scores)
            if arm.startswith('class_'):
                assert len(row['detail']['classes']) <= 3
                budgets = []
                for group in row['detail']['classes']:
                    members = group['members']
                    assert 1 <= len(members) <= 2
                    assert all(group_of[s] == group['group'] for s in members)
                    assert abs(group['score']-np.mean([scores[s] for s in members])) < 1e-10
                    budgets.append((members, .98/3*len(members)/2))
            else:
                budgets = [(sorted(held), .98*len(held)/6)]
            for members, budget in budgets:
                inv = {s: 1/vol[symbols.index(s)] for s in members}
                for s in members:
                    expected = min(.45, budget*inv[s]/sum(inv.values()))
                    assert abs(float(weights[s])-expected) < 1e-12
            target_count += 1
    policy_count, decisions_count = 0, 0
    for key, item in result['results'].items():
        tape = tapes[item['arm']]
        ledger = read(root/'adoptions'/(key+'.json'))
        assert [r['signal_session'] for r in ledger] == list(tape)
        previous, previous_month = None, None
        dates, movement = [], []
        for event in ledger:
            day = event['signal_session']
            current = {t['symbol']: D(t['target_weight']) for t in tape[day]['targets']}
            current['CASH'] = 1-sum(current.values())
            monthly = day[:7] != previous_month
            gap = sum(abs(current[s]-previous[s]) for s in current) if previous else None
            threshold = item['policy'] != 'monthly' and gap is not None and gap > D(item['policy'])
            adopt = previous is None or monthly or threshold
            assert event['adopted'] == adopt
            # The app sums over a set; Decimal summation order can differ in the
            # last context digit. Verify numerical equality and exclude any
            # threshold close enough for that rounding to affect adoption.
            assert (event['distance'] is None and gap is None) or abs(D(event['distance'])-gap) < D('1e-24')
            if item['policy'] != 'monthly' and gap is not None:
                assert abs(gap-D(item['policy'])) > D('1e-20')
            assert event['latest'] == {s: str(w) for s, w in current.items()}
            assert event['anchor_before'] == (None if previous is None else {s: str(w) for s, w in previous.items()})
            if adopt:
                dates.append(day)
                movement.append([abs(float(current[s])-float(previous[s]) if previous else float(current[s])) for s in symbols])
                previous = current
            previous_month = day[:7]
        movement = np.asarray(movement)
        for label, window in item['windows'].items():
            if label == 'calibration':
                start, end = p['start'], p['calibration_end']
            elif label == 'later':
                start, end = p['later_start'], p['through']
            else:
                start, end = max(p['start'], label+'-01-01'), min(p['through'], label+'-12-31')
            selected = [j for j, d in enumerate(dates) if start <= d <= end]
            years = (date.fromisoformat(end)-date.fromisoformat(start)).days/365.25
            totals = movement[selected].sum(axis=0)/years
            assert abs(float(totals.sum())-window['annual_turnover']) < 1e-10
            assert abs(sum(v['annual_target_turnover'] for v in window['constituents'].values())-window['annual_turnover']) < 1e-10
            for j, s in enumerate(symbols):
                assert abs(totals[j]-window['constituents'][s]['annual_target_turnover']) < 1e-10
            for observation in window['observations']:
                d = observation['day']
                i = indices[d]
                assert days[i+21] == observation['label_end'] <= end
                members = admissions[d]['admitted']
                w = {t['symbol']: float(t['target_weight']) for t in tape[d]['targets']}
                x = np.array([w[s] for s in members])
                y = np.array([opens[i+21, symbols.index(s)]/opens[i, symbols.index(s)]-1 for s in members])
                expected = float(np.corrcoef(rankdata(x), rankdata(y))[0, 1]) if np.ptp(x) and np.ptp(y) else None
                assert (expected is None and observation['ic'] is None) or abs(expected-observation['ic']) < 1e-12
                observation_count += 1
            annual_count += 1
        # Independent gate formula, including the critical absence of a default IC.
        calibration = item['windows']['calibration']
        obs = calibration['observations']
        ic = [r['ic'] for r in obs if r['ic'] is not None]
        returns = [v for r in obs for v in r['forward_returns']]
        sigma = np.std(returns, ddof=1)
        breakeven = calibration['annual_turnover'] * .0005 * 21/252/sigma
        margin = np.mean(ic)/breakeven
        expected = 'pass' if calibration['annual_turnover']*5 <= 44 and np.mean(ic) > 0 and margin >= 3 else 'reject'
        assert item['gate']['status'] == expected
        assert abs(margin-item['gate']['ic_margin']) < 1e-12
        decisions_count += len(dates)
        policy_count += 1
    assert policy_count == 16 and target_count == 4*result['daily_sessions']
    return dict(input_manifest_sha256=digest(root/'input_manifest.json'), analysis_sha256=digest(root/'analysis.json'),
                verified_daily_target_vectors=target_count, verified_member_scores=score_count,
                verified_policies=policy_count, verified_adoptions=decisions_count,
                verified_window_turnovers=annual_count, verified_ic_observations=observation_count,
                verdict_counts=dict(Counter(r['gate']['status'] for r in result['results'].values())),
                assertions='prior-session features, gates, caps/cash, overlap, class scores/budgets, adoption anchors, security turnover, IC labels/ranks and gate formula',
                native_replays=0, reason='All mappings rejected before portfolio replay',
                verifier_sha256=digest(Path(__file__)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('var/research/class-volatility-screen-20261016-v1'))
    args = parser.parse_args()
    receipt = check(args.root)
    write(args.root/'acceptance.json', receipt)
    print(json.dumps(receipt, indent=2))
