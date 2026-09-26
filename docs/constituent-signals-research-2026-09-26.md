# Constituent information for ETF allocation

## Result: retain SOTA

**The tested constituent overlays do not establish an improvement.** All 15 native LEAN runs passed unchanged parity and were registered as research evidence. The fixed composite lowered full-period CAGR from **8.52% to 8.49%**, Sharpe from **0.784 to 0.782**, with **IR -0.394**. Concentration acceleration lowered CAGR to **8.45%**, Sharpe to **0.778**, with **IR -0.507**. Full-period cumulative returns were 76.76% for SOTA versus 76.40% for the composite. These are measured results of the declared small SPY overlays, not a rejection of every possible constituent signal.

Because sufficient stock coverage begins in 2023, the more relevant active-history comparison is:

| Overlay on SOTA | CAGR, Jan 2023–Sep 24 2026 | Sharpe | IR versus SOTA | Monthly targets changed |
| --- | ---: | ---: | ---: | ---: |
| Unchanged SOTA | 14.72% | 1.292 | — | — |
| Concentration acceleration | 14.57% | 1.280 | -0.695 | 26 |
| Trend breadth | 14.72% | 1.295 | +0.026 | 29 |
| Breadth improvement | 14.66% | 1.287 | -0.260 | 32 |
| Momentum participation | 14.57% | 1.280 | -0.740 | 23 |
| Signed activity | 14.77% | 1.299 | +0.262 | 26 |
| Fixed constituent composite | 14.65% | 1.287 | -0.540 | 33 |
| ETF-price-only control | 14.79% | 1.301 | +0.299 | 34 |

Signed activity is the strongest constituent candidate in this sample, but adds only **0.058 percentage points of annual return** post-2023 and underperforms the price-only control. Its full-period annual arithmetic active-return 95% block interval is **-0.059pp to +0.112pp**, with family-adjusted one-sided p=**0.810** (post-2023 p=**0.831**). This does not establish additional information beyond ETF prices. Do not promote the best sample result or reverse negative signals after seeing these outcomes.

The primary remains below SOTA with 45bp combined fee/slippage (5.75% versus 5.79% CAGR), a one-session execution delay (9.07% versus 9.10%), half-sized tilts and lower coverage. The 60-day holdings lag yields identical composite trades even though 18 monthly cohort dates differ; that is limited sensitivity evidence, not proof of true historical availability. Only **44 of 84 monthly decisions** have qualified base features; SPY is selected on 39, and the primary changes 33. Pre-2023 constituent robustness is untested. The full-period max drawdown is identical at -13.54%, dominated by the earlier neutral period; post-2023 drawdowns are -8.488% for SOTA and -8.495% for the composite.

Daily descriptive Spearman IC for concentration acceleration is +0.070/+0.087/+0.052 at 20/60/120 sessions. Breadth IC is -0.231/-0.376/-0.450, and signed activity -0.065/-0.213/-0.295. These overlapping, reused-period associations need not agree with a monthly, conditional SPY sleeve's IR. They suggest testing a separately declared mean-reversion hypothesis on new evidence; they do not justify flipping signs on this sample. There are 906/866/806 daily labels, not that many independent observations. Price control/composite ICs use their ternary/averaged scores; single-signal ICs use the continuous underlying feature.

![Native LEAN results](D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1/results.png)

[Full metrics, stress results and uncertainty](D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1/report.md) · [Forward-return IC chart](D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1/ic.png)

Validation: **589 passed, 51 optional checks skipped** in the full repository suite; 45 focused checks passed with one optional integration skipped. Ruff and changed-file whitespace checks passed. Both plots were inspected. ClickHouse archives the 3,592 new feature records, 180 period/scenario metrics and source/report documents with exact payload-hash verification; all 15 native runs are in the immutable research registry. No new price download, broker action, service restart or promoted strategy change occurred.

## Scope and experiment

The first experiment adds historical U.S. stock information to the current SOTA's SPY allocation. It uses dated ITOT equity holdings as a broad U.S. equity proxy, not as exact historical SPY constituents. It does not apply U.S. stock measurements directly to VGK, EWJ, EWH, EWY or MCHI, or pretend bonds and commodities have stock constituents. Production strategy and paper/live controls remain unchanged.

The frozen protocol is `config/constituent-research-v1.json`. Evidence lives at `D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1/`. The comparison covers October 1, 2019 through September 24, 2026, with July 2018 ETF warmup. It reuses the same archived ETF/FX snapshot as the previous LEAN study so different downloads cannot explain differences between variants. The old 2013-start headline is not a matched comparison for this shorter test.

Fifteen native LEAN runs are declared before looking at their returns: SOTA, five single signals, an equal-weight primary composite, a price-only control, three composite sensitivities, and matched SOTA/composite high-cost and delayed-execution pairs. SOTA and primary recompute targets inside LEAN from frozen code/features; the other trials replay frozen targets through native LEAN orders, fills and accounting. An independent Python reference must match the original target/fill/quantity and money tolerances. No parameter fitting, retraining or winner substitution is part of this round.

## Signals tested

All stock calculations use the same dated cohort and a fixed subset with a complete 211-session price/volume lookback. This makes the concentration derivative insensitive to mechanical membership changes *within its own backward stencil*. It does not eliminate all changes in scores between monthly decisions when a new cohort becomes available. Prices for stock momentum and breadth use adjusted closes; activity uses provider close times volume.

| Signal | Definition and ex-ante direction | Interpretation |
| --- | --- | --- |
| Concentration acceleration | Across-sector dollar-volume HHI, causal EMA(10), backward second difference with lag 10, divided by the previous 126 derivatives' standard deviation. Score +1 above +0.5, -1 below -0.5. | Literal test of the proposed acceleration direction. Concentration has no inherent bullish direction, so this is a hypothesis to test. |
| Trend breadth | Fraction of observed stocks above their 126-session moving average; +1 above 55%, -1 below 45%. | Is the advance broad or dependent on a few large names? |
| Breadth improvement | Change in the same cohort's breadth over 20 sessions; +1 above +3 percentage points, -1 below -3pp. | Is participation improving before the ETF price fully reflects it? |
| Momentum participation | Mean stock 63-session return minus the same stocks' lagged holding-value-weighted return; +/-2pp dead band. | Are smaller constituents participating, or are the largest names carrying the index? |
| Signed activity | Over 21 sessions, sum of stock dollar volume times the sign of that stock's daily adjusted return, divided by all observed dollar volume; +/-5% dead band. | Is trading activity associated with advancing or declining stock prices? This is not measured buying pressure or net inflow. |
| Fixed composite | Equal mean of the five ternary scores, with no fitted coefficients. | Predeclared primary test of combining constituent information. |
| ETF price control | SPY's 63-session price return, +/-2% dead band. | Tests whether any apparent benefit can already be obtained from the ETF price using identical sizing and coverage eligibility. |

Every score uses information only through the completed session before the monthly trade. The overlay adjusts an already positive SPY target by 15% times the score, capped at 3 percentage points. Offsetting changes go proportionally to other selected ETFs, bounded by 3pp per asset and the 45% target cap. It preserves total gross exposure/cash, creates no new ETF selection and uses no leverage. An inherited target above the cap cannot be increased. Thus this tests incremental allocation information, not a completely new timing strategy.

## Data and coverage

Source: 95 historical monthly ITOT snapshots, 5,923,052 stock-day records across 3,267 populated histories; all raw holdings/download responses, failures and documented aliases are already in ClickHouse. Historical sectors come from dated snapshots. Obvious name mismatches and ambiguous ticker reuse are excluded; unavailable names and their portfolio values remain in coverage denominators. A ticker/name heuristic is not a permanent security master.

The first-use timestamp of old holdings is unknown. Base features activate a snapshot 45 calendar days after its as-of date; 60 days is a declared sensitivity. No assumption is written as a genuine historical availability timestamp: ClickHouse `available_at` stays null. Today's provider-adjusted history is also not a certified historical vintage. These limitations prevent promotion or a claim of an unbiased whole-market backtest.

The base gate requires at least 95% of the **whole cohort's lagged holding value** and 70% of its names to have a complete lookback. This intentionally differs from the earlier sector plot's requirement that *every sector* pass separately. A missing 5% of holding value can account for more than 5% of turnover; the concentration feature retains that limitation. Individual sector value coverage is retained in each feature record. There are 1,796 feature dates under each availability assumption; 926 meet the 45-day base gate and 917 meet the 60-day gate. Ninety-percent value coverage is an explicitly lower-quality sensitivity (1,105 dates), not a repair of survivorship bias.

Below the gate, every overlay score is zero and SOTA's targets are unchanged. Forward returns and forward-return coverage never determine feature eligibility. For the main comparison, unavailable dates remain in the continuous return path; `signal_activity.json` separately counts available monthly decisions, positive SPY selections and actual target changes. The nominal seven-year backtest therefore does not provide seven years of active constituent evidence.

The base gate first passes on **January 17, 2023**. There are no qualified dates in 2019–2022, then 241 in 2023, 252 in 2024, 250 in 2025 and 183 in 2026. Accordingly this experiment cannot establish behavior in the COVID crash or 2022 selloff; identical pre-2023 performance is a neutral-fallback check, not evidence of robustness. Post-2023 metrics and uncertainty are reported separately.

## Evaluation

Report total return, CAGR, zero-hurdle Sharpe, drawdown, traded notional/NAV, fees, cash and information ratio (IR). IR is `sqrt(252) * mean(challenger daily return - SOTA daily return) / std(daily active return)`, computed from paired net CNH returns. It is undefined when tracking error is zero. Incremental CAGR and annual arithmetic active return are different quantities and are stored separately.

Robustness checks are: half-sized tilts, 60-day holdings delay, 90%-value coverage sensitivity, 25bp fees plus 20bp slippage, and one extra execution session. Both stressed strategies use the same costs/delay. Report pre-2023, reused post-2023, 2025-onward and calendar-year results. The tree was fitted before 2023 and SOTA has been selected using later data; none is an untouched holdout.

Paired circular block bootstraps use 63 and 126 sessions, 2,000 replications and a fixed seed. The centered max-t audit covers all ten challengers, including sensitivities and control. It is exploratory under nonstationarity and cannot correct missing delistings or earlier selection of SOTA. Daily Spearman/Pearson ICs at 20/60/120 sessions are descriptive, have overlapping labels, and are not independent observations or portfolio IRs.

## Next signal families and inclusion plan

| Priority | Candidate | Fixed first test | Data needed / public-data path | Inclusion question |
| --- | --- | --- | --- | --- |
| 1 | Actual ETF-specific participation | Reuse the five frozen definitions with each ETF's own dated stocks and weights, before adding thresholds. Compare exact SPY membership with this ITOT proxy. | Issuer historical holdings, effective/publication dates, exchange-qualified permanent IDs, delisted histories and corporate actions. For foreign ETFs add local calendars and prior-known FX; align the last fully closed constituent session to the U.S. ETF decision. | Does matching the traded ETF improve results beyond broad U.S. market breadth? |
| 2 | Downside breadth and joint declines | Fraction of members with negative 21-session returns; equal-pair sign co-movement over 63 sessions. Initially test risk reduction only when both are unusually high relative to their trailing 252-session history. | Existing stock bars can support a pilot after a 252-session warmup; the same membership/coverage limits apply. | Does it reduce drawdown beyond SOTA's existing volatility/adaptive trend controls, after cash drag? |
| 3 | Internal dispersion and narrow leadership | 63-session constituent-return interquartile range plus the gap between the top-ten-weighted names' return and the remaining basket. Standardize using trailing data; predeclare a trend-confirmation interaction before testing. | Existing stock histories and dated weights; exact ETF membership preferred. | Does narrowing leadership identify fragility, or is it just another momentum/capitalization exposure? |
| 4 | Fundamental participation | Fraction of constituents with improving year-over-year revenue and operating margin; lagged-weighted and equal-count versions. Use filing acceptance time and a full-session processing lag. | Public SEC filing submissions and original XBRL facts with accession/acceptance lineage; map company IDs to securities and store original filings. Quarterly reports, amendments and restatements must remain distinct. Foreign coverage needs issuer/regulator equivalents. | Does improving business breadth add information beyond price breadth over 60/120 sessions? |
| 5 | Holdings crowding and fund issuance confirmation | Weight HHI and top-ten holding share, plus creation/redemption or split-adjusted ETF-share growth. Require issuer-NAV/share timestamps before calling anything a flow signal. | Historical daily ETF shares outstanding, NAV, splits and published holdings. Current AUM or secondary-market volume cannot reconstruct this reliably. | Does actual issuance confirm a constituent signal or merely follow returns? |

Sequence: repair ETF/security identity and historical availability first; then evaluate the next two price-based families individually against the unchanged SOTA and price-only control. Freeze each family before observing outcomes, keep a complete results ledger, and do not recycle the best in-sample period as a holdout. Use prospective observations for the final confirmation. Fundamental/issuance families wait for their required public-source timestamps, rather than substituting revised present-day aggregates.

Retain a factor only if incremental net return/IR survives matched costs, delay, time splits and modest specification changes, and is not entirely explained by the ETF-price control. A positive sample IR alone is insufficient. Before paper inclusion require reproducible point-in-time inputs, a versioned factor contract, incremental risk/capital limits and the existing promotion process. No new scheduler or unattended recurring run is created by this plan.

## Replay and archives

```powershell
.venv/Scripts/python.exe scripts/run_constituent_research.py --root D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1 --resume
.venv/Scripts/python.exe scripts/analyze_constituent_research.py --root D:/systematic_trading_data/lean/research/constituent-signals-20260926-v1
```

New experiments need a new root; finished native bundles/runs are immutable. `input_manifest.json` freezes the actual feature-builder and identity-check code plus protocol, feature values and ClickHouse receipt. `datasets/*/manifest.json` freezes engine and strategy code. The feature matrices were computed from the hash-verified local mirror of the archived sources; the source publication/counts were checked against ClickHouse, and new feature payload hashes were read back exactly before publication. No additional price downloads were needed in this round.

ClickHouse source `constituent-research/constituent-signals-20260926-v1/features` contains 3,592 dated feature records (45-/60-day assumptions), protocol and coverage documents; source vintage `fcbc0b4cf6b6d493c544aa1de98a35864bb43e0066bd418355083eb71e2a7fda`. Results use the adjacent `/results` source. Native run evidence is registered separately in PostgreSQL `ops.lean_research_runs` as research-only; this does not alter trading proposals or policy.

## Primary sources

- [BlackRock ITOT](https://www.blackrock.com/us/individual/products/239724/ishares-core-s-p-total-u-s-stock-market-etf) and [historical holdings endpoint page](https://www.blackrock.com/ae/intermediaries/products/239724/ishares-core-sp-total-us-stock-market-etf) establish the fund's broad U.S. equity scope and issuer holdings source.
- [QuantConnect ETF constituent universes](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/etf-constituents-universes) describes membership and historical universe queries. The local open-source LEAN engine does not itself supply that historical dataset or grant an entitlement; this study imports the public frozen features.
- [Lee and Swaminathan, Price Momentum and Trading Volume (2000)](https://www.lsvasset.com/pdf/research-papers/Price-Momentum-Trad-Vol-2000.pdf) studies the interaction of stock momentum and volume. It motivates a separate activity/participation test; it does not establish that this particular HHI acceleration or ETF overlay predicts returns.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) provides public submissions/XBRL access for the planned fundamental features. Access to current company facts alone does not prove a point-in-time reconstruction.
