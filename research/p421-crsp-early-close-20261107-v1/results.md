# UTHR early-close control

Alpaca and IBKR agree exactly on UTHR July 3, 2024: 7,635 eligible trades and
281,294 shares. Their price/size/condition multisets and all session clock
buckets match. The CRSP daily total differs. This establishes the disagreement,
not which upstream correction or aggregation rule caused it.

The case was frozen separately after the CRSP comparison identified it as the
largest absolute percentage discrepancy among identifier-qualified stock-days.
It is a diagnosed outlier, not a random control or new admission threshold.

The actual exchange session closed at 13:00 New York (17:00 UTC). Both captures
have 21 shares before the open, 187,797 during regular trading before that close,
63,913 in the closing minute, and 29,563 afterward. Thus an accidental 16:00
boundary in our diagnostic does not explain their full-day agreement or the
CRSP disagreement. The existing published total is six shares higher.

One Alpaca response contains 7,640 trade/reference records; five price/reference
markers are excluded by the frozen tape rules. IBKR has nine forward responses,
including the terminal empty page, and a 1,001-tick backward control that matches
exactly. No spill rows or forced clock alignment. Raw CRSP comparison values are
retained only in the licensed local archive.

One observation and two documents are published as isolated field-audit evidence
under `governance/pilots/p421-early-close-v1`, with exact native hash readback.
Historical availability remains null; the active catalog and strategy inputs
were not changed. This data-only check has no weakest-ETF trade chart. Source
archives remain protected for active qualification.

[Protocol](protocol.json) · [Calendar](calendar.json) · [Assessment](assessment.json) ·
[Publication receipt](publication.json) · [Acceptance](acceptance.json) ·
[Artifact hashes](artifact-manifest.json).
