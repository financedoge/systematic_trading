# Signal decay, alpha overlays and portfolio robustness — research plan

## Agreed priorities after the 2026-10-11 review

The [second review](strategy-review-2026-10-11.md) supersedes conflicting numerical claims in the
historical completion notes below. No further budget/exit optimization should use those old results.

**Operator agreement — 2026-10-11.** The operator accepted these recommendations and explicitly
requested substantial expansion of the tradable ETF universe. Universe expansion is a major workstream,
not a two-ticker extension; the staged delivery and acceptance requirements are registered in P4.16d
below. This records the agreed direction and dependencies, not an allocation change.

1. Finish the minimum P8.1–P8.5 paper execution contract for the complete 14-ETF pool; retain all
   approval, raw-share sizing, account permission and reconciliation checks. Bind FR25 financial-model
   schedules and audited activity inputs in the paper target builder, resolve the union of component
   instruments, and verify target/order/reconciliation parity. This minimum delivery need not wait for
   the full multi-venue platform. A shared gate alone does not complete the execution contract.
2. Complete P4.19a app-owned benchmark collection/publication, then resume P4.19 on matched retained
   evidence. The October 11 audit found zero published benchmarks, so the timing comparison is blocked.
   Measure session/ETF cost before a faster alpha experiment; do not fetch provider prices directly
   into a study.
3. Deliver the substantial ETF-universe expansion under P4.16d: candidate inventory and registry,
   staged audited admission, comparable peer groups and scalable app calculations. Include volatility
   normalization, duplicate-exposure control, point-in-time membership and full-pool attribution.
   More tickers alone are not independent breadth.
4. Register one incremental alpha hypothesis with a declared horizon, training/validation split,
   1/5/10/21-session decay diagnostics, and net contribution versus the unchanged base. Separate
   reversal and trend families; correlated 46/49/51 passes are not independent discoveries.
5. Before another TP/SL run, specify actual fill-based alpha-sleeve PnL, exposure/risk units, time expiry,
   re-entry/cooldown and gap rules. The repaired legacy study is a prior-close contribution proxy;
   it cannot establish intraday TP/SL execution. Keep a small fixed comparison and an untouched
   prospective period instead of another inspected-sample exit grid.

**Conditional paper pilot.** Once the minimum execution contract passes, prepare a concrete allocation
preview for **5% FR25 / 95% F3 paper capital**, with combined risk limits and the existing approval flow.
This capital share is distinct from a 5% Alpha101 tilt. Keep the alpha variant at zero allocation while
incremental evidence is absent. Retain app-owned targets, raw-share orders, fills, cash and reconciliation;
review the first 30 sessions for operational behavior, without treating that short sample as proof of
alpha. A contract or reconciliation failure stops new pilot orders and invokes the reviewed rollback
plan toward F3, subject to reconciliation and the existing controls. XLE/XLB permission was manually
confirmed by the operator and gateway/reconciliation passed during the review; these are not presumed
denied, and operational checks must be fresh at execution. Planning agreement does not submit orders.

P4.18's registered fixed rule is now complete and rejected: 18 replays, all risk/return criteria failed,
including against the exposure-matched diagnostic; native parity passed. See the protocol below and
`var/research/volatility-target-20261011-v1/`. This closes that fixed rule without target/window tuning.
P4.20 must distinguish base momentum coverage from the Alpha101 tilt's incremental diagnostic gap.

**Platform dependency — P6.15, requested 2026-10-11.** Review research-worker deployment and resource
scheduling before scaling the ETF universe: measure actual per-engine memory and CPU use, compare
host-native and containerized LEAN, remove avoidable duplication and serial work, and replace fixed
resource assumptions with a tested budget. The objective is useful multicore throughput with responsive
database/operations services. Do not assume that enlarging Docker's memory cap is the solution or that
ClickHouse supplies shared working memory to research processes. Preserve reproducible outputs and
independent engine parity. See [resource review](calculation-performance.md#p615--worker-deployment-and-resource-budget-review).


Registered 2026-10-10. This is the plan for the next research phase, agreed with
the user after a review of the existing research record and a first-hand reading
of Kakushadze's *101 Formulaic Alphas*. It authorises no promotion, funding or
execution change. Each item is registered in
[`docs/execution-kanban.md`](execution-kanban.md) as `P4.13`–`P4.21`.

## Working cadence

One item at a time. Take an item, produce its report, **stop and review it**,
draw inspiration, reflect, and only then start the next item. Do not run the
programme in one pass, and do not start item *n+1* while item *n*'s report is
unreviewed. Each item closes with a written outcome — including negative ones —
in `log.md`, `docs/research-state.md` and the Kanban.

## Where we are

Three regularities hold across every experiment run so far, and they set the base
rate for anything new:

1. **Selection-layer changes work; sizing and timing overlays do not.** The
   full-pool rank blends (FR25, CR50) applied *before* eligibility and top-six
   selection produced +0.087 / +0.065 Sharpe over the capped control. The
   context/financial ridge *sizing* overlays produced +0.016 and failed the
   registered effect-size screen. Cash and stress-deployment policies,
   confirmation-based re-entry and BIL parking all failed theirs.
2. **Nothing passes family-adjusted significance.** Every completed study ends
   with no contrast passing 5% Holm at any registered block length. Effect sizes
   are small relative to noise.
3. **The strongest current lead is fragile and this is already documented.** FR25
   changes 13 of 70 evaluation selections, one asset each, and its 2026
   net-return advantage is +4.552pp. That is concentration, not robustness.

Data reality that constrains what can be attempted:

- **Daily research:** published audited histories for the ~1,056 certified
  series; all 14 pool instruments and benchmarks are `audited_with_limitations`.
  `market_data.daily_bars` holds 142,191 rows across 39 symbols, 2012-01-03 to
  2026-10-09.
- **No VWAP history, no market capitalisation, no industry classification field.**
- **No intraday research data at all.** There are no intraday tables in
  ClickHouse. The recorder holds raw five-second sampled quotes for five ETFs
  from 2026-04-04, flagged `research_approved: false`, and the source channel is
  documented as not being complete interval OHLCV.
- **No intraday execution stack.** Routing is a single monthly TWAP window;
  `P5.1`–`P5.4` (blotter domain model, pre-trade checks, blotter API,
  resize/defer) are all Pending.

## The programme

### P4.13 — Signal decay, IC instrumentation, dashboard and decay warning *(start here)*

**Question.** What is the current predictive content of every signal the
application already uses, how fast does it decay, and is any funded strategy
running on a signal that has stopped working?

**Why now.** The user's stated requirement is to monitor decay closely, and no
decay instrumentation exists today. There are no new data requirements. It has an
immediate use: FR25's edge sits almost entirely in 2026, and this is how we find
out whether its ridge signal has already decayed.

**Scope.** Three parts, delivered together because a number nobody sees cannot
inform a decision:

1. **Instrumentation.** Per signal and per candidate: forward rank IC at
   1/5/10/21/63-session horizons from published audited inputs on a pinned batch,
   the IC decay curve, implied half-life, hit rate, sub-period stability, the
   turnover-adjusted breakeven IC at the frozen 5bp, and dependence-aware
   confidence intervals.
2. **Dashboard surface.** A **Signal decay** panel on `/strategies` showing, for
   every monitored strategy, its key signal(s), current and long-run IC, decay
   status, estimated half-life, last computed and the input batch. Readable
   without opening a report.
3. **Allocation-aware decay warning.** A durable warning when a strategy's key
   signal is decaying or decayed. When that strategy **currently holds an
   allocation**, the warning is highlighted on `/operator` with the allocation
   weight and a link to the evidence, so the operator can decide whether to
   switch or deallocate.

**Signals covered.** The M1 selection score (75% momentum / 25% volume) and its
components, because it drives M1/14 and FR25 selection; the financial ridge
forecast that FR25 consumes; the context ridge forecast that CR consumes; the
rolling XGBoost forecast; and the raw momentum, volatility and activity features.
Model forecasts are obtained by reusing the same loaders and schedule builders the
strategies use, so the IC measures the deployed signal rather than a
reimplementation. Any signal that cannot be covered reproducibly must be listed as
an explicit coverage gap in the published output, never silently omitted.

**Method constraints.** Forward windows overlap at the longer horizons, so naive
t-statistics are badly overstated; intervals must use the platform's existing
circular block bootstrap over decision dates at 3/6/12 months. Per-date rank IC on
a 14-asset universe is coarse, so the averaged statistic is the finding and the
per-date dispersion must be shown, not hidden. Every signal value must be
point-in-time at its own decision cutoff; forward returns are labels only.

**Acceptance.** Reproducible from pinned published inputs with verified hashes;
deterministic tests over horizons, alignment, missingness, the bootstrap and the
threshold logic; a breakeven-IC table at 5bp; the panel renders real published
values; the warning fires with dedupe and carries the allocation weight; and the
warning **never** changes an allocation, an approval or a broker record by itself.

**Stop / honesty condition.** With ~130 monthly decisions the effective sample is
small. If IC estimates are too unstable to support a conclusion, report that
plainly rather than promoting a noise estimate into a finding.

**Does not authorise** any change to monitored strategies, funding or execution.
The decay warning is decision support; switching or deallocating remains an
operator decision through the existing allocation workflow.

### P4.14 — FR25 robustness stress

**Question.** Is FR25's selection advantage robust, or is it 13 selections and
one year?

**Why now.** It de-risks the lead we would otherwise build on. If it fails, that
is the single most valuable finding available and it costs almost nothing. P4.13
found no decay in the M1 score, so the open question is robustness, not decay.

**Protocol frozen before outcomes — 2026-10-10.** These thresholds are declared
here, before any robustness statistic is computed, and must not be revised after
seeing results. Analysis runs against the *published* selection-blend evidence
(`var/research/selection-blend-20261010-v1/`) with its parent protocol pinned, and
must not re-tune FR25 or add arms to the frozen study.

*Reference pair:* FR25 versus **CP** (the capped-M1 control), evaluation window
2021-01-04 onward, 5bp, zero delay — the same pair the selection study reported,
so the comparison is like-for-like.

*Predeclared retention tolerance.* FR25 is **retained** only if all of:

1. its evaluation-window excess return over CP stays **positive** in at least
   **two-thirds of complete calendar years**, and
2. dropping any **single** changed selection leaves the aggregate excess return
   over CP **positive**, and
3. the 95% circular block-bootstrap interval on the monthly FR25-minus-CP return
   difference has a **positive lower bound** at the 6-month block length, and
4. the observed excess return exceeds the **90th percentile** of a matched-
   availability placebo distribution (below).

Otherwise the outcome is **reject**, or **inconclusive** when the point estimate
is positive but the interval spans zero and the concentration tests pass — in
which case the honest statement is that the sample cannot distinguish the effect
from noise, and FR25 stays a monitored research lead without promotion.

*Part A — analysis of the published evidence (no new replays).*
Sub-period stability by complete calendar year; the paired block bootstrap on
monthly differences at 3/6/12 months; leave-one-changed-selection-out
attribution; and concentration measures (share of total excess return from the
best selection, from the best year, and from the top three selections).

*Part B — requires a separately frozen re-run, not analysis.* Three perturbations
cannot be evaluated from the published artifacts because each changes which
assets were selected and therefore the realised path:

**Part B protocol — frozen 2026-10-10, before any Part B outcome.** Reconnaissance
established that all three perturbations are **selection-layer** operations, so
none of them needs a model re-fit except the 2022 refit.

- **Evidence root.** A new root, `var/research/fr25-placebo-20261010-v1/`, pinning
  the parent selection-blend protocol hash and input manifest. It must not extend
  or overwrite the selection-blend root.
- **Reused frozen inputs.** The parent's `bars.json`, `macro.json`, `xgb_usd.json`,
  `selection.json` (per-decision rank tables) and `forecasts.json`, each with
  verified hashes.
- **Injection hook.** `SelectionBlend.ridge` is a mapping with `ready` plus
  `models[symbol]['linear_forecast']`. Replacing those forecasts with a permuted
  assignment regenerates the blended rank through the engine's own
  `_selection_scores`, so eligibility, abstention and downstream sizing are
  preserved by construction rather than re-implemented. Re-implementing the
  downstream sizing outside the engine is explicitly forbidden: a placebo must
  differ from FR25 in exactly one respect.
- **Placebo randomisation.** At each decision, **permute the ridge rank values
  across the available symbols**. A permutation preserves the marginal
  distribution of ranks and destroys only the *assignment*, which is precisely the
  information the ridge claims to supply. Draws: 200, fixed seed, declared here.
- **Statistic and threshold.** FR25's evaluation-window excess over CP, located in
  the placebo distribution. Retention requires exceeding the **90th percentile**,
  as already declared. Every draw is retained as evidence, including the ones that
  beat FR25.
- **Power, established during recon and recorded because it bounds the test.**
  FR25 **abstained on 0 of 70** evaluation decisions, so the placebo acts on the
  full sample. By contrast CR25 abstained on 12 of 70, which is why the same
  placebo for CR would have less power. FR25 changed 13 selections; its mean-only
  control FR25M changed 21.
- **Top-N and financial-weight sensitivity.** Slots 4/5/6/7 and ridge weights
  0.10/0.25/0.40, on the same frozen rank tables, reported as a sensitivity
  surface. This is **not** a search and **not** out-of-sample evidence: these are
  the axes the study already varied.
- **Data-through-2022 refit.** The only perturbation needing a genuine re-fit:
  train the ridge on labels completed by end-2022 and replay 2023 onward. If it
  cannot be run reproducibly, report it as not run rather than approximated.
- **Decision rule.** Unchanged from the frozen retention tolerance above. Part B
  can only move the verdict between *preserve* and *inconclusive*; it cannot
  rescue a failed year or interval test.

- **Matched-availability placebo rank** — replace the financial-ridge rank with a
  random rank carrying the same availability and abstention behaviour, over a
  predeclared number of draws, and locate the observed excess return in that
  distribution. This is the decisive test of whether the ridge contributes at
  all, as opposed to any perturbation of the M1 ordering.
- **Data-through-2022 refit** — fit the ridge only on information available to the
  end of 2022 and replay 2023 onward, measuring the incremental effect of continued causal retraining after 2022. It is not a
  full-sample hindsight comparison.
- **Top-N and financial-weight sensitivity** — top-4/5/6/7 and ridge weights
  0.10/0.25/0.40, reported as a sensitivity surface and **not** as a search. These
  are the same axes the study already varied, so they cannot be presented as a
  fresh out-of-sample result.

Part B must be registered as its own study with its own frozen protocol and its
own evidence root; it must not overwrite or extend the selection-blend root.

**Acceptance.** Retention tolerance predeclared before outcomes; report
preserve / reject / inconclusive; every failed variant retained as evidence; no
re-tuning of the inspected sample. Part A is analysis over published artifacts
with pinned hashes; Part B is a new frozen study.

**Part B completed 2026-10-10** in `var/research/fr25-placebo-20261010-v1/` (protocol
`429ec002…`), with the declared seed (`20261010`), the permutation generator, the log-excess
statistic and the percentile rule all frozen in the study protocol before the run — every arm
gated, no re-tuning. Outcome: the placebo check **passes** (96.50th percentile; 7 of 200 draws
beat FR25; the median draw is −0.26pp and only 45% of draws are above zero), the
data-through-2022 refit keeps **+4.20pp of FR25's +7.06pp** 2023+ excess over CP with a lower
drawdown, and the top-N / ridge-weight surface has no dominating cell and is non-monotone in
ridge weight. Because the 6-month interval test failed in Part A and Part B may not rescue it,
retention is **not preserved** and the verdict is **inconclusive** under both readings of the
verdict sentence above; that ambiguity was recorded in the frozen protocol before outcomes and
both readings are reported. [Part B findings](fr25-placebo-findings.md) ·
[Report](../research/fr25-placebo-2026-10-10/index.html).

**Does not authorise** re-optimising FR25, nor any change to monitoring,
allocation or the 45% cap. A **reject** outcome is a research finding and does not
by itself deallocate; that remains an operator decision.

### P4.15 — Turnover and breakeven-IC gate *(standing pre-test)*

**Question.** For a candidate overlay, how much turnover does it imply and what IC
must it earn to survive the frozen 5bp cost?

**Why now.** It is cheap, it is decisive, and it would have killed several ideas
before they consumed effort. It is also the specific gate that decides whether any
Alpha101 use is viable.

**Approach.** A small reusable function: implied annual one-way turnover from the
candidate's signal-to-position mapping, the resulting annual cost at 5bp, and the
IC required to break even. Report the implied ratio against the current
strategy's ~8× turnover and ~40bp annual drag.

**Acceptance.** Used by every later item in this programme; documented thresholds;
deterministic tests.

**Completed 2026-10-10.** `research/turnover_gate.py` implements the gate and delegates the
breakeven definition to `signal_decay.breakeven_ic` so the programme keeps one; thresholds, the
two turnover conventions and the usage contract are documented in
[docs/turnover-gate.md](turnover-gate.md); 23 deterministic tests are in
`tests/test_turnover_gate.py`. Frozen thresholds: a 40bp annual cost ceiling at the frozen 5bp
(the monitored book's own 40.4bp drag, +10% disclosed tolerance) and an IC margin of 3× the
breakeven IC, both required.

**Calibrated, not assumed.** Over 217 frozen replays the implied mapping tracks the measured
traded-notional turnover to within 3.5% and is **slightly conservative** (median measured/implied
0.9854) — the opposite of the expected direction, because the engine trades to targets only in
whole adjusted units and beyond its target tolerance. The raw implied value is therefore the
screening basis: it produced **zero false passes**, while a median-ratio correction would have
admitted one arm the replay rejects.

**Result on the registered candidates.** All three Alpha101 turnover archetypes from Appendix A
are rejected before any portfolio work — the fastest by 46×, the median by 14×, the slowest by 5×
on the cost ceiling — while the monitored book passes at 40.4bp with a 14.6× IC margin. P4.17's
premise is therefore constrained from the start. This also reconciles a measurement discrepancy
worth recording: P4.13's 3.97× is the selection-change proxy (19.8bp), not the traded-notional
drag (40.4bp), so the decay panel's cost headroom is about half what that number implies.
[Report](../research/turnover-gate-2026-10-10/index.html).

### P4.16 — Sleeve-aware construction

**Question.** Does selecting within asset-class sleeves (equity / fixed income /
commodity / gold) beat the pooled top-six over 14 heterogeneous instruments?

**Why now.** It is cheap, it uses data already held, and it tests the premise that
any cross-sectional signal can work on this universe at all — which is the
question P4.17 depends on. FR25's recent substitutions were cross-asset-class
(XLE for TLT, EWY for HYG), so the pooled cross-section is doing real work today
and its validity is untested.

**Approach.** A small frozen family: the pooled control, within-sleeve top-N with
explicit sleeve budgets, and an equal-weight-sleeve control, on matched costs,
timing and cash conventions.

**Acceptance.** Standard shared-report comparison; family-adjusted tests; no
threshold grid.

**Completed 2026-10-10, verdict inconclusive with two structural findings.** Evidence root
`var/research/sleeve-construction-20261010-v1/` (protocol `dc73d46d…`); every candidate screened
by the P4.15 gate **before** any replay (equal budgets pass at 34.0bp; composition budgets are a
recorded boundary case at 46.8bp).

1. **Sleeve construction is directionally better than pooled selection under a matched
   construction but not established.** +1.39pp (composition) and +2.50pp (equal) of CAGR with
   5.2pp and 3.9pp less maximum drawdown, yet all six registered contrasts have 95% intervals
   spanning zero at 3/6/12 months with Holm p = 1.000. The pooled cross-section is therefore
   acceptable and not shown to be worse — the answer P4.17 needed.
2. **The published control's advantage is its defensive-cash fallback, not its pooling.** The
   construction-matched arm makes the same decision on **119 of 130** days, and all 11
   differences are fallback days with zero weight-only differences. The entire gap (CAGR 11.92%
   against 9.50%, maximum drawdown −8.31% against −20.89%) is that one contract. An episode
   attribution then showed this value is **one bear market**: all seven evaluation-window
   episodes are 2022 (+13.69 log points, of which +8.94 is a single month) and the four pre-2021
   episodes are net negative (−2.18pp over five years), so only the drawdown property plausibly
   generalises.

[Findings](sleeve-construction-findings.md) ·
[Report](../research/sleeve-construction-2026-10-10/index.html). No promotion, no monitoring or
allocation change.

### P4.16b — Hierarchical construction *(operator-proposed 2026-10-11)*

**Question.** If an asset class is in a downtrend — bonds into a rising-rate environment — is
forcing an allocation to that bucket wrong? Pick the top two or three classes, then the top two or
three inside them.

**Origin.** The operator proposed this after reviewing P4.16, which measured that fixed sleeve
budgets hold `DBC` and `GLD` in all 70 evaluation decisions and that the composition-budget arm
paid 6% over the P4.15 cost ceiling for that representation.

**Frozen rule.** A class qualifies only if at least one member passes the same positive
126-session momentum gate the pooled control uses; qualifying classes are scored by the mean of
their two best eligible members; the top K share the incoming gross equally; inside each chosen
class the top two eligible names split that class's budget by incoming inverse-volatility weight;
an unfilled slot, or a day with no qualifying class, is cash. K=2 and K=3 are both declared; the
selection stage is the existing balanced-group overlay with a per-day budget override, so the
class ranking, the weight arithmetic and the "never force an ineligible asset" contract are the
parent primitive's own code.

**Completed 2026-10-11; verdict inconclusive, with the mechanism confirmed and the risk problem
untouched.** Evidence root `var/research/hierarchical-construction-20261011-v1/` (protocol
`af9bb329…`); screened by P4.15 before any replay (K=3 passes at 40.7bp implied, cheaper than the
pooled control; K=2 is a boundary case at 45.5bp).
[Findings](hierarchical-construction-findings.md).

- **The mechanism works as the operator described.** Neither arm held a single fixed-income
  instrument in any month of 2022; bonds are chosen 13% of the time under K=2 against 46% under
  the pooled control, and one decision was held entirely in cash because no class qualified. Both
  behaviours are regression tests.
- **Largest raw return effect in the programme so far, not established.** HIER-K2 is +5.32pp
  annualised against the construction-matched pooled control with a 95% interval excluding zero at
  3, 6 and 12 months, and both risk ratios improve — but the family-adjusted Holm p is 0.164.
- **Risk is orthogonal.** HIER-K2 holds 2.91 names and draws down −22.18%, worse than the
  diversified arm it beats on return (−20.89%) and far worse than CP (−8.31%). This reproduces
  P4.16's conclusion from the other direction: a better selection rule does not substitute for the
  exposure rule.
- **K=3 reverses part of the effect**: with three slots, fixed income is chosen *more* often than
  the pooled control does (64% against 46%). The benefit is a property of K=2, not of the rule in
  general.

**Next candidate, registered but not run: P4.16c — hierarchical qualification plus the defensive
fallback.** Keep the qualifying-class rule and add the pooled control's defensive behaviour, so
the family addresses representation *and* exposure at once. It should be judged on drawdown across
episodes rather than on one window's return, and it must pass the P4.15 gate.

**Parked at the operator's request, 2026-10-11.** The operator's reason is recorded in P4.16d
below: the four-class split is probably too coarse for the class question to be answerable at all,
so P4.16c is revisited only after the taxonomy and universe work.

### P4.16d — Granular asset classes, a wider ETF pool and volatility-aware class ranking *(operator-proposed 2026-10-11, registered, not run)*

**Operator's comments, recorded 2026-10-11.** Four asset classes are probably not enough to
differentiate performance between asset classes at all. The operator suggests a more granular
taxonomy:

- **equity** split by region — US equity, EU equity, Asian-ex-China equity, China equity;
- **fixed income** differentiated regionally, not treated as one block;
- **commodities** split by complex — base metals, energy, precious metals, agriculture,
  chemicals/industrial — with semiconductors listed alongside them;
- **boundary cases are real and must be decided, not ignored**: silver is both a precious and an
  industrial metal, and a fund's mandate can straddle categories or change (index switch,
  share-class change, roll methodology). Any taxonomy therefore needs dated, documented assignment
  rules, an explicit treatment of multi-category funds, and a rule for mandate changes rather than a
  static label;
- **volatility control is part of the question, not an afterthought.** In the operator's words,
  selecting the top-performing asset *without* volatility control is not a good idea, because the
  top performer is often simply the most volatile one. A class ranking must therefore be
  risk-adjusted, or class selection must carry an explicit volatility ceiling or size adjustment,
  and that rule must be frozen before outcomes;
- **the data prerequisite is binding.** A granular class selection cannot be built on the current
  14-ETF pool. It needs a **much larger audited ETF pool first**, admitted through the existing
  qualification, audit and publication process — pinned batch, verified input hashes, coverage and
  identity checks — never by reading provider archives or online prices directly into research.

**Taxonomy note.** Semiconductors are an equity industry rather than a commodity complex; they are
already registered as a narrow-industry pilot in the
[ETF expansion roadmap](etf-research-expansion-roadmap.md#portfolio-design-and-universe-expansion),
together with energy. The operator's list is recorded verbatim above while noting this, so the
eventual taxonomy is built from dated classifications rather than from the list's ordering.

**Scope strengthened by the operator — 2026-10-11.** Substantially expand the **tradable** ETF universe,
not merely the research watchlist. Design capacity for hundreds of candidate ETFs rather than a small
extension of the current fourteen; the admitted count is determined by evidence, not a ticker quota.
Cover economically distinct regional, country, sector/industry, duration, credit and commodity exposures.
Candidate admission permits selection; it never mandates a holding or an allocation.

**Staged delivery.** Preserve the one-item-at-a-time review cadence and publish an outcome for each stage:

1. **Inventory and taxonomy.** Produce a versioned candidate inventory with stable identities, listing
   venue/currency, dated peer groups, inception/closure and mandate changes, duplicate-exposure groups,
   and per-instrument data/execution gaps. Prioritize supported USD-listed venues for the first wave;
   additional venues/currencies depend on the corresponding P8 calendar, lot, FX and routing contracts.
   Freeze admission, liquidity and duplicate-handling rules before comparing strategy outcomes.
2. **Audited publication in waves.** Ingest through the existing audit/publication process; publish
   coverage and admission/rejection reasons with pinned batches and verified hashes. Use adjusted
   prices for returns and audited raw prices/volume for activity. Preserve missing history, point-in-time
   eligibility and closed funds where available; disclose survivorship and historical-availability gaps.
   Do not backfill today's surviving universe into periods before its members were eligible.
3. **App and paper execution readiness.** Use the shared registry for calculations, reports and execution
   without adding a hard-coded branch for every ETF. Benchmark refresh, feature, replay and report costs
   at the expanded scale. Verify raw sizing, account permissions, mixed-universe orders, cash and
   reconciliation for each supported contract class; show research-ready and paper-tradable states
   separately. The existing 14-ETF pilot need not wait for completion of the entire expansion.
4. **Controlled research on the expanded pool.** Freeze a new protocol and compare the existing strategy
   on its original pool with the same recipe on the full newly supported pool before adding alpha changes.
   Attribute results by constituent and peer group, control duplicate exposures, then test risk-normalized
   ranking and one declared alpha family at matched horizons/costs. Use time/group holdouts and prospective
   observations; report effective breadth and concentration as well as ticker count.

**First executable deliverable.** A candidate inventory, taxonomy, data/contract gap matrix and proposed
first admission wave with estimated storage/refresh costs. Review it before ingestion; the research
comparison waits for publication, but inventory/admission planning does not require an already expanded
pool. Actual instrument admission and strategy capital remain separate decisions.

**Acceptance when it is run.** The taxonomy, its boundary rules and the risk-adjustment rule
frozen in advance; a pinned audited publication batch with verified input hashes; the P4.15
turnover gate applied to every candidate mapping before any replay; controls that stop
near-duplicate funds from multiplying a class's selection probability (the roadmap's existing
rule); family-adjusted tests; and judgement on drawdown across episodes, consistent with P4.16's
finding that exposure rules matter more than the partition.

**Research comparison blocked on** universe admission. The inventory and admission stages above
are the prerequisites to execute first; do not run the expanded-pool comparison before its inputs are
published. This registration does not itself admit instruments, authorize direct provider downloads
as research inputs, or change monitoring, allocation or the 45% cap.

### P4.17 — Alpha101 restricted time-series subset as selection features

**Question.** Do the formulaic alphas that survive the data and structure filters
add incremental information at the selection layer?

**Why now.** It is the user's original idea, reduced to the part that can be done
honestly. See Appendix A — only 16 of the 101 are both computable and free of a
cross-sectional operator.

**Prerequisites.** P4.15 (turnover gate), P4.13 (decay measurement of the new
signals), P4.16 (whether the cross-sectional premise holds).

**Approach.** Implement the 16 pure time-series alphas from the paper's verbatim
formulas as point-in-time features. Treat them as **features feeding a regularized
model at the selection layer**, not as standalone strategies — selection is where
the evidence says effects live. Declare the whole 16 as one comparison family with
a mean-only control of matched availability, in the shape of the existing ridge
studies. Measure per-alpha turnover and decay before any portfolio result. If
anything survives, trade it as a **bounded satellite sleeve** (5–10% NAV), never
as a whole-book overlay.

**Acceptance.** Frozen protocol with the family declared up front; measured
turnover and breakeven ratio for every alpha; no promotion; the report states
which alphas were rejected and why.

**Explicitly excluded.** The 22 implementable Tier-D alphas (their cross-sectional
core is noise at 14 names), any attempt to fake `indneutralize`, and any
unconditional daily overlay of the book.

**Completed 2026-10-11; verdict: none of the sixteen clears the gate, so the family closes
before any portfolio work.** Evidence root `var/research/alpha101-screen-20261011-v1/`
(protocol `7865c485…`); 15 alphas rejected, one (alpha 7) not judged because it is a
constant. Findings: [alpha101-screen-findings.md](alpha101-screen-findings.md).

- **The failure is turnover, not information.** The same family translated to this
  programme's monthly decision frequency turns over 7.62×–15.29× against the monitored
  book's 8.07×, costing 38.1bp–76.5bp against the 44.0bp ceiling. Only alpha 21 is inside
  the ceiling (38.1bp) and it fails on the IC margin (2.22× against the required 3×). P4.15
  rejected the *daily* archetypes by 5×–46×; at the frequency actually traded here the gap
  is 1.0–1.9×.
- **Information does exist at the decision horizon, and that is the result worth keeping.**
  Alpha 53 (+0.0747) and alpha 26 (+0.0572) have 21-session rank-IC intervals excluding zero
  positively, and alpha 101 (−0.0749) excludes zero *negatively* — its information is real
  and inverted, so a long-only mapping of it is a short signal.
- **Disclosed: the published formulas mix dollar volume with share volume.**
  `adv{d}` is defined as average daily dollar volume while `volume` is shares, so alpha 7's
  `adv20 < volume` never holds here and the formula collapses to its constant branch. That
  is reported, not repaired; a dollar-volume-consistent variant is a separately declared
  family.
- **Disclosed: a wiring defect in the first run, fixed before publication.** The first screen
  reported alpha 7 as passing with a 102.77× margin, because a candidate with no measurable
  IC was judged against the programme reference IC — the false-pass mode the gate exists to
  prevent. Two rules were added and frozen: a cross-section with fewer than two distinct
  values cannot rank and forms no mapping, and a candidate with no measurable IC is reported
  *insufficient*, never passed on the reference IC. Pre-correction 1 pass / 15 reject;
  post-correction 0 pass / 15 reject / 1 insufficient. The correction cannot manufacture a
  pass.
- **Consequence for sequencing.** The plan's next step was conditional — *if anything
  survives, trade it as a bounded 5–10% satellite sleeve* — and nothing survives; there is
  no satellite and no model stage. A follow-up must attack turnover rather than signal
  quality (slower rebalance, hold bands, or use as a feature inside an already-slower
  mapping), and must measure its turnover against the P4.15 ceiling first.
- **Verification.** 22 tests including character-for-character formula pinning against a
  hash-pinned extraction of the paper, hand-computed spot checks, a window-boundedness check
  across all sixteen alphas, the screen's point-in-time slicing, and exact artifact
  reproduction with the pinned inputs and paper re-checked by hash.

### P4.17b — Alpha101 as a tactical tilt instead of an on/off allocation *(operator-proposed 2026-10-11)*

**Operator's proposal.** If the problem with the Alpha101 family is turnover, do not use it to
choose the book at all: use it to **overweight and underweight the holdings we already have**. Set
aside some X% for overweight/underweight and find the balance between cost and alpha. The alpha
should also feed the IC decay monitor, and the IC threshold does not need to be high.

**Why this is the right reading of the P4.17 failure.** The family died on *membership churn*:
top-six mappings turned over 7.62×–15.29× against the monitored book's 8.07×. A tilt changes no
membership at all — it only redistributes a bounded amount of NAV inside the existing book — so the
incremental turnover is bounded by the tilt budget rather than by how often the alpha changes its
mind about *which* instruments to hold. And because the breakeven IC scales with turnover, the
absolute IC a tilt must clear falls in proportion: the operator's "the threshold does not need to be
that high" follows from the design rather than from relaxing the gate.

**The binding constraint is cost headroom, not signal quality.** The monitored book already measures
**40.4bp** of traded-notional drag at the frozen 5bp against an effective ceiling of **44.0bp** — so a
tilt overlay has about **3.6bp a year**, roughly 0.7× of extra annual turnover, to work with. That is
the number the design has to fit, and it is why re-tilting monthly and a bounded X are the whole
question. The gate's 3× margin is *not* relaxed: it simply applies against a breakeven IC one to two
orders of magnitude smaller than the one the P4.17 mappings faced.

**Declared design, measured before any replay.**

- **Base book.** The pinned capped pooled control's own decisions — real membership, real weights,
  unchanged. The tilt never adds or removes an instrument.
- **Tilt shape.** Held names are ranked by the alpha; each gets a linear rank score in [−1, +1] with
  zero mean; total overweight equals total underweight equals X/2 of NAV, so the tilt is NAV-neutral
  and gross exposure and cash are unchanged.
- **Bounds.** A single per-decision shrink factor scales the whole tilt so no name breaches the 45%
  cap or goes negative. The mean shrink factor is reported, because a book sitting at the cap cannot
  be overweighted into and that interaction is a measured result, not an assumption.
- **Budget family.** X ∈ {5%, 10%, 20%}, reported as a surface. X is not chosen from the outcome: the
  grid is small, declared, and any performance claim later must clear family adjustment across the
  whole 16 × 3 grid.
- **Cost test.** Incremental traded notional and cost against the untilted book, judged against the
  published headroom; breakeven IC at the incremental turnover; the observed IC from the frozen P4.17
  screen. Every candidate is gated before any replay, and a replay happens only if something clears.
- **Decay monitoring.** If a tilt candidate is ever monitored it enters the P4.13 decay instrumentation
  like every other signal. That is an explicit follow-on, not an implication of this measurement.

**Lifecycle of the tilt, measured (2026-10-11).** The alpha is a *ranking* signal, so a tilt has no
take-profit and no stop-loss in any arm: it is re-derived from the current ranks, never triggered by its
own profit or loss.

- **Monthly arms open and hold.** Between a strategy's monthly decisions nothing acts on the tilt at all
  — no intra-month close, resize or review. At the next decision it is re-derived, which in practice
  means it usually *rotates*: across FR25's 70 evaluation decisions the live tilt flips sign on **54**,
  resizes on 6, closes on 2 and opens on 2, and 62 of the 70 decisions carry a live tilt. A flip is a
  close and a reopen in one trade, so the exposure rotates rather than exiting.
- **Daily arms can act inside the month**, but only on the signal-distance band, never on P&L. With no
  band the tilt changes on every session it applies (1,269 changes across 1,448 sessions, 1,097 of them
  flips); at a band of 100% of the budget it changes 670 times and is unchanged on 599 sessions; at 300%
  it changes 64 times, is unchanged on 1,215 sessions, and reproduces the monthly arm's event profile
  almost exactly (54 flips) — the mechanical form of the P4.17e conclusion.
- **An explicit exit rule is untested.** A price-based stop on the tilt's own P&L, or an exit when the
  alpha's score crosses a level rather than a rank, is a different rule that no arm here implements. It
  would be a new declared study, and it would face the P4.15 gate first.

**Does not authorise** promoting a tilt, changing the monitored book, or relaxing the 45% cap, the cash
reserve, the cost ceiling or the IC margin.


**Measured 2026-10-11; the tilt works where the mapping did not.** Evidence root
`var/research/alpha101-tilt-20261011-v1/` (protocol `1fa318f9…`); 48 declared candidates
(16 alphas × 3 budgets) gated before any replay. Findings:
[alpha101-tilt-findings.md](alpha101-tilt-findings.md).

- **At 5%: 12 of 16 alphas clear the gate for 0.00–0.48bp**, against the **3.65bp** of headroom
  between the monitored book's published 40.35bp drag and the 44.0bp ceiling — the worst candidate
  uses **13%** of the available room. At 10%: 12 of 16 for up to 1.69bp. At 20% the balance breaks
  the other way (5 of 16; the worst candidate costs 5.17bp, above the headroom itself), so the
  cost/alpha balance sits at **5–10%**.
- **The breakeven IC collapses by two orders of magnitude** — from 0.0061–0.0122 for the rejected
  top-six mappings to **0.00000–0.00008** for a 5% tilt — because the breakeven scales with
  turnover. The operator's "the IC threshold need not be high" is therefore a consequence of the
  design, not a relaxation: the frozen 3× margin is applied unchanged.
- **The three rejections are information failures, not cost failures**: alpha 101's tilt points the
  wrong way (−0.0749 with an interval excluding zero), and alphas 23 and 12 are negative too. Alpha
  7 stays degenerate. This is the exact inversion of P4.17, where cost killed everything.
- **The 45% cap interaction is measured**: the shrink factor averages 0.98–1.00 and binds on 2–7% of
  decisions, so a book at the cap shrinks the tilt rather than breaching the limit.
- **A defect was found by the test and fixed before publication**: the first rule tilted a constant
  held cross-section on the alphabetical tie-break, and a zero incremental cost then read as a pass
  — the same false-pass class as P4.17's alpha 7. Two rules were frozen: a cross-section with fewer
  than two distinct values cannot rank and is left untilted, and a candidate that never ranked the
  book is reported *insufficient*, never passed on a zero cost. Re-measured: 29 passes instead of
  28, with the ternary alphas cheaper because days where they say nothing about the book no longer
  trade.

**Registered next: P4.17c — the tilt replay.** A small declared family: the equal-weight tilt
composite across the family at 5% and 10% (which avoids selecting on the in-sample ICs), the
matched untilted control, and the lowest-cost variant; replayed through the engine with the 45% cap
and cash reserve unchanged, family-adjusted intervals, and judgement on drawdown across episodes as
well as return. If a tilt is ever monitored it enters the P4.13 decay instrumentation like every
other signal.

**Does not authorise** promoting a tilt, changing the monitored book, or relaxing the 45% cap, the
cash reserve, the cost ceiling or the IC margin.


### P4.17c — The tilt replayed on the current SOTA

**Operator request, 2026-10-11:** bake the tested alpha into the current SOTA with a 10% tilt and
report the final return, Sharpe, Calmar and max drawdown. Measured in its own frozen study,
`var/research/alpha101-tilt-replay-20261011-v1/` (protocol `bb7dba31…`), 36 replays, gate before
replay. Findings: [alpha101-tilt-replay-findings.md](alpha101-tilt-replay-findings.md).

| Arm | Total return | CAGR | Sharpe | Calmar | Max DD | Incremental cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SOTA, untouched | 76.4% | 10.36% | 0.916 | 0.805 | −12.88% | — |
| SOTA + 10% tilt of alpha 53 | 77.0% | 10.42% | 0.913 | 0.818 | −12.75% | +2.08bp |
| SOTA + 10% family tilt | 77.5% | 10.48% | 0.922 | 0.840 | −12.47% | +1.53bp |

- **Affordable and directionally better on every measure, and not established.** +0.07% and +0.12%
  annualised against the untouched SOTA, 95% intervals spanning zero at 3/6/12 months and Holm
  p = 1.000 across the three contrasts; Sharpe flat, Calmar +1.6–4.3%, maximum drawdown
  −0.13 to −0.41pp. The tilt costs 1.5–2.1bp and returns 7–12bp a year: nearly free, nearly neutral.
- **The gate passed all three arms before any replay** (SOTA 35.14bp, +tilt-53 37.23bp with +2.08bp
  incremental, +family 36.67bp with +1.53bp) — the SOTA leaves ~8.9bp of headroom and the tilt uses a
  fifth of it.
- **The family tilt beats the best-information single alpha at lower cost** (+0.12% for 1.53bp
  against +0.07% for 2.08bp), which is direct evidence that alpha 53's apparent superiority was
  in-sample noise and that diversifying is the better instrument.
- **The SOTA's book can arrive above the 45% cap** (the final clamp runs after the overlay chain), so
  on 4–6 of 130 decisions the declared single-shrink-factor rule shrank the tilt to a no-op rather
  than pushing an over-cap name further up; the tilt applied on 115 of 130 decisions.
- **Why it is small, and expected:** a 10% budget moves each weight by a few percent of NAV against a
  forward rank IC of 0.05–0.075, so the expected edge is tens of basis points a year. 20% was already
  measured to break the cost balance, so there is no cheap way to make the effect larger.

**Does not authorise** promoting the tilt, changing the monitored book, or relaxing the 45% cap, the
cash reserve, the cost ceiling or the IC margin. The SOTA remains `research_fallback_f3_v1`,
monitored and unchanged.


### P4.17d — The tilt budget surface, and the ceiling on how far it goes

**Operator request:** add the tilt to FR25, raise the budget much higher, and find the optimal X%
without worrying about cost first. Measured in `var/research/alpha101-tilt-surface-20261011-v1/`
(protocol `99cd55a8…`): FR25 and the SOTA over the same 70 evaluation decisions, monthly family tilt at
X in {10, 20, 30, 50, 75, 100, 150}%, every arm replayed regardless of its gate verdict at the
operator's instruction. Findings: [alpha101-tilt-surface-findings.md](alpha101-tilt-surface-findings.md).

- **There is no higher-X regime.** On FR25 every measure degrades monotonically as the budget rises
  (untouched 106.0% total return / 13.37% CAGR / 1.218 Sharpe; X=10% 104.1% / 13.20% / 1.196; X=50%
  94.9% / 12.29% / 1.059; X=150% 96.2% / 12.42% / 1.028). On the SOTA the return peaks at X=10% and
  every risk ratio worsens above it.
- **The tilt saturates at about half of NAV.** Declared 100% gives an effective 50.6% and declared 150%
  gives 50.7%, for identical cost to a tenth of a basis point — one shrink factor keeps every name
  inside the 45% cap and above zero, and a six-name book can only move as much as its smallest weight.
- **Cost, measured but not binding by instruction:** X <= 20% passes the 44.0bp ceiling and X >= 30% is
  rejected (FR25 46.7bp at 30%, 56.5bp at 100%; SOTA 45.7bp and 56.7bp). The arms above the ceiling are
  also the ones that degrade the portfolio, so the deviation changes no conclusion.
- **No optimal X is declared.** The best X by any metric is an in-sample maximum on an inspected window;
  the honest reading is the smallest budget in the grid, or none.

**Does not authorise** promoting the tilt, changing the monitored book, or relaxing the cap, the cash
reserve, the cost ceiling or the IC margin.

### P4.17e — Daily, threshold-triggered tilting: high frequency destroys value

**Operator clarification:** do not wait for the monthly rebalance — monitor daily and re-tilt X% whenever
the alpha signal gives a buy/sell, accepting high frequency to enhance the return; if cost becomes an
issue, control the threshold at which the signal trades. Measured in
`var/research/alpha101-tilt-daily-20261011-v1/` (protocol `725aa02b…`): FR25 and the SOTA, 1,448 sessions
each, X in {5, 10, 20}% and a re-tilt band of {daily, 50%, 100%, 200%, 300%} of the budget, plus the
monthly arm as the frequency reference. Findings:
50%, 100%, 200%, 300%} of the budget, plus the monthly arm as the frequency reference. Findings:
[alpha101-tilt-daily-findings.md](alpha101-tilt-daily-findings.md).

- **Every daily arm is worse than doing nothing and costs 2–5.5x more.** On FR25 the daily arms return
  101.1% / 96.5% / 87.6% against the untouched 105.8%, with Sharpe 1.174 / 1.131 / 1.042 against 1.214,
  at 91.8bp / 142.8bp / 243.3bp of cost. The SOTA shows the same ordering.
- **The threshold works exactly as proposed — which is the problem.** Raising the band from daily to
  300% cuts re-tilts from 1,269 to 64 over the study (about 221 to 11 per year) and cost from 91.8–243.3bp to 37–44bp; but fitting the
  44.0bp ceiling requires a band of 200–300%, where the arm trades 64–86 times a year — the monthly
  design's own 70. Daily monitoring behind a wide deadband is the monthly tilt with extra bookkeeping.
- **Nothing that clears the ceiling is distinguishable from doing nothing**: every band arm's contrast
  has an interval spanning zero and Holm p = 1.000.
- **Why:** the family's information is at the 21-session horizon (rank IC 0.05–0.075), so daily re-tilting
  trades one-session noise while paying linearly in cost — the frequency multiplies cost as the
  information per trade falls to zero. A higher-frequency use would need a higher-frequency signal.

**Verification note:** the study required a shared `tilt_vector` refactor of the tested rule, whose
behaviour-preservation is proven by the earlier frozen artifacts still reproducing exactly; two trigger
defects were caught by the test bench and fixed (the establishing re-tilt was not counted as a trade,
and a band of a whole budget could never open from a zero tilt on the first session).

**Does not authorise** daily re-tilting or any change to the monitored book.


### P4.17f — Exit rules: close the tilt when the signal stops

**Operator direction:** holding until the next monthly rebalance is not optimal — test removing the
tilt whenever the signal disappears or stops; and cost is not a constraint, the objective is the
optimum. Measured in `var/research/alpha101-tilt-exit-20261011-v1/` (protocol `db40c5e1…`): FR25 and
the SOTA, 42 arms, 252 replays, monthly entry with declared intra-month exits, ranked on net outcomes
with **no cost filter** (arms up to 84.3bp were replayed). Findings:
[alpha101-tilt-exit-findings.md](alpha101-tilt-exit-findings.md).

- **Holding beats exiting.** On FR25 the best net configuration is **X = 5% held** (104.9% total
  return / 13.27% CAGR / 1.204 Sharpe / 1.598 Calmar / −8.30% maxDD / 40.9bp) and on the SOTA
  **X = 10% held** (77.3% / 10.46% / 0.922 / 0.839 / −12.46% / 38.3bp). Four of the six metric optima
  across the two books are plain HOLD arms.
- **Three of the six declared exit rules never fire at all**, which answers the question directly:
  EXIT-NOSIG never triggers in 1,448 sessions because this family never stops ranking the held book;
  the −2% stop and the +1% take-profit never trigger either, and the −0.5% stop fires once. At a 5–20%
  tilt the tilt's own return does not travel that far inside a month.
- **What does fire is the flip — 61 exits — and acting on it is worse:** it gives up the remaining
  edge and pays a round trip, adding +2.4bp at X = 5% and +4.6bp at X = 10% while leaving Sharpe
  unchanged and Calmar lower. The re-entry variant costs +10 to +25bp for the same or worse return.
- **Why:** the monthly design already rotates the tilt at the next decision (54 flips, 2 closes and 2
  opens across 70 decisions), so an early exit is an extra trade against a rotation the rebalance was
  going to pay for anyway.
- **Nothing is established:** 0 of 20 contrasts per book differ from the untouched book at Holm
  p < 0.05, so every optimum is a selection on noise as much as on signal.

**On a native LEAN algorithm:** each arm is frozen as one target vector per session — exactly what a
daily-rebalancing strategy submits — and the replay engine's LEAN parity is already verified (0
differences). A native algorithm would add promotion-grade parity evidence, not different numbers; it
is the right artefact if a tilt is ever taken toward promotion.

**Does not authorise** promoting a tilt or changing the monitored books.

### P4.18 — Volatility-targeted exposure

**Execution registration — 2026-10-11 review session, before outcomes.** Run one fixed
FR25 overlay on the complete supported 14-ETF pool and the verified P4.14 inputs,
2021-01-04 through 2026-10-08. At each existing monthly rebalance estimate the
incoming book's volatility from 63 prior daily adjusted returns on an exact common
calendar; scale all risky weights by `min(1, 10% / estimated annual volatility)`.
No leverage, no new selection rule, no daily rebalancing and no volatility-parameter
search. The app's shared signal service owns the calculation. Cash earns zero under
the inherited research contract. Missing required observations stop the calculation.

Compare with unchanged FR25 and a constant multiplier chosen to match the dynamic
arm's time-weighted average target gross exposure. This last control is explicitly
an ex-post diagnostic, not a deployable parameter estimate. Report 5/10/20 bp costs
and zero/one additional session of delay. A useful historical result must reduce
maximum drawdown by at least 2 percentage points, sacrifice at most 1 percentage
point of CAGR and not reduce Sharpe versus FR25; also require better drawdown and
Sharpe than the exposure-matched control, and at most 44 bp annual drag at 5 bp.
Report every scenario; these hurdles must hold across scenarios for retention.
Freeze a new protocol/input/source root before outcomes. This is inspected-sample
research, with revised historical vintages; no promotion or paper allocation is
authorized by a successful backtest. An inconclusive/failed result closes this
fixed rule without tuning the 10% target or 63-session window.

**Question.** Does scaling exposure to a target volatility improve drawdown
without an unacceptable return sacrifice, against a matched-average-exposure
control?

**Why now.** The full-history drawdown is ~-19.5% and is the strategy's real weak
point. The completed cash/stress study tested *drawdown-triggered cash* and failed;
volatility-scaled exposure is a different mechanism and has not been tested. Note
the relevant literature is already filed in `research/references/` (`R09`, `R10`,
`R29`, `F05`).

**Acceptance.** Matched-average-exposure control, cost and delay sensitivity,
and the return-sacrifice budget declared before outcomes.

### P4.19 — Execution timing

**Question.** What is the cost difference between open-window TWAP, session close
and intraday VWAP execution?

**Why now.** The TWAP benchmark infrastructure and retained slippage evidence
were expected to support a comparison without new data. The October 11 evidence audit below disproves
that coverage assumption: the infrastructure exists but the published benchmarks are empty.

**Acceptance.** Uses retained execution evidence and the existing benchmark
service; report per-symbol and aggregate slippage by execution style; no claim
beyond the observed sample.

**Evidence-audit protocol — registered 2026-10-11, before cost calculations.** Snapshot all retained
paper order records and the pinned `execution-benchmarks` publication. Initial inventory has already
identified an empty benchmark publication; this is a coverage audit, not a prospective profitability
test. Retain input/source hashes and reproduce offline without broker calls or provider downloads.
Include filled orders in coverage counts, but require complete, unique, consistent execution details
before measuring costs. Use the existing benchmark-window and duration-weighted minute-close functions;
original intent survives rescheduling. A benchmark needs matching identity, full interval coverage and
valid published observations. Positive signed slippage means worse execution; aggregate signed price
cost over gross benchmark notional within each currency, never average order bps or mix currencies.
Report per-symbol and style coverage with unavailable values as null, never zero. Commissions/fees and
market impact are not inferred. Retained minute closes cannot supply session VWAP without volume/trade
value, and execution against different reference prices does not establish a causal timing advantage.
If matched close/VWAP/TWAP evidence is missing, publish the gap and the app-owned collection requirements;
do not rank execution styles or claim the research question is answered.

**2026-10-11 outcome: evidence audit complete; comparison blocked.** Snapshot
`var/research/execution-timing-20261011-v1/` retains 270 paper order records, 45 filled orders (42 TWAP),
27 with complete execution details, and zero published benchmark documents. Thirty-two TWAP orders
have explicit benchmark windows; none has an available published comparison. Close/VWAP costs also
remain unavailable. No execution-style ranking or policy change. [Full audit](execution-timing-findings.md).

**P4.19a — next prerequisite, registered.** Add app-owned post-trade benchmark collection independent
of blotter visits, with idempotent window identities, retained failures and audit/publication receipts.
Specify and publish matched raw close and intraday traded-value/volume evidence before comparing
TWAP/close/VWAP; no substitution of unaudited recorder data or planning reference prices. Report
per-symbol/style coverage and preserve historical gaps. A new frozen study follows adequate publication;
benchmark collection does not require orders or allocation changes.

**2026-10-11 implementation follow-up.** The app-owned TWAP collector, durable attempts/retries,
original/routed windows, audited publication and coverage API are implemented; see the
[collection contract](execution-benchmark-collection.md). Volume and WAP are retained where the
provider supplies them. This completes the collection mechanism, not the timing comparison: trading-time
raw-unit, raw-close and full-session VWAP qualification remain pending. The frozen v1 zero-coverage audit
is retained as the pre-implementation baseline. P6.15 remains queued separately.

### P4.20 — Decay-based promotion gate *(governance)*

Require any new signal to demonstrate a minimum estimated half-life and sub-period
IC stability before it can enter a monitored recipe. Depends on P4.13. This is the
structural protection against the Alpha101 selection problem described in
Appendix A.

### P4.21 — Look-through constituent alpha *(deferred, larger)*

**Question.** Can the structurally cross-sectional alphas be used honestly by
computing them on the constituent cross-section and aggregating holdings-weighted
to ETF scores?

**Why.** The 76 structurally cross-sectional alphas need breadth; the application
already holds 680 IVV constituent series plus issuer holdings and sector data.
This is the only route to using them without pretending 14 ETFs are a
cross-section.

**Caveats to carry.** Index-membership history is a survivorship trap already
flagged in the roadmap; issuer holdings snapshots are prospective-only from
October 2026; and the constituent series are the `review`-status population from
`P3.8`, so this work carries that disclosure.

**Blocked on** the constituent-coverage assessment. Do not start before P4.16
answers whether the cross-sectional premise holds at all.

### Platform item — intraday activation and stops *(not research)*

The user's "activate on an intraday alpha signal, exit on signal flip or a
predefined stop" design is registered as a **platform workstream**, not a research
item, because it needs two things that do not exist: published audited intraday
data, and an intraday execution stack (broker-side or monitored stops, intraday
risk checks, intraday reconciliation). It is tracked in the Kanban's P5 table.

Until both exist, any stop-loss research can only be approximated at daily
resolution (assume the stop fills when the session low breaches it), and that
approximation must be disclosed because it flatters stops in gap-down markets.

## Sequencing

| Order | Item | Gate to proceed |
| ---: | --- | --- |
| 1 | P4.13 decay instrumentation, dashboard panel and allocation-aware warning | — |
| 2 | P4.14 FR25 robustness stress | — |
| 3 | P4.15 turnover / breakeven gate | — (completed 2026-10-10) |
| 4 | P4.16 sleeve-aware construction | — (completed 2026-10-10; inconclusive, fallback dominates) |
| 4b | P4.16b hierarchical construction *(operator-proposed)* | — (completed 2026-10-11; inconclusive, largest raw return effect, risk untouched) |
| 4c | P4.16c hierarchical + defensive fallback | parked at the operator's request 2026-10-11 |
| 4d | P4.16d substantial tradable ETF expansion, granular classes and volatility-aware ranking | inventory/taxonomy and admission planning pending; research comparison waits for audited publication |
| 5 | P4.17 Alpha101 restricted time-series subset | — (completed 2026-10-11; no alpha clears the gate, family closed on turnover) |
| 5b | P4.17b Alpha101 tactical tilt *(operator-proposed)* | — (completed 2026-10-11; 12 of 16 pass at a 5% budget for 0.00–0.48bp against 3.65bp of headroom) |
| 5c | P4.17c the tilt replay *(operator-requested)* | — (completed 2026-10-11; affordable and directionally better, but +0.07–0.12% annualised and not established) |
| 5d | P4.17d tilt budget surface on FR25 and the SOTA *(operator-requested)* | — (completed 2026-10-11; no higher-X regime, saturates at ~51% of NAV) |
| 5e | P4.17e daily threshold-triggered tilt *(operator-requested)* | — (completed 2026-10-11; high frequency destroys value, the band that fits the ceiling is monthly) |
| 5f | P4.17f exit rules: close when the signal stops *(operator-directed)* | — (completed 2026-10-11; holding beats exiting, and three of six rules never fire) |
| 6 | P4.18 fixed volatility rule | completed and rejected October 11; no parameter search |
| 6a | P4.19 execution timing / P4.19a benchmark collection | coverage audit complete; comparison blocked on app-owned collection and published matched benchmarks |
| 7 | P4.20 decay-based promotion gate | P4.13 |
| 8 | P4.21 look-through constituent alpha | P4.16, constituent coverage |

P4.13 and P4.14 come first because neither needs new data, both directly serve the
stated goal, and P4.14 de-risks the strategy we actually fund.

## Explicit non-goals

- No further threshold or parameter search on the already-inspected sample.
- No automatic combination of previously failed recipes; the roadmap already
  forbids this.
- No implementation of the 22 Tier-D cross-sectional alphas on 14 ETFs, and no
  substitute for `indneutralize`.
- No unconditional daily Alpha101 overlay of the whole book (see Appendix A for
  the arithmetic).
- No promotion, funding, allocation or execution-authority change is implied by
  any item here. Existing approval, reconciliation, broker-environment and
  live-disabled gates remain in force.

## Appendix A — Alpha101 frozen premises

Established 2026-10-10 by extracting the paper's Appendix A verbatim and
classifying all 101 formulas; counts independently corroborated against
DolphinDB's separately written `wq101alpha` implementation, which agrees exactly
on the 19 alphas requiring an "info" table and the 43-alpha `vwap` set.

| Property | Count |
| --- | ---: |
| Requires `vwap` (not held) | 43 |
| Requires `IndClass.sector/.industry` (not held) | 18 |
| Requires `cap` (not held) | 1 |
| **Blocked by unavailable data (union)** | **49** |
| **Implementable with OHLCV + derived `adv`** | **52** |
| **Contain at least one cross-sectional operator** | **83** |
| Tier A — no cross-sectional operator (pure time series) | 18 |
| **Tier A and implementable** | **16** |

The 16 usable pure time-series alphas: **6, 7, 9, 12, 21, 23, 24, 26, 35, 43, 46,
49, 51, 53, 54, 101.** Six further Tier-B alphas (`1, 8, 10, 18, 28, 33`) become
usable if the outer `rank`/`scale` is replaced by a z-score.

`adv{d}` is not a blocker — it is `mean(close × volume, d)` and the application
publishes audited raw close and raw volume.

Holding period and cost, from the paper's own Table 1 (4 Jan 2010 – 31 Dec 2013,
1,006 observations, proprietary data):

| | Paper's figure | Implied annual one-way turnover | Cost at the frozen 5bp |
| --- | --- | ---: | ---: |
| Fastest alpha | τ=1.604, holding 0.62 sessions | ~404× | ~20.2% |
| **Median alpha** | **τ=0.475, holding 2.10 sessions** | **~120×** | **~6.0%** |
| Slowest alpha | τ=0.157, holding 6.37 sessions | ~40× | ~2.0% |
| Current strategy | — | ~8× | ~0.4% |

Other frozen premises, all from the paper or its immediate lineage:

- The paper's Table 1 caption states the performance figures are *"exclusive of any
  trading or transaction costs, price impact, etc."* The published Sharpe
  figures are therefore gross, at ~48–55% daily turnover.
- The alphas were validated on a cross-section of the top ~2,500 most liquid US
  stocks. A 14-instrument universe is roughly 0.6% of that breadth.
- The 101 are survivor-selected: the paper states 80 were in production when
  written, and reports one sample window with no out-of-sample split.
- Four alphas are "delay-0" (`42, 48, 53, 54`) and must trade at or near the same
  session's close; only `53` and `54` survive the data constraints, and both are
  high-urgency.
- The paper publishes only the *distribution* of turnover, never per-alpha
  turnover. Any per-alpha turnover used in P4.17 must be measured, not assumed.

**Reference.** Kakushadze, Z. (2016), *101 Formulaic Alphas*,
[arXiv:1601.00991](https://arxiv.org/abs/1601.00991). Full text is PDF-only —
`arxiv.org/html/1601.00991` returns 404 and ar5iv refuses the cross-origin
redirect — so re-derivation requires PDF text extraction. Retrieved copy:
sha256 `1f9c21afe32dcb3ee77b31548acdaea00451fbfa1c0ee10c907867bcc736fce9`,
244,416 bytes, 22 pages, arXiv v3. Not filed in `research/references/` yet: that
library keys every entry on a `cited_in` report id, and no report exists for this
work until P4.17 runs.

## Appendix B — data prerequisites and blockers

| Need | Status | Blocks |
| --- | --- | --- |
| Published audited daily OHLCV + volume | Available | — |
| VWAP history | Not held | 43 alphas; any VWAP-execution study |
| Market capitalisation, industry classification | Not held | 19 alphas; `indneutralize` |
| Published audited intraday bars | Not held; raw sampled quotes are `research_approved: false` | Intraday activation and stops |
| Intraday execution stack | Does not exist (`P5.1`–`P5.4` Pending) | Intraday activation and stops |
| Constituent coverage assessment | Pending | P4.21 |
| Security master for identity certification | Blocked (same access gap as `P3.7`/CRSP) | `P3.8`; long-window alphas needing certified identity |
| Qualified USD/CNH history and FX inputs | Unresolved input class | Any CNH-denominated claim beyond the current disclosures |

No paid subscription is assumed by this plan. Source acquisition, retention and
derived-data rights must be confirmed before any paid feed is selected.
