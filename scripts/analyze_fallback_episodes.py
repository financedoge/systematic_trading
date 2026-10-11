"""Attribute the defensive fallback's measured value, episode by episode (P4.16 follow-up).

CP and the construction-matched POOL arm differ only on the decisions where CP's
defensive fallback fires, so tiling the full-window replay at those decisions attributes
the whole gap between them. Weights are compared with a tolerance: the two overlays
round weights differently in the last decimal digits, and a string comparison would
misreport 89 changed decisions where the true count is 11.

Read-only over the frozen P4.16 evidence. Writes one follow-up receipt beside the study
root; it does not touch the frozen revision.
"""
import argparse
import json
import math
from decimal import Decimal
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json

ROOT = Path('var/research/sleeve-construction-20261010-v1')
DEFAULT_OUTPUT = ROOT / 'followup/fallback-episodes.json'
TOLERANCE = Decimal('1e-12')


def load(root, arm):
    decisions = json.loads((root / 'decisions' / f'{arm}.json').read_text(encoding='utf8'))
    nav = json.loads((root / 'python' / f'{arm}-cost5-delay0-full.json').read_text(encoding='utf8'))['nav']
    return decisions, {row['date']: float(row['nav']) for row in nav}


def weights(row):
    return {t['symbol']: Decimal(t['target_weight']) for t in row['targets']}


def analyse(root=ROOT, candidate='CP', control='POOL', evaluation_start='2021-01-04'):
    root = Path(root)
    left, nav_left = load(root, candidate)
    right, nav_right = load(root, control)
    quotes = json.loads((root / 'bundles' / f'{candidate}-cost5-delay0-full' / 'quotes.json').read_text(encoding='utf8'))
    benchmark = {d: float(q['close']) for d, q in quotes['SPY'].items()}
    days = sorted(nav_left)
    if days != sorted(nav_right):
        raise ValueError('The two arms do not share one valuation calendar')
    differing = []
    for day in sorted(set(left) & set(right)):
        a, b = weights(left[day]), weights(right[day])
        if any(abs(a.get(s, Decimal(0)) - b.get(s, Decimal(0))) > TOLERANCE for s in set(a) | set(b)):
            differing.append(day)
    daily = [0.0]
    for i in range(1, len(days)):
        daily.append(math.log(nav_left[days[i]] / nav_left[days[i - 1]])
                     - math.log(nav_right[days[i]] / nav_right[days[i - 1]]))
    episodes, total = [], 0.0
    for i, day in enumerate(differing):
        start = days.index(day) + 1
        end = days.index(differing[i + 1]) + 1 if i + 1 < len(differing) else len(days)
        window = days[start:end]
        if not window:
            continue
        piece = sum(daily[start:end])
        total += piece
        held = sorted(s for s, w in weights(left[day]).items() if w > 0)
        episodes.append(dict(decision=day, through=window[-1], sessions=len(window),
                             candidate_minus_control_log=piece,
                             candidate_return=math.exp(math.log(nav_left[window[-1]] / nav_left[days[start - 1]])) - 1,
                             control_return=math.exp(math.log(nav_right[window[-1]] / nav_right[days[start - 1]])) - 1,
                             benchmark_return=benchmark[window[-1]] / benchmark[days[start - 1]] - 1,
                             candidate_held=held, cash_only=not held,
                             inside_evaluation=bool(day >= evaluation_start)))
    whole = (math.log(nav_left[days[-1]] / nav_left[days[0]])
             - math.log(nav_right[days[-1]] / nav_right[days[0]]))
    inside = [e for e in episodes if e['inside_evaluation']]
    outside = [e for e in episodes if not e['inside_evaluation']]
    return dict(candidate=candidate, control=control, decisions=len(days), differing=len(differing),
                window=[days[0], days[-1]],
                candidate_total_return=nav_left[days[-1]] / nav_left[days[0]] - 1,
                control_total_return=nav_right[days[-1]] / nav_right[days[0]] - 1,
                whole_log_difference=whole, tiled_log_difference=total,
                tiled_share_of_whole=total / whole,
                evaluation_episodes_log=sum(e['candidate_minus_control_log'] for e in inside),
                earlier_episodes_log=sum(e['candidate_minus_control_log'] for e in outside),
                episodes=episodes,
                inputs={str(path): sha256(path) for path in
                        (root / 'decisions' / f'{candidate}.json', root / 'decisions' / f'{control}.json',
                         root / 'python' / f'{candidate}-cost5-delay0-full.json',
                         root / 'python' / f'{control}-cost5-delay0-full.json')})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = analyse(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(f"differing decisions {result['differing']} of {result['decisions']}; "
          f"tiled {100 * result['tiled_log_difference']:+.2f} log pp of "
          f"{100 * result['whole_log_difference']:+.2f} ({100 * result['tiled_share_of_whole']:.0f}%)")
    print(f"earlier episodes {100 * result['earlier_episodes_log']:+.2f}pp | "
          f"evaluation-window episodes {100 * result['evaluation_episodes_log']:+.2f}pp")
    for e in result['episodes']:
        print(f"  {e['decision']} -> {e['through']} {e['sessions']:4d}s "
              f"{100 * e['candidate_minus_control_log']:+7.2f}pp  "
              f"{'CASH' if e['cash_only'] else '+'.join(e['candidate_held'])}")
    print(args.output)


if __name__ == '__main__':
    main()
