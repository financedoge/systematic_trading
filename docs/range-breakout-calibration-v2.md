# Range-breakout calibration v2 — October 18, 2026

The operator correctly challenged v1's unoptimized `log(1.25)` range limit and
tight initial/failed-range/heat stops. V2 explicitly fits these choices on longer
individual histories, then evaluates the sealed choices from January 2023 onward.
V1's results and recipe remain unchanged. This is finite retrospective research,
not a promoted or monitored strategy.

[Review report](../research/range-breakout-20261018-v2/index.html) ·
[Protocol](../research/range-breakout-20261018-v2/protocol.json) ·
[Every IS finalist](../research/range-breakout-20261018-v2/IS-fitting.json) ·
[Acceptance](../research/range-breakout-20261018-v2/acceptance.json).

## Data and chronology

The split has no overlap: fit through **December 31, 2022**, then evaluate
**January 1, 2023–October 16, 2026**. The last IS session is December 30, 2022;
the first OOS execution session is January 3, 2023. Post-2023 history was already
discussed and inspected in earlier work: this is chronological OOS for this
selection procedure, not an untouched prospective holdout.

Pin: published batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`,
`var/governance/listed-2026-10-16-a861d1534a00`. All consumed publication
files and study inputs are hash-verified. Adjusted OHLC supplies return/signal
prices; audited raw volume and raw close supply activity/liquidity. No online
prices, provider archives, source splicing or missing-observation filling.

The full supported candidate pool contains 52 of 54 reviewed ETFs. Each asset
uses its own longest complete supported suffix; early invalid observations and
their dates are recorded. BWX/XOP retain listing-identity holds. CPER becomes
usable from August 24, 2018, but has insufficient IS history for an individual fit
and uses the common IS rule. The other 51 were already supported on the shorter
v1 window. Current-cohort, provider-identity and revised-publication limitations
remain; this does not certify historical universe/mandate/vintage availability.

Full histories were already available for the requested cases:

| ETF | Supported history begins | IS replay after 252-session warmup | IS sessions |
|---|---|---|---:|
| GLD | 2004-11-18 | 2005-11-17 | 4,309 |
| USO | 2006-04-10 | 2007-04-12 | 3,960 |
| SOXX | 2001-07-13 | 2002-07-19 | 5,150 |

SPY extends to 1993 and older sector ETFs are included. New stock data was not
needed for this pass. Long daily histories still contain few independent cycles:
the chosen GLD fit has only eight closed IS episodes, USO fifteen, SOXX eighteen.
Those counts cannot make a 1,080-choice search statistically certain.

The operational calendar documents that it is not a complete historical exception
feed. Research therefore uses installed `exchange_calendars==4.13.2` XNYS, which
handles September 2001 closures, Reagan/Ford mourning closures and pre-1998 MLK
sessions. No operational/broker calendar was modified.

Coverage amendment: the first inventory rejected entire histories for unsupported
early bars. After four IS fits, before any OOS evaluation, the study retained each
complete valid suffix instead. Existing four case/control input files stayed
byte-identical; a receipt records prior manifest and asset hashes. No signal,
search or selection parameter changed in this amendment.

## Mathematical search

For completed close t, use prior log prices x=log(C) over L sessions, excluding t:

`W(L,t) = q95(x[t-L:t]) - q05(x[t-L:t])`.

The adaptive duration is the longest currently qualifying L from
`21,42,63,126,252,504,756,1008,1260`. Qualification requires:

- Absolute mode: `W <= log(1+w)`, with `w=10/15/25/40/60/80%`.
  First/last block median drift must be at most `35%` or `65%` of W.
- Relative mode: W below its preceding 756-observation width distribution's
  `25th/50th/75th` percentile, minimum 252 prior widths, excluding today's W.
  Drift limit is 50% of W.
- Recent return volatility no greater than full-window return volatility.

There are 15 range recipes. Bands and duration freeze on the initial crossing
above `U+0.5*priorATR20`. Three closes must remain above that boundary. Volume
confirmation is on/off: three-day mean raw volume >=1.2 times the pre-crossing
63-session median. Earliest fill is the next open. The 21-session cooldown remains.

Each range is crossed with 36 exit recipes and two volume settings: **1,080**
candidates per ETF, plus unchanged v1 as an exact-accounting control.

- 27 ATR recipes: initial `E-i*entryATR`, `i=2/4/8`; ratcheting trailing stop
  `max(oldStop, highestClose-k*currentATR)`, `k=4/8/12`; failed-range buffer
  `U-b*entryATR`, `b=0.5/2/disabled`.
- Three heat ablations: initial4/trail8 at each range buffer, halving the trailing
  multiplier after v1's joint price-extension/volume heat event.
- Six percentage recipes: initial4/8 ATR, ratcheting 10/20/30% drawdown from
  highest close, failed-range and heat exits disabled.

V2 removes v1's extra initial-stop floor `max(...,U-ATR)` and its 21-session
no-follow-through exit. V1 retains both. A stop is a close-time decision with a
later-open execution; neither intraday stop prices nor eventual peaks are fills.
Price and volume do not establish that fundamentals changed.

## IS objective and sealed selection

The fitter physically removes all 2023+ arrays before screening or selection.
Fractional held-unit screening at 98% budget and 5bp per side uses:

`score = .5*fullISSharpe + .5*median(three IS block Sharpes)
         - .25*std(three IS block Sharpes)`.

Blocks are equal contiguous IS session blocks, evaluated without resetting their
prior NAV. These are IS stability diagnostics, not independent validation folds.
Retain top six overall and top six satisfying return/drawdown/trade guards, plus
v1. Replay that union with the shared whole-share engine at 5bp, 10bp and 5bp plus
one extra session delay. Final score is the minimum across those frictions.

Evidence requires at least 1,260 IS sessions after warmup, eight closed episodes,
10% average exposure and activity in all three blocks. Guards at all three
frictions require CAGR >= max(0,buyhold CAGR−2pp) and maximum drawdown no worse
than buyhold−5pp. Among passing candidates within 0.03 of the best score, prefer
lower turnover. If no guard-passing candidate exists, retain the best
evidence-qualified descriptive candidate marked failed. No absolute cost ceiling.

47 ETFs have individually fitted choices; 46 pass IS guards. Five use a shared
rule for insufficient history or trade evidence: BIL, CPER, IBB, XLC, XLV.
The common rule maximizes the median within-ETF IS score percentile over all ETFs
with adequate history. It selects 15% width, 65% drift, initial8/trail12 ATR,
no failed-range/heat exit and no volume requirement. It is evaluated as a control
on every ETF, not selected after looking at OOS cases.

The all-ETF selection file was sealed before OOS replay:
`2e2dcc5b12cdf26479c2e6f53c50a26d431923b10cd98480795facc51827358a`.

## Individual results

All figures below: January 2023–October 16, 2026, next-open fills, 5bp per side,
98% entry target, whole shares, zero idle-cash yield. Inherited virtual factor
state can enter the fresh OOS account at its first open, incurring costs.

| ETF | Selected range width / drift | Initial stop | Trailing exit | Failed-range / volume |
|---|---|---|---|---|
| GLD | 15% / 35% | 4 ATR | 20% from high | disabled / off |
| USO | 60% / 35% | 2 ATR | 8 ATR | 2 ATR / off |
| SOXX | 15% / 65% | 8 ATR | 8 ATR | disabled / on |

All three disable heat tightening. Widths refer to the prior q95/q05 band ratio,
not the full high-low range. Duration remains adaptive after parameter selection.

| ETF | Fitted CAGR | v1 CAGR | Buy-hold CAGR | Fitted Sharpe | Fitted max DD |
|---|---:|---:|---:|---:|---:|
| GLD | 20.10% | 3.27% | 23.48% | 1.111 | −24.05% |
| USO | −3.21% | 3.38% | 24.71% | −0.026 | −36.87% |
| SOXX | 32.11% | −0.46% | 46.95% | 1.123 | −28.74% |

Gold and semiconductors capture substantially more of their rallies than v1,
but with larger drawdowns than its largely idle exposure. The gold SMA200 control
earns 22.75% with −20.30% drawdown; shared-rule gold earns 21.78%. Shared-rule
SOXX earns 37.41%. The SOXX individual candidate already failed its IS guards.
USO passes IS guards but fails OOS: this result is retained, not retuned away.
USO is an oil-futures fund, not a spot-crude series.

Across all 52 ETFs, fitted OOS CAGR beats v1 in 35, buy-hold in only two, and the
shared rule in fifteen. Separate per-ETF optimization has not established an
advantage over pooled parameters. The report includes all losses/open episodes,
annual OOS results, six cost/delay cases, monthly versus event timing and complete
IS search surfaces. Statistical inference is descriptive: 1,000 paired 21-session
circular block samples with simultaneous max-t bounds over 52 comparisons to v1.

## Full-pool mapping

Only after individual choices and evaluations, apply selected/shared/v1 factors
to all 52 candidates using existing causal liquidity/duplicate admission,
parent/child overlap checks and six inverse-vol slots capped at45%. Unallocated
budget stays cash. Selection, active-only trading and 20% FR25 sleeves compare
monthly with event adoption (>10% L1 theoretical versus last adopted incl.cash,
plus risk exits). Frozen FR25 targets are repriced on the same v2 input batch,
ending at their original October12 cutoff; no newer economic targets invented.

| 2023–October12,2026 mapping | Net CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| Selected trading, event | 2.86% | 3.387 | −0.55% |
| Selected trading, monthly | 2.99% | 3.439 | −0.51% |
| v1 trading, event | 7.02% | 1.082 | −4.63% |
| Selected 20% tilt, event | 13.87% | 1.495 | −6.89% |
| Construction-matched FR25/M1 blend | 13.73% | 1.493 | −6.74% |
| Frozen FR25 | 16.51% | 1.450 | −8.65% |
| BIL buy-hold | 4.45% | 17.773 | −0.06% |

The new standalone sleeve's high zero-risk-free Sharpe is misleading if read as
risky breakout alpha. BIL earns $79,043 of $111,806 total net profit on the initial
$1m account; about half the portfolio remains unexposed. The common-rule BIL
signal persists, and inverse-vol construction plus the cap concentrates the sleeve
in BIL/cash. This is a portfolio-construction limitation, separate from individual
gold/SOXX signal improvement. No construction was retuned after seeing this result.

## Validation and disposition

The artifact set contains 56,160 fractional IS screens, 1,536 shared-engine IS
finalist/control replays, 1,872 individual OOS replays and 156 portfolio replays.
47 focused tests cover the new vectorized state machine, scalar/vector equality,
prefix/future-open causality, relative-range history, ratchets/gaps, screening
holdings, selection guards, data truncation, historical calendar and existing
admission/timing/input contracts. Native verification covers GLD, USO, SOXX,
selected trading and selected tilt; the acceptance receipt records exact status.

Research remains unpromoted. Useful evidence supports wider holding rules for
gold/semiconductors; the oil failure, limited independent cycles, poor general
buy-hold comparison and BIL-dominated mapping prevent a general validation claim.
Any further parameter or construction change requires a new registered experiment;
the inspected 2023+ interval cannot be presented as newly untouched data.

Source: `src/systematic_trading/research/range_calibration.py`.
Runners: `scripts/calibrate_range_breakout.py` and
`scripts/evaluate_range_calibration.py`. Frozen inputs, code, IS records,
selections, compact paths and native evidence:
`var/research/range-breakout-20261018-v2`.

Replay frozen fitting/evaluation with `PYTHONPATH` set to the study's `source`
directory and its `runner.py` stages `fit`, `seal`, `evaluate`. Portfolio/report
runner stages are `pool`, `native`, `report`, `accept`; it verifies critical live
calculation source equals the frozen snapshot before calculations. Do not rebuild
existing inputs from a new publication under the same study identity.

## Joint lifecycle v3 follow-up

The later operator request broadened fitting to all consequential parameters,
changed the split to pre2023 numeric fitting /2023 model selection /2024+ OOS,
and added a return/Sharpe/Calmar target with soft holding and wide-stop penalties.
The [v3 report](../research/range-breakout-20261018-v3/index.html) preserves v2 as
a separate control and uses the same pinned52 audited histories without copying
the input matrices. Fifty histories qualify for individual fitting; CPER/XLC use
shared numeric fallback. Existing histories provide15–20 IS years for the three
cases and extend to1993 in the broad pool, so stocks were unnecessary for length.

Thirty-three continuous/integer parameters are searched jointly with differential
evolution, because threshold-driven trades are not differentiable. Three search
objectives ×two seeds ×128 population ×30 generations yielded1,100,502 distinct
IS evaluations, plus exact shared-accountant finalist checks. Raw, weak/moderate/
strong penalties, chronological/local stability, shared parameters and continuous
50% shrinkage are compared. The objective uses45% scaled excess CAGR,40% excess
clipped Sharpe and15% excess regularized Calmar; all references are matched
buy-hold. Sharpe/Calmar levels are clipped separately to avoid a near-cash
denominator dominating optimization. Actual reported ratios remain uncapped.
Soft stop penalties begin above10% initial and20% peak-to-stop risk. These levels,
bounds and weights are predeclared design choices, not themselves OOS fits.

2023 selects a frozen variant and event/monthly clock using worst utility under
5bp,10bp and one additional session, preferring buy-hold return/drawdown guard
passes. If every variant fails, the best remains explicitly descriptive. All
52 choices are sealed before OOS. 36 pass2023 guards; the three motivating cases
all fail them. OOS selected CAGR GLD−0.19%,USO−4.11%,SOXX42.72%, compared with
buy-hold27.75%/36.67%/40.83%. Gold's fitted five-session follow-through rule,
not its6.1ATR initial stop, ends all six completed OOS signal episodes. Semiconductors
improve drawdown from−40.29% to−28.46%, but5/52 beat buy-hold CAGR overall and
none has a positive simultaneous lower bound versus buy-hold. BIL/SHY alone
have positive bounds versus v1. The later-period medians of common utility are
negative for every model family. Broad fitted width caps can also move the rule
away from the original literal compression premise.

Full-pool equal-budget trading produces7.24% event /8.39% monthly versus
matched momentum10.11%/11.94%. Inherited inverse-volatility trading2.75% is
BIL/cash dominated;20% FR25 tilt16.24% is near the matched blend16.20% and below
FR25 19.64%. Portfolio cutoff remains October12; individuals end October16.
No construction is selected from OOS and no strategy is promoted or tracked.

Source: `src/systematic_trading/research/range_joint.py`. The runner
`scripts/run_joint_breakout.py` has stages `prepare`, `fit`, `shared`, `validate`,
`seal`, `evaluate`; each existing study verifies its frozen source and parent
hashes. `scripts/evaluate_joint_breakout.py` seals construction before OOS and
runs `pool`, `native`, `report`, `accept`. `scripts/analyze_joint_breakout.py`
adds descriptive interpretation only. Set process `PYTHONPATH` to the isolated
`var/research/range-breakout-20261018-v3/runtime` for Numba0.67/llvmlite0.49;
the shared application environment is unchanged. The pure-Python lifecycle is
the checked reference. Do not regenerate inputs, choices or existing outputs
under a changed protocol; a changed fit is a separately registered experiment.

63 tests and scoped lint pass;7,320 reported individual OOS scenarios and204
pool scenarios retain compact metrics, with1,220 primary individual paths.
Five independent Windows-native jobs match exactly. Acceptance verifies
input/runtime/variant/selection/native manifests and recomputes primary metrics.
Further research should use several pre2023 rolling validation windows, pool or
remove weakly identified dimensions, and test explicit compression restrictions.
The already inspected2024+ period must remain labeled used historical evidence.
