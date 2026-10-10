# Project Log

## 2026-10-10 — P4.13 signal decay: IC instrumentation, dashboard panel, decay warning

Completed P4.13, the first item of the [signal decay and alpha plan](../docs/signal-decay-and-alpha-plan.md),
including the dashboard surface and the allocation-aware warning the user asked
for. Findings are in [signal decay findings](../docs/signal-decay-findings.md).
Decision support only: no monitored strategy, allocation, approval or broker
record was changed.

Built `research/signal_decay.py` (IC maths, block bootstrap, half-life, breakeven
gate, status logic), `research/signal_decay_job.py` (point-in-time signal series
and publication), `research/signal_health.py` (strategy-to-signal join and warning
gating), a read-only `GET /api/v1/strategies/signal-decay`, a **Signal decay**
panel at the top of `/strategies`, an operator banner on `/operator` that appears
only when a *funded* strategy is affected, and a durable alert from the analytics
readiness loop.

Method: labels are next-open to next-open because the platform decides at the
close and fills at the next open; rank IC uses the platform's own normalised
ranks; intervals come from the circular block bootstrap at 3/6/12-month blocks
because forward windows overlap; the breakeven gate scales annual cost to the
signal's own horizon and deliberately omits the selection-intensity multiplier,
so it is conservative.

130 monthly decisions, 2016-01-04 to 2026-10-01, 14 candidates, batch
`b02d9372…`, 5bp, **measured** annual one-way turnover 3.97x, 21-session return
dispersion 5.22%.

- **`m1_total`, the funded strategy's selection score, shows no decay.** Long-run
  IC 0.0548, recent 24-decision IC 0.0943, hit rate 54%, IR 0.13, status healthy.
  The FR25 concentration concern is not visible as lost ranking power in the M1
  component.
- **But its interval spans zero**: 95% block-bootstrap [−0.016, +0.127] at 3
  months, [−0.023, +0.134] at 6, [−0.023, +0.136] at 12. The sign is consistent
  across all five horizons, but 130 overlapping monthly decisions cannot establish
  a nonzero edge. Published as such.
- **Two signals are decayed**: `m1_volume` (a quarter of the M1 score) has
  long-run IC 0.0141 and recent −0.0110, the weakest IR in the family; and
  `drawdown_252` is negative throughout and strongly negative recently.
- `momentum_63` has the best IR (0.16, mean IC 0.070).
- **Cost headroom is large**: at the measured 3.97x turnover the breakeven IC is
  0.0032, about 17x below the observed `m1_total` IC.

Consequence for P4.15 and P4.17: the identical gate applied to Alpha101's own
turnover gives a breakeven IC of 0.100 at the median and 0.337 at the fastest.
0.100 exceeds every signal measured here, so the turnover gate is no longer a
formality — it decides whether the restricted Alpha101 subset is viable at all.

Coverage gaps are published rather than hidden: FR25's financial ridge, CR's
context ridge, the rolling XGBoost and the USD ridge forecasts are **not** yet
measured, because their per-decision values are not published and reproducing
them means re-running the frozen model schedules. The practical consequence is
that the FR25 warning currently rests on the M1 component only; closing that is
the next increment of P4.13.

Verification: 29 focused tests in `tests/test_signal_decay.py`, plus a wide
regression batch over the strategy, API, UI, recorder and governed-refresh suites.
Node is not installed here, so the repository's `.cjs` browser checks skip; the
panel and banner were verified against the served HTML of the live application and
by an element-id agreement test. That regression batch caught one integration
fault: the job originally raised a missing-audited-history error into the research
lane, so it now skips quietly when nothing is published yet while still raising on
any other error.

## 2026-10-10 — Next research phase registered: signal decay, alpha overlays, robustness

Reviewed the existing research plan and results and read Kakushadze's *101
Formulaic Alphas* first-hand, then registered the next phase as
`P4.13`-`P4.21` in the execution Kanban, documented in
`docs/signal-decay-and-alpha-plan.md`. No promotion, funding or execution change.

The plan is governed by three regularities in our own record: selection-layer
changes work (FR25/CR50 +0.087/+0.065 Sharpe) while sizing and timing overlays do
not (+0.016 and below); nothing has ever passed 5% Holm at any registered block
length; and the strongest lead is fragile, since FR25 changes 13 of 70 evaluation
selections with a +4.552pp 2026 advantage concentrated in recent substitutions.

Alpha101 was assessed against the data we actually hold. Extracting and
classifying all 101 formulas verbatim, and corroborating the counts against
DolphinDB's independently written implementation, gives: 43 alphas need `vwap`,
18 need an industry classification and one needs market capitalisation, so **49
of 101 cannot be computed at all**; 83 contain a cross-sectional operator; and
only **16 are both implementable and free of a cross-sectional operator**
(6, 7, 9, 12, 21, 23, 24, 26, 35, 43, 46, 49, 51, 53, 54, 101). The paper's own
Table 1 puts the median alpha at a 2.10-session holding period and 0.475 daily
turnover — roughly **120x annual one-way turnover, about 6.0% a year at our frozen
5bp** against the current strategy's ~8x and ~0.4% — and states its published
figures exclude transaction costs. The alphas are also survivor-selected (80 in
production when written, one sample window, no out-of-sample split) and were
validated on the top ~2,500 US stocks, roughly 700 times our universe breadth.

Disposition: use Alpha101 only as a restricted feature set at the selection layer,
behind measured turnover and decay, and never as an unconditional daily overlay.
Registered order: P4.13 decay instrumentation and P4.14 FR25 robustness stress
first (neither needs new data), then P4.15 turnover/breakeven gate, P4.16
sleeve-aware construction, and P4.17 the restricted Alpha101 subset. P4.18
volatility targeting and P4.19 execution timing cover the risk and execution
axes; P4.20 registers a decay-based promotion gate; P4.21 (look-through
constituent alpha) is deferred pending P4.16.

The "activate on an intraday alpha signal, exit on a signal flip or a predefined
stop" design is registered as **P5.11, a platform workstream rather than
research**: there are no intraday tables in ClickHouse, the recorder holds only
raw five-second sampled quotes for five ETFs flagged `research_approved: false`,
and routing is a single monthly TWAP window. Until audited intraday data and an
intraday execution stack exist, stop research is limited to a disclosed
daily-resolution approximation.

Working cadence agreed with the user: **one item at a time, with a review and
reflection between items**. Do not start an item while the previous item's report
is unreviewed. Recorded in the plan and in the Kanban work order.

## 2026-10-10 — Governed-data `review` status: decision and triage

The user decided to leave the decision gate unchanged for now and to spend effort
later promoting `review` series to `audited_with_limitations` by investigating and
filling or fixing the underlying gaps. Registered as P3.8 in the execution Kanban
with the triage below; no code or schema changed.

`portfolio/decision_inputs.py` continues to hard-fail only on `unavailable` and
`complex_identity_requires_review`, so `review` series remain admissible to
paper/live decisions. That is acceptable today because no traded or benchmark
instrument carries `review`.

Triage of the current catalog batch `b02d9372…` (5,341 series: 1,056
`audited_with_limitations`, 3,482 `review`, 803 `unavailable`), read from the
latest published audit document per symbol:

- All 3,482 `review` series share the same four certification gaps —
  `identity_not_certified`, `raw_tape_not_certified`,
  `listing_boundary_not_certified`, `listing_history_not_certified`. Only 11 have
  no other gap.
- 3,471 also carry at least one data gap: `volume_conflicts` 2,818,
  `cross_source_conflicts` 2,401, `stale_tail` 1,303, `pre_listing_observations`
  681, `source_gaps` 269, `internal_gaps` 269, `unresolved_names` 153,
  `source_seams` 4.
- By research role the population is `underlying-sector-hhi-20260926-v1` (3,460)
  and `ivv-constituents-2012-2026-v1` (680, partly overlapping): research-only
  constituent stocks, not trading instruments.
- **Only four `review` series are ETFs, and none is in the trading universe:**
  IVV (1,014 cross-source conflicts), XLF (890), XLRE (2 volume conflicts) and
  HYXU (delisted, stale tail, 1,304 conflicts).

Consequence for the deferred work: certification is not achievable for the
constituent bulk with current sources — it needs a security master, the same
access gap recorded for CRSP — so the tractable work is (1) the four ETFs,
including reclassifying delisted HYXU instead of leaving it `review`; (2) the two
data-gap classes, which likely share a few systemic root causes such as provider
volume conventions and source precedence and may therefore flip in bulk from one
rule fix; (3) certification, which stays blocked. A useful outcome of tier 2 is
splitting `review` so it stops conflating a fixable data gap with a series that
was never certified, which is what would make the decision gate meaningful.

## 2026-10-10 — FR25 close-out, calculation identity and governed-data hardening

Closed out the FR25 monitoring item and repaired four hazards found in a
repository review. No funding, approval, reconciliation or execution-authority
change.

FR25 (`research_fr25_14_v1`) was already implemented, registered and verified
before this session: membership generation 4, membership revision 4, and research
parity against the frozen selection-blend protocol
`5399931f5267d8beceb1ff52b15d84a81547f4f1e8a285a413bace7702769276` with 130
decisions, 898 fills, 2,707 daily NAV observations, 130 model fits and matching
final positions. This session supplied the missing durable bookkeeping: the
architecture contract, `docs/fr25-selection-tracking.md`, a research-state entry,
the Kanban transition to Done and a written runtime acceptance receipt. The
report is served with its current-state, USD model, financial-ridge selection
rank, model-training, signal-attribution and full-decision-chart panels.

That registration-time parity is bound to audited price batch `4bfdef17…`. The
live runtime revision now calculates on the newer committed batch `b02d9372…`, so
the two are distinct evidence versions of the same frozen recipe and are not
bit-identical: the first differing NAV is 2016-02-25 (about 48 CNH) and recent
rebalances differ by about one share. This is the documented "new audited
revision produces a separate reproducible calculation version" behaviour, not a
code, definition or contract change. `runtime-final.json` records both batches and
re-verifies 11 native parity receipts; the four existing USD strategy replays are
byte-identical to the previous revision, and allocation revision 5 with all 270
order records is unchanged.

The calculation code-hash identity is now derived from package contents instead of
a hand-maintained file list. `calculation_code_hashes()` globs the `research`,
`lean`, `signals`, `portfolio` and `backtest` packages plus
`recorders/economics.py` and `runtime_io.py`; a new calculation module can no
longer be omitted from the revision identity, and a missing declared source or an
empty calculation package fails loudly. The on-disk key format is unchanged. The
restart produced a distinct revision, confirming the identity changed as
intended.

The XOP admission hold moved out of configuration alone into
`research/etf_admission.py`, consulted by the research-ETF recorder, M1/14
constituent validation and the universe control. Deleting the `admission_hold`
configuration key can no longer release the hold; the quarantined state records
the evidence reference. Configuration-only holds keep their previous behaviour.

Three further hazards were repaired. The catalog re-read in `_build_publish` now
raises the intended `ValueError` when the committed publication is missing rather
than a `TypeError`. The two divergent `canonical_payload_hash` implementations
collapsed into one shared definition in `systematic_trading/canonical.py`; 735
recorded raw envelopes re-verified with zero hash mismatches, and the previous
key order, separators, escaping and naive-timestamp handling are pinned by test.
The paper/live decision receipt now states
`provider_reported_split_adjusted_source_volume` and records explicitly that it
is not the reconstructed raw-volume basis.

Tracker drift was swept: the monitoring-configuration header now states that the
ID list is a baseline seed and that durable overrides are authoritative;
`log.md` is consistently newest-first (the 2026-10-09/10 sessions had been
appended at the end); the roadmap's stated work order and the stale P-table rows
were corrected against verified code.

Validation: 39 focused tests across the four repaired areas, then a 143-test
regression batch (one optional skip) passed; Ruff and whitespace checks pass.
The dashboard and event dispatcher restarted on the new code and recalculated all
monitored strategies. Allocation revision 5, the 100% F3 allocation, approvals,
reconciliation and the live-disabled posture are unchanged.

## 2026-10-10 — Momentum/XGBoost/ridge ranks at the asset-selection stage

Executed the user's request to combine predictor rankings before selecting
the portfolio from the full 14-candidate pool. Corrected one terminology point:
the original M1 score is 75% momentum and 25% volume, not pure momentum. That
score, XGBoost forecasts and context/financial total-return ridge forecasts are
converted into comparable midranks and blended. No ETF is forced into a slot.
Positive126 momentum eligibility, top6/min4 and the defensive fallback remain.

Froze ten main blends before running: M/X 75/25 and 50/50; M/R 75/25 and 50/50,
M/X/R 50/25/25 and equal weights for each ridge group. Eight mean-only controls
match every ridge blend's availability. Three controls remove the downstream
XGBoost tilt; two match the equal blends to CP target gross; seven references
include exact M1, cap-only CP, earlier sizing-only ridge, funded F3, RP14 and
URTH. Primary arms retain the original downstream sizing and add no economic
weight tilt. Required ridge gaps revert to original selection; missing XGBoost
fails closed. Reused pinned models without refits or new prices. Protocol hash:
5399931f5267d8beceb1ff52b15d84a81547f4f1e8a285a413bace7702769276.

FR25 (75% M1 /25% financial ridge) and CR50 (50% M1 /50% context ridge) pass
the practical +0.05 Sharpe/+0.05 Calmar screen, risk budgets, paired mean-only
controls and cost/delay checks. Evaluation CAGR/Sharpe/Calmar are
13.09%/1.193/1.512 and 12.49%/1.171/1.533, versus CP's11.92%/1.106/1.435.
Corresponding earlier sizing-only results are12.03%/1.108/1.425 and
12.09%/1.122/1.436. Selection therefore produces larger effects in this sample,
without establishing that selection always dominates sizing. Neither leading
selector uses XGBoost in its blend; both retain its existing downstream tilt.
Equal predictor weights and a50% XGBoost selection share are not consistently
better. No contrast passes5% Holm across the50-comparison return family at
3/6/12-month blocks; recipe-screen passes are not promotion decisions.

FR25 is the stronger full-history lead: CAGR/Sharpe11.21%/1.109 versus
CP10.65%/1.062; drawdown-19.83% versus-19.49%. CR50's full-history drawdown
is-20.95%, and equal financial blending reaches-30.46%. FR25 changes13/70
selections, one asset each time; eight entrants outperform displaced ETFs
over the next rebalance-open interval. Average target gross rises only0.040pp
and annual traded notional falls8.59×→8.07×. Gains are materially concentrated
in2026: July TLT→XLE and August HYG→EWY correspond to+1.974pp/+1.670pp net
calendar outperformance; October2024 HYG→TLT loses-1.157pp. CR50's strong2021
gain is followed by weaker2022/2023. All episodes and assets remain visible in
the report; no new regime rules or weight search were added after outcomes.

Disposition: freeze FR25 as primary research candidate, CR50 secondary, for
prospective/concentration robustness evidence. Any future monitored strategy
must use the full app-owned service contract. No monitoring, funding, broker,
approval, reconciliation or paper/live controls changed. Sector-release
qualification remains queued; standalone SPY dip-buying remains deferred.

Implementation caught and fixed Decimal tie noise before protocol registration:
blend scores canonicalize to18 decimal places so exact rank ties resolve by
the declared symbol ordering. Six new behavior tests cover eligibility,
missing-model fallback, mean controls, tie handling and cap capacity. Alongside
existing tests,18 focused tests pass. All240 replays,30 native checks,54 exact
controls and72 inference jobs pass. Independently verified40,040 rank cells,
2,990 gate/cap/label contracts and unchanged decisions after poisoning future
prices/models. Thirty complete shared reports include full decision flows,
targets/held weights and benchmark comparisons. Local links, JavaScript,
source/artifact hashes, Ruff and whitespace pass. Browser automation blocks
file URLs; used direct source checks,1,540 DOM render states and visual chart
inspection without bypassing that restriction.

Evidence: research/selection-blend-2026-10-10/index.html;
var/research/selection-blend-20261010-v1/{protocol,report,acceptance}.json.
Preserved existing studies and unrelated repository/application work.

## 2026-10-10 — Full-pool IC challenge and portfolio-contribution diagnosis

User directs future research to the full candidate pool and asks whether IC
above 0.1 warrants deeper analysis. Recorded the standing full-pool rule in
AGENTS, research state and roadmap. No further standalone XLE/XLB-only tests;
individual-asset attribution remains part of explaining the full portfolio.

Froze a diagnostic protocol before new calculations. Reused the exact audited
price/economic pins, expanding-window models, decisions and trade ledgers of
expanded-economics-20261010-v1. No refits, parameter search, new strategy arms,
new prices or app/execution changes. Diagnostic protocol SHA-256:
5f5467917cfe5bb4d46debd02bd1a2ddc73383e61244bf789073920392cf0f4a.

The original interpretation was too broad: failure of the threshold-sizing
recipe is not rejection of the underlying economic ranking signal. Context,
financial and combined ridge total ICs are 0.1182/0.1188/0.1152, versus matched
training-mean ICs 0.0435/0.0706/0.0435. Macro-increment ICs are
0.0887/0.1213/0.1003. Marginal total-IC intervals are positive under every
3/6/12-month block length; financial/combined increment intervals also are
individually positive. Paired improvement over mean-only ranking is uncertain,
and none of 12 incremental contrasts passes Holm. Dependent months/assets,
inspected history, retrospective M1 selection and economic-vintage availability
limitations remain disclosed. Whole-pool MAE does not invalidate ranking merit.

Forecast IC uses total return predictions, while the overlay thresholds macro
increments at +/-25bp into +/-10% sizing and preserves membership/cash. Context
changes 40/70 decisions: 12 unavailable, six cash, two single holding, ten
uniform multiplier. Average capital shifted is 1.74% overall and 3.04% when
changed. Financial IC on the same months falls from 0.130 across 14 candidates
to 0.049 within held assets. These are transfer diagnostics, not restricted
universe tests or evidence that removing selection constraints would help.

Context adds +0.167pp CAGR/+0.0162 Sharpe/+0.0010 Calmar versus the cap-only
control. Its higher CAGR contributes +0.0202 Calmar and worse maximum drawdown
subtracts -0.0192. Costs are near neutral/favorable. Context adds +0.625pp in
2024, financial +0.943pp in 2022, but financial loses -0.644pp relative return
in 2025. During March 19-April 8, 2025, context adds -11.1bp to the drawdown;
all-asset attribution reconciles (XLE -23.9bp, MCHI +12.0bp, GLD +3.1bp, others
the balance). Context recovers June 24 versus CP June 12. Descriptive trend
splits disagree across models and are not promoted into new regime rules.

Retain context/financial ridge as signal-research leads. The exact sizing
recipes still fail the original +0.05 Sharpe/+0.05 Calmar screen; monitoring and
funded F3 are unchanged. Proposed next experiment: separately specify and
freeze a finite full-pool rank-based selection/sizing comparison, with
mean-only forecasts, matched cash/risk controls and prospective evidence where
available. New sector-release history qualification remains separately queued;
standalone SPY dip buying remains deferred.

Evidence: research/full-pool-signal-diagnostics-2026-10-10/index.html and
var/research/full-pool-signal-diagnostics-20261010-v1/. Verified 10,677 parent
manifest entries, seven replay bundles and exact NAV/cash/asset PnL. All prior
total ICs reproduce; 1,110 independent SciPy correlations and 414 monthly
active-weight return attributions pass. Twelve focused tests, Ruff, source/
artifact hashes, report links/anchors and static figure inspection pass.
Shared complete strategy reports remain linked from the frozen original study.
Preserved unrelated strategy-table work and all historical study artifacts.

## 2026-10-10 — Strategy comparison period returns and frozen names/actions

Added 1M, YTD and 1Y cumulative performance to the strategy registry, including
archived rows. Returns end at each row's Data Through date in its displayed
accounting currency. 1M/1Y use calendar offsets with month-end clamping; YTD
uses prior year-end. Each anchor is the last observed close on/before the
boundary. Missing anchors and invalid window values remain unavailable, with
no since-inception substitute, provider fetch, FX conversion or annualization.
The serving projection summarizes existing verified tracked NAVs; no strategy
retraining/replay or new historical research is required. Archived artifacts
retain their existing legacy-evidence status.

The table scrolls horizontally while the strategy name, report link and
monitoring/allocation buttons stay fixed together on the left. Headers remain
sticky, narrow layouts use a smaller frozen column, and the scroll region is
keyboard accessible. Automatic catalog refresh retains horizontal position.

Validation: 37 focused tests passed, one disposable-ClickHouse test skipped;
Ruff and whitespace checks passed. Browser checks covered narrow and desktop
layouts and real published values. All five monitored rows independently
reconcile to their October 9 NAVs. Restarted through the normal guarded local
launcher; allocation revision 5, active weights and pending state are unchanged.
Evidence: var/strategy-columns-tests.xml, var/strategy-columns-expected.json,
var/strategy-columns-acceptance.json. Preserved unrelated working-tree edits;
no commit or push requested. Paper/live, approval and reconciliation controls
are unchanged.

## 2026-10-10 — Expanded-pool economics completed; standalone SPY deferred

User explicitly deferred standalone SPY dip-buying and requested the next
research item. Recorded the independent SPY hypothesis without starting a new
experiment or automation. Executed the existing queued economic revisit after
ETF-universe admission, using M1/14's fixed candidate selection. Historical
energy/CFTC/issuer availability remains unqualified and was not bypassed.

Froze protocol `9265c4e96c0a48bc17815b422eeab40f8de29e21a3c45b33e0ffb4950916100a`
before model/portfolio outcomes. Pinned the October 8 audited price batch and
the original published sixteen-series economic batch. Recomputed all 130
monthly feature states and matched the previous frozen features exactly. All
new signals use those vintage-specific observations and completed monthly
labels, with inherited retrospective archive/price-availability limitations.
No online prices, source-archive research reads or missing-value substitutions.

The M1 parent has no final cap. Added CP as an explicit 45% final-target-cap
control, leaving clipped amounts in cash. Only four monthly decisions change,
with 0.183% average target cash added. Economic arms preserve exact CP gross,
cash and positive membership; no forced XLE/XLB allocation. Tested context,
financial and combined feature groups with the existing ridge/tree capacities,
plus matched-context availability. No threshold/grid search or monitored recipe
change. Shared 14-ETF and global-equity benchmarks accompany every report.

All 104 portfolio replays and 13 independent native full-history validations
passed. M1/F3/CR12/RP14/URTH controls reproduce exact original NAV, fills and
positions. All 57 inference jobs completed 10,000 paired calendar-block draws;
no 18-family mean-return contrast passes 5% Holm at any block length. Evaluated
520 monthly group models, with 336 ready group fits; insufficient history
abstains. Matched-context models reproduce original-context outputs exactly.

2021–October 8, USD/5bp/zero cash interest: M1 CAGR/Sharpe/Calmar/DD are
11.91%/1.104/1.433/-8.31%; CP 11.92%/1.106/1.435/-8.31%; context ridge
12.09%/1.122/1.436/-8.42%; financial ridge 12.03%/1.108/1.425/-8.44%;
combined ridge 12.04%/1.115/1.443/-8.34%. Context-ridge gains over CP are
only +0.0162 Sharpe/+0.0010 Calmar, below +0.05/+0.05 requirements. Its
six-month Sharpe interval includes zero; the positive twelve-month marginal
Sharpe interval does not establish joint return or Calmar superiority. Trees
fail paired linear comparisons; augmented candidates fail their stronger
matched-context hurdle. None passes retention.

XLE/XLB ridge forecast MAE is worse than the training-mean predictor in every
feature group: context 5.79% versus 5.01%, financial 5.39% versus 5.02%,
combined 6.53% versus 5.01%, on their respective availability-matched samples.
Context/combined ready 58/70 evaluation decisions, financial 70/70; prior
missing/stale observations and CPI windows remain unavailable. Context ridge
changes 40 decisions but its full-history gain is small and drawdown is worse.
Reject these variants for additional monitoring/promotion; preserve M1/14,
monitored CR12 and funded F3. Next is original-release sector/energy source
qualification, not another tuned combination of the same economic inputs.

Verification: 57 focused tests passed; initial test invocation named a
nonexistent test file and collected no tests, then the corrected complete set
passed. Ruff, immutable hashes, 910 selection/cash/cap/label checks, matched
samples, 13 shared report payloads, local links/embedded JavaScript and visual
plot checks passed. Control revision 5, monitoring membership and 270 order
records match the before snapshot. The app independently advanced to October
9 prices with empty analytics errors; this finite study retains its preregistered
October 8 common cutoff. No app restart, broker action, allocation or approval
change was needed. Paper/live safeguards and pre-existing dirty files preserved.

Evidence: `var/research/expanded-economics-20261010-v1/acceptance.json`;
full reports: `research/expanded-economics-2026-10-10/index.html`. Added isolated
research orchestration/analysis and tests; existing model and trading services
are unchanged. Execution Kanban P4.12 and research state are complete. No commit
or push requested.

## 2026-10-09 — M1/14 monitored; cash/stress and loser-basket research completed

User authorized monitoring the exact M1/14 candidate, then explicitly requested
a separate broad-market stress sleeve and bottom-momentum comparison. Registered
`research_m1_14_v1` on a distinct 14-ETF pool, with the shared selector/overlays,
audited raw-dollar activity and causal per-pool XGBoost/USD models. App-owned
signals, scheduled and indicative targets, held weights/NAV and full decision
reports now calculate through October 8. No manual research card or Codex
automation performs recurring calculations. The original execution-universe
gate stays closed for M1/14; monitoring is not capital approval.

Development and app replays exactly reproduce 130 monthly decisions, 907 fills,
2,707 NAV values and final positions. Nine app native checks passed. Current
revision is `baad7794e23ccaeee3d359fd6c6ee0565d6873cfd60c67e9cc31ffb5e9e991c6`;
the five currently monitored entries are Current. Membership was concurrently
changed to archive the former SOTA at 15:28 UTC, after our M1 addition; retained
that newer state. The generation guard discarded obsolete work and the next
complete publication passed. F3 control revision 5 and 270 order records are
unchanged. Acceptance: `var/research/m114-monitoring-20261009/runtime-final.json`.

Recovered development diagnostics without weakening gates: the first parity
bundle omitted required limitations metadata and was retained; its corrected
successor passed. The first app load demanded URTH before its January 12, 2012
inception. Corrected benchmark coverage to require the real anchor/valuation
calendar, while all 14 strategy histories retain full warmup requirements and
actual gaps still fail closed. No pre-inception rows were filled. Acceptance
hash validation uses the native runner's canonical economic digest, not a raw
JSON byte hash; source/native artifact checks remain intact.

Froze cash protocol `cc19d9f608c8484aedbf81afae41d3db9e696daed1f7f0b8be07d86760e10b4a`
before outcomes, on the current published audited batch and exact F3 targets.
Fourteen fixed policies × ZERO/BIL parking cover scheduled/stress/confirmed SPY,
bottom/top-three momentum and separate 10%/20% additional reserves. Stages are
10/20/30% drawdowns, one-third locked-budget tranches; recovery or twelve-month
exit, no repeated stage spending, parent funding priority and no added leverage.
An evaluation-only URTH control freezes its volatility match using 2016–2020.
Adjusted histories only for new signals, no direct provider archive prices or
unqualified FX; legacy parent limitations are explicit.

All 232 dynamic-to-frozen replays and 30 independent native checks passed.
Paired phase-dollar P&L reconciles terminal wealth; actual virtual ownership
cannot exceed held quantities. Diagnostic deployment counts exclude clipped
attempts with no material purchase. Nine initial cash-state/causality tests
plus a hand-calculated entry/exit fee-attribution test pass. The combined
focused regression covers 89 distinct tests, with Ruff and whitespace checks.
All 141 inference jobs completed 10,000 draws. Finalization initially withheld
publication while native runs continued; saved inference was reused unchanged
after the last parity check, with no resampling or frozen-input modification.

2021+ ZERO-cash CAGR: F3 10.58%, scheduled SPY 10.79%, stress SPY 10.76%,
confirmed SPY 10.65%, bottom-three 10.52%, top-three 10.58%. Bottom-three DD
is -11.98%, versus SPY -10.84% and F3 -11.69%. Extra fixed 10%/20% reserves
cost 1.07/2.14pp CAGR; stress buying recovers 0.09/0.18pp. BIL reduces fixed
reserve drag to 0.79/1.58pp, still beyond the 0.5pp sacrifice tolerance.
No effect/protection screen passes; no 46-family Holm result at any block size.
Only two existing-cash cycles are funded in full history and one in evaluation;
the 2020 parent had already invested its cash. Full-period Stage A drawdown is
effectively unchanged near -16.42%. Preserve these negative/inconclusive results;
do not promote, add a permanent reserve or optimize the bottom-rank rule from
this sample. This is not evidence against all possible reversal strategies.

Artifacts: `var/research/cash-stress-losers-20261009-v1/` and
`research/cash-stress-losers-2026-10-09/` (30 full shared reports, benchmark
comparisons, decision flows, targets/held weights, attribution and uncertainty).
Report/source hashes are retained separately from frozen economics. Settlement
timing, broker cash remuneration and account/product eligibility remain outside
qualified historical inputs. Existing paper/live-disabled approval, broker and
reconciliation checks are unchanged. Independent IB recorder competing-session
and unconfigured-email issues remain visible; no login or notification change.
Next: continue queued data qualification/information-signal research; preserve
M1/14 monitoring and F3 funding. No commit or push requested.

Final artifact acceptance verifies all frozen input/output hashes, nonnegative
cash, target cash floors and 22,960 actual-ownership events across the 232
replays. All 30 report payloads contain decision diagrams and matched benchmarks;
local links and embedded JavaScript syntax pass. The shared template's app
navigation links were made absolute for local-file reports. The comparison plot
was visually checked. Receipt: `var/research/cash-stress-losers-20261009-v1/acceptance.json`.
Final app read shows empty analytics errors, current October 8 prices and the
same accepted serving revision. Documentation and P4.11 status are complete.

## 2026-10-09 — Candidate-pool correction and finite momentum rerun

User clarified that ETF additions always meant the candidate pool, with no forced
allocation. Preserved the earlier all-asset inverse-volatility study as evidence
for a different question; its rejection cannot reject candidate-pool expansion.
Completed four predeclared selectors on matched 12/14 pools: existing 63/126/252,
faster 21/63/126, 21-session-skipped momentum and volatility-normalized momentum.
Each retains top six, positive gate, minimum-four breadth and defensive-cash
fallback. No new ETF is exempt from selection or revived by downstream layers.

Pinned published catalog 4bfdef171ba1d180f2191c589d269a9ad42e2f497b9f069b80e1e9043668f3fd;
XOP still quarantined. Adjusted OHLC for returns/direction, raw volume for activity,
raw close × raw volume for dollar turnover. New arms consistently use this basis;
exact legacy F3 benchmark retains its older activity proxy. The 12-pool bridge
changes CAGR only 9.8458%→9.8306%, and is not attributed to pool expansion.
Causal monthly one-year XGBoost schedules refit per pool; USD U1 also refits per
pool from already published snapshots. Architecture/parameters unchanged; momentum
variants share the same pool's model schedules. Unsupported inputs fail closed.

Findings (USD, 5bp, zero cash interest, through October 8): M0 12→14 full-history
CAGR 9.83%→9.56%, Sharpe 1.047→0.924, max drawdown -16.42%→-16.33%.
XLE selected 48/130 months, XLB 59/130; mean held weights 4.44%/6.62%.
M1/14 full CAGR/Sharpe/DD 10.64%/1.061/-19.48%; 2021+ 11.91%/1.104/-8.31%.
M0/14 2021+ is 10.14%/0.897/-12.89%. Faster momentum retains its 2021+ advantage
over M0/14 at 10/20bp and delayed execution, but the six-month-block Sharpe-delta
95% interval is [-0.083, +0.526]. All eleven paired mean-return contrasts fail
5% Holm across the three block lengths. Expansion under M1 versus M1/12 also
fails the combined cost/delay Sharpe-and-Calmar condition. M2/M3 do not establish
a superior replacement. Keep M1/14 as a finite research lead only; no promotion,
new monitoring, capital or execution authority. These previously inspected periods
are retrospective, not untouched out-of-sample evidence.

Found and corrected a specification description error: exact current F3 has no
final 45% cap; incoming inverse-volatility and later active bounds do not imply
one. Some economic-study controls do impose that cap. Preserved the exact F3
recipe and exposed concentration; corrected P4.11 R0 wording so an added cap
cannot be silently confounded with cash/stress deployment.

Evidence: var/research/candidate-pool-momentum-20261009-v1/.
Protocol SHA-256: 8242daf88c16cf28c8f12f16f68aafd84ff4ec71dfbc85d37cc0aa32acdfce60.
Report: research/candidate-pool-momentum-2026-10-09/index.html, with 12 complete
shared strategy reports, decision flow, latest scheduled targets/held weights,
selection frequencies, cost/delay, yearly/context metrics and uncertainty.
260 XGBoost fits, 94 accounting replays, 12 frozen-target native LEAN parity
checks, 36 inference jobs with 10,000 draws, exact legacy economics, 65 focused
tests and Ruff passed. Report finalization first withheld publication because
native checks were still running; inference was preserved and finalization
succeeded after all native checks passed. Frozen source/evidence are unchanged;
analysis/presentation editions and the unused-import cleanup are recorded separately.

Read-only acceptance: control revision 5 and 270 order records/statuses unchanged;
analytics errors empty and no changed strategies. No app restart or broker write.
Preserved pre-existing dirty files. P4.11 remains next on current F3/original pool,
with cash income, complete-cycle deployment/replenishment and falling-knife risk
explicitly registered before execution. No commit or push requested.

## 2026-10-09 — Audited sector ETF admission and frozen universe control

Continued the next research milestone before P4.11. Extended the app-owned
research ETF recorder with issuer ISIN/inception/exact-listing checks for
XLE/XOP/XLB. Published 6,991 sessions each for XLE/XLB through October 8 under
catalog `4bfdef171ba1d180f2191c589d269a9ad42e2f497b9f069b80e1e9043668f3fd`.
BIL is also current. XOP failed its listing-date gate: issuer June 23, 2006
versus provider first-trade metadata and first bar June 22. Preserved the
original capture, added a visible explicit admission hold, and excluded XOP
before portfolio outcomes. No trimming, relabeling or substitute history.

Read-only paper IB ISIN discovery verified BIL/XLE/XOP/XLB contract identities.
Account/product permissions and settlement eligibility remain unverified; no
order preview or order call was used. Issuer holdings residuals were inspected
without fabricating balancing entries. Holdings-derived features and split-aware
issuance remain blocked; no new issuer/EIA/CFTC record was backdated.

XLB publication twice hit a 30-second HTTP INSERT timeout. ClickHouse was healthy;
no rows or catalog publication from either failed attempt were persisted. The
exact transport cause is unproven. Bounded inserts to 1,000 rows instead of 10,000
while preserving full-batch SHA-256 readback and no uncertain-write retries.
The subsequent real publication succeeded. Multi-chunk corruption rejection is
covered by regression tests. Failed evidence and diagnostics remain in
`var/research/etf-admission-20261009/` and the referenced governance roots.

Froze a four-arm universe control: original 12 versus original plus XLE/XLB with
identical monthly inverse-63-session-volatility sizing, 45% target cap and 2%
cash floor; current capped F3 and URTH are separate benchmarks. One primary
contrast, 5/10/20bp costs, one-session delay and predeclared economic thresholds.
Verified the current app F3 parent through October 8 before freeze; an older
candidate input failed exact price equality and was not used. Published adjusted
prices are the only inputs to the two new arms. Original F3 prices/quotes,
decisions, NAV, fills and final positions reproduce exactly. Existing F3 retains
its inherited source-volume proxy limitation; no new activity signal is added.

Completed 14 replays, four full native parity checks and three block-bootstrap
jobs (10,000 draws each) with all 16 CPUs and bounded native memory. Added ETFs
change CAGR 5.73% to 6.16%, Sharpe 0.748 to 0.753, Calmar 0.255 to 0.311 and max
drawdown -22.46% to -19.81%. The +0.05 Sharpe threshold fails. Other economic and
cost/delay checks pass, but paired 3/6/12-month confidence intervals all include
zero; return p-values 0.224–0.265. Reject unchanged-sizing expansion under the
frozen screen. This does not establish the result of an expanded F3/model study.

Protocol SHA-256: `0d25e4fb623a25cbe52cceb0e5ae1e3c76b5244f3c961c1a3bfc424d0335ff7a`.
Frozen evidence/acceptance: `var/research/energy-materials-universe-20261009-v1/`.
Shared strategy reports/decision flows and comparison:
`research/energy-materials-universe-2026-10-09/index.html`.
Retained the initial presentation separately; corrected asset labels and made
annualization conventions explicit without changing any frozen calculation.
The report edition includes the exact presentation source and file hashes.

Validation: 68 focused tests pass, input/output/native hashes and exact parent
parity pass, Ruff/whitespace pass, and browser reports render with no errors or
warnings. No allocation/control/order change: revision 5, current SOTA F3 and
270 broker-order records match the initial snapshot. Preserved pre-existing
issuer/EIA changes and unrelated working files. No commit or push requested.
Next: P4.11 on retained capped F3 and the original 12 ETFs; freeze cash/parking
assumptions and complete-cycle stress/deployment/replenishment rules before
outcomes. XOP evidence and prospective holdings/account qualification remain
separate unresolved work, not reasons to assume additional admission.

Final guarded runtime acceptance: all eight app native runs passed hashes/parity;
new tracked revision `1ef8c43dd057b1a0ed3c38dd2b331528da54be174e9985860cbd5a704cf4617d`
is published. Five monitored strategies are current through October 8, analytics
errors/startup/freshness flags are clear, and allocation calculation status is OK.
Rechecked unchanged control revision 5 and all 270 order records. Application
acceptance is in `var/research/etf-admission-20261009/runtime-final.json` and
`app-native-acceptance.json`. Overall platform health remains degraded solely by
the separate IB market-data recorder's competing-session error 10197; no account
login/session was altered. Email alerts remain unconfigured. The temporary
report preview server and browser tab were closed after verification.

## 2026-10-09 — Cash reserve and stress-deployment research queued

The user requested adding the cash-for-market-stress idea to the research plan
for execution. Added P4.11 to the execution Kanban and the ETF expansion roadmap,
sequenced after the current ETF admission and frozen universe-control milestone.
Stage A compares unchanged capped F3 with scheduled, stress-staged and
recovery-confirmed deployment of existing defensive cash. Stage B separately
tests additional 10%/20% reserve sleeves against ordinary scheduled rebalancing;
it must retain every case rather than choose a historical winner.

The plan requires a frozen complete policy and predeclared economic tolerances,
full-cycle waiting/deployment/replenishment attribution, matched exposure and
benchmarks, audited pinned prices, explicit cash income and FX limitations,
dependence-aware crisis evidence, costs/delays and application/native replay
parity. Buying below a peak is not evidence of compensating for earlier cash drag.
Protection bought with lower return must be reported separately from return alpha.

Next: complete the current admission/control work, then pin one parent/universe,
qualify cash/FX coverage and freeze the finite P4.11 execution manifest before
calculating outcomes. Existing issuer/EIA changes are preserved. This session
changes planning documents only; it starts no backtest, recurring automation,
monitored strategy, promotion, capital allocation or order.

Validation: added local links and heading anchors resolve, P4.11 is unique and
belongs to the research Kanban table, pre-session document content is preserved,
and changed-file whitespace checks pass. No behavior changed, so no runtime
tests or service restart were needed. Planning is complete; study execution is
Pending under P4.11.

## 2026-10-09 — Issuer ETF fundamentals pilot recorded and inspected

Continued the next authorized research item: prospective issuer holdings,
shares/NAV and valuation/growth snapshots for XLE, XOP and XLB. Added the
six-hour application recorder, strict HTML/OOXML parsers, independent per-fund
raw-first publication, manifest-verified readers and Market Data → ETF
Fundamentals. Each capture preserves issuer section dates, actual completion
timestamps, original responses, normalized data, config and parser/recorder code.
The CLI uses the same service; recurring work belongs to the app.

First captures were October 8 16:21:59.873391 / 16:22:03.036322 /
16:22:06.157480 UTC, October 9 local. Statistics and holdings are dated October 7;
listing metadata October 8. The exact catalog pins and source links are in
`docs/issuer-etf-recorder.md`. NAV × rounded shares reconciles to displayed AUM.
Holding weight sums are 100.000861%, 99.977651% and 99.915674%. Their unexplained
residuals exceed displayed-precision rounding; the records remain inspectable
with yellow warnings, while holdings features are blocked. No balancing cash,
renormalization or constituent-sector substitution was introduced. Separate
NAV/characteristics/allocation groups can qualify prospectively. Rounded share
counts are not labeled flows and futures valuation weights are not notionals.

Strict first-capture cutoffs, unchanged-capture deduplication, same-date
revisions, naive/future/regressing/stale times, missing values, unit/identity
failures, publication retry, raw/hash tampering and independent-fund recovery
are covered. 83 distinct focused tests pass; one opt-in disposable ClickHouse
test skipped. Ruff and diff checks pass. Verified actual publications/readers,
then performed guarded app restart and browser checks for all funds, negative
holdings weights, missing sectors and warning colors. Browser errors/warnings
are empty; application analytics is error-free and strategies current through
October 7. Source/replay/admission/runtime evidence and screenshot are local in
`var/research/issuer-source-qualification-20261009/`.

The inspected price catalog already publishes 6,982 XLE/XLB sessions through
September 25 with explicit identity, historical availability and reconstructed
raw-basis limitations. XOP is absent. Next: common-cutoff price audit/publication,
security identity and read-only IB contract/account qualification, followed by a
frozen expanded-universe control. Historical issuer/estimates/share-action data,
holdings accounting residuals and additional industry activity remain gaps.
No new historical backtest, return-ratio claim, monitored definition, allocation
or execution authority changed. Existing EIA edits and unrelated runtime state
were preserved; no commit/push was requested in this implementation session.

## 2026-10-08 - Anchor allocation performance at first verified account NAV

- User requested the strategy NAV begin at account NAV on the first available verified results date, with later normalization using that date as 1.0. Implemented recovery after an unverified allocation gap: require exact app-published audited strategy NAV and observed account NAV on the same allocation close, set strategy NAV/index to account NAV/100, expose the comparison date and exclude earlier missing history with a warning. Recorded opening estimates cannot recover a chain after a gap.
- Aligned both chart lines to the anchor and labeled cumulative Strategy Return with its start date. The account summary remains cumulative from reset. Validation: allocation/dashboard/operator UI suite 37 passed; Ruff and `git diff --check` passed.

## 2026-10-07 - Economic context ridge monitored and financial challengers completed

- User requested the combined leading + payroll/inflation linear model in Monitored, then new economic inputs and ETF-specific combinations. Added the exact frozen CR recipe as `research_economic_context_ridge_v1`, with the unchanged F3 pipeline, final 45% target cap, thirteen original economic features, expanding per-ETF ridge alpha 1 and fixed availability/tilt rules. App-owned calculation includes historical/current signals, scheduled rebalances, holdings, targets, NAV, benchmarks, native parity and complete decision flow. Shared model receipts bind any later proposal preparation. Prospective decisions from October 8 require actual capture before the cutoff; archived catch-up cannot backdate economic knowledge. Missing features show a yellow capped-parent abstention notice.
- Durable user-authorized monitoring event `economic-context-monitor-20261007` created membership revision/generation 1. Accepted calculation `3ac2ba32ec1413383b849c589e7ccd7d593955e4adee3c7626025a57e169cc38` has five current allocation-ready monitored strategies through October 6. All 130 CR model decisions, 795 fills, 2,705 NAV values and final positions reproduce frozen economic-response v2. Four CNH and five USD native monitored/control runs passed. An earlier complete replay was withheld because newly captured required October 5 vintages changed its economic subset during calculation; the automatic immutable-input retry succeeded. Unrelated financial series do not invalidate the original recipe. Both attempts remain retained.
- Extended the recorder additively to T10Y3M/T10Y2Y weekday Treasury slopes, NFCICREDIT Friday weekly credit conditions and quarterly DRTSCILM/DRTSCIS bank lending standards. Source review kept restricted corporate bond spreads as an access gap; NFCI is explicitly not a bond spread. New frequency/calendar tests preserve negative values, null holidays and release/vintage boundaries. Initial Treasury captures failed on omitted January 2, 2006; retained those rejections and added disclosure of omitted initial closed weekdays only. January 3 open-day omissions and internal gaps still fail; no rows are inserted. Normal retries completed all 2,112 planned captures (132 per series), preserving the original 1,441 publication entries exactly. Economic batch `9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4`; all source hashes and ten new-series history API views verified. All sixteen indicators, source attribution and missing-data charts are available in Economic Data.
- Froze financial-condition study v1 before outcomes: eight financial-only features, augmented 21-feature set, paired ridge/depth-two trees and original-context ridge with matched samples/current availability. Every candidate applies directly to P3 and preserves its gross, cash, eligibility and final caps. No threshold, capacity, ETF or feature search. Original economic vintages and completed next-month labels use the declared retrospective archive availability assumption. Audited price batch a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2. Protocol `7744d4585a435d4a5781d84eab4de0f7757e75e7198e00de9f8db83d1cd7d4fd`; evidence `var/research/economic-financial-20261007-v1/`.
- Completed 51 replays in 63.75 seconds, eleven native accounting checks in 106.76 seconds and 27 inference jobs in 29.91 seconds. Used all 16 logical CPUs; native work uses three memory-bounded lanes sharing the CPU budget. F0/F3/P3/CR full-period controls reproduce exactly. All label cutoffs, matched samples, unchanged gross/membership/caps and frozen manifests verified. Financial inputs usable on 130/130 decisions; models ready 70/70 evaluation decisions versus 58/70 for augmented/matched. Matched ridge exactly reproduces CR. FR changes 42 monthly allocations and can increase equity, commodity or other eligible asset weights conditionally; it is not an equity-reduction rule.
- 2021–October 6, 2026, 5bp costs, USD zero-interest cash: CR CAGR 10.9995%, Sharpe 1.10267, Calmar 0.97399; financial ridge FR 11.1024% / 1.10574 / 0.97977; financial tree FT 11.0659% / 1.09917 / 0.95344; augmented ridge AR 11.0401% / 1.10294 / 0.97529; augmented tree AT 10.9007% / 1.08772 / 0.95270. FR passes the retention screen; AR fails delayed Calmar and both trees fail stronger comparisons. FR-minus-CR six-month ratio intervals include zero. No mean contrast passes 5% Holm at 3/6-month blocks; only FT-P3 passes the 12-month sensitivity (p=.0204), without surviving its linear/delay hurdles. Full-period FR Sharpe/Calmar trail CR, with drawdown 17.13% versus 16.83%. All combinations have worse forecast MAE than the asset-specific training mean. Retain FR as research evidence; no replacement or extra monitoring.
- 121 distinct focused tests passed (91 monitoring/recorder/model/lifecycle, 21 integration/reporting, eight financial-model, one additional receipt-binding test); Ruff and whitespace checks passed. Browser verified current CR report, holdings/targets, full flow, yellow abstention, all new indicators/source attribution and completed research findings, with no JavaScript errors. Findings and eleven complete reports: `research/economic-financial-2026-10-07/`. Deployment/verification receipts and screenshots: `var/research/economic-monitoring-20261007/`.
- SOTA, allocation control revision 3, pending F3 event d41767d9-04f4-4d1f-98f2-1e3f02aafb93, approvals and execution authority unchanged. No order or promotion action, commit or push. Separate preexisting `lean-history` archive ingestion still has a connection-timeout warning and normal retry; monitored and economic publications are complete. Next: issuer/ETF-universe admission and holdings/shares/NAV recorders, then sector activity/growth/valuation/positioning with qualified release histories. Revisit frozen economics after expansion; national PMI/consensus and corporate-spread access remain gaps; single stocks stay out of scope.

## 2026-10-07 - Economic asset-response experiment completed

- Resumed the authorized research after the allocation fix. Used the existing eleven-series app-owned vintage publication, so no new source was required. Froze seven leading features, six context features from four series, per-ETF depth-two trees and standardized ridge, 36 completed monthly labels minimum, fixed 10% multipliers and 25bp thresholds. Matched leading controls share the combined models' exact training rows and decision availability. Economic tilts preserve capped F3 gross/cash/membership and 45% final target caps. GDP, national-PMI substitution, consensus inference, single stocks and new instruments are excluded.
- Published audited adjusted-price batch a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2 and economic batch 25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460 are pinned with source hashes. Every training/query row uses its original archived economic vintage before the completed prior close; labels end by that cutoff. Daily ALFRED archive availability remains an explicit assumption; actual recorder first capture is October 2026. Price auditing does not prove historical dissemination or unresolved FX/holdings availability.
- Retained failed v1: the first calculation found a 1e-28 Decimal allocation-sum discrepancy before any portfolio replay/output inspection. Canonical 24-decimal rounding plus exact residual reconciliation repaired arithmetic only. No data, feature, model, threshold or hypothesis was tuned. Successful v2 protocol SHA-256 bd405774bb76310d0b8ddb9e2926435740a7088ba87f1dd80a224d09ed11165c; evidence var/research/economic-response-20261007-v2/.
- Completed 51 Python price/cost/delay/context replays in 85.21 seconds with 16 workers; eleven primary native LEAN checks in 117.85 seconds on three memory-bounded lanes sharing all 16 CPUs; 30 inference jobs in 54.26 seconds with 16 workers. Original full-period F0/F3 fills, NAV and final positions reproduce their frozen parent exactly. All 130 decisions passed label/cutoff/sample/cap/gross/membership checks. Twenty-one focused tests passed, including poisoned future-price, vintage, missing-month label and signed-response cases; Ruff and whitespace checks passed.
- January 2021–October 6, 2026, USD, 5bp costs, zero cash interest: capped F3/P3 CAGR 10.7781%, Sharpe 1.08113, Calmar 0.92200, drawdown 11.6899%. Leading tree LT: 10.9720% / 1.08406 / 0.92980 / 11.8003%; leading ridge LR: 10.9946% / 1.08964 / 0.97015 / 11.3328%; combined tree CT: 10.7932% / 1.08128 / 0.94867 / 11.3771%; combined ridge CR: 10.9995% / 1.10267 / 0.97399 / 11.2933%. Unchanged F3: 10.7402% / 1.07648 / 0.91852 / 11.6929%. Ridge arms pass declared cost/delay retention screens. Both trees fail to beat linear controls; CT also fails delayed Sharpe. At 20bp CR Sharpe remains 1.01567 versus P3 0.99407; delayed CR is 1.12084 versus P3 1.09891.
- No paired mean-return contrast passes 5% Holm across the nine-comparison family under 3/6/12-month blocks. CR minus P3 six-month adjusted p=0.7966; marginal Sharpe interval [0.00143, 0.04503], Calmar interval [-0.00394, 0.16238]. Ratio intervals are not familywise. CR context increment versus matched leading ridge is only 6.18bp CAGR / 0.00854 Sharpe. On full 2016-onward context CR Calmar declines to 0.59767 versus P3 0.60588, drawdown rises to 16.8256%; leading ridge lowers both ratios. Previously inspected years are not untouched OOS. Retain ridge for further evidence; reject these trees as replacements, no promotion.
- Leading availability is 66/70 evaluation decisions, combined/matched 58/70. All twelve decisions November 2025–October 2026 abstain in combined models; missing CPI interior observations are not filled from later revisions. Leading ridge next-month MAE 3.5745% versus 3.5895% historical-mean baseline, rank IC 0.1176; combined ridge MAE worsens to 3.7960% versus 3.4883%, rank IC 0.1121 on a different 58-month sample. Small portfolio gains do not establish a generally better return forecast. CR changed 35 allocations, increasing and decreasing several assets; beneficiaries outside the parent momentum basket remain excluded and untested. Conditional feature-response signs are descriptive, not identified causal shocks.
- Delivered research/economic-response-2026-10-07/findings.html, the complete assessment, eleven shared reports/flows and inspected comparison chart. Presentation-only findings supplement has separate source/report hashes and does not alter frozen v2 research. Updated research state, roadmap, experiment contract and kanban. Next recorder work: yield curve, credit spreads and lending standards with release/vintage contracts; prospective issuer holdings/shares/NAV before country/sector fundamentals. National PMI and pre-release consensus remain access gaps; no outcome-driven tuning.
- User-saved F3 pending event d41767d9-04f4-4d1f-98f2-1e3f02aafb93 remains at control revision 3 for October 7 close. No new allocation, approval, submission, live setting or monitored membership was changed. Monitored replay is complete/current through October 6. The independent lean-history archive-import lane still reports a connection timeout and retries normally; do not describe all analytics as error-free. Final acceptance records runtime state and report/hash checks separately. No commit or push.
- Final acceptance at 14:38 UTC passed all input/output/native hashes, eleven report NAV/held-weight/benchmark/flow checks, 16 local report links and browser inspection with no console warnings. The independent lean-history warning cleared through normal app recovery: analytics errors are now empty, four candidates remain available, all monitored reports are current and control revision 3/pending F3 event are unchanged. No additional service restart or intervention was needed. The shared report cash anchor explains its slightly different calendar annualization; study metrics and actual ledger economics are reconciled.

## 2026-10-07 - Allocation preview race, offline preparation and deferred rebalance

- User reported a null allocations error and a stale-reconciliation activation blocker while allocating to Qualifying defensive ETFs + cash. Confirmed the second attempt had already saved the requested allocation/SOTA change at control revision 3 for October 7 close. Preserved that event; no replacement or cancellation was performed.
- Reproduced the exact error against the unmodified editor: reopening/editing while a preview response is in flight clears the shared change object. The editor now ignores stale responses, captures the reviewed change for submission, guards missing historical rollback state, and cannot revive an invalid preview by rechecking approval. Added explicit yellow routing warnings, separate from red preparation failures, at the user's request.
- Removed broker freshness/connectivity from configuration preparation, preserving account identity, snapshot integrity, known reconciliation breaks, uncertainty, recipe/input and capital-cap checks. A dated activation stores its pending rebalance in the atomic control event and recovers a missed queue write idempotently. A missed handover remains pending for the next completed handover window; requested/effective dates stay distinct. Cached holdings are indicative, with the capture timestamp retained; actual routing still requires fresh matching balances.
- Added Refresh for approval on app-prepared allocation proposals. It creates a pending successor with recalculated quantities/window and immutable lineage; old routes become invalid, and approval/automatic authority never carry over. Known submissions, fills, partial/uncertain outcomes and ancestor attempts cannot be replayed by this action. Ordinary order-management controls remain authoritative. Original decision-price and TWAP references survive renewals in execution analytics and reference PnL; observed fills include approval/rescheduling delay. Unfilled attempts remain missed evidence, fees are separate, and unavailable original minute bars withhold the TWAP estimate.
- Validation: 202 passed / two optional disposable-PostgreSQL skips, Ruff and whitespace checks passed. Original-editor regression reproduced the exact reported exception. Deployed page opens normally and shows the unchanged pending change. Read-only real F3 preview against a deliberately one-hour-stale capture returned five indicative orders, zero activation blockers and one routing warning on price batch a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2; no production state was altered by that check. Normal dashboard/dispatcher restart deployed the fix. Accounting hash update triggered the normal all-16-core monitored replay, completed on revision 6c1cb0ccd5378480d7a4e94023b37d6a6da6a8e77a10cb3568e98229479e5f87; publication-race retries are kept separate from trading faults. Evidence: var/research/allocation-workflow-20261007/; contract: docs/trading-allocations.md. No real order was approved or submitted to test this work; live remains disabled.
- User requested that research continue after the fix. Next is the bounded eleven-series leading/context per-asset tree/linear experiment, with pinned vintages, matched missingness controls, completed labels and all-core reproducible replays. No data subscription, new instrument, strategy promotion or execution authority is implied.

## 2026-10-07 - Leading indicators, context groups and expanded recorder

- User asked for broader economic coverage (payroll, PMI, CPI), prioritized leading indicators over GDP, required ex-ante nonlinear predictions and asset-specific positive/negative responses, and confirmed no existing data subscription. Expanded the recorder before any economic portfolio experiment. Seven leading candidates now accompany four separate context series; GDP excluded. National PMI is still an explicit source gap, not replaced by a regional survey.
- Added AWHMAN, TEMPHELPS, NEWORDER, Philadelphia future orders/employment, PAYEMS, CPIAUCSL and CPILFESL. Verified official identities/units and original-vintage availability. Added an explicit predecessor-hash migration that permits only a larger registry with unchanged original series contracts and schedules; all original 393 captures remain byte-identical. Recorded all 1,441 planned captures through the app-owned bounded acquisition/publication service, including ongoing daily catch-up. One CPI request returned HTTP 404; its failed attempt was retained and the normal five-minute retry succeeded without substitution.
- Added versioned thirteen-feature definitions with seven leading candidates and a separate context group. Features use exact audited publications, conservative prior-day archives, group-specific freshness/completeness, signed diffusion levels and no fills. The frozen audit covers 130 decisions: 126 leading-ready and 118 context/combined-ready. CPI has an interior missing observation; the predeclared complete 13-month window conservatively excludes ten 2026 decisions per CPI series. This missingness must be controlled when comparing context against leading-only models. These are readiness results, not return predictions or profitability evidence.
- Market Data now lists all eleven series and visible pending source requirements. Browser verified the December 2015 Philadelphia future-orders archive, 120 rows with separate archive/first-seen timestamps, regional labelling and source gaps. PMI manufacturing/services/components, dated consensus, yield curve/credit/lending standards and country/sector releases remain roadmap items. No paid subscription was purchased or assumed. Historical use still has ALFRED date-level availability limitations; captured-in-2026 data are not represented as actual historical app observations.
- Validation: 68 passed / one optional skip, Ruff and whitespace checks; 22 real latest/earliest history API checks; all source hashes and original publication identities verified. Normal dashboard restart deployed the recorder migration. Temporary lock contention with the finite acquisition drain cleared; final analytics errors are empty. Four monitored strategies remain allocation-ready on tracked revision 723851d7f43e81bef82dd994218ebd9e4b7b2a731a32f165e76a4cbec0bc4cce; allocation/SOTA control revision 2 unchanged. IB remains disconnected; no broker orders or authority changes.
- The first readiness audit attempt passed extra provenance fields to the pinned reader and stopped after feature generation. Retained v1 with an explicit failure receipt; corrected v2 passed without source/formula changes. Final catalog 25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460; evidence var/research/economic-leading-panel-20261007-v2; report research/economic-leading-data-2026-10-07/assessment.html.
- Next: complete the broader per-ETF tree/linear experiment, leading-only then separate context ablation, with original historical vintages, completed labels, matched samples/availability, costs/delays, all-core replay and complete shared reports. The earlier economic_overlay/economic_models/economic_study draft remains unrun and is not an implemented strategy. No performance claim, promotion, allocation change, commit or push.

## 2026-10-07 - Economic recorder, full vintage capture and revision audit

- User resumed the ETF research roadmap. Completed the next recorder-first workstream: ICSA jobless claims, PERMIT housing permits and IPMAN manufacturing output. Verified official FRED/ALFRED definitions and archive-date limitations. Manufacturing is a coincident confirmation series; the panel is US-only and is not silently mapped onto foreign country ETFs. Historical index bases vary, so features compare growth within a vintage.
- Added `config/economic-recorders.json`, `recorders/economics.py`, the app analytics job, exact-vintage `EconomicInputs`, read-only economics APIs and Market Data → Economic Data with vintage selection, missing/stale labels, charts and provenance-bearing exports. Retained raw bytes before audit; verified schema/identity/calendar/domain/coverage and freshness; committed snapshots only after existing ClickHouse exact-hash readback. Catalog commits only published snapshots and reports planned/completed coverage. Consumers explicitly distinguish end-of-vintage-day New York archive availability from actual first capture; generic analytics availability uses first capture. No later-vintage substitution or forward fill.
- Finished all 393 indicator/vintage captures, 131 per series, for 130 monthly decisions from January 2016 through October 2026 plus October 6 current snapshot. Observations begin January 2006. Final catalog `bd5668b74622858a88bdc0619ce02cc27a6f26b3d13570b55e61fea1da3c0682`. Daily prospective captures and missed-day catch-up are app-owned. Initial serial bootstrap was interrupted only at its verified research recorder process to deploy bounded three-request concurrency; committed captures recovered and one uncommitted capture resumed after the existing five-minute retry window. Raw attempts were retained. No trading process or calculation artifact was stopped for this acquisition change.
- Fixed same-vintage diagnostic measurements before outcome inspection: four-week claims average versus thirteen-week average; three-month permits/manufacturing versus the same three months a year earlier. Verified the 130 decision dates against the frozen fallback study's hashed baseline schedule and every economic source manifest. Five readings fail the predeclared age limits: ICSA November 3, 2025 (41 days / 21 limit), PERMIT and IPMAN December 1 (119 / 100), PERMIT January 2, 2026 (152 / 100) and February 2 (121 / 100). No freshness limit was relaxed and no later release substituted. All captures completed, but full feature availability is not claimed.
- Of 385 usable decision/indicator measurements, 379 numeric values differ when recalculated from October 6, 2026 revised history at the exact original endpoints. Weakening flags change in 13/129 claims, 4/127 permits and 34/129 manufacturing cases: 51/385 overall. These are revision diagnostics, not independent economic events or performance evidence. No return model, threshold search or strategy backtest was run; all-core replay requirements remain for the next experiment. Freeze a small US-only overlay and explicit unavailable-input behavior before inspecting equity curves.
- Report: `research/economic-data-2026-10-07/assessment.html`; pinned inputs, features, protocol and acceptance: `var/research/economic-panel-20261007-v1/`. Guide: `docs/economic-vintage-recorder.md`. 61 relevant tests passed, one optional skip; Ruff/whitespace passed. UI tests cover lazy loading, vintage choice, missing-value line breaks, unavailable-data clearing and tab navigation. Updated two obsolete date-label assertions in the touched Market Data page test to its existing Captured From/Through wording, resolving that previously excluded failure. Browser verified real latest values, stale historic permits and 393/393 coverage.
- Normal dashboard deployment completed (dashboard PID 38896, dispatcher 7784 at acceptance). APIs match published data; a no-op recorder run does not reacquire completed identities. Analytics errors are empty; four monitored strategies remain allocation-ready and tracked revision `723851d7f43e81bef82dd994218ebd9e4b7b2a731a32f165e76a4cbec0bc4cce` is unchanged. Control revision 2 and 100% existing SOTA paper allocation remain unchanged. No promotion, orders, live enablement, commits or pushes. IB paper Gateway remains disconnected, so account-specific tradability checks still await that connection. Prospective issuer snapshots, release calendars, country panels and sector fundamentals remain subsequent research/data work.

## 2026-10-07 - Recorder-first BIL admission, F4 parking and IB tradability requirement

- User resumed the ETF research roadmap and subsequently required Interactive Brokers tradability, asking for the bill ticker and simplest purchase route. Selected BIL for its one-to-three-month US Treasury-bill mandate and long history before strategy outcomes. Verified issuer name, USD currency, ISIN US78468R6633, NYSE Arca listing, monthly distribution convention and May 25, 2007 inception against State Street. No paid feed or individual Treasury-bill ladder was introduced.
- Added `recorders/research_etfs.py`, the explicit research ETF source registry, an independent app analytics job, a read-only status endpoint and a Market Data recorder section. Raw issuer/provider bytes precede normalization. Identity, listing boundaries, required calendar, distributions, price revisions and hashes gate the existing exact-readback ClickHouse publisher. Failed captures retain evidence and retry after five minutes; completed captures are idempotent. Fixed bounded catalog inheritance to preserve newly admitted and recently updated untouched series on later active-universe refreshes. Tests cover quarantine, retry, source mutation and carry-forward integrity.
- Published BIL batch `a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`: 4,870 observations, May 30, 2007–October 6, 2026, zero internal gaps and complete 2012–2026 experiment coverage. The first five calendar days after issuer inception remain unsupported. Market Data shows the history and recorder status. Historical dissemination, independent price certification, dated holdings/mandates and account eligibility remain unverified; the source audit is not a historical-vintage certification. Source evidence: `var/governance/research-2026-10-06-e5d1b059d029/`.
- Froze `bill-parking-v1`, protocol SHA-256 `4ac477e45428bf49704b28b5fcde306b9d8003fe0a510dacc544e8ac4af0f0a8`, before outcomes. F4 preserves F1's final ETF weights and only on fewer-than-four-qualifier decisions parks residual cash in BIL, capped at 45% with at least 2% cash. BIL is excluded from model fitting/ranking and exits at normal monthly breadth. No fund/cap/trigger search, no F3/BIL combination, no new model fit. All input prices come from pinned published audited histories; previous control prices are exact matches.
- Completed 25 Python replays in 12.08 seconds using 16 workers, all seven primary native checks in 81.73 seconds using three 4-GiB lanes sharing 16 CPUs, and 20,000-draw paired analysis in 24.78 seconds with 16 workers. F0/F1/F3 exactly reproduce all 12 prior matched cost/delay controls' decisions, fills, daily NAV and final positions. Primary F4 CAGR 9.8409%, zero-reference Sharpe 1.04744, Calmar 0.58564, drawdown 16.8038%; F1 9.7019%/1.03389/0.57150/16.9761%; F3 9.9313%/1.05814/0.60482/16.4204%. F4 improves F1 by 13.9bp CAGR at 5bp costs and 9.6bp at 20bp, but remains behind F3. Only 18 fallback decisions / three episodes; strongest benefit 2022–23 and a slight early-2016 cost. Three-family Holm p-values versus F1 are 0.093/0.251/0.396 across block lengths, with 12-month ratio intervals including zero. Retain as a modest cash-management component, not established alpha or promotion evidence. Cash remains zero-interest and BIL distributions are embedded in adjusted prices.
- Delivered the assessment, inspected chart and seven full shared-format reports with decisions, holdings, NAV and matched SOTA/risk-parity/URTH/BIL comparisons at `research/bill-parking-2026-10-07/assessment.html`; frozen study `var/research/bill-parking-20261007-v1/`. Regression batch 98 passed / one optional skip; final IB-mapping/chart batch ten passed; Ruff and whitespace checks passed. No full-suite claim. Source/receipt/link/economic acceptance is captured in the study `acceptance.json` when the refreshed app publication completes.
- IBKR publicly lists BIL; the actual existing app mapper and IB API object pass `BIL / STK / SMART / USD` compatibility checks without network/order submission. The ETF mapper deliberately leaves primary exchange unset rather than sending the internal NYSE family as BIL's listing venue. User-facing guidance is the normal Client Portal Trade → Order Ticket → BIL ETF flow. Actual broker contract qualification, account/product permissions and paper order/reconciliation evidence are now explicit requirements before any new ETF strategy allocation. The local paper Gateway remains disconnected at port 4002; this prevents account-specific verification. No purchase, permission change or live enablement.
- Normal dashboard restart deploys the recorder and refreshes monitored reports. An acquisition-triggered replay overlapped code development and correctly failed the source-change publication guard; its uncommitted evidence remains at revision `5eaaa017216e51c9fb81bde72a9272e8f43a27643b2902bf3744b313ce3916a3`. After restart, revision `723851d7f43e81bef82dd994218ebd9e4b7b2a731a32f165e76a4cbec0bc4cce` encountered a native risk-parity replay stalled on its first time step (>3 minutes, ~3% CPU). Verified the exact container's input/output mounts, stopped only that finite benchmark process, retained failed attempt 1 and requested the app's normal identical-input retry. No stale or partial publication was substituted. Incident receipt: `app_stalled_attempt.json` in the study. Final runtime outcome is recorded below after acceptance.
- Current SOTA, monitored membership, funding, approval/reconciliation policy and live-disabled posture remain unchanged; no commit or push. Next data work: macro release-vintage recorder and prospective issuer holdings/shares/NAV snapshots, then a bounded country/energy/sector fundamental pilot. Historical broker interest remains an unresolved comparator; do not represent the zero-interest-cash test as an exact IB cash-return counterfactual.
- Final app recovery succeeded: risk-parity attempt 2 passed native parity in 33.63 seconds on the exact same manifest `c08c46fe0af81539561d1ed418bd0027505014a3d69915cc1dd4a81d6df01f3a`; failed attempt 1 remains intact. Complete tracked revision `723851d7f43e81bef82dd994218ebd9e4b7b2a731a32f165e76a4cbec0bc4cce` is published on the BIL-admitted data batch, with empty analytics errors and current-through-October-6 reports. App F3 NAV, fills and final positions still exactly equal the frozen study. Final acceptance receipt passed; public data view/browser and unchanged control revision 2 verified. IB account-specific checks remain pending solely on the disconnected Gateway, not on research or report completion.

## 2026-10-07 - Direct XGBoost ranking and portfolio construction research

- User resumed the ETF research roadmap, then added using XGBoost predictions for top-6/8/10 selection instead of only a portfolio tilt. Applied the continuous-research playbook. Before outcomes, froze `fallback-ranking-construction-v1`: 16 primary portfolios, 66 replay scenarios and 15 registered contrasts. Retained the current next-month relative-USD-return target, one-year rolling models, features and schedules. Three integration modes at each N isolate price/volume rank plus model tilt, price/volume rank without that tilt, and forecast rank without that tilt; P6 is F3. Eligibility, fallback, inverse-volatility sizing and later relative/adaptive/activity/USD layers remain fixed. No forced fill to N or cap/ranking combination.
- Added reusable research controls implementing the common TargetOverlay contract, a forecast pool adapter reusing the existing eligibility/fallback/sizing implementation, frozen batch orchestration, paired statistical analysis and standard reports. These finite recipes have no monitored/execution registration. All inputs use published audited adjusted-price batch `9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e` with verified model/USD archives and source hashes. Protocol SHA-256 `87170ad71831222e50845de82421fe69bae34dd6ec7d4a00c9f2bfbfb97178d4`; immutable study `var/research/ranking-construction-20261007-v1/`. No new source or recorder was required.
- Calibrated the constant-exposure control only on 60 monthly 2016–2020 decisions: factor 0.9151116667. Common evaluation starts January 4, 2021 with USD 1m cash and ends October 6, 2026. It is an already-inspected retrospective period, not untouched OOS. Primary 5bp/zero-interest results: F3 CAGR 10.740%, Sharpe 1.0765, Calmar 0.9185, DD 11.693%; forecast top 6 9.876%/1.0141/0.7945/12.431%; top 8 7.695%/0.8881/0.6264/12.284%; top 10 5.963%/0.7811/0.4843/12.312%. No-tilt price/volume top 6 Sharpe is 1.0668. Direct ranking did not improve this frozen forecast; widening the existing basket also weakened results.
- Forecast top 6 increases annual turnover from 5.87× to 7.93× and maximum held concentration from 53.65% to 55.29%. Higher-cost and extra-session-delay results retain its disadvantage. Average eligible-universe next-month rank IC is 0.110 for XGBoost versus 0.233 for price/volume across 57 complete eligible months; this is descriptive. All 15 paired mean-return tests fail 5% Holm significance under 3/6/12-month blocks, with minimum adjusted p-values 0.074/0.208/0.472. Six-month-block Sharpe difference interval for forecast top 6 minus F3 is [-0.189, +0.060]. Marginal ratio intervals are not familywise guarantees; Calmar bootstrap uses 252-session annualization. The as-of return bootstrap retains 70 calendar blocks including partial October; forecast accuracy diagnostics use only 69 complete forward months.
- Constant exposure gives Sharpe 0.8613 and DD 20.397%. Applying F3's same-date invested budget to F0 composition gives Sharpe 1.0769 and CAGR 10.744%, almost identical to F3. The result attributes protection mainly to exposure timing within the single post-calibration 2022–23 fallback episode, not a proved defensive-selection edge or future timing skill. The isolated 45% final target cap reduces full-history F3 maximum held weight from 53.65% to 46.64%, with CAGR 9.931% → 9.949% and Sharpe 1.0581 → 1.0608. Held drift remains possible; no new drift-rebalance rule was introduced. Retain as a risk-control candidate, not an alpha/promotion finding.
- All 130 baseline target schedules reproduce with zero difference. Full-history F0/F3 NAV, fills and final positions exactly match the prior fallback study. Completed 66 Python replays in 18.77 seconds using 16 workers and all 16 primary native execution/accounting parity checks in 127.21 seconds using three 4-GiB lanes sharing all 16 CPUs. Paired analysis used 16 workers and 20,000 replications per block specification. All 39 focused construction/fallback/rolling tests passed; Ruff, whitespace, input/output hashes and target-budget/selection checks passed. The study retains all recipes, including negative variants.
- Delivered an assessment, inspected comparison chart and 16 standard reports with portfolio histories, benchmarks, holdings and full decision flows at `research/ranking-construction-2026-10-07/assessment.html`. Updated research state, roadmap and kanban. Current paper SOTA and 100% funding remain the rolling XGBoost + activity + USD baseline, control revision 2; F3 remains monitored, with no new membership, promotion, order, approval, execution-authority or live-setting changes. The previous independent archive-history import warning has cleared through normal app recovery. No commit or push.
- Next: recorder-first Treasury-bill ETF coverage for F4 and release-vintage macro/issuer/industry inputs, exposed through Market Data before backtests. Preserve ETF-only scope. A new momentum forecast target or ranking-specific objective needs its own finite registration; neither was tuned in this batch. Prospective evidence, capital approval and any capped monitored recipe remain separate tasks.

## 2026-10-07 - Complete F3 monitoring report and archive/restore lifecycle

- User requested the qualifying defensive ETFs + cash strategy directly in Monitored, its complete standard report, Archive/Restore buttons, no ongoing archived calculations, monitored-only allocation and full catch-up after restore. Added durable, audited membership with revisions/generations and cross-scope transaction guards. Buttons are directly under each strategy name so they remain visible in the narrow app panel. Funded/current-SOTA/pending-allocation strategies cannot be archived; unavailable historical replay recipes are explained rather than silently treated as executable.
- Application analytics now owns the complete F3 USD history: signals, monthly rebalances/fills, cash, daily holdings/NAV, latest/scheduled weights, benchmark comparisons, model details and the decision flow. Archived histories remain readable and frozen; restore requires a new complete publication with all intervening decisions replayed. Membership, generation, date and published-batch guards apply to allocation previews, scheduling, activation and target plans. No Codex recurring calculation or research card was introduced.
- Pinned audited adjusted price batch `9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e`, verified USD/model inputs and application source produced revision `19bcca6e344472ec1187f95635513e7c11de43f486636f21dc6ee937a72ef099`, through October 6. F3 matches the frozen finite study exactly: 130 decisions, 2,705 daily values, 795 fills and final positions. Four new USD native parity runs (F3, matched SOTA, risk parity, URTH) and four existing monitored/control runs succeeded. All 16 CPUs are budgeted; native parallelism remains memory-bounded. Existing archived parent/control strategies are no longer silently recalculated as hidden monitored jobs.
- F3 report consistently identifies USD accounting, uses matched-USD benchmarks and separately labels signal attribution against the current SOTA. Final historical NAV is USD 2,768,412.30; Sharpe 1.0581, Calmar 0.6042, max drawdown 16.42%. The shared report's 9.9207% annualization differs slightly from the study's 9.93% because of calendar/anchor conventions; actual decisions and economics are identical. Zero USD cash interest, only three fallback episodes, retrospective reconstruction and input-availability limitations remain explicit. Prospective tracking conservatively begins October 8. A separate exact-date, hash-verified FX bridge supplies CNH comparison only where observed; no uncertified historical FX or USD-as-CNH substitution was added.
- Validation: consolidated affected suite 229 passed / one optional integration skip, plus the new per-request catalog-cache regression and final serving suite (21 passed / one skip). The unchanged Market Data UI test expecting the obsolete “Start Session” label remains excluded and was not repaired in this scope. Tests exercise archive/restore, revision races, protected roles, monitored-only allocation, report preservation, catch-up generation, missing FX and a three-month replay with missed sells/buys. Ruff and whitespace checks passed. Real browser verified visible Archive/Restore actions, a cancelled archive dialog, the complete report and currency/benchmark labels; no real strategy was archived for testing. Request-only catalog caching reduces repeated database reads without hiding later changes.
- Deployed through the normal dashboard/dispatcher scripts. Four strategies are monitored and allocation-ready; control revision 2, current SOTA, 100% paper assignment and no pending request are unchanged. Existing IB paper API disconnection remains visible and its routing/reconciliation blockers remain intact. No new source, order, promotion, approval-policy change, live enablement, commit or push. Architecture/resource guides, research state and kanban updated. Receipts: `var/research/strategy-lifecycle-20261007-tests.xml`, `strategy-lifecycle-serving-tests.xml`, `strategy-lifecycle-20261007-acceptance.json`, and publication `usd/study_comparison.json`. Next promotion/allocation remains with the operator.
- Final serving restart successfully deployed the explicit attribution label without recalculating the pinned strategy publication. The independent `lean-history` archive-ingestion lane reported a connection timeout and began its normal five-minute retry at 08:34:17 UTC; that retry remains in progress at the final receipt. Current monitored strategy publication, candidate eligibility and allocation checks passed throughout. ClickHouse reports healthy, with no recent server query exceptions. This archival ingestion warning is not a failed strategy replay; do not claim all analytics errors are clear. Inspect its completion separately if the warning persists.

## 2026-10-07 - Cash fallback implemented and first finite study completed

- User authorized starting the ETF roadmap, with application-owned recorders and Market Data publication before any new source enters research, and all-core backtesting. First bounded batch implemented F0–F3 against the operator-selected rolling XGBoost + activity + USD baseline. ETF-only scope retained.
- Added versioned pool fallback policies: retain eligible incoming weights plus cash; all cash below four qualifiers; eligible IEF/TLT/GLD incoming weights plus cash. A shared overlay pipeline preserves rejected membership and the declining invested budget. Incomplete features/short input universe fail calculation rather than authorize liquidation. Defaults preserve current strategies; four-or-more-qualifier decisions remain unchanged. Added full model-card decision flow and zero-variance Sharpe handling.
- Froze published price batch `9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e`, tracked revision `f37f34dddade4342e7fa2f8dcb3d38a45578b953427ecafafc4852a09cffbfe1`, audited USD snapshots, existing model schedules, source and finite definitions before inspecting returns. No provider archive/online price research inputs or historical uncertified FX. One orchestration cadence-name correction preceded all calculations; no strategy recipe was changed after outcomes.
- All 130 baseline decisions reproduce with zero weight difference; 19 Python replays cover F0–F3 and URTH at 5/10/20 bp plus delayed F0–F3 execution. Used 16 Python workers (8.30 seconds) and three native lanes totaling 16 CPUs, 4 GiB each (56.54 seconds). Four primary native execution/accounting parity checks passed. Native target schedules are frozen; separate shared-service baseline replay validates signal targets.
- Net USD zero-interest-cash results: parent CAGR 9.78%, Sharpe 0.978, Calmar 0.443, max drawdown 22.10%; F1 9.70%/1.034/0.572/16.98%; F2 9.92%/1.058/0.604/16.42%; F3 9.93%/1.058/0.605/16.42%. Eighteen fallback decisions form only three episodes. Cash missed gains in 2016 and 2018–19; benefit concentrates in 2022–23. Joint 3/6/12-month block inference gives paired mean-return intervals spanning zero and Holm p=1.00. Retain active strategy; no promotion, monitored membership, allocation, order or execution-authority change.
- First regression batch passed 81 tests; added/passed the constant-cash undefined-Sharpe regression subsequently. Focused Ruff checks passed. Study report and inspected chart: `research/fallback-results-2026-10-07.md`, `research/fallback-experiments-2026-10-07/`. Immutable calculations and receipts: `var/research/fallback-20261007-v1/`. Follow-up acceptance/runtime evidence is recorded below when complete.
- F4 was not run: BIL and SGOV are absent from the admitted governed history. Recorder implementation, audit/publication and visible Market Data coverage must precede a frozen parking experiment. No new source was needed or recorded for F0–F3. Matched-exposure controls, final-weight constraints, cash remuneration and prospective validation remain explicit next actions.
- Final acceptance: 27 focused fallback/momentum tests passed after the zero-variance fix; changed-code Ruff, normal repository whitespace checks and 22 local document links passed. Verified all frozen input/source/target hashes and compared each original Python result directly with native economic output. Restarted dashboard/analytics through the normal scripts to clear the source-change guard. All eight application strategy jobs completed and published revision `a07d102d9f41c7d38ad4f8111017ad3d7bfe926df8ee3c9235e5d82bfe5b0b9d`; the active baseline decision file is byte-identical to the prior publication. Analytics has no errors and current strategy/account calculations. Operator control remains revision 2, same SOTA and 100% paper assignment, no pending change. Runtime caveat: IB paper API is unavailable at localhost:4002 (no local IB API listener detected), so trading management is degraded; routing/environment checks were not bypassed. Other infrastructure, data recorder and backup services are healthy. Receipts: study `acceptance.json`, `runtime-acceptance.json`, `focused-tests.xml`. No commits or pushes.

## 2026-10-07 - Cash and alternative fallback added to research roadmap

- User requested testing removal of the full inverse-volatility fallback, allowing almost all cash and identifying alternative fallbacks. Confirmed `AssetPoolFilterOverlay.apply` passes incoming targets through when fewer than four ETFs qualify; later overlays still apply. It also has distinct unavailable-score and short-input early returns. Changing only survivor reallocation would leave the weak-breadth fallback intact. The active rolling definition inherits this pool layer.
- Added an early F0–F4 comparison family to `docs/etf-research-expansion-roadmap.md`: unchanged baseline; qualified base weights plus cash; all cash on weak breadth; qualified defensive IEF/TLT/GLD base weights plus cash; and a separately specified Treasury-bill ETF parking version. No risky-investment minimum; zero qualifiers may target 100% cash. Preserved normal behavior at four or more qualifiers in the first comparison, and separated final-cap changes from fallback attribution.
- Specified downstream selected-set/budget preservation, no revival of rejected assets, required-input failures as blockers rather than liquidation signals, unchanged initial rebalance/re-entry clock, cash credit/FX/parking data requirements, matched exposure/cost controls, episode attribution and zero-variance metric handling. Added app/LEAN parity and boundary-case acceptance requirements for later implementation.
- Documentation-only follow-up: no backtests, strategy implementation, deployment, portfolio allocation, order, promotion or scheduler changes. Verified current code/earlier report evidence, local links and changed-file whitespace. Next research implementation should begin with the active baseline fallback audit and frozen candidate definitions; performance benefits remain untested.

## 2026-10-07 - ETF research boundary and data expansion proposal

- User wants continuing Sharpe/Calmar improvement through country economic leading indicators, momentum/crash research, additional ETF exposures and sector/narrow-industry signals incorporating activity, growth, valuation, sentiment and positioning. Recorded an ETF-only trading boundary for this workstream; company financials may be used through dated ETF constituents, while individual-stock positions require the separate fundamental/Bayesian valuation workflow.
- Added `docs/etf-research-expansion-roadmap.md` as a discussion proposal. Anchored comparisons to the October 4 active rolling XGBoost + activity + USD strategy, recognized existing gold/broad-commodity exposure, prior inconclusive/negative incremental-signal evidence, and the inherited base-versus-final weight-cap issue. Proposed hierarchical exposure budgets, a separately versioned final-weight/drift contract, staged universe-versus-signal comparisons and macro/energy/sector pilots.
- Assessed official source documentation for ALFRED, OECD, EIA, CFTC, SEC, issuer ETF snapshots, ICI, LME, ACC, SIA/WSTS, PMI and point-in-time estimates. Prioritized dated holdings/issuance and release vintages. Documented that the existing SEC importer needs taxonomy, availability, quarterly/TTM and debt-ratio validation before sector use; provider manifests and static score maps do not constitute audited coverage. No subscription entitlement or historical completeness is assumed.
- Preserved published-audited-input and hash-pinning requirements, explicit adjusted/raw bases, missingness/identity thresholds and historical FX/holdings/vintage limitations. All recurring recorders, features and complete strategy reports belong to the application; no agent calculation schedule is proposed.
- Validation: reviewed source/code evidence and official source pages; checked the new document's local links and changed-file whitespace. Documentation only: no behavior tests required. No research calculations, downloads of research inputs, recorder/service deployments, orders, allocations, promotion, credentials, subscriptions, commits or pushes. Next: review the proposed source priorities and experiment scope, then implement the selected data/constraint package before frozen candidate comparisons.

## 2026-10-07 - System dashboard backup process and status

- Added **System → Backups** above the service map. It shows connection/capture/transfer/verification stages, current source-processing progress, previous completed NAS recovery point, capture/completion timestamps, protected and newly stored byte counts, PostgreSQL checkpoint results, next capture/retry, coverage and destination. Five-second polling and manual refresh are independent of platform health polling.
- Read-only `/api/v1/platform/backups` performs bounded local reads only: no NAS probe, database query, backup start or recovery action. Phase/time guards reject previous-run progress; new candidate summaries cannot be labelled as the previous completed snapshot. Missing state, stale heartbeats, stopped/paused workers and failed page refreshes are explicit. Response fields omit credentials, command output and individual source filenames. Progress represents source data processed, not network throughput, and completion requires worker verification.
- The earlier NAS stall caught up automatically: first full snapshot `70cfe9315379f9642a3747fe082f46269564f3b57cfefe53d71c6dca5cefe9b0` completed at 11:28:42 Shanghai (63,335,058,721 source bytes). The next capture finished at 11:51:49 and published verified snapshot `93b421cf36a3bf1dd3dcc1e82298a631e6d198024b77985f478073435c08e84d` at 11:53:51: 63.56 GB / 210,330 files, with 123.12 MB newly stored after deduplication. These are repository metadata and decrypted capture-manifest checks; a full data scrub and second-machine recovery rehearsal remain separate follow-ups.
- Validation: 29 focused API/status/JavaScript/platform-health tests passed; Ruff and whitespace checks passed. Real browser confirmed current completion, counts, checkpoint status, next schedule and manual refresh, with no browser errors. Deployed through normal dashboard stop/start scripts using the saved PostgreSQL/ClickHouse profile; backup worker PID 42536 continued throughout. The pre-existing account-calculation freshness warning cleared after the app's normal refresh; all eight required services were healthy at final verification. No order/approval/reconciliation/live-policy changes. Guide: `docs/full-system-backup.md`; receipts: `var/research/backup-dashboard-tests.xml`, `backup-dashboard-before.json`, `backup-dashboard-runtime.json` and `backup-dashboard.jpg`.

## 2026-10-07 - Full optional recovery backups and PostgreSQL/ClickHouse consolidation

- Final operating observation at 10:59 Shanghai: the first full transfer is **not complete**. NAS TCP remains reachable but SMB metadata stalled after worker deployment. Added a cancellable 30-second filesystem probe (in addition to the two-second TCP probe), with tests for the hung-SMB case and damaged repositories. The deployed worker reports `deferred`, retains the 10:40 capture and retries every five minutes. Local services and the verified compressed PostgreSQL NAS backup remain available. Full-system completion and a later full data scrub remain operational follow-ups, not completed claims.

- Confirmed no active application/research function depends on SQLite: defaults and factories use PostgreSQL for relational state and ClickHouse for time series. Reverified all 145,836 legacy rows, schema and sequence metadata against PostgreSQL archive `a7235fb109d493339812617b3d9895929fc053258b61ec3af28433716506f7c7`. Removed SQLite from the active NAS layout and CLI requirement for PostgreSQL configurations. The compatibility bridge verifies the exact frozen SQLite fingerprint and all incoming hashes, rejecting changed old-PC data; both PCs must upgrade. The original file and explicit test backend remain.
- Added the application-owned `system_backup` worker under existing database-worker supervision. Hourly native PostgreSQL, all non-system ClickHouse databases, NATS streams/consumer state, and durable project/raw/governed/research/LEAN/model/account artifacts are encrypted, compressed and deduplicated with pinned SHA-256-verified restic 0.18.1. Includes explicit pre-restore rollback evidence, effective non-secret environment settings and launcher configuration. Excludes credentials, private key material, PC-specific PID/sync identity, routine checkpoints, caches and ClickHouse system logs. The generated restic key stays in `var/private/system-backup-recovery-key.txt`; operator must preserve an off-device copy.
- NAS is optional: bounded preflight, a separate upload process, five-minute retry, persistent native capture and block reuse across interruptions, crash-released local locks, no forced remote lock takeover, explicit pause protection and platform health/status. A partial/unreadable candidate never receives `system-complete`; publication requires restic metadata checks and decrypted manifest readback. Full data scrubs are explicit and separate. Restores extract into empty isolated roots with a path map and content verification; no automatic live database replacement. Native components are individually consistent over a recorded interval; live files are read during upload, so this is not an atomic whole-machine image.
- Frequent SQL snapshots now use gzip while retaining logical revision semantics and old uncompressed reads. Real NAS generation `19b2d0d7d5c04ba4b0d4c5aedc0db924` has PostgreSQL only, 193,312,041 bytes versus approximately 2.15 GB uncompressed; independent NAS SHA-256 passed. Local/remote heads match. Existing NAS generations are retained; no automatic destructive retention was introduced.
- Validation: 62 focused checks passed / one optional SMB test skipped; seven launcher/storage checks passed; final affected suite 19 passed; Ruff clean. Restored the real custom PostgreSQL dump into a disposable PostgreSQL 18 cluster: all 19 tables loaded, including 1,662,057 outbox rows, 266 orders, 143 fills and the 145,836-row legacy archive. An isolated ClickHouse instance restored 142,076 daily bars and 3,935 FX rows with matching content hashes. An isolated NATS instance restored all 450,333 messages, 580,909,612 bytes and exact sequence bounds. Disposable servers are stopped; Docker probes removed. Automatic approval review rejected recursive deletion of the stopped PostgreSQL test cluster; those files are retained under excluded `var/system-backup/postgres-restore-drill`.
- Deployed the final workers without restarting trading services or changing broker/approval/live settings. Initial native capture spans 10:34:14–10:40:21 Shanghai, with 3,882 native files / 28,935,342,488 bytes; the full input set is about 63 GB across approximately 210,000 files before deduplication. Its first NAS upload remains in progress, with the same capture resumed after worker updates; no completed full-system NAS snapshot or full repository scrub is claimed yet. The app owns completion and future catch-up. Guide: `docs/full-system-backup.md`; receipts: `var/research/full-backup-acceptance-20261007.json`, `full-backup-*-restore.json`, `full-backup-compressed-sql-readback.json`, and test XMLs. Next: confirm first `system-complete` publication, preserve the recovery key off-device, perform a full repository data scrub, and later rehearse complete second-machine recovery.

## 2026-10-07 - Verify NAS database catch-up after returning home

- Read-only operational check confirmed NAS access, backup worker PID 36560 running, `published_local` with no sync error, and matching local/NAS head `2e951be140c84f49b1dbbf7bbe78b22c`. Snapshot observed October 7 at 10:06:17 Shanghai and publication completed at 10:11:34; multiple earlier October 7 generations confirm resumed periodic publication. Full snapshots capture accumulated database changes; missed offline timer runs are not recreated individually.
- Independently read both NAS files and verified SHA-256 against the NAS and corresponding local checkpoint manifests: PostgreSQL 2,106,812,241 bytes and SQLite 42,094,592 bytes. Checkpoint fingerprints match and local checkpoint SQLite integrity is `ok`; NAS head remained unchanged through verification at 10:16:57. Evidence: `var/research/nas-backup-verification-20261007.json`.
- Coverage remains PostgreSQL/SQLite only. The manifest inventories 43,612 external files, two governed roots and 30,937 ClickHouse publications but does not copy them. The configured raw-market-data NAS destination does not exist. Complete analytical/raw-data disaster recovery still requires separate backup and restore verification. No implementation, service restart, database replacement, broker action or policy change was performed.

## 2026-10-05 - Reset-anchored cumulative NAV and broker spot preview

- Follow-up corrects the earlier allocation comparison's handover-only anchor. Both cumulative paths now start at the confirmed reset opening. Executed, account-scoped legacy proposals and the subsequent explicit allocation record identify historical strategy periods; their daily close convention and intraday timing limitations are disclosed. Recovery is read-only and disclosed as a preceding-close approximation to intraday execution; allocation authority/history is not rewritten. The original SOTA NAV comes from its exact named benchmark in the app's audited USD report, pinned by publication/document/input hashes. The recovered theoretical path is carried through the recorded allocation handover.
- Cumulative headline NAV/returns stay anchored across switches, range selection and display rebasing. Allocation rows still show full-period results; actual-value rebasing changes period levels, not cumulative returns. Added live holding Spot and Daily % (IB marked position value / quantity versus audited prior raw close, contract currency), independent of the broker's P&L reset and intraday trading P&L denominator.
- The application analytics worker prepares pinned prior-close held weights, capital shares, raw marks, dated FX and recent account cash/quantities. Cached live callbacks append a provisional current-session endpoint to strategy/account series; no per-request source reads or broker connections. Account values require exact matching quantities and account identity, cash <=10 minutes old, fresh unambiguous USD equity marks and complete FX. Missing/stale inputs, delayed rebalance publications and out-of-session marks remain unavailable; brief pauses retain the last same-session browser point with its original timestamp and a stale label. FX is fixed at close, and dividends/fees/corporate actions/new cash movements since capture are explicitly provisional limitations. Daily histories and execution controls remain unchanged.
- Startup warms the performance cache from a validated publication before the slower account-capture import and refreshes it afterward. The first warm-up may fail safely if there is no account publication; a successful later build clears that transient error.
- Historical account imports took over ten minutes during live validation, exceeding the cash freshness bound. Added an independent five-second application worker reading only the newest app-written broker cash/quantity snapshot, retaining its hash and original capture time. Pinned return anchors remain unchanged and account/quantity/currency checks still gate each endpoint. No agent/automation performs recurring calculations.
- Validation complete: 97 relevant tests passed / one optional skip; Ruff and whitespace checks clean. The existing unrelated Market Data "Start Session" assertion was excluded as in the previous session. All eight app-owned native strategy calculations refreshed successfully. Final guarded API/dispatcher deployment (PIDs 48848/13868) passed the Gateway probe; spot worker is running with no analytics errors. Browser verified two different nonzero intraday strategy/account values, six Daily % rows, all-history/current-allocation ranges, both rebasing modes, and retention of the last same-session endpoint with explicit stale timestamps during callback pauses. Latest cash refreshed to 14:38:23 UTC while historical imports continued. No orders or allocation/approval/live-control mutations were made by this implementation; concurrent operator fills were reflected by the normal feed and quantity checks.
- Evidence: `var/research/reset-spot-performance-tests.xml`, `reset-spot-performance-acceptance.json`, `reset-spot-performance-chart.png`, `reset-spot-holdings.png`; contract: `docs/dashboard-performance.md`.

## 2026-10-05 - Allocation-period theoretical performance and rebasing

- User requested actual P&L versus each dated allocation's underlying theoretical strategy values, with continuous theoretical and actual-portfolio rebasing modes. Added an app-owned analytical comparison reading only complete published strategy NAV documents with audited batch/file lineage. Saved results retain publication version, document SHA-256 and original input provenance; publication races retain the prior complete result. No provider archives, online price calls or agent-scheduled calculations were introduced.
- Formula per allocation period: reserve weight plus the sum of capital weight × current strategy NAV / switch-close strategy NAV. Incoming virtual units start at the exact handover close; the outgoing allocation earns returns through that close. Continuous mode carries its closing theoretical value; actual mode uses each switch's observed account value or immutable opening valuation. Capital weights drift between switches, with flat CNH reserve; strategy-level scheduled rebalances and simulated costs remain embedded in NAV. This is an explicitly separate comparison from monthly capital resets, handover trading costs and the existing holdings/reference-fill accounting model.
- Both chart lines share a CNH P&L scale and original starting capital, fixed when selecting dates. Actual rebasing is shown with line breaks and excluded from strategy return/risk statistics. A per-allocation table compares actual NAV changes and theory at matched dates. Missing switch NAVs/components/US sessions remain unavailable and stop the affected period; a missing theoretical handover prevents later continuous compounding, while independently supported actual-rebased periods can resume. Earlier account assignments stay legacy/unverified, and cash-flow and historical FX/publication limitations remain disclosed.
- Runtime diagnosis: the opening-only comparison produced n/a. The follow-up recovers the evidenced strategy history from reset, and the app continues later observations through its published strategy service. Browser inspection also found NAV-based padding flattened small P&L changes and inclusive date clamping shifted the navigation caption one day; both are corrected.
- Validation: 112 relevant tests passed / one optional integration skip; 22 final focused checks plus 18 final UI checks passed, Ruff and whitespace checks clean. Performance tables scroll within their panel on narrow screens; the theoretical opening marker remains visible when it overlaps actual value. Broad verification exposed an unrelated pre-existing Market Data assertion for the removed “Start Session” label; that test remains unchanged and was excluded from the passing rerun. Tests cover mixed weights/reserve, switch continuity, actual resets without fake returns, missing anchors/sessions, invalid NAVs, publication races, opening-only API results and chart behavior. Browser verified both modes, Current allocation, shared P&L scale, correct date captions and 0.00% Strategy Return. Guarded dashboard/dispatcher deployment completed with a successful read-only Gateway probe; final PIDs 4844/39428. Allocation revision remains 2 with the original active version and no pending change. No strategy request, broker order, approval-policy change, live enablement, commit or push.
- Evidence: `var/research/allocation-performance-tests.xml`, `allocation-performance-final-tests.xml`, `allocation-performance-acceptance.json`; contract and limitations: `docs/dashboard-performance.md`. Next observations are owned by the existing application analytics worker; no manual historical assignment was inferred.

## 2026-10-04 - Simplify and refine Market History; CRSP access unavailable

- Added a top-level Debug switch, off by default, hiding Intraday Bars flags/raw evidence, provider archives, source comparisons, raw daily columns and audit lineage. Disabling it clears comparison overlays and returns an active Raw Data view to Historical Daily Price. Diagnostics remain available; this is a presentation preference, not an access-control change. Archives and bar views initialize on first activation.
- Renamed Audited Series to Historical Daily Price and Recorded Bars to Intraday Bars. USD is selected through the same Series field, with no special shortcut button. The existing verified USD publication remains an index series with its own units, gaps and provenance; decimal-string levels are converted for charting without fabricating OHLCV. Live browser loaded 5,410 USD observations, latest level 120.33. Future currency pairs can use this selector but were not acquired or implemented in this session.
- Refined Market Data's navigation, compact header, control sizing, focus/hover states, responsive filters, summary cards, chart grid and scrollable tables. Styling is scoped to this workspace. Browser verification at 1440 and 390 pixels found no page-wide horizontal overflow; the phone intraday table scrolls within its card. Confirmed 120 genuine IB candles, flags/evidence hidden by default and visible in Debug, raw-view exit, and a real Stooq comparison disappearing immediately when Debug is disabled. Restored the browser's original viewport. Screenshots: `var/research/market-history-normal.png`, `market-history-intraday.png`.
- Validation: 56 affected tests passed; subsequent layout/label refinements passed 19 and nine focused checks. Ruff and whitespace checks passed; browser reported no console errors. Restarted only the dashboard and event dispatcher through normal scripts; final read-only IB health probe passed. Existing independent historical recovery, source evidence, published research inputs, paper/live and approval settings are unchanged. Runtime reconciliation changes remain unstaged and unrelated.
- CRSP's official US Stock database and WRDS access documentation require licensed access. Operator confirmed no CRSP access: no download, ClickHouse import, demo replacement or speculative importer was made. Recorded the access blocker and future identity/basis/provenance requirements in `docs/crsp-data-access.md`. Next step requires a subscription or a licensed export; no purchase or third-party contact was authorized.

## 2026-10-04 - Correct sampled quote records presented as five-second OHLCV

- User challenged the line-like chart and identical open/high/low/close values. Inspected every retained pilot bar across September 25–October 4 reception partitions: 32,917 of 32,923 records flagged `ib_delayed_trade_aggregate` contain one observation with identical OHLC. The existing delayed `reqMktData` callback buckets were incorrectly described as complete five-second OHLCV; their observed sizes/counts cannot establish market volume/trade counts. Earlier recorder acceptance verified storage and advancing timestamps but missed this source-completeness issue.
- New outage recovery calls IB historical TRADES directly and maps independent OHLC fields. A fresh read-only SPY five-minute query returned 60 bars, all OHLCV fields matching recovered raw records. Example October 2 19:55:00 UTC: O 769.54 / H 769.72 / L 769.51 / C 769.57 / V 59,944. Also fixed official SDK `wap` mapping with legacy `average` compatibility; earlier missing WAP values remain preserved, not invented. Source receipts: `var/research/intraday-ohlcv-source-probe.json`, `intraday-ohlcv-diagnostic.json`.
- API now labels legacy/current samples explicitly, retains their original raw records and hashes, and excludes them from chart-ready bars. An explicit provenance filter runs before latest-row limits. Genuine flat/zero-volume broker bars remain intact. New sampled captures carry an incomplete-OHLCV flag and sampled source name; service/README wording no longer claims complete bars from that channel. Recovery independently acquires actual OHLCV without accepting sampled coverage as completion.
- Recorded Bars had defaulted to stream-only data and overlaid a closing-price line on candles. It now defaults to historical OHLCV, removes the overlay, initially shows the latest 120 loaded bars with full-range reset/pan/zoom, names capture dates correctly and uses exchange UTC timestamps consistently. Browser verified the deployed SPY candles/source/times; saved `var/research/intraday-ohlcv-candles.png`. Live API checks preserve old raw samples while excluding all 1,448 October 2 SPY samples from the candle view; 120 recovered bars pass hash checks.
- Validation: 95 affected tests passed (API/source filtering, real SDK mapping, raw recorder/recovery/service, and JavaScript candle/navigation/timezone behavior), Ruff passed. Normal dashboard/recorder restart resumed persistent acquisition: 51 complete windows / 34,920 slots, 4,359 pending at acceptance. New recovery records include WAP. Historical bars are delayed by the 20-minute-after-window-end eligibility rule, backlog and IB availability; complete realtime capture is not claimed. Paper/live/approval controls unchanged; no orders or research publication. Full bootstrap remains the operational follow-up. Receipts/tests: `var/research/intraday-ohlcv-deployment.json`, `intraday-ohlcv-tests.xml`.

## 2026-09-27 - Cross-application connection audit, repairs pending selection

- User requested a thorough audit after noticing inconsistent workspace appearance and historical missed rebalances remaining after the portfolio P&L reset. Inspected all four workspaces and the full SOTA report, local API responses, and producer/consumer paths across portfolio accounting, execution, targets, governed data, analytics, EOD, health, alerts and database handoff. No application behavior, portfolio baseline, approvals, strategy deployment or broker orders changed; existing uncommitted work preserved.
- Runtime evidence: reset cutoff `2026-09-25T03:59:59.999999Z`; attribution still contains 220 pre-reset missed orders and 18 pre-reset filled order aggregates. Its CNH -983.04 execution difference and -197.24 bps use different scopes. A stale standalone Gateway probe also disagrees with ongoing matched reconciliation. Existing shared strategy code does not unify governed research prices and production daily-bar inputs; recurring audited publication remains a missing producer for app-owned tracking.
- In-memory probes reproduce reference execution difference disappearing after accounting compaction, future-baseline holdings entering earlier P&L queries, and skipped missing-FX fills marked valuation-complete. Focused existing suite: 109 passed, two optional integration skips; no full-suite or live-execution certification claimed. Receipts/programs: `var/research/link-audit-*`, `var/research/link_audit_*.py`.
- Durable proposal: a versioned portfolio/account/environment episode with one start-session/timezone boundary and opening state, separate from accounting compaction and research prospective dates. Use it across monitoring and revision-aware EOD, preserve individual execution evidence and paired reference accounting, then unify target/data lineage, common presentation, operational freshness and restore prerequisites. Old working/uncertain orders and reconciliation problems must remain safety obligations regardless of monitoring date filters. Detailed 17-item register and acceptance criteria: `docs/app-connection-audit-2026-09-27.md`. Next action belongs to the user's repair-scope decision; this session intentionally stops at the audit.

## 2026-09-27 - Rolling XGBoost and lag-20 added to app tracking

- User requested rolling one-year XGBoost as another tracked candidate, with ETF activity lag-20 and a detailed strategy page. The original experiment omitted activity. Registered `research_rolling_xgboost_1y_lag20_v1`, replacing only the SOTA tree model and appending the existing activity overlay after the remaining SOTA steps. Tracking confers no execution or promotion authority.
- The analytics service now owns isolated monthly training, completed-label embargo, one-calendar-year outcome windows, immutable hashed requests/receipts and per-fit caching. All 16 cores fitted 129 monthly models in 10.3 seconds for the final preparation. Every model and all 1,884 training observations exactly reproduce the original study. Missing/stale/wrong-recipe models fail explicitly; indicative targets reuse the current monthly model with fresh features.
- Shared full report includes five matched benchmark choices, current held/last scheduled/latest indicative weights, NAV, period metrics/drawdowns, combined attribution, 26 feature definitions/current values, forecasts/activity signals, allocation after every executable stage, training provenance/download, all 100 inspectable fitted trees and the complete strategy flow. Current fit August 31 uses 120 observations and labels through July 31; latest prices/valuation September 25; next scheduled rebalance October 1.
- Five final native LEAN runs pass the existing Python parity checks and are registered in PostgreSQL. SOTA and activity-only economics are exactly unchanged; XGBoost-only NAV reproduces the original experiment through September 24. Combined full-history CAGR 10.093%, Sharpe 0.9675, drawdown -15.336%, final NAV CNH 2,807,393.56 from CNH 1 million. This is a selected retrospective result; forward tracking starts September 28. The prior 15.88% post-2023 research CAGR belongs to the candidate without activity.
- Published 8,100 observations/seven documents under ClickHouse revision `0d277ed7bb486f16db29250a9eddc0782bd073d625ac1f24e10b5232e5c5873c`. An initial native attempt pulled `psycopg` through the live calendar package; inference now selects from the verified input calendar without operational imports, protected by an import-blocking regression check. Failed revision `3e1a33034f2e8b69fe30447b1566769fa1856ebe07e03c31a6477bc8b84c8f19` remains unpublished audit evidence.
- Full suite 686 passed / 51 optional skips; final affected suite 41 passed / one skip; Ruff, whitespace and both rendered JavaScript blocks passed. Browser verified candidate navigation, model and activity tables, all-tree selection, zoom, matched benchmark switching and completed app refresh with no new tracked calculation or browser console errors. Standard guarded startup passed read-only IB health checks; paper policy unchanged. Guide: `docs/rolling-xgboost-lag20-tracking.md`; evidence: `var/research/rolling-tracking-acceptance.json`, `rolling-tracking-suite.xml`, `rolling-tracking-final-tests.xml`. Next: the app calculates prospective observations as new audited batches publish; retain separate promotion discipline and resolve historical price-vintage/FX limitations.

## 2026-09-27 - Rolling model investigation completed

- Completed 41 predeclared LEAN trials, each passing original Python target/fill/cash/NAV parity. Post-2023 CAGR: frozen SOTA 14.94%; rolling tree 1y/2y 15.21%/15.12%; forest 15.75%/15.42%; XGBoost 15.88%/15.36%. One-year forest/XGBoost gains versus SOTA survive matched 45bps cost, one-session delay and seed checks. Primary max-t adjusted p=0.020/0.014 at 63 sessions; findings remain conditional on revised/reused data.
- Critical control: frozen forest/XGBoost return 15.68%/15.72%, and removing the original tree returns 15.49%. Rolling 1y adds only 0.063/0.159 annual percentage points versus its frozen family; confidence intervals include zero and adjusted p=0.692/0.529. Two-year ensembles lose versus frozen family controls. Long-history CAGR: reconstructed SOTA 9.63%, forest1y 9.97%, XGBoost1y 9.94%; long adjusted p=0.068/0.108. Gains cluster in 2025–26; all variants lag SOTA in 2020. Retain SOTA; one-year ensembles merit a fixed prospective comparison, without claiming that rolling retraining itself has proven added value.
- All 1,136 fitted models and native artifacts are retained under `D:/systematic_trading_data/lean/research/rolling-models-20260927-v1/`; report, three inspected figures, CSV, causal fit records and paired uncertainty are complete. ClickHouse exact readback stored 52,749 NAV/metric observations and six documents; all 41 native receipts are registered in PostgreSQL. One native long-SOTA run stalled at its first step and was stopped; its identical-bundle retry passed in 60.7 seconds. Initial interrupted receipts and unused preflight control schedules remain separate immutable evidence. All finite workers finished; no recurring agent calculation was installed.
- Verification: 45 focused and 67 extended checks passed, one optional integration skipped in each suite; native/portable unseen-input prediction equivalence, chronological leakage/window checks, Ruff and whitespace passed. Source and replay guide: `docs/rolling-model-research-2026-09-27.md`. No provider archive inputs, broker commands, tracked membership, paper-policy or promotion changes. Next: if chosen for forward observation, implement complete app-owned rolling/frozen ensemble definitions and shared reports before tracking; continue price-vintage/FX certification separately.

## 2026-09-27 - Rolling model experiment started

- User requested one-/two-year rolling tree/forest fits and XGBoost, permitting overnight or multi-day calculations, then explicitly requested all CPU cores. Froze a 41-run protocol before observing performance. Independent monthly fits use 16 processes with one library thread each; remaining 491 fits took about five seconds. Portfolio/backtest preparation uses eight processes and two-CPU offline LEAN containers. Calculations are a finite application research job, not an agent-maintained tracked strategy.
- Added causal trailing-window selection, strict completed-label embargo, full-feature coverage, portable forest/XGBoost inference and native prediction equivalence checks. Retained the SOTA features, labels and portfolio rules. All inputs come from committed audited price batch `69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3`, with pinned hashes and unchanged disclosed legacy FX. Revised vintages and fixed-universe/FX limitations remain; no untouched-holdout claim.
- Matrix includes six rolling variants, actual frozen-tree and frozen-ensemble controls, tree-free/risk-parity controls, 2016 stress history, matched costs/delay and two additional forest/XGBoost seeds. Initial threaded preparation was replaced with processes; eight interrupted native receipts and complete reusable bundles are retained, with a finite resume queued after the active batch. Two unused frozen-control schedules were retained after correcting fit availability to the last prior close. Neither correction used performance results.
- Focused checks 45 passed/one optional skip; extended causal/feature/strategy/LEAN checks 67 passed/one optional skip; Ruff and diff checks pass. First native simulations pass parity; final analysis remains pending. Durable protocol/replay: `docs/rolling-model-research-2026-09-27.md`; outputs: `D:/systematic_trading_data/lean/research/rolling-models-20260927-v1/`. Tracked membership, broker approvals, paper policy and promotion state are unchanged. Next: verify all 41 receipts, inspect charts and paired uncertainty, archive research evidence and report whether rolling fitting helps.

## 2026-09-27 - Source publication preparation

- User requested commit and push of the completed changes. Prepared 48 source, configuration, test and documentation files covering audited-input research, shared chart navigation and app-owned Python/LEAN strategy tracking. Generated histories, native results, databases and operational reconciliation records are excluded.
- Staged Python/JSON parsing, whitespace and Ruff passed; retained full/final test receipts have no failures. Remote `master` matched the starting revision. Direct GitHub HTTPS failed to connect; fetching through the existing Windows proxy succeeded without changing persistent network or Git settings.

## 2026-09-27 - Application-owned tracked strategies and complete reports

- User correction: recurring strategy calculations belong to the application, with either Python or LEAN. Deleted Codex automation `track-etf-lag-20-research-candidate`, retired the daily review command, and recorded the rule in `AGENTS.md` and the continuous research playbook. The original research card/publication remains archived evidence. ETF lag-20 is a complete executable definition sharing SOTA's unchanged base and frozen activity parameters; it remains tracked, without promotion or execution authority.
- Added a reusable monthly multi-asset calculation adapter, configured to native LEAN with Python parity and also supporting isolated Python execution. Audited batches, full definitions, model/FX evidence, source, fees and dates are versioned; changed inputs trigger app-owned signal/rebalance/NAV/current held/latest indicative target calculations. Both monitored strategies and matched benchmarks publish atomically to ClickHouse; unchanged revisions are reused. HTTP readers serve saved results, and **Refresh calculations** wakes the app worker. Source changes require restarting the loaded implementation; failed calculations preserve complete reports while other analytical projections continue.
- Replaced the short research card with the shared full SOTA report: risk parity on the matched universe, URTH and SOTA benchmarks, metrics/IR, drawdowns, contributions, signal attribution, current portfolio/target weights, and zoomable/pannable full strategy and regression-tree diagrams. SOTA signal attribution compares its combined overlays with risk parity; lag-20 attribution compares with SOTA. The dashboard now accepts app-calculated NAV without legacy static-holding extension fields.
- History covers 2016-01-04 through 2026-09-25 with an initial-capital anchor on 2015-12-31: pinned causal annual trees through 2022, unchanged deployed frozen tree from 2023. This resolves the old frozen-model companion's 2023-only display without applying a future-trained tree backwards. It is a disclosed reconstruction, different from the prior all-years annual-refit experiment. Legacy FX and unavailable historical publication vintages remain explicit limitations. Validated direct IB USD/CNH evidence extends valuation through September 25; source evidence is also in ClickHouse. No forward sessions precede the declared September 28 start.
- Current matched reconstruction: lag-20 CAGR 9.799%, Sharpe 0.95835, NAV CNH 2,727,983.35; SOTA 9.656%, 0.94921, CNH 2,690,124.87 from CNH 1 million initial capital. Lag-20 daily-return IR versus SOTA is +0.2610. These descriptive results do not change the user's track-only decision or satisfy additional promotion requirements.
- Validation: full suite 668 passed / 51 optional skips; final API, reporting, attribution and worker regression suite 62 passed / one optional skip, plus 14 final source/renderer checks. Normal NAS-guarded deployment waited for a verified backup to finish; ownership and lock checks were preserved. Paper policy and production SOTA definition are unchanged. Native replay, ClickHouse publication and UI acceptance are recorded in `var/research/app-tracking-acceptance.json`; native immutable runs are under `var/tracked_strategies/`. Protocol: `docs/etf-activity-lag20-tracking.md`.
- Final acceptance: calculation revision `eec1b3569b2f3441fd3679095bd8ced5bddecb4f8383d78552213172be48d10d`; three native runs passed parity, with 5,400 observations and five documents published together. A serving-publication connection timeout preserved the previous report and cleared on app retry. Browser confirmed both corrected attribution baselines, all report sections, three benchmark selections, full decision diagrams/zoom/pan and successful app refresh without calculation changes. All eight services were healthy after a fresh read-only IB probe; dashboard PID 10580. Historical self-benchmark IR can reflect floating-point noise when tracking error is approximately zero; treat it as undefined and exclude self-comparisons from research decisions. Candidate-versus-SOTA metrics are unaffected.

## 2026-09-26 - ETF lag-20 research tracking, no promotion

- User explicitly chose tracking without SOTA promotion. Froze exact lag-20 overlay and fixed deployed-model baseline, native run receipts/manifests and historical summary hashes. Registered ClickHouse research publication with 935 paired historical NAV observations and two documents. Research tracking is isolated from production definitions and the existing static final-holdings marking path. New Monitored entry has historical comparison chart/zoom controls, explicit forward boundary 2026-09-28, zero accepted forward sessions and null forward metrics.
- Daily 09:00 Asia/Shanghai heartbeat `track-etf-lag-20-research-candidate` reviews published audited inputs and records status. It stays quiet on unchanged conditions and reports meaningful new evidence or problems. The review command is a status publisher, not a replay/import engine; fresh supported versioned FX and audited ETF coverage plus matched native LEAN parity/overlap reconciliation are still required. First forward acceptance/import work occurs when a valid new pair exists. No online/canonical price fallback, historical relabelling, parameter tuning, capital allocation or automatic promotion. Details: `docs/etf-activity-lag20-tracking.md`.
- Validation: 59 focused tests passed / one optional integration skipped, Ruff clean; rejection of modified evidence/parameters and historical/prospective overlap, unchanged-review idempotency, no marking/report fallback and SOTA identity preserved. Browser verified registry route, historical/future labels and comparison chart. Standard NAS-preflight/guarded dashboard restart deployed the change; API confirms SOTA and paper approval policy unchanged. Receipts: `var/research/activity-tracking-tests.xml`, `activity-tracking-acceptance.json`.


## 2026-09-26 - Audited research rerun, input policy and Market History

- Rebuilt signals/labels and annual causal base/residual models from governed batch `69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3`, preserving explicit raw/adjusted bases, identity exclusions and missing observations. Frozen 24-run protocol completed in native LEAN with unchanged parity and risk bounds. Baseline 2016–2026 CAGR/Sharpe 9.84%/0.956; early signed 9.82%/0.955, IR -0.172; concentration IR -0.289. Early integration does not establish improvement. Fixed ETF lag-20 remains observational (9.99%/0.966, IR +0.285, family-adjusted p=0.574). No SOTA promotion or trading-policy change.
- Material coverage correction: only 32/129 monthly decisions qualify versus 122 under legacy features; first qualified daily date July 17, 2023, first monthly decision August 1. Unsupported raw prices and identities dominate early shortfalls. Earlier fallback periods are not constituent validation. The 19 regenerated scatter grids use 551 common dates and fixed-cohort forward labels without survivor reweighting. Native receipts, plots, uncertainty, matched old/new comparisons and decomposition are frozen under `D:/systematic_trading_data/lean/research/audited-rerun-20260926-v1/`. ClickHouse exact-readback publications hold 11,862 observations/22 documents; 24 runs registered in PostgreSQL. Findings: `docs/audited-research-rerun-2026-09-26.md`.
- User directed all future price research to audited continuous histories; recorded the requirement in AGENTS.md and the recurring playbook. New online acquisitions must be audited/published before research use. Raw provider archives remain inspection evidence; audited raw-price versions remain appropriate for activity signals. Unknown vintages/FX/holdings timing are not silently certified.
- Reorganized Market Data as Market History with Audited Series and Recorded Bars plus nested Raw Data; preserved old deep links. Added shared zoom/pan/reset to other market, trading-performance, P&L/slippage, archived-strategy and standalone-report time-series charts. Full-history defaults for audited/performance views; bounded source-page scopes are explicit. Browser verified drag selections, panning and resets in real app views, including date-field synchronization and unchanged report normalization. HTML exports embed their controls; publication signatures include the navigation code.
- Validation: 652 tests passed / 51 optional integrations skipped; all-source Ruff clean. Additional shipped-JavaScript checks cover transformed coordinates, reversed drag, pointer capture/cancellation, refreshed domains, intraday precision, independent windows and archived/exported normalization. Evidence: `var/research/audited-rerun-full-tests.txt`, `var/research/audited-ui-verification.json`.
- Deployment incident: Windows reported the existing NAS share as Reconnecting, stalling the normal dashboard start. Reconnecting that existing mapping restored access; the first guarded start then correctly declined during a backup lock. After the backup finished, the normal retry succeeded without removing locks, changing ownership or bypassing guards. Dashboard/dispatcher running; all eight services healthy after a real read-only IB health probe. Existing paper policy compares identical. Next actions: resolve historical identity/raw-price gaps in a new governed batch; prospective/cost-delay evidence for fixed lag-20; no promotion based on reused samples.

## 2026-09-26 - Interactive governed price histories

- Pre-push verification of the completed research, analytical storage, governance and chart source bundle: 645 tests passed, 51 optional integrations skipped, Ruff clean, staged Python syntax/import closure and whitespace checks passed. Receipt: `var/research/pre-push-20260926-tests.xml`. Generated datasets, local runtime evidence and reconciliation state are excluded from Git publication.

- User requested full-history defaults, drag selection to zoom and drag panning. Added a shared date viewport to the governed and original-source charts, Zoom/Pan controls, Shift+drag, Full history reset and keyboard navigation. Pointer capture keeps drags bounded and releases outside the plot; Esc/cancellation restores the prior pan window. Dates, table rows and JSON exports follow the selected window. New underlyings reset to the full range; source/basis changes retain the current range within available bounds. Both charts rescale to visible values while preserving nulls and audited gaps. Chart navigation uses already loaded data; old audit content clears during an underlying switch and stale responses cannot overwrite it.
- Validation: 25 focused tests passed, including a Node DOM fixture executing the actual inline pointer/keyboard/render/loading handlers. Ruff clean. Browser verified AAPL 1980-12-12–2026-09-25 default, zoom to 2012-02-08–2021-04-02, equal-span pan to 2010-04-11–2019-06-04, reverse source-chart selection, Home/Full history, exact date inputs and basis retention. HYG opens 2007-04-11–2026-09-25. GE raw remains empty despite its long date axis; ASRT has zero governed rows while its archived source comparison remains available. No browser console errors. Receipts: var/research/governed-chart-tests.xml and governed-chart-ui-verification.json.
- Deployed through the standard guarded dashboard restart, health 200 and existing paper policy byte-identical. This changes chart navigation only; frozen governed data and strategy inputs are unchanged.

## 2026-09-26 - Governed underlying histories and adjustment/identity audit

- User requested a joined, audited per-underlying history with explicit raw and dividend-adjusted versions, persistent ClickHouse evidence, and comparisons in the existing Market Data page. Inventoried the historical stock constituents, public Yahoo2020/Stooq2017 archives, strategy ETFs and all 39 existing Market Bars ETFs. Retained immutable source JSON/CSV, request failures, action ledgers, dated issuer-name evidence, calendar and code manifests. Unknown historical availability remains null; raw values are conditional split-ledger reconstructions, never relabelled adjusted Close or certified exchange tape. Missing/uncertain values remain missing.
- Material input finding: the earlier frozen ETF snapshot mixes adjustment/source vintages. HYG's May 26 daily return is -1.6528% in the old snapshot versus +0.3379% in the new consistent provider vintage (1.9907 percentage-point discrepancy); SPY/LQD show the same saved SQLite-to-platform source boundary, while EWH has an earlier unexplained discrepancy. These are measured comparisons, not independent tape certification. Earlier backtests and their incremental IRs are provisional; rerun baseline and candidates on pinned governed data before any promotion. Existing strategy, trading-data reader and controls are unchanged.
- Final identity review rejected the first governed build before publication: archived NET/WMS/TXG/DAL series included old economic identities preceding the current listing while still passing recent overlap checks. Added policy-v2 provider listing boundaries, per-source quarantined date counts and explicit comparison exclusions; retain original source columns but no aligned values for excluded eras. NET begins September 13, 2019 and WMS July 25, 2014, corroborated by issuer/SEC sources in the guide. ASRT returned newer listing metadata with entirely older prices and is withheld, not force-joined. V1 remains frozen locally with partial database rows inaccessible through the committed-catalog API; exact incident evidence saved under governance/quarantine/00eed508ed7a2a570bc3ba917f86ea09dac674306911e657c03e20bf6b12d07c. The publisher refuses v1.
- Implementation: versioned governed_daily/governance_comparisons tables, row/source SHA256 readback, atomic catalog publication, full lineage and actions, and Governed Histories UI with basis/source/date controls, review filters and exports. Separate process workers use disjoint symbol keys; the parent alone commits the complete catalog. Recovered an initial pre-1970 Windows timestamp/calendar issue, and a v2 all-observations-excluded edge case before publication. Regression tests cover split boundaries, overlap disagreements, listing-era contamination, unavailable identities, calendar sessions and interrupted imports.
- Operational notes: first standard dashboard restart waited for an active NAS operation to complete; no guard bypass. Later standard restart loaded the listing-boundary UI and reported services healthy. Existing paper-approval file remains byte-identical. No new broker instruction, strategy promotion, data-reader switch or recurring automation. The final restart also waited for a transient NAS operation lock; the normal guarded retry succeeded.

- Final evidence: policy-v2 batch 69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3 committed after exact SHA256 readback. Independent SQL/API checks confirm 23,295,861 daily rows (4,537 symbols), 55,169,737 comparison rows (4,936 symbols), 228,262 action records, 20,310 per-symbol documents and 5,340 catalog/symbol publications. There are 17,825,179 supported raw-price rows, 14,828,552 supported raw-volume rows, 4,268 series without internal gaps, 3,123 complete reconstructed-raw observed spans and 803 unavailable symbols. Listing/identity controls quarantine 772,141 original observations across 686 symbols; compared with v1, 120,657 selected rows are removed. Only seven supplemental-source rows across four symbols remain necessary after full-range collection and identity gating. ASRT/IAS/KALV/NUVL/VRNT have no valid current-identity observations after their metadata boundary. Archives without listing evidence use the preferred source's first valid observation as a conservative floor; borrowed action ledgers cannot certify raw prices before their own price coverage.
- Final validation: full suite 643 passed, 51 optional skips, zero failures; nine final API checks and Ruff passed. Browser verified adjusted/raw/source charts, NET exclusions, 686/803 review filters, empty ASRT and raw GE charts, HYG's rejected legacy source, original-unit action disclosure, and preserved Research Data/Market Bars; no console errors. User-facing Governed Histories tab retained. Evidence: var/research/governance-publication-verification.json, governance-ui-verification.json, governance-v2-full-tests.xml; data/review roots D:/systematic_trading_data/research/governed-prices-20260926-v2 and governed-prices-audit-20260926-v2; guide docs/price-governance-2026-09-26.md. Next: resolve permanent security/issuer episodes, delistings, raw-basis failures and remaining gaps, then replay baseline/candidate LEAN tests on pinned governed inputs with explicit corporate-action units and historical availability. No claim of universal listing-to-delisting certification or strategy promotion.
- Archived the final report, guide, independent SQL/API/browser verification, regression receipts and quarantine evidence as 15 exact-hash documents under `governance/review`, version `12c14f467ab9f1ec89e3bbb702c648535639f4ab34f048170c378aa60cca5510`. Repeated publication wrote nothing. Receipt: `var/research/governance-review-clickhouse-receipt.json`.

## 2026-09-26 - Ten-year constituent testing and visible research histories

- User requested a minimum ten-year test before discussing SOTA elevation and a fix for missing histories in Market Data. The prior ITOT signal only passed the 95%-value/70%-names/211-session gate from January 2023; earlier backtest months were baseline fallbacks. Added public dated IVV holdings (170 snapshots, 85,050 rows), 885 current-provider requests (634 populated histories, three empty successes, 248 unavailable), 2,298,993 stock observations, and 1,173 relevant public archive CSVs (666 Yahoo2020/507 Stooq2017) containing 7,595,897 observations. Original source ZIPs retained on disk; every extracted research history and exact CSV source persisted with verified ClickHouse payload hashes. Unknown historical availability remains NULL; 45/60-day publication lags remain assumptions. Stooq adjustment conventions and contemporaneous-ticker identity limits are explicit.
- Long native LEAN window 2016-01-04–2026-09-24, 122/129 qualified decisions, first February 2016. Seven neutral months retained, including the issuer's six missing 2017 snapshots and subsequent incomplete windows. The same provider supplies each stock's entire backward window; missing holdings stay in denominators and snapshots older than 140 days are rejected. Yahoo-only90% is a labeled sensitivity, not a replacement for the unchanged95% primary. Tree models first become usable February2018; their effective history is shorter than the full10.7-year run.
- Added research-only dated base-tree schedules to frozen LEAN bundles, reference and native adapters. Expanding annual fits use completed labels before fit date and prior-close model availability. Production SOTA definition remains unchanged; its pre2023 trained tree cannot be replayed causally in2016. Twenty-two long trials cover early/late allocation, selection, residual trees, HHI, price controls, provider/lag sensitivity, and matched fee/slippage/delay stresses. Four additional2023+ trials compare against the actual frozen production model with fresh starting cash. All26 successful runs passed the original parity tolerances and were registered as research-only in PostgreSQL.
- Result: no case for promotion. Long baseline9.64% CAGR/0.932 Sharpe; early signed9.68%/0.936/IR+0.158, weaker than price-only9.69%/0.937/+0.190. Primary gain3.4bps annual CAGR,63-session block interval for annual arithmetic active return[-0.081,+0.136]pp, family-adjusted p0.813. Joint-tree stock contribution beyond price-only is0.002pp CAGR/direct IR+0.039 (adjusted p0.900). Selection loses slightly; concentration IR-0.232. Signed activity helps2020 but worsens2022(-8.88% vs-8.59%). Actual frozen-model2023+ signed IR+0.429 versus SOTA falls to+0.105 versus price control; its interval includes zero. Updated HHI derivative scatter plots remain weak. No parameter tuning or promotion after results.
- Market Data previously queried canonical daily bars/recorder captures only, leaving research in analytics.observations invisible. Added workspace/prefix-scoped read-only catalog/entity/row endpoints and a Research Data tab: dataset/type/symbol/date filters, bound pagination, JSON page export, single-source price charts, scalar results/features and exact source/quality inspection. Browser checks verified2016 AAPL bars/holdings, source hashes, legacy datasets and displayed CAGR/Sharpe/IR. Operator dashboard restarted to load the fix; paper approval values/revisions/history unchanged after normalizing equivalent timezone formatting. IB Gateway startup health remained unavailable; no broker repair, order or policy action.
- Incidents/recovery: initial prepared v1 used warmup2012-01-03 but the ETF snapshot begins2012-01-05; validation stopped before a native run. V2 corrected only the boundary; feature/model/label hashes match. One native selection-price attempt stalled at the first data step; stopped only that owned container, retained failed receipt/logs under failed_attempts, retried the identical frozen bundle successfully. ClickHouse imports resumed idempotently after transient localhost timeouts. Fixed CRLF normalization for exact Stooq source preservation and added a regression test. Inherited generic native provenance text mentions ITOT; explicit hash-bound provenance_clarification.json records that actual inputs are IVV. Immutable economic artifacts unchanged; future runner metadata uses the protocol description.
- Evidence: main root D:/systematic_trading_data/lean/research/constituent-tenyear-20260926-v2; companion D:/systematic_trading_data/lean/research/constituent-frozen-reference-20260926-v1; guide docs/constituent-tenyear-research-2026-09-26.md. Main ClickHouse feature/model/label records16,352, result/contrast records366; companion result records4. Full suite616 passed/51 optional integration skips, two existing dependency deprecations; Ruff clean, plots visually inspected, browser verified. Next: fixed prospective evidence and better ETF-specific identity/publication data. No new automation, commit, PR, live enablement or SOTA promotion.

## 2026-09-26 - Earlier constituent integration in selection, allocation and trees

- User requested embedding signals with positive sample IR earlier in selection/allocation or deeper inside the tree. Froze a bounded, explicitly post-selection follow-up using the existing archived stock features. Added research-only early allocation, pool-score adjustment and shallow SPY residual-tree correction. Production SOTA and broker/scheduling/approval policy remain unchanged. A small tree forecast-method refactor preserves default behavior, verified by exact prior SOTA/three late-reference economic hashes.
- Nineteen native LEAN runs: SOTA, twelve stage/control/strength specifications and six matched selection cost/delay stresses. SOTA, selection primary and both tree variants recompute targets inside LEAN; other targets execute through native fills/accounting. All passed unchanged parity. Target gross matches SOTA; every asset's active change is bounded at 3pp with a 45% increase ceiling. Runtime models use only prior completed dates; annual fits use 23/35 completed monthly labels at 2025/2026 cutoffs and first activate in February. Training outcomes are stored separately from runtime features. The shallow joint fits use actual breadth and signed-activity branches.
- Result: retain SOTA. Post-2023 early signed activity 14.77% CAGR / Sharpe 1.299 / IR +0.262 is effectively unchanged from late; earlier price-only 14.79% / 1.301 / +0.301 is stronger. Signed selection and half-strength reproduce SOTA weights/fills/NAV, including cost/delay stresses. SPY is held on 39/44 qualified dates; other five scores are negative twice and neutral three times. Breadth selection changes one decision and loses return (IR -0.550). No new SPY selections. Tree joint changes 19 decisions but 2025-onward 18.84% / 1.467 / IR -0.876 trails SOTA 19.03% / 1.474 and price-only tree 18.89% / 1.471; incremental tree IR against price-only is -0.851. Paired intervals do not establish improvement. No extra tuning or promotion; a deeper tree is not justified by 23/35 training months.
- Reused source histories remain in ClickHouse. Published 3,592 features, four dated model records, 43 separate training labels, 228 period metrics and 24 direct contrasts, plus report/exposure documents with exact hash readback; all 19 immutable native receipts registered in PostgreSQL. Read-only SQL confirms counts, null availability and receipt hashes; repeated analysis publication is a no-op (`var/research/constituent-integration-verification.json`). No new market-data downloads. Historical availability remains null, and the 45-day holdings lag, incomplete delistings and ITOT-as-SPY proxy limitations remain explicit. The previously inspected dates do not constitute a fresh holdout.
- Validation: full suite 599 passed/51 optional integrations skipped, two existing dependency deprecations; focused 55 passed/1 skipped. Ruff/whitespace checks clean; result and model-tree charts visually inspected. Reproducible guide: `docs/constituent-integration-research-2026-09-26.md`; protocol: `config/constituent-integration-v1.json`; frozen root: `D:/systematic_trading_data/lean/research/constituent-integration-20260926-v1/`. Next: actual ETF-specific constituent panels and more complete histories, then a declared cross-ETF selection comparison on fresh evidence. No unattended task, service restart or broker action.

## 2026-09-26 - Constituent information in the SOTA ETF strategy

- User requested stock/ETF-constituent signals in the current strategy and evaluation of return, Sharpe and IR, plus a broader signal-testing plan. Added research-only `sota_constituents` identity and bounded SPY tilt to the LEAN adapter; frozen public ITOT cohorts are explicitly a U.S. market proxy, not actual SPY/foreign-ETF holdings. Monthly previous-close signals, neutral coverage fallback, no new selections, preserved gross/cash, maximum 3pp active change and 45% target cap; no promotion, service restart or broker action.
- Froze five definitions before results: sector dollar-volume concentration acceleration, trend breadth, breadth change, equal-vs-holding-value momentum participation, signed activity; equal-weight composite primary and ETF-price-only control. Fifteen native runs include half-size, 60-day holdings availability, 90%-value coverage, matched 45bp costs and next-session execution-delay checks. SOTA/primary compute targets inside LEAN; others replay frozen targets through native fills. Every run passed original parity and was appended to the immutable PostgreSQL research registry.
- Full period 2019-10-01–2026-09-24: SOTA CAGR 8.52%, Sharpe 0.784; composite 8.49%, 0.782, IR -0.394; concentration 8.45%, 0.778, IR -0.507. Whole-cohort 95%-value/70%-name coverage first passes January 17, 2023: 44 of 84 decisions qualify, SPY selected on 39 and composite changes 33. Thus earlier identical results are neutral fallback, not crash robustness. Post-2023 composite 14.65%/1.287/IR -0.540 versus SOTA 14.72%/1.292. Best constituent, signed activity, 14.77%/1.299/IR +0.262, lags price-only 14.79%/1.301/IR +0.299 and has family-adjusted p=0.831. No evidence for inclusion; retain SOTA. Negative descriptive breadth IC is a new mean-reversion hypothesis, not permission to reverse the signal after seeing results.
- Reused hash-verified archived sources with no additional downloads; ClickHouse source counts checked (5,923,052 bars, 299,575 holding rows, all unavailable/empty requests retained). Published 3,592 new causal feature records with genuine historical availability null, and 180 period/scenario metrics plus report documents with exact SHA256 readback. 45-/60-day publication lags remain assumptions; missing delistings/security IDs and unknown adjusted-data vintages prevent certified strategy evidence. Native inputs/runs immutable; plotting/report corrections only affected derived analysis versions.
- Validation: 589 full-suite tests passed, 51 optional integrations skipped, two existing dependency deprecations. Focused 45 passed/1 skipped; Ruff and whitespace checks clean; result and IC charts visually inspected. Analysis smoke corrected a return-vector call and Windows UTF-8 report read, then completed publication/registration. Artifact root `D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1/`; guide `docs/constituent-signals-research-2026-09-26.md`; protocol `config/constituent-research-v1.json`. Next data/signal plan prioritizes actual ETF membership/identity, downside participation, internal dispersion, filing-time fundamental breadth and issuance-confirmed crowding; no unattended automation was requested or created.

## 2026-09-26 - Underlying-stock sector aggregates and ClickHouse research archive

- User correctly limited the ETF-only inference and requested underlying-stock sector aggregation, then explicitly chose public data and requested ClickHouse persistence. Downloaded 95 issuer historical monthly ITOT equity snapshots (October 2018–August 2026), retaining dated sectors and original symbols. Requested 5,156 distinct historical symbols plus one supplemental class-share endpoint; 3,267 populated histories, 32 accepted-but-empty responses and 1,858 unavailable/rejected. Verified material pure renames against issuer announcements before correlation results. Preserve unavailable requests, raw data, timestamps and hashes. Dated membership uses a stated 45-day publication-lag assumption, not certified historical availability.
- Aggregate observed stocks' share volume and dollar turnover by sector. Sector/market daily returns use stock adjusted-close returns and lagged snapshot holding-value weights; equal-stock weighting is a sensitivity. Across-sector HHI, within-sector stock HHI and causal raw/EMA derivatives have separate definitions; derivative stencils use one cohort to suppress mechanical membership changes. Obvious identity mismatches are excluded with their weights/names retained in coverage denominators. This is a broad US equity fund sample, not an exchange census or a net-flow dataset.
- Missing histories are material: only 259 of 1,943 sessions meet every sector's 95%-value/70%-name coverage thresholds. Requiring full 120-session labels leaves 139 common signal dates (2025-09-15–2026-04-02). Raw dollar-HHI correlations with underlying aggregate returns: +0.038/+0.250/-0.117; first differences -0.002/-0.014/-0.009; second differences +0.019/+0.014/+0.027. Longer observed-subset sample n=1,823 also has near-zero raw derivatives but cannot estimate the whole market because of missing/delisted securities. Smoothed qualified 60-day HHI r=+0.542 is not evidence of robustness in this short overlapping sample. No strategy or LEAN promotion; preserve SOTA and trading policy.
- Archived 5,923,052 daily stock records, 299,575 dated holdings, 5,157 endpoint statuses and 8,696 exact source documents to the existing versioned ClickHouse analytics contract. Also archived 21,373 sector aggregates and 64,119 forward labels in separate families, plus computed reports; previous ETF study's 24,936 bars and original sources are saved. All row/document identities and SHA-256 payloads are read back before publication. Unknown historical availability stays NULL; retrieval and assumed availability are distinct. Ingestion never writes production daily bars, broker controls or operational classifications. ETF and computed-analysis repeat imports are no-ops; final stock/holding/aggregate family counts and a historical AAPL SQL query match expected source evidence.
- Validation: 18 focused tests passed, Ruff clean; main raw/smoothed grids and coverage/turnover timelines visually inspected. Coverage, identities, raw inputs, code and 43 plots are frozen under `D:/systematic_trading_data/research/underlying-sector-hhi-20260926-v1/`. Guide/replay/query contract: `docs/underlying-sector-hhi-2026-09-26.md`; import/readback receipts: `var/research/underlying-sector-clickhouse-receipt.json`, `underlying-sector-clickhouse-verification.json`, `underlying-sector-analysis-clickhouse-receipt.json` and `sector-etf-clickhouse-receipt.json`. Original files retained for recovery; ClickHouse D: volume remains outside PostgreSQL-only NAS snapshots. Next: complete delisted prices, stable IDs and actual historical publication/classification vintages before full-market or strategy conclusions.

## 2026-09-26 - Sector-volume HHI and forward-return plots

- Followed up the user's request for scatter plots of HHI, its first derivative and second derivative against subsequent 20/60/120-session returns. Froze raw Yahoo responses, retrieval metadata, corporate actions and hashes for SPY plus all eleven sector SPDRs. All twelve series have 2,078 observed aligned sessions from June 2018 through September 24, 2026; no missing sectors were filled. Common scatter dates are January 2, 2019–April 2, 2026 (1,823), so every horizon uses the same dates with fully observed outcomes.
- Implemented raw share-volume HHI, backward daily differences, causal EMA(10)/lag-10 sensitivity and provider-close dollar-volume sensitivity. Returns use adjusted USD prices; equal-weight sector basket starts at equal capital and holds for each horizon. Produced 19 scatter grids covering SPY, the basket and each sector, plus timeline, heatmap, selector gallery, CSV, full Pearson/Spearman/period/nonoverlapping diagnostics and paired 240-session block intervals. Source code and all artifacts are hashed for replay.
- SPY raw HHI correlations are +0.075/+0.115/+0.093, first differences -0.012/-0.002/-0.001 and second differences -0.011/-0.004/-0.005. Smoothed acceleration remains weak (-0.012/+0.026/+0.024). Raw level correlations are unstable pre/post-2023 and much weaker with dollar volume. Do not infer an actionable signal from these overlapping outcomes or equate ETF activity with net flow. ETF unit/split conventions and present-vintage provider history remain limitations; no underlying constituent turnover or holdings data were acquired.
- Eight focused tests and Ruff passed; main raw/smoothed grids, timeline and heatmap visually inspected. Artifact bundle: `D:/systematic_trading_data/research/sector-hhi-20260926-v1/`; guide: `docs/sector-hhi-correlations-2026-09-26.md`. This is a descriptive follow-up to the completed LEAN experiment; no new backtest, strategy promotion, service change or broker action. Retain SOTA and seek timestamped net-issuance data before testing the actual flow hypothesis.

## 2026-09-26 - Flow/concentration acceleration strategy research

- Tested the user's capital-inflow/deceleration idea against current SOTA using actual pinned offline LEAN. Separated net flows from secondary-market activity, and acceleration from Hurst persistence. Added a research-only causal activity-share overlay with directional confirmation, optional Hurst filter, HHI/volume/velocity ablations, bounded exposure-preserving tilts and explicit monthly hysteresis gate. Production SOTA definition, approvals, broker orders and live/paper policy remain unchanged.
- Froze one primary, eleven challenger variants and robustness rules before results. Read-only ClickHouse snapshot has 3,701 valid sessions per SOTA ETF; excluded 24 actual market-holiday rows, retained 434 prior-only legacy FX carries with lineage. Two preflight attempts stopped on invalid URTH observations before any backtest. Final v3 marks affected URTH benchmark windows unavailable (36 invalid early sessions), never fills them or changes trading data. Historical vintage/FX/survivorship and adjusted turnover limitations remain explicit.
- Seventeen predeclared native runs cover 3,393 sessions, April 2013–September 24, 2026. Primary CAGR 9.06%, Sharpe 0.919, max DD -13.84%; matched SOTA 9.11%, 0.924, -14.16%. Primary loses 0.28 annual percentage points post-2023 and fails all retention checks. Hurst does not help; literal entry/exit gate returns 2.90% with 64.8% average cash. Best fixed lag-20 neighbor returns 9.28%, Sharpe 0.935, max DD -13.39%; family-adjusted p=0.354 overall / 0.132 post-2023 across all eleven challengers. Two separately predeclared post-result implementation checks retain its small advantage: high-cost CAGR 6.61% vs 6.53%; delayed CAGR 9.30% vs 9.21%. These are observation evidence, not new holdout data or a promoted winner.
- All nineteen native runs pass exact decision/fill/position parity and original money/weight tolerances; immutable research registry evidence retained. Artifacts include frozen source/data/protocol, all fills/NAV, annual and stress metrics, 63-session paired bootstrap, uncertainty/multiple-testing audit, 1,944 asset-month diagnostics and inspected PNG/SVG figures. Full pytest passed with existing optional-integration skips and two existing deprecation warnings; final focused checks 38 passed/1 skipped and Ruff clean. Optional research statistics/plot dependencies are separate from production runtime; plotting installed to an external D: research directory.
- Decision: retain SOTA; reject the current primary proxy overlay, retain the fixed lag-20 variant for observation only. The underlying net-flow hypothesis remains untested directly. Next required data: historical split-consistent ETF shares outstanding, NAV/AUM, creations/redemptions and publication/revision timestamps; historical holdings and sector membership for separate concentration tests. Literature/source links, contracts and replay commands: `docs/flow-concentration-research-2026-09-26.md`. Evidence: `D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/`, including explicitly post-hoc `followups/lag_20/`. Do not reuse post-2023 as an untouched holdout or continue tuning on this history.

## 2026-09-26 - Analytical time-series migration and Strategy latency

- User expanded the Strategy performance fix to all analytical time-series after clarification. Historical backtest NAV was stored in JSON, while each request recalculated monitoring marks and report attribution. Catalog measured 11.634s; report 36.295s. Request-local dated market reads eliminate repeated FX history queries; report FX alignment is computed once; deterministic session boundaries are cached without caching whether a session has completed.
- Added `analytics.observations`, `documents`, `publications` and a committed-current view in ClickHouse. Rows retain exact source JSON, typed family/entity/time, nullable original availability and separate ingestion time. Verify every payload hash/key before publishing; failed builds retain the previous version. Capture files import incrementally in verified batches, avoiding full-history copies each minute. Raw source-event duplicates with different receipt metadata remain distinct; identical hot/archive copies dedupe. Original files, PostgreSQL transactional state and raw-first recording remain intact.
- Migrated Strategy NAV/benchmarks, chart/period/holding contributions and diagnostics, all dated research artifact rows, registered hash-verified LEAN outputs, account snapshots, daily P&L, execution order/fill projections, available fundamentals, FX response legs and raw intraday bars. Empty execution-benchmark/fundamental sources are supported without invented records. Latest count evidence includes 67,593 strategy NAV points, 233,788 research rows, 24,726 LEAN rows, 8,397 raw bars, 10,486 period metrics, 44 P&L snapshots and 48 individual execution fills. Counts grow with ongoing captures. Live broker callbacks remain a live view; unrecorded history is not fabricated.
- Strategy HTTP reads now use prepared ClickHouse documents; account performance is likewise published and refuses an old baseline after reset. Account/P&L analytical history reads ClickHouse; operational ledger/fundamental input/reset contracts remain PostgreSQL. Background polling defaults to 60 seconds after each pass, detects historical corrections and source file/code revisions, exposes worker errors/freshness and never makes broker calls. Readback/resume, file revisions/deletion, date bounds, sparse FX, account resets, source-copy preservation and P&L equal-time ordering tested.
- Validation: full suite 548 passed/51 optional integrations skipped; final affected suite 65 passed with real ClickHouse tests in a disposable workspace; Ruff clean. Running old versus published full report dictionaries matched exactly (3,704 chart points); all 44 P&L payloads and order match PostgreSQL. Runtime catalog 0.0125–0.0915s, report 0.1105–0.1376s, account performance 0.0918–0.2035s. First embedded refresh completed successfully. Policy revision 1/enabled state unchanged; reconciliation matched. No broker orders, approvals or resets performed.
- Evidence: `var/migration/analytical-timeseries-deploy.json`, `analytical-row-counts.json`, `strategy-report-parity.json`, `pnl-projection-parity.json`, `analytics-latency-after.json`, `analytics-worker-status.json`, `analytics-full-tests.txt`. Guide: `docs/analytics-migration.md`. Rollback: disable analytics serving and restart dashboard, retaining original sources. ClickHouse still needs its separate volume handoff/backup or replay from retained sources; superseded analytical versions have no automatic deletion policy. Monitor storage growth and periodic refresh operationally.

## 2026-09-26 - URTH benchmark historical coverage repair

- Confirmed 92 missing URTH sessions between April 29 and September 11. Recorder only fetched a recent 14-day window; stored recent bars did not imply contiguous history. Repaired April 30–September 10 using observed Yahoo adjusted bars, retaining source/ingestion metadata. Repeat through September 24 inserted zero rows. Frozen strategy artifacts and trading controls are unchanged.
- Default daily symbol discovery now includes registered benchmarks even when absent from ClickHouse. Unless explicitly bounded by --start-date, benchmark backfill scans completed sessions from the research horizon (URTH January 12, 2012; AOR January 3, 2012), then expands the provider request to the first missing date. Incomplete provider coverage is counted, warned, and returned as a nonzero child exit with a concise stderr error for recorder health. No synthetic bars are written. Fresh child processes load this change on the existing six-hour schedule; no trading-service restart required.
- Validation: 38 golden-store, script, report and API tests passed; Ruff and diff whitespace checks passed. Regression coverage includes the exact 92-session gap, replay idempotency, absent benchmark bootstrap, explicit symbol/date scopes, and provider omissions/weekends. Running monitored Strategy report reloads repaired observations. Evidence: var/urth-benchmark-repair.json, var/urth-benchmark-repeat.json, var/urth-report-verification.json.
- Remaining provider limitation: September 25 adjusted URTH is absent from Yahoo; a separate IB read-only history request timed out with ushmds disconnected. Evidence: var/urth-benchmark-latest.json. Recurring repair retries; existing report behavior carries its last benchmark value with an explicit forward-fill warning for that date. Historical provider availability and existing FX lineage are not recertified by this repair. No broker orders, approval changes, or account resets.

## 2026-09-26 - PnL N/A after-hours and attribution follow-up

- Reproduced two defects: the UI discarded valid cached IB figures after the 15-second freshness threshold, and a shared `Promise.all` prevented every accounting panel from rendering until the slowest dashboard calculation finished. Attribution took 87.14 seconds; repeated complete FX-history reads for each execution slice were a major contributor.
- Retain finite last-received broker fields with timestamps, age, stale/disconnected status, and the explicit caveat that callback time is not quote time or an official close. Missing fields remain unavailable individually; fresh position rows no longer depend on account freshness. Changed position quantity invalidates its old values. A failed HTTP refresh retains prior figures with an error/stale label. The lightweight cached PnL endpoint runs independently of the synchronous worker pool.
- Each dashboard panel now renders independently with bounded requests, per-panel errors, retry and overlap suppression. Request-scoped read reuse shares the ledger, baseline, FX and prices across actual/reference calculations without a cross-request cache or economic changes. Live deployed attribution: 3.23 seconds; actual CNH 977.08, reference CNH 1,960.12, difference CNH -983.04, identical to before.
- Validation: 75 tests passed across PnL, API, operator UI, execution history, reset and performance; full Ruff clean. Tests cover after-hours values, partial/sentinel fields, quantity changes, HTTP failure/recovery, slow or failed independent panels, dated read keys and refreshed inputs on the next calculation. Evidence: `var/pnl-na-regression.xml`, `var/pnl-na-before.json`, `var/pnl-na-after.json`.
- Deployed dashboard/dispatcher PIDs 33380/32148; Gateway/recorder retained. Real browser displayed HKD 1,208.38 last-received account PnL and six USD position daily values, with stale timestamps; IB does not supply those position realized fields, so they remain n/a. Attribution populated, no console errors or horizontal overflow. Reconciliation matched and paper automatic policy revision 1 remained unchanged. No broker order or account/PnL reset was performed.

## 2026-09-26 - Live broker PnL and platform audit

- Replaced the misleading daily-mark live display with a dedicated read-only IB account/position PnL stream, separate client, verified DU account and broker currencies, stale/unavailable handling, reconnect and bounded browser polling. Real browser/API verification observed changing values and six positions; account totals HKD and these position rows USD. Callback freshness is not a claim of exchange quote entitlement. Dashboard/dispatcher restarted; paper reconciliation remains matched. The final policy read found paper automatic approval already enabled; preserved its state/caps without enabling or reconfiguring it. Live remains disabled.
- Fixed same-day closing FX used for opening funding, future bars exposed to signal plugins, same-day filings used at the open, fiscal period end treated as publication, training labels touching the holdout boundary, missing execution prices silently filled from stale marks, calendar intersections hiding missing days, and dynamic holdings valued indefinitely at carried marks. Kept the existing frozen SOTA model and promotion state. Added regression tests and correctness lint configuration.
- Preserved 45 suspect daily rows on D: before removing unfinished session rows and repairing invalid provider OHLC. Current audit: 141,582 rows, zero invalid OHLC, 821 zero-volume observations. A fresh provider check confirms MCHI 2012-01-04 still has zero volume; retained the observation. Strict LEAN export rejects it; long-history warmup begins 2012-01-05, trading 2013-02-01 onward. Legacy FX/vintages/universe and selected holdout history remain uncertified.
- Full regression before the final import-boundary change: 578 passed, one optional SMB test skipped in 313.07s; Ruff correctness lint clean. Evidence: `var/platform-audit-tests.xml`, runtime JSON snapshots, D: preserved source rows and `docs/platform-audit-2026-09-26.md`. Earlier IB recorder 10197 / historical FX 162 restrictions cleared by the final 19:22 UTC probe: recorder wrote 155 delayed bars across five symbols, and IB returned September 23/24 USD/CNH closes. No other session was disconnected. Realtime entitlement is still absent; delayed provenance is preserved. PostgreSQL's earlier physical D: relocation remains an administrator action.
- LEAN v1 is implemented and passed twelve native runs: target replay plus exact repeat, shared signals, synthetic stress, 2025 SOTA/baseline, fee/slippage/delay and 42/84-bar neighborhoods, and both 3,330-session histories. Full SOTA: 159 decisions, 1,212 fills, all daily cash/NAV within predeclared 0.01 CNH; no unexplained discrepancies, repeat economic hash identical. Official image digest `27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59`, release label 18130. Full SOTA wall times: Python 30.33s, LEAN 46.14s; LEAN peak RSS 868 MiB. All twelve runs registered research-only with idempotent insertion. SQL migrations 003/004 enforce non-promotion and append-only evidence. NAS database backup completed after registration. Report: `docs/lean-validation-2026-09-26.md`; immutable bundles/results: `D:/systematic_trading_data/lean/validation/20260926-v1/`.
- Final verification after isolating shared analytics from eager broker/database imports: **579 passed, one optional SMB test skipped** in 287.35s; Ruff clean. Dashboard/dispatcher reloaded to PIDs 31352/7052; recorder 39520 retained. Fresh PnL, six positions and matched reconciliation verified after deployment; browser no errors/overflow. Paper automatic policy revision 1 / CNH 1,000,000 cap preserved. Broad-watchlist HYXU remains unavailable (Yahoo 404 / IB 200), outside current SOTA. Frozen LEAN datasets/results are on D: and require separate copying from database NAS snapshots for PC handoff.

## 2026-09-25 - Fill prices, TWAP estimates, paper automatic approval and opening P&L reset

- Final UI hardening keeps the reviewed policy revision fixed while its dialog is open, binds policy to the configured environment, and labels the P&L cutoff explicitly in New York time. Follow-up policy/UI checks: 21 passed, 1 skipped (Postgres already covered by the full/focused runs); final UI checks: 9 passed. Final dashboard/dispatcher PIDs 37548/35860.

- Added retained average fill prices beside quantities in the blotter, plus full-window duration-weighted 1-minute TRADES TWAP estimates, coverage/window provenance, buy/sell signed slippage bps and quote-currency price cost. Positive is adverse; fees/commissions are excluded. Estimates require complete observed data and completed windows. The read-only client defaults to ID 191 and caches raw minute bars locally; unavailable requests retry after five minutes while viewed. Actual IB requests reported the US historical-data farm `ushmds` disconnected; local delayed aggregates covered only 184 of the expected 360 five-second intervals for SPY/GLD in today's window. No substitute benchmark is published. Next: restore IB historical-data connectivity/permissions and verify all six full-window benchmarks.
- Added an audited optional paper policy, left OFF. The UI explicitly enables approval plus submission of new current-strategy TWAP proposals under an operator-set gross CNH cap. Existing queues are excluded. Policy is bound to machine/workspace/environment/broker/strategy; single verified DU account, fresh matched reconciliation, exact latest daily data/FX, sizing/target limits, liabilities, local/broker working/uncertain orders and regular-session deadlines gate routing. A durable attempt claim precedes atomic pending-to-approved approval and normal router handoff; interrupted/partial/failed attempts require manual review. SQLite/PostgreSQL decisions support expected status, and manual API decisions/routing share the order lock. Existing live prohibition is unchanged. Policy revisions/attempts survive restart; switch events enter the outbox. First automatic paper cycle still needs operator enablement and observation.
- User explicitly requested restarting live P&L before today after resetting the paper account. Verified matched flat snapshot `ib_paper_account_snapshot_20260925_193904.json` held HKD 1,018,123.95 at 11:39:04 UTC before all today's fills. Applied baseline `d229466e93af`, cutoff `2026-09-25T03:59:59.999999Z` (immediately before Sep 25 New York), zero carried P&L/lots/trade count. Saved an explicitly derived prior-close opening cash reference retaining the actual capture time and source path. All 48 current executions and six holdings match and remain active; 244 order records and earlier baselines/snapshots remain immutable audit history. Audit: `var/live/pnl_opening_reset_d229466e93af.json`. Active P&L snapshot/comparison history excludes prior reset episodes without deleting records.
- Validation: full suite 522 passed, 1 skipped in 303.27s; 38 focused tests after cache/metadata hardening passed. Includes SQLite/Postgres approval status gates, automatic-mode eligibility and no retries, TWAP coverage/sign/persistence failures, opening reset holdings/provenance, preserved history and real JavaScript columns. Dashboard/dispatcher restarted; real browser shows six full fills and prices, Manual/off policy with review dialog, Sep 24 account opening reference, and Matched reconciliation. No broker order or automatic-mode enablement was performed during implementation.

## 2026-09-25 - Blotter date filters and completed TWAP visibility

- Confirmed the initial six TWAP orders fully filled: DBC 586, EWH 1161, EWJ 209, EWY 29, GLD 40, SPY 52 shares, across 48 executions. Reconciliation matched six holdings. Orders were retained in both the local ledger and Gateway completed snapshots; the previous default Working filter hid them after completion.
- Default is now Today plus All statuses. Added Last 7 days, inclusive Date range and All dates alongside Filled, Working, Needs attention, Completed / closed and Missed filters. Missed is separate from completed orders. Dates use the intended New York session or legacy actual submission date, never bulk update time. Submission/update timestamps display the browser's named local timezone. Newest dates/submissions first; counts and audit details follow filters. Current unlinked working orders stay visible with unknown dates, and a notice identifies working local orders outside the date range.
- Real browser verification found completed callbacks with quantity zero, previously displayed as filled/0. Display now falls back to the retained order quantity and prioritizes durable full-fill evidence over stale working observations. Order actions remain disabled for filled records. No history, approval, broker order or baseline was changed.
- Verification: nine UI/Node tests passed, including date boundaries/DST, legacy missed updates, completed-order retention, sort order, status combinations, invalid ranges, external unknown dates and completed quantity/action handling. Browser Today + All statuses displayed six filled rows with correct totals and timestamps; All dates + Missed exposed 220 historical records; restored Today + All statuses. Dashboard/dispatcher restarted to 39140/32936, recorder/Gateway/NAS retained, reconciliation remained matched. Guide updated at `docs/trading-operations.md`.

## 2026-09-25 - Active TWAP reconciliation synchronization repair

- Operator's retry successfully sent all six initial TWAP orders (broker IDs 20–25). The reported history-review warning was transient: reports around 13:46–13:50 UTC contained only `broker executions await durable synchronization`, while the underlying records had no durable execution issues. Periodic fill sync and subsequent reconciliation queried different execution batches during active slicing; the page retained its own older warning after management reconciliation had caught up.
- Added explicit `sync_new_fills` reconciliation mode for API/management operations. Persist each matching order's exact freshly queried batch through the existing atomic fill validation/audit/outbox path, then obtain the account snapshot and compare holdings. Diagnostic callers retain explicit sync semantics. No execution IDs, quantities, corrections, or account identities are guessed; existing durable conflicts stay blocked and cannot be removed through reset.
- Added a separate report `execution_sync_pending` field/status for benign pending persistence. This still blocks routing and resets. UI labels it as synchronization, explains that existing broker orders continue, polls latest reconciliation every 15 seconds, and ignores older asynchronous results. The real history-review warning remains for durable conflicts.
- Tests: affected execution/reconciliation/recovery/service/API/UI suites 95 passed; 10 new SQLite/PostgreSQL tests verify exact-batch persistence, replay idempotency, correction/gap handling and route/reset blocking; UI suite 7 passed including actual JavaScript rendering and stale-response rejection. Restarted dashboard/dispatcher to 6512/31132; Gateway, recorder and NAS worker preserved. At 13:57:06 UTC a fresh runtime check matched 30 executions and six positions with zero execution issues, pending sync or position differences. DBC 350/586, EWH 700/1161, EWJ 140/209, EWY 20/29, GLD 30/40, SPY 40/52 filled at that observation; orders still in progress. No agent broker action or baseline reset. Next: verify final broker fills and reconciliation after the execution window.

## 2026-09-25 - Proposal readiness and post-handoff approval repair

- Traced the empty initial queue to missing HKD/CNH refresh, stale USD/CNH, repeated legacy zero-volume repairs delaying EOD, and undated historical approvals. Operational FX now uses observed IB USD/CNH midpoint daily closes and matched-date USD/CNH / USD/HKD crosses, retaining source observations under ignored `var/market_data/fx_observations/`. No onshore CNY substitution or stale carry-forward. Reject unclosed FX sessions. Refreshed September 24 USD/CNH 6.71595 and HKD/CNH 0.8563532036978004; September 24 EOD completed.
- Old PyPI SDK negotiated protocol 157 and failed Gateway FX requests with 10285. Installed official IB API 10.45.1 from its pinned vendor archive via `scripts/install_ib_api.py`; SHA-256 checked. Added old/new error callback and cancellation compatibility, cash/IDEALPRO midpoint historical contracts and dedicated FX client 181. Updated installation docs and protobuf dependency. Restarted dashboard/dispatcher and recorder; Gateway/NAS ownership preserved.
- Automatic alignment refreshes all required currencies before readiness checks. Normal EOD restricts zero-volume repair to the current target; explicit historical refresh keeps historical repair enabled. Treat legacy undated approvals as history only when all attempts are covered by the reconciled baseline; uncertain/missing/new attempts still block. No historical approvals or broker states rewritten. Queue and readiness refresh every 15 seconds.
- Generated initial proposal `initial-9f6f68b03399-20260925`: DBC/EWH/EWJ/EWY/GLD/SPY TWAP buys for 09:35–10:05 New York / 21:35–22:05 Shanghai, based on September 24 completed data. Operator clicked approval while verification was in progress. Approval persisted but the first database reservation failed: Gateway returned ID 1 already present in NAS-restored history (local maximum 19). Trace retained in ignored `var/log/operator_dashboard.approval-id-collision-20260925.err.log`.
- Routing now selects max(Gateway next ID, highest retained local ID + 1), preserves the database uniqueness/intent guards, and stops with a structured operator message on connection/reservation/persistence failure. Partial batches retain their recorded legs; uncertain outcomes still block retry. No automatic retry or approval rollback. Verified against both SQLite and disposable PostgreSQL with a reset/larger Gateway sequence and first/second-leg reservation failures.
- Verification: full suite 465 passed, 1 skipped before the ID fix; final focused FX/UI/API/routing/management/regression suite 128 passed. Whitespace check passed. Final dashboard/dispatcher PIDs 6216/33364. At 13:42 UTC fresh Gateway snapshot had zero orders, and this approved proposal had zero broker records; EOD through September 24, heartbeat current, no service error. Agent did not submit/amend/cancel broker orders. Next: operator review and **Resubmit Failed/Missing** before 14:05 UTC; validate broker acknowledgements/fills and reconciliation after the operator sends. Live remains disabled; approval and 2 percentage point drift policy unchanged.

## 2026-09-25 - Docker socket recovery and platform startup

- Reproduced Docker Desktop 4.79.0 failure replacing stale Windows AF_UNIX sockets. Preserved `%LOCALAPPDATA%/Docker/run` as timestamped `run.stale-*` directories and the socket-only `%LOCALAPPDATA%/docker-secrets-engine` as a timestamped sibling. Each rename occurred with Docker stopped; no container volumes or settings were deleted. A failed intermediate startup recreated an inference socket, so its runtime folder also needed preservation.
- Docker engine 29.5.3 now responds. Standard platform startup completed with PostgreSQL, ClickHouse, NATS, dashboard, dispatcher, recorder and NAS backup worker. `/operator` and `/platform` return 200.
- ClickHouse SQLite import: 140,686 daily bars and 3,790 FX rates. Default 5,000-row batch exceeded the ClickHouse partition-per-insert limit; the documented 1,000-row batch succeeded. Final daily count 140,816 across 39 symbols, latest 2026-09-24, including fresh provider backfill. This is not a full copy of source-machine ClickHouse or raw intraday history.
- Paper TWS 7497 remains unavailable; trading-management loop is degraded. Recorder daily backfill succeeded and service is idle before market open, but E:/Z: recorder storage paths are absent on this PC and need local configuration before intraday capture. Paper/live and approval checks remain intact.
- Explicit post-start NAS backup remains pending on NAS I/O after producing local PostgreSQL/SQLite snapshots. SMB port is reachable, but an independent latest.json read also stalls. Preserve active ownership and operation lock; do not switch PCs before a successful clean handoff. Runtime health verified independently.

## 2026-09-25 - PostgreSQL provisioning and receiving-PC restore

- NAS authentication now works; verified both SHA-256 hashes of source snapshot `218c1db999494848abcfaf47944e5a35`.
- Operator provided local administrator credentials. Created dedicated empty `systematic_trading` database, `st_owner` NOLOGIN, and non-superuser `st_app`, `st_migrator`, `st_readonly` roles with generated passwords in ignored `.env`. Granted migrator owner-role membership, restricted database connections and set UTC timezone.
- Standard NAS prepare completed. App login and all 14 PostgreSQL source table counts verified; restored SQLite integrity passed.
- Docker cannot initialize its stale `dockerInference` socket. Rename failed; automatic approval review rejected socket removal. Existing storage contract rejected PostgreSQL plus SQLite market data, leaving dashboard unstarted. Clean stop completed; final NAS backup published and ownership released. No storage contract or broker gate weakened.
- Next: recover Docker, start standard stack, seed ClickHouse and verify service health. Paper TWS API is also unavailable.

## 2026-09-25 - Receiving-PC handoff preflight

- User requested NAS database restore and local service startup. Verified Python dependencies (including psycopg, FastAPI, NATS, IB API and timezone data) and running PostgreSQL 18.
- Restore blocked: `192.168.1.32:445` unreachable, Windows NAS neighbor unresolved, and no local PostgreSQL credentials configured. Passwordless connections require authentication. Requested NAS address/connectivity and local credential setup from the operator.
- Created ignored `.env` from the template with paper mode and PostgreSQL/ClickHouse backends. Requested Docker Desktop startup; Linux engine remained unavailable during preflight. Paper TWS API port 7497 is closed.
- Network retry restored TCP access to NAS SMB, but Windows share enumeration returns system error 5 (access denied). Docker logs identify startup failure initializing the `dockerInference` Unix socket. NAS authentication, PostgreSQL credentials and Docker recovery remain outstanding.
- No database restore or NAS ownership mutation performed; application services remain unstarted. Resume with the standard handoff/startup scripts after prerequisites are available; verify snapshot integrity, local data, periodic backup and service health before claiming completion.

## 2026-09-25 - Publish NAS handoff and verify the real backup

- Refreshed PostgreSQL and SQLite snapshots on WD My Cloud and released the source workstation's ownership. Current NAS generation: `218c1db999494848abcfaf47944e5a35`, under `\\192.168.1.32\Public\systematic-trading\snapshots`. Local state is clean; no owner or operation lock remains. Source application services remain stopped for handoff.
- Downloaded and verified SHA-256 checksums from the NAS, restored the real dump into a disposable PostgreSQL cluster, and compared row counts and normalized content hashes across all 14 tables. Restored SQLite passed integrity and logical-content checks across its 12 tables. PostgreSQL dump text itself differs across server timezone/default-schema-comment settings, so the restore comparison uses normalized row content instead of treating dump formatting as data loss. The local production databases were not restored or rewritten.
- Saved the verification report on the NAS at `verification/218c1db999494848abcfaf47944e5a35.json`. Backup sizes: SQLite 42,094,592 bytes; PostgreSQL 25,296,202 bytes. Added the new-PC checklist to `docs/database-sync.md`; infrastructure, private credentials, ClickHouse and raw-data migration remain explicit prerequisites/exclusions.
- Published migration commit `48e49d0108b774a7ed0c4e9a3a24bc8dc150f2de` to `origin/master`; verified the remote SHA equals the local tested commit. Unrelated backfill edits, WSL/research notes and runtime reconciliation files remain outside the commit. Git HTTPS fetch worked with command-local Schannel, but subsequent push connections timed out. Published the identical blobs/tree/commit through the authenticated GitHub Git Data API and advanced the branch without force; no persistent Git settings changed.
- Validation: exact staged-code regression **356 passed, 1 skipped in 253.22s** from an isolated index export. PowerShell launcher parsing and staged whitespace checks passed. The skipped optional network smoke test is separate from the successful real-backup restore drill above. The next action is new-PC provisioning followed by normal platform startup; keep the source PC stopped until handoff completes.

## 2026-09-21 - NAS database handoff between PCs

- Implemented `config/database-sync.json`, `storage/nas_sync.py` and `scripts/sync_databases.py`, integrated into standard local platform start/stop and guarded standalone dashboard startup. Default target is `\\192.168.1.32\Public\systematic-trading`; backups run every 300 seconds while active.
- Chose a persistent single-workspace owner and immutable verified snapshots rather than merging trading databases. PostgreSQL logical dumps preserve grants and audit state; SQLite online backup includes committed WAL contents. Startup restores only new/clean local databases. Final stopped-service backup releases ownership. Missing/divergent history, changed layout, corrupt uploads, offline edits and interrupted restores fail closed.
- PostgreSQL restore replaces user schemas in one transaction so deletions also propagate. A real disposable cluster verified non-superuser migrator/owner permissions, application grants, stable fingerprints, obsolete-object removal and rollback on SQL failure. Pre-restore local copies remain available; cross-database partial restoration stays blocked for reviewed recovery.
- Fixed an existing storage import cycle exposed by the standalone sync CLI by making the recovery request import type-checking-only. Approval, broker environment and reconciliation behavior is unchanged.
- Full regression run: **350 passed, 1 skipped in 251.98s**. Final focused sync/storage/launcher tests after additional safeguards: **25 passed, 1 skipped**. Separate real NAS and disposable PostgreSQL smoke run: **12 passed**; tiny synthetic NAS evidence retained at `\\192.168.1.32\Public\systematic-trading-sync-smoke-4120c99563bb47b9b88412265decb7e0`. PowerShell parser, Python compilation and `git diff --check` passed.
- Documented first-time roles/credentials setup, stopped-service switching, conflict recovery, unbounded snapshot retention and excluded ClickHouse/NATS/raw/research data in `docs/database-sync.md`. New-PC infrastructure and ClickHouse migration remain separate setup steps. Use the next clean standard platform restart to activate; no production database replacement, service restart, broker action, commit or push occurred. Existing unrelated backfill and runtime changes were preserved.

## 2026-09-20 - Dashboard performance repair

- Completed reset-aware account history, UTC snapshot capture metadata and reset provenance retained through PnL collapse. Legacy report lookup tolerates malformed evidence; history selection uses capture time without rewriting audit files. Include non-SOTA holdings in their recorded currency and refuse incomplete NAV when a holding cannot be priced.
- Completed the interactive dual-axis performance chart: fixed alignment, Tracking preset, hover/tap and keyboard inspection, drag selection, selected-period statistics, empty/single-series handling, month-end range clamping and responsive geometry. Account changes explicitly include cash flows; missing strategy sessions/marks are disclosed and long chart gaps remain visible.
- Focused verification: **15 passed** for performance, reconciliation and snapshot behavior, including Node.js checks. Synthetic browser preview verified keyboard inspection, drag selection, Escape-to-All, empty/single-series cases and a 390px viewport with no document overflow or console errors. No operational services were restarted and no broker was contacted.
- Exact staged-snapshot full suite: **339 passed in 220.72s**, including real disposable Postgres and Node.js behavior checks. Syntax and staged `git diff --check` passed. The verified dashboard snapshot is ready for the authorized commit/push. Unrelated backfill, WSL/research and runtime changes remain outside this batch.

## 2026-09-20 - Publish completed review repairs

- Prepare a single commit containing the execution-history/recovery, monthly scheduling, recorder calendar and local Docker binding repairs. Preserve unrelated performance-dashboard, account metadata, backfill and research changes in the working tree; exclude runtime reconciliation artifacts.
- Exact staged-snapshot verification: **331 passed in 224.17s**, including real disposable Postgres; syntax parsed for 179 Python files and staged `git diff --check` passed. The verified repair snapshot is ready for the authorized commit/push to `origin/master`.

## 2026-09-20 - Recorder calendar and local Docker bindings

- Recorder capture now uses the same US holiday calendar as proposal scheduling, with recurring 13:00 New York early closes verified against the [NYSE calendar](https://www.nyse.com/trade/hours-calendars). Configured windows can narrow the equity core session, and exchange dates remain New York dates even when another display/window timezone is selected. Exceptional closures and emergency halts remain outside this static calendar.
- Re-evaluate session state after synchronous daily and gap backfills, including jobs crossing the open or close. Limit capture chunks to the remaining session time without extending sub-second windows to one second. Child startup latency still prevents treating this as a hard shutdown deadline; delayed-feed draining after close remains separate work.
- Bind the NATS client/monitor and ClickHouse HTTP/native published ports to `127.0.0.1`. Resolved Docker Compose JSON confirmed all four bindings without printing resolved credentials. Existing containers were not recreated, so runtime bindings have not been changed by this edit.
- Focused recorder/calendar/operator checks: **42 passed**. Full suite with disposable Postgres enabled: **331 passed in 235.31s**. Python syntax parsed successfully for 179 files; `git diff --check` passed.
- Preserve earlier uncommitted execution-recovery and unrelated local work. No service restart, broker access, trading-data migration, commit or push. Next review priorities remain golden-source selection/availability semantics and evidence-backed handling of historical execution corrections.

## 2026-09-20 - Reviewed paper execution recovery

- Added preview-first recovery for active paper execution histories. The review token binds the current order, replacement evidence, operator/reason and PnL baseline; apply validates again inside the same transaction as audit, order and outbox writes. No recovery has been applied to the operator's database in this session.
- Store before/after execution evidence in the order's recovery audit. Preserve it against stale order updates and ignore verified superseded executions on later broker-history replay. Require reconciliation started after the most recent recovery before routing.
- Refuse live orders, account changes, missing or rewritten execution identities, incomplete cumulative evidence, overfills and changes affecting saved PnL baselines. Zero-fill busts and historical baseline rebuilds remain follow-up work.
- Added execution-state and parent-baseline checks to PnL collapse/reset persistence, with a shared Postgres transaction advisory lock for broker-record/baseline mutations. A calculation made stale by recovery fails instead of overwriting the ledger. API collapse conflicts return HTTP 409.
- Added a disposable Postgres test fixture using the locally installed binaries and a separate password-protected loopback cluster. Fixed a Windows subprocess-pipe hang in the test launcher. Focused verification: **31 passed**, exercising SQLite and real Postgres recovery, stale reviews, reservation races, concurrent fill accumulation and atomic outbox rollback. Full suite with disposable Postgres enabled: **302 passed in 228.85s**. Final CLI checks after rejecting an ambiguous SQLite-path/Postgres combination: **2 passed**. Python syntax and `git diff --check` passed; disposable test clusters stopped successfully.
- Existing services, broker accounts, databases and historical artifacts were not changed. No broker submissions, deployment, commit or push occurred in this batch.

## 2026-09-20 - Durable executions and monthly staging

- Committed and pushed the first review repair batch as `8913ff1` on `origin/master`. All 240 tests passed against a separate export of the exact staged snapshot (221.05s). Unrelated dashboard, recorder and backfill edits remain local.
- Added individual execution evidence to the existing broker-order JSON payload. SQLite immediate transactions and Postgres row locks serialize accumulation and commit the order and outbox together. Duplicate/short-window responses retain prior evidence; delayed placement acknowledgments cannot erase synchronized fills. No schema migration is required.
- Capture IB execution IDs, account, individual execution price and cumulative quantity. Match by stable local order reference, reject conflicting identities and overfills, and preserve partial cancellation status. Complete broker cumulative evidence can bootstrap legacy aggregates; incomplete legacy history and corrections require audited recovery. Persistent execution issues block routing and PnL collapse, including after an empty history response or broker reset.
- PnL and reconciliation now apply individual execution timestamps across baseline boundaries. Reconciliation accepts persisted evidence outside the broker query window, still compares broker positions, and detects unsynchronized or conflicting new executions. Execution-sync failure invalidates EOD reconciliation readiness.
- Automatic staging honors the registered static monthly scheduler at the final US session before the new month. Daily EOD reporting continues on other sessions, with data and reconciliation gates intact. Live plans and default API execution dates now share the US session calendar. Manual proposal generation remains available; unsupported automatic schedulers fail closed.
- Added regression tests for restarts, overlapping/duplicate broker responses, concurrent fill writers, atomic outbox rollback, cumulative gaps, legacy bootstrap, corrections, reused numeric order IDs, per-execution pricing, baseline boundaries, month-end/holiday scheduling and off-cycle EOD gating. Full suite: **271 passed in 197.10s**. Final targeted API/operator/history/scheduler checks: **64 passed**; JavaScript reconciliation rendering passed three states (execution issue, position break, matched). Syntax and `git diff --check` passed. New batch remains local and uncommitted.
- No services were restarted, broker orders submitted, migrations applied, or existing historical records rewritten. Isolated Postgres/IB paper integration evidence and an audited execution correction/recovery command remain follow-up work.

## 2026-09-19 - Review-driven execution and accounting repairs

- Preserved the pre-existing working-copy changes and implemented the first repair batch from the codebase review. No services were restarted, broker orders submitted, migrations applied, or historical trading/research data rewritten.
- The submission CLI now uses the configured trading-store factory; unsupported Postgres/SQLite combinations fail before database access. Shared router validation requires recent, successful paper reconciliation, including for CLI calls.
- SQLite uses an immediate transaction and Postgres uses a transaction-scoped advisory lock to reserve each proposal/order intent before placement. Uncertain placement outcomes retain the durable pending claim and block subsequent routing; only confirmed unfilled failures can be retried. Pending claims are not reclassified as missed by deadline expiry.
- Backtest sizing now uses decision-date holding marks and FX. Affordability simulates whole-share purchases with native cash, conversion rounding and fees. Existing backtest artifacts must be regenerated and re-audited before relying on their results.
- PnL collapse advances the existing baseline instead of replaying pre-reset history; broker-reset lots and realized PnL survive subsequent collapses, and backwards cutoffs are rejected.
- Removed synthetic price/FX writes from the refresh path. Legacy carry-forward settings are accepted but cannot make stale observations current. Zero-volume bars are retried and cannot establish current trading prices; EOD readiness requires current FX too. Legacy synthetic FX has no reliable provenance and needs a separate provider-backed historical repair.
- Added isolated test defaults and regression coverage for concurrent routing, lost acknowledgments, invalid reconciliation, partial cancellations, future-price/FX independence, native cash affordability, repeated outages, and broker-reset baseline preservation.
- Validation: final full suite **240 passed in 189.33s** (`.venv/Scripts/python.exe -B -m pytest -o addopts='' -q -p no:cacheprovider --durations=5`), including 23 new regression cases; Python syntax checks and repository-configured `git diff --check` passed. SQLite concurrency is exercised with real transactions. Postgres reservation SQL and IB behavior have not been tested against external services in this session.


## 2026-07-14 - Current Full Report For Monitored Strategies

- Changed Monitored strategy clicks to open the complete backtest report directly instead of the simplified strategy detail page. Archived rows retain the existing detail fallback, including the 67 discovered artifacts without generated HTML reports.
- The report is rendered from an in-memory monitored copy of the artifact. It extends NAV and the risk-parity benchmark through current golden data, reads current market prices/FX for holdings and contribution analysis, and does not overwrite immutable JSON/HTML artifacts.
- Added explicit artifact-end, monitored-through, lifecycle, and monitoring-method provenance. The report retains full period metrics, largest drawdowns, two benchmark choices, holdings contribution, and signal attribution, and now shares the operational navigation header.
- Live browser verification clicked the monitored SOTA directly into the full report: artifact end `2026-04-29`, monitored through `2026-07-14`, 8 summary metrics, 2 benchmark choices, 15 yearly rows, 1,348 monthly contribution rows, signal attribution visible, and no horizontal overflow. An archived strategy still opened its existing detail page.
- Verification: focused reporting/API/UI tests passed (`32 passed`); full suite passed (`217 tests`); compile and `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Broker-Authoritative Portfolio Reconciliation

- Diagnosed the paper-account reset against live TWS: IB reported zero positions and HKD cash while the local fill-derived ledger implied six positions; the pre-change report contained 18 local filled records, 10 IB executions, and six position differences.
- Made IB positions/cash authoritative for active holdings. The Trading page refreshes reconciliation before rendering and the trading-management loop repeats it on the execution-sync cadence with a dedicated client id (`ST_IB_RECONCILIATION_CLIENT_ID`, default 161).
- Persisted timestamped and latest reconciliation reports, emitted a durable `alert.raised` on a new break signature, disabled operator approval/resubmission, blocked EOD PnL/rebalance staging, and server-blocked IB routing when reconciliation is missing, stale, or broken.
- Added `Reset local to IB` with a server-enforced confirmation. It creates an empty or populated broker-derived PnL baseline while preserving all earlier local orders/fills as immutable audit history.
- Fixed IB execution timestamps without an explicit suffix: TWS supplies them in workstation-local time, so they are now localized before UTC conversion instead of being mislabeled as UTC.
- During live verification an operator-confirmed empty baseline `bed6ac19a652` was created. Final state: reconciliation `matched`, IB positions `0`, HKD cash `1,015,927.30`, zero active open lots, total PnL `0.00`, and the unattended management loop reporting zero breaks.
- Verification: focused reconciliation/execution/management/API/UI suite passed (`60 passed`); full suite passed (`216 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Explicit Market Data Symbol Selection

- Diagnosed the apparent SPY-only Market Data page as a UI discovery failure, not missing data: the datalist held all symbols but rendered only the current SPY value until browser-native suggestions were opened.
- Replaced the datalist text input with an explicit symbol dropdown that visibly repopulates for the selected store and intraday session range.
- Live latest-session Intraday Bars exposed the active pilot `GLD/IWM/QQQ/SPY/TLT`; QQQ loaded 223 delayed 5-second bars. The broader raw catalog also contains AAPL from an earlier smoke partition, for six raw symbols overall.
- Daily Bars exposed all 39 converted symbols. AOR was selected and loaded 3,643 rows from `2012-01-03` through `2026-07-13`, proving the non-SPY converted-store path.
- Verification: focused market-data API/UI tests passed (`11 passed`); full suite passed (`212 passed`); browser checks had zero desktop overflow; `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-14 - Multi-Session Intraday Market Data

- Extended the raw audit and symbol-discovery APIs with inclusive `recorder_start_date` and `recorder_end_date` filters while retaining the existing exact `recorder_date` contract.
- Added `1D`, `5D`, `10D`, and `All` intraday presets plus explicit start/end session inputs. Presets select the latest available recorder partitions, so weekends and recorder gaps do not create artificial empty sessions.
- Multi-session reads scan newest matching catalog evidence first when a limit applies, then return bars and rows chronologically for the chart and audit table. Exact duplicate event ids remain excluded only from the main series and retained in Raw Evidence.
- Live verification found recorder partitions `2026-06-27`, `2026-07-11`, and `2026-07-13`. `1D` selected the latest partition; `5D` and `10D` selected all three. The final 5D SPY view loaded 198 unique delayed 5-second bars with zero desktop overflow; the active recorder continued increasing the count. Daily Bars remained available with 3,651 SPY rows.
- Verification: focused market-data API/UI tests passed (`11 passed`); full suite passed (`212 passed`); `git diff --check` passed apart from existing line-ending warnings. The in-app viewport override remained at 1280px, so no new 390px runtime claim was made.

## 2026-07-13 - First-Class Intraday Market Data Workspace

- Promoted raw intraday recorder bars from the secondary Raw Evidence form into the primary Market Data store selector; `/platform/market-data-audit` now opens on Intraday Bars.
- Extended raw symbol discovery with available/latest recorder dates. The UI automatically selects the latest date, limits symbols to that partition, defaults to 5-second stream bars, and exposes capture mode, delayed/live provenance, quality flags, and raw references.
- Kept raw audit semantics explicit: the main OHLCV series removes exact duplicate raw event ids, while Raw Evidence retains every immutable record and duplicate/hash diagnostics.
- Live browser verification on `2026-07-13` loaded `GLD/IWM/QQQ/SPY/TLT`, 52 unique SPY bars, 57 raw rows, five duplicate ids, and `IB delayed`. Daily Bars remained selectable and loaded 3,651 ClickHouse rows. Desktop/full-width table and 390px compact layouts had no horizontal overflow.
- Verification: focused market-data API/UI tests passed (`10 passed`); full suite passed (`211 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Five-Symbol IB Intraday Recorder Recovery

- Diagnosed the scheduled recorder as process-live but data-degraded: `reqRealTimeBars` failed for all pilot symbols with IB 10089/420 API entitlement errors, historical gap-fill timed out inside the slow raw-write callback after SPY, and the stop script left the child holding client id 121.
- Added independent historical-request timeouts so one symbol cannot abort later symbols, a buffered `reqHistoricalData(..., keepUpToDate=True)` recovery channel, and a timestamped delayed trade stream using TWS delayed last/size/timestamp plus delayed RTVolume callbacks.
- The active testing feed aggregates delayed trades into raw 5-second bars and always records `ib_market_data_mode_delayed` plus `ib_delayed_trade_aggregate`. It is explicitly barred from signals and execution. Paid `reqRealTimeBars` remains selectable after API subscriptions are enabled.
- Kept the initial runtime universe at `SPY/QQQ/TLT/GLD/IWM`; it is a recorder pilot, not the investible universe. Prospective capture now starts before synchronous recovery, and historical gap-fill runs only after a failed stream chunk.
- Hardened service operations: parent state identifies the actual intraday channel and stores parsed child results; degraded children return nonzero; recorder shutdown stops both supervisor and child; health staleness allows the configured 300-second capture chunk plus startup margin.
- Live evidence: bounded canary wrote 25 valid bars in 40 seconds, five per pilot symbol. The first supervised chunk wrote 32 bars (`SPY 7`, `QQQ 6`, `TLT 7`, `GLD 6`, `IWM 6`) with all five symbols covered, raw/catalog/outbox parity, and zero hash mismatches. Timestamps were about 15 minutes delayed, matching IB mode 3.
- A later normal-service restart completed daily ClickHouse backfill, then IB began returning 10197 `No market data during competing live session` for all five subscriptions. The child now fails fast and the parent immediately reports `service_mode=degraded`, the exact source error, and scheduled historical recovery. Clear the competing IB live/TWS session before expecting prospective capture to resume.
- Verification: focused recorder/service/script tests passed (`18 passed`); full suite passed (`211 passed`); PowerShell parsing, service-manifest JSON validation, and `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Monitored Strategy Workspace

- Renamed global navigation to `Trading / Strategies / System / Market Data` across operational pages.
- Added `config/strategy-monitoring.json` and split the registry into Monitored and Archived views. Current SOTA is always monitored; additional strategy ids can be added to the config.
- Monitored strategies extend their audited artifact NAV through current golden daily bars using final audited holdings. The UI explicitly distinguishes artifact end from data-through date and discloses that this is mark-to-market, not full signal/rebalance replay.
- Added click-through strategy detail pages and APIs with NAV versus benchmark, full/in-sample/OOS comparison metrics, holdings, leverage, country/currency exposures, attribution context, and generated rich-report access.
- Live verification: 1 monitored SOTA, 89 archived; SOTA artifact end `2026-04-29`, monitored through `2026-07-10` with 49 extension points; detail rendered 8 metrics, 6 holdings, 3 comparison windows, 2 chart series, and the full report link.
- Verification: full suite passed (`207 tests`); focused catalog/API/UI tests passed (`36 passed`); platform health remained `ok`.

## 2026-07-13 - Rebalance Execution Window And Missed Attribution

- Added a configurable next-open execution deadline using `ST_EXECUTION_REBALANCE_TIMEOUT_MINUTES` (default 30) after `ST_EXECUTION_TWAP_START_TIME` in `ST_AUTOMATION_TIMEZONE`.
- Added durable `missed` proposal and broker-order states. Pending proposals and approved proposals with failed/missing orders expire; broker-accepted orders remain active.
- Approval, direct submission, resubmission, and lower-level IB routing all reject expired proposals. Missed orders store their remaining quantity, reference notional, deadline, timestamp, and reason without inventing a fill price.
- Operator proposal rows are grey when missed, decisions/resubmission are disabled, and deadline/reason are visible. Execution-quality analysis reports missed count, reference notional, and detailed missed orders.
- Live queue cleanup marked 32 stale proposals and 192 orders missed while preserving 6 approved proposals with routed activity. Browser verification confirmed 32 grey rows with disabled Approve/Reject controls.
- Reduced the operator's legacy PnL-comparison history request from 60 recomputed points to 1 so missed analysis is not held behind a multi-minute historical recalculation.
- Verification: full suite passed (`207 tests`); focused API/domain/router/UI tests passed (`48 passed`); `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-13 - Unified Operational Header

- Standardized Operator, Strategies, Platform Health, and Market Data headers on the same ordered navigation: Operator, Strategies, Health, Market Data.
- Removed page-specific controls from the global header. Health Refresh/status now live in Service Status; market-data refresh/status live in filter toolbars; operator connection state lives in Automation.
- Added a regression test that compares the header link contract across all primary pages and rejects header buttons or status widgets.
- Browser verification confirmed identical Health and Strategies navigation with zero header buttons/status elements; focused UI/script tests passed (`7 passed`).
- Updated dispatcher startup to store the child process id reported by its state file, preventing orphaned dispatcher processes during dashboard restarts.

## 2026-07-13 - Primary Strategy Navigation

- The strategy catalog existed at `/strategies`, but its only Operator entry point was buried inside the Performance panel and was not discoverable from the global page header.
- Added a persistent `Strategies` destination to the Operator, Platform Health, and Market Data headers.
- Browser verification clicked Strategies from Platform Health, opened `/strategies`, loaded 90 strategy runs, and displayed the current SOTA detail.
- Replaced supervisor command-line inspection with privilege-independent identity checks: operator PID must own port 8000, while the dispatcher publishes its process id in the service state file.
- Verification: focused operator UI/script tests passed (`6 passed`); dispatcher script compiled; live `/platform` and `/strategies` browser checks passed.

## 2026-07-13 - Operator Startup Blocked By Recycled PID

- `start_local_platform.ps1` reported completion but `127.0.0.1:8000` had no listener because `var/run/operator_dashboard.pid` contained stale PID `31312`, which Windows had reassigned to Microsoft Edge.
- Hardened `scripts/start_operator_dashboard.ps1` so operator and dispatcher PID files are trusted only when the process command line contains the expected service script; a mismatched live PID is treated as stale.
- Hardened `scripts/stop_operator_dashboard.ps1` with the same identity check so stale PID reuse cannot terminate an unrelated process.
- Live recovery preserved Edge, started Uvicorn as PID `36112`, and restored `/platform` with HTTP 200. Browser verification reported overall `ok`, 7/7 required services healthy, and 0 errors/degraded services.
- Verification: `tests/test_operator_scripts.py` passed; live startup and browser smoke passed; `git diff --check` passed apart from existing line-ending warnings.

## 2026-07-12 - Strategy Catalog And Theoretical Versus Actual Attribution

- Added a read-only strategy artifact catalog over `var/backtests`, exposed through `GET /api/v1/strategies` and `/strategies`.
- The catalog pins the canonical current SOTA, normalizes comparable backtest metrics, exposes artifact provenance and final allocation, and discovers 90 distinct usable strategy runs in current local artifacts.
- Clarified the operator performance contract: indexed SOTA backtest NAV is theoretical strategy performance and account NAV is actual performance; reference-fill PnL remains a separate execution-quality counterfactual.
- Recorded the alpha-factory direction in `docs/research-state.md`: versioned factor identities, theoretical and realized contribution, covariance-aware weighting, capacity/cost controls, and promotion discipline are required before factor risk-parity allocation.
- Verification: focused strategy/operator/API tests passed (`35 passed`); full suite passed (`200 passed`).

This file records durable project decisions, operating status, incidents, and next actions. Keep entries concise, dated, and useful for future agents and human review.

## 2026-07-12

### TWS Health, Docker Preflight, And Paper Reset Reconciliation

- Operator reported three operational gaps: TWS was not monitored as a critical dependency, `start_local_platform.ps1` failed opaquely when Docker Desktop Linux engine was not running, and the IB paper account reset can diverge from local trade records.
- Added Docker daemon preflight: `scripts/assert_docker_ready.ps1` now runs before NATS and ClickHouse Docker Compose startup. It attempts to start Docker Desktop and wait for the daemon when used by the NATS/ClickHouse startup scripts. Local Docker-down smoke returned a concise Docker Desktop/Linux engine remediation message and suggested `-SkipNats -SkipClickHouse` for partial startup.
- Added TWS/API health monitoring: `systematic_trading.execution.ib_health`, `scripts/probe_ib_tws_health.py`, and service manifest entry `ib_tws_api`. Startup and watchdog runs refresh `var/run/ib_tws_api.state.json`; platform health reads the state file.
- Local TWS probe on 2026-07-12 reported `running=false`: TWS/API was not reachable at `127.0.0.1:7497`, and no `nextValidId` arrived for health client id `151`. This is now visible as a platform health error instead of a silent dependency failure.
- Added report-first IB paper reconciliation: `systematic_trading.execution.reconciliation`, API endpoint `POST /api/v1/dashboard/reconciliation/interactive-brokers`, and CLI `scripts/reconcile_ib_paper_account.py`.
- Reconciliation compares local broker order records with IB paper executions and the fetched IB account snapshot. It reports unmatched local orders, unmatched IB fills, and position differences.
- For confirmed IB paper-account resets with zero broker positions, the CLI can explicitly write an empty PnL reset baseline with `--record-pnl-reset-baseline --confirm-paper-reset`. Local broker order records remain audit history and are not deleted or mutated automatically.
- Current remaining gate work: make order routing and live recorder capture require fresh IB health plus no unresolved reconciliation breaks before proceeding; include broker open orders and commissions in reconciliation; persist reconciliation runs in Postgres.
- Verification: focused tests passed (`30 passed`); compile pass passed for `src`, `scripts/probe_ib_tws_health.py`, and `scripts/reconcile_ib_paper_account.py`.

## 2026-07-11

### Postgres Transactional Store Migration

- Completed the first Postgres transactional runtime migration slice after ClickHouse market-data routing was verified.
- Added versioned migration tooling: `deploy/postgres/migrations/001_initial_transactional_store.sql` and `scripts/apply_postgres_migrations.py`.
- Added `PostgresStore` and factory support for `ST_TRANSACTIONAL_STORE_BACKEND=postgres`. The Python settings default remains SQLite for isolated tests/fallback, but local startup scripts now default to Postgres transactional state and ClickHouse market data.
- Added compatibility settings for existing local password names in `.env` (`ST_APP_POSTGRE_DB_PASSWORD`, `ST_MIGRATOR_POSTGRE_DB_PASSWORD`, and related aliases) plus cleaner `ST_POSTGRES_*` settings for future deployments.
- Added one-way migration tooling from SQLite transactional state to Postgres: `scripts/sync_sqlite_transactional_to_postgres.py`. The script intentionally does not copy SQLite price bars or FX rates because daily bars and FX belong in ClickHouse.
- Applied migration `001_initial_transactional_store` to local Postgres.
- Postgres adapter smoke passed: wrote/read a synthetic instrument, thesis, fundamental snapshot, proposal, approval, filled broker order, PnL baseline/snapshot, and outbox rows through `PostgresStore`, then cleaned up.
- Synced current SQLite transactional state into Postgres: 39 instruments, 38 proposals, 7 approval decisions, 16 broker order records, 37 PnL snapshots, and 955 copied outbox events.
- Fixed a migration-safety issue: copying through store methods briefly recreated 44 deterministic proposal/order/fill events that were not in the original SQLite outbox. Updated the sync script to treat SQLite outbox ids as authoritative during migration and delete migration-generated synthetic events. Final Postgres outbox count is 955 with 0 pending copied events.
- Runtime smoke with `ST_TRANSACTIONAL_STORE_BACKEND=postgres` and `ST_MARKET_DATA_STORE_BACKEND=clickhouse` passed. `/health`, `/api/v1/proposals`, and `/api/v1/market-data/bars/SPY?start_date=2026-06-01&end_date=2026-06-01` returned HTTP 200; the SPY bar came from ClickHouse with close `756.5908203125` and volume `43634900`.
- Verification: focused storage/script tests passed (`19 passed`), full suite passed (`194 passed`), and final affected script/manifest/storage tests passed (`14 passed`).
- Current posture: Postgres is the recommended local transactional runtime; ClickHouse is the market-data runtime; SQLite remains a legacy fallback/migration source until a short operational soak and legacy research-script cleanup are complete.

### Live Market-Data Subscription Shakedown

- Operator reported IB market-data subscription is now active.
- Started a P3.4a foundation shakedown: bring up NATS, Postgres, ClickHouse, operator dashboard, dispatcher, and then run a bounded IB paper market-data recorder canary in live mode.
- Guardrail: keep recorder opt-in and canary-sized until raw writes, catalog coverage, health state, and disk impact are verified.
- First startup attempt failed because Docker Desktop's Linux engine was not running. Launched Docker Desktop, then `scripts/start_local_platform.ps1` completed.
- Core services verified: watchdog reported required NATS JetStream, Postgres, ClickHouse, and operator dashboard `ok`; service graph endpoint returned 7 nodes; ClickHouse smoke returned `smoke_rows=2`; Docker showed NATS and ClickHouse containers running.
- Initial `/health` degraded because TWS was not logged in, causing IB automation `nextValidId` timeouts and opening the IB automation circuit until `2026-07-11T03:45:31Z`. After TWS login, standalone IB paper API smoke passed with `next_valid_order_id=20`.
- Recorder proof is still blocked by IB market-data entitlements/session state. Historical SPY live-mode smoke wrote 0 bars and returned IB 162: `Trading TWS session is connected from a different IP address`. Follow-up tests with explicit `20260710 16:00:00 US/Eastern` end time failed the same way for 5-second live, 5-second delayed, and 1-day live historical bars. Realtime live canaries wrote 0 bars: AAPL/MSFT/QQQ/TLT returned IB 420 for `ISLAND STK`; SPY/IWM/GLD returned IB 420 for `AMEX STK`. Delayed AAPL realtime canary returned IB 10089 requiring an additional API market-data subscription.
- Raw-data audit after the blocked canaries: recorder state shows 0 records written, 0 catalog entries appended, and the E hot spool remains about 0.006 MB with only the previous 3 SPY historical-smoke records from 2026-06-27.
- Next action: verify IB Account Management/TWS Market Data Connections for API-enabled US equity/ETF streaming on the paper session, eliminate the different-IP session conflict, then rerun a 1-symbol live ETF canary during market hours before scaling.
- Started follow-up debug specifically for the IB historical-data failure path to separate local request-construction issues from IB entitlement, paper/live sharing, and session-IP causes.
- Historical-data debug result: IB contract-detail probes resolved SPY to conId `756733` primary `ARCA`, AAPL to `265598` primary `NASDAQ`, and QQQ to `320227571` primary `NASDAQ`; contract resolution is not the historical blocker.
- Direct IB API historical probes succeeded for SPY daily bars across SMART/no-primary, SMART+ARCA, conId, ARCA direct, AMEX direct, MIDPOINT, and AAPL daily variants.
- Recorder historical path then succeeded: 3 SPY daily bars, 5 SPY 5-second bars, and 6 multi-symbol 5-second bars for SPY/QQQ/AAPL were written under the E hot spool for recorder date 2026-07-11 and appended to the raw catalog/outbox.
- Catalog/replay audit: `scripts/catalog_market_data_raw.py --date 2026-07-11` reported 14 entries, 0 invalid records, and 0 duplicate raw refs. `scripts/replay_market_data_raw.py --symbol SPY --date 2026-07-11` read 10 valid records with 0 payload-hash mismatches and 2 duplicate deterministic raw event ids caused by repeated smoke pulls of the same bars.
- Updated diagnosis: the earlier historical IB 162 looks like transient TWS market-data session readiness or stale different-IP ownership immediately after login, not a local recorder request-construction bug. Live realtime streaming remains separately blocked: a SPY/AAPL realtime canary wrote 0 bars and returned IB 10089 requiring additional API market-data subscription.
- Started first-party market-data audit portal implementation. Decision: use the existing operator/platform portal for raw/historical audit drilldown, with Grafana/Superset reserved for broader monitoring and ad-hoc BI later.
- Completed first market-data audit portal slice. Added `/api/v1/market-data/audit` for raw catalog queries with raw JSONL dereference, payload-hash verification, duplicate raw-event-id counting, and chart/table-ready rows. Added `/platform/market-data-audit` with filters, summary metrics, OHLC SVG chart, raw-record table, and audit details.
- Fixed the IB historical recorder to persist the requested historical bar size because IB historical `BarData` did not provide a `barSize` attribute; the audit UI leaves bar-size blank by default so older records with null bar size remain visible.
- Clarified market-data environment semantics: raw records keep capture environment as provenance, but canonical historical market data should not be keyed as paper versus live. Updated the audit API/UI so capture environment is optional/default-all and labelled as `Capture Env`.
- Added a raw-catalog symbol discovery endpoint and wired the audit page symbol input to a searchable dropdown. Live `/api/v1/market-data/audit/symbols?recorder_date=2026-07-11` returned `AAPL`, `QQQ`, and `SPY`.
- Unified the top navigation across `/operator`, `/platform`, and `/platform/market-data-audit` with quick links to Operator, Health, and Market Data so the major platform functions are reachable from each page.
- Added safe restart controls to the health page. `/api/v1/platform/service-actions` marks NATS JetStream and ClickHouse restartable through fixed local script mappings, while Postgres, the operator API itself, dispatcher, and embedded trading loop show disabled reasons. The health page renders restart buttons only for supported services.
- Live verification after dashboard restart: `/platform/market-data-audit` returned HTTP 200 and `/api/v1/market-data/audit?symbol=SPY&recorder_date=2026-07-11&limit=20` returned 10 rows/bars, 0 hash mismatches, 0 invalid records, and 2 duplicate deterministic raw event ids from repeated smoke pulls.
- Verification passed: focused audit/UI/recorder tests `11 passed`; full suite `175 passed`.
- Changed the recorder operating model from opt-in one-shot pilot to always-on scheduled service. Added `scripts/run_market_data_recorder_service.py` and `scripts/start_market_data_recorder_service.ps1`; `scripts/start_local_platform.ps1` now starts the recorder service by default unless `-SkipMarketDataRecorder` is used.
- Recorder service behavior: stays running and writes health state while idle outside regular US equity hours/weekends, runs a historical lookback gap-fill before live capture after startup/restart during the session, then records in bounded realtime chunks. Current v0 uses weekday/time windows and does not yet include exchange holiday calendar logic.
- Health smoke after starting the service on Saturday 2026-07-11: recorder process PID existed, state showed `service_mode=idle` and `session_reason=weekend`, `/health` reported overall `ok`, and `market_data_recorder` reported `ok` with message `Market data recorder service idle: weekend.`
- Health restart controls updated: `market_data_recorder` is now restartable through fixed stop/start scripts.
- Verification passed after scheduled-recorder changes: focused service/script/manifest/action tests `10 passed`; full suite `181 passed`.
- Corrected market-data architecture direction after operator review: the raw audit page is not enough and should not be the main market-data workstation. Added `docs/market-data-golden-source.md` defining raw evidence, future source observations, and ClickHouse golden daily/intraday tables.
- Added `systematic_trading.market_data.golden` and `scripts/sync_sqlite_daily_bars_to_clickhouse.py` as the first bridge from existing SQLite `price_bars` into ClickHouse golden daily bars.
- Ran the initial ClickHouse sync from SQLite: `market_data.daily_bars` now has 140,686 golden daily rows after `OPTIMIZE FINAL`, covering 39 symbols from 2012-01-03 through 2026-07-10.
- ClickHouse golden client query smoke returned 7 SPY rows for 2026-07-01 through 2026-07-10 from `market_data.daily_bars`.
- Verification passed after golden-source changes: focused tests `5 passed`; full suite `182 passed`.
- Next correction for the market-data page: switch the main view from raw recorder audit to ClickHouse golden historical bars with symbol search, date range, zoomable OHLC/volume chart, table, and optional drilldown from golden bar to source observations/raw refs.
- Completed the golden-market-data workstation slice. Added `/api/v1/market-data/golden/daily-symbols` and `/api/v1/market-data/golden/daily-bars` around the ClickHouse golden daily table, with uppercased symbol normalization and chart/table-ready response summaries.
- Replaced the primary `/platform/market-data-audit` workflow with golden daily history: searchable golden symbol dropdown, full-history default range, date range filters, 1M/3M/YTD/1Y/5Y/All buttons, pan/zoom controls, OHLCV chart with volume pane, and golden-bar table. Raw recorder audit remains available as secondary raw evidence on the same page.
- Live platform smoke after operator dashboard restart: `/health` returned overall `ok`; golden symbol endpoint returned 39 symbols; `/api/v1/market-data/golden/daily-bars?symbol=SPY&start_date=2026-07-01&end_date=2026-07-10&limit=100` returned 7 bars from `sqlite_price_bars`; page HTML returned 200 and included the golden endpoints.
- Browser verification: desktop loaded SPY full history with 3,652 bars, one chart SVG, 3,652 table rows, no console warnings/errors; the 1Y range control narrowed to 254 bars; compact 390px viewport rendered without horizontal overflow.
- Verification passed: focused market-data/API/UI tests `9 passed`; full suite `184 passed`.
- Next action for P3.4: add ClickHouse source-observation tables and explicit source precedence/disagreement checks, then add intraday golden bars and gap/staleness panels.
- Operator challenged the implementation on three points: visible SPY gaps, overuse of `Golden` in the interface, and whether the database is truly unified or still glued together.
- Correction: the platform is not fully unified yet. Daily historical bars are in ClickHouse `market_data.daily_bars` and are now the preferred serving source, but SQLite `price_bars` remains for legacy research/backtest/automation paths, raw recorder JSONL remains the immutable evidence archive, and intraday bars are not yet normalized into ClickHouse.
- Added direct ClickHouse daily backfill: `systematic_trading.market_data.backfill` plus `scripts/backfill_clickhouse_daily_bars.py`. The job compares provider-returned dates with ClickHouse dates and inserts only missing rows by default, with `--refresh-existing` available for deliberate source refresh. Providers supported: Yahoo adjusted daily, IB historical daily fallback, and explicit Tushare.
- Wired the always-on market-data recorder service to run the ClickHouse daily backfill child job on startup and on interval, including after-hours/weekends. Recorder health state now records daily-backfill status and degrades via `last_error` if the child fails. `/health` now preserves state-file detail payloads.
- Removed visible `Golden` wording from the market-data UI. The page now calls plain aliases `/api/v1/market-data/daily-symbols` and `/api/v1/market-data/daily-bars`; existing `/golden/...` aliases remain for compatibility.
- SPY backfill smoke: 2026-07-01 through 2026-07-10 returned Yahoo provider bars=7, existing ClickHouse dates=7, inserted=0. Full SPY 2012-01-01 through 2026-07-10 returned existing dates=3,652, Yahoo provider bars=3,650, inserted=0. Conclusion: the visible issue is not a simple Yahoo-visible missing-date gap; next UI/data-quality slice needs explicit trading-calendar/source-disagreement panels.
- Restarted the market-data recorder service to load the new daily-backfill behavior. Startup backfill completed with returncode 0, returned the service to weekend idle, and increased ClickHouse daily rows from 140,686 to 140,920 by filling recent stale symbols. SPY/TLT/VGK already had the recent 9 provider dates and inserted 0. HYXU remains stale at 2026-05-22 because Yahoo returned no recent bars and the IB adjusted-last fallback rejected the end-date request; track this as a source-specific quality issue.
- Live verification after dashboard restart: `/health` overall `ok`, `/api/v1/market-data/daily-symbols` returned 39 symbols, SPY July slice returned 7 rows, page HTML returned 200, visible `Golden Daily` text was absent, browser reload rendered SPY with 3,652 rows and no console warnings/errors.
- Verification passed: focused backfill/API/UI/script/health tests `20 passed`; full suite `186 passed`.
- Operator reported SPY still had no usable bars in May/June 2026. Debug showed the API did return rows, but many were stale SQLite carry-forward artifacts: flat OHLC, volume 0, source `sqlite_price_bars`. Example: 2026-06-01 stored as flat 745.70/0 volume while Yahoo adjusted data returned close 756.5908203125 with volume 43,634,900.
- Root cause: the new backfill inserted only absent dates, so stale existing rows blocked provider replacement. Fixed `backfill_clickhouse_daily_bars` to repair flat zero-volume carry-forward rows when provider bars exist and to delete flat zero-volume rows absent from provider calendars.
- SPY May/June repair result: first pass inserted/repaired 23 Yahoo adjusted rows from 2026-05-26 through 2026-06-26. Second pass deleted two stale holiday artifacts: 2026-05-25 and 2026-06-19. Final API check for 2026-05-01 through 2026-06-30 returned 41 rows, 0 flat zero-volume rows, and valid Yahoo bars for 2026-05-29, 2026-06-01, and 2026-06-15.
- Ran the same 60-day repair over all 39 symbols. It inserted/repaired 884 rows, then deleted stale holiday artifacts across affected symbols. Final ClickHouse daily total is 141,512 rows.
- Verification passed after stale-row repair: focused tests `9 passed`; full suite `188 passed`.
- Audited whether signal, portfolio rebalance, trade generation, dashboard valuation, and backtests have moved to ClickHouse. Result: not yet. The market-data page/API and direct daily backfill use ClickHouse, but active strategy/rebalance/PnL/backtest paths still read `store.list_price_bars`, which is backed by SQLite through the current `storage.factory`.
- Active SQLite-dependent paths include `live/sota.py` SOTA rebalance plan generation, `web/api.py` dashboard mark-to-market/account valuation helpers, `live/pnl.py` unrealized PnL valuation, `backtest/stored.py` and `backtest/stock_replacement.py`, `live/market_data.py` after-close refresh/carry-forward, and multiple research scripts. `scripts/run_sota_live_rebalance.py` explicitly instantiates `SQLiteStore`.
- Verified the risk: SQLite still has bad SPY May/June 2026 data after ClickHouse was repaired. SQLite query returned 43 SPY rows from 2026-05-01 through 2026-06-30, with 25 flat zero-volume rows including 2026-05-29, 2026-06-01, 2026-06-15, and the holiday artifacts 2026-05-25/2026-06-19. Therefore current rebalance/signal output would still see stale prices unless migrated or explicitly repaired.
- Added P3.4c to the Kanban as the next safety-critical work item: migrate strategy, rebalance, dashboard valuation/PnL, and stored backtest daily-bar reads from SQLite to ClickHouse before trusting new rebalance output.
- Started P3.4c migration. Added `ClickHouseMarketDataStore`, `MarketDataRoutedTradingStore`, and `create_trading_store` so active runtime code can use ClickHouse for daily bars and FX while delegating transactional state to SQLite.
- Added `ST_MARKET_DATA_STORE_BACKEND`; the operator startup script defaults to `clickhouse`, so dashboard, SOTA rebalance, PnL, and legacy market-data API calls route `list_price_bars`/`list_fx_rates` to ClickHouse in the local platform runtime.
- Added `market_data.fx_rates` ClickHouse table support and synced 3,790 SQLite FX rows into ClickHouse with `scripts/sync_sqlite_fx_rates_to_clickhouse.py`.
- Live routed-store smoke: `store.list_price_bars("SPY", 2026-06-01)` returned ClickHouse close 756.5908203125 and volume 43,634,900; `store.list_fx_rates(USD, end_date=2026-06-01)` returned latest USD/CNH 6.794000148773193.
- Restarted dashboard with ClickHouse market-data backend. Legacy `/api/v1/market-data/bars/SPY?start_date=2026-06-01&end_date=2026-06-01` returned the repaired ClickHouse bar, matching `/api/v1/market-data/daily-bars`.
- SOTA rebalance CLI smoke succeeded for decision date 2026-07-10 and intended trade date 2026-07-13 without queuing orders, producing artifacts in `var/tmp/sota_clickhouse_smoke/`.
- Remaining SQLite scope: transactional state still uses SQLite until the Postgres adapter is implemented, and older research scripts that instantiate `SQLiteStore` directly are not fully migrated.
- Verification passed after routed-store migration: focused tests `40 passed`; full suite `190 passed`.

## 2026-06-29

### Recorder/VPN/TWS Incident And Hardening

- Operator reported a one-day recorder run with multiple failures: external VPN was switched off or idled, NATS/ClickHouse became unavailable, and IB TWS later logged out and produced repeated API failures that required manual relogin.
- Local evidence showed a repeated automation alert storm from IB execution/account snapshot tasks. Messages progressed from IB farm disconnects to repeated `Timed out waiting for IB nextValidId callback for client_id 131/141`.
- The 2026-06-29 delayed 5-symbol recorder pilot for `SPY`, `QQQ`, `TLT`, `GLD`, and `IWM` wrote 0 records and received IB 420 market-data-permission errors for AMEX/ISLAND ETF contracts. Delayed mode remains useful for tiny experiments, but it is not sufficient proof that the 5-second streaming recorder can run before live subscriptions are enabled.
- Decision: do not rely on an external idle-sensitive VPN as part of the critical local trading platform network path. For 24x7 operation, move required infrastructure and IB Gateway toward a supervised server/native-service path.
- Decision: keep IB live-data subscriptions planned for July 2026 as the gating event for real intraday streaming. After subscriptions are enabled, run live-mode entitlement smoke tests before scaling from 1 symbol to 5 symbols and then to 30-40 ETFs.
- Added an IB automation circuit breaker to the trading management loop. After repeated IB failures, automation backs off execution/account-snapshot retries, records circuit state in `var/live/trading_management_service_state.json`, and exposes it through platform health details.
- Added automation alert deduplication so repeated identical warning/error events do not flood `var/log/automation_alerts.jsonl` or the platform outbox.
- Added `scripts/watch_local_platform.ps1` for local health checks and optional repair. It checks NATS, Postgres, ClickHouse, the operator API, and recorder state; `-Repair` recreates NATS/ClickHouse through Docker Compose and restarts the operator dashboard if needed. It does not auto-start the recorder.
- Hardened SOTA automation against account snapshots that include holdings outside the current SOTA universe. Non-SOTA positions such as `DBB` and `USO` are filtered with warnings for SOTA proposal staging instead of failing the trading management loop.
- Updated platform health semantics so an optional service with `running=false`, such as the intentionally stopped recorder, reports `disabled` rather than stale/degraded.
- Ran the watchdog after repair: required services were `ok` for NATS JetStream, Postgres, ClickHouse, and operator dashboard. The recorder was explicitly stopped and reported as optional/disabled.
- Verification passed: full suite `173 passed`; focused watchdog smoke returned required-service status `ok`; final `GET /health` returned overall `ok` with NATS, Postgres, ClickHouse, operator dashboard, event dispatcher, and trading management loop all `ok`, and the optional recorder `disabled`.

## 2026-06-27

### Foundation Proving Session

- Started P6.0 after the operator chose to prove the current foundation before expanding market-data recording or normalization.
- Scope: add a recommended local startup path, monitor NATS/Postgres/ClickHouse/operator/dispatcher/recorder health, expose a web portal with a service connection chart, and keep market-data recording opt-in to protect disk space.
- P3.4a was added as the next market-data step: a small ETF raw-data recording and audit loop before broad normalized-bar ingestion.
- Completed P6.0 foundation proving.
- Added `scripts/start_local_platform.ps1` as the recommended local startup path. It starts NATS JetStream, configures the `ST_EVENTS` stream, verifies Postgres, starts ClickHouse, starts the operator dashboard and event dispatcher, and leaves market-data recording opt-in behind `-StartMarketDataRecorder`.
- Added `scripts/stop_local_platform.ps1` and `scripts/stop_market_data_recorder.ps1`; the stop path does not stop external Postgres.
- Promoted NATS, Postgres, and ClickHouse into active health-monitored services in `config/service-manifest.json`.
- Added TCP health checks for Postgres and a service graph contract at `/api/v1/platform/service-graph`.
- Added the platform health portal at `/platform`; it shows summary health, per-service cards, detail rows, and a manifest-derived service connection chart.
- Local smoke after startup reported required services `ok`: NATS JetStream, Postgres, ClickHouse, operator dashboard, event outbox dispatcher, and embedded trading management loop. Optional market-data recorder was degraded because it was intentionally not started.
- Browser check of `/platform` showed 7 service cards, 7 detail rows, an in-bounds SVG graph, overall `ok`, and no console errors.
- Verification passed: full test suite `166 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.
- Next action remains P3.4a: run a small ETF raw-data pilot and data audit before broad normalization.
- Started P3.4a pilot operation. First live-mode IB recorder attempt reached TWS but failed with IB error 420: no live market-data permissions for AMEX STK.
- Decision: default local recorder pilots to IB delayed market data until live exchange subscriptions are explicitly enabled. Added `-RecorderMarketDataMode` to `scripts/start_local_platform.ps1`; default is `delayed`, with `live`, `frozen`, and `delayed_frozen` available.

### Observability Logs

- Completed P6.0a structured operational logs v0.
- Added `systematic_trading.services.operational_log` with `OperationalLogger`, JSONL append helpers, UTC timestamps, level/event/message/details fields, and redaction for obvious secret keys such as passwords, tokens, credentials, secrets, and API keys.
- Standard operational log path is `var/log/platform_operations.jsonl`.
- `scripts/start_local_platform.ps1` now logs local supervisor startup requests, NATS/ClickHouse/Postgres readiness steps, operator startup, recorder opt-in decisions, recorder pilot process start, completion, and startup failures.
- `scripts/start_operator_dashboard.ps1` passes the shared operational log path to `scripts/dispatch_event_outbox.py`.
- `scripts/dispatch_event_outbox.py` now logs dispatcher start, dispatch batches with activity or periodic heartbeat, publish failures, max-iteration stops, one-shot completion, and operator interruption.
- Operator API lifespan logs are emitted by `systematic_trading.app`: API startup/shutdown plus embedded automation loop start/stop.
- Market-data recorder logs now include run start/completion/failure/interruption, PID removal, initialization, subscriptions/request starts, IB market-data mode callbacks, pacing sleeps, first/periodic bar writes, source errors, and disconnects.
- `scripts/stop_market_data_recorder.ps1` now rewrites the recorder state file as stopped and appends operational log events for normal stops, stale PID cleanup, empty PID cleanup, and no-PID cases.
- Smoke check wrote `dispatcher_started`, `dispatch_batch`, and `dispatcher_completed` rows to `var/log/dispatch_smoke_operations.jsonl`.
- Verification passed: focused observability suite `31 passed`; full suite `169 passed`; final focused script/log/recorder suite `9 passed`; service manifest JSON validation; `git diff --check` only reported existing LF/CRLF warnings.

### Execution Process

- Added `docs/execution-kanban.md` as the durable Kanban-style execution tracker.
- Future sessions must update the Kanban before starting and after completing implementation work.
- Status values are `Done`, `In Progress`, `Pending`, `Blocked`, and `Review`.
- `AGENTS.md`, `README.md`, and `docs/industrial-platform-plan.md` now point future agents to the tracker.

### Direction

- Reframed the project target from a local Python research toolkit into a 24x7 industrial systematic trading platform.
- Target architecture now requires micro-services, message queue, columnar analytics storage, transactional order state, live market-data recording, LEAN-compatible backtesting, Interactive Brokers execution, Grafana-class monitoring, strong rebalance blotter, and explicit research-to-paper-to-live promotion controls.
- Python remains the default for research, APIs, reports, and orchestration. Go, Rust, or C++ should be introduced only at measured bottlenecks or reliability-critical service boundaries.

### Decisions

- Keep the existing FastAPI, SQLite, dashboard, and paper-routing implementation as the v0 control plane.
- Treat `docs/industrial-platform-plan.md` as the target-state architecture and execution schedule.
- Treat `docs/research-state.md` as the current strategy research memory and SOTA promotion reference.
- Treat `docs/live-rollout.md` as the current paper-to-live operating path.
- Live trading remains blocked until paper execution, reconciliation, alerts, monitoring, market-data recording, and rollback procedures are proven.

### Next Actions

1. Select the initial local queue and storage stack: NATS JetStream or Redpanda for events, Postgres for transactional state, ClickHouse or Parquet-first warehouse for columnar analytics.
2. Define event schemas for market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
3. Add a market-data recorder service that writes immutable raw data before publishing normalized events.
4. Add a strategy promotion registry with artifact hashes and explicit state transitions.
5. Build the strong rebalance blotter model and dashboard workflow.
6. Add Grafana-class metrics and dashboards for data, services, portfolio, and execution.
7. Add daily post-trade, continuous research, and robustness review reports.

### Open Risks

- SQLite is not a sufficient target-state system of record for 24x7 trading operations.
- Current backtesting is useful but must be supplemented with LEAN or a proven equivalent before production promotion.
- Current alerting is not broad enough for live trading because urgent SMS, push, desktop popup, dashboard, and incident workflows are not complete.
- Live market-data recording is not yet a first-class always-on service.

### Implementation Progress

- Added initial versioned platform event contracts in `systematic_trading.domain.events`.
- Covered market data, features, proposals, orders, fills, reconciliation, alerts, and incidents.
- Added tests for event subjects, JSON round trips, typed decoding, timezone-aware timestamps, positive trading quantities, and strict payload fields.
- Full test suite passed: 123 tests.
- Added durable SQLite platform event outbox with append, pending-list, publish-success, and publish-failure recording.
- Added queue-agnostic event outbox dispatcher and in-memory publisher in `systematic_trading.messaging.outbox`.
- Added tests for idempotent event append, pending order, publish marking, failure retention, retry, and successful dispatch.
- Wired transactional event producers into SQLite storage for proposal creation, approval decisions, broker order status changes, and aggregate fill records.
- Added tests proving real storage mutations append the expected outbox events without duplicate proposal or fill events on repeated saves.
- Added local JSONL platform event publisher and `scripts/dispatch_event_outbox.py`.
- The dispatch script can run once or poll continuously with `--loop`; default output is `var/events/platform_events.jsonl`.
- Integrated the event outbox dispatcher into `scripts/start_operator_dashboard.ps1` and `scripts/stop_operator_dashboard.ps1`.
- Start script now launches `dispatch_event_outbox.py --loop` unless `-DisableEventDispatcher` is passed.
- Stop script now stops both the event outbox dispatcher and the dashboard.
- Smoke tested the operator stack on port 8765: dashboard health returned `{"status":"ok"}`, dispatcher PID existed, and stop removed both processes.
- Added `docs/service-supervisor.md` and `config/service-manifest.json`.
- Added `systematic_trading.services.manifest` loader and validation models.
- Service manifest currently covers the operator dashboard, event outbox dispatcher, embedded trading management loop, and planned market data recorder.
- Corrected execution ordering after review: P1.6 event replay and P1.7 queue selection should come before P2.3 health-check work.
- Marked P1.8 real queue publisher adapter as blocked until P1.7 selects a queue and a local/server runtime is available.
- Added platform event replay support for JSONL and SQLite outbox records in `systematic_trading.messaging.replay`.
- Added `scripts/replay_platform_events.py` for event replay summaries and detailed event inspection.
- Selected NATS JetStream as the initial real queue adapter target; rationale and adapter contract are documented in `docs/queue-adapter-selection.md`.
- P1.8 remains blocked until a local/server NATS JetStream runtime path and Python client dependency are available.
- Added the P2.3 service health contract in `systematic_trading.services.health`.
- `GET /health` now returns normalized platform health with per-service status, heartbeat, running state, and last error while preserving HTTP 200 for API liveness.
- The event outbox dispatcher now writes `var/run/event_outbox_dispatcher.state.json` heartbeats via `--state-path`.
- Updated `config/service-manifest.json`, `docs/service-supervisor.md`, and `docs/data-contracts.md` for the health contract.
- Full test suite passed: 144 tests.
- Added the P6.4 alert event producer.
- `AutomationAlertNotifier` now accepts an optional event store and appends typed `alert.raised` platform events for automation warnings and errors.
- `TradingManagementService` passes its SQLite store to the default alert notifier, so automation alerts enter the durable outbox without changing existing JSONL/email behavior.
- Alert outbox append failures are logged to `automation_alert_event_errors.log` and do not suppress existing alert logging.
- Full test suite passed: 146 tests.
- Added the P3.1 market data recorder contract in `docs/market-data-recorder-contract.md`.
- The contract defines raw-before-publish rules, the raw JSONL envelope, storage layout, normalized `market_data.recorded` mapping, replay behavior, quality flags, and service-health state requirements.
- Linked the contract from `README.md`, `docs/data-contracts.md`, and `docs/service-supervisor.md`.
- `git diff --check` passed after the documentation update.
- Accepted Docker Compose as the recommended NATS JetStream runtime path.
- Added `deploy/nats/docker-compose.yml`, `deploy/nats/nats-server.conf`, `scripts/start_nats_jetstream.ps1`, `scripts/stop_nats_jetstream.ps1`, and `scripts/configure_nats_stream.py`.
- Added optional queue dependency `nats-py` and `systematic_trading.messaging.NatsJetStreamPublisher`.
- `scripts/dispatch_event_outbox.py` now supports `--publisher nats --nats-url nats://127.0.0.1:4222`.
- Added `nats_jetstream` to `config/service-manifest.json` as a planned Docker Compose service.
- Docker CLI is not installed on this machine, so live NATS startup/stream smoke remains blocked under P2.8.
- Full test suite passed: 147 tests.
- Attempted live NATS smoke after operator reported Docker installation.
- `docker --version` and `docker compose version` are still unavailable in this shell; standard Docker Desktop paths were not present.
- `winget list --name Docker` showed `Docker.sbx`, not Docker Desktop or a visible Docker CLI/engine.
- Installed the queue optional dependency into `.venv`; `nats-py` imports successfully.
- Focused queue tests passed after dependency install: `tests/test_nats_publisher.py` and `tests/test_event_outbox.py`.
- Docker became visible in the shell: Docker version 29.5.3 and Docker Compose v5.1.4.
- Started NATS JetStream through `scripts/start_nats_jetstream.ps1`; NATS health returned `{"status":"ok"}` and container `systematic-trading-nats` is running.
- Created JetStream stream `ST_EVENTS` with subject `systematic_trading.events.v1.>`.
- Published smoke event `evt-nats-smoke-20260627-001` through `scripts/dispatch_event_outbox.py --publisher nats`; dispatcher result was `attempted=1`, `published=1`, `failed=0`.
- Verified SQLite outbox marked the event published with no pending records and JetStream stream state shows one message.
- Added the P2.4 Postgres transactional store design in `docs/postgres-transactional-store-design.md`.
- The design covers schema families for core, strategy, portfolio, execution, ops, and events; transaction boundaries; indexes; outbox locking; migration stages; and operational controls.
- Linked the Postgres design from `README.md` and `docs/data-contracts.md`.
- Full test suite passed after NATS smoke and script fix: 147 tests.
- Inspected local storage for market-data recording: D has 600.25 GB free, E has 308.15 GB free, and Z is a network drive at `\\WDMYCLOUDMIRROR\Public` with 1138.21 GB free.
- Added `config/market-data-storage.json` with a tiered policy: E hot spool, D local archive, Z asynchronous backup.
- Updated `docs/market-data-recorder-contract.md` to keep bulk market data outside the git repo and to enforce free-space watermarks before recorder implementation.
- Completed P2.5 SQLite-to-Postgres adapter boundary.
- Added protocol contracts in `systematic_trading.storage.interfaces` for watchlist, proposals, broker orders, market data, PnL, event append, outbox dispatch, and outbox replay.
- Added `systematic_trading.storage.create_transactional_store` and `ST_TRANSACTIONAL_STORE_BACKEND`; SQLite is the only implemented backend today and unsupported backends fail explicitly until the Postgres adapter is built.
- Routed FastAPI app composition and the event dispatch/replay scripts through the transactional store factory.
- Replaced production package type dependencies on `SQLiteStore` with storage protocols; direct SQLite imports remain only in the concrete storage package and local research/CLI scripts.
- Added `tests/test_storage_factory.py`.
- Full test suite passed: 151 tests.
- Validated local Postgres runtime for P2.8 after operator reported it installed and running.
- PostgreSQL service `postgresql-x64-18` is running with automatic startup; installer registry reports PostgreSQL `18.4-2`, base directory `C:\Program Files\PostgreSQL\18`, and data directory `C:\Program Files\PostgreSQL\18\data`.
- Port `5432` is listening on IPv4 and IPv6; `pg_isready -h 127.0.0.1 -p 5432` returned accepting connections.
- `psql` authenticated SQL check was blocked because no project password, `.env` DSN, or `pgpass.conf` is configured; next Postgres implementation work needs a project role/database/DSN before adapter or migration smoke tests.
- P2.8 remains blocked overall because ClickHouse is still pending.
- Ran authenticated Postgres role smoke after operator configured local project roles/database and supplied current-session credentials.
- `st_app`, `st_migrator`, and `st_readonly` all connect to database `systematic_trading`; timezone is UTC.
- Expected schemas exist: `core`, `strategy`, `portfolio`, `execution`, `ops`, and `events`.
- `st_migrator` can `SET ROLE st_owner` and create DDL inside a rolled-back transaction.
- `st_app` is correctly denied schema DDL.
- No project application tables are present yet; table creation should come from versioned migration tooling, not manual setup.
- Passwords were not written into repo files or durable logs.
- Completed P2.6 columnar store target design.
- Selected ClickHouse as the serving analytical store, Parquet as the immutable archive/interchange layer, and DuckDB as the local/offline Parquet research reader.
- Added `docs/columnar-store-target-design.md`, `config/columnar-store.json`, `deploy/clickhouse/docker-compose.yml`, `scripts/start_clickhouse.ps1`, `scripts/stop_clickhouse.ps1`, and `scripts/smoke_clickhouse_columnar_store.ps1`.
- Linked the columnar target from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, `docs/industrial-platform-plan.md`, and `docs/service-supervisor.md`.
- Added ClickHouse to `config/service-manifest.json` as the planned local columnar store service.
- Focused verification passed: JSON validation for `config/service-manifest.json` and `config/columnar-store.json`; `pytest tests/test_service_manifest.py tests/test_operator_scripts.py`; `git diff --check`.
- Attempted ClickHouse data storage on `E:/systematic_trading_runtime/clickhouse/data`; health and table creation worked, but MergeTree inserts failed because the Windows bind mount denied atomic part renames.
- Switched the local Windows ClickHouse runtime to Docker volume `clickhouse_clickhouse_data` for `/var/lib/clickhouse`; ClickHouse logs remain on `D:/systematic_trading_data/clickhouse/logs`.
- Completed P2.8 external service runtime smoke: NATS JetStream container is running and healthy, Postgres `pg_isready` reports `127.0.0.1:5432` accepting connections, and ClickHouse container `systematic-trading-clickhouse` is healthy.
- ClickHouse smoke passed through `scripts/smoke_clickhouse_columnar_store.ps1`: created a MergeTree smoke table, inserted one row, and queried `smoke_rows=1`.
- Keep the durable market-data lake on D with async Z backup; ClickHouse is a rebuildable serving store until server/native-disk deployment is validated.
- Completed P2.7 schema registry convention.
- Added `systematic_trading.schemas` as the code-based schema registry for the current single-repo phase.
- Registered current platform event schemas and core data schemas with stable schema ids, owners, statuses, JSON Schema export, and compatibility modes.
- Event schemas remain strict by default because current event models reject extra fields; core data schemas start with backward compatibility.
- Added compatibility checks for Pydantic models and JSON Schema snapshots; optional additions can be backward-compatible, while required additions, field removals, and type changes are flagged.
- Added `docs/schema-registry-convention.md` and linked it from `README.md`, `docs/data-contracts.md`, `docs/architecture.md`, and `docs/industrial-platform-plan.md`.
- Focused verification passed: `pytest tests/test_schema_registry.py tests/test_events.py tests/test_event_replay.py tests/test_nats_publisher.py`; `git diff --check`.
- P2 Service Foundation is now complete on the Kanban; next recommended work starts P3.2 IB paper market-data recorder v0.
- Completed P3.2a recorder source and capacity spec before implementing the IB recorder.
- Added `docs/market-data-recorder-source-plan.md` to define two recorder lanes: a low-frequency daily reference recorder and an intraday IB recorder.
- Documented IBKR capacity assumptions for P3.2: default 100 market-data lines, reserve 20 lines, record 5-second real-time bars for the 40-symbol ETF seed, keep top-of-book optional, keep tick-by-tick to a 3-symbol default canary set with hard cap 5, and keep Level 2 out of scope.
- Added `config/market-data-recorder-sources.json` as the machine-readable lane, pacing, ETF seed, and secondary-source policy.
- Secondary intraday candidates for later validation are IB delayed mode, Alpaca, Alpha Vantage Premium, Massive/Polygon, and Wind intraday if local entitlement/storage rights allow it.
- Verification passed: `python -m json.tool config\market-data-recorder-sources.json`, 40 unique seed symbols, and `git diff --check`.
- Started and completed P3.2 IB paper market-data recorder v0 after the operator logged into IB TWS paper and enabled the API.
- Added `systematic_trading.recorders` with raw JSONL envelope writing, deterministic raw/event ids, source-policy capacity validation, token-bucket pacing, recorder state-file updates, and raw replay dry-run validation.
- Added `scripts/record_ib_market_data.py` for IB realtime recording and bounded `historical-smoke` tests, plus `scripts/replay_market_data_raw.py` for one-symbol/day raw validation.
- Updated the service manifest so `market_data_recorder` is an implemented optional worker with state-file health, PID path, and manual startup command.
- Smoke-tested the running IB TWS paper connection: `scripts/test_ib_paper_connection.py --timeout-seconds 15` connected to `127.0.0.1:7497` and received `nextValidId=1`.
- Ran a bounded SPY historical-smoke request ending at the 2026-06-26 US market close: wrote 3 raw 5-second bar records under `E:/systematic_trading_runtime/market-data/hot/...`, appended 3 `market_data.recorded` events to `var/systematic_trading.db`, and wrote `var/run/market_data_recorder.state.json`.
- Raw replay dry-run for `SPY` on recorder partition date `2026-06-27` read 3 records, validated 3 records, and found 0 payload-hash mismatches.
- Verification passed: focused recorder/service/event tests, full test suite `162 passed in 172.62s`, JSON validation for recorder and service config, and `git diff --check`.
- Started and completed P3.3 raw data catalog.
- Added append-only raw manifest entries under `<root>/raw/_manifest/date=<YYYY-MM-DD>.jsonl` with source, environment, data kind, symbol, recorder date, raw schema version, raw ref, byte offset, byte count, payload hash, timestamps, capture mode, request id, and quality flags.
- Recorder write order is now raw JSONL first, raw catalog entry second, and `market_data.recorded` outbox event third.
- Added query and rebuild helpers in `systematic_trading.recorders.market_data` and `scripts/catalog_market_data_raw.py` for operator-level discovery and manifest recovery from existing raw partitions.
- Rebuilt and queried the existing IB SPY smoke data in the E hot spool: 3 catalog entries, 0 invalid records, 0 duplicate raw refs; query filters covered source `interactive-brokers`, environment `paper`, data kind `bar`, date `2026-06-27`, symbol `SPY`, and raw schema version 1.
- Verification passed: focused recorder/service/event suite `38 passed`, full test suite `163 passed in 173.86s`, JSON validation for service/recorder/storage configs, and `git diff --check`.

### 2026-09-25 IB Gateway cutover and engine assessment

Moved this PC's shared paper broker profile to Gateway 127.0.0.1:4002 (live port configured as 4001 but live remains disabled). Coordinated platform stop/start preserved NAS ownership/backup handling. Order connection, execution sync, account snapshots, health and reconciliation use distinct clients on the same login; paper reconciliation matched, with no order submitted. Local external D: storage policy now feeds recorder/catalog/replay CLIs consistently; explicit CLI overrides still work. Fixed IB warning 2176 prematurely ending capture: retain warning, mark affected bars ib_fractional_volume_rounded, and preserve fatal handling for other request failures and delayed-data labels. Historical canary: 60 bars/five symbols; corrected 45-second delayed stream: 16 new bars/five symbols. SPY replay: 16 valid, zero hash mismatches/duplicates. Dashboard audit exposes the new raw bars. Tests: 365 passed, 1 skipped; existing two deprecation warnings.

Documented operation and official-source engine assessment. Decision: retain control plane/approval/audit/reconciliation and evaluate LEAN first in a frozen-data backtest pilot for monthly ETFs; no engine installed or migrated. Nautilus remains a candidate for future intraday execution requirements. Next: check Gateway Read-Only API before first approved paper order; session/restart soak; official API compatibility upgrade; implement raw NAS backup separately. EOD September 24 remains incomplete because USD/CNH is latest September 23; slow serial EOD work temporarily staled the loop heartbeat, which recovered with fresh matched reconciliation. Do not weaken data freshness checks or claim continuous/order-path validation from connectivity alone.


### 2026-09-25 Gateway trading operations workspace

Deployed a redesigned `/operator` with a broker order blotter, working/attention/history filters, order review dialogs, audit details and IB positions/native cash. Visible pages poll Gateway order snapshots every 15 seconds; portfolio sync still uses persisted account snapshots and reconciliation without resetting the PnL baseline. Added paper-only same-client cancel, plain-limit amendments within approved exposure/price, and zero-fill confirmed-cancellation resubmission. Operator/reason and an exact review token are recorded. Atomic DB claims survive crashes/timeouts; concurrent fills are preserved; both normal routing and reservations block nonzero or unknown broker fill evidence before execution sync. The installed IB API completed-order callback omits API order/client IDs, so completed histories require a previously observed permanent ID. External/unlinked orders remain view-only. Unchanged executions are not republished as new fill events during lifecycle updates. Resubmission retains the same local identity and prior-attempt audit.

Validation: final full suite 406 passed, 1 skipped in 170.91s with disposable PostgreSQL; existing two deprecation warnings. Synthetic browser amendment flow and desktop/mobile layout checks passed with no console errors. Real Gateway snapshot and portfolio sync succeeded: zero current broker orders/positions and matched reconciliation. Kept 238 historical local records, including ten with unconfirmed terminal status; no invented cancellations or historical rewrites. Restarted only dashboard/dispatcher, preserving running recorder and NAS backup ownership. No real broker placement, amendment or cancellation performed. Next: review a fresh small paper proposal and perform supervised submit/amend/cancel/resubmit checks. Amend currently supports plain limits; algorithm changes/new exposure require a new proposal. Restart/reconnect soak and unresolved-action recovery remain follow-ups. Operating guide: docs/trading-operations.md.

### 2026-09-25 initial allocation and portfolio drift maintenance

Implemented the user's empty-portfolio TWAP trigger and subsequent instruction to monitor IB holdings against strategy targets. User explicitly chose 2 percentage points per holding. The management loop now evaluates portfolio alignment independently of the month-end queue. An empty, verified, freshly reconciled single paper account can stage an initial allocation. Existing holdings are valued using completed daily prices and same-date FX; a threshold breach stages a portfolio TWAP rebalance. Target weights come from an approved proposal in the current monthly period or a point-in-time reconstruction of the latest scheduled month-end targets. Proposal metadata preserves trigger, target date and source proposal. Monthly signals remain unchanged, and monthly staging waits for unexpired alignment proposals.

Fresh broker open-order snapshots and local pending/uncertain states block duplicates. Historical records covered by a reconciled baseline are retained without falsely cancelling them. Deterministic account/target/position/execution episodes plus atomic SQLite/Postgres insert-once prevent restarts and competing workers from overwriting approvals or repeatedly creating the same proposal. Rejections pause unchanged attempts; expired windows cannot be reused. TWAP uses the configured duration, regular/early-close calendars and a short intraday review lead, or the next session. No approval, route, environment or reconciliation checks were weakened; the service only stages pending proposals. The operator page displays target/actual weights, drift, valuation dates and readiness blockers. Initial intraday and drift turnover are separately tagged paper execution policies, not validated additions to the existing monthly backtest benchmark.

Validation: 451 passed, 1 skipped in the full suite (disposable PostgreSQL enabled); final affected service/allocation checks 54 passed and the added monthly-conflict/UI checks 2 passed. Two existing dependency deprecation warnings remain. Restarted dashboard (PID 37504) and dispatcher (PID 10036); recorder and NAS ownership retained. Runtime API confirms running, threshold 0.02 and matched IB reconciliation. Observed readiness blocker: September 24 FX required; USD/CNH latest September 23, HKD/CNH latest April 29. The current EOD refresh covers USD only; cash-currency FX needs repair, and its existing CNY proxy semantics warrant correction rather than fabricating CNH rates. No stale-rate carry-forward, broker order placement, amendment or cancellation was performed. Next: restore verified observed FX coverage, then review the generated pending allocation and conduct supervised paper execution/cost checks.


### 2026-09-25 SQLite retirement, D: storage and LEAN plan

User requested D: database storage, SQLite retirement and a LEAN backtest plan; explicitly selected retaining ClickHouse analytics. SQLite was already on D:, PostgreSQL service data was on C:, and ClickHouse/NATS were in Docker's C: WSL disk. All legacy operational instrument/proposal/order/P&L identities and approval payloads already exist in the newer PostgreSQL ledger. Preserved every SQLite row (145,836 across 12 tables including sequence metadata) in PostgreSQL legacy.sqlite_snapshots/sqlite_rows using consistent source reads, one destination transaction and exact readback. No stale ledger overwrite or historical outbox republish. Snapshot a7235fb109d493339812617b3d9895929fc053258b61ec3af28433716506f7c7. All 140,686 legacy bar and 3,790 FX keys exist in ClickHouse; coverage does not certify unchanged values or historical availability.

Default configuration, 13 research/backfill scripts including multiprocessing workers, and reporting now use configured PostgreSQL/ClickHouse stores. Explicit SQLite test/recovery support remains. Different SQLite path overrides cannot silently redirect PostgreSQL. Protected golden CNH data from legacy CNY proxy fetchers; first-backtest consumes stored data. Old bootstrap refuses nonempty ledgers. Retain original SQLite as recovery/NAS-layout artifact; removal from two-PC backups needs a coordinated version transition, not disabling ownership checks.

Completed standard platform stop/final NAS snapshot, stopped ClickHouse/NATS, and preserved complete tar backups with hashes on D: (initial directory extraction could not create Linux symlinks under the non-elevated token; use tar archives, not that partial folder). Docker Desktop's supported disk move relocated both WSL disks to D:/systematic_trading_data/docker/DockerDesktopWSL. C: docker_data.vhdx is absent. Standard startup restored operator PID 17688, dispatcher 16724 and recorder 30488; NAS ownership reacquired. All eight health services report ok; fresh IB reconciliation matched with no execution issues. Post-move coverage: 141,620 bar keys and 3,857 FX keys across the legacy universe; PostgreSQL archive reverified. Read-only 2025 SPY/TLT/GLD smoke produced 250 NAV points/eight research proposals; no broker commands.

PostgreSQL physical relocation remains BLOCKED by Windows service-control error 5 (Access denied); postmaster.pid confirms C:/Program Files/PostgreSQL/18/data. Prepared scripts/move_postgres_data_to_d.ps1 for elevated PowerShell: guarded paths/config, clean NAS stop, stopped-service ACL-preserving copy/SHA-256 checks, service retarget, PID/data-path check, pre-start rollback and normal guarded startup. Syntax checked; actual admin execution outstanding. Original copy is retained and cannot be selected again after new D: writes.

LEAN plan defines an isolated pinned backtest worker, frozen point-in-time bundles, target replay then shared strategy adapter, CNH/corporate-action/execution parity, runtime benchmarks and promotion evidence registry. L1/L2 contracts/exporter are next; no engine installation or routing change. Official-source references and CLI licensing caveat are in the plan. Validation: full suite 525 passed/1 skipped, two existing deprecations; final affected checks 21 passed, Python compilation, PowerShell parsing and diff checks. Evidence: var/migration/, D:/systematic_trading_data/backups/20260925-pre-docker-move/, docs/database-consolidation.md and docs/lean-backtest-integration-plan.md. Next: elevated PostgreSQL relocation/verification, coordinated NAS archival-layout cleanup, then LEAN L1/L2.


### 2026-09-25 elevated relocation NAS failure and recovery

User's administrator relocation stopped recorder/dashboard/dispatcher but failed final NAS handoff. PostgreSQL still runs from C:/Program Files/PostgreSQL/18/data; no move occurred. Normal-session UNC access is healthy and NAS owner/head match local active state (head 50370ace0ebe4a14a1b4af12ccf1ba65 at diagnosis). Suspect elevated SMB session access; transient outage cannot be excluded without an elevated-session test. Restored via standard guarded startup; all eight services healthy, paper reconciliation matched/no execution issues. Added NasSync.preflight and CLI action plus elevated-script invocation before any service stop. Tests cover active/clean identity preservation, competing ownership and unavailable shares; NAS/operator suite 20 passed, 1 optional SMB skip. Real normal-session preflight, PowerShell parsing and diff checks passed. Next: connect the NAS from the user's Administrator PowerShell, pass preflight, rerun relocation. Retain ownership and final-backup safeguards; no credential/security settings changed and no broker commands issued.


### 2026-09-26 PostgreSQL service-command quoting repair

User's elevated run completed final NAS handoff, stopped PostgreSQL and copied/verified 1,386 files (232.36 MB), but sc.exe printed usage and rejected service reconfiguration. Source service recovered on C:. Replaced sc.exe calls with structured Invoke-CimMethod Win32_Service.Change PathName arguments, return-code validation and exact readback. Rollback is armed before the method call so accepted changes followed by readback failure also restore the old command. Helper tests execute under actual Windows PowerShell 5.1 and PowerShell 7 with mocked service APIs; forward/rollback quote preservation, error return and readback mismatch pass. Combined operator test run: 3 passed; actual elevated service mutation remains for operator retry.

Verified original C: running and D: copy shut down with identical system identifier 7687613963351431084 and no D: postmaster.pid. Preserved the prior copy via explicitly bounded rename to D:/systematic_trading_data/postgresql/18/data.failed-sc-20260926; retry target is absent. Standard guarded platform startup resumed services and NAS ownership. Required services healthy and paper reconciliation matched; optional recorder separately reports IB 10197 competing market-data session, not a storage error. No broker commands or security/credential changes. Next: rerun move_postgres_data_to_d.ps1 from the same NAS-connected Administrator PowerShell and verify actual D: service/data path; preserve both source/failed copies until post-move validation.

### 2026-09-28 shared application connection repairs

User authorized implementation of all seventeen findings in docs/app-connection-audit-2026-09-27.md. Added a versioned shared portfolio episode derived from the existing reset (September 25 New York, exact cutoff 2026-09-25T03:59:59.999999Z); baseline d229466e93af and original evidence preserved. Monitoring, missed sessions, execution slices, paired actual/reference accounting, historical checkpoint eligibility, EOD financial revisions, approved target selection and account opening anchors now follow shared contracts. Current captures cannot be backdated into historical catch-up. Missing/stale marks and FX remain incomplete.

Production decisions consume hash-pinned published audited inputs with adjusted signal/raw execution bases and full decision receipts. The app owns acquisition, audit, verified publication and bounded retry for the tracked ETF universe plus URTH; failed evidence is quarantined, other histories remain pinned, historical availability and legacy FX limitations remain disclosed. Research and operations workers are independent. Shared shell covers all workspaces/reports; System includes recurring broker probes, calculation freshness/errors and durable email delivery receipts. NAS manifests verify external analytical/model/input prerequisites before incoming restore or ownership changes; SQL backups do not claim to include ClickHouse/artifact copies.

Added signed source-referenced economic cash events and NAV bridge, with idempotent account/environment/episode validation and Modified Dietz returns withheld until reconciled. Runtime: 6 filled orders, 48 execution slices, zero current-period misses; security P&L CNH 977.08 vs reference 1,960.12, difference -983.04/-11.57 bps. Exact opening NAV 871,873.70, closing 873,375.41; cash FX 617.61; residual -92.98 explicitly unresolved. Do not infer fees or manufacture cash events to force agreement. Source statement evidence is the next accounting requirement.

Validation: final full suite 702 passed / 51 optional integrations skipped; focused 84 passed / 3 skips and edge 45 passed / 1 skip; whole-project Ruff clean. Browser verified common desktop navigation/reports, current portfolio scope, economic panel, expanded service map and compact layout without horizontal overflow. Guarded dashboard/dispatcher and backup-worker restart; eight required services healthy, SMTP explicitly disabled due missing host/recipient. New NAS generation 2b0c1b76a1f84600a36e7b023591ca6a contains the dependency receipt (4,667 files, one governed root, 19,946 publication versions). No additional portfolio reset, trading-policy change, new order/cash event, live enablement or ownership bypass. Existing uncommitted work preserved; no commit/push requested. Guide: docs/app-connection-repairs-2026-09-28.md; test/runtime/backup receipts: var/research/app-connections-*.

Next evidence: reconcile broker statement flows/income/costs; configure email if desired; perform a full second-machine restore drill with separately preserved analytical prerequisites before claiming disaster-recovery readiness.

### 2026-09-28 calculation parallelism and final acceptance

User asked whether calculations use all cores and requested using as many as practical. Verified 16 available host/Docker logical CPUs, 32 GiB host RAM and 15.39 GiB Docker memory. Monthly XGBoost fits already used 16 independent processes with the versioned n_jobs=1 estimator; retained that recipe. Found serial historical decision preparation and serial two-core native backtests. Added isolated, credential-stripped preparation subprocesses on pinned inputs (five parallel jobs here), plus a resource-aware native pool (three simultaneous runs, five CPUs/4 GiB each). Parent thread alone registers results and atomically publishes the full set; numerical thread caps prevent nested oversubscription. CPU/memory plan and phase counters are exposed through analytics status and retained in receipts. Sequential/I/O phases may use fewer than all CPUs.

Before this change, repeated deployment restarts left a risk-parity run marked running after its owner exited. Confirmed no matching process/container, preserved the immutable directory as risk_parity.interrupted-20260928, and retried the identical manifest successfully. Receipt: var/research/app-connections-recovery-receipt.json. Intermediate development outputs remain evidence; no incomplete calculation was published. The previous complete report and independent operations continued serving during retries.

Final application revision 4ad0f8ac9939ea9dd2766abf5b38e98beed647c8579234e24875af7e05e95b2b published all five strategies/benchmarks after native parity. Preparation 39.13 seconds; parallel backtest phase 153.74 seconds; summed individual native run elapsed time 370.88 seconds. Every economic output matches the prior serial run. Final combined regression suite: 708 passed / 51 optional skips, including real isolated-preparation parity, concurrent overlap, resource constraints and credential exclusion; Ruff/diff checks clean. Eight required services healthy, operations fresh, current portfolio still September 25 / 6 orders / 48 fills / zero misses. Runtime residual -92.98 CNH remains explicitly unresolved; email disabled pending configuration. No additional reset, strategy recipe/promotion, broker order, cash event or execution-policy change. Guides: docs/app-calculation-resources.md and docs/app-connection-repairs-2026-09-28.md. Receipts: var/research/parallel-calculation-acceptance.json, app-connections-and-parallel-final.xml, app-connections-runtime-final.json. All changes remain local and uncommitted.

### 2026-09-28 source commit and push authorization

User requested committing and pushing the completed work. Reviewed the pending source set and included the existing rolling-model tracking implementation/configuration/tests required by the repaired application, together with its reproducible research scripts and documentation. Staged 80 text files across source, tests, configuration, scripts and docs. Excluded all generated var artifacts and the changing broker reconciliation snapshot. Confirmed origin/master matched the starting commit ae9ef2c. Final full-suite evidence remains 708 passed / 51 optional skips and five successful native runs with matching prior economics; changed Python/JSON syntax, whole-project/script Ruff and staged whitespace checks passed. Prepared publication through the configured origin/master with the existing Git author identity; paper/live policy and running services unchanged.

### 2026-09-28 rebalance visibility and PnL attribution repair

User reported an empty approval queue despite automatic approval, excessive performance warning text and missing PnL attribution after initial allocation. Read the live application and durable strategy/account state. Automatic paper approval remains enabled and waiting for a new eligible proposal. Portfolio is aligned on September 25 marks: maximum absolute holding drift about 0.28 percentage points, below the 2pp trigger. No monthly rebalance is due September 28; the registered monthly decision is September 30 close for October 1 execution. These dates and the alignment reason now appear beside the proposal queue. The current portfolio has six filled orders, 48 execution slices and zero missed orders.

Root causes: default daily accounting requested the current New York date before its close/marks existed; the UI discarded valid history and observed slippage whenever current valuation was incomplete; the chart requested only one snapshot and drew no point for a single observation. GET PnL and attribution now default to the latest completed US session under the existing holiday/early-close calendar. Explicit dates retain strict marks/FX checks, and incomplete attribution totals are null. Historical attribution and execution slippage remain visible with dated fallback labels. The chart loads up to 100 snapshots and draws both series' first points. No stale data was relabelled as a current valuation. Current September 25 daily attribution: CNH 977.08 actual security PnL, 1,960.12 reference-fill PnL, -983.04 difference / -11.57bps. Live broker PnL remains separately streamed; fees and unresolved economic cash events retain their existing limitations.

Performance notes are collapsed in a scrollable disclosure. The 706 backdated account captures remain excluded, with one count and three example filenames replacing repeated messages; original snapshots remain audit evidence. Existing complete publications containing old messages are also compacted at rendering. Research/data caveats are retained.

Validation: 65 display/API/calendar/connection tests and 56 accounting/approval/execution tests passed; one optional integration skipped. Final nine UI tests passed after the single-point chart fix, Ruff and diff checks clean. Guarded dashboard/dispatcher restart deployed the changes. Browser verified restored totals/two chart dots, collapsed and expanded bounded diagnostics, enabled automatic approval, and no console errors or horizontal overflow. Live APIs show complete September 25 valuations and unchanged approval policy bytes. A pre-existing IB account-snapshot client 141 timeout had opened the automation circuit; its scheduled retry at 13:32:48 UTC succeeded, cleared the circuit/errors and reconciled the portfolio. No broker order, portfolio reset, strategy promotion or live enablement was performed. Changes remain uncommitted. Evidence: var/research/rebalance-attribution-tests.xml, rebalance-accounting-tests.xml and rebalance-attribution-runtime.json. Guide: docs/dashboard-performance.md.

### 2026-09-30 optional NAS and daily strategy refresh repair

User requested normal laptop operation without NAS and repair of stale monitored/active strategies. Added optional local-first PostgreSQL/SQLite checkpoints and latest-observed-revision synchronization. UTC revision advances only when the logical fingerprint changes; unchanged backups cannot win by copying an old generation. Cross-PC publication lock, local OS lock, hashes/layout/path/dependency verification and pre-restore rollback remain. Incoming newer data waits for stopped services; partial multi-database restore still blocks local startup. Retain two local checkpoints and explicit rollback copies; NAS generations remain immutable. Legacy owner metadata no longer gates optional mode. Latest snapshots are whole-generation selection, not a row merge or a guarantee for simultaneous disconnected trading. Documented observed-timestamp/clock limitations and upgrade both-PC requirement.

Actual start, stop with KeepInfrastructure, and restart all succeeded while NAS SMB was unreachable. The app, dispatcher and recorder are running. Periodic backup retains local checkpoints and reports local_only with its error, retrying on the configured interval. Updated dashboard startup and PostgreSQL relocation checks to use local integrity rather than NAS availability. No PostgreSQL service relocation performed.

Diagnosed repeated Yahoo HTTP 403, unavailable IB clients/FX and stale prices through September 25. Added bounded transport retry across Yahoo's two chart hosts, five-minute governed retry, independent evidence-first USD/CNH catch-up before tracked calculations, and latest-session acquisition while older EOD accounting is blocked. Preserved audited publication, revision/identity/coverage checks, raw evidence, monthly strategy timing and execution gates. Strategy/catalog/System responses expose expected date, price date, NAV date and stale state even when workers are alive; job errors surface immediately. IB health now treats 1100/2110 server loss as unavailable despite a successful local handshake, respecting subsequent 1101/1102 restoration messages.

Application published audited batch 320fb6bb9b37ac9885677affb6563daaffb9f292425318557303e375d655739d through September 29. Native revision 7a33fc372d7649928cb03150bd04454f2166cd7938ebab344396e24ad2e5c63a completed five runs with all parity checks passing; all three monitored strategies expose indicative targets known through September 29 and next rebalance October 1. Trading daily bars also advanced to September 29. CNH NAV and held weights remain September 25 because direct observed USD/CNH evidence for September 28–29 is unavailable. At acceptance Gateway's socket responds but it reports 2110 and disconnected data farms; account reconciliation and routing remain blocked. Asked the user to reconnect paper Gateway. The app automatically retries after recovery; no synthetic FX, historical account captures, forced approvals or routing bypasses were introduced. Existing paper policy remains byte-identical, SHA-256 71cb2afeb61d9418122d6c87b18ec3ac4f9d22dc5d982a7544d93f7498d7a513. Existing unrelated local edits were preserved.

Validation: full suite 731 passed / 51 optional skips; final affected checks 40 passed / one optional skip; final extra checks 28 passed / one skip; real isolated PostgreSQL (both strict and optional restore/rollback) plus NAS regressions 26 passed / one external SMB skip. Whole-project Ruff, PowerShell parsing and real offline lifecycle passed. Runtime source verification showed a temporary lean-history import timeout recovered on the app retry; only strategy-fx remained failed at final inspection. Evidence: var/research/optional-nas-daily-refresh-tests.xml, optional-nas-postgres-tests.xml, optional-nas-daily-refresh-final-focused.xml, optional-nas-daily-refresh-final-extra.xml and optional-nas-daily-refresh-runtime.json. Guides: docs/database-sync.md, docs/live-rollout.md. Remaining operational work: reconnect Gateway, verify observed FX catch-up/new complete CNH publications and fresh reconciliation; monthly September 30 decision/October 1 execution and 2pp drift policy remain unchanged. No commit or push requested.

### 2026-09-30 Gateway recovery and complete strategy catch-up

User reconnected Gateway and reported artifacts still stuck at September 25. Read-only probe confirmed healthy IB farms. The app received missing observed September 28–29 USD/CNH at 14:35:26 UTC and began native revision 9b1bb2dd8b5078d432e59139e4135efac6c1dc8cf27fbe9d5e84c9a2e16a626f at 14:35:30. Five runs finished by 14:38:26; all passed parity. Prices, NAV, held weights and latest indicative targets now reach September 29 for all three monitored strategies. Existing reports stayed open on old publications, the previous FX timeout remained visible until unrelated history imports finished, and the trading connection circuit still imposed its old cooldown after recovery.

Added a health transition callback (including initial healthy startup) to queue the analytical worker and wake normal trading reconciliation/data retries. Fresh observed recovery can clear the connection cooldown once; stale/future probes and probes predating a newer IB failure cannot. Recovery does not mark reconciliation matched or grant approval/routing authority. The normal broker environment, reconciliation, approval and execution-window checks remain. Successful dependency jobs now remove their old errors immediately, and status exposes the complete serving publication version. Saved reports poll progress and reload on a newer complete publication; the strategy catalog polls without resetting its lifecycle filter or discarding usable rows on temporary failure.

Deployed dashboard PID 33400 and dispatcher PID 34332 after native calculations completed. The app's healthy startup probe queued recovery at 14:44:52 UTC; fresh reconciliation matched and normal accounting replay completed September 28 and 29 by 14:45:20, leaving no pending dates or IB circuit/error. Runtime APIs confirmed all three complete artifacts and NAV series end September 29. Current holdings remain within the 2pp drift policy; monthly decision September 30 close and execution October 1 are unchanged. Paper approval policy SHA-256 remains 71cb2afeb61d9418122d6c87b18ec3ac4f9d22dc5d982a7544d93f7498d7a513. No manual order, reset, synthetic FX, promotion or live enablement performed.

Validation: 59 regression checks passed with one optional integration skip, including real JavaScript polling/recovery behavior, health transition wiring and stale/newer-failure cooldown guards. Whole-project Ruff passed. Runtime assertions verified observed catch-up, all five native success/parity receipts, all monitored report dates/valuation/target dates, fresh matched reconciliation, empty EOD backlog and unchanged approval policy. Evidence: var/research/gateway-reconnect-unit.xml, gateway-reconnect-regression.xml and gateway-reconnect-catchup-runtime.json. Guide: docs/live-rollout.md. Source changes remain local; no commit or push requested.

### 2026-09-30 self-healing and self-calculating robustness review

User requested a broader code/connection review and implemented recovery improvements after repeated stale-strategy incidents. Applied the system-robustness-review playbook across lifecycle, input ingestion, calculation, publication, broker/account state, queue delivery, recorder, checkpoints and health. Preserved all prior uncommitted work. The review and risk register are in docs/robustness-review-2026-09-30.md.

Reproduced fatal trading-worker exceptions, lost broker-health recovery callbacks, immutable failed/running receipts poisoning retries, partial preparation directories, non-atomic state writes, incorrect Windows exited-process detection, stale backup PID startup, unbounded NATS/recorder operations, six-hour failed daily backfill retry, FX evidence saved before a failed normalized-store write and watchdog HTTP-200 false readiness. Added bounded iteration recovery; atomic state/receipt writes; locked separate native attempts with backoff and hash verification; atomic bundle staging; correct Windows process exit checks; crash-released backup-worker locking; timed event delivery with stable deduplication IDs; bounded acquisition child trees and five-minute failure retry; evidence-to-store reconciliation; and embedded-worker readiness checks. Integrity/parity failures remain blocked with the last complete publication retained.

Added a local recovery process, started/stopped with the platform, to restore missing desired NATS, ClickHouse, operator/dispatcher, recorder and backup services using their existing guarded commands. Persisted profile retains startup settings, retries back off to 15 minutes, low disk space prevents unsafe restart attempts, and lifecycle control serializes explicit stops with in-flight starts. Normal service starts pause competing recovery during startup and resume afterward. It never grants trading authority, resets a database, replaces an active database from NAS, logs in to IB or kills an unrelated live process. No Codex automation or Windows scheduled task was created.

Real deployment completed offline NAS shutdown/startup successfully. Recovery PID 9912 observed all desired services. Deliberately terminated only the verified event dispatcher; recovery restarted it while API PID 17568 stayed unchanged and native calculations continued. An isolated temporary NATS stream confirmed two identical event-ID publishes produced one stored message, then was removed. Native run st-lean-735312e23dc8 stalled; deliberately killed only that network-isolated research container to exercise failure recovery. The app preserved its failed receipt, reused the other four successful runs and automatically retried the missing run into a separate attempt. All five parity checks passed and every economic hash equals the prior September 29 results. Complete revision db180b3312c8906fae94d0101656cbd7b8190206e05a08085573a9d759056652 published; retry backtests took 69.06 seconds. No manual artifact rename, fabricated inputs or incomplete publication was used.

That drill also exposed archive-import latency delaying research retries. Moved historical/raw archive imports to a third analytical worker with independent status, leaving strategy and account refreshes independent; a blocked-archive concurrency test verified both still complete. Deployed that final change after calculations finished: API PID 20088 and dispatcher PID 14044. Runtime acceptance found all required services healthy, three monitored strategies and account EOD current through September 29, no EOD backlog, fresh matched reconciliation and active independent research/account/archive workers. Verified the current local PostgreSQL/SQLite checkpoint file hashes. Paper policy SHA-256 remains 71cb2afeb61d9418122d6c87b18ec3ac4f9d22dc5d982a7544d93f7498d7a513; monthly schedule, approval, reconciliation, broker environment and live-disabled controls unchanged.

Validation: full suite 759 passed / 52 optional integration skips; subsequent recorder/lifecycle checks 46 passed, data recovery checks 40 passed, archive/application regressions 48 passed / one optional skip, final lifecycle/readiness checks 15 passed. Whole-project Ruff, diff checks and PowerShell parsing passed. Receipts: var/research/self-healing-full-suite.xml, self-healing-recovery-tests.xml, self-healing-final-extra.xml, self-healing-data-recovery.xml, self-healing-archive-isolation.xml, self-healing-final-lifecycle.xml, self-healing-dispatcher-drill.json, self-healing-native-drill.json, self-healing-nats-dedupe.json and self-healing-runtime.json.

Remaining operator/data-owner conditions: email host/recipient are not configured, so external alert delivery remains explicitly disabled; NAS remains unreachable and optional; full second-machine ClickHouse/raw/governed restore is not yet proven; Gateway login/2FA, exceptional closures/clock issues, historical input limitations and broker cash-event evidence remain external dependencies. Known work is bounded and retryable, but an unexplained live-process deadlock or OS/Postgres failure is reported rather than forcibly reset. The local supervisor itself starts with the platform and cannot run while the laptop is asleep/off. These limits prevent a fully unattended/live-readiness claim. No new broker order, portfolio reset, strategy promotion, live enablement, email, commit or push was performed.

### 2026-10-01 source commit and push authorization

User requested committing and pushing the completed work. Reviewed the pending optional NAS, daily calculation/FX ingestion, Gateway recovery, worker/service recovery and dashboard attribution changes, together with their regression tests, configuration, scripts and documentation. Generated var artifacts and the changing broker reconciliation snapshot are excluded from publication and retained locally. Existing validation includes the 759-pass / 52-skip full suite, subsequent targeted checks and real recovery drills recorded above; whole-project Ruff and whitespace checks passed again before staging. Publication uses the configured origin/master and existing Git identity. No running service, database, strategy or trading policy is changed by this publication session.

### 2026-10-01 momentum literature collection and initial review

User supplied three momentum reports and clarified that cited original papers should be collected and read before proposing research. Preserved the originals. Acquired and verified 45 PDFs in research/references: 42 identifiable academic papers, the cited 浙商证券 framework report and two governance documents. The cited 中银国际 and 国金证券 reports remain inaccessible from located sources. Unnamed international/Japan/earnings studies and an unspecified Romano–Wolf citation remain unresolved. An eight-page morning briefing that mentioned the 中银国际 report was identified as the wrong document, moved to references/excluded and excluded from the count. Manifest records source URLs, attempts, retrieval times, full SHA-256 hashes, page counts, identity checks and working-paper versus publication versions.

Read the three supplied reports and completed an initial firsthand pass through substantive selected sections of each acquired document; the notes list inspected PDF pages and explicitly do not claim full proof/appendix review or replication. Scanned Jegadeesh (1990) and De Bondt–Thaler (1985) needed OCR and visual title-page verification. The reading distinguishes recent-return exclusion, turnover control and portfolio risk scaling, and documents why stock long/short evidence cannot be assumed to transfer to twelve long-only ETFs. It also corrects the interpretation of the 1993 one-week skip, preserves Cederburg's momentum-specific exceptions, and rejects using wealth concentration as proof of optimal momentum breadth.

Created research/momentum-literature-notes-2026-10-01.md and research/momentum-research-plan-2026-10-01.md. The proposal specifies two standalone changes (21-session exclusion in pool momentum and a Top-6/retain-through-rank-8 buffer), each versus its unchanged monitored parent, with a six-comparison budget. It requires baseline parity, published audited histories with pinned hashes, explicit adjusted/raw price and volume contracts, missingness/identity checks, disclosure of uncertified legacy FX and historical-publication limits, paired inference, costs and a new prospective freeze. Thresholds and all experiments await user discussion; no new market-data inputs, strategy calculations, code/config changes, promotion, orders, service restarts, commits or pushes were performed. Validation was document/provenance inspection, PDF parse/size/hash checks, original-file hash checks and local-link checks; no behavior changed and no test suite was needed.

### 2026-10-01 momentum proposal revised after user discussion

User requested symmetric short-horizon (one/two-week) versus older momentum, dynamic short/long selection potentially conditioned on trend/skew, flexible holdings above six, and both fast-entry/slow-exit and slow-entry/fast-exit policies. User also wants predictive USD information for ETF allocation, accepts unhedged USD/CNH exposure, generally agrees with the remaining validation discipline and defers inaccessible broker reports/unnamed citations. This is continuing plan review, not authorization to run the experiments.

Revised the existing plan to v2. It defines eight static score recipes, four mirrored trend/skew mixtures, three variable-breadth timing policies and seven weekly counterparts, plus two matched USD-model recipes; proposed ceiling is 24 additional SOTA recipes before limited unchanged-rule transfer to the other parents. This supersedes the original six comparisons. It specifies recent/older window endpoints, treats trend and skew as distinct, separates signal horizon from trading frequency, and records cases where a six-position floor overrides delayed entry. Dynamic policies must face the same fixed S/L controls; USD must show predictive improvement against the same model without USD rather than contemporaneous correlation or CNH translation. No combination grid is implied. The exact comparison ledger and proposed constants remain for discussion.

Downloaded two further BIS papers with provenance and verified PDF hashes in research/references/supplemental; initial firsthand notes distinguish same-period capital-flow regressions from lagged return prediction and note changing commodity/dollar relationships. Fed documentation establishes the need to respect weekly release timing and revised index vintages. No dollar-index observations or other market data were fetched as research inputs. A clarification was requested because the prior 25 bp/year figure was a net-return hurdle but the user described it as trading cost; the draft separates annual cost allowance, per-trade costs and the unsettled return hurdle pending an answer.

Validation: local document links, original and supplemental PDF sizes/page counts/hashes, original report hashes and scoped whitespace checks. No behavior changed, so no test suite was run. No strategy/configuration edits, calculations, experiments, orders, promotion, service restarts, commits or pushes were performed.

### 2026-10-01 authorized momentum experiments and USD vintage data

The user authorized the revised research and requested all available cores, then asked for historical USD-index data. Froze 24 additional SOTA recipes, monthly/weekly parent controls, a 58-comparison family, cost scenarios, bootstrap rules and transfer selection before reviewing performance. Used the published ETF batch `7a5b3b7d442f3be171d73327a3d92769b7ae3510a45f76d872ecdb073fee7d57`, verified all input/model hashes and retained the parent feature basis. New code is isolated under research modules and scripts; production strategy definitions, execution safeguards and services remain unchanged.

Completed 102 Python replays across 34 portfolios and 5/10/20 bp per traded dollar. All 34 portfolios at 5 bp plus two 20 bp stress cases pass native LEAN parity (36 total). Monthly target weights exactly reproduce each of the three monitored parents for all 129 decisions. The explicit USD replay adapter uses USD cash and adjusted units; its shared proposal helper uses an internal unit conversion, not an observed FX rate. Native LEAN independently accounts in USD and matches cash/NAV to the cent and integer fills. Historical uncertified USD/CNH was excluded, so these results differ in accounting currency/scenario from the existing dashboard and no full historical CNH bridge is claimed.

Used 16 single-threaded Python process workers; the initial 26-portfolio batch took 67.2 seconds. Native checks used three 4 GiB containers with five CPUs each within the 15.4 GiB Docker VM, leaving the service reserve. Retained an initial preparation error, a native import failure and one native weekly-parent stall; the import was fixed without changing economics, and an identical-bundle retry passed. An early selection script wrongly excluded U0/U1 even after their data prerequisite was met; the prior empty selection and correction are retained. The original unchanged rule selected both USD models for descriptive transfers. No additional fitted parameters or comparison family were introduced by these engineering corrections.

Downloaded the Fed's revised broad-dollar daily history (5,410 dated rows, 212 missing values preserved) and 92 monthly ALFRED DTWEXBGS vintages. Audited series/vintage identity, ordered dates, availability cutoffs, positive levels, coverage, staleness and large jumps; verified analytical readback and published `governance/usd-broad-index`, batch `ddb5624ba023c71b9ca41ff0571318eb48f390ad4131ab20858d7eaafdae006b`. Each 21/63-observation change uses one vintage; no goods-only index splice or use of today's revisions as past information. Daily ALFRED archive availability is placed conservatively before the signal close; intraday dissemination remains uncertified. Provider-adjusted ETF histories retain their separately disclosed vintage limitations. Files and source URLs are in `research/usd-data/README.md`.

Monthly SOTA net USD CAGR is 9.17%; one/two-week pool momentum gives 4.17%/5.61%, older blend 6.95%. All four dynamic trend/skew gates trail the parent. The monthly C1/C2 membership rules reduce annual costs from 31.8 to 26.0/28.5 bp while reducing CAGR to 8.32%/8.41%. Weekly C2 has a small +6.5 bp/year paired improvement over its weekly parent, but does not pass the registered transfer/evidence gates. Up-trend/left-skew occurs in 42 monthly decisions versus 11 up-trend/right-skew: trend and skew are not interchangeable. The 25 bp/year number remains a proposed cost allowance, not a flat fee or settled economic-return hurdle.

With 60 completed training months, U0/U1 first become eligible in April 2024. USD-specific U1-minus-U0 adds 13.9 bp/year over 30 months; marginal six-month-block 95% interval [-11.4, 33.7] bp, Holm p=1 over the full 58-slot family. Descriptive activity/rolling-parent transfers show 13.1/14.2 bp increments. No candidate meets promotion requirements; retain the current strategies and discuss the USD hypothesis before any further combined/learned model or forward observation. No prospective performance is claimed.

Concrete risk finding: the inherited 45% setting limits base weights before pool reallocation, not final portfolio weights. Monthly parent held weight reached 54.68% (258 sessions above 45%); weekly reached 61.52%. Recorded a pending versioned final-weight risk-contract fix; no silent cap change or reinterpretation was applied to the comparisons. Parent activity remains a legacy adjusted-price/source-volume proxy, not raw traded-dollar activity or ETF flow.

Artifacts: `var/research/momentum-20261001-v1b`, `research/momentum-results-2026-10-01.md` and `research/momentum-experiments-2026-10-01/`. All signs, three block lengths, cost scenarios, pre/post-2023 splits, fixed stresses, regime counts, membership overrides, asset contributions and daily trade/NAV records are retained. Validation: 48 relevant tests passed and one PostgreSQL-dependent test skipped; all 36 native checks and fill-ledger reconciliations passed; charts visually inspected. Installed the already-declared optional matplotlib 3.10.8 dependency in the project venv to render the report. No orders, monitoring registration, strategy promotion, broker-policy edits, service restarts, commits or pushes.

### 2026-10-02 USD market-data integration and operator-authorized SOTA promotion

The user reviewed the results, explicitly selected USD for SOTA and both monitored strategies, and requested a decision about blending USD into XGBoost. Preserved the tested separate U1 expanding ridge after each complete parent. It uses per-ETF coefficients for short/older momentum, volatility and same-vintage USD21/USD63; 60 completed training months; monthly fits; labels strictly before fit close; 12% forecast-rank tilt with 3pp bounds, preserved cash and selections. The existing XGBoost recipe and 26 features are unchanged. Blending USD into trees would need a new version, retraining and a matched comparison; it has not been tested and is not claimed to perform worse. U1's whole gain includes price features; the USD-specific roughly 14 bp/year increment remains statistically inconclusive (30 months, Holm p=1). The operator decision changes the selected strategy, not that evidence. Preserved original strategy IDs and matched parent benchmarks; new versions append `_usd_v1`. Prospective start is October 2. Decision and rollback contract: `config/strategy-promotions/usd-ridge-u1-2026-10-02.json`.

Added Market Data → USD index, with Federal Reserve broad-dollar identity DTWEXBGS, 5,410 daily rows since 2006, retained missing values, index units, 21/63-observation changes, vintage/release labels, date range and JSON export. The application acquires required ALFRED snapshots, audits and publishes them before models consume them, verifies published file hashes and freezes complete USD model schedules into the shared Python/native LEAN bundles. The latest USD publication has 93 signal vintages, batch `cda8efbb6cfbe32e42192541a8014652abe62e3d8c358ad5d10484677e85a56a`, latest index observation September 25, vintage September 30 for October 1 features. Weekly release lag is expected; current-vintage chart history is never substituted for historical model vintages. Daily archive availability and revised ETF/legacy FX limitations remain explicit. The USD feature is predictive and does not hedge USD/CNH.

All 30 study USD models reproduce on the original pinned inputs within 3.56e-17. The newer audited ETF publication revises some earlier values slightly: maximum forecast change is 1.10e-7; this is recorded separately from same-input parity. Eight complete native LEAN runs (three USD portfolios, three parents, rolling-only and risk parity) pass Python target/fill/cash/NAV parity. Used all 16 model-fitting workers, eight isolated preparation workers and three 4 GiB native containers with five CPUs each. Preparation took 46.31 seconds; native batch 231.42 seconds. Published complete strategy revision `ea2688052e33cd4501e67db03e68a9bf4888a3e633f8cc4b621a4a6692143d0a` on audited ETF batch `a3245f0fe94558cbbccdcb25ec8334518b42620e6f8aab43e57d4a82aa0e37c2`. All three reports, historical NAV, held weights and indicative targets reach October 1. Reports show the separate USD models, inputs/coefficients, vintage provenance, parent benchmarks and complete decision flow. The XGBoost allocation table explicitly ends with the USD step.

Found an existing paper/backtest timing mismatch while wiring the published USD schedule: paper's SignalContext used the decision date, which excludes that day's completed close. It now uses the next trading session, matching the shared historical target service. A dedicated causal/parity test passes; actual October 1 paper target calculation matches published SOTA weights within 1.12e-17. This verification computes weights only and creates no proposal. Paper/live target generation reads the committed USD model receipt and requires its audited ETF batch to match current decision inputs. Missing/stale inputs, missing monthly fits or modified hashes stop calculation. Historical periods before the registered April 2024 eligibility retain their parents.

Preserved the inherited risk contract rather than silently changing the tested portfolio: 45% is the base inverse-volatility cap, not a final holdings cap; the USD tilt cannot increase inherited weights above 45%. A hard final cap remains separate pending versioned work. No capital, broker-environment, reconciliation, live, order approval or submission limits were weakened. The strategy-change guard disables automatic paper approval on the new SOTA identity. Policy file SHA256 remains `bb0cf028f43742be85ae1a5701287a0f26141be0d5bccfbbb42c8506c4333259`; resumption requires the normal operator review/re-enable flow. No order was requested or submitted by this work.

Validation: final full suite 781 passed / 52 optional skips, Ruff and whitespace checks clean. Initial test failures exposed old hardcoded strategy IDs and execution fixtures without USD inputs; fixtures now explicitly provide synthetic neutral USD publications while dedicated tests check inference, historical causality, monthly availability, hash/batch binding, complete target parity and missing-data failures. Initial same-input comparison mistakenly compared a newer price batch to the frozen study; corrected the verification to distinguish exact frozen-input reproduction from data revisions. No economic recipe changed in that correction. During deployment the old process briefly reported unknown new IDs while the new calculation job was running; stopped the old dashboard through its guarded launcher and retained all completed native receipts. Final dashboard PID 3816 and dispatcher 25392; analytics running, error-free and current. IB Gateway was unavailable on port 4002 at deployment; existing retry and routing gates remain active. Browser verified the USD chart and range controls, all three registry names/dates, and the separate USD panel in the full rolling report without console errors. The USD page is left open. Evidence: `var/research/usd-promotion-final-tests.xml`, `usd-promotion-publication.json`, `usd-promotion-model-parity.json`, `usd-promotion-paper-target-parity.json`, `usd-promotion-http-verification.json`, `usd-promotion-execution-status.json`, `usd-promotion-market-data.png`. No commit or push.


### 2026-10-02–03 Asset names in portfolio, trading and market-data views

Added the requested Asset name column beside ticker identifiers throughout portfolio holdings and drift, scheduled/indicative targets, proposal orders, broker records and order blotter, reconciliation, broker/account PnL, missed trades and execution attribution. The shared SOTA report now identifies assets in current holdings, historical contributions, USD forecasts, XGBoost forecasts, allocation stages, feature headers, chart legends and tooltips. Market-data selectors and raw/research tables use the same labels. Governed histories continue to show their own provider identity. Standard archived reports are rendered from their embedded frozen payload; the saved files and financial data are preserved.

The presentation helper uses the existing ETF/stock registries, an explicit cash label and an issuer-verified recorder label for QQQ (https://www.invesco.com/qqq-etf/en/home.html). Labels are escaped and embedded for standalone/offline reports. Missing names remain explicit. Name columns wrap and tables scroll on narrow screens. Serving-cache inputs now include the name metadata and shared shell, so subsequent label changes refresh saved reports.

Deployed through the guarded dashboard/dispatcher launchers. The application completed all eight native validations and published refreshed reports under calculation revision 36c6b8884308455b12a1946f6c8dddc472e02e520fe3a8e76222463d08c92f0a. All three monitored portfolios have complete name coverage; holdings, NAV histories, final NAV, total/annual return, Sharpe and drawdown exactly match the pre-update snapshot. Analytics reports no errors. The existing paper-approval response, already enabled at session start, is unchanged; no execution controls or strategy economics were edited and no orders were manually submitted.

Validation: 49 focused tests passed, one optional integration test skipped; Ruff and whitespace checks pass. Tests execute the production table renderers to check escaping, column alignment, offline labels and unchanged values. Browser checks confirm names in broker holdings/orders, all recorder selectors, SOTA portfolio weights and rolling/USD forecasts, with no console errors. Evidence: var/research/asset-names-tests.xml, asset-names-before.json, asset-names-verification.json and asset-names-portfolio.png. No commit or push.


### 2026-10-03 Proposed strategy promotion and trading-history workflow — review pending

User is considering Rolling 1y XGBoost + ETF activity lag-20 + USD for SOTA and active paper trading. Requested a plan before implementation, verification before the actual switch, and user-operated promotion/trading buttons in Strategies. Read project architecture, rollout/research state, accounting/performance contracts and the strategy-promotion-control playbook. This session performs planning and source inspection only.

Confirmed three implementation gaps: current_sota_definition() is a code-selected global consumed by targets, account-performance comparisons and automatic approval; there is no dated per-portfolio strategy-assignment history; and the trading builder binds the USD schedule but does not bind a validated monthly model to RollingModelOverlay. Current execution attribution replays the actual execution quantities at proposal reference prices; it must retain that meaning separately from a complete strategy benchmark.

Proposed design for review: separate persistent SOTA designation, trading assignments and chart comparison selection, with a combined Promote to SOTA and schedule trading action. Keep immutable account/environment/portfolio-scoped assignment events, strategy/model/input versions, approval/operator/reason, effective session/time, handover valuation and rollback lineage. Use verified after-close handovers and next-session execution for the first release. Preserve portfolio inception, cash and lot cost bases; allocate strategy-period PnL from marked boundary values and keep order-origin attribution separately. Build a replayable reference portfolio following the dated assignment/transition policy, with switch markers and period filters in both Performance and PnL. Old proposals/approvals cannot authorize the new assignment; existing paper-policy binding and routing/reconciliation checks remain in force. Rolling trading must reproduce monitored targets from the same validated monthly XGBoost and USD receipts before eligibility.

Migration must derive older assignments from retained proposal/approval/model evidence, identify unknown activation times and avoid assigning today's strategy to all earlier history. Implementation acceptance would include A-to-B-to-A histories, inherited positions, flows/FX/fees, partial and late fills, stale previews, concurrent switches, restart/rollback recovery and target parity. Deploy and verify the controls with the current strategy selected; then present the actual candidate-switch preview for a separate operator decision. No strategy selection, trading policy, application source or runtime state changed in this planning session.


## 2026-10-03 — Dated strategy roles, capital allocation and attribution

User approved executing the reviewed plan, including multiple strategies with capital weights, while retaining the current trading strategy until implementation and verification are reviewed. Implemented separate SOTA designation and paper trading allocation, preview-bound approval, after-close activation, exact account binding, immutable events, cancellation and rollback. PostgreSQL migration 005 is applied; transactional compare-and-swap/idempotency was verified inside a rolled-back test transaction. Legacy portfolio context remains intact and is not assigned an invented strategy inception date.

Added virtual per-strategy positions/cash, explicit monthly capital transfers, drifting capital between resets, internal crosses and one net account order per ETF. Actual partial fills replay by economic timestamp. Shared unclassified cash is disclosed; a reserve debit is funded pro rata through explicit capital flows. Marked PnL excludes internal transfers and approvals after the last valued session. Missing marks or incomplete fill evidence withhold the affected result. The allocation reference carries holdings across switches, uses adjusted units at next-session close and a separate 25 bp/year model cost; actual tax-lot and execution-reference attribution remain intact. Historical FX availability and cash-flow classification limitations are disclosed.

Trading now binds rolling XGBoost to the same verified definition, audited price batch, scheduled fit and model hash as monitoring, followed by the registered separate USD prediction layer. Old allocation proposals cannot route after activation or rollback. A new allocation invalidates automatic paper approval authority; SOTA designation alone does not change trading targets. Existing reconciliation, broker-account and live-disabled controls are retained.

During acceptance, LEAN's New York end-date clamp omitted the just-completed October 2 session. The frozen runner now validates the bundle's final scheduled close, sets only the end-date boundary in UTC+14, and restores New York before subscriptions. Its isolated runtime reads the calendar-checked frozen quote rather than importing live broker dependencies. All eight final native runs preserve complete-session and Python target/fill/cash/NAV parity through October 2. Final calculation revision: `0e5267447ff8cba69c57b40b0afc09c2283a41749d3ddfe658b64af99a955475`; audited price batch: `2515d735b070c5caa178bfe3786f0546ef13ec35e128b3d9dd91e7fae4b6ca08`. Used the 16-core fitting policy, eight preparation workers and three five-CPU/4 GiB native containers. Final native batch took 285.25 seconds after 81.54 seconds of preparation.

Verification: final full suite 809 passed / 52 optional skips; final model, ledger and browser-approval harness 25 passed. The harness confirms that editing inputs invalidates the reviewed configuration and rechecking consent cannot revive it. Ruff, JavaScript syntax and whitespace checks passed. Real read-only previews at 100% XGBoost and illustrative 60% XGBoost / 40% current strategy match published component target weights exactly (maximum difference zero) and create six net orders each. PostgreSQL control revision remains 0 with no events or pending change. Existing paper approval policy (enabled, revision 2) and portfolio context compare equal to the pre-deployment snapshots. Final app PID 46396; analytical errors empty at final verification.

Browser verified promotion links/editor, named ETFs, current/previous allocation controls, legacy attribution, rendered order/evidence preview, no document overflow or console errors, and unchecked/disabled final approval. Left the XGBoost preview open for discussion. Current strategy remains 100%; no actual strategy switch, order submission/cancellation, accounting reset, commit or push. Existing broker reconciliation (five issues) and an open/uncertain order remain the activation blockers; resolve them through normal operator controls before any handover.

Guide: `docs/trading-allocations.md`. Evidence: `var/research/strategy-control-acceptance.xml`, `strategy-control-model-ledger-final.xml`, `strategy-control-native-parity.json`, `strategy-control-runtime-acceptance.json`, `strategy-control-review.png` and `strategy-control-trading.png`. Next decision: review the desired SOTA designation, single/multiple-strategy capital weights, cap and effective close, then approve through the new UI once reconciliation is clear. No prospective performance claim is inferred from these replay checks.

## 2026-10-04 — Strategy switch form validation repair

User reported a raw `string_too_short` error when switching strategy. Request logs show two rejected POST requests to the strategy-control preview endpoint (HTTP 422). The required reason was empty; the form neither labelled it required nor validated it before sending, and rendered the API validation array as JSON. This was a preview validation failure, not an activation failure or evidence of lost text.

Added explicit required labels for operator/reason, trimmed empty-field validation, accessible inline errors and focus on the first missing field. Validation preserves entered text and weights. API validation arrays now produce readable field messages, including nested schedule errors; existing service error strings remain intact. Cancellation uses the same validation and its own input handler. Backend reason/operator requirements, preview invalidation and reviewed approval checks remain unchanged.

Verification: 32 focused strategy-control/operator UI tests passed; Ruff, JavaScript syntax and whitespace checks passed. Browser verification confirmed a whitespace-only reason is blocked locally, focused and marked invalid, with candidate weight preserved at 100%; server logs contain no preview request from that check. Valid trimmed submission and server rejection paths are covered by the browser-script harness. No console errors were observed. Deployed through the guarded dashboard/dispatcher launchers; dashboard PID 49952. Evidence: `var/research/strategy-form-validation-tests.xml`, `strategy-form-validation-log-excerpt.txt`, `strategy-form-validation-fixed.png`, and before/after JSON snapshots.

During verification, a separate operator action was recorded at 2026-10-04 08:47:17 +08:00 under Defeng, reason "better performance.": promote and allocate 100% to Rolling 1y XGBoost + ETF activity lag-20 + USD, effective after October 2 close, batch cap CNH 1,000,000. Event `3e71cad9-b3ab-4a41-9b5d-7dbdf8828bd7` raised control revision from 0 to 1. This debugging session did not submit that request. It remains pending because open/uncertain orders and unresolved IB reconciliation block activation. Current SOTA and 100% active allocation remain the prior strategy; paper approval policy and portfolio context exactly match the session-start snapshots. Preserved the pending request and left its status visible (`strategy-form-validation-pending.png`). No broker order, cancellation, activation, accounting reset, commit or push was performed by this session. Next operational action is to resolve the existing blockers through normal controls before handover can activate.

## 2026-10-04 — Verified execution recovery and approved XGBoost handover

User requested resolution of the open/uncertain-order blocker. The fresh IB workspace snapshot contained no open orders. Five October 2 drift orders (DBC, EWH, EWJ, EWY, VGK) were fully filled with zero remaining quantity and retained matched completed-order/permanent-ID evidence, but each had a durable execution replay-conflict flag. Current broker holdings exactly matched the local ledger. Legacy May partial records predate the existing September 25 portfolio baseline and were not the active blocker; they remain untouched.

Queried four days of executions through the installed IB API's supported `lastNDays` filter using a separate read-only client (941; server version 223). Saved 48 raw execution callbacks. All 17 executions belonging to the five flagged orders exactly matched the retained execution IDs, account, symbol/side/currency, quantity, price, cumulative quantity, timestamp and broker order ID; permanent IDs/client IDs also matched retained completed-order observations. The original rejected replay payload was not retained by the application, so the precise field that differed in that earlier response cannot be established. No original cause was inferred or validation rule weakened.

Prepared five reviewed recovery previews and applied the existing transactional `recover_broker_executions` workflow using their bound tokens. The audit retains previous flags/fills and links the fresh raw evidence by SHA-256. DBC 8 @ 32.3300; EWH 171 @ 21.5423; EWJ 9 @ 98.5500; EWY 6 @ 191.1900; VGK 48 @ 86.1692 are unchanged. Verified all 255 order records retain their orders, submission times, fill histories, aggregate quantities/prices, remaining quantities and statuses. The original PnL baseline and portfolio context are unchanged. Fresh order sync and portfolio reconciliation report no open orders, no execution conflicts, no position differences and no warnings; no accounting reset occurred. Subsequent app reconciliation remained matched.

The normal app loop then activated the already-approved XGBoost + ETF activity lag-20 + USD request at 2026-10-04 08:56:12 +08:00. Control revision is 2; SOTA and active capital target now select that strategy at 100%, with no pending change. Immutable history contains scheduling and activation events. The approved effective close is October 2, and the app staged a rebalance for October 5 09:30–10:00 New York time. This repair grants no new routing authority; the strategy-bound approval guard remains in place.

Added a regression verifying that a repeated consistent fill response cannot automatically clear a durable conflict, while explicit audited recovery using identical verified fills clears it without changing economics/history; replay remains idempotent. Focused recovery/history/reconciliation/strategy-control suite: 66 passed, 21 optional isolated-PostgreSQL tests skipped; Ruff passed. No production source changes or restart were required. Browser verified the active XGBoost SOTA/allocation and recorded time. Evidence: `var/research/order-blocker-before.json`, `order-blocker-broker-executions.json`, `order-blocker-recovery-preview.json`, `order-blocker-recovery-applied.json`, `order-blocker-after.json`, `order-blocker-tests.xml`, and `order-blocker-resolved.png`. No broker order was submitted, amended or cancelled; no history reset, commit or push.

## 2026-10-04 — Execution replay hardening and readable approval review

User asked why completed orders could remain in limbo, requested prevention, and then requested a redesign of the crowded approval rail. Reviewed the execution boundary, fill merge/recovery, reconciliation, management loop and strategy handover under the robustness-review playbook. The original October 2 rejected replay payload was discarded by old code, so the exact historical mismatching field remains unprovable. A fresh filtered broker query did not reproduce it; no original cause is asserted.

Closed specific failure paths: removed timestamp-to-current-time fallback and host-timezone inference; accept explicit UTC/zoned instants and reject malformed, missing or ambiguous DST times. Request seven days of executions instead of the current-day default and require supported Gateway semantics. Retain content-addressed raw callback snapshots and completion/error metadata before parsing; incomplete, interrupted, pending-price-revision or invalid callbacks fail the whole read without partial ledger writes. IO/hash failures also fail closed. Economic comparisons ignore evidence paths and reconnect-assigned client order IDs. True execution-ID conflicts retain both normalized versions, provenance, exact differing fields and a useful message; recovery retains these audits. Consistent later replays cannot clear an existing conflict. Filled records requiring review have a distinct label and strategy handover reports the actual issue.

Read-only reconciliation now continues on closed-market days. Obsolete automatic-approval bindings are invalidated without invoking routing. The reported reconciliation break count uses the latest report. Browser verification found that weekend alignment used the pre-sync clock; advanced it by elapsed sync time, with a regression for a seven-second read, so a freshly collected snapshot is not falsely considered future-dated.

Then moved proposal approval into the main page width. The compact status-filtered queue leads to a selected-proposal summary, clear decision controls, full-width order table with names/currencies/quantities/notional/New York windows, expandable order rationale and proposal drivers, targets and broker records. The button explicitly says Approve & submit paper orders. Per-proposal comment drafts survive selection/background refresh within the page. Late/out-of-order record responses cannot replace another selection; failed reads and in-flight decisions disable controls. Existing broker, reconciliation, risk and execution-window checks remain intact.

Validation: initial hardening suite 113 passed / 22 optional skips; adapter/management suite 48 passed / 20 optional skips; isolated PostgreSQL plus SQLite recovery/reconciliation suite 44 passed. UI suite 17 passed. Final affected management/approval/UI suite 47 passed / one optional skip, plus two final targeted checks passed. Ruff and whitespace checks passed. The installed SDK's read-only seven-day query returned 48 fills, all replaying identically with zero changed order records or conflicts. Guarded dashboard/dispatcher restarts deployed both changes. Runtime snapshots show matched reconciliation, zero execution conflicts, all 255 orders retaining original terms/fill economics/status, unchanged portfolio context and PnL baseline, and unchanged active XGBoost allocation/control revision 2. Automatic paper approval is disabled under the existing changed-strategy binding rule.

Browser verification at 1440px showed the approval table using all 1371px of the panel with no horizontal overflow; at 390px the 349px table container scrolls its readable columns and the page remains within the viewport. Tested proposal filtering and inspected the real pending October 5 review without submitting it. No orders were approved, submitted, amended or cancelled; no accounting reset, strategy change, commit or push was performed in this implementation session. Guide: docs/trading-operations.md. Evidence: var/research/order-sync-hardening-tests.xml, order-sync-adapter-tests.xml, order-sync-postgres-tests.xml, order-sync-readonly-replay.json, order-sync-deploy-before.json, order-sync-deploy-after.json, approval-workspace-tests.xml, approval-workspace-final-tests.xml, approval-workspace-runtime.json and approval-workspace screenshots. Broker retention is finite; older gaps or genuine conflicting evidence still require audited investigation.

### Concurrent approval and IB 2111 handling

During final UI verification, a separate approval request was recorded at 09:42:16 +08:00 with comment "Looks OK" for drift-75058e33ce57-20261005. The verification actions did not enter that comment or target Approve. Asked the operator to confirm the concurrent activity. The approval left the Pending filter empty. This supersedes the earlier runtime order-count snapshot: original 255 orders remain unchanged; a new DBC order (c782ae1bd09c, broker ID 37, 43 shares, zero fills) is acknowledged, bringing the total to 256. The other five proposed orders have no submission records. Evidence: var/research/approval-workspace-concurrent-approval.json.

The raw message exposed a separate boundary defect: documented IB code 2111 (algo window adjusted to next trading date) was treated as an error and woke the acknowledgement wait. The router conservatively stopped the batch as uncertain; subsequent broker reconciliation positively acknowledged DBC. Corrected this exact warning classification: retain the warning, wait for a real openOrder/orderStatus acknowledgement, and preserve other errors/timeouts as blockers. Warnings persist in the broker record. The UI now reports incomplete submissions with confirmed, uncertain, failed and unattempted counts, and retains the number of orders with broker records in the review after refresh. No automatic retry or resubmission was added or invoked. DBC's terms and status were left intact.

The warning/adapter/router/UI/boundary suite passed 53 tests; a final UI guard check and Ruff passed. Added tests for warning then acknowledgement, warning alone timing out, a real error following the warning, and two-order batches retaining warning evidence. Deployed through the normal dashboard/dispatcher scripts. This fix was verified with SDK callback mocks and actual retained broker evidence; no new order was submitted to test it. The approved five unattempted orders remain for operator review.

## 2026-10-04 — Intraday outage recovery and historical bootstrap

User reported sparse intraday recording during downtime and requested maximum recovery within IB Gateway limits. Confirmed recovery previously depended on an in-memory failed stream chunk, covered one hour only and did not run after hours/weekends. The active feed is delayed-trade aggregates, not a complete tick tape. After a scope clarification the user selected recovery of existing 5-second bars only.

Found a second concrete cause: historical warning 2188 was classified as terminal, waking the completion waiter before valid older data arrived. A direct isolated callback probe returned all 60 October 2 bars after that message (a true-tick probe also worked, but tick acquisition was not enabled). Corrected only this warning; actual historical end, errors, bounded timeouts and write failures still determine success. Invalid/out-of-window timestamps cannot establish coverage. Historical recovered mode is explicitly unknown; source warnings and filtered-trade provenance remain attached.

Implemented an application-owned acquisition process on separate paper client ID 221. It bootstraps six calendar months in nonoverlapping one-hour RTH windows with a 20-minute settlement lag, alternating latest gaps and oldest retrievable history. It honors existing holidays/DST/early closes, starts independently of streaming/daily backfill, persists request claims/pacing/results, retries connection failures, retains partial/empty/expired gaps, checks disk watermarks and resumes after crashes. Parent supervision restarts exited/stale workers; explicit stop retains the ledger. No agent automation, alternate price source, synthetic bars, research publication or trading authority was introduced.

The first full-hour canary exposed per-bar PostgreSQL connection overhead and hit the bounded timeout after 678 rows. Kept that attempt and its raw evidence, then batched each window's outbox in one transaction after individually durable raw/catalog writes. Throttled only diagnostic heartbeat writes. The same GLD April 6 hour retried and acquired all 720 rows. Raw/catalog failures cannot advance coverage; deterministic event IDs make replay idempotent. Concurrent raw files have unique names and manifest offset/appends are serialized. Market Data queries stream manifests with bounded result rows or compact symbol/date summaries, rather than loading millions of full objects. Large manifest scans still need a future normalized intraday serving store.

Deployed recorder and operator/dispatcher through their normal launchers. A controlled acquisition-worker termination was automatically replaced, preserving all nine completed windows at that checkpoint. At acceptance, the active ledger held 15 complete windows / 9,000 unique bars and 4,395 pending windows out of 4,410. Verified every completed-window raw payload hash, last catalog offset and all 9,000 corresponding PostgreSQL event IDs; the Market Data API reports no hash mismatches. April 6 and October 2 data are both present. Recovery remains running and may take many hours of machine/Gateway uptime; source/retention limits cannot be bypassed. Reception timestamps were not relabelled as historical availability, and recovered records remain unapproved raw evidence.

Validation: full suite 852 passed / 54 optional skips; 86 regression tests including a disposable PostgreSQL batch idempotency/rollback test; final 63 unit checks after pacing and publication-counter refinements. Ruff, PowerShell parsing and whitespace checks passed. Tests cover restart pacing, interrupted claims, calendar/retention boundaries, new dates/symbols, partial/empty/timeout/write failures, global pacing cooldown, outbox failure, raw-before-publish replay, concurrent manifest offsets and bounded catalog results. Runtime receipts: `var/research/intraday-recovery-acceptance.json`, `intraday-recovery-before-crash.json`, `intraday-recovery-after-crash.json`, and related test XML. Operating guide: `docs/intraday-recovery.md`.

IB emitted intermittent farm/server connectivity messages during canaries; completed windows require actual end callbacks and coverage. At acceptance recorder, Gateway, storage and analytics health are OK; the separate trading loop reports an execution-details timeout after dashboard restart, retaining its reconciliation/routing blockers. No order was submitted, cancelled or retried, no approval or live setting was changed, and no commit/push was requested. Next actions: let the app drain the backlog while Gateway is authenticated, inspect persistent partial/expired gaps, and address any continuing broker execution-sync timeout separately.
## 2026-10-08 — October 7 allocation replay incident and explicit late catch-up

The approved allocation event `d41767d9-04f4-4d1f-98f2-1e3f02aafb93` requested 100% `research_fallback_f3_v1` after October 7 close. The governed price batch had advanced to October 7, while the tracked publication and rolling-model binding remained through October 6. All three immutable USD replay attempts failed because the native USD adapter omitted the completed-session boundary handling already present in the CNH adapter: LEAN clamped its end date to yesterday in New York. The partial-output check correctly withheld publication, and the model/input identity guard correctly prevented handover, but the operator only saw a vague pending message.

Shared completed-close handling now verifies every symbol's final close, sets the LEAN boundary under UTC+14 and restores New York before subscriptions. It uses the same frozen calendar without importing the live package's broker/database dependencies. The first container acceptance run caught that packaging dependency; its failed evidence was preserved and the isolation defect fixed before acceptance. New replay errors identify the requested endpoint, engine cause and evidence directory. Exhausted immutable attempts explain that repair and a new verified calculation are needed. Stale prices/FX, job failures, overdue workers, handover blockers, alert-log/outbox failures and status-request timeouts are surfaced through status, dashboard warnings and durable alerts. Startup warmup is distinguished from a missed deadline. Last verified publications and all routing/identity/approval gates remain enforced. Email delivery is not configured; dashboard, JSONL and platform alert events are the verified channels.

Accepted calculation revision `bb7e6d08f32eaa1aaddcb7e8a44d4d3ff0b95def896d874493847a924ee064c0` completed at 13:46 UTC. All four CNH and five USD native replays passed parity through October 7, and all retained output hashes were reverified. Application prices and NAV/held weights both became current through October 7. Evidence and test XML are under `var/research/allocation-incident-20261008/`, including `diagnosis.json`, `replay-acceptance.json` and `recovered-analytics.json`. An independent archive import briefly reported a connection timeout; the new error path surfaced it.

After the default 09:30 New York handover cutoff, the user explicitly requested behaving as an overdue October 7 rebalance and sending the paper orders as soon as possible. Added an explicit, auditable catch-up authorization bound to the existing approved event, the original next trading session and the remaining full TWAP window. It preserves October 7 signal/effective-close provenance, actual authorization/activation/fill timestamps and the original intended execution benchmark. It cannot authorize live trading, other pending allocations, another session, or an incomplete remaining window. Normal proposal approval and paper broker routing still apply; no recurring auto-approval opt-in is granted by this recovery. Authorization was recorded at 13:47:37 UTC as control revision 4. Activation/submission acceptance is recorded below when verified.

Preparation exposed a second time-comparison defect: the worker passed its iteration-start timestamp to the handover, so an account snapshot refreshed during a lengthy preparation could appear future-dated. The worker now supplies its advancing elapsed clock; catch-up rechecks freshness/expiry and creates the execution window at completion. Regression coverage includes expiry during preparation, revised completion time, other-session rejection, pending/revision mismatch, paper-only authority, stale reconciliation, idempotent queuing and preservation of original benchmarks. The allocation activated at 13:56:33 UTC with October 7 signal/effective-close provenance and actual October 8 activation time. The generated proposal contains buy 76 DBC, sell 97 EWH, buy 2 EWJ and sell 2 EWY, paper TWAP 09:59–10:29 New York, with normal approval and routing requested under the user's explicit instruction.

Submission acceptance: the ordinary `approve-and-submit` endpoint routed all four orders at 13:57:53 UTC without validation errors. An independent IB order synchronization acknowledged IDs 43 DBC, 44 EWH, 45 EWJ and 46 EWY, each with broker status `Submitted`, no pending management action and no execution-sync issue; fills were still zero at that pre-window checkpoint. The saved allocation is active at control revision 5 with no pending change. The old automatic-approval policy disabled itself on allocation change; this one-time approval does not authorize future automatic routing. The application remains responsible for order/fill supervision. Final focused suites cover 247 distinct passing tests and four optional integration skips; the final management-worker suite also passed 11 tests. Ruff and whitespace checks passed. The final replay, authorization, proposal, submission and independent broker acknowledgement receipts are in the incident evidence directory. No live orders, account resets, evidence deletion, commit or push occurred.

The account operations lane's startup refresh briefly exceeded its five-minute budget and was visibly flagged; it completed at 14:00:15 UTC. Final analytics status has no errors, no operations staleness and no strategy staleness. At the final order-record checkpoint the four orders remain acknowledged with zero recorded fills; submission/acknowledgement is confirmed, completed execution is not claimed.


## 2026-10-08 — Host standby, interrupted database exchanges and resumable analytics archives

The follow-up timeout incident coincided with Windows Modern Standby: Kernel-Power events show entry at 22:08:53 Shanghai (14:08:53 UTC), deeper standby at 22:09:02, and resume at 22:31:30. ClickHouse query activity has the matching 14:09–14:31 gap. Queries normally completed in under 4.3 seconds around that interval; server-side broken pipes/socket timeouts appeared on resume. The original tracked calculation failure recovered at 14:37:34 using the retained verified replay outputs. Strategy prices and valuations stayed current through October 7. Evidence: `host-standby-events.json`, `database-activity-around-standby.json` and `analytics-before-hardening.json` in `var/research/allocation-incident-20261008/`.

LEAN archive imports also had a separate recovery weakness: every added registered replay caused the whole archive to be extracted and reinserted. The registry now contains 356 runs / 712 JSON files / approximately 1.03 GB. A transient exchange failure restarted millions of rows on the next pass; archive timeouts also occurred outside the standby interval, so standby is not asserted to explain every connection failure. The import now verifies both receipt hashes for every run, including unchanged runs, and publishes each changed run independently with the existing payload readback checks. Successfully committed runs are retained across retry/restart. A completeness manifest advances only after all registered runs verify; the old aggregate becomes an empty current projection while all historical evidence remains. No strategy calculation input or execution authority moved to these archival projections.

All 356 runs completed this migration at 14:56:29 UTC; the archive lane completed at 14:56:39. The accepted manifest is `79bfd0ba8a15adbf0b91d10a71031651267da3cba26fe0384ec97b7f06303899`, saved in `archive-migration-accepted.json`. An application restart during migration demonstrated resumption from committed checkpoints. The completed manifest is reused on subsequent refreshes without recopying unchanged runs.

ClickHouse transport failures now identify the dependency, sanitized endpoint, operation and socket timeout. They retain their transport exception type and cause, omit credentials/query payloads, and never automatically retry ambiguous database writes. Job failures include traceback evidence in the worker log. An independent 15-second watchdog detects stopped/overdue workers even when all refresh lanes are blocked. A monitoring gap over 90 seconds emits a durable interruption alert, wakes every lane, and remains visible until all lanes complete successful refreshes started after the gap. Worker startup is explicitly unverified until each lane's first complete refresh. Errors for untried jobs survive unrelated failures. Operator refresh also wakes the archive/account lanes. Dashboard and health use the same readiness evaluation, including archive/watchdog failures.

The focused regression suite passes 140 tests with one optional integration skip; Ruff passes. Coverage includes connect/read/reset/partial-response failures without retries or secret leakage, dead/all-stalled workers, pause/resume recovery, failed and pre-resume refreshes, startup readiness, archive checkpoints across interruption, unchanged-run idempotency, missing/tampered artifacts, and preservation of the previous aggregate on failure. Results are in `analytics-recovery-final-tests.xml`.

Independent broker records confirm all four previously authorized paper orders filled: buy 76 DBC (last fill 14:24:54 UTC), sell 97 EWH (14:25:56), buy 2 EWJ (14:19:01), sell 2 EWY (14:19:00), all with zero remaining quantity. These broker-managed orders continued while the host slept. `filled-orders.json` preserves their execution evidence. No additional orders were submitted in this repair; live routing and approval/reconciliation/input gates remain unchanged. Host power settings were not modified. The operator must keep the host awake for uninterrupted local work; local monitoring can report suspension only on resume. Existing email configuration remains absent; verified alerts use dashboard, local log and platform events. Historical ClickHouse projections remain retained and have no automatic retention policy. No commit or push was requested.

Final deployment verification: operator PID 19148 and dispatcher PID 42932 are running through the normal guarded startup. All three analytics lanes completed their first refresh after restart; the unchanged archive completed at 14:57:33 UTC without advancing or rewriting the accepted manifest. Final API checks report no analytics errors, no stale lane/data/watchdog flags, `calculation_status=ok`, no pending allocation, and both analytics/trading-management health `ok`. Saved `analytics-after-hardening.json`, `control-after-hardening.json` and `health-after-hardening.json` record this state. The skipped test requires an explicitly disposable ClickHouse workspace; production publication readback verification completed for all 356 registered archive runs.
## 2026-10-08 — CFTC disaggregated positioning source admitted to Market Data

Added the app-owned CFTC Disaggregated Futures Only recorder and a Fund
Positioning view within Market Data. The recorder preserves raw source rows,
configuration/version hashes, report dates and the app's first-seen time, and
publishes auditable normalized net-position/open-interest ratios for WTI, Henry
Hub natural gas, COMEX gold/silver/copper and LME aluminum. The API/recorder
refresh runs in the application's research analytics lane with a six-hour
source-check interval; no separate task or manual card is used.

Initial publication: 1,903 reports starting 2020-01-07 through 2026-09-29 for
five contracts, plus 143 aluminum reports through 2026-06-09. Accepted batch:
`406d59e27de2c63addef7ee832720ebb05102e9b3ebdad9c37993532f47ac9a6`. A
subsequent capture produced the same version and was idempotent. Twenty-eight
focused positioning/economic recorder tests pass; Ruff and `git diff --check`
pass.

The CFTC row contains the Tuesday position date, not its original dissemination
timestamp. Reports are usually released Friday at 3:30 p.m. Eastern, subject to
holiday delays. Every row is available in the app only from `first_seen_at`;
none is backfilled into an earlier strategy decision. Do not use this history in
historical backtests or model-training rows before its first capture. Positioning
measures futures trader categories, not direct ETF holdings/flows; related ETFs
are proxies only. No ETF admission, strategy calculation, allocation, promotion
or execution authority changed. Next: qualify an EIA energy balance recorder
with release-time semantics, then prospective issuer holdings/shares/NAV and ETF
identity/price histories.

## 2026-10-08 — EIA energy recorder and source qualification

Continued the authorized recorder-first ETF expansion research. Added independent
hourly petroleum and natural-gas capture jobs to the application analytics lane,
with raw bytes saved before validation, immutable revision snapshots, verified
ClickHouse publications, pinned ex-ante readers and Market Data → Energy Data.
The service uses free official release files; no subscription or broker connection
is required. Original data/metadata, response completion times, code/config hashes
and failed attempts remain replay evidence under `var/governance/eia-energy/`.

First publication covers October 2: 12 petroleum indicators and five gas indicators.
Petroleum source release October 7 14:30 UTC / capture October 8 15:44:22.128948 UTC;
gas source release October 8 14:30 UTC / capture 15:44:30.583014 UTC. Catalog pins
are `e9dc9194fb3da76491a7e63b47a17a7ed19bfab316485be86259538c45d87d91` and
`f0654328d09b8bdf05b900e4cb512483ca5c78e6e4f705d2fcf4a4bc73b0d355`, respectively.
The current crude-stock JSON contains 314 observations, but all belong to the
newly captured current vintage. No old decision or model-training row may use
them before capture. Source-date/URL inconsistency in an inspected historical
archive page keeps historical release admission unresolved. Inventory/activity
context is not asserted to be a leading predictor or an analyst-consensus surprise.

Pinned readers reject pre-capture/equal-cutoff decisions, naive times, missing or
stale current data, and altered evidence. Tests exercise revisions with unchanged
nominal release clocks, mixed reports, DST, changing averaging windows, history
gaps, failed publication/retry and independent-source recovery. 65 distinct focused
tests pass (49 existing recorder/recovery tests, 15 new energy tests and one
navigation suite); Ruff passes. Browser verification found and fixed a direct-link
bug affecting Energy Data and Fund Positioning. Yellow availability notices remain
separate from actual publication faults. Both source views and their dates/values
were checked after guarded application restart; no browser console errors.

Source samples, publication summary and runtime checks are retained in
`var/research/energy-source-qualification-20261008/`. The app retained the initial
pins across normal refreshes. No historical energy return backtest was run and
no new Sharpe/Calmar result is claimed. Monitored strategy definitions, funding
and routing authority were not changed. Next: prospective issuer holdings/shares/
NAV and a small ETF identity/audited-price/IB admission pilot. The finite subsequent
linear/tree, positive/negative asset-response design and additional data gaps are
recorded in `docs/energy-fundamentals-recorder.md`. Single-stock trading stays out
of scope; existing economic ridge stays frozen until the universe revisit.
