# Peer review of the Alpha101 work: five findings, all confirmed, and what changed

A second agent reviewed the P4.17 screen, the tilt studies and the deployed overlay on 2026-10-11 and
reported five implementation defects. **All five were reproduced against the code before anything was
changed, all five were real, and all five are fixed.** This is the record of what was wrong, what the
corrections are, what was re-run, and which conclusions changed.

The reviewer's own framing was right and is worth keeping: these defects do not establish that
Alpha101 is useless, and they do not mean the monitored monthly strategy inherited the *exit study's*
look-ahead. They do mean the affected conclusions had to be withdrawn until the experiments were
corrected and rerun.

## The five findings

| # | Finding | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | The "hold until next month" arms re-submit the same target weights every session, which rebalances on price drift instead of holding shares | **Confirmed** | The exit study's HOLD arm wrote **1,448** decision rows where the monthly strategy has 70. Every arm, including each control, was a daily-rebalanced process |
| 2 | The exit-and-re-enter rule cannot re-enter after an exit | **Confirmed** | The branch sat behind an `elif held:` guard that the exit had just emptied. A synthetic run left the book untilted while the signal re-aligned, and the 211 "re-entries" it reported were re-tilts of a position still on |
| 3 | The profit/loss exits read today's close to decide a target executed at today's open | **Confirmed** | `should_exit` indexed the same session's close that the resulting row traded on: look-ahead |
| 4 | Alpha 43 divides every historical volume by the **latest** average dollar volume instead of each date's own rolling average | **Confirmed** | Published formula 0.450000 vs implementation 0.600000 on a synthetic series. The other three `adv20` users (7, 21, 43) correctly use today's value; **43 was the only defective alpha of the sixteen** |
| 5 | Rank IC assigns tied forecasts different ranks, so it depends on ticker labels | **Confirmed** | Identical signal/return pairs with renamed tickers scored 0.657143 vs 0.371429; the implementation also disagreed with textbook mid-rank Spearman (0.371429 vs 0.441367) |

## The fixes

**Alpha 43** now divides by each date's own rolling average dollar volume through a new
`rolling_adv(close, volume, d)` helper, and `test_alpha_43_divides_by_each_dates_own_rolling_dollar_volume`
recomputes the published formula independently and asserts equality — including that the wrong flat
divisor genuinely differs on the same series. I audited the other fifteen alphas against their
published formulas: 7, 21 and 23 use only today's value, 26 and 24 build their rolling series
explicitly, and 6, 9, 12, 35, 46, 49, 51, 53, 54, 101 are point-in-time correct. 43 was the only one.

**Rank IC** now averages tied ranks (`midranks`), and
`test_rank_ic_averages_ties_instead_of_ranking_them_in_ticker_order` pins both the label-invariance
and the textbook value. `signal_decay.rank_ic`, which feeds the monitored decay panel, was already
correct — the defect was confined to the new Alpha101 screen.

**Holding** is now expressed properly: both studies, and **both of their controls**, emit a decision
row *only when the target vector changes*. Between events the engine holds shares, so price drift
generates no trade. The corrected diagnostics show it: the exit study's HOLD arm submits **70**
targets, not 1,448, and the daily control submits **65**.

**Re-entry** is evaluated when no tilt is held, so an exited arm can genuinely re-enter. The corrected
FR25 X=5% re-enter arm records **155 exits and 126 re-entries** where the old code recorded zero
reachable re-entries.

**The profit/loss exits** now read only closes **strictly before** the session they trade, and the
entry base is the entry session's own close (known before every later decision — not look-ahead).
`test_the_profit_and_loss_rules_cannot_see_the_session_they_trade_on` proves a collapse on the traded
session does not trigger, while the same collapse one session earlier does.

## Re-runs

The code changes invalidate artifacts rather than merely annotating them, so every affected study was
re-frozen under a **v2** root whose protocol records the correction. The v1 roots are kept as the
historical record and are marked superseded.

| Study | Root | Result after correction |
| --- | --- | --- |
| P4.17 screen | `alpha101-screen-20261011-v2` | **0 pass, 15 reject, 1 insufficient — verdict unchanged** |
| P4.17f exit rules | `alpha101-tilt-exit-20261011-v2` | 42 arms; **the conclusion changed, below** |
| P4.17e daily threshold | `alpha101-tilt-daily-20261011-v2` | 34 arms; **the conclusion survived** |
| P4.17d budget surface, P4.17c replay, P4.17b measurement | `…-v2` | re-run on the corrected chain (surface bases now point at the corrected replay, the measurement at the corrected screen) |

The monitored strategy was recalculated by the app's own services on the corrected alpha 43
(revision `c519e86cd455`), and **all five M1-family native runs passed LEAN parity with 0
differences**. Its published figures barely move — 11.17% annualised, Sharpe 1.1025, maximum drawdown
−20.28% against 11.18% / 1.103 / −20.28% before — because one alpha of sixteen enters a rank average,
but the code behind those figures is now correct.

## Corrected conclusions

**Withdrawn: "exiting early is worse than holding".** With the re-entry branch actually reachable, the
best FR25 arm *in sample* on total return, CAGR and Sharpe is **X = 5% with the flip-exit-and-re-enter
rule**: 105.4% total return / 13.32% CAGR / 1.212 Sharpe / 1.553 Calmar at 53.2bp, against **X = 5%
held** at 105.0% / 13.28% / 1.207 / **1.609** at 41.0bp and the untouched book at 106.0% / 13.37% /
1.218 / 1.545 at 41.0bp. So the re-entering rule buys about +0.4pp of net return for about +12bp/yr of
cost, while plain exiting without re-entry is still clearly worse (103.9% at 43.5bp). The old claim
held only because the re-entry arm could not re-enter.

**Qualified: "5% HOLD is the best configuration".** HOLD remains the best on Calmar and drawdown
(1.609, −8.25%), and the corrected table puts 5%-with-re-entry ahead on return, CAGR and Sharpe. On
the SOTA nothing changed: every exit rule is still worse than holding, and X = 20% held is the best on
return and CAGR while X = 10% held is the best on Sharpe, Calmar and drawdown.

**Unchanged: nothing is statistically established.** 0 of 20 family-adjusted contrasts differ from the
untouched book on either base at Holm p < 0.05, exactly as before. The corrected table changes which
arm *looks* best; it does not make any of them distinguishable from noise.

**Unchanged: high frequency destroys value.** The corrected daily study reproduces the frontier: FR25
X = 10% at no band costs 142.7bp for 96.5%, at a 100% band 112.7bp for 100.3%, and at a 300% band
41.6bp for 103.9% — statistically the monthly arm at 41.7bp and 104.1%. The band that fits the cost
ceiling is still the monthly arm.

**Unchanged: the screen rejects the family.** 0 of 16 alphas clear the gate as top-six mappings, with
the same 15 rejections and the same single insufficient case.

## What this means for the monitored strategy

`research_fr25_alpha_tilt_5_v1` is the **X = 5% held** configuration the operator asked for. It is
still monitored, still carries `promotion_eligible=False`, `execution_enabled=False` and
`allocation_ready=False` with the platform's 14-ETF execution-contract reason, and its spec sheet
already disclosed that the evidence was not established. After the correction it is no longer the
single best in-sample arm on three of five metrics — 5% with flip-and-re-enter is — and it is slightly
below its own control on total return while remaining the best on Calmar. Both facts are now in this
record and in the findings documents.

Switching the monitored recipe is a one-line parameter change and an operator decision. It is not
made here, because the corrected advantage is +0.4pp of net return for +12bp/yr of cost with **no
statistical support**, and because the operator chose the held configuration deliberately.

## Verification

The corrected code is covered by new regression tests: alpha 43 against the published formula, rank IC
label-invariance and mid-rank equality, the emission rule for both studies, re-entry after exit, and
the look-ahead boundary. The frozen-artifact tests caught the drift themselves — they failed the
moment the code changed, which is exactly what they exist for, and they now assert against the v2
roots.

## Limitations, stated plainly

- The v2 re-runs correct the implementation, not the design: one inspected window, in-sample optima,
  and no significant contrast anywhere.
- The measured overlap in the exit study is internally consistent across arms, but it is a *different*
  process from the monitored strategy in one respect: the studied arms enter at the strategy's monthly
  decision, while the monitored strategy's own scheduler supplies those decisions.
- The rank-IC correction changes the screen's recorded IC values; the verdict did not change, but the
  saved series are the corrected ones.
