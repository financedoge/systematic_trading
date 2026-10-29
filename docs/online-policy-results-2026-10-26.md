# Continuous single-ETF policy learning — 26 October 2026

The operator explicitly deferred all portfolio selection, overlays and monthly
rebalancing. This study tests the single-ETF algorithm across the supported pool.
Loss warnings now trigger faster learning rather than a health pause. The result
is a working adaptive policy, but not a general performance improvement.

[Interactive report and every ETF chart](../research/online-policy-20261026-v1/index.html).
The default weakest chart is TLT in 2023–2026; the earlier weak-case button opens
PPLT. WEAT, GLD and exact-date selection remain available. The report shows three
algorithms only, explicit mathematical formulas, actual parameter values and all
dated warning/change/trade records.

## Declared experiment

A retains the ETF's previous training-selected policy. B updates separate
discounted Bayesian payoff estimates for nine nearby policies. C adds faster
forgetting after actual loss warnings. No arm has a health-driven pause, exposure
reduction or calendar recovery timeout. Ordinary entry/rearming rules still apply.

The grid changes up-entry confidence by -0.1/0/+0.1 and initial/trailing distances
by 0.5/1/1.5. Entry confidence is clipped to [0.5,0.9]. Down-exit confidence shifts
by 0.2 times (distance multiplier minus 1), clipped to [0.45,0.9]; confirmed-slow-up
exit confidence changes from 0.85 similarly, clipped to [0.65,0.95]. Existing
context-aware distances remain linked. These are trading-policy thresholds,
not refitted Kalman/HMM likelihood parameters or new range geometry. The underlying
filters, HMM emissions/transitions and daily volatility calibration stay fixed.

For a completed candidate shadow trade i, define net unit return r_i including
both fees and normalized payoff y_i = clip(r_i/(sigma*sqrt(D_i)), -3,3), where D_i
is holding sessions and sigma is training daily log-return dispersion. Clipping
only affects learning, never reported actual P&L. Each policy has its own
Normal(0,1/4) prior over its payoff mean and unit-variance powered likelihood.

Daily discount rho=2^(-1/126) multiplies sufficient statistics N,S,W; newly closed
trades add 1,y_i,I(r_i>0). Posterior mean=S/(4+N), variance=1/(4+N). The diagnostic
win estimate is (1+W)/(2+N), from Beta(1+W,1+N-W); it is not multiplied into the
payoff likelihood. Policy score=mean-0.25*posteriorSD. Change requires improvement
above0.05 and at least one newly closed evaluation shadow trade for the candidate.
Training outcomes are recency-weighted and capped at four effective observations;
all initial states are sealed before evaluation. They are in-sample outcomes
because the parent market model was fitted over that training history.

C accelerates on an actual third/fourth consecutive loss, realized loss below
minus tau, first marked loss below minus tau in a position, or negative protective
exit. Tau=max(training winner-return sample SD,2*fee,1e-6), requiring five training
winners; otherwise sigma warnings are unavailable. At most once per20sessions,
multiply OLD N,S,W by0.25 before adding the day's new outcomes. A warning need
not change the selected policy. Actual returns drive warnings only, so an actual
trade and its matching shadow trade are not counted twice.

Pending orders remain binding. Updates can change current-position future exit
decisions, but an adopted protection level never widens. The old level is tested
before raising the next-close level. Close signals execute at next open plus
0/1extra session. Cash-funded fractional adjusted units;5/10/20bp each side;
idle cash0; terminal holding marked rather than forcibly sold. This is a hybrid
adaptive path, different from any one fixed shadow policy's returns.

This is a working Bayesian approximation with deterministic policy selection,
not Thompson sampling. Correlated candidate observations are never pooled as
independent evidence for a common model. Neither Normal precision nor the Beta
win probability is calibrated confidence under serially dependent trade data.

## Results

Primary next-open execution,5bp per side,2023-01-03 to2026-10-16:

| ETF | A frozen | B continuous learning | C warning-accelerated |
|---|---:|---:|---:|
| GLD | +56.69% | +88.30% | +85.34% |
| WEAT | -32.51% | -10.69% | -18.17% |
| TLT | -12.48% | -12.59% | -24.08% |
| CORN | -14.19% | -16.98% | -16.70% |
| EWH | -1.92% | +18.99% | +15.51% |
| EWY | +92.33% | +64.30% | +14.80% |

GLD B Sharpe1.133, Calmar0.941, DD19.40%; C1.116/0.989/DD17.96%, versus
A0.824/0.607/DD20.81%. WEAT B Sharpe-0.162/DD20.04%; C-0.367/DD21.50%,
versus A-0.619/DD35.11%. The new learning arms improve selected examples without
remaining paused for years. That does not generalize across the full pool.

| Era | Algorithm | Median Sharpe | Median CAGR | Within A return/DD guards |
|---|---|---:|---:|---:|
| 2023–2026 | A | 0.412 | 4.36% | 100% |
| 2023–2026 | B | 0.284 | 2.15% | 47.1% |
| 2023–2026 | C | 0.277 | 2.76% | 35.3% |
| 2020–2022 | A | 0.276 | 2.43% | 100% |
| 2020–2022 | B | 0.195 | 1.29% | 57.1% |
| 2020–2022 | C | 0.195 | 1.10% | 55.1% |

Preservation requires at least90% of risky ETFs within1pp CAGR and2pp maximum
drawdown of A, plus improvement in median Sharpe and lower-quartile CAGR. Neither
B nor C passes in either era/any of six frictions (zero of12 for each).
B improves net return on17/51 later and22/49 earlier risky ETFs; C15/51 and25/49.
C beats B's return in20/51 later and26/49 earlier cases. Median changes B/C are
7/9 later and6/8 earlier. Six friction settings reuse the same history and are
not independent confirmations. Full yearly and cost/turnover results are exported.

## Failure mechanism: TLT

TLT is the weakest risky ETF under primary C, by lowest net cumulative return:
-24.08%, Sharpe-0.873, DD26.91%,18closed trades,5wins,13parameter changes and
6accelerations. A/B return-12.48%/-12.59%; matched buyhold-8.84%.

On2023-09-22 the third loss triggers accelerated forgetting and switches policy8
to6. Entry confidence stays0.85, while normal protection changes7.5 ->2.5 sigma
units and down-exit confidence0.7 ->0.5. C enters2023-11-06 and exits at protection
on2023-11-10 for+1.23%. B enters the same date and stays until2024-01-05 for+11.43%;
A until2024-01-09 for+11.59%. Rearming requires fast-up probability below0.5, so
after the tight exit C cannot re-enter the continuing rise. There is no health
pause, but the old signal-rearming rule still causes missed participation.

The wider shadow policy's completed win only arrives in January; C switches back
to8 on2024-01-09. This is direct evidence of delayed reward feedback and an
exit/re-entry mismatch. Merely forgetting faster cannot make an unfinished
winner's final outcome available earlier. The2024-07-18 to09-27 upswing remains
captured by both B/C for+5.78%; the problem is not universal failure to detect TLT.

[TLT dated inspection figure](../research/online-policy-20261026-v1/TLT_late.png).

## Earlier weakest case and unresolved WEAT risk

PPLT is weakest in2020–2022: C-32.56%, Sharpe-0.483, DD39.49%;30closed trades,
10wins,24parameter changes,15accelerations. A-26.54%, B-26.42%, buyhold+6.75%.
This remains a false-rebound/whipsaw problem. Its3.62% winner-sigma warning does
not cap losses; some larger losses persist while policy selection waits for
comparative evidence. [PPLT figure](../research/online-policy-20261026-v1/PPLT_early.png).

WEAT still loses6.99% on2023-01-03..01-11 and9.01% on02-15..02-27 in every arm.
A marked warning requests learning, not an emergency exit, and fresh candidate
outcomes can be sparse. Later learning improves the total, but it does not solve
those first two damaging trades. C completes15trades with no health pause,
compared with one actual trade in the earlier long-pause experiment. Its smaller
loss is no longer explained by staying inactive for925sessions.

## Next research hypotheses; no retrospective retuning

1. Separate a hard loss/risk budget from the learning trigger. Learning may change
   what to trade next; an immediate risk rule controls current damage. Test each
   component against matched controls instead of assuming faster learning is SL.
2. Separate entry-quality, exit-giveback and re-entry learning. Tight trailing
   protection needs a causal pullback/recovery re-entry rule; do not require a
   full trend reset when the thesis remains positive.
3. Use causal daily marked utility or predictive errors in addition to completed
   outcomes, accounting for serial dependence. Avoid rewarding fast-closing
   candidates simply because long profitable trades have not closed yet.
4. Condition learning on slow-market context with shrinkage and minimum retained
   evidence. A losing short rebound should not erase evidence about sustained
   uptrends globally. Keep ordinary learning and frozen policies as controls.

These fit the accepted multiscale direction, but this study did not implement
three HMMs, spectrum features or full online market-model refitting. The next
experiment remains single-ETF; no overlay or monthly rebalance work is pending.

## Provenance and verification

Protocol52a79975a9ac143da7659fc2631bec4db88004647a2e3fb54ac141210c923635.
Published input batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd,
verified through frozen parent manifests. Prices adjusted for returns; raw volume
is audited inspection context, not a learned feature here. No external prices.
Audited histories do not establish historical publication-vintage availability.
All evaluation eras have already been inspected and remain development evidence.

The first evaluation attempt aborted on a duplicate Calmar output keyword before
producing any results. Only that writer error was repaired; initial states and
algorithm settings were unchanged. Original protocol and a repair receipt remain.

16 focused tests cover causality/prefix invariance, delayed fills, non-loosening
stops, posterior magnitude/win differences, shadow evidence, missing sigma and
continued trading.612 frozen controls reproduce existing simulator NAV within
8.9e-15; independent cash/share reconstruction within5.2e-15.306 offline UI
combinations cover every ETF/era/algorithm, parameter tables, dates and weak cases.
Four static figures and nine equations visually inspected; browser-layout
certification is not claimed.

Three native Windows LEAN single-ETF executions match the application's whole-unit
reference exactly. They validate frozen-signal execution, not learning logic.
App sizing/cent prices differ from fractional study accounting: WEAT C-18.08%
versus-18.17%; TLT C-24.01% versus-24.08%; GLD C with extra1session delay+113.17%
versus+114.29%. Maximum GLD normalized NAV discrepancy is1.34percentage points,
so do not describe these as exact independent reproductions of fractional returns.
No portfolio, runtime, promotion, funding or broker changes.

Method references: [discounted Bayesian learning](https://arxiv.org/abs/2305.10718)
and [nonstationarity and information value](https://proceedings.mlr.press/v206/liu23e.html).
These motivate discounting; their algorithms/guarantees are not our trading rule.
