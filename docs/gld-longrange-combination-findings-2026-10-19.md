# GLD long-range lifecycle and the short/long combination

2026-10-19. Research only; no strategy monitoring, allocation, funding, promotion or
broker authority changed. This is the operator-requested second strategy: the same
range-breakout lifecycle logic as the sealed short-range study, but with a predeclared
long-range structural domain (126-756 session ranges, much larger stops and trailing
distances, longer holds), followed by a correlation and combination test against the
frozen short-range strategy.

- [Combination report with charts, daily ledgers and both strategies](../research/gld-lifecycle-combination-20261019-v1/index.html)
- Frozen roots: `var/research/gld-longrange-lifecycle-20261019-v1`, `var/research/gld-lifecycle-combination-20261019-v1`
- Short-range parent: [findings](gld-range-lifecycle-findings-2026-10-19.md), [report](../research/gld-lifecycle-20261019-v1/index.html)
- Code: `src/systematic_trading/research/range_lifecycle.py` (shared state machine, two predeclared `Spec` domains);
  runner `scripts/run_gld_lifecycle.py`; combination analysis `scripts/analyze_gld_lifecycle_combination.py`;
  reports `scripts/build_gld_lifecycle_report.py`, `scripts/build_gld_lifecycle_combination_report.py`

## The long-range domain

The lifecycle logic is identical to the sealed short-range rule; only the predeclared
structural search domain changes, and it was declared before fitting:

| Structural element | Short-range (frozen) | Long-range (new) |
| --- | --- | --- |
| Candidate range lookbacks | 21, 42, 63, 126, 252, 504 | 126, 189, 252, 378, 504, 756 |
| ATR periods | 10, 20, 40, 60 | 20, 40, 60, 120 |
| Volume references | 20, 63, 126 | 63, 126, 252 |
| Time-exit limits | 0-126 sessions | 0, 126, 252, 504 |
| Initial stop | 1.5-12 ATR | 4-20 ATR |
| Failed-range floor | -1 to 4 ATR | -1 to 8 ATR |
| Trailing distance | 1-12 ATR / 3-35% | 3-20 ATR / 8-50% |
| Cooldown | 0-42 sessions | 0-126 sessions |

All behavioral thresholds inside the long domain are fitted on pre-2023 sessions only,
with the same objective, differential-evolution search, friction set, evidence/guard
rules, neighbourhood stability and sealing protocol as the short-range study. Search
was 4 seeds x 20 x dimension x 150 generations = **326,160 pre-2023 evaluations** at
5bp; 400 finalists were replayed at 5/10/20bp and +1 session delay. The 2023+ interval
was not read before the selection was sealed.

### Sealed long-range vector (decoded)

Width cap 0.3346, tail 5%, drift cap 0.600, short/long vol ratio 1.447, ATR 120,
breakout buffer 0.0 ATR, confirmation 8 closes, no volume shortcut, initial stop
11.06 ATR, failed-range floor 8.0 ATR (disabled in practice), trailing ATR 3.77 from
the highest close armed after a 9.89 ATR advance, overheat tightening on (extension
15.45 ATR, volume 1.0, near-high 0.25 ATR, multiplier 0.20), time exit 504 sessions
with a 2.16 ATR progress hurdle, cooldown 0 sessions, continuation re-entry off.
These are the "much larger stops, much longer holds" parameters the operator asked for:
entries are 126-756-session range breaks, initial risk is about 11 ATR (ATR120), and
positions are held on a wide 3.8 ATR trail armed after a ~10 ATR advance.

## Long-range performance (5bp per side, next-open fills)

| Window | CAGR | Sharpe | Max DD | Calmar | Exposure |
| --- | ---: | ---: | ---: | ---: | ---: |
| IS 2005-2022 | 8.02% | 1.05 | -12.52% | 0.641 | 21.2% |
| OOS 2023-2026 development retest | 11.65% | 1.29 | -11.35% | 1.026 | 40.1% |
| Full 2005-2026 | 8.67% | 1.10 | -12.52% | 0.692 | 24.6% |
| Buy-hold OOS | 23.75% | 1.16 | -26.40% | 0.900 | 100% |

The long-range rule captures the persistent 2023-2026 gold trend far better than the
short-range burst rule: it entered on 2023-03-30 (a 756-session range break) and held
251 sessions to 2024-04-10 for **+15.63%**, then took +14.55% (2024-07-12 to
2024-10-31) and +14.69% (2025-02-07 to 2025-04-22). All 13 finished full-history
episodes were winners, but that is mostly an in-sample statistic and the out-of-sample
event count is only three.

Long-range anomalies/caveats:
- Only ~10 closed pre-2023 episodes, so the fit is evidence-thin. The 2005-2015 refit
  procedure validation failed on 2016-2022 (0.69% CAGR, 0.12 Sharpe, -22.30% DD versus
  buy-hold 7.42%/0.58/-22.00%); the sealed 2023+ result is a development retest, not an
  untouched holdout.
- It sits flat for long stretches (2012-2015 and after 2025-04), so it is a
  trend-capture sleeve, not a stand-alone gold allocation.

## Short/long correlation and combination

The two strategies are the same machine on different horizons. Their **daily-return
correlation is 0.338 out-of-sample** (0.368 in-sample, 0.361 full) because they are in
the market at different times, not because they hold different assets. When both are
long, the correlation is 0.998 — same ETF. Active-sleeve overlap OOS: short-only 162
sessions (17.1%), long-only 221 (23.3%), both 160 (16.8%), neither 408 (42.9%); each
sleeve is active only 34%/40% of sessions.

Predeclared combination: **50/50 independent half-accounts** (each parent manages its
own half, no between-sleeve rebalancing, so only parental internal costs) plus
daily-/monthly-rebalanced 50/50 controls and a fixed capital-split grid.

| Portfolio | OOS CAGR | OOS Sharpe | OOS max DD | OOS Calmar |
| --- | ---: | ---: | ---: | ---: |
| Short-range only | 7.87% | 0.86 | -12.20% | 0.645 |
| Long-range only | 11.65% | 1.29 | -11.35% | 1.026 |
| **50/50 independent (primary)** | **9.62%** | **1.28** | **-6.64%** | **1.448** |
| 50/50 daily-rebalanced | 9.90% | 1.31 | -6.64% | 1.500 |
| 50/50 monthly-rebalanced | 9.90% | 1.30 | -6.64% | 1.496 |
| Buy and hold | 23.75% | 1.16 | -26.40% | 0.900 |

In-sample the combination is 8.6% CAGR / 1.27 Sharpe / -6.9% DD versus 9.2%/1.06/-13.3%
(short) and 8.0%/1.05/-12.5% (long). The improvement is present for every interior
capital split (25/75, 50/50, 75/25); the 50/50 rule was predeclared, not chosen from the
grid. Costs and delay: at 20bp per side the combined OOS Sharpe is 1.23; with one extra
execution session at 5bp it is 1.23.

**Answer:** yes, the long-range strategy's return is sufficiently uncorrelated with the
short-range strategy's return (about 0.34 OOS) to add the two sleeves together. The
diversification is horizon/time-in-market, not asset diversification: it reduces
drawdown by roughly half while preserving a combined Sharpe close to the long parent's,
at the cost of some long-range CAGR. A persistent single gold trend in which both
sleeves are long together would reduce the benefit.

## Disposition and next step

Both strategies are sealed research artifacts on the same audited GLD history; the
short-range report remains unchanged and the long-range/combination evidence is in the
new report. No monitoring, promotion, funding or allocation follows. The next step is
the supported ETF pool: apply both structural domains per asset (or with shared
fallbacks), require cross-period stability before admission, then test the two-horizon
pair as an asset-selection rule and as a trading/tilting sleeve against matched
controls, including dynamic-rebalance and fixed-interval controls.

## Reproduction

```powershell
$env:GLD_STUDY_KIND='long'
python scripts/run_gld_lifecycle.py prepare
python scripts/run_gld_lifecycle.py fit
python scripts/run_gld_lifecycle.py select
python scripts/run_gld_lifecycle.py evaluate
python scripts/run_gld_lifecycle.py validate
python scripts/analyze_gld_lifecycle_combination.py
python scripts/build_gld_lifecycle_combination_report.py
```

The short-range study reproduces with `GLD_STUDY_KIND=short` and the original paths. The
spec refactor preserves the short domain exactly (sealed IS metrics reproduce to 0.0).
Tests: `tests/test_range_lifecycle.py`, `tests/test_range_lifecycle_domains.py`.
