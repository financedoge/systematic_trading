# Strategy health: learning from losses without chasing the latest noise

Status: research-only controller implemented and tested; warning timing audited
on existing frozen trades. Adaptive entries/exits, online refitting and their net
returns are not yet implemented or validated. The operator accepts the proposed
three-timescale/spectral direction and asks that performance feedback be included.
This document extends that direction; it does not replace the market model.

Follow-up: the [single-large-loss experiment](loss-feedback-results-2026-10-26.md)
now implements actual changed-trade simulation for streak and severity/stop
responses. It reduces WEAT's damage but fails broad return preservation, with
slow recovery hurting GLD and other winners. This original controller definition
is retained as tested historical evidence; its strict response is not endorsed
for general adoption. Online market-model refit benefit remains untested.

## Two different hidden questions

The market model estimates structural, intermediate and fast states, with joint
uncertainty. The health controller estimates whether the current *trading policy*
deserves continued risk. A losing run does not prove a downward market or justify
forcing an HMM label. A sound market classifier can also have poor entry/exit
rules. Conversely, an effective trend follower can lose several small trades
before a large winner. State uncertainty, trade outcomes and execution problems
must be inspectable separately.

The current WEAT hypothesis has at least two mechanisms to examine:

1. Confirmation arrives after most of a brief rebound, so an apparently strong
   upward probability offers little remaining reward relative to downside.
2. The entry captures a real rise, but slow exit confirmation and broad protection
   give it back. Tightening entries alone would not repair this second case.

Use the existing trade ledger to distinguish these failures. Favorable/adverse
excursions and local extrema are hindsight diagnostics, never entry-time labels
silently made available to a historical trader.

## A concrete first controller

Maintain a separate controller for each ETF/strategy version. Let r_n be its
completed net trade return after both entry and exit fees/slippage; d_n > 0 is
the initial planned risk fraction known at entry, and R_n = r_n/d_n. This planned
risk is a normalization, not a bound on gap losses. Observe outcomes only when
the exit and costs are known. Partial exits form one position episode; they do
not manufacture multiple losses. A zero net return breaks the losing run but
does not count as a recovery win.

The consecutive-loss statistic is

`L_n = (L_(n-1) + 1) * 1[r_n < 0]`.

The proposed states and exact reference-controller constants are:

| State | Entry or exit rule | Risk budget multiplier |
|---|---|---:|
| Normal | Default; move to defensive after 3 consecutive net losses | 1.00 |
| Defensive | Move to paused at 4 consecutive net losses; return to normal after 2 consecutive positive trades and positive sum R and compounded return since entering defensive | 0.50 |
| Paused | No new exposure; emit one refit-review event; retain one declared shadow candidate | 0.00 |
| Probation | Enter after the last 4 fresh shadow trades include at least 3 wins, positive sum R and positive compounded net return | 0.25 |
| Probation recovery | Last 3 actual probation trades include at least 2 wins, positive sum R and positive compounded return: return to normal | 1.00 |
| Probation failure | 2 consecutive actual losses: pause and request another review | 0.00 |

All changes take effect no earlier than the next session after the evidence is
known, plus any additional tested execution/computation delay. These constants
are a proposed starting recipe, not results of optimization. The loss that raises
an alarm has already occurred: a backtest cannot erase it by reducing risk earlier.

The risk multiplier caps both the allocated notional budget and initial loss
budget; a tighter stop must not quietly increase position size and undo the cut.
For a long position, use

`weight <= min(h * base_notional, h * base_risk_budget / initial_risk_fraction)`.

The prototype emits only decisions; it places no orders and does not change the
existing trading simulator. Its actual outcomes come from the strategy *after*
previous decisions. An unchanged baseline ledger cannot stand in for those
outcomes once an adaptive entry or exit differs.

## Recent return and win rate as additional evidence

Report a decayed win fraction and risk-normalized expectancy. With trade half-life
H = 4 as an initial diagnostic constant, let lambda = 2^(-1/H):

`W_n = lambda*W_(n-1) + 1`
`U_n = lambda*U_(n-1) + R_n`
`V_n = lambda*V_(n-1) + 1[R_n > 0]`
`recent_expectancy = U_n/W_n; recent_win_rate = V_n/W_n`.

These are descriptive estimates, not calibrated probabilities of profitability.
Win rate alone ignores the relative size of gains and losses. Do not compute a
trade Sharpe on 3–4 outcomes and treat it as a reliable regime diagnosis. Daily
net Sharpe can be monitored over a declared sufficient history, with uncertainty
and serial dependence, but cash exposure can also change the ratio. Keep an
always-running, frozen reference simulation beside the actually traded policy
so reducing size or pausing does not falsely appear to repair the underlying edge.

A later extension should catch cumulative deterioration interrupted by small
winners. For a completed trade, standardize against training-only expected
outcomes for the relevant context:

`z_n = (R_n - mu_0(context_n)) / sigma_0(context_n)`
`C_n^- = max(0, C_(n-1)^- - z_n - k)`.

An alarm when C^- exceeds h detects a sustained shortfall. Context, mu_0, sigma_0,
k and h must be fixed before evaluation; calibrate repeated-alarm rates using
chronological training and dependence-preserving blocks. Daily predictive-return
residuals can supply an additional earlier warning, but actual and reference
series must be monitored separately and idle-cash observations must not count
as evidence that the trading signal recovered. This detector is specified here,
not activated by the current streak-only prototype.

This use of sequential shortfall follows the CUSUM construction described by
[NIST](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm). The
financial calibration, risk actions and thresholds are our proposed research
design. A threshold is not a market-change probability.

## Defensive execution for short-lived rebounds

Cutting risk can limit damage but does not fix late entries. Declare two separate
candidate mechanisms before fitting:

**Limit chasing.** Require positive expected net payoff relative to initial risk,
and reject an entry if its price has moved too far above the causal fast latent
price. One dimensionless extension feature is

`E_t = (log(P_t) - fast_log_level_(t|t)) / sigma_t`.

Fit the extension limit on training data, conditional on slow context if coverage
permits; retain shrinkage when context samples are sparse. Buying after a stronger
upward-probability threshold may make entry even later. An earlier change signal
with smaller risk and explicit invalidation is an alternative hypothesis, not
permission to buy any falling price.

**Protect a rebound as it matures.** A proposed close-tested long protection is

`stop_t = max(stop_(t-1), entry_price - k_initial*sigma_entry*entry_price,`
`             max_held_close_t - k_trail(context_t, health_t)*sigma_t*entry_price)`.

Lower k_trail in slow-down/uncertain context and in defensive/probation health;
allow more room in a confirmed slow uptrend. The adopted stop never moves down.
Test the previously adopted level before updating it from the current close,
then fill at the next permitted open. A gap can overshoot the stop. If current
volatility/volume shocks imply a smaller risk tolerance, reduce k or size under
a declared rule; multiplying by larger volatility alone would widen protection.
Separate that hypothesis from the first constant-volatility control.

Also test exiting on a deterioration of the fast upswing before a fully confirmed
downtrend. The expected trade-off is earlier protection versus more false exits.
Evaluate it across GLD and other successful ETFs as well as WEAT; a rule selected
only because it repairs WEAT's inspected trades is development evidence.

## Refitting, recovery and version discipline

Four losses request a refit review; they are too few observations for unrestricted
re-estimation of three latent layers. First diagnose data/execution errors, entry
extension, exit giveback and distribution changes. Prefer a bounded fast-layer/
exit-policy update, regularized toward the current model. Change intermediate or
structural dynamics only if their own predictive evidence supports it.

A possible regularized fit at alarm time t is

`theta_new = argmax_theta [sum_(s<=t) w_(s,t)*log p_theta(x_s | I_(s-1))`
`                          - penalty(theta, theta_old)]`.

Weights may depend on the inferred probability of relevance to the current
environment, using only information known by t. Specify that mechanism before
fitting; do not use a full-sample change-point label. Any forward-return training
label must have matured by the cutoff; purge overlapping labels/trades across
inner chronological validation. Select the bounded fast/risk policy by matched
net performance, with return/drawdown guards, costs and delay stress.

Only one challenger is staged per pause in the reference controller. A candidate
records its training cutoff and actual availability; it cannot act before
availability. Historical replay used to fit/select it does not count as fresh
recovery. Shadow trades must enter after both the pause and candidate availability.
Replacing the candidate clears its recovery evidence. If no challenger qualifies,
the frozen incumbent may demonstrate fresh recovery in shadow; a pause does not
require risking money to collect evidence. Few opportunities can mean a long
pause. The strategy may abstain rather than fabricate evidence from a calendar
timeout. Recovery proceeds at reduced risk and can fail again.

Keep actual and hypothetical ledgers separate. Health records retain version,
event ID, entry/exit/known timestamps, costs, initial risk, reason, fitted cutoff,
availability, and earliest action time. Refitting does not erase actual historical
P&L, drawdown or the alert that requested it. Application-owned analytics would
perform recurring inference/refitting if this were later promoted; an agent or
automation must not be its runtime.

## Incorporation into the accepted next study

Keep only three principal model families in the user report:

1. A matched two-timescale market model.
2. The proposed structural/intermediate/fast duration-aware hierarchy.
3. That hierarchy plus causal time-frequency features.

Apply the same declared health-controller recipe to each family. Retain paired
feedback-disabled controls to separate the controller's contribution from a
better market model. Compare event-triggered refit/adoption with a fixed-interval
control under matched candidate/search budgets; do not confuse refit timing with
portfolio rebalance timing. Continue dynamic versus monthly target adoption,
including cash and the last adopted target, at the portfolio layer.

Proceed in stages: full-pool diagnostic atlas and loss mechanisms; synthetic
known-regime and causal-prefix checks; chronological recognition/forecast tests;
then actual adaptive trade simulation. Show realized net returns/Sharpe/Calmar,
costs, drawdown and missed winners, together with false alarms, detection delay,
time paused, refit count, recovery delay and parameter movement. Inspect both
worst remaining ETFs and formerly good ETFs damaged by adaptation. Preserve the
current weakest training-selected ETF chart in every handoff. Use FR25, simple
controls, cash and buy-and-hold as empirical comparators. All inspected historical
episodes remain development data; reserve a subsequently sealed prospective slice.

## Current deliverables and methodological references

The completed warning audit covers all 51 later and 49 earlier risky ETF cases,
using the training-selected primary policy and a neutral health start at each
evaluation boundary. Existing return results retain their original carried-position
accounting; carried-in outcomes are excluded from this new streak diagnostic.

WEAT's first three newly entered closed trades all lose. The third closes on
June 29, 2023, with original cumulative return already -17.21%; the first possible
reaction is June 30. The fourth closes on August 1, 2023 at -20.28% cumulative;
the first possible reaction is August 2. These are timing observations, not the
returns an adaptive policy would have achieved. A defensive policy after the
third loss may change the fourth trade, which then needs actual resimulation.

| WEAT trade | Best held-close gain, gross | Realized net return | Diagnostic |
|---|---:|---:|---|
| January 3–11, 2023 | 0.00% | -6.99% | No favorable close above entry |
| February 15–27, 2023 | 0.00% | -9.01% | No favorable close above entry |
| June 16–29, 2023 | +8.75% | -2.18% | A real upswing was given back |
| July 21–August 1, 2023 | +7.09% | -3.71% | A real upswing was given back |

Seven of WEAT's ten losing trades had a positive gross held-close excursion;
the minimum among these was only +0.17%, so the count alone does not establish
meaningful profit opportunities. The June/July examples are stronger evidence
for testing a faster exit. Favorable close excursions exclude the exit day's
post-fill close; they are not claims of attainable peak-sale returns.

Three-loss runs occur in 37/51 later cases, including 27/41 ultimately profitable
cases; four-loss runs occur in 22/51, including 13/41 profitable cases. Earlier,
39/49 have three-loss runs, including 24/32 profitable cases; 28/49 have four-loss
runs, including 17/32 profitable cases. These are not estimates of false-positive
rates for genuine regime changes: profitable whole-period outcomes can still
contain real deterioration. They show why an irreversible shutoff can sacrifice
good strategies. GLD has a three-loss run in both eras; its selected later policy
still returns +58.32%. Earlier weakest MCHI has a maximum run of 13 losses.

For scale only, under an independent 50/50 win/loss toy model the probability
of at least one three-loss run in 14 trades is 64.79%, and of a four-loss run is
34.87% (exact recursion, checked against enumeration). This is not a financial
null model or a p-value for WEAT. Repeated monitoring must be calibrated.

The controller/audit have 17 passing focused tests, including delayed knowledge,
duplicate/backdated outcomes, forward-only recovery, failed probation, policy
identity, causal prefix invariance, and exclusion of exit-day future prices.
WEAT and MCHI warning charts were visually inspected. No adaptive return uplift
has been calculated, and no new market-state model has been fitted this session.

- [Warning audit and WEAT/MCHI charts](../research/strategy-health-20261026-v1/index.html).
- [Existing all-ETF trend inspection](../research/latent-slope-20261025-v1/index.html).
- [Accepted regime/spectral direction](regime-hierarchy-direction-2026-10-26.md).
- [NIST CUSUM construction](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm).
- [Lo, The Statistics of Sharpe Ratios](https://alo.mit.edu/publications/page/18/): estimation uncertainty and serial dependence.
- [Gama et al., A Survey on Concept Drift Adaptation](https://doi.org/10.1145/2523813): distinguish detecting change, adapting and evaluating the adaptation.

Web references supply methodological background only. All numerical ETF
diagnostics use the pinned audited-history artifacts of the previous study.
