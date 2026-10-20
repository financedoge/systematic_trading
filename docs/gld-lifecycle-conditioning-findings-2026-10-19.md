# Two-era stable life-cycle signals as an FR25/M1 eligibility filter

2026-10-19. Research only; no strategy monitoring, allocation, funding, promotion or
broker authority changed. This follows the operator's request to (a) deepen the per-ETF
fit with an explicit pre-2023 two-era stability requirement, (b) use the fitted life-cycle
state only as an active/inactive eligibility filter on FR25/M1 while momentum keeps ranking,
(c) fit the event threshold on pre-2023 data only, and (d) retest net Sharpe/return/drawdown,
turnover, costs and delay against matched controls.

- [Full report](../research/gld-lifecycle-conditioning-20261019-v1/index.html)
- Frozen root: `var/research/gld-lifecycle-conditioning-20261019-v1`
- Code: `scripts/run_gld_lifecycle_conditioning.py`,
  `scripts/build_gld_lifecycle_conditioning_report.py`
- Inputs: frozen 52-ETF v2 panel, FR25/M1/EW/URTH frozen paths, scanner-study Rule A
  short-only daily NAV

## (a) Deeper per-ETF refit with two-era stability

Pre-2023 only, both structural domains: 300 random bounded vectors per domain + the sealed
GLD vector + 60 anchor mutations; candidates screened by the **worse** of the 2005-2015 and
2016-2022 eras; the top 20 replayed at 5/10/20bp and +1 session delay. Stability requires
positive fitness in both eras, at least 2 closed trades per era, at least 8 total and at
least 10% exposure. Result: **25/52 short-range and 9/52 long-range sleeves pass**
(2 transfer fallbacks each). The long-range domain is the harder case: 126-756-session
ranges need long histories and the two eras have different regimes. Full per-asset era
fits, trades and IS diagnostics are in the report.

## (b) Eligibility filter on FR25/M1

At each monthly FR25/M1 decision, names without a stable life-cycle signal at that close are
removed; the remaining names keep their FR25 relative weights. Two variants: **renormalise**
(the remaining names are rescaled to the 98% budget) and **cash** (removed weight simply stays
in cash). The matched control removes the **same number of names at random** at each
rebalance, so the test separates life-cycle information from merely holding fewer names.

FR25, 2023-01-03 to 2026-10-12, 5bp, next-open fills:

| Scenario | CAGR | Sharpe | Max DD | Calmar | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Frozen FR25 SOTA** | **16.75%** | **1.469** | **−8.65%** | **1.935** | — |
| FR25 + union filter, renormalised | 15.79% | 1.302 | −8.82% | 1.79 | 9.9x |
| FR25 + union filter, removed weight in cash | 12.94% | 1.275 | −7.78% | 1.66 | 7.9x |
| FR25 + short-only filter, renormalised | 13.15% | 1.035 | −11.77% | 1.12 | 10.8x |
| FR25 + long-only filter, renormalised | 15.22% | 1.137 | −10.79% | 1.41 | 10.4x |
| Matched random filter, seed 7 | 18.60% | 1.436 | −10.76% | 1.73 | 12.4x |
| Matched random filter, seed 11 | 15.00% | 1.308 | −8.87% | 1.69 | 12.1x |
| Matched random filter, seed 23 | 16.32% | 1.394 | −8.55% | 1.91 | 12.4x |

The life-cycle filter **does not beat frozen FR25**, and it sits at or below the matched
random-filter distribution (random controls span 15.0-18.6% CAGR and 1.31-1.44 Sharpe). So
the filter's information has no demonstrated edge over simply dropping the same number of
names at random. The cash variant lowers return and drawdown, but its risk-adjusted
result (Sharpe 1.275) is still below FR25.

Costs/delay: the union-renormalised filter costs about 49bp/year at 5bp and 198bp/year at
20bp; net CAGR falls from 15.79% to 15.24% (10bp) and 14.15% (20bp), and to **14.26% with one
extra session of delay** (Sharpe 1.192) — the filter is not delay-robust. M1 conditioning is
immaterial (2.67% vs 2.91% frozen; cash-heavy base).

## (c) Pre-2023-calibrated conditional overlay

The Rule A short-only daily sleeve gets 20% capital only in months whose stable union-signal
breadth is at or above the **pre-2023 median** (36 of 52 active names; condition true in 69%
of 2023-2026 months, decided at the prior month-end close, applied from the next session):

| Scenario | CAGR | Sharpe | Max DD | Calmar |
| --- | ---: | ---: | ---: | ---: |
| Frozen FR25 SOTA | 16.75% | 1.469 | −8.65% | 1.935 |
| Unconditional 80/20 FR25 + Rule A short | 15.54% | 1.454 | −7.67% | 2.028 |
| **Conditional 80/20 (pre-2023 breadth)** | **16.01%** | **1.478** | **−7.67%** | **2.088** |

The conditional overlay is the only construction here that improves **both** Sharpe
(1.478 vs 1.469) and max drawdown (−7.67% vs −8.65%) versus frozen FR25 — but it gives up
0.74pp CAGR and the improvement is small (Sharpe +0.009). It beats the unconditional overlay
on CAGR (+0.47pp) and Sharpe (+0.024), so the pre-2023 breadth timing does add something
relative to an always-on sleeve. This remains a risk-shaping sleeve, not a SOTA replacement.

An FR25-breadth-weak version could not be calibrated: FR25 target weights exist for only one
pre-2023 month-end decision (2022-12-30) in this panel, so that condition was dropped and
the unconditional overlay is reported as its matched alternative.

## (d) Verdict

- **The deeper two-era refit is a real improvement in robustness but is selective**: only
  25/52 short and 9/52 long sleeves survive it. That is the honest price of demanding
  chronological stability from a shallow per-ETF search.
- **Life-cycle eligibility on FR25/M1 fails its matched-control test.** Filtered FR25 is
  worse than frozen FR25 and indistinguishable from a random filter that removes the same
  number of names; with costs and delay it is clearly worse. Retire the eligibility-filter
  route rather than tune it on 2023+.
- **The conditional overlay is the one candidate worth keeping**: marginal Sharpe improvement
  and ~1pp less drawdown at a ~0.7pp return cost, with a pre-2023-calibrated timing rule.
  It must be reported as a small risk-shaping sleeve, not as an improvement to the SOTA.
- **No promotion or authority change.** 2023-2026 remains an inspected development retest;
  the overlay's inter-sleeve rebalancing cost is not explicitly charged (sleeve costs are in
  the sleeve NAV), which is a further reason to treat the overlay as provisional.

## Next actions

1. Test the conditional overlay with explicit inter-sleeve rebalancing cost and +1 delay;
   require it to beat FR25 on multiple risk-adjusted measures before any further work.
2. Do not pursue the eligibility-filter route further; the random matched control already
   explains its result.
3. If a deeper fit is revisited, require the two-era stability screen inside the candidate
   generation (not just post-selection) and test whether the 9 long-range stable sleeves are
   enough to support a long-horizon sleeve at all.

## Reproduction

```powershell
python scripts/run_gld_lifecycle_conditioning.py refit
python scripts/run_gld_lifecycle_conditioning.py condition
python scripts/build_gld_lifecycle_conditioning_report.py
```

Research only; no monitoring, promotion, allocation, funding or broker action.
