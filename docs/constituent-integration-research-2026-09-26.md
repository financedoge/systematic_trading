# Earlier constituent information in the ETF strategy

## Result: earlier placement did not improve this strategy

All **19 native LEAN runs passed**. Moving the positive-sample-IR signals upstream did not establish additional return, Sharpe or information ratio. Retain SOTA. This conclusion applies to the tested, bounded implementations and available public stock proxy; it does not establish that constituent information is generally useless.

The comparable window below is **2023-01-01–2026-09-24**, when the stock coverage first becomes usable. Returns are net CNH CAGR; Sharpe uses a zero hurdle, and IR is annualized daily active return divided by tracking error against unchanged SOTA. A dash means no active return, so IR is undefined.

| Variant | CAGR | Sharpe | IR vs SOTA | Changed monthly decisions |
| --- | ---: | ---: | ---: | ---: |
| SOTA | 14.72% | 1.292 | — | 0 |
| Signed activity, late allocation | 14.77% | 1.299 | +0.262 | 26 |
| Signed activity, earlier allocation | 14.77% | 1.299 | +0.262 | 26 |
| Signed activity, pool selection | 14.72% | 1.292 | — | 0 |
| Breadth, pool selection | 14.69% | 1.291 | -0.550 | 1 |
| Constituents + price, tree forecast | 14.63% | 1.288 | -0.596 | 19 |
| Price-only tree forecast control | 14.65% | 1.290 | -0.472 | 19 |
| Price-only earlier allocation control | 14.79% | 1.301 | +0.301 | 34 |

Earlier signed allocation differs from the late version by only **-0.00064 percentage points of CAGR**. Its direct IR against the late version is -0.061, and against the earlier price-only control is -0.127. Earlier breadth is also effectively unchanged over this window: IR +0.030 versus +0.026 late. Positive IR versus SOTA alone is insufficient evidence that the stock information adds something beyond ETF prices or that the new placement helps.

Selection signed activity and its half-strength neighbor produce exactly SOTA's weights, fills and NAV. Among 44 qualified decisions, SPY is already held on 39; on the five remaining dates the signed score is negative twice and neutral three times, never a positive entry signal. Changing scores within the selected basket does not change this pool filter's allocation. Breadth changes one decision, June 2, 2025, and its bounded blend retains seven names; this loses return. No variant introduces a new SPY selection. The matched selection cost/delay stresses are therefore identical to SOTA, not evidence of robust new alpha.

The trees do use the stock features: the 2025 fit splits on breadth, and the 2026 fit splits first on signed activity and then breadth. These interactions change 19 monthly allocations, but do not pay off. Over **2025-01-01–2026-09-24**, which includes the first eligible model decision on February 3, SOTA earns **19.03% / Sharpe 1.474**, the joint tree **18.84% / 1.467**, and the price-only tree **18.89% / 1.471**. Joint-tree IR is **-0.876 versus SOTA** and **-0.851 versus the price-only tree**. A split appearing in a fitted tree is not evidence of incremental investment value.

The 63-session paired interval for the tree's additional stock information spans -0.121 to +0.022 annual active-return percentage points in the 2025-onward window. The earlier-vs-late allocation intervals also cross zero. The late signed signal does beat the price-only late signal in this shorter window, but its own SOTA-relative IR is -0.059; this subperiod reversal does not establish a benefit from deeper integration. The full 2019-10-01–2026-09-24 tree CAGR/Sharpe is 8.48%/0.782 versus SOTA 8.52%/0.784, with neutral fallback before sufficient data/model availability.

Artifacts include `results.png`, `trees.png`, `report.md`, every annual/stress metric, paired block intervals, exposure audit, and immutable native runs under the frozen root below. The charts were visually inspected. The current study adds **3,592 feature records, four models, 43 separate training labels and 252 result/contrast records** to versioned ClickHouse sources; all 19 native receipts are registered in PostgreSQL. Existing downloaded stock histories remain archived. Validation: **599 tests passed, 51 optional integrations skipped**; focused 55 passed/1 skipped, Ruff and whitespace checks clean. SOTA and all three late-reference economic hashes exactly reproduce the preceding study.

Next evidence should be actual ETF-specific membership and longer completed histories, followed by a declared cross-ETF constituent ranking test and a prospective period. A broader panel would test selection where constituent information differs across competing ETFs; a deeper tree on only 23/35 monthly training examples is not supported by this experiment. No production strategy or trading-policy change is made.

## Question and design

The preceding late-overlay test found small positive sample IRs for stock breadth and signed activity. That does not establish either as an independent alpha, but a late tilt may conceal useful interactions: selection can admit an ETF absent from the basket, an earlier tilt passes through downstream risk layers, and a tree can condition the signal on price trends. This study tests those mechanisms directly instead of increasing the position size of the prior winner.

This is an explicitly **selected follow-up on previously inspected history**. The two stock signals were chosen because of the preceding results. Freezing the follow-up and training chronologically prevents certain leakage errors; it cannot turn the historical period into an untouched holdout or remove prior selection bias. The user authorized research, not promotion.

Protocol: `config/constituent-integration-v1.json`. Frozen root: `D:/systematic_trading_data/lean/research/constituent-integration-20260926-v1/`. The source ETF/FX snapshot and stock features are exactly those of the preceding study, with no new download or relaxed coverage. Monthly ITOT stocks remain a broad U.S. proxy for SPY, not its exact holdings or the constituents of foreign ETFs. Actual historical source availability remains uncertified.

## Three earlier integration points

| Stage | Implementation | Matched control |
| --- | --- | --- |
| Earlier allocation | Apply the same 15%-relative, maximum 3pp SPY tilt immediately after the pool filter, before the existing tree, relative-momentum and adaptive layers. | The same step using SPY's price-only signal. Compare also with the unchanged late tilt. |
| Pool selection | Add `0.15 × score` to SPY's existing price/volume pool score before top-six ranking. Keep positive 252-session momentum eligibility and all other scores unchanged. | Price-only score at the same point; a 0.075 boost is the sole strength neighbor. |
| Tree forecast | Keep the frozen pre-2023 tree and add a small learned correction to its SPY forecast before ranking forecasts across ETFs. The correction tree can use price trend, the original forecast, breadth and signed activity together. | Same training dates, target, tree size and shrinkage, using only the price features and original forecast. |

All earlier candidates are normalized to SOTA's target gross exposure, then blended toward SOTA so no asset changes by more than **3 percentage points**, no negative weights appear and no target rises above 45%. Inherited weights above 45% cannot increase. This isolates information placement from simply taking more total risk. Selection may introduce up to 3pp of SPY where SOTA holds none; the blend can retain members of both baskets, including seven ETFs. It is a risk-constrained combination of selections, not an unrestricted hard replacement of the six-ETF basket.

Late signed-activity, breadth and price-only references are rerun unchanged. Nineteen native LEAN runs comprise SOTA, twelve challenger/control specifications, and two matched three-strategy stress groups (SOTA, selection signed, selection price). Costs are 5bp in the base case, 25bp fees plus 20bp slippage in the cost stress; execution delay adds one session. The primary is **selection signed activity**, chosen before the follow-up outputs, not the best eventual result. SOTA, primary selection and both tree variants recompute targets inside LEAN; the remaining variants replay frozen targets through native LEAN transactions/accounting.

## Small chronological tree experiment

The qualified stock history starts January 17, 2023. It cannot be inserted into the old tree's pre-2023 training window. A full retrain pretending those features existed would be invalid. Instead this study fits a shallow SPY residual tree using completed monthly observations:

- Inputs for both models: SPY 63-session momentum, 126-session momentum and the frozen tree's forecast. The augmented model additionally receives continuous stock breadth and signed activity; the control differs only by omitting these two inputs.
- Target: SPY's next-rebalance close-to-close USD return minus the equally weighted return of the twelve ETF assets, minus SPY's original tree forecast. This is a forecasting residual, not a fitted portfolio Sharpe or a realized trade-profit label.
- Annual expanding fit as of January 1; require every label end and feature date to precede the fit date. Eighteen completed monthly samples are the minimum, depth is at most 2, minimum leaf size 6. These settings and the sample frequency were fixed before testing.
- The 2025 model has 23 completed months; the 2026 model has 35. Both models use exactly the same qualified sample rows. The small sample is a material limitation even with shallow trees.
- Add 25% of the residual forecast, capped at +/-1 percentage point, to the existing SPY forecast inside the tree overlay. Existing cross-ETF ranking and sizing then execute normally, followed by the common final risk bounds.
- The runtime adapter selects models with `fit_as_of <= prior completed session`. January 1 fits therefore first enter this monthly adapter in **February**, not January. Their model records carry fit date, last training-label date, training dates and node structure. Future models cannot influence earlier decisions. Dates before model availability use unchanged SOTA.

Runtime feature bundles contain dated models and historical features, **no training outcome records**. Training labels are frozen separately in `training_records.json` and archived under their own ClickHouse family. Historical availability timestamps remain null; model dates describe the reconstruction, not a claim that these models were actually fitted in 2025/2026.

## Evaluation and interpretation

The report contains continuous net CNH returns and matched SOTA-relative CAGR, Sharpe, IR, drawdown, fees, turnover and cash. It compares each earlier stage with both the corresponding late overlay and its price-only control. For the learned correction, the 2025-onward period is shown separately, because earlier years contain no active fitted constituent model. Pre-2023 equality is a neutral-fallback check, not crash robustness.

The exposure audit checks every target's active bound and total target exposure, counts changed decisions and new SPY selections, and reconstructs average actual SPY/gross weights from native fills. A large IR with unchanged membership must not be described as successful ETF selection. A price-only tree's advantage must not be attributed to stock information.

Paired 63-/126-session circular block intervals and centered max-t comparisons cover the twelve current challenger/control variants. Eight direct earlier-vs-late and stock-vs-price contrasts have a separate 63-session family audit. These estimates are exploratory under the reused sample and changing market regimes; they do not account for the entire historical research search, missing delistings or unknown vendor vintages. No direction reversal, parameter grid or fit to the whole evaluation period is used.

High-cost and delay runs cover the predeclared selection primary and its price control. A promising tree result would require its own cost/delay check and fresh data before inclusion. Training rows, fitted models, failures and unfavorable results are retained, rather than only a winning specification. Production SOTA, scheduling, approval and broker checks remain unchanged.

## Reproduction and storage

```powershell
.venv/Scripts/python.exe scripts/prepare_constituent_integration.py --root D:/systematic_trading_data/lean/research/NEW-INTEGRATION-STUDY
.venv/Scripts/python.exe scripts/run_constituent_research.py --root D:/systematic_trading_data/lean/research/NEW-INTEGRATION-STUDY --resume
.venv/Scripts/python.exe scripts/analyze_constituent_integration.py --root D:/systematic_trading_data/lean/research/NEW-INTEGRATION-STUDY
```

Use a new root for preparation. `input_manifest.json` verifies the frozen protocol, preparation/feature code, features, models and labels. Each native bundle freezes its own complete strategy source and inputs; completed native runs are immutable. The native engine is the same pinned offline LEAN image used in prior studies. Archived old SOTA/late economic hashes must match the new references exactly before results are accepted.

ClickHouse source `constituent-research/constituent-integration-20260926-v1/features` holds 3,592 feature observations, four annual fitted-model records and 43 explicitly marked training-label records, with protocol/model documents. The adjacent `/results` source holds 228 period metrics, 24 direct contrasts, exposure audit and report documents. Publication verifies exact payload hashes. Native successful receipts are registered in PostgreSQL `ops.lean_research_runs`, never as trading proposals. Read-only SQL confirms all family counts and null historical availability, all 19 registry receipt hashes match disk, and repeat analysis publication writes no new version. Verification: `var/research/constituent-integration-verification.json`.

## Method references

- [QuantConnect walk-forward optimization](https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization) describes training on trailing data and evaluating later behavior. This study uses fixed annual fits and no optimization grid.
- [Scikit-learn time-series splits](https://scikit-learn.org/1.5/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) explains why time-ordered evaluation differs from ordinary shuffled folds. Here, monthly labels whose end dates have not arrived are excluded explicitly; the repository's deterministic regression-tree implementation is used, not scikit-learn.
- The public holdings, adjustment and point-in-time limitations and original signal formulas are detailed in [the preceding constituent study](constituent-signals-research-2026-09-26.md).
