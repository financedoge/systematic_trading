# Local LEAN research worker

The worker integrates the existing SOTA strategy and baseline with the actual
LEAN event engine. It cannot route orders to IB. Input bundles and run artifacts
live under `D:/systematic_trading_data/lean/`; PostgreSQL stores immutable research
evidence in `ops.lean_research_runs`.

The [September 26 validation report](lean-validation-2026-09-26.md) records all
twelve successful native runs, including two 3,330-session histories. Tested
image: `quantconnect/lean@sha256:27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59`
(release label 18130). Input, fill, fee, cash and NAV comparisons passed without
widening the declared tolerances.

## Contract and scenario

`BacktestRunSpec v1` freezes strategy/model/source hashes, repository commit,
calendar, warmup, execution interval, seeds, costs, normalization, settlement,
currency, data certification and parity tolerances. The manifest hashes every
data and source file. Runs verify it before and after execution, reject extra or
modified files, and retain failures without marking success.

Version 1 is **adjusted CNH units, next-session open**. Signals use the existing
pure Python SOTA implementation on prior USD bars. The open converts with the
previous completed FX observation; the closing valuation uses that session's FX.
Prices are rounded to 0.01 CNH per adjusted unit. Cash settles immediately in CNH,
whole units only, without leverage. This is an explicitly separate engineering
scenario from the older runner retaining USD cash. It cannot certify broker TWAP
or raw splits/dividends; adjusted data receives no additional corporate actions.

`targets` replays frozen monthly targets. `shared` recomputes those targets in
the container from the frozen strategy source and prior-only signal context.
Both route simulated orders through LEAN's native transactions, fill model,
portfolio and cash book. The Python engine independently runs identical declared
economics. Target/date/symbol/quantity differences fail; cash, fee and NAV checks
use predeclared tolerances. Failed or partial results cannot enter the registry.

## Use

Install the official `quantconnect/lean` container, then use its immutable
`quantconnect/lean@sha256:...` repository digest. Mutable tags are rejected by the
runner. The open-source engine is invoked directly; no QuantConnect cloud upload,
paid CLI subscription, or brokerage credentials are involved.

```powershell
.\.venv\Scripts\python.exe scripts/run_lean_backtest.py --export `
  --bundle D:/systematic_trading_data/lean/datasets/my-sota-run `
  --start 2025-01-02 --end 2025-12-31 --warmup-start 2023-10-01

.\.venv\Scripts\python.exe scripts/run_lean_backtest.py `
  --bundle D:/systematic_trading_data/lean/datasets/my-sota-run `
  --output D:/systematic_trading_data/lean/runs/my-sota-run `
  --image quantconnect/lean@sha256:<verified-digest> --register
```

Strict export refuses missing/invalid bars and missing FX dates. Current legacy
data may require the explicit `--allow-legacy-fx` engineering mode: no future rate
is used, original source dates are retained, carry is limited to seven days, and
the run remains ineligible for promotion. It is not a repair of historical FX
provenance. Warmup requires 253 prior observations. `--strategy benchmark`,
`--mode targets`, `--cost-bps`, `--slippage-bps` and `--delay-sessions` are explicit
scenario controls, recorded in the immutable specification.

Run the repeatability, one-year, long-history and robustness suite with:

```powershell
.\.venv\Scripts\python.exe scripts/validate_lean_integration.py `
  --root D:/systematic_trading_data/lean/validation/my-new-suite `
  --image quantconnect/lean@sha256:<verified-digest>
```

Each suite directory is new and immutable. The suite includes target replay,
shared strategy calculation, identical replay, higher fees/slippage, one-session
delay, 42/84-bar parameter neighborhoods, and SOTA/baseline comparisons.
`report.md` is the readable result; `summary.json` records process CPU, peak RSS,
runtime versions, event counts, first/repeat timings, artifact sizes and separate
pre-/post-2023 metrics. These are explicitly labelled fitted/selected intervals.

The container has no network, a read-only filesystem/input mount, no privileges,
2 CPUs, 4 GiB memory, a PID limit and a bounded timeout. Only its dedicated output
directory and temporary scratch space are writable. The project `.env`, Docker
socket, database credentials and broker connection are not mounted.
The NAS database snapshot includes registry rows. Frozen datasets/run files and
the Docker image remain on D: and require separate copying when moving PCs,
just like ClickHouse/raw market-data artifacts.

Artifacts include the specification, source/data provenance, target decisions,
native fills/fees, daily NAV/cash, final holdings, engine logs, Python reference,
parity discrepancies, economic hash and completion receipt. Registry insertion
re-verifies hashes, is idempotent for identical evidence, and never emits an
approval, executable proposal, broker order or event-outbox entry.
PostgreSQL triggers prohibit updating, deleting or truncating the research
registry; a database constraint prohibits setting its promotion flag.

## Promotion and rollback

Every initial run is marked research-only. Missing historical vintages,
survivorship evidence, raw corporate-action/settlement testing and observed TWAP
costs remain promotion blockers. See the [platform audit](platform-audit-2026-09-26.md).
Disabling the worker or choosing the existing Python runner is the rollback;
current paper trading and the promoted strategy are unaffected.
