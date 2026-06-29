from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/platform", response_class=HTMLResponse, include_in_schema=False)
def platform_health_portal() -> HTMLResponse:
    return HTMLResponse(_PLATFORM_HTML)


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
      <span class="status-line"><span id="overall-dot" class="dot"></span><span id="overall-status">Loading</span></span>
      <a class="button" href="/operator">Operator</a>
      <button id="refresh-btn" class="primary" type="button">Refresh</button>
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
          <span class="status-line">Auto-refresh 5s</span>
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

    function renderCards(health) {
      const services = health.services || [];
      if (!services.length) {
        el("service-cards").innerHTML = '<div class="empty">No services</div>';
        return;
      }
      el("service-cards").innerHTML = services.map((service) => {
        const cls = statusClass(service.status);
        return `
          <article class="service-card">
            <div class="service-top">
              <div class="service-name">${esc(service.display_name)}</div>
              <span class="status ${cls}">${esc(service.status)}</span>
            </div>
            <div class="service-meta">${esc(service.service_id)} | ${esc(service.service_type)} | ${service.required ? "required" : "optional"}</div>
            <div class="service-meta">Heartbeat age: ${esc(age(service.heartbeat_at, health.checked_at))}</div>
            <div class="service-message">${esc(service.message)}</div>
          </article>
        `;
      }).join("");
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

    async function load() {
      try {
        const [health, graph] = await Promise.all([
          api("/health"),
          api("/api/v1/platform/service-graph")
        ]);
        renderSummary(health);
        renderCards(health);
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
