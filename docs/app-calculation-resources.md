# Application calculation resources

## October 31 native memory policy

The operator removed the default 4 GiB native process/Job quota and the 10 GiB
free-physical-RAM admission gate. These were policy choices carried into the
October 18 native migration, not requirements of Windows isolation. Normal
native model, bundle, USD accounting, Python-reference and LEAN workers now use
Windows-managed memory, including its existing system-managed pagefile. Receipts
report `memory_limit_bytes: null` and `memory_policy: windows_managed`.

Available RAM and estimated duplicated inputs size the number of independent
workers started. There is no fixed 4 GiB scheduling budget or 6 GiB reservation;
memory pressure reduces concurrency to one without rejecting the whole stage.
Running workers can grow beyond the launch-time estimate. Windows allocation
failure and paging latency remain possible; no RAM/pagefile setting is changed.

AppContainer network denial, read-only inputs, credential exclusion, descendant
cleanup, deadlines, shared-ACL serialization, deterministic estimators, independent
LEAN validation and atomic publication remain enforced. The process-count ceiling
allows the Windows venv redirector/interpreter pair for each CPU worker. Explicit
memory limits remain available to tests or intentionally bounded recovery runs;
legacy Docker retains its explicitly selected historical quota. DuckDB query
budgets and storage-retention limits are separate and unchanged.

## October 30 CPU parallelism — historical initial memory budget

The operator requested using available CPU resources again. Native model fitting
and USD/M1/FR25 preparation can now use the host CPU budget (16 logical CPUs on
this workstation). Independent monthly fits/targets and complete accounting
replays use subprocesses inside one restricted AppContainer and Windows Job.
File transport avoids the global named pipes denied to the ordinary Windows
process pool. Every estimator retains its single-threaded deterministic recipe;
each portfolio's sessions remain chronological.

Concurrency is bounded by independent work, available CPUs and duplicated input
memory. The planner reserves 512 MiB plus four times serialized input size for
the coordinator, then 256 MiB plus four times input size per child. The existing
4 GiB aggregate Job ceiling, 10 GiB admission requirement, service headroom,
storage budget and native validation remain enforced. Six workers fit the current
67 MB M1/FR25 input. This is a conservative planning estimate, not a guaranteed
maximum working set; the Job remains the hard limit.

The external native-worker mutex still serializes separate AppContainers to
protect inherited ACL updates. Independent LEAN/oracle validation remains serial;
the CPU improvement is inside model/decision/accounting preparation. Network
acquisition, ordered replay and publication can still leave CPU idle. Account
operations already run in their own lane; their capture inventory now uses a
single directory scan instead of repeated full path resolution/stat calls.

Receipts record actual preparation workers, stage durations, child CPU times and
peak aggregate commit. Serial/parallel targets, fits, fills and NAV are checked
for equality. The reproducible read-only benchmark is
`scripts/benchmark_calculation_parallelism.py`; it verifies retained application
inputs and never publishes or changes broker state. See the current measurements
in [calculation performance](calculation-performance.md).

## October 18 storage and memory policy

At that date the operator superseded the historical all-core preference below
with memory/storage-first operation. The app admitted one heavy calculation and limited native workers to
4 GiB and two CPUs, uses one Windows model-fit worker, and requires 10 GiB host
memory available before starting. DuckDB uses 1 GB/two threads per query with two
query slots. Generated artifacts have a 40 GiB admission budget, including a 2 GiB
reserve; protected evidence is never evicted to make a run fit. See the
[native runtime guide](native-windows-runtime.md) for enforced limits and the
remaining distinction between DuckDB memory and total API-process memory.

## Historical September/October all-core configuration

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
