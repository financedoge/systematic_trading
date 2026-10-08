# ETF strategy research and data expansion

Discussion proposal dated October 7, 2026. The objective is to improve net Sharpe and Calmar through economically distinct ETF exposures, country and industry information, and portfolio risk control. No improvement is assumed in advance. The trading boundary is ETFs only; constituent company data may inform ETF analysis without introducing single-stock trades.

The original three-series vintage milestone remains preserved as data evidence.
The user then broadened the scope before any economic portfolio test: prioritize
leading indicators, test payroll/CPI as separate context, use nonlinear models,
and allow positive and negative asset responses. The recorder registry now covers
sixteen series with seven leading candidates, four context series and five
financial-condition series; GDP is
excluded. See the [expanded recorder and feature contract](economic-vintage-recorder.md).
The [original revision audit](../research/economic-data-2026-10-07/assessment.html)
is data evidence, not a strategy result.

The primary economic test is complete: per-ETF leading trees/ridge, separate
payroll/output/inflation additions, matched sample and availability controls,
and unchanged SOTA/F3 references. Models use original vintages, completed labels
and training-only preprocessing, with positive and negative ETF responses.
Combined ridge raises evaluation Sharpe 1.081→1.103 and Calmar 0.922→0.974
versus capped F3. Trees fail the linear comparisons; no paired return contrast
passes 5% family adjustment, and combined ridge full-history Calmar is weaker.
Retain ridge as research, no promotion. All 51 replays and eleven native checks
passed using all 16 CPUs. See the [findings and complete reports](../research/economic-response-2026-10-07/findings.html).
Preserved parent eligibility/gross isolates allocation among beneficiaries;
expanding eligibility or adding ETFs requires a new experiment, not tuning this
batch. Missing context causes twelve latest monthly abstentions.

The user subsequently requested combined ridge in Monitored. Its exact CR
specification now runs through the application's complete strategy/report service,
including archive/restore catch-up, and stays frozen until the ETF-universe
revisit. Monitoring grants no capital or execution authority. Late prospective
economic captures cannot be backdated into missed strategy decisions.

The next financial-condition stage is also complete: Treasury curves, Chicago Fed
credit conditions and bank lending standards now have 2,112 published snapshots
across the sixteen-series panel. Eight financial-only and 21 augmented features
were tested with per-ETF ridge/trees and a matched original-context control.
Financial ridge improves evaluation Sharpe/Calmar only from 1.1027/0.9740 to
1.1057/0.9798; full-history ratios weaken and uncertainty includes zero.
Augmented ridge fails delayed Calmar, and both trees fail stronger comparisons.
Retain financial ridge as research evidence without changing monitored CR.
All 51 replays and eleven native validations passed on all 16 CPUs. See the
[financial-condition findings](../research/economic-financial-2026-10-07/findings.html).

## Commodity futures positioning recorder — 2026-10-08

Added an application-owned recorder for the CFTC Public Reporting Environment's
Disaggregated Futures Only dataset. It captures WTI, Henry Hub gas, COMEX gold,
silver and copper, plus LME aluminum as an indicator-only reference. The
normalized observations expose managed-money, producer/merchant and swap-dealer
net positions as shares of open interest, with the original source rows, hashes,
configuration version and first-app-seen timestamps retained. The first audited
publication contains 1,903 reports from 2020 onward: 352 each for the first five
markets and 143 for aluminum, ending June 9, 2026. The other five series end
September 29, 2026. The application refresh lane checks for updates every six
hours, and Market Data → Fund Positioning displays the published history.

CFTC report dates are Tuesdays; reports are normally released Friday at 3:30
p.m. Eastern and may be delayed by holidays. The API rows do not carry their
actual historical dissemination timestamps, so every row keeps its first time
captured by this app. No history has been backdated into earlier decisions and
this batch is not eligible for historical strategy backtests. COT describes
futures trader positioning, not ETF holdings or fund flows; linked funds are
economic proxies only. CFTC trader classifications can change, and the LME
aluminum code has materially shorter coverage. These records cannot qualify or
add any ETF to a tradable universe. Source: [CFTC COT reports and release
schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm),
[disaggregated report notes](https://www.cftc.gov/MarketReports/CommitmentsofTraders/DisaggregatedExplanatoryNotes/index.htm).

Recorder batch `406d59e27de2c63addef7ee832720ebb05102e9b3ebdad9c37993532f47ac9a6`;
the unchanged second capture was idempotent. Focused recorder/economic tests
pass (28), Ruff passes. Do not backtest the captured history. Next qualify an
energy supply/demand source with explicit release times (EIA weekly petroleum
and natural-gas balances), then build dated issuer-fund snapshots and ETF
price/identity admissions. Revisit positioning only under a prospective
availability contract and after the energy/metal ETF candidates are qualified.

National manufacturing/services PMI, permitted corporate bond spreads and
release-time consensus remain source-access work; regional Fed expectations and
NFCI credit conditions are separately labelled. Country/sector fundamentals still
need qualified sources. Source gaps are visible in Economic Data. Next: ETF
universe/issuer admission, prospective holdings/shares/NAV recorders, then sector
activity/growth/valuation/positioning pilots. Revisit economics after expansion;
small retrospective improvements are not established predictive alpha. No
economic strategy has been promoted or funded.

Implementation started October 7. The first F0–F3 fallback comparison is complete: cash-aware policies reduce historical drawdown, but only three episodes drive the evidence and paired return uncertainty includes zero. See the [results and reproducibility receipts](../research/fallback-results-2026-10-07.md). The active strategy remains the comparison baseline. Exposure-matched controls and a separately versioned final target cap have now been tested in the second batch below; the third batch qualifies BIL and tests F4. Continue building histories of ETF holdings and issuance, macro releases and selected industry fundamentals in small stages. Deployment, subscriptions, promotion and allocation changes retain their separate contracts.

The second finite batch is also complete: user-requested XGBoost forecast ranking at top 6/8/10 did not improve on the F3 top-6 price/volume ranking plus tilt. Matched-budget controls attribute most fallback benefit in the evaluation window to exposure timing; the final 45% target cap reduces concentration with little performance change. See the [assessment and complete reports](../research/ranking-construction-2026-10-07/assessment.html). Preserve these results without expanding the parameter search or automatically combining variants. The 66 scenarios and 16 primary native checks passed; no monitored recipe, SOTA or capital assignment changed. A genuinely new forecast target or ranking-specific training objective would be a distinct registered test.

The user requires **recorder first** for every new source: application-owned acquisition and original-vintage retention, audit and publication, inspectable coverage/history in Market Data, then frozen features and backtests. Expand the page categories to include economic and industry data as sources are admitted. F0–F3 and the ranking/construction batch required no new source. BIL is now admitted through the research ETF recorder, with 4,870 published daily observations and status/history in Market Data; SGOV remains unadmitted. Independent research calculations must use all available cores, bounded by memory and deterministic job dependencies; all three batches used 16 Python workers and native lanes totaling 16 CPUs.

The third finite batch is complete: F4 retains F1's qualifying positions and parks residual cash in BIL only during weak breadth, with a 45% BIL target cap and 2% cash reserve. It raises full-period F1 CAGR from 9.70% to 9.84% and Sharpe from 1.034 to 1.047, but remains behind F3. The gain survives 20bp costs, concentrates in 2022–23 and is not robust to dependence/family-adjusted inference. Retain it as a cash-management component for further research, not a promoted strategy. All 25 scenarios and seven primary native checks passed. See the [assessment and complete reports](../research/bill-parking-2026-10-07/assessment.html) and [recorder contract](bill-recorder-and-parking.md). Next work should add macro release vintages and prospective issuer snapshots before the country/industry signal pilots.

## Starting evidence

The active comparison baseline is **Rolling 1y XGBoost + ETF activity lag-20 + USD**, `research_rolling_xgboost_1y_lag20_v1_usd_v1`, selected as SOTA and the paper allocation on October 4. Older references to the frozen-tree SOTA are historical context. See [research state](research-state.md).

The existing research universe contains SPY, VGK, EWJ, EWH, EWY, MCHI, IEF, TLT, LQD, HYG, GLD and DBC. Gold and broad commodities are therefore already represented. Adding energy equities or a particular metal would refine the opportunity set, not introduce commodities for the first time. The recorder configuration contains a wider ETF seed, including sectors, but a configured symbol or downloaded archive does not establish audited research eligibility.

The user also requires every strategy to be executable through Interactive Brokers. Each new ETF must therefore pass broker contract identity, account/product permissions, supported currency/order sizing and paper execution checks before allocation. Public listings and backtest price coverage do not establish account-specific permission. F4 uses BIL (USD; issuer listing NYSE Arca; ISIN US78468R6633), represented by the existing IB stock/ETF SMART contract. The local paper Gateway is disconnected on October 7, so actual contract qualification and account acceptance remain pending. Do not substitute an inaccessible fund or direct Treasury security without a new audited instrument specification and replay.

Recent evidence argues for restraint in further tuning:

- The October 1 momentum round found shorter pool momentum and the tested trend/skew gates weaker than their parent. This is evidence about those recipes, not proof that all crash controls fail.
- The USD-specific increment was about 14 basis points per year in a 30-month comparison, with uncertainty including zero. The operator's subsequent selection does not strengthen that statistical evidence.
- Constituent activity work became much shorter under audited raw-price and identity requirements. The stricter study qualified only 32 of 129 monthly decisions; neutral fallback months are not constituent evidence.
- An older country macro result used a static country score map. Its persistent US overweight is not evidence for a release-aware economic forecasting signal.
- The inherited 45% limit applies to base weights before subsequent reallocation. The October 1 study found final held weights above it. A final target constraint and a separate drift policy require explicit versions and matched replay.
- The inherited pool filter passes through the original inverse-volatility basket when fewer than four ETFs pass its positive long-momentum gate. Later overlays still apply, but the pool itself does not allocate the rejected exposure to cash. This weak-signal behavior is a priority research hypothesis, not an established source of underperformance.

Evidence: [momentum results](../research/momentum-results-2026-10-01.md), [audited constituent rerun](audited-research-rerun-2026-09-26.md), and [flow research](flow-concentration-research-2026-09-26.md). Previously inspected historical periods remain development evidence.

## Portfolio design and universe expansion

More tickers help only if they add useful exposures or information after costs. First allocate risk across economic groups, then choose ETFs within those groups. Otherwise, adding eleven equity sectors to a twelve-fund universe can mechanically turn a diversified selector into a US equity portfolio.

| Expansion | Research purpose | Eligibility and interpretation |
| --- | --- | --- |
| Treasury bills or short duration; inflation-linked bonds | Better choices for defensive allocation and inflation exposure | Compare with existing IEF/TLT and properly remunerated cash; evaluate real-rate duration and stock/bond correlation stress. |
| Broad equity sectors | Separate sector cycles from country allocation | Begin with a complete sector family, dated classifications and common controls; do not select sectors because their recent returns look attractive. |
| Energy and industrial or precious metals | Isolate physical supply/demand and inflation sensitivities | Keep futures-based funds, physically backed products, producers and miners in distinct categories. Futures roll, collateral returns and equity operating leverage differ. |
| Narrow industries | Capture a measurable industry cycle | Energy and semiconductors are suggested pilots. Chemicals, metals/mining and other industries follow source and fund-coverage checks. |
| Additional countries | Add different economic and currency exposures | Require usable releases, dated ETF constituents, investability and adequate histories; geographic labels alone do not establish diversification. |

No specific new fund is approved by this table. Instrument selection must check mandate, legal structure, underlying holdings, inception, closures/mergers, expenses, spreads, capacity, premium/discount behavior and broker eligibility. Exclude leveraged, inverse and single-stock products from the initial expansion. Evaluate a small number of representatives per exposure, rather than letting near-duplicates multiply its allocation probability.

Use final portfolio limits on ETF weights, aggregate equity/country/sector exposure, constituent overlap, issuer concentration, liquidity and turnover. Specify whether each is a target-only limit or also requires a dated drift-rebalance rule; a target cap does not guarantee a held-weight cap between rebalances. Apply constraints after all overlays, with a deterministic feasible-allocation/cash rule and comparable controls.

## Weak signal fallback and cash allocation

The user requested this addition on October 7: test removing the return to the full inverse-volatility basket, explicitly allow almost all capital to remain in cash, and compare alternative fallbacks. This workstream precedes broad universe and feature expansion because it can first be isolated on the existing ETF universe.

The current `AssetPoolFilterOverlay.apply` returns the incoming targets unchanged when fewer than `minSelected=4` pass the positive 252-session momentum gate. It also has separate pass-through branches for unavailable scores and fewer than two incoming targets. Changing `reallocateSelected` alone does not remove those early returns. The active rolling XGBoost + activity + USD definition inherits this pool layer. Inspect all branches during implementation; weak signals and missing inputs must not share a generic fallback reason.

The [October 1 membership results](../research/momentum-results-2026-10-01.md) recorded 18 fallback decisions for each of the three monthly membership variants. Those are historical-study counts, not a newly measured count for the current active strategy. Begin by replaying and counting the active baseline's actual fallback episodes, qualifying assets, exposure and subsequent returns.

Proposed comparison family, with the existing monthly decision and next-session execution clock held fixed:

| Policy | Behavior when zero to three ETFs qualify | Purpose |
| --- | --- | --- |
| F0 Existing baseline | Pass through the original basket, then apply the existing later layers | Reproduce the current behavior exactly as the control. |
| F1 Qualified positions plus cash | Zero rejected ETF targets. Keep each qualifying ETF's incoming base weight, without scaling survivors to the former invested total. Leave the residual in cash. Zero qualifiers means a 100% cash target. | Primary test of the user's near-total cash proposal without requiring four holdings or forced investment. |
| F2 Cash only | Set all ETF targets to zero whenever fewer than four qualify | Isolate whether weak breadth warrants suspending the entire risky allocation rather than retaining one to three positions. |
| F3 Qualified defensive subset plus cash | Keep only eligible IEF, TLT and GLD positions at their incoming base weights, with no redistribution; rejected or non-defensive positions become cash. Require the same positive long-momentum gate and complete audited inputs. If none qualify, target cash only. | Test an explicit defensive alternative using existing instruments. Duration and gold exposures remain risky; their labels never exempt them from the gate. |
| F4 Qualified positions plus a Treasury-bill ETF | Use F1 for qualifying positions and invest the otherwise idle portion, less the operational cash reserve, in one predeclared eligible short Treasury-bill ETF, subject to its explicit instrument limit. Residual above that limit stays in cash. | Separate the cash-parking vehicle from the risk signal. This requires audited fund history, a defined instrument-specific limit and an investability check before testing. |

F1 is the primary challenger. F2–F4 are secondary comparisons, not a menu to select retrospectively for each historical crisis. Under F1–F3, four or more qualifiers retain the parent's normal pool behavior in the first experiment. Thus the initial test changes the weak-breadth branch only. A no-redistribution policy at every breadth level or a continuous breadth-based exposure rule would be a later, separately counted experiment. F4 changes parking only during the same weak-breadth regime and does not imply a Treasury-bill fund has always existed or is identical to cash.

There is no compulsory minimum risky allocation and no arbitrary 98% cash ceiling. A cash reserve is a minimum amount of cash, not a requirement to invest the balance. A 100% cash target is valid when nothing qualifies; residual units, open orders, settlement and execution costs may mean actual holdings take time to approach it. Do not describe a zero-target proposal as an executed liquidation.

For F1–F3, the selected-set mask and reduced invested budget must survive all later tree, relative-momentum, adaptive, activity and USD layers. Later layers may redistribute within eligible assets without exceeding that budget, and may reduce exposure further; they must not revive a rejected asset or refill intentionally released cash. F2's zero budget must remain zero. F4's parking position is accounted for separately from the risky budget and must not be fed into momentum tilts unintentionally. Show these budgets and final cash in the complete decision trace.

Keep missing required history, failed model fitting, corrupt hashes, unavailable FX and stale publications separate from a valid observation that momentum is weak. Such failures retain the existing error/publication and trading-block behavior; they do not authorize an all-cash trade or a substitute basket. Optional-feature handling must remain the versioned parent contract. A hold-last-publication display is not fresh authorization to trade. Check the short-input early return explicitly rather than letting it bypass the selected fallback.

Re-entry in the first comparison occurs at the next regular monthly decision under the unchanged eligibility gate: F1 can add qualifying positions at base budgets while breadth remains below four; F2 resumes risky targets only when breadth reaches four; F3 resumes the normal basket at four, and F4 unwinds parking as eligible exposure increases. Record the jump at the three-to-four boundary. Faster checks, confirmation periods, hysteresis and staged re-entry are later tests if this discontinuity or missed recoveries warrants them, not additional tuned knobs in the first round.

Cash economics need their own audited inputs. Keep the parent's declared cash treatment for the first causal comparison, then apply identical cash-remuneration scenarios to every policy and the baseline. Broker cash credit depends on currency, account terms, settled balances and balance/NAV tiers; a current advertised rate is not a historical return series. [IBKR cash-interest methodology](https://www.interactivebrokers.com/en/accounts/fees/pricing-interest-rates.php). Record dated rates/rules and reconcile actual credited interest. If history cannot be certified, report a zero-interest sensitivity separately and withhold any claim of fully verified broker-cash economics. Treasury-bill ETF returns require published adjusted prices and distributions without double-counting income, plus spreads, costs and inception coverage. USD cash still carries USD/CNH translation risk; becoming cash-heavy does not imply a currency hedge.

Evaluation must report cash share and duration, fallback entry/exit dates, qualifying counts, full-period and fallback-episode P&L, drawdowns avoided, recovery returns missed, re-entry costs, turnover and paired net Sharpe/Calmar/CAGR. Attribute complete holding intervals from a fallback decision to subsequent scheduled decisions, not only the trigger day. Compare both native exposure and a predeclared constant-exposure control with its risk target estimated from training data. Do not infer skill merely from holding less risk. Near-zero volatility or zero drawdown makes ratios undefined or unstable; report those cases honestly rather than ranking infinite ratios as wins.

Freeze four challengers plus F0 before outcomes, with costs/delays treated as declared robustness scenarios and all comparisons recorded. Keep prices, FX, fit schedules, labels and non-fallback signal recipes pinned. Where F4 has shorter valid history, show all policies on that common window in addition to the existing-universe long comparison. First isolate fallback changes under inherited constraints; then compare any selected policies and their controls under the same separately versioned final-weight contract. Do not credit the fallback with gains caused by a simultaneous cap change.

Implementation acceptance includes zero, one, two, three and four qualifying-asset cases; all-zero target handling; no forced min-holdings fill; no survivor renormalization under F1; no rejected-symbol resurrection downstream; source/model failures; unavailable defensive/parking assets; re-entry and settlement/cash accounting; and shared Python/native LEAN target, fill, cash and NAV parity. Publish complete strategies and reports through the app if selected for tracking. Current production fallback is unchanged by this roadmap edit, and no new performance result is claimed.

## Country economic information

Model the **change in the economic outlook and its relationship to expectations**, rather than assuming strong GDP growth predicts strong stock returns. A country fund's sector mix, foreign revenues, currency exposure and starting valuation can dominate its domestic cycle. Retain a common global component and test the additional country-specific information.

Start with a few interpretable families:

| Family | Candidate measurements | Intended role |
| --- | --- | --- |
| Leading activity | PMI new orders and orders versus inventories; OECD CLI changes; building permits or export orders where relevant | Detect improving or weakening demand ahead of reported earnings. |
| Inflation and policy | Inflation momentum, input prices, real yields and policy-rate changes | Distinguish demand expansion from margin pressure or restrictive financing. |
| Credit and liquidity | Lending standards, credit growth/impulse, credit spreads | Assess financing availability and risk appetite. |
| Earnings and valuation | Forecast revisions, sales/margin growth, earnings or cash-flow yields | Connect the economy to the securities actually held. |

For existing exposures, start with the US and a comparable cross-country core, then add local information for China/Hong Kong, Japan, Korea and Europe. VGK needs a documented regional aggregation; EWH cannot simply inherit mainland China's score. Candidate local releases include China's official PMI components and Japan's Tankan, both available from their [official publishers](https://www.stats.gov.cn/english/PressRelease/202608/t20260803_1964272.html) and [Bank of Japan](https://www.boj.or.jp/en/statistics/tk/). Other proposed national series need a source-by-source coverage review.

OECD describes CLI as a qualitative indicator of economic turning points, not a stock-return forecast. Use a verified historical release/version where available; current revised CLI values cannot stand in for what was known then. [OECD definition](https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html).

Begin with a small regularized model or fixed, versioned composite. Use macro information initially for bounded allocation or risk tilts and compare it with the same price-only model. A one-year monthly window supplies very few independent macro observations, even if the same releases are repeated across daily rows and ETFs. A longer macro training window or pooled model needs its own specification. Economic surprises require a consensus snapshot captured before release; without it, label the signal a change or model forecast error, not a consensus surprise.

## Sector and narrow industry information

Every sector strategy should expose five separate views: activity, growth, valuation, sentiment and positioning. Do not average them blindly into a universal score. Their useful direction, horizon and reliability vary by industry.

| Dimension | Quantitative candidates | Main interpretation control |
| --- | --- | --- |
| Activity | Orders, shipments, production, capacity utilization, inventories relative to sales | Distinguish real demand from nominal price inflation; account for seasonality and release lag. |
| Growth | Revenue and earnings growth, margin change, capex, forecast revision breadth | Compare consistent fiscal periods and expectations; preserve amendments and original forecasts. |
| Valuation and quality | Earnings/FCF yields, EV/EBITDA where appropriate, profitability, leverage and cash conversion | Use industry-appropriate measures and own-history comparisons; low cyclical P/E can reflect peak earnings. |
| Sentiment | Business surveys, estimate dispersion, option skew/term structure, versioned news measures | Identify the measured population; validate incremental information beyond returns and volatility. |
| Positioning | ETF net issuance, institutional ownership changes, futures positioning, constituent overlap | These describe different owners and instruments. None alone is a complete measure of money entering a sector. |

Suggested industry pilots:

| Industry | Activity and growth measurements | Valuation, sentiment and positioning context |
| --- | --- | --- |
| Energy | Oil/product inventories versus seasonal norms, refinery utilization, production, product supplied, producer capex | Futures curve and crack spreads, producer FCF/leverage, ETF issuance and CFTC positioning. Map upstream producers, refiners and physical commodity funds separately. |
| Semiconductors | Industry sales/shipments, inventory days, customer capex, revenue/margin and estimate revisions | Valuation versus growth/cycle, forecast dispersion, ETF issuance and concentration in the largest names. Do not treat smoothed public sales as unsmoothed monthly observations. |
| Industrial metals and mining | Warehouse stocks and movements, manufacturing orders, imports and physical demand measures | Curve/basis, supply costs, miner margins, positioning. Warehouse inventories cover a particular system, not all world supply. |
| Chemicals | Chemical output/utilization, inventories, end-market orders, product-minus-feedstock margins | Normalized earnings/FCF, leverage and estimate revisions. Petrochemicals, fertilizers, industrial gases and specialty chemicals need different drivers. |
| Banks and other financials | Loan growth, lending standards, deposit funding, delinquency and provisioning trends | Price/tangible book with profitability and capital context; a generic industrial-company EV/EBITDA score is inappropriate. |

The public [EIA data service](https://www.eia.gov/opendata/) supplies energy series. [LME warehouse reports](https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports) include stocks, movements and warrants, with different publication delays/access arrangements. The [American Chemistry Council](https://www.americanchemistry.com/chemistry-in-america-industry-innovation-impact/chemical-industry-statistics-u.s.-jobs-economic-impact/u.s.-chemical-production-index-by-region) publishes chemical production information. SIA's public semiconductor sales releases use WSTS data and describe the monthly series as a three-month moving average; detailed product data are a separate acquisition question. [SIA methodology example](https://www.semiconductors.org/global-semiconductor-sales-increase-15-8-from-q2-to-q3-month-to-month-sales-grow-7-0-in-september/).

Aggregate financials using the ETF's dated holdings and only filings available at the decision time. Retain weighted and equal-weight breadth, missing coverage, top-name concentration and classification history. For valuation, aggregate consistent yields or numerators/denominators rather than arithmetically averaging P/E ratios; explicitly handle losses and sector accounting differences. Begin with the existing constituent coverage discipline and predeclare any feature-specific thresholds before seeing outcomes. Do not silently renormalize a small surviving subset into a full-sector signal.

This preserves the boundary reflected in the user's Bayesian valuation work: company statements and sector outlook can inform an ETF signal, while individual-company positions remain a separate research and approval process. Narrow ETFs can still have substantial company-specific risk, so the boundary needs look-through concentration checks.

## Momentum and crash research

Keep price information as the timing and confirmation layer. Candidate improvements include agreement across a small fixed set of momentum horizons, constituent breadth, residual momentum after common market/sector exposure, abnormal traded activity and portfolio volatility/correlation stress. Estimate residual exposures causally and compare with simpler controls before using a more complex classifier.

Separate three failures: a falling market with persistent losses, a sharp reversal that punishes the previous winners, and a liquidity/correlation shock that defeats diversification. The classic momentum-crash research associates crashes with high-volatility states after declines and concurrent market rebounds. Its evidence is not a ready-made exit rule for this long-only ETF portfolio. [Daniel and Moskowitz](https://www.nber.org/papers/w20439).

A crash overlay must be evaluated as a complete allocation policy, including exposure reduction, cash destination, re-entry, turnover, gaps and missed recoveries. Compare smooth risk scaling and a simple fixed-risk control before complicated state models. Freeze a small comparison family; do not restart an unrestricted search over thresholds after the October 1 negative results.

Portfolio drawdown can also improve through independent return sources and stronger construction. Test those alongside predictive crash signals. Report return sacrificed for protection, not just a higher ratio.

## Data recorders and source priorities

The code already contains a broad-dollar ALFRED acquisition/publication path, ETF price governance, immutable market-data recording, and an SEC Company Facts importer. Provider manifests and optional macro/valuation score maps are not evidence of a populated, audited country/sector panel.

The existing SEC importer is a starting point, not a certified sector fundamentals engine: it uses filing dates rather than complete dissemination timestamps, approximates quarterly annualization, and labels a debt ratio with operating income in its denominator as net debt/EBITDA. Audit taxonomy, units, missing fields, quarter/YTD/TTM conversion, amendments and dated issuer identity before reuse. Extend the current service boundaries instead of building a parallel data store.

| Priority and recorder | Capture and cadence | Sources and access assessment |
| --- | --- | --- |
| First for fallback tests: cash economics and parking assets | Dated cash-credit rates/rules, balance tiers, currency/settlement eligibility and statement interest; daily data and distributions for a chosen Treasury-bill ETF | Broker statements and published terms plus the existing audit/publication pipeline. Current rates cannot populate past years; unverified history remains an explicit scenario limitation. No automatic switch of cash currency. |
| First: ETF reference, holdings and issuance | Daily issuer snapshots of shares outstanding, NAV, AUM, distributions, holdings and metadata; capture dated changes and corrections | Issuer downloads first. The [SPY issuer page](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy) demonstrates these fields, not a complete historical archive for every fund. Licensed holdings/flow history may be needed for backtests. |
| First: macro release vintages | Release-calendar acquisition plus retry; first publication, revisions and source timestamps | Extend ALFRED; add OECD and selected central-bank/statistical-agency releases. [ALFRED](https://alfred.stlouisfed.org/help) retains vintages but may use source, provider or first-FRED-availability dates and is not proof of intraday dissemination. |
| First pilot: energy and positioning | Weekly/monthly releases with actual publication time; curves at the declared decision frequency | EIA public API requires registration; [CFTC COT](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) normally reports Tuesday positions on Friday. Record actual releases, holidays and delays. COT is futures positioning, not ETF ownership. |
| Next: constituent financial statements | New filings/amendments, normalized after validation, with an immutable original | [SEC submissions and XBRL APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) for US issuers; global filings/standardized vendor data need a separate coverage assessment. API aggregates do not replace accession-specific availability checks. |
| Next: estimates, valuation and industry surveys | Daily consensus snapshots where entitled; release-based industry observations | Evaluate a point-in-time estimates product such as [LSEG I/B/E/S](https://www.lseg.com/en/training/learning-centre/learning-paths/learning-path-for-data-solutions/learn-about-quantitative-data-solutions/learn-about-data-and-content/learn-about-ibes). Detailed [S&P Global PMI](https://www.spglobal.com/market-intelligence/en/solutions/products/pmi) is subscription/licensing based. Verify samples and rights before selecting a feed. |
| Later: metals and chemicals detail | Daily/weekly inventories and curves; monthly activity; product/feedstock prices at matching timestamps | LME reports and licensed history; ACC public releases; specialist chemical-price data if the pilot needs it. Broad materials ETFs are not automatically chemical exposure. |
| Later: options, institutional holdings and news | Decision-frequency option surfaces; actual filing releases; immutable timestamped text | Seek licensed quote/history coverage where needed. Institutional disclosures are delayed and incomplete; news scores require frozen extraction rules, model versions and an availability audit. |

[ICI estimated ETF issuance](https://www.ici.org/research/stats/etf_flows) is useful as a weekly category-level cross-check, not a ticker-level daily history. Preserve revisions. With split-consistent shares, an estimated ETF issuance measure is `NAV_t × change_in_shares_t / prior_AUM`; reconcile distributions, mergers and reporting conventions against reported issuance. AUM changes include investment returns, and secondary-market turnover is not net subscription flow.

Start collecting prospective snapshots early once recorder implementation is selected: holdings, forecasts and web-published fund statistics can be difficult to reconstruct later. A recorder creates future evidence; it cannot manufacture a valid ten-year history. Evaluate paid data primarily on point-in-time estimates, holdings/issuance history and industry coverage. Additional high-frequency price data is a lower priority for the present monthly strategy. The existing delayed sampled channel remains inspection-only, and recovered intraday bars need their own audit/publication before research use.

No subscription access is assumed. Confirm delivery method, retention/derived-data rights, original timestamps, revisions, survivorship, mapping and sample coverage before a paid source is chosen. Price quotes and entitlements remain open decisions.

## Availability and publication contract

Every new input needs its entity/series identity, reference period, value and units, geography/classification, source publication timestamp or documented bound, first-seen/ingestion time, revision/vintage, source URI, raw payload hash, parser version, quality status and source rights. Holdings also need both membership-effective and public-availability dates; forecasts need target period and pre-release snapshot time.

Use this sequence: **capture immutable source evidence → validate and reconcile → publish a complete audited batch → verify hashes → calculate versioned features → replay or calculate a complete strategy**. Raw provider archives remain available for inspection and governance only.

- Historical as-of joins require supported public availability; a recent download timestamp does not certify historical availability. Verified historical releases may support reconstruction, while prospective operation records what the application actually received.
- A figure referring to June and published in August first becomes eligible in August. Date-only releases receive a conservative next-session rule; never imply an exact intraday timestamp.
- Preserve every revision and join only the version then available. Keep unavailable history missing. A bounded carry of an already published monthly observation must expose its age and expiry; it is not a newly observed daily value.
- Return calculations use the published dividend/split-adjusted basis. Traded activity uses audited raw price and raw volume; ratios involving shares and prices need compatible units and split treatment. Do not silently exchange adjusted and raw inputs.
- Retain fund inception, liquidations, mergers, dated security mappings and historical sector changes. Do not splice pre-inception index returns into executable ETF history; index-only exploratory studies must be separate and labelled.
- Publish source and date coverage alongside every feature. Price audit does not certify FX, holdings, forecasts or release vintages. Historical USD/CNH and other unresolved inputs retain their limitations; no fully audited CNH backtest can be claimed until the required classes qualify.

The application owns recorders, availability checks, features, scheduled rebalances, targets, held weights, NAV and benchmark reports. Use PostgreSQL for jobs/manifests/control state, immutable files for raw evidence and committed ClickHouse publications for analytical reads, following existing boundaries. Recovery needs idempotent capture, bounded retries, gap ledgers, clock/timezone checks, schema-drift alerts and last-complete publication retention. Research jobs have no trading authority. Agents and Codex reminders are not recurring calculation infrastructure.

## Evaluation sequence

1. **Freeze the baseline, fallback and constraints.** Pin the active strategy, data/feature/model versions, report economics and comparison dates. Prove replay parity and count valid weak-signal fallback episodes separately from data failures. Freeze F0–F4, downstream cash preservation and re-entry/cash economics before tests. Specify final weights, overlap and drift controls as a separate candidate, with the unchanged baseline preserved.
2. **Qualify data and exposures.** Establish a dated ETF inventory and coverage matrix. Choose sources by the hypotheses they can test; publish acquisitions before any research input is consumed.
3. **Separate universe value from signal value.** Compare old universe/old signal, expanded universe/same signal, old universe/new signal and expanded universe/new signal, wherever coverage supports a genuinely matched comparison. Use the same group budgets, timing and costs; show a price-only control on exactly the new signal's eligible dates.
4. **Test a small initial family.** First compare cash and alternative fallback policies on the existing universe, adding F4 only after parking-asset coverage qualifies. Then test a country macro tilt, an energy fundamental overlay, and a broad-sector or semiconductor fundamental pilot. Each new information model faces a simple composite or regularized control before XGBoost. Do not automatically combine the best observed variants or cross all fallback policies with all new signals.
5. **Validate stability and forward behavior.** Use chronological walk-forward fits with completed-label embargoes, dependence-aware uncertainty, a declared comparison ledger, costs and delayed-execution sensitivity. Stress cases should cover prolonged declines, sharp rebounds, inflation/rate shocks and liquidity stress where supported data exist. Preserve all failed trials. Freeze accepted recipes for prospective tracking; do not relabel the repeatedly inspected post-2023 period as untouched.

Use matched net returns, currency, risk-free series, calendars and samples for Sharpe; disclose a zero-risk-free legacy calculation separately. Compare Calmar as net CAGR divided by absolute maximum drawdown on the same window. Add drawdown duration, expected shortfall, turnover, concentration, capacity, average exposure and cash yield. Evaluate both natural exposure and a matched-risk control. A higher ratio produced by sacrificing most of the return is a tradeoff to report, not an automatic success. Use dependence-aware intervals for paired metrics, and treat Calmar estimates as particularly sensitive to a small number of drawdown episodes.

Advancement requires either credible return improvement at comparable risk or meaningful drawdown improvement with an explicitly acceptable return cost, supported across periods and costs. Predeclare economic tolerances before experiments. The shared SOTA report must show the full decision flow and matched benchmarks, including the active SOTA, risk parity on the relevant universe and URTH. Tracking, paper allocation and live authorization remain separate. Existing approval, broker-environment and reconciliation gates remain in force; live stays disabled.

## Proposed first implementation package

Deliver the fallback episode audit and versioned F0–F4 specification, cash-preservation/parity checks and cash-economics coverage assessment; an ETF coverage/overlap inventory; the versioned final-weight candidate specification; reusable release/vintage and issuer-snapshot recorders; a corrected and audited financial-statement normalization contract; and a small macro/energy feature catalog with explicit missing-data behavior. Source acceptance should include replay of a known historical release, revision/as-of tests, duplicate and outage recovery, source hash verification and a complete published batch.

After coverage is established, freeze the experiment recipes and comparison budget for review. Actual candidate calculations belong in the app and its standard report. No new backtests, recorders, paid acquisitions, schedules or portfolio changes were performed in this discussion session.
