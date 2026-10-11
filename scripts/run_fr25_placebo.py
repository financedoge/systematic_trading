"""Execute the frozen P4.14 Part B study using its own pinned calculation code."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'calculate', 'economics', 'analyze', 'report', 'verify'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--draws', type=int, default=None, help='pilot only: restrict the declared draw range')
    parser.add_argument('--days', type=int, default=None, help='pilot only: restrict the number of decisions')
    args = parser.parse_args()
    root = args.root.resolve()
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      NUMEXPR_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    if args.stage != 'prepare':
        sys.path.insert(0, str(root / 'source'))
    from systematic_trading.research import fr25_placebo_study as study
    from systematic_trading.research.momentum_replay import checked_files
    from systematic_trading.lean.contracts import write_json, sha256
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
        if args.stage == 'calculate':
            draws = args.draws or study.DRAWS
            study.initialize(str(root))
            days = study.evaluation_days()
            if args.days:
                days = days[:args.days]
            with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=study.initialize,
                                     initargs=(str(root),)) as pool:
                futures = {}
                for day in days:
                    futures[pool.submit(study.placebo_day, day, draws)] = ('placebo', day)
                arms = [study.CANDIDATE, study.SENTINEL, study.BASELINE_ARM,
                        *[study.variant_name(n, w) for n, w in study.sensitivity_arms()]]
                for arm in arms:
                    futures[pool.submit(study.arm_days, arm)] = ('arm', arm)
                futures[pool.submit(study.refit_days)] = ('refit', study.REFIT_ARM)
                rows = {a: {} for a in arms}
                placebo_evidence = {}
                for future in as_completed(futures):
                    kind, key = futures[future]
                    value = future.result()
                    if kind == 'placebo':
                        day, day_rows, evidence, source = value
                        for arm, row in day_rows.items():
                            rows.setdefault(arm, {})[day] = (row, evidence[str(study.draw_of(arm))])
                        placebo_evidence[day] = dict(source=source, draws=evidence)
                        save(dict(kind=kind, day=day, draws=len(day_rows)))
                    else:
                        rows[key] = value
                        save(dict(kind=kind, arm=key, days=len(value)))
            study.freeze_decisions(root, rows, placebo_evidence)
            save(dict(arms=len(rows), placebo_days=len(placebo_evidence)))
        elif args.stage == 'economics':
            with ProcessPoolExecutor(max_workers=max(1, min(os.cpu_count(), 8)), initializer=study.initialize,
                                     initargs=(str(root),)) as pool:
                for future in as_completed([pool.submit(study.economics_resumable, str(root), job)
                                            for job in study.jobs()]):
                    save(future.result())
        elif args.stage == 'analyze':
            from systematic_trading.research.fr25_placebo_analysis import summarize, finalize
            summarize(root)
            save('summarized')
            print(finalize(root), flush=True)
        elif args.stage == 'report':
            from systematic_trading.research.fr25_placebo_analysis import artifacts
            if not args.output:
                raise ValueError('--output required')
            print(artifacts(root, args.output), flush=True)
        else:
            from systematic_trading.research.fr25_placebo_analysis import verify
            print(verify(root), flush=True)
        progress.update(status='succeeded', elapsed_seconds=time.perf_counter() - start)
    except BaseException as exc:
        progress.update(status='failed', error=repr(exc), elapsed_seconds=time.perf_counter() - start)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
