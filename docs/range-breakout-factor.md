# Adaptive range-breakout lifecycle factor — 2026-10-18

Implemented and tested as a research prototype. No strategy monitoring, allocation,
paper-policy or live authority changed. The [full report](../research/range-breakout-20261018-v1/index.html)
contains equations, every primary case episode, charts, controls, costs, delays,
annual and walk-forward results, and constituent attribution. The
[registered protocol](../research/range-breakout-20261018-v1/protocol.json) and
[USO extension](../research/range-breakout-20261018-v1/uso-extension-protocol.json)
preserve the finite experiment definitions.

## Observable hypothesis

A compact, non-trending price distribution followed by a persistent upward break
may identify a new price regime. Price and volume cannot establish that fundamentals
were stable or changed; that causal claim needs separately available fundamental
evidence. Neither confirmation nor a stop can guarantee avoidance of false breaks.
No rule knows the eventual peak. The experiment evaluates implementable exits,
not an oracle exit optimized with future prices.

The operator clarified before signal/performance calculation that one and two
years were illustrations, not required lookbacks. The primary duration is adaptive;
252 and 504 sessions remain controls. Gold, oil and semiconductors were requested
as illustrative cases, not selected after observing their results.

## Mathematical definition

At completed session t, let x_s = log(P_s), with P an audited adjusted close.
For each L in {42,63,126,252,504,756}, use s=t−L,…,t−1, excluding the breakout bar.
Define q05 and q95, W=q95−q05, and b=min(63,max(10,floor(L/4))). A range qualifies when:

1. W ≤ log(1.25): its central 90% price distribution spans at most 25%.
2. |median(last b log prices)−median(first b log prices)| ≤ W/2.
3. Standard deviation of the latest min(63,floor(L/3)) log returns is no greater
   than the whole-window standard deviation.

Choose the longest complete qualifying L using only prior observations. This is
an adaptive-duration rule with declared candidate windows, not a claim to an
optimal arbitrary change-point estimator. Freeze U=exp(q95), D=exp(q05), L and
entry ATR20 when price first crosses U+0.5 ATR20 from below. ATR is the arithmetic
20-session mean of adjusted true range.

Require three consecutive closes above that frozen breakout level. In the volume
variant, mean raw volume across those three sessions must be at least 1.2 times
the median raw volume over the 63 sessions before the initial crossing. A failed
close or failed third-day volume condition cancels confirmation. The first
possible entry is the next session open.

For a virtual signal episode filled at E, set

`S_initial = max(E − 2 × ATR_entry, U − ATR_entry)`

and ratchet after each close:

`S_t = max(S_(t−1), H_t − k_t × ATR20_t)`.

H is the highest close since entry, initialized at the entry price. Normally k=4.
An episode becomes permanently overheated when its close is at least
U+3 ATR_entry, within one current ATR of H, and its raw volume is at least twice
its prior-63-session median. The heat-sensitive variant then uses k=2. The other
variant retains k=4, providing a direct exit ablation.

Exit after a close below S or below U−0.5 ATR_entry. Also exit after 21 holding
sessions if H has never reached E+ATR_entry. Execution is the next open, including
any gap, never the stop threshold or a future maximum. An extra one-session delay
is a separate stress scenario. The delayed target remains unchanged, with sizing
using the latest available pre-fill close under the shared accounting contract.

Wait 21 sessions after an exit and require another qualifying range for re-entry.
A close below the old lower band during this reset is an oversold diagnostic;
it does not create a bottom-buy signal. A new rolling range supplies a new
equilibrium estimate. There is no short position or inferred fundamental value.

The continuous active factor is `clip((P_t−U)/ATR_entry,0,10)`, otherwise zero.
Signal episodes are independent of actual portfolio selection and fills.

## Test design and data

Twelve variants: adaptive/252/504 × volume off/on × heat trail off/on. Three uses:

- Selection: add 0.5 times the active factor's cross-sectional rank to the
  volatility-normalized full-pool M1 momentum rank, preserving its positive
  126-session eligibility gate and inverse-volatility/top-six construction.
- Trading: select up to six active breakout episodes; inverse-volatility sizing,
  45% security cap and unfilled slots in cash.
- Tilt: 80% of the frozen matched FR25 monthly target plus 20% breakout sleeve.
  Compare with both FR25 and the construction-matched 80% FR25 / 20% M1 control.

Monthly adoption is the fixed control. Event adoption includes monthly anchors,
strictly >0.10 L1 change between latest theoretical and last adopted targets
including cash, and mandatory breakout-exit adoptions for trading/tilt exposure.
It never compares with actual held weights. Monthly controls deliberately delay
exits; they are not daily stop implementations.

Each use/timing/variant is replayed at 5/10/20 bp per traded security side and
zero/one extra execution session. The 44 bp annual-cost ceiling is not used.
Actual fills, traded notional, fees, cash, NAV and attribution use the existing
application accounting engine. Price/volume signal calculations retain full input
precision; accounting follows the existing cent-quantized adjusted-unit convention.
Cash earns zero. USD accounting avoids unsupported historical CNH/FX assumptions.

Original experiment: 53 reviewed, 50 supported, pinned published batch
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
BWX/XOP listing conflicts and CPER's unsupported 2018-08-23 raw-volume observation
remain exclusions. Histories share a 2018 warmup and January 4, 2021–October 12,
2026 portfolio calendar. This is a current-cohort retrospective study, not a
survivorship-free historical security master.

After the operator explicitly allowed usable histories beyond that pool, the
wider published catalog supplied USO. The extension reviewed 54 funds and tested
51. USO binds to batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`,
truncated to the same October 12 endpoint. The original 50 input arrays and all six
FR25 control NAV paths are exactly unchanged. No within-series splicing occurred.
USO's published audit has complete raw/adjusted coverage, the expected fund name
and no unresolved historical names; identity remains provider-based, not a
certified security master or recorder/broker admission. Its futures-fund return
is not spot oil. See [USCF's objective](https://www.uscfinvestments.com/uso).

Each pool has 486 fixed scenario replays, 18 continuous walk-forward replays and
72 candidate/control inference contrasts. Three-year trailing selection for
2024/2025/2026 requires return/drawdown guards, higher net Sharpe, cost/delay
robustness and a passing neighboring variant. Holdings and cash continue through
annual switches; NAV is not spliced. The 2024+ block-bootstrap family intervals
are descriptive historical evidence, not untouched prospective validation.

## Findings

The following are the 51-ETF extension's primary adaptive/volume/heat/event rule,
net of 5 bp per traded side, January 2024–October 12, 2026:

| Portfolio | CAGR | Sharpe (rf=0) | Max drawdown | Mean exposure |
| --- | ---: | ---: | ---: | ---: |
| Selection factor | 1.96% | 1.440 | −1.88% | 57.96% |
| Standalone breakout | 9.23% | 1.413 | −4.63% | 46.45% |
| 80% FR25 / 20% breakout | 17.00% | 1.659 | −7.32% | 87.02% |
| 80% FR25 / 20% M1 control | 15.99% | 1.666 | −6.74% | 90.16% |
| Matched FR25 | 19.37% | 1.624 | −8.65% | 97.84% |

The standalone rule's full-period CAGR is only 4.76%, Sharpe 0.764 and drawdown
−10.69%. In 2024+, one extra execution session reduces CAGR from 9.23% to 6.42%;
20 bp plus that delay yields 2.99%, Sharpe 0.488 and drawdown −8.52%. Its actual
base turnover is 21.90 times annually, costing approximately 109.6 bp annually.
This is a measured net-performance tradeoff, not a cost-ceiling rejection.

There are 239 primary virtual entries since 2021, 238 closed. About 39.9% exceed
a simple 10 bp round-trip hurdle; 58.8% lose money before costs. The median gross
episode is −0.53%, median hold 16 sessions. Positive outliers can coexist with
many false signals; volume confirmation does not certify a true breakout.

GLD's September–October 2025 episode returned 13.73% gross, USO's March–April 2026
episode 37.52%, and XLE's January–April 2026 episode 30.38%. USO's June 2025 exit
lost 11.74% despite a tighter nominal stop, illustrating executable gap risk.
The primary rule has no new SOXX entries after June 2023 and misses most of its
later rally. It also exits gold early in several episodes. These counterexamples
are visible alongside the successful cases, rather than used to retune v1.

No contrast has a positive 95% simultaneous mean-return lower bound in either
pool's 72-comparison family. Walk-forward standalone selection mostly falls back
to M1 and earns 1.60% in 2024+; the tilt selector earns 16.05%. Selection/control
results are partly bill dominated: the report includes BIL-relative Sharpe and
exposure so zero-risk-free Sharpe is not mistaken for an alpha discovery.

Disposition: retain the mathematical/engineering prototype and findings, with
**no demonstrated incremental edge or optimal exit**. A new version could study
failed-entry recovery and trend continuation, with new predeclared rules and
later validation. Do not tune this version to the displayed peaks. BNO/DBO/USL/OILK
and alternative gold/semiconductor ETFs remain future data-admission work; ingest,
audit, verify identity/coverage and publish before studying them. No reminder or
agent-owned recurring strategy calculation was created.

## Implementation and verification

- `src/systematic_trading/research/range_breakout.py`: causal shared factor,
  portfolio construction and theoretical-target adoption primitives.
- `scripts/run_range_breakout.py`: one frozen input/source snapshot, compact
  arrays, signals and shared-engine replay; resumes through the frozen runner.
- `scripts/extend_range_breakout.py`: explicit USO data extension.
- `scripts/analyze_range_breakout.py`: selection, bootstrap, full report and charts.
- `scripts/verify_range_breakout.py`: accepted restricted native LEAN checks.

Four representative native checks (original FR25/trading/tilt and extended
trading) match the study NAV exactly, with full native/Python parity. Native
two-CPU/4-GiB isolation and runtime/acceptance hash checks remain active. The first
native orchestration attempt failed before launch because the frozen source tree
had no deployment configuration; the exact accepted config was then bound with
a receipt. No runtime acceptance check was weakened.

The focused regression set initially passed 34 tests, including 13 new factor
tests. Later acceptance also checks chronological selection, data-extension
identity and all artifacts. Original and extension artifacts occupy approximately
164 MiB together at initial acceptance, including native evidence. No full
source bundle is created per scenario. Retain compact findings, source/runner,
protocols and receipts under the repository storage policy.

Rerun (PowerShell, from the repository):

```powershell
.\.venv\Scripts\python.exe scripts/run_range_breakout.py prepare
.\.venv\Scripts\python.exe scripts/run_range_breakout.py signals
.\.venv\Scripts\python.exe scripts/run_range_breakout.py replay
.\.venv\Scripts\python.exe scripts/extend_range_breakout.py
.\.venv\Scripts\python.exe scripts/verify_range_breakout.py
.\.venv\Scripts\python.exe scripts/verify_range_breakout.py --root var/research/range-breakout-uso-20261018-v1 --only trading
.\.venv\Scripts\python.exe scripts/analyze_range_breakout.py
```

Research context: [Brock, Lakonishok and LeBaron (1992)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1992.tb04681.x)
studied trading-range rules; [CME's pattern discussion](https://www.cmegroup.com/education/courses/technical-analysis/technical-patterns-reversals)
describes confirmation. These references motivate testable definitions, not the
parameter values or a claim of profitability for this factor.
