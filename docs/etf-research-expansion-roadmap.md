# ETF strategy research and data expansion

Discussion proposal dated October 7, 2026. The objective is to improve net Sharpe and Calmar through economically distinct ETF exposures, country and industry information, and portfolio risk control. No improvement is assumed in advance. The trading boundary is ETFs only; constituent company data may inform ETF analysis without introducing single-stock trades.

## Latest result — October 14, 2026

The accepted first wave is ingested and the first full-supported-pool study has
finished its registered gate. Of 52 candidates, 50 have complete supported common
histories. Unchanged FR25 on this larger pool fails both cost and IC thresholds;
its full portfolio replay is withheld. Original-pool controls and the benchmark
pass native accounting parity. [Findings, exclusions and full attribution](etf-expansion-findings-2026-10-14.md).
The 14-ETF FR25 paper contract is implemented and its conditional preview passed;
capital remains separate. Class/volatility-aware ranking and historical membership
reconstruction are still required work, not completed by this diagnostic.

## Accepted direction — October 11, 2026

The operator accepted the second-review recommendations and requested **substantial expansion of the
tradable ETF universe**. The current priorities and staged P4.16d delivery are recorded in the
[research plan, P4.16d](signal-decay-and-alpha-plan.md):
inventory/taxonomy, audited admission waves, scalable app and paper-execution contracts, then controlled
full-pool research. Design for hundreds of candidates; admit on evidence, not a ticker quota. Allocation
remains separate from admission. The minimum 14-ETF contract and conditional FR25 paper pilot need not
wait for the full expansion. The October 10 disposition below is retained as historical context.

## Current delivery and historical context

The authoritative queue is [P4.16d in the research plan](signal-decay-and-alpha-plan.md).
Start with inventory and taxonomy; subsequent admission requires pinned published
inputs and point-in-time membership. Earlier proposed fallback, cash-stress and
first-package sequences are superseded by completed studies and the accepted
October 11 priorities. Their original wording and evidence references remain in
the [research-plan archive](archive/README.md).

Use [research state](research-state.md) for accepted results, [economic vintages](economic-vintage-recorder.md),
[energy data](energy-fundamentals-recorder.md), [issuer fundamentals](issuer-etf-recorder.md)
and [BIL qualification](bill-recorder-and-parking.md) for current recorder contracts.
Missing historical release availability remains a blocker, not an invitation to
backfill later-known data into earlier decisions.

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
