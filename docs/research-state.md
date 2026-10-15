# Research State

Current conclusions and review queue, updated October 15, 2026. Detailed historical
entries are preserved in the [verified history archive](archive/README.md).
The [research plan](signal-decay-and-alpha-plan.md) controls sequencing; the
[execution Kanban](execution-kanban.md) tracks open implementation work.

## Authority and input rules

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

| Work | Current conclusion | Evidence |
| --- | --- | --- |
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
   Next: separately specify the accepted class/volatility-aware design; do not
   tune this rejected arm or treat current-cohort evidence as historical membership.
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
