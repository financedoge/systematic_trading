"""Run the P4.15 turnover and breakeven-IC gate calibration and its published report.

The gate itself is a pre-test over evidence that already exists, so this runner takes
no new data and runs no new replay: it calibrates the implied mapping against the
frozen replays and writes the pinned artifact plus the report.
"""
import argparse
from pathlib import Path
import sys
import time

from systematic_trading.lean.contracts import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['build', 'report'])
    parser.add_argument('--root', type=Path, default=Path('var/research/turnover-gate-20261010-v1'))
    parser.add_argument('--output', type=Path, default=Path('research/turnover-gate-2026-10-10'))
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from systematic_trading.research import turnover_gate_analysis as analysis
    start = time.perf_counter()
    progress = dict(stage=args.stage, status='running', completed=[])
    def save(value=None):
        if value is not None:
            progress['completed'].append(value)
            print(value, flush=True)
        write_json(args.root / (args.stage + '_progress.json'), progress)
    save()
    try:
        if args.stage == 'build':
            report = analysis.build(args.root)
            save(dict(arms=len(report['arms']), sigma=round(report['sigma'], 6),
                      median_measured_over_implied=round(report['calibration']['ratio_median'], 6),
                      implied_conservative_in_all=report['calibration']['implied_is_conservative_in_all'],
                      raw_screen=report['calibration']['raw_screen']['false_pass'],
                      correction=report['calibration']['correction']))
            for entry in report['verdicts']['archetypes']:
                save(dict(candidate=entry['name'], status=entry['status'],
                          cost_bps=round(entry['annual_cost_bps'], 1), margin=entry['ic_margin']))
        else:
            print(analysis.artifacts(args.root, args.output), flush=True)
        progress.update(status='succeeded', elapsed_seconds=time.perf_counter() - start)
    except BaseException as exc:
        progress.update(status='failed', error=repr(exc), elapsed_seconds=time.perf_counter() - start)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
