# Hard posterior resets — 26 October 2026

The operator proposes resetting Bayesian memory after a large drawdown or 3/4 loss
streak, optionally after a high-probability HMM regime change. Implemented and
tested across all 52 supported ETFs, two chronological eras and six frictions.
This is single-ETF research; all overlays/rebalancing remain deferred.

[Report, mathematical definitions and every ETF chart](../research/reset-policy-20261026-v1/index.html).
Default weakest case is INDA later; the earlier weakest button opens PPLT. GLD,
WEAT and TLT inspection figures are also retained. Earlier frozen work unchanged.

## Memory audit and scope

The previous policy learner did not retain years of unweighted outcome counts:
training evidence was capped at 4 effective trades per candidate (median 2.49),
decayed with a 126-session half-life, and warning acceleration multiplied old
evidence by 0.25. Median selected-policy count immediately after those warnings
was 0.59. This does not mean every parameter adapted quickly: the latent filters,
HMM parameters, daily volatility estimate and nine-candidate policy grid remained
based on the original fit. Slow policy learning also reflects delayed outcomes.

This study resets the learned policy payoff/win statistics. It does not refit
HMM emissions/transitions, Kalman noise or range geometry. Ordinary filtered HMM
state transitions are not evidence that its generative parameters changed.

## Three predeclared algorithms

A is the exact previous continuous Bayesian learner (previous B), with no
warning acceleration. B adds hard resets on the 3rd/4th actual consecutive net
loss, first marked loss below minus tau per position, realized loss below minus
tau, or account drawdown since start/last reset at least max(10%,2tau). Tau is
the training winner-return sample SD with at least 5 winners, floored at 2 fees/1e-6.
Missing winner sigma disables the sigma loss trigger; drawdown then uses 10%.
Ordinary losing-stop exits alone do not reset. These triggers differ from the
previous 75%-forgetting study, so that comparison is not a pure reset-size test.

At reset close r, set N_j=S_j=W_j=fresh_j=0 for all 9 candidates. Retain the proper
neutral Normal(0,1/4) payoff prior and Beta(1,1) win prior. Training payoffs are
not reimported. Admit a completed shadow trade only if its entry fill was after r;
discard pre-reset and straddling trades, including same-close outcomes. The
current policy is the operational fallback until new evidence justifies changing.
The current position, adopted stop and queued orders stay binding. Reset does
not force liquidation, rearming, a policy switch, or a trading pause.

C adds a confirmed fast-HMM transition. With filtered previous state alpha,
transition matrix A and today's emission likelihood L:

    J_t(i,j) = alpha_(t-1)(i) * A_ij * L_t(j) / normalizing_sum
    q_t = 1 - trace(J_t)

Require q_t>=0.8 and the destination state's probability>=0.9 for 3 consecutive
closes, including t. Act only at the third close. This is filtered joint
transition probability, not a difference between posterior vectors and not the
probability of structural parameter drift. Use the existing fast HMM for every
ETF, including when its selected trading rule uses Gaussian-slope probabilities.
Shared reset cooldown 20 sessions; HMM reset cooldown 63 sessions. Forward inference
only; no historical action based on later confirmation. Thresholds were frozen
before outcomes and were not relaxed after seeing sparse coverage.

Other learning/execution settings match A: independent candidate payoff means,
daily forgetting, Normal posterior mean S/(4+N), SD 1/sqrt(4+N), selection score
mean-0.25SD and a 0.05 switch margin, one fresh qualifying shadow close needed before
adopting a candidate. Per-policy net ROI/(sigma*sqrt(held sessions)) clipped to ±3
for learning, never for P&L. Beta win-rate diagnostic is not an additional
independent likelihood. Contextual wide/tight stop distances and entry/down-exit
confidence are selected from the same 9 tuples. Adopted stops never loosen.

## Results

Primary next-open fills, 5 bp each side,2023-01-03..2026-10-16:

| ETF | Continuous A | Loss reset B | Loss + HMM reset C |
|---|---:|---:|---:|
| GLD | +88.30% | +90.66% | +90.66% |
| WEAT | -10.69% | -13.88% | -13.88% |
| TLT | -12.59% | -17.66% | -17.66% |
| PPLT | +3.66% | +36.93% | +36.93% |
| INDA | -16.75% | -18.99% | -18.99% |

| Era | Algorithm | Median Sharpe | Median CAGR | Within A return/DD guards |
|---|---|---:|---:|---:|
| Later | A | .284 | 2.15% | 100% |
| Later | B | .370 | 2.76% | 72.5% |
| Later | C | .370 | 2.76% | 72.5% |
| Earlier | A | .195 | 1.29% | 100% |
| Earlier | B | .217 | 1.19% | 69.4% |
| Earlier | C | .217 | 1.35% | 69.4% |

Median Sharpe improves versus continuous learning, a limited positive. Neither
reset arm passes the declared full-pool acceptance in any of 12 era/friction cases:
require improved median Sharpe/lower-quartile CAGR and>=90% risky ETFs within 1 pp CAGR / 
2 pp DD of A. Original frozen median Sharpe .412/.276 is still higher. B improves
return on 21/51 later and 23/49 earlier cases; ties are possible, so the remainder
is not automatically all worse. C has the same improvement counts versus A.

HMM-trigger-involving resets occur in 4/51 later risky ETFs and 14/49 earlier ETFs;
two earlier events coincide with loss triggers. No extra HMM reset occurs in GLD,
WEAT or TLT. It improves return versus B on 3 ETFs per era; pool medians are largely
unchanged. Sparse threshold coverage limits conclusions about HMM-guided learning.
The earlier PPLT case is materially worse: A -26.42%, B -31.77%, C -40.98%.

## Why forgetting can still be slow

WEAT C has 261/951 sessions with no newly qualifying shadow payoff since the latest
start/reset, compared with 2 for A. It still completes 15 actual trades, so this is
not a trading pause. The initial-training evidence can exist before the first
evaluation close; after a hard reset, the count is truly zero until a qualifying
new trade closes. Median no-fresh fractions A/B/C are 2.5%/11.4%/11.4% later and
4.9%/16.0%/18.1% earlier. An evidence reset can make adaptation wait longer.

The warning date is not necessarily the market change date. A three-loss warning
arrives after several potentially informative observations; erasing them all
discards evidence about the new conditions. Preserving no data before the alarm
is a stricter and often less useful rule than retaining information after an
estimated earlier change boundary. No retrospective boundary was fitted here.

## Weakest cases

**INDA later C: -18.99%, Sharpe -.430, DD 35.25%,11 closed trades / 3 wins.** Three
resets,230 sessions without fresh qualifying payoff evidence,15 rejected candidate
outcomes (correlated shadow observations, not 15 distinct actual trades).
Frozen strategy -5.60%; buy-and-hold +14.46%. The 2024-12-03..2025-02-27 trade loses 10.82%.
A marked-loss reset on 2025-02-14 retains policy 5; its initial distance was 11.25%
of entry. Resetting beliefs neither tightens that adopted risk nor forces exit.
Later 3-loss resets on 2026-01-21 and10-01 also retain current policy2. Memory
clearing alone cannot repair poor entry/exit/context inference.

**PPLT earlier C: -40.98%, Sharpe -.802, DD 44.20%,34 closed trades / 10 wins.** Fifteen
resets,359/756 sessions without fresh evidence,117 discarded candidate outcomes.
The additional 2020-03-30 HMM reset changes the subsequent path; B ends -31.77%.
Do not attribute the entire long-run difference mechanically to one isolated
trade: the endogenous reset/selection paths diverge after it.

**TLT diagnostic:** all three preserve the 2023-11-06..2024-01-05 rebound for +11.43%.
Its full-period deterioration has other causes; e.g. reset arms enter 2024-06-06
and lose 2.20% to July 2, versus A's June 7 entry losing 1.04%. The July 17–September 27
trade earns 5.51% for reset arms versus A's July 18 entry +5.78%. Do not recycle the
previous experiment's November early-exit explanation for these different paths.

## Recommended next design, not yet fitted

Use predictive evidence that the market model has become wrong as a structural
reset cue. Maintain an incumbent and a fresh challenger rather than erasing all
useful information immediately. Initialize the challenger from a plausible recent
change boundary, which may precede the alarm; use only data available at that time.
Let daily causal marked rewards/predictive errors provide information without
waiting for whole trades to close. Weight/adopt the challenger using subsequent
predictive performance with retained uncertainty. This is compatible with the
accepted multiscale direction and explicit risk/exit/re-entry separation.

A recurrent HMM state change can instead select a stored state-conditional model.
Changes in likelihood/predictive calibration suggest refitting its parameters.
A proper change-point/run-length posterior is one candidate for that distinction.
Do not assume a high up/down state probability is high structural-change confidence.
Independent hard risk limits remain necessary: resetting beliefs is not an SL.

This experiment does not validate full market-model reset or those proposed
challenger/daily-reward mechanisms. Continue single-ETF work before overlays.

## Verification and provenance

Protocol0b2857f166d62a570bbc4e38a34501df903e10e07a940d8006b357e8b093241d;
chart-cache hashfb9910c4c6e765901171fd7355f00d1a835d574cc906cc18db8f85444b6d51b6.
Parent52a79975a9ac143da7659fc2631bec4db88004647a2e3fb54ac141210c923635 and
published batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd
verified. Adjusted prices for returns; audited raw volume is chart context only.
Both eras already inspected development evidence; publication-vintage limits
remain. No downloaded provider histories or external prices used.

15focused tests,612exact continuous-learning controls with zero NAV error,
independent cash/share ledger within 5.6e-15,306 offline chart combinations. Five
static figures and nine equations prepared; figures/controls visually inspected
without claiming browser-layout certification. Three native Windows executions
match the application whole-unit reference exactly; not an independent test of
online learning or exact fractional NAV. Native/fractional terminal returns:
WEAT -13.82%/-13.88%, INDA -19.04%/-18.99%, GLD delay 1 +115.13%/+116.26%; maximum
GLD normalized path difference 1.35 pp. No runtime, promotion or broker effects.

Method references: [Bayesian online change-point detection](https://arxiv.org/abs/0710.3742)
and [discounted Bayesian learning](https://arxiv.org/abs/2305.10718). The former
models generative parameter changes; it was not implemented in this study. Neither
reference establishes profitability of the tested ETF reset rules.
