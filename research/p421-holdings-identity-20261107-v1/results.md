# Dated identifiers and mixed receipt dates

After checkpoint commit `18061ce` was pushed, this separately frozen check
corroborated nine additional MDY positions. The December 2024 control now has
391 of 401 filed equity positions matched by supported identifiers; all nine new
pairs agree exactly on share count and market value. Ten foreign identifier
bridges remain open. This improves identity evidence without admitting a new
historical strategy input.

VNOM's mismatch is explained by its November 13, 2023 conversion from a limited
partnership into a corporation. Nasdaq announced the CUSIP change from 92763M105
to 927959106, with the ticker retained. The dated CRSP stock-security intervals
switch on exactly that boundary and agree with the CUSIP in the December 2024
SEC filing. The CRSP mutual-fund holding still carries the older CUSIP. The
audit records that stale identifier and its supported transition; it does not
rewrite the source row or use ticker equality as the identity test.
[Nasdaq conversion notice](https://nasdaqtrader.com/TraderNews.aspx?id=ECA2023-653).

Eight other positions are corroborated using documented numbering rules for
Bermuda, Cayman Islands and British Virgin Islands. Their filed ISINs embed a
CUSIP/CINS; both check digits, the original holding identifier, and unique dated
CRSP security intervals agree. These positions are AXTA, CPRI, ESNT, FN, G, RNR,
ROIV and VAL. The earlier US-only audit remains frozen; this is a new, explicitly
scoped check with retained primary documentation.
[Bermuda numbering agency](https://www.bsx.com/numbering-services) ·
[Cayman/BVI numbering agency](https://www.csx.ky/isin/isin-cusip.asp) ·
[CGS identifier structure](https://www.cusip.com/identifiers.html?section=ISIN).

The remaining equity bridges are ALTM, CNH, FLEX, JAZZ, JHG, LIVN, NVT, PRGO, ST
and WFRD. Their other national identifier formats are not silently interpreted
as CUSIPs. The extra CRSP cash row remains separate from the 401 filed equities.
Effective security dates and structural identifier rules do not establish the
historical dissemination of today's vendor dataset.

The mixed-receipt control was selected prospectively as the largest receipt-date
span in the earlier 2,012-snapshot coverage extract: VGK, January 31, 2022.
Its 1,371 current holdings rows reproduce all three earlier coverage groups:

| Vendor receipt date | Rows | Sum of reported percent TNA |
| --- | ---: | ---: |
| 2022-02-21 | 1,367 | 99.59997037 |
| 2022-03-21 | 2 | 0.019999996 |
| 2022-04-07 | 2 | 0.229999915 |

The four later-dated positions account for approximately 0.25% of net assets.
Assigning the entire current snapshot to February 21 would backdate those rows
by as much as 45 days. The receipt labels alone do not establish whether these
were late reports or revisions, nor when end users received this exact vintage.
Using the latest receipt would also require that separate availability review.

No exact repeated rows or repeated nonmissing CUSIPs appear in the control;
38 CUSIPs are missing and stay missing. Rank ties are not deduplicated. Group
counts, distinct-rank counts and unnormalized weight sums reproduce the earlier
aggregate exactly. One control does not certify all 461 mixed-receipt snapshots.

Retained four WRDS responses locally: one connection check, 34 dated stock
intervals, 31 legacy name intervals and 1,371 holdings. Four public documents are
also archived with hashes and capture times. Licensed rows and exact comparisons
remain outside Git. Twenty-four focused tests and Ruff pass. No existing source
values, registered strategy assets or active catalog publications changed. No
strategy replay or portfolio result was calculated, so a weakest-ETF trade chart
does not apply.

Next qualification work is the ten remaining foreign bridges and independently
supported dissemination/revision timing, followed by portfolio completeness and
broader price/activity coverage. Current source archives remain protected while
this qualification work is active.

[Protocol](protocol.json) · [Audit plan](audit-plan.json) · [Assessment](assessment.json) ·
[Capture receipt](capture.json) · [Primary sources](public-sources.json) ·
[Acceptance](acceptance.json) · [Artifact hashes](artifact-manifest.json).
