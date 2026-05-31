from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/operator")


@router.get("/operator", response_class=HTMLResponse, include_in_schema=False)
def operator_dashboard() -> HTMLResponse:
    return HTMLResponse(_OPERATOR_HTML)


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
    button, select, input {
      font: inherit;
    }
    button {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      min-height: 32px;
      padding: 6px 10px;
      border-radius: 6px;
      cursor: pointer;
    }
    button:hover { border-color: #aeb9c9; }
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
      .actions button { flex: 1 1 130px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Trading Operator</h1>
    <div class="status-line"><span class="dot"></span><span id="connection-status">Loading</span></div>
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
      <section class="panel">
        <div class="panel-head">
          <h2>Automation</h2>
          <span class="status-line"><span class="dot"></span><span id="automation-state">n/a</span></span>
        </div>
        <div class="metrics-compact" aria-label="Automation summary">
          <div class="mini-metric"><label>Heartbeat</label><strong id="auto-heartbeat">n/a</strong></div>
          <div class="mini-metric"><label>Market Data</label><strong id="auto-market-data">n/a</strong></div>
          <div class="mini-metric"><label>IB Fill Sync</label><strong id="auto-fill-sync">n/a</strong></div>
          <div class="mini-metric"><label>EOD PnL</label><strong id="auto-eod-pnl">n/a</strong></div>
          <div class="mini-metric"><label>Staged Proposal</label><strong id="auto-proposal">n/a</strong></div>
        </div>
        <div id="automation-events"></div>
        <div id="automation-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Performance</h2>
          <span class="status-line">Auto-updated</span>
        </div>
        <div class="metrics-compact" aria-label="Performance summary">
          <div class="mini-metric"><label>Strategy NAV</label><strong id="perf-strategy-nav">n/a</strong></div>
          <div class="mini-metric"><label>Strategy Return</label><strong id="perf-strategy-return">n/a</strong></div>
          <div class="mini-metric"><label>Account NAV</label><strong id="perf-account-nav">n/a</strong></div>
          <div class="mini-metric"><label>Account Return</label><strong id="perf-account-return">n/a</strong></div>
        </div>
        <div class="chart-tools" aria-label="Performance period">
          <div class="segmented" id="performance-range-buttons">
            <button type="button" data-perf-range="1m">1M</button>
            <button type="button" data-perf-range="3m">3M</button>
            <button type="button" data-perf-range="6m">6M</button>
            <button type="button" data-perf-range="ytd">YTD</button>
            <button type="button" data-perf-range="1y">1Y</button>
            <button type="button" data-perf-range="all">All</button>
          </div>
          <label class="date-field">Start <input id="perf-range-start" type="date"></label>
          <label class="date-field">End <input id="perf-range-end" type="date"></label>
        </div>
        <div id="performance-chart" class="chart-wrap"></div>
        <div id="performance-legend" class="legend"></div>
        <div id="performance-analysis" class="analysis-table"></div>
        <div id="performance-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Live PnL</h2>
          <div class="actions">
            <span class="status-line"><span id="pnl-as-of">n/a</span></span>
          </div>
        </div>
        <div class="metrics-compact" aria-label="PnL summary">
          <div class="mini-metric"><label>Realized PnL</label><strong id="pnl-realized">n/a</strong></div>
          <div class="mini-metric"><label>Unrealized PnL</label><strong id="pnl-unrealized">n/a</strong></div>
          <div class="mini-metric"><label>Total PnL</label><strong id="pnl-total">n/a</strong></div>
          <div class="mini-metric"><label>Open Value</label><strong id="pnl-open-value">n/a</strong></div>
        </div>
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
          <div class="mini-metric"><label>Real PnL</label><strong id="exec-actual-pnl">n/a</strong></div>
          <div class="mini-metric"><label>Execution Gain</label><strong id="exec-gain">n/a</strong></div>
          <div class="mini-metric"><label>Execution Bps</label><strong id="exec-bps">n/a</strong></div>
        </div>
        <div id="pnl-comparison-chart" class="chart-wrap"></div>
        <div id="slippage-chart" class="chart-wrap"></div>
        <div id="execution-quality-legend" class="legend"></div>
        <div id="execution-slippage-table"></div>
        <div id="execution-quality-warnings" class="warnings"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Holdings Drift</h2>
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

    async function loadProposals() {
      el("connection-status").textContent = "Connected";
      const path = state.filter ? `/api/v1/proposals?status=${encodeURIComponent(state.filter)}` : "/api/v1/proposals";
      state.proposals = await api(path);
      if (!state.selectedId && state.proposals.length) state.selectedId = state.proposals[0].proposal_id;
      if (state.selectedId && !state.proposals.some((item) => item.proposal_id === state.selectedId) && state.proposals.length) {
        state.selectedId = state.proposals[0].proposal_id;
      }
      renderList();
      await renderSelected();
    }

    async function loadDashboardData() {
      const [automation, performance, holdings, pnl, pnlHistory, executionQuality] = await Promise.all([
        api("/api/v1/automation/status"),
        api("/api/v1/dashboard/performance"),
        api("/api/v1/dashboard/holdings"),
        api("/api/v1/dashboard/pnl"),
        api("/api/v1/dashboard/pnl/snapshots?limit=60"),
        api("/api/v1/dashboard/execution-quality?history_limit=60")
      ]);
      renderAutomation(automation);
      renderPerformance(performance);
      renderHoldings(holdings);
      renderPnl(pnl, pnlHistory);
      renderExecutionQuality(executionQuality);
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
      const svg = performanceSvg(strategy, account);
      el("performance-chart").innerHTML = svg;
      el("performance-legend").innerHTML = `
        <span class="legend-item"><span class="swatch"></span>Strategy</span>
        <span class="legend-item"><span class="swatch account"></span>Account</span>
      `;
      renderPerformanceAnalysis(strategy, account);
    }

    function normalizedPerformanceSeries(series) {
      return series
        .map((point) => ({
          trade_date: String(point.trade_date || "").slice(0, 10),
          index: Number(point.index),
          nav_cnh: point.nav_cnh,
          time: Date.parse(point.trade_date)
        }))
        .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.index) && point.index > 0)
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
      if (years) date.setUTCFullYear(date.getUTCFullYear() + years);
      if (months) date.setUTCMonth(date.getUTCMonth() + months);
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

    function performanceSvg(strategy, account) {
      const width = 760;
      const height = 260;
      const pad = { left: 44, right: 16, top: 16, bottom: 28 };
      const all = [...strategy, ...account];
      if (!all.length) return '<div class="empty">No performance data in selected period</div>';
      const times = all.map((point) => point.time);
      const values = all.map((point) => point.index);
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const valuePad = Math.max((maxValue - minValue) * 0.08, 2);
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
      const pathFor = (series) => series
        .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.trade_date).toFixed(2)} ${y(point.index).toFixed(2)}`)
        .join(" ");
      const strategyDots = strategy.map((point) => `<circle class="strategy-dot" cx="${x(point.trade_date).toFixed(2)}" cy="${y(point.index).toFixed(2)}" r="3"><title>${esc(point.trade_date)} strategy ${Number(point.index).toFixed(2)}</title></circle>`).join("");
      const dots = account.map((point) => `<circle class="account-dot" cx="${x(point.trade_date).toFixed(2)}" cy="${y(point.index).toFixed(2)}" r="3.5"><title>${esc(point.trade_date)} account ${Number(point.index).toFixed(2)}</title></circle>`).join("");
      const yTicks = [0, 0.5, 1].map((fraction) => yMin + (yMax - yMin) * fraction);
      const grid = yTicks.map((value) => {
        const yy = y(value);
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy.toFixed(2)}" y2="${yy.toFixed(2)}"></line><text x="8" y="${(yy + 4).toFixed(2)}" fill="#657083" font-size="11">${value.toFixed(0)}</text>`;
      }).join("");
      const startDate = new Date(minTime).toISOString().slice(0, 10);
      const endDate = new Date(maxTime).toISOString().slice(0, 10);
      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Strategy and account performance comparison">
          ${grid}
          <line class="axis-line" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}"></line>
          <text x="${pad.left}" y="${height - 8}" fill="#657083" font-size="11">${esc(startDate)}</text>
          <text x="${width - pad.right - 70}" y="${height - 8}" fill="#657083" font-size="11">${esc(endDate)}</text>
          ${strategy.length > 1 ? `<path class="strategy-line" d="${pathFor(strategy)}"></path>` : ""}
          ${account.length > 1 ? `<path class="account-line" d="${pathFor(account)}"></path>` : ""}
          ${strategyDots}
          ${dots}
        </svg>
      `;
    }

    function renderPerformanceAnalysis(strategy, account) {
      const rows = [
        performanceStats("Strategy", strategy),
        performanceStats("Account", account)
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

    function renderPnl(payload, history) {
      el("pnl-as-of").textContent = payload.as_of ? `as of ${String(payload.as_of).slice(0, 10)}` : "n/a";
      el("pnl-realized").textContent = fmtSignedMoney(payload.realized_pnl_cnh);
      el("pnl-unrealized").textContent = fmtSignedMoney(payload.unrealized_pnl_cnh);
      el("pnl-total").textContent = fmtSignedMoney(payload.total_pnl_cnh);
      el("pnl-open-value").textContent = fmtMaybeMoney(payload.open_market_value_cnh);
      const warnings = [...(payload.warnings || [])];
      if (payload.baseline_cutoff_at) warnings.push(`Trade history collapsed through ${String(payload.baseline_cutoff_at).slice(0, 10)}.`);
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
        <button class="proposal-row ${proposal.proposal_id === state.selectedId ? "active" : ""}" data-id="${esc(proposal.proposal_id)}">
          <span>
            <span class="proposal-title">${esc(proposal.sleeve)}</span>
            <span class="meta">${esc(proposal.as_of)} | ${esc(proposal.proposal_id)} | ${proposal.orders.length} orders</span>
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
      const canDecide = enabled && proposal && proposal.status === "pending";
      el("approve-btn").disabled = !canDecide;
      el("reject-btn").disabled = !canDecide;
      const retryable = retryableOrderIndexes();
      el("resubmit-failed-btn").hidden = !retryable.length;
      el("resubmit-failed-btn").disabled = !enabled || !retryable.length;
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

    Promise.all([loadProposals(), loadDashboardData()]).catch((error) => {
      el("connection-status").textContent = "API error";
      log(error.message, true);
    });
    setInterval(() => {
      loadDashboardData().catch((error) => log(error.message, true));
    }, 60000);
  </script>
</body>
</html>
"""
