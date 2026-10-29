# N=15 strategy-sleeve portfolio backtest — 2026-10-29

Completed the operator-requested fixed N=15 experiment using frozen entry-value B (`symmetric-trend-sleeve-v1`). The ranking layer is not a demonstrated improvement. Equal capital is the clearer working reference; unranked full-pool sleeves have better primary Sharpe in both chronologies. The subsequent request for N20/N30 is a separate declared extension.

[Interactive report, all ETF charts and historical ranks](../research/trend-sleeve-portfolio-20261029-v1/index.html)

## Primary results

5 bp each traded side; monthly allocation, daily strategy signals, next-open fills. USD fractional adjusted-unit accounting; zero interest on sleeve cash. Sharpe uses a zero reference rate, not BIL excess.

| Era | Portfolio | Net cumulative | CAGR | Sharpe | Max drawdown | Calmar |
|---|---|---:|---:|---:|---:|---:|
| late | N15 equal capital | 18.15% | 6.38% | 0.776 | 7.67% | 0.831 |
| late | N15 covariance risk parity | 12.06% | 4.31% | 0.692 | 6.63% | 0.650 |
| late | Unranked full pool | 17.50% | 6.16% | 1.144 | 6.10% | 1.009 |
| early | N15 equal capital | -4.19% | -2.12% | -0.217 | 12.91% | -0.164 |
| early | N15 covariance risk parity | -4.73% | -2.40% | -0.325 | 11.42% | -0.210 |
| early | Unranked full pool | -1.13% | -0.57% | -0.049 | 11.04% | -0.052 |

Late: first decision2024-01-31, invest2024-02-01 through2026-10-16; models trained<=2022-12-30. Early: decision2020-12-31, invest2021-01-04 through2022-12-30; models trained<=2019-12-31. At least252post-fit shadow-return observations before first month-end ranking. Thus funded portfolio evidence excludes2020crash and2023. Both eras were inspected repeatedly.

## Exact recipe

All51/49risky ETF virtual strategies continue while unselected. BIL is a separate reference. Four equally weighted percentile ranks: net strategy return and Sharpe over63/252sessions, including cash. Average rank ties, then ticker. Complete aligned history and nonzero volatility both windows; no positive-return gate. Top15, no width search. Monthly capital rebalance plus existing daily signals; no cash redistribution between allocations. Joining an already active shadow buys at the allocation open, preserving its signal/stop state; pending exit dominates. Leaving liquidates only the actual portfolio.

Equal capital or252-session strategy-return covariance ERC;50%diagonal shrinkage,5%annual volatility diagonal floor, no leverage or concentration cap. Solve post-fee capital self-consistently, net same-open allocation/signal trades and charge each actual fill once. Use shadow NAV only for ranks. Independent global cash/share ledger and per-ETF P&L contributions reconcile.

## Findings

- Average active ETF count8.64later/7.99earlier despite15selected; cash42.04%/46.34%. Risk-parity effective invested breadth6.76/6.55, largest capital weights27.18%/24.99%.
- N15monthly equal has annual costs76.97/78.29bp versus57.82/58.01for unranked sleeves. No absolute annual-cost gate applied.
- Cross-sectional rank versus subsequent21session shadow-return mean IC−.032later/−.024early, descriptive and not executable entry alpha.
- N15equal passes Sharpe/CAGR/DD guards versus unranked in2of12era/friction settings; risk parity0of12. Neither is stable.
- One extra execution session changes early equal return−4.19%to+2.99% at5bp. Costs affect shadow ranks as well as portfolio fees.
- Dynamic10%cash-inclusive target change triggers on a single15-way ETF/cash flip (L1=2/15=13.33%):538later allocations versus33monthly. Costs roughly double; equal dynamic passes no matched monthly guards. This is threshold/width interaction, not a universal dynamic rejection.
- Declared21/126rank sensitivity improves returns but remains below unranked primary Sharpe in both eras. Only5bp/zero-extra-delay diagnostic; no adoption.
- Later raw-ETF rankN15returns53.87%,Sharpe1.113,DD12.85%; full-pool buyhold49.26%,1.307,DD11.01%. Higher exposure/risk matters.
- FR25replayed frozen monthly targets at matched USDdates throughOct12; own universe/risk design, no claim that it is a universal gold standard.

## Weakest cases

Weakest matched-window shadow: TLTlate−18.56%, MCHIearly−31.99%. Worst actual equal-capital contributors: IATlate−1.535pp, XLYearly−2.477pp. Actual fills, shadow OHLCV/states/stops and all100risky ETF-era charts are available with date hover and interval selection. IAT allocation buysAug1 2024 at45.00, daily exitAug6 at41.05; XLY allocation buysJun1 2022 at74.72, protective exitJun13 at67.07. Mature-trend joining, failed rebounds, closing-stop latency and gaps remain. N15avoids IATMarch–April2025shadow−15.76%loss, so standalone worst trades must not be attributed to the portfolio without holdings.

## Validation and limitations

106portfolio cases,612exact frozenBmatches;17focused/regression tests;100chart combinations/171allocation dates offline; three native Windows multiasset accounting fixtures match the app reference to the cent. Native uses execution-open target oracles and whole units: accounting-only, not independent HMM/ranking/causality validation. Fractional global ledger max error2.22e-14; contribution2.01e-14; ERC1.05e-7. Static figures inspected; offline DOM controls tested, not browser layout certification.

Pinned batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd. Published adjusted OHLC and audited raw volume, strict calendars, no fills/substitution. Retrospective universe and publication-vintage limitations; no FX, tax, actual spread/impact or intraday protection. Underlying fixed thresholds inherit extensive earlier research. No new fits or prices.

The first draft protocol is retained as `protocol-pre-evaluation-1.json`: a chart-input adapter tried to read high/low from a feature object that only holds open/close/volume. Corrected it to the already audited OHLC source and resealed before any portfolio evaluation. No performance-driven change.

## Recipe and authority

Run `scripts/research_trend_sleeve_portfolio.py prepare`, `shadows`, then `evaluate` in a new versioned output directory; existing completed evidence is protected. Report builder and native validator are retained. Compact artifacts and source hashes are sealed. Retain equal capital as reference and full pool as control; inspect weakest trades and ranking timing before another isolated test. User subsequently requested N20/N30. No monitoring, broker, live or approval settings changed.
