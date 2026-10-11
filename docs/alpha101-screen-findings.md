# P4.17 — Alpha101 restricted time-series subset: the per-alpha screen

Registered 2026-10-10 in [the plan](signal-decay-and-alpha-plan.md), run 2026-10-11. The
question was whether the formulaic alphas that survive the data and structure filters add
incremental information at the selection layer. P4.17's acceptance put the cost test
**before any portfolio work**: every alpha must have a measured turnover and breakeven
ratio, and the report must say which alphas are rejected and why. This is that screen.

Evidence root `var/research/alpha101-screen-20261011-v1/` (protocol `7865c485…`), report
[`research/alpha101-screen-2026-10-11/index.html`](../research/alpha101-screen-2026-10-11/index.html).
Pre-registered: the family, the mapping, the information measure and the cost test were
frozen before the screen ran.

Research finding only. Nothing here changed a monitored strategy, an allocation, an
approval or a broker record.

## Verdict: none of the sixteen clears the gate — the family closes before any portfolio work

**15 of 16 are rejected and 1 cannot be judged; no alpha passes.** Twelve fail the cost test
alone, three fail both tests, and alpha 7 is not judged at all because it is a constant.

| Alpha | Coverage | Implied turnover | Annual cost | Breakeven IC | Observed IC (21) | IC margin | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| **21** | 70% | **7.62×** | **38.1bp** | 0.0061 | +0.0135 | 2.22× | reject — cost inside the ceiling, **information** fails |
| 24 | 100% | 10.34× | 51.7bp | 0.0083 | +0.0435 | 5.26× | reject — cost |
| 46 | 98% | 12.77× | 63.9bp | 0.0102 | +0.0355 | 3.49× | reject — cost |
| 23 | 98% | 13.41× | 67.0bp | 0.0107 | −0.0136 | −1.27× | reject — both |
| 6 | 100% | 13.74× | 68.7bp | 0.0110 | +0.0009 | 0.08× | reject — both |
| 54 | 100% | 13.93× | 69.7bp | 0.0111 | +0.0441 | 3.96× | reject — cost |
| 101 | 100% | 13.94× | 69.7bp | 0.0111 | −0.0749 | −6.73× | reject — both (inverted) |
| 49 | 100% | 13.99× | 70.0bp | 0.0112 | +0.0411 | 3.68× | reject — cost |
| 43 | 100% | 14.10× | 70.5bp | 0.0113 | +0.0196 | 1.74× | reject — both |
| 51 | 100% | 14.35× | 71.8bp | 0.0115 | +0.0325 | 2.84× | reject — both |
| 26 | 99% | 14.39× | 72.0bp | 0.0115 | +0.0572 | 4.98× | reject — cost |
| 9 | 100% | 14.56× | 72.8bp | 0.0116 | +0.0042 | 0.36× | reject — both |
| 53 | 100% | 14.94× | 74.7bp | 0.0119 | **+0.0747** | 6.26× | reject — cost |
| 12 | 100% | 15.11× | 75.5bp | 0.0121 | −0.0007 | −0.06× | reject — both |
| 35 | 100% | 15.29× | 76.5bp | 0.0122 | +0.0014 | 0.12× | reject — both |
| 7 | 0% | — | — | — | not measurable | — | not judged — degenerate |

Ceiling 44.0bp (the frozen 40bp plus the published 10% tolerance); cost at the frozen 5bp;
IC measured at 21 sessions, the decision horizon.

## The failure is turnover, not information

This is the finding worth carrying forward. Several of these alphas have genuinely positive
information at the decision horizon:

| Alpha | IC 1 | IC 5 | IC 10 | IC 21 | IC 63 | 95% interval (21 sessions) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **53** | +0.0546 | +0.0752 | +0.0899 | **+0.0747** | +0.0731 | [+0.0016, +0.1522] |
| **26** | −0.0089 | +0.0296 | +0.0679 | **+0.0572** | +0.0339 | [+0.0106, +0.1052] |
| 54 | +0.0098 | +0.0347 | +0.0453 | +0.0441 | +0.0111 | [−0.0241, +0.1100] |
| 24 | +0.0287 | +0.0545 | +0.0532 | +0.0435 | +0.0515 | [−0.0150, +0.1023] |
| 49 | +0.0497 | +0.0333 | +0.0496 | +0.0411 | +0.0383 | [−0.0275, +0.1058] |
| 51 | +0.0635 | +0.0148 | +0.0386 | +0.0325 | +0.0361 | [−0.0302, +0.0934] |
| 46 | +0.0871 | +0.0155 | +0.0153 | +0.0355 | +0.0240 | [−0.0220, +0.0899] |
| **101** | −0.0597 | −0.0723 | −0.0841 | **−0.0749** | −0.0526 | [−0.1313, −0.0140] |

Two alphas' 21-session intervals exclude zero positively (**53**, the negated nine-step
change of the high-low-close range ratio; and **26**, the negated three-day maximum of a
rolling correlation of volume and high ranks), and one excludes zero **negatively**:
**101**'s information is real and *inverted* — a long-only mapping of it is a short signal,
which is why its IC margin is −6.73×.

Against that, the mapping's own turnover is the whole story. The same family translated to
monthly decisions turns over **7.62×–15.29×** against the monitored book's 8.07×, costing
**38.1bp–76.5bp** against the 44.0bp ceiling. P4.15 rejected the *daily* archetypes by 5×,
14× and 46×; at the decision frequency this programme actually trades at, the gap is
1.0–1.9× — much narrower, but still binding for all but one alpha, and the binding mechanism
is top-six membership churn.

## Two disclosures

**The published formulas have a unit quirk, and it makes one alpha degenerate.** The paper
defines `adv{d}` as average daily *dollar* volume while `volume` is share volume, and three
registered alphas compare the two directly. Implemented verbatim — which the plan requires —
alpha 7's `adv20 < volume` condition never holds on this data, so it collapses to its
constant `-1` branch, and alphas 21 and 43 have their volume comparisons distorted by price
level. Alpha 7's degeneracy is reported, not repaired: a dollar-volume-consistent variant is
a *different*, separately declared family.

**A wiring defect was found by inspecting the first run, and fixed at the root.** The first
screen reported alpha 7 as **passing** with a 102.77× IC margin — a false pass of exactly the
kind the gate exists to prevent. The cause: alpha 7 has no measurable IC (a constant
cross-section has no dispersion), and the gate judges a candidate that declares no IC
against the programme reference IC. Two rules were added before publishing, and both are in
the frozen protocol: **a cross-section with fewer than two distinct values cannot rank, so it
forms no mapping**, and **a candidate with no measurable IC is reported *insufficient* and is
never judged against the programme reference IC**. The correction only reclassifies a
non-measurable candidate — it cannot manufacture a pass — and the corrected artifact is the
one published. Pre-correction run: 1 pass, 15 reject. Post-correction: 0 pass, 15 reject,
1 insufficient.

## What this means for the programme

1. **P4.17 closes here.** The plan's next step was conditional — *if anything survives, trade
   it as a bounded 5–10% satellite sleeve* — and nothing survives. There is no satellite, no
   model stage and no promotion, because the family cannot pay for its own turnover.
2. **The interesting result is the information, not the rejection.** Alpha 53 and 26 carry
   real monthly information with intervals excluding zero, and alpha 101 carries real
   *inverted* information. That is a new, specific fact about this universe, and it is the
   first evidence in the programme that a simple published formula has measurable forward
   rank IC here.
3. **Any follow-up must attack turnover, not signal quality.** A slower rebalance, hold bands
   that suppress membership churn, or use as a feature inside an already-slower mapping are
   all different, declared studies — and each must measure its turnover against the P4.15
   ceiling first, exactly as this screen did. Re-running this family at a lower decision
   frequency would be tuning on the inspected sample unless the frequency is fixed by
   something other than these outcomes.
4. **The gate earned its place.** It decided the item before a single replay, and it caught a
   false pass in its own wiring. P4.18 and P4.19 inherit it unchanged.

## Verification

22 focused tests in `tests/test_alpha101.py`: every implemented formula is compared
character-for-character with a hash-pinned extraction of the paper; the operators are checked
against their definitions and against missing-value behaviour; nine alphas have hand-computed
spot checks; **all sixteen are checked for window-boundedness**, so a value at one session
cannot depend on how much earlier history is supplied; the screen's point-in-time slicing is
checked on a synthetic calendar; and the frozen artifact is re-run and must reproduce
identically, with the pinned P4.16 inputs and the paper re-checked by hash. The screen
reproduced exactly on re-run and the formula extraction reported no mismatches.

## Limitations

- **One declared mapping.** A different slot count, weighting or rebalance rule would change
  the measured turnover; the mapping is the pooled control's construction with the alpha
  replacing its selection score, and nothing else.
- **Implied, not replayed, turnover.** The gate's mapping measure is calibrated to within
  3.5% of measured traded notional on the monitored strategy and is slightly conservative;
  this screen produces no replay, by design.
- **A short IC series.** 130 monthly decisions over an already-inspected window, so a single
  episode can dominate an interval; the interval is a block bootstrap, not a test of
  stability across regimes.
- **Missing observations stay missing.** Alphas 21, 23, 26, 46 and 43 are judged on the
  decisions where their windows were available, and their coverage is reported beside every
  result.
- **No economics.** No portfolio result exists for any alpha, so nothing here speaks to
  drawdown, capacity or interaction with the existing overlays.
- **Not out-of-sample.** The window and the fourteen-instrument universe were inspected by
  the P4.13–P4.16 studies.
