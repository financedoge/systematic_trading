from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/platform", response_class=HTMLResponse, include_in_schema=False)
def platform_health_portal() -> HTMLResponse:
    return HTMLResponse(_PLATFORM_HTML)


@router.get("/platform/market-data-audit", response_class=HTMLResponse, include_in_schema=False)
def market_data_audit_portal() -> HTMLResponse:
    from systematic_trading.web.research_archive_panel import RESEARCH_ARCHIVE_HTML
    from systematic_trading.web.governed_panel import GOVERNED_HTML
    page = _MARKET_DATA_AUDIT_HTML.replace('<main>', '<main>'+RESEARCH_ARCHIVE_HTML+GOVERNED_HTML+'<div id="market-bars-panel">', 1)
    return HTMLResponse(page.replace('</main>', '</div></main>', 1))


_PLATFORM_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Platform Health</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d2433;
      --muted: #657083;
      --line: #d8dee8;
      --line-soft: #ebeff5;
      --focus: #2456a6;
      --good: #0f766e;
      --warn: #a15c06;
      --bad: #b42318;
      --planned: #5b6472;
      --disabled: #7a6472;
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
      min-height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2 {
      margin: 0;
      font-weight: 650;
      letter-spacing: 0;
    }
    h1 { font-size: 18px; }
    h2 { font-size: 15px; }
    main {
      padding: 16px 18px 28px;
      max-width: 1440px;
      margin: 0 auto;
    }
    a.button, button {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 6px 10px;
      text-decoration: none;
      cursor: pointer;
      font: inherit;
    }
    a.button:hover, button:hover { border-color: #aeb9c9; }
    button.primary { background: var(--focus); border-color: var(--focus); color: white; }
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .metric, .panel, .service-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .metric {
      min-height: 78px;
      padding: 10px 12px;
    }
    .metric label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    .metric strong {
      font-size: 20px;
      overflow-wrap: anywhere;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, .65fr);
      gap: 12px;
      align-items: start;
    }
    .panel {
      overflow: hidden;
      min-width: 0;
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
    .status-line {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      min-width: 0;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--planned);
      flex: 0 0 auto;
    }
    .dot.ok, .status.ok { background: var(--good); }
    .dot.degraded, .status.degraded { background: var(--warn); }
    .dot.error, .status.error { background: var(--bad); }
    .dot.planned, .status.planned { background: var(--planned); }
    .dot.disabled, .status.disabled { background: var(--disabled); }
    .status {
      display: inline-flex;
      min-width: 78px;
      height: 24px;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      color: white;
      font-size: 12px;
      text-transform: capitalize;
    }
    .status.unknown { background: #4b5563; }
    .graph-wrap {
      padding: 10px 12px 12px;
      min-height: 380px;
    }
    svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .edge {
      stroke: #95a1b2;
      stroke-width: 1.5;
      fill: none;
    }
    .edge.supervises {
      stroke-dasharray: 5 4;
    }
    .node rect {
      fill: #ffffff;
      stroke: #c8d0dc;
      stroke-width: 1.2;
    }
    .node.ok rect { stroke: var(--good); }
    .node.degraded rect { stroke: var(--warn); }
    .node.error rect { stroke: var(--bad); }
    .node.planned rect { stroke: var(--planned); }
    .node.disabled rect { stroke: var(--disabled); }
    .node-title {
      fill: var(--text);
      font-size: 12px;
      font-weight: 650;
    }
    .node-meta {
      fill: var(--muted);
      font-size: 11px;
    }
    .cards {
      display: grid;
      gap: 8px;
      padding: 12px;
    }
    .service-card {
      padding: 10px 12px;
    }
    .service-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 8px;
    }
    .service-name {
      font-weight: 650;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .service-meta, .service-message {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .service-message {
      color: var(--text);
      margin-top: 8px;
    }
    .service-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .service-actions button {
      min-height: 30px;
      font-size: 12px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      background: #fbfcfd;
      font-size: 12px;
      font-weight: 650;
    }
    tr:last-child td { border-bottom: 0; }
    .empty, .error {
      padding: 14px 12px;
      color: var(--muted);
    }
    .error { color: var(--bad); }
    .hidden { display: none !important; }
    @media (max-width: 980px) {
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
    }
    @media (max-width: 580px) {
      header {
        align-items: flex-start;
        flex-direction: column;
        padding: 10px 12px;
      }
      main { padding: 12px; }
      .summary { grid-template-columns: 1fr; }
      .actions { width: 100%; }
      .actions .button, .actions button { flex: 1 1 120px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Platform Health</h1>
    <div class="actions">
      <a class="button" href="/operator">Trading</a>
      <a class="button" href="/strategies">Strategies</a>
      <a class="button" href="/platform">System</a>
      <a class="button" href="/platform/market-data-audit">Market Data</a>
    </div>
  </header>
  <main>
    <section class="summary" aria-label="Service summary">
      <div class="metric"><label>Overall</label><strong id="metric-overall">n/a</strong></div>
      <div class="metric"><label>Required OK</label><strong id="metric-required-ok">0 / 0</strong></div>
      <div class="metric"><label>Errors</label><strong id="metric-errors">0</strong></div>
      <div class="metric"><label>Degraded</label><strong id="metric-degraded">0</strong></div>
      <div class="metric"><label>Last Check</label><strong id="metric-check">n/a</strong></div>
    </section>
    <div class="layout">
      <section class="panel">
        <div class="panel-head">
          <h2>Service Map</h2>
          <span class="status-line">Manifest graph</span>
        </div>
        <div id="service-graph" class="graph-wrap"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Service Status</h2>
          <div class="actions"><span class="status-line"><span id="overall-dot" class="dot"></span><span id="overall-status">Loading</span></span><span class="status-line">Auto-refresh 5s</span><button id="refresh-btn" class="primary" type="button">Refresh</button></div>
        </div>
        <div id="service-cards" class="cards"></div>
      </section>
    </div>
    <section class="panel" style="margin-top: 12px;">
      <div class="panel-head">
        <h2>Health Details</h2>
        <span id="detail-count" class="status-line">n/a</span>
      </div>
      <div id="health-table"></div>
    </section>
  </main>
  <script>
    const el = (id) => document.getElementById(id);
    const statusOrder = ["error", "degraded", "unknown", "planned", "disabled", "ok"];
    const statusClass = (value) => statusOrder.includes(value) ? value : "unknown";

    async function api(path) {
      const response = await fetch(path, { headers: { "Accept": "application/json" } });
      if (!response.ok) throw new Error(`${path} returned ${response.status}`);
      return response.json();
    }

    function esc(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function fmtTime(value) {
      if (!value) return "n/a";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString();
    }

    function age(value, checkedAt) {
      if (!value) return "n/a";
      const start = Date.parse(value);
      const end = Date.parse(checkedAt);
      if (!Number.isFinite(start) || !Number.isFinite(end)) return "n/a";
      const seconds = Math.max(0, Math.round((end - start) / 1000));
      if (seconds < 60) return `${seconds}s`;
      const minutes = Math.round(seconds / 60);
      if (minutes < 60) return `${minutes}m`;
      return `${Math.round(minutes / 60)}h`;
    }

    function renderSummary(health) {
      const services = health.services || [];
      const required = services.filter((service) => service.required && service.implementation_status === "active");
      const requiredOk = required.filter((service) => service.status === "ok").length;
      const errors = services.filter((service) => service.status === "error").length;
      const degraded = services.filter((service) => service.status === "degraded").length;
      const overall = statusClass(health.status);
      el("overall-dot").className = `dot ${overall}`;
      el("overall-status").textContent = health.status || "unknown";
      el("metric-overall").textContent = health.status || "unknown";
      el("metric-required-ok").textContent = `${requiredOk} / ${required.length}`;
      el("metric-errors").textContent = errors;
      el("metric-degraded").textContent = degraded;
      el("metric-check").textContent = fmtTime(health.checked_at);
    }

    function renderCards(health, actionCatalog) {
      const services = health.services || [];
      const actionsById = new Map((actionCatalog?.services || []).map((item) => [item.service_id, item]));
      if (!services.length) {
        el("service-cards").innerHTML = '<div class="empty">No services</div>';
        return;
      }
      el("service-cards").innerHTML = services.map((service) => {
        const cls = statusClass(service.status);
        const action = actionsById.get(service.service_id);
        const actionHtml = action?.restartable
          ? `<button class="restart-service-btn" type="button" data-service-id="${esc(service.service_id)}">Restart</button>`
          : `<span class="service-meta">${esc(action?.reason || "No restart action configured.")}</span>`;
        return `
          <article class="service-card">
            <div class="service-top">
              <div class="service-name">${esc(service.display_name)}</div>
              <span class="status ${cls}">${esc(service.status)}</span>
            </div>
            <div class="service-meta">${esc(service.service_id)} | ${esc(service.service_type)} | ${service.required ? "required" : "optional"}</div>
            <div class="service-meta">Heartbeat age: ${esc(age(service.heartbeat_at, health.checked_at))}</div>
            <div class="service-message">${esc(service.message)}</div>
            <div class="service-actions">${actionHtml}</div>
          </article>
        `;
      }).join("");
      for (const button of document.querySelectorAll(".restart-service-btn")) {
        button.addEventListener("click", () => restartService(button.dataset.serviceId, button));
      }
    }

    function renderTable(health) {
      const services = health.services || [];
      el("detail-count").textContent = `${services.length} services`;
      if (!services.length) {
        el("health-table").innerHTML = '<div class="empty">No service health records</div>';
        return;
      }
      el("health-table").innerHTML = `
        <table>
          <thead>
            <tr>
              <th style="width: 18%;">Service</th>
              <th style="width: 10%;">Status</th>
              <th style="width: 9%;">Running</th>
              <th style="width: 16%;">Heartbeat</th>
              <th style="width: 17%;">Target</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            ${services.map((service) => `
              <tr>
                <td>${esc(service.service_id)}<br><span class="service-meta">${esc(service.display_name)}</span></td>
                <td><span class="status ${statusClass(service.status)}">${esc(service.status)}</span></td>
                <td>${service.running === null || service.running === undefined ? "n/a" : esc(service.running)}</td>
                <td>${esc(fmtTime(service.heartbeat_at))}</td>
                <td>${esc(service.target || "")}</td>
                <td>${esc(service.message)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderGraph(graph, health) {
      const nodes = (graph.nodes || []).slice().sort((a, b) => a.startup_order - b.startup_order);
      if (!nodes.length) {
        el("service-graph").innerHTML = '<div class="empty">No graph nodes</div>';
        return;
      }
      const healthById = new Map((health.services || []).map((service) => [service.service_id, service]));
      const width = 920;
      const height = 360;
      const left = 92;
      const usable = width - 184;
      const lane = { worker: 92, api: 184, embedded_worker: 276 };
      const positions = new Map();
      nodes.forEach((node, index) => {
        const x = nodes.length === 1 ? width / 2 : left + (usable * index / (nodes.length - 1));
        const y = (lane[node.service_type] || 184) + ((index % 2) * 18);
        positions.set(node.service_id, { x, y });
      });
      const marker = `
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#95a1b2"></path>
          </marker>
        </defs>
      `;
      const edges = (graph.edges || []).map((edge) => {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) return "";
        return `<path class="edge ${esc(edge.relation)}" d="M ${source.x.toFixed(1)} ${source.y.toFixed(1)} C ${((source.x + target.x) / 2).toFixed(1)} ${(source.y - 48).toFixed(1)}, ${((source.x + target.x) / 2).toFixed(1)} ${(target.y - 48).toFixed(1)}, ${target.x.toFixed(1)} ${target.y.toFixed(1)}" marker-end="url(#arrow)"><title>${esc(edge.source)} ${esc(edge.relation)} ${esc(edge.target)}</title></path>`;
      }).join("");
      const renderedNodes = nodes.map((node) => {
        const pos = positions.get(node.service_id);
        const serviceHealth = healthById.get(node.service_id);
        const status = statusClass(serviceHealth?.status || node.implementation_status);
        const label = node.display_name.length > 24 ? `${node.display_name.slice(0, 23)}...` : node.display_name;
        return `
          <g class="node ${status}" transform="translate(${(pos.x - 70).toFixed(1)}, ${(pos.y - 28).toFixed(1)})">
            <rect width="140" height="56" rx="7"></rect>
            <circle cx="13" cy="16" r="4.5" fill="var(--${status === "ok" ? "good" : status === "error" ? "bad" : status === "degraded" ? "warn" : "planned"})"></circle>
            <text class="node-title" x="24" y="20">${esc(label)}</text>
            <text class="node-meta" x="12" y="40">${esc(node.service_id)}</text>
            <title>${esc(node.display_name)}: ${esc(serviceHealth?.message || node.implementation_status)}</title>
          </g>
        `;
      }).join("");
      el("service-graph").innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Platform service dependency graph">
          ${marker}
          <line x1="30" x2="${width - 30}" y1="92" y2="92" stroke="#ebeff5"></line>
          <line x1="30" x2="${width - 30}" y1="184" y2="184" stroke="#ebeff5"></line>
          <line x1="30" x2="${width - 30}" y1="276" y2="276" stroke="#ebeff5"></line>
          <text x="8" y="96" fill="#657083" font-size="11">Workers</text>
          <text x="8" y="188" fill="#657083" font-size="11">API</text>
          <text x="8" y="280" fill="#657083" font-size="11">Embedded</text>
          ${edges}
          ${renderedNodes}
        </svg>
      `;
    }

    async function restartService(serviceId, button) {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = "Restarting";
      try {
        const response = await fetch(`/api/v1/platform/services/${encodeURIComponent(serviceId)}/restart`, {
          method: "POST",
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `restart returned ${response.status}`);
        }
        button.textContent = "Done";
        await load();
      } catch (error) {
        button.textContent = "Failed";
        el("overall-status").textContent = error.message;
      } finally {
        setTimeout(() => {
          button.disabled = false;
          button.textContent = original;
        }, 2000);
      }
    }

    async function load() {
      try {
        const [health, graph, actionCatalog] = await Promise.all([
          api("/health"),
          api("/api/v1/platform/service-graph"),
          api("/api/v1/platform/service-actions")
        ]);
        renderSummary(health);
        renderCards(health, actionCatalog);
        renderTable(health);
        renderGraph(graph, health);
      } catch (error) {
        el("overall-dot").className = "dot error";
        el("overall-status").textContent = "error";
        el("service-cards").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      }
    }

    el("refresh-btn").addEventListener("click", load);
    load();
    setInterval(load, 5000);
  </script>
</body>
</html>
"""


_MARKET_DATA_AUDIT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Data</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d2433;
      --muted: #657083;
      --line: #d8dee8;
      --line-soft: #ebeff5;
      --focus: #2456a6;
      --good: #0f766e;
      --warn: #a15c06;
      --bad: #b42318;
      --volume: #7b8798;
      --shadow: rgba(29, 36, 51, 0.06);
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
      min-height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2 {
      margin: 0;
      font-weight: 650;
      letter-spacing: 0;
    }
    h1 { font-size: 18px; }
    h2 { font-size: 15px; }
    main {
      padding: 16px 18px 28px;
      max-width: 1500px;
      margin: 0 auto;
    }
    a.button, button {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 6px 10px;
      text-decoration: none;
      cursor: pointer;
      font: inherit;
    }
    a.button:hover, button:hover { border-color: #aeb9c9; }
    button.primary { background: var(--focus); border-color: var(--focus); color: #fff; }
    button.icon {
      width: 34px;
      padding: 0;
      font-weight: 650;
    }
    button:disabled {
      color: var(--muted);
      background: #f3f5f8;
      cursor: default;
    }
    .actions, .filters, .range-buttons {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .panel, .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      box-shadow: 0 1px 2px var(--shadow);
    }
    .filters {
      padding: 12px;
      margin-bottom: 12px;
    }
    label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    input, select {
      height: 32px;
      min-width: 112px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 5px 8px;
      color: var(--text);
      background: #fff;
      font: inherit;
      font-size: 13px;
    }
    .symbol {
      width: 210px;
      min-width: 160px;
      text-transform: uppercase;
    }
    input.small {
      width: 92px;
      min-width: 92px;
    }
    .range-buttons {
      align-self: end;
      min-height: 32px;
    }
    .range-buttons button {
      min-height: 30px;
      padding: 5px 9px;
      font-size: 12px;
    }
    .range-buttons button[aria-pressed="true"] {
      border-color: var(--focus);
      background: #eaf1fb;
      color: var(--focus);
      font-weight: 650;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .metric {
      min-height: 74px;
      padding: 10px 12px;
    }
    .metric label {
      display: block;
      margin-bottom: 8px;
    }
    .metric strong {
      font-size: 18px;
      overflow-wrap: anywhere;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }
    .panel {
      overflow: hidden;
      min-width: 0;
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
    .status-line, .muted {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .chart-wrap {
      padding: 10px 12px 12px;
      min-height: 490px;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
    .axis, .grid-line { stroke: #d8dee8; stroke-width: 1; }
    .grid-line { stroke: #eef2f7; }
    .axis-label { fill: var(--muted); font-size: 11px; }
    .wick.up, .body.up { stroke: var(--good); fill: var(--good); }
    .wick.down, .body.down { stroke: var(--bad); fill: var(--bad); }
    .wick.flat, .body.flat { stroke: #5b6472; fill: #5b6472; }
    .volume-bar { fill: var(--volume); opacity: .48; }
    .close-line { stroke: var(--focus); stroke-width: 1.2; fill: none; opacity: .78; }
    .table-wrap {
      max-height: 560px;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      color: var(--muted);
      background: #fbfcfd;
      font-size: 12px;
      font-weight: 650;
    }
    td.numeric, th.numeric { text-align: right; }
    .ok { color: var(--good); }
    .bad { color: var(--bad); }
    .warn { color: var(--warn); }
    .empty, .error {
      padding: 14px 12px;
      color: var(--muted);
    }
    .error { color: var(--bad); }
    .raw-section {
      margin-top: 12px;
    }
    .hidden { display: none !important; }
    .raw-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, .55fr);
      gap: 12px;
      align-items: start;
      padding: 0 0 12px;
    }
    @media (max-width: 1120px) {
      .summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid, .raw-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      header {
        align-items: flex-start;
        flex-direction: column;
        padding: 10px 12px;
      }
      main { padding: 12px; }
      .summary { grid-template-columns: 1fr; }
      .filters { align-items: stretch; }
      label, input, select, button, .button { flex: 1 1 140px; width: 100%; }
      .symbol { width: 100%; }
      button.icon { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Market Data</h1>
    <div class="actions">
      <a class="button" href="/operator">Trading</a>
      <a class="button" href="/strategies">Strategies</a>
      <a class="button" href="/platform">System</a>
      <a class="button" href="/platform/market-data-audit">Market Data</a>
    </div>
  </header>
  <main>
    <form id="golden-filters" class="filters panel">
      <label>Store<select id="store"><option value="intraday-bars" selected>Intraday Bars</option><option value="daily-bars">Daily Bars</option></select></label>
      <label>Symbol<select id="golden-symbol" class="symbol" aria-label="Symbol"></select></label>
      <label class="daily-control">Start<input id="start-date" type="date"></label>
      <label class="daily-control">End<input id="end-date" type="date"></label>
      <label class="intraday-control">Start Session<input id="intraday-start-date" type="date"></label>
      <label class="intraday-control">End Session<input id="intraday-end-date" type="date"></label>
      <label class="intraday-control">Capture<select id="intraday-capture-mode"><option value="stream" selected>stream</option><option value="">all</option><option value="historical_backfill">historical backfill</option></select></label>
      <label class="intraday-control">Bar Size<input id="intraday-bar-size" class="small" type="number" min="1" value="5"></label>
      <label>Limit<input id="golden-limit" class="small" type="number" min="1" max="50000" value="5000"></label>
      <div id="daily-range-controls" class="range-buttons daily-control" aria-label="Date range controls">
        <button type="button" data-range="1m">1M</button>
        <button type="button" data-range="3m">3M</button>
        <button type="button" data-range="ytd">YTD</button>
        <button type="button" data-range="1y">1Y</button>
        <button type="button" data-range="5y">5Y</button>
        <button type="button" data-range="all">All</button>
        <button id="pan-left" class="icon" type="button" title="Pan left">&lt;</button>
        <button id="zoom-in" class="icon" type="button" title="Zoom in">+</button>
        <button id="zoom-out" class="icon" type="button" title="Zoom out">-</button>
        <button id="pan-right" class="icon" type="button" title="Pan right">&gt;</button>
      </div>
      <div id="intraday-range-controls" class="range-buttons intraday-control" aria-label="Recorder session range">
        <button type="button" data-sessions="1" aria-pressed="true">1D</button>
        <button type="button" data-sessions="5" aria-pressed="false">5D</button>
        <button type="button" data-sessions="10" aria-pressed="false">10D</button>
        <button type="button" data-sessions="all" aria-pressed="false">All</button>
      </div>
      <button class="primary" type="submit">Run</button>
      <button id="refresh-btn" type="button">Refresh</button>
      <span id="status" class="status-line">Loading</span>
    </form>
    <section class="summary" aria-label="Market-data summary">
      <div class="metric"><label>Bars</label><strong id="metric-bars">0</strong></div>
      <div class="metric"><label>Range</label><strong id="metric-range">n/a</strong></div>
      <div class="metric"><label>Last Close</label><strong id="metric-close">n/a</strong></div>
      <div class="metric"><label>Change</label><strong id="metric-change">n/a</strong></div>
      <div class="metric"><label>Volume</label><strong id="metric-volume">n/a</strong></div>
      <div class="metric"><label>Source</label><strong id="metric-source">n/a</strong></div>
    </section>
    <div class="grid">
      <section class="panel">
        <div class="panel-head">
          <h2>OHLCV</h2>
          <span id="chart-meta" class="status-line">n/a</span>
        </div>
        <div id="golden-chart" class="chart-wrap"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2 id="table-title">Intraday Bars</h2>
          <span id="table-meta" class="status-line">n/a</span>
        </div>
        <div id="golden-table" class="table-wrap"></div>
      </section>
    </div>
    <section class="panel raw-section">
      <div class="panel-head">
        <h2>Raw Evidence</h2>
        <span id="raw-status" class="status-line">Idle</span>
      </div>
      <form id="raw-filters" class="filters">
        <label>Source<input id="raw-source" value="interactive-brokers"></label>
        <label>Capture Env<select id="raw-environment"><option value="">all</option><option value="paper">paper</option><option value="live">live</option></select></label>
        <label>Kind<select id="raw-kind"><option value="bar">bar</option><option value="quote">quote</option><option value="trade">trade</option></select></label>
        <label>Recorder Date<input id="raw-recorder-date" type="date"></label>
        <label>Bar Size<input id="raw-bar-size" class="small" type="number" min="1" placeholder="all"></label>
        <label>Limit<input id="raw-limit" class="small" type="number" min="1" max="5000" value="200"></label>
        <button type="submit">Run</button>
      </form>
      <div class="raw-grid">
        <div id="raw-table" class="table-wrap"></div>
        <div id="raw-details"></div>
      </div>
    </section>
  </main>
  <script>
    const el = (id) => document.getElementById(id);
    const state = { symbols: [], goldenBars: [], recorderDates: [], sessionPreset: "1" };

    function esc(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function number(value, digits = 2) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return "n/a";
      return parsed.toLocaleString(undefined, { maximumFractionDigits: digits });
    }

    function fmtDate(value) {
      return value || "n/a";
    }

    function fmtDateTime(value) {
      if (!value) return "n/a";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return String(value);
      return parsed.toLocaleString();
    }

    function fmtCompactDateTime(value) {
      if (!value) return "n/a";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return String(value);
      return parsed.toLocaleString(undefined, {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }

    function parseIsoDate(value) {
      const [year, month, day] = String(value).split("-").map(Number);
      return new Date(Date.UTC(year, month - 1, day));
    }

    function isoDate(date) {
      return date.toISOString().slice(0, 10);
    }

    function shiftDays(value, days) {
      const date = parseIsoDate(value);
      date.setUTCDate(date.getUTCDate() + days);
      return isoDate(date);
    }

    function shiftMonths(value, months) {
      const date = parseIsoDate(value);
      date.setUTCMonth(date.getUTCMonth() + months);
      return isoDate(date);
    }

    function daysBetween(start, end) {
      return Math.max(1, Math.round((parseIsoDate(end) - parseIsoDate(start)) / 86400000));
    }

    function selectedSymbol() {
      return el("golden-symbol").value.trim().toUpperCase();
    }

    function selectedStore() {
      return el("store").value;
    }

    function isIntraday() {
      return selectedStore() === "intraday-bars";
    }

    function setStoreControls() {
      for (const control of document.querySelectorAll(".daily-control")) {
        control.classList.toggle("hidden", isIntraday());
      }
      for (const control of document.querySelectorAll(".intraday-control")) {
        control.classList.toggle("hidden", !isIntraday());
      }
      el("table-title").textContent = isIntraday() ? "Intraday Bars" : "Daily Bars";
    }

    function selectedMeta() {
      const symbol = selectedSymbol();
      return state.symbols.find((item) => item.symbol === symbol);
    }

    function setBoundedRange(start, end) {
      const meta = selectedMeta();
      let nextStart = start;
      let nextEnd = end;
      if (meta?.first_trade_date && nextStart < meta.first_trade_date) nextStart = meta.first_trade_date;
      if (meta?.last_trade_date && nextEnd > meta.last_trade_date) nextEnd = meta.last_trade_date;
      if (nextStart > nextEnd) nextStart = nextEnd;
      el("start-date").value = nextStart;
      el("end-date").value = nextEnd;
    }

    function currentWindow() {
      const bars = state.goldenBars || [];
      const meta = selectedMeta();
      const firstBar = bars.length ? bars[0].trade_date : null;
      const lastBar = bars.length ? bars[bars.length - 1].trade_date : null;
      const start = el("start-date").value || firstBar || meta?.first_trade_date;
      const end = el("end-date").value || lastBar || meta?.last_trade_date;
      return { start, end };
    }

    function applyRange(range) {
      const meta = selectedMeta();
      const end = meta?.last_trade_date || el("end-date").value || new Date().toISOString().slice(0, 10);
      if (range === "all") {
        el("start-date").value = "";
        el("end-date").value = "";
        loadGolden();
        return;
      }
      if (range === "ytd") {
        setBoundedRange(`${end.slice(0, 4)}-01-01`, end);
      } else if (range === "1m") {
        setBoundedRange(shiftMonths(end, -1), end);
      } else if (range === "3m") {
        setBoundedRange(shiftMonths(end, -3), end);
      } else if (range === "1y") {
        setBoundedRange(shiftMonths(end, -12), end);
      } else if (range === "5y") {
        setBoundedRange(shiftMonths(end, -60), end);
      }
      loadGolden();
    }

    function zoom(factor) {
      const window = currentWindow();
      if (!window.start || !window.end) return;
      const span = daysBetween(window.start, window.end);
      const center = parseIsoDate(window.start).getTime() + ((parseIsoDate(window.end).getTime() - parseIsoDate(window.start).getTime()) / 2);
      const nextSpan = Math.max(7, Math.round(span * factor));
      const start = new Date(center - (nextSpan * 86400000 / 2));
      const end = new Date(center + (nextSpan * 86400000 / 2));
      setBoundedRange(isoDate(start), isoDate(end));
      loadGolden();
    }

    function pan(direction) {
      const window = currentWindow();
      if (!window.start || !window.end) return;
      const step = Math.max(1, Math.round(daysBetween(window.start, window.end) * 0.5)) * direction;
      setBoundedRange(shiftDays(window.start, step), shiftDays(window.end, step));
      loadGolden();
    }

    function goldenParams() {
      const params = new URLSearchParams();
      const symbol = selectedSymbol();
      if (symbol) params.set("symbol", symbol);
      if (el("start-date").value) params.set("start_date", el("start-date").value);
      if (el("end-date").value) params.set("end_date", el("end-date").value);
      if (el("golden-limit").value) params.set("limit", el("golden-limit").value);
      return params;
    }

    function applySymbolOptions(labelFor) {
      const current = selectedSymbol();
      el("golden-symbol").innerHTML = state.symbols.map((item) =>
        `<option value="${esc(item.symbol)}">${esc(item.symbol)} | ${esc(labelFor(item))}</option>`
      ).join("");
      if (!state.symbols.length) return;
      const selected = state.symbols.find((item) => item.symbol === current)
        || state.symbols.find((item) => item.symbol === "SPY")
        || state.symbols[0];
      el("golden-symbol").value = selected.symbol;
    }

    async function loadDailySymbols() {
      el("status").textContent = "Loading symbols";
      const response = await fetch("/api/v1/market-data/daily-symbols", {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error(`daily symbols returned ${response.status}`);
      const data = await response.json();
      state.symbols = data.symbols || [];
      applySymbolOptions((item) => `${item.row_count} rows | ${item.first_trade_date || "n/a"} to ${item.last_trade_date || "n/a"}`);
    }

    async function loadIntradaySymbols() {
      el("status").textContent = "Loading recorder dates";
      const baseParams = new URLSearchParams({ source: "interactive-brokers", data_kind: "bar" });
      const baseResponse = await fetch(`/api/v1/market-data/audit/symbols?${baseParams.toString()}`, {
        headers: { "Accept": "application/json" }
      });
      if (!baseResponse.ok) throw new Error(`intraday symbols returned ${baseResponse.status}`);
      const base = await baseResponse.json();
      state.recorderDates = base.recorder_dates || [];
      if (!el("intraday-start-date").value && !el("intraday-end-date").value && base.latest_recorder_date) {
        setIntradaySessionRange(state.sessionPreset);
      }
      const start = el("intraday-start-date").value;
      const end = el("intraday-end-date").value;
      if (start) baseParams.set("recorder_start_date", start);
      if (end) baseParams.set("recorder_end_date", end);
      const response = await fetch(`/api/v1/market-data/audit/symbols?${baseParams.toString()}`, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error(`intraday symbols returned ${response.status}`);
      const data = await response.json();
      state.symbols = (data.symbols || []).map((symbol) => ({ symbol }));
      applySymbolOptions(() => `raw intraday | ${intradayRangeLabel()}`);
    }

    function setIntradaySessionRange(sessionCount) {
      const dates = state.recorderDates || [];
      state.sessionPreset = String(sessionCount);
      for (const button of document.querySelectorAll("[data-sessions]")) {
        button.setAttribute("aria-pressed", String(button.dataset.sessions === state.sessionPreset));
      }
      if (!dates.length) {
        el("intraday-start-date").value = "";
        el("intraday-end-date").value = "";
        return;
      }
      const requestedCount = Number(sessionCount);
      const count = sessionCount === "all" || !Number.isFinite(requestedCount)
        ? dates.length
        : Math.max(1, requestedCount);
      el("intraday-start-date").value = dates[Math.max(0, dates.length - count)];
      el("intraday-end-date").value = dates[dates.length - 1];
    }

    function intradayRangeLabel() {
      const start = el("intraday-start-date").value;
      const end = el("intraday-end-date").value;
      if (!start && !end) return "all sessions";
      if (start === end || !end) return start || end;
      return `${start} to ${end}`;
    }

    function selectedRecorderSessionCount() {
      const start = el("intraday-start-date").value;
      const end = el("intraday-end-date").value;
      return state.recorderDates.filter((value) => (!start || value >= start) && (!end || value <= end)).length;
    }

    async function applyIntradaySessions(sessionCount) {
      setIntradaySessionRange(sessionCount);
      await loadIntradaySymbols();
      await loadIntraday();
    }

    async function loadSymbols() {
      if (isIntraday()) return loadIntradaySymbols();
      return loadDailySymbols();
    }

    async function loadGolden() {
      const symbol = selectedSymbol();
      if (!symbol) {
        renderGolden({ summary: {}, bars: [] });
        el("status").textContent = "No symbol";
        return;
      }
      el("status").textContent = "Loading";
      const response = await fetch(`/api/v1/market-data/daily-bars?${goldenParams().toString()}`, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error(`daily bars returned ${response.status}`);
      const data = await response.json();
      renderGolden(data);
      el("status").textContent = "Loaded";
    }

    function intradayParams() {
      const params = new URLSearchParams({ source: "interactive-brokers", data_kind: "bar" });
      const symbol = selectedSymbol();
      if (symbol) params.set("symbol", symbol);
      if (el("intraday-start-date").value) params.set("recorder_start_date", el("intraday-start-date").value);
      if (el("intraday-end-date").value) params.set("recorder_end_date", el("intraday-end-date").value);
      if (el("intraday-capture-mode").value) params.set("capture_mode", el("intraday-capture-mode").value);
      if (el("intraday-bar-size").value) params.set("bar_size_seconds", el("intraday-bar-size").value);
      if (el("golden-limit").value) params.set("limit", Math.min(Number(el("golden-limit").value), 5000));
      return params;
    }

    async function loadIntraday() {
      const symbol = selectedSymbol();
      if (!symbol) {
        renderGolden({ summary: {}, bars: [] });
        el("status").textContent = "No symbol";
        return;
      }
      el("status").textContent = "Loading intraday";
      const response = await fetch(`/api/v1/market-data/audit?${intradayParams().toString()}`, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error(`intraday bars returned ${response.status}`);
      const data = await response.json();
      const summary = data.summary || {};
      const rowsById = new Map((data.rows || []).map((row) => [row.raw_event_id, row]));
      const seenBarIds = new Set();
      const uniqueBars = (data.bars || []).filter((bar) => {
        if (seenBarIds.has(bar.raw_event_id)) return false;
        seenBarIds.add(bar.raw_event_id);
        return true;
      });
      const bars = uniqueBars.map((bar) => {
        const row = rowsById.get(bar.raw_event_id) || {};
        const timestamp = bar.exchange_timestamp || bar.received_at;
        return {
          ...bar,
          trade_date: fmtCompactDateTime(timestamp),
          adjustment: `${bar.capture_mode || "unknown"} | ${bar.bar_size_seconds || "?"}s`,
          source_name: `${row.source_name || "interactive-brokers"} | ${bar.market_data_mode || "unknown"}`,
          available_at: bar.received_at,
          payload_hash: row.payload_hash || bar.raw_event_id,
          raw_ref: row.raw_ref || "",
        };
      });
      const modes = [...new Set(uniqueBars.map((bar) => bar.market_data_mode).filter(Boolean))];
      renderGolden({
        summary: {
          symbol: summary.symbol || symbol,
          rows_returned: bars.length,
          first_trade_date: fmtCompactDateTime(summary.first_exchange_timestamp),
          last_trade_date: fmtCompactDateTime(summary.last_exchange_timestamp),
          source_names: modes.map((mode) => `IB ${mode}`),
        },
        bars,
      });
      const exactDate = el("intraday-start-date").value === el("intraday-end-date").value
        ? el("intraday-start-date").value
        : "";
      el("raw-recorder-date").value = exactDate;
      el("raw-bar-size").value = el("intraday-bar-size").value;
      const sessions = selectedRecorderSessionCount();
      el("chart-meta").textContent = `${symbol} | ${bars.length} bars | ${sessions} recorded session${sessions === 1 ? "" : "s"} | ${intradayRangeLabel()}`;
      renderRaw(data);
      el("raw-status").textContent = "Loaded";
      el("status").textContent = modes.length ? `Loaded | ${modes.join(", ")}` : "Loaded";
    }

    async function loadActive() {
      if (isIntraday()) return loadIntraday();
      return loadGolden();
    }

    function renderGolden(data) {
      const summary = data.summary || {};
      const bars = data.bars || [];
      state.goldenBars = bars;
      const first = bars[0];
      const last = bars.length ? bars[bars.length - 1] : null;
      const prev = bars.length > 1 ? bars[bars.length - 2] : null;
      const change = last && prev ? (Number(last.close) - Number(prev.close)) : null;
      const changePct = last && prev && Number(prev.close) ? (change / Number(prev.close) * 100) : null;
      el("metric-bars").textContent = summary.rows_returned ?? bars.length;
      el("metric-range").textContent = `${fmtDate(summary.first_trade_date || first?.trade_date)} to ${fmtDate(summary.last_trade_date || last?.trade_date)}`;
      el("metric-close").textContent = last ? number(last.close, 4) : "n/a";
      el("metric-change").innerHTML = change === null
        ? "n/a"
        : `<span class="${change >= 0 ? "ok" : "bad"}">${esc(number(change, 4))} (${esc(number(changePct, 2))}%)</span>`;
      el("metric-volume").textContent = last ? number(last.volume, 0) : "n/a";
      el("metric-source").textContent = (summary.source_names || []).join(", ") || "n/a";
      el("chart-meta").textContent = `${summary.symbol || selectedSymbol()} | ${bars.length} bars`;
      el("table-meta").textContent = `${bars.length} rows`;
      renderGoldenChart(bars);
      renderGoldenTable(bars);
    }

    function renderGoldenChart(bars) {
      if (!bars.length) {
        el("golden-chart").innerHTML = `<div class="empty">No ${isIntraday() ? "intraday" : "daily"} bars</div>`;
        return;
      }
      const width = 940;
      const height = 440;
      const pad = { left: 62, right: 18, top: 18, bottom: 42 };
      const priceTop = pad.top;
      const priceH = 292;
      const volumeTop = priceTop + priceH + 28;
      const volumeH = 66;
      const plotW = width - pad.left - pad.right;
      const highs = bars.map((bar) => Number(bar.high)).filter(Number.isFinite);
      const lows = bars.map((bar) => Number(bar.low)).filter(Number.isFinite);
      const max = Math.max(...highs);
      const min = Math.min(...lows);
      const span = Math.max(max - min, 0.0001);
      const volumes = bars.map((bar) => Number(bar.volume)).filter(Number.isFinite);
      const maxVolume = Math.max(...volumes, 1);
      const x = (index) => pad.left + (bars.length === 1 ? plotW / 2 : (plotW * index / (bars.length - 1)));
      const y = (value) => priceTop + ((max - value) / span) * priceH;
      const candleW = Math.max(1, Math.min(12, plotW / Math.max(bars.length, 1) * 0.58));
      const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const gy = priceTop + ratio * priceH;
        const price = max - ratio * span;
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${gy.toFixed(1)}" y2="${gy.toFixed(1)}"></line>
          <text class="axis-label" x="7" y="${(gy + 4).toFixed(1)}">${esc(number(price, 2))}</text>`;
      }).join("");
      const volumeBars = bars.map((bar, index) => {
        const volume = Number(bar.volume);
        const barH = Math.max(1, (volume / maxVolume) * volumeH);
        const cx = x(index);
        return `<rect class="volume-bar" x="${(cx - candleW / 2).toFixed(1)}" y="${(volumeTop + volumeH - barH).toFixed(1)}" width="${Math.max(candleW, 1).toFixed(1)}" height="${barH.toFixed(1)}"></rect>`;
      }).join("");
      const candles = bars.map((bar, index) => {
        const open = Number(bar.open);
        const high = Number(bar.high);
        const low = Number(bar.low);
        const close = Number(bar.close);
        const cls = close > open ? "up" : close < open ? "down" : "flat";
        const cx = x(index);
        const yOpen = y(open);
        const yClose = y(close);
        const top = Math.min(yOpen, yClose);
        const bodyH = Math.max(Math.abs(yClose - yOpen), candleW < 2 ? 1 : 2);
        return `<g>
          <line class="wick ${cls}" x1="${cx.toFixed(1)}" x2="${cx.toFixed(1)}" y1="${y(high).toFixed(1)}" y2="${y(low).toFixed(1)}"></line>
          <rect class="body ${cls}" x="${(cx - candleW / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${candleW.toFixed(1)}" height="${bodyH.toFixed(1)}" rx="1"></rect>
          <title>${esc(bar.trade_date)} O ${esc(bar.open)} H ${esc(bar.high)} L ${esc(bar.low)} C ${esc(bar.close)} V ${esc(bar.volume)}</title>
        </g>`;
      }).join("");
      const closeLine = bars.map((bar, index) => `${index === 0 ? "M" : "L"} ${x(index).toFixed(1)} ${y(Number(bar.close)).toFixed(1)}`).join(" ");
      const first = bars[0]?.trade_date;
      const last = bars[bars.length - 1]?.trade_date;
      el("golden-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Market data OHLCV chart">
        ${grid}
        <line class="axis" x1="${pad.left}" x2="${width - pad.right}" y1="${priceTop + priceH}" y2="${priceTop + priceH}"></line>
        <line class="axis" x1="${pad.left}" x2="${pad.left}" y1="${priceTop}" y2="${priceTop + priceH}"></line>
        <line class="axis" x1="${pad.left}" x2="${width - pad.right}" y1="${volumeTop + volumeH}" y2="${volumeTop + volumeH}"></line>
        <text class="axis-label" x="7" y="${volumeTop + 12}">Vol</text>
        ${volumeBars}
        <path class="close-line" d="${closeLine}"></path>
        ${candles}
        <text class="axis-label" x="${pad.left}" y="${height - 14}">${esc(first)}</text>
        <text class="axis-label" text-anchor="end" x="${width - pad.right}" y="${height - 14}">${esc(last)}</text>
      </svg>`;
    }

    function renderGoldenTable(bars) {
      if (!bars.length) {
        el("golden-table").innerHTML = `<div class="empty">No ${isIntraday() ? "intraday" : "daily"} bars</div>`;
        return;
      }
      el("golden-table").innerHTML = `<table>
        <thead>
          <tr>
            <th style="width: 16%;">${isIntraday() ? "Timestamp" : "Date"}</th>
            <th class="numeric" style="width: 12%;">Open</th>
            <th class="numeric" style="width: 12%;">High</th>
            <th class="numeric" style="width: 12%;">Low</th>
            <th class="numeric" style="width: 12%;">Close</th>
            <th class="numeric" style="width: 13%;">Volume</th>
            <th style="width: 13%;">Source</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          ${bars.map((bar) => `<tr>
            <td>${esc(bar.trade_date)}<br><span class="muted">${esc(bar.adjustment)}</span></td>
            <td class="numeric">${esc(number(bar.open, 4))}</td>
            <td class="numeric">${esc(number(bar.high, 4))}</td>
            <td class="numeric">${esc(number(bar.low, 4))}</td>
            <td class="numeric">${esc(number(bar.close, 4))}</td>
            <td class="numeric">${esc(number(bar.volume, 0))}</td>
            <td>${esc(bar.source_name)}<br><span class="muted">${esc(fmtDateTime(bar.available_at))}</span></td>
            <td>${esc((bar.quality_flags || []).join(", ") || "none")}<br><span class="muted">${esc(bar.raw_ref || String(bar.payload_hash || "").slice(0, 24))}</span></td>
          </tr>`).join("")}
        </tbody>
      </table>`;
    }

    function rawParams() {
      const params = new URLSearchParams();
      const symbol = selectedSymbol();
      if (el("raw-source").value.trim()) params.set("source", el("raw-source").value.trim());
      if (el("raw-environment").value) params.set("environment", el("raw-environment").value);
      if (el("raw-kind").value) params.set("data_kind", el("raw-kind").value);
      if (symbol) params.set("symbol", symbol);
      if (el("raw-recorder-date").value) params.set("recorder_date", el("raw-recorder-date").value);
      if (el("raw-bar-size").value) params.set("bar_size_seconds", el("raw-bar-size").value);
      if (el("raw-limit").value) params.set("limit", el("raw-limit").value);
      return params;
    }

    async function loadRaw() {
      el("raw-status").textContent = "Loading";
      try {
        const response = await fetch(`/api/v1/market-data/audit?${rawParams().toString()}`, {
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`raw audit returned ${response.status}`);
        const data = await response.json();
        renderRaw(data);
        el("raw-status").textContent = "Loaded";
      } catch (error) {
        el("raw-status").textContent = "Error";
        el("raw-table").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      }
    }

    function renderRaw(data) {
      const summary = data.summary || {};
      const rows = data.rows || [];
      if (!rows.length) {
        el("raw-table").innerHTML = '<div class="empty">No raw records</div>';
      } else {
        el("raw-table").innerHTML = `<table>
          <thead>
            <tr>
              <th style="width: 18%;">Time</th>
              <th style="width: 10%;">Symbol</th>
              <th style="width: 18%;">OHLC</th>
              <th style="width: 12%;">Volume</th>
              <th style="width: 12%;">Hash</th>
              <th>Raw Ref</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => {
              const payload = row.payload || {};
              const ohlc = payload.open ? `${payload.open} / ${payload.high} / ${payload.low} / ${payload.close}` : "n/a";
              const flags = (row.quality_flags || []).length ? ` <span class="warn">${esc(row.quality_flags.join(", "))}</span>` : "";
              const dupe = row.duplicate_raw_event_id ? ' <span class="warn">duplicate id</span>' : "";
              return `<tr>
                <td>${esc(fmtDateTime(row.exchange_timestamp || row.received_at))}</td>
                <td>${esc(row.symbol || "")}<br><span class="muted">${esc(row.capture_mode)}</span></td>
                <td>${esc(ohlc)}${flags}${dupe}</td>
                <td class="numeric">${esc(number(payload.volume, 0))}</td>
                <td class="${row.hash_ok ? "ok" : "bad"}">${row.hash_ok ? "ok" : "bad"}</td>
                <td>${esc(row.raw_ref)}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>`;
      }
      const errors = summary.errors || [];
      el("raw-details").innerHTML = `<table>
        <tbody>
          <tr><th style="width: 150px;">Rows</th><td>${esc(summary.rows_returned ?? 0)} of ${esc(summary.entry_count ?? 0)}</td></tr>
          <tr><th>Root</th><td>${esc(summary.root || "n/a")}</td></tr>
          <tr><th>Hash Bad</th><td>${esc(summary.payload_hash_mismatches ?? 0)}</td></tr>
          <tr><th>Duplicate IDs</th><td>${esc(summary.duplicate_raw_event_ids ?? 0)}</td></tr>
          <tr><th>Invalid</th><td>${esc(summary.records_invalid ?? 0)}</td></tr>
          <tr><th>Flags</th><td>${esc(JSON.stringify(summary.quality_flag_counts || {}))}</td></tr>
          <tr><th>Errors</th><td>${errors.length ? esc(errors.join("; ")) : "none"}</td></tr>
        </tbody>
      </table>`;
    }

    async function start() {
      try {
        setStoreControls();
        await loadSymbols();
        await loadActive();
      } catch (error) {
        el("status").textContent = "Error";
        el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
        el("golden-table").innerHTML = "";
      }
    }

    for (const button of document.querySelectorAll("[data-range]")) {
      button.addEventListener("click", () => applyRange(button.dataset.range));
    }
    for (const button of document.querySelectorAll("[data-sessions]")) {
      button.addEventListener("click", () => {
        applyIntradaySessions(button.dataset.sessions).catch((error) => {
          el("status").textContent = "Error";
          el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
        });
      });
    }
    el("zoom-in").addEventListener("click", () => zoom(0.5));
    el("zoom-out").addEventListener("click", () => zoom(2));
    el("pan-left").addEventListener("click", () => pan(-1));
    el("pan-right").addEventListener("click", () => pan(1));
    el("golden-filters").addEventListener("submit", (event) => {
      event.preventDefault();
      loadActive().catch((error) => {
        el("status").textContent = "Error";
        el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      });
    });
    el("golden-symbol").addEventListener("change", () => {
      el("start-date").value = "";
      el("end-date").value = "";
      loadActive().catch((error) => {
        el("status").textContent = "Error";
        el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      });
    });
    el("raw-filters").addEventListener("submit", (event) => {
      event.preventDefault();
      loadRaw();
    });
    el("refresh-btn").addEventListener("click", () => {
      const reload = isIntraday() ? loadSymbols().then(loadActive) : loadActive();
      reload.catch((error) => {
        el("status").textContent = "Error";
        el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      });
    });
    el("store").addEventListener("change", () => {
      setStoreControls();
      loadSymbols().then(loadActive).catch((error) => {
        el("status").textContent = "Error";
        el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
      });
    });
    for (const input of [el("intraday-start-date"), el("intraday-end-date")]) {
      input.addEventListener("change", () => {
        state.sessionPreset = "custom";
        for (const button of document.querySelectorAll("[data-sessions]")) button.setAttribute("aria-pressed", "false");
        loadIntradaySymbols().then(loadIntraday).catch((error) => {
          el("status").textContent = "Error";
          el("golden-chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
        });
      });
    }
    start();
  </script>
</body>
</html>
"""


_RAW_MARKET_DATA_AUDIT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Data Audit</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d2433;
      --muted: #657083;
      --line: #d8dee8;
      --line-soft: #ebeff5;
      --focus: #2456a6;
      --good: #0f766e;
      --warn: #a15c06;
      --bad: #b42318;
      --bar-up: #0f766e;
      --bar-down: #b42318;
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
      min-height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2 {
      margin: 0;
      font-weight: 650;
      letter-spacing: 0;
    }
    h1 { font-size: 18px; }
    h2 { font-size: 15px; }
    main {
      padding: 16px 18px 28px;
      max-width: 1440px;
      margin: 0 auto;
    }
    a.button, button {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 6px 10px;
      text-decoration: none;
      cursor: pointer;
      font: inherit;
    }
    button.primary { background: var(--focus); border-color: var(--focus); color: #fff; }
    .actions, .filters {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .panel, .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .filters {
      padding: 12px;
      margin-bottom: 12px;
    }
    label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    input, select {
      height: 32px;
      min-width: 110px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 5px 8px;
      color: var(--text);
      background: #fff;
      font: inherit;
      font-size: 13px;
    }
    input.symbol { width: 88px; min-width: 88px; text-transform: uppercase; }
    input.small { width: 88px; min-width: 88px; }
    .summary {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .metric {
      min-height: 72px;
      padding: 10px 12px;
    }
    .metric label {
      display: block;
      margin-bottom: 8px;
    }
    .metric strong {
      font-size: 18px;
      overflow-wrap: anywhere;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(420px, .9fr);
      gap: 12px;
      align-items: start;
    }
    .panel {
      overflow: hidden;
      min-width: 0;
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
    .muted, .status-line {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .chart-wrap {
      padding: 10px 12px 12px;
      min-height: 420px;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
    .axis, .grid-line { stroke: #d8dee8; stroke-width: 1; }
    .grid-line { stroke: #eef2f7; }
    .axis-label { fill: var(--muted); font-size: 11px; }
    .wick.up, .body.up { stroke: var(--bar-up); fill: var(--bar-up); }
    .wick.down, .body.down { stroke: var(--bar-down); fill: var(--bar-down); }
    .body.flat { stroke: #5b6472; fill: #5b6472; }
    .table-wrap {
      max-height: 520px;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      color: var(--muted);
      background: #fbfcfd;
      font-size: 12px;
      font-weight: 650;
    }
    .ok { color: var(--good); }
    .bad { color: var(--bad); }
    .warn { color: var(--warn); }
    .empty, .error {
      padding: 14px 12px;
      color: var(--muted);
    }
    .error { color: var(--bad); }
    @media (max-width: 1080px) {
      .summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      header {
        align-items: flex-start;
        flex-direction: column;
        padding: 10px 12px;
      }
      main { padding: 12px; }
      .summary { grid-template-columns: 1fr; }
      .filters { align-items: stretch; }
      label, input, select, button, .button { flex: 1 1 140px; width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Market Data Audit</h1>
    <div class="actions">
      <a class="button" href="/operator">Trading</a>
      <a class="button" href="/strategies">Strategies</a>
      <a class="button" href="/platform">System</a>
      <a class="button" href="/platform/market-data-audit">Market Data</a>
    </div>
  </header>
  <main>
    <form id="filters" class="filters panel">
      <label>Source<input id="source" value="interactive-brokers"></label>
      <label>Capture Env<select id="environment"><option value="">all</option><option value="paper">paper</option><option value="live">live</option></select></label>
      <label>Kind<select id="data-kind"><option value="bar">bar</option><option value="quote">quote</option><option value="trade">trade</option></select></label>
      <label>Symbol<input id="symbol" class="symbol" list="symbol-options" placeholder="search"><datalist id="symbol-options"></datalist></label>
      <label>Recorder Date<input id="recorder-date" type="date"></label>
      <label>Bar Size<input id="bar-size" class="small" type="number" min="1" placeholder="all"></label>
      <label>Limit<input id="limit" class="small" type="number" min="1" max="5000" value="500"></label>
      <button class="primary" type="submit">Run</button>
      <button id="refresh-btn" type="button">Refresh</button>
      <span id="status" class="status-line">Loading</span>
    </form>
    <section class="summary" aria-label="Market data audit summary">
      <div class="metric"><label>Rows</label><strong id="metric-rows">0</strong></div>
      <div class="metric"><label>Bars</label><strong id="metric-bars">0</strong></div>
      <div class="metric"><label>Hash Bad</label><strong id="metric-hash">0</strong></div>
      <div class="metric"><label>Duplicate IDs</label><strong id="metric-dupes">0</strong></div>
      <div class="metric"><label>Invalid</label><strong id="metric-invalid">0</strong></div>
      <div class="metric"><label>Range</label><strong id="metric-range">n/a</strong></div>
    </section>
    <div class="grid">
      <section class="panel">
        <div class="panel-head">
          <h2>OHLC</h2>
          <span id="chart-meta" class="status-line">n/a</span>
        </div>
        <div id="chart" class="chart-wrap"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>Raw Records</h2>
          <span id="table-meta" class="status-line">n/a</span>
        </div>
        <div id="table" class="table-wrap"></div>
      </section>
    </div>
    <section class="panel" style="margin-top: 12px;">
      <div class="panel-head">
        <h2>Audit Details</h2>
        <span id="detail-meta" class="status-line">n/a</span>
      </div>
      <div id="details"></div>
    </section>
  </main>
  <script>
    const el = (id) => document.getElementById(id);

    function esc(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function fmtTime(value) {
      if (!value) return "n/a";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString();
    }

    function shortTime(value) {
      if (!value) return "n/a";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }

    function number(value, digits = 2) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return "n/a";
      return parsed.toLocaleString(undefined, { maximumFractionDigits: digits });
    }

    function queryParams() {
      const params = new URLSearchParams();
      for (const [key, id] of [
        ["source", "source"],
        ["environment", "environment"],
        ["data_kind", "data-kind"],
        ["symbol", "symbol"],
        ["recorder_date", "recorder-date"],
        ["bar_size_seconds", "bar-size"],
        ["limit", "limit"]
      ]) {
        const value = el(id).value.trim();
        if (value) params.set(key, value.toUpperCase && key === "symbol" ? value.toUpperCase() : value);
      }
      return params;
    }

    function symbolParams() {
      const params = new URLSearchParams();
      for (const [key, id] of [
        ["source", "source"],
        ["environment", "environment"],
        ["data_kind", "data-kind"],
        ["recorder_date", "recorder-date"]
      ]) {
        const value = el(id).value.trim();
        if (value) params.set(key, value);
      }
      return params;
    }

    async function loadSymbols() {
      try {
        const response = await fetch(`/api/v1/market-data/audit/symbols?${symbolParams().toString()}`, {
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`symbol endpoint returned ${response.status}`);
        const data = await response.json();
        const symbols = data.symbols || [];
        el("symbol-options").innerHTML = symbols.map((symbol) => `<option value="${esc(symbol)}"></option>`).join("");
        const current = el("symbol").value.trim().toUpperCase();
        if (!current && symbols.length) {
          el("symbol").value = symbols[0];
          return true;
        }
        if (current && symbols.length && !symbols.includes(current)) {
          el("symbol").value = symbols[0];
          return true;
        }
      } catch (error) {
        el("symbol-options").innerHTML = "";
      }
      return false;
    }

    async function load() {
      el("status").textContent = "Loading";
      try {
        const response = await fetch(`/api/v1/market-data/audit?${queryParams().toString()}`, {
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`audit endpoint returned ${response.status}`);
        const data = await response.json();
        render(data);
        el("status").textContent = "Loaded";
      } catch (error) {
        el("status").textContent = "Error";
        el("chart").innerHTML = `<div class="error">${esc(error.message)}</div>`;
        el("table").innerHTML = "";
      }
    }

    function render(data) {
      const summary = data.summary || {};
      const bars = data.bars || [];
      const rows = data.rows || [];
      el("metric-rows").textContent = summary.rows_returned ?? 0;
      el("metric-bars").textContent = bars.length;
      el("metric-hash").textContent = summary.payload_hash_mismatches ?? 0;
      el("metric-dupes").textContent = summary.duplicate_raw_event_ids ?? 0;
      el("metric-invalid").textContent = summary.records_invalid ?? 0;
      el("metric-range").textContent = `${shortTime(summary.first_exchange_timestamp)} - ${shortTime(summary.last_exchange_timestamp)}`;
      el("chart-meta").textContent = `${summary.symbol || "all"} | ${summary.recorder_date || "all dates"}`;
      el("table-meta").textContent = `${rows.length} rows`;
      renderChart(bars);
      renderTable(rows);
      renderDetails(summary);
    }

    function renderChart(bars) {
      if (!bars.length) {
        el("chart").innerHTML = '<div class="empty">No bars</div>';
        return;
      }
      const width = 860;
      const height = 360;
      const pad = { left: 58, right: 16, top: 16, bottom: 42 };
      const highs = bars.map((bar) => Number(bar.high)).filter(Number.isFinite);
      const lows = bars.map((bar) => Number(bar.low)).filter(Number.isFinite);
      const min = Math.min(...lows);
      const max = Math.max(...highs);
      const span = Math.max(max - min, 0.0001);
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;
      const x = (index) => pad.left + (bars.length === 1 ? plotW / 2 : (plotW * index / (bars.length - 1)));
      const y = (value) => pad.top + ((max - value) / span) * plotH;
      const candleW = Math.max(4, Math.min(16, plotW / Math.max(bars.length, 1) * 0.55));
      const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const gy = pad.top + ratio * plotH;
        const price = max - ratio * span;
        return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${gy.toFixed(1)}" y2="${gy.toFixed(1)}"></line>
          <text class="axis-label" x="6" y="${(gy + 4).toFixed(1)}">${esc(number(price, 2))}</text>`;
      }).join("");
      const candles = bars.map((bar, index) => {
        const open = Number(bar.open);
        const close = Number(bar.close);
        const high = Number(bar.high);
        const low = Number(bar.low);
        const cls = close > open ? "up" : close < open ? "down" : "flat";
        const cx = x(index);
        const yOpen = y(open);
        const yClose = y(close);
        const top = Math.min(yOpen, yClose);
        const bodyH = Math.max(Math.abs(yClose - yOpen), 2);
        return `<g>
          <line class="wick ${cls}" x1="${cx.toFixed(1)}" x2="${cx.toFixed(1)}" y1="${y(high).toFixed(1)}" y2="${y(low).toFixed(1)}"></line>
          <rect class="body ${cls}" x="${(cx - candleW / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${candleW.toFixed(1)}" height="${bodyH.toFixed(1)}" rx="1"></rect>
          <title>${esc(fmtTime(bar.exchange_timestamp))} O ${esc(bar.open)} H ${esc(bar.high)} L ${esc(bar.low)} C ${esc(bar.close)}</title>
        </g>`;
      }).join("");
      const first = bars[0]?.exchange_timestamp;
      const last = bars[bars.length - 1]?.exchange_timestamp;
      el("chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Market data OHLC chart">
        ${grid}
        <line class="axis" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}"></line>
        <line class="axis" x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${height - pad.bottom}"></line>
        ${candles}
        <text class="axis-label" x="${pad.left}" y="${height - 14}">${esc(fmtTime(first))}</text>
        <text class="axis-label" text-anchor="end" x="${width - pad.right}" y="${height - 14}">${esc(fmtTime(last))}</text>
      </svg>`;
    }

    function renderTable(rows) {
      if (!rows.length) {
        el("table").innerHTML = '<div class="empty">No records</div>';
        return;
      }
      el("table").innerHTML = `<table>
        <thead>
          <tr>
            <th style="width: 19%;">Time</th>
            <th style="width: 10%;">Symbol</th>
            <th style="width: 18%;">OHLC</th>
            <th style="width: 12%;">Volume</th>
            <th style="width: 12%;">Hash</th>
            <th>Raw Ref</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => {
            const payload = row.payload || {};
            const ohlc = payload.open ? `${payload.open} / ${payload.high} / ${payload.low} / ${payload.close}` : "n/a";
            const hashClass = row.hash_ok ? "ok" : "bad";
            const flags = (row.quality_flags || []).length ? ` <span class="warn">${esc(row.quality_flags.join(", "))}</span>` : "";
            const dupe = row.duplicate_raw_event_id ? ' <span class="warn">duplicate id</span>' : "";
            return `<tr>
              <td>${esc(fmtTime(row.exchange_timestamp || row.received_at))}</td>
              <td>${esc(row.symbol || "")}<br><span class="muted">${esc(row.capture_mode)}</span></td>
              <td>${esc(ohlc)}${flags}${dupe}</td>
              <td>${esc(number(payload.volume, 0))}</td>
              <td class="${hashClass}">${row.hash_ok ? "ok" : "bad"}</td>
              <td>${esc(row.raw_ref)}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>`;
    }

    function renderDetails(summary) {
      const errors = summary.errors || [];
      el("detail-meta").textContent = summary.root || "n/a";
      el("details").innerHTML = `<table>
        <tbody>
          <tr><th style="width: 180px;">Root</th><td>${esc(summary.root)}</td></tr>
          <tr><th>Entries</th><td>${esc(summary.entry_count)} catalog entries, ${esc(summary.rows_returned)} returned</td></tr>
          <tr><th>Raw Ref Duplicates</th><td>${esc(summary.duplicate_raw_refs)}</td></tr>
          <tr><th>Raw Event ID Duplicates</th><td>${esc(summary.duplicate_raw_event_ids)}</td></tr>
          <tr><th>Quality Flags</th><td>${esc(JSON.stringify(summary.quality_flag_counts || {}))}</td></tr>
          <tr><th>Errors</th><td>${errors.length ? esc(errors.join("; ")) : "none"}</td></tr>
        </tbody>
      </table>`;
    }

    el("recorder-date").value = new Date().toISOString().slice(0, 10);
    for (const id of ["source", "environment", "data-kind", "recorder-date"]) {
      el(id).addEventListener("change", async () => {
        const changed = await loadSymbols();
        if (changed) load();
      });
    }
    el("filters").addEventListener("submit", (event) => {
      event.preventDefault();
      load();
    });
    el("refresh-btn").addEventListener("click", load);
    loadSymbols().then(load);
  </script>
</body>
</html>
"""
