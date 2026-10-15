# Target change rebalance backtest plan

Registered October 15, 2026 as **P4.22**, protocol `target-change-rebalance-20261015-v1`.
Status: executed with the separately recorded [operator amendment](../research/target-change-rebalance-20261015-v1/execution-amendment.json).
[Results](../research/target-change-rebalance-20261015-v1/results.md): all annual
selectors and the final candidate retain monthly. No monitored strategy changed.
The separately registered [joint X/n extension](../research/selection-width-timing-20261015-v1/results.md)
also completed and retained top-six monthly across all chronological selections.
The original registered protocol remains immutable. The operator selected
**net Sharpe with return/drawdown guardrails** and explicitly requested the current
FR25 and F3 universes first, with full-supported-pool validation later.

The question is whether adopting materially changed theoretical targets between
monthly rebalances improves net performance. Only the rebalance policy changes.
The machine-readable [protocol](../research/target-change-rebalance-20261015-v1/protocol.json)
records the proposed constants. Freeze its hash and verified execution inputs
before the first run; any subsequent design change requires a new version.

## Two independent decisions

Let `q[t]` be the latest valid theoretical target, `a[t-1]` the last target adopted
by the strategy, and `h[t]` the account's actual marked holdings. All vectors
include every instrument in the strategy's frozen universe and a cash component.

| Decision | Distance | Owner and use |
| --- | --- | --- |
| Strategy target adoption | `S[t] = sum(abs(q[t,i] - a[t-1,i]))` | Strategy/analytics service; the only threshold optimized in this study. |
| Trading alignment | `H[t] = sum(abs(a[t,i] - h[t,i]))` | Trading section; housekeeping against the latest adopted target. Outside this study's trigger and parameter search. |

The operator confirmed that “latest versus held” means **latest adopted versus
held**, not an unadopted indicative target. The existing paper policy is an
individual-ETF 0.02 drift test rather than this displayed aggregate distance;
this plan does not replace, tune or activate that policy. Portfolio holdings,
cash, fees and price drift still enter backtest accounting and order sizing.
They never feed back into `S[t]` or reset its anchor.

Examples: moving a theoretical target from 50/50 to 55/45 gives `S=0.10`.
Moving 5% from an ETF to cash also gives `S=0.10`. This is target distance,
not realized turnover: actual trades can differ because holdings have drifted.
An unchanged theoretical target cannot trigger an additional strategy rebalance
merely because prices moved. Repeated small target changes accumulate relative
to the last adopted target, not yesterday's unadopted target.

## Exact event rule

1. After each completed US session, calculate `q[t]` with the existing app
   evaluator and only information available by that decision cutoff. Preserve
   the existing model-fit schedules, feature windows, fallbacks, caps and cash rules.
2. Establish the initial target at the first eligible decision. Thereafter adopt
   `q[t]` on the normal month-end decision, or when `S[t] > x`. Equality does not
   trigger. Compare full-precision decimal weights without display rounding.
3. A month-end and threshold breach on the same date create one event. Record
   both reasons, with monthly as the primary reason. Monthly events remain due
   even when the target vector is unchanged. An extra event does not move the
   next monthly date.
4. On an adoption event set `a[t]=q[t]`; otherwise retain `a[t]=a[t-1]` and hold
   shares. The anchor changes on the strategy decision, independently of fills.
   An event producing no whole-unit orders still adopts its target. Failed or
   missing target computation never advances the anchor.
5. Execute the frozen event at the next session's open in the base simulation.
   Delayed execution uses the same event targets and dates of knowledge; it does
   not recalculate the target or use future prices to decide the event. Process
   delayed events chronologically, at most one event per decision day. An event
   awaiting execution at the data boundary remains pending and receives no
   invented fill or return.

The strategy event stream is therefore reproducible without a broker account.
Pending orders, partial fills, rejected orders and operational retries belong to
Trading and cannot silently adopt a new strategy target. Any later deployment
must bind orders to the adopted target version and retain its existing controls.

## Strategies and comparison arms

**Primary selection:** `research_fr25_14_v1`, all 14 current candidates: DBC,
EWH, EWJ, EWY, GLD, HYG, IEF, LQD, MCHI, SPY, TLT, VGK, XLB and XLE.
**Transfer check:** `research_fallback_f3_v1`, its complete current 12-candidate
pool, the same list without XLB/XLE. Use the exact effective app evaluator,
including audited raw activity, and freeze definitions and calculation source.
F3 receives the thresholds selected using FR25; do not pick a different F3 winner
after inspecting its results. Its fixed-grid surface remains a disclosed diagnostic.

This is the operator-authorized, timing-only exception to the default expanded-pool
research scope. It cannot establish portability to the larger universe. The
previous expanded-FR25 rejection remains valid; full-pool confirmation must use a
separately qualified parent and cannot retune that rejected arm to rescue it.

| Arm | Rule | Role |
| --- | --- | --- |
| Monthly | Existing monthly target adoption and rebalance; shares held between events | Primary matched control; also the fallback if no threshold qualifies. |
| Daily full | Adopt and rebalance to `q[t]` every valid session, even if unchanged | Maximum-frequency reference; not a threshold candidate. |
| Monthly plus target change | Monthly rule plus `S[t] > x` | Eight candidates: **0.025, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40**. |
| URTH | Buy and hold, matched funding and dates | Context benchmark; never used to select the threshold. |

There is no held-weight trigger arm, threshold-only calendar replacement, cooldown
search, partial rebalance fraction, new risk overlay or daily model refitting in v1.
In particular, `x=0` with a strict inequality would mean target-change-only
events, not the daily-full control; do not conflate those implementations.

## Data and accounting contract

- Evaluation: **January 4, 2021 through October 14, 2026**. Funding precedes the
  first fill; include establishment costs and the first return/drawdown observation.
  Preserve sufficient published prehistory for existing model fitting and feature
  warmup. Do not fabricate a longer cash-only history for an unavailable model.
- Pin the currently identified published price batch
  `ad78b10e053829e5fd2d0d18fc82c2c572cb1901a1cc1bdecd01fb727bfa6472`.
  This planning reference was read from the app, not independently re-certified.
  Preparation must resolve its immutable catalog, verify every used file hash,
  and freeze model, USD and financial-vintage receipts and source/dependency hashes.
  A missing or changed input stops preparation; never silently use `latest`.
- Use dividend/split-adjusted USD OHLC for return accounting and separately
  audited raw close/raw volume for activity signals. Join by identity and date.
  A missing required observation invalidates the decision/run; only the existing
  strategy's explicitly defined signal abstention may substitute its parent rule.
  Do not forward-fill prices, splice sources, read provider archives or fetch prices
  online. This session's paper download is literature, not a research data source.
- USD 1,000,000 initial capital; cash earns zero. Use the current whole-adjusted-unit
  accounting convention, disclosed as simulated units rather than historical raw
  broker shares. No uncertified historical CNH FX enters the primary comparison.
- Next-session open fills, with prior-close sizing and the app's sell-first,
  affordability, rounding and fee accounting. Held shares drift between events.
  The delay scenario adds one trading session, with order sizing from the close
  immediately before the delayed execution, while retaining the original target.
- Charge **5, 10 and 20 bp per actual traded notional**, including sells and buys,
  with **zero or one extra session of delay**: six fixed scenarios. The primary
  score is 5 bp/no extra delay. These are friction assumptions, not observed spreads
  or proof of an achievable TWAP. Do not charge costs on target L1 or on cash twice.
- Run the frozen chosen policy and controls at USD 100,000 as a separate rounding/
  account-size diagnostic; do not re-optimize at the smaller capital size.

Published revised prices do not establish historical publication availability.
Current-cohort survivorship, economic archive assumptions and actual first-capture
rules remain explicit. Record the actual earliest valid decision for each parent.
If the declared interval cannot be supported, report the gap before changing it.

## Chronological threshold selection

Generate each parent's valid daily target tape once, then replay the fixed policies.
Monthly fitting remains causal: no incomplete forward label or future model may
enter an earlier prediction. Shared monthly event targets must reproduce the
existing application strategy exactly before testing extra event dates.

| Selection data, inclusive | Subsequent validation interval |
| --- | --- |
| 2021-01-04 to 2023-12-29 | 2024 trading sessions |
| 2022-01-03 to 2024-12-31 | 2025 trading sessions |
| 2023-01-03 to 2025-12-31 | 2026 sessions through October 14 |

Each annual threshold is selected using only its preceding three-calendar-year
window. Candidate accounting runs continuously from the common initial funding;
score only the indicated window, including drawdown from its opening NAV. The
walk-forward account follows monthly through 2023, then uses the chosen threshold
from the first monthly event of each validation year. Carry cash, positions and
adopted targets across year boundaries, charge every transition trade, and do not
splice independent candidate NAV curves or reset funding annually. F3 follows the
same selected threshold calendar using its own target and accounting state.

The periods are chronological validation for this new policy, but the underlying
strategies and historical markets have already been inspected. They are **not an
untouched holdout**. Label fixed-threshold whole-sample winners as descriptive
in-sample maxima, never as the chosen optimal threshold.

## Selection objective and guardrails

The operator chose net Sharpe with return/drawdown guardrails. The following
numeric tolerances are declared design choices, not empirically optimized values:

| Criterion versus the same parent's monthly control | Requirement |
| --- | --- |
| Net Sharpe, zero cash-rate convention | At least **+0.05** in the selection window at 5 bp/no extra delay. |
| Net CAGR | No more than **0.50 percentage point/year** below monthly. |
| Maximum drawdown magnitude | No more than **2.00 percentage points** worse than monthly. |
| Two training stress checks | At 10 bp/no delay and 5 bp/one extra session, positive Sharpe improvement and the same CAGR/drawdown limits. |
| Neighbor support | At least one immediately neighboring threshold in the declared grid also passes all the criteria above. |

Among eligible candidates with neighbor support, retain those within **0.02 net
Sharpe** of the best. Select the one with the **lowest actual annual traded
notional/NAV** at the primary cost; break an exact tie with the larger threshold.
This identifies a stable region instead of automatically selecting a narrow peak.
If none qualifies, select monthly. Undefined Sharpe, inadequate coverage or failed
accounting never counts as a pass. All costs and guardrails use matched dates.

Do not assume a larger threshold always reduces realized turnover: event paths
and full-target resets can change. Keep the full response curve and event ledger.
Existing promotion/turnover policies remain separate. Report the 44 bp research
affordability benchmark, but do not silently apply its monthly calibration as a
validated daily pre-test or relax it to qualify a result. A useful backtest does
not itself amend that policy or authorize allocation.

## Validation, uncertainty and the eventual candidate

Report the stitched 2024-2026 walk-forward result and every annual fold, alongside
the full fixed-grid surface. A candidate is retained for prospective observation
only if walk-forward Sharpe improves by at least 0.05, aggregate return/drawdown
guardrails pass, Sharpe improves in at least two of the three validation folds,
and the two stress checks still pass in aggregate. Require the selected threshold
to improve F3's aggregate walk-forward Sharpe and meet its guardrails before
claiming transfer to F3; failure does not permit reselecting on F3.

Use paired stationary-block bootstrap intervals for Sharpe and mean net-return
differences: 20,000 replicates, seed 20261015, expected block length 63 sessions;
21/126-session blocks are declared sensitivity checks. Resample aligned parent,
candidate and benchmark return rows together. Disclose that intervals for the
realized walk-forward policy are conditional on its selected threshold sequence.
For any formal superiority claims, use a selection-aware resampling procedure
that repeats the registered selector within each replicate; if that is not
implemented, the evidence remains descriptive. Correct the declared family of
18 primary comparisons (eight fixed thresholds and one walk-forward policy for
each of two parents) with Holm adjustment. Do not choose the best block length,
cost scenario or parent after seeing the results.

After historical review, use the same selector on the trailing three-year window
from October 16, 2023 (the first session on or after October 15) through October 14,
2026 to name **one fixed FR25 candidate threshold**, or monthly.
Freeze it before prospective observation. Do not call a threshold appearing most
often in the retrospective folds the optimum, and do not retune during the
prospective period. The eventual result may legitimately be “retain monthly.”
Prospective evaluation starts at the first completed session after the candidate
is frozen, with at least 126 sessions before its first performance review; that
duration alone does not establish significance. Full-supported-pool validation
follows separately with a qualified parent and the chosen timing rule frozen.

## Implementation and acceptance checks

Implement the event policy as a pure, versioned strategy/analytics component using
the existing target services; no agent scheduler or broker state in the calculation.
Expose indicative target, last adopted target, distance, threshold, decision reason,
pending target version and next monthly date in the common strategy report. Keep
adopted-target versus actual-held diagnostics in Trading.

Before interpreting performance, verify:

- Unchanged targets plus large price drift create no extra event; small successive
  target moves accumulate against the last adopted vector. Cash changes and exits
  count, equality does not trigger, and symbol ordering is irrelevant.
- Monthly and threshold events deduplicate; unchanged monthly targets still
  rebalance. Initial establishment, missing inputs, zero-order events, holidays,
  month/year boundaries and pending final-window events have explicit outcomes.
- Changing holdings, funding, fees or fill delays cannot change the strategy event
  tape. Execution prices and costs affect quantities/NAV only. Future-data
  perturbations cannot change earlier signals, models, selections or events.
- No repeated daily order requests between events. Fees, cash, positions and
  constituent contributions reconcile to NAV, including initial costs.
- Monthly controls reproduce the app's decisions/accounting. Independently
  verify event decisions and native LEAN/Python fills, quantities, cash and NAV
  for both controls and each selected walk-forward policy; parity of accounting
  alone cannot validate a shared erroneous event schedule.

Required artifacts: sealed protocol/input/source hashes, daily target tape,
adoption/event ledger with old/new anchors, fills and costs, NAV, all thresholds
and cost/delay scenarios, yearly selections with reasons, full-portfolio
constituent attribution, and common SOTA-format reports/decision flow. Include
rebalance count/year, holding times, five-session reversal trades, gross/net
returns, Sharpe, CAGR, drawdown, exposure and liquidity diagnostics. Never report
only the winning threshold. Run a bounded pilot before scaling worker concurrency.

This session delivers the plan and reference. The next implementation step is
input freezing, monthly-control reproduction and event-policy tests; no new
strategy is monitored, funded or routed by registering this plan.

## Literature reference

Gârleanu, Nicolae, and Lasse Heje Pedersen (2013), *Dynamic Trading with
Predictable Returns and Transaction Costs*, The Journal of Finance 68(6),
2309-2340, DOI [10.1111/jofi.12080](https://doi.org/10.1111/jofi.12080).
[Downloaded journal PDF](../research/references/supplemental/T01_dynamic_trading_with_predictable_returns_and_transaction_costs.pdf).

The paper motivates accounting for forecast persistence and trading costs.
Its quadratic-cost model derives gradual movement toward a forward-looking
portfolio; it does not derive our target-to-target L1 band or an ETF threshold.
Treat v1 as a separate empirical test, not a replication of that model.
