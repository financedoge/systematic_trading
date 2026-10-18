# Expanded ETF study — October 14, 2026

The first expanded FR25 candidate is rejected by the registered pre-test. It estimates **67.73 bp annual cost**, above the **44 bp ceiling**, and its calibration rank IC is **−0.01463**. No expanded portfolio NAV or performance advantage is claimed: its full replay was withheld by the frozen rule. The original 14-ETF FR25 control passes. No strategy, allocation or broker authority changed.

## Scope and verified inputs

The approved first wave contains 52 candidates: the original 14 plus 38 additions. All 38 additions passed current issuer/ISIN broker identity discovery. The application recorder published 39 of its 41 configured entries, including refreshes of BIL/XLE/XLB. XOP remains outside the candidate wave and held. Execution admission remains limited to the reviewed 14-ETF contract.

The study reads only published, hash-verified histories from catalog `0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`, through **October 12, 2026**. The resulting study pool has **50 funds**. BWX is held because the issuer lists October 2, 2007 while the provider starts October 11. CPER is excluded from this common-window study because its August 23, 2018 audited raw volume is zero and the current activity-model contract requires positive volume. The bar is present; this is a model-input limitation, not a missing-price claim or a revocation of its recorder publication. No source is spliced, trimmed to conceal a conflict or filled.

Common input history starts **June 19, 2018**, the youngest supported fund’s start. Trading decisions span **January 4, 2021–October 12, 2026**, with 70 monthly decisions. Both arms retrain the unchanged app-owned FR25 recipe on this common history. This control differs from app monitoring that has longer training history. Features use prior observations; financial fits require completed labels and abstain to M1 when unavailable. Selection, downstream XGBoost sizing, activity/USD overlays, defensive fallback and the 45% final cap are preserved.

The expanded arm applies the frozen admission mask: 253 prior observations, 63 prior-session raw-dollar activity with median at least $5 million and minimum at least $0.5 million, and at most one representative per duplicate group. Representatives use prior activity, then permanent ID; historical fees are unavailable. Full-pool feature ranks remain unchanged; no class or volatility normalization is silently introduced. Admission permits selection but never mandates allocation.

## Pre-test results

The calibration period ends December 31, 2024. IC is the mean monthly cross-sectional Spearman correlation of the FR25 selection score with the following 21-session open-to-open return, over that arm’s admissible pool. The gate uses candidate-specific IC and pooled forward-return dispersion, never the programme’s default IC. Costs use absolute target changes, including initial establishment, annualized over the calibration interval.

| Test | Original 14 control | Expanded 50 | Requirement |
| --- | ---: | ---: | --- |
| Annual target turnover | 8.635× | 13.546× | Cost-dependent |
| Implied annual cost at 5 bp | 43.17 bp | 67.73 bp | ≤44 bp |
| Calibration rank IC | 0.03545 | -0.01463 | Positive with ≥3× margin |
| IC / breakeven IC | 5.41× | -1.37× | ≥3× |
| Verdict | Pass | Reject | Both tests must pass |

Across all monthly decisions, 44–49 of the 50 funds passed the liquidity/duplicate admission mask. IBND failed liquidity in all 70 months; CORN, DBB, LEMB, WEAT, IGOV, IAT and DBA failed in some months. Thirty-eight distinct ETFs received positive targets. Average intended cash was 6.62%, versus 13.02% in the control. These are target diagnostics, not realized holdings or expanded portfolio returns.

## Completed control and benchmark replays

USD 100,000 initial capital, dividend/split-adjusted units, next-session open fills, whole adjusted units and zero cash interest. Native LEAN and the Python accounting oracle reconcile decisions, fills, cash and NAV to the cent. Each native run used two CPUs and a 4 GiB memory limit; runs were sequential. Costs are assumptions; spreads, market impact and slippage are not modeled.

| Replay | CAGR | Annual volatility | Sharpe, zero cash rate | Max drawdown | Final USD NAV |
| --- | ---: | ---: | ---: | ---: | ---: |
| FR25 original 14, 5 bp | 12.93% | 10.81% | 1.182 | -8.66% | 201,660.71 |
| FR25 original 14, 10 bp | 12.49% | 10.81% | 1.146 | -8.87% | 197,177.95 |
| URTH buy-and-hold, 5 bp | 12.82% | 15.81% | 0.844 | -26.05% | 200,586.83 |

The 5 bp control realizes 8.113× annual turnover and 40.57 bp annual costs. Its complete 14-asset P&L reconciles to the NAV change. The maximum order/prior-median-dollar-volume ratio is 0.415%, with 0 breaches of 0.5%. Historical spread qualification remains unavailable.

There is no paired expanded-versus-control return inference because the expanded replay did not pass admission to that stage. The planned later-period comparison and bootstrap remain unexecuted; omitted results are not zero or evidence of equivalence.

## Interpretation and next research boundary

Adding candidates changes the competition for six slots and the cross-sectional model ranks. The resulting increase in switching cost and negative calibration IC do not support adopting unchanged FR25 on this larger pool. This result does not establish that all ETF expansion is harmful. The accepted roadmap’s class/volatility-aware design needs a separately frozen specification and full-supported-pool tests; no tuning was performed to rescue this failed arm.

The cohort is selected from current surviving funds and uses current reference classifications. Historical membership and complete mandate history have not been reconstructed. Published adjusted prices are audited revised histories, not certified historical publication vintages. Economic archive availability before October 10, 2026 is an explicit retrospective assumption; later decisions require actual first-seen evidence. The 2025+ split is not an untouched holdout for the previously researched FR25 recipe. These diagnostics do not satisfy promotion gates.

## Full-pool attribution

Every supported constituent is included below. Expanded weights and turnover describe intended decisions only; original-control P&L is realized simulated attribution after fees. A dash means the asset was outside the control, not zero performance. Annual target turnover uses the 2021–2024 calibration interval.

| ETF | Selected months / 70 | Liquidity-excluded months | Mean expanded target | Annual target turnover | Original-control P&L, USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| AGG | 0 | 0 | 0.00% | 0.000× | — |
| BIL | 5 | 0 | 3.21% | 0.691× | — |
| CORN | 7 | 54 | 1.01% | 0.153× | — |
| DBA | 13 | 3 | 3.96% | 0.769× | — |
| DBB | 5 | 53 | 1.15% | 0.204× | — |
| DBC | 23 | 0 | 5.12% | 0.516× | 14,706.75 |
| EEM | 2 | 0 | 0.50% | 0.180× | — |
| EFA | 5 | 0 | 1.40% | 0.124× | — |
| EMB | 0 | 0 | 0.00% | 0.000× | — |
| EWA | 7 | 0 | 1.41% | 0.418× | — |
| EWC | 14 | 0 | 4.44% | 0.503× | — |
| EWG | 10 | 0 | 2.32% | 0.101× | — |
| EWH | 2 | 0 | 0.48% | 0.000× | 6,717.58 |
| EWJ | 10 | 0 | 2.21% | 0.387× | 11,110.80 |
| EWT | 26 | 0 | 5.89% | 0.758× | — |
| EWU | 7 | 0 | 2.04% | 0.441× | — |
| EWY | 14 | 0 | 2.65% | 0.304× | 18,708.77 |
| GLD | 12 | 0 | 3.10% | 0.298× | 12,072.42 |
| HYG | 0 | 0 | 0.00% | 0.000× | 5,341.39 |
| IAT | 9 | 4 | 1.63% | 0.275× | — |
| IBB | 7 | 0 | 1.14% | 0.152× | — |
| IBND | 0 | 70 | 0.00% | 0.000× | — |
| IEF | 0 | 0 | 0.00% | 0.000× | -392.09 |
| IGOV | 0 | 32 | 0.00% | 0.000× | — |
| INDA | 11 | 0 | 2.76% | 0.582× | — |
| ITA | 16 | 0 | 3.03% | 0.285× | — |
| IWM | 6 | 0 | 1.38% | 0.139× | — |
| LEMB | 0 | 60 | 0.00% | 0.000× | — |
| LQD | 0 | 0 | 0.00% | 0.000× | -1,611.23 |
| MBB | 0 | 0 | 0.00% | 0.000× | — |
| MCHI | 2 | 0 | 0.38% | 0.056× | 1,029.74 |
| MDY | 6 | 0 | 1.61% | 0.349× | — |
| PPLT | 9 | 0 | 1.56% | 0.271× | — |
| SHY | 0 | 0 | 0.00% | 0.000× | — |
| SLV | 12 | 0 | 1.91% | 0.195× | — |
| SOXX | 30 | 0 | 4.67% | 0.406× | — |
| SPY | 14 | 0 | 4.33% | 0.796× | 16,082.93 |
| TIP | 0 | 0 | 0.00% | 0.000× | — |
| TLT | 0 | 0 | 0.00% | 0.000× | -2,642.02 |
| VGK | 7 | 0 | 1.71% | 0.264× | 3,341.18 |
| WEAT | 3 | 47 | 0.40% | 0.039× | — |
| XLB | 4 | 0 | 1.05% | 0.283× | 1,644.72 |
| XLC | 21 | 0 | 4.85% | 0.616× | — |
| XLE | 22 | 0 | 3.64% | 0.396× | 15,549.77 |
| XLI | 10 | 0 | 2.91% | 0.605× | — |
| XLK | 28 | 0 | 6.40% | 0.581× | — |
| XLP | 3 | 0 | 0.90% | 0.228× | — |
| XLU | 9 | 0 | 1.69% | 0.457× | — |
| XLV | 6 | 0 | 1.47% | 0.315× | — |
| XLY | 15 | 0 | 3.08% | 0.409× | — |

## Replay and evidence

- [Frozen protocol](../research/etf-expansion-2026-10-14/protocol.json), [receipt](../research/etf-expansion-2026-10-14/receipt.json), and [full target attribution](../research/etf-expansion-2026-10-14/target-attribution.json).
- Full immutable input/model/result manifests, 70 decisions per arm, all admission reasons, native economic ledgers and per-asset daily attribution: `var/research/etf-expansion-20261014-v1/`.
- Application-owned model/replay composition: `scripts/run_etf_expansion.py`, stages `prepare`, `models`, `replay`. Existing complete artifacts are verified and reused; failed attempts are retained.
- Synthetic 52-asset native/Python parity is separate engineering evidence: `var/research/execution-expansion-20261013-v1/synthetic-52-parity-v2/`. It is not an investment backtest.
- [FR25 paper execution readiness](execution-readiness-2026-10-13.md); actual capital remains F3 100%.
