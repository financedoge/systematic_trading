# P4.14 Part A — FR25 robustness attribution

Findings for the FR25 robustness stress, Part A: analysis of the published
selection-blend evidence with **no portfolio re-run**. Completed 2026-10-10.
The retention tolerance applied here was frozen in
[the plan](signal-decay-and-alpha-plan.md) **before** any statistic on this page
was computed.

Research finding only. Nothing here changed a monitored strategy, an allocation,
an approval or a broker record, and a reject would not by itself deallocate.

## Verdict: inconclusive

| Frozen check | Result |
| --- | --- |
| Excess over CP positive in ≥ 2/3 of complete calendar years | **pass** — 4 of 5 (80%) |
| Positive after dropping any single changed selection | **pass** — worst tile −1.50% |
| Positive 95% bootstrap lower bound at the 6-month block | **fail** — [−0.12%, +2.51%] |
| Above the 90th percentile of a placebo distribution | **not run** (Part B) |

Because the interval spans zero and no placebo comparison exists, the item
**cannot be reported as preserved**. Absence of a placebo result is not evidence
in FR25's favour.

## Reference pair

FR25 versus **CP** (the capped-M1 control), evaluation window 2021-01-04 to
2026-10-08, 5bp, zero delay — 1,448 sessions, 70 decisions, read from
`var/research/selection-blend-20261010-v1/python/` with input and protocol hashes
recorded in the output.

FR25 returned **+105.98%** against CP's **+93.98%**: a difference of **+12.00
percentage points**, or +0.0600 in log terms.

## The mechanism does what it claims

This is the most useful positive result. Tiling the window at the 13 changed
selections — each tile running from a changed decision to the next changed
decision, so it contains that selection's full downstream footprint — **the
changed tiles account for +0.0576 of the +0.0600 total, i.e. 96%.** Only +0.0024
arises before the first changed selection.

So FR25's advantage is not coming from somewhere else in the sample. It is
attributable to the substitutions the recipe makes, which is what the recipe is
for.

**Why tiles and not months.** A changed selection alters share counts and cash,
and that difference persists and compounds through later intervals even after the
two arms realign their target weights. A single-month interval would capture only
the direct effect and would attribute the carry-over to periods where both arms
held identical targets. A first pass using monthly intervals reported the changed
selections as only 5% of the total — an artefact of that framing, not a finding.
The tiled decomposition is exact and additive in log terms.

## But the edge is concentrated

| Measure | Value |
| --- | ---: |
| Changed selections | 13 of 70 |
| Tiles with a positive contribution | 10 of 13 |
| Largest single tile, share of the changed total | **31.3%** |
| Top three tiles, share of the changed total | **79.3%** |
| Best calendar year (2026, partial), share of the difference | **37.5%** |

Every tile, in time order:

| Selection | Runs to | Sessions | Log difference | Added | Removed |
| --- | --- | ---: | ---: | --- | --- |
| 2021-06-01 | 2021-10-01 | 85 | +0.0095 | SPY | DBC, EWH, GLD, VGK, XLB, XLE |
| 2021-10-01 | 2021-11-01 | 20 | +0.0121 | DBC, EWJ, HYG | IEF |
| 2021-11-01 | 2023-05-01 | 374 | +0.0014 | HYG | DBC, SPY, TLT, VGK, XLB, XLE |
| 2023-05-01 | 2023-06-01 | 21 | −0.0023 | EWJ, GLD, SPY | LQD |
| 2023-06-01 | 2023-09-01 | 63 | +0.0016 | EWJ, EWY, GLD | HYG |
| 2023-09-01 | 2024-01-02 | 82 | −0.0013 | DBC, EWJ, HYG | LQD |
| 2024-01-02 | 2024-02-01 | 20 | +0.0098 | EWJ | EWY, GLD, HYG, SPY, VGK, XLB |
| 2024-02-01 | 2024-10-01 | 166 | +0.0039 | EWJ, HYG, LQD | IEF |
| **2024-10-01** | **2024-12-02** | **42** | **−0.0150** | EWH, GLD, LQD | HYG |
| 2024-12-02 | 2025-08-01 | 164 | +0.0025 | GLD | EWH, MCHI, SPY, TLT, XLE |
| 2025-08-01 | 2026-07-01 | 228 | +0.0020 | EWH, EWJ, EWY | VGK |
| **2026-07-01** | **2026-08-03** | **21** | **+0.0180** | EWJ, EWY, SPY | TLT |
| **2026-08-03** | **2026-10-08** | **47** | **+0.0156** | DBC, EWJ, EWY | HYG |

Two tiles dominate. The 2026 pair together contribute +0.0336, which is 58% of
the changed total, and both fall inside the partial final year. Against that, the
October 2024 substitution into EWH/GLD/LQD and out of HYG is the single largest
tile in absolute terms and it **lost** 1.50 log points.

That is the same concentration the selection study already disclosed, now visible
per substitution rather than as a summary statistic.

## Calendar years

| Year | Complete | FR25 | CP | Excess |
| --- | --- | ---: | ---: | ---: |
| 2021 | yes | +12.55% | +10.35% | **+2.20%** |
| 2022 | yes | +3.70% | +3.70% | +0.0006% |
| 2023 | yes | +9.57% | +9.84% | −0.28% |
| 2024 | yes | +5.53% | +5.22% | +0.32% |
| 2025 | yes | +24.16% | +23.90% | +0.26% |
| 2026 | **no** | +23.43% | +18.94% | **+4.49%** |

The complete years pass the two-thirds test at 4 of 5, but note how thin three of
them are: 2022 is a rounding error, and 2023 is negative. Outside 2021 and the
partial 2026, FR25 and CP are effectively the same portfolio.

## Bootstrap

Monthly FR25-minus-CP differences, circular block bootstrap, 20,000 draws:

| Block | n | Mean annualised | 95% interval | p |
| ---: | ---: | ---: | --- | ---: |
| 3 months | 69 | +1.06% | [−0.10%, +2.51%] | 0.105 |
| 6 months | 69 | +1.06% | [−0.12%, +2.51%] | 0.112 |
| 12 months | 69 | +1.06% | [−0.13%, +2.49%] | 0.115 |

The point estimate is positive at every block length and the interval is *nearly*
positive — but nearly is the honest word. The frozen tolerance required a
positive lower bound and it is not met.

## What Part B still has to answer

Three perturbations cannot be evaluated from published artifacts, because each
changes which assets were selected and therefore the realised path. They need
their own frozen study:

1. **Matched-availability placebo rank** — the decisive test of whether the
   financial ridge contributes at all, or whether any perturbation of the M1
   ordering does as well. Until this runs, the item is capped at *inconclusive*.
2. **Data-through-2022 refit** — whether the 2026 concentration is an artefact of
   fitting on the full sample.
3. **Top-N and financial-weight sensitivity** — the same axes the study already
   varied, so it cannot be presented as fresh out-of-sample evidence.

## Limitations

- This is an attribution of the realised path, not a counterfactual re-run.
  Dropping a tile removes its realised difference; it does not re-simulate what
  the portfolio would have held instead.
- **The attribution is path-dependent.** A small changed-tile total would have
  meant the effect works through the position path, not that selections do not
  matter. Read the tile table as "when did the difference accumulate", not as "how
  much did this decision cause".
- Log differences telescope exactly; reading them as percentage points is an
  approximation.
- The evaluation window was already inspected when FR25 was chosen. Nothing here
  is out-of-sample evidence.
- A year counts as complete only when the window reaches its end, so the strong
  partial 2026 is reported but excluded from the retention test.

## Verification

15 focused tests in `tests/test_fr25_robustness.py` cover changed-selection
detection and calendar mismatch rejection, complete-versus-partial year handling,
tile disjointness and exact telescoping, the one-session fill alignment, month-end
differencing, every verdict branch including the guarantee that a full *preserve*
is impossible without the placebo, input-hash recording, and rejection of an
incomplete replay. Ruff passes.

Two faults were found and fixed by running the analysis rather than by reading it:
the completeness test originally treated the partial final year as complete
(which would have let a strong stub year carry the verdict), and the tile
boundaries were mis-assigned so that the changed selections appeared to explain
only 5% of the difference instead of 96%.
