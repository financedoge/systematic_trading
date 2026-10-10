# Signal decay, alpha overlays and portfolio robustness — research plan

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
is the single most valuable finding available and it costs almost nothing.

**Approach.** A frozen diagnostic family on the existing published run:
leave-one-selection-out, leave-one-ETF-out, sub-period stability, bootstrap over
the 70 evaluation months, a matched-availability **placebo rank** (same
availability and labelling, random ranks), a data-through-2022 refit, and
sensitivity to top-N and to the financial-ridge weight.

**Acceptance.** Predeclared retention tolerance before outcomes; report
preserve / reject / inconclusive; every failed variant retained as evidence. No
re-tuning of the inspected sample.

**Does not authorise** re-optimising FR25, nor any change to monitoring,
allocation or the 45% cap.

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

### P4.18 — Volatility-targeted exposure

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
already exist. This is real basis points with no alpha and no new data.

**Acceptance.** Uses retained execution evidence and the existing benchmark
service; report per-symbol and aggregate slippage by execution style; no claim
beyond the observed sample.

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
| 3 | P4.15 turnover / breakeven gate | — |
| 4 | P4.16 sleeve-aware construction | — |
| 5 | P4.17 Alpha101 time-series subset | P4.13, P4.15, P4.16 |
| 6 | P4.18 volatility targeting *or* P4.19 execution timing | — |
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
