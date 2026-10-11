# P4.17f — Closing the tilt when the signal stops: exit rules measured

Operator direction, 2026-10-11: *holding until the next monthly rebalance is of course not optimal —
test rebalancing (removing the tilt) whenever the signal disappears or stops.* And on cost: *nobody
said the strategy cannot spend more; the key is optimal.*

Run as its own frozen study in `var/research/alpha101-tilt-exit-20261011-v1/` (protocol `db40c5e1…`):
FR25 and the current SOTA over the same 70 months / 1,448 sessions, 42 arms, 252 replays. Report:
[`research/alpha101-tilt-exit-2026-10-11/index.html`](../research/alpha101-tilt-exit-2026-10-11/index.html).

**Cost was not a filter.** Every arm was replayed whatever it cost — including arms at 84.3bp, nearly
twice the P4.15 ceiling — and the arms are ranked on **net** outcomes, because the replay charges the
5bp cost. The ceiling appears as a column and nothing was dropped for exceeding it. In this study the
exits turn out to be cheap; they simply do not help.

## Verdict: holding beats exiting, and half the exit rules never fire

**FR25** (untouched: 105.8% / 13.36% CAGR / 1.214 Sharpe / 1.549 Calmar / −8.62% maxDD / 40.9bp):

| Arm | Exits | Total return | CAGR | Sharpe | Calmar | Max DD | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **X = 5%, HOLD** | 0 | **104.9%** | **13.27%** | **1.204** | **1.598** | **−8.30%** | **40.9bp** |
| X = 5%, EXIT-FLIP | 61 | 104.5% | 13.23% | 1.203 | 1.540 | −8.59% | 43.3bp |
| X = 5%, EXIT-FLIP-REENTER | 61 | 103.3% | 13.11% | 1.195 | 1.510 | −8.68% | 50.8bp |
| X = 10%, HOLD | 0 | 103.9% | 13.17% | 1.191 | 1.596 | −8.25% | 41.6bp |
| X = 10%, EXIT-FLIP | 61 | 103.2% | 13.10% | 1.191 | 1.530 | −8.56% | 46.2bp |
| X = 10%, EXIT-FADE | 4 | 103.6% | 13.15% | 1.190 | 1.593 | −8.25% | 41.8bp |
| X = 10%, EXIT-NOSIG / PNL / TP-1 | **0** | 103.9% | 13.17% | 1.191 | 1.596 | −8.25% | 41.6bp |
| X = 10%, EXIT-SL-05 | 1 | 104.0% | 13.19% | 1.193 | 1.598 | −8.25% | 41.6bp |

**Three of the six rules are no-ops on this data**, and that is itself the answer to "when the signal
disappears or stops":

- **EXIT-NOSIG never fires (0 exits in 1,448 sessions).** The family never stops ranking the held
  book — the cross-section always has a spread — so "the signal disappears" does not happen.
- **EXIT-PNL (−2%) and EXIT-TP-1 (+1%) never fire**, and EXIT-SL-05 (−0.5%) fires **once**. At a 5–20%
  tilt the tilt's own weighted return simply does not move that far inside a month; the P&L-based
  version of the idea has no traction at these sizes.
- **What does fire is the flip: 61 exits.** The signal does not vanish, it *turns* — and acting on
  that turn is worse than waiting: it gives up the tilt's remaining edge, pays a round trip, and adds
  **+2.4bp at X = 5% and +4.6bp at X = 10%** while leaving Sharpe unchanged and Calmar lower. The
  re-entry variant is worse still: +10bp and +25bp of cost for the same or lower return.

The same ordering holds on the SOTA, where X = 10% HOLD (**77.3% / 10.46% / 0.922 / 0.839 / −12.46%**)
beats every exit rule on return, Sharpe and Calmar, and EXIT-FLIP costs +4.1bp for a lower return and
a deeper drawdown. The single exception is cosmetic: X = 20% EXIT-FLIP-REENTER has the shallowest
drawdown on the SOTA (−12.45% against −12.83% untouched) at the price of the lowest return in the
family (67.5%) and 77.3bp of cost.

## The optimum, ranked strictly on net outcomes

| Book | Best total return / CAGR | Best Sharpe / Calmar | Shallowest drawdown |
| --- | --- | --- | --- |
| FR25 | **X = 5%, HOLD** | **X = 5%, HOLD** | X = 10%, EXIT-FADE (tied with HOLD) |
| SOTA | X = 20%, HOLD | X = 10%, HOLD | X = 20%, EXIT-FLIP-REENTER |

**Four of the six metric optima across the two books are plain HOLD arms**, and the two exceptions are
an EXIT-FADE arm that fired four times (statistically a HOLD arm) and a re-entry arm that buys 0.4pp
of drawdown with 10pp of return. **No arm in either family differs from its untouched book at Holm
p < 0.05** — 0 of 20 contrasts per book — so every optimum here is a selection on noise as much as on
signal, and none of it is established.

## Why exiting early loses

The monthly design already re-derives the tilt at every decision, and that re-derivation measures a
**flip on 54 of 70 decisions** with 2 closes and 2 opens. So the tilt is not "left open and forgotten"
between months: it is rotated at the next decision with no extra round trip beyond the one the
rebalance already pays. Closing it earlier converts that scheduled rotation into an *extra* trade and
forgoes the part of the tilt's edge that has not yet been realised — which is precisely what the
numbers show: return down, cost up, risk ratios flat to worse.

## On "rebuild it as a LEAN strategy if you have to"

The daily arms in these studies are not an approximation of a daily-rebalancing strategy: each arm is
frozen as **one target vector per session**, which is exactly what a strategy that rebalances daily
submits, and the replay engine executes those targets with the same accounting, costs and cash
conventions whose LEAN parity the parent studies already verified (0 differences on this machine).
A new native LEAN algorithm would therefore produce the same NAV path — it would add *native parity
evidence*, which is a promotion-grade requirement, not a research one. If a tilt is ever taken toward
promotion, that algorithm is the right next artefact, and I would build it then rather than now.

## Verification

11 tests in `tests/test_alpha101_tilt_exit.py` cover the arm registry and the two declared families,
each exit rule's trigger semantics (hold, flip, fade, no-signal, stop, take-profit), the re-entry
condition, a synthetic simulation proving monthly entry and intra-month exit, and the frozen study:
all 42 arms present and replayed, the controls untilted, the signal rules firing as declared, an
optimum reported for every metric, and — explicitly — that arms above the cost ceiling exist and were
replayed rather than filtered.

## Limitations

- **In sample.** One inspected window; the optima are maxima of a searched surface with 0 of 20
  contrasts significant on either book.
- **Entries stay monthly.** Only exits are intra-month, except in the re-entry arm.
- **The P&L rules use the tilt's own weighted return**, a declared proxy for its contribution rather
  than the book's NAV.
- **Costs are the parents' 5/10/20bp** with zero and one-session delay; nothing is re-optimised.
- **No promotion**: the 45% cap, the cash reserve and the monitored books are unchanged.
