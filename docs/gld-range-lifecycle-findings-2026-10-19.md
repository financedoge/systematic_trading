# GLD range-breakout lifecycle: fitted signal, dynamic take-profit and honest out-of-sample

2026-10-19. Research only; no strategy monitoring, allocation, funding, promotion or
broker authority changed. This is the operator-requested second attempt on GLD after
the earlier daily diagnostic (8-close confirmation, 5-session progress exit) failed
the February-March 2023 breakout.

- [Full report with all fitting, daily ledgers and 2023 drill-down](../research/gld-lifecycle-20261019-v1/index.html)
- [Long-range sibling strategy and the short/long combination](gld-longrange-combination-findings-2026-10-19.md)
- Frozen study root: `var/research/gld-lifecycle-20261019-v1`
- Predeclared protocol and bounds: `protocol.json`, `bounds.json` (same directory and in the report)
- Research code: `src/systematic_trading/research/range_lifecycle.py`; runner: `scripts/run_gld_lifecycle.py`; report builder: `scripts/build_gld_lifecycle_report.py`

## What changed

Every behavioral threshold is now an element of a 24-dimensional fitted vector. The
earlier fixed values the operator objected to are gone:

| Earlier choice | This study |
| --- | --- |
| `W <= log(1.25)` range limit | `width_cap` fitted (selected 0.0979 for GLD's central band) |
| 8-close confirmation | `confirm_sessions` fitted (1), with a fitted volume surge shortcut (`volume_ratio` 1.69 x the 126-session median) |
| 5-session progress exit with a 2.39 ATR hurdle | `time_exit_index` fitted (selected off, 0) |
| Initial stop `E - 2 ATR`, failed range `U - 0.5 ATR` | `initial_stop_atr` fitted (12.0) and `band_fail_atr` fitted (2.54) |
| Fixed 21-session cooldown | `cooldown_sessions` fitted (36) |

The signal is a staged state machine on completed daily closes:

1. **Tight range.** For lookbacks `{21, 42, 63, 126, 252, 504}`, a prior central
   quantile band must be narrow (`W <= width_cap`), non-trending (first/last block
   median drift relative to `W`), and not accompanied by a recent volatility
   expansion. The **longest** qualifying lookback is selected; this is the formal
   "stable for a while" criterion, with the quantile tail, width cap, drift cap,
   volatility-ratio cap and lookback all fitted.
2. **Breakout.** `close > U + buffer * ATR` with the crossing requiring the prior
   close to be below the trigger; the bands and range length freeze at that close.
3. **Confirmation.** A fitted number of closes above the frozen trigger, cancellable
   by any close back at/below it; a fitted volume surge confirms immediately.
4. **Entry.** Next available open after confirmation, 5bp per side in the base case.
5. **Initial risk.** Fitted wide initial stop plus a fitted failed-breakout floor
   `max(entry - i*ATR, U* - f*ATR)`; a breakout that closes back into the range is cut.
6. **Dynamic take-profit.** The stop ratchets from the highest close since entry
   after a fitted activation gain, at a fitted ATR distance (or percent), tightened
   when fitted extension + volume + near-high conditions mark overheating. A fitted
   time stop with a progress hurdle, and a fitted continuation re-entry option, are
   available; both were rejected by the pre-2023 evidence for GLD.
7. **Cooldown.** A fitted flat period after exit before a new breakout is adopted.

## Data and chronology

- Pinned published audited adjusted GLD OHLC and raw volume, batch
  `5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`,
  asset SHA-256 `968d382f...8b9`, 5,512 sessions from 2004-11-18 to 2026-10-16.
  Adjusted and raw closes are identical for GLD; no filling or splicing.
- Warm-up 252 sessions. **Fit and selection:** 2005-11-17 to 2022-12-30 only.
- **Out-of-sample:** 2023-01-03 to 2026-10-16, one evaluation after the vector is
  sealed. The operator has already inspected this interval and earlier work covered
  it; the report labels it a chronological **development retest**, not a pristine
  holdout. The fit/selection code never reads 2023+ arrays (the full-history
  evaluation asserts its IS slice equals the sealed fit).
- A second, fully pre-2023 chronology (fit 2005-2015, evaluate 2016-2022) is used as
  pseudo-out-of-sample validation of the **procedure**.

## Fitting and selection

Bounded rand/1/bin differential evolution over 24 mixed continuous/integer
parameters, 4 seeds x population 20 x dimension x 110 generations = 213,120
pre-2023 evaluations at 5bp per side. Objective: a 45/40/15 weighted utility of
clipped scaled excess CAGR, excess Sharpe and excess regularized Calmar versus the
matched buy-and-hold, plus a three-block chronological stability term, minus scarcity
and low-exposure penalties. The 400 best finalists were replayed at 5bp, 10bp, 20bp
and 5bp plus one session of delay; the final score is the minimum across frictions.
Evidence required >=10 closed IS episodes, >=20% average IS exposure, closed episodes
in all three IS blocks, and return/drawdown guards versus matched buy-and-hold.
Among near-best candidates the selector prefers parameter-neighbour stability and
then lower turnover.

Selected vector (decoded): width cap 0.0979, tail 5%, drift cap 0.150, volatility
ratio cap 1.600, ATR 20, breakout buffer 0.315 ATR, confirmation 1 close, volume
shortcut on at 1.687x the 126-session median, initial stop 12.0 ATR, failed-range
floor 2.54 ATR below the frozen upper band, trailing ATR 1.000 from the highest close
after a 6.0 ATR advance, overheat tightening on (extension 2.61 ATR, volume 1.00,
near-high 1.76 ATR, trail multiplier 0.445), time stop off, cooldown 36 sessions.

## Results (5bp per traded side, next-open fills)

| Window | Rule CAGR | Rule Sharpe | Rule max DD | Rule exposure | Buy-hold CAGR | Buy-hold Sharpe | Buy-hold max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| IS 2005-2015 (first era) | 9.28% | 0.98 | -13.28% | ~30% | 7.58% | 0.46 | -45.56% |
| IS 2016-2022 (second era) | 9.12% | 1.24 | -8.55% | ~30% | 7.42% | 0.58 | -22.00% |
| IS total 2005-2022 | 9.21% | 1.06 | -13.28% | 29.8% | 7.60% | 0.49 | -45.56% |
| OOS 2023-2026 (development retest) | 7.87% | 0.86 | -12.20% | 33.9% | 23.75% | 1.16 | -26.40% |
| Full history | 9.01% | 1.03 | -13.28% | 30.6% | 10.40% | 0.63 | -45.56% |

Friction stress: at 20bp per side IS/OOS CAGR is 8.70%/7.28%; with one extra
execution session 5bp gives IS/OOS 8.79%/7.69%. The result is not cost-fragile.

## The 2023 breakout the operator challenged

| Test | Earlier daily diagnostic | This study |
| --- | --- | --- |
| Crossing | 2023-03-15 | 2023-03-13 |
| Confirmation | 2023-03-24 (8 closes) | 2023-03-13 (same close; fitted 1-close rule, volume shortcut on) |
| Entry | 2023-03-27 at $181.15 | 2023-03-14 at $177.35 |
| Exit rule | five-session progress deadline | dynamic trailing take-profit (1 ATR from high after 6 ATR advance) |
| Exit | 2023-04-03 (loss) | 2023-04-14 at $185.89 |
| Outcome | missed the move, bought high | +4.82% gross over 23 sessions |

The rule then re-armed and caught the October 2023 breakout, held it into March 2024
(+9.08%, 93 sessions), and caught the 2025 and 2024 legs. In-sample episodes, every
daily range/trigger/stop/trailing level, and the full daily ledger are in the report.

## Robustness, and what does not work

- **The fitted range detector is shorter-horizon than the premise.** It qualifies 33.8% of
  sessions, and for 30 of the 35 recorded breakouts the selected lookback is 21-63
  sessions (20 at 21, 10 at 42, 4 at 63, 1 at 126); no entry used 252 or 504 sessions
  because the fitted drift cap (selected at its 0.15 lower bound) rejects those windows.
  The strict drift/width tests therefore reduce "stable for a while" to a one-to-three
  month compression for GLD. The breakout, confirmation and exit mechanics carry more of
  the result than the long-horizon range premise. This is the clearest candidate for the
  next refinement: a scale-relative tightness measure or a longer-window stability
  statistic that can survive the drift test.
- **Frozen-vector chronological stability holds** across both pre-2023 eras (table
  above).
- **The fitted procedure is data-hungry.** Refitting on 2005-2015 only selected a
  boundary-hugging vector (width cap at its 0.80 bound) that lost money on 2016-2022
  (CAGR 1.00%, Sharpe 0.16, DD -23.02% versus buy-hold 7.42%/0.58/-22.0%). This is
  reported as a failed procedure validation, not hidden. It is a warning for the
  ETF-pool extension: per-asset fits need enough independent cycles, and
  cross-period stability should be a selection requirement, not an afterthought.
- **Holding longer.** The sealed take-profit is a fast burst exit. A one-dimensional
  surface over trailing distance (1-12 ATR) and activation (0-6 ATR), holding every
  other parameter fixed, shows IS fitness falls as the trail widens, while the
  2023+ development CAGR rises. That divergence is a real regime difference: the
  exceptional 2024-2026 leg was more persistent than anything in the IS window.
  Choosing the wide trail after seeing 2023+ would be out-of-sample tuning, so the
  sealed vector remains the IS choice and the surface is reported as sensitivity.
- **Continuation re-entry.** A fitted re-entry option (re-enter the same trend above
  the previous peak plus a buffer within a waiting window) was tested on the sealed
  vector: the best enabled setting lowers IS CAGR from 9.21% to 5.7%, IS Sharpe from
  1.06 to 0.46, raises maximum drawdown to -33.8% and exposure to ~65%. Pre-2023 gold
  did not reward mechanical re-engagement; the switch is off.

## Disposition and next step

The GLD lifecycle mechanics now satisfy the operator's acceptance test: early entry
on the crossing, no five-session forced exit, a dynamic drawdown-from-high
take-profit, and a fitted failed-breakout stop. The strategy is an IS-selected
breakout harvester with ~30% exposure, not a buy-and-hold replacement; during an
exceptional persistent bull leg it trails buy-and-hold return while halving drawdown.

No promotion, monitoring, funding or broker action follows. The next step requested
by the operator is to apply the same parameterized algorithm, with per-asset fitted
parameters, to the supported ETF pool, then test it as an asset-selection rule and as
a trading/tilting sleeve against matched controls. Given the failed procedure
validation above, that extension should add an explicit cross-period (two-era)
stability requirement to per-ETF selection and should compare a shared-parameter
fallback, rather than relying on 10-year per-asset fits alone.

## Reproduction

```powershell
python scripts/run_gld_lifecycle.py prepare
python scripts/run_gld_lifecycle.py fit
python scripts/run_gld_lifecycle.py select
python scripts/run_gld_lifecycle.py evaluate
python scripts/run_gld_lifecycle.py validate   # pre-2023 procedure validation
python scripts/build_gld_lifecycle_report.py
```

The runner verifies the pinned input hash, freezes the search, seals the selection
before any 2023+ read, and asserts the full-history IS slice equals the sealed fit.
Focused tests: `tests/test_range_lifecycle.py` (causality, prefix stability, stop/fill
ordering, determinism and accounting identities).
