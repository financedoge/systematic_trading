# CSL full-day trade reconciliation — November 7, 2026

**Complete for CSL on February 24, 2025. Both sources reconstruct exactly 413,821
shares of eligible full-day activity. The tested daily/minute volume gaps are
fully accounted for by trade eligibility and bar emission. This does not qualify
the wider history or authorize a publication. Stop for operator discussion.**

The operator authorized this one-day follow-up after the frozen 50-stock-day bar
comparison. We queried the full New York calendar day, retained raw responses
locally, and reused the existing archived bars and pinned published comparison.
No strategy performance was evaluated and no replacement data was published.

| Full-day source or reconstruction | Shares |
| --- | ---: |
| Alpaca eligible SIP trade records | **413,821** |
| IBKR all historical trade ticks | **413,821** |
| Alpaca daily bar | **413,821** |
| Existing published daily history | 413,800 |
| Sum of Alpaca returned minute bars | 377,382 |
| IBKR ticks without its `unreported` flag | 223,314 |
| IBKR all-hours minute bars | 223,314 |
| IBKR all-hours daily bar | 223,314 |
| IBKR regular-hours daily bar | 179,315 |

The 21-share published-history residual is compatible with nearest-100 rounding
for this day. It is not exact agreement and is not a new qualification tolerance;
the preceding sample still has 14/50 exceptions to that rounding explanation.

The full-day IBKR bar gap decomposes exactly:

| Eligible tick volume excluded from IBKR bars | Shares |
| --- | ---: |
| Odd lots, condition `I` | 162,920 |
| Average-price trades, condition `B`, including `4+B` | 6,501 |
| Extended-hours prior-reference-price trades, `T+P` | 21,086 |
| Total excluded | **190,507** |
| Retained in all-hours bars | **223,314** |
| Full activity | **413,821** |

All 931 returned IBKR minute bars, including provider-supplied zero-volume bars,
match the corresponding sum of ticks without the vendor flag. The flag coincided
with odd lots in the earlier 33-minute sample; the full day reveals 71 additional
non-odd-lot records totaling 27,587 shares. This explicitly refines the short-sample
inference. `unreported` is IBKR's classification, not proof that a trade was absent
from the consolidated tape. Its historical-data documentation also describes
trade filtering. [IBKR limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations).

Alpaca's 242 returned minute bars each match the eligible trade volume exactly.
Another 205 minutes contain 36,439 eligible shares but no price-eligible trade.
Those minutes have no returned OHLC bar:

`377,382 observed-minute shares + 36,439 absent-minute shares = 413,821 daily shares`.

This is consistent with Alpaca's documented rule that a bar is emitted only when
all OHLC and volume fields are nonzero. Volume-only trades can therefore contribute
to a daily bar while their individual minute has no bar. Do not replace missing
bars with invented prices or treat their absence as zero trading activity.
[Alpaca aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq).

| New York clock bucket | Alpaca eligible trades | IBKR all ticks | IBKR unflagged ticks |
| --- | ---: | ---: | ---: |
| Before 09:30 | 689 | 689 | 200 |
| 09:30 inclusive to 16:00 exclusive | 347,278 | 347,278 | 179,315 |
| 16:00 minute | 53,904 | 53,904 | 43,799 |
| 16:01 onward | 11,950 | 11,950 | 0 |

These clock bins match exactly across both sources. They do not establish the
original execution clock for every late or prior-reference-price report. The
43,799-share close trade contributes to the 16:00 bucket; simply cutting the day
at 16:00 would change the activity definition.

Alpaca returned 14,681 records. Twelve are official price-reference records
(`Q`, `M`, `9`), whose sizes total 177,835 but do not count toward volume. Three
have size zero. The remaining **14,669 eligible records** match IBKR's **14,669
in-day ticks** in total count, volume and the multiset of condition combinations
and trade sizes. Blindly summing every Alpaca record would give 591,656 shares and
double-count price-reference information.

All returned Alpaca update flags are absent: the snapshot contains no records
labelled canceled, incorrect or corrected. The analysis explicitly excludes
canceled/incorrect records and retains corrected ones when present. This result
cannot prove that no historical correction occurred or identify when a revision
became available. [Historical trade fields](https://docs.alpaca.markets/us/reference/stocktradesingle-1).

Exact second/price/size matching, preserving repeated occurrences, matches 14,505
records and 403,843 shares. The remaining 164 occurrences contain 9,978 shares on
each side. Exploratory diagnostics identify 153 same-price/size occurrences
(9,898 shares) with IBKR one second later, and 11 same-second/size occurrences
(80 shares) with IBKR's price $0.0001 higher. These patterns explain the remaining
coarse comparison differences; they do not change the primary exact-match result,
create a tolerance, establish which clock/price is correct, or prove unique trade
identity. IBKR exposes neither an exchange trade ID nor nanosecond timestamps.
The source prices and timestamps remain unchanged.

Both sources' first trade falls at 04:01:12 New York and last at 19:06:22. Alpaca
completed two trade pages using its explicit next-page token. IBKR completed 15
nonempty forward pages, followed by an empty completed response. A separate
1,001-tick backward request exactly matches the full multiset of the ending
seconds in the forward capture. Paging advances only after each completed whole
second; identical-looking ticks within a page are preserved. This is documented
endpoint exhaustion and boundary evidence, not an independent full-tape guarantee.
[IBKR historical ticks](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-ticks).

Two acquisition details are retained transparently. The first Alpaca validator
incorrectly required strictly positive size for price-reference markers; the
complete saved responses passed a corrected, tested validator without another
download. The original failed-validation manifest and executed runner remain.
IBKR reported a historical-farm disconnection/recovery during page three. A new
connection resumed from the verified next second, preserving the first two pages
and failed request. No completed data page was fetched again. One of the two
predeclared recovery connections was used.

Raw responses, metadata, queries, timestamps, executed code and hashes remain in:

- `D:/systematic_trading_data/source-archives/alpaca/csl-trades-20261107T114452061078Z`
- `D:/systematic_trading_data/source-archives/ibkr/csl-trades-20261107T114452242849Z`
- `D:/systematic_trading_data/source-archives/ibkr/csl-trades-20261107T114711070054Z`

All 22 new response payloads verify, including failures and the independent tail
check. The prior 18 payloads and pinned publication comparison were also rechecked.
Detailed minute differences stay in `full-day-reconciliation.json` inside the
Alpaca archive; compact results are retained here. Credentials remained in the
ignored `.env`; no keys were copied or logged. Paper-only account checks and the
read-only order guard were retained. Twenty-three focused tests and Ruff pass.
No subscriptions, registered assets, shared providers or trading settings changed.

Replay without network access:

```powershell
.venv\Scripts\python.exe scripts/reconcile_csl_trades.py D:/systematic_trading_data/source-archives/alpaca/csl-trades-20261107T114452061078Z D:/systematic_trading_data/source-archives/ibkr/csl-trades-20261107T114711070054Z
```

**Decision for discussion:** the large CSL bar-volume discrepancy is explained;
there is no basis to overwrite the database with IBKR bar volume. Existing IBKR
tick access is useful for consolidated-activity reconciliation, and Alpaca daily
SIP volume is corroborated on this day. Retain both as source evidence.

**Proposed next item:** extend the frozen daily-activity reconciliation to the
14 stock-days that did not match nearest-100 rounding in the original sample,
with exact residuals and no fitted acceptance threshold. Use the same documented
condition rules and retain the original controls. Then decide field-specific
qualification and publication. Broader identity/action coverage and historical
availability remain separate gates; one matching day does not certify a universe.

[Frozen protocol](protocol.json) · [Condition rules](condition-rules.json) ·
[Validation correction](validation-amendment.json) · [IBKR recovery](ibkr-recovery.json) ·
[Exploratory residual declaration](residual-diagnostic-declaration.json) ·
[Assessment](assessment.json).
