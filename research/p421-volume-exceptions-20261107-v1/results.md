# Fourteen volume-rounding exceptions — November 7, 2026

**The declared comparison is complete. All 14 Alpaca trade reconstructions match
its archived daily bars exactly, and all three independent IBKR tick controls
match Alpaca's full-day volume exactly. The small residuals against the existing
published history remain unresolved. No acceptance tolerance, source replacement,
publication or strategy replay was introduced. Stop for operator discussion.**

The cases were selected from the earlier 50-stock-day comparison because rounding
Alpaca daily volume to the nearest 100 shares did not reproduce the published
figure. This is a diagnostic follow-up on known discrepancies, not random or fresh
statistical validation. The original 36 other stock-days and the separately checked
CSL February 24 control remain unchanged evidence.

Across seven stocks and 14 days, 307,092 retained Alpaca trade/reference records
reconstruct every daily volume exactly using the documented tape-specific rules.
All 4,289 returned minute bars also match their eligible trade totals. A further
1,916 minutes contain 550,359 eligible shares but no price-eligible trade; their
absence is consistent with the documented OHLC bar-emission rule. Every day obeys
observed-minute volume plus absent-minute eligible volume equals daily volume.
[Alpaca aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq).

NYSE and Nasdaq rules were declared separately. In particular, condition `B` is
an average-price trade on NYSE but a price-eligible bunched trade on Nasdaq;
Nasdaq uses `W` for average-price trades. Official price-reference conditions
`M`, `Q`, `9` do not add volume. Canceled/incorrect records are excluded and
corrected records retained. All 307,092 returned records lack an update flag;
that does not prove no historical correction occurred or establish its availability.
No prices, volume multipliers or missing bars were filled or substituted.

| Stock | Date | Reconstructed minus published, shares | Relative difference | Reconstructed minus Alpaca daily, shares |
| --- | --- | ---: | ---: | ---: |
| CSL | 2025-02-26 | +124 | 0.049799% | +0 |
| FIX | 2025-02-24 | +75 | 0.006856% | +0 |
| FIX | 2025-02-25 | +184 | 0.020690% | +0 |
| FIX | 2025-02-26 | +95 | 0.014340% | +0 |
| FIX | 2025-02-27 | +75 | 0.011300% | +0 |
| FIX | 2025-02-28 | +52 | 0.007140% | +0 |
| UTHR | 2025-02-24 | +75 | 0.008572% | +0 |
| UTHR | 2025-02-25 | +59 | 0.009980% | +0 |
| FLEX | 2025-02-25 | +79 | 0.002260% | +0 |
| MANH | 2025-02-25 | +152 | 0.010533% | +0 |
| MANH | 2025-02-27 | +173 | 0.037228% | +0 |
| XPO | 2025-02-24 | +110 | 0.005890% | +0 |
| XPO | 2025-02-26 | +157 | 0.015442% | +0 |
| CASY | 2025-02-24 | +60 | 0.022313% | +0 |

Every residual is unchanged from the preceding comparison: 52–184 shares, maximum
0.049799%. None is an exact or nearest-100 match. The sample-selection process
already singled out rounding exceptions; their positive signs must not be
interpreted as an unbiased estimate of a general provider bias. We did not switch
to truncation, fit a multiplier or choose a larger tolerance to make these pass.
The cause of these small provider/capture-vintage differences remains unproven.

Before acquisition, three independent IBKR full-day tick controls were frozen:
FIX February 25 for the maximum absolute residual, CSL February 26 for the maximum
relative residual, and MANH February 27 for the maximum Nasdaq relative residual.

| Stock | Date | Alpaca eligible volume | IBKR tick volume | IBKR trade records |
| --- | --- | ---: | ---: | ---: |
| CSL | 2025-02-26 | 249,124 | 249,124 | 9,596 |
| FIX | 2025-02-25 | 889,484 | 889,484 | 22,430 |
| MANH | 2025-02-27 | 464,873 | 464,873 | 14,188 |

All three also match the full multiset of condition combinations and trade sizes,
normalizing the different regular-sale encodings. Each ending boundary passed an
independent backward tick request, with 1,025, 1,001 and 1,030 records respectively
in the table's order. The 46,214 in-day IBKR ticks are not deduplicated by their
second, price or size. Completed whole-second pagination preserves repeated
occurrences. No next-day spill entered the totals. This supports full-day activity
on these three controls, not independent tick qualification of the other 11 days
or unique trade-ID equivalence.

The reconstructed IBKR ticks without its vendor `unreported` flag also reproduce
the retained regular-hours IBKR daily bars exactly for all three controls. That
filtered bar quantity is distinct from consolidated full-day activity.

**Full-day agreement does not imply identical session clocks.** In two controls,
some volume lands on opposite sides of the 16:00 boundary:

| Stock | Date | Alpaca minus IBKR, 09:30–before 16:00 | Alpaca minus IBKR, 16:00 minute |
| --- | --- | ---: | ---: |
| CSL | 2025-02-26 | +2,538 | -2,538 |
| FIX | 2025-02-25 | +100 | -100 |
| MANH | 2025-02-27 | +0 | +0 |

The differences cancel within each full day. We retain the original clocks and
do not force these bins to match or infer the original execution time of late
reports. A regular-session volume input would need its own timestamp/session
contract. No full-session total is treated as available at that same 16:00 close;
the frozen activity cutoff still needs a genuinely completed, available session.
[Prior volume/availability contract](../p421-volume-contract-20261107-v1/results.md).

Alpaca used 37 successful trade pages. One earlier request exhausted its bounded
transport attempts before receiving HTTP; a resumed run verified and reused every
completed page. IBKR used 55 requests, including one interrupted request, three
terminal empty responses and three independent backward checks; one reconnect
recovered the historical-data farm interruption. Failed requests remain retained.
No HTTP denial, TLS certificate failure or unknown schema was bypassed.

All 92 new compressed payloads, executed code copies and protocol hashes verify.
The 18 preceding source payloads and original comparison were rechecked against
published batch `ebffbedaaf8ae35bd5654887f83459156abff13d12537b2bd614e593c64ee77d`
and its input hashes. Seventeen focused tests, Ruff and whitespace checks pass.
The dependency preflight and asset-pool reuse review preserve all registered
versions; these are standalone inspection runners, not new strategy providers.
This source-only item has no portfolio policy or weakest-ETF performance chart.

Raw responses and detailed minute/condition diagnostics remain outside Git:

- `D:/systematic_trading_data/source-archives/alpaca/volume-exceptions-20261107T121936468778Z`
- `D:/systematic_trading_data/source-archives/ibkr/volume-exceptions-20261107T122036989991Z`

Credentials remain in the ignored local `.env`, with HTTPS authentication passed
through stdin only. Broker requests used verified paper accounts and a read-only
order guard. No subscriptions or trading settings changed.

Replay without downloading data:

```powershell
.venv\Scripts\python.exe scripts/reconcile_volume_exceptions.py D:/systematic_trading_data/source-archives/alpaca/volume-exceptions-20261107T121936468778Z D:/systematic_trading_data/source-archives/ibkr/volume-exceptions-20261107T122036989991Z
```

**Recommendation for discussion:** move to a versioned, audited SIP-volume pilot
for the frozen ten-stock history. Preserve the older published series, its source
lineage and these residuals. Specify full-day eligibility, corporate-action basis
and decision-time availability before admission; any regular-session input stays
separate. The evidence supports that pilot, not automatic replacement or a claim
that the entire history is qualified. Historical publication timing remains
uncertified by a November 2026 capture.

[Frozen cases and controls](protocol.json) · [Preflight](preflight.json) ·
[Recovery amendment](transport-recovery.json) · [Complete assessment](assessment.json).
