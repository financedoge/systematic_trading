# Consolidated U.S. source alternatives — November 7, 2026

**Test Alpaca historical SIP access first. Massive is the clearest moderately
priced fallback. AlgoSeek offers useful daily session/FINRA breakdowns, but a
small daily extract needs separate pricing.** This online source-selection item
is complete; account access and data quality have not been tested.

We need an alternative vendor to the unavailable WRDS/NYSE TAQ entitlement.
Consolidated CTA/UTP coverage remains the requirement. The immediate question is
whether daily volume differences arise from venue, session or trade eligibility;
it does not require purchasing the entire TAQ archive or quote history.

| Candidate | Documented access/history | Fit and remaining checks |
| --- | --- | --- |
| Alpaca historical SIP | Basic is free, history since 2016, 200 historical calls/minute. The FAQ explicitly permits historical SIP when `end` is at least 15 minutes old. | Best first pilot for 2024–2025. Set `feed=sip` explicitly; a default or IEX response would be unsuitable. Verify account entitlement, dated identities, complete pagination, condition rules and historical cancellation/correction treatment. |
| Massive Stocks Developer | Listed individual price $79/month; historical trades included with ten years of history. Free and $29 Starter exclude this trades endpoint. | Useful paid fallback: trade conditions, correction indicator, exchange, SIP/participant timestamps and TRF identifiers. Establish correction/deduplication semantics before summing shares. |
| AlgoSeek daily OHLC, algoseek aggregation | SIP-derived daily data separately expose total, market-hours and FINRA volume. Its equities catalog advertises history from 2007. No price for the exact small daily extract was verified. | Potentially the smallest sufficient dataset. Select unadjusted full consolidated data and pin aggregation variant. The published full trade-and-quote offering is $1,500/month, which is unnecessary for an initial daily comparison. |

Alpaca's [plan table](https://docs.alpaca.markets/us/docs/about-market-data-api)
and [specific historical-access FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
support the free historical SIP route. The more general historical overview uses
looser subscription language, so an actual bounded account probe is still needed.
Recent SIP access and real-time streaming have different entitlements. The
[historical trades endpoint](https://docs.alpaca.markets/us/reference/stocktrades-1)
supports time-bounded retrieval; retrospective history is not evidence of what
the account could have seen at each historical decision time.

Massive's [trades specification and plan matrix](https://massive.com/docs/rest/stocks/trades-quotes/trades)
document the fields, access and history above. It supports pagination up to
50,000 records per page. Its [stocks overview](https://massive.com/stocks)
includes exchange and off-exchange/FINRA reporting coverage. Ten years on the
Developer plan covers our requested window; the product's longer overall archive
does not imply that all years are included in that plan. Prices are listed
individual-plan terms, not a quote for every license category.

AlgoSeek's [daily endpoint specification](https://algoseek.com/docs/rest-api/reference/endpoint-v-1-data-us-equity-daily-ohlc-identifier-get)
distinguishes algoseek and industry-standard aggregation and defaults to as-is
values. Its linked [field and calculation guide](https://us-equity-market-data-docs.s3.us-east-1.amazonaws.com/algoseek.US.Equity.algoseek.Daily.OHLC.Adjusted.Guide.pdf)
lists raw `DailyVolume`, `MarketHoursVolume`, `DailyFinraVolume` and
`MarketHoursFinraVolume`, alongside separate adjusted fields. It describes
cancellation filtering and auction/condition treatment. Some appendix labels
differ from the field table, so pin the delivered schema and exact rules rather
than guessing. Do not select an excluding-FINRA/TRF product or substitute the
separate industry-standard daily variant. The [pricing page](https://algoseek.com/pricing/)
lists the full TAQ product at $1,500/month and equities history from 2007; that
price is not the price of the bounded daily extract. Exact date/identifier access,
retention terms and extract pricing need confirmation before acquisition.

Databento is another possible vendor, but its [equities catalog](https://databento.com/equities)
separates proprietary-feed combinations and daily summary products. Full venue/TRF
coverage in our historical dates would require a dataset-specific check. It is
not the first small pilot. Tushare remains a daily cross-check candidate under the
[completed assessment](../p421-tushare-access-20261107-v1/results.md).

## Proposed next item

Reuse the [frozen source request](../p421-volume-contract-20261107-v1/source-request.json):
CSL, WSO, MANH, RPM, UTHR, XPO, FIX, FLEX, CASY and RS for February 24–28, 2025
(50 stock-days). Start with one symbol/day to verify access, feed identity and
response shape, then complete only that sample. Do not expand to the full
February 2024–February 2025 window until the sample has been reviewed.

Retrieve raw daily bars as a compact control and trade records only as needed to
explain session/condition differences. Preserve regular-hours and full-reporting-
day totals separately, including explicit handling of closing auctions, late
reports and cancellations/corrections. Retain all pages, token-free queries,
capture times, source/schema versions, row counts and hashes locally. Compare
against pinned published histories and existing IBKR evidence; do not overwrite
either series or infer a volume multiplier.

Documentation supports a candidate, not qualification. Matching vendors may
share upstream SIP lineage. Coverage, identities, volume eligibility and
historical availability still need separate evidence. Any accepted source must
pass audit/publication before strategy research. No new account, subscription,
vendor contact, market-data extraction, publication or strategy replay occurred
in this item. Pause for the source discussion before the next acquisition item;
the previously prepared CRSP comparison remains available as a separate control.
