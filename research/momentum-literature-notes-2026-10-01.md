# Firsthand momentum literature notes — 2026-10-01

**Discussion update:** the user broadened the plan to symmetric short/long horizons, trend/skew selection, both entry/exit timing directions, variable holdings and predictive USD information. See the [revised plan](momentum-research-plan-2026-10-01.md) and two additional [BIS firsthand notes](references/supplemental/README.md). The missing broker reports and unnamed citations are deferred by the user and are not prerequisites. The original reading record below is retained.

## Scope and reading depth

Read the three supplied reports, collected their identifiable cited works, then read selected substantive sections of each of the **45 acquired references**. The library comprises 42 academic papers, one broker report and two governance documents. Two cited broker reports remain inaccessible; several unnamed studies in the commentary remain unidentified.

This is an **initial firsthand reading**, with deeper attention to momentum definitions, costs, crash risk, model fitting and inference. It is not a claim to have read every proof/appendix or reproduced the studies. Each entry identifies the actual downloaded version and PDF page numbers inspected (including cover pages). Some versions predate the cited publication. The [reference index](references/README.md) and [manifest](references/manifest.json) record URLs, hashes, access failures and version differences.

## What changed after reading the originals

1. **Separate the mechanisms.** Recent-return exclusion, slower trading and risk scaling solve different problems. Combining them immediately would obscure what helped.
2. **Binary versus continuous is contextual.** Our existing momentum ranking is already continuous/ranked. Safety and eligibility gates have a different purpose from predictive features. R12 even uses a sign-based factor signal.
3. **Risk-scaling evidence is mixed but particularly relevant to momentum.** R10 qualifies universal claims; it does not rule out momentum benefits. Its implementation and estimation limits matter alongside R09 and F05.
4. **Stock results need an ETF translation.** The main papers use much wider cross-sections, and many use shorting or leverage. Their construction does not establish the result in twelve long-only ETFs.
5. **Selection and sample limits come before model complexity.** Shared strategy ancestry, reused history and short training windows constrain what we can infer from another favorable backtest.

These are research judgments from the reading, not empirical results for our monitored strategies. The [proposed plan](momentum-research-plan-2026-10-01.md) makes them testable and awaits discussion.

## Assessment of the supplied reports

- **Main report (42 pages, September 19):** useful record of iterative research, including revoked findings. Its weekly concentrated US-stock strategy differs materially from the app's monthly ETF stack. A common benchmark subtraction does not change cross-sectional ranks. Overlapping 65/130-day forward returns are not realized returns of a funded holding policy, and turnover cannot simply be divided by the label horizon. The selected 126-day specification and the rolling procedure that selected 250 days need separate interpretation. PIT corrections improve bias control but do not create independent validation.
- **Commentary V5 (5 pages):** many methodological objections are sound. The unnamed international/Japan/earnings studies cannot be verified from the supplied references. The suggestion to test alternative momentum definitions is appropriate, but the 1993 original uses a one-week skip, not a one-month skip.
- **Open questions and literature report (29 pages):** useful bibliography and organization. Primary reading narrows several implications: lifetime wealth concentration does not establish optimal momentum breadth; factor persistence does not identify all strategy returns as factor momentum; confidence sequences require assumptions; publication decline estimates are not universal return haircuts.

Additional issues to preserve in a future replication: the main report's fourteen binary/continuous pairs are correlated; increasing absolute IC can strengthen a negative signal without validating an ex-ante sign flip. A market being significant while another is not does not establish a significant difference. A rough maximum-statistic heuristic is not a calibrated 5% family-wise threshold. The illustrative 4.44-year information-ratio calculation reaches expected t≈1.96 under ideal assumptions, not 80% power. The European chart on PDF page 21 and the following prose also disagree. These points were assessed from the supplied material, without access to its original data/code.

## Paper-by-paper notes

Entries are ordered by the decisions they inform. The implications for this repository are our inferences; they are not claims made by the authors about these strategies.

### M01 — Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency

[Local paper](<D:/projects/systematic_trading/research/references/M01_returns_to_buying_winners_and_selling_losers_implications_for_stock_market_efficiency.pdf>) · [Retrieved source](https://www.wallstreetcourier.com/wp-content/uploads/data_download/research/Returns_to_Buying_Winners_and_Selling_Losers.pdf)

**Version:** Published, Journal of Finance 1993. **Inspected PDF pages:** 3-6,24.

Tests formation and holding periods of 3, 6, 9 and 12 months using overlapping portfolio cohorts. Its alternative construction skips **one week** between formation and holding; it is not an original test of the now-common one-month skip. The evidence concerns US stock winner-minus-loser portfolios. Our inference: distinguish formation horizon, excluded recent returns, holding duration and rebalance frequency. A longer forward-return label is not a funded long-holding strategy. Testing a 21-session exclusion in ETFs is a new hypothesis, not a literal replication.

### M02 — Evidence of Predictable Behavior of Security Returns

[Local paper](<D:/projects/systematic_trading/research/references/M02_evidence_of_predictable_behavior_of_security_returns.pdf>) · [Retrieved source](https://finance.martinsewell.com/stylized-facts/dependence/Jegadeesh1990.pdf)

**Version:** Scanned published Journal of Finance 1990 PDF; OCR used, title page visually verified. **Inspected PDF pages:** 2-4,9,17.

Finds monthly stock reversal and positive dependence at longer lags, especially the twelve-month lag. Separates statistical tests from implementable portfolio forecasts. Some statistical regressions estimate unconditional means using future observations; those are analytical devices, not permissible live features. Tests excluding the last trading day reduce, but do not eliminate, the reported reversal. This motivates checking the recent-return component separately from slower momentum; it does not establish net ETF profits after modern execution costs.

### M05 — Does the Stock Market Overreact?

[Local paper](<D:/projects/systematic_trading/research/references/M05_debondt.pdf>) · [Retrieved source](https://fac.comtech.depaul.edu/wdebondt/Publications/DoesStockM.pdf)

**Version:** Scanned published Journal of Finance 1985 PDF; OCR used, title page visually verified. **Inspected PDF pages:** 2-4,6,13.

Forms extreme stock winner/loser portfolios using prior three-year performance and studies subsequent multi-year reversal. The January effect is prominent and incompletely explained. This is a different time scale and portfolio construction from intermediate momentum. It provides no basis for automatically reversing a 252-session ETF signal. The study's historical sample selection and market-adjusted returns also require scrutiny before any replication.

### R12 — Factor Momentum and the Momentum Factor

[Local paper](<D:/projects/systematic_trading/research/references/R12_factor_momentum_and_the_momentum_factor.pdf>) · [Retrieved source](https://www.nber.org/papers/w25551.pdf)

**Version:** NBER working paper, February 2019; cited publication is 2022. **Inspected PDF pages:** 3-5,7-11,17-20,36.

The downloaded 2019 version links stock momentum to persistent factor returns and dispersed stock factor loadings. Its time-series factor strategy uses the **sign** of prior twelve-month factor performance. Binary signals can therefore encode a meaningful decision; blanket replacement with continuous values is not justified. Time-series and cross-sectional factor momentum are distinct constructions, and each factor is itself a long/short portfolio. For our ETFs, common-exposure attribution is a useful diagnostic; shorting published factors or removing all common momentum is not an established improvement.

### R17 — Characteristic-Sorted Portfolios: Estimation and Inference

[Local paper](<D:/projects/systematic_trading/research/references/R17_characteristic_sorted_portfolios_estimation_and_inference.pdf>) · [Retrieved source](https://mdcattaneo.github.io/papers/Cattaneo-Crump-Farrell-Schaumburg_2020_RESTAT.pdf)

**Version:** Published, Review of Economics and Statistics 2020. **Inspected PDF pages:** 5,17.

Treats characteristic sorting as nonparametric estimation and shows why the choice of portfolio bins depends on the estimation objective. Its momentum examples suggest nonlinearity and sensitivity to industry controls. The large stock cross-sections underlying the theory differ sharply from twelve ETFs. We should inspect rank changes and incremental portfolio returns, rather than transplant ten-bin stock sorts or select Top-N by the best historical Sharpe.

### R07 — Empirical Asset Pricing via Machine Learning

[Local paper](<D:/projects/systematic_trading/research/references/R07_empirical_asset_pricing_via_machine_learning.pdf>) · [Retrieved source](https://dachxiu.chicagobooth.edu/download/ML.pdf)

**Version:** Published, Review of Financial Studies 2020. **Inspected PDF pages:** 4-5,10-11,22-23,26-27.

Compares return-prediction models using many decades, thousands of stocks, extensive characteristics and chronological training/validation/test splits. Regularization and nonlinear interactions matter in that setting. Its early training and validation spans are much longer than our rolling one-year model window. Monthly cross-sectional rank transforms and missing-value treatments belong to its own data contract. The paper motivates a simple regularized benchmark and causal fitting; it does not validate our 100-tree model from roughly twelve calendar months of ETF labels.

### R08 — Shrinking the Cross-Section

[Local paper](<D:/projects/systematic_trading/research/references/R08_shrinking_the_cross_section.pdf>) · [Retrieved source](https://www.nber.org/papers/w24070.pdf)

**Version:** NBER working paper, November 2017; cited publication is 2020. **Inspected PDF pages:** 3-5,41.

Uses shrinkage in a high-dimensional stochastic discount factor. Low-eigenvalue directions receive stronger shrinkage; a sparse set of raw characteristics is less successful than a richer regularized representation in the studied setting. This concerns pricing portfolios and their covariance structure, not just a next-month return regressor. Our inference is to control unstable combinations and compare against a simple baseline, not to add many correlated technical indicators because they fit historical returns.

### R23 — Dissecting Characteristics Nonparametrically

[Local paper](<D:/projects/systematic_trading/research/references/R23_dissecting_characteristics_nonparametrically.pdf>) · [Retrieved source](https://bfi.uchicago.edu/wp-content/uploads/we6b7o-WP_2018-50.pdf)

**Version:** BFI working paper, July 2018; cited publication is 2020. **Inspected PDF pages:** 3-5.

Uses nonlinear characteristic functions and adaptive group LASSO, selecting a subset of characteristics and comparing nonlinear and linear models. The downloaded 2018 version fixes a selection period before later rolling estimation and acknowledges that previously discovered predictors can inflate absolute performance. Its sparse predictive model and R08's dense pricing model solve different problems. For us, any encoding comparison must hold the learner, causal training window, labels and cost model fixed.

### F04 — A Taxonomy of Anomalies and Their Trading Costs

[Local paper](<D:/projects/systematic_trading/research/references/F04_a_taxonomy_of_anomalies_and_their_trading_costs.pdf>) · [Retrieved source](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf)

**Version:** Working paper, August 2015; cited publication is 2016. **Inspected PDF pages:** 2-4,8-10,24,26,41.

Compares cost-mitigation methods for stock anomalies. A stricter entry rule than continued-holding rule performs well; its example buys the top decile and retains positions until they leave the top quintile. This supports a small, explicit rank buffer hypothesis. The study's spread estimates, missing-cost matching and limited market-impact treatment cannot be imported as ETF execution assumptions. Savings must come from replayed trades and be assessed against any lost signal responsiveness.

### F05 — Momentum Has Its Moments

[Local paper](<D:/projects/systematic_trading/research/references/F05_momentum_has_its_moments.pdf>) · [Retrieved source](http://www.snifferquant.com/gyantal/Incode/papers/Momentum%20Has%20Its%20Moments%28scaling%20Momentum%20by%20vol%29%2C2014.pdf)

**Version:** Forthcoming manuscript, November 2014; cited publication is 2015; mirror contains reader annotations. **Inspected PDF pages:** 3-4,7-14,20.

Scales a long/short momentum portfolio by lagged realized volatility, using 126 daily squared returns and a 12% annual volatility target. This is portfolio-level inverse-volatility scaling, not the inverse-volatility allocation of individual assets. Some scaled exposures exceed one, and the payoff relies on the risks of a winner-minus-loser portfolio. A capped, long-only implementation would be a separate test. Reader annotations in this mirror are excluded from the evidence.

### R09 — Volatility-Managed Portfolios

[Local paper](<D:/projects/systematic_trading/research/references/R09_volatility_managed_portfolios.pdf>) · [Retrieved source](https://www.nber.org/system/files/working_papers/w22208/w22208.pdf)

**Version:** NBER working paper, April 2016; cited publication is 2017. **Inspected PDF pages:** 7-9,27.

Uses inverse **variance**, estimated from the previous month's daily returns, to scale factor exposure. The normalization matches volatility in the sample. Constant normalization leaves unconstrained Sharpe unchanged, but matters once leverage, caps and costs enter. Spanning-regression alpha and an implementable prospective allocation answer different questions. Any adaptation would need a lagged risk estimate, a scale fixed using past information, and explicit cash/exposure accounting.

### R10 — On the Performance of Volatility-Managed Portfolios

[Local paper](<D:/projects/systematic_trading/research/references/R10_on_the_performance_of_volatility_managed_portfolios.pdf>) · [Retrieved source](https://www.lehigh.edu/~xuy219/research/COWY.pdf)

**Version:** Published, Journal of Financial Economics 2020. **Inspected PDF pages:** 2-3,12,17,19.

Across 103 equity strategies, simple volatility management produces mixed direct comparisons; the significantly improved cases cluster around momentum. The paper also finds unstable out-of-sample combinations of scaled and unscaled portfolios despite attractive ex-post regressions. This is a qualification of universal volatility-scaling claims, not evidence that momentum risk management never helps. Our existing inverse-volatility base and adaptive scaling make a further risk overlay an incremental, potentially redundant choice.

### R24 — Momentum Crashes

[Local paper](<D:/projects/systematic_trading/research/references/R24_momentum_crashes.pdf>) · [Retrieved source](https://www.kentdaniel.net/papers/published/jfe_16.pdf)

**Version:** Published, Journal of Financial Economics 2016. **Inspected PDF pages:** 2-3,5,12-13,16,22.

Momentum crashes occur in stressed markets and rebounds, with an important contribution from shorting past losers that subsequently rally. The dynamic construction considers conditional mean and variance; the paper also presents expanding-estimation out-of-sample checks. Some allocations are leveraged or negative. Our long-only multi-asset strategies do not have the same short-leg mechanism. Test rebound losses and portfolio exposure first; do not label a copied bear-market switch as a proven crash hedge.

### M03 — The Cross-Section of Volatility and Expected Returns

[Local paper](<D:/projects/systematic_trading/research/references/M03_the_cross_section_of_volatility_and_expected_returns.pdf>) · [Retrieved source](https://www.ruf.rice.edu/~yxing/vol.pdf)

**Version:** Early working paper, August 13, 2003; substantially predates cited 2006 publication. **Inspected PDF pages:** 1,4-5,27.

The acquired copy is an early **August 2003** draft of the paper cited as 2006. It distinguishes exposure to aggregate volatility innovations from a stock's idiosyncratic volatility and reports low subsequent returns for high-idiosyncratic-volatility stocks. These are not interchangeable with total ETF volatility. Its early numerical results should not be attributed to the final journal version. It is insufficient evidence to reverse our risk allocation after observing a recent growth-stock sample.

### M04 — Betting Against Beta

[Local paper](<D:/projects/systematic_trading/research/references/M04_betting_against_beta.pdf>) · [Retrieved source](https://pages.stern.nyu.edu/~afrazzin/pdf/Betting%20Against%20Beta%20-%20Frazzini%20and%20Pedersen.pdf)

**Version:** Published, Journal of Financial Economics 2014. **Inspected PDF pages:** 2,6,20.

Models leverage constraints and constructs a betting-against-beta portfolio by leveraging low-beta assets and shorting high-beta assets to balance market exposure. It studies equities and other asset classes and documents funding-liquidity risks. A low-risk long-only allocation is not the same payoff as this self-financing factor. Use it to reason about exposures and constraints, not to assume that inverse volatility must outperform without accounting for leverage and cash.

### R25 — Low-Risk Anomalies?

[Local paper](<D:/projects/systematic_trading/research/references/R25_low_risk_anomalies.pdf>) · [Retrieved source](https://research-api.cbs.dk/ws/portalfiles/portal/65573325/christian_wagner_et_al_low_risk_anomalies_publishersversion.pdf)

**Version:** Published, Journal of Finance 2020, with repository cover. **Inspected PDF pages:** 3-4,18,41.

Develops a skewness-aware pricing explanation for beta and volatility anomalies. Option-implied measures and a quadratic pricing kernel help explain the low-risk strategy alphas in the studied stock sample. This is a competing explanation for those returns, rather than an instruction to flip the sign of volatility. An empirical adaptation would require audited option data and appropriate timing; those inputs are outside the present ETF price/volume plan.

### R26 — A Lottery-Demand-Based Explanation of the Beta Anomaly

[Local paper](<D:/projects/systematic_trading/research/references/R26_a_lottery_demand_based_explanation_of_the_beta_anomaly.pdf>) · [Retrieved source](https://4c2fbf95-cd10-40e9-8bf8-f71417d8f87e.filesusr.com/ugd/c124ce_bcfc84cba3a9484183936867d97995de.pdf)

**Version:** Published, Journal of Financial and Quantitative Analysis 2017. **Inspected PDF pages:** 2-3,27.

Proxies lottery demand with the average of a stock's five largest daily returns in the month. Controlling for that measure reduces the beta anomaly; institutional ownership and time variation provide additional evidence. MAX is a proxy, not an observed investor-demand flow. Stock-specific lottery demand and high-beta selection do not transfer automatically to diversified ETFs. This strengthens the case for exposure attribution and cautions against interpreting all low-risk results as one mechanism.

### R11 — Do Stocks Outperform Treasury Bills?

[Local paper](<D:/projects/systematic_trading/research/references/R11_do_stocks_outperform_treasury_bills.pdf>) · [Retrieved source](https://r.jordan.im/download/investing/bessembinder2018.pdf)

**Version:** Accepted manuscript; cited publication is 2018. **Inspected PDF pages:** 3-4,7-8.

Studies US stock lifetime buy-and-hold returns and the concentration of aggregate wealth creation in relatively few winners. Mean and median experiences differ because returns are skewed. This is an ex-post distributional result, not a demonstrated rule for selecting future winners. It cannot establish that Top-5 or Top-6 momentum is optimal, and individual-stock lifetime outcomes are a poor direct analogue for a monthly diversified-ETF allocation.

### R21 — Long-Term Shareholder Returns: Evidence from 64,000 Global Stocks

[Local paper](<D:/projects/systematic_trading/research/references/R21_long_term_shareholder_returns_evidence_from_64_000_global_stocks.pdf>) · [Retrieved source](https://covestreetcapital.com/wp-content/uploads/2023/07/Long-Term-Shareholder-Returns-Evidence-from-64-000-Global-Stocks.pdf)

**Version:** Published, Financial Analysts Journal 2023, with cover. **Inspected PDF pages:** 2-4.

Extends long-horizon shareholder-return analysis globally and again finds concentrated wealth creation. The non-US evidence makes an exclusively US winner-tail explanation untenable. Results depend on stock lives, dividends, security identity and a common currency. They do not determine the right number of ETF holdings. Our use is to assess contribution concentration and missed winners, while keeping ex-ante selection skill separate from ex-post wealth concentration.

### R01 — False (and Missed) Discoveries in Financial Economics

[Local paper](<D:/projects/systematic_trading/research/references/R01_false_and_missed_discoveries_in_financial_economics.pdf>) · [Retrieved source](https://people.duke.edu/~charvey/Research/Published_Papers/P143_False_and_missed.pdf)

**Version:** Published, Journal of Finance 2020. **Inspected PDF pages:** 3,10-13.

Calibrates false discoveries and missed discoveries through a double-bootstrap framework, making the cost of the two error types explicit. Its threshold depends on assumptions about the share of true signals. False discovery rate is not family-wise error probability. For our small candidate family, retain the joint date-by-candidate return matrix, specify the error criterion and account for serial dependence; quoting one universal t-statistic cutoff would lose the substance of the method.

### R02 — The Probability of Backtest Overfitting

[Local paper](<D:/projects/systematic_trading/research/references/R02_the_probability_of_backtest_overfitting.pdf>) · [Retrieved source](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

**Version:** Working paper, February 2015; cited journal publication is 2017. **Inspected PDF pages:** 9-11.

Defines probability of backtest overfitting through the relative out-of-sample rank of an in-sample winner across combinatorial splits. It is not the probability that a strategy loses money in the future. CSCV requires a recorded candidate-performance matrix and does not turn reused history into fresh evidence. It is also distinct from purged chronological model validation. Useful as a selection diagnostic when the candidate archive exists, not as a substitute for a new forward freeze.

### F02 — The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality

[Local paper](<D:/projects/systematic_trading/research/references/F02_the_deflated_sharpe_ratio_correcting_for_selection_bias_backtest_overfitting_and_non_normality.pdf>) · [Retrieved source](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

**Version:** Forthcoming manuscript, July 2014. **Inspected PDF pages:** 8-10.

Adjusts inference about a selected Sharpe ratio for non-normal returns and the number/distribution of trials. It requires more than the winning Sharpe: sample length, higher moments and a defensible selection benchmark matter. Unknown discarded trials cannot be reconstructed from the final result. Our plan should retain complete returns for every candidate and disclose trial-count sensitivity; a deflated Sharpe calculation alone cannot certify an already selected strategy.

### F01 — … and the Cross-Section of Expected Returns

[Local paper](<D:/projects/systematic_trading/research/references/F01_and_the_cross_section_of_expected_returns.pdf>) · [Retrieved source](https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF)

**Version:** Published, Review of Financial Studies 2016. **Inspected PDF pages:** 2-3,32-33.

Shows why conventional significance thresholds become unreliable when many factors are searched. Its illustrative higher t-statistic hurdle belongs to a specified factor-discovery setting, not every future trading study. Economic reasoning and the prior plausibility of a hypothesis matter as well. We should record the finite family, including failed variants and tuning choices, and test paired incremental performance rather than compare separate significance labels.

### R22 — Anomalies and False Rejections

[Local paper](<D:/projects/systematic_trading/research/references/R22_anomalies_and_false_rejections.pdf>) · [Retrieved source](https://drive.google.com/uc?export=download&id=1bKjGRlvtSugND_QH1HVWB9RIobY7UxbQ)

**Version:** Published, Review of Financial Studies 2020. **Inspected PDF pages:** 2-3.

Uses a very large constructed universe of strategies and dependence-aware multiple testing to study false rejections and discovery thresholds. The calibration reflects that search universe; it does not supply a portable universal threshold for six ETF comparisons. The practical lesson is that the visible winning specification can conceal a much wider search. Known trials and uncertainty about missing trials both belong in the evidence record.

### R31 — Detection of False Investment Strategies Using Unsupervised Learning Methods

[Local paper](<D:/projects/systematic_trading/research/references/R31_detection_of_false_investment_strategies_using_unsupervised_learning_methods.pdf>) · [Retrieved source](https://smallake.kr/wp-content/uploads/2020/04/SSRN-id3167017.pdf)

**Version:** Working paper, November 2018; cited publication is 2019. **Inspected PDF pages:** 5,8,13.

Clusters correlated strategy trials to estimate effective independent trials and support selection-bias assessment. That estimate is conditional on the strategies retained in the archive. It cannot recover forgotten experiments or neutralize repeated analyst choices. Keep full candidate histories and report sensitivity to clustering/trial assumptions; do not count correlated variants as independent discoveries or silently discard them from the search budget.

### R13 — Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences

[Local paper](<D:/projects/systematic_trading/research/references/R13_time_uniform_nonparametric_nonasymptotic_confidence_sequences.pdf>) · [Retrieved source](https://arxiv.org/pdf/1810.08240)

**Version:** arXiv v9, August 2022; later than cited 2021 publication. **Inspected PDF pages:** 1-3,9.

Constructs confidence sequences whose coverage holds uniformly over time under stated probabilistic conditions. Nonparametric does not mean assumption-free: conditional moment/tail bounds and supermartingale constructions matter. Financial returns and adaptively changing strategies do not automatically satisfy those conditions. Fixed review dates are a practical initial protocol; any later anytime-valid stopping rule needs a separate assumptions review and dependence treatment.

### R03 — A Backtesting Protocol in the Era of Machine Learning

[Local paper](<D:/projects/systematic_trading/research/references/R03_a_backtesting_protocol_in_the_era_of_machine_learning.pdf>) · [Retrieved source](https://people.duke.edu/~charvey/Research/Published_Papers/G138_A_backtesting_protocol.pdf)

**Version:** 2019 journal author draft marked Author Draft for Review only. **Inspected PDF pages:** 2-4,8-9.

Offers a research protocol covering economic motivation, data limits, implementation costs, model dynamics and complexity. Repeatedly fixing a model after observing its holdout destroys the holdout's untouched status. A nonsensical ticker-letter strategy illustrates how impressive historical evidence can arise from searching. The direct application is a prospective trial ledger, fixed rules before evaluation and a clean distinction between a causal historical replay and genuinely new observations.

### R18 — Presidential Address: The Scientific Outlook in Financial Economics

[Local paper](<D:/projects/systematic_trading/research/references/R18_presidential_address_the_scientific_outlook_in_financial_economics.pdf>) · [Retrieved source](https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf)

**Version:** Published, Journal of Finance 2017, with introductory portrait. **Inspected PDF pages:** 3-4.

The presidential address argues for scientific discipline beyond mechanical significance. Its examples expose how specification searches and weak economic foundations can produce impressive statistics. Raising a cutoff alone is not a cure. Our hypotheses need a stated mechanism, a reason they may fail, full reporting and evidence that survives implementation choices—not just a selected backtest chart.

### R04 — Replicating Anomalies

[Local paper](<D:/projects/systematic_trading/research/references/R04_replicating_anomalies.pdf>) · [Retrieved source](https://www.nber.org/system/files/working_papers/w23394/w23394.pdf)

**Version:** NBER working paper, May 2017; 447 anomalies; predates cited 2020 publication. **Inspected PDF pages:** 2-5,8-9.

The downloaded May 2017 version examines 447 anomalies and finds that many fail under its common construction, including NYSE breakpoints and value weighting. Microcap treatment changes conclusions materially. These counts belong to this version, not automatically to the cited 2020 article. The lesson is to distinguish reproducing an author's exact test from testing whether the economic idea survives a different investable portfolio.

### R05 — Is There a Replication Crisis in Finance?

[Local paper](<D:/projects/systematic_trading/research/references/R05_is_there_a_replication_crisis_in_finance.pdf>) · [Retrieved source](https://www.nber.org/system/files/working_papers/w28432/w28432.pdf)

**Version:** NBER working paper, February 2021; predates cited 2023 publication. **Inspected PDF pages:** 2-5,8-9.

Uses a hierarchical Bayesian framework, related factor themes and international evidence, reaching a more favorable assessment of factor replication. Cross-country evidence is correlated and is explicitly modeled as such. Weighting and hypotheses differ from R04, so their headline replication rates do not answer an identical question. Similarly, our three strategies share most of their allocation machinery and cannot provide three independent confirmations of a shared signal change.

### R06 — Open Source Cross-Sectional Asset Pricing

[Local paper](<D:/projects/systematic_trading/research/references/R06_open_source_cross_sectional_asset_pricing.pdf>) · [Retrieved source](https://www.cfr-cologne.de/download/workingpaper/cfr-20-04.pdf)

**Version:** CFR manuscript dated May 2021; cited publication is 2022. **Inspected PDF pages:** 2-4,8-9.

Reconstructs published characteristics and compares reproduced findings with the evidence claimed in the original papers. Distinguishes clear predictors, mixed evidence and other characteristics. It explicitly separates reproducibility from implementable trading profits. For us, an exact baseline replay is an engineering prerequisite; persistence after costs and a new freeze remain separate empirical requirements.

### R19 — The History of the Cross-Section of Stock Returns

[Local paper](<D:/projects/systematic_trading/research/references/R19_the_history_of_the_cross_section_of_stock_returns.pdf>) · [Retrieved source](https://www.nber.org/papers/w22894.pdf)

**Version:** NBER working paper, December 2016; cited publication is 2018. **Inspected PDF pages:** 3-4,7.

Extends anomaly evidence to earlier accounting history and finds weaker performance outside discovery samples. The construction includes assumed accounting lags and imputed delisting outcomes, which are material replication choices. We cannot copy those conventions into an audited-input workflow without qualification. Earlier history is only new validation if it was genuinely unused and supports the same identities, availability and definitions.

### R20 — Anomalies across the Globe: Once Public, No Longer Existent?

[Local paper](<D:/projects/systematic_trading/research/references/R20_anomalies_across_the_globe_once_public_no_longer_existent.pdf>) · [Retrieved source](https://www.unicreditgroup.eu/content/dam/unicreditgroup-eu/ucfoundation/WorkingPapers/2019/wp-135-Jacobs-e-Mueller.pdf)

**Version:** Published, Journal of Financial Economics 2020. **Inspected PDF pages:** 2,4,17.

Studies anomalies across 39 markets under a common framework. A reliable post-publication decline appears in the US, with different evidence elsewhere. This concerns publication-related decay, not a finding that momentum exists only in the US. Cross-market comparisons must hold portfolio construction and selection intensity comparable, and test differences directly rather than infer them from one significant result and one insignificant result.

### F03 — Does Academic Research Destroy Stock Return Predictability?

[Local paper](<D:/projects/systematic_trading/research/references/F03_does_academic_research_destroy_stock_return_predictability.pdf>) · [Retrieved source](https://counterpointfunds.com/wp-content/uploads/2017/07/PredictabilityMcleanPontiff.pdf)

**Version:** Forthcoming Journal of Finance manuscript; cited publication is 2016. **Inspected PDF pages:** 7,10,27-28.

Separates returns after the original sample ends but before publication from returns after publication for 97 predictors. The reported declines support both statistical selection and market-learning explanations, with limitations in separating mechanisms. Its average percentage declines are not forecasts for our specific strategies. Development history, publication dates and actual prospective freezes should remain explicit in any decay discussion.

### R27 — Understanding Alpha Decay

[Local paper](<D:/projects/systematic_trading/research/references/R27_understanding_alpha_decay.pdf>) · [Retrieved source](https://wp.lancs.ac.uk/fofi2018/files/2018/03/FoFI-2018-0089-Julien-Penasse.pdf)

**Version:** Working paper, December 2017; cited publication is 2022. **Inspected PDF pages:** 2-3,11,15.

Explains how declining expected alpha can generate a one-time repricing gain, making historical realized returns overstate sustainable forward expected returns. The acquired December 2017 paper predates the cited 2022 publication. It supports conservative interpretation of recent success and changing opportunity sets, but does not provide an operational rule for turning our signals on or off.

### R28 — When Do Systematic Strategies Decay?

[Local paper](<D:/projects/systematic_trading/research/references/R28_decay.pdf>) · [Retrieved source](https://dspace.mit.edu/server/api/core/bitstreams/90821bfa-3c4c-4682-9773-b588e272590a/content)

**Version:** Published, Quantitative Finance 2022, with repository cover. **Inspected PDF pages:** 3-4,10,12.

Replicates systematic strategies and relates decay to complexity and influential observations. International comparisons account for diversification differences. Tests removing influential returns are diagnostics, not a tradable rule for deleting adverse observations. Our application is a predeclared concentration/complexity assessment, with all observed outcomes preserved and no tuning to the subset that looks most favorable.

### R29 — Nonstandard Errors

[Local paper](<D:/projects/systematic_trading/research/references/R29_nonstandard_errors.pdf>) · [Retrieved source](https://www.pure.ed.ac.uk/ws/portalfiles/portal/431586790/MenkveldEtal2024JFNonstandardErrors.pdf)

**Version:** Published publisher PDF, 2024, with repository cover; online pagination. **Inspected PDF pages:** 5-7,12,36-37.

Has 164 teams analyze the same data and questions, measuring variation introduced by research choices. Peer feedback reduces this additional uncertainty. That is distinct from sampling error and helps explain why independent implementation is valuable. One wording needs care: its conclusion says Bonferroni assumes independence; Bonferroni's family-wise bound does not require independence, although dependence can make it conservative. Reproducible calculations and a review of reasonable specifications address different failure modes.

### R30 — Computational Reproducibility in Finance: Evidence from 1,000 Tests

[Local paper](<D:/projects/systematic_trading/research/references/R30_computational_reproducibility_in_finance_evidence_from_1_000_tests.pdf>) · [Retrieved source](https://affi2023.eventsadmin.com/Papers/ViewContribution?cid=9409&h=0A9E36F506D8DB446BBA763B10757256)

**Version:** Working paper, April 14, 2023; cited publication is 2024. **Inspected PDF pages:** 1,8,23,36.

The April 2023 draft studies computational reproduction of over 1,000 results from a multi-analyst microstructure exercise. Original code and data reproduce the exact result only about half the time. A runnable package is therefore necessary, but does not establish a sound hypothesis or unbiased data. We should preserve pinned inputs, versions, commands and machine-readable outputs, then separately evaluate scientific validity.

### R32 — Alice’s Adventures in Factorland: Three Blunders That Plague Factor Investing

[Local paper](<D:/projects/systematic_trading/research/references/R32_alice_s_adventures_in_factorland_three_blunders_that_plague_factor_investing.pdf>) · [Retrieved source](https://people.duke.edu/~charvey/Research/Published_Papers/P139_Alices_adventures_in.pdf)

**Version:** Published, Journal of Portfolio Management 2019. **Inspected PDF pages:** 2-4,16.

Discusses overestimated factor returns, implementation effects, changing exposures and understated uncertainty. Its factor portfolios use volatility normalization and its simulations compare different resampling assumptions. Those constructions need to be read before interpreting a factor Sharpe or drawdown. Our strategy comparisons should report cash, gross exposure, correlation, costs and actual compounded portfolios alongside predictive statistics.

### R14 — Automating Large-Scale Data Quality Verification

[Local paper](<D:/projects/systematic_trading/research/references/R14_automating_large_scale_data_quality_verification.pdf>) · [Retrieved source](https://www.vldb.org/pvldb/vol11/p1781-schelter.pdf)

**Version:** Published, PVLDB 2018. **Inspected PDF pages:** 2-3,11.

Presents declarative data checks, reusable metrics, incremental validation and anomaly detection. Completeness, consistency and accuracy are different properties; a syntactically valid value can still be wrong. Useful for explicit data contracts and failed-check evidence. It does not establish point-in-time availability or prove that a provider-adjusted historical value was published at the decision date.

### R15 — Data Validation for Machine Learning

[Local paper](<D:/projects/systematic_trading/research/references/R15_data_validation_for_machine_learning.pdf>) · [Retrieved source](https://mlsys.org/Conferences/2019/doc/2019/167.pdf)

**Version:** Published, MLSys 2019. **Inspected PDF pages:** 2-3,7,10.

Examines data errors across training and serving pipelines, including failures hidden by acceptable aggregate model metrics. Uses schemas, distribution comparisons and model tests to make alerts actionable. Our application is parity of research and monitored feature contracts, with missingness and coverage checked by date and instrument. Detection of an anomaly is not authorization to fill, substitute or silently repair historical observations.

### R16 — Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019  Reproducibility Program)

[Local paper](<D:/projects/systematic_trading/research/references/R16_improving_reproducibility_in_machine_learning_research_a_report_from_the_neurips_2019_reproducibility_pro.pdf>) · [Retrieved source](https://jmlr.org/papers/volume22/20-303/20-303.pdf)

**Version:** Published, JMLR 2021. **Inspected PDF pages:** 3-4,12.

Reports the NeurIPS reproducibility program's code policy, challenge and checklist. It distinguishes reproducibility, replication, robustness and generalization and notes limits to causal claims about the program's effects. A completed checklist cannot itself establish correctness. For us, reproducible run artifacts and independent checks should accompany the exact hypothesis and data limitations.

### S02 — 多因子量化投资框架梳理

[Local paper](<D:/projects/systematic_trading/research/references/S02_multifactor_framework_20240222.pdf>) · [Retrieved source](https://upfile.haotouxt.com/1723536616345/20240222-%E6%B5%99%E5%95%86%E8%AF%81%E5%88%B8-%E9%87%91%E8%9E%8D%E5%B7%A5%E7%A8%8B%E6%B7%B1%E5%BA%A6%EF%BC%9A%E5%A4%9A%E5%9B%A0%E5%AD%90%E9%87%8F%E5%8C%96%E6%8A%95%E8%B5%84%E6%A1%86%E6%9E%B6%E6%A2%B3%E7%90%86.pdf?1723536616581=)

**Version:** 浙商证券研究所, 陈奥林, 2024-02-22, 21 pages. **Inspected PDF pages:** 2,4-6,8-9,11,17-18.

A practitioner overview of the pipeline from data through factors, portfolio construction, execution and monitoring. Its examples show that the same factor can behave differently in all-A-share and large-stock universes. IC-based information ratios and portfolio active-return information ratios should not be confused. The report lists interpolation/filling and discretionary adjustments; these are general practices, not approved methods under this repository's audited-input and frozen-strategy rules.

### N01 — Revised Guidance on Model Risk Management SR 26-2

[Local paper](<D:/projects/systematic_trading/research/references/N01_revised_guidance_on_model_risk_management_sr_26_2.pdf>) · [Retrieved source](https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf)

**Version:** Federal Reserve/OCC/FDIC SR 26-2 attachment, April 17, 2026. **Inspected PDF pages:** 1-2,6-7.

Supervisory guidance for banking organizations emphasizes model purpose, proportionate development/testing, validation, limitations and ongoing monitoring. It is a governance reference, not evidence of momentum profitability or a declaration that this personal project has bank regulatory obligations. Borrow the discipline of documented intended use and review when changing the use of a model.

### N02 — GIPS Sample Error Correction Policy for Firms

[Local paper](<D:/projects/systematic_trading/research/references/N02_gips_sample_error_correction_policy_for_firms.pdf>) · [Retrieved source](https://www.gipsstandards.org/wp-content/uploads/2025/04/sample_error_correction_policy_firms-1.pdf)

**Version:** CFA Institute sample policy, copyright 2021; URL directory year is not publication year. **Inspected PDF pages:** 2-3,6.

A sample policy for correcting errors in GIPS reports, including materiality, corrected reports and incident records. The sample's particular thresholds and organization are illustrative. We can use the idea of a correction ledger and linking replaced claims to corrected evidence. This does not establish or claim GIPS compliance for our project.

## Remaining reading and access work

- S01/S03 collection is deferred by user instruction; they were not read as original reports and their claims are excluded.
- Unnamed citations are also deferred. Resolve their identities only if a later agreed study needs their specific claims.
- Before implementing a shortlisted method, check its complete equations/appendices and reconcile working-paper versus final-publication differences. M03 is an especially early version.
- Any replication code and supplementary datasets would require their own identity, license and data-contract review. No online factor returns or provider price archives were admitted as research inputs in this session.
