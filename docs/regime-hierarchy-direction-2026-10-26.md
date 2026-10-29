# Next direction: structural context, multiple timescales and spectral diagnostics

Status: research direction accepted by the operator; not a fitted strategy or a
frozen new numerical protocol. The accepted extension adds a separate
[strategy-health controller](strategy-health-framework-2026-10-26.md): loss
feedback, defensive risk, paused refit review and forward-only recovery.
The operator suggests that TLT's later weakness reflects a multi-year range or
structural change, asks about three interacting timescales and Fourier analysis,
and rejects treating FR25 as an unquestionable gold standard. This session changes
inspection/reporting only; all existing fits, policies and performance remain fixed.

## What the current evidence supports

The latest model is two continuous Kalman slope filters plus one fast HMM,
not two HMMs. All 102 slow smoothness ratios and 100/102 fast ratios reached the
declared upper bound. Its weights eventually become effectively fixed. Adding
another similar filter does not itself solve timescale identification or adaptation.

On the same pinned audited adjusted history, TLT declines 34.32% between the first
2021 close and the last 2022 close. It then falls another 15.59% between January 3
and October 31, 2023. From January 3, 2023 to October 16, 2026 the endpoint change
is -8.13%, with adjusted closes between 72.8334 and 93.9110. From November 1, 2023
to October 16, 2026 the change is +6.53%, with repeated reversals visible. These
are first-close/last-close descriptions, not strategy returns or formal estimates
of a structural-break date. The long range hypothesis is plausible, especially
after late 2023; do not automatically impose January 1, 2023 as the change date.

A near-zero average return is insufficient to identify a tradable range. A driftless
random walk also has zero expected return, but does not revert to a stable center.
We must distinguish trend, stationary/locally mean-reverting range, and uncertain
or unstable behavior. Price remaining within a historical band does not prove its
future bounds. Likewise, state probability is not probability of trading profit.

The causal stories remain hypotheses. COVID's initial pandemic shock was in 2020
(WHO characterization March 11), followed by later phases; 2021 should not be used
as its start. AI, wars, oil, inflation, fiscal supply and monetary policy can affect
different channels, with opposing effects. No causal contribution or record-oil
claim is established by the current price backtest. For TLT, investigate the yield
curve, expected rate path, inflation/real yields and term premia as measurable
channels. Any new macro or futures-curve inputs must be audited, published and
available at the historical release time before entering a backtest. Web sources
consulted here are background/method references, not numerical research inputs.

## Recommended hierarchy

Three roles are worth comparing, rather than simply three independent HMMs on
the same observations:

| Layer | Question | Intended scale, not a fixed lookback |
|---|---|---|
| Structural G | Persistent drift, mean-reverting range, or a changing/uncertain environment? | Multi-year context |
| Intermediate M | Which directional leg is developing within that environment? | Quarter to year |
| Fast S | Is an upswing starting, persisting or failing? | Week to month |

Those scales are hypotheses/broad priors, not discovered constants. Uncertainty
should be retained in the posterior, not forced into a range label. The structural
state should modify the intermediate/fast transition and risk distributions;
it should not automatically block every countertrend long entry. Long downward
context can coexist with a profitable short upswing, and a long range can contain
strong intermediate trends.

One proposed transition factorization, conditional on previous information I,
is:

`P(G_t,M_t,S_t | I_{t-1})`
`= P(G_t | G_{t-1},aG_{t-1})`
`  * P(M_t | M_{t-1},G_t,aM_{t-1})`
`  * P(S_t | S_{t-1},M_t,G_t)`.

Here aG/aM are time already spent in a state. Inference must retain their joint
uncertainty instead of substituting hard state labels. This factorization is a
design proposal; emissions, priors, duration families and update schedules must be
declared and identified before fitting. Three chains with three states give 27
joint combinations, which can be underidentified when long regimes are scarce.
Do not freely estimate every joint transition or multiply likelihoods of several
overlapping price features as if they were independent evidence.

An ordinary HMM gives geometric state duration:

`P(D=d | state=i) = a_ii^(d-1) * (1-a_ii)`.

Its exit hazard is constant regardless of time already spent in the state.
Explicit-duration hidden semi-Markov modeling lets us estimate a more appropriate
duration distribution for the broad/intermediate environment. It does not remove
the need for priors or create more historical regimes. A hierarchical model and
an explicit-duration model address different aspects of this problem; they can
be combined, but one does not automatically imply the other.

Separately, online change-point diagnostics can track
`P(run length=k | observations through t)`, signaling that the old observation
law is failing before a replacement multi-year state is confidently identified.
Recognizing a change and learning its eventual duration are distinct tasks. We
need not wait a fixed one or two years to become less confident in the old model,
but we cannot know in advance that a new state will last years.

## Where frequency analysis fits

Use time-frequency analysis first as a diagnostic. A full-history Fourier spectrum
averages over changes and does not locate when a frequency becomes important.
Trend or a structural break can produce low-frequency power without a repeating
cycle. Spectral power also measures variation, not the direction or expected
profitability of a trade.

Examine returns and past-standardized volume innovations; distinguish this from
looking for attractive periodicity in nonstationary raw price levels. A wavelet
map or a causal multiband filter bank can show how activity shifts between short,
intermediate and slow scales. Its frequency resolution and sample support still
require explicit choices; this is not a window-free discovery machine.

For an executable causal filter-bank feature, a generic definition is

`z_t^(k) = sum_{j>=0} h_j^(k) * x_{t-j}`.

The nonnegative lag is essential. Full-sample centered wavelet coefficients or
zero-phase filtered paths may use future observations and are only retrospective
illustrations. Truncating/recomputing at each date avoids future input, but does
not eliminate boundary uncertainty. The newest point is exactly where long-scale
wavelet estimates are least supported. Report edge masks, effective support,
revision under appended data, and phase/group delay for executable features.

Before using spectral features for trading:

- Compare apparent structure with random-walk/drift and volatility-clustered nulls;
  account for trying many frequencies, dates and assets. A red-noise comparison
  alone is not proof of market predictability.
- Require persistence across chronological training segments and nearby scales.
  Multi-year cycles have very few independent repetitions even in long ETF history.
- Test whether features improve forward density/calibration or distinguish
  mean-reverting range from trend, then whether they add net trading value.
- Treat raw ETF share volume as ETF activity, not underlying futures volume or
  direct investor demand. Splits, shares outstanding and fund growth can shift it.
  Preserve audited raw-volume gaps; use no retrospective filling or normalization.

## A small, interpretable next experiment

First make a diagnostic atlas on the full supported pool, with TLT/WEAT as
failure cases and GLD as a preservation case. Plot price, raw volume, directional
structure, uncertainty, time-frequency activity and possible changes. All analysis
dates must be explicit; price-only visual annotations remain hypotheses.

Then predeclare only three main comparisons:

1. A two-timescale control with the same chronological refit and execution schedule.
2. The three-level, duration-aware hierarchy with price/volume observations.
3. The same hierarchy with the causal spectral features added.

Incorporate the accepted loss-feedback idea with the same health controller in
each family and paired feedback-disabled controls. Three consecutive completed
net losses trigger defensive risk; four request a pause/refit review. Use fresh
shadow recovery and gradual re-entry, with trade/daily shortfall diagnostics as
a later calibrated extension. Keep market-state inference separate from policy
health. The [framework and full-pool warning audit](strategy-health-framework-2026-10-26.md)
show that a streak can occur in profitable strategies and can arrive after large
losses; it cannot substitute for improved entry timing and profit protection.

The subsequent [actual large-loss feedback test](loss-feedback-results-2026-10-26.md)
also shows that hard pauses and slow shadow recovery can forfeit strong recoveries.
Retain severity/stop observations as inputs, but redesign and isolate their
response before adopting the initial controller in the hierarchy comparison.
The completed fixed recipe and its failed preservation verdict remain unchanged.

These are proposed comparisons, not fitted results or an approved numerical grid.
Hold trading/risk/search budgets as comparable as possible; distinguish effects
of more states, duration assumptions and spectral features. Retain the current
frozen result as historical evidence without silently changing its parameters.
Use rolling-origin training/selection, filter forward only, show parameter/bound
stability, compare recognition delay and false transitions on synthetic cases
with known states, and use predictive calibration on real data without pretending
to know its true states. Include a level-shock versus persistent-slope distinction
so one-off jumps need not become long trends. If data cannot identify the long
state, expose uncertainty or abstention rather than manufacture confidence.

Only after recognition diagnostics should net trading be assessed: full pool,
per-ETF fitting, costs/delays, chronological robustness, dynamic and fixed-interval
adoption, turnover and drawdown. Do not adopt the best later-return model per ETF.
All old dates are inspected development evidence; a genuinely prospective slice
requires a recipe sealed before new audited observations arrive. Shrinkage across
related assets can help estimation, but correlated bond ETFs do not supply many
independent multi-year regimes.

## FR25 and the benchmark set

FR25 remains a useful empirical incumbent. Whether it is unusually lucky or
benefits from particular rotations is testable, not established. Retain it, cash,
individual buy-and-hold and simple trend/range controls. Match timing, costs,
universe and risk budget for controlled comparisons, while retaining original
FR25 as the actual incumbent reference. Attribute its results by year, asset,
asset class, exposure and event episode; inspect leave-one-period/class-out
sensitivity and uncertainty with blocks preserving temporal and cross-asset
dependence. Events must not become hindsight features or a way to select the
most flattering evaluation slice.

Separate three questions: does the model describe useful structure; does a trading
rule profit from that information; does it improve or diversify a portfolio?
Failure to beat FR25 over one favored regime does not answer all three questions.
This clarification does not rewrite old frozen acceptance verdicts or weaken
paper/live promotion requirements.

## Standard weakest-case inspection

Every round now identifies the weakest risky ETF under the training-selected
policy, defaulting to net cumulative return at the declared primary cost/delay
setting. Cash references are excluded; report both chronological evaluations.
Do not choose a particularly bad unselected variant to make a failure look worse.
If worst Sharpe, drawdown or benchmark-relative loss differs, show that separately.

Current later case: WEAT, model B, -32.51% return, -.619 Sharpe, 35.11% maximum
drawdown, 10 losses in 14 completed trades. Gross return -31.56%, before fee drag.
Current earlier case: MCHI, model A, -29.80%, -.475 Sharpe, 56.30% maximum drawdown.
The report defaults to WEAT/B and provides a weakest-case button for either era,
raw volume alongside price, exact dates, states, protection, fills and trade ledger.
Static full WEAT, 2023 close-up and earlier MCHI charts are ready. No trading
signals changed; visual comments will inform the next declared hypothesis.

- [Interactive report, now opening on WEAT](../research/latent-slope-20261025-v1/index.html)
- [WEAT full context](../research/latent-slope-20261025-v1/WEAT_late_selected.png)
- [WEAT 2023 close-up](../research/latent-slope-20261025-v1/WEAT_2023.png)
- [Earlier weakest MCHI](../research/latent-slope-20261025-v1/MCHI_early_selected.png)
- [Ranking and trade details](../research/latent-slope-20261025-v1/weakest-cases.json)

## Primary references

- Johnson & Willsky, [Bayesian Nonparametric Hidden Semi-Markov Models](https://www.jmlr.org/papers/v14/johnson13a.html): explicit non-geometric durations.
- Adams & MacKay, [Bayesian Online Changepoint Detection](https://arxiv.org/abs/0710.3742): causal run-length uncertainty.
- Torrence & Compo, [A Practical Guide to Wavelet Analysis](https://paos.colorado.edu/research/wavelets/bams_79_01_0061.pdf): localized power, statistical nulls and edge effects. The proposed causal financial implementation is our design, not a replication of the paper.
- Federal Reserve, [Waller on long-run interest rates](https://www.federalreserve.gov/newsevents/speech/waller20240524a.htm): expected real short rates and term-premium channels.
- WHO, [March 11, 2020 briefing](https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020): pandemic chronology.
- Teucrium, [WEAT fund description](https://teucrium.com/weat): exposure through wheat futures at multiple maturities. Roll/curve effects are a research consideration, not an attribution of the observed losses without audited futures data.
