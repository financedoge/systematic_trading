"""Run the P4.17 Alpha101 time-series screen.

    python scripts/run_alpha101_screen.py prepare  --root var/research/alpha101-screen-20261011-v1
    python scripts/run_alpha101_screen.py screen   --root var/research/alpha101-screen-20261011-v1
    python scripts/run_alpha101_screen.py report   --root var/research/alpha101-screen-20261011-v1 \
        --output research/alpha101-screen-2026-10-11
    python scripts/run_alpha101_screen.py verify   --root var/research/alpha101-screen-20261011-v1

The screen is deterministic and produces no economics: it measures each registered alpha's
turnover, cost, breakeven IC and decay on the pinned audited evidence, and applies the
frozen P4.15 gate, before any portfolio work is attempted.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.research import alpha101_analysis as analysis
from systematic_trading.research import alpha101_screen as screening


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'screen', 'report', 'verify'))
    parser.add_argument('--root', default=str(screening.DEFAULT_ROOT))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.stage == 'prepare':
        print(screening.prepare(args.root))
    elif args.stage == 'screen':
        print(screening.run_screen(args.root))
    elif args.stage == 'report':
        print(analysis.report(args.root, args.output))
    else:
        checks = screening.verify(args.root)
        print(checks)
        if not all(checks.values()):
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
