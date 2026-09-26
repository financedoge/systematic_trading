# Trading and backtesting audit — 2026-09-26

Scope: current local paper platform, persisted data, research/backtest timing,
execution gates, messaging/backup health and LEAN isolation. This is an engineering
review, not authorization to trade live or certification of historical returns.

## Implemented corrections

| Finding | Correction and evidence |
| --- | --- |
| “Live PnL” used daily research marks | Dedicated read-only IB `reqPnL` / `reqPnLSingle` worker. Separate client ID, verified DU account, reconnect, explicit broker currency, callback timestamps, unavailable sentinel handling and stale-state display. HTTP reads cached state; browser polls every two seconds with a five-second timeout. Local accounting history remains separately labelled. |
| Closing FX funded same-day opening trades | Stored and research runners now pass previous-session FX for opening cash conversion. Closing FX is used only for valuation. Regression doubles closing FX and verifies opening affordability is unchanged. |
| A missing daily bar could fill at the previous close | Removed executable-price carry-forward, including missing whole execution/rebalance dates. Non-finite/nonpositive execution prices fail; historical FX carry is bounded to seven days. LEAN export checks every expected calendar session, including gaps shared by all symbols. |
| Calendar intersections and dynamic valuation hid gaps | Common-window research refuses to silently discard an interior session missing from one symbol. Dynamic research passes only that session's closing marks; an unpriced held position fails even on a day without rebalancing. |
| Signal plugins received the entire future dataset | `SignalContext` now supplies only strictly earlier sessions. Mutation test changes all subsequent prices and volume and confirms current SOTA targets are identical. |
| An opening stock screen could use a filing published later that day | Fundamental selection uses the prior session's information date. Missing publication dates no longer default to fiscal period end. |
| Training labels could end on the first holdout date | Training requires the complete label window to end strictly before the split. The existing frozen SOTA model was not refitted. |
| Unfinished daily bars retained as completed observations | Yahoo and ClickHouse backfill reject unfinished sessions and inconsistent OHLC. Store reads exclude observations captured before completion. Backfill detects and repairs those legacy rows. US DST, early close and known exceptional closures are tested. |
| Imported history falsely claimed midnight availability | Unspecified availability now records ingestion time and `availability_unverified`, never fabricated historical publication time. |
| IB adjusted historical fallback rejected its explicit end timestamp | `ADJUSTED_LAST` uses the required empty endpoint, a duration covering the requested start, and an explicit output date filter. |
| Lint defects | Fixed missing `Mapping` and `PlatformEventOutboxRecord` imports, unused imports/locals and ineffective f-strings. Repository correctness lint is explicitly configured as Ruff E9/F; pytest fixture imports have targeted file-level exceptions. |

## Runtime observations

- PostgreSQL, ClickHouse, NATS, API and dispatcher were reachable. The event outbox
  had zero unpublished events at inspection. Broker reconciliation was matched.
- NAS ownership and local/NAS heads matched. Existing backup/restore and handoff
  guards remain active; disposable PostgreSQL integration tests exercise recovery.
- Real browser verification showed six position rows, changing broker P&L, no
  console errors and no horizontal overflow. IB account totals are HKD; these ETF
  position rows are USD. Neither is silently labelled CNH. `received_at` means a
  broker callback arrived, not that every underlying exchange quote is entitled
  realtime. Daily P&L and unrealized-plus-realized have different reset meanings.
- Initial market-data audit: 141,620 rows, 34 invalid OHLC, 825 zero-volume bars,
  and unfinished September 25 rows. Preserved 45 suspect rows before repair in
  `D:/systematic_trading_data/backups/20260926-data-audit/suspect-daily-bars.jsonl`.
  Provider repair plus unfinished-session cleanup left 141,582 rows, zero invalid
  OHLC and 821 zero-volume observations, through completed September 24.
- Earlier inspections saw recorder error 10197 and historical-FX error 162
  (another trading session/IP). At 19:22 UTC these restrictions had cleared:
  the recorder's latest completed chunk contained 155 delayed bars across all
  five configured symbols, and a fresh IB request returned observed September
  23/24 USD/CNH closes 6.7117/6.71595. Evidence:
  `var/audit-ib-fx-final-probe.json`. The recorder still reports no realtime
  subscription and explicitly labels its data delayed; it is not a realtime
  quote source. No other trading session was disconnected by this work.
- The final read-only policy check found paper automatic approval enabled. Its
  existing setting was preserved; this implementation did not enable it or
  change its caps. Live routing remains disabled.
- The broader daily watchlist still cannot refresh HYXU (Yahoo 404; IB security
  definition error 200). It is outside the current twelve-ETF SOTA workload;
  its unavailable history remains a visible warning, not a fabricated series.

## Remaining limitations and promotion blockers

1. Historical source vintages and historical universe membership are incomplete.
   Today's adjusted history is not proof of what was known years ago. A fixed
   surviving ETF/stock universe can create survivorship/selection bias.
2. Legacy FX contains proxy/unknown source lineage and gaps. Yahoo's offshore
   CNH symbols returned no requested historical series. Recent IB history now
   works, but the long legacy series has not been re-sourced and certified.
   Strict LEAN export rejects missing observations. An
   explicit engineering-only legacy mode preserves the original FX observation
   date and caps carry at seven days. It never writes proxies into operational FX.
3. SOTA's pre-2023 fitted tree makes its fitted-period returns descriptive, not
   independent predictive evidence. Repeated strategy selection on the historical
   post-2023 window means it is not a pristine untouched holdout either. New
   promotion needs a genuinely untouched interval and forward paper evidence.
4. The initial LEAN scenario is adjusted-price, whole-unit, next-open execution
   with instantaneous CNH settlement and explicit fees/slippage. It does not
   certify raw corporate-action accounting, borrow, margin, delayed settlement,
   partial fills or production TWAP costs. Adjusted inputs receive no additional
   dividends or splits. Unsupported scenarios are rejected by the run contract.
5. Zero-volume observations remain in the wider historical dataset. They are
   visible audit findings and rejected by the LEAN exporter; they are not silently
   fabricated into liquid sessions. The calendar supports the current US-listed
   universe, not all global exchange calendars or future emergency closures.
   A fresh provider check also reports zero MCHI volume on 2012-01-04; this was
   not overwritten. The long-history LEAN benchmark starts warmup on 2012-01-05
   and execution on 2013-02-01, after the required 253 prior observations. The
   rejected export and original row are retained as data-quality evidence.
6. Broker commissions are not yet incorporated in the local fill-ledger P&L.
   Broker P&L is separately sourced. Alert delivery was not tested by sending an
   unsolicited email or push. Reconciliation/live-route checks remain in place.
7. PostgreSQL physical relocation still requires the administrator move script
   from the previous session. No successful D: service switch has been reported.

## Verification artifacts

`var/platform-audit-tests.xml` records the complete test suite, including a
disposable PostgreSQL cluster: **579 passed, 1 optional SMB test skipped** in
287.35 seconds. Ruff correctness lint passes. Two upstream test-client
deprecation warnings remain; neither is a failing runtime check.
`var/platform-audit-runtime.json` and `var/platform-audit-runtime-final.json` contain the
timestamped read-only service/data observations. `var/platform-audit-lint.json`
retains the initial broad lint inventory; many entries are style suggestions
(notably Decimal spelling), not correctness defects. The reproducible correctness
command is `python -m ruff check src scripts tests`.

Final deployment: dashboard PID 31352, dispatcher 7052, recorder 39520.
Post-restart checks showed fresh account PnL, six positions, matched
reconciliation and no browser console errors/overflow. Per-position values
whose callbacks stop updating are explicitly shown as stale. See the
[native LEAN evidence](lean-validation-2026-09-26.md) for twelve passing runs.

Follow-up at 01:18 UTC: the after-hours UI was hiding cached broker figures
after 15 seconds, and attribution took 87.14 seconds while the dashboard waited
for every panel. Fixed timestamped last-value display, independent panel loading
and calculation-scoped read reuse. Attribution now took 3.23 seconds with the
same totals; 75 focused regressions passed, Ruff clean. Deployed dashboard
33380 / dispatcher 32148; real browser verified both panels populated,
reconciliation matched and paper policy unchanged. Evidence is in
`var/pnl-na-before.json`, `var/pnl-na-after.json` and `var/pnl-na-regression.xml`.

Sources: [IB portfolio P&L](https://interactivebrokers.github.io/tws-api/pnl.html),
[LEAN custom data](https://www.quantconnect.com/docs/v2/lean-cli/datasets/custom-data),
[NYSE hours/calendars](https://www.nyse.com/markets/hours-calendars).
