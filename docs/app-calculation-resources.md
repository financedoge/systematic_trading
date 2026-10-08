# Application calculation resources

The October 7 finite fallback research honors the user's all-core request with
16 independent Python workers and three native lanes allocated 6/5/5 CPUs,
retaining the existing 4 GiB-per-container and 2 GiB service memory reserve.
This explicit study resource plan is recorded in
`var/research/fallback-20261007-v1/{calculate,native}_progress.json`.
The application refresh now also uses the available CPU budget in full, as requested; native concurrency retains the memory limits below.

The application now parallelizes independent strategy calculations. The earlier path fitted monthly models in parallel but then prepared and replayed every strategy serially, with a two-CPU native container limit. That left much of the machine idle during a full refresh.

On this workstation, Python and Docker both expose 16 logical CPUs. Docker has 15.39 GiB of memory; the host has approximately 32 GiB. The application chooses this plan automatically:

| Phase | Parallelism | Limit |
| --- | --- | --- |
| Monthly model fits | Up to 16 processes | Each individual estimator retains the versioned single-thread recipe; independent monthly fits use all available CPU workers. |
| Historical decision-bundle preparation | One isolated process per independent strategy/benchmark job, up to the CPU budget | Up to the available host CPU budget, one numerical thread per process. Each strategy preserves its chronological decision order. |
| Native LEAN/Python parity runs | Three independent runs concurrently | Approximately 5.333333 CPUs and 4 GiB per native container; 16 CPUs shared across three lanes. Two GiB of Docker memory is reserved before calculating the worker count. |
| Account, execution and dashboard calculations | Separate operations worker | Continues independently while research runs. |

The scheduler uses the lower of host and Docker CPU availability, uses that full CPU budget, and reduces concurrency when Docker memory is smaller. It never requests more workers than independent jobs. Python-only calculations do not need Docker discovery. These are capacity limits, not a promise of continuous 100% CPU use: chronological calculations, file I/O and publication have sequential phases.

Bundle preparation now runs in subprocesses with only the runtime environment, frozen input references and numerical thread limits. Database/broker credentials are excluded. Input/model file hashes are verified before preparing the bundle. Independent run threads only orchestrate subprocesses; PostgreSQL registration and the final publication remain on the parent research worker.

The same immutable bundles, chronological strategy definitions, economics and native parity checks apply. A failed worker cannot publish a partial set. Per-run CPU/memory limits are recorded in native run receipts; the complete batch retains its resource plan, phase timings and completed job list. The status is available through `/api/v1/analytics/status` in `compute`, with a durable state file at `var/run/strategy-compute.json` and a final `compute.json` in the calculation's artifact directory.

The USD defensive-cash report uses 16 independent monthly-decision workers, then independent complete USD accounting replays and native checks. It uses the same memory bounds and all available Docker CPUs. Restore performs a complete deterministic replay; no missed monthly decisions are replaced by a holdings-only extension.

Relevant implementation: `research/compute.py`, `research/calculation_worker.py`, `research/tracked_runtime.py`, and `lean/runner.py`. Tests cover actual overlap, CPU/Docker-memory limits, failure propagation, input tampering, credential exclusion and identical decisions from isolated preparation. Runtime acceptance and complete regression results are recorded in the execution Kanban and `var/research/parallel-*` receipts.

## Verified application run

Revision `4ad0f8ac9939ea9dd2766abf5b38e98beed647c8579234e24875af7e05e95b2b` completed and published on September 28 Shanghai time. All five preparation jobs completed in **39.13 seconds**; the native backtest phase completed in **153.74 seconds**, versus **370.88 seconds summed across its individual runs**. The summed figure demonstrates overlap, rather than claiming a controlled hardware benchmark. Every native parity check passed, and every strategy's economic output matched its previous serial calculation.

The final suite passed **708 tests / 51 optional skips**; whole-project Ruff and diff checks passed. Account calculations stayed fresh during the run; all eight required services were healthy at acceptance. Evidence: `var/research/parallel-calculation-acceptance.json`, `var/research/app-connections-and-parallel-final.xml`, and `var/research/app-connections-runtime-final.json`.
