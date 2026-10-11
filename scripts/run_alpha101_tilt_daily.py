"""Run the P4.17e daily, threshold-triggered tilt.

    python scripts/run_alpha101_tilt_daily.py freeze    --root var/research/alpha101-tilt-daily-20261011-v1
    python scripts/run_alpha101_tilt_daily.py gate      --root ...
    python scripts/run_alpha101_tilt_daily.py economics --root ...
    python scripts/run_alpha101_tilt_daily.py analyze   --root ...
    python scripts/run_alpha101_tilt_daily.py report    --root ... --output research/alpha101-tilt-daily-2026-10-11
    python scripts/run_alpha101_tilt_daily.py verify    --root ...

Daily monitoring of the Alpha101 family tilt on FR25 and the current SOTA, with the re-tilt threshold as
the cost control: X in {5, 10, 20}% and threshold in {daily, 50%, 100%} of the budget, plus the monthly
arm as the frequency reference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_tilt_daily_analysis as analysis
from systematic_trading.research import alpha101_tilt_daily_study as study


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
        print({'arms': len(payload['metrics']), 'gate_passing': payload['gate_passing']})
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
