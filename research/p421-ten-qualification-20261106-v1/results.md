# Ten MDY histories — qualification result

**The ten holdings passed the identity-anchor and numerical consistency checks. Zero histories qualified for a new publication.** Together they represent 5.35% of MDY's December 31, 2024 equity value. Independent daily prices and volume remain unavailable for the required February 27, 2024–February 28, 2025 window, and the earlier source reviews remain unresolved.

The operator authorized the ten selected in the previous inventory. We retained that selection and the original November 3 catalog and verified parent. All ten have 253 supported raw/adjusted OHLC and raw-volume observations. The September and November publications agree on raw OHLC for all ten and raw volume for eight. The earlier publication withheld raw volume for WSO and XPO. Their newer captures contain volume but retain review status, so those two lack an earlier raw-volume comparison. Adjacent adjusted-close log-return differences are below 0.006 basis points. These captures come from the same provider. They establish numerical stability across captures.

**The security evidence improved.** We retrieved and checked 20 SEC periodic filings, choosing the last 10-K or 10-Q published by each of two cutoffs, February 27, 2024 and February 27, 2025. All filings match the expected registrant CIK and list the expected ticker and share class. Separately, all ten ISINs from the December portfolio resolved through the application's paper-broker identity verifier to a unique matching USD stock contract on the expected exchange. Watsco's filing lists WSO common and WSOB Class B separately. The lookup matched the ISIN filed for WSO. FLEX uses its filed Singapore ISIN.

The filing anchors and current broker lookup are dated observations. A certified record of security continuity and corporate actions throughout the historical interval remains open. The current broker response dates from November 2026. It cannot establish what a March 2025 strategy knew. [Broker identity receipts](ib-contracts.json).

**All ten December valuation checks agree to the cent.** The values below are the filed market value divided by the filed share balance. They match the governed raw close on December 31. The 24 provider dividend events recorded inside the window pass the existing internal adjustment audit, and that ledger records zero splits in the window. Verification of event terms against an independent history remains part of qualification.

| Stock | Share of MDY equities | Filed USD value per share | Provider dividends in window | SEC identity filing dates |
| --- | ---: | ---: | ---: | --- |
| CSL | 0.573% | 368.84 | 4 | 2024-02-16 / 2025-02-14 |
| WSO | 0.567% | 473.89 | 4 | 2024-02-23 / 2024-11-01 |
| MANH | 0.567% | 270.24 | 0 | 2024-02-06 / 2025-02-07 |
| RPM | 0.544% | 123.06 | 4 | 2024-01-04 / 2025-01-07 |
| UTHR | 0.541% | 352.84 | 0 | 2024-02-21 / 2025-02-26 |
| XPO | 0.524% | 131.15 | 0 | 2024-02-08 / 2025-02-07 |
| FIX | 0.517% | 424.06 | 4 | 2024-02-22 / 2025-02-20 |
| FLEX | 0.511% | 38.39 | 0 | 2024-02-02 / 2025-01-31 |
| CASY | 0.505% | 396.23 | 4 | 2023-12-11 / 2024-12-09 |
| RS | 0.500% | 269.26 | 4 | 2023-11-02 / 2025-02-27 |

The dollar checks cover one date. They provide no independent daily volume comparison. Full event dates, amounts, price-file hashes and validation outcomes are retained. [Detailed assessment](assessment.json).

**The independent data requests hit a specific access problem.** The configured IBKR paper gateway was reachable, and the ISIN contract lookups succeeded. Its CSL historical-data request failed with error 162 reporting that the trading TWS session was connected from a different IP address. The failed request returned zero observations. The error receipt is included in the assessment. A question about releasing the other session was sent to the operator during the work.

A separate public Nasdaq check returned zero rows for the required CSL and MANH windows. A recent-date CSL control returned three rows, demonstrating that the endpoint responded to a supported request. This establishes the outcome of these queries, without establishing a general retention limit. A Stooq download attempt returned a browser-verification page. The application's primary end-of-day provider/key configuration supplies no additional configured source. [Captured Nasdaq request results](acquisition.json).

**The older source disagreements remain open.** MANH and UTHR have volume-only failures in the earlier audit. The other eight also have earlier adjusted-price disagreements. All recorded failing dates and failed volume-comparison intervals precede this pilot window. Some source differences involve price adjustment and some involve volume conventions. Their age alone does not resolve them or supply an independent check within the window. The assessment retains each affected pair and date range. It makes zero new source dispositions.

**The next practical step is historical-data access.** Once IBKR can return history, acquire the ten instruments over the specified 253 sessions and reconcile them against the published bars. Keep the original broker contract IDs, source timestamp, price basis, volume units and session definition. An independent provider may filter trades or aggregate sessions differently, so a disagreement needs field-specific examination. If IBKR cannot supply the window, request the same bounded extract from another documented source. The request is ten instruments by 253 sessions, with the action and identity evidence needed to interpret those bars. [Prepared data request](historical-data-request.json).

This closes the evidence-check portion of the pilot and stops for discussion. New publication and the constituent-alpha replay remain blocked. Nineteen focused tests passed. Prior records, original filing hashes, identifiers, denominator, all table values and current receipt hashes were checked. The evidence folder contains compact records and the runner. The downloaded filing cache is inspection material eligible for routine retirement after its findings and receipts are retained. Private broker receipts remain protected evidence.

[CSL filings](issuers/CSL.json) · [WSO filings](issuers/WSO.json) · [MANH filings](issuers/MANH.json) · [RPM filings](issuers/RPM.json) · [UTHR filings](issuers/UTHR.json) · [XPO filings](issuers/XPO.json) · [FIX filings](issuers/FIX.json) · [FLEX filings](issuers/FLEX.json) · [CASY filings](issuers/CASY.json) · [RS filings](issuers/RS.json)

[Previous weighted inventory](../p421-mdy-inventory-20261105-v1/results.md) · [Artifact hashes](artifact-manifest.json).
