"""Execute the frozen P4.16b hierarchical-construction study.

Stage order matters: the P4.15 turnover gate screens both candidate arms **before** any
economic replay exists.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from pathlib import Path
import sys
import time

from systematic_trading.lean.contracts import sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'decisions', 'gate', 'economics', 'analyze', 'report', 'verify'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      NUMEXPR_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    if args.stage != 'prepare':
        sys.path.insert(0, str(root / 'source'))
    from systematic_trading.research import hierarchical_construction_study as study
    from systematic_trading.research.momentum_replay import checked_files, read_json
    if args.stage == 'prepare':
        print(study.prepare(root, Path(__file__)), flush=True)
        return
    checked_files(root, 'input_manifest.json')
    if sha256(Path(__file__)) != sha256(root / 'runner.py'):
        raise ValueError('Runner differs from frozen code')
    start = time.perf_counter()
    progress = dict(stage=args.stage, status='running', completed=[])
    def save(value=None):
        if value is not None:
            progress['completed'].append(value)
            print(value, flush=True)
        write_json(root / (args.stage + '_progress.json'), progress)
    save()
    try:
        if args.stage == 'decisions':
            study.initialize(str(root))
            with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=study.initialize,
                                     initargs=(str(root),)) as pool:
                futures = {pool.submit(study.arm_days, arm): arm for arm in study.ARMS}
                rows = {}
                for future in as_completed(futures):
                    rows[futures[future]] = future.result()
                    save(dict(arm=futures[future], days=len(rows[futures[future]])))
            from systematic_trading.research.sleeve_construction_study import freeze_decisions
            freeze_decisions(root, rows)
            save(dict(arms=len(rows), decisions=sum(len(v) for v in rows.values())))
        elif args.stage == 'gate':
            from systematic_trading.research.sleeve_construction_gate import screen_arms
            print(screen_arms(root, arms=study.ARMS, always=('POOL',), version_label='p4.16b'), flush=True)
        elif args.stage == 'economics':
            gate = read_json(root / 'gate.json')
            allowed = [arm for arm, row in gate['arms'].items() if row['may_replay']]
            jobs = study.jobs(tuple(dict.fromkeys(allowed)))
            save(dict(jobs=len(jobs), arms=allowed, gate_rejected=gate['gate_rejected'],
                      boundary=gate.get('boundary_cases', [])))
            with ProcessPoolExecutor(max_workers=max(1, min(os.cpu_count(), 8)), initializer=study.initialize,
                                     initargs=(str(root),)) as pool:
                for future in as_completed([pool.submit(study.economics_resumable, str(root), job) for job in jobs]):
                    save(future.result())
        elif args.stage == 'analyze':
            from systematic_trading.research.hierarchical_construction_analysis import summarize, finalize
            summarize(root)
            save('summarized')
            print(finalize(root), flush=True)
        elif args.stage == 'report':
            from systematic_trading.research.hierarchical_construction_analysis import artifacts
            if not args.output:
                raise ValueError('--output required')
            print(artifacts(root, args.output), flush=True)
        else:
            from systematic_trading.research.hierarchical_construction_analysis import verify
            print(verify(root), flush=True)
        progress.update(status='succeeded', elapsed_seconds=time.perf_counter() - start)
    except BaseException as exc:
        progress.update(status='failed', error=repr(exc), elapsed_seconds=time.perf_counter() - start)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
