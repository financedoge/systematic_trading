# Supplemental research references

Two BIS papers added October 1, 2026 support the USD research question; the dynamic-trading paper added October 15 supports the rebalance-policy study. These supplement the original 45-document collection. They are literature, not approved market-data inputs. [Provenance and SHA-256 hashes](manifest.json) · [USD plan](../../momentum-research-plan-2026-10-01.md)

## T01 — Dynamic Trading with Predictable Returns and Transaction Costs

Nicolae Gârleanu and Lasse Heje Pedersen. Published journal version, The Journal
of Finance 68(6), December 2013, pp. 2309-2340; DOI 10.1111/jofi.12080.
32 PDF pages. Title, authors, journal and DOI verified; title page rendered and
visually checked. Selected firsthand reading: PDF pp. 1, 5-6, 8-9, 24; not a
complete proof review or empirical replication.

[Local PDF](T01_dynamic_trading_with_predictable_returns_and_transaction_costs.pdf)
· [Author's university source](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
· [Rebalance protocol](../../../docs/target-change-rebalance-plan.md)

The quadratic-cost model connects forecast persistence to gradual portfolio
adjustment. It motivates testing costs and responsiveness together; it does not
establish the proposed target-to-target L1 band, a numerical ETF threshold or
superiority over the app's monthly strategies. Those require the separate study.

## U01 — The US dollar and capital flows to EMEs

Gaston Gelos, Pietro Patelli and Ilhyock Shim. BIS Quarterly Review, September 2024. 17 PDF pages. Initial firsthand reading: PDF pp. 1, 5–6, 11; not a complete appendix review.

[Local PDF](D:/projects/systematic_trading/research/references/supplemental/U01_the_us_dollar_and_capital_flows_to_emes.pdf) · [BIS source](https://www.bis.org/publications/qr-202409/us-dollar-and-capital-flows-emes)

Uses monthly portfolio-flow and quarterly loan-flow panels across EMEs. Its dollar measure excludes EME currencies to reduce endogeneity concerns. The baseline regression includes contemporaneous dollar changes, and responses differ by financing type. This motivates an economic channel for a USD feature; a useful lagged ETF return forecast still needs a separate test. The proposed broad-index predictor also differs from the paper's AE-only index and must not be described as its replication.

## U02 — Commodity prices, the dollar and stagflation risk

Boris Hofmann, Taejin Park and Albert Pierres Tejada. BIS Quarterly Review, March 2023. 13 PDF pages. Initial firsthand reading: PDF pp. 1–5, 9, supplemented by the official article's empirical discussion.

[Local PDF](D:/projects/systematic_trading/research/references/supplemental/U02_commodity_prices_the_dollar_and_stagflation_risk.pdf) · [BIS source](https://www.bis.org/publications/qr-202302/commodity-prices-dollar-and-stagflation-risk)

Uses quarterly panel quantile regressions for growth and inflation tails in 22 economies that are not dependent on commodity exports. It documents commodities and USD appreciation moving together in 2021/22. This is macroeconomic evidence, not a traded DBC timing test. Our inference is to estimate and validate heterogeneous USD effects rather than assume one permanent sign for every ETF.

## Input-methodology references

- [Federal Reserve H.10 release documentation](https://www.federalreserve.gov/releases/h10/about.htm): daily observations are published in a weekly release covering the preceding week; original releases can differ from subsequently revised histories.
- [Federal Reserve dollar-index documentation](https://www.federalreserve.gov/releases/h10/Summary/): currency weights are revised and historical index values may change. A point-in-time feature therefore needs release/vintage evidence as well as an audited value.

Only documentation and papers were retrieved. No USD index observations entered the research input store.

The publisher abstract of [Cooper, Gutierrez and Hameed, Market States and Momentum (2004)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00665.x) was also inspected. A full original was not acquired/read in this revision, so it is background only and not used to set the proposed regime/window constants.
