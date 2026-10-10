# Research State

## Next research phase — registered 2026-10-10

The next phase is the [signal decay and alpha plan](signal-decay-and-alpha-plan.md),
registered as `P4.13`–`P4.21`. It starts with **signal decay and IC
instrumentation** and an **FR25 robustness stress**, neither of which needs new
data, before any Alpha101 work.

Two conclusions from reviewing the Alpha101 paper are frozen into that plan.
First, of the 101 formulaic alphas, 49 cannot be computed with the data we hold
(43 need `vwap`, 18 an industry classification, one market capitalisation), 83
contain a cross-sectional operator, and only **16 are both implementable and free
of a cross-sectional operator**. Second, the paper's own Table 1 puts the median
alpha at a 2.10-session holding period and ~120× annual one-way turnover —
roughly **6.0% a year at our frozen 5bp**, against the current strategy's ~8× and
~0.4% — and its published figures exclude transaction costs. Alpha101 is
therefore usable only as a restricted feature set at the selection layer, behind
measured turnover and decay, never as an unconditional daily overlay.

Intraday signal activation and stop-loss execution is registered as a platform
workstream (`P5.11`), not research. There is no published intraday data and no
intraday execution stack.

Work proceeds **one item at a time, with a review and reflection between items**.

## Standing research scope — updated 2026-10-10

At the user's direction, future ETF, feature and momentum research uses the full
candidate pool. Do not repeat XLE/XLB-only model tests or make those two ETFs'
forecast errors the basis for judging full-pool signals. Whole-portfolio asset
attribution remains useful; preserve historical subgroup evidence without
extending that standalone test program. Assets compete in the candidate pool;
none is forced into the portfolio. A failed portfolio-recipe screen is distinct
from rejecting the underlying predictive signal.

## 2026-10-10 — FR25 authorized for application-owned monitoring

The user authorized monitoring the frozen FR25 selector as
`research_fr25_14_v1`. The application now fits the financial ridge monthly,
blends 75% M1 rank with 25% financial total-return rank before the positive
126-session gate and top-six selection, and publishes scheduled and indicative
targets, fills, daily NAV, held weights, the matched benchmark and the full
shared report with an inspectable rank table.

Research parity was verified against the frozen selection-blend protocol
`5399931f5267d8beceb1ff52b15d84a81547f4f1e8a285a413bace7702769276`: 130
decisions, 898 fills, 2,707 daily NAV observations, 130 model fits and matching
final positions. Membership generation 4, membership revision 4. Evidence:
`var/research/fr25-monitoring-20261010/`.

That parity is bound to audited price batch `4bfdef17…`; the live runtime revision
calculates on the newer committed batch `b02d9372…`, so the two are distinct
evidence versions of the same frozen recipe rather than bit-identical outputs.
Parity claims must name their batch.

This authorization does not upgrade the evidence. FR25 remains an
already-inspected retrospective candidate that passed practical effect-size,
mean-only, cost/delay and risk-budget screens but **no** 5% Holm contrast across
the 50-comparison family, with recent substitutions concentrating its advantage.
Monitoring is not promotion: allocation readiness stays false, the 14-ETF
execution gate stays closed, and no capital, approval, reconciliation or broker
authority changes. The contract is in
[FR25 tracked strategy](../docs/fr25-selection-tracking.md).

## 2026-10-10 — Predictive ranks moved into full-pool selection

Executed the user's requested momentum/XGBoost/ridge selection comparison.
The fixed full14 candidate pool ranks the existing M1 score (75% momentum,
25% volume), causal XGBoost forecasts and context/financial ridge total-return
forecasts on the same midrank scale. Ten predeclared blends: two M/X blends,
four M/R or M/X/R blends for each ridge group. Positive126 eligibility,
top6/min4, defensive fallback, inverse-volatility sizing and downstream controls
remain fixed. Primary arms keep the existing XGBoost sizing tilt and add no
economic sizing overlay. Final45 cap is controlled separately against exact
M1. Eight same-availability training-mean controls, three XGBoost-placement
controls, two matched-target-gross controls and seven references complete the
30-arm experiment. Required-ridge gaps revert the whole selector to M1;
missing XGBoost fails closed. No model or parameter refits after registration.

| Fresh-cash 2021–2026-10-08, 5bp | CAGR | Sharpe | Calmar | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| CP: capped M1 control | 11.92% | 1.106 | 1.435 | -8.31% |
| Context ridge sizing only | 12.09% | 1.122 | 1.436 | -8.42% |
| Financial ridge sizing only | 12.03% | 1.108 | 1.425 | -8.44% |
| CR50: 50% M1 / 50% context rank | 12.49% | 1.171 | 1.533 | -8.14% |
| FR25: 75% M1 / 25% financial rank | 13.09% | 1.193 | 1.512 | -8.66% |
| X25: 75% M1 / 25% XGBoost rank | 12.56% | 1.159 | 1.448 | -8.67% |
| CEQ: equal M1/XGBoost/context | 11.10% | 1.058 | 1.288 | -8.62% |
| FEQ: equal M1/XGBoost/financial | 12.95% | 1.192 | 1.427 | -9.07% |

CR50 and FR25 pass the frozen +0.05 Sharpe/+0.05 Calmar effect-size screen,
the CAGR/drawdown budgets, matched mean-only checks and positive cost/delay
comparisons. CR50 improves Sharpe/Calmar +0.065/+0.099; FR25 +0.087/+0.078.
This is a materially larger portfolio effect than the corresponding sizing
overlays. Neither leading selection blend uses XGBoost in its selector; both
retain XGBoost downstream. Increasing XGBoost's selection share to50% weakens
Sharpe to1.003. Equal blending is not generally superior. Removing the existing
XGBoost sizing tilt does not improve either equal blend.

FR25 is the stronger long-history lead: 2016+ CAGR/Sharpe rise from CP's
10.65%/1.062 to11.21%/1.109; max drawdown worsens -19.49%→-19.83%.
CR50's full-history CAGR/Sharpe are10.55%/1.061, with -20.95% drawdown.
FEQ's full-history drawdown reaches -30.46%, despite strong2021+ return.
Retain CR50 as a secondary evaluation-period lead, not a stable full-history
improvement. All results remain retrospective and the weights were chosen
from a predeclared finite menu, not an independent holdout.

FR25 changes13/70 selections, one replacement each; eight entering ETFs beat
the displaced name in the subsequent rebalance-open interval, with mean
entrant advantage2.60pp. Mean target gross changes only+0.040pp; annual traded
notional drops8.59×→8.07×. July2026 TLT→XLE and August2026 HYG→EWY correspond
to+1.974pp/+1.670pp actual calendar net outperformance. October2024 HYG→TLT
loses-1.157pp. FR25's2026 net annual-return advantage is+4.552pp, making recent
decision concentration a material limitation. CR50 changes35/70 selections,
with17 positive equal-weight entrant/exit outcomes; portfolio sizing and
timing still matter. Its+5.012pp2021 gain contrasts with-1.709pp2022 and
-1.402pp2023. These are attribution examples within the full pool.

No registered contrast passes5% Holm across the50-comparison return family at
3/6/12-month blocks. FR25's six-month Sharpe-difference interval is
[-0.026,+0.226], CR50's[-0.070,+0.246]. No statistically robust superiority
claim or promotion follows from the practical screen. Equal-blend target-gross
controls match CP on all70 evaluation decisions but do not establish matched
volatility/factor risk. No new universe/threshold/weight search was added after
seeing these results.

Disposition: freeze FR25 as the primary selection-research candidate and CR50
as secondary for prospective and concentration robustness evidence. Do not
retune the inspected sample. Monitoring and funded allocation were not changed;
any future monitored version must be a complete app-owned strategy. New sector
release-history qualification remains separately queued; standalone SPY stays
deferred. [Complete results and interactive rank tables](../research/selection-blend-2026-10-10/index.html).
Evidence: `var/research/selection-blend-20261010-v1/`; protocol SHA-256
`5399931f5267d8beceb1ff52b15d84a81547f4f1e8a285a413bace7702769276`.

Validation: 240 economic replays, 30 native engine checks, 54 exact control
reproductions, 72 inference jobs and 18 focused tests pass. Independent exact
rational ranks verify 40,040 cells and 2,990 selection/gate/cap/label contracts.
Poisoning current/future prices and future models does not change prior-close
decisions. All 30 shared reports, local links, source hashes and JavaScript
syntax pass; a local DOM harness exercises 1,540 rank-table states. Browser
automation blocks local file URLs, so no browser-interaction pass is claimed.
Static charts were visually inspected. Acceptance is in `acceptance.json`.

## 2026-10-10 — Full-pool IC diagnosis: retain signal leads, distinguish recipe failure

The user's IC challenge prompted a frozen diagnostic follow-up, using all 14
candidates and the exact prior models/decisions/net ledgers. No refitting,
parameter search, new strategy arm or market-data ingestion was performed.
The earlier XLE/XLB-only MAE discussion does not decide the full-pool question.
The original recipe-retention failure remains valid, but rejecting economic
information itself would overstate that evidence.

| Ridge model | Full-pool total IC | Training-mean IC | Macro-increment IC | Partial rank IC* |
| --- | ---: | ---: | ---: | ---: |
| Context | 0.1182 | 0.0435 | 0.0887 | 0.0836 |
| Financial | 0.1188 | 0.0706 | 0.1213 | 0.0985 |
| Combined | 0.1152 | 0.0435 | 0.1003 | 0.0960 |

*Descriptive correlation after controlling ranks for training means and M1
selection scores. Context/combined have 58 complete labels; financial has 69.
All three total-IC marginal intervals are positive with 3/6/12-month calendar
blocks. Financial/combined increment intervals are also individually positive.
Paired improvement over the mean baseline remains uncertain; none of the 12
incremental-IC tests passes 5% Holm. This is suggestive ranking evidence,
not established incremental alpha or independent prospective validation.

The implementation preserves the existing selected members and cash budget;
it thresholds macro increments into 0.9/1.0/1.1 multipliers rather than using
total forecast ranks. Context changes 40/70 decisions: 12 unavailable, six
all-cash, two single-holding and ten uniform-multiplier months cannot change
weights. Mean capital shifted is 1.74% overall, 3.04% when changed. On identical
months with at least three positive targets, financial total IC declines from
0.130 across all 14 to 0.049 within held assets; context declines 0.138→0.108.
This is a selection diagnostic of the full pool, not a separate universe test.

Context contributes +0.167pp CAGR, +0.0162 Sharpe and +0.0010 Calmar versus CP.
Its Sharpe gain decomposes into +0.0137 from arithmetic mean return and +0.0025
from lower volatility. Its Calmar gain from higher CAGR (+0.0202) is nearly
cancelled by a worse maximum drawdown (-0.0192). Annual cost changes are near
zero or favorable, so costs are not the primary obstacle. Financial's higher
volatility offsets most of its mean-return Sharpe benefit.

Context adds +0.625pp net calendar return in 2024, but -0.022pp in 2023.
Financial adds +0.943pp in 2022 and subtracts -0.644pp in 2025. Context's April
2022 SPY underweight contributes positively; its April 2025 energy overweight
and gold underweight contribute negatively. During the common March 19–April 8,
2025 drawdown, all asset contributions reconcile to -11.1bp relative return:
XLE -23.9bp, partly offset by MCHI +12.0bp, GLD +3.1bp and other holdings.
Context's worst drawdown is -8.419% versus CP -8.308%, with recovery June 24
versus June 12. Predeclared trailing-trend/stress splits disagree across models
and are descriptive; do not turn them into tuned trading gates.

Disposition: retain context and financial ridge as signal-research leads;
combined has no demonstrated advantage over context, and trees have weaker
full-pool IC. The existing sizing recipes still fail their frozen screen.
Monitored M1/14/CR12 and funded F3 remain unchanged. Next proposed full-pool
experiment: freeze a finite comparison of rank-based selection/sizing versus
the current threshold overlay, including a historical-mean-only control,
matched risk/cash budgets, unchanged admission rules and prospective evidence.
Specify the experiment before running it; do not force assets or conduct an
open-ended search. Original-release sector-history qualification remains a
separate queued prerequisite for new data blocks; standalone SPY stays deferred.

[Diagnostic report](../research/full-pool-signal-diagnostics-2026-10-10/index.html).
Evidence: `var/research/full-pool-signal-diagnostics-20261010-v1/`.
Protocol SHA-256 `5f5467917cfe5bb4d46debd02bd1a2ddc73383e61244bf789073920392cf0f4a`.
Verified 10,677 parent-manifest entries, seven replay bundles, exact NAV/cash,
monthly asset attribution and peak/trough contribution reconciliation. Twelve
focused tests pass; no service, strategy or execution behavior changed.

## 2026-10-10 — Expanded-universe economic revisit completed

Executed the queued economic revisit once XLE/XLB and M1/14 were qualified.
The fixed M1 top-six candidate selector is unchanged. Seven overlay arms use
existing context (13), financial (8) and combined (21) features, per-ETF ridge
alpha 1 and depth-two/minimum-12-leaf trees. No feature, threshold or momentum
search was added. CP separately clips M1 targets above 45% and leaves the excess
in cash; all economic arms preserve CP's exact positive membership and cash.
The cap changes four of 130 monthly decisions, adding 0.183% average target cash.
No added ETF is forced into a portfolio.

| 2021-01-04–2026-10-08 | CAGR | Sharpe | Calmar | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| Unchanged M1/14 | 11.91% | 1.104 | 1.433 | -8.31% |
| CP: explicit cap-only control | 11.92% | 1.106 | 1.435 | -8.31% |
| Context ridge (CR) | 12.09% | 1.122 | 1.436 | -8.42% |
| Context tree (CT) | 11.94% | 1.109 | 1.406 | -8.49% |
| Financial ridge (FR) | 12.03% | 1.108 | 1.425 | -8.44% |
| Financial tree (FT) | 12.00% | 1.107 | 1.401 | -8.56% |
| Combined ridge (AR) | 12.04% | 1.115 | 1.443 | -8.34% |
| Combined tree (AT) | 11.83% | 1.094 | 1.331 | -8.88% |

USD, 5bp per traded dollar, zero-interest cash, fresh-cash evaluation. MR's
matched-context models/economics reproduce CR exactly; financial availability
does not remove further context-ready rows in this sample. The common October
8 cutoff is deliberately pinned to the preceding M1 study; later app prices
are not injected into this comparison. All history was previously inspected,
and M1 itself was selected retrospectively.

CR's matched-control gain is +0.167 percentage points CAGR, +0.0162 Sharpe and
about +0.0010 Calmar, below the registered +0.05 Sharpe/+0.05 Calmar threshold.
Its positive cost/delay comparisons do not override that shortfall. The
six-month-block 95% Sharpe-difference interval is [-0.0086,+0.0418]. The
twelve-month marginal Sharpe interval is positive, but Calmar and jointly
adjusted mean returns do not establish robust superiority. None of the 18
mean-return contrasts passes 5% Holm at 3/6/12-month blocks. Trees do not beat
their paired ridge controls; combined models do not beat matched context on
both risk ratios. No candidate passes the predeclared retention screen.

Prediction evidence also remains weak. XLE/XLB next-month return MAE is 5.79%
for context ridge versus 5.01% for the ETF-specific training mean, 5.39% versus
5.02% for financial ridge, and 6.53% versus 5.01% for combined ridge. These
paired samples differ by availability and are not interchangeable. Context and
combined models are ready on 58/70 evaluation decisions; financial models on
70/70. November 2025–October 2026 context abstentions remain intact, including
incomplete CPI windows. The latest capture never repairs an earlier gap.
Context ridge changes 40/70 allocations; XLE rises/falls in 6/10 months and XLB
in 3/17. Response signs are learned per ETF, not assumed from economic growth.

Full-history CR CAGR/Sharpe/DD are 10.73%/1.070/-19.59%, versus M1's
10.64%/1.061/-19.48%. FR weakens to 10.59%/1.051/-20.36%. Preserve these small
and inconsistent effects rather than retuning the same sample. Disposition:
reject these recipes for additional monitoring/promotion under the frozen
screen; keep monitored M1/14 and CR12 unchanged, and F3 funded. Next qualify
original-release sector/energy history before introducing new feature blocks.

Evidence: [13 complete shared reports and diagnostics](../research/expanded-economics-2026-10-10/index.html),
`var/research/expanded-economics-20261010-v1/`. Protocol SHA-256:
`9265c4e96c0a48bc17815b422eeab40f8de29e21a3c45b33e0ffb4950916100a`.
Audited price batch `4bfdef171ba1d180f2191c589d269a9ad42e2f497b9f069b80e1e9043668f3fd`;
economic batch `9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4`.
All 104 replays, 13 native checks, 57 inference jobs (10,000 draws each), 57
focused tests and 910 selection/cash/cap/label checks pass. All 130 feature
states reproduce from the original published snapshots; five portfolio controls
reproduce exactly. There are 520 model evaluations, of which 336 have sufficient
data to fit. Input/output/report hashes, links, JavaScript and plot checks pass.
Control revision 5, membership and all 270 order records are unchanged. The
independent app has advanced through October 9 with empty analytics errors.

## 2026-10-10 — Deferred standalone SPY idea

User requested continuing the next item and deferred SPY dip-buying for a later
standalone strategy study. Preserve it separately from the completed bounded
F3 cash-sleeve experiment; the latter is not a test of an independent SPY
strategy. No additional SPY threshold search or monitoring is authorized now.

The economic-model revisit after universe expansion is now completed above.
Historical EIA/CFTC/issuer feature qualification remains the next separate
data-dependent work item; its missing availability evidence is not bypassed.

## 2026-10-09 — P4.11 cash reserve and loser-basket study completed

Tested the user-authorized separate stress sleeve, including assets rejected
by F3's positive-momentum gate. Parent F3 and its original 12-ETF pool remain
exactly frozen. SPY, bottom three and top three use identical cash limits and
stress/confirmation rules; baskets freeze at first deployment. Bottom/top
ranking uses the existing pure 63/126/252-session momentum blend, without
volume or a positive gate. These are mixed-asset ETFs, not stock-level losers.

Monthly SPY drawdowns of 10/20/30% trigger equal tranches from one locked
dollar budget. Confirmation requires SMA63 and positive 21-session return.
Exit occurs at 95% of the entry peak or after twelve monthly intervals;
spent tranches cannot re-arm. Stage A uses existing F3 cash, capped at 20%
NAV. Separate Stage B cases scale F3 to 90%/80% and reserve 10%/20%. Both
ZERO cash and audited BIL parking are tested, with BIL capped at 45% and a
2% operational cash floor. No final cap is silently imposed on inherited F3.

| ZERO cash, 2021-01-04–2026-10-08 | CAGR | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: |
| Exact F3 | 10.58% | 1.062 | -11.69% |
| Existing cash, scheduled SPY | 10.79% | 1.068 | -10.75% |
| Existing cash, stress SPY | 10.76% | 1.072 | -10.84% |
| Existing cash, confirmed SPY | 10.65% | 1.064 | -11.36% |
| Existing cash, stress bottom three | 10.52% | 1.053 | -11.98% |
| Existing cash, stress top three | 10.58% | 1.059 | -11.70% |
| 10% fixed reserve / stress reserve | 9.51% / 9.60% | 1.060 / 1.067 | -10.57% / -10.14% |
| 20% fixed reserve / stress reserve | 8.45% / 8.63% | 1.059 / 1.070 | -9.44% / -8.57% |

USD, 5bp per traded dollar, fresh-cash evaluation; retrospective previously
inspected history. Fixed reserves cost 1.07/2.14pp CAGR; stress deployment
recovers only 0.09/0.18pp. BIL lowers the 10%/20% fixed-reserve drag to
0.79/1.58pp versus the same-parking parent, still outside the registered
0.5pp return-sacrifice budget for protection. Existing-cash SPY does not beat
scheduled deployment, so its modest parent improvement is not timing evidence.
Full-history Stage A drawdown stays near -16.42%; stress SPY CAGR is 10.01%
versus F3's 9.85%. Bottom-three full CAGR is 9.89%, weaker in evaluation.

Only three monthly market-stress episodes occur: January 2019, March 2020
and May 2022. Existing F3 cash funds two, and only the 2022 episode falls in
evaluation. It funds no 2020 sleeve because the parent had already invested.
In the 2022 full-history cycle, bottom-three MCHI/TLT/EWJ loses about $5,175
on a $323,152 locked budget, after falling as much as 13.57% of that budget;
SPY earns about $15,205 after a 5.91% budget loss. Budget denominators include
unused cash; these are sleeve P&L diagnostics, not asset-return drawdowns.

Disposition: reject the tested extra-reserve and loser-basket recipes for
progression under the frozen thresholds. Existing-cash SPY remains a small,
inconclusive effect below the worthwhile-improvement threshold. No comparison
passes either effect-size/protection screen or 5% Holm across the 46 contrasts
at 3/6/12-month blocks. This does not establish that reversal never works.
Do not optimize thresholds from these few episodes or promote a cash variant.
Retain M1/14 only under the separate monitoring authorization below. Next
research returns to unresolved data qualification and the already queued
information-signal work; combining failed cash recipes is not the next step.

Evidence: [complete study and 30 shared reports](../research/cash-stress-losers-2026-10-09/index.html),
`var/research/cash-stress-losers-20261009-v1/`. All 232 dynamic/frozen replays,
30 independent native checks and 141 inference jobs pass; 10,000 draws per
job. Exact F3 reproduction, paired phase-dollar reconciliation, lower-frequency
episode sensitivity, costs/delay, cash-proxy Sharpe and risk-matched URTH are
included. Protocol SHA-256:
`cc19d9f608c8484aedbf81afae41d3db9e696daed1f7f0b8be07d86760e10b4a`.
Audited price histories are reconstructed vintages, not proof of historical
publication availability. BIL is not broker interest; no uncertified FX is
used. Settlement timing/product permissions remain unqualified live inputs.

## 2026-10-09 — M1/14 added to app-owned monitoring

User authorized monitoring `research_m1_14_v1`: XLE/XLB join the original 12
candidates, with 21/63/126-session momentum and a positive 126-session gate.
Top six, minimum four and the F3 defensive-cash fallback remain unchanged.
No asset is mandatory. Audited raw dollar activity uses adjusted direction;
rolling XGBoost and USD models refit for this distinct pool.

The app's own service now publishes monthly rebalances, daily NAV/held weights,
October 9 indicative targets and the complete shared report/decision chart.
All 130 decisions, 907 fills and 2,707 daily values exactly reproduce the
registered research result. Nine native app checks pass, including the new
M1/14 and 14-ETF inverse-volatility benchmark. Existing USD economics remain
unchanged; all currently monitored entries are Current through October 8.
Monitoring is not promotion: M1/14 is ineligible for capital allocation until
its separate 14-ETF execution contract and promotion evidence are approved.
F3 remains funded at control revision 5; all 270 order records are unchanged.

Acceptance: `var/research/m114-monitoring-20261009/runtime-final.json`;
calculation revision `baad7794e23ccaeee3d359fd6c6ee0565d6873cfd60c67e9cc31ffb5e9e991c6`.
The historical candidate report below remains the selection evidence; its
earlier no-monitoring disposition is superseded only by this explicit user
authorization, not by a new claim of statistical superiority.

## 2026-10-09 — Corrected candidate-pool and momentum experiment completed

The user meant candidate-pool expansion throughout. The previous all-asset
inverse-volatility experiment answers a different question and cannot reject
adding XLE/XLB to the top-six selector. The corrected study adds no mandatory
allocation: four predeclared momentum policies × original 12 / expanded 14
candidates, retaining the six-slot limit and F3 defensive-cash fallback.

M0 is the existing 63/126/252-session ranking and positive 252-session gate.
M1 uses 21/63/126 and a positive 126-session gate. M2 excludes the most recent
21 sessions; M3 divides momentum by 63-session volatility. Ranking blend,
volume weight and other overlay parameters stay fixed. Shared XGBoost and USD
models refit causally for each pool, with one model schedule per pool reused
by all four policies. Audited raw dollar activity is used consistently in all
eight new arms; frozen legacy F3 is reproduced separately. That basis/refit
bridge moves full-history CAGR from 9.8458% to 9.8306%, not a pool effect.

| Rule / pool | 2016–2026 CAGR | Sharpe | Max drawdown | 2021+ CAGR | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 / 12 | 9.83% | 1.047 | -16.42% | 10.52% | 1.054 | -11.63% |
| M0 / 14 | 9.56% | 0.924 | -16.33% | 10.14% | 0.897 | -12.89% |
| M1 / 12 | 9.56% | 1.072 | -18.79% | 9.34% | 1.033 | -8.02% |
| M1 / 14 | 10.64% | 1.061 | -19.48% | 11.91% | 1.104 | -8.31% |
| M2 / 14 | 8.99% | 0.863 | -21.10% | 10.70% | 0.953 | -10.79% |
| M3 / 14 | 8.40% | 0.980 | -14.33% | 8.49% | 0.943 | -9.72% |

USD, 5bp per traded dollar, zero-interest cash, through October 8. The 2021+
period restarts from cash and is the registered chronological evaluation;
all history was previously inspected, so this is not an untouched holdout.
M0 selects XLE in 48/130 months (36.9%) and XLB in 59/130 (45.4%). Their
average held weights are 4.44% and 6.62%. M1 selects them in 48 and 63 months.
New candidates therefore enter often enough to matter, and can also change
cross-sectional ranks and model labels when not selected.

Disposition: unchanged-momentum expansion does not improve the observed
risk-adjusted results. M1/14 is a useful research lead, with a cost/delay-stable
2021+ advantage over M0/14, but deeper full-history drawdown and no convincing
paired evidence. Six-month block 95% interval for its Sharpe improvement over
M0/14 is [-0.083, +0.526]; all 11 mean-return contrasts fail 5% Holm across
3/6/12-month blocks. Its expansion benefit versus M1/12 also fails the combined
cost/delay Sharpe-and-Calmar check. No variant establishes a robust replacement;
no monitoring, promotion, strategy allocation or execution change.

Validation: 260 causal XGBoost fits, 94 accounting replays, 12 frozen-target
native LEAN parity checks, 36 uncertainty jobs (10,000 draws each), exact legacy
F3 fills/NAV/targets/positions reproduction, 65 focused tests, Ruff and input /
model / decision / output hashes. Control revision 5 and 270 order records
unchanged; analytics errors empty. Report assembly initially withheld publication
while native checks were pending, then finalized after all 12 passed.

[Complete comparison, selection frequencies, uncertainty and 12 full reports](../research/candidate-pool-momentum-2026-10-09/index.html).
Frozen evidence: `var/research/candidate-pool-momentum-20261009-v1/`.
Protocol SHA-256: `8242daf88c16cf28c8f12f16f68aafd84ff4ec71dfbc85d37cc0aa32acdfce60`.

Specification correction: current `research_fallback_f3_v1` does **not** include
a final 45% cap; that cap exists in some economic-study controls. F3 has the
incoming inverse-volatility cap and later active-weight constraints, but selection
and downstream overlays can produce final weights above 45%. This study preserves
the exact rule and reports concentration. P4.11 remains next on the original pool;
freeze exact current F3 as R0 and label any added cap as a separate intervention.

## 2026-10-09 — XLE/XLB admitted; first universe control rejected

Published common-cutoff XLE/XLB histories through October 8, 6,991 sessions each,
with issuer identity/listing validation and full hash readback. XOP is quarantined:
issuer listing June 23, 2006 conflicts with provider metadata/first bar June 22.
An explicit hold preserves the failed evidence without blocking other funds.
Read-only IB ISIN discovery verifies BIL/XLE/XOP/XLB identities; account/product
permission and settlement eligibility remain unverified. Holdings residuals and
split-aware issuance remain unresolved. [Admission evidence and study](issuer-etf-recorder.md#price-admission-and-first-universe-control--completed-2026-10-09).

Frozen 12-versus-14 ETF inverse-volatility control: adding XLE/XLB changes CAGR
5.73%→6.16%, Sharpe 0.748→0.753, Calmar 0.255→0.311 and maximum drawdown
-22.46%→-19.81% over 2016-01-04–2026-10-08 (USD, 5bp costs, zero cash interest).
The predeclared +0.05 Sharpe threshold fails; all paired block intervals include
zero. Cost/delay consistency passes, but does not override the failed screen.
Reject unchanged-sizing expansion; no claim about expanded F3/ranking follows.
Current F3 is a matched benchmark, exactly reproducing app economics.
All 14 replays, four native checks and three 10,000-draw uncertainty jobs passed.
Full shared reports include held/target weights, NAV, benchmarks and decision flow:
[research results](../research/energy-materials-universe-2026-10-09/index.html).

This previously inspected history and present-day ETF selection are retrospective,
not an untouched holdout. New arms use audited adjusted prices only; F3 retains
its disclosed inherited volume proxy. No new issuer/EIA/CFTC data is backdated,
and uncertified historical FX is excluded. Next: P4.11 on the retained current F3
and original universe, freezing cash economics and full-cycle deployment rules
before outcomes. Monitored definitions, capital and execution authority stay fixed.

Final runtime acceptance: all eight app native replays pass; five monitored
strategies are current through October 8 on revision
`1ef8c43dd057b1a0ed3c38dd2b331528da54be174e9985860cbd5a704cf4617d`.
Analytics is error-free with no freshness/startup flags; allocation calculation
status is OK, control revision 5 and 270 order records are unchanged. The separate
IB market-data recorder reports competing-session error 10197; no login/session
was changed to suppress it. Email delivery remains unconfigured.

## 2026-10-09 — Cash reserve and stress-deployment study queued

The user requested research on whether buying during market stress compensates
for cash drag and falling-knife risk. Execution item **P4.11** is Pending in the
[ETF roadmap](etf-research-expansion-roadmap.md#cash-reserve-and-stress-deployment--queued-2026-10-09),
after the current ETF admission and frozen universe-control milestone. First test
redeployment of existing capped-F3 defensive cash against unchanged and scheduled
re-entry controls; then compare 10%/20% additional reserves with ordinary
rebalancing, staged stress buying and recovery-confirmed deployment.

Freeze complete rules and acceptance tolerances before outcomes. Required evidence
covers full-cycle waiting/deployment/replenishment economics, matched exposure,
cash yield/FX qualification, crisis dependence, costs/delays, audited pinned inputs,
shared app calculations and native parity. Return enhancement and protection with
a return sacrifice are separate conclusions. This is queued research, not a new
backtest result, monitored definition, promotion or allocation change. Existing
issuer/ETF work continues and economic ridge retains its current freeze.

## 2026-10-09 — Prospective issuer ETF fundamentals recorded

The next recorder-first milestone is implemented for XLE, XOP and XLB. The app
captures issuer holdings, NAV/shares/AUM, valuation/growth statistics and industry
allocation every six hours, with independent fund publications and Market Data
→ ETF Fundamentals inspection. Eight statistics per ETF retain separate section
dates and actual capture times. First captures occurred October 8 at
16:21:59–16:22:06 UTC (October 9 local); October 7 issuer dates never grant earlier
availability. Hash-verified readers enforce strict cutoffs and feature-group
freshness/missing-data checks. See the [recorder and admission evidence](issuer-etf-recorder.md).

NAV/share/AUM reconciliation passes. All three holdings files have small
unexplained residuals to 100%, exceeding displayed-precision rounding. Preserve
their exact signed weights and missing sectors; show yellow warnings and reject
holdings-based features until reconciled. Shares are recorded, not labeled flows.
The issuer aggregates are not original historical analyst forecast vintages.

The current price catalog already contains XLE/XLB through September 25 with
explicit identity/availability/raw-basis limitations; XOP is absent. Next: common
cutoff price publication, issuer/security identity reconciliation, read-only IB
contract qualification, then a frozen expanded-universe control. No new backtest,
allocation or monitored-strategy change was made at this milestone.

Validation: 83 distinct focused tests pass; one opt-in disposable ClickHouse test
is skipped. Ruff, diff checks and browser selection/holdings inspection pass,
with no browser warnings/errors. Live publications, strict cutoff rejection,
feature-group isolation and preserved pins across application refresh were
verified. The guarded restart leaves analytics error-free and strategies current
through the latest completed US session, October 7.

## 2026-10-08 — EIA energy context recorded and published

The app now captures free official petroleum and natural-gas releases hourly
and exposes them in Market Data → Energy Data. The first publication contains
12 petroleum indicators (inventories, supply, demand and refinery activity) and
five Lower 48 gas-storage indicators, including separate net change and implied
flow. Both cover October 2. Petroleum was released October 7 at 14:30 UTC and
captured October 8 at 15:44:22 UTC; gas was released October 8 at 14:30 UTC and
captured at 15:44:30 UTC. Original raw bytes, revision flags, config/code hashes
and independently verified publication pins are retained.

The petroleum release's 314-row crude history is one current snapshot. It is
available only from capture, not from each observation date. The inspected
historical archive page had inconsistent date metadata, so original-release
archive admission remains unresolved. These inputs are physical context, not
proven leading signals or consensus surprises. Pinned readers enforce actual
first-seen cutoffs, freshness and missing-value checks. No historical return
experiment or Sharpe/Calmar claim has been made with this data.

The [recorder contract and next research stage](energy-fundamentals-recorder.md)
contains source qualification, exact publication pins and the proposed finite
per-ETF linear/tree comparison. Next: prospective issuer holdings/shares/NAV,
ETF identity/price admission, then a frozen expanded-universe control. Economic
ridge stays frozen until that universe revisit; single-stock trading is excluded.

Validation: 65 distinct focused recorder, publication, recovery and navigation
tests pass; Ruff and browser checks pass. Application-owned publications are
visible and source checks have no recorded error. No strategy allocation or
execution authority changed.

## 2026-10-08 — CFTC positioning recorder published; no historical backtest

Market Data → Fund Positioning now includes an app-owned, raw-first recorder for
the CFTC disaggregated futures-only reports. Six contracts cover WTI and natural
gas positioning plus COMEX gold/silver/copper and LME aluminum. The normalized
features report managed-money, producer/merchant and swap-dealer net-to-open-
interest ratios; original rows and publication hashes are retained. The audited
batch contains 1,903 reports beginning 2020-01-07 through September 29, 2026 for
five contracts. Aluminum has 143 reports through June 9, 2026. Initial catalog
revision: `406d59e27de2c63addef7ee832720ebb05102e9b3ebdad9c37993532f47ac9a6`.

The report date is Tuesday, while CFTC normally releases on Friday at 3:30 p.m.
Eastern and may delay around holidays. The API data rows do not prove their
actual historical release timestamps. Each row is therefore available to this
app only from its recorded `first_seen_at`; these first-captured historical rows
are not admissible for earlier strategy decisions or walk-forward training.
The repeat capture was byte-stable and idempotent. The CFTC classification is
managed futures trader positioning, not fund flows or ETF holdings. Linked ETFs
are not yet admitted by audited price coverage or IB account qualification, and
LME aluminum is only an indicator reference. No strategy inputs, backtest,
monitored strategy, allocation, or execution authority changed.

Files: `config/positioning-recorders.json`,
`src/systematic_trading/recorders/positioning.py`,
`research/etf-research-expansion-roadmap.md`. Next: qualify a point-in-time EIA
energy supply/demand recorder, then prospective issuer holdings/shares/NAV and
ETF price/identity records; only then freeze an ETF positioning/fundamental
comparison. National PMI, corporate bond spread rights, and dated consensus
remain separate source gaps.

## 2026-10-07 - Context ridge monitored; financial-condition combinations completed

On the user's explicit instruction, `research_economic_context_ridge_v1`
(Leading + payroll/inflation context · linear model) is now Monitored, generation
1. The exact economic-response v2 CR recipe is app-owned and remains frozen until
the ETF-universe revisit. Its full report is current through October 6: all 130
historical model decisions, 795 fills, 2,705 daily values and final positions
exactly match the prior study. Nine native monitored/control runs passed. Accepted
calculation revision:
`3ac2ba32ec1413383b849c589e7ccd7d593955e4adee3c7626025a57e169cc38`.
All five monitored strategies are current and allocation-ready. Monitoring did
not alter SOTA, capital, approvals or orders; allocation control revision remains
3 and the user's pending F3 handover is unchanged.

Latest economic features are incomplete, so CR correctly abstains to capped F3
and shows a yellow notice. Future decisions from October 8 require actual app
capture before the cutoff; archive restoration cannot backdate late observations.
During the first app calculation, the required October 5 vintages finished
publishing. The publication guard rejected the older calculation; the normal
retry completed on the final input subset. Both immutable attempts are retained.

Added Treasury slopes T10Y3M/T10Y2Y, Chicago Fed NFCICREDIT and SLOOS
DRTSCILM/DRTSCIS to the app recorder and Economic Data. Published all 2,112 planned
snapshots, preserving the original 1,441 entries exactly. Batch:
`9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4`.
The Treasury histories omit the initial January 2, 2006 holiday; it is disclosed
as unsupported, never filled. Internal gaps remain audit failures. NFCI is a
credit composite, not a corporate bond spread; corporate-spread storage rights,
national PMI and pre-release consensus remain access gaps.

The user additionally authorized combinations of the new economic inputs per
ETF. Frozen financial v1 tests eight financial features alone and all 21 original
plus financial features, each with separate per-ETF ridge and depth-two trees.
An original-context ridge matches the augmented training rows and availability.
All tilts apply to capped F3 directly and preserve its gross, cash and positive
membership. Prices remain on audited batch
`a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`;
vintages and labels obey the declared ex-ante contract with historical archive
availability limitations. No parameter or ETF search was performed.

January 2021–October 6, 2026, 5bp costs, USD, zero-interest cash:

| Recipe | CAGR | Sharpe | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| Frozen context ridge (CR) | 11.000% | 1.1027 | 0.9740 | -11.293% |
| Financial-only ridge (FR) | 11.102% | 1.1057 | 0.9798 | -11.332% |
| Financial-only tree (FT) | 11.066% | 1.0992 | 0.9534 | -11.606% |
| Augmented ridge (AR) | 11.040% | 1.1029 | 0.9753 | -11.320% |
| Augmented tree (AT) | 10.901% | 1.0877 | 0.9527 | -11.442% |

FR passes the fixed retention screen but its six-month-block Sharpe and Calmar
difference intervals versus CR include zero. No mean contrast passes 5% Holm
with three- or six-month blocks; FT versus P3 passes only the twelve-month-block
sensitivity (p=0.0204), while FT fails its linear and delay hurdles. AR fails
delayed Calmar. Both trees fail replacement screens. Full-history FR Sharpe
1.0619/Calmar 0.5845 trail CR 1.0703/0.5977, with drawdown 17.13% versus 16.83%.
All model combinations have worse prediction MAE than the ETF-specific training
mean. Retain FR as research evidence, no additional monitoring or promotion.

Financial features are ready on 130/130 historical decisions and models on
70/70 evaluation decisions. Augmented/matched models remain ready 58/70; matched
ridge reproduces CR exactly. FR changes 42/70 allocations: it increases SPY in
29 months, EWJ in 23 and DBC in 18, while also reducing assets conditionally.
These are model associations, not identified causal shock sensitivities.

Completed 51 replays, eleven native validations and 27 inference jobs on all 16
logical CPUs, with three memory-bounded native lanes. F0/F3/P3/CR full-period
controls reproduce exactly. 121 distinct focused monitoring, recorder, model,
reporting and integration tests passed; Ruff/whitespace and browser checks passed.
Evidence: `var/research/economic-monitoring-20261007/` and
`var/research/economic-financial-20261007-v1/`. Protocol SHA-256:
`7744d4585a435d4a5781d84eab4de0f7757e75e7198e00de9f8db83d1cd7d4fd`.
[Findings](../research/economic-financial-2026-10-07/findings.html) and
[complete assessment / reports](../research/economic-financial-2026-10-07/assessment.html).

Next: admit an expanded ETF universe through issuer identity and audited price
coverage; build prospective issuer holdings, shares outstanding and NAV records,
then a sector activity/growth/valuation/positioning pilot. Energy balances and
futures positioning require separate source and release-history qualification.
Revisit economic combinations once that universe exists; single stocks remain
out of scope. The independent legacy `lean-history` archive import is still
retrying a connection timeout; accepted monitored reports and economic
publications are complete. This is a separate archive-ingestion follow-up.

## 2026-10-07 - Completed economic asset-response experiment

Completed the broader eleven-series experiment after fixing allocation
preparation and deferred approval. Seven leading indicators and separate
payroll/output/headline/core inflation context feed per-ETF shallow trees and
ridge models. Original daily economic vintages, completed training labels,
training-only transforms and matched sample/availability controls enforce the
declared ex-ante contract. All inputs use published audited price batch
`a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`
and economic batch
`25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460`.
Historical dissemination limitations remain; app first capture is October 2026.

Primary evaluation: January 2021–October 6, 2026, USD, 5bp costs, zero-interest
cash. P3 (F3 with a 45% final target cap) gives CAGR 10.778%, Sharpe 1.0811,
Calmar 0.9220 and maximum drawdown 11.690%. Leading ridge gives
10.995% / 1.0896 / 0.9702 / 11.333%; combined ridge gives
11.000% / 1.1027 / 0.9740 / 11.293%. Both pass the finite cost/delay retention
screen. Trees fail to beat their paired linear models; combined tree also fails
delayed Sharpe. Original F3 remains reported at 10.740% / 1.0765 / 0.9185.

No paired mean-return contrast passes 5% Holm for any predeclared block length.
Combined ridge versus P3 has a positive marginal Sharpe interval but a Calmar
interval crossing zero. Combined ridge versus sample-matched leading ridge
adds only about 6bp CAGR and 0.0085 Sharpe. Full 2016-onward context lowers
combined ridge Calmar (0.5977 versus P3 0.6059); leading ridge lowers both ratios.
Forecast MAE worsens with context despite its small portfolio gain. Preserve
these limitations; retain linear candidates for further evidence, no promotion.

Leading features support 66/70 evaluation decisions; combined/matched support
58/70 and abstain November 2025–October 2026. No missing CPI observation was
filled from a later vintage. Models learn different signed associations and
increase as well as decrease ETF weights, but cannot add a beneficiary excluded
by parent eligibility or spend parent cash. Country-specific fundamentals,
national PMI, consensus surprises and expanded eligibility remain untested.

All 51 price/cost/delay replays, eleven primary native checks and 30 inference
jobs completed using the 16-CPU budget. Original full F0/F3 fills, NAV and final
positions reproduce exactly. Twenty-one focused tests passed. The retained v1
attempt stopped before portfolio replays on a 1e-28 Decimal sum difference;
v2 fixes arithmetic precision only, with no model or threshold change.

[Findings](../research/economic-response-2026-10-07/findings.html),
[complete assessment and eleven reports](../research/economic-response-2026-10-07/assessment.html),
[contract](economic-response-research.md); frozen receipts under
`var/research/economic-response-20261007-v2/`. Protocol SHA-256
`bd405774bb76310d0b8ddb9e2926435740a7088ba87f1dd80a224d09ed11165c`.
No new source, monitored recipe, funding or execution authority was introduced.
The user's separately saved F3 allocation remains pending for October 7 close,
control revision 3. Next: public yield/credit/lending vintage recorders, then
prospective issuer holdings/shares/NAV and a bounded sector-fundamental pilot.
Do not tune this batch further or use manually maintained monitoring cards.

## 2026-10-07 - Leading economic panel expansion

User broadened the economic work before the three-series portfolio experiment
was frozen or run: prioritize leading indicators, exclude GDP, use ex-ante
nonlinear predictions and allow different assets to benefit or suffer. Expanded
the app recorder from three to eleven series with 1,441 verified captures (131
per series). Preserved all original 393 captures and their hashes through an
explicit additive registry migration.

Seven leading candidates: claims, permits, manufacturing hours, temporary help,
core capital-goods orders, and Philadelphia Fed future orders/employment. Four
separate context series: payrolls, manufacturing output, headline CPI and core
CPI. Regional surveys are not national PMI; a leading business-cycle measure is
not automatically predictive of asset prices. User confirmed no existing data
subscription. Continue public-source work; national PMI and pre-release consensus
remain explicit access/availability gaps, alongside upcoming credit-condition,
country and sector recorders.

Published catalog `25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460`.
Readiness across 130 frozen decisions: leading group 126, context group 118,
combined group 118. Preserve unavailable readings. The conservative complete
13-month CPI window excludes ten 2026 decisions per CPI series because an
interior observation is missing; do not fill it from later history. Compare
context additions against leading models with matched training/availability
controls so differences in usable samples are not mistaken for feature value.

[Readiness report](../research/economic-leading-data-2026-10-07/assessment.html).
Frozen source, features and acceptance:
`var/research/economic-leading-panel-20261007-v2/`. The v1 attempt is retained as
incomplete after an audit adapter passed extra provenance fields to the reader;
the v2 repair did not change any source or feature formula. One transient source
404 recovered after the declared retry interval. 68 tests passed, one optional
skip; 22 real API history checks, source hashes, browser coverage and unchanged
four allocation-ready monitored strategies passed. Analytics errors cleared;
tracked revision and control revision 2 remain unchanged.

Next: implement the broader, bounded leading-only versus leading-plus-context
asset-specific tree/linear experiment on the pinned panel, with original-vintage
features, completed training labels, all-core replay, costs/delays and full shared
reports. The three-series overlay/model/study files remain an unfinished draft,
not a backtest result or registered strategy. No economic performance improvement,
promotion or funding change is claimed.

## 2026-10-07 — Economic vintage panel and revision sensitivity

The app now records ICSA (jobless claims), PERMIT (housing permits) and IPMAN
(manufacturing output), with 393 verified captures / 131 vintages per series in
**Market Data → Economic Data**. Catalog batch
`bd5668b74622858a88bdc0619ce02cc27a6f26b3d13570b55e61fea1da3c0682`
is pinned in `var/research/economic-panel-20261007-v1/input_pin.json`.

Against the frozen 130 monthly strategy decisions, five readings exceed freshness
limits (claims November 2025; permits December 2025–February 2026; manufacturing
December 2025). Preserve these as unavailable. There are 385 usable same-vintage
features; later revisions change the weakening flag in 13/129 claims, 4/127 permits
and 34/129 manufacturing measurements. Latest revised histories would therefore
change 51 flags in this fixed diagnostic. This is not a stock-return forecasting
result. No economic overlay was backtested or promoted.

Report: [economic data readiness](../research/economic-data-2026-10-07/assessment.html).
Contract: [economic vintage recorder](economic-vintage-recorder.md). The app owns
daily capture and catch-up; archive end-of-day availability and actual first capture
remain separate, with an explicit archive assumption required for historical use.
61 tests passed / one optional skip, source/API/browser acceptance passed; existing
SOTA, F3 monitoring and paper capital remain unchanged. Next freeze the small US-only
overlay, stale-data behavior and exposure/cost controls before outcome inspection.
Continue issuer holdings/shares/NAV and country/industry recorders separately.

## Treasury-bill recorder and F4 parking — 2026-10-07

Completed recorder-first BIL qualification and one predeclared F4 ablation.
Application-owned research ETF acquisition now captures issuer identity and
provider price/action evidence, audits complete coverage and revisions, verifies
ClickHouse rows/documents and commits the shared Market Data catalog. Failed
captures remain quarantined and retry after five minutes. Subsequent active-ETF
refreshes preserve the newly admitted series and its pinned storage batch.
Initial BIL coverage is 4,870 sessions, May 30, 2007–October 6, 2026; issuer
inception is May 25, 2007 and the unsupported initial days remain missing.
Published batch: `a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`.
The price/action audit is single-provider reconstruction, not certification of
historical dissemination, holdings, broker eligibility or interest terms.

Frozen `bill-parking-v1` retains F1's final risky ETF weights, adds BIL only below
four positive-momentum qualifiers, caps its target at 45% and reserves at least
2% cash. BIL exits on normal monthly breadth; no ranking/model change, cap search
or F3/BIL combination. Seven primary portfolios, 25 cost/delay replays and all
seven native accounting checks passed. F0/F1/F3 decisions, fills, daily NAV and
positions exactly reproduce all 12 matched prior cost/delay controls. Used 16
Python workers and three native lanes sharing 16 CPUs.

| Full 2016–October 6, 2026 / 5bp | CAGR | Sharpe, zero reference rate | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| F0 current SOTA | 9.779% | 0.9783 | 0.4425 | 22.097% |
| F1 qualifying ETFs + cash | 9.702% | 1.0339 | 0.5715 | 16.976% |
| F4 F1 + capped BIL | 9.841% | 1.0474 | 0.5856 | 16.804% |
| F3 qualifying defensive ETFs + cash | 9.931% | 1.0581 | 0.6048 | 16.420% |

F4 adds 13.9bp annualized return versus F1 at 5bp trading costs, 9.6bp at 20bp,
and 13.9bp with one extra execution session. It passes the fixed economic screen
but remains weaker than F3 overall. Eighteen decisions form only three episodes;
the largest benefit is in 2022–23, while early 2016 slightly loses after costs.
Holm-adjusted paired mean-return p-values versus F1 are 0.093/0.251/0.396 for
3/6/12-month blocks. Twelve-month ratio intervals include zero. Retain parking as
a modest cash-management component for future research, not an established alpha
improvement or replacement for F3. Cash earns zero; distributions enter through
adjusted prices; no broker cash-yield or untouched out-of-sample claim.

Assessment and seven full reports: `research/bill-parking-2026-10-07/assessment.html`.
Frozen inputs/economics/inference: `var/research/bill-parking-20261007-v1/`.
Protocol SHA-256: `4ac477e45428bf49704b28b5fcde306b9d8003fe0a510dacc544e8ac4af0f0a8`.
Relevant regression suite: 98 passed / one optional skip. Current SOTA, monitored
membership and capital remain unchanged. Next: macro release vintages and issuer
holdings/shares/NAV recorders, then a finite country/energy/sector fundamental
pilot. ETFs remain the trading boundary; no more unregistered ranking search.

## XGBoost ranking, exposure attribution and final target caps — 2026-10-07

Completed a second finite batch after the user asked to use XGBoost predictions
for top-6/8/10 selection instead of only a weight tilt. Protocol
`fallback-ranking-construction-v1` was frozen before the new outcomes: 16 primary
portfolios, 66 cost/delay/context replays and 15 registered contrasts. The model
target remains next-month adjusted USD return relative to the universe mean;
training, features and monthly model schedule were held fixed. All ranking arms
use the F3 defensive/cash fallback, the same positive 252-session eligibility gate
and later overlays. Price/volume rankings at each N and no-XGBoost-tilt controls
separate basket size, ranking and tilt removal. Top N is a maximum, never a
forced investment in rejected assets.

Common evaluation window: January 4, 2021–October 6, 2026, starting with USD 1m,
5bp trading costs, zero cash interest/reference rate. This window was already
inspected; no untouched holdout claim is made.

| Integration | CAGR | Sharpe | Calmar | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| F3 price/volume top 6 + XGBoost tilt | 10.74% | 1.076 | 0.919 | 11.69% |
| Forecast ranking top 6, no XGBoost tilt | 9.88% | 1.014 | 0.794 | 12.43% |
| Forecast ranking top 8, no XGBoost tilt | 7.69% | 0.888 | 0.626 | 12.28% |
| Forecast ranking top 10, no XGBoost tilt | 5.96% | 0.781 | 0.484 | 12.31% |
| Price/volume top 8 + XGBoost tilt | 7.46% | 0.864 | 0.616 | 12.10% |
| Price/volume top 10 + XGBoost tilt | 6.10% | 0.798 | 0.503 | 12.12% |

Forecast top 6 increases turnover from 5.87× to 7.93× annually and remains weaker
at 10/20bp and with an extra execution-session delay. Removing the XGBoost tilt
alone gives top-6 Sharpe 1.067; prediction-driven selection itself supplies no
improvement here. Average eligible-universe rank IC is 0.110 for XGBoost versus
0.233 for price/volume over 57 complete eligible months, a descriptive diagnostic.
All 15 paired mean-return tests fail the 5% Holm-adjusted threshold across
3/6/12-month block sensitivities. The six-month Sharpe-difference interval for
forecast top 6 minus F3 is [-0.189, +0.060]. Preserve the negative result;
do not replace the monitored recipe or widen its basket on this evidence.

The exposure control calibrated on 2016–2020 freezes its scale at 0.9151117.
It does not reproduce F3 protection (Sharpe 0.861, drawdown 20.40%). Matching
F3's monthly invested budget while keeping F0 composition produces almost the
same result as F3 (Sharpe 1.077 versus 1.076). Exposure timing explains much more
than defensive selection in this window, which contains only one fallback episode.
Neither result establishes future timing skill.

A separately tested 45% final target cap sends excess weight to cash. Full
2016–October 2026 F3 Sharpe changes only from 1.058 to 1.061 and CAGR from 9.931%
to 9.949%, while maximum held weight falls from 53.65% to 46.64%. Target weights
are capped at 45%; holding drift and execution gaps remain possible. Retain as a
risk-control candidate, not a demonstrated alpha improvement or an approved
portfolio change. No cap/ranking winner combination was searched.

All 130 original monthly targets reproduced exactly; full-history F0/F3 NAV,
fills and final positions match the prior study. All 16 primary native parity
checks passed. Used 16 Python workers (18.77 seconds) and three memory-bounded
native lanes sharing 16 CPUs (127.21 seconds). 39 focused tests passed. Inputs
remain the pinned audited adjusted-price batch
`9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e`, with verified
model/USD artifacts and explicit historical availability/volume/FX limitations.
No new source, recorder, monitored membership, SOTA, allocation or execution
authority change. The app's previous archive-ingestion warning has cleared.

Findings and all 16 standard reports:
[research assessment](../research/ranking-construction-2026-10-07/assessment.html).
Frozen evidence: `var/research/ranking-construction-20261007-v1/`.
Next: recorder-first Treasury-bill parking and macro/issuer/industry inputs from
the roadmap. A new momentum target or ranking-specific training objective needs
a separately frozen experiment; it was not tested here. Prospective F3 tracking
and operator promotion remain separate.

## Defensive-cash monitoring and strategy lifecycle — 2026-10-07

At the operator's request, **Qualifying defensive ETFs + cash** (`research_fallback_f3_v1`)
is now the fourth monitored strategy, with a complete application-calculated shared
report through October 6. Monitoring is separate from SOTA promotion, capital and
execution authority. Existing rolling XGBoost + activity + USD remains the SOTA
and 100% paper allocation at control revision 2; no pending change was added.

The new USD replay uses pinned published adjusted histories and verified model/USD
inputs, avoiding uncertified historical currency conversion. All 130 decisions,
2,705 daily values, 795 fills and final positions match the frozen F3 study exactly.
Four USD native runs passed execution/accounting parity. Standard report Sharpe is
1.0581, Calmar 0.6042 and maximum drawdown 16.42%; its calendar/anchor annualization
is 9.9207%, explaining the small rounding difference from the study's 9.93%.
These remain retrospective results from only three fallback episodes. Prospective
monitoring starts October 8, with no prospective observations yet. CNH portfolio
comparison uses only a separate exact-date verified FX bridge; raw USD NAV cannot
be substituted for CNH. No new data source was required.

Archive now pauses ongoing app calculations and retains the complete report.
Restore replays missed signals, scheduled trades, cash, holdings and daily NAV;
allocation remains blocked until the current membership generation is fully
published. Current SOTA, funded or pending-allocation strategies must be released
from those roles before archiving. Historical artifacts without an executable
recipe remain viewable but cannot be restored by merely relabelling them.

Publication: `19bcca6e344472ec1187f95635513e7c11de43f486636f21dc6ee937a72ef099`;
acceptance evidence: `var/research/strategy-lifecycle-20261007-*` and the publication's
`usd/study_comparison.json`. Next: operator promotion/allocation if desired, followed
by the already recorded prospective, matched-exposure and recorder-first F4 work.

## Fallback implementation and first results — 2026-10-07

Completed the authorized F0–F3 batch on the active rolling XGBoost/activity/USD
baseline, with 16-core independent calculations, 19 Python replays and four
native execution-parity checks. All 130 baseline monthly target schedules
reproduce exactly. Versioned cash/defensive fallback parameters and downstream
membership/gross-budget protection now use the shared backtest and paper target
pipeline; existing definitions retain the neutral policy.

At 5 bp costs and zero cash interest, USD Sharpe improves from 0.978 to
1.034/1.058/1.058 and Calmar from 0.443 to 0.572/0.604/0.605. Maximum drawdown
falls from 22.10% to 16.98%/16.42%/16.42%; CAGR is 9.78% versus
9.70%/9.92%/9.93%. Only three fallback episodes drive these results, with gains
concentrated in 2022–23 and missed gains in the earlier episodes. Paired return
uncertainty includes zero after multiple-comparison adjustment. Retain the
active strategy; preserve challengers for further validation, with no monitoring,
capital or execution-authority change.

Full interpretation, constraints, source hashes, costs, delayed execution,
episode attribution and next steps: [fallback results](../research/fallback-results-2026-10-07.md).
Immutable artifacts: `var/research/fallback-20261007-v1/`.

F4 remains unrun: neither BIL nor SGOV has admitted published history. The next
new-data task must implement the recorder and make its audited publication
inspectable in Market Data before features or backtests consume it. Existing
audited ETF and dollar-index sources sufficed for F0–F3. Exposure-matched controls,
final portfolio caps, cash remuneration and prospective validation remain open.

## ETF research expansion proposal — 2026-10-07

The user set an ETF-only boundary for the ongoing strategy-improvement work,
with country leading indicators, better momentum/crash handling, broader asset
exposures and sector-specific activity, growth, valuation, sentiment and
positioning information as research directions. Constituent financial statements
may inform ETF signals; single-stock trading remains outside this workstream.

The [research and data roadmap](etf-research-expansion-roadmap.md) proposes staged
universe/signal comparisons against the active October 4 rolling XGBoost +
activity + USD strategy. Priorities are a separately versioned final-weight risk
contract, dated ETF holdings/issuance, macro release vintages and macro/energy
pilots, followed by validated sector financials and selected narrow industries.
Existing SEC parsing and macro score hooks do not establish an audited sector
panel. The proposal includes recorder/source priorities, availability controls,
matched benchmarks and app-owned calculations. Experiment recipes, paid sources
and acceptance tolerances remain proposals; no experiments, recorder deployment,
new tracking, promotion or allocation changes were performed in this session.

October 7 follow-up: the user requested explicit near-total cash and alternative
fallback tests. The pool code confirms that fewer than four positive-momentum
qualifiers cause the original basket to pass through, before subsequent layers.
The roadmap now prioritizes F1 qualified base weights plus residual cash, F2
cash only, F3 qualified IEF/TLT/GLD base weights plus cash, and F4 an explicitly
specified Treasury-bill ETF parking alternative, against the unchanged F0.
Zero qualifiers may target 100% cash; no minimum investment is imposed.
Cash budgets must survive downstream overlays. Missing-data/model failures are
separate blockers, with matched cash/FX economics, re-entry and fallback-episode
attribution required. This is a research specification, not a tested improvement
or a change to the active strategy.

## Active SOTA and paper allocation — 2026-10-04

The operator approved 100% Rolling 1y XGBoost + ETF activity lag-20 + USD
(`research_rolling_xgboost_1y_lag20_v1_usd_v1`) through the strategy controls.
After evidence-preserving recovery of five completed-order conflict flags and
fresh matched IB reconciliation, the app activated that allocation and SOTA
designation at 08:56:12 +08:00 on October 4 (control revision 2). The approved
handover follows October 2 close; next execution session is October 5.
This is the existing monitored version and separate USD layer, with no model
recipe change. New routing approval remains required. Prior strategy periods,
holdings, execution history and the portfolio baseline are retained.

## USD promotion decision — 2026-10-02

The operator reviewed the momentum results and selected the tested U1 USD layer
for SOTA and both monitored portfolios. The new strategy IDs append `_usd_v1`
to the original SOTA, ETF activity lag-20 and rolling one-year XGBoost IDs.
The complete original definitions remain registered and serve as matched
benchmarks and rollback parents. This decision supersedes the earlier instruction
to retain those parents unchanged.

U1 is a separate final allocation layer: per-ETF expanding ridge with short and
older momentum, 63-return volatility, and same-vintage broad-dollar changes over
21/63 valid observations. Monthly fits require 60 completed monthly labels ending
strictly before the fit close. It preserves selected assets and gross exposure,
using the tested 12% rank tilt and 3 percentage point bounds. XGBoost keeps its
existing 26 inputs and training recipe; including USD inside the trees would
require a separately versioned, matched refit comparison. No such comparison has
been run, so the integration preserves the tested separate model.

The statistical conclusion has not changed: the USD-specific U1-minus-U0 gain is
about 14 bp/year over 30 months, with an interval including zero and Holm p=1.
U1 also contains price features; its full improvement cannot all be attributed to
USD. Prospective tracking of these selected versions begins October 2, 2026.
The inherited 45% setting remains a base allocation limit; it is not a final
holdings cap. The USD layer cannot increase an inherited overweight above 45%.
The requested addition does not alter broker risk limits or increase capital.

Market Data includes USD in Historical Daily Price for published DTWEXBGS history, index
levels, 21/63-observation changes, vintage dates, missing observations and export.
The chart uses one revised vintage; historical models use their own archived
vintages. The application acquires, audits and publishes new required snapshots,
fits models and calculates complete portfolios on refresh. Daily ALFRED archives
do not certify intraday dissemination. Revised ETF histories and legacy CNH FX
retain their existing availability limitations. USD/CNH remains unhedged.

Decision and rollback contract: `config/strategy-promotions/usd-ridge-u1-2026-10-02.json`.
The existing paper policy is bound to the previous strategy ID and therefore
disables automatic approval on restart. It must be reviewed and re-enabled for
the new version through the normal controls; live remains disabled. Paper/live
proposal calculation uses the same published USD model receipt as monitoring and
requires its ETF batch to match the audited decision inputs.

## Momentum horizon, membership and USD round — 2026-10-01

User authorized the revised research plan and all-core backtesting. Completed
102 USD replays: 24 new SOTA recipes, two parent clocks, two benchmarks, two
other-parent controls and four USD transfers, each at 5/10/20 bp per traded dollar.
All 34 base-cost portfolios plus two high-cost stress cases pass native LEAN
parity. Monthly targets reproduce all three monitored parents exactly across
129 decisions. No monitored strategy, execution policy or live setting changed.

Current monthly SOTA returns 9.17% net USD CAGR in this accounting scenario.
One/two-week momentum gives 4.17%/5.61%; the older-window blend gives 6.95%.
All four trend/skew gates trail the parent. Membership C1/C2 reduce annual cost
from 31.8 bp to 26.0/28.5 bp, but CAGR falls to 8.32%/8.41%. These are USD
adjusted-unit research results, not the existing CNH-accounting dashboard series.

Downloaded 92 ALFRED DTWEXBGS vintages and the Fed's revised daily history.
Audited same-vintage snapshots and verified analytical readback before publication
under `governance/usd-broad-index`, batch
`ddb5624ba023c71b9ca41ff0571318eb48f390ad4131ab20858d7eaafdae006b`.
The fixed 60-month ridge training requirement leaves April 2024–September 2026
for evaluation. USD adds 13.9 bp/year versus the matched price-only model;
the marginal six-month-block 95% interval is [-11.4, 33.7] bp, Holm p=1 over
the frozen 58-comparison family. Selected same-data transfers add 13.1/14.2 bp
on activity/rolling parents; these are correlated descriptive evidence.
Retain the USD hypothesis for discussion; no candidate clears promotion criteria.

Risk finding: the inherited 45% cap applies before pool reallocation; the
monthly parent reached 54.68% held weight and the weekly parent 61.52%.
A separately versioned final-weight constraint is needed before advancement.
Parent volume features remain legacy normalized proxies; audited prices are
revised vintages, and ALFRED availability is daily archive evidence with a
conservative prior-day cutoff. Legacy historical USD/CNH was excluded, so no
full historical CNH bridge is claimed. No prospective performance is claimed.

Full results: [review report](../research/momentum-results-2026-10-01.md).
Artifacts: `var/research/momentum-20261001-v1b`; earlier failed engineering
attempts and the transfer-selection correction are preserved. Tests: 48 passed,
one environment-dependent PostgreSQL integration test skipped. Source checks
and native parity retain paper-first controls.

## Rolling one-year XGBoost with lag-20 selected for app tracking — 2026-09-27

The user selected a third tracked candidate: `research_rolling_xgboost_1y_lag20_v1`.
The original rolling study had no activity overlay; the new definition adds the
unchanged lag-20 allocation overlay after XGBoost and the remaining SOTA steps.
The application owns monthly causal fitting, portfolio calculations and the full
shared report. All 129 models exactly match the study, and five native runs pass
parity. Matched activity-only and XGBoost-only controls appear in the report.

Full-history annualized return is 10.093%, Sharpe 0.9675, maximum drawdown -15.336%
through September 25, versus SOTA 9.656%, 0.9492 and -15.055%. This is historical
reconstruction selected after reviewing results; prospective tracking starts
September 28 with zero observations at publication. SOTA and existing activity
results are unchanged. No promotion, broker execution or paper-policy change.
See [strategy specification and initial acceptance](rolling-xgboost-lag20-tracking.md).

## Rolling tree, forest and XGBoost investigation — 2026-09-27

Completed all 41 native LEAN runs with unchanged parity. Monthly one-year
XGBoost/forest return 15.88%/15.75% CAGR from 2023 versus deployed frozen SOTA's
14.94%; primary six-candidate adjusted p=0.014/0.020 (63-session blocks).
However, frozen XGBoost/forest return 15.72%/15.68%, and tree-free SOTA returns
15.49%. Rolling adds only 0.159/0.063 annual percentage points versus the same
frozen model family; intervals include zero (adjusted p=0.529/0.692). Two-year
ensembles lag their frozen counterparts. Cost, delay and seed checks retain
the one-year ensemble gains versus SOTA, but gains are concentrated in 2025–26.
Long-history forest/XGBoost CAGR 9.97%/9.94% versus reconstructed SOTA 9.63%;
long adjusted p=0.068/0.108. No uniform stress-period improvement or clean
evidence for rolling refitting itself. Retain SOTA; future evidence should compare
fixed frozen and rolling ensemble recipes prospectively.

All 16 logical cores were used for independent fits; eight process workers ran
isolated two-CPU LEAN simulations. Published audited inputs, pinned FX/model
hashes, completed-label embargo and fixed portfolio rules are retained. Revised
vintages, fixed-universe selection and uncertified legacy FX remain limitations.
Archived 52,749 NAV/metric observations, six documents and 41 native receipts.
See [findings, protocol and replay](rolling-model-research-2026-09-27.md).
Calculations were a finite application job; no tracked membership, promotion,
paper policy or execution authority changed.

## App-owned tracked calculations — 2026-09-26

The application now owns the entire calculation lifecycle for monitored executable strategies. `config/strategy-monitoring.json` selects native LEAN with Python parity (default) or the application's isolated Python engine. New audited inputs/definitions trigger signal, monthly rebalance, daily NAV, held-weight and latest indicative-target calculations; unchanged revisions are reused. Complete results and their matched benchmarks publish atomically to ClickHouse. **Refresh calculations** wakes the application worker. The Codex heartbeat was deleted and its review script retired. `AGENTS.md` and the continuous research playbook explicitly prohibit agent-scheduled strategy calculation.

Both SOTA and ETF lag-20 use the same full report, including risk parity on the matched ETF universe, URTH, current SOTA, period metrics, drawdowns, holdings contributions, signal attribution, current allocation and complete decision diagrams. SOTA attribution uses risk parity; lag-20 attribution uses SOTA. History spans 2016 onward: pinned causal annual trees before 2023, then the unchanged deployed frozen model. The old 2023 card was the frozen-model companion, not a price-data boundary. The new history is a disclosed reconstruction and differs from the earlier all-years annual-refit experiment.

User decision remains **track, do not promote**. Forward observations begin 2026-09-28; historical results are not relabelled as prospective evidence. Only published audited prices are used. Legacy FX remains explicitly uncertified through September 24; validated direct IB USD/CNH close evidence supports September 25. Historical price vintages remain a limitation. Protocol and engine configuration: [app-native lag-20 tracking](etf-activity-lag20-tracking.md).

## Superseded initial ETF lag-20 observation workflow — 2026-09-26

The initial frozen card remains historical evidence in `config/etf-activity-lag20-tracking-v1.json` and ClickHouse `research-tracking/etf-activity-lag20-v1` (935 paired historical NAV points). Its daily Codex review automation has been deleted. The application calculation and common report above supersede this workflow; do not restart its agent scheduler or treat its archived card as the current strategy.

## Audited-input rerun — 2026-09-26

Retain current SOTA. The pinned audited batch has now been used for 24 native LEAN runs, all passing parity, covering 2016-01-04–2026-09-24 with causal annual fits plus actual-frozen-model companions from 2023. Baseline CAGR/Sharpe 9.84%/0.956; early signed constituent activity 9.82%/0.955, IR -0.172; constituent concentration IR -0.289. Earlier allocation/selection and joint residual trees do not establish added value. The fixed ETF lag-20 observation candidate reaches 9.99%/0.966, IR +0.285, but its 63-session family-adjusted p=0.574 and uneven period performance do not justify promotion. Candidate-specific audited cost/delay work remains before any lag-20 promotion review.

The stricter supported-raw/identity rules qualify only 32/129 monthly decisions, first 2023-08-01. Earlier months are neutral fallback, not a decade of constituent evidence. There are 551 matched scatter dates starting 2023-07-17; unsmoothed derivatives are near zero, with a modest smoothed 20-session relationship that has not improved the strategy. Do not lower coverage rules after seeing these results. Resolve historical issuer/raw-price gaps in a new audited batch before extending constituent evidence.

Future price research must read published audited continuous histories with pinned batches, verified hashes and explicit adjustment/volume bases, as required by `AGENTS.md` and the continuous research playbook. Provider archives are acquisition/audit evidence only. Auditing does not supply missing point-in-time vintages, complete delistings or certified FX. The unchanged legacy FX and assumed holdings-publication lags in this frozen rerun remain disclosed limitations.

Evidence: [audited rerun findings](audited-research-rerun-2026-09-26.md); `D:/systematic_trading_data/lean/research/audited-rerun-20260926-v1/`. ClickHouse contains 11,862 new observations and 22 documents across feature/result/review publications with exact payload readback; 24 native receipts are registered in PostgreSQL. Prior studies remain reproducible legacy evidence; the production model and monitoring-reader contracts are unchanged.

## Data-governance hold — 2026-09-26

The frozen ETF inputs used in the recent studies contain adjustment/source
boundary inconsistencies against a consistently collected new Yahoo vintage.
For HYG on 2026-05-26, the old snapshot implies -1.6528% versus +0.3379% in the
new governed series (1.9907 percentage points). That boundary coincides with
`sqlite_price_bars` changing to `platform_market_data_store`; SPY and LQD also
differ there. EWH has a separate discrepancy on 2026-04-30. Preserve prior
results as reproducible evidence of the old inputs, but rerun baseline and
candidate comparisons on pinned governed data before any promotion decision.
The identity audit also found older CSVs containing multiple economic issuers
under reused tickers (including NET/WMS/TXG). Recent price agreement does not
validate their earlier eras. Policy v2 quarantines periods before the current
provider listing boundary, or a conservative preferred-source identity floor
when that metadata is absent. Historical constituent research must map dated
issuer episodes rather than apply the current ticker's identity retrospectively.
The first governed build was quarantined before publication; its joined rows
are not accepted inputs. Original historical sources remain available for review.

No new strategy is elevated. See `docs/price-governance-2026-09-26.md`.


## Latest evidence — 2026-09-26 ten-year constituent follow-up

Retain current SOTA. The earlier January 2023 signal cutoff was a completeness
limit, not a deliberate short evaluation window. New dated IVV holdings and
archived public stock histories support 2016-01-04–2026-09-24: 122 of 129 monthly
decisions pass the unchanged primary 95%-value/70%-names rule. The 2020 and 2022
stress periods now have constituent observations. Histories remain revised,
publication lags are assumed, and IVV is a same-index proxy only for SPY.

Twenty-two long LEAN runs use annual expanding base trees to avoid future-label
leakage from the deployed pre-2023 fitted model. Baseline CAGR/Sharpe is
9.64%/0.932; early signed activity 9.68%/0.936/IR +0.158 trails the matched price
control 9.69%/0.937/+0.190. Its gain is 3.4bps CAGR, with a confidence interval
including zero and family-adjusted p=0.813. Joint residual-tree IR is +0.218
versus baseline but only +0.039 versus the price-only tree; concentration is
negative (-0.232). Selection changes three decisions and loses slightly. Early
signed activity worsens 2022. The four-run actual frozen-model companion has a
recent signed-activity IR +0.429 versus SOTA, only +0.105 versus price control,
and no statistically established gain. No promotion or trading-policy change.

The Market Data page now exposes the previously hidden ClickHouse research
archive, including stock bars, dated holdings, features and results. Added
2,298,993 current-provider stock observations, 85,050 holding rows and 7,595,897
public archived observations with exact readback. Final long-study features,
models and labels total 16,352 records; results/contrasts total 366. All 26
successful native receipts are registered. Public-source overlaps are preserved
as separate histories, not inserted into the canonical production daily bars.

Guide and replay: `docs/constituent-tenyear-research-2026-09-26.md`. Remaining
work is ETF-specific identity/publication quality and prospective validation of
fixed candidates, not further tuning on this inspected sample. Full suite 616
passed/51 optional skips; research/LEAN/browser lint, charts and browser checks
passed. Existing IB Gateway health remained unavailable during dashboard startup;
broker settings, orders and approval policy were not changed.

## Production Research Rule

Research is now part of a controlled research-to-paper-to-live pipeline. New candidates must compare against the current SOTA, use point-in-time data, record reproducible artifacts, and pass the promotion gates in `docs/industrial-platform-plan.md` before paper or live use.

## Alpha Factory Direction

The next research operating model should treat each alpha or factor as a versioned, independently observable contributor rather than only storing monolithic strategy runs. Before risk-parity-style alpha weighting is promoted, add contracts for factor identity and lineage, point-in-time signal values, theoretical factor returns, realized portfolio contribution, turnover/cost/capacity, correlation and covariance estimates, allocation weights, and retirement or rollback state.

Portfolio attribution should remain layered: strategy backtest NAV versus actual account NAV measures implementation divergence; reference-fill versus actual-fill PnL measures execution quality; factor-level theoretical and realized contribution explains which alphas earned or lost the portfolio result. Factor weights must be reproducible artifacts with concentration, correlation, liquidity, and regime-stability limits, not an unconstrained inverse-volatility calculation.

Use `.agents/skills/continuous-research-loop.md` for recurring challenger research and `.agents/skills/strategy-promotion-control.md` for promotion decisions.

## Current SOTA

September 26 earlier-integration follow-up: **retain current SOTA**. Nineteen
native LEAN runs test the selected signed-activity/breadth signals in earlier
allocation, pool selection and a shallow residual tree, with matched price-only
controls. Post-2023 earlier signed allocation is effectively identical to late
(14.77% CAGR / Sharpe 1.299 / IR +0.262); price-only early remains stronger
(14.79% / 1.301 / +0.301). Signed selection changes no weights or trades: SPY is
already held on 39/44 qualified dates and the other five have neutral/negative
signed scores. Breadth selection changes one decision and loses return.
The joint tree actually branches on stock breadth/signed activity, but 2025-onward
CAGR 18.84% / Sharpe 1.467 / IR -0.876 trails SOTA 19.03% / 1.474 and the price-only
tree 18.89% / 1.471. Twenty monthly model decisions begin February 2025; 19 change
allocations. Models have just 23/35 training months; future labels are excluded
and runtime features contain no outcome records. All samples were previously
inspected, so chronological fits are not an untouched holdout. Earlier placement
does not repair missing delistings, assumed availability or a U.S.-proxy-only
universe. Sources, four models, training labels, results and native receipts are
archived; no promotion. Next: ETF-specific constituent panels and fresh data
before a broader selection test. See
[earlier-integration evidence](constituent-integration-research-2026-09-26.md).

September 26 constituent follow-up: **retain current SOTA**. Five fixed stock
signals, their equal-weight primary composite, a price-only control and declared
robustness checks completed 15 native LEAN runs with unchanged parity. Historical
ITOT stocks guide only the SPY sleeve; they are a broad U.S. proxy, not exact SPY
or foreign-ETF membership. Full-period (2019-10-01–2026-09-24) primary CAGR
8.49% / Sharpe 0.782 / IR -0.394 versus SOTA 8.52% / 0.784. Concentration
acceleration IR -0.507. The 95%-value/70%-name complete-history rule first passes
January 2023, leaving 44 eligible monthly decisions and 33 composite target
changes. There is no constituent evidence from COVID/2022. Post-2023 primary
IR -0.540; signed activity has sample IR +0.262 but lags the price-only control
(+0.299), and its family-adjusted p=0.831 does not support inclusion. Do not
flip signs or refit weights on this reused history. Costs, delay, size and coverage
checks do not rescue the primary. All feature/results evidence is in ClickHouse
and native runs are registered; historical availability remains uncertified.
See [results and the constituent research plan](constituent-signals-research-2026-09-26.md).
Next: actual ETF-specific identities/holdings and earlier delisted histories;
then separately declared downside breadth, internal dispersion, filing-time
fundamental breadth and genuine issuance-confirmed crowding. No new recurring
job or paper/live strategy change.

September 26 flow/concentration research: **retain current SOTA**. Nineteen native
LEAN runs (17 predeclared plus two labeled post-hoc stresses) compare the current
12-ETF stack with activity-share acceleration, direction/Hurst/HHI/volume
ablations, a literal exit gate and parameter neighbors. Over 2013-04-01 to
2026-09-24, the predeclared primary returned 9.06% annually / 0.919 Sharpe versus
SOTA 9.11% / 0.924. A 20-session neighbor returned 9.28% / 0.935 and survived
matched higher-cost and delay checks, but full-period family-adjusted p=0.354
and weak neighborhood consistency do not support promotion. Retain that fixed
variant for observation; it was selected after results. The literal gate held
64.8% cash and returned 2.90%. Historical actual net flows, shares outstanding,
holdings and certified point-in-time constituent-sector membership remain absent; activity is not net inflow.
All runs passed unchanged parity and remain research-only. See the
[research report and data plan](flow-concentration-research-2026-09-26.md) and
`D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/`.
These numbers are a fresh adjusted-CNH LEAN comparison, not a recertification of
the older canonical artifact below. Next: timestamped net-issuance data and an
untouched prospective observation period, not more optimization on these dates.

Sector-HHI follow-up: daily Yahoo price/volume history for all eleven sector
SPDRs and SPY is now frozen separately under
`D:/systematic_trading_data/research/sector-hhi-20260926-v1/` (research only).
The 1,823 common signal dates, 2019-01-02–2026-04-02, show weak SPY return
correlations with share-volume HHI (+0.075/+0.115/+0.093 at 20/60/120 sessions)
and almost zero correlations with its daily first/second differences.
Smoothing does not establish an acceleration effect; period and dollar-volume
checks weaken the level relationship. These are descriptive overlapping-label
plots, not a new LEAN backtest or a promotion. ETF activity is not full-sector
turnover or investor net flows; historical adjustment vintages remain
uncertified. See [plots, methods and findings](sector-hhi-correlations-2026-09-26.md).

Underlying-stock follow-up: the public-data pilot now uses 95 historical monthly
ITOT equity snapshots, 3,267 populated stock histories and sector aggregates of
the stocks' own volumes/returns. It has dated sector cohorts, a modeled 45-day
publication lag and explicit missing/identity coverage, rather than today's
constituents applied to all past dates. However, only 139 common signal dates
(2025-09-15–2026-04-02) pass the 95%-value/70%-name coverage rules and have all
forward horizons observed. Raw first/second differences remain near zero in
that sample; its length and overlapping labels preclude a stable market-wide
conclusion. The longer observed-subset sample has material missing/delisted
history. The stock/fund histories and computed aggregates are archived under
ClickHouse `sector-research/<dataset>/` source prefixes. Keep SOTA unchanged.
See [underlying-sector evidence and storage guide](underlying-sector-hhi-2026-09-26.md).

September 26 audit: historical results below are retained as prior research
artifacts, not re-certified after the timing/data corrections. Missing source
vintages, fixed-universe survivorship and legacy FX lineage remain limitations.
The pre-2023 tree is fitted; post-2023 has been used repeatedly for strategy
selection and is not an untouched holdout. The new LEAN adjusted-CNH-unit scenario
has separate economics and artifacts; it does not overwrite these numbers or
promote a replacement. See [audit findings](platform-audit-2026-09-26.md) and
[LEAN workflow](lean-backtesting.md).

Paper operations now include separately tagged initial-allocation and 2 percentage point drift-maintenance proposals. Monthly signal calculation is preserved; intraday TWAP timing and additional turnover are not represented in the existing monthly benchmark. Keep attribution separate and validate execution/cost effects before live promotion.

### Original parent record — superseded by the October 2 USD version

- Name: SOTA: price/volume top 6 + technical tree + relative/adaptive
- Promoted on: 2026-05-26
- Registry: `systematic_trading.research.strategy_catalog.legacy_sota_definition`; `current_sota_definition` now returns the USD version described above.
- Backtest hurdle: future candidates should compare against the current USD SOTA and preserve this parent as a matched control.
- Canonical artifact folder: `var/backtests/sota_current/`
- Model HTML: `var/backtests/sota_current/sota_model.html`
- Promotion source artifact: `var/backtests/monthly_allweather_sleeve_variant_floor_search_20260525/`
- Prior SOTA artifact: `var/backtests/sota_current/history/2026-05-17_sota_dynamic_sleeve_commodity_guard_55/`

## Original Parent Model Summary

The original parent uses the expanded multi-asset ETF universe and static monthly rebalancing. The current SOTA appends the USD layer described above to this stack:

- Base: monthly multi-asset ETF universe, 63-bar inverse-volatility risk parity, 45% base weight cap before subsequent reallocation, 2% cash reserve.
- Pool filter: rank assets using 63/126/252-bar price momentum and 21/126-bar volume pressure; keep the top 6, require at least 4 selected assets, require positive 252-bar momentum, and reallocate residual weight.
- Technical tree: frozen pre-2023 regression tree, max depth 3, min leaf 25, trained on 1,572 in-sample asset-month observations with MACD, Bollinger, RSI, price trend, volume pressure, drawdown, valuation, and macro features. Tilt is 16%, with active changes capped at 6% per ETF.
- Relative momentum: 20/60-bar relative momentum overlay, 12% calm and 12% risk tilt, with active changes capped at 5% per ETF.
- Adaptive trend: 63/126/252-bar trend and volume/rebound/volatility-shock gates with weak, neutral, defensive, and rebound scaling.
- Benchmark: the canonical folder includes a benchmark-only run using the same multi-asset universe and static monthly scheduler.

Canonical results versus benchmark-only multi-asset risk parity, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Window | Ann. Return | Sharpe | Calmar | Max DD | Alpha vs Benchmark | Information Ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 9.10% | 0.95 | 0.65 | -14.11% | 134.60% | 0.63 |
| In-sample | 6.89% | 0.77 | 0.49 | -14.11% | 54.07% | 0.49 |
| Out-of-sample | 16.92% | 1.48 | 2.00 | -8.46% | 28.57% | 1.13 |

Stability note: this candidate was promoted because it is cleaner than the high-OOS all-weather sleeve after penalizing weak in-sample evidence. The OOS/IS Sharpe ratio is still high at about 1.92, so it should be treated as the current best production candidate rather than a final answer to the stability objective.

## Workflow Rule

Use `scripts/export_sota_artifacts.py` to regenerate the canonical SOTA folder after a promotion. Use the multi-asset research scripts for new challengers; use legacy `scripts/compare_trend_signal.py` only for old single-basket diagnostics or to quantify value added versus the original beta sleeve.

The comparison artifacts include model structure diagrams for the SOTA and candidate:

- Layer diagram: data, rebalance schedule, base beta sleeve, overlays, final targets.
- Decision tree: the gating and transformation logic used by each model.
- HTML reports shade the out-of-sample region and mark the split date when a split is provided.

## Short-Horizon Relative Momentum Tests

Artifacts:

- `var/backtests/relative_momentum_20_40_signal_2012/`
- `var/backtests/relative_momentum_20_60_signal_2012/`
- `var/backtests/relative_momentum_40_60_signal_2012/`
- `var/backtests/relative_momentum_20_40_60_trend_rank_2012/`
- `var/backtests/relative_momentum_20_60_tilt_grid_2012/`
- `var/backtests/relative_momentum_20_60_tilt20_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | In-Sample Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Relative momentum 20/40d, 12% tilt | -2.31% | -1.39% | 0.16% | -0.00 | 0.02% |
| Relative momentum 20/60d, 12% tilt | -0.09% | -0.42% | 0.36% | 0.00 | 0.05% |
| Relative momentum 40/60d, 12% tilt | -1.29% | -0.80% | 0.24% | -0.00 | 0.06% |
| Three-horizon trend rank 20/40/60d, 12% tilt | -0.89% | -0.30% | -0.09% | -0.00 | 0.06% |
| Relative momentum 20/60d, 20% tilt | 1.09% | -1.02% | 1.47% | 0.01 | 0.03% |

The 20/60d shorter-horizon pair became a prior registered SOTA and remains part of the current promoted stack at a more restrained 12% calm / 12% risk tilt. A 25-case tilt grid ranked 20% calm / 20% risk tilt first by OOS alpha. It still trailed the MSCI World proxy by 0.87% OOS, versus the prior 126/252d SOTA trailing URTH by 2.34% OOS, so future work should continue using URTH as an external benchmark check.

## Latest Country-Factor Research

Added `CountryCompositeFactorOverlay` for country ETF allocation research. It can blend:

- Price trend: 63/126/252-bar relative trend ranks.
- Volume pressure: up-volume share and signed volume acceleration.
- Mean reversion: 21-bar reversal and 63-bar moving-average deviation.
- Optional valuation score maps where positive means cheaper or more attractive.
- Optional macro-growth score maps where positive means stronger country growth.

Artifacts:

- Diversified price-trend candidate: `var/backtests/country_factor_trend_only_2012/`
- Balanced multi-factor candidate: `var/backtests/country_factor_signal_2012/`
- Aggressive US macro-prior candidate: `var/backtests/country_factor_macro_us_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | 0.10% | 1.19% | 0.01 | 0.00% |
| Balanced trend/volume/mean-reversion default | -0.87% | -0.54% | -0.01 | 0.08% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 213.16% | 27.62% | 0.17 | -4.15% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | -163.54% | -1.16% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 49.51% | 25.28% |

Promotion note: these country-factor candidates were not promoted. The diversified trend-only country factor is a credible challenger but only modestly improves out-of-sample and is weaker in-sample. The aggressive US macro-prior candidate beats URTH, but it is mostly a persistent US overweight and uses a static score map across history. Treat it as a benchmark-aware stress case until point-in-time macro and valuation tables are added to the SQLite data contract.

## Signal Library And Decision Tree

The code-backed signal library is in `systematic_trading.signals.library`; the human-readable table is `docs/signal-library.md`. Decision-tree runs also write `signal_library.md` and `decision_tree_training.json` in their output directory.

Decision-tree candidate:

- Artifacts: `var/backtests/decision_tree_signal_tilt20_2012/`
- Training sample: 655 in-sample asset-month rows, ending before the 2023-01-01 split.
- Features: 16 signal-library features from that run, covering trend, mean reversion, volume, risk regime, valuation score, and macro-growth score. The library now also includes the promoted 20/60d momentum features for future training runs.
- Model: max-depth 3 regression tree, min leaf 25, target is next-rebalance asset return minus cross-sectional basket mean.
- Learned first split: `macro_growth_score <= 0.5`, then short momentum, extended momentum, and volatility ratio.

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Decision tree, depth 3, 20% tilt | 29.00% | 0.50% | 0.01 | 0.08% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Decision tree, depth 3, 20% tilt | -134.64% | -1.84% |

Promotion note: do not promote the decision tree yet. It helped versus the prior 126/252d SOTA OOS, but the OOS edge was small, the tree uses a static macro score map, and it still trails URTH. It is useful as an interpretable research candidate and a framework for point-in-time macro/valuation data once those tables exist.
