# IBKR reconciliation — prices corroborated, activity basis unresolved

November 6, 2026

IBKR historical access is restored. All ten selected stocks have complete 253-session TRADES and ADJUSTED_LAST windows for February 27, 2024–February 28, 2025. That is 20 complete series and 2,530 matched stock-days. 2,529 closing prices agree within half a cent; the sole exception is one cent. Zero new histories were published: the new evidence supports the closing-price fields, while volume comparability, dated continuity and earlier source reviews remain open.

| Stock | Closes within $0.005 | Max adjusted-return difference (bp) | Median IB volume / published volume |
| --- | --- | --- | --- |
| CSL | 253/253 | 0.0041 | 36.9% |
| WSO | 253/253 | 0.0042 | 31.5% |
| MANH | 252/253 | 0.4140 | 37.6% |
| RPM | 253/253 | 0.0086 | 43.7% |
| UTHR | 253/253 | 0.0009 | 35.5% |
| XPO | 253/253 | 0.0010 | 54.6% |
| FIX | 253/253 | 0.0053 | 38.0% |
| FLEX | 253/253 | 0.0009 | 68.7% |
| CASY | 253/253 | 0.0068 | 34.3% |
| RS | 253/253 | 0.0049 | 36.3% |

## What the comparison establishes

The existing published closes are strongly corroborated for this ten-stock window. MANH on June 24, 2024 is 241.47 at IBKR versus 241.48 in the publication. The maximum difference between adjacent dividend-adjusted daily log returns is 0.414 basis points (MANH); all other stocks remain below 0.009 basis points. A constant adjustment-vintage scale cancels in this return comparison. The half-cent count is a numerical diagnostic, not a new promotion gate. This sample does not certify other names, earlier periods or historical information availability.

## Open, high and low require their own interpretation

Agreement at the close does not extend to every traded price. FIX has the largest opening-price difference: IBKR is $2.00 lower on July 25, 2024. UTHR differs by $1.05 on October 29, 2024; MANH differs by $0.97 on April 26, 2024. All day-level differences are retained. The comparison does not establish which feed supplies the appropriate official auction/open definition for execution modeling. No source was silently substituted.

## Volume is not interchangeable

For every stock-day, the returned regular-hours broker volume is lower than the published raw-volume value. The per-stock median ratio ranges from 31.5% to 68.7%. The ratios vary by name and date; a single constant rescaling cannot reconcile them. The table preserves broker values as returned and makes no undocumented shares/lots conversion. The two IBKR price types return identical volume within this window. That is an internal broker consistency check, not two independent confirmations.

## A bounded session control explains part of the gap

Additional all-hours TRADES requests were predeclared for CSL, WSO and XPO after the initial comparison. Their median ratios rise from 36.9% to 54.0%, 31.5% to 49.8%, and 54.6% to 68.7%, respectively. All 759 all-hours volume observations still remain below the publication. Session coverage therefore explains part of the discrepancy in these controls, but does not reconcile it. All-hours close prices also differ from the regular-session close and must not replace it.

## Documented limitation and inference

IBKR documents filtering certain trade types from historical data and warns that captured history may change as it is adjusted and filtered. This makes differences in feed coverage a plausible contributor to the residual volume gap. It does not quantify that contribution or prove either feed is wrong. Explicit volume units, trade eligibility and consolidated-versus-venue scope remain necessary before raw-volume or raw-dollar-activity research can use the comparison.

[IBKR documentation](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations).

## Decision and next item

Retain this independent closing-price corroboration as evidence. Keep the current source reviews until a dated, field-specific disposition is recorded. The next item is to settle the required volume/session definition for constituent activity and identify a matching documented history; also resolve opening-price semantics where simulated fills require them. Price-only qualification can be assessed separately from volume-dependent eligibility. Earlier action and identity reviews remain in force. Historical replay remains blocked; this closes the requested acquisition/reconciliation item and stops for operator discussion.

## Capture and validation

A dedicated paper API client verified paper managed accounts and sent no orders. All 23 successful requests reached the historical-data completion callback. IBKR warning 2188 about up-to-the-second data was retained as an advisory; required dates are historical and every expected session was checked. The first premature stop on this advisory is retained in the attempt archive; the collector was corrected and tested before completing the run. Twenty-six focused tests passed. Published inputs were read through their pinned manifest and hashes. Broker receipts, compressed observations and private account-verification receipts remain protected evidence while qualification is active. No catalog, strategy, approval or trading configuration was changed.

[Detailed assessment](assessment.json) · [Session controls](session-control.json) · [Frozen protocol](protocol.json) · [Artifact hashes](artifact-manifest.json) · [Previous qualification report](../p421-ten-qualification-20261106-v1/results.md) · [IBKR historical data definitions](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars) · [IBKR historical filtering](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations)
