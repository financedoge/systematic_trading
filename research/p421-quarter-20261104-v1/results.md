# Can we reconstruct the December 2024 ETF portfolios?

**The December 2024 qualification pilot is complete. Keep the P4.21 constituent-alpha backtest on hold.** We identified all 29 equity ETFs in the frozen 52-fund pool and found public December 31 portfolios for 16. Those 16 first qualify on the monthly schedule at the March 3, 2025 open. None reaches the earlier research reference of 95% of equity value and 70% of equity lines with complete price windows. The other 23 ETFs are bills, bonds and commodities, outside this equity-constituent pilot.

**MDY separates the price problem from the holdings problem.** Its filing supplies identifiers and tickers for all 401 common-equity positions. Of these, 67 have complete admitted histories, representing 17.92% of common-equity value. Another 325 positions, worth 80.56%, have price histories under review, and nine are unavailable. Collecting additional MDY filing dates would leave the December price gap in place.

## When the portfolios became public

The 2024 SEC registry identifies the registrant, series and share class for 27 funds. SPY and MDY are unit investment trusts. Their 2024 prospectuses establish the trading symbols, and their December filings agree on the registrant and investment-company file number. All 16 original XMLs match the expected fund identity and holdings date. Holdings for a multiclass fund belong to the series. [Fund inventory](funds.json) · [SEC series and classes](https://www.sec.gov/files/investment/data/other/investment-company-series-and-class-information/investment-company-series-class-2024.csv) · [SPY prospectus](https://www.sec.gov/Archives/edgar/data/884394/000119312524017688/d315180d497.htm) · [MDY prospectus](https://www.sec.gov/Archives/edgar/data/936958/000119312524017907/d657320d497.htm).

IAT and ITA appear in the February 24 daily EDGAR dissemination index, 55 days after December 31. The other 14 appear on February 27, 58 days after month-end. Each receipt records acceptance time in New York, original accession, source hashes, and the public feed row. A daily index establishes public presence by that day's end. We conservatively require a later market close and use the last completed New York session before each monthly decision. Zero December filings qualify on January 2 or February 3. All 16 qualify on March 3 using the February 28 close. The saved timestamps describe acceptance. The exact intraday dissemination time is unknown. All eight public N-PORT release indexes from 2024 Q4 through 2026 Q3 were searched for this reporting date and cohort. They contain 16 originals and zero amendments. [February 24 dissemination index](https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/master.20250224.idx) · [February 27 dissemination index](https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/master.20250227.idx) · [SEC N-PORT releases](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets).

**Thirteen funds have no December 31 public portfolio in those releases.** The first-quarter release instead has November 30 for EEM, EWA, EWC, EWG, EWH, EWJ, EWT, EWU, EWY, INDA and MCHI. EFA and VGK report January 31. They stay missing for the December comparison. Selecting each fund's most recent public portfolio at a decision would be a separate, explicitly age-limited policy. [Fund dates and accessions](index-2025q1.json).

## How much disclosed equity can be priced?

Each percentage uses the absolute USD value of **all** filed common or preferred equity positions in that fund. All 3,629 qualifying lines here were common equity. “Dated symbol” requires a unique same-date CUSIP or ISIN to ticker observation. “Complete window” additionally requires an admitted catalog entry and all 253 US sessions from February 27, 2024 through February 28, 2025 with positive, finite adjusted and raw OHLC and raw share volume. Each audit and bar file read was hash-verified against the pinned November 3 published catalog or its verified parent. The complete-window column is a diagnostic. The price-side identity and historical vintage still require certification.

| Fund | Public date in 2025 | Equity lines | Equity value with dated symbol | Lines with complete window | Equity value with complete window |
| --- | --- | ---: | ---: | ---: | ---: |
| IAT | Feb 24 | 34 | 83.37% | 1 | 3.65% |
| IBB | Feb 27 | 261 | 67.66% | 27 | 8.45% |
| ITA | Feb 24 | 35 | 50.76% | 5 | 6.68% |
| IWM | Feb 27 | 1,966 | 33.07% | 163 | 8.33% |
| MDY | Feb 27 | 401 | 100.00% | 67 | 17.92% |
| SOXX | Feb 27 | 30 | 54.16% | 1 | 1.01% |
| SPY | Feb 27 | 503 | 52.91% | 27 | 3.09% |
| XLB | Feb 27 | 28 | 28.23% | 2 | 5.90% |
| XLC | Feb 27 | 22 | 64.32% | 0 | 0.00% |
| XLE | Feb 27 | 22 | 78.94% | 1 | 3.00% |
| XLI | Feb 27 | 78 | 53.07% | 5 | 4.63% |
| XLK | Feb 27 | 69 | 49.89% | 7 | 7.46% |
| XLP | Feb 27 | 38 | 56.56% | 1 | 2.50% |
| XLU | Feb 27 | 31 | 66.61% | 1 | 6.04% |
| XLV | Feb 27 | 61 | 63.08% | 4 | 1.86% |
| XLY | Feb 27 | 50 | 54.11% | 3 | 7.51% |

Across these 16 funds, 1,612 of 3,629 equity lines have a dated candidate symbol and 315 have a complete window. A security held by two funds counts once in each. All unmatched holdings remain in their fund's denominator. Coverage can improve as more identities are resolved. XLC has zero complete matches among its 22 equities in this check, which says nothing about its investment performance.

For filings without an explicit ticker we linked the same instrument across available December filings or used the SEC's December 31 settlement-date CUSIP/symbol observations. A settlement file only covers securities with reported fails that day. Its exact historical public release timestamp is unknown here. Its only input to this diagnostic was the identifier pair. An ambiguous match, placeholder identifier or name-only resemblance supplies no link. We retained the evidence for each match. None of the 315 complete windows has a certified, effective-dated link from the security identifier to the governed price series throughout the lookback. **Replay-qualified coverage is therefore zero for this pilot.** The original price vintages, listing history, corporate actions and exits still matter for a historical replay. [SEC identifier source and scope](https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data) · [Line-level diagnostics](positions.jsonl.gz) · [Audited files, counts and values](qualification.json).

## Full-portfolio checks

The 16 schedules contain 3,687 positions. In addition to the equities, they include 34 short-term investments, 16 derivatives and eight other positions. The complete filed XML preserves cash, liabilities, rights, collateral and derivative detail. For each fund we reconciled total assets less liabilities to net assets within two cents. We also reconciled the sum of filed position weights to the sum of position values divided by NAV within 0.02 percentage points. Cash outside the schedule and the remaining net balance are reported separately. Differences between position value and NAV are retained. For example, SPY reports $1.925 billion of cash outside the investment schedule alongside a negative $1.785 billion remaining net balance. The missing 13 portfolios have unknown values. [Fund-level balances](qualification.json) · [SPY filing and source receipt](filings/0001752724-25-043826.json).

## Discussion point

Before a multiyear backfill, the bounded next item would be to inspect the existing audit failures for MDY's largest review-status holdings. This would separate repairable raw/adjusted data conflicts from cases that require another historical source or a dated security master. MDY makes that question measurable because its entire December equity portfolio has a disclosed ticker. The five largest review holdings by value were Williams-Sonoma, Illumina, EMCOR, Interactive Brokers and Pure Storage. The pilot ends here. No strategy was selected or traded.

## Verification and retention

The acquisition runner reads SEC registry, index and filing evidence. The qualification runner reads pinned governed prices and produces diagnostics at the prior close. Run the acquisition stage with `scripts/acquire_p421_quarter.py scan`, then `scripts/qualify_p421_quarter.py` in the project environment. The compressed originals, receipts, line-level results, catalog hashes and runners are retained as compact evidence. The separate download cache under `var/research/p421-quarter-20261104-v1` is eligible for routine retirement. The project’s canonical price publications remain protected. [Original coverage assessment](../p421-coverage-20261104-v1/results.md) · [Evidence hashes](artifact-manifest.json).
