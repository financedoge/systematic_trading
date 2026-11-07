# Ten-stock SIP-volume pilot — November 7, 2026

Completed the authorized pilot over February 27, 2024–February 28, 2025. All **2,530 stock-days** are present (ten stocks × 253 sessions). The native analytical database now contains a separately versioned **field-audit publication**. It is **not admitted to the active continuous-history catalog or any strategy input**: earlier identity, corporate-action and historical-availability reviews remain open.

## What the wider window revealed

The median absolute volume difference from the pinned published history is **0.006888%**, but the tail is materially larger than the original five-day sample. Only 21 observations match exactly; 1,475 are higher and 1,034 lower. Five differences exceed 1% and 16 exceed 0.5%. Those percentages are descriptive counts, not acceptance thresholds. Neither source is declared correct from this comparison alone.

| Stock | Activity date | SIP shares | Previous published shares | Difference | Difference / previous |
|---|---|---:|---:|---:|---:|
| RPM | 2024-04-29 | 405,083 | 364,400 | +40,683 | +11.1644% |
| UTHR | 2024-06-25 | 562,256 | 523,500 | +38,756 | +7.4032% |
| UTHR | 2024-06-21 | 1,851,871 | 1,800,900 | +50,971 | +2.8303% |
| FIX | 2025-02-07 | 401,164 | 407,500 | -6,336 | -1.5548% |
| FIX | 2025-02-04 | 285,817 | 288,900 | -3,083 | -1.0672% |

The largest absolute discrepancy is 50,971 shares (UTHR, June 21). These outliers cannot be explained merely by rounding to hundreds. Their cause is unresolved: retain the values and investigate trades, eligibility and correction/capture vintages before any replacement. Price agreement does not qualify volume.

## Coverage and price/action checks

| Stock | Sessions | Exact volume matches | Median absolute volume difference | Maximum absolute volume difference |
|---|---:|---:|---:|---:|
| CSL | 253 | 2 | 0.008734% | 0.467748% |
| WSO | 253 | 4 | 0.010460% | 0.644007% |
| MANH | 253 | 2 | 0.007958% | 0.413759% |
| RPM | 253 | 0 | 0.005218% | 11.164380% |
| UTHR | 253 | 2 | 0.007315% | 7.403247% |
| XPO | 253 | 5 | 0.002466% | 0.707418% |
| FIX | 253 | 2 | 0.010759% | 1.554847% |
| FLEX | 253 | 2 | 0.001154% | 0.494761% |
| CASY | 253 | 1 | 0.012001% | 0.602889% |
| RS | 253 | 1 | 0.009515% | 0.847723% |

All 2,530 raw SIP daily closes are within $0.005 of the earlier IBKR regular-session bars. Against the pinned published raw closes, 2,529 are within that diagnostic. FLEX on October 18, 2024 is 34.895 at Alpaca, 34.900001525878906 in the publication, and 34.90 at IBKR: the exact published residual is −$0.005001525878906 and is retained outside the frozen half-cent diagnostic. No tolerance was widened. MANH on June 24 is 241.475 at Alpaca, 241.47999572753906 in the publication and 241.47 at IBKR; the sub-cent source value does not settle which closing-price convention is appropriate.

All published split multipliers equal one in this window. The pinned action ledgers contain 24 dividend records and no split records. Raw SIP shares were never adjusted. This verifies the retained ledger/basis, not the independent completeness or historical publication of corporate actions. All ten prior series remain in review. Frozen broker conIds, ISINs, literal tickers, USD currency and stock class agree; a current broker identity is not a dated historical security-master certificate.

## Capture, audit and publication

Captured 2,480 new daily bars in one successful response after two transport failures; both failed-request receipts remain local. Reused the existing 50 stock-days without redownloading them, preserving their original payload hashes and capture times. The new compressed response is 76,495 bytes. Exact session coverage, duplicates, numeric values, integer share/trade units, OHLC consistency, New York day boundaries and complete pagination were checked. No missing observations were filled.

Raw SIP requests explicitly use `adjustment=raw`, `feed=sip`, `asof=-` and USD. Literal-symbol mode avoids implicit ticker remapping; it does not prove historical continuity. Daily aggregation and condition eligibility follow the provider contract, with the prior 15 full-day Alpaca reconstructions and four independent IBKR tick controls retained only as evidence for their actual dates. The other dates have not received independent trade-by-trade validation. [Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars) and [aggregation/condition rules](https://docs.alpaca.markets/us/docs/market-data-faq).

- Publication: `governance/pilots/p421-sip-volume-v1`.
- Batch: `35d1efe82c7d7fbd77edd043fe2f33b34d7b9dec74190c0609374195aa2cb1b9`.
- Native storage: `postgres-parquet-duckdb`; 2,530 observations and five documents verified by SHA256 readback.
- Local audited artifacts: `D:\projects\systematic_trading\var\governance\pilots\p421-sip-volume-20261107-v1`.
- New raw archive: `D:\systematic_trading_data\source-archives\alpaca\sip-pilot-20261107T130127809457Z`.
- Existing `governance/catalog` head was unchanged across publication; no registered provider or consumer was migrated.

Full-day activity uses the New York reporting date and is not ready at that date’s market close. The paired price remains the same-activity-date pinned raw regular-session close. Price × volume is an activity proxy, not traded dollars or net flow. All `historical_published_at` and database `available_at` fields remain null. Actual November 2026 capture timestamps are retained separately; a one-day lag cannot make this a point-in-time March 2025 input. The fail-closed availability check returns no eligible observations.

## Verification and next discussion

32 focused tests passed for the new audit and reused acquisition helper, including daylight-saving boundaries, missing/duplicate/unsorted sessions, invalid or fractional volume, source hash tampering, short-page token chains, failed requests and retrospective availability rejection. Ruff and dependency contract checks passed. Existing activity asset versions were inspected and preserved; the compatible hash reader and native publication service were reused. The unregistered pilot candidate is not a monitored strategy input.

**Stop for discussion.** Recommended next item: freeze the five largest percentage discrepancies in the table above, reconstruct their eligible Alpaca trades, and seek matching independent IBKR full-day tick controls. This is a diagnostic selection prompted by this completed audit, not random validation or a retrospective acceptance rule. Resolve field-specific discrepancies before wider admission. Historical identity/availability and ETF holdings coverage remain separate P4.21 gates; no strategy backtest has started.

This data-only item has no portfolio policy or weakest-ETF trading case. No subscriptions, orders, strategy replay or promotion occurred. Active qualification archives and compact findings/recipes remain retained locally under the existing storage policy.

[Frozen protocol](protocol.json) · [Assessment](assessment.json) · [Proposed diagnostic cases](diagnostics.json) · [Publication receipt](publication.json) · [Reuse/preflight](preflight.json) · [Acceptance](acceptance.json) · [Artifact hashes](artifact-manifest.json)
