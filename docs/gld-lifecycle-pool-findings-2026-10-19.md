# Two-horizon lifecycle across the 52-ETF pool and the asset-selection test versus FR25

2026-10-19. Research only; no strategy monitoring, allocation, funding, promotion or
broker authority changed. This tests the two sealed GLD lifecycle algorithms (short-range
and long-range) on the full supported 52-ETF pool, then uses them as an asset-selection
signal and compares net results with the current FR25 SOTA.

- [Full report with per-ETF evidence, portfolio results and charts](../research/gld-lifecycle-pool-20261019-v1/index.html)
- Frozen root: `var/research/gld-lifecycle-pool-20261019-v1`
- Parent strategies: [short-range](../research/gld-lifecycle-20261019-v1/index.html),
  [long-range and combination](../research/gld-lifecycle-combination-20261019-v1/index.html)
- Code: `scripts/run_gld_lifecycle_pool.py`, `scripts/build_gld_lifecycle_pool_report.py`;
  shared state machine `src/systematic_trading/research/range_lifecycle.py` (two `Spec` domains)

## Design

- **Pool.** 52 audited ETFs from the frozen v2 batch: 15 US equity/sector, 13 international
  equity, 13 fixed income/credit, 10 commodities, 1 real asset. The 52-asset panel equals the
  per-asset audited closes exactly (max absolute difference 0.0). FR25 target weights and the
  frozen FR25/M1/equal-weight/URTH/BIL NAV paths are from the same batch.
- **Per-ETF fits.** Each ETF gets an independent pre-2023 fit in *both* structural domains:
  200 random bounded vectors + the sealed GLD vector + 40 anchor mutations, screened at 5bp
  over the IS window (252-session warm-up through 2022-12-30). The top 15 per domain are
  replayed at 5/10/20bp and 5bp plus one session delay; one vector is sealed per ETF/domain.
  Evidence requires at least 5 closed IS episodes and 5% average exposure. ETFs under 500
  evaluable IS sessions inherit the sealed GLD vector (none needed in this cohort).
- **Signals.** Causal sleeve state plus an extension score `(close - frozen trigger)/ATR`
  are mapped onto the portfolio panel. Only pre-2023-fitted parameters generate 2023+ signals.
- **Portfolio window.** 2023-01-03 to 2026-10-12 (947 sessions). Next-open fills, 5/10/20bp
  per side, 45% cap, 98% budget, zero cash yield, no shorting or leverage. The same shared
  application accounting engine that produced the frozen FR25 paths is used; replaying the
  FR25 target weights reproduces the frozen FR25 SOTA path to 0.03% (max relative NAV
  deviation).
- **Predeclared selection rules.**
  - **R1 lifecycle top-six:** among ETFs with an active short/long sleeve and positive
    126-session momentum, rank by combined extension score, hold up to six, inverse-vol
    (63-session) weights, 45% cap, cash for unfilled slots.
  - **R2:** R1 without the momentum gate.
  - **R3 lifecycle allocation:** all active ETFs, weight = combined sleeve exposure x
    inverse-vol.
  - **R4 lifecycle-gated momentum:** among active ETFs, rank by 126-session momentum.
  - Event clock: mandatory adoption on a held-name lifecycle exit or when the L1 target
    change including cash exceeds 0.10, plus monthly anchors. Monthly clock: month-end only.
  - Tilt: 80% frozen FR25 targets + 20% lifecycle target, rebalanced monthly/event.
  - BIL is excluded from selection (Treasury-bill cash proxy; same BIL-dominance issue
    flagged in the earlier study).

## Per-ETF signal evidence

Short-range fits pass the evidence rule for all 52 ETFs; long-range fits for 47/52
(commodities 8/10, fixed income 12/13, international 13/13, US equities 13/15, real assets
1/1). The per-asset budget recovers the GLD deep-dive numbers closely (GLD short OOS
7.9%/0.86, long OOS 11.6%/1.29). Standalone sleeve results vary widely: SOXX short OOS
32.7%, SPY short 21.8%, SLV long 17.1%, while TLT, USO and XLE produce negative sleeves.
This is expected for a breadth-first fit, not evidence that the lifecycle fails on those
assets. Full per-ETF table is in the report and `per-asset.csv`.

## Portfolio results versus FR25 (5bp, next-open fills, 2023-2026)

| Portfolio | CAGR | Sharpe | Max DD | Calmar | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| **FR25 SOTA (frozen path)** | **16.75%** | **1.47** | **−8.65%** | **1.93** | — |
| Equal-weight pool | 14.74% | 1.38 | −10.89% | 1.35 | — |
| URTH buy-hold | 20.45% | 1.40 | −16.80% | 1.22 | — |
| R1 lifecycle top-six (event) | 4.46% | 0.63 | −9.80% | 0.46 | 29.1x |
| R1 lifecycle top-six (monthly) | 7.35% | 1.00 | −8.62% | 0.85 | 5.7x |
| R2 no momentum gate (monthly) | 7.86% | 1.00 | −9.89% | 0.79 | 3.1x |
| R3 lifecycle allocation (monthly) | 8.05% | 1.20 | −6.66% | 1.21 | 3.2x |
| R4 lifecycle-gated momentum (event) | 14.53% | 1.00 | −11.62% | 1.25 | 56.8x |
| R4 lifecycle-gated momentum (monthly) | 14.09% | 0.93 | −13.50% | 1.04 | 10.8x |

Event adoption is clearly harmful for this signal family: R1 event churns 299 rebalances
and gives up 2.9pp CAGR versus the monthly clock. The best lifecycle-only portfolio is R4
(active lifecycles ranked by momentum) at 14.5% CAGR but with a lower Sharpe than FR25 and
a larger drawdown; **no standalone lifecycle selection rule beats FR25 on both net CAGR and
Sharpe**.

### Tilt results

| Portfolio | CAGR | Sharpe | Max DD | Calmar |
| --- | ---: | ---: | ---: | ---: |
| FR25 SOTA | 16.75% | 1.47 | −8.65% | 1.93 |
| 80% FR25 + 20% R1 (monthly) | 14.86% | 1.475 | −7.53% | 1.97 |
| 80% FR25 + 20% R1 (event) | 14.32% | 1.42 | −7.92% | 1.81 |
| 80% FR25 + 20% R3 (monthly) | 14.99% | 1.47 | −7.91% | 1.89 |

The 80/20 tilt is a risk-shaping candidate, not a return improvement: it keeps Sharpe at
the SOTA level and reduces drawdown by about 1.1pp, but gives up about 1.8-1.9pp of CAGR.
Daily-return correlation between R1 and FR25 is 0.60.

## Verdict

**The two-horizon lifecycle does not beat the current FR25 SOTA as a standalone
asset-selection rule on the 52-ETF pool.** The best lifecycle-only rule (R4, active
lifecycles ranked by momentum) reaches 14.5% OOS CAGR versus 16.75% for FR25, with lower
Sharpe and higher drawdown. The primary predeclared rule (R1 extension-ranked top-six) is
much weaker (7.4% monthly, 4.5% event). A 20% lifecycle sleeve inside FR25 is roughly
neutral on Sharpe and improves drawdown slightly at the cost of return. The lifecycle
signals do generalise to the pool (short evidence 52/52, long 47/52, and several strong
standalone sleeves), but the *selection scoring and per-ETF fit depth* are not yet good
enough to beat the momentum/financial blend.

Why, and what is worth fixing next:
1. **The per-ETF fit is deliberately shallow** (241 candidates per domain) compared with the
   GLD deep dives. It finds signals but not necessarily the best ones per asset.
2. **The extension-score ranking is weak.** It picked defensive names (SHY 34/47 monthly
   selections, XLV, IBB, XLP) and no commodities, so the sleeve missed the 2023-2026 gold and
   commodity trends that the GLD deep dive captured. Ranking active names by momentum (R4)
   was much better; the lifecycle is more useful as a *filter* than as a ranking score.
3. **The event clock needs a wider threshold** than 0.10 L1 for this signal family; the
   current setting over-trades.
4. **The 2023-2026 window is an inspected development retest**, and the GLD procedure failed
   its 2005-2015 refit validation on 2016-2022, so the fitting procedure remains data-hungry.

## Suggested next step

Treat the lifecycle as a *conditioning filter* on the existing SOTA selection, not as a
standalone ranker: (a) increase the per-ETF search budget and add a cross-period (two-era)
stability requirement so per-asset parameters are less noisy; (b) use the lifecycle state as
an eligibility filter on FR25/M1 names while leaving momentum to rank; (c) optimise the event
threshold only inside pre-2023 sessions; (d) rerun on the full pool with matched FR25
controls and report net Sharpe/return/drawdown, turnover and delay sensitivity. No promotion
or allocation decision should follow from the current result.

## Reproduction

```powershell
python scripts/run_gld_lifecycle_pool.py prepare
python scripts/run_gld_lifecycle_pool.py fit
python scripts/run_gld_lifecycle_pool.py signals
python scripts/run_gld_lifecycle_pool.py portfolio
python scripts/build_gld_lifecycle_pool_report.py
```

Frozen inputs: pinned 52-asset panel and per-asset histories (panel SHA-256 and close
identity checks in the protocol); FR25/M1/equal-weight/URTH/BIL frozen paths from the same
batch. Tests: `tests/test_gld_lifecycle_pool.py` plus the shared lifecycle tests.
