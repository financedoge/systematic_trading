# FIX direct-minute gap check

All three direct Alpaca minute queries reproduce the original full-day capture's
records exactly, including identifiers, timestamps, prices, sizes and conditions.
The gaps persist without full-day pagination. They are differences between the
retained source datasets; these queries do not identify their upstream cause.

| Date / New York minute | UTC minute | Alpaca shares | IBKR shares | IBKR minus Alpaca |
| --- | --- | ---: | ---: | ---: |
| 2025-02-07 10:53 | 15:53 | 7,896 | 14,255 | 6,359 |
| 2025-02-04 12:16 | 17:16 | 843 | 2,160 | 1,317 |
| 2025-02-04 14:59 | 19:59 | 4,946 | 6,747 | 1,801 |

The three responses contain 227, 27 and 199 records, respectively, and explicit
terminal pagination tokens. Every record lies inside the frozen minute. The
February 4 gaps sum to 3,118 shares. Six additional February 7 minute differences
occur in offsetting pairs of 63, 10 and 4 shares; all are retained unchanged and
sum to zero. We do not infer unique missing trade identities from nonunique
price/size/condition keys.

IBKR and CRSP agree on both full-day FIX totals. This supports investigating
Alpaca's stored coverage for these minutes; it does not prove a universal provider
defect, certify CRSP history generally, or justify silently filling one source
from another. The complete earlier captures and independent boundary checks
remain pinned. The audit runner adds an explicit check against those pinned
source-manifest hashes; its original capture recipe is also retained unchanged
inside the archive.

This completes the bounded pagination diagnosis. Keep the observations as source
inspection evidence with historical availability unknown. No active publication,
strategy replay, tolerance change or investment choice was made. No portfolio
was calculated, so a weakest-ETF chart is inapplicable.

[Protocol](protocol.json) · [Assessment](assessment.json) ·
[Acceptance](acceptance.json) · [Artifact hashes](artifact-manifest.json).
