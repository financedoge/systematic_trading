# P4.21 — constituent Alpha33 feasibility pilot

Completed 108 new net backtests plus one frozen-weight winner-dependence replay. March 3–May 30, 2025; no parameter selection, training fit or claimed pristine OOS result. The monthly case remains the primary test regardless of sensitivity results. No strategy was promoted or given execution authority.

## Main comparison

| Model / control | Net return | Annualized Sharpe | Max drawdown | Fees USD | Mean invested |
| --- | ---: | ---: | ---: | ---: | ---: |
| constituent33-monthly | -2.37% | -0.286 | 13.93% | 992.85 | 97.88% |
| etf33-monthly | -3.86% | -0.468 | 14.58% | 1,536.01 | 97.84% |
| momentum126-monthly | -2.51% | -0.267 | 15.15% | 1,114.88 | 98.24% |
| unranked-monthly | -2.66% | -0.246 | 15.09% | 560.17 | 98.04% |
| covered-buyhold | -2.35% | -0.169 | 15.95% | 491.27 | 98.20% |
| full-pool-buyhold | 1.50% | 0.402 | 10.42% | 491.90 | 98.40% |
| FR25-reference | -0.50% | -0.078 | 8.31% | 1,248.77 | 98.21% |
| URTH | 1.17% | 0.301 | 15.37% | 493.99 | 98.80% |
| BIL | 0.94% | 15.033 | 0.05% | 490.11 | 98.08% |
| cash | 0.00% | 0.000 | -0.00% | 0.00 | 0.00% |

![Matched monthly net paths](comparison.png)

The same daily coverage and liquidity mask governs the three models and unranked control. Holdings coverage can change by day; see [every eligibility change](coverage.json). All controls use the same audited ETF quotes and accounting, except FR25's frozen signal generation comes from its original published inputs. FR25 is an empirical reference, not a matched constituent-alpha ablation. Cash earns zero; BIL/URTH controls have a 98% initial allocation. Buy-and-hold controls enter once and drift, with no terminal liquidation.

## Qualified input basis

Raw traded stock open/close for the same-session Alpha33 ratio; common split/dividend factors cancel. ETF portfolio returns, sizing, vol and momentum continue to use the existing pinned split/dividend-adjusted histories. No raw stock return series is presented as total return. The original five-ETF coverage run is retained separately and made no alpha trades. This version admits explicitly labelled single-source CRSP observations after identity, field, session and overlap checks. Conflicting overlaps remain quarantined.

## What was tested

Public December 31, 2024 SEC holdings, filed before the first signal → dated permanent security identity → separately audited stock open/close → rank(open/close − 1) across unique observed constituents → filed-value weighted ETF score, only with at least 95% equity value and 70% position coverage → same eligible ETF pool → top six and 63-return inverse volatility → 98% budget, 45% cap → frozen rebalance policy → next-open whole adjusted-unit fills and fees.

Higher Alpha33 selects stocks whose open was high relative to the close, an intraday reversal hypothesis. ETF33 applies the same formula directly to each ETF. Momentum uses 126-session return; unranked removes the score ranking. Missing positions stay in the coverage denominator. Fewer than six eligible names or all equal ranked scores produces cash. No stops, protective exits, leverage, fitting or rule changes follow from these results. Full decision and source rules: [frozen protocol](protocol.json).

## Chronology and timing

| Month | Constituent33 return / Sharpe | ETF33 return / Sharpe | Momentum return / Sharpe |
| --- | ---: | ---: | ---: |
| march | -4.44% / -3.566 | -3.38% / -2.827 | -4.86% / -2.966 |
| april | -0.57% / -0.013 | -2.48% / -0.514 | -2.72% / -0.668 |
| may | 2.74% / 2.435 | 2.03% / 1.929 | 5.34% / 5.452 |

| Timing (fixed before results) | Constituent33 return / Sharpe / turnover | ETF33 return / Sharpe / turnover | Momentum return / Sharpe / turnover |
| --- | ---: | ---: | ---: |
| monthly | -2.37% / -0.286 / 8.1x | -3.86% / -0.468 / 12.7x | -2.51% / -0.267 / 9.2x |
| daily | -3.95% / -0.405 / 283.6x | -3.49% / -0.347 / 283.6x | -3.44% / -0.408 / 39.6x |
| 0.40 | -4.10% / -0.425 / 280.9x | -3.30% / -0.320 / 281.5x | -1.21% / -0.069 / 16.2x |

Turnover is annualized gross traded notional / opening NAV. Annualized Sharpe and turnover over this short window are descriptive, not forecasts. Target-change threshold is strict L1 >0.40 including cash versus the last adopted target, plus monthly reset; actual holdings drift is not a trigger. Daily is a fixed-interval sensitivity, not a post-result recommendation.

| Cost bp | Extra session | Primary return | Sharpe | Drawdown |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 0 | -2.37% | -0.286 | 13.93% |
| 5 | 1 | -0.55% | 0.022 | 12.32% |
| 10 | 0 | -2.47% | -0.302 | 13.99% |
| 10 | 1 | -0.66% | 0.004 | 12.38% |
| 20 | 0 | -2.68% | -0.336 | 14.11% |
| 20 | 1 | -0.86% | -0.031 | 12.50% |

[Every cost, delay, control and monthly metric](results.json) includes actual fees, exposure, turnover, return and drawdown. No annual cost ceiling is imposed.

## Winner dependence

Largest primary contributor: ITA, 1.96 percentage points. Replacing only that asset's frozen weights with cash, without reranking or reallocating, gives -4.34% net return, Sharpe -0.784 and drawdown 12.45%. This is an ex-post sensitivity, not a new strategy or a causal claim about a market theme. [Full attribution](attribution.json), [winner diagnostic](winner-dependence.json) and [individual same-window buy-and-hold references](individual-buyhold.json) are retained.

## Coverage and evidence limits

Screened all 52 supported-pool candidates; 52 have qualified complete ETF prices. Only 16 had the selected public holdings quarter. Initial eligible allocation pool: IAT, IBB, ITA, IWM, MDY, SOXX, SPY, XLC, XLE, XLK, XLP, XLU, XLV, XLY. Daily eligible counts range from 14 to 14. This cannot establish superiority over the full 52-candidate pool.

| Fund with public holdings | Eligible sessions (including final diagnostic close) | Initial equity-value coverage | Minimum coverage |
| --- | ---: | ---: | ---: |
| IAT | 64 | 100.00% | 100.00% |
| IBB | 64 | 97.82% | 96.87% |
| ITA | 64 | 99.89% | 99.89% |
| IWM | 64 | 96.39% | 95.27% |
| MDY | 64 | 97.61% | 96.82% |
| SOXX | 64 | 96.36% | 96.36% |
| SPY | 64 | 97.32% | 97.23% |
| XLB | 0 | 72.55% | 72.55% |
| XLC | 64 | 100.00% | 100.00% |
| XLE | 64 | 100.00% | 100.00% |
| XLI | 0 | 92.74% | 92.74% |
| XLK | 64 | 96.42% | 96.42% |
| XLP | 64 | 99.34% | 99.34% |
| XLU | 64 | 100.00% | 100.00% |
| XLV | 64 | 97.56% | 97.56% |
| XLY | 64 | 97.16% | 97.16% |

- Only one public holdings quarter; portfolios deliberately frozen, not contemporaneous actual holdings after December 2024.
- Full 52-candidate scope screened, but holdings-signal allocation only where public dated holdings and daily coverage qualify; not a full-pool superiority claim.
- Current-vintage revised prices and CRSP identities; original historical dissemination is unknown. Public SEC filing availability is evidenced separately. Reused history is not pristine out of sample.
- Three months cannot establish Sharpe stability or an investment edge. Annualized metrics are descriptive only; inspect monthly results and winner dependence.
- Synthetic whole adjusted units, zero cash interest, no taxes/spread/impact; stated per-notional costs and delay sensitivity only. No stops or protective exits.
- CRSP-only observations without an independent existing overlap are admitted after source/identity/field/session checks and labelled single-source. Historical availability and corporate-action vintage are not certified; no constituent total returns are inferred.

WRDS extracts remain saved locally with exact SQL, parameters, types, timestamps and hashes. Backtesting reads a new immutable native publication after field/date qualification; it never reads provider archives as strategy inputs. Original volume/full-history audit verdicts were preserved. The projection supports open/close only and is research-only. Public filing dates are evidenced; price vintage dissemination remains unknown. [Publication receipt](publication.json).

## Weakest held risky ETF

Criterion fixed before results: lowest net contribution divided by opening portfolio NAV, excluding cash references and assets never held in the window. This contribution criterion includes allocation and costs; it is not the asset's standalone return. Every monthly window is shown. FIFO lots overlapping a window may span other months and therefore do not sum to that month's contribution.

### full: MDY (-1.38 pp)

![Dated price, volume, states, fills and contribution](weakest-full-MDY.png)

[Exact observations and FIFO outcomes](weakest-full-MDY-detail.json).
### march: IAT (-1.14 pp)

![Dated price, volume, states, fills and contribution](weakest-march-IAT.png)

[Exact observations and FIFO outcomes](weakest-march-IAT-detail.json).
### april: MDY (-0.39 pp)

![Dated price, volume, states, fills and contribution](weakest-april-MDY.png)

[Exact observations and FIFO outcomes](weakest-april-MDY-detail.json).
### may: XLV (-0.91 pp)

![Dated price, volume, states, fills and contribution](weakest-may-XLV.png)

[Exact observations and FIFO outcomes](weakest-may-XLV-detail.json).

## Validation

Independent native LEAN verified 3 cases: primary constituent, matched ETF control and dynamic stressed/delayed constituent. Maximum daily NAV difference was $0.00. The separate inspection book reconciled within $0.0000. Native replay validates orders, fills, cash and NAV from frozen targets, not the economic hypothesis. [Native validation](native-validation.json).
