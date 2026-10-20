# Daily life-cycle opportunity scanner / CTA-style portfolios

2026-10-19. Research only; no strategy monitoring, allocation, funding, promotion or
broker authority changed. This tests the operator's two daily event-driven constructions
on the full 52-ETF audited pool, using only the sealed pre-2023 short-range and long-range
life-cycle signals.

- [Full report with charts and sensitivity tables](../research/gld-lifecycle-daily-scanner-20261019-v1/index.html)
- Frozen root: `var/research/gld-lifecycle-daily-scanner-20261019-v1`
- Signals from the [52-ETF pool study](gld-lifecycle-pool-findings-2026-10-19.md)
- Code: `scripts/run_gld_lifecycle_daily_scanner.py`,
  `scripts/build_gld_lifecycle_daily_scanner_report.py`

## The two rules

- **Rule A — equal re-split.** Existing holdings persist until their own life-cycle signal
  exits. When a new ETF entry triggers, all current holdings are rebalanced to equal weights
  (capacity 6); an exit drops the name and the remaining book is re-equalised. Empty book =
  100% government/cash proxy. The OOS account starts flat and only entries inside the window
  populate it.
- **Rule B — 1/6-slot CTA.** At most six holdings; each accepted entry gets one 1/6 slot and
  unused slots stay in the government/cash proxy. An exit returns its slot to the proxy; the
  other holdings keep their 1/6.
- **Signals.** Union of the sealed short-range and long-range sleeve states per ETF; a "new
  entry" is a daily 0→1 transition, an "exit" a 1→0 transition. Short-only and long-only runs
  attribute the two horizons. BIL (1-3m T-bill) is the base cash/government proxy; SHY and IEF
  are sensitivities (GOVY itself is not in the audited pool).
- **Execution.** Daily close decisions, next-open fills, cost per side, long-only, no leverage,
  no monthly ranking. Window 2023-01-03 to 2026-10-12 (947 sessions).

## Results (5bp, next-open fills)

| Portfolio | CAGR | Sharpe | Max DD | Calmar | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| FR25 SOTA (reference) | 16.75% | 1.47 | −8.65% | 1.93 | — |
| Equal-weight pool | 14.74% | 1.38 | −10.89% | 1.35 | — |
| URTH buy-hold | 20.45% | 1.40 | −16.80% | 1.22 | — |
| BIL cash proxy | 4.46% | — | ≈0% | 1.49 | 0 |
| Rule A equal re-split, union | 8.51% | 0.94 | −11.04% | 0.77 | 5.3x |
| Rule B 1/6 slots, union | 7.20% | 0.85 | −10.09% | 0.71 | 4.6x |
| Rule A, short-only signals (best variant) | 10.57% | 1.04 | −10.27% | 1.03 | 8.1x |
| Rule A, long-only signals | 5.85% | 0.68 | −11.32% | 0.52 | 5.0x |
| Rule A, 8 slots | 9.06% | 0.89 | −9.61% | 0.94 | 5.0x |

Both rules are positive, long-only, low-turnover and cost-robust, but **neither beats the
reference benchmarks** (FR25 SOTA, equal-weight pool or URTH); the best variant (short-only
equal-split) reaches 10.6% CAGR / Sharpe 1.04. Correlation with FR25 is 0.73 and with URTH
0.66 — the daily books are equity-like, not a distinct CTA diversifier in this sample.

## The binding finding: the cash leg is effectively unused

The fitted per-ETF signals are active for about 73% of OOS asset-days and the 52-ETF
universe almost always has at least six simultaneous active signals. Across the OOS window,
**0.0% of days had zero holdings and 83% had the full six** (average holdings 5.7; only 29
accepted entries and 23 exits for Rule A). The daily rules therefore behave as concentrated
rotating six-name portfolios, not as scanners that spend time in govvies. The cash-proxy
choice is irrelevant: BIL, SHY and IEF produce identical results because the residual cash
weight is almost always zero.

This is a *signal-selectivity* problem, not a portfolio-rule problem. The per-ETF fits were
selected for breadth in the pool study with only a minimum 5% exposure rule (median
short-range sleeve long 59% of IS sessions). A daily scanner needs sparse, high-conviction
entries; that requires stricter per-ETF fits (event-style exposure range, cross-period
stability), an explicit entry-strength threshold calibrated pre-2023, or a
replace-when-full ranking rule.

## Verdict and next experiments

The two daily constructions work mechanically and produce a viable long-only return
stream, but on the 52-ETF pool they do not beat the current SOTA or even an equal-weight
pool. The opportunity-scanner concept is not falsified — its current implementation is
starved of selectivity. Suggested next experiments, in order:
1. entry-strength threshold: accept an entry only above a pre-2023-calibrated extension-score
   quantile, creating real cash periods;
2. replace-when-full ranking: when all slots are held and a stronger signal fires, replace the
   weakest holding;
3. stricter per-ETF scanner fits (5-50% exposure, two-era stability);
4. a smaller, higher-conviction universe (sector or asset-class scanner) so the cash leg can
   express the opportunity cycle.

## Reproduction

```powershell
python scripts/run_gld_lifecycle_daily_scanner.py
python scripts/build_gld_lifecycle_daily_scanner_report.py
```

No OOS tuning: rules, cash proxy, capacity and frictions were fixed before the 2023+ replay.
No promotion, monitoring, allocation, funding or broker action follows.
