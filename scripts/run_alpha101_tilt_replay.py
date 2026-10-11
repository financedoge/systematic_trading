"""Run the P4.17c tilt replay on the current SOTA.

    python scripts/run_alpha101_tilt_replay.py prepare   --root var/research/alpha101-tilt-replay-20261011-v1
    python scripts/run_alpha101_tilt_replay.py decisions --root ...
    python scripts/run_alpha101_tilt_replay.py gate      --root ...
    python scripts/run_alpha101_tilt_replay.py economics --root ...
    python scripts/run_alpha101_tilt_replay.py analyze   --root ...
    python scripts/run_alpha101_tilt_replay.py report    --root ... --output research/alpha101-tilt-replay-2026-10-11
    python scripts/run_alpha101_tilt_replay.py verify    --root ...

The untouched SOTA and the same SOTA with a 10% Alpha101 tilt appended last in its overlay chain,
replayed on the parent study's own quotes, sessions, costs and windows. Gate before replay.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_tilt_replay_analysis as analysis
from systematic_trading.research import alpha101_tilt_study as study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'decisions', 'gate', 'economics', 'analyze', 'report', 'verify'))
    parser.add_argument('--root', default=str(study.DEFAULT_ROOT))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.stage == 'prepare':
        print(study.prepare(args.root))
    elif args.stage == 'decisions':
        study.initialize()
        rows = {}
        for arm in study.ARMS:
            rows[arm] = study.arm_days(arm)
            print({'arm': arm, 'days': len(rows[arm])})
        study.freeze(args.root, rows)
        print({'arms': len(rows), 'decisions': sum(len(v) for v in rows.values())})
    elif args.stage == 'gate':
        print(study.gate(args.root))
    elif args.stage == 'economics':
        study.initialize()
        for job in study.jobs():
            print(study.economics_resumable(args.root, job))
    elif args.stage == 'analyze':
        payload = analysis.summarize(args.root)
        print({'status': payload['verdict']['status'], 'statement': payload['verdict']['statement']})
    elif args.stage == 'report':
        print(analysis.report(args.root, args.output))
    else:
        checks = study.verify(args.root)
        print(checks)
        if not all(checks.values()):
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
