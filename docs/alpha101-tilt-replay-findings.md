# P4.17c — Baking the Alpha101 tilt into the current SOTA

Operator request, 2026-10-11: *can we bake the tested alpha into the current SOTA with a 10% tilt,
and see the final return / Sharpe / Calmar / maxDD?*

Run as its own frozen study in `var/research/alpha101-tilt-replay-20261011-v1/` (protocol
`bb7dba31…`), 36 replays on the parent evidence root's own quotes, sessions, costs and windows.
Gate applied to every arm **before** any replay. Report:
[`research/alpha101-tilt-replay-2026-10-11/index.html`](../research/alpha101-tilt-replay-2026-10-11/index.html).

Research finding only. Nothing here changed a monitored strategy, an allocation, an approval or a
broker record.

## Verdict: affordable and directionally better on every measure — and not distinguishable from zero

| Arm | Total return | CAGR | Sharpe | Calmar | Max drawdown | Volatility | Implied turnover | Incremental cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **SOTA** — untouched | 76.4% | 10.36% | 0.916 | 0.805 | −12.88% | 11.52% | 7.03× | — |
| **SOTA + 10% tilt of alpha 53** | 77.0% | 10.42% | 0.913 | 0.818 | **−12.75%** | 11.64% | 7.45× | **+2.08bp** |
| **SOTA + 10% family tilt** | **77.5%** | **10.48%** | **0.922** | **0.840** | **−12.47%** | 11.57% | 7.33× | **+1.53bp** |

Evaluation window, 5bp, zero delay, fresh cash, the SOTA built from its own registered definition and
its own overlay chain. The tilt is appended **last**, so it inherits the model tilt, relative
momentum, adaptive trend, activity and USD layers instead of replacing any of them.

**Every measure moves the right way and none of it is established.** Against the untouched SOTA the
annualised difference is **+0.07%** (alpha 53) and **+0.12%** (family), with 95% intervals spanning
zero at 3, 6 and 12 months and **Holm p = 1.000** across the three registered contrasts. Sharpe is
flat (0.913 / 0.922 vs 0.916), Calmar improves 1.6–4.3%, and maximum drawdown improves 0.13–0.41pp.
The honest summary is that baking the tilt in is **nearly free and nearly neutral**: it costs
1.5–2.1bp a year and returns 7–12bp a year, which is too small to separate from noise on one
inspected window.

## The gate ran first, and the tilt is comfortably affordable

| Arm | Implied turnover | Implied annual cost | Incremental cost | IC margin | Gate verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| SOTA | 7.03× | 35.14bp | — | 16.80× | pass |
| SOTA + tilt of alpha 53 | 7.45× | 37.23bp | **+2.08bp** | 15.86× | pass |
| SOTA + family tilt | 7.33× | 36.67bp | **+1.53bp** | 16.10× | pass |

The SOTA's own drag is 35.14bp against the 44.0bp ceiling, so it leaves about 8.9bp of headroom and
the tilt uses a fifth of it. Unlike P4.17's top-six mappings — which needed 44.7–76.5bp and died on
cost — the tilt passes the gate on all three arms with room to spare.

## Two findings worth keeping

**The family tilt beats the best-information single alpha, at lower cost.** Alpha 53 had the
strongest measured information of the sixteen (+0.0747 rank IC with an interval excluding zero), yet
its tilt returns +0.07% while the equal-weight family tilt returns +0.12% **and costs less**
(1.53bp against 2.08bp). That is direct evidence that alpha 53's apparent superiority was in-sample
noise, and that diversifying the tilt across the registered family is the better instrument — which
is exactly why the family arm, not the selected one, is the honest companion.

**The SOTA's book can arrive above the 45% cap.** The final clamp runs *after* the overlay chain, so
on 4–6 of the 130 decisions a name reached the tilt overlay already above 45%. The declared
single-shrink-factor rule then shrank the whole tilt to a no-op for that decision rather than pushing
an over-cap name further above it, and the tilt applied on 115 of 130 decisions. That is a real
property of the engine's ordering, it is measured rather than assumed, and it is why the rule
guarantees "never worse" instead of "always inside the cap".

## Why the effect is small, and why that is expected

A 10% budget moves each held weight by only a few percent of NAV, and the alphas' forward rank IC is
0.05–0.075. The expected edge is therefore tens of basis points a year, not percent — and the
measured +7 to +12bp sits exactly in that range, against a cost of 1.5–2.1bp. The tilt is
*profitable on paper*; it is simply not large enough to clear the family-adjusted bar on this sample.
Raising X to 20% was already measured in P4.17b to break the cost balance, so there is no cheap way
to make it bigger.

## Verification

13 tests in `tests/test_alpha101_tilt_replay.py`: the arm definitions and the declared selection
disclosure, the rank rule's refusal to rank an unrankable book, NAV-neutrality and the cap bound,
the over-cap case shrinking to a no-op, the zero-floor shrink, the overlay preserving the symbol set
the defensive fallback protects, the composite averaging rank scores rather than values (whose scales
differ by four orders of magnitude), and — against the frozen artifact — all 36 replays present once,
the gate passing every arm before any replay, the incremental costs below 3bp, the verdict being
inconclusive with directionally better return, Calmar and drawdown, and the analysis reproducing from
the replays. Every arm's decisions pass the cap, long-only, universe and protected-budget contracts
in the same run that produces them, and the pinned parent inputs are re-checked by hash.

## Limitations

- **One inspected window.** 2021+ has been looked at by P4.13–P4.17; nothing here is out-of-sample
  evidence.
- **The single-alpha arm is selected on the screen.** Only the family arm avoids that selection, and
  it dilutes by averaging in three negative-information alphas and one degenerate one.
- **X was the operator's declared 10%**, not a tuned value; P4.17b measured 5%, 10% and 20%.
- **Monthly re-tilting only**, at the SOTA's own decision dates.
- **Inherited conventions.** Costs, delays, currency and cash treatment come from the parent study so
  the comparison is like-for-like; none is re-optimised.
- **A tilt is not a promotion.** Nothing here changes monitoring, allocation, the 45% cap, the cash
  reserve or execution authority.
