"""Run the P4.17b Alpha101 tilt measurement.

    python scripts/run_alpha101_tilt.py prepare --root var/research/alpha101-tilt-20261011-v1
    python scripts/run_alpha101_tilt.py measure --root var/research/alpha101-tilt-20261011-v1
    python scripts/run_alpha101_tilt.py verify  --root var/research/alpha101-tilt-20261011-v1

Measures the incremental turnover, cost and breakeven IC of tilting the pinned monitored book by
each registered alpha at each declared budget, and applies the P4.15 gate against the published
cost headroom. No economics and no replay: nothing is replayed until a candidate clears.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_tilt as tilt
from systematic_trading.research import alpha101_tilt_analysis as analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'measure', 'report', 'verify'))
    parser.add_argument('--root', default=str(tilt.DEFAULT_ROOT))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.stage == 'prepare':
        print(tilt.prepare(args.root))
    elif args.stage == 'measure':
        tilt.initialize()
        print(tilt.run(args.root))
    elif args.stage == 'report':
        print(analysis.report(args.root, args.output))
    else:
        tilt.initialize()
        checks = tilt.verify(args.root)
        print(checks)
        if not all(checks.values()):
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
