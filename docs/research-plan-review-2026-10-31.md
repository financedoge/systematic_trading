# Research-plan review — October 31, 2026

Operator disposition: cash-relative retained as research evidence October31;
Alpha54/the six-signal experiment retained November1. Both discussion checkpoints
are resolved. P4.20 evidence/decay governance is complete, and the operator
continued November2. Expanded FR25, breadth and stability follow-ups, and the
class/volatility net replay completed November3. Stop at the class/volatility
discussion. The [research guidelines](research-stability-guidelines.md) retain
the operator's lessons from the prior discussion.

The programme is **not complete**. The controlling research queue is
[signal decay and alpha](signal-decay-and-alpha-plan.md), amended by the
[October 17 cost-policy decision](research-cost-policy-review-2026-10-17.md)
and the subsequent operator-directed trend/BroadTrend branch. Completed negative
experiments count as completed work; a diagnostic that withheld portfolio replay
does not establish a net-performance verdict.

## Reconciled status

| Workstream | Status | Evidence / remaining boundary |
| --- | --- | --- |
| P4.13–P4.19 original programme | Completed experiments/diagnostics | Signal decay, FR25 robustness/placebos, sleeve/hierarchical construction, corrected Alpha101 screen/tilt/replay and fixed volatility targeting. Follow the corrected [second review](strategy-review-2026-10-11.md), not superseded exit/budget optima. |
| P4.19 execution timing | Scoped retrospective comparison complete | [27 orders, seven ETFs, five sessions](execution-reference-findings.md); insufficient to establish achievable execution-style superiority or continuous intraday admission. |
| P4.22/P4.23 timing and width | Complete | Monthly, then top-six/monthly retained in the original FR25/F3 universe; not a universal calendar-only conclusion. [Protocol/results](target-change-rebalance-plan.md). |
| P4.16d inventory and first publication wave | Delivered; broader expansion partial | 299 symbol/regime inventory, 38 additions plus original 14; published-history and identity holds remain explicit. Historical membership/mandate reconstruction and broader tradable-universe acceptance remain open. |
| P4.16d expanded FR25 net replay | **Complete November3; stop for discussion** | 144 cases,52 histories,63 tests,nine monthly policy checks,three exact native accounting checks. Monthly selected; higher later return but weaker Sharpe/drawdown than original14, no net superiority established. [Report](../research/expanded-fr25-net-20261102-v1/index.html). |
| P4.16d class/volatility construction | **Net replay complete November 3** | All 16 constructions/timings at six frictions on each of two audited batches. Selected pooled risk/monthly passed 6/6 matched guards IS and 0/6 later. [Full report](../research/class-vol-net-20261103-v1/index.html). |
| P4.16d fixed cash-relative net retest | **Complete; retained as research evidence by operator** | 126 cases, 35 tests, three native LEAN accounting checks, exact published-pool reconstruction and 5,698 reproduced adoptions. [Full report](../research/cash-relative-net-20261031-v1/results.md). |
| Six cost-excluded standalone Alpha101 signals | **Complete; retained as research evidence November1** | 24/26/46/49/53/54, 52 supported histories,222 cases,55 tests/one optional skip,three native checks. Monthly wins each training selection; Alpha54/monthly leads training, no robust guarded advantage across eras. [Full illustrated report](../research/alpha101-net-20261031-v1/index.html). |
| P4.20 evidence and decay review | **Complete November1; discussion resolved November2** | [Versioned policy, validator and worked Alpha54 review](research-evidence-governance-v1.md). Explicit sample reuse/decay states; no universal half-life/IC/cost veto or automatic authority.37 tests pass,one Windows skip. |
| P4.21 constituent alpha | Coverage assessment, December pilot and MDY inventory complete. Historical replay blocked. | [December pilot](../research/p421-quarter-20261104-v1/results.md) and [November 5 weighted inventory](../research/p421-mdy-inventory-20261105-v1/results.md). Existing observations cover much of the review population. Source, action and dated identity qualification remain open. |
| Single-ETF trend/reviewer branch | Closed by operator direction | [Synthesis](trend-sleeve-synthesis-2026-10-29.md); retain symmetric trend sleeves, not a universal winning model. |
| N15/N20/N30 portfolio tests | Complete | [Width comparison](trend-sleeve-width-2026-10-29.md); unranked full pool has stronger primary Sharpe; no width optimum established. |
| BroadTrend strategy and 70/30 blend | Complete implementation and historical comparison | [Specification](broadtrend-strategy-v1.md), [blend report](broadtrend-fr25-comparison-2026-10-29.md). App-owned monitoring published; unfunded; blend did not pass the FR25 return guards. Prospective evidence requires time. |
| P6.15 worker resources | Native cutover and implementation complete; measurement follow-up remains | October 18 native acceptance, October 30 CPU scheduling, October 31 removal of fixed memory defaults supersede Docker-era backlog text. Component speedups are measured; whole-refresh latency remains a separate measurement. |
| P8.1–P8.5 execution readiness | Minimum US-listed USD ETF boundary passed | [Acceptance](execution-readiness-2026-10-13.md); general registry migration and additional market/FX/lot contracts remain partial or blocked. |
| P5.11 intraday activation/stops | Blocked platform work | Requires admitted continuous intraday research histories plus execution/risk/reconciliation contracts. Recovery coverage is not research admission. |

The running app was read only during this review. Its October 31 serving snapshot
reports price/NAV freshness through October 30 and seven currently monitored
strategies. This supersedes the older catch-up warning for that observation time;
it is not a guarantee of future feed availability. Membership is application state,
not the older config seed or historical count. No operational controls were changed.

## Cash-relative item — retained as research evidence

The fixed class-first/monthly cash-relative policy was selected on 2021–2024.
For January 2, 2025–October 12, 2026 at 5 bp with next-open fills:

| Policy | Net return | Sharpe | Maximum drawdown | Calmar |
| --- | ---: | ---: | ---: | ---: |
| Cash-relative class/monthly | 56.36% | 1.474 | 12.36% | 2.330 |
| Matched removal-only control | 36.46% | 1.176 | 12.01% | 1.603 |
| Frozen common-input FR25 | 55.80% | 2.072 | 8.31% | 3.436 |

The candidate improves the matching control in all six later friction settings,
but only three of six calibration settings. It passes zero of six guarded FR25
comparisons in each period. Family-adjusted Sharpe/CAGR-difference intervals
include zero. Benefits concentrate in 2024–2026; 2022/2023 worsen versus removal-only.
Dynamic 0.10 is stronger later but weaker during training, so it was not selected.

Weakest **actual net contribution / opening portfolio NAV** under the selected
policy: EWH −2.46 percentage points in calibration, XLE −1.98 points later.
This explicit portfolio criterion accounts for changing allocations; it is not
an invented standalone ETF return. Both inspections show prices, raw volume,
adopted/held weights, actual fills, protection absence and dated trade outcomes.

[Open the illustrated report](../research/cash-relative-net-20261031-v1/index.html)
or [read the results](../research/cash-relative-net-20261031-v1/results.md).
Current monitored strategies are included as same-date USD context, separately
labelled because their input vintages and model histories differ.

**Operator decision:** retain cash-relative as research evidence and proceed with
the six-signal retest. The later dynamic result remains a hypothesis for a new
declared test, not authority to retune this one. No monitoring, funding or promotion.

## Alpha101 item — retained as research evidence November1

All six formulas selected monthly timing on2021–2024. Alpha54/monthly leads
training: net33.37%,Sharpe0.679,DD19.33%. Later2025–October30,2026:
net26.90%,CAGR13.97%,Sharpe1.569,DD7.54%, versus matching momentum
63.82%/31.13%/1.211/16.70% and FR25 55.26%/27.32%/2.013/8.31%.
All222 cases include actual costs and next-open/extra-session delay. No cost veto.
Selected-policy guards versus momentum6/6early,0/6later; unranked0/6,1/6;
FR25 0/6both. Family-adjusted uncertainty includes zero. This is retrospective
current-cohort evidence, not prospective confirmation; incumbent signal inputs differ.

Weakest actual net contribution/opening NAV: EWY−3.12ppcalibration,
XLC−1.70pplater. [Open all results and inspections](../research/alpha101-net-20261031-v1/index.html).
55 focused tests pass, one optional historical-artifact test skipped, three native
accounting checks match to the cent. The operator retained the completed study as
research evidence, with no standalone candidate promoted. Concern about selecting
on reused evaluation is incorporated into P4.20. Unequal cumulative-return periods
are clarified: Alpha54 annualized return7.49%early/13.97%later, not deterioration.

## Previous discussion — completed P4.20 governance

[Evidence/decay policy](research-evidence-governance-v1.md) separates inspectable
evidence, scientific net verdict and operational authority. The worked Alpha54
dossier is reviewable retained evidence, with unidentifiable lifetime and explicit
additional diagnostic work before any new recipe. No new strategy results or
operational changes. The two completed studies' bulk folders are classified for
routine guarded retirement; compact findings and recipes remain.

The operator resolved this checkpoint by asking to continue November2.

## Expanded FR25 net replay and breadth follow-up

[Full report](../research/expanded-fr25-net-20261102-v1/index.html) retains both eras,
all timing/cost/delay cases, uncertainty and EWC/XLK weakest inspections. Expanded
FR25 fails original14's guarded comparison in all six cases in each era, despite
its higher later return. This completes the withheld net replay; it does not
establish FR25 as a universal benchmark or prove the larger pool is unhelpful.

The operator requested a like-for-like percentage fallback and expanded M,N search.
The [completed follow-up](../research/fr25-breadth-20261103-v1/index.html) froze
42/33 on 2021–2024 before its later replay. Six slots with a 4/14 breadth rule
matched the original fallback frequency, lowered IS Sharpe and produced the same
later monthly target decisions as fixed four. Stop for this discussion.
The operator subsequently requested the winner-dependence and stability comparison,
retained the resulting guidelines and continued. The class/volatility net replay
is now complete. The operator continued November 4 and the constituent-coverage
assessment and the subsequent December filing pilot are complete. Stop at the pilot discussion. P4.21 still
requires admissible historical holdings, dated security identities and
sufficient constituent prices. The withheld-replay queue is complete, while
the wider programme retains data and platform work.
