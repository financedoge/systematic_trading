# IBKR API access recheck — November 7, 2026

**Older historical ticks and bars now work through the existing paper Gateway.
The earlier session/IP messages did not recur. Frozen quotes for MANH and SPY
still require additional API market-data permission; billing packages were not
inspected.** The operator reports no other live session open. We did not change
subscriptions, terminate broker sessions or alter paper-sharing settings.

| Successful retry request | Result |
| --- | --- |
| CSL historical trades from February 24, 2025, 09:30 New York | 1,004 ticks; completion callback received |
| CSL regular-hours daily, February 24–28 | 5 bars; complete |
| CSL all-hours daily, February 24–28 | 5 bars; complete |
| CSL all-hours minutes, February 24 | 931 bars; complete |
| MANH and SPY frozen quotes | No ticks; explicit 10089 additional API subscription response |
| CSL frozen quote | No ticks or explicit denial within bounded wait |

Warning 2188 accompanies the successful historical requests and refers to
up-to-the-second access. It is not a failure of the returned older history.
Provider-supplied zero-volume minute bars were preserved; none were manufactured.
Historical ticks retain timestamp, price, size, exchange, special conditions and
the vendor flags. The 1,000 requested ticks extend to 1,004 to finish the final
second, as allowed by IBKR's historical-tick contract.
[Official historical-tick documentation](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-ticks).

For the 33 complete minutes in this tick page, total trade volume is 24,441 shares.
Removing the 11,523 shares flagged `unreported` leaves 12,918, exactly the IBKR
historical-minute total. The flag coincides with odd-lot condition `I` throughout
this sample. It is a vendor classification, not proof of absence from the tape.
This evidence supports investigating trade eligibility/aggregation as a cause of
the volume gap. It does not certify a full day or establish historical corrections.
[Matched Alpaca diagnostic and limitations](results.md).

Initial attempts, retained as historical access evidence:

| Initial request | Observed response |
| --- | --- |
| MANH frozen quote | 10197, competing live session; no quote rows |
| CSL regular daily retry | Timed out after 40 seconds; no completion or explicit entitlement error |
| Separate CSL historical-tick probe | 10187, specifically reporting a trading TWS session on a different IP; zero rows |

These earlier responses do not establish that another session was actually open
or that the operator lacks paid data. The later successful retries supersede the
access blockage; the reason for the change is unknown. Exact live-username
subscription and paper-sharing coverage remains unverified. Current 10089 quote
responses establish only the tested API entitlement limitation.

The earlier 23 captured IBKR series, including 2,530 primary matched stock-days,
remain valid evidence. Historical bars can filter trade classes even with paid
access. Buying data permissions is not by itself a solution to a mismatched volume
definition. [IBKR historical-data limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations),
[IBKR third-party subscription FAQ](https://www.interactivebrokers.com/docs/third-party-integrations/general-third-party-frequently-asked-questions).

Four access-attempt folders retain twelve compressed payloads and executed runner
copies under `D:/systematic_trading_data/source-archives/ibkr`. All hashes and
counts verify; the two successful attempts contain 1,945 market rows. Dedicated
client 29408 used verified paper accounts on port 4002, with orders blocked and
regulatory snapshots disabled. No publication or strategy replay.

[Declared requests](ibkr-recheck-protocol.json) ·
[Initial attempt receipts](ibkr-access-assessment.json) ·
[Final assessment and all receipts](assessment.json).

This bounded recheck is complete. Discuss the proposed full-day trade-level
reconciliation before acquiring more data.
