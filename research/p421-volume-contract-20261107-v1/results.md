# Volume qualification: define coverage before changing data

November 7, 2026

The definition review is complete. The ten-stock discrepancy is not explained by our split reconstruction or a fixed shares/lots multiplier. Session coverage explains part of the difference; the remaining trade-coverage and unit semantics need a documented source. A proposed input contract and a 50-stock-day qualification request are ready. No new history or asset was published.

![Volume ratio comparison](volume-comparison.png)

| Stock | Median volume ratio | 1st–99th percentile ratio | 99th percentile error after fitted constant |
| --- | --- | --- | --- |
| CSL | 36.9% | 18.0%–55.9% | 58.8% |
| WSO | 31.5% | 14.2%–52.1% | 66.8% |
| MANH | 37.6% | 21.4%–66.9% | 77.7% |
| RPM | 43.7% | 20.0%–57.8% | 54.1% |
| UTHR | 35.5% | 13.4%–52.4% | 62.4% |
| XPO | 54.6% | 30.8%–69.3% | 43.6% |
| FIX | 38.0% | 21.6%–55.6% | 51.2% |
| FLEX | 68.7% | 37.0%–84.1% | 46.2% |
| CASY | 34.3% | 19.0%–49.6% | 45.8% |
| RS | 36.3% | 13.9%–56.1% | 65.0% |

## What we ruled out

All 2,530 matched published rows have split multiplier one and raw volume equal to source volume. The dates align exactly. Our split-reconstruction arithmetic therefore does not create this gap. The fixed 0.01, 1 and 100 multiplier checks do not reconcile the series. Even fitting a separate constant to each stock leaves 99th-percentile absolute relative discrepancies of 43.6%–77.7%. That fitted scale is diagnostic only; it was never applied to the database. The result does not prove every corporate action in the source ledger is correct.

## What session coverage explains

The existing all-hours controls for CSL, WSO and XPO are larger than the regular-hours values on every one of their 759 observations, and still below the published values on every observation. Their median ratios rise to 54.0%, 49.8% and 68.7%. Even after median scaling, their all-hours 99th-percentile discrepancies remain 24.0%–51.6%. We retain the source values and do not infer an undocumented unit conversion.

## Why price agreement cannot validate volume

Price and volume can legitimately count different trades. The UTDF specification describes a closing consolidated volume that includes pre- and post-market activity; it can exist without a regular-session last sale. Massive documents separate condition rules for price and volume, including a condition that updates volume without updating price. These definitions establish why matching closes cannot certify matching volume; they do not certify our Yahoo or IBKR captures.

[UTDF specification 14.4, November 2015](https://www.utpplan.com/DOC/utdfspecification.pdf) · [Massive aggregate condition rules](https://massive.com/knowledge-base/article/how-does-massive-create-the-open-high-low-close-volume-aggregate-bars)

## The proposed activity definition

Use unadjusted consolidated share volume for the completed tape reporting day, with explicit historical session hours and eligible exchange/off-exchange trades. Preserve the source rules for auctions, odd lots, corrections and cancellations. Pair it with the same activity-date audited raw regular-session close. Close times volume remains an activity proxy, not actual traded dollar value or net capital flow. A regular-session consolidated series can be a separate control; filtered broker history is not silently substituted for either series.

## A necessary timing rule

Keep the frozen preceding-close information cutoff. Full-session volume including after-hours trading is not available at that same close. For the March 3, 2025 decision with a February 28 16:00 New York cutoff, February 28 full-session volume is ineligible. February 27 is only a candidate if its publication and capture timestamps support the cutoff. Use the latest genuinely available complete price/volume pair and shift the whole activity stencil and matching return direction together. A November 2026 download cannot establish actual March 2025 availability. Any retrospective availability assumption must be declared separately.

## Asset reuse and implementation boundary

The new catalog search found activity-raw-v1 and activity-audited-lag20-v1, plus related legacy signals. Their pinned definitions were inspected. The existing raw asset certifies its frozen raw-basis contract, not a new full-universe consolidated-coverage claim. This item reused GovernedInputs, calendar/audit utilities and the repaired verified HTTP reader for inspection. It changed no registered asset, composite, shared service, runtime fingerprint or calculation. A future consolidated-activity version needs pinned inputs, a reuse review and a monitoring contract before a tracked composite can demand it.

## Source access and the next concrete action

Four bounded Nasdaq requests for February 24–28, 2025 returned no rows (CSL, WSO, XPO, MANH); the recent CSL control returned three rows. These results establish the tested requests, not a general historical retention limit. NYSE Daily TAQ and a documented SIP-based vendor are routes to investigate for a matching source; product documentation alone does not qualify a dataset. The prepared request is the ten frozen identities over five dates (50 stock-days), plus three previously observed price exceptions. Establish existing access or obtain a bounded evaluation extract, check its definitions, and then decide whether to expand acquisition. No purchase, subscription or provider contact was made.

[NYSE historical data — Daily TAQ](https://www.nyse.com/market-data/historical/)

## Status and limitations

This completes the volume-definition item and stops for operator discussion. Closing-price corroboration remains useful; volume eligibility, security continuity, historical availability and previous source reviews remain unresolved. No portfolio policy or performance result was calculated, so a weakest-ETF trading inspection does not apply. Thirty-two focused tests passed, including missing/invalid ratios, time-varying versus constant scales, and future/naive-timestamp rejection. Dependency contract preflight passed. Compact findings, contracts, hashes and runners are retained; small public probe caches and the rendered chart are disposable after closure. The earlier protected broker evidence retains its existing retention status.

[Field contract](field-contract.json) · [Prepared data request](source-request.json) · [Detailed diagnostics](assessment.json) · [Asset reuse review](reuse-review.json) · [Source references](sources.json) · [Artifact hashes](artifact-manifest.json)
