"""Run the P4.17d tilt budget surface.

    python scripts/run_alpha101_tilt_surface.py freeze    --root var/research/alpha101-tilt-surface-20261011-v1
    python scripts/run_alpha101_tilt_surface.py gate      --root ...
    python scripts/run_alpha101_tilt_surface.py economics --root ...
    python scripts/run_alpha101_tilt_surface.py analyze   --root ...
    python scripts/run_alpha101_tilt_surface.py report    --root ... --output research/alpha101-tilt-surface-2026-10-11
    python scripts/run_alpha101_tilt_surface.py verify    --root ...

FR25 and the current SOTA tilted by the equal-weight family of all sixteen registered alphas at
X in {10, 20, 30, 50, 75, 100, 150}%, over the same 70 evaluation decisions. Cost is measured for
every arm but, at the operator's instruction, does not gate the replays.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_tilt_surface_analysis as analysis
from systematic_trading.research import alpha101_tilt_surface_study as study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('freeze', 'gate', 'economics', 'analyze', 'report', 'verify'))
    parser.add_argument('--root', default=str(study.DEFAULT_ROOT))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.stage == 'freeze':
        print(study.freeze(args.root))
    elif args.stage == 'gate':
        print(study.gate(args.root))
    elif args.stage == 'economics':
        for job in study.jobs():
            print(study.economics_resumable(args.root, job), flush=True)
    elif args.stage == 'analyze':
        payload = analysis.summarize(args.root)
        print({'arms': len(payload['metrics']), 'bases': list(payload['in_sample_best'])})
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
