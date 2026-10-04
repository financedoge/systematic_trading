# Improving momentum in the monitored strategies

**Status: authorized and tested on 2026-10-01; results await discussion.**  
The user approved the revised direction and requested all available cores for backtesting, then asked us to obtain historical USD-index data. The defaults below were frozen before performance review. The completed round contains 102 Python replays and 36 native parity checks, including the USD ablation on published ALFRED vintages. No promotion followed. [Results](momentum-results-2026-10-01.md) · [Frozen registration](momentum-experiments-2026-10-01/protocol.json) · [Reading notes](momentum-literature-notes-2026-10-01.md) · [Reference library](references/README.md)

## Recommendation

Study four questions: **short versus older momentum; dynamic horizon selection; symmetric entry/exit timing with variable holdings; and USD information that predicts relative ETF returns.** Use fixed rules and simple controls before combining the ideas.

The previous six-comparison proposal is superseded. The revised design separates signal horizon, decision frequency, holding breadth and regime selection so we can identify why performance changes. Proposed constants below are defaults for review, not empirically selected values. No finding currently establishes which direction will win.

The user has deferred the inaccessible broker reports and unnamed citations. They remain documented gaps and are excluded from the rationale; obtaining them is no longer a prerequisite.

## 1. What we currently monitor

The source of truth is [strategy-monitoring.json](D:/projects/systematic_trading/config/strategy-monitoring.json) and the definitions in [strategy_catalog.py](D:/projects/systematic_trading/src/systematic_trading/research/strategy_catalog.py:79). Snapshot reviewed on 2026-10-01:

| Strategy | Allocation flow | Research comparison |
|---|---|---|
| `sota_price_volume_technical_tree_relative_adaptive_top6` | Inverse-volatility base → price/volume Top-6 pool → technical tree tilt → 20/60-session relative momentum → adaptive trend scaling | Every candidate versus this complete unchanged strategy |
| `research_etf_activity_lag20_v1` | SOTA flow → lag-20 ETF activity overlay | Candidate versus the unchanged activity strategy |
| `research_rolling_xgboost_1y_lag20_v1` | SOTA flow with monthly rolling one-year XGBoost replacing the tree → unchanged activity overlay | Candidate versus the unchanged rolling strategy |

Common universe: **SPY, VGK, EWJ, EWH, EWY, MCHI, IEF, TLT, LQD, HYG, GLD, DBC**. These are US-listed funds spanning countries and asset classes. They are not twelve independent stock-market experiments.

The pool currently combines ranks of 63/126/252-session momentum with weights 0.20/0.35/0.45, then combines that trend category with volume measures at 75%/25%. It requires positive 252-session momentum and at least four eligible assets before applying Top-6 selection. **If fewer than four qualify, the current pool overlay is neutral; it does not automatically liquidate into cash.** This fallback must be reproduced explicitly.

The relative-momentum layer ranks a 45%/55% mixture of 20/60-session returns. The feature library already contains continuous momentum and moving-average deviation features alongside binary above-average indicators. There is no basis for a blanket conversion of all binary logic. See [trend.py](D:/projects/systematic_trading/src/systematic_trading/signals/trend.py:362) and [library.py](D:/projects/systematic_trading/src/systematic_trading/signals/library.py:31).

The monitored configuration uses monthly decisions, next-session open fills, simulated CNH accounting, 5 bp transaction costs and zero modeled slippage. Its baseline trees are causal annual models before 2023 and frozen thereafter; the rolling challenger refits every month using one calendar year. A year of ETF-month rows still contains only about twelve calendar decision periods, with strong shared exposures.

Existing evidence also limits expectations: the activity lag-20 study's family-adjusted result was about p=0.574; the rolling model's improvement against its matched frozen family was about p=0.529. These support continued observation, not a claim of established incremental alpha. See [activity tracking](D:/projects/systematic_trading/docs/etf-activity-lag20-tracking.md) and [rolling tracking](D:/projects/systematic_trading/docs/rolling-xgboost-lag20-tracking.md).

## 2. What the literature supports testing

| Question | Firsthand evidence | Implication for this project |
|---|---|---|
| Which momentum horizon helps? | M01 separates formation, gap and holding periods; M02 finds short-horizon reversal in stocks. M01's skip is one week. | Compare 1/2-week continuation against older 2/3-month segments, then static and dynamic mixtures. Preserve the sign of losing results. |
| Can asymmetric trading improve outcomes? | F04 studies stricter entry than continued-holding rules. | Compare both entry/exit directions and an immediate-action control, permitting six or more holdings. |
| Can market state select the horizon? | R24 links momentum crash behavior to stress/rebounds. | Treat trend and skewness separately, test both mappings, and compare dynamic mixtures with the same fixed signals. |
| Should all signs become continuous features? | R12 uses a sign-based factor signal; R07/R23 show nonlinear prediction in much larger datasets. | Treat predictive representation and allocation gates separately. |
| Should we add volatility targeting? | F05 and R09 find benefits in particular constructions; R10 finds mixed broad results with stronger momentum cases; R24 highlights crash mechanisms. | Distinguish inverse variance, inverse volatility, asset weights and portfolio exposure. Assess the incremental effect over our existing risk layers. |
| Should we concentrate or neutralize more? | R11/R21 document ex-post stock wealth concentration; R12 links momentum and common factors. | Diagnose concentration and exposures; neither result supplies an optimal ETF breadth or a universal residualization rule. |
| How strong is another successful backtest? | R01/R02/F01/F02 address selection; R03/R29/R30 distinguish reused samples, researcher choices and reproducibility. | Freeze a finite trial family, preserve every outcome and seek genuinely new forward evidence. |

Paper IDs link to full citations, original PDFs, inspected pages and version limitations in the [reading notes](momentum-literature-notes-2026-10-01.md). Some downloaded copies are working papers. Before implementation, inspect the complete relevant methods and any final-version differences for the shortlisted methods.

## 3. Prerequisites after we agree on the plan

### A. Freeze the baseline and comparison contract

Create a dated specification containing the exact universe, strategy definitions, overlay order, model hashes, fit/label cutoffs, rebalance clock, fill timing, fees, units, cash treatment, constraints, fallback behavior, code revision and environment. Record all three parent strategies and any prior trials recovered from existing reports/configurations.

Reproduce the app's current complete baseline and its Python/LEAN parity before interpreting candidate differences. A discrepancy becomes a separately documented correction; do not quietly adopt a changed baseline because it improves the candidate comparison.

Historical baseline reproduction is a prerequisite to be performed after approval. This literature session did not run it or verify a new market-data batch.

### B. Pin admissible inputs

- Use **published, audited continuous histories**, with an explicit publication batch, verified hashes and per-instrument/date coverage. Select the actual batch when research starts; “latest” is not a reproducible input identifier.
- Use dividend/split-adjusted prices for return features and return research. Identify audited raw prices and raw volume separately for traded-activity features. A volume-derived direction or turnover proxy must disclose its price/volume basis.
- The existing activity overlay is a proxy derived from price and volume; it is not measured net investor flow. Do not silently change its basis during a momentum comparison. If the existing basis cannot meet the supported contract, handle that as a separately reviewed baseline/data correction first.
- Missing observations remain missing. Define an admissible common comparison sample and a fail-closed research eligibility rule; report exclusions and their effect on coverage. Never fill from provider archives, splice instruments, or substitute an online series.
- Audited provider-adjusted histories do not establish historical publication vintages. Distinguish a causal calculation from a fully point-in-time input claim.
- Use USD total returns for the primary signal study, with a matched parent recalculated in the same USD contract. Report the bridge from this USD research baseline to the existing CNH/whole-unit simulation; do not compare unlike accounting conventions as if the difference were alpha. The user accepts unhedged USD/CNH exposure. Preserve CNH reporting and its explicit FX attribution; legacy FX through 2026-09-24 remains uncertified. Accepting exposure does not certify that historical series.
- A broad-dollar predictor is a separate input from USD/CNH accounting. It needs its own audited publication, availability timestamps, vintage policy and coverage before an experiment. Same-day economic dates do not imply same-day publication.
- Historical constituent/holdings coverage is sparse. Do not add a constituent-flow or holdings-based signal to a ten-year comparison by treating unsupported early observations as neutral evidence.

Downloaded papers are literature sources only. Any new factor, option, holdings or price dataset would enter through the project's audit and publication process before use.

## 4. Symmetric momentum and dynamic horizon selection

### A. Fixed horizons establish the comparison

For dividend/split-adjusted USD prices available at decision close `t`, define the following. One week is five trading sessions; two weeks is ten. `rank()` uses the existing tied-rank transform to [-1, 1] on the same supported cross-section.

| ID | Signal | Purpose |
|---|---|---|
| A1 | `rank(P[t]/P[t-5] - 1)` | 1-week continuation |
| A2 | `rank(P[t]/P[t-10] - 1)` | 2-week continuation |
| A3 | `rank(P[t]/P[t-21] - 1)` | 1-month bridge/control |
| A4 | `rank(P[t-21]/P[t-42] - 1)` | The older part of a 2-month lookback |
| A5 | `rank(P[t-21]/P[t-63] - 1)` | The older part of a 3-month lookback |
| A6 | `S = (A1 + A2)/2` | Fixed short-horizon blend |
| A7 | `L = (A4 + A5)/2` | Fixed older-horizon blend |
| A8 | `(S + L)/2` | Fixed blend that dynamic policies must improve |

The older windows end 21 sessions ago: A4 spans **21 older sessions**, and A5 spans **42 older sessions**. They exclude all returns within the most recent month. They do not mean full 42/63-session windows shifted back another month; that would be a different registered specification.

Each signal replaces only the pool's trend category. Preserve the 75% trend/25% volume mixture, unskipped positive-252-session eligibility gate, allocation layers, constraints and fallback. Keep the current full strategy as the parent. Keeping its 20/60 tilt initially isolates the pool change, but report redundancy with that layer. A later tilt ablation is a separate trial.

All eight use the same continuation direction. A negative result remains negative; a reversal strategy requires its own registered test. Report signed IC, paired net returns, membership changes, turnover and contributions. Neither taking absolute IC nor flipping signs after inspection establishes success.

### B. Dynamic allocation between S and L

Test `trend_score(t) = a(t)*S(t) + (1-a(t))*L(t)`. This adjusts the effective lookback while using the same two signals. It avoids independently optimizing a new window at every date.

**Bull/bear trend and right/left skew are separate variables.** Trend measures direction; skewness measures asymmetry around the mean. Adding a constant to every daily return changes the mean without changing skewness. An upward-trending market can have a left tail, and a falling market can have large positive rebound outliers. The user-proposed connection is a hypothesis to test, not a label definition.

Proposed causal state inputs:

- A fixed equity basket of SPY, VGK, EWJ, EWH, EWY and MCHI, with the daily return equal to the unweighted mean of their supported USD total returns. This is a fixed signal index, independent of the strategy's selected holdings; it is not an investable benchmark with assumed zero trading costs.
- **Trend:** sign of its trailing 126-session compounded return. Call the states up/down to avoid implying a hindsight bull/bear chronology.
- **Skew:** adjusted Fisher–Pearson sample skewness of its trailing 126 daily returns. Proposed thresholds: above +0.25 right-skew, below -0.25 left-skew, otherwise neutral. Require complete supported observations and nonzero variance; missing state inputs make the candidate unavailable for the paired test, rather than creating a synthetic state.
- Use only information available at the decision timestamp. No future peak/trough labels or full-sample quantiles. An equity state may be a poor guide for bonds or commodities; show results by asset sleeve and state.

| ID | `a(t)` in positive state | `a(t)` in negative state | Neutral |
|---|---:|---:|---:|
| B1: trend mapping | 0.75 in up-trend | 0.25 in down-trend | 0.50 |
| B2: mirrored trend mapping | 0.25 in up-trend | 0.75 in down-trend | 0.50 |
| B3: skew mapping | 0.75 with right-skew | 0.25 with left-skew | 0.50 |
| B4: mirrored skew mapping | 0.25 with right-skew | 0.75 with left-skew | 0.50 |

Compare each with **S alone, L alone and the fixed 50/50 blend**, including switching costs. Also report the trend-by-skew cells and transitions, with observation counts; these are diagnostics, not extra retrospectively selected strategies. A dynamic rule that only beats a poor parent but loses to a fixed horizon has not justified its complexity.

**Later option:** if there is credible conditional evidence, compare one regularized joint trend/skew gate against these simple policies. Fit its mapping only on completed past labels, shrink toward 50/50, and evaluate through chronological refits. The target is the subsequent short-minus-long strategy outcome, not contemporaneous market direction. A minimum training history and state-coverage rule must be fixed before fitting; sparse cells must not become unconstrained regime parameters. This learned gate is outside the initial recipe budget.

## 5. Variable holdings and both entry/exit directions

Six becomes a **normal minimum**, with room for 7, 8 or more up to the twelve-asset universe. It remains subordinate to data eligibility, position limits and the existing fallback. A floor cannot require buying an unsupported or otherwise prohibited asset.

To separate breadth from timing, use one common desired-membership rule. With the unchanged pool score `q` on [-1, 1], let `q6(t)` be the sixth-highest eligible score. Define `D(t)` as all eligible assets with `q_i(t) >= q6(t) - 0.10`. This admits close contenders beyond sixth place without setting a hard Top-8 ceiling. The score margin is a proposed default, not a tuned value. It can retain too many nearly tied assets; report that behavior.

Test three policies with this same desired set:

| ID | Entry condition | Exit condition | Interpretation |
|---|---|---|---|
| C0 | In D at the decision | Outside D at the decision | Immediate entry and exit; breadth control |
| C1 | In D at the decision | Outside D for five consecutive completed sessions | Add faster, drop slower |
| C2 | In D for five consecutive completed sessions | Outside D at the decision | Add slower, drop faster |

Counters use completed daily signals, but membership/orders change only at the chosen rebalance dates. Holding state is the strategy's previous selected membership, independent of broker holdings. All policies start with the same eligible Top-6 seed; the initial seed exception is reported. Hard eligibility/risk exits override waiting periods.

After applying each rule, if at least six eligible assets exist but fewer than six are selected, fill to six from the best eligible nonmembers and flag every **floor override**. A floor may force C2 to admit an asset before its five-session confirmation. Report the unconstrained indicated count, final count, forced entries and how often the floor removes the intended asymmetry. Never count those trades as confirmed entries. If only four/five qualify, select the qualifying set; with fewer than four, preserve the parent's existing neutral pool fallback and reset policy state.

Use the same inverse-volatility sizing, gross allocation, cash reserve and caps for each policy, applied to its selected set. Do not add equal-weighting or exposure timing in this comparison. Compare C1/C2 with C0 to isolate timing and C0 with the original fixed-Top-6 parent to isolate breadth. Track nominal and effective holding counts, weight dilution, trade sizes and costs after every downstream layer. Staying in a pool does not imply an unchanged weight or zero trading.

Report selected membership, positive target weights and actually held assets separately. Whole-unit rounding, capital constraints or later risk controls can prevent a selected asset from becoming a held position; a nominal minimum must not conceal this difference.

## 6. Signal horizon and rebalance frequency

A one-week signal assessed only through monthly trades may decay before the next rebalance. Keep the monthly comparisons for continuity, then run a prespecified **weekly** comparison using the last trading-session close of each week and next-session open execution.

Weekly candidates: A1, A2, A7, A8 and C0/C1/C2. Use a weekly version of the unchanged parent as their control. Keep the learned-model fitting schedule monthly and use only the latest already-fitted model; a faster trading clock must not accidentally add refits or new labels. Selection confirmation still means one/five trading sessions in both schedules.

Report both candidate-minus-parent within each clock and the difference between those increments across clocks. Thus we can distinguish a useful short signal from a benefit or cost of simply trading the whole portfolio more frequently. All weekly recipes incur their actual greater or lower trade costs. Daily trading and weekly dynamic-gate variants would expand the trial family and are deferred.

## 7. A predictive USD feature with unhedged USD/CNH exposure

### The question

Can information about broad USD strength available today improve **subsequent relative USD returns of the ETFs**, beyond their existing price signals? The objective is better ETF allocation. The user accepts USD/CNH exposure; this proposal does not add an FX hedge or change the reporting currency.

USD listing/quotation does not imply a common economic USD exposure. The foreign-equity ETFs hold non-US assets, while bonds, gold and commodity futures can respond through different channels. A single USD number added identically to every ETF score leaves cross-sectional ranks unchanged. A useful ranking feature therefore needs asset-specific effects or interactions.

New firsthand background: Gelos, Patelli and Shim (BIS, September 2024) find a role for dollar strength in EME capital flows, but their principal regressions include **same-period** dollar changes. That supports an economic mechanism, not a demonstrated next-month ETF predictor. Hofmann, Park and Tejada (BIS, March 2023) document a period when commodities and the dollar rose together, cautioning against a permanent rule that a strong dollar must hurt every commodity exposure. See [supplemental notes and PDFs](references/supplemental/README.md).

### Proposed input and availability

Start with the Federal Reserve nominal broad dollar index as one candidate input, with positive changes denoting USD appreciation. Use its lagged 21- and 63-observation changes; do not run a search across many dollar proxies. A USD ETF is a different instrument with fees/carry/roll effects and cannot silently substitute for the index.

The Fed's H.10 release publishes prior-week daily observations, and dollar-index history can change when weights are revised. The input must therefore join by **release availability**, using original releases/vintages where supported, rather than treat a current downloaded history as contemporaneously known. Reading the latest available released value is not permission to create filled daily observations; retain its observation date, release timestamp and age. Missing/too-old evidence makes this study unavailable. [H.10 release documentation](https://www.federalreserve.gov/releases/h10/about.htm), [index methodology and revisions](https://www.federalreserve.gov/releases/h10/Summary/).

No dollar-index prices were downloaded as research inputs in this planning session. Ingestion, audit, publication and a feature-age limit would be a prerequisite for this block. USD/CNH accounting evidence is not a substitute for the broad-dollar feature's provenance.

### Matched predictive test

Propose two small, regularized models: **U0**, a price-only control using the fixed S/L signals and trailing volatility; **U1**, the same model plus the two USD changes with asset-specific coefficients shrunk toward zero. Fit the same completed monthly relative-return labels, dates and regularization policy. Compare the same capped allocation tilt from U0 and U1 on the unchanged monthly SOTA parent. Fix the fit window, penalty selection and tilt budget in the detailed specification before running either; a one-year window is not presumed adequate. A starting design is expanding estimation with at least 60 completed calendar months, with no claims for earlier unavailable dates.

Primary test: **U1 minus U0** after costs. Both also appear alongside the unchanged parent, so a useful USD increment is not confused with a generally harmful model overlay. All models must share an identical admissible sample. Use only lagged predictors; concurrent correlations and CNH translation gains are attribution, not predictive success. Do not hard-code common USD sensitivity or its sign across all ETFs.

Maintain two reports: USD strategy returns for signal evaluation, and unhedged CNH outcomes with an explicit FX bridge. For a USD sleeve with no external flows, `1 + r_CNH = (1 + r_USD)*(1 + r_USDCNH)`, where USD/CNH means CNH per USD. Residual CNH cash, flows, fees and conversions need the actual ledger treatment. Broad-dollar strength and USD/CNH are different exposures; neither is a guaranteed proxy for the other.

## 8. Staging and trial budget

Use SOTA as the first mechanism-testing parent, followed by unchanged-rule transfer to the other two monitored parents. Proposed initial ceiling: **24 additional SOTA recipes**—eight fixed monthly horizon recipes, four monthly gates, three monthly breadth/timing policies, seven weekly counterparts, and two monthly USD model specifications—plus the monthly and weekly parent controls. Data-unavailable blocks remain unavailable; no replacement proxy is selected because it improves results.

This is a staged design, **not a full combination grid**. Do not multiply every horizon by every gate, buffer, clock and USD feature. The original proposal's six-test count no longer applies.

Before any run, finalize a comparison ledger covering dynamic-versus-static comparisons, timing-versus-breadth controls, frequency interactions, U1-versus-U0, and up to three frozen finalists transferred to the other two parents. The number of statistical comparisons exceeds the number of recipes. All attempted comparisons, tuning and transfer selection remain in one cumulative record; phases do not reset the search penalty. Report all signs and failures. Transfer on reused data is robustness evidence and is correlated across parents; it is not fresh validation.

Only after reviewing the isolated results should we register a combined strategy or a learned regime gate. Earlier inspected history remains exploratory throughout.

## 9. Evaluation and decision rules

### Chronology and estimation

Use the same admissible dates, starting capital, constraints and cost rules for each matched pair. Keep labels and overlapping forward horizons wholly on the training side of every fit boundary; monthly models may use only labels completed and available before that fit. Any normalization or tuning uses training data only.

The history from 2016 onward, including the 2023 boundary, has already been examined. Label historical results **retrospective causal replays**, not untouched validation. A newly selected rule needs a new dated forward freeze; it cannot inherit the existing September 28 prospective start.

### Primary endpoint

For each pair, calculate the monthly difference in complete portfolio net returns, candidate minus parent. The primary economic endpoint is its annualized arithmetic mean, with a confidence interval. Also show compounded NAV and terminal wealth differences; they answer a different question.

Use paired inference on common calendar observations. Aggregate complete daily portfolios to calendar months for primary comparisons, including weekly strategies. Resample complete calendar blocks jointly across assets and every registered comparison, preserving contemporaneous dependence and serial structure. Propose a six-month block length as the primary specification, with three- and twelve-month blocks reported as fixed sensitivity checks. Set those rules before results; never choose the most favorable block length. These are finite-sample approximations with stationarity limits, not guaranteed confidence coverage in every market regime. Regime analysis must report independent calendar observations, persistence and transitions; twelve ETF rows in one month are not twelve independent state observations.

Apply a prespecified family-wise correction across the complete registered comparison ledger (Holm is a simple conservative choice). Freeze the family before results and include the transfer slots; do not restart significance testing in each phase. Report raw and adjusted values; identify whether intervals are marginal or simultaneous. Higher Sharpe, two separate t-statistics, or one significant/one insignificant result cannot replace the paired comparison. Treat DSR/PBO as optional selection diagnostics only when their trial-history inputs and assumptions are supportable. Unknown earlier trials remain a disclosed limitation. The broader design will have limited power, so an inconclusive result is plausible.

### Economics, implementation and risk

**Cost clarification pending:** the earlier draft proposed 25 bp/year as a minimum net return improvement; the user called 25 bp/year a reasonable trading cost. Keep these separate. Provisionally present 25 bp/year as the user's proposed annual cost allowance, with its budget interpretation awaiting clarification; the net-return materiality hurdle is not yet settled. No experiment depends on an assumed answer.

Compute costs from actual buys and sells: `annual_cost_bps = sum(one_way_cost_bps * abs(traded_notional) / pretrade_NAV) / years`, with explicit treatment of fees, slippage and initial deployment. At 5 bp per traded dollar, 25 bp/year corresponds approximately to total annual buy-plus-sell notional of 5× NAV; selling 100% and buying 100% consumes 2×. Do not subtract a flat 25 bp from every recipe or cap costs there: that would hide the cost of frequent trades.

Retain the current 5 bp per-side assumption and 10/20 bp stress scenarios as proposed comparisons. Report average annual cost and each calendar year's cost against the proposed allowance. Avoid counting slippage twice. If audited spread/impact information is unavailable, label these as scenarios rather than execution estimates. Do not claim capacity from fixed-bp costs. A budget breach is a result to discuss, not permission to alter the rules retrospectively.

Report, without selecting by them afterward:

- CAGR, volatility, Sharpe/active-return IR with explicit definitions, drawdown and worst calendar periods;
- gross exposure, cash, effective number of holdings, turnover and holding duration;
- asset contribution and exposure changes, including equity/bond concentration;
- trend/skew state counts, transition performance, dynamic horizon weights and switch frequency;
- membership counts, entry/exit confirmation delays and minimum-six overrides;
- USD feature availability, asset-specific sensitivities, USD returns and separate unhedged CNH translation;
- losses and behavior during fixed calendar stress periods, identified before the test;
- dependence on a few dates/assets, without removing those observations from primary performance;
- data exclusions, unavailable features, eligibility fallbacks and model-fit failures.

**Advance to a new paper observation phase only if** the paired improvement is economically material, supported under the prespecified family correction, robust to the declared cost/dependence checks, and within agreed risk limits. Proposed risk discussion flag: more than two percentage points of additional maximum drawdown requires an explicit trade-off review even if average return improves. Existing hard risk limits remain binding. A non-significant or fragile result is retained and reported; it does not justify widening the search until something passes.

A paper observation phase tests implementation and prospective behavior. A few weeks or months cannot establish a small return improvement. Review dates and a power/minimum-detectable-effect assessment should be agreed when the candidate is frozen. Do not promise that a fixed short observation period will deliver statistical certainty.

## 10. Later questions

1. **Predictive representation and redundancy.** Identify binary indicators actually consumed by the deployed models, their existing continuous counterparts and redundancy with the 20/60 and 63/126/252 signals. If justified, compare one prespecified encoding or a simple regularized predictor with the same completed labels and fitting schedule. A model feature change requires retraining/versioning; substituting values into a frozen tree changes its meaning.
2. **Interactions and existing relative tilt.** After the separate blocks, consider a registered combination and a matched ablation of the existing 20/60 tilt. Deleting a layer changes the complete strategy and is a trial even when called an ablation. The joint learned trend/skew gate also belongs here.
3. **Portfolio risk scaling.** Study a capped, lagged exposure rule against the existing adaptive layer, with matched cash and exposure accounting. No leverage or shorts are implied. F05/R09/R10/R24 motivate a question; their coefficients and full-sample normalization are not production defaults.
4. **Common-factor attribution and residual momentum.** Start with exposures derivable from already governed inputs. External factors require published/audited inputs and availability review. Residualizing can remove useful trend as well as unwanted exposure; compare complete portfolios if later approved.
5. **Broader universes, holdings and nonlinear models.** These require a distinct data/sample-size case and a new research budget. Variable holdings within the existing universe are already in scope; adding assets is a separate choice. The current literature does not justify an unrestricted feature search or reversing low-risk signals after inspecting performance.

## 11. Required artifacts for any approved research round

The application must calculate any eventual tracked candidate as a complete, versioned strategy. Use the shared SOTA detail/report format: full decision flow, signal values and eligibility, scheduled rebalance, latest targets and held weights, portfolio value, costs and matched benchmark report. Preserve Python/LEAN replay parity and machine-readable artifacts. Tracking remains separate from promotion and execution authority.

Required research package: specification and hypothesis ledger; pinned data and feature manifest; source/model hashes; reproducible commands/environment; full candidate return/trade histories; paired comparisons and all failures; review notes; and a dated freeze if a candidate advances. Promotion additionally needs the repository's out-of-sample, paper evidence, risk/capital limits, operator approval and rollback requirements.

No agents, reminders or Codex automations should perform recurring strategy calculations. No change to paper-first status, broker checks, reconciliation or live-disabled controls follows from this proposal.

## 12. Review status

**Direction agreed by the user:** symmetric short/long momentum; dynamic horizon selection as a hypothesis; both entry/exit timing directions with six or more holdings; a predictive USD feature; acceptance of unhedged USD/CNH exposure; deferral of missing broker/unnamed references; and the broader validation discipline.

**Proposed details still to settle:** the older-window endpoints; the fixed equity-state basket and 126-session state estimates; skew thresholds and 75/25 mixtures; the 0.10 breadth margin and five-session confirmations; minimum-six overrides; the staged recipe/comparison budget; the USD model/data contract; and the meaning of the 25 bp/year figure. These choices are written down to make the next review concrete, not to imply consent to every constant.

The user subsequently authorized the experiment round. The dated registration and results linked above now supersede the proposal-only status. Defaults were fixed without tuning, including the ridge penalty and USD availability rules. The 25 bp/year figure remains a proposed cost allowance, separate from the unset return hurdle. All monitored definitions and execution settings remain unchanged. Review the results before any combined strategy, further search or promotion work.
