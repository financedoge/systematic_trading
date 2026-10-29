# Research State

Current conclusions and review queue, updated October 29, 2026. Detailed historical
entries are preserved in the [verified history archive](archive/README.md).
The [research plan](signal-decay-and-alpha-plan.md) controls sequencing; the
[execution Kanban](execution-kanban.md) tracks open implementation work.

## BroadTrend full-pool strategy and FR25 70/30 — October 29, 2026

BroadTrend v1 registers the selected51-ETF full-pool monthly equal-capital,
daily symmetric-HMM policy with retained sleeve cash. Models frozen through2022;
no reviewer/Bayesian refit. Exact original paths reproduced. App-owned calculator,
normal report/held weights/current intents implemented; durable monitoring
revision 6 registered. Normal app calculation and serving publication completed
October 29 at 07:51 UTC; verified at 12:27 UTC. Report, all 51 states, held
quantities, current intents and benchmarks are available. The report ends
October 27 because USO lacks October 28; Catching up now denotes this data lag,
not pending activation. SOTA/allocation revision 7 preserved; no broker authority.

Matched USD2024-02-01..2026-10-12: FR25return62.89%,CAGR19.95%,Sharpe1.649,
DD8.64%;70/30return47.94%,CAGR15.72%,Sharpe1.640,DD7.66%;BroadTrend
17.50%/6.20%/1.147/6.10%. Correlation.677;blend volatility9.16%vs11.43%,
FR25approx86.5%risk share despite70%capital. It diversifies but gives up4.23pp
CAGR; both monthly anddynamic10%L1 pass0/6 guards. Native accounting-only
parity remains distinct from independent policy validation. Weak contributions
TLTforBroadTrend/LQDforblend;all51chartsready. Do not optimize weights after
this result and call it fresh confirmation. Need prospective and matched-risk/
cash evidence. [Specification](broadtrend-strategy-v1.md) ·
[Full results](broadtrend-fr25-comparison-2026-10-29.md).

## Strategy portfolios at N15, N20 and N30 — October 29, 2026

Completed fixed N15, then the operator-requested N20/N30 extension with unchanged
63/252 strategy ranks, daily symmetric-HMM policy, monthly capital, cash and costs.
N30 improves diversification and later Sharpe; it does not repair weak selection.
Equal monthly net return / Sharpe: later N15 18.15%/.776, N20 13.84%/.682,
N30 16.72%/.917; earlier −4.19%/−.217, −4.53%/−.269, −4.03%/−.251.
Unranked full pool: 17.50%/1.144 later, −1.13%/−.049 earlier. N30 passes
8/12 guarded comparisons versus N15, 0/12 versus unranked. No width is optimal
or promoted. N fixed by operator; prior proposal to search6/10/15/20/30 deferred.

N30 averages16.51/15.35 active ETFs, still45%/49%cash. Strategy-risk parity
reduces concentration but gives10.77%/−3.90%return. Dynamic10%L1 has a width
interaction (one sleeve cash flip=2/N); more trading offers no stable replacement.
Raw-price rank/hold controls have better returns but more exposure/drawdown;
future isolation should separate rank source from daily gate with matched cash.

Post-fit252day warmup makes funded periods2024-02-01..2026-10-16 and
2021-01-04..2022-12-30; repeatedly inspected development evidence.226portfolio
cases,612exact shadow matches,20tests,five native accounting fixtures. All100ETF
charts, three widths, dated ranks/fills and full attribution. N30 weakest actual
equal contributors CPERlater−.960pp/PPLTearly−1.187pp; risk WEAT/GLD. Weakest
shadows TLT−18.56%/MCHI−31.99%. No production, monitoring or broker changes.
[Width comparison](trend-sleeve-width-2026-10-29.md) ·
[N15 methods](trend-sleeve-portfolio-2026-10-29.md).

## Single-ETF branch closed; monthly portfolio direction — October 29, 2026

Operator requests synthesis and one algorithm before portfolio research, then
clarifies continuous tracking of all ETF strategies, monthly top-N membership,
and daily signals within members. Larger N is preferred if diversification helps.
This supersedes earlier portfolio deferral and further single-ETF reviewer work.

Retain entry-value B as `symmetric-trend-sleeve-v1`: two Kalman price filters,
symmetric fast HMM for every ETF, fixed policy, optional selected thesis exit
and closing protection. No return gate, Bayesian reset/learning, recovery review
or standing intraday stop. This is a transparent working choice, not a universal
winner; original fixed detector has stronger later medians. Chosen Sharpe medians
.392/.322, CAGR3.13%/2.40%; weakest CORN−23.25%, MCHI−34.29%, charts ready.

Full math/flows, 102 exact snapshots, 612 baseline comparisons and historical
rank preview retained. Primary four equal percentile ranks: 63/252d strategy
return and Sharpe, including cash. N6/10/15/20/30, EW or strategy-covariance ERC;
N15 only illustrative. All shadow histories continue unselected; exits leave
sleeve cash until next buy, without daily redistribution. Covariance shrinkage
and floor do not guarantee diversified capital or invested exposure.

Next implement actual fill/cash portfolio replay, causal post-fit warmup,
chronological N choice, monthly/dynamic control and full-pool benchmarks. Reused
eras remain development evidence. No portfolio backtest or promotion yet.
[Synthesis and specification](trend-sleeve-synthesis-2026-10-29.md).

## Coherent reviewer — October 28, 2026

One per-ETF return forecast now serves holding and recovery, with explicit
changes since the last decision and purged rolling model selection. Constant or
unconvincing fits abstain. The previous unchanged-evidence conflict is removed,
but neither challenger passes any of 12 full-pool era/friction gates. Later
median Sharpe A/B/C .402/.397/.402; earlier all .312. Training enables just
five asset/era/model fits, all of which worsen evaluation MSE versus constants.

XLU price review improves cumulative return 24.27%→48.55% later and
23.01%→35.41% earlier. All 12 return comparisons improve, but later harshest
stress leaves only 0.30pp and earlier some Sharpe/drawdown outcomes worsen.
ITA volume review cuts a longer winner, reducing return 38.48%→19.72%.
WEAT/GLD retain baseline because review abstains, not because active recognition
improved. Weakest CORN later −22.73%, MCHI earlier −34.96%; detailed loss charts
ready. Both historical periods remain repeatedly inspected development evidence.

Keep the research baseline. Next investigate temporary pullback versus failed
trade thesis using a compatible longer-horizon/time-to-invalidation target,
with this one-session control and full-pool preservation checks. 1,836 main/
816 diagnostic cases, 42 tests, 306 chart cases, 612 exact parent controls and
four native accounting fixtures pass. No overlay/promotion/live changes.
[Report and recipe](coherent-review-results-2026-10-28.md).

## Trained reviewer — October 28, 2026

Full 52/50 ETF study trains separate protected continuation/recovery models per
asset. Price-only and price/volume challengers both fail all 12 era/friction gates.
Median Sharpe A/B/C: .402/.241/.251 later, .312/.202/.182 earlier. C improves
DBA/SLV but harms GLD; recovery activity alone does not establish value. Weakest
C WEAT later −45.79%, MCHI earlier −34.96%; all charts and exact-date views ready.
WEAT exposes a structural conflict: constant recovery value positive, holding
value negative, producing 315 one-session trades. GLD's constant exit cuts all
35 completed trades short. Labels assume no future learned exit, unlike the
actual policy; HMM handoff cannot resolve this learned-model inconsistency.
Keep existing research baseline. Next use coherent action values, consistent
continuation labels, evidence changes and abstention, with nested rolling
validation and final-refit consistency checks. Shadow updating still fails median
forecast-error comparisons. 41 tests, 612 exact controls, 306 offline chart cases
and four native accounting fixtures pass; no promotion or live changes.
[Report and recipe](trained-review-results-2026-10-28.md).

## Independent decision review — October28,2026

Completed three-arm single-ETF study: standing protection, independent price/volume
review, then established/recent predictive-model averaging. Neither challenger
passes any12 era/friction gates. Later median Sharpe .402 for all; earlier
.312/.312/.268. Fixed review is mostly inactive; adaptive forecast IC/Brier does
not improve over simple controls. Stacked recovery conditions admit no executed
later recovery; CPER/IWM selected intervals unchanged. Weakest adaptive TLT later
−24.49%, IWM earlier−32.05%, all charts ready. PPLT illustrates premature profit
taking followed by a worse entry. Preserve earlier research baseline. Next use
decision-specific path labels, a simpler calibrated review rule and independent
pre-entry loss budget, with adaptation first evaluated in shadow. Frozen protocol,
full-pool cost/delay diagnostics,41 tests,612 exact controls,306 chart checks and4
native accounting fixtures retained. No overlay/promotion/live changes.
[Report and recipe](decision-review-results-2026-10-28.md).

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

### Standing protection and reversed-decision learning — 2026-10-27

Operator selected entry-value B as research baseline (not promotion). B0 exact
control; B1 standing gap-aware stop; B2 adds near-exit recovery and three-policy
warning-driven forgetting. Full52/50 pool,1,836 main and1,632 diagnostic cases.
CPER2025-03-04..09-04 net-15.45%→+10.00%/+11.81%; IWM2024-07-01..12-01
-14.04%→-9.64%/-11.60%. Recovery did not fire in either interval:requiring the
same lagging HMM makes nearby rebound evidence arrive too late. B2's wider
July IWM policy gave back B1's early-stop benefit. Later median Sharpe
.392/.402/.350; earlier.322/.312/.326. Both challengers fail all12 acceptance
cases; B2 preservation60.8%/63.3%. Repeated warnings/changes are not evidence of
improvement. Weakest B2 TLT later-23.36%,PPLT earlier-41.52%; charts ready.

All612 original controls and612 close-engine paths exact, independent multi-fill
ledger6.44e-15. A delayed-exit rearming bug was corrected before accepted
evaluation; all102 training calibrations unchanged, amendment retained.
Daily OHLC standing fills remain approximations; touch-to-close is conditional
and not validated auction execution. Native checks are explicit event-accounting
fixtures, not proof of intraday executability. Keep B0; investigate independent
hard-risk boundary, exit invalidation without the same HMM gate, partial recovery
and tempered evidence resets as separate components. No overlay/live change.
[Findings](stop-review-results-2026-10-27.md).

### Directional HMM and online entry value — 2026-10-27

Full52/50 ETF, three fixed-policy arms, six frictions:1,836 cases. Symmetric
directional Gaussian means/variance remove wrong-tail state inversion, but B
median Sharpe .392/.322 versus A .419/.276 fails preservation. C adds causal
discounted return/adverse forecasts; training-only prefix validation selects
intercept-only46/51 later and45/49 earlier risky ETFs. Median forecast IC
-.086/-.091; full-feature forecasts beat intercept return MSE on0/5 and1/4.
C exposure10.3%/8.5%, Sharpe-.007/.000. Neither passes any of12 acceptance cases.
Reject both replacements; retain directional semantics as a design constraint.

Weakest C CPER later-31.51%: late July24,2025 entry then-24.96% trade as price
crosses daily protection before next-open execution. IWM earlier-17.53%,six
losing trades; stale mean blocks recovery then admits late setups. WEAT/MCHI
later remain cash; TLT misses Nov2023 and delays Aug2024 rebound. Cash avoidance
does not satisfy rebound-capture objective. Charts, exact formulas and dated
incident traces ready;40 tests,612 exact controls,306 offline charts,3 native
accounting checks. Inspected development eras, no overlay or authority change.
Next examine event-conditioned continuation before invalidation at eligible
setups, aligned with actual exits; keep independent sizing/boundary work separate.
[Full findings](entry-value-results-2026-10-27.md).

### Trend detection and cautious entry — 2026-10-27

Rejected two new component replacements after the operator flagged market-like
PnL and repeated false rebounds. Current adaptive thesis-exit B median daily
correlation .601/.542 and beta .360/.293 later/earlier; regression intercepts are
descriptive, not demonstrated alpha. To isolate market signals from endogenous
policy feedback, all three new arms use fixed base policy0: original detector,
per-ETF constrained-range HMM, and HMM plus adverse-context/post-loss entry
confirmation. The fixed control differs from the actual adaptive incumbent.

1,836 cases. Later median Sharpe .419/.367/.247; earlier .276/.255/.309. Neither
challenger passes any12 era/friction acceptance cases. Range narrowing with
unequal Gaussian variances introduces a semantic defect: broad directional tails
can assign high down probability to large positive slopes.11/51 later and17/49
earlier risky ETFs have opposite-sign >=80% scores. ITA April9,2020 has +.970
normalized fast slope but99.89% down. This rejected study must not be promoted
based on its passing accounting/causality tests or WEAT improvement alone.

Weakest C TLT later-21.14%,23 closed/6wins; confirmation disabled by training.
More switches fragment the profitable2024 rebound. Earlier ITA-34.12%,13/2;
gate misses April/May2020 winners yet retains later losses. MCHI later falls
from B+24.72% to C-1.71% partly through delayed rebound entry. WEAT fixed A
-32.51% becomes-13.21%, but actual adaptive incumbent already-13.88%.
All charts and weakest cases ready. Next require meaningful directional states,
then chronological conditional-return/downside prediction and entry-value/risk
tests. Reconnect Bayesian learning only after matched component improvement.
No overlay/live changes. [Results and recipe](regime-entry-results-2026-10-27.md).

**October 27 full-pool thesis-exit test:** three arms compare the exact hard-reset
incumbent, context-aware loss of up-state support, and an additional signed-slope
correction of HMM-neutral down evidence. Six tuples fitted per ETF before evaluation;
disable when training guards fail. New exits also govern shadow learning and seeds.
1,836 cases. INDA December loss becomes -1.12% versus -10.82%; later cumulative
A/B/C -18.99%/-0.57%/-7.82%. Later median Sharpe 0.370/0.415/0.403, preservation
86.3%/84.3% below 90%. Earlier GLD +14.70% becomes -12.74%/-0.38%; early exits
create new losing re-entries and change risk-policy learning. B passes 1/12 gates,
C none. Retain simple invalidation as a component, not a universal replacement.
Weakest charts: TLT later -17.66% (addition disabled by training), MCHI earlier
-41.37%. Next isolate exit versus learning feedback and improve evidence for
re-entry after failed setups, with independent risk. 44 tests, 612 exact controls,
306 chart cases and three native checks passed. No overlay or runtime changes.
[Full findings](thesis-exit-results-2026-10-27.md).

**October 27 INDA loss inspection:** exact frozen replay of December 3, 2024 to
February 27, 2025. Fast up 68.91% justified the entry under the existing rule,
despite slow down 81.64%; context was disabled. Up falls below 20% on December 16
and 17; the HMM's neutral state absorbs moderate declines, while fast down peaks
at 66.30%, below the 70% exit threshold. Initial protection 11.25% lets the position
remain until a February 26 close breach and next-open -10.82% exit. The February
14 belief reset is not an exit. Simple illustrative up<20% for two closes exits
December 18 at -0.59%; negative fast slope for two closes exits December 19 at
-1.12%. No tuned thresholds, full-pool result or profitability inference. Preserve
this as evidence of missing thesis invalidation and imperfect state semantics.
Next: context-aware thesis monitoring, causal predictive likelihood evidence,
independent risk and re-entry. [Dated chart and trace](../research/inda-trade-20261027-v1/index.html).

**October 26 hard posterior reset experiment:** operator proposes forgetting old
information after large loss/drawdown or3–4losses, optionally an HMM change.
Current policy learner already caps training at4effective trades and discounts;
previous acceleration leaves median0.59effective trades. New full-pool3arm study
compares continuous learning, hard loss/drawdown reset, plus confirmed filtered
HMM-transition reset. Clears payoff/win statistics and accepts only post-reset
entries; underlying market fits remain frozen.1,836cases. MedianSharpe improves
.284→.370 later/.195→.217 earlier, but preservation72.5%/69.4% fails90%, and neither
reset passes any12era/friction gates. Later GLD+90.66%, WEAT-13.88%, TLT-17.66%.
HMM reset affects4later/14earlier risky ETFs; no extra event for GLD/WEAT/TLT.
Learning waits for new completed trades: WEAT261sessions without new eligible
outcome versus2continuous, while still trading. Weakest C INDA-18.99% later and
PPLT-40.98% earlier ready. Full reset can discard useful triggering losses;
warning date need not equal change date. Next hypothesis: daily predictive/marked
rewards, plausible recent change boundary and incumbent/fresh challenger; distinguish
HMM state switching from structural parameter drift.15tests,612zero-error controls,
306offline charts and3native single-ETF checks. No overlay/runtime/promotion change.
[Detailed results](reset-policy-results-2026-10-26.md).

**October 26 continuous single-ETF learning:** operator explicitly defers ALL
portfolio overlays and rebalancing research until the ETF trading rule improves.
Three frozen comparisons now implement evolving entry/exit/protection parameters:
fixed, discounted Bayesian policy learning, warning-accelerated learning. No health
pause; underlying latent market fits unchanged. Completed shadow outcomes update
separate policy posteriors; actual loss warnings accelerate old-evidence discounting.
1,836 cases,52supported ETFs/two eras/six frictions. Later ordinary learning raises
GLD+56.69% ->+88.30%, WEAT-32.51% ->-10.69%; added warnings+85.34%/-18.17%.
Full-pool median Sharpe falls0.412 ->0.284/0.277 later and0.276 ->0.195/0.195 earlier.
Neither adaptive arm passes any of12era/friction guards. TLT weakest C(-24.08%)
shows the key failure: tighter exit captures only+1.23% of late2023rebound versus
B+11.43%; rearming excludes the continuing uptrend while winning shadow outcomes
are not yet closed. Earlier PPLT-32.56%; both charts ready. WEAT's first two losses
remain, so learning alone is not a hard risk cap. Next: separate risk, entry/exit/
re-entry learning, causal marked rewards and context-conditioned evidence.
16tests,612exact controls,306offline charts and3native single-ETF checks pass;
native uses app whole-unit sizing, not exact fractional NAV. Research only.
[Results and formulas](online-policy-results-2026-10-26.md).

**October 26 single-large-loss experiment:** added training-winner-sigma and
losing-protective-exit feedback to the3/4-loss controller, with actual changed
trades, next-open execution and explicit shadow recovery. Three fixed arms,
1,836 ETF/friction and138 portfolio cases. WEAT improves from-32.51% to-5.36%
largely by pausing925 sessions after January5,2023; GLD drops+56.69% to+10.66%.
These are matched fresh-funded controls, not prior carried-position headlines.
Neither adaptive arm passes the full-pool guards in either era/any friction.
Monthly severity selection is a limited positive: versus fixed monthly selection,
both eras/all6frictions improve Sharpe/DD within1ppCAGR, but stronger alternatives
are not consistently beaten. Dynamic severity overlay1.470Sharpe/10.93%CAGR
fails return preservation versus fixed13.18%. Keep the warning features; redesign
the overly strict pause/recovery response and test refit benefit separately.
Current weakest severity cases EWH-20.57% later/EWY-19.36% earlier have prepared
charts; all306ETF/era/arm charts available.29tests,612exact controls, independent
cash ledger and3zero-error native checks pass. No online refit, promotion or
runtime change. [Findings](loss-feedback-results-2026-10-26.md).

**October 26 loss-feedback extension:** operator accepts the three-timescale/
spectral direction and asks for recent strategy outcomes to trigger adaptation.
A research-only controller now implements three net losses -> defensive risk,
four -> pause/refit-review event, fresh shadow recovery and reduced-risk probation.
Seventeen tests pass; no adaptive trade simulation or refitting is claimed. The
full-pool frozen-trade audit covers 51 later/49 earlier risky cases. WEAT's first
three losses close June 29, 2023 (already -17.21% cumulative); the fourth closes
August 1 (-20.28%), with action permitted no earlier than the next session. June
and July trades reached +8.75%/+7.09% held-close gains but exited -2.18%/-3.71%
net, supporting separate entry-lag and profit-giveback hypotheses. A streak alone
is not evidence of a new market regime: 27/41 profitable later cases have a
three-loss run, including GLD. Integrate common health logic and matched disabled/
scheduled controls into the next three model families. WEAT/MCHI warning charts
are ready; all frozen results and operational controls remain unchanged.
[Framework, equations and audit](strategy-health-framework-2026-10-26.md).

**October 26 operator direction and inspection standard:** investigate whether
multi-year context changes explain TLT failures, considering a short/intermediate/
structural hierarchy, explicit durations, online change uncertainty and causal
time-frequency features. This is a proposal, not a fitted new strategy. A flat
average slope is not proof of a mean-reverting range; current TLT evidence still
shows a substantial decline through October 2023. FR25 is one empirical incumbent,
not a universal gold standard; test its own asset/period dependence and retain
cash, buy-and-hold and simple matched controls. Historical gates/promotion rules
remain intact. Every round must prepare the weakest training-selected risky ETF
chart under a stated primary criterion and each chronology. Current report now
opens WEAT/B (-32.51%, 10/14 closed losses); earlier weakest MCHI/A (-29.80%) is
one click away. Raw volume and static inspection figures added without refitting.
[Proposed design and inspection links](regime-hierarchy-direction-2026-10-26.md).

**October 26 continuous-slope experiment:** three choices only: Gaussian slope
direction with uniform exits (A), fast-slope HMM with uniform exits (B), and
fast-slope HMM with slow-context exits (C). Per-ETF fits cover all 52 supported
ETFs; the report has 306 charts, exact mathematical equations and actual fitted
parameters. Later median Sharpe A/B/C=.374/.449/.461 versus prior .319; earlier
.340/.291/.271 versus .214. No family meets the preservation guards. TLT C
captures November 6–January 9 for +11.59% and July 17–September 27 for +5.51%,
but full later return remains -12.48% (B -11.45%) versus prior -18.53%.
EWA/MCHI improve, CORN deteriorates, and GLD C +76.60% still trails prior +85.78%;
its actual training choice A earns +58.32%. WEAT B is worst at -32.51%, with
10/14 losing closed trades. All slow noise-ratio fits and 100/102 fast fits hit
the upper bound: learned continuous slopes do not establish unconstrained or
time-varying horizon selection. Dynamic overlay 13.46% CAGR/1.372 Sharpe trails
FR25 16.51%/1.450. Four earlier selector/friction gates pass; no later gate or
both-era/all-friction acceptance. 35 tests, exact controls and three native
replays pass. Keep research-only. Next discussion: WEAT/CORN false rebounds and
slow-context timescale/price-shock separation under a new protocol; do not retune
the inspected TLT events. [Findings and report](latent-slope-research-2026-10-26.md).

**October 25 TLT coupled-regime experiment:** daily-observation slow/fast factors
with learned conditional transitions capture November 3, 2023–January 5, 2024
for +9.24%, but June–October 2024 loses 0.98% across two trades. Full TLT return
is −17.81%, Sharpe −0.596, DD25.13%; prior selected −18.53%/−0.656/DD20.36%.
Independent factors make the same event trades and have better full TLT return
(−15.49%). Slow direction never reaches the 55% context threshold in any of 951
later sessions, so this does not establish long-down/short-up identification.
GLD drops from +85.78% to +18.02%; selected median Sharpe 0.316/0.215 later/earlier
versus prior 0.319/0.214. None of 36 portfolio gates passes; dynamic overlay
11.35% CAGR/1.401 Sharpe trails FR25 16.51%/1.450. Keep as diagnostic evidence,
not a replacement. Next hypothesis is a continuous latent slow slope and fast
switching rebound process, with direct regime/timing diagnostics and full-pool
preservation. Exact date selection is added to both reports. 32 tests, 66 exact
controls and three zero-error native checks pass; no runtime changes.
[Method, TLT cases and full table](tlt-coupled-trends-2026-10-25.md).

**October 25 multiscale/adaptive/HMM follow-up:** the operator requested combined
long/short context, adaptive horizons, countertrend/volatility/volume protection
and then HMMs before the design was frozen. Seven components with paired volume
controls fit one combined strategy per ETF. Separate fast/slow three-state HMMs
observe multiple horizons and use forward-filtered probabilities only; this is
not a fitted factorial HMM or latent-window model. All 52 files were sealed before
9,792 asset/friction and 102 portfolio evaluations. The previous short/long union
is the matched control; prior models are unchanged and TLT/MCHI charts added.

GLD's selected fixed model exits March 26, 2026, +85.78% return / 18.52% DD.
Protected HMM improves CORN's loss from 29.19% to 9.86%; MCHI improves to +7.95%.
EWA/TLT remain negative, while later trend participation suffers broadly: selected
40/51 positive, median Sharpe 0.319 versus prior union 0.615; earlier 32/49 positive,
0.214 versus 0.198. Only three later cases improve union CAGR. HMM price median
Sharpe is 0.336 later / 0.292 earlier; tighter exits often sacrifice the later
advances. No family passes preservation; no selected positive alpha survives Holm.
Six earlier dynamic-selector portfolio gates pass, none later. New dynamic overlay
13.95% CAGR / 1.339 Sharpe trails FR25 16.51% / 1.450. No SOTA replacement.
HMM probabilities are often nearly binary; correlated features/diagonal covariance
and semantic validity need inspection, not a claim of calibrated certainty.
All 54 unchanged controls reproduce, three native checks have zero NAV error,
26 tests pass. [Protocol, cases and report](multiscale-hmm-research-2026-10-25.md).

**October 25 independently parameterized trend modes:** three causal detector
methods, each with price-only and volume-confirmed variants, use separate range,
up and down parameter blocks selected jointly on training trading outcomes for
every ETF/domain. Buy range/down-to-up, hold through range, sell on confirmed down;
no inherited TP/SL or time exit. The bounded full-pool study seals all fits before
8,568 asset/friction and 102 portfolio evaluations. Later selected outcomes are
positive in 92/102 risky cases and improve previous breakout CAGR in 74, but only
15 beat buy-hold CAGR; 86 have fewer than five closed evaluation trades. Earlier
59/98 are positive, median Sharpe 0.190 versus later 0.562. No positive alpha
survives Holm adjustment in either era; these remain inspected development periods.

GLD long +94.09%, IAT short +64.48% and SOXX short +374.90% illustrate restored
trend participation. SLV long's +69.78% comes with 52.96% peak drawdown: a
126-session down detector confirms late, then conflicting up evidence delays
adoption eight more sessions. IAT's profitable fit labels 88.85% of sessions range,
showing that return fitting alone does not validate the intended trend semantics.
Worst net case is CORN short -29.19%; EWA short -19.47% misses buy-hold +45.80%.
Volume helps regression most consistently, not every family. The new dynamic
FR25 overlay earns 15.51% CAGR / 1.430 Sharpe versus FR25 16.51% / 1.450; none
of 36 matched portfolio gates pass. No SOTA replacement or promotion. All 66
unchanged controls reproduce exactly; three native engine checks have zero NAV
difference. Next separately declared study should test faster down detection,
state-dependent conflict handling and range-shape identification separately from
trading utility. [Findings and full report](trend-mode-research-2026-10-25.md).

**October 23 full-pool trend-exit failure inspection:** all 104 later actual
21-session/1 ATR control fits and matched baselines replay exactly. The new paired
52-ETF table separates the control from training-selected baseline retention.
Among 102 risky ETF/domain cases, 56 earn positive returns, 46 lose, and 28 improve
the previous exit. SLV long is worst at -20.31% versus previous +84.41% and buy-hold
+133.92%; SOXX short has the largest deterioration (+187.66% to +24.62%). SLV's
wide initial risk, late positive-slope formation below entry, next-open gaps and
disabled continuation explain distinct observed failure mechanisms. Five of six
trades lose; fees account for only 0.48 pp. One-session extra delay lowers return
to -30.85%. All 15,875 reconstructed daily stop levels reconcile; no implementation
or parameter changes are made. [Full table and trade inspection](../research/trend-exit-failure-review-20261023-v1/index.html).

**October 23 breakout diagnosis and component tests:** full-pool short/long tables
verify 104 later and 100 earlier independent fits. Broad percentage trails can
activate without raising the initial floor; some losses never activate a trail;
other ETFs miss trends through sparse entries. Earlier/tighter exits, trend gates
and flat/rising range alternatives were refitted on each ETF's training history
in a separate 90-candidate component study. First-lower exits improve IAT/XLY but
damage GLD/SLV/PPLT; combined changes do not qualify. All 24 later portfolio gates
fail; 6/12 earlier gates pass without later transfer.

The operator then specified exits on failure of the new post-entry upward trend.
A separate 13-candidate rising-support study retains initial protection and fixed
entries. Its fixed 21-session/1 ATR control improves IAT short from -29.93% to -5.07%
cumulative, but cuts GLD long from +51.45% to +10.40%; IAT long/MCHI/PPLT have
better risk-adjusted outcomes while SLV deteriorates. No later training-selected
exit clears the preservation requirements. Local trend deceleration can trigger
an exit while the broader trend survives; unchanged sparse re-entry then misses
continuation. **Neither experiment validates a SOTA replacement or overlay.**
Both use pinned published histories and previously inspected development periods.
All baseline metrics reproduce exactly, independent ledgers/training prefixes
reconcile, native accounting checks pass and 45 focused tests pass. No execution,
funding, promotion or monitoring changes. Next hypothesis: causal trend structure
and coordinated continuation re-entry, with initial false-breakout protection kept
distinct. [Tables, diagnosis and full findings](breakout-components-review-2026-10-23.md).

**October 21 individually fitted breakout audit:** the operator clarified that the
question is per-ETF predictive quality, GLD extrapolation and incremental SOTA use,
not merely an unfitted construction experiment. Original GLD long with corrected
execution reproduces 11.63% CAGR / 1.290 Sharpe / -11.35% DD (2023–October 16),
but only three closed trades and weak alpha/IC; its older procedure test fails.
Corrected per-ETF refits across the 52 supported ETFs give positive later-period
CAGR for 39/51 short and 37/51 long risky ETFs, but only 1/51 and 3/51 materially
positive ETF-beta/BIL-adjusted alpha estimates, none after multiple-test adjustment.
Median state IC21 is -0.097 / -0.054; cross-sectional state IC is +0.006 / -0.034.
Earlier independently refitted chronology does not establish later generalization.
All 24 matched selection/overlay SOTA friction gates fail. Dynamic overlay earns
12.34% / 1.395 / -7.55% versus FR25 16.51% / 1.450 / -8.65%; constant exposure
reduction and all three shuffled-state controls have stronger Sharpe. **Do not use
this fitted family as validated selection alpha or a SOTA overlay.** Original
frozen engine behavior is preserved; corrected execution lives in a separate
versioned research module. Three exact native checks, 41 focused tests, full
signal/standard-overlay report. No promotion, funding, monitoring or runtime change.
[Findings and limitations](fitted-breakout-signal-audit-2026-10-21.md).

The operator's GLD drilldown is available as an
[interactive range / breakout / exit inspection](../research/gld-breakout-inspection-20261021-v1/index.html).
Original short/long fitted parameters are unchanged; corrected execution supplies
the 52 historical trades. All plotted daily stop levels reconcile exactly.
This is a visual explanation of the existing evidence, not a new fit or test.

**October 20 correction review supersedes the conditional-candidate claims below.**
The app calculation is a frozen historical USD replay, not a current CNH strategy:
its October 12 cutoff is hard-wired and cannot catch up merely by receiving prices.
Implementation 1.1.0 repairs input verification/revision binding, real holdings/cash,
Rule A/cash-trigger contracts and report readiness. A predeclared 72-replay
cost/timing retest gives dynamic 10% CAGR 15.85%, Sharpe 1.459, DD -7.64% versus
matched FR25 16.51%/1.450/-8.65% at 5 bp. It passes only 2/6 friction gates,
fails every added-delay gate, fails Sortino at 20 bp, and trails two matched
random-condition controls in base Sharpe. Annual Sharpe differences turn negative
in 2025 and 2026. Four native LEAN checks match exactly. **Do not promote or retune
this candidate on the inspected sample.** Membership/funding remain unchanged;
running-app deployment and current signal extension remain open.
[Review, corrected results and next decision](conditional-lifecycle-review-2026-10-20.md).

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
