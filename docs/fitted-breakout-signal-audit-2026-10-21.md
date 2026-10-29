# Individually fitted breakout signals: GLD, extrapolation, alpha and IC

October 21, 2026. Operator clarification: determine whether the algorithm fitted
separately to each ETF has predictive value, whether the earlier GLD claim is
true, and whether the signals help asset selection or an overlay on SOTA.
The preceding unfitted construction test is supplementary and does not answer
that question by itself.

**Decision: retain the corrected implementation and GLD observation as research
evidence; do not use this family as validated selection alpha or a SOTA overlay.**
Positive returns reproduce, but reliable incremental alpha does not. No running
service, monitored membership, funding, allocation or broker state changed.

- [Full signal-first dossier and standard overlay report](../research/fitted-breakout-audit-20261021-v1/index.html)
- [Frozen protocol](../research/fitted-breakout-audit-20261021-v1/protocol.json)
- [Compact summary](../research/fitted-breakout-audit-20261021-v1/summary.json)
- [Sealed per-ETF fits](../research/fitted-breakout-audit-20261021-v1/sealed-fits.json)
- [All per-ETF returns and alpha](../research/fitted-breakout-audit-20261021-v1/asset-results.json)
- [Time-series IC](../research/fitted-breakout-audit-20261021-v1/information-coefficients.json)
- [Cross-sectional IC](../research/fitted-breakout-audit-20261021-v1/cross-sectional-ic.json)
- [Portfolio comparisons](../research/fitted-breakout-audit-20261021-v1/portfolio-results.json)
- [Native checks](../research/fitted-breakout-audit-20261021-v1/native-checks.json)

## Implementation review

`range_lifecycle.py` remains frozen for historical reproduction and the existing
historical candidate. The separate versioned `breakout_revisit.py` corrects:

1. One-close confirmation previously waited for a second close unless the volume
   shortcut happened to fire. Eleven of the 52 original short-domain fits request
   one-close confirmation.
2. Execution-delay stress delayed entries, but exits still used the next open.
3. Exit checks skipped the entry-session close.
4. Continuation re-entry could bypass the cooldown check.
5. The scanner consumed filled-position state and then traded next open, adding
   another session relative to the underlying close-time decision. The new API
   exposes decision state separately from held exposure.

The corrected contract also freezes initial-risk ATR at confirmation and funds
entry fees from available cash. These are explicit versioned conventions; they
must not silently rewrite old fitted results. The new stops remain close-based
signals executed at the following open, with gap risk, rather than intraday stop
fills. A portfolio eligibility signal is a virtual per-ETF regime, not a broker
stop attached to the portfolio's own entry price. No production migration was made.

## Inputs and fitting

Pinned publication batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`,
verified source and derived hashes; adjusted OHLC and separately audited raw
volume. All 52 supported ETFs are examined; BIL is the cash benchmark, leaving
51 risky ETFs for the inference family. BWX/XOP listing holds remain intact.
No provider archives or online prices are research inputs. USD only; no FX claim.

Two existing structural domains are fitted separately to each ETF. Each fit uses
200 random vectors, its anchor and 40 mutations; the best 15 training candidates
are rescored at 5/10/20 bp and zero/one added execution sessions. Selection uses
the original return/Sharpe/regularized-Calmar objective with its chronological
stability terms, but correct initial-capital anchoring. Training evidence requires
five closed trades and 5% exposure. A fit without that evidence remains labelled
insufficient and supplies no portfolio eligibility.

- Fit through 2022; evaluate January 3, 2023–October 16, 2026.
- Independently fit through 2019; evaluate January 2, 2020–December 30, 2022.
- Warm-up 252 sessions; at least 500 subsequent training sessions. CPER and XLC
  cannot satisfy the earlier requirement and receive no later-trained fallback.
- Later fits may start from the original own-ETF pre-2023 vector. Earlier fits
  start from the domain midpoint and cannot import those later-trained vectors.
- The original highly optimized GLD vectors and their pre-2016 procedure-test
  vectors are audited separately. Their search budget was much larger than the
  bounded pool refit; they are not interchangeable with the new GLD pool fit.
- Also test unchanged GLD parameters transferred to every other ETF, separately
  from individual fitting. No test-period winner selection or parameter retuning.

Both periods and the underlying price paths were previously inspected. These are
chronological development tests, not untouched confirmation. A retrospective
price-supported cohort is not historical membership or publication-vintage proof.

## Is the GLD result true?

Yes, as a historical lower-exposure strategy. Corrected execution of the original
GLD fits, 2023–October 16, 2026 at 5 bp:

| Rule | CAGR | Sharpe | Max drawdown | Annual alpha | 21-session state IC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original short fit, corrected | 9.47% | 1.004 | -12.19% | +0.84% | +0.127 |
| Original long fit, corrected | 11.63% | 1.290 | -11.35% | +3.29% | +0.025 |
| GLD buy-and-hold | 24.00% | 1.171 | -26.40% | Benchmark | — |

Alpha is the annualized intercept after controlling for the same ETF's daily
return above BIL; it is not simply CAGR minus buy-and-hold CAGR. Overlap-aware
approximate p-values are weak: short alpha 0.832 / IC 0.250; long alpha 0.377 /
IC 0.832. The long rule has only three completed evaluation-period trades.

Its earlier independent procedure test still fails: fit through 2015 and test
2016–2022 gives corrected long CAGR 0.58%, Sharpe 0.108, DD -22.86%; short CAGR
1.08%, Sharpe 0.166. Thus the favorable GLD path is real, but it does not validate
the fitting procedure or establish persistent alpha. Differences from old printed
metrics include restoring the preceding-session anchor/first evaluation return.

The new bounded own-ETF GLD short refit earns 7.26% with negative alpha; the long
refit retains the original long vector/result. Do not substitute the better
original GLD short outcome for the new pool procedure's outcome.

## Does individual fitting extrapolate?

Base cost, corrected refits. Positive-alpha counts exclude numerical values below
1e-8 annually: an effectively buy-and-hold path is zero alpha, not a positive hit.

| Evaluation | Domain | Available risky ETFs | Positive CAGR | Beat buy-hold CAGR | Positive alpha | Positive alpha after Holm | Median state IC21 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020–2022 | Short | 49 | 32 | 21 | 21 | 0 | -0.101 |
| 2020–2022 | Long | 49 | 31 | 22 | 21 | 0 | -0.039 |
| 2023–2026 | Short | 51 | 39 | 2 | 1 | 0 | -0.097 |
| 2023–2026 | Long | 51 | 37 | 2 | 3 | 0 | -0.054 |

Later-period materially positive point estimates are SOXX short and GLD/PPLT/SLV
long. None is reliable after the 102 ETF/domain test adjustment. SOXX and SLV
reverse alpha sign in the earlier test; GLD long is effectively buy-and-hold
(zero alpha) there; PPLT's positive estimates are statistically weak in both eras.
These are diagnostic observations, not selected investments or promotion candidates.

Only 3/51 short and 5/51 long refits beat buy-and-hold Sharpe in the later era
after treating numerical ties as ties. Primary IC is undefined for constant
signals: 45 short and 48 long have usable later-period state IC. No later positive
state IC survives Holm correction; one earlier long-domain exception does not
establish later extrapolation.

Daily cross-sectional IC is the relevant ranking test. At 21 sessions in the
later era, mean state IC is +0.006 short / -0.034 long; extension/ATR IC is
-0.003 / -0.019. None is convincing. Earlier long-state cross-sectional IC was
positive, but did not persist. Merely copying GLD's parameters elsewhere also
does not establish broad superiority; full results retain that distinct control.

IC labels start at the next executable open and end at close t+h; 5/21/63-session
labels remain wholly within each evaluation window. State, entry event and
extension scores are tested separately. Newey–West adjustment handles overlap
approximately. Holm controls the declared asset/domain families, but neither
method removes prior research selection or turns these data into a pristine test.
Standalone cash earns zero; BIL-excess alpha therefore includes cash opportunity
cost. The portfolio tests below actually park unused capital in BIL.

## Asset selection and overlay on SOTA

January 3, 2023–October 12, 2026, all 52 candidates, same published panel and
shared app accounting, 5 bp/side. Selection uses the existing causal raw-dollar-
volume admission mask, six fixed slots, positive momentum ranking and replacement
below rank eight. It tests fitted short/long-union eligibility against the same
selector without lifecycle gating. Overlay scales each frozen FR25 weight by
`0.5 + 0.25*short_state + 0.25*long_state`, parks removed weight in BIL and
preserves core cash. Dynamic adoption is month-end or cash-inclusive L1 >=10%;
fixed-monthly controls are explicit.

| Portfolio | CAGR | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: |
| FR25 SOTA | 16.51% | 1.450 | -8.65% |
| Fitted lifecycle selection, dynamic | 6.87% | 0.593 | -13.29% |
| Matched momentum selection, dynamic | 10.60% | 0.781 | -14.36% |
| Fitted lifecycle overlay, dynamic | 12.34% | 1.395 | -7.55% |
| Fitted lifecycle overlay, monthly | 12.71% | 1.411 | -7.81% |
| Constant exposure-reduction control | 13.43% | 1.593 | -6.00% |

All three 21-session block-shuffled dynamic overlay controls beat the real overlay's
Sharpe (1.437/1.459/1.628 versus 1.395); matched monthly placebos also beat the
real monthly overlay. They are non-deployable diagnostics, not candidate strategies.
The constant control estimates exposure multipliers from training data only.
Its stronger risk-adjusted result means lower exposure explains more than the
breakout timing. It still loses more than the declared one-percentage-point CAGR
guard versus SOTA and is not selected/promoted from this test.

All 24 selection/overlay SOTA gates fail across 5/10/20 bp and 0/1 extra sessions.
Dynamic overlay turnover is about 8.5x/year, cost 42.7 bp/year; the rejection uses
net outcomes, not the retired absolute annual cost ceiling. The original frozen-
fit overlay is also retained as a control; its monthly Sharpe near FR25 comes
with materially lower returns and does not establish incremental prediction.

## GLD visual inspection requested by the operator

[Interactive GLD ranges, signals and exits](../research/gld-breakout-inspection-20261021-v1/index.html)
replays the original GLD fits with corrected execution, without refitting. It
contains all 39 short and 13 long historical trades, exact prior-window boxes,
206 raw upward crossings, confirmation decisions, next-open buys/sells, stop
decomposition, daily values and CSV exports. The range uses prior closes only;
the displayed historical box is recognized at its crossing, not at its start.

The first post-2022 short trade uses a 21-session February 9–March 10, 2023 box,
confirms March 13 and buys March 14 at $177.35. Its initial effective stop is
$168.75; trailing activates at $188.24 on April 13, with the heat flag already
set. It sells April 17 at $185.89 after the April 14 closing exit decision.
The first post-2022 long trade uses a 756-session March 30, 2020–March 29, 2023
box, crosses March 30, confirms April 11 and buys April 12 at $187.54. Its
initial effective stop is $166.89; trailing activates at $207.69 on April 1,
2024. It sells April 11 at $216.85 after the April 10 exit decision.

There is no fixed take-profit order: the profit threshold activates a ratcheted
close-based exit. The heat flag is sticky and may be set before activation;
it only tightens the trail once that trail exists. Intraday touches do not sell.
This distinction and the long delay before activation are explicit in the chart.
All 2,930 held-close stop levels reconcile exactly; prior quantiles and actual
fill prices/dates are checked. Seventeen focused tests pass (eight new plot
evidence tests plus nine existing simulator tests). Offline Node checks exercise
all trade/crossing selectors, overlays, zoom, cursor/pin and CSV alignment.
The static plot was visually checked. The browser tool blocked the local-file
URL; no browser layout certification is claimed.

## Verification and next action

3,096 per-ETF return/alpha cases; 516 IC records with three signals and three
horizons each; 102 matched portfolio cases. Every corrected per-ETF path reconciles
to an independently calculated event ledger. Selected fits reproduce their
truncated training prefix exactly. Three independent native Windows LEAN checks
(dynamic overlay, delayed dynamic overlay, dynamic selection) have zero NAV
difference. Focused regression suite: 41 passed; repository Ruff passes. The
shared report's actual allocation renderer passes its Node contract test, holdings
reconcile to NAV, and the scientific figure was visually inspected. No full
browser-layout certification or running-app publication verification is claimed.

Do not rescue this family by selecting successful ETFs or retuning exits on the
same evaluation sample. The next justified research question is incremental
signal value on a qualified parent and chronological validation, not a larger
search over this inspected outcome. The full-pool cash-relative net replay remains
open in the broader plan. Any larger ETF wave must first add distinct exposures,
resolve identity/coverage, and publish audited histories before testing; the old
299-record inventory is a dated admission backlog, not a currently approved pool.

Compact fits, protocols, source recipes, results and validation receipts are
retained. Supplementary unfitted study:
[report](../research/breakout-revisit-20261021-v1/index.html). It has 136 replays
and three exact native checks, but used price-supported membership without the
legacy dollar-volume mask and is not the evidence for individually fitted alpha.
Its preflight tuple/JSON comparison error was repaired before any results; the
original preflight protocol remains recorded. No source batches were fetched,
changed, deleted or silently substituted.
