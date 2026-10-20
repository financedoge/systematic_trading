# Research State

Current conclusions and review queue, updated October 19, 2026. Detailed historical
entries are preserved in the [verified history archive](archive/README.md).
The [research plan](signal-decay-and-alpha-plan.md) controls sequencing; the
[execution Kanban](execution-kanban.md) tracks open implementation work.

## Authority and input rules

- Storage/memory now take priority over exact replay of archived exploratory work.
  Retain compact findings, definitions/runners and retirement receipts; bulky outputs
  and study-only snapshots may be discarded. Protect current monitored/funded/pending
  strategies, active studies, promotion inputs and operational evidence. A new run
  after input retirement is new evidence on a new audited batch. See the
  [retention and native migration plan](storage-retention-and-windows-native-plan.md).

- The operator retired the 44 bp annual research cost ceiling on October 17. Judge
  incremental returns after incremental costs, net Sharpe and Calmar, return/drawdown
  guards, cost/delay sensitivity and chronological stability. Cost and IC-margin
  screens are diagnostics, not net-performance verdicts. See the [rejection audit](research-cost-policy-review-2026-10-17.md).

- Monitoring is application-owned: versioned signals, scheduled rebalances,
  target/held weights, daily NAV and the shared benchmark/decision-flow report.
  Monitoring, SOTA designation, funding and order approval are separate authorities.
- The last recorded operational acceptance (October 12) has F3 at 100% paper
  capital, control revision 5, no pending allocation. This is a dated receipt,
  not a replacement for current transactional strategy-control state. Config
  seeds membership; operator lifecycle events override it.
- Live routing remains disabled. Paper allocation changes still require verified
  strategy/input identity, fresh account reconciliation and the existing approval flow.
- New ETF, feature and momentum research uses the full supported candidate pool
  and pinned, hash-verified published histories. Admission never requires allocation.
  Do not repeat standalone XLE/XLB-only studies without an explicit request.
- Always test dynamic rebalancing as an explicit option alongside a fixed-interval
  control in future strategy, ETF, feature and portfolio-construction research.
  Predeclare candidates and compare net Sharpe, return/drawdown guardrails,
  turnover/costs, delay sensitivity and chronological robustness. Target-change
  triggers use latest theoretical versus last adopted targets, including cash;
  adopted versus actual held remains Trading housekeeping. P4.22/P4.23's monthly
  outcome applies to the tested recipes and universes, not every future strategy.
- Use adjusted prices for returns and separately audited raw prices/volume for
  traded-activity signals. Preserve missing coverage, source identity and vintage
  limitations. Provider archives are inspection/governance evidence only.
- Price auditing does not prove historical publication availability. Legacy FX
  through September 24 remains uncertified; later CNH calculations require verified
  observed FX. Do not present the entire research input stack as fully audited.

## Accepted findings

Active operator direction: GLD first, then extend the same parameterized algorithm to
other ETFs one component at a time. The GLD lifecycle has now been re-fitted with every
behavioral threshold fitted on pre-2023 sessions; its 2023-2026 evaluation is a
development retest. The 2023 crossing-to-entry gap is closed (crossing 2023-03-13, entry
2023-03-14), the five-session progress exit is gone, and the exit is a fitted dynamic
take-profit from the recent high. A long-range sibling with 126-756 session ranges and
much larger stops/trails was then fitted on pre-2023 only, and the two sleeves are
sufficiently uncorrelated out-of-sample (0.338) for a predeclared 50/50 combination to
halve parent drawdown. Both horizons were then fitted per ETF across the full 52-ETF pool
and tested as an asset-selection rule: the lifecycle signals generalise (short evidence
52/52, long 47/52) but no standalone selection rule beats FR25 SOTA; the 80/20 FR25
lifecycle tilt is a modest risk-shaping control. Two daily event-driven constructions
(equal re-split when a new entry fires, and a 1/6-slot CTA style with a BIL government leg)
were then tested: both work mechanically but return 8.5%/7.2% CAGR at Sharpe 0.94/0.85, do
not beat the benchmarks, and their cash leg never activates because the permissive per-ETF
fits keep at least six simultaneous signals. A final conditioning pass then deepened the
per-ETF fit with an explicit pre-2023 two-era stability rule (25/52 short and 9/52 long
sleeves pass) and used the stable state only as a monthly eligibility filter on FR25/M1.
The eligibility filter failed its matched random-filter test (15.79%/1.30 versus 15.0-18.6%/
1.31-1.44 for random removal; worse under cost/delay), so that route is retired. The
pre-2023-calibrated conditional 20% Rule A short-only overlay gives 16.01%/1.478/-7.67%
versus FR25 16.75%/1.469/-8.65%: a marginal risk-shaping improvement, not a SOTA
replacement. The overlay was then rebuilt as one portfolio in the shared engine with every
inter-sleeve trade and execution delay charged. The dynamic target-change (10% L1) variant
gives 16.08%/1.479/-7.64%/Calmar 2.10 at 5bp and beats FR25 on all four risk-adjusted
measures at 5bp, 10bp and 20bp (CAGR -0.66pp at 5bp), beats the unconditional and
random-condition controls, and beats the fixed-monthly conditional control on DD/Calmar. It
fails the +1-session delay test (Sharpe 1.39 vs matched FR25 1.41). It is retained only as a
research candidate for monitoring review; adding it to monitoring requires an app-tracked
versioned strategy, paper-trading evidence, resolution of the delay weakness, risk limits,
operator approval and a rollback plan, none of which is done here. The fitted procedure
itself failed a 2005-2015 refit validation on 2016-2022 in both GLD domains, so per-ETF pool
fitting must keep the two-era stability requirement and a shared-parameter fallback. Daily
trading remains the operator's execution clock for this research line; preserve the
pre-2023 fit / 2023+ evaluation chronology. Already inspected dates are development retests.

| Work | Current conclusion | Evidence |
| --- | --- | --- |
| Cost-charged conditional FR25 overlay and monitoring candidate | The conditional 80/20 FR25 + Rule A short-only overlay was rebuilt as one portfolio in the shared engine so every intra/inter-sleeve trade and execution delay is explicit. Dynamic target-change (10% L1) candidate at 5bp: CAGR 16.08%, Sharpe 1.479, Sortino 2.10, max DD −7.64%, Calmar 2.10, turnover 8.8× versus frozen FR25 16.75%/1.469/2.063/−8.65%/1.935. It beats FR25 on all four risk-adjusted measures at 5bp, 10bp and 20bp (CAGR −0.66pp at 5bp), beats the unconditional and random-condition controls on Sharpe/Sortino/maxDD/Calmar, and beats the fixed-monthly conditional control on DD/Calmar. It FAILS the +1-session delay test (Sharpe 1.39 vs matched FR25 1.41); delay sensitivity is the unresolved weakness. Kept as a research candidate for monitoring review only — no monitored strategy, allocation, funding, promotion or broker change; app-tracked versioned strategy, paper evidence, approval and rollback plan are prerequisites. The dynamic candidate has now been frozen as versioned package `fr25-lifecycle-conditional-v1` v1.0.0 with a full project-standard strategy page (spec, decision flow, cost/delay stress, latest target 2026-09-30 marked to 2026-10-12 close — condition ON, breadth 36/52, sleeve 20% across six life-cycle names, FR25 core 80%, cash 2%, rebalance ledger and promotion checklist). It also has an app-owned registered definition (`fr25_lifecycle_conditional_v1`, catalog), app-module calculation through the shared `DailyBacktestEngine` (947 sessions, 55 rebalances, CAGR 16.09% matching the 16.08% research page), tracked artifact and promotion record. Added to monitored on 2026-10-19: config membership plus app tracked publication (detail/report HTTP 200; 947 observations through 2026-10-12; CAGR 16.09%, Sharpe 1.479, max DD -7.64%). Status is Catching up because 23 of 52 pool ETFs lack audited app bars for 2026-10-13..16; allocation unavailable because the allocation contract supports monthly multi-asset strategies while this uses a dynamic clock. | [Candidate dossier](conditional-fr25-lifecycle-overlay-candidate-2026-10-19.md), [strategy page](../research/fr25-lifecycle-conditional-v1/index.html), [promotion record](../config/strategy-promotions/fr25-lifecycle-conditional-2026-10-19.json), [report](../research/gld-lifecycle-overlay-robustness-20261019-v1/index.html) |
| Two-era stable signals as FR25/M1 eligibility filter and conditional overlay | Deeper per-ETF refit (300 random + 60 anchor mutations, screened by worst of 2005-2015/2016-2022, top 20 across frictions) with a formal two-era stability requirement: 25/52 short-range and 9/52 long-range sleeves pass (2 fallbacks each). Using stable state only as monthly eligibility on FR25 while momentum ranks: union-renormalised filter 15.79%/1.302/−8.82% at 5bp versus frozen FR25 16.75%/1.469/−8.65%; matched random filters (same names removed) span 15.00–18.60%/1.31–1.44, so the filter has no demonstrated edge and degrades to 14.26%/1.192 with +1 delay. M1 conditioning immaterial. The pre-2023-calibrated conditional 20% Rule A short-only overlay gives 16.01%/1.478/−7.67% (Calmar 2.09) versus FR25 16.75%/1.469/−8.65% and unconditional overlay 15.54%/1.454/−7.67% — a marginal risk-shaping improvement, not a SOTA replacement; FR25-weak condition could not be calibrated (one pre-2023 FR25 rebalance). | [Findings](gld-lifecycle-conditioning-findings-2026-10-19.md), [report](../research/gld-lifecycle-conditioning-20261019-v1/index.html) |
| Daily life-cycle opportunity scanner / CTA portfolios | Two predeclared daily event rules on the 52-ETF pool using the sealed pre-2023 two-horizon signals. Rule A equal re-split: holdings persist to exits; new entry re-equalises the book (cap 6). Rule B 1/6-slot CTA: each entry one 1/6 slot, unused slots in BIL. 2023-2026 at 5bp: Rule A union 8.51%/0.94/−11.04%, Rule B 7.20%/0.85/−10.09%, best short-only variant 10.57%/1.04/−10.27%, versus FR25 16.75%/1.47/−8.65%, equal weight 14.74%/1.38, URTH 20.45%/1.40. Cash leg never activates (0% flat days, 83% full, avg 5.7 holdings) because the permissive per-ETF fits keep ≥6 simultaneous signals; cash-proxy choice (BIL/SHY/IEF) is irrelevant. Daily books are equity-like (corr 0.73 vs FR25). Not better than SOTA; entry selectivity is the binding constraint. | [Findings](gld-lifecycle-daily-scanner-findings-2026-10-19.md), [report](../research/gld-lifecycle-daily-scanner-20261019-v1/index.html) |
| Two-horizon lifecycle on the 52-ETF pool and versus FR25 | Both structural domains fitted independently per ETF on pre-2023 sessions (200 random + 40 GLD-anchor mutations + GLD vector; top 15 across 5/10/20bp and +1 delay); short evidence 52/52, long 47/52. Selection rules predeclared and replayed through the shared FR25 engine (FR25 path reproduced to 0.03%). 2023-2026, 5bp: FR25 SOTA CAGR 16.75%, Sharpe 1.47, DD −8.65%; best lifecycle-only rule R4 14.53%/1.00/−11.62% (monthly 14.09%/0.93); primary R1 7.35%/1.00/−8.62% monthly (4.46% event). 80/20 FR25+R1 monthly 14.86%/1.475/−7.53% — risk-shaping only. No standalone lifecycle selection beats FR25 on both CAGR and Sharpe; event adoption over-trades. | [Findings](gld-lifecycle-pool-findings-2026-10-19.md), [report](../research/gld-lifecycle-pool-20261019-v1/index.html) |
| GLD two-horizon lifecycle and combination | Same lifecycle algorithm, two predeclared structural domains. Long-range domain (126-756 session ranges, 4-20 ATR stops, 3-20 ATR trails, 0-504 session time limits) fitted on pre-2023 only: IS 8.02%/1.05/−12.52%, 2023-2026 development CAGR 11.65%/Sharpe 1.29/−11.35% (short-range 7.87%/0.86/−12.20%). Daily-return correlation short vs long is 0.338 OOS (0.998 when both long; diversification is time-in-market). Predeclared 50/50 independent half-accounts: OOS CAGR 9.62%, Sharpe 1.28, DD −6.64% vs parents 7.87%/0.86/−12.20% and 11.65%/1.29/−11.35%; robust to 20bp and +1 session delay. Long-range 2005-2015 refit validation also failed 2016-2022 (0.69%/0.12/−22.30%), so both horizons remain evidence-thin outside the inspected interval. No promotion or monitoring. | [Findings](gld-longrange-combination-findings-2026-10-19.md), [report](../research/gld-lifecycle-combination-20261019-v1/index.html) |
| GLD fitted range-breakout lifecycle | 24 fitted lifecycle parameters, 213,120 pre-2023 evaluations, sealed before the 2023+ read. The 2023 breakout is entered 2023-03-14 at $177.35 (crossing 2023-03-13) and exited by the dynamic take-profit 2023-04-14 at $185.89 (+4.82%), versus the earlier 8-close entry at $181.15 and five-session loss. IS 2005-2022 CAGR 9.21%, Sharpe 1.06, DD −13.28%; 2023-2026 development CAGR 7.87%, Sharpe 0.86, DD −12.20% versus buy-hold 23.75%/1.16/−26.40%. Frozen vector stable across both pre-2023 eras; a 2005-2015 refit validation failed on 2016-2022, and continuation re-entry was rejected on IS. The fitted range detector is short-horizon (30/35 entries use 21-63 sessions; no 252/504 entry), so the "stable for a while" premise is only partly implemented. No promotion or monitoring. | [Findings](gld-range-lifecycle-findings-2026-10-19.md), [report](../research/gld-lifecycle-20261019-v1/index.html) |
| GLD daily drill-down | 5,512 dated sessions with candidate ranges, confirmations, actual entries/exits and daily stop/time calculations. Seven 2024+ entries; all six completed trades exit on the five-session progress rule. Latest trail never activated: threshold $431.98 versus peak $428.07; stop $357.45. Inherited parameters under daily execution: CAGR −1.84%, Sharpe −0.229, DD −11.99%. 23 tests, report source checks and exact independent native daily parity (13 fills/701 NAVs). Numerical repair remains open; local-file browser QA blocked. | [Daily report](../research/gld-breakout-drilldown-20261018-v1/index.html) |
| Joint lifecycle calibration v3 | 33 parameters, 1,100,502 pre2023 evaluations; 2023 selects regularization/model/timing, 2024+ OOS. Return/Sharpe/Calmar 45/40/15 with soft holding/stop penalties. Selected GLD −0.19%, USO −4.11%, SOXX 42.72% CAGR; only5/52 beat buy-hold, no positive family bound versus buy-hold. Gold's five-session time exit misses the rally; 2023 selection is unstable. Equal-budget breakout 7.24%/8.39% trails momentum 10.11%/11.94%. 63 tests, 7,320 individual/204 pool scenarios, five exact native checks. No general validation or promotion. | [Report](../research/range-breakout-20261018-v3/index.html), [recipe](range-breakout-calibration-v2.md#joint-lifecycle-v3-follow-up) |
| Individual range/exit calibration v2 | 52 supported ETFs; 1,080 choices each, pre2023 fitting and2023+ OOS. Gold/SOXX capture more rally than v1, oil fails. OOS CAGR20.10%/−3.21%/32.11%; only2/52 beat buy-hold and15/52 beat shared parameters. BIL alone has a positive family-adjusted bound; BIL/cash dominates full-pool standalone construction. 47 tests and five exact native checks; no promotion. | [Definition/results](range-breakout-calibration-v2.md), [report](../research/range-breakout-20261018-v2/index.html) |
| Adaptive range-breakout lifecycle | Research prototype; no demonstrated incremental edge. Adaptive 42–756-session detection plus fixed 252/504 controls, volume/heat ablations, selection/trading/tilt, monthly/event timing. 50-ETF original and 51-ETF USO extension: 972 fixed +36 walk-forward replays, four exact native checks, 37 focused tests. Primary 2024+ trading CAGR 9.23%, Sharpe 1.413, DD −4.63% at 46.45% exposure; full-period CAGR 4.76%. Tilt 17.00% vs FR25 19.37%; no family-adjusted positive contrast. Includes failed signals and missed semiconductor/gold trends. | [Definition/findings](range-breakout-factor.md), [full report](../research/range-breakout-20261018-v1/index.html) |
| P4.16d cash-relative follow-up | Net replay reopened. Class-first monthly was withheld solely for 45.66 bp cost despite a 3.59x IC margin; no net-performance result exists yet. All 16 fixed mappings and matched controls will be compared with SOTA/monitored recipes. | [Rejection audit](research-cost-policy-review-2026-10-17.md), [historical findings](cash-relative-momentum-findings.md) |
| P4.16d class/volatility screen | Historical 16/16 proxy failures; all also missed the IC heuristic. Weak information and BIL/cash concentration remain diagnostics, but no net portfolio rejection is established. | [Historical findings](class-volatility-screen-findings.md) |
| P4.23 joint width/timing | The 6-by-8 search retains 6/monthly in all annual selections and the final window. FR25 monthly X=6/8/12: Sharpe 1.190/1.048/0.830, CAGR 13.05%/10.08%/6.96%, turnover 8.05×/7.01×/5.85×. Wider portfolios reduce turnover but do not qualify. Top four/monthly is an isolated early-window pass, rejected by neighbor stability. 588 scenarios, six native checks; current pools only. | [Joint results](../research/selection-width-timing-20261015-v1/results.md) |
| P4.22 target-change timing | With top six fixed, no threshold qualifies in the three annual selection windows or final trailing-three-year window. FR25 0.10: Sharpe 0.966 vs monthly 1.190; CAGR 10.05% vs 13.05%; drawdown -13.10% vs -8.66%; annual turnover 58.36× vs 8.05×. Explicit monthly macro fallback; F3 is legacy-basis sensitivity. 132 scenarios and six native checks completed. | [Results](../research/target-change-rebalance-20261015-v1/results.md) |
| P4.19 execution references | Retain execution policy. 27 complete orders, seven ETFs, five sessions: actual-fill cost 1.185 bps versus routed TWAP, 3.769 versus close, 9.471 versus session VWAP, before fees. Reference differences are not achievable counterfactual fills; close sensitivity changes sign under session omission. | [Execution references](execution-reference-findings.md) |
| P4.19a collection | App-owned original/routed window and full-session collection, immutable attempts and separate reference audits. 34 windows and 30 sessions verified at acceptance. Eighteen filled orders lack complete executions; USO/DBB contracts and legacy windows remain gaps. This is retrospective diagnostic qualification, not continuous intraday research admission. | [Collection contract](execution-benchmark-collection.md) |
| FR25 selection | Frozen 75% M1 / 25% financial-ridge selection blend is monitored. Effect-size leads remain concentrated and retrospective; family-adjusted significance is absent. Part B placebo rank passes, but the registered retention interval fails. | [FR25 tracking](fr25-selection-tracking.md), [robustness](fr25-robustness-findings.md), [placebo](fr25-placebo-findings.md) |
| P4.17 Alpha101 | Corrected standalone screen: 0/16 passes. Corrected tilt gates: 4/3/3 passes at 5/10/20%. Fixed 5% monthly replay trails FR25 in return and Sharpe across six cost/delay scenarios; no incremental edge. Earlier 12/12/5 claims are superseded. | [Second review](strategy-review-2026-10-11.md), [corrections](alpha101-peer-review-corrections.md) |
| P4.18 exposure targeting | Fixed 10% / 63-session monthly rule rejected after 18 replays and native parity; all registered risk/return criteria fail. No parameter retuning on the inspected sample. | [Reviewed result](strategy-review-2026-10-11.md), frozen `var/research/volatility-target-20261011-v1/` |
| P4.16 construction | Defensive-cash fallback explains most of the original pooled control's advantage. Hierarchical K2 improves raw return while worsening concentration/drawdown; family-adjusted evidence remains inconclusive. | [Sleeves](sleeve-construction-findings.md), [hierarchy](hierarchical-construction-findings.md) |
| P4.13 decay | Base momentum monitoring exists; Alpha101 incremental diagnostics and promotion rules are separate work. No automatic promotion or trading authority follows a dashboard warning. | [Decay findings](signal-decay-findings.md), [turnover gate](turnover-gate.md) |

Corrected fixed-pair FR25 versus 5% Alpha101 results, January 4, 2021-October 8,
2026 at 5 bp: CAGR 13.091% versus 12.988%, Sharpe 1.193 versus 1.182,
maximum drawdown -8.656% versus -8.253%. Native parity and 70 monthly app/research
decisions are recorded in `var/research/strategy-review-20261011-v3/`. This is
already-inspected historical evidence, not an untouched holdout.

## Next work and blocked dependencies

**Operator-requested timing research: P4.22 and P4.23 completed:**
[Target-change rebalance protocol](target-change-rebalance-plan.md). Strategy events
compare the latest theoretical target with the last adopted target; Trading alone
handles latest adopted versus actual held. The operator chose net Sharpe with
return/drawdown guardrails and explicitly scoped the first study to the current
FR25/14 and F3/12 pools, with full-supported-pool validation later. Use unchanged
signals/models, eight frozen thresholds, monthly/daily controls and chronological
selection. P4.22 retained monthly. P4.23 jointly searched maximum selected count X
and target-change threshold n, including wider selections and larger thresholds,
with a frozen [6-by-8 grid](../research/selection-width-timing-20261015-v1/protocol.json).
The annual selectors and final selector retained top-six monthly. Wider selection
reduced traded notional, but also reduced net return and Sharpe in the current
FR25 pool. F3 followed the FR25-selected calendar; it was not separately optimized.
Full-pool validation remains a separate qualified-parent study, not evidence
established by these current-pool results. Conditional bootstrap intervals do not
provide selection-aware formal superiority evidence.
The operator authorized previous-monthly macro snapshots when daily snapshots are
absent. Keep source dates and disclose the no-change/no-new-publication assumption.
No monitored or trading policy changed. This is a
separate timing hypothesis; it does not reopen or rescue the expanded-FR25 rejection.

1. P4.16d stage 1 was accepted and the 38-addition recorder wave is enabled.
   The first retrospective comparison reviewed all 52 candidates and used 50
   supported common-window histories. Expanded FR25 failed its frozen pre-test:
   67.73 bp annual implied cost against 44 bp, with rank IC −0.01463. Its portfolio
   replay was withheld. The original control passed; native 5/10 bp replays and
   URTH reconciled. [Full findings and attribution](etf-expansion-findings-2026-10-14.md).
   The October 16 and 17 screens withheld all mappings under old proxy rules.
   The operator removed the absolute-cost ceiling and requested retests before
   the next planned item. First: full net replays of the fixed cash-relative family
   and matched controls, including dynamic policies, against current SOTA FR25 and
   monitored strategies; report Sharpe and Calmar. Six standalone Alpha101 signals
   (24/26/46/49/53/54) were also excluded solely by cost and are queued separately.
   See the [audit](research-cost-policy-review-2026-10-17.md). The reserved prospective
   design remains inactive; current-cohort evidence is not historical membership.
   BWX and XOP retain listing holds; CPER is excluded from this study for an
   unsupported raw-volume observation. HYXU/EUHY remain separate quarantined
   regimes. [Inventory](etf-universe-inventory-2026-10-13.md).
2. P6.15: measure host/container working sets, copies and scheduling before scaling
   concurrency. Static web rendering improvements do not resolve this worker review.
3. The minimum 14-ETF paper execution contract and conditional 5% FR25 / 95% F3
   preview passed. Raw-share sizing, component union, financial/activity model
   binding and conId routing now share verified contracts. Existing funding stays
   F3 100%; a preview is not activation. [Execution evidence](execution-readiness-2026-10-13.md).
   Remaining P8 work covers general registry migration and additional markets.
4. Register the next alpha's horizon, peer group, incremental payoff, untouched
   validation period and actual fill-based exit contract before another budget/exit grid.
5. P5.11 intraday activation and stops require admitted continuous intraday histories
   and a separate execution contract. Sampled quotes and recovery captures do not qualify.

## Data and monitoring references

- [Governed prices](price-governance-2026-09-26.md) and [audited reruns](audited-research-rerun-2026-09-26.md).
- [App-owned tracked strategies](etf-activity-lag20-tracking.md), [rolling XGBoost](rolling-xgboost-lag20-tracking.md), [allocations](trading-allocations.md).
- [Economic vintages](economic-vintage-recorder.md): original publication assumptions
  and actual first capture remain distinct. CR's original economic feature subset is frozen.
- [Energy recorder](energy-fundamentals-recorder.md) and [issuer recorder](issuer-etf-recorder.md):
  current rolling histories cannot be backdated into old decisions. CFTC positioning
  measures futures categories, not ETF holdings or flows.
- [Intraday recovery](intraday-recovery.md): actual historical candles and incomplete
  delayed quote samples remain distinct; recovered data is unapproved raw evidence.
- [LEAN worker](lean-backtesting.md): engineering parity is required evidence but
  does not repair historical input limitations or grant execution authority.
