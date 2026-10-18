> **Policy correction — October 17, 2026.** The annual cost ceiling is retired. Historical gate failures below are not net-performance verdicts. See the [audit and reopened studies](research-cost-policy-review-2026-10-17.md). The [original report](../research/cash-relative-momentum-20261017-v1/findings-original.md) retains the text covered by the original receipt.

# Cash-relative momentum — October 17, 2026

**All 16 mappings fail the unchanged cost gate.** The class-first cash-relative
monthly rule clears the heuristic information margin at **3.59x**, but its implied
annual cost is **45.66 bp**, above the frozen **44 bp** ceiling. It is a near miss,
not an admitted strategy. No portfolio replay, monitoring or trading change follows.

![Cost admission and paired static excess payoff](../research/cash-relative-momentum-20261017-v1/screen.png)

## Hypothesis and matched controls

The previous normalized rule gave BIL a high score because positive carry was
divided by very low volatility. This follow-up asks whether comparing each risky
ETF's momentum with bill carry adds information **beyond simply removing BIL**.
The user requested continuation after that result. The hypothesis is informed by
inspected historical evidence; it is not an untouched out-of-sample discovery.

- Control: exclude BIL from position selection; retain `126-session return / 63-session volatility`.
- Candidate: exclude BIL; rank `(ETF 126-session return − BIL 126-session return) / ETF 63-session volatility`.
- Both retain the positive **raw** momentum gate. The candidate also requires
  positive excess momentum. A negative ETF return cannot qualify merely because
  BIL performed worse. Unsupported reference history stops the calculation.
- Run each with pooled six-name and class-first three-class/two-name selection,
  using monthly and 0.10/0.40/0.80 target-change adoption. All sizing, class/overlap
  rules, liquidity, duplicate handling, 45% cap and unfilled-slot cash are inherited.
- All 50 supported histories remain inputs: 49 can compete for positions and BIL
  supplies the reference. BIL receives zero target by design. Unused budgets stay
  literal cash; BIL's return is not assumed to be paid on that cash.

The 52-candidate first wave, BWX/CPER exclusions and published price batch are
unchanged. The actual published histories were re-read and hash-checked before
freezing; they reproduce the parent pool exactly. Inputs end October 12, 2026;
signals use only prior sessions. Adjusted prices supply returns, audited raw
prices/volume supply liquidity. The two normalized parent strategies also
reproduce all **1,450 daily targets each** exactly under the inherited code.

## Primary screen

The 2021–2024 calibration gate is unchanged: 44 bp annual implied cost and a 3x
candidate IC/breakeven margin. The label remains 21-session adjusted open-to-open
return over the same full admissible pool, including zero-weight BIL. No switch
to a more favorable latent-score IC or reduced cost threshold is permitted.

| Monthly mapping | Implied annual cost, bp | Calibration mapping IC | IC margin | 2025+ mapping IC |
| --- | ---: | ---: | ---: | ---: |
| Pooled / remove BIL | 50.19 | +0.01023 | 1.28x | -0.03406 |
| Pooled / cash-relative | 51.71 | +0.00958 | 1.16x | +0.01700 |
| Class-first / remove BIL | 45.36 | +0.01503 | 2.08x | -0.04467 |
| Class-first / cash-relative | 45.66 | +0.02606 | 3.59x | +0.02639 |

The cash-relative class rule's margin is a useful improvement over its removal-only
control, but its cost is **1.66 bp above the ceiling**, and all calibration mapping
IC family intervals still include zero. Clearing the heuristic margin is not
statistical confirmation. Removing BIL alone also fails. The prior low-cost bill
concentration was therefore not a free source of affordable risky-asset selection.

| Mapping | Monthly | Threshold 0.10 | Threshold 0.40 | Threshold 0.80 |
| --- | ---: | ---: | ---: | ---: |
| Pooled / remove BIL | 50.19 | 296.21 | 228.29 | 148.15 |
| Pooled / cash-relative | 51.71 | 333.46 | 260.63 | 155.55 |
| Class-first / remove BIL | 45.36 | 252.00 | 192.97 | 116.31 |
| Class-first / cash-relative | 45.66 | 243.08 | 184.93 | 108.46 |

Every dynamic variant fails; the cheapest is 108.46 bp annually. All policies
still adopt at monthly anchors, so monthly IC is shared within each arm. These
are security-target-change costs, including initial establishment, not measured
fill turnover or realized fees. No conclusions about net Sharpe, drawdown or
execution-delay performance are inferred from these rejected screens.

## Incremental payoff and horizon diagnostics

Subtracting the same future BIL return from every ETF return leaves cross-sectional
ranks unchanged. The implementation verifies that identity. Excess-return rank IC
is therefore not counted as a second discovery. Selection-score IC is reported
separately and never substitutes for the final-weight mapping gate.

The independently registered payoff diagnostic is the static sum of target
weights times ETF forward returns **in excess of BIL**, candidate minus the matched
removal-only control. It is a BIL-financed, zero-cost forward contribution, not
account PnL, actual idle-cash return or a path-dependent portfolio backtest.

| Window | Construction | Monthly observations | Mean 21-session incremental payoff, bp | 95% family interval, 6-month blocks |
| --- | --- | ---: | ---: | --- |
| calibration | pooled | 47 | +6.79 | [-20.84, +39.81] |
| calibration | class | 47 | +4.80 | [-21.16, +38.14] |
| later | pooled | 21 | +97.69 | [+9.05, +180.93] |
| later | class | 21 | +62.57 | [-12.40, +124.47] |

The pooled later-period contrast is positive under the registered family interval,
but it is already-inspected, before-cost evidence. Its candidate also averages
95.45% invested versus 83.33% for the removal-only control; exposure differs by
12.12 percentage points. The interval cannot establish exposure-matched alpha.
The class-first contrast's interval includes zero in both periods. Neither later
diagnostic can rescue the calibration gate failure.

All four horizons were declared before results; 21 sessions remains primary.
The entries below are per-horizon static payoff differences, **not annualized**.
All eight contrasts and 3/6/12-month-block intervals are retained in the summary.

| Horizon, sessions | Calibration pooled, bp | Calibration class, bp | Later pooled, bp | Later class, bp |
| --- | ---: | ---: | ---: | ---: |
| 1 | -7.19 | -2.02 | -0.31 | +12.01 |
| 5 | -0.89 | -0.12 | +12.98 | +15.44 |
| 10 | +5.66 | +6.40 | +69.02 | +35.52 |
| 21 | +6.79 | +4.80 | +97.69 | +62.57 |

The early versus later horizon pattern is descriptive. No best holding period,
exit threshold or delayed-entry rule is selected from it.

## Comparable-class coverage

The inherited primary classes are conditioning groups, not proof of homogeneous
economic payoffs. A valid within-class observation needs at least three admissible
risky names and nonconstant weights/returns; a class summary needs twelve valid
months. Most classes cannot support it. For the cash-relative class-first rule,
only **two of 23 non-bill classes** have sufficient calibration coverage and only
**one** has sufficient later coverage. No broad peer-relative alpha claim follows.

Entries below are valid months / mean mapping IC; insufficient means unavailable,
not zero information. This is the primary 21-session horizon for the two candidates.

| Class | Calibration pooled | Calibration class-first | Later pooled | Later class-first |
| --- | --- | --- | --- | --- |
| aggregate_us | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| bills_us | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| commodity_agriculture | 2 / insufficient | 2 / insufficient | 1 / insufficient | 0 / insufficient |
| commodity_base_metals | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| commodity_broad_parent | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| commodity_precious | 12 / +0.0305 | 10 / insufficient | 12 / +0.2917 | 8 / insufficient |
| credit_emerging_local | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| credit_emerging_usd | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| credit_ex_us_unhedged | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| credit_usd_high_yield | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| credit_usd_investment_grade | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_asia_ex_china | 29 / -0.1200 | 21 / +0.0201 | 16 / +0.2925 | 10 / insufficient |
| equity_australia | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_canada | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_china | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_developed_ex_us_parent | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_emerging_parent | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_europe | 18 / -0.1186 | 10 / insufficient | 9 / insufficient | 6 / insufficient |
| equity_hong_kong | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| equity_us | 45 / +0.0330 | 45 / +0.0359 | 19 / -0.0557 | 16 / -0.0323 |
| inflation_linked_us | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| securitized_us | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| sovereign_developed_ex_us | 0 / insufficient | 0 / insufficient | 0 / insufficient | 0 / insufficient |
| sovereign_us | 1 / insufficient | 1 / insufficient | 1 / insufficient | 0 / insufficient |

## Verification, evidence and next boundary

**72 focused tests passed**, including cash-reference failure, subtraction
before risk division, preserved absolute gates, matched-control equivalence,
common-return rank invariance, label boundaries, static payoff arithmetic and the
prospective calendar. Ruff passes. Independent checks reproduce **5,800 target
vectors, 165,674 member scores, 16 adoption policies, 5,698 adoptions, 128 turnover
windows, 1,108 forward rows, 26,592 class rows and 554 paired payoff observations**.
All target turnover attribution reconciles. The frozen parent helper is unchanged;
both original normalized controls reproduce exactly. No app calculation source or
operational process was changed.

The [registration](../research/cash-relative-momentum-20261017-v1/registration.json)
was frozen before results; the [full protocol](../research/cash-relative-momentum-20261017-v1/protocol.json),
[compact summary and all diagnostic intervals](../research/cash-relative-momentum-20261017-v1/summary.json),
[all-policy constituent attribution](../research/cash-relative-momentum-20261017-v1/attribution.json)
and [hash receipt](../research/cash-relative-momentum-20261017-v1/receipt.json) are retained.
Large immutable inputs, targets, event ledgers and diagnostics live in
`var/research/cash-relative-momentum-20261017-v1/`.

The registered prospective design reserves 126 application-calendar decision
sessions from **October 19, 2026 through April 20, 2027**, with final 21-session
labels due **May 19, 2027**, subject to actual session/publication availability.
It is **inactive**, because no mapping passed. It contains no future evidence,
does not constitute a powered alpha test by itself and creates no agent schedule,
automation, app monitoring or execution authority. Any later eligible strategy
must be frozen and calculated through the app's services before observation.

**Decision:** reject this declared family at the gate and review the near miss.
The binding issue for class-first cash-relative selection is cost, with weak
statistical and peer-coverage support still unresolved. The next useful decision
is whether to register an explicit turnover/cost mechanism with the signal fixed;
do not lower the ceiling, pick a favorable horizon or retune this grid after seeing
the result. Actual turnover, net Sharpe, return/drawdown guards, 5/10/20 bp costs,
execution delays, exposure-matched controls, original FR25/URTH benchmarks and
native parity remain mandatory before any surviving future mapping qualifies.

Current-survivor membership, historical mandates/classifications and historical
publication vintages remain uncertified. No provider archive, new online price,
FX or macro input was used. No strategy, funding, broker or live-routing setting
changed. The earlier expanded-FR25 and class/volatility rejections remain intact.
