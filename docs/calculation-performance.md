# Tracked-calculation performance: measurements and levers

Operator question, 2026-10-11: *does the research worker use all the resources available? It is
incredibly slow, and CPU sits around 40% while it calculates.*

Measured, then changed once, then measured again. Nothing here changes a strategy, a contract or a
published number: the change is scheduling only, and the result is bit-identical.

## Where the time actually goes

A tracked-strategy batch on this machine (16 logical CPUs, 31.5 GiB host RAM, Docker allocated
16.53 GB / 16 CPUs):

| Stage | Baseline | After the change | Mean CPU | Peak memory |
| --- | ---: | ---: | ---: | ---: |
| Model preparation (`preparing_models`, `preparing_bundles`) | 45.5s | 53.5s | 54–56% | 1.2 GiB |
| Native backtests (`running_backtests`) | **101.8s** | **81.4s** | 65% | 1.3 GiB |
| Reports (`building_reports`) | — | 8s | 28% | 0.8 GiB |
| USD strategies (`replaying_usd_strategies`) | ~105s | 105s | 53% | 4.2 GiB |
| M1/FR25 (`replaying_m1_14`) | ~150s | 204s | 46% | 6.5 GiB |
| **Whole batch** | ~6.0 min | 7.9 min | — | — |

The batch-to-batch spread above is larger than the change for the tail stages; the two comparable
numbers are the backtest stage (101.8s → 81.4s, the change) and the per-job engine times below.

**Per job, before the change** (from the receipts): `elapsed_seconds` was exactly
`lean_wall_seconds + reference_wall_seconds` — 89.4s = 51.5s + 37.7s, 90.9s = 51.3s + 39.2s,
66.3s = 43.9s + 20.9s. The two engines ran one after the other.

## Why the CPU sits at 40–65%, and why that is partly deliberate

1. **Every numerical engine here is pinned to one thread on purpose.** The receipts record
   `numerical_threads: 1`, and both the reference runner and the preparation workers set
   `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`. Thread count
   changes floating-point summation order, so the pin is what makes a fit reproducible from its
   revision identity. It is a determinism guarantee, not an oversight — and it means "allocate
   5.33 CPUs per LEAN run" buys nothing, because a LEAN backtest is single-threaded.
2. **The real concurrency cap is Docker memory, not CPU.** `resource_plan` limits workers to
   `min(jobs, cpu_budget // 2, (docker_memory_gib - 2) // 4)` — 4 GiB per LEAN run plus 2 GiB of
   Docker headroom. With Docker at **15.39 GiB that is 3 concurrent runs**, on a machine whose host
   has **31.5 GiB**. CPU allocation (`16` logical, `budget // 2 = 8` workers) is never the binding
   constraint.
3. **Stages run one after another.** The three analytics lanes (research, operations, archives) do
   run in parallel, but the jobs *within* a lane are sequential, so a long `tracked-strategies`
   batch holds up `signal-decay`, the recorders and the serving publication behind it.

## The change: the two engines now run together

`lean/runner.run_bundle` ran the Python reference (37.7s) and then the LEAN container (51.5s). They
are independent — LEAN writes `economic.json`, the oracle writes `reference.json`, and parity
compares them only after both exist — so the job was paying their sum rather than their maximum.

The runner now launches both, waits for both, still records each engine's own wall time, and still
fails the same way: a non-zero exit terminates its partner and raises `CalledProcessError`, a
timeout terminates both and raises `TimeoutExpired`. Nothing about either engine's inputs, threads
or code changed, so nothing about the numbers changed.

**Measured on the same frozen bundle** (`risk_parity`, the actual tracked revision):

| | elapsed | LEAN | reference |
| --- | ---: | ---: | ---: |
| sequential (recorded receipt) | 66.3s | 43.9s | 20.9s |
| concurrent (re-run) | **47.8s** | 47.3s | 20.4s |
| **speedup** | **1.39×** (18.5s saved per job) | | |

LEAN parity passed with **0 differences** and the economic artifact hash is **identical** to the
published one. The two ~90s jobs save proportionally more (their reference leg is 38–39s). On the
real batch the backtest stage fell from **101.8s to 81.4s**.

Three tests pin the new contract: the engines genuinely overlap, a failing engine terminates its
partner instead of leaving it running, and a timeout terminates both.

## What is left, and what needs an operator decision

1. **Docker Desktop memory is the cheapest big win and it is a setting, not code.** The host has
   31.5 GiB; Docker is allocated 15.39 GiB, which caps concurrency at 3 LEAN runs. Raising the
   Docker allocation to about 24 GiB would allow 5–6 concurrent runs and would shorten both the
   native backtest stage and the M1/FR25 tail, which is now the largest single block (~3.5 min).
   I have not changed it: it is a desktop-wide resource setting, not a repository change.
2. **Relaxing the single-thread pin needs governance first.** It would change model fits, and the
   numerical thread count is *not* part of `calculation_revision` — the receipt records it, but the
   revision identity does not. Any change there must add it to the identity first, so a published
   calculation stays reproducible from the code and settings that produced it.
3. **`cpus_per_run` is cosmetic for LEAN.** The resource plan divides the CPU budget by the worker
   count and passes it to `docker run --cpus`; a single-threaded algorithm cannot use it. It is
   recorded in receipts as though it were a capacity statement, which is misleading rather than
   harmful, and correcting it is a labelling change worth doing with the memory work above.
4. **Parallelising the tail stages** (`replaying_usd_strategies`, `replaying_m1_14`, report
   building) is the next code-level lever. The M1 stage already fans out over decision sessions and
   native attempts; what remains serial is the publication and report assembly around it, and that
   is a larger change than this one — worth doing deliberately rather than quickly.

## Verification

The change is covered by `tests/test_lean_runner_concurrency.py`; the full suite passes; the real
batch that followed the restart completed with no error, all six monitored strategies republished,
and the platform and analytics health returned to `ok`. The per-job receipts still record LEAN and
reference wall times separately, so the effect of this change stays auditable after the fact.
