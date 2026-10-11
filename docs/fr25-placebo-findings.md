# P4.14 Part B — FR25 placebo rank, data-through-2022 refit and sensitivity

Findings for the second half of the FR25 robustness stress, run as **its own frozen
study** in its own evidence root, `var/research/fr25-placebo-20261010-v1/`
(protocol SHA-256 `429ec002…`). Completed 2026-10-10. The retention tolerance was
frozen in [the plan](signal-decay-and-alpha-plan.md) **before** any statistic on
this page was computed, and the Part B protocol was frozen the same day before any
Part B outcome existed.

Part A ([findings](fr25-robustness-findings.md)) analysed the published
selection-blend evidence and returned *inconclusive*. Part B could not be
evaluated from those artifacts, because each perturbation changes which assets were
selected and therefore the realised path — so every arm here is replayed.

Research finding only. Nothing here changed a monitored strategy, an allocation, an
approval or a broker record, and a reject would not by itself deallocate.

## Verdict: the placebo check passes; retention does not

| Frozen check | Result |
| --- | --- |
| Excess over CP positive in ≥ 2/3 of complete calendar years | **pass** — 4 of 5 (80%) |
| Positive after dropping any single changed selection | **pass** — worst tile −1.50% |
| Positive 95% bootstrap lower bound at the 6-month block | **fail** — [−0.12%, +2.51%] |
| Above the 90th percentile of the matched-availability placebo distribution | **pass** — 96.50th percentile |

**Retention verdict: not preserved.** Retention requires all four checks, the
interval test failed in Part A, and Part B may not rescue a failed interval test.
`preserve` was therefore unreachable before this study ran, and nothing here
changes that. The reachable verdict is **inconclusive** — under the declared
mapping *and* under the plan's literal sentence, which happen to agree on this
evidence.

### The verdict sentence in the plan is ambiguous, and both readings are reported

The plan's tolerance is unambiguous (all four checks). Its verdict sentence —
"otherwise **reject**, or **inconclusive** when the point estimate is positive but
the interval spans zero and the concentration tests pass" — describes the
noise-limited case. A failed placebo is not noise-limited: it is positive evidence
that the assignment carries nothing. The plan also says Part B "can only move the
verdict between preserve and inconclusive".

| Reading | Placebo fails | Placebo passes (this study) |
| --- | --- | --- |
| Declared mapping: a failed placebo is a mechanism rejection | reject | inconclusive |
| Plan's literal sentence: a failed placebo is still noise-limited | inconclusive | inconclusive |

Both are reported rather than resolved silently. The retention verdict ("not
preserved") is identical under either, so no threshold was revised after seeing
results — only an ambiguity that was documented in the frozen protocol before the
run.

## What the placebo establishes

At each of the 70 evaluation decisions the frozen financial-ridge **forecast
values** were permuted across the fourteen available symbols and injected through
the engine's own `SelectionBlend` path, so eligibility, the positive-momentum gate,
the top-six selection, the defensive fallback and every downstream sizing overlay
are the engine's own code. A placebo differs from FR25 in exactly one respect: the
assignment of ridge information.

FR25's evaluation excess over CP is **+105.98% against +93.98%, +12.00pp**
(+6.0008 in log terms). In 200 declared draws:

| Distribution | log excess (pp) | ratio equivalent |
| --- | ---: | ---: |
| **FR25 observed** | **+6.001** | **+6.18%** |
| 90th percentile (frozen hurdle) | +4.095 | +4.18% |
| Median draw | −0.261 | −0.26% |
| Mean draw | −0.288 | −0.29% |
| Best draw (#195) | +8.252 | +8.60% |
| Worst draw (#192) | −10.300 | −9.79% |
| Standard deviation | 3.313 | — |
| Share of draws above zero | 45.0% | — |

FR25 sits at the **96.50th percentile**, ranked 194 of 200, and **seven random
assignments beat it** (draws 195, 158, 38, 101, 200, 12, 150 — +6.08 to +8.25 log
points). Every draw, its permutation, its injected assignment and its realised rank
table are retained as evidence, including the seven that win.

**What this does establish.** A random re-assignment of the same ridge information
is typically slightly *worse* than doing nothing (median −0.26pp, only 45% of draws
above zero), while FR25 clears the 90th percentile. So the ridge's rank assignment
does carry information: it is not true that any perturbation of the M1 ordering
does as well. That is the decisive question the plan asked this test to settle, and
the answer is yes — weakly.

**What it does not establish.** Beating the 90th percentile of a wide distribution
is a weak claim. The draws span ±8–10pp around zero, so the placebo distribution is
dominated by selection noise, and FR25's +6.00pp is inside the range that random
re-selection produces. The claim is "better than a random assignment", not "better
than noise", and the frozen interval test is what measures the latter — and fails.

**The positive tail comes from churn, not from information.** The seven drawing
assignments that beat FR25 differ from CP on about **23 of 70 decisions** on
average, against FR25's **13**; the seven weakest differ on about **25**. Draws that
re-order selection aggressively get both the best and the worst outcomes. FR25's
placement in the distribution is therefore a statement about the ridge ordering, not
about the recipe being well-tuned.

## The data-through-2022 refit: about 60% of the recent edge survives

The financial ridge was refitted on the **83** training labels completed by
2022-12-31 (the last ending 2022-12-01) and replayed from 2023-01-03. All three arms
start from identical fresh cash on the first 2023 decision, so the comparison is
like-for-like rather than a continuation of a path the refit could not have traded.
Only the ridge training sample changed; momentum and XGBoost are untouched.

| Arm | CAGR | Sharpe | Calmar | Max DD | Total return | Excess vs CP | Log excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CP | 15.18% | 1.367 | 1.828 | −8.31% | +71.40% | — | — |
| FR25 (full-sample fit) | 16.42% | 1.447 | 1.897 | −8.66% | +78.45% | **+7.06pp** | +4.034 |
| **Data-through-2022 refit** | 15.93% | 1.399 | **1.917** | **−8.31%** | +75.60% | **+4.20pp** | +2.423 |

**A ridge that never saw a post-2022 label still beats CP by +4.20pp on the 2023+
window — 59.6% of FR25's +7.06pp — with a lower maximum drawdown (−8.31% against
−8.66%) and a slightly better Calmar (1.917 against 1.897).** So the recent edge is
neither purely full-sample fitting nor unaffected by it: roughly 40% of FR25's
2023-onward advantage depends on labels that only exist because the model was fitted
with hindsight.

The refit changes **13 of 46** selections against FR25, with a mean ridge-rank
correlation of **0.709** and a mean absolute rank gap of **0.346** — the refit is a
genuine perturbation of the ridge ordering, not a cosmetic one.

**Why this is a re-fit and not an approximation.** The parent protocol preserved
every training row and every decision-time query vector inside `macro.json`, so the
refit is computed from frozen evidence. Refitting on the parent's own frozen
training rows reproduces the published forecasts **exactly** (worst absolute
difference 0.0 across all fourteen symbols at every checked decision), which is the
property that makes the subset refit trustworthy. At the first 2023 decision the
two samples coincide — 83 rows each — because no label completed after 2022-12-31
can exist yet; that coincidence is reported rather than treated as a failure, and
by 2024-01-02 all fourteen forecasts differ.

## The sensitivity surface: no stable winner, and the frozen cell is not the best

Slots 4/5/6/7 and ridge weights 10/25/40%, on the same frozen rank tables, over the
same evaluation window. This is **not** a search: the plan registered these as the
axes the parent study already varied, and none of it is out-of-sample evidence.

Excess over CP, percentage points of total return (CP: CAGR 11.92%, Sharpe 1.106,
Calmar 1.435):

| Slots | 10% ridge | 25% ridge | 40% ridge |
| --- | ---: | ---: | ---: |
| Top 4 | +17.03 | +27.91 | +32.17 |
| Top 5 | +17.08 | +21.78 | +18.19 |
| Top 6 | +4.15 | **+12.00 (FR25)** | +6.40 |
| Top 7 | −3.90 | −2.42 | +0.63 |

Sharpe change against CP across the same surface is small everywhere (+0.03 to
+0.08, with Top 4 · 10% at −0.04), and the high-CAGR corner carries materially worse
risk:

| Configuration | CAGR | Sharpe | Calmar | Max DD | Excess vs CP | Decisions differing from CP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 4 · 40% | 14.95% | 1.185 | 1.408 | **−10.62%** | +32.17pp | 59 |
| Top 4 · 25% | 14.55% | 1.141 | 1.176 | **−12.38%** | +27.91pp | 59 |
| Top 5 · 25% | 14.00% | 1.177 | **1.643** | −8.53% | +21.78pp | 56 |
| **Top 6 · 25% (FR25)** | 13.09% | **1.193** | 1.512 | −8.66% | +12.00pp | 13 |
| Top 6 · 10% | 12.33% | 1.138 | 1.484 | −8.31% | +4.15pp | 2 |
| Top 7 · 25% | 11.66% | 1.151 | 1.426 | −8.18% | −2.42pp | 55 |

Three things are worth stating plainly.

1. **FR25 is not the best cell, and no cell is uniformly better.** Top 4 with 40%
   ridge weight has the largest excess but a −10.62% drawdown and a Calmar below
   CP's; Top 5 · 25% has a better Calmar than FR25 and a slightly worse Sharpe; Top
   7 is neutral to negative. There is no configuration that dominates on return and
   risk together.
2. **The surface is not monotone in the ridge weight**, which is what a genuine
   dose-response relationship would look like. At six slots, 10% · 25% · 40% gives
   +4.15 · +12.00 · +6.40pp with 2 · 13 · 31 changed decisions. The middle weight
   producing the largest excess, with a third of the 40% arm's changes, is the
   signature of path luck rather than signal strength.
3. **The corner is not promotable, and that is a protocol statement, not a taste.**
   Picking Top 4 · 40% because it has the largest excess would be selecting a
   parameter on the inspected sample, with a worse drawdown, a Calmar below the
   control's, and no family-adjusted evidence. The frozen plan forbids presenting
   the surface as a search, and this study does not.

The surface therefore neither privileges FR25 nor reveals a robust improvement on
it. That is itself the robustness answer: on these axes the recipe's advantage is
not stable to small changes in the axes it was chosen on.

## What makes these numbers trustworthy

| Bridge | Result |
| --- | --- |
| FR25 re-derived in this root (engine path) | 70 of 70 decisions identical to the parent's published decisions |
| Identity-assignment sentinel (injection path) | 70 of 70 identical to the parent's published decisions |
| N6W25 re-derived from the frozen rank tables | 70 of 70 identical to the parent's published decisions |
| CP, FR25 and M1 control replays | terminal NAV, CAGR, Sharpe and max drawdown identical to the parent's published replays (1e-12) |
| Randomisation | 14,000 recorded injections recomputed from the declared seed and re-checked against the frozen marginal |
| Injection round trip | at every one of the 14,000 (draw, decision) pairs the engine's realised ridge rank equals the permuted frozen rank exactly |
| Abstention preserved | 0 of 70 evaluation decisions abstained; no placebo point is ever injected where FR25 had no ridge |
| Refit machinery | refitting on the frozen training rows reproduces the published forecasts with worst difference 0.0 |
| Changed-selection cross-check | the changed-decision count re-derived here is 13, matching the published Part A finding |

The identity sentinel is a declared verification arm, not a draw, and is excluded
from the distribution. Three independent routes — the macro path, the injection
path, and the frozen rank table with a re-derived weight registry — reproduce the
same 70 decisions, which is what rules out the placebo being an artefact of the
harness rather than of the assignment.

**Native LEAN parity is inherited, not re-run.** The reference engine used here is
the one the parent study validated against native LEAN runs on the identical FR25
and CP paths, and the sentinel above ties this study's arms to that engine's
outputs exactly. This study submitted no new native runs; the environment's Docker
access is confined, and the plan's Part B acceptance does not require them. That
limitation is recorded rather than glossed.

## Limitations

- **Nothing here is out-of-sample evidence.** The evaluation window was already
  inspected when FR25 was chosen, and the sensitivity surface re-uses axes the
  parent study varied.
- **The placebo tests the ridge's ranking information, not the ridge family.** A
  permutation preserves availability, the marginal distribution and the health of
  the downstream sizing chain. A different ridge specification is not tested.
- **The refit re-fits one stage.** Momentum and XGBoost are unchanged, and the refit
  path starts from fresh cash in 2023 rather than continuing the evaluation path, so
  the +4.20pp is a 2023-onward statement, not a full-evaluation-window one.
- **The 2023+ window is short** (46 decisions) and overlaps the period Part A found
  to be FR25's strongest. The refit result should be read as "the edge is partly
  robust", not as an independent confirmation.
- **Permutation placebos understate the alternative.** A random assignment can
  produce far more selection churn than FR25 does, which inflates the tails; a
  placebo matched on churn would be a different, and stricter, test.
- **A passing placebo is not superiority.** Seven of 200 random assignments beat
  FR25 outright, and the frozen interval test still spans zero.

## Consequence for FR25

FR25 stays a **monitored research lead**, not promotion evidence. Its selection
mechanism now has a positive answer to "does the ridge rank contribute at all?"
(96.50th percentile of a matched-availability placebo distribution) alongside a
negative answer to "is the advantage distinguishable from noise at the frozen
tolerance?" (6-month interval [−0.12%, +2.51%]). Both are true, and the second is
the one that governs retention.

No re-tuning of FR25, no change to monitoring, allocation, funding, approval or the
45% cap, and no allocation decision follows from this page. Switching or
deallocating remains an operator decision through the existing allocation workflow.

## Verification

39 focused tests in `tests/test_fr25_placebo.py` cover the declared randomisation
(per-draw and per-decision independence, reproducibility, seed), the injection
invariants (marginal preservation, exact realisation of the permuted rank, identity
sentinel, abstained days, partially populated rank tables), refit determinism and
its minimum-sample and cutoff rules, evidence verification (tampered permutation,
tampered injection, injection on an abstained day, changed seed), the resumable
economics contract, the frozen decision bridges, the percentile and tie arithmetic,
and every branch of the verdict mapping. Ruff passes; the study re-verifies its own
14,000 injections and three decision bridges from the frozen evidence root.

Two faults were found by running the study rather than by reading it: the decision
calendar was initially conflated with the underlying session calendar (1,448 days
instead of 70 decisions), and the first version of the refit sanity check demanded
that the data-through-2022 subset differ from the full sample at the first 2023
decision, where the two samples are necessarily identical. A third defect — the
engine reproduces injected rank values through its own `_rank_metric`, so the
round-trip check must compare ranks with ranks, not values with ranks — was caught
by the same invariant assertion.
