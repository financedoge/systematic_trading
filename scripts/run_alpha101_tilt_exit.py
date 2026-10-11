"""Run the P4.17f exit-rule study.

    python scripts/run_alpha101_tilt_exit.py freeze    --root var/research/alpha101-tilt-exit-20261011-v1
    python scripts/run_alpha101_tilt_exit.py costs     --root ...
    python scripts/run_alpha101_tilt_exit.py economics --root ...
    python scripts/run_alpha101_tilt_exit.py analyze   --root ...
    python scripts/run_alpha101_tilt_exit.py report    --root ... --output research/alpha101-tilt-exit-2026-10-11
    python scripts/run_alpha101_tilt_exit.py verify    --root ...

Monthly entry, intra-month exits (flip / fade / no-signal / P&L stop / flip-with-re-entry / hold) at
X in {5, 10, 20}% on FR25 and the current SOTA, ranked on net outcomes after cost. Nothing is filtered
by the cost ceiling: the objective is the optimum.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_tilt_exit_analysis as analysis
from systematic_trading.research import alpha101_tilt_exit_study as study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze', 'costs', 'economics', 'analyze', 'report', 'verify'))
    parser.add_argument('--root', default=str(study.DEFAULT_ROOT))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.stage == 'freeze':
        print(study.freeze(args.root))
    elif args.stage == 'costs':
        print(study.costs(args.root))
    elif args.stage == 'economics':
        for job in study.jobs():
            print(study.economics_resumable(args.root, job), flush=True)
    elif args.stage == 'analyze':
        payload = analysis.summarize(args.root)
        print({'arms': len(payload['metrics']),
               'significant': {base: len(rows) for base, rows in payload['family_significant'].items()}})
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
