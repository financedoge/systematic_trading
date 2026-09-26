from __future__ import annotations

from systematic_trading.web.trading_workspace import WORKSPACE_CSS, WORKSPACE_HTML, WORKSPACE_DIALOG, WORKSPACE_JS

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/operator")


@router.get("/operator", response_class=HTMLResponse, include_in_schema=False)
def operator_dashboard() -> HTMLResponse:
    html = _OPERATOR_HTML.replace('</style>', WORKSPACE_CSS + '</style>', 1)
    html = html.replace('<main>', '<main>' + WORKSPACE_HTML, 1)
    html = html.replace('<script>', WORKSPACE_DIALOG + '<script>', 1)
    html = html.replace('    Promise.all([loadProposals(), loadDashboardData()])', WORKSPACE_JS + '\n    Promise.all([loadProposals(), loadDashboardData()])', 1)
    return HTMLResponse(html)


@router.get("/strategies", response_class=HTMLResponse, include_in_schema=False)
def strategy_portal() -> HTMLResponse:
    return HTMLResponse(_STRATEGIES_HTML)


@router.get("/strategies/{strategy_id}", response_class=HTMLResponse, include_in_schema=False)
def strategy_detail_portal(strategy_id: str) -> HTMLResponse:
    html = _STRATEGY_DETAIL_HTML.replace("join('\n')", "join(String.fromCharCode(10))")
    return HTMLResponse(html)


_OPERATOR_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Operator</title>
  <style>
    :root {
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1d2433;
      --muted: #657083;
      --line: #d8dee8;
      --line-soft: #ebeff5;
      --focus: #2456a6;
      --good: #0f766e;
      --warn: #a15c06;
      --bad: #b42318;
      --ink: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, Segoe UI, Arial, sans-serif;
      font-size: 14px;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { margin: 0; font-size: 18px; font-weight: 650; letter-spacing: 0; }
    .shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(380px, 520px);
      min-height: calc(100vh - 56px);
    }
    aside {
      grid-column: 2;
      grid-row: 1;
      border-left: 1px solid var(--line);
      background: #fbfcfd;
      min-width: 0;
      max-height: calc(100vh - 56px);
      overflow: auto;
    }
    main {
      grid-column: 1;
      grid-row: 1;
      min-width: 0;
      padding: 16px 18px 28px;
    }
    .toolbar {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }
    .tabs {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 4px;
      width: 100%;
    }
    a.button, button, select, input {
      font: inherit;
    }
    a.button, button {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      min-height: 32px;
      padding: 6px 10px;
      border-radius: 6px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    a.button:hover, button:hover { border-color: #aeb9c9; }
    button:focus-visible, select:focus-visible, input:focus-visible, textarea:focus-visible {
      outline: 2px solid var(--focus);
      outline-offset: 1px;
    }
    button.primary { background: var(--focus); border-color: var(--focus); color: white; }
    button.good { background: var(--good); border-color: var(--good); color: white; }
    button.bad { background: var(--bad); border-color: var(--bad); color: white; }
    button.warn { border-color: #d69e2e; color: #7a4a03; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    .tab.active {
      background: #e9f0fb;
      border-color: #b8c7e6;
      color: #183b73;
      font-weight: 650;
    }
    .list {
      overflow: auto;
      max-height: 300px;
      border-bottom: 1px solid var(--line);
    }
    .proposal-row {
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      text-align: left;
      border: 0;
      border-bottom: 1px solid var(--line-soft);
      border-radius: 0;
      padding: 10px 12px;
      background: transparent;
    }
    .proposal-row.active { background: #eef4fb; }
    .proposal-row.missed { background: #f1f3f5; color: #7b8492; opacity: .72; }
    .proposal-row.missed:hover, .proposal-row.missed.active { background: #e5e8ec; }
    .proposal-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 650;
    }
    .meta {
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 74px;
      height: 22px;
      padding: 0 8px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
      text-transform: capitalize;
    }
    .badge.pending { color: var(--warn); border-color: #f0c674; background: #fff8e8; }
    .badge.approved { color: var(--good); border-color: #9cd6cd; background: #ecf9f6; }
    .badge.rejected { color: var(--bad); border-color: #f0a7a1; background: #fff0ef; }
    .badge.missed { color: #667085; border-color: #c7cdd6; background: #eef0f3; }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .execution-summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }
    .execution-summary .metric {
      min-height: 62px;
      padding: 8px 10px;
    }
    .execution-summary .metric strong {
      font-size: 14px;
    }
    .metric, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .metric {
      min-height: 74px;
      padding: 10px 12px;
    }
    .metric label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    .metric strong {
      font-size: 18px;
      overflow-wrap: anywhere;
    }
    .metrics-compact {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line-soft);
    }
    .mini-metric {
      min-width: 0;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      padding: 8px 10px;
      background: #fbfcfd;
    }
    .mini-metric label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .mini-metric strong {
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .panel {
      margin-top: 12px;
      overflow: hidden;
    }
    .rail-panel {
      margin: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
    }
    .rail-panel .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      padding: 12px;
      border-bottom: 1px solid var(--line-soft);
    }
    .rail-panel textarea {
      min-height: 76px;
      border-left: 0;
      border-right: 0;
      border-radius: 0;
    }
    .rail-panel table th,
    .rail-panel table td {
      padding: 7px 8px;
      font-size: 12px;
    }
    .panel-head {
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line-soft);
    }
    h2 {
      margin: 0;
      font-size: 15px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }
    textarea {
      width: 100%;
      min-height: 62px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      color: var(--text);
    }
    .body { padding: 12px; }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 8px 10px;
      vertical-align: top;
      text-align: left;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      background: #fbfcfd;
    }
    tr:last-child td { border-bottom: 0; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .empty, .error, .log {
      color: var(--muted);
      padding: 14px 12px;
    }
    .error { color: var(--bad); }
    .log {
      border-top: 1px solid var(--line-soft);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      max-height: 180px;
      overflow: auto;
    }
    .split {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
      gap: 12px;
      align-items: start;
    }
    .chart-wrap {
      height: 280px;
      padding: 10px 12px 12px;
    }
    .chart-wrap svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .axis-line, .grid-line {
      stroke: var(--line-soft);
      stroke-width: 1;
    }
    .strategy-line {
      fill: none;
      stroke: #2456a6;
      stroke-width: 2.2;
    }
    .account-line {
      fill: none;
      stroke: #0f766e;
      stroke-width: 2.2;
    }
    .pnl-line {
      fill: none;
      stroke: #7c4a03;
      stroke-width: 2.2;
    }
    .actual-line {
      fill: none;
      stroke: #7c4a03;
      stroke-width: 2.2;
    }
    .theoretical-line {
      fill: none;
      stroke: #2456a6;
      stroke-width: 2.2;
      stroke-dasharray: 5 4;
    }
    .account-dot {
      fill: #0f766e;
      stroke: white;
      stroke-width: 1.5;
    }
    .strategy-dot {
      fill: #2456a6;
      stroke: white;
      stroke-width: 1.5;
    }
    #performance-chart { position: relative; height: 320px; }
    #performance-chart svg { touch-action: none; user-select: none; }
    #performance-chart .strategy-dot, #performance-chart .account-dot { stroke: none; }
    #performance-chart .strategy-line, #performance-chart .account-line { vector-effect: non-scaling-stroke; stroke-linejoin: round; }
    .performance-note { padding: 6px 12px; color: var(--muted); font-size: 12px; }
    #performance-hover { min-height: 34px; font-variant-numeric: tabular-nums; }
    .perf-crosshair { stroke: #657083; stroke-dasharray: 3 3; pointer-events: none; }
    .perf-selection { fill: #2456a622; stroke: #2456a6; pointer-events: none; }
    .pnl-dot {
      fill: #7c4a03;
      stroke: white;
      stroke-width: 1.5;
    }
    .chart-tools {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px 12px 0;
      border-top: 1px solid var(--line-soft);
    }
    .segmented {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 4px;
    }
    .segmented button {
      min-width: 44px;
      min-height: 30px;
      padding: 4px 8px;
    }
    .segmented button.active {
      background: #e9f0fb;
      border-color: #b8c7e6;
      color: #183b73;
      font-weight: 650;
    }
    .date-field {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      min-height: 30px;
    }
    .date-field input {
      height: 30px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 3px 6px;
      color: var(--text);
      background: var(--panel);
    }
    .analysis-table {
      padding: 0 12px 12px;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      padding: 0 12px 12px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .swatch {
      width: 18px;
      height: 3px;
      border-radius: 999px;
      display: inline-block;
      background: var(--focus);
    }
    .swatch.account { background: var(--good); }
    .swatch.pnl { background: #7c4a03; }
    .swatch.theoretical { background: #2456a6; }
    .warnings {
      color: var(--warn);
      font-size: 12px;
      padding: 0 12px 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .reconciliation-break { border-color: #d92d20; }
    .reconciliation-break .panel-head { background: #fff4f2; }
    .reconciliation-message {
      padding: 10px 12px;
      color: var(--bad);
      font-weight: 650;
      overflow-wrap: anywhere;
    }
    .status-line {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--good);
      display: inline-block;
    }
    @media (max-width: 900px) {
      .shell { grid-template-columns: 1fr; }
      main { grid-column: 1; grid-row: 1; }
      aside { grid-column: 1; grid-row: 2; border-left: 0; border-top: 1px solid var(--line); max-height: none; }
      .list { max-height: 280px; }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .metrics-compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .split { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      header { align-items: flex-start; height: auto; min-height: 56px; flex-direction: column; padding: 10px 12px; gap: 6px; }
      main { padding: 12px; }
      .grid { grid-template-columns: 1fr; }
      .metrics-compact { grid-template-columns: 1fr; }
      .tabs { grid-template-columns: repeat(2, 1fr); }
      .actions { width: 100%; }
      .actions .button, .actions button { flex: 1 1 130px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>SYSTEMATIC <span style="font-weight:400;color:#9caec4">/ Trading operations</span></h1>
    <div class="actions">
      <a class="button" href="/operator">Trading</a>
      <a class="button" href="/strategies">Strategies</a>
      <a class="button" href="/platform">System</a>
      <a class="button" href="/platform/market-data-audit">Market Data</a>
    </div>
  </header>
  <div class="shell">
    <aside>
      <div class="toolbar">
        <div class="tabs" role="tablist" aria-label="Proposal status">
          <button class="tab active" data-filter="">All</button>
          <button class="tab" data-filter="pending">Pending</button>
          <button class="tab" data-filter="approved">Approved</button>
          <button class="tab" data-filter="rejected">Rejected</button>
        </div>
      </div>
      <div id="proposal-readiness" class="warnings" role="status"></div>
      <div class="list" id="proposal-list"></div>
      <section class="execution-summary" aria-label="Execution summary">
        <div class="metric"><label>Selected</label><strong id="metric-proposal">n/a</strong></div>
        <div class="metric"><label>Status</label><strong id="metric-status">n/a</strong></div>
        <div class="metric"><label>Orders</label><strong id="metric-orders">0</strong></div>
        <div class="metric"><label>Notional CNH</label><strong id="metric-notional">0.00</strong></div>
        <div class="metric"><label>Completion</label><strong id="metric-completion">n/a</strong></div>
        <div class="metric"><label>Filled Qty</label><strong id="metric-filled">0 / 0</strong></div>
      </section>
      <section class="rail-panel">
        <div class="panel-head"><h2>Trading</h2></div>
        <div class="actions">
          <button id="refresh-btn">Refresh</button>
          <button id="approve-btn" class="good">Approve</button>
          <button id="reject-btn" class="bad">Reject</button>
          <button id="resubmit-failed-btn" class="warn" hidden>Resubmit Failed/Missing</button>
        </div>
        <textarea id="decision-comment" placeholder="Decision comment"></textarea>
        <div id="proposal-detail" class="body"></div>
        <div id="action-log" class="log"></div>
      </section>
      <section class="rail-panel">
        <div class="panel-head"><h2>Orders</h2></div>
        <div id="orders-table"></div>
      </section>
      <section class="rail-panel">
        <div class="panel-head"><h2>Broker Records</h2></div>
        <div id="broker-records"></div>
      </section>
      <section class="rail-panel">
        <div class="panel-head"><h2>Targets</h2></div>
        <div id="targets-table"></div>
      </section>
    </aside>
    <main>
      <section id="reconciliation-panel" class="panel">
        <div class="panel-head">
          <h2>IB portfolio & reconciliation</h2>
          <div class="actions">
            <span id="reconciliation-checked" class="status-line">Not checked</span>
            <button id="refresh-reconciliation-btn" type="button">Sync portfolio</button>
            <button id="reset-to-ib-btn" class="bad" type="button" hidden>Reset local to IB</button>
          </div>
        </div>
        <div class="metrics-compact" aria-label="IB reconciliation summary">
          <div class="mini-metric"><label>Status</label><strong id="reconciliation-status">n/a</strong></div>
          <div class="mini-metric"><label>IB Positions</label><strong id="reconciliation-ib-positions">n/a</strong></div>
          <div class="mini-metric"><label>IB Cash</label><strong id="reconciliation-ib-cash">n/a</strong></div>
          <div class="mini-metric"><label>Position Breaks</label><strong id="reconciliation-break-count">n/a</strong></div>
        </div>
        <div id="reconciliation-message" class="reconciliation-message" hidden></div>
        <div id="broker-portfolio"></div>
        <div id="reconciliation-table"></div>
        <div id="reconciliation-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Automation</h2>
          <div class="actions"><span class="status-line"><span class="dot"></span><span id="connection-status">Loading</span></span><span class="status-line" id="automation-state">n/a</span></div>
        </div>
        <div class="metrics-compact" aria-label="Automation summary">
          <div class="mini-metric"><label>Heartbeat</label><strong id="auto-heartbeat">n/a</strong></div>
          <div class="mini-metric"><label>Market Data</label><strong id="auto-market-data">n/a</strong></div>
          <div class="mini-metric"><label>IB Fill Sync</label><strong id="auto-fill-sync">n/a</strong></div>
          <div class="mini-metric"><label>EOD PnL</label><strong id="auto-eod-pnl">n/a</strong></div>
          <div class="mini-metric"><label>Staged Proposal</label><strong id="auto-proposal">n/a</strong></div>
        </div>
        <p id="auto-portfolio-alignment" role="status"></p>
        <p id="auto-portfolio-valuation" class="status-line"></p>
        <div id="auto-portfolio-drift"></div>
        <div id="automation-events"></div>
        <div id="automation-warnings" class="warnings"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Performance</h2>
          <div class="actions"><a class="button" href="/strategies">Strategy catalog</a><span class="status-line">Auto-updated · Backtest theoretical vs actual account</span></div>
        </div>
        <div class="metrics-compact" aria-label="Performance summary">
          <div class="mini-metric"><label>Strategy NAV</label><strong id="perf-strategy-nav">n/a</strong></div>
          <div class="mini-metric"><label>Strategy Return · selected period</label><strong id="perf-strategy-return">n/a</strong></div>
          <div class="mini-metric"><label>Account NAV</label><strong id="perf-account-nav">n/a</strong></div>
          <div class="mini-metric"><label>Account NAV change · selected period</label><strong id="perf-account-return">n/a</strong></div>
        </div>
        <div class="chart-tools" aria-label="Performance period">
          <div class="segmented" id="performance-range-buttons">
            <button type="button" data-perf-range="1m">1M</button>
            <button type="button" data-perf-range="3m">3M</button>
            <button type="button" data-perf-range="6m">6M</button>
            <button type="button" data-perf-range="ytd">YTD</button>
            <button type="button" data-perf-range="1y">1Y</button>
            <button type="button" data-perf-range="all">All</button>
            <button type="button" data-perf-range="tracking">Tracking</button>
          </div>
          <label class="date-field">Start <input id="perf-range-start" type="date"></label>
          <label class="date-field">End <input id="perf-range-end" type="date"></label>
        </div>
        <div id="performance-chart" class="chart-wrap"></div>
        <div id="performance-hover" class="performance-note" role="status" aria-live="polite">Hover or tap for dates and values. Drag across the chart to select a period; use arrow keys to inspect points.</div>
        <div id="performance-alignment" class="performance-note"></div>
        <div class="performance-note">Account NAV changes include deposits and withdrawals; cash flows are not adjusted. Statistics use available observations. Gaps longer than seven days appear as breaks in the chart.</div>
        <div id="performance-legend" class="legend"></div>
        <div id="performance-analysis" class="analysis-table"></div>
        <div id="performance-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Live broker PnL</h2>
          <div class="actions">
            <span class="status-line"><span id="pnl-as-of">n/a</span></span>
          </div>
        </div>
        <div class="metrics-compact" aria-label="PnL summary">
          <div class="mini-metric"><label>Realized PnL</label><strong id="pnl-realized">n/a</strong></div>
          <div class="mini-metric"><label>Unrealized PnL</label><strong id="pnl-unrealized">n/a</strong></div>
          <div class="mini-metric"><label>Daily PnL</label><strong id="pnl-total">n/a</strong></div>
          <div class="mini-metric"><label>Currency</label><strong id="pnl-open-value">n/a</strong></div>
        </div>
        <div id="live-pnl-table"></div>
        <div id="live-pnl-warnings" class="warnings" role="status"></div>
        <h3>Stored daily accounting — CNH</h3>
        <div class="performance-note">Daily research marks and local reset baseline; separate from current broker PnL.</div>
        <div id="pnl-chart" class="chart-wrap"></div>
        <div id="pnl-legend" class="legend"></div>
        <div id="pnl-table"></div>
        <div id="pnl-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>PnL Attribution</h2>
          <span class="status-line">Reference fills</span>
        </div>
        <div class="metrics-compact" aria-label="PnL attribution summary">
          <div class="mini-metric"><label>Reference Fill PnL</label><strong id="exec-theoretical-pnl">n/a</strong></div>
          <div class="mini-metric"><label>Stored-price PnL</label><strong id="exec-actual-pnl">n/a</strong></div>
          <div class="mini-metric"><label>Execution Gain</label><strong id="exec-gain">n/a</strong></div>
          <div class="mini-metric"><label>Execution Bps</label><strong id="exec-bps">n/a</strong></div>
          <div class="mini-metric"><label>Missed Orders</label><strong id="exec-missed-count">0</strong></div>
          <div class="mini-metric"><label>Missed Notional</label><strong id="exec-missed-notional">0.00</strong></div>
        </div>
        <div id="pnl-comparison-chart" class="chart-wrap"></div>
        <div id="slippage-chart" class="chart-wrap"></div>
        <div id="execution-quality-legend" class="legend"></div>
        <div id="execution-missed-table"></div>
        <div id="execution-slippage-table"></div>
        <div id="execution-quality-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>IB Holdings vs Strategy</h2>
          <div class="actions">
            <span class="status-line"><span id="holdings-as-of">n/a</span></span>
          </div>
        </div>
        <div id="holdings-table"></div>
        <div id="holdings-warnings" class="warnings"></div>
      </section>
    </main>
  </div>
  <script>
    const state = {
      proposals: [],
      selectedId: null,
      filter: "",
      brokerRecords: [],
      reconciliation: null,
      performance: { payload: null, rangeKey: "3m", start: null, end: null }
    };
    const el = (id) => document.getElementById(id);
    const fmtMoney = (value) => Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const fmtMaybeMoney = (value) => value === null || value === undefined ? "n/a" : fmtMoney(value);
    const fmtSignedMoney = (value) => {
      if (value === null || value === undefined) return "n/a";
      const number = Number(value || 0);
      const formatted = Math.abs(number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return `${number >= 0 ? "+" : "-"}${formatted}`;
    };
    const fmtDateTime = (value) => {
      if (!value) return "n/a";
      const date = new Date(value);
      if (!Number.isFinite(date.getTime())) return String(value);
      return date.toLocaleString();
    };
    const fmtPct = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
    const fmtMaybePct = (value) => value === null || value === undefined ? "n/a" : fmtPct(value);
    const fmtMaybeBps = (value) => value === null || value === undefined ? "n/a" : `${Number(value || 0).toFixed(2)} bps`;
    const fmtSignedPct = (value) => {
      if (value === null || value === undefined) return "n/a";
      const number = Number(value || 0) * 100;
      return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
    };
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options
      });
      const text = await response.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = text; }
      if (!response.ok) {
        const message = data && data.detail ? JSON.stringify(data.detail) : response.statusText;
        throw new Error(message);
      }
      return data;
    }

    async function loadProposals({ background = false } = {}) {
      el("connection-status").textContent = "Connected";
      const requestedFilter = state.filter;
      const path = requestedFilter ? `/api/v1/proposals?status=${encodeURIComponent(requestedFilter)}` : "/api/v1/proposals";
      const proposals = await api(path);
      if (state.filter !== requestedFilter) return;
      if (background && JSON.stringify(proposals) === JSON.stringify(state.proposals)) return;
      state.proposals = proposals;
      if (!state.proposals.length) state.selectedId = null;
      if (!state.selectedId && state.proposals.length) state.selectedId = state.proposals[0].proposal_id;
      if (state.selectedId && !state.proposals.some((item) => item.proposal_id === state.selectedId) && state.proposals.length) {
        state.selectedId = state.proposals[0].proposal_id;
      }
      renderList();
      await renderSelected();
    }

    const dashboardRequests = new Map();
    function loadDashboardPanel(key, load, render, failed) {
      if (dashboardRequests.has(key)) return dashboardRequests.get(key);
      const pending = Promise.resolve().then(load).then(render).catch(failed)
        .finally(() => dashboardRequests.delete(key));
      dashboardRequests.set(key, pending);
      return pending;
    }

    async function loadDashboardData() {
      const read = path => api(path, {signal: AbortSignal.timeout(45000)});
      const warning = id => error => {
        el(id).textContent = `Refresh failed: ${error.message}. Any displayed values are from the previous refresh; retrying automatically.`;
      };
      await Promise.allSettled([
        loadDashboardPanel("reconciliation",
          () => api("/api/v1/dashboard/reconciliation/interactive-brokers", {method:"POST", signal:AbortSignal.timeout(20000)}),
          renderReconciliation, error => {
            state.reconciliation = {has_breaks:true, unavailable:true};
            renderReconciliationUnavailable(error.message);
          }),
        loadDashboardPanel("automation", () => read("/api/v1/automation/status"), renderAutomation, warning("automation-warnings")),
        loadDashboardPanel("performance", () => read("/api/v1/dashboard/performance"), renderPerformance, warning("performance-warnings")),
        loadDashboardPanel("holdings", () => read("/api/v1/dashboard/holdings"), renderHoldings, warning("holdings-warnings")),
        loadDashboardPanel("pnl", async () => {
          // Missing history must not hide a successful current accounting snapshot.
          const [current, history] = await Promise.allSettled([
            read("/api/v1/dashboard/pnl"), read("/api/v1/dashboard/pnl/snapshots?limit=60")
          ]);
          if (current.status === "rejected") throw current.reason;
          const payload = current.value;
          if (history.status === "rejected") payload.warnings = [...(payload.warnings || []), `Snapshot history unavailable: ${history.reason.message}`];
          return [payload, history.status === "fulfilled" ? history.value : []];
        }, ([pnl, history]) => renderPnl(pnl, history), warning("pnl-warnings")),
        loadDashboardPanel("attribution", () => read("/api/v1/dashboard/execution-quality?history_limit=1"), renderExecutionQuality, warning("execution-quality-warnings"))
      ]);
    }

    function renderReconciliation(payload) {
      if (!payload) return;
      // A slower check must not restore an old warning after a newer sync.
      if (state.reconciliation?.checked_at && payload.checked_at &&
          Date.parse(payload.checked_at) < Date.parse(state.reconciliation.checked_at)) return;
      state.reconciliation = payload;
      const positions = payload.broker_positions || [];
      el("broker-portfolio").innerHTML = positions.length ? `<table><thead><tr><th>IB holding</th><th class="num">Quantity</th><th class="num">Average cost</th><th>Currency</th></tr></thead><tbody>${positions.map(p => `<tr><td class="order-symbol">${esc(p.symbol)}</td><td class="num">${esc(p.quantity)}</td><td class="num">${fmtMoney(p.average_cost)}</td><td>${esc(p.currency)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty-state"><strong>No open positions at IB</strong>Cash balances above are from the latest broker snapshot.</div>';
      const hasBreaks = Boolean(payload.has_breaks);
      const hasExecutionIssues = Boolean((payload.execution_issues || []).length);
      const hasPendingSync = Boolean((payload.execution_sync_pending || []).length);
      el("reconciliation-panel").classList.toggle("reconciliation-break", hasBreaks);
      el("reconciliation-checked").textContent = fmtDateTime(payload.checked_at);
      el("reconciliation-status").textContent = payload.status === "matched" ? "Matched" : payload.status === "reset_to_broker" ? "Reset to IB" : payload.status === "sync_pending" ? "Syncing fills" : "Break";
      el("reconciliation-ib-positions").textContent = payload.ib_position_count ?? 0;
      el("reconciliation-ib-cash").textContent = (payload.broker_cash || []).map((row) => `${row.currency} ${fmtMoney(row.amount)}`).join(" / ") || "0";
      el("reconciliation-break-count").textContent = (payload.position_differences || []).length;
      el("reset-to-ib-btn").hidden = !payload.requires_operator_confirmation || hasExecutionIssues || hasPendingSync;
      el("reconciliation-message").hidden = !hasBreaks;
      el("reconciliation-message").textContent = hasExecutionIssues
        ? "Broker execution history needs review. Trading is blocked; a position reset cannot resolve these issues."
        : hasPendingSync
        ? "New IB fills are awaiting synchronization. New orders are paused until reconciliation catches up; existing broker orders continue. No position reset is needed."
        : hasBreaks
        ? "IB official holdings do not match the active local ledger. Trading is blocked until the break is resolved or a trader confirms reset to IB."
        : "";
      const rows = payload.position_differences || [];
      el("reconciliation-table").innerHTML = rows.length ? `
        <table>
          <thead><tr><th>Symbol</th><th class="num">Local Qty</th><th class="num">IB Qty</th><th class="num">Difference</th></tr></thead>
          <tbody>${rows.map((row) => `<tr><td>${esc(row.symbol)}</td><td class="num">${esc(row.local_quantity)}</td><td class="num">${esc(row.ib_quantity)}</td><td class="num">${esc(row.difference)}</td></tr>`).join("")}</tbody>
        </table>
      ` : '<div class="empty">No position differences</div>';
      const warnings = [...(payload.warnings || [])];
      if ((payload.unmatched_local_orders || []).length) warnings.push(`${payload.unmatched_local_orders.length} unmatched local order(s).`);
      if ((payload.unmatched_ib_fills || []).length) warnings.push(`${payload.unmatched_ib_fills.length} unmatched IB fill(s).`);
      el("reconciliation-warnings").textContent = warnings.join("\\n");
      setButtons(Boolean(selectedProposal()));
    }

    function renderReconciliationUnavailable(message) {
      el("broker-portfolio").innerHTML = '<div class="empty-state">Portfolio unavailable. Sync to retrieve current IB holdings.</div>';
      el("reconciliation-panel").classList.add("reconciliation-break");
      el("reconciliation-checked").textContent = "IB unavailable";
      el("reconciliation-status").textContent = "Unavailable";
      el("reconciliation-ib-positions").textContent = "n/a";
      el("reconciliation-ib-cash").textContent = "n/a";
      el("reconciliation-break-count").textContent = "n/a";
      el("reset-to-ib-btn").hidden = true;
      el("reconciliation-message").hidden = false;
      el("reconciliation-message").textContent = "Fresh IB portfolio state could not be obtained. Trading is blocked.";
      el("reconciliation-table").innerHTML = "";
      el("reconciliation-warnings").textContent = message;
      setButtons(Boolean(selectedProposal()));
    }

    function renderAutomation(payload) {
      const stateText = payload.running ? "Running" : (payload.enabled ? "Starting" : "Manual mode");
      el("automation-state").textContent = stateText;
      el("auto-heartbeat").textContent = fmtDateTime(payload.heartbeat_at);
      el("auto-market-data").textContent = payload.last_market_data_refresh_at
        ? `${payload.last_market_data_date || "n/a"} / ${payload.last_market_data_bars_upserted ?? 0} bars`
        : "n/a";
      el("auto-fill-sync").textContent = payload.last_execution_sync_at
        ? `${fmtDateTime(payload.last_execution_sync_at)} / ${payload.last_execution_sync_records_updated ?? 0} records`
        : "n/a";
      el("auto-eod-pnl").textContent = payload.last_eod_pnl_date
        ? `${payload.last_eod_pnl_date} / ${fmtSignedMoney(payload.last_eod_pnl_total_cnh)}`
        : "n/a";
      el("auto-proposal").textContent = payload.last_rebalance_proposal_id || "n/a";
      el("auto-portfolio-alignment").textContent = `Portfolio alignment: ${payload.portfolio_alignment_message || "Waiting for a fresh portfolio check."}`;
      el("proposal-readiness").textContent = payload.portfolio_alignment_status === "blocked"
        ? payload.portfolio_alignment_message : "";
      const alignment = payload.portfolio_alignment || {};
      el("auto-portfolio-valuation").textContent = `Trigger: ${(Number(payload.rebalance_drift_threshold || 0.02) * 100).toFixed(2)} percentage points per holding. Prices: ${alignment.valuation_date || "unavailable"} daily close. Targets: ${alignment.target_as_of || "unavailable"}.`;
      const driftView = el("auto-portfolio-drift");
      driftView.replaceChildren();
      if ((alignment.holdings || []).length) {
        const table = document.createElement("table");
        const header = table.createTHead().insertRow();
        for (const label of ["Holding", "Shares", "Actual weight", "Target weight", "Difference (pp)"]) {
          const cell = document.createElement("th"); cell.textContent = label; header.appendChild(cell);
        }
        const body = table.createTBody();
        for (const holding of alignment.holdings) {
          const row = body.insertRow();
          for (const value of [holding.symbol, holding.quantity, fmtPct(holding.actual_weight), fmtPct(holding.target_weight), (Number(holding.drift) * 100).toFixed(2)]) {
            row.insertCell().textContent = value;
          }
        }
        driftView.appendChild(table);
      }
      const events = payload.events || [];
      const warningLines = [];
      if (payload.last_error) warningLines.push(payload.last_error);
      for (const event of events) {
        if (event.status === "warning" || event.status === "error") {
          const line = `${fmtDateTime(event.timestamp)} ${event.event_type}: ${event.message}`;
          if (!warningLines.includes(line)) warningLines.push(line);
        }
      }
      el("automation-warnings").textContent = warningLines.slice(0, 6).join("\\n");
      if (!events.length) {
        el("automation-events").innerHTML = '<div class="empty">No automation events</div>';
        return;
      }
      el("automation-events").innerHTML = `
        <table>
          <thead><tr><th>Time</th><th>Event</th><th>Status</th><th>Message</th></tr></thead>
          <tbody>
            ${events.slice(0, 8).map((event) => `
              <tr>
                <td>${esc(fmtDateTime(event.timestamp))}</td>
                <td>${esc(event.event_type)}</td>
                <td>${esc(event.status)}</td>
                <td>${esc(event.message)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderPerformance(payload) {
      state.performance.payload = payload;
      el("perf-strategy-nav").textContent = fmtMaybeMoney(payload.latest_strategy_nav_cnh);
      el("perf-strategy-return").textContent = fmtMaybePct(payload.strategy_total_return);
      el("perf-account-nav").textContent = fmtMaybeMoney(payload.latest_account_nav_cnh);
      el("perf-account-return").textContent = fmtMaybePct(payload.account_total_return);
      el("performance-warnings").textContent = (payload.warnings || []).join("\\n");
      const strategyAll = normalizedPerformanceSeries(payload.strategy || []);
      const accountAll = normalizedPerformanceSeries(payload.account || []);
      const extent = performanceExtent(strategyAll, accountAll);
      if (!extent) {
        el("performance-chart").innerHTML = '<div class="empty">No performance data</div>';
        el("performance-legend").innerHTML = "";
        el("performance-analysis").innerHTML = "";
        el("performance-alignment").textContent = "";
        el("performance-hover").textContent = "No observations to inspect.";
        state.performance.start = state.performance.end = "";
        updatePerformanceControls();
        return;
      }
      if (state.performance.rangeKey === "custom") {
        state.performance.start = clampDateText(state.performance.start || extent.minDate, extent.minDate, extent.maxDate);
        state.performance.end = clampDateText(state.performance.end || extent.maxDate, extent.minDate, extent.maxDate);
      } else {
        applyPerformanceRangeKey(extent, state.performance.rangeKey);
      }
      if (state.performance.start > state.performance.end) {
        const previousStart = state.performance.start;
        state.performance.start = state.performance.end;
        state.performance.end = previousStart;
      }
      updatePerformanceControls();
      const strategy = filterPerformanceSeries(strategyAll, state.performance.start, state.performance.end);
      const account = filterPerformanceSeries(accountAll, state.performance.start, state.performance.end);
      const svg = performanceSvg(strategy, account, payload);
      el("performance-chart").innerHTML = svg;
      bindPerformanceInteraction(strategy, account);
      el("performance-hover").textContent = strategy.length || account.length
        ? "Hover or tap for dates and values. Drag to select a period; arrow keys inspect points."
        : "No observations in the selected period.";
      el("perf-strategy-nav").textContent = fmtMaybeMoney(strategy.at(-1)?.nav_cnh);
      el("perf-account-nav").textContent = fmtMaybeMoney(account.at(-1)?.nav_cnh);
      el("perf-strategy-return").textContent = fmtMaybePct(performanceStats("Strategy", strategy).totalReturn);
      el("perf-account-return").textContent = fmtMaybePct(performanceStats("Account", account).totalReturn);
      el("performance-alignment").textContent = payload.account_alignment_date
        ? `Aligned on ${payload.account_alignment_date}: account CNH ${fmtMoney(payload.account_alignment_nav_cnh)} = strategy index ${Number(payload.account_alignment_strategy_index).toFixed(2)}. The alignment stays fixed when zooming. Strategy uses the left axis; account CNH uses the right.`
        : `Account has ${payload.account_tracking_start_date ? "no shared strategy date yet" : "not built a position since the reset"}. Axes are independent until tracking begins. Account history starts ${accountAll[0]?.trade_date || "n/a"}.`;
      el("performance-legend").innerHTML = `
        <span class="legend-item"><span class="swatch"></span>Theoretical strategy · left index</span>
        <span class="legend-item"><span class="swatch account"></span>Actual account · right CNH</span>
      `;
      renderPerformanceAnalysis(strategy, account);
    }

    function normalizedPerformanceSeries(series) {
      return series
        .map((point) => ({
          trade_date: String(point.trade_date || "").slice(0, 10),
          index: Number(point.index),
          nav_cnh: Number(point.nav_cnh),
          time: Date.parse(point.trade_date)
        }))
        .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.index) && point.index > 0 && Number.isFinite(point.nav_cnh) && point.nav_cnh > 0)
        .sort((a, b) => a.time - b.time);
    }

    function performanceExtent(strategy, account) {
      const all = [...strategy, ...account];
      if (!all.length) return null;
      const minTime = Math.min(...all.map((point) => point.time));
      const maxTime = Math.max(...all.map((point) => point.time));
      return {
        minDate: dateTextFromTime(minTime),
        maxDate: dateTextFromTime(maxTime)
      };
    }

    function dateTextFromTime(time) {
      return new Date(time).toISOString().slice(0, 10);
    }

    function shiftDateText(dateText, { months = 0, years = 0 } = {}) {
      const date = new Date(`${dateText}T00:00:00Z`);
      const day = date.getUTCDate();
      date.setUTCDate(1);
      if (years) date.setUTCFullYear(date.getUTCFullYear() + years);
      if (months) date.setUTCMonth(date.getUTCMonth() + months);
      const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
      date.setUTCDate(Math.min(day, lastDay));
      return date.toISOString().slice(0, 10);
    }

    function clampDateText(dateText, minDate, maxDate) {
      if (dateText < minDate) return minDate;
      if (dateText > maxDate) return maxDate;
      return dateText;
    }

    function applyPerformanceRangeKey(extent, rangeKey) {
      const end = extent.maxDate;
      let start = extent.minDate;
      if (rangeKey === "1m") start = shiftDateText(end, { months: -1 });
      if (rangeKey === "3m") start = shiftDateText(end, { months: -3 });
      if (rangeKey === "6m") start = shiftDateText(end, { months: -6 });
      if (rangeKey === "ytd") start = `${end.slice(0, 4)}-01-01`;
      if (rangeKey === "1y") start = shiftDateText(end, { years: -1 });
      if (rangeKey === "tracking") start = state.performance.payload.account_alignment_date || state.performance.payload.account?.[0]?.trade_date || start;
      state.performance.start = clampDateText(start, extent.minDate, extent.maxDate);
      state.performance.end = end;
    }

    function updatePerformanceControls() {
      document.querySelectorAll("[data-perf-range]").forEach((button) => {
        button.classList.toggle("active", button.dataset.perfRange === state.performance.rangeKey);
      });
      el("perf-range-start").value = state.performance.start || "";
      el("perf-range-end").value = state.performance.end || "";
    }

    function filterPerformanceSeries(series, start, end) {
      return series.filter((point) => point.trade_date >= start && point.trade_date <= end);
    }

    function performanceGeometry(strategy, account, payload = {}) {
      const width = Math.max(el("performance-chart").clientWidth - 24, 320), height = 300;
      const pad = { left: 56, right: 96, top: 30, bottom: 28 };
      const all = [...strategy, ...account];
      if (!all.length) return null;
      const minTime = Math.min(...all.map(p => p.time)), maxTime = Math.max(...all.map(p => p.time));
      const factor = Number(payload.account_alignment_nav_cnh) > 0 && Number(payload.account_alignment_strategy_index) > 0
        ? Number(payload.account_alignment_strategy_index) / Number(payload.account_alignment_nav_cnh) : null;
      const bounds = values => {
        if (!values.length) return [0, 100];
        const low = Math.min(...values), high = Math.max(...values);
        const margin = Math.max((high - low) * .1, Math.abs(high) * .005, .01);
        return [low - margin, high + margin];
      };
      const leftValues = strategy.map(p => p.index);
      if (factor) leftValues.push(...account.map(p => Number(p.nav_cnh) * factor));
      const [leftMin, leftMax] = bounds(leftValues);
      const [rightMin, rightMax] = factor ? [leftMin / factor, leftMax / factor] : bounds(account.map(p => Number(p.nav_cnh)));
      const x = time => pad.left + (maxTime === minTime ? .5 : (time - minTime) / (maxTime - minTime)) * (width - pad.left - pad.right);
      const y = (value, low, high) => height - pad.bottom - (value - low) / (high - low) * (height - pad.top - pad.bottom);
      return { width, height, pad, minTime, maxTime, leftMin, leftMax, rightMin, rightMax, x,
        strategyY: p => y(p.index, leftMin, leftMax), accountY: p => y(Number(p.nav_cnh), rightMin, rightMax) };
    }

    function performanceSvg(strategy, account, payload = {}) {
      const g = performanceGeometry(strategy, account, payload);
      if (!g) return '<div class="empty">No performance data in selected period</div>';
      const {width, height, pad, x} = g;
      const pathFor = (series, y) => series.map((p, i) => `${i && p.time - series[i-1].time <= 7 * 86400000 ? "L" : "M"} ${x(p.time).toFixed(2)} ${y(p).toFixed(2)}`).join(" ");
      // Dense markers obscure the line at full history. Keep every line point and
      // every hover observation, showing markers only for short series.
      const dots = (series, y, cls) => (series.length <= 45 ? series : [series.at(-1)])
        .map(p => `<circle class="${cls}" cx="${x(p.time)}" cy="${y(p)}" r="3"></circle>`).join("");
      const grid = [0, .25, .5, .75, 1].map(f => {
        const yy = height - pad.bottom - f * (height - pad.top - pad.bottom);
        return `<line class="grid-line" x1="${pad.left}" x2="${width-pad.right}" y1="${yy}" y2="${yy}"></line>
          <text x="${pad.left-8}" y="${yy+4}" text-anchor="end" fill="#2456a6" font-size="11">${strategy.length ? (g.leftMin+f*(g.leftMax-g.leftMin)).toFixed(1) : "—"}</text>
          <text x="${width-pad.right+8}" y="${yy+4}" fill="#0f766e" font-size="11">${account.length ? fmtMoney(g.rightMin+f*(g.rightMax-g.rightMin)) : "—"}</text>`;
      }).join("");
      return `
        <svg viewBox="0 0 ${width} ${height}" role="group" tabindex="0" aria-label="Interactive strategy and account performance. Drag to select dates. Arrow keys inspect observations. Escape clears selection.">
          <text x="${pad.left}" y="14" fill="#2456a6" font-size="12">Strategy index</text>
          <text x="${width-pad.right}" y="14" fill="#0f766e" font-size="12" text-anchor="end">Account CNH</text>
          ${grid}
          <text x="${pad.left}" y="${height-7}" fill="#657083" font-size="11">${dateTextFromTime(g.minTime)}</text>
          <text x="${width-pad.right}" y="${height-7}" text-anchor="end" fill="#657083" font-size="11">${dateTextFromTime(g.maxTime)}</text>
          ${strategy.length > 1 ? `<path class="strategy-line" d="${pathFor(strategy,g.strategyY)}"></path>` : ""}
          ${account.length > 1 ? `<path class="account-line" d="${pathFor(account,g.accountY)}"></path>` : ""}
          ${dots(strategy,g.strategyY,"strategy-dot")}${dots(account,g.accountY,"account-dot")}
          <rect class="perf-selection" y="${pad.top}" height="${height-pad.top-pad.bottom}" width="0" visibility="hidden"></rect>
          <line class="perf-crosshair" y1="${pad.top}" y2="${height-pad.bottom}" visibility="hidden"></line>
          <rect class="perf-hit-area" x="${pad.left}" y="${pad.top}" width="${width-pad.left-pad.right}" height="${height-pad.top-pad.bottom}" fill="transparent" style="cursor:crosshair"></rect>
        </svg>
      `;
    }

    function bindPerformanceInteraction(strategy, account) {
      const svg = el("performance-chart").querySelector("svg");
      if (!svg) return;
      const g = performanceGeometry(strategy, account, state.performance.payload);
      const dates = [...new Set([...strategy,...account].map(p => p.time))].sort((a,b) => a-b);
      const strategyMap = new Map(strategy.map(p => [p.time,p])), accountMap = new Map(account.map(p => [p.time,p]));
      const crosshair = svg.querySelector(".perf-crosshair"), selection = svg.querySelector(".perf-selection"), hit = svg.querySelector(".perf-hit-area");
      let dragStart = null, cursor = dates.length-1;
      const pointerX = event => Math.max(g.pad.left,Math.min(g.width-g.pad.right,new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse()).x));
      const timeAt = xx => g.minTime+(xx-g.pad.left)/(g.width-g.pad.left-g.pad.right)*(g.maxTime-g.minTime);
      const nearest = time => dates.reduce((best,t,i) => Math.abs(t-time)<Math.abs(dates[best]-time)?i:best,0);
      const show = index => {
        cursor = index;
        const time = dates[index], s = strategyMap.get(time), a = accountMap.get(time);
        crosshair.setAttribute("x1",g.x(time)); crosshair.setAttribute("x2",g.x(time)); crosshair.setAttribute("visibility","visible");
        el("performance-hover").textContent = `${dateTextFromTime(time)} · Strategy ${s ? `index ${s.index.toFixed(2)} / CNH ${fmtMoney(s.nav_cnh)}` : "no observation"} · Account ${a ? `CNH ${fmtMoney(a.nav_cnh)}` : "no observation"}`;
      };
      hit.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        dragStart = pointerX(event); hit.setPointerCapture(event.pointerId); svg.focus();
        selection.setAttribute("x",dragStart); selection.setAttribute("width",0); selection.setAttribute("visibility","visible");
        show(nearest(timeAt(dragStart)));
      });
      hit.addEventListener("pointermove", event => {
        const xx = pointerX(event); show(nearest(timeAt(xx)));
        if (dragStart !== null) { selection.setAttribute("x",Math.min(xx,dragStart)); selection.setAttribute("width",Math.abs(xx-dragStart)); }
      });
      hit.addEventListener("pointerup", event => {
        if (dragStart === null) return;
        const xx = pointerX(event), start = dragStart; dragStart = null;
        selection.setAttribute("visibility","hidden");
        if (hit.hasPointerCapture(event.pointerId)) hit.releasePointerCapture(event.pointerId);
        if (Math.abs(xx-start)<5) return;
        const first = dates[nearest(timeAt(Math.min(xx,start)))], last = dates[nearest(timeAt(Math.max(xx,start)))];
        state.performance.rangeKey = "custom";
        state.performance.start = dateTextFromTime(first); state.performance.end = dateTextFromTime(last);
        renderPerformance(state.performance.payload);
        el("performance-hover").textContent = `Selected ${state.performance.start} to ${state.performance.end}. Statistics below use observations in this period. Use All to restore full history.`;
      });
      hit.addEventListener("pointercancel", () => { dragStart = null; selection.setAttribute("visibility","hidden"); });
      svg.addEventListener("keydown", event => {
        if (["ArrowLeft","ArrowRight"].includes(event.key)) { event.preventDefault(); show(Math.max(0,Math.min(dates.length-1,cursor+(event.key==="ArrowRight"?1:-1)))); }
        if (event.key === "Escape") {
          state.performance.rangeKey="all"; renderPerformance(state.performance.payload);
          el("performance-chart").querySelector("svg")?.focus();
        }
      });
    }

    function renderPerformanceAnalysis(strategy, account) {
      const rows = [
        performanceStats("Strategy", strategy),
        performanceStats("Account NAV (includes cash flows)", account)
      ];
      el("performance-analysis").innerHTML = `
        <table>
          <thead><tr><th>Series</th><th class="num">Points</th><th>Start</th><th>End</th><th class="num">Return</th><th class="num">Ann Vol</th><th class="num">Sharpe</th><th class="num">Max DD</th><th class="num">Calmar</th></tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${esc(row.label)}</td>
                <td class="num">${esc(row.points)}</td>
                <td>${esc(row.start || "n/a")}</td>
                <td>${esc(row.end || "n/a")}</td>
                <td class="num">${fmtMaybePct(row.totalReturn)}</td>
                <td class="num">${fmtMaybePct(row.annualVolatility)}</td>
                <td class="num">${fmtMaybeRatio(row.sharpe)}</td>
                <td class="num">${fmtMaybePct(row.maxDrawdown)}</td>
                <td class="num">${fmtMaybeRatio(row.calmar)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function performanceStats(label, series) {
      const points = [...series].sort((a, b) => a.time - b.time);
      const stats = {
        label,
        points: points.length,
        start: points[0]?.trade_date || null,
        end: points[points.length - 1]?.trade_date || null,
        totalReturn: null,
        annualVolatility: null,
        sharpe: null,
        maxDrawdown: null,
        calmar: null
      };
      if (points.length < 2) return stats;
      const first = points[0];
      const last = points[points.length - 1];
      const days = Math.max((last.time - first.time) / 86400000, 1);
      stats.totalReturn = last.index / first.index - 1;
      const returns = [];
      const gaps = [];
      for (let index = 1; index < points.length; index += 1) {
        const previous = points[index - 1];
        const current = points[index];
        if (previous.index > 0) returns.push(current.index / previous.index - 1);
        gaps.push(Math.max((current.time - previous.time) / 86400000, 1));
      }
      if (returns.length > 1) {
        const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
        const variance = returns.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / (returns.length - 1);
        const stdev = Math.sqrt(variance);
        const averageGapDays = gaps.reduce((sum, value) => sum + value, 0) / gaps.length;
        const periodsPerYear = 365.25 / Math.max(averageGapDays, 1);
        stats.annualVolatility = stdev * Math.sqrt(periodsPerYear);
        stats.sharpe = stdev > 0 ? (mean / stdev) * Math.sqrt(periodsPerYear) : null;
      }
      let peak = first.index;
      let maxDrawdown = 0;
      points.forEach((point) => {
        peak = Math.max(peak, point.index);
        maxDrawdown = Math.min(maxDrawdown, point.index / peak - 1);
      });
      stats.maxDrawdown = maxDrawdown;
      const annualReturn = (last.index > 0 && first.index > 0)
        ? (last.index / first.index) ** (365.25 / days) - 1
        : null;
      stats.calmar = annualReturn !== null && maxDrawdown < 0 ? annualReturn / Math.abs(maxDrawdown) : null;
      return stats;
    }

    function fmtMaybeRatio(value) {
      return value === null || value === undefined || !Number.isFinite(Number(value)) ? "n/a" : Number(value).toFixed(2);
    }

    function renderHoldings(payload) {
      el("holdings-as-of").textContent = payload.as_of ? `as of ${payload.as_of}` : "n/a";
      el("holdings-warnings").textContent = (payload.warnings || []).join("\\n");
      const rows = payload.rows || [];
      if (!rows.length) {
        el("holdings-table").innerHTML = '<div class="empty">No holdings drift data</div>';
        return;
      }
      el("holdings-table").innerHTML = `
        <table>
          <thead><tr><th>Symbol</th><th class="num">Account Qty</th><th class="num">Account %</th><th class="num">Strategy %</th><th class="num">Target - Account</th><th>Trade</th><th class="num">Target CNH</th></tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${esc(row.symbol)}</td>
                <td class="num">${row.account_quantity ?? ""}</td>
                <td class="num">${fmtMaybePct(row.account_weight)}</td>
                <td class="num">${fmtPct(row.strategy_weight)}</td>
                <td class="num">${fmtSignedPct(row.weight_diff)}</td>
                <td>${row.trade_side ? `${esc(row.trade_side)} ${esc(row.trade_quantity)}` : ""}</td>
                <td class="num">${fmtMaybeMoney(row.target_value_cnh)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderLivePnl(payload) {
      const live = payload.status === "live";
      const money = value => value === null || value === undefined || !Number.isFinite(Number(value)) ? "n/a" : Number(value).toLocaleString(undefined, {minimumFractionDigits:2,maximumFractionDigits:2});
      const age = payload.age_seconds == null ? "" : ` · ${Math.floor(payload.age_seconds / 60)}m ${Math.floor(payload.age_seconds % 60)}s ago`;
      el("pnl-as-of").textContent = `${live ? "live" : payload.received_at ? "Last received · stale" : "unavailable"} · ${payload.account || "account pending"} · ${payload.received_at ? fmtDateTime(payload.received_at) : "no broker update"}${age}${payload.connected === false ? " · disconnected" : ""}`;
      el("pnl-realized").textContent = payload.currency ? money(payload.realized_pnl) : "n/a";
      el("pnl-unrealized").textContent = payload.currency ? money(payload.unrealized_pnl) : "n/a";
      el("pnl-total").textContent = payload.currency ? money(payload.daily_pnl) : "n/a";
      el("pnl-open-value").textContent = payload.currency || "unknown";
      el("live-pnl-warnings").textContent = (payload.warnings || []).join(" ");
      el("live-pnl-table").innerHTML = `<table><thead><tr><th>Symbol</th><th>Currency</th><th>Quantity</th><th>Daily PnL</th><th>Unrealized</th><th>Realized</th><th>Value</th><th>Update</th></tr></thead><tbody>${(payload.positions || []).map(row => `<tr><td>${esc(row.symbol)}</td><td>${esc(row.currency)}</td><td>${esc(row.quantity)}</td>${[row.daily_pnl,row.unrealized_pnl,row.realized_pnl,row.market_value].map(v => `<td class="num">${row.currency ? money(v) : "n/a"}</td>`).join("")}<td>${row.received_at ? `${row.stale ? "Last received · stale · " : ""}${esc(fmtDateTime(row.received_at))}` : "waiting for broker"}</td></tr>`).join("")}</tbody></table>`;
    }

    let livePnlLoading = false;
    let lastLivePnl = null;
    async function loadLivePnl() {
      if (livePnlLoading) return;
      livePnlLoading = true;
      try {
        lastLivePnl = await api("/api/v1/dashboard/pnl/live", {signal: AbortSignal.timeout(5000)});
        renderLivePnl(lastLivePnl);
      } catch (error) {
        const previous = lastLivePnl || {};
        renderLivePnl({...previous, status:"unavailable", connected:false,
          age_seconds: previous.received_at ? Math.max(0, (Date.now() - Date.parse(previous.received_at)) / 1000) : null,
          positions:(previous.positions || []).map(row => ({...row, stale:true})),
          warnings:[...(previous.warnings || []), `Feed refresh failed: ${error.message}. Values shown are last received, not current.`]});
      }
      finally { livePnlLoading = false; }
    }

    function renderPnl(payload, history) {
      const warnings = [...(payload.warnings || [])];
      if (payload.baseline_cutoff_at) warnings.push(`Accounting baseline cutoff: ${new Intl.DateTimeFormat('en-GB',{timeZone:'America/New_York',dateStyle:'medium',timeStyle:'medium',hourCycle:'h23'}).format(new Date(payload.baseline_cutoff_at))} New York.`);
      if (!payload.valuation_complete) warnings.push("PnL valuation is incomplete because one or more symbols could not be marked.");
      el("pnl-warnings").textContent = warnings.join("\\n");
      renderPnlTable(payload.symbols || []);
      const points = [...(history || [])].sort((a, b) => Date.parse(a.as_of) - Date.parse(b.as_of));
      if (!points.length) {
        el("pnl-chart").innerHTML = '<div class="empty">No saved PnL snapshots</div>';
        el("pnl-legend").innerHTML = "";
        return;
      }
      el("pnl-chart").innerHTML = pnlHistorySvg(points);
      el("pnl-legend").innerHTML = '<span class="legend-item"><span class="swatch pnl"></span>Total PnL</span>';
    }

    function renderExecutionQuality(payload) {
      el("exec-theoretical-pnl").textContent = fmtSignedMoney(payload.theoretical_pnl_cnh);
      el("exec-actual-pnl").textContent = fmtSignedMoney(payload.actual_pnl_cnh);
      el("exec-gain").textContent = fmtSignedMoney(payload.execution_gain_cnh);
      el("exec-bps").textContent = fmtMaybeBps(payload.execution_gain_bps);
      el("exec-missed-count").textContent = payload.missed_order_count || 0;
      el("exec-missed-notional").textContent = fmtMoney(payload.missed_notional_cnh);
      el("execution-quality-warnings").textContent = (payload.warnings || []).join("\\n");
      const currentPoint = {
        as_of: payload.as_of,
        actual_pnl_cnh: payload.actual_pnl_cnh,
        theoretical_pnl_cnh: payload.theoretical_pnl_cnh,
        execution_gain_cnh: payload.execution_gain_cnh
      };
      const history = [...(payload.history || [])];
      if (payload.as_of && !history.some((point) => String(point.as_of).slice(0, 10) === String(payload.as_of).slice(0, 10))) {
        history.push(currentPoint);
      }
      const points = history.sort((a, b) => Date.parse(a.as_of) - Date.parse(b.as_of));
      el("pnl-comparison-chart").innerHTML = pnlComparisonSvg(points);
      el("slippage-chart").innerHTML = slippageSvg(payload.slippage || []);
      el("execution-quality-legend").innerHTML = `
        <span class="legend-item"><span class="swatch pnl"></span>Real PnL</span>
        <span class="legend-item"><span class="swatch theoretical"></span>Reference Fill PnL</span>
        <span class="legend-item"><span class="swatch pnl"></span>Daily Slippage</span>
        <span class="legend-item"><span class="swatch theoretical"></span>Cumulative Slippage</span>
      `;
      renderExecutionSlippageTable(payload.rows || []);
      renderMissedOrdersTable(payload.missed_rows || []);
    }

    function renderMissedOrdersTable(rows) {
      if (!rows.length) {
        el("execution-missed-table").innerHTML = "";
        return;
      }
      el("execution-missed-table").innerHTML = `
        <div class="panel-head"><h2>Missed Rebalances</h2><span class="status-line">Not eligible for resubmission</span></div>
        <table>
          <thead><tr><th>Missed At</th><th>Proposal</th><th>Symbol</th><th>Side</th><th class="num">Qty</th><th class="num">Reference CNH</th></tr></thead>
          <tbody>${rows.map((row) => `<tr><td>${esc(fmtDateTime(row.missed_at))}</td><td>${esc(row.proposal_id)}</td><td>${esc(row.symbol)}</td><td>${esc(row.side)}</td><td class="num">${esc(row.quantity)}</td><td class="num">${fmtMoney(row.reference_notional_cnh)}</td></tr>`).join("")}</tbody>
        </table>`;
    }

    function renderExecutionSlippageTable(rows) {
      if (!rows.length) {
        el("execution-slippage-table").innerHTML = '<div class="empty">No filled executions</div>';
        return;
      }
      el("execution-slippage-table").innerHTML = `
        <table>
          <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th class="num">Qty</th><th class="num">Ref</th><th class="num">Fill</th><th class="num">Gain</th><th class="num">Bps</th></tr></thead>
          <tbody>
            ${rows.slice().reverse().map((row) => `
              <tr>
                <td>${esc(fmtDateTime(row.filled_at))}</td>
                <td>${esc(row.symbol)}</td>
                <td>${esc(row.side)}</td>
                <td class="num">${esc(row.filled_quantity)}</td>
                <td class="num">${fmtMoney(row.reference_price)}</td>
                <td class="num">${fmtMoney(row.average_fill_price)}</td>
                <td class="num">${fmtSignedMoney(row.execution_gain_cnh)}</td>
                <td class="num">${fmtMaybeBps(row.execution_gain_bps)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function pnlComparisonSvg(points) {
      const width = 760;
      const height = 260;
      const pad = { left: 64, right: 16, top: 16, bottom: 28 };
      const valid = points
        .map((point) => ({
          as_of: point.as_of,
          time: Date.parse(point.as_of),
          actual: Number(point.actual_pnl_cnh),
          theoretical: Number(point.theoretical_pnl_cnh)
        }))
        .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.actual) && Number.isFinite(point.theoretical));
      if (!valid.length) return '<div class="empty">No saved PnL comparison history</div>';
      const times = valid.map((point) => point.time);
      const values = valid.flatMap((point) => [point.actual, point.theoretical]);
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const valuePad = Math.max((maxValue - minValue) * 0.12, Math.max(...values.map((value) => Math.abs(value))) * 0.04, 10);
      const yMin = minValue - valuePad;
      const yMax = maxValue + valuePad;
      const x = (dateText) => {
        const time = Date.parse(dateText);
        if (maxTime === minTime) return (pad.left + width - pad.right) / 2;
        return pad.left + ((time - minTime) / (maxTime - minTime)) * (width - pad.left - pad.right);
      };
      const y = (value) => {
        if (yMax === yMin) return (pad.top + height - pad.bottom) / 2;
        return height - pad.bottom - ((Number(value) - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);
      };
      const pathFor = (key) => valid
        .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.as_of).toFixed(2)} ${y(point[key]).toFixed(2)}`)
        .join(" ");
      const yTicks = [0, 0.5, 1].map((fraction) => yMin + (yMax - yMin) * fraction);
      const grid = yTicks.map((value) => {
        const yy = y(value);
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy.toFixed(2)}" y2="${yy.toFixed(2)}"></line><text x="8" y="${(yy + 4).toFixed(2)}" fill="#657083" font-size="11">${fmtSignedMoney(value)}</text>`;
      }).join("");
      const startDate = new Date(minTime).toISOString().slice(0, 10);
      const endDate = new Date(maxTime).toISOString().slice(0, 10);
      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Real and reference-fill PnL comparison">
          ${grid}
          <line class="axis-line" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}"></line>
          <text x="${pad.left}" y="${height - 8}" fill="#657083" font-size="11">${esc(startDate)}</text>
          <text x="${width - pad.right - 70}" y="${height - 8}" fill="#657083" font-size="11">${esc(endDate)}</text>
          ${valid.length > 1 ? `<path class="actual-line" d="${pathFor("actual")}"></path>` : ""}
          ${valid.length > 1 ? `<path class="theoretical-line" d="${pathFor("theoretical")}"></path>` : ""}
        </svg>
      `;
    }

    function slippageSvg(points) {
      const width = 760;
      const height = 240;
      const pad = { left: 64, right: 16, top: 16, bottom: 28 };
      const valid = points
        .map((point) => ({
          trade_date: point.trade_date,
          time: Date.parse(point.trade_date),
          daily: Number(point.daily_slippage_cnh),
          cumulative: Number(point.cumulative_slippage_cnh)
        }))
        .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.daily) && Number.isFinite(point.cumulative));
      if (!valid.length) return '<div class="empty">No daily slippage history</div>';
      const times = valid.map((point) => point.time);
      const values = valid.flatMap((point) => [point.daily, point.cumulative, 0]);
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const valuePad = Math.max((maxValue - minValue) * 0.12, Math.max(...values.map((value) => Math.abs(value))) * 0.04, 10);
      const yMin = minValue - valuePad;
      const yMax = maxValue + valuePad;
      const x = (dateText) => {
        const time = Date.parse(dateText);
        if (maxTime === minTime) return (pad.left + width - pad.right) / 2;
        return pad.left + ((time - minTime) / (maxTime - minTime)) * (width - pad.left - pad.right);
      };
      const y = (value) => {
        if (yMax === yMin) return (pad.top + height - pad.bottom) / 2;
        return height - pad.bottom - ((Number(value) - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);
      };
      const zeroY = y(0);
      const barWidth = Math.max(5, Math.min(28, (width - pad.left - pad.right) / Math.max(valid.length, 1) * 0.55));
      const bars = valid.map((point) => {
        const cx = x(point.trade_date);
        const yy = y(point.daily);
        const top = Math.min(yy, zeroY);
        const barHeight = Math.max(Math.abs(zeroY - yy), 1);
        return `<rect x="${(cx - barWidth / 2).toFixed(2)}" y="${top.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" fill="#7c4a03" opacity="0.45"><title>${esc(point.trade_date)} daily slippage ${fmtSignedMoney(point.daily)}</title></rect>`;
      }).join("");
      const cumulativePath = valid
        .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.trade_date).toFixed(2)} ${y(point.cumulative).toFixed(2)}`)
        .join(" ");
      const yTicks = [0, 0.5, 1].map((fraction) => yMin + (yMax - yMin) * fraction);
      const grid = yTicks.map((value) => {
        const yy = y(value);
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy.toFixed(2)}" y2="${yy.toFixed(2)}"></line><text x="8" y="${(yy + 4).toFixed(2)}" fill="#657083" font-size="11">${fmtSignedMoney(value)}</text>`;
      }).join("");
      const startDate = new Date(minTime).toISOString().slice(0, 10);
      const endDate = new Date(maxTime).toISOString().slice(0, 10);
      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Daily and cumulative execution slippage">
          ${grid}
          <line class="axis-line" x1="${pad.left}" x2="${width - pad.right}" y1="${zeroY.toFixed(2)}" y2="${zeroY.toFixed(2)}"></line>
          <text x="${pad.left}" y="${height - 8}" fill="#657083" font-size="11">${esc(startDate)}</text>
          <text x="${width - pad.right - 70}" y="${height - 8}" fill="#657083" font-size="11">${esc(endDate)}</text>
          ${bars}
          ${valid.length > 1 ? `<path class="theoretical-line" d="${cumulativePath}"></path>` : ""}
        </svg>
      `;
    }

    function renderPnlTable(rows) {
      if (!rows.length) {
        el("pnl-table").innerHTML = '<div class="empty">No symbol PnL rows</div>';
        return;
      }
      el("pnl-table").innerHTML = `
        <table>
          <thead><tr><th>Symbol</th><th class="num">Qty</th><th class="num">Cost CNH</th><th class="num">Market CNH</th><th class="num">Realized</th><th class="num">Unrealized</th></tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${esc(row.symbol)}</td>
                <td class="num">${esc(row.quantity)}</td>
                <td class="num">${fmtMaybeMoney(row.cost_basis_cnh)}</td>
                <td class="num">${fmtMaybeMoney(row.market_value_cnh)}</td>
                <td class="num">${fmtSignedMoney(row.realized_pnl_cnh)}</td>
                <td class="num">${fmtSignedMoney(row.unrealized_pnl_cnh)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function pnlHistorySvg(points) {
      const width = 760;
      const height = 260;
      const pad = { left: 64, right: 16, top: 16, bottom: 28 };
      const valid = points.filter((point) => Number.isFinite(Date.parse(point.as_of)) && Number.isFinite(Number(point.total_pnl_cnh)));
      if (!valid.length) return '<div class="empty">No saved PnL snapshots</div>';
      const times = valid.map((point) => Date.parse(point.as_of));
      const values = valid.map((point) => Number(point.total_pnl_cnh));
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const valuePad = Math.max((maxValue - minValue) * 0.12, Math.max(...values.map((value) => Math.abs(value))) * 0.04, 10);
      const yMin = minValue - valuePad;
      const yMax = maxValue + valuePad;
      const x = (dateText) => {
        const time = Date.parse(dateText);
        if (maxTime === minTime) return (pad.left + width - pad.right) / 2;
        return pad.left + ((time - minTime) / (maxTime - minTime)) * (width - pad.left - pad.right);
      };
      const y = (value) => {
        if (yMax === yMin) return (pad.top + height - pad.bottom) / 2;
        return height - pad.bottom - ((Number(value) - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);
      };
      const path = valid
        .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.as_of).toFixed(2)} ${y(point.total_pnl_cnh).toFixed(2)}`)
        .join(" ");
      const dots = valid.map((point) => `<circle class="pnl-dot" cx="${x(point.as_of).toFixed(2)}" cy="${y(point.total_pnl_cnh).toFixed(2)}" r="3.5"><title>${esc(String(point.as_of).slice(0, 19))} total PnL ${fmtSignedMoney(point.total_pnl_cnh)}</title></circle>`).join("");
      const yTicks = [0, 0.5, 1].map((fraction) => yMin + (yMax - yMin) * fraction);
      const grid = yTicks.map((value) => {
        const yy = y(value);
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy.toFixed(2)}" y2="${yy.toFixed(2)}"></line><text x="8" y="${(yy + 4).toFixed(2)}" fill="#657083" font-size="11">${fmtSignedMoney(value)}</text>`;
      }).join("");
      const startDate = new Date(minTime).toISOString().slice(0, 10);
      const endDate = new Date(maxTime).toISOString().slice(0, 10);
      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Saved total PnL history">
          ${grid}
          <line class="axis-line" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}"></line>
          <text x="${pad.left}" y="${height - 8}" fill="#657083" font-size="11">${esc(startDate)}</text>
          <text x="${width - pad.right - 70}" y="${height - 8}" fill="#657083" font-size="11">${esc(endDate)}</text>
          ${valid.length > 1 ? `<path class="pnl-line" d="${path}"></path>` : ""}
          ${dots}
        </svg>
      `;
    }

    function renderList() {
      const list = el("proposal-list");
      if (!state.proposals.length) {
        list.innerHTML = '<div class="empty">No proposals</div>';
        return;
      }
      list.innerHTML = state.proposals.map((proposal) => `
        <button class="proposal-row ${proposal.status === "missed" ? "missed" : ""} ${proposal.proposal_id === state.selectedId ? "active" : ""}" data-id="${esc(proposal.proposal_id)}">
          <span>
            <span class="proposal-title">${esc(proposal.sleeve)}</span>
            <span class="meta">${esc(proposal.as_of)} | ${esc(proposal.proposal_id)} | ${proposal.orders.length} orders${proposal.execution_deadline_at ? ` | deadline ${esc(fmtDateTime(proposal.execution_deadline_at))}` : ""}</span>
          </span>
          <span class="badge ${esc(proposal.status)}">${esc(proposal.status)}</span>
        </button>
      `).join("");
      list.querySelectorAll(".proposal-row").forEach((button) => {
        button.addEventListener("click", async () => {
          state.selectedId = button.dataset.id;
          renderList();
          await renderSelected();
        });
      });
    }

    async function renderSelected() {
      const proposal = selectedProposal();
      if (proposal) state.brokerRecords = [];
      setButtons(Boolean(proposal));
      if (!proposal) {
        state.brokerRecords = [];
        el("metric-proposal").textContent = "n/a";
        el("metric-status").textContent = "n/a";
        el("metric-orders").textContent = "0";
        el("metric-notional").textContent = "0.00";
        el("metric-completion").textContent = "n/a";
        el("metric-filled").textContent = "0 / 0";
        el("proposal-detail").innerHTML = '<div class="empty">No proposal selected</div>';
        el("orders-table").innerHTML = '<div class="empty">No orders</div>';
        el("targets-table").innerHTML = '<div class="empty">No targets</div>';
        el("broker-records").innerHTML = '<div class="empty">No broker records</div>';
        setButtons(false);
        return;
      }
      const total = proposal.orders.reduce((sum, order) => sum + Number(order.notional_cnh || 0), 0);
      el("metric-proposal").textContent = proposal.proposal_id;
      el("metric-status").textContent = proposal.status;
      el("metric-orders").textContent = proposal.orders.length;
      el("metric-notional").textContent = fmtMoney(total);
      updateExecutionSummary([]);
      el("proposal-detail").innerHTML = `
        <table>
          <tbody>
            <tr><th>As Of</th><td>${esc(proposal.as_of)}</td></tr>
            <tr><th>Intended Trade</th><td>${esc(proposal.intended_trade_date || "n/a")}</td></tr>
            <tr><th>Execution Deadline</th><td>${esc(fmtDateTime(proposal.execution_deadline_at))}</td></tr>
            ${proposal.missed_reason ? `<tr><th>Missed</th><td>${esc(proposal.missed_reason)}</td></tr>` : ""}
            <tr><th>Summary</th><td>${esc(proposal.summary)}</td></tr>
            <tr><th>Reasoning</th><td>${esc(proposal.reasoning?.summary || "")}</td></tr>
            <tr><th>Drivers</th><td>${esc((proposal.reasoning?.drivers || []).join("; "))}</td></tr>
          </tbody>
        </table>
      `;
      renderOrders(proposal);
      renderTargets(proposal);
      await renderBrokerRecords(proposal.proposal_id);
    }

    function renderOrders(proposal) {
      if (!proposal.orders.length) {
        el("orders-table").innerHTML = '<div class="empty">No orders</div>';
        return;
      }
      el("orders-table").innerHTML = `
        <table>
          <thead><tr><th>Symbol</th><th>Side</th><th class="num">Qty</th><th>Type</th><th class="num">Ref</th><th class="num">CNH</th></tr></thead>
          <tbody>
            ${proposal.orders.map((order) => `
              <tr>
                <td>${esc(order.symbol)}</td>
                <td>${esc(order.side)}</td>
                <td class="num">${esc(order.quantity)}</td>
                <td>${esc(order.order_type)}</td>
                <td class="num">${fmtMoney(order.reference_price)}</td>
                <td class="num">${fmtMoney(order.notional_cnh)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderTargets(proposal) {
      if (!proposal.targets.length) {
        el("targets-table").innerHTML = '<div class="empty">No targets</div>';
        return;
      }
      const targets = [...proposal.targets].sort((a, b) => Number(b.target_weight) - Number(a.target_weight));
      el("targets-table").innerHTML = `
        <table>
          <thead><tr><th>Symbol</th><th class="num">Weight</th><th>Rationale</th></tr></thead>
          <tbody>
            ${targets.map((target) => `
              <tr>
                <td>${esc(target.symbol)}</td>
                <td class="num">${fmtPct(target.target_weight)}</td>
                <td>${esc(target.rationale)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    async function renderBrokerRecords(proposalId) {
      const records = await api(`/api/v1/execution/interactive-brokers/orders?proposal_id=${encodeURIComponent(proposalId)}`);
      state.brokerRecords = records;
      setButtons(Boolean(selectedProposal()));
      updateExecutionSummary(records);
      if (!records.length) {
        el("broker-records").innerHTML = '<div class="empty">No broker records</div>';
        return;
      }
      el("broker-records").innerHTML = `
        <table>
          <thead><tr><th>Order ID</th><th>Status</th><th>Symbol</th><th class="num">Filled</th><th class="num">Done</th><th class="num">Broker ID</th></tr></thead>
          <tbody>
            ${records.map((record) => `
              <tr>
                <td>${esc(record.local_order_id)}</td>
                <td>${esc(record.status)}</td>
                <td>${esc(record.order.symbol)}</td>
                <td class="num">${esc(record.filled_quantity || 0)} / ${esc(record.order.quantity || 0)}</td>
                <td class="num">${fmtCompletion(record)}</td>
                <td class="num">${esc(record.broker_order_id ?? "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function updateExecutionSummary(records) {
      const proposal = selectedProposal();
      if (!proposal) {
        el("metric-completion").textContent = "n/a";
        el("metric-filled").textContent = "0 / 0";
        return;
      }
      const targetQuantity = proposal.orders.reduce((sum, order) => sum + Number(order.quantity || 0), 0);
      const latestByIndex = new Map();
      records.forEach((record) => {
        const current = latestByIndex.get(record.order_index);
        if (!current || String(record.updated_at || "") >= String(current.updated_at || "")) {
          latestByIndex.set(record.order_index, record);
        }
      });
      const filledQuantity = [...latestByIndex.values()].reduce((sum, record) => sum + Number(record.filled_quantity || 0), 0);
      const completion = targetQuantity > 0 ? filledQuantity / targetQuantity : 0;
      el("metric-completion").textContent = `${(completion * 100).toFixed(1)}%`;
      el("metric-filled").textContent = `${filledQuantity} / ${targetQuantity}`;
    }

    function fmtCompletion(record) {
      const quantity = Number(record.order?.quantity || 0);
      if (quantity <= 0) return "n/a";
      const filled = Math.max(Number(record.filled_quantity || 0), 0);
      return `${Math.min((filled / quantity) * 100, 100).toFixed(1)}%`;
    }

    function selectedProposal() {
      return state.proposals.find((proposal) => proposal.proposal_id === state.selectedId) || null;
    }

    function setButtons(enabled) {
      const proposal = selectedProposal();
      const brokerReady = state.reconciliation && !state.reconciliation.has_breaks && !state.reconciliation.unavailable;
      const canDecide = enabled && proposal && proposal.status === "pending" && brokerReady;
      el("approve-btn").disabled = !canDecide;
      el("reject-btn").disabled = !canDecide;
      const retryable = retryableOrderIndexes();
      el("resubmit-failed-btn").hidden = !retryable.length;
      el("resubmit-failed-btn").disabled = !enabled || !retryable.length || !brokerReady;
    }

    function retryableOrderIndexes() {
      const proposal = selectedProposal();
      if (!proposal) return [];
      const latestByIndex = new Map();
      state.brokerRecords.forEach((record) => {
        const current = latestByIndex.get(record.order_index);
        if (!current || String(record.updated_at || "") >= String(current.updated_at || "")) {
          latestByIndex.set(record.order_index, record);
        }
      });
      if (!latestByIndex.size && proposal.status === "approved" && proposal.orders.length) {
        return proposal.orders.map((_order, index) => index);
      }
      const retryable = [...latestByIndex.values()]
        .filter((record) => ["rejected", "cancelled"].includes(record.status))
        .map((record) => record.order_index);
      if (latestByIndex.size) {
        proposal.orders.forEach((_order, index) => {
          if (!latestByIndex.has(index)) retryable.push(index);
        });
      }
      return retryable;
    }

    function log(message, isError = false) {
      el("action-log").className = isError ? "log error" : "log";
      el("action-log").textContent = message;
    }

    function submitResultMessage(result, prefix) {
      const records = result.records || [];
      const rejected = records.filter((record) => ["rejected", "cancelled"].includes(record.status));
      if (rejected.length) {
        return `${prefix} ${records.length} TWAP paper order(s); ${rejected.length} failed and can be resubmitted`;
      }
      return `${prefix} ${records.length} TWAP paper order(s)`;
    }

    async function decide(status) {
      const proposal = selectedProposal();
      if (!proposal) return;
      try {
        setButtons(false);
        const comment = el("decision-comment").value;
        if (status === "approved") {
          log(`Approving ${proposal.proposal_id}; submitting TWAP paper orders...`);
          const result = await api(`/api/v1/proposals/${encodeURIComponent(proposal.proposal_id)}/approve-and-submit`, {
            method: "POST",
            body: JSON.stringify({ comment })
          });
          log(submitResultMessage(result.broker_submission || {}, "Approved and submitted"));
          await renderBrokerRecords(proposal.proposal_id);
        } else {
          await api(`/api/v1/proposals/${encodeURIComponent(proposal.proposal_id)}/decisions`, {
            method: "POST",
            body: JSON.stringify({ status, comment })
          });
          log(`${status} ${proposal.proposal_id}`);
        }
        await loadProposals();
      } catch (error) {
        log(error.message, true);
        await loadProposals();
        await renderBrokerRecords(proposal.proposal_id);
      }
    }

    async function resubmitFailed() {
      const proposal = selectedProposal();
      if (!proposal) return;
      const retryable = retryableOrderIndexes();
      if (!retryable.length) return;
      if (!confirm(`Resubmit ${retryable.length} failed or missing TWAP paper orders for ${proposal.proposal_id}?`)) return;
      try {
        const result = await api(`/api/v1/execution/interactive-brokers/proposals/${encodeURIComponent(proposal.proposal_id)}/submit`, {
          method: "POST",
          body: JSON.stringify({ environment: "paper", confirm_submit: true, failed_only: true, route_order_type: "twap" })
        });
        log(`Resubmitted ${result.records.length} failed or missing TWAP paper orders`);
        await renderBrokerRecords(proposal.proposal_id);
        await loadDashboardData();
      } catch (error) {
        log(error.message, true);
      }
    }

    async function resetPortfolioToIb() {
      const reconciliation = state.reconciliation;
      if (!reconciliation?.requires_operator_confirmation) return;
      const confirmed = confirm(
        `Reset active portfolio and PnL state to the fresh IB snapshot with ${reconciliation.ib_position_count || 0} position(s)? ` +
        "Historical orders and fills will remain immutable audit records."
      );
      if (!confirmed) return;
      el("reset-to-ib-btn").disabled = true;
      try {
        await api("/api/v1/dashboard/reconciliation/interactive-brokers/reset-to-broker", {
          method: "POST",
          body: JSON.stringify({ confirm_reset_to_ib: true })
        });
        log("Active portfolio and PnL state reset to the official IB snapshot.");
        await loadDashboardData();
      } catch (error) {
        log(error.message, true);
      } finally {
        el("reset-to-ib-btn").disabled = false;
      }
    }

    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", async () => {
        document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        state.filter = button.dataset.filter || "";
        state.selectedId = null;
        await loadProposals();
      });
    });
    el("refresh-btn").addEventListener("click", async () => {
      await loadProposals();
      await loadDashboardData();
    });
    el("refresh-reconciliation-btn").addEventListener("click", () => {
      loadDashboardData().catch((error) => log(error.message, true));
    });
    el("reset-to-ib-btn").addEventListener("click", resetPortfolioToIb);
    el("approve-btn").addEventListener("click", () => decide("approved"));
    el("reject-btn").addEventListener("click", () => decide("rejected"));
    el("resubmit-failed-btn").addEventListener("click", resubmitFailed);
    document.querySelectorAll("[data-perf-range]").forEach((button) => {
      button.addEventListener("click", () => {
        state.performance.rangeKey = button.dataset.perfRange || "3m";
        if (state.performance.payload) renderPerformance(state.performance.payload);
      });
    });
    el("perf-range-start").addEventListener("change", () => {
      state.performance.rangeKey = "custom";
      state.performance.start = el("perf-range-start").value;
      if (state.performance.payload) renderPerformance(state.performance.payload);
    });
    el("perf-range-end").addEventListener("change", () => {
      state.performance.rangeKey = "custom";
      state.performance.end = el("perf-range-end").value;
      if (state.performance.payload) renderPerformance(state.performance.payload);
    });
    loadLivePnl();
    setInterval(loadLivePnl, 2000);

    let performanceResizeFrame = null;
    window.addEventListener("resize", () => {
      cancelAnimationFrame(performanceResizeFrame);
      performanceResizeFrame = requestAnimationFrame(() => {
        if (state.performance.payload) renderPerformance(state.performance.payload);
      });
    });

    Promise.all([loadProposals(), loadDashboardData()]).catch((error) => {
      el("connection-status").textContent = "API error";
      log(error.message, true);
    });
    setInterval(() => {
      loadDashboardData().catch((error) => log(error.message, true));
    }, 60000);
    setInterval(() => {
      if (document.visibilityState === "visible") {
        loadProposals({ background: true }).catch((error) => log(error.message, true));
        api("/api/v1/automation/status").then(renderAutomation).catch((error) => log(error.message, true));
        api("/api/v1/dashboard/reconciliation/interactive-brokers").then(renderReconciliation).catch((error) => log(error.message, true));
      }
    }, 15000);
  </script>
</body>
</html>
"""


_STRATEGIES_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Strategy Catalog</title><style>
:root{--bg:#f6f7f9;--panel:#fff;--text:#1d2433;--muted:#667085;--line:#d9dee7;--focus:#2456a6;--good:#087f5b}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px Inter,Segoe UI,Arial,sans-serif}header{height:56px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid var(--line)}h1,h2{margin:0;letter-spacing:0}h1{font-size:18px}h2{font-size:15px}.actions{display:flex;gap:8px;align-items:center}.button{min-height:32px;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--text);text-decoration:none;display:inline-flex;align-items:center;justify-content:center}.layout{display:grid;grid-template-columns:minmax(500px,1.35fr) minmax(340px,.65fr);min-height:calc(100vh - 56px)}main,aside{padding:16px;min-width:0}aside{border-left:1px solid var(--line);background:#fbfcfd}.panel{background:#fff;border:1px solid var(--line);border-radius:7px;overflow:hidden}.head{padding:12px 14px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.note{color:var(--muted);font-size:12px}.table-wrap{overflow:auto;max-height:calc(100vh - 145px)}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:9px 10px;border-bottom:1px solid #edf0f4;text-align:left;white-space:nowrap}th{position:sticky;top:0;background:#f8fafc;color:var(--muted);font-weight:650}td.num,th.num{text-align:right}.strategy-row{cursor:pointer}.strategy-row:hover,.strategy-row.active{background:#eef4fb}.sota{display:inline-block;margin-left:6px;padding:2px 6px;border:1px solid #9cd6cd;border-radius:999px;background:#ecf9f6;color:var(--good);font-size:10px;font-weight:700}.details{padding:14px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}.metric{border-bottom:1px solid #edf0f4;padding:8px 0}.metric label{display:block;color:var(--muted);font-size:11px}.metric strong{display:block;margin-top:3px;font-size:15px}.path{overflow-wrap:anywhere;color:var(--muted);font:11px Consolas,monospace}.alloc{margin-top:14px}.bar{height:7px;background:#e8edf4;margin-top:4px}.fill{height:100%;background:#2456a6}.empty{padding:24px;color:var(--muted);text-align:center}@media(max-width:850px){header{height:auto;align-items:flex-start;flex-direction:column;padding:10px 12px}.actions{width:100%;flex-wrap:wrap}.actions .button{flex:1 1 110px}.layout{grid-template-columns:1fr}.table-wrap{max-height:none}aside{border-left:0;border-top:1px solid var(--line)}}
</style></head><body><header><h1>Strategy Catalog</h1><div class="actions"><a class="button" href="/operator">Trading</a><a class="button" href="/strategies">Strategies</a><a class="button" href="/platform">System</a><a class="button" href="/platform/market-data-audit">Market Data</a></div></header>
<div class="layout"><main><section class="panel"><div class="head"><div><h2>Backtest strategies</h2><div id="catalog-note" class="note">Loading artifact registry</div></div><strong id="strategy-count">0</strong></div><div class="table-wrap"><table><thead><tr><th>Strategy</th><th>End</th><th class="num">Return</th><th class="num">Ann. Return</th><th class="num">Sharpe</th><th class="num">Max DD</th></tr></thead><tbody id="strategy-list"></tbody></table></div></section></main><aside><section class="panel"><div class="head"><h2>Strategy detail</h2></div><div id="strategy-detail" class="empty">Select a strategy</div></section></aside></div>
<script>
const state={items:[],selected:null};const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const pct=v=>v===null||v===undefined?"n/a":`${(Number(v)*100).toFixed(2)}%`;const ratio=v=>v===null||v===undefined?"n/a":Number(v).toFixed(2);const money=v=>v===null||v===undefined?"n/a":Number(v).toLocaleString(undefined,{maximumFractionDigits:0});
function renderList(){document.getElementById("strategy-count").textContent=state.items.length;document.getElementById("strategy-list").innerHTML=state.items.map((item,index)=>`<tr class="strategy-row ${index===state.selected?'active':''}" data-index="${index}"><td>${esc(item.name)}${item.is_sota?'<span class="sota">SOTA</span>':''}<div class="note">${esc(item.strategy_id)}</div></td><td>${esc(item.end_date)}</td><td class="num">${pct(item.total_return)}</td><td class="num">${pct(item.annualized_return)}</td><td class="num">${ratio(item.sharpe)}</td><td class="num">${pct(item.max_drawdown)}</td></tr>`).join("");document.querySelectorAll("[data-index]").forEach(row=>row.onclick=()=>{state.selected=Number(row.dataset.index);renderList();renderDetail()})}
function renderDetail(){const item=state.items[state.selected];const target=document.getElementById("strategy-detail");if(!item){target.className="empty";target.textContent="No strategy artifacts found";return}target.className="details";target.innerHTML=`<h2>${esc(item.name)}${item.is_sota?'<span class="sota">CURRENT SOTA</span>':''}</h2><p class="note">Theoretical performance from stored backtest NAV. It is not actual account PnL.</p><div class="metrics"><div class="metric"><label>Period</label><strong>${esc(item.start_date)} to ${esc(item.end_date)}</strong></div><div class="metric"><label>Observations</label><strong>${item.observations}</strong></div><div class="metric"><label>Final NAV (CNH)</label><strong>${money(item.final_nav_cnh)}</strong></div><div class="metric"><label>Annual volatility</label><strong>${pct(item.annualized_volatility)}</strong></div><div class="metric"><label>Calmar</label><strong>${ratio(item.calmar)}</strong></div><div class="metric"><label>Max drawdown</label><strong>${pct(item.max_drawdown)}</strong></div></div><div class="path">${esc(item.artifact_path)}</div><div class="alloc"><h2>Final backtest allocation</h2>${item.allocation.length?item.allocation.sort((a,b)=>b.weight-a.weight).map(row=>`<div class="metric"><label>${esc(row.symbol)}</label><strong>${pct(row.weight)}</strong><div class="bar"><div class="fill" style="width:${Math.max(0,Math.min(100,Number(row.weight)*100))}%"></div></div></div>`).join(""):'<div class="empty">No final allocation in this artifact</div>'}</div>`}
fetch("/api/v1/strategies").then(r=>{if(!r.ok)throw new Error(r.statusText);return r.json()}).then(payload=>{state.items=payload.strategies||[];state.selected=state.items.length?0:null;document.getElementById("catalog-note").textContent=`${payload.registry_type}; theoretical source: ${payload.theoretical_performance_source}`;renderList();renderDetail()}).catch(error=>{document.getElementById("catalog-note").textContent=`Catalog error: ${error.message}`});
</script></body></html>"""


_STRATEGIES_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Strategies</title>
<style>:root{--bg:#f6f7f9;--panel:#fff;--text:#1d2433;--muted:#667085;--line:#d9dee7;--focus:#2456a6;--good:#087f5b}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px Inter,Segoe UI,Arial,sans-serif}header{height:56px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid var(--line)}h1,h2{margin:0;letter-spacing:0}h1{font-size:18px}h2{font-size:15px}.actions,.segments{display:flex;gap:8px;align-items:center}.button,button{min-height:32px;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--text);text-decoration:none;display:inline-flex;align-items:center;justify-content:center;cursor:pointer}.segments button.active{background:#e9f0fb;border-color:#b8c7e6;color:#183b73;font-weight:650}main{padding:16px 18px 28px}.panel{background:#fff;border:1px solid var(--line);border-radius:7px;overflow:hidden}.head{padding:12px 14px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;justify-content:space-between}.note{color:var(--muted);font-size:12px}.table-wrap{overflow:auto;max-height:calc(100vh - 170px)}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:10px;border-bottom:1px solid #edf0f4;text-align:left;white-space:nowrap}th{position:sticky;top:0;background:#f8fafc;color:var(--muted)}td.num,th.num{text-align:right}.strategy-link{border:0;padding:0;min-height:0;background:transparent;color:var(--focus);font-weight:650}.strategy-link:hover{text-decoration:underline}.badge{display:inline-block;margin-left:6px;padding:2px 6px;border:1px solid #c7cdd6;border-radius:999px;color:#667085;font-size:10px}.badge.sota,.badge.monitored{border-color:#9cd6cd;background:#ecf9f6;color:var(--good)}@media(max-width:700px){header{height:auto;align-items:flex-start;flex-direction:column;padding:10px 12px}.actions{width:100%;flex-wrap:wrap}.actions .button{flex:1 1 110px}.head{align-items:flex-start;flex-direction:column}.table-wrap{max-height:none}}</style></head>
<body><header><h1>Strategies</h1><div class="actions"><a class="button" href="/operator">Trading</a><a class="button" href="/strategies">Strategies</a><a class="button" href="/platform">System</a><a class="button" href="/platform/market-data-audit">Market Data</a></div></header>
<main><section class="panel"><div class="head"><div><h2>Strategy Registry</h2><div id="catalog-note" class="note">Loading strategy artifacts</div></div><div class="segments"><button class="active" data-lifecycle="monitored">Monitored <span id="monitored-count">0</span></button><button data-lifecycle="archived">Archived <span id="archived-count">0</span></button></div></div><div class="table-wrap"><table><thead><tr><th>Strategy</th><th>Lifecycle</th><th>Artifact End</th><th>Data Through</th><th class="num">Return</th><th class="num">Ann. Return</th><th class="num">Sharpe</th><th class="num">Max DD</th></tr></thead><tbody id="strategy-list"></tbody></table></div></section></main>
<script>const state={items:[],lifecycle:"monitored"};const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const pct=v=>v==null?"n/a":`${(Number(v)*100).toFixed(2)}%`;const ratio=v=>v==null?"n/a":Number(v).toFixed(2);function render(){const items=state.items.filter(x=>x.lifecycle===state.lifecycle);document.getElementById("strategy-list").innerHTML=items.length?items.map(item=>`<tr><td><button class="strategy-link" data-id="${esc(item.strategy_id)}" data-strategy-lifecycle="${esc(item.lifecycle)}">${esc(item.name)}</button>${item.is_sota?'<span class="badge sota">SOTA</span>':''}<div class="note">${esc(item.strategy_id)}</div></td><td><span class="badge ${esc(item.lifecycle)}">${esc(item.lifecycle)}</span></td><td>${esc(item.artifact_end_date)}</td><td>${esc(item.end_date)}</td><td class="num">${pct(item.total_return)}</td><td class="num">${pct(item.annualized_return)}</td><td class="num">${ratio(item.sharpe)}</td><td class="num">${pct(item.max_drawdown)}</td></tr>`).join(""):'<tr><td colspan="8" class="note">No strategies in this lifecycle.</td></tr>';document.querySelectorAll(".strategy-link").forEach(button=>button.onclick=()=>location.href=button.dataset.strategyLifecycle==="monitored"?`/api/v1/strategies/${encodeURIComponent(button.dataset.id)}/report`:`/strategies/${encodeURIComponent(button.dataset.id)}`);document.querySelectorAll("[data-lifecycle]").forEach(button=>button.classList.toggle("active",button.dataset.lifecycle===state.lifecycle))}document.querySelectorAll("[data-lifecycle]").forEach(button=>button.onclick=()=>{state.lifecycle=button.dataset.lifecycle;render()});fetch("/api/v1/strategies").then(r=>r.json()).then(payload=>{state.items=payload.strategies||[];document.getElementById("monitored-count").textContent=state.items.filter(x=>x.lifecycle==="monitored").length;document.getElementById("archived-count").textContent=state.items.filter(x=>x.lifecycle==="archived").length;document.getElementById("catalog-note").textContent=payload.monitoring_notes||payload.theoretical_performance_source;render()}).catch(error=>document.getElementById("catalog-note").textContent=`Catalog error: ${error.message}`);</script></body></html>"""


_STRATEGY_DETAIL_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Strategy Detail</title>
<style>:root{--bg:#f6f7f9;--panel:#fff;--text:#1d2433;--muted:#667085;--line:#d9dee7;--focus:#2456a6;--good:#087f5b;--benchmark:#111827}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px Inter,Segoe UI,Arial,sans-serif}header{height:56px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid var(--line)}h1,h2{margin:0;letter-spacing:0}h1{font-size:18px}h2{font-size:15px}.actions{display:flex;gap:8px;align-items:center}.button{min-height:32px;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--text);text-decoration:none;display:inline-flex;align-items:center;justify-content:center}main{padding:16px 18px 28px}.titlebar{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.note{color:var(--muted);font-size:12px}.badge{display:inline-block;margin-left:6px;padding:2px 7px;border:1px solid #9cd6cd;border-radius:999px;background:#ecf9f6;color:var(--good);font-size:10px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}.metric,.panel{background:#fff;border:1px solid var(--line);border-radius:7px}.metric{padding:11px}.metric label{display:block;color:var(--muted);font-size:11px}.metric strong{display:block;margin-top:4px;font-size:16px}.grid{display:grid;grid-template-columns:1.4fr .6fr;gap:12px;margin-bottom:12px}.panel{overflow:hidden}.head{padding:11px 13px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.body{padding:12px}.chart{min-height:300px}.chart svg{display:block;width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:8px 9px;border-bottom:1px solid #edf0f4;text-align:left}td.num,th.num{text-align:right}.line{fill:none;stroke:#2456a6;stroke-width:2}.bench{fill:none;stroke:var(--benchmark);stroke-width:1.5}.axis{stroke:#ccd3dd;stroke-width:1}.legend{display:flex;gap:14px;color:var(--muted);font-size:12px}.swatch{width:18px;height:3px;background:#2456a6;display:inline-block}.swatch.bench{background:#111827}.exposures{display:grid;grid-template-columns:1fr 1fr;gap:12px}.warning{white-space:pre-wrap;color:#9a5b09}@media(max-width:900px){header{height:auto;align-items:flex-start;flex-direction:column;padding:10px 12px}.actions{width:100%;flex-wrap:wrap}.actions .button{flex:1 1 110px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.grid,.exposures{grid-template-columns:1fr}}@media(max-width:520px){.metrics{grid-template-columns:1fr}}</style></head>
<body><header><h1>Strategy Detail</h1><div class="actions"><a class="button" href="/operator">Trading</a><a class="button" href="/strategies">Strategies</a><a class="button" href="/platform">System</a><a class="button" href="/platform/market-data-audit">Market Data</a></div></header><main><div class="titlebar"><div><h1 id="name">Loading strategy</h1><div id="method" class="note"></div></div><div class="actions"><a class="button" href="/strategies">Back to registry</a><a id="report-link" class="button" hidden target="_blank">Full backtest report</a></div></div><section id="metrics" class="metrics"></section><div class="grid"><section class="panel"><div class="head"><h2>Performance vs Benchmark</h2><div class="legend"><span><i class="swatch"></i> Strategy</span><span><i class="swatch bench"></i> Benchmark</span></div></div><div id="chart" class="body chart"></div></section><section class="panel"><div class="head"><h2>Current Holdings</h2></div><div id="holdings" class="body"></div></section></div><section class="panel" style="margin-bottom:12px"><div class="head"><h2>Benchmark Comparison</h2></div><div id="comparison" class="body"></div></section><section class="panel"><div class="head"><h2>Exposure and Performance Attribution</h2></div><div class="body exposures"><div><h2>Country Exposure</h2><div id="country"></div></div><div><h2>Currency Exposure</h2><div id="currency"></div></div></div></section><div id="warnings" class="warning"></div></main>
<script>const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const pct=v=>v==null?"n/a":`${(Number(v)*100).toFixed(2)}%`;const ratio=v=>v==null?"n/a":Number(v).toFixed(2);const money=v=>v==null?"n/a":Number(v).toLocaleString(undefined,{maximumFractionDigits:0});function metric(label,value){return `<div class="metric"><label>${label}</label><strong>${value}</strong></div>`}function table(rows,headers){return `<table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`}function exposureTable(values){const rows=Object.entries(values||{}).sort((a,b)=>Number(b[1])-Number(a[1])).map(([key,value])=>`<tr><td>${esc(key)}</td><td class="num">${money(value)}</td></tr>`);return table(rows,["Exposure","CNH"])}function chartSvg(strategy,benchmark){const s=strategy.map(x=>({d:x.trade_date,v:Number(x.nav_cnh)})).filter(x=>x.v>0),b=benchmark.map(x=>({d:x.trade_date,v:Number(x.nav_cnh)})).filter(x=>x.v>0);if(!s.length)return '<div class="note">No NAV series</div>';const baseS=s[0].v,baseB=b[0]?.v||1,all=[...s.map(x=>({...x,i:x.v/baseS*100})),...b.map(x=>({...x,i:x.v/baseB*100}))],dates=all.map(x=>Date.parse(x.d)),vals=all.map(x=>x.i),w=820,h=300,p={l:50,r:15,t:15,b:28},minX=Math.min(...dates),maxX=Math.max(...dates),minY=Math.min(...vals)*.98,maxY=Math.max(...vals)*1.02,x=d=>p.l+(Date.parse(d)-minX)/(maxX-minX||1)*(w-p.l-p.r),y=v=>h-p.b-(v-minY)/(maxY-minY||1)*(h-p.t-p.b),path=(rows,base)=>rows.map((q,i)=>`${i?'L':'M'} ${x(q.d).toFixed(1)} ${y(q.v/base*100).toFixed(1)}`).join(' ');return `<svg viewBox="0 0 ${w} ${h}"><line class="axis" x1="${p.l}" x2="${w-p.r}" y1="${h-p.b}" y2="${h-p.b}"/><path class="line" d="${path(s,baseS)}"/>${b.length?`<path class="bench" d="${path(b,baseB)}"/>`:''}<text x="${p.l}" y="${h-8}" fill="#667085" font-size="11">${esc(s[0].d)}</text><text x="${w-90}" y="${h-8}" fill="#667085" font-size="11">${esc(s[s.length-1].d)}</text></svg>`}function comparisonTable(c){if(!c?.metrics)return '<div class="note">No structured benchmark comparison artifact is available for this run.</div>';const labels={full:'Full',in_sample:'In sample',out_of_sample:'Out of sample'},rows=Object.entries(c.metrics).map(([key,v])=>`<tr><td>${labels[key]||esc(key)}</td><td class="num">${pct(v.candidate?.return)}</td><td class="num">${pct(v.baseline?.return)}</td><td class="num">${pct(v.delta?.return)}</td><td class="num">${ratio(v.candidate?.sharpe)}</td><td class="num">${ratio(v.active?.informationRatio)}</td><td class="num">${pct(v.candidate?.maxDrawdown)}</td></tr>`);return table(rows,["Window","Strategy","Benchmark","Alpha","Sharpe","Info Ratio","Max DD"])}const id=decodeURIComponent(location.pathname.split('/').filter(Boolean).pop());fetch(`/api/v1/strategies/${encodeURIComponent(id)}`).then(r=>{if(!r.ok)throw new Error(`${r.status} ${r.statusText}`);return r.json()}).then(d=>{if(d.lifecycle==='monitored'&&d.report_url){location.replace(d.report_url);return}document.title=d.name;document.getElementById('name').innerHTML=`${esc(d.name)}${d.is_sota?'<span class="badge">CURRENT SOTA</span>':''}<span class="badge">${esc(d.lifecycle)}</span>`;document.getElementById('method').textContent=d.lifecycle==='monitored'?`Data through ${d.end_date}; artifact ended ${d.artifact_end_date}. ${d.monitoring_notes}`:`Archived artifact through ${d.artifact_end_date}.`;document.getElementById('metrics').innerHTML=metric('Total Return',pct(d.total_return))+metric('Annual Return',pct(d.annualized_return))+metric('Annual Volatility',pct(d.annualized_volatility))+metric('Sharpe',ratio(d.sharpe))+metric('Max Drawdown',pct(d.max_drawdown))+metric('Calmar',ratio(d.calmar))+metric('Leverage',ratio(d.leverage))+metric('Final NAV CNH',money(d.final_nav_cnh));document.getElementById('chart').innerHTML=chartSvg(d.nav_series||[],d.benchmark_series||[]);document.getElementById('holdings').innerHTML=table((d.holdings||[]).map(x=>`<tr><td>${esc(x.symbol)}</td><td class="num">${pct(x.weight)}</td><td class="num">${money(x.value_cnh)}</td></tr>`),['Symbol','Weight','CNH']);document.getElementById('comparison').innerHTML=comparisonTable(d.comparison);document.getElementById('country').innerHTML=exposureTable(d.country_exposure_cnh);document.getElementById('currency').innerHTML=exposureTable(d.currency_exposure_cnh);document.getElementById('warnings').textContent=(d.warnings||[]).join('\n');if(d.report_url){const a=document.getElementById('report-link');a.href=d.report_url;a.hidden=false}}).catch(e=>{document.getElementById('name').textContent='Strategy unavailable';document.getElementById('warnings').textContent=e.message});</script></body></html>"""
