# Flow and concentration acceleration research — September 26, 2026

Decision: keep the current SOTA. The predeclared primary fails the research hurdle. A slower 20-session variant is worth observing, but its small historical edge is not sufficient for promotion. No trading configuration changed.

## Research question and interpretation

Does accelerating concentration of trading activity add information beyond the current SOTA's price/volume selection, frozen technical tree, relative momentum and adaptive trend layers?

The economic idea is plausible: persistent fund subscriptions can cause subsequent purchases and price pressure. It is not a mechanical rule. Secondary-market transactions exchange ownership, and high volume can accompany redemptions or selling. A slowing positive inflow is still a positive inflow. Concentration is relative: one asset's share can rise solely because activity elsewhere falls. A scalar HHI does not identify the asset to buy.

Hurst estimates persistence/scaling; it is neither a second derivative nor the direction of capital movement. Smoothing can create apparent persistence. We estimate Hurst on unsmoothed log prices only, as a separate optional gate on buys, with no claim that a 252-session estimate establishes long memory.

Relevant primary research and data documentation:

- [Coval and Stafford, Asset Fire Sales (and Purchases) in Equity Markets](https://www.nber.org/papers/w11357): flow-related forced transactions can produce price pressure. This does not establish that a daily ETF volume proxy predicts returns.
- [Lou, A Flow-Based Explanation for Return Predictability](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1468382): maps fund flows through underlying holdings to estimate demand shocks.
- [Lo, Long-term Memory in Stock Market Prices](https://www.nber.org/papers/w2984): short-range dependence can explain apparent long memory in returns. A raw Hurst threshold needs an ablation, not an assumption of predictive power.
- [Lillo and Farmer, The long memory of the efficient market](https://arxiv.org/abs/cond-mat/0311053): persistent order signs can coexist with offsetting liquidity adjustments. Order-flow persistence does not imply the same persistence in returns.
- [ICI, ETF primary/secondary-market discussion](https://www.ici.org/speeches-opinions/19_choi_ffi): secondary-market ETF turnover and primary-market net issuance measure different activity.

## Available data and unresolved requirements

The frozen study uses the existing 12-ETF SOTA universe: SPY, VGK, EWJ, EWH, EWY, MCHI, IEF, TLT, LQD, HYG, GLD and DBC. It tests rotation across country equities and asset classes. It does not test US industry-sector rotation: XLK/XLF/XLE/XLV histories were absent from the local store.

| Input | Local availability | Use and next source |
| --- | --- | --- |
| Daily adjusted OHLC and volume for SOTA ETFs | Available, 2012-01-05 through 2026-09-24 | Current proxy study; preserve provider, retrieval timestamp and snapshot hashes. Adjusted price × reported volume is an activity proxy, not certified contemporaneous dollar turnover. |
| USD/CNH history | Available with legacy lineage gaps | Identical FX for all trials, prior completed observation for fills; explicit maximum seven-day carry. No fabricated observations written to the store. Legacy CNY/proxy lineage remains a promotion blocker. |
| Daily ETF shares outstanding, NAV, AUM, creations/redemptions | No versioned historical dataset or adapter found | Highest-priority next input. Issuer fund data or licensed fund-flow feed; require original availability timestamps, splits, distributions, mergers, corrections and fund identifiers. |
| Daily historical ETF constituents and weights | Not available | Issuer archives or a licensed historical holdings feed; retain as-of and publication timestamps. Current holdings cannot be applied retrospectively. |
| Ownership concentration across institutional managers | Not available | SEC filings can support a slower signal, joined at filing acceptance/public availability time, not quarter end. |
| Intraday buyer/seller-initiated trades and quotes | No long, certified research history | Needed to separate aggressive buying from gross turnover; the recent delayed recorder pilot cannot supply historical order flow. |
| Historical sector ETF membership/classification | Not available | Freeze a survivorship-aware sector universe and inception/mapping histories before a sector-specific experiment. |

Practical source assessment as of September 26, 2026:

- [State Street's SPY fund page](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy) exposes NAV, AUM, shares outstanding, daily holdings and a NAV-history link. This demonstrates fields to capture; it does not certify a complete historical, point-in-time shares-outstanding archive for all twelve funds.
- [ICI weekly estimated ETF net issuance](https://www.ici.org/weekly-estimated-etf-net-issuance) supplies broad classifications with publication lag. Useful as an asset-class flow check, but it is neither daily nor ticker-level. Preserve the release timestamp and original revisions; do not assign a week's result to its first day.
- [LSEG Lipper fund performance/data](https://www.lseg.com/en/data-analytics/asset-management-solutions/lipper-fund-performance) describes daily/weekly/monthly estimated net flows. Access, historical vintages, classifications and redistribution rights would need verification; no entitlement or purchase is assumed.
- [SEC Form 13F FAQ](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f): quarterly reporting can arrive up to 45 days after period end. It is too slow to stand in for daily capital movement and does not disclose a complete short/cash portfolio.
- [SEC's February 2026 N-PORT update](https://www.sec.gov/newsroom/press-releases/2026-19-sec-proposes-amendments-reduce-burdens-reporting-fund-portfolio-holdings) and [compliance extension](https://www.sec.gov/files/rules/final/2026/ic-35963.pdf): do not assume the 2024 monthly-publication changes already apply. Compliance dates were extended to November 2027/May 2028. Use each filing's actual public availability and coverage, including amendments.

Suggested data contract for the stronger flow study: fund ID, ticker mapping interval, asset-class/sector mapping interval, observation date, publication timestamp, first-seen timestamp, revision ID, native currency, raw NAV, shares outstanding, AUM, split factor, distributions, gross creations/redemptions, source URI and content hash. Historical holdings additionally need security ID, share quantity, weight, classification and publication timestamp. Original snapshots must be immutable; as-of joins use availability timestamps.

With split-consistent shares, approximate net issuance as `NAV[t] * (shares[t] - shares[t-1])`, normalized by prior AUM. Validate this against reported creations/redemptions. AUM changes alone mix market returns and flows; a return-adjusted AUM residual also needs correct dividend/distribution conventions and merger treatment. These are estimates, not broker transaction-level money flow.

For a holdings signal, distinguish **constituent HHI** (concentration of securities inside a fund) from **owner HHI** (concentration of fund/security ownership across managers). Neither is automatically an inflow measure; valuation changes can change weights without a trade. Compare changes at fixed/reference prices where possible. Do not use signed net flows as a share denominator that can cross zero; use normalized net issuance or separate positive-inflow and outflow concentration.

## Frozen signal specification

All inputs precede the execution session. For asset `i`, daily adjusted trading activity is `D[i,t] = adjusted_close[i,t] * volume[i,t]`. Divide it by that asset's **prior** 63-session average to obtain abnormal activity `R[i,t]`. Then compute the cross-sectional share `s[i,t] = R[i,t] / sum_j R[j,t]`.

This equalizes persistent differences in ETF size and trading frequency; it measures a share of abnormal activity, not a dollar allocation share. The volume-only ablation removes prices. Another ablation uses the individual HHI contribution `s[i,t]^2`; the aggregate `sum_i s[i,t]^2` is retained as a diagnostic.

Smooth the share using a 10-session EMA. With lag `L=10`, calculate:

```
velocity[t]     = (C[t] - C[t-L]) / L
acceleration[t] = (C[t] - 2*C[t-L] + C[t-2L]) / L**2
z[t]            = acceleration[t] / std(acceleration[t-126:t])
```

The scale excludes the current derivative. The EMA has five spans of causal warmup before the noise interval. The score is not a Gaussian p-value; the threshold only creates a dead band.

- Primary entry/overweight: `z > 0.5`, positive concentration velocity, positive 20-session price momentum, and positive 20-session signed-volume balance (close-to-close tick proxy).
- Reduce/exit signal: `z < -0.5`, including when the concentration level is still rising.
- Tilt action: multiply SOTA-selected weights by `1 + 0.15 * signal`, then project to preserve SOTA gross exposure, no new assets, maximum 3 percentage point active change and 45% weight cap. An inherited base weight above the cap cannot be increased. Cash and asset-selection rules remain inherited from SOTA.
- Literal gate ablation: begin out of each asset, enter on positive signals, retain state in the dead band, exit to cash on negative signals. State changes only at monthly decisions; no redistribution of exited weights. It is a literal timing test, with an intentional exposure change.
- Hurst ablation: log-log regression of the standard deviation of unsmoothed 252-session log-price increments at lags 2/4/8/16/32. Require estimated H > 0.55 for entry; retain the same exit rule. Missing/degenerate estimates prevent entry.

The finite-difference derivative and signed-volume confirmation are approximations at daily/monthly resolution. The base experiment retains monthly rebalancing, so it does not test intramonth crossings. Faster scheduling would be a separate turnover/cost study.

## Experiment discipline and execution

The [predeclared protocol](../config/flow-concentration-research-v1.json) fixes one primary, all eleven challengers, four parameter neighbors, the matched cost/delay stresses and the decision rule before any result. No post-result parameter search is included. Raw acceleration, directional confirmation, Hurst, first derivative, HHI contribution, volume-only and literal exit gate are reported together. Threshold neighbors are 0.25 and 1.0; lag neighbors are 5 and 20 sessions.

Execution uses the existing pinned, offline native LEAN worker. SOTA and the primary recompute shared targets in the container; other cases replay frozen targets through native LEAN orders/fills/portfolio accounting. An independent Python engine must match decision sessions, symbols and whole-unit quantities exactly; weight tolerance is 1e-8 and cash/fees/NAV tolerance is 0.01 CNH. The engine image is recorded in the protocol and every receipt.

Economics: 1,000,000 CNH initial cash; provider-adjusted CNH units, monthly prior-close targets, next-session opening fills; 5bps base fee, no base slippage; whole units, instant settlement and no leverage. Stress cases apply 25bps fees plus 20bps slippage per traded side, or one extra execution session, to both SOTA and the primary. These economics are separate from legacy USD-cash artifacts and actual broker TWAP.

Data cleaning excludes only explicit non-session dates from internal ETF histories, with an exclusion record. All actual sessions require complete synchronized positive-volume bars. URTH has additional invalid early true-session observations; affected external benchmark windows are unavailable rather than filled. It does not enter the SOTA feature panel. The first two extraction attempts stopped on URTH coverage before any strategy run; the revised handling retains the failures and unavailable benchmark intervals.

Temporal interpretation: pre-2023 includes the SOTA tree's fit period; post-2023 has repeatedly influenced strategy selection. The extension after April 29, 2026 is newer than the old canonical artifact but is short and not independently certified as untouched. Calendar-year/stress-period slices and fixed-parameter temporal stability checks are reported, not mislabeled as newly trained walk-forward out-of-sample performance.

Report CAGR, zero-risk-free Sharpe, drawdown, turnover, fees, exposure/cash and concentration; all neighbors and cost/delay cases; SPY buy-and-hold and valid URTH windows. Paired circular 63-session block bootstrap uses 2,000 replicates and a fixed seed. Max-t one-sided family adjustment covers all eleven challengers; it cannot erase historical SOTA selection. Bootstrap intervals describe annualized arithmetic daily excess return, not CAGR. Research retention requires the preregistered primary to improve in multiple intervals and stresses, rather than simply choosing the best cell.

## Results

The 17 predeclared native LEAN runs completed successfully over **3,393 sessions, April 1, 2013–September 24, 2026**. Every run passed the unchanged parity tolerances and was appended to the research-only PostgreSQL registry. Two separately recorded post-hoc implementation stresses test the fixed 20-session neighbor; they are not new holdout evidence.

| Strategy | CAGR | Sharpe, Rf=0 | Max drawdown | Post-2023 CAGR |
| --- | ---: | ---: | ---: | ---: |
| Current SOTA, fresh LEAN comparison | 9.11% | 0.924 | -14.16% | 14.72% |
| Primary: confirmed concentration acceleration, lag 10 | 9.06% | 0.919 | -13.84% | 14.44% |
| Acceleration with Hurst filter | 9.11% | 0.921 | -14.22% | 14.62% |
| Best neighbor: concentration acceleration, lag 20 | 9.28% | 0.935 | -13.39% | 15.13% |
| Literal threshold entry/exit gate | 2.90% | 0.590 | -10.45% | 2.95% |
| Risk parity | 5.12% | 0.646 | -16.81% | 8.12% |

The primary reduced annual return by 0.05 percentage points over the full period and 0.28 points after 2023. It finished with 0.62% less wealth than SOTA. Its modest drawdown improvement did not compensate for the return/Sharpe deterioration. It also lost in the post-April-2026 extension. Under higher costs its CAGR was 6.42% versus SOTA's 6.53%; under one-session delay it was 9.12% versus 9.21%. All five predeclared retention checks failed.

Hurst did not help. The first-derivative control improved the full period by 0.11 annual percentage points but lost after 2023. Volume-only and HHI-contribution versions also failed to improve consistently. The literal exit gate averaged **64.8% cash**, compared with 2.6% for SOTA: lower drawdown largely accompanies substantially lower exposure, not a better risk-adjusted result. Cash earns zero in this declared scenario; no interest income is modeled, which matters much more for the cash-heavy gate. Annual traded notional/NAV rose from 6.04x for SOTA to 6.17x for the primary (the sum of both buy and sell notionals, not half-turnover).

The **lag-20 neighbor** gained 0.17 annual percentage points overall and 0.41 points after 2023, with 2.06% greater terminal wealth across the full history. This is the best of eleven variants, selected after observing their results. Its 95% block-bootstrap interval for annual arithmetic excess return is **[-0.06%, +0.39%]** over the full period; the multiple-testing-adjusted one-sided p-value is **0.354**. Post-2023 the adjusted p-value is **0.132**, despite an attractive unadjusted result. None of the eleven challengers clears a 5% family-adjusted threshold. The primary interval is [-0.25%, +0.15%]. These diagnostics do not prove zero effect, but they do not establish a reliable improvement.

Only two of the four parameter neighbors show positive full-period and post-2023 relative wealth; the threshold neighbors are weaker after 2023. This is insufficient parameter stability for replacement. Retain lag 20 as an observation candidate only; do not relabel it as the predeclared winner or restart parameter searches on these same periods.

The two **post-hoc lag-20 follow-ups** also passed native LEAN/Python parity, bringing the total to **19 native runs**. At 25bps fees plus 20bps slippage it returned 6.61% annually versus the matched SOTA's 6.53%; with one-session delay it returned 9.30% versus 9.21%. Its small edge survives these implementation stresses but roughly halves. This is useful observation evidence, not a new statistical holdout. The original protocol and 17-run analysis remain unchanged; follow-up plans, outputs and metrics are separately retained under `followups/lag_20/`.

SPY buy-and-hold context returned 15.07% annually with a -32.78% drawdown over the full period. In the reused post-2023 window URTH returned 19.04% with a -16.32% drawdown, versus SOTA's 14.72% and -8.48%. These external references carry substantially different risk and are separately labeled Python buy-and-hold calculations, not native LEAN strategy runs. URTH's full-period comparison is unavailable because 36 early actual sessions had invalid observations.

The frozen data contains 3,701 sessions per SOTA ETF including warmup. Excluded 24 non-session internal rows (May 25 and June 19, 2026 across twelve ETFs); preserved 434 carried FX dates and their original observations. No prices or flows were synthesized. Missing historical vintages, mixed legacy source lineage, adjusted-price/volume semantics and fixed-universe survivorship still prevent a production certification. Monthly fills do not establish intraday liquidity, spread/market-impact capacity or TWAP parity. Historical order-book/quote data and actual paper cost evidence remain missing.

Replayable evidence: `D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/`. `report.md` contains every trial, year, stress window, external benchmark and uncertainty estimate; `analysis.json` includes all metrics and exposure statistics; `signal_diagnostics.json` has 1,944 asset-month rows. `comparison.png/.svg` and `ablations.png/.svg` are the inspected figures. Each run preserves its manifest, spec, native fills, NAV, Python reference, parity and immutable receipt. No production strategy, approval, live/paper policy or broker order was changed.

## Next research step

Keep SOTA and freeze the lag-20 observation candidate. The most useful next evidence is an untouched prospective comparison plus a historical **net-issuance** dataset: daily shares outstanding, NAV/AUM, corporate actions and original publication timestamps across the same universe. If sector rotation is the target, add survivorship-aware sector ETF history and classifications. Test true flow level and deceleration directly against this activity proxy, with a predeclared holdout and the same cost/exposure controls. Holdings/13F/N-PORT are slower, separate factors; do not backdate them or treat them as daily flows.

## Replay

The optional `research` dependency group supplies NumPy for statistical analysis and Matplotlib for figures. The signal and native LEAN runtime use the existing standard-library/Pydantic dependencies. This session installed plotting dependencies in a separate D: research directory, leaving the running application environment unchanged.

```powershell
.\.venv\Scripts\python.exe scripts/run_flow_concentration_research.py --root D:/systematic_trading_data/lean/research/<new-study-directory>
.\.venv\Scripts\python.exe scripts/analyze_flow_concentration_research.py --root D:/systematic_trading_data/lean/research/<new-study-directory>
.\.venv\Scripts\python.exe scripts/run_flow_concentration_followup.py --root D:/systematic_trading_data/lean/research/<new-study-directory> --candidate lag_20
```

`--resume` uses the existing frozen protocol/snapshot and skips successful immutable runs. Failed native runs require investigation and a new study directory. Frozen bundles include actual source contents/hashes as well as the Git commit, so preexisting working-tree edits cannot be hidden by a commit identifier. The current SOTA definition, approvals, broker routing and live-disabled policy are unchanged.
