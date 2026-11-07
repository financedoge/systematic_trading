# Alpaca SIP sample and IBKR access — November 7, 2026

**The bounded source comparison is complete. Both Alpaca historical SIP bars and
IBKR older historical ticks/bars are accessible. Volume qualification remains
open; no new data has been published or used in a strategy replay. Stop for the
operator discussion before the next acquisition item.**

Used the operator's existing `ST_ALPACA_MARKET_API_KEY` and
`ST_ALPACA_MARKET_API_SECRET` in the ignored `.env`, without displaying values or
copying them into another credential file. The frozen sample is CSL, WSO, MANH,
RPM, UTHR, XPO, FIX, FLEX, CASY and RS across February 24–28, 2025. Alpaca returned
50 daily bars and 13,878 minute bars, with complete pagination and all 50 stock-days.
Requests explicitly selected SIP, raw prices/volume and literal historical tickers
(`asof=-`). These are source-inspection observations, not admitted research inputs.

| Comparison against the pinned published histories | Result |
| --- | ---: |
| Closes within $0.005 | 50 / 50 |
| Largest absolute close difference | $0.00001465 |
| Exact daily-volume matches | 0 / 50 |
| Median absolute daily-volume difference | 0.006373% |
| Largest relative daily-volume difference | 0.049799% |
| Largest absolute daily-volume difference | 184 shares |
| Matches after rounding Alpaca volume to nearest 100 | 36 / 50 |
| Sum of returned minute volume / daily volume | 75.7681%–99.9435% |

The daily volumes are close, but not identical. Rounding is compatible with 36
comparisons and leaves 14 exceptions; it is not a complete explanation. No new
acceptance tolerance was chosen after seeing the results. Provider agreement can
also share upstream feed lineage and does not independently certify every input.

The largest relative discrepancy is CSL on February 26: 249,124 Alpaca shares
versus 249,000 published shares. The original diagnostic day, CSL on February 24,
shows why the minute-bar and daily-volume contracts must be kept separate:

| CSL, February 24, 2025 | Volume, shares |
| --- | ---: |
| Published daily history | 413,800 |
| Alpaca SIP daily | 413,821 |
| Sum of all returned Alpaca minutes | 377,382 |
| IBKR regular-hours daily bar | 179,315 |
| IBKR all-hours daily bar | 223,314 |

Alpaca's 242 observed minutes contain 488 shares before 09:30, 322,990 from 09:30
until before 16:00, and 53,904 in the 16:00 minute, New York time. The daily total is
36,439 shares above those observed minutes. A clock bucket is not a certification
of auction or late-report conditions. Missing minutes remain absent.

The predeclared IBKR 1,000-tick access request returned 1,004 ticks, completing the
last second. Inspecting only its 33 complete minutes, 09:30 inclusive to 10:03
exclusive on February 24, gives a direct diagnostic:

| Same 33-minute interval | Volume, shares |
| --- | ---: |
| All IBKR historical ticks, 964 trades | 24,441 |
| IBKR ticks without its `unreported` flag | 12,918 |
| IBKR historical minute bars | 12,918 |
| Alpaca's 23 observed minute bars | 22,138 |
| IBKR ticks in the ten minutes absent from Alpaca bars | 2,303 |

All 23 common-minute volumes match exactly between Alpaca bars and all IBKR
ticks. Every IBKR tick in the ten missing Alpaca minutes is flagged; across the
entire 1,004-tick page, the flag coincides exactly with condition `I` (odd lot).
Thus IBKR's bar total equals the tick total after excluding these flagged trades,
while Alpaca's returned bars include their volume. The missing-minute pattern is
consistent with minutes containing no price-eligible trades. This is an observed
aggregation identity for this interval, not proof of the full-day algorithm or
its applicability to other securities. IBKR's `unreported` label does not mean
the trade was absent from the consolidated tape.

Alpaca documents different trade-condition rules for price and volume, including
odd lots contributing volume without updating prices. IBKR separately documents
historical-bar trade filtering. These contracts support examining eligibility and
aggregation before treating lower volume as a broken database or missing paid
subscription. [Alpaca aggregation FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
[IBKR historical-data limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations).

The IBKR retry also returned five regular-hours daily bars, five all-hours daily
bars and 931 all-hours minute bars. All four historical requests completed;
warning 2188 concerns up-to-the-second access and did not prevent the older data.
Frozen quote requests for MANH and SPY explicitly returned 10089, requiring
additional API data permission; CSL returned neither ticks nor an explicit
denial. Billing packages were not inspected. The initial session/IP errors did
not recur; the operator reports no other live session, and the reason they cleared
is unknown. No subscription or session-sharing settings were changed.
[Full IBKR recheck](ibkr-recheck.md).

Acquisition initially encountered connection timeouts. The complete sample used
the existing localhost:7892 proxy with IPv4 and verified HTTPS; each successful
page took one transport attempt. Bounded retries were available but are not an
established cause of recovery. No TLS bypass, redirects, global network changes
or alternate-feed substitution occurred. [Transport receipts](transport-recovery.json).

All responses, including failures, remain under
`D:/systematic_trading_data/source-archives/alpaca` and `.../ibkr`, outside Git.
The final sample is `alpaca/sample-20261107T105628852021Z`; successful IBKR ticks
and bars are `ibkr/access-20261107T104817113627Z` and
`ibkr/access-20261107T105031824028Z`. Eighteen payload hashes and row counts across
ten acquisition attempts verify, together with the executed runner copies.
The comparison rechecks pinned publication batch
`ebffbedaaf8ae35bd5654887f83459156abff13d12537b2bd614e593c64ee77d` and the original
IBKR comparison manifest. Its source-level rows stay in the local archive.

Replay this assessment without new network requests:

```powershell
.venv\Scripts\python.exe scripts/assess_alpaca_ibkr_sources.py
```

Thirty-five focused tests pass; Ruff and whitespace checks pass. Asset-pool reuse
review and dependency preflight are retained in the original protocol. No shared
provider, strategy, broker guard or calculation changed. This is a data-contract
inspection, so portfolio selection and weakest-ETF performance charts do not apply.

**Proposed next item:** predeclare a complete-day CSL trade-level reconciliation
for February 24, 2025, comparing both sources' conditions, timestamps, corrections,
session boundaries and bar eligibility. Reconstruct volume without filling absent
bars; account for pagination and second boundaries. Discuss this finding before
starting that acquisition or expanding the historical database. Broader identity,
corporate-action, publication-availability and audit/publication checks remain open.
No new paid source is required for the next bounded access/coverage test; full-day
completeness has not yet been demonstrated.

[Frozen protocol](protocol.json) · [Input preflight](comparison-preflight.json) ·
[Pinned source receipts](source-inputs.json) · [Replayed assessment](assessment.json).
