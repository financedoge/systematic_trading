> **Policy correction — October 17, 2026.** The annual cost ceiling is retired. Historical gate failures below are not net-performance verdicts. See the [audit and reopened studies](research-cost-policy-review-2026-10-17.md). The [original report](../research/class-volatility-screen-20261016-v1/findings-original.md) retains the text covered by the original receipt.

# Class and volatility screen — October 16, 2026

**All 16 mappings fail the frozen admission gate. No portfolio replay is warranted for this family.**
Volatility normalization reduces monthly target-change costs below the 44 bp
ceiling, but its information margins are only **1.91× pooled** and **0.55×
class-first**, below the required 3×. Class-first selection alone remains too
expensive. The dynamic thresholds are also too expensive. These findings close
this declared construction screen; they do not reject class allocation, ETF
expansion or dynamic rebalancing in general.

![Cost gate, information intervals and later defensive exposure](../research/class-volatility-screen-20261016-v1/screen.png)

## Registered question and controls

This is the next separate P4.16d design after the unchanged expanded-FR25 rejection.
The four comparisons isolate **pooled versus class-first selection** and **raw
126-session momentum versus momentum divided by 63-session annualized volatility**.
This transparent price-only family omits FR25's financial, XGBoost, activity and
USD overlays. It is not an amendment to FR25 or evidence of outperformance over SOTA.
The original 14-ETF FR25 and URTH remain required replay benchmarks if a new
qualified family is later tested. The original control's existing gate receipt is
retained, but its latent-score IC is not directly comparable to this target-weight IC.

Pooled selection chooses up to six names. Class-first selection chooses up to
three classes and two funds per class, using the actual selected members' mean
score to rank classes. Within each budget, weights are inverse-volatility;
unfilled slots and any excess above the 45% security cap remain cash. The maximum
gross is 98%. Monthly controls accompany fixed target-distance thresholds of
0.10, 0.40 and 0.80. All thresholds retain monthly adoption and compare latest
theoretical versus last adopted targets, including cash, without held-weight inputs.

There are 24 declared primary classes, 18 of them singletons in the supported
50-fund pool (16 in the full 52-candidate list). Every
fund has one class. Prior raw-dollar activity selects duplicate representatives.
Explicit broad-parent/child conflicts prevent selected overlaps such as SPY and
its sector funds, EFA and its country funds, and DBC and commodity sub-funds. The
remaining class scores are recomputed after conflicts remove members. These are
declared modelling controls, not a verified historical holdings-overlap census.
Semiconductors and energy producers remain equities; silver receives one precious
metals vote; Hong Kong remains separate from mainland China. Pure energy-futures
and chemicals exposure remain gaps.

## Inputs and causal scope

The complete accepted first wave contains 52 candidates. The same 50 supported
common-window histories reproduce exactly from the published October 12 batch
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
BWX retains its listing-date hold. CPER retains the unsupported August 23, 2018
raw-volume observation. Neither is silently repaired or replaced. All original
publication audit/bar hashes and inherited manifests are verified before freezing.

Inputs start June 19, 2018. The study generates **1,450 daily target dates per
arm**, January 4, 2021–October 12, 2026, with **70 monthly anchors**. Signals and
liquidity use only observations before the proposed next-open date. Adjusted
prices supply returns; audited raw prices and volume supply liquidity. No macro,
FX, provider archive or online-price input is used. The old cutoff is intentional
for comparability and says nothing about current application freshness.

The cohort contains current surviving funds. Historical membership, mandate
and classification validity are not reconstructed; the October 13 reference
inventory is a retrospective classification assumption. Auditing revised prices
does not establish historical publication availability. These are inspected
historical diagnostics, not untouched validation or promotion evidence.

## Gate and chronological information

Calibration ends December 31, 2024. The information measure is the monthly
Spearman correlation of **final target weights, including zero allocations**,
with the following 21-session adjusted open-to-open returns across the admissible
pool. Thus it tests the composed ranking/sizing mapping, rather than claiming an
untraded raw signal's IC. Labels must finish inside the window. There are 47 valid
calibration observations and 21 later observations. Constant cross-sections never
receive the programme's default IC.

| Monthly mapping | Implied annual cost, bp | Calibration IC | IC / breakeven | 2025+ IC | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Pooled / raw | 56.97 | -0.03160 | -3.52× | +0.04453 | Reject |
| Pooled / risk-normalized | 24.84 | +0.00746 | 1.91× | -0.04680 | Reject |
| Class-first / raw | 48.32 | -0.02350 | -3.09× | +0.08049 | Reject |
| Class-first / risk-normalized | 38.15 | +0.00328 | 0.55× | -0.08144 | Reject |

The cost measure sums security-target changes and initial establishment over a
fixed interval. Cash affects the adoption trigger but is not charged as a second
traded security. These are **implied mapping costs**, not realized turnover, fees,
NAV, Sharpe or drawdown. Prior calibration of the legacy mapping does not establish
turnover accuracy for these new dynamic policies.

Every policy adopts at the same monthly anchors, so its monthly information
observations are identical within an arm; timing changes the cost side of this
screen. That identity is not a claim that the policies have equal portfolio returns.
The later period and per-year diagnostics cannot rescue a calibration failure.
In particular, the normalized pooled/class mappings turn negative in the later
period, while the raw mappings improve; this is temporal instability, not a
license to switch recipes after seeing the result.

Joint stationary-bootstrap diagnostics use 20,000 draws at each of 3, 6 and 12
monthly blocks, shared across all 16 mappings. Individual and Bonferroni family
intervals are saved. Every calibration family interval spans zero. These intervals
are descriptive and conditional on this inspected cohort, not formal discovery evidence.

## Dynamic comparison

All cells below are implied annual bp at the unchanged 5 bp per traded security
side; the ceiling is 44 bp. Each dynamic rule also adopts monthly.

| Mapping | Monthly | Threshold 0.10 | Threshold 0.40 | Threshold 0.80 |
| --- | ---: | ---: | ---: | ---: |
| Pooled / raw | 56.97 | 336.54 | 276.65 | 153.64 |
| Pooled / risk-normalized | 24.84 | 142.96 | 116.14 | 79.54 |
| Class-first / raw | 48.32 | 233.79 | 178.51 | 105.46 |
| Class-first / risk-normalized | 38.15 | 225.77 | 173.02 | 78.84 |

The least expensive dynamic mapping still costs 78.84 bp annually. No threshold
survives to portfolio replay. Actual traded turnover, net Sharpe, episode drawdown,
5/10/20 bp costs, next-open versus one-additional-session delay, matched exposure,
SOTA/URTH comparisons and native parity remain required for a future surviving
mapping. They were **not run or inferred** for these gate failures.

## Why lower cost is insufficient

| Monthly mapping, later period | Mean invested | Mean BIL | Mean cash | Mean names |
| --- | ---: | ---: | ---: | ---: |
| Pooled / raw | 98.00% | 0.00% | 2.00% | 6.00 |
| Pooled / risk-normalized | 58.36% | 45.00% | 41.64% | 6.00 |
| Class-first / raw | 85.63% | 0.00% | 14.37% | 5.24 |
| Class-first / risk-normalized | 67.32% | 16.33% | 32.68% | 4.12 |

The normalized pooled rule averages **45% BIL and 41.64% cash** in 2025–2026:
only **13.36%** is allocated to other ETFs. Dividing positive carry by very small
bill volatility elevates BIL's rank; inverse-volatility sizing reaches its cap
and leaves the excess in cash. The class-first rule limits bills to one of six
slots, but singleton classes also leave cash. Cheap trading alone therefore does
not establish better opportunity selection. Even after scaling its calibration
cost to 98% gross as a diagnostic, the class-normalized mapping costs 53.39 bp.
That scaling is not a new gate or a replay.

## Full supported-pool attribution

Average **adopted target** weights during calibration are below, including zero
weights. These are not held weights or P&L. All 16 policies' constituent weights,
selection counts and annual security-target turnover, in calibration and later
windows, are in [attribution.json](../research/class-volatility-screen-20261016-v1/attribution.json).
Per-constituent target turnover reconciles to each mapping's total.

| Fund | Primary class | Pooled raw | Pooled normalized | Class raw | Class normalized |
| --- | --- | ---: | ---: | ---: | ---: |
| AGG | aggregate_us | 0.00% | 0.00% | 0.00% | 0.00% |
| BIL | bills_us | 3.12% | 28.51% | 1.35% | 10.22% |
| CORN | commodity_agriculture | 1.03% | 0.57% | 1.85% | 1.15% |
| DBA | commodity_agriculture | 0.96% | 1.84% | 1.69% | 1.66% |
| DBB | commodity_base_metals | 0.93% | 0.54% | 0.67% | 0.67% |
| DBC | commodity_broad_parent | 3.18% | 1.90% | 4.47% | 3.46% |
| EEM | equity_emerging_parent | 0.00% | 0.00% | 0.00% | 0.00% |
| EFA | equity_developed_ex_us_parent | 0.00% | 0.00% | 0.00% | 0.00% |
| EMB | credit_emerging_usd | 0.00% | 0.00% | 0.00% | 0.34% |
| EWA | equity_australia | 1.36% | 0.00% | 1.71% | 0.00% |
| EWC | equity_canada | 2.57% | 2.38% | 1.74% | 1.72% |
| EWG | equity_europe | 3.06% | 0.23% | 1.80% | 1.17% |
| EWH | equity_hong_kong | 0.80% | 0.04% | 0.73% | 0.36% |
| EWJ | equity_asia_ex_china | 1.38% | 0.11% | 2.42% | 1.42% |
| EWT | equity_asia_ex_china | 4.98% | 2.04% | 5.76% | 3.24% |
| EWU | equity_europe | 2.23% | 1.08% | 2.98% | 2.56% |
| EWY | equity_asia_ex_china | 1.52% | 0.69% | 1.91% | 1.32% |
| GLD | commodity_precious | 2.13% | 0.20% | 3.70% | 0.00% |
| HYG | credit_usd_high_yield | 0.62% | 2.59% | 0.33% | 2.75% |
| IAT | equity_us | 4.04% | 1.15% | 4.15% | 0.98% |
| IBB | equity_us | 1.11% | 0.08% | 1.07% | 1.07% |
| IBND | credit_ex_us_unhedged | 0.00% | 0.00% | 0.00% | 0.00% |
| IEF | sovereign_us | 0.00% | 0.00% | 0.52% | 0.98% |
| IGOV | sovereign_developed_ex_us | 0.00% | 0.00% | 0.00% | 0.00% |
| INDA | equity_asia_ex_china | 6.25% | 2.08% | 6.40% | 3.13% |
| ITA | equity_us | 3.49% | 0.49% | 1.29% | 1.53% |
| IWM | equity_us | 2.00% | 1.10% | 1.14% | 1.02% |
| LEMB | credit_emerging_local | 0.00% | 0.00% | 0.00% | 0.00% |
| LQD | credit_usd_investment_grade | 0.00% | 0.00% | 0.00% | 0.00% |
| MBB | securitized_us | 0.00% | 0.09% | 0.00% | 0.00% |
| MCHI | equity_china | 0.79% | 0.00% | 1.37% | 0.00% |
| MDY | equity_us | 3.21% | 1.07% | 0.00% | 1.53% |
| PPLT | commodity_precious | 1.06% | 0.04% | 2.11% | 0.34% |
| SHY | sovereign_us | 0.00% | 2.44% | 0.00% | 1.91% |
| SLV | commodity_precious | 3.11% | 0.04% | 3.31% | 0.31% |
| SOXX | equity_us | 4.51% | 0.64% | 4.23% | 0.76% |
| SPY | equity_us | 0.00% | 0.36% | 0.00% | 1.23% |
| TIP | inflation_linked_us | 0.85% | 3.82% | 0.36% | 1.71% |
| TLT | sovereign_us | 0.25% | 0.25% | 0.20% | 0.20% |
| VGK | equity_europe | 0.00% | 1.11% | 0.34% | 0.68% |
| WEAT | commodity_agriculture | 0.13% | 0.13% | 0.20% | 0.20% |
| XLB | equity_us | 0.67% | 0.56% | 0.00% | 0.76% |
| XLC | equity_us | 6.84% | 0.84% | 4.47% | 2.96% |
| XLE | equity_us | 4.94% | 1.73% | 5.33% | 3.92% |
| XLI | equity_us | 3.56% | 0.92% | 0.38% | 1.70% |
| XLK | equity_us | 2.81% | 1.31% | 2.44% | 3.28% |
| XLP | equity_us | 3.18% | 2.70% | 0.44% | 2.48% |
| XLU | equity_us | 5.16% | 1.55% | 3.98% | 3.17% |
| XLV | equity_us | 2.06% | 2.45% | 0.75% | 1.15% |
| XLY | equity_us | 3.25% | 0.59% | 0.85% | 0.99% |

## Verification and decision

57 focused tests passed, including causal windows, missing/zero-volatility inputs,
singleton momentum gates, cash slots/caps, parent-child exclusions, duplicate
class refusal, future-label boundaries, missing-IC rejection and frozen-input
tampering. Ruff passed. Independent arithmetic acceptance checked **5,800 daily
target vectors, 179,940 member scores, 16 adoption policies, 4,485 adoptions,
128 window turnover totals and 2,144 monthly IC observations**. Target attribution
reconciles, labels remain inside each window, and all 16 gate verdicts reproduce.
Decimal summation can differ in the last context digit; independent event checks
use 1e-24 distance tolerance and verify no event is within 1e-20 of its threshold.

The protocol and results are frozen in
`var/research/class-volatility-screen-20261016-v1/`. The
[protocol](../research/class-volatility-screen-20261016-v1/protocol.json),
[compact summary](../research/class-volatility-screen-20261016-v1/summary.json)
and [hash receipt](../research/class-volatility-screen-20261016-v1/receipt.json)
are retained alongside the chart and attribution.

**Decision:** reject these 16 mappings at the pre-test and stop this item for
review. Do not retune their thresholds, horizons, class counts or volatility rule
on the inspected sample. The next research decision is whether to register a
cash-relative, peer-comparable momentum hypothesis that separates bill carry
from risky-asset selection, with an explicit horizon and prospective observation
period. That is a new hypothesis, not an automatic rescue of this family.
Historical membership/mandate evidence and P6.15 resource work remain open.
No tracked-strategy, allocation, paper policy or live-routing setting changed.
