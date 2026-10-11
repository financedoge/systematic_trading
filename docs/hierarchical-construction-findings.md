# P4.16b — Hierarchical construction: qualify the class, then pick inside it

Operator proposal, 2026-10-11, after reviewing [P4.16](sleeve-construction-findings.md):
*if an asset class is in a downtrend — bonds into a rising-rate environment — forcing an
allocation to that bucket is wrong; pick the top two or three classes, then the top two
or three inside them.*

Run as its own frozen study in `var/research/hierarchical-construction-20261011-v1/`
(protocol SHA-256 `af9bb329…`), screened by the [P4.15 turnover gate](turnover-gate.md)
before any replay. **The rule was proposed after P4.16's outcome was known, so it is
post-hoc on the inspected sample and is not out-of-sample evidence.**

**Corrected evidence, 2026-10-11 peer review.** The v1 run inherited two defects from the
shared balanced-group overlay: a one-name sleeve bypassed the positive-momentum gate
entirely, and each class was scored from its globally top-ranked members rather than from
the members the rule holds. Both are repaired and the study is re-published in
`var/research/hierarchical-construction-20261011-v2/` (protocol SHA-256 `b115a5c5…`,
parent `sleeve-construction-20261010-v2`). **Every statistic in this document was
re-derived from that root and is numerically identical to v1**: the corrected class score
changes which members represent a class on 35 of 130 decisions but never changes which
classes are chosen, so the holdings and the economics do not move. The v1 root is
preserved as published.

Report: [`research/hierarchical-construction-2026-10-11/index.html`](../research/hierarchical-construction-2026-10-11/index.html)
(v1 rendering; the corrected v2 root is read directly through `protocol.json`,
`gate.json`, `analysis.json`, `statistics.json` and the class-score audit in
`var/research/hierarchical-construction-20261011-v2/audit/`, because the frozen analysis
module hard-codes the v1 presentation paths).

Research finding only. Nothing here changed a monitored strategy, an allocation, an
approval or a broker record.

## Verdict: inconclusive — the largest return effect measured so far, with the risk problem untouched

| Arm | CAGR | Sharpe | Calmar | Max DD | Turnover | Cost | Mean names held |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **CP** — published pooled control | 11.92% | **1.106** | **1.435** | **−8.31%** | 8.59× | 43.0bp | 5.19 |
| **POOL** — construction-matched pooled control | 9.50% | 0.754 | 0.455 | −20.89% | 9.05× | 45.3bp | 5.39 |
| **HIER-K2** — top 2 classes, top 2 inside | **15.07%** | 0.941 | 0.680 | −22.18% | 9.05× | 45.2bp | **2.91** |
| **HIER-K3** — top 3 classes, top 2 inside | 13.44% | 0.938 | 0.640 | −21.01% | 8.00× | **40.0bp** | 4.17 |

Evaluation window from fresh cash, 5bp, zero delay. Against the construction-matched
pooled control:

| Contrast | Mean annual difference | 95% interval (3m) | 95% interval (6m) | Holm p (6m) |
| --- | ---: | --- | --- | ---: |
| **HIER-K2 − POOL** | **+5.32%** | [+0.59%, +10.28%] | [+0.69%, +10.41%] | 0.164 |
| HIER-K3 − POOL | +3.60% | [−0.37%, +7.69%] | [−0.14%, +7.72%] | 0.288 |
| HIER-K3 − HIER-K2 | −1.72% | [−5.02%, +1.64%] | [−5.16%, +1.54%] | 0.935 |
| HIER-K2 − CP | +3.31% | [−3.70%, +10.38%] | [−3.85%, +10.10%] | 0.935 |
| HIER-K3 − CP | +1.59% | [−4.35%, +7.58%] | [−4.35%, +7.56%] | 0.935 |

**HIER-K2's raw interval excludes zero at every registered block length** — the strongest
raw return evidence any construction has produced in this programme — but the
family-adjusted Holm p is 0.164, so under the frozen rule it is **not established**.
Both risk ratios do improve against the matched pooled control (Sharpe 0.941 vs 0.754,
Calmar 0.680 vs 0.455), so `better_risk` is satisfied; the family adjustment is what
fails. The corrected v2 root reproduces this table and every contrast in it exactly
(15.07% / 13.44% / 9.50% CAGR; HIER-K2 − POOL +5.32%, Holm p 0.164), so none of the
findings here depend on the two defects the repair removes.

## The peer-review repair: what the gate and the class score actually did

**A one-name sleeve bypassed the momentum gate.** `BalancedAssetGroupOverlay` forms rank
metrics inside each sleeve, and rank metrics need at least two members. For the
single-instrument commodity (`DBC`) and gold (`GLD`) sleeves the rank table is therefore
always empty, and v1's overlay returned the sleeve's whole target list unchanged whenever
that table was empty. The published sentence "each is the only instrument in its sleeve
and its 126-session gate passed throughout" described a gate that was never consulted on
that path. The review's reproduction — 150 falling observations, 126-session momentum
−0.711864, still allocated 0.98 — is reproduced exactly by
`tests/test_balanced_momentum_gate.py`. Eligibility is now an absolute per-member test,
evaluated from each member's own price history before any ranking or rank fallback and
independently of sleeve size. On the corrected P4.16 arms (`sleeve-construction-20261010-v2`)
`DBC` and `GLD` are held on **49 of the 70 evaluation decisions** — exactly the days their
126-session momentum is positive (80/130 and 94/130 over the full window) — against
70/70 under the v1 bypass. No other instrument's admission count moves, and the pooled
control's decisions are unchanged.

**The published explanation does not survive as written.** `DBC`/`GLD` did not "qualify at
every decision" in P4.16: their gate passed on 49 of the 70 evaluation decisions, and the
other 21 holdings were the bypass, not a qualification. What does survive is the *class*
claim this study is about: the hierarchical arms buy a class only when one of its members
passes the same gate, so their `DBC`/`GLD` holdings (30–31 of 70 under K=2, 40/44 under K=3)
are gate-passing days on a genuinely gated path. The corrected P4.16 root is
`var/research/sleeve-construction-20261010-v2/` (protocol SHA-256 `d3c1135b…`); the
corrected sleeve-arm numbers live in that root and in
[P4.16](sleeve-construction-findings.md), which still carries the uncorrected reading.

**The class score used a population the rule did not hold.** v1 scored a class by the mean
of its globally top-ranked eligible members, while the members it held came from the
parent overlay's within-sleeve reranking. The review's synthetic case scored `TLT`/`HYG`
but held `IEF`/`TLT`; the same disagreement is present in the published evidence. Under
the registered two-population rule the held members still come from the parent's
within-sleeve reranking, the number attached to each held member is its **global**
cross-section score (the only population in which a one-name class is scoreable at all),
and the class score is the mean of exactly that held set. The audit in
`var/research/hierarchical-construction-20261011-v2/audit/class-score-population.json`
rebuilds the superseded population on all 260 corrected decisions: it differs from the
held set on **35 of 130 decisions** (38 class-level pairs: fixed income 19, equity 19;
36 of them also change the class-score value; 15 of the 70 evaluation decisions), but the
top-K class choice **never** changes (0 of 130). `2016-07-01` is the review's case in the
real data: v1 scored fixed income from `HYG`/`TLT` while the rule held `LQD`/`TLT`.

## The operator's mechanism works exactly as described

| Class | POOL chosen | HIER-K2 chosen | HIER-K3 chosen |
| --- | ---: | ---: | ---: |
| equity | 98.6% | 94.3% | 98.6% |
| **fixed income** | **45.7%** | **12.9%** | **64.3%** |
| commodity | 51.4% | 42.9% | 57.1% |
| gold | 51.4% | 44.3% | 62.9% |
| mean classes held | 2.47 | 1.94 | 2.83 |
| all-cash decisions | 1 | 1 | 1 |

**Neither arm held a single fixed-income instrument in any month of 2022** — the exact case
the operator raised. That is now a regression test. Bonds are chosen 13% of the time under
K=2 against 46% under the pooled control; the class is dropped, not underweighted, whenever
it has no eligible member. One decision (2022-10-03) had no qualifying class at all and was
held entirely in cash rather than forced into anything.

Two consequences worth stating plainly:

- **K=3 reverses part of the effect.** With three slots, fixed income is chosen *more* often
  than the pooled control does (64% vs 46%), because it frequently ranks third. The "drop
  the downtrending class" benefit is a property of K=2, not of the rule in general.
- **Concentration is the price.** HIER-K2 holds **2.91 names** on average and its two chosen
  names each hit the 45% cap in many months. Its drawdown (−22.18%) is **worse** than the
  diversified pooled arm it beats on return (−20.89%), and its Sharpe (0.941) is far below
  the published control's (1.106).

## The risk problem is orthogonal, and P4.16 already identified it

The hierarchical arms fix *representation* but not *drawdown*: −22.18% and −21.01% against
CP's −8.31%. That is the same gap P4.16 attributed to CP's defensive-cash fallback — the
construction-matched pooled arm, which also lacks it, drew down −20.89%. So this study
reproduces the earlier finding from the other direction: **a better selection rule does not
substitute for the exposure rule.**

The obvious next experiment follows directly, and is registered as a candidate rather than
run: **hierarchical class qualification plus the defensive fallback** — keep the
qualifying-class rule and add the pooled control's defensive behaviour. That combination is
the first construction in this programme that would address both the representation and the
exposure problem at once. It is **parked at the operator's request**: four classes are
probably too coarse for the class question to be answerable, so the taxonomy and universe
work in P4.16d comes first.

## The P4.15 gate

| Arm | Implied turnover | Implied annual cost | IC margin | Gate verdict |
| --- | ---: | ---: | ---: | --- |
| **HIER-K2** | 9.09× | **45.5bp** | 12.99× | reject — boundary case, replayed |
| **HIER-K3** | 8.15× | **40.7bp** | 14.49× | pass |
| CP (reference) | 8.72× | 43.6bp | 13.54× | pass |
| M1 (reference) | 8.75× | 43.7bp | 13.50× | pass |

K=3 is **cheaper than the pooled control** (40.0bp measured against CP's 43.0bp), while K=2
sits 3% over the effective 44bp ceiling and was replayed as a boundary case under P4.15's
published rule with its verdict recorded unchanged. Dispersion recomputed here (0.052190)
matches the published calibration exactly. The corrected v2 root reproduces this gate
record and the measured costs exactly (HIER-K2 9.09×/45.5bp, HIER-K3 8.15×/40.7bp).

## What this means for the programme

1. **Qualifying classes before selecting names is a real improvement over fixed sleeve
   budgets** — +5.32pp annualised against the matched pooled control, with both risk ratios
   better, and it removes the forced-representation behaviour that P4.16 measured. That
   behaviour was larger than P4.16 could see: under the repaired gate the P4.16 sleeve arms
   hold `DBC`/`GLD` on 49 of their 70 evaluation decisions, and the hierarchical arms hold
   them 30–31 of 70 — a genuine reduction, not the 70-of-70-versus-30-of-70 contrast the
   first version of this document reported.
2. **It is not established.** Raw intervals excluding zero with Holm p ≈ 0.16 is the pattern
   this programme keeps producing; the honest statement is a positive, unconfirmed effect.
3. **It does not address drawdown.** Any further work on this family should pair the
   selection rule with an exposure rule, and be judged on drawdown across episodes rather
   than on one window's return.
4. **P4.17 should still not expect selection alone to carry the day.** A structural change to
   *which classes are eligible* produces a large but unconfirmed return effect; an added
   selection feature inside the existing pooled rule is a smaller change and faces the same
   noise floor.

## Verification

19 focused tests in `tests/test_hierarchical_construction.py` cover the declared family and
K values, the corrected class-score rule, the overlay's inherited parameters, the registered
contrasts, the post-hoc disclosure and the two-population registration in the frozen v2
protocol, every verdict branch, and — against the frozen decisions — that no arm ever holds
more classes or more names per class than the rule allows, that every decision respects the
long-only and 45% cap contracts, that **no fixed-income instrument is held in any month of
2022**, that **no held name fails the 126-session gate**, that the corrected arms hold
exactly what the published arms held, and that the pinned P4.16 parent inputs are unchanged.
Every pooled reference replay reproduces the parent's published statistics to 1e-12. Ruff
passes.

Two further focused modules pin the repair itself: 11 tests in
`tests/test_balanced_momentum_gate.py` (the review's falling-singleton fixture allocated
zero; zero, positive and insufficient-history singletons; the gate independent of sleeve
size; the rank fallback restricted to gate-passers; the gate using the declared lookback)
and 6 tests in `tests/test_hierarchical_class_score_population.py` (a synthetic
cross-section in which the globally top-ranked members differ from the held members, the
class score equal to the mean of the held members' global scores, the class choice
following the held population, and the review's case in the real audit). Run with:

```
.venv\Scripts\python.exe -m pytest tests/test_balanced_momentum_gate.py tests/test_hierarchical_class_score_population.py tests/test_sleeve_construction.py tests/test_hierarchical_construction.py -q --no-header -p no:cacheprovider --basetemp=tmp\pytest
```

## Limitations

- **Post-hoc.** Proposed after P4.16's outcome was known; nothing here is out-of-sample
  evidence, and the 2021+ window was already inspected.
- **K was not chosen on evidence.** Both values are reported because selecting K=2 on this
  outcome would be tuning on the inspected sample; K=3's interval spans zero and K=2's
  family-adjusted p is 0.164.
- **Concentration is a new risk, not a solved one.** 2.91 names with two 45% positions is
  close to a two-asset portfolio; the 45% cap is what supplies the residual cash.
- **The class score is member-derived, not a class index.** A class-index momentum variant
  with its own lookback is a different, untested rule. The score is a class-ranking
  statistic: it averages the global-table scores of the members the within-sleeve reranking
  holds, so it tracks the held set but is not a weighted average of portfolio weights.
- **The population repair is decision-neutral on this sample.** It changes the scored
  members on 35 of 130 decisions and the class-score value on 36 class-day pairs, but never
  the chosen classes, so the corrected run cannot discriminate between the two populations
  on outcomes. The synthetic fixture in `tests/test_hierarchical_class_score_population.py`
  is the counterexample in which the choice does change.
- **The corrected root carries the frozen analysis module's own version label.** The v2
  root's `protocol.json` records `hierarchical-construction-v2`; `analysis.json` still
  carries the analysis module's `hierarchical-construction-v1` constant, and the module's
  HTML presentation hard-codes the v1 evidence links. The repair's write scope excluded
  that module, so no v2 report was rendered; the v2 root is read through its JSON evidence.
- **The CP contrasts carry the fallback difference** established in P4.16: CP has a
  defensive fallback and none of these arms do, so the HIER-versus-CP rows mix the
  construction difference with the exposure difference. The matched contrast is against POOL.
- **A reject is a research finding.** It does not deallocate, and switching remains an
  operator decision through the existing allocation workflow.
