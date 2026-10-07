# Market History and chart navigation

Market Data opens **Market History → Historical Daily Price** at the longest
available history. Select a stock/ETF ticker or **USD** (Federal Reserve broad
dollar index, DTWEXBGS) in the same series selector. USD uses the existing verified
publication, preserves missing levels, and shares date/zoom/pan/reset controls;
it is shown in index units rather than as a traded USD price. There is no separate
USD shortcut button; future currency-pair series can use the same selector.
Currency-pair acquisition is not implemented by this UI change. **Intraday Bars**
is the other primary view.

Both views share compact tab navigation, consistent control heights, keyboard
focus states, responsive filters, aligned summary metrics and scrollable tables.
The chart has a separate navigation toolbar and understated price grid. Styling
is scoped to Market Data, including its compact application header; other
workspaces keep their existing layouts.

The **Debug** switch at the top is off by default. It reveals Intraday Bars flags,
raw references and Raw Evidence; source archives; daily price-basis diagnostics,
comparison controls/overlays, source charts, audit catalogs, raw columns and
lineage. Normal mode shows one selected series and concise daily observations.
Turning Debug off immediately clears comparisons and returns raw-source views to
Historical Daily Price. The switch is carried by `debug=1` in the current URL,
so it survives refresh without changing global account preferences. It controls
presentation only; APIs, source evidence and audit requirements remain intact.
Source archives and recorded bars load when their views are opened.

Canonical links use `?view=history`, `?view=history&series=USD`, `?view=bars` and
`?view=raw&debug=1`. Old `view=governed` and `view=usd` links remain supported;
`view=raw` / `view=research` without Debug resolve to Historical Daily Price.

CRSP cross-reference acquisition is pending licensed access; see
[CRSP access assessment](crsp-data-access.md). No CRSP data is present from that
request.

New price research must use the published audited continuous series, a pinned batch, checked hashes and an explicit price/volume basis. This requirement is recorded in `AGENTS.md` and the continuous research playbook. Raw provider archives remain evidence for ingestion and audit, not direct inputs for new backtests. The audited raw-price version remains valid where a signal needs raw traded prices. Unknown vintages, missing observations and identity/coverage exclusions remain visible.

Time-series charts support drag selection to zoom, Pan mode or Shift-drag to move, and a full-range reset. Home resets; arrow keys pan. Trading performance retains arrow-key observation inspection; its Pan button and Shift-drag move the window. Escape cancels an active drag. Controls remain attached when a chart redraws, and selected windows survive ordinary refreshes. A changed underlying resets its range. Return indices and cumulative values retain their original bases.

The controls cover published daily prices and USD index, comparison histories in Debug, recorded daily/intraday bars, the raw event inspector, source archive charts, trading performance, saved P&L, real/reference-fill comparisons, execution slippage, archived strategies and standalone backtest reports. Recorded/source pages explicitly reset to their **loaded range/page**; pagination and recorder limits are not presented as a complete history. Historical Daily Price is the complete-history research view. The performance chart defaults to All.

The shared implementation is `src/systematic_trading/chart_navigation.py`. Reports embed it, so exports work without an external JavaScript service. Report publication signatures include both the report renderer and chart controls. Tests exercise real shipped JavaScript, transformed SVG coordinates, reversed selections, pan bounds, cancellation, refreshes, intraday precision, independent charts and fixed normalization in archived and exported reports.
