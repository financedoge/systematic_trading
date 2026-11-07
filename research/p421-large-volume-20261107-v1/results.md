# Five large volume discrepancies

The five frozen cases are fully reconciled. Alpaca's retained trades reproduce
its daily bars exactly in all five cases. Independent IBKR full-day ticks agree
in three cases and contain additional activity in two FIX cases. This evidence
does not support replacing the existing volume history with one provider.

| Stock / date | Published volume | Alpaca eligible shares | IBKR shares | IBKR minus Alpaca |
| --- | ---: | ---: | ---: | ---: |
| RPM 2024-04-29 | 364,400 | 405,083 | 405,083 | 0 |
| UTHR 2024-06-25 | 523,500 | 562,256 | 562,256 | 0 |
| UTHR 2024-06-21 | 1,800,900 | 1,851,871 | 1,851,871 | 0 |
| FIX 2025-02-07 | 407,500 | 401,164 | 407,523 | 6,359 |
| FIX 2025-02-04 | 288,900 | 285,817 | 288,935 | 3,118 |

The cases were selected by the largest absolute percentage volume residuals in
the completed ten-stock pilot, before these trade downloads. They are targeted
diagnostics, not a random validation sample or an acceptance threshold.

Ten Alpaca responses retain 72,577 trade/reference records. Eighty-six IBKR
responses retain 72,839 in-day ticks plus 5,020 backward boundary-control ticks.
Every case has a terminal forward page and an exact backward-tail multiset
check; no out-of-day ticks enter the totals. All five unflagged IBKR regular-hours
sums reproduce the earlier broker daily bars. The initial unavailable-Gateway
failure remains archived; the operator subsequently opened the paper Gateway.

RPM and UTHR June 21 match on exact price/size/condition multisets and clock
buckets. UTHR June 25 matches volume, condition/size and clock buckets, with two
small-price representation differences covering five shares retained unchanged.
The FIX condition/size multisets contain 191 and 115 extra IBKR occurrences.
Exact-price differences are also retained; they must not be mistaken for all of
the missing volume or treated as unique cross-provider trade identifiers.

The [independent CRSP comparison](../p421-crsp-qualification-20261107-v1/results.md)
agrees with IBKR on both FIX daily totals. A subsequent, separately frozen
[three-minute query](../p421-fix-minute-gaps-20261107-v1/results.md) reproduces the
original Alpaca records exactly and localizes the net gaps. Upstream correction
timing or provider capture rules remain unproven. Missing update flags do not
certify absence of historical corrections.

Five observations and two documents were published under the isolated
`governance/pilots/p421-large-volume-v1` source, with exact native-store hash
readback. The publication is field-audit evidence only; historical availability
is null. No catalog admission, source substitution, strategy replay or investment
decision occurred. A weakest-ETF trade chart is inapplicable to this data-only
check. Preserve local source archives while qualification remains active.

[Protocol](protocol.json) · [Assessment](assessment.json) ·
[Publication receipt](publication.json) · [Acceptance](acceptance.json) ·
[Artifact hashes](artifact-manifest.json).
