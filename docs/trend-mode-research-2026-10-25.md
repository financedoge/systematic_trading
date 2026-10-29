# Separately parameterized range, up and down modes — October 25, 2026

[Full ETF table, fitted parameters and state charts](../research/trend-modes-20261025-v1/index.html)
· [Protocol](../research/trend-modes-20261025-v1/protocol.json)
· [Results summary](../research/trend-modes-20261025-v1/summary.json)

## Question and authority

The operator proposed separate parameter sets for range-bound, rising-corridor
and falling-corridor identification, with several price/volume methods. Buy on
range/down to up; hold through range; sell only when a down mode is confirmed.
This includes up-to-range-to-down, preventing an accidental permanent holding
caused by demanding adjacent up/down labels. There is no inherited TP, initial
stop, time exit or cooldown in the primary strategy. No runtime, monitoring,
funding, approval, broker or promotion changes are made.

This implements three independently parameterized detector blocks, jointly
selected on training trading outcomes. It does not claim three supervised models
trained against objectively correct trend labels. Return optimization cannot by
itself establish whether the identified corridors match a human's interpretation.

## Frozen design

Three methods, each with price-only and volume-confirmed versions:

- Regression: log-price slope scaled by ATR, with R-squared quality.
- Channel structure: changes in lower/upper price quantiles between the first
  and last thirds of the window, with directional price-path efficiency.
- Moving-average corridor: fast/slow mean-log separation, slow-mean direction
  and price-path efficiency.

Each range block has its own length, drift, width/ATR, efficiency, confirmation,
box buffer and optional activity ceiling. Up and down each have their own length,
strength/ATR, quality, confirmation and optional pressure/activity thresholds.
Short windows: 10/21/42/63 sessions; long: 63/126/189/252. ATR20 is common volatility
normalization. Volume is audited raw shares relative to the strictly previous
21-session median, capped at 5x; signed price-volume pressure is not observed order
flow. Range uses prior information and the current close's position inside the
prior box. Directional features use information available at the current close.

An intact prior range box has priority over directional evidence on another
timescale. Otherwise, conflicting up/down detectors need a 25% normalized
strength/quality advantage. Unresolved/absent evidence retains the last confirmed
mode; the initial mode is unknown. Unknown-to-up does not initiate a trade.
Every desired-position change executes at the next open, with a symmetric added
session in the delay test; pending changes remain binding. Idle cash earns zero.

All 52 supported ETFs use the same verified published adjusted OHLC/raw-volume
batch 5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd.
No price downloads, substituted sources or filled observations. Historical
membership and publication-vintage limitations remain. Asset data ends October 16;
matched portfolios end October 12. USD adjusted-unit research, no CNH/FX claim.

The grid was sealed as protocol
8e230d2622e0be26436a48c0592d06f22264803521004dde811e268c999bb656
before fitting/evaluation. Each ETF/domain/cutoff gets 384 configurations: 64 per
method/volume family. Paired price/volume searches share price parameters. Top 5
per family are rescored at 5/10/20 bp per side and 0/1 added execution session. Prefer
at least 5 closed training trades and 5% exposure at every friction, otherwise mark
insufficient evidence and still show the new-mode result. No old-strategy fallback
hides poor mode performance. Choose each family and the overall winner using
worst-friction utility, full training and three chronological blocks. The frozen
objective has a 3% Calmar floor; reported Calmar uses actual drawdown.

Train through 2022, evaluate January 3, 2023–October 16, 2026; independently train through 2019,
evaluate 2020–2022. Minimum 500 training sessions after 252 warmup. All 52 fit files
sealed before evaluation: 104 later and 100 earlier ETF/domain fits, 78,336 initial
training configurations plus finalist stress tests. Both periods were inspected
in prior research and remain development evidence, not untouched holdouts.

## Results

Overall training-selected modes, 5 bp per side, next open:

| ETF / fit | Previous breakout return | Previous fixed 21/1 exit | Mode-switch return | Sharpe | Max DD | IC21 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GLD short | +30.30% | +13.38% | +114.49% | 1.195 | -25.54% | +0.159 |
| GLD long | +51.45% | +10.40% | +94.09% | 1.016 | -26.40% | +0.046 |
| IAT short | -29.93% | -5.07% | +64.48% | 0.795 | -17.49% | +0.114 |
| IAT long | +6.72% | +10.05% | +18.81% | 0.330 | -31.28% | -0.026 |
| SLV long | +84.41% | -20.31% | +69.78% | 0.570 | -52.96% | +0.040 |
| SOXX short | +187.66% | +24.62% | +374.90% | 1.351 | -29.01% | +0.049 |

These are cumulative returns on the later common evaluation, not training
returns. GLD short uses the equal-budget pool anchor for the previous strategy;
the earlier original heavily optimized GLD fit is a different vector.

Of 102 risky later cases, 92 are positive, 9 negative,one flat. 74 improve the previous
breakout's CAGR; among 96 with adequate new training evidence, 70 improve and 26
worsen. Median CAGR 6.37%, Sharpe 0.562, exposure 82.97%. Only 15/102 beat their own ETF's
buy-and-hold CAGR and 20 beat its Sharpe. 86/102 have fewer than 5 closed evaluation
trades. Median IC21 is -0.057; 17 positive annualized alpha estimates, none surviving
Holm adjustment; one positive IC survives. These are descriptive diagnostics
after repeated development, not certified alpha.

Earlier: 59/98 positive, 39 negative; median CAGR 1.33%, Sharpe 0.190. 50 improve previous
CAGR across all 98; among 91 adequate-evidence cases, 43 improve and 48 worsen.
Median exposure 63.89%, IC21 +0.015; 53 positive alpha estimates, none survive Holm;
two positive IC estimates survive. 87/98 have fewer than 5 closed evaluation trades.
The later improvement does not transfer consistently to the earlier procedure.

| Detector family | Later median Sharpe | Earlier median Sharpe |
| --- | ---: | ---: |
| Regression, price | 0.524 | 0.111 |
| Regression, price + volume | 0.536 | 0.283 |
| Channel structure, price | 0.615 | 0.204 |
| Channel structure, price + volume | 0.578 | 0.210 |
| Moving-average corridor, price | 0.622 | 0.214 |
| Moving-average corridor, price + volume | 0.606 | 0.248 |

Volume helps regression most consistently; it does not universally improve
results. Later training choices select regression in 66/104 cases, structure in 20,
average in 18; 51 use volume. Those choices precede evaluation. No family passes the
full preservation design. For selected later cases, only 47.92% of the 96 adequate
cases stay within 1 pp CAGR loss and 2 pp DD deterioration versus previous breakout;
earlier 26.37%. The requirement is 90% across both eras and all frictions.

## What the charts reveal

IAT short holds through 560 range-labelled sessions and earns +64.48%. Its mode is
range 88.85% of the evaluation period. Local range criteria can describe portions
of a stair-step advance; profitability does not prove the label means a globally
horizontal market. This is a parameter-identification issue to inspect, not an
execution discrepancy. GLD long has only 24.40% of sessions with fresh qualifying
evidence, retaining a prior mode otherwise; its return depends heavily on one
open trade from February 2024.

SLV long enters April 19, 2024 at 25.93, captures the advance, and exits July 17, 2026
at 49.70 for +91.48% on that trade. Yet maximum account drawdown is 52.96%, from the
January 28, 2026 peak to July 17. Its up detector uses 189 sessions; down uses 126 with
strength 4 ATR, quality 0.4, three confirmations. First confirmed down evidence arrives
July 6. Both directions qualify, and normalized-strength arbitration retains up
for eight additional sessions; down finally wins July 16. No intact range box
blocks those down detections. The long window first delays recognition, then
cross-timescale conflict handling delays adoption. The strategy meets the
requested trading rule while identifying this reversal too late.

Worst net result is CORN short: -29.19%, Sharpe -0.834, versus buy-hold -32.45%. Seven
trades include a June 2023 entry losing 13.35% in ten sessions. EWA short loses 19.47%
while buy-hold gains 45.80%; it holds through 544 range-labelled sessions and suffers
a February–April 2025 trade loss 14.31%. These cases differ from merely missing a
rally and remain visible in the full-pool table.

## Portfolio comparison and decision

Same full 52 liquidity-admitted pool, six 98%/6 momentum slots, rank buffer 8 and
BIL vacancies; selected short/long position-state union for admission. Dynamic
membership and monthly controls. FR25 overlay uses 0.5 + 0.25 × short + 0.25 × long with diverted
weight in BIL; dynamic cash-inclusive last-adopted target change ≥ 10% plus monthly,
versus monthly only. No annual trading-cost ceiling.

| Later portfolio, 5 bp, next open | CAGR | Sharpe | Max DD | Turnover/year | Cost bp/year |
| --- | ---: | ---: | ---: | ---: | ---: |
| FR25 | 16.51% | 1.450 | -8.65% | 8.694 | 43.47 |
| Previous dynamic breakout overlay | 12.34% | 1.395 | -7.55% | 8.538 | 42.69 |
| New dynamic mode overlay | 15.51% | 1.430 | -8.31% | 8.961 | 44.80 |
| New monthly mode overlay | 15.43% | 1.425 | -8.36% | 8.604 | 43.02 |
| Ungated dynamic momentum | 10.60% | 0.781 | -14.36% | 21.531 | 107.65 |
| New dynamic mode selector | 10.82% | 0.795 | -14.36% | 21.277 | 106.38 |

The new selector's modest later gain over ungated momentum does not establish
SOTA improvement. Earlier dynamic mode selector 1.87% CAGR / 0.198 Sharpe underperforms
the previous selector 3.57% / 0.316. Earlier monthly mode selector 7.86% / 0.598 slightly
raises return but lowers Sharpe versus previous 7.69% / 0.605. None of 24 later or 12
earlier matched portfolio/friction gates pass. Keep this as research evidence;
no SOTA replacement or promotion is justified.

## Verification and next hypothesis

8,568 asset/friction cases; all selected training scores and causal prefixes
reproduce. Independent event-ledger relative NAV error ≤ 2.31e-14. 102 matched
portfolio cases, 66 unchanged control cases reproduce exactly. Three independent
native Windows LEAN checks (dynamic overlay, delayed overlay, dynamic selector)
have zero NAV difference. 18 focused tests and Ruff pass; offline report controls
cover both eras, seven variants, 1,428 detail records and 30 chart windows. Static
figures inspected; browser layout is not certified. No frozen prior research
code was modified.

The next separately declared test should examine faster down detection and
state-dependent arbitration of fresh down versus older up evidence, preserving
hold-through-range. Range identification also needs a shape/semantic objective
or visual acceptance criterion separate from merely maximizing trading return.
Volume can be tested as entry confirmation versus an exit veto, with paired
price controls. Do not retune this completed experiment or select ETF membership
from its evaluation winners. Retain full-pool training-only selection, costs,
delays, chronological robustness and dynamic/monthly portfolio checks.
