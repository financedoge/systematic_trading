"""Presentation for the Gateway execution workspace; broker actions stay in the API."""

WORKSPACE_CSS = """
:root { --bg:#edf1f6; --text:#1b2b42; --line:#dfe6ee; --focus:#255bce; }
[hidden] { display:none !important; }
body { font-family:"Segoe UI",system-ui,sans-serif; font-variant-numeric:tabular-nums; }
header { background:#13243b; color:#fff; height:68px; padding:0 28px; }
header h1 { font-size:17px; letter-spacing:.02em; }
header .button { background:transparent; color:#c5d2e5; border-color:transparent; }
header .button[href="/operator"] { background:#28415e; color:#fff; }
.shell { grid-template-columns:minmax(0,1fr) 350px; max-width:1920px; margin:auto; }
main { padding:26px; }
aside { background:#f8fafc; border-left:1px solid var(--line); top:0; height:calc(100vh - 68px); }
.panel { border-radius:12px; border:1px solid var(--line); box-shadow:0 2px 5px #162b4305; margin-bottom:20px; }
.panel-head { padding:17px 20px; background:#fff; }
.panel-head h2 { font-size:14px; font-weight:650; }
.metrics-compact { padding:16px 20px; gap:18px; background:#fff; }
.mini-metric label { font-size:10px; text-transform:uppercase; letter-spacing:.08em; }
.mini-metric strong { font-size:19px; font-weight:600; margin-top:7px; }
button,a.button { border-radius:7px; font-size:12px; font-weight:600; min-height:34px; }
button:disabled { opacity:.4; cursor:not-allowed; }
th { font-size:10px; text-transform:uppercase; letter-spacing:.065em; background:#f7f9fc; }
td { padding:12px 14px; font-size:12px; }
.workspace-heading { display:flex; justify-content:space-between; align-items:center; margin:0 0 24px; gap:16px; }
.workspace-heading h2 { font-size:27px; letter-spacing:-.7px; margin:3px 0 6px; font-weight:650; }
.eyebrow { color:#667991; font-size:10px; text-transform:uppercase; letter-spacing:.15em; font-weight:700; }
.subtle { color:#738297; font-size:12px; line-height:1.6; }
.paper-tag { background:#e4f2ec; color:#176445; border:1px solid #c1e1d2; border-radius:20px; padding:6px 12px; font-size:11px; font-weight:700; white-space:nowrap; }
.approval-control { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:20px; }
.approval-control h3 { margin:0 0 7px; font-size:15px; }
.approval-switch { flex-shrink:0; background:#eef2f7; color:#344b66; border:1px solid #cbd5e1; }
.approval-switch[aria-checked="true"] { background:#176445; color:white; border-color:#176445; }
.cost-adverse { color:#a04b23; } .cost-better { color:#176445; }
.blotter-tools { padding:12px 20px; display:flex; flex-wrap:wrap; align-items:center; gap:12px 18px; border-bottom:1px solid var(--line); }
.blotter-tools label { display:flex; align-items:center; gap:7px; }
.blotter-tools select,.blotter-tools input { padding:7px 10px; border:1px solid var(--line); border-radius:6px; background:white; font:inherit; }
.blotter-range { display:flex; flex-wrap:wrap; gap:12px; }
.blotter-caption { padding:9px 20px; display:flex; flex-wrap:wrap; justify-content:space-between; gap:6px 18px; background:#f7f9fc; }
.order-timing { font-size:11px; line-height:1.7; }
.order-status.terminal { background:#e4f2ec; color:#176445; }
.order-status.missed { background:#f0f1f4; color:#697789; }
.order-scroll { overflow:auto; max-height:490px; }
.order-scroll table { min-width:940px; table-layout:auto; }
.order-scroll td,.order-scroll th { white-space:nowrap; overflow-wrap:normal; }
.row-actions { min-width:180px; }
.row-actions button { white-space:nowrap; flex-shrink:0; }
.proposal-row { min-width:0; }
.proposal-row > span:first-child { min-width:0; overflow:hidden; flex:1; }
.proposal-row .badge { flex-shrink:0; }
.proposal-title,.meta { display:block; }
.list { overflow-x:hidden; }
.order-symbol { font-weight:700; color:#182c47; }
.order-status { display:inline-block; padding:4px 8px; border-radius:5px; background:#eef2f7; font-size:11px; white-space:nowrap; }
.order-status.working { background:#e9f0fe; color:#275ac0; }
.order-status.attention { background:#fff0d8; color:#8b5909; }
.row-actions { display:flex; gap:5px; }
.row-actions button { min-height:27px; font-size:11px; padding:4px 8px; }
.workspace-message { padding:12px 20px; font-size:12px; color:#49617c; background:#f6f9fd; }
.workspace-message.error { color:#a02323; background:#fff1f0; }
.empty-state { padding:42px 24px; text-align:center; color:#77879a; }
.empty-state strong { display:block; color:#344b66; margin-bottom:8px; font-size:15px; }
#broker-portfolio { overflow:auto; }
.audit-detail { padding:10px 20px; border-top:1px solid var(--line); font-size:12px; }
.audit-detail pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:200px; overflow:auto; color:#596a80; }
dialog { border:1px solid var(--line); border-radius:14px; width:min(520px,calc(100vw - 32px)); padding:26px; color:var(--text); box-shadow:0 24px 80px #13243b40; }
dialog::backdrop { background:#10213980; }
dialog h2 { margin:0 0 12px; font-size:22px; }
dialog label { display:block; font-size:12px; font-weight:600; margin-top:16px; }
dialog input,dialog textarea { display:block; width:100%; border:1px solid #cbd5e1; border-radius:6px; padding:9px; margin-top:6px; font:inherit; }
dialog .actions { margin-top:24px; justify-content:flex-end; }
#amend-fields { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
#amend-fields[hidden] { display:none; }
.rail-panel { margin:12px; border:1px solid var(--line); border-radius:9px; background:white; overflow:hidden; }
@media(max-width:1200px) { .shell{grid-template-columns:minmax(0,1fr) 300px;} main{padding:18px;} }
@media(max-width:950px) { .shell{display:flex;flex-direction:column;} main{order:0;} aside{order:1;height:auto;position:static;width:100%;} }
@media(max-width:560px) { header{height:auto;padding:14px;} main{padding:12px;} .workspace-heading{align-items:flex-start;} .workspace-heading h2{font-size:23px;} .panel-head,.blotter-tools{padding:12px;flex-wrap:wrap;} .metrics-compact{grid-template-columns:repeat(2,minmax(0,1fr));padding:12px;} .mini-metric strong{font-size:16px;overflow-wrap:anywhere;} .workspace-heading .subtle{max-width:220px;} }
"""

WORKSPACE_HTML = """
<div class="workspace-heading"><div><div class="eyebrow">Execution workspace</div><h2>Trading operations</h2><div class="subtle">Manage orders, reconcile holdings and review your next trade.</div></div><span class="paper-tag">PAPER ACCOUNT</span></div>
<section class="panel"><div class="approval-control"><div><h3>Approval mode <span id="approval-mode-label" class="paper-tag">Manual</span></h3><div class="subtle">Automatic mode approves and submits new strategy TWAP proposals in the paper account.</div><div class="subtle" id="approval-policy-status" role="status">Loading approval policy…</div></div><button id="approval-mode-switch" class="approval-switch" role="switch" aria-checked="false" aria-label="Automatic paper approval and submission" disabled>Automatic: off</button></div></section>
<section class="panel" id="gateway-orders-panel">
<div class="panel-head"><div><h2>Order blotter</h2><span class="subtle">IB Gateway · Broker status alongside the local audit trail</span></div><button id="sync-orders-btn" class="primary">Sync orders</button></div>
<div class="metrics-compact"><div class="mini-metric"><label>Working in date range</label><strong id="orders-working">—</strong></div><div class="mini-metric"><label>Needs review in date range</label><strong id="orders-pending">—</strong></div><div class="mini-metric"><label>Orders in date range</label><strong id="orders-total">—</strong></div><div class="mini-metric"><label>Last broker sync</label><strong id="orders-sync-time" style="font-size:12px">Not synced</strong></div></div>
<div class="blotter-tools">
<label class="subtle">Trade date <select id="order-date-filter"><option value="today" selected>Today</option><option value="week">Last 7 days</option><option value="range">Date range</option><option value="all">All dates</option></select></label>
<span class="blotter-range" id="order-date-range" hidden><label class="subtle">From <input id="order-date-start" type="date"></label><label class="subtle">To <input id="order-date-end" type="date"></label></span>
<label class="subtle">Status <select id="order-filter"><option value="all" selected>All statuses</option><option value="working">Working</option><option value="filled">Filled</option><option value="attention">Needs attention</option><option value="terminal">Completed / closed</option><option value="missed">Missed</option></select></label>
</div>
<div class="blotter-caption subtle"><span id="order-filter-summary" role="status"></span><span id="order-timezone-note"></span></div>
<div id="gateway-order-table" class="order-scroll"></div>
<div class="blotter-caption subtle">TWAP estimate: time-weighted 1-minute trade closes over the scheduled window, including any approval delay. Requires complete coverage. Positive slippage / price cost = worse execution; negative = improvement. Costs are in the instrument’s currency and exclude commissions and fees.</div>
<div id="order-action-message" class="workspace-message" role="status" aria-live="polite">Connecting to Gateway…</div>
<details class="audit-detail"><summary>Order activity and audit history</summary><div id="order-audit-history"></div></details>
</section>
"""

WORKSPACE_DIALOG = """
<dialog id="approval-mode-dialog" aria-labelledby="approval-mode-title"><form id="approval-mode-form">
<div class="eyebrow">Paper trading policy</div><h2 id="approval-mode-title">Enable automatic approval</h2>
<p class="subtle">New proposals from the current strategy will be approved and sent to IB Gateway automatically when their TWAP window opens. Existing proposals keep their current approval status. Reconciliation, cash, risk and execution checks still apply. Failed or uncertain submissions need manual review.</p>
<label>Maximum gross order value per batch (CNH)<input id="approval-cap" type="number" min="1" step="any" required value="1000000"></label>
<label>Operator<input id="approval-operator" required maxlength="100" value="Local operator"></label>
<label>Reason<textarea id="approval-reason" required maxlength="500" rows="2" placeholder="Reason for enabling automatic paper trading"></textarea></label>
<p class="subtle">Turning this off stops future automatic submissions. Orders already sent to IB continue and can be managed in the blotter.</p>
<div id="approval-policy-error" class="warnings" role="alert"></div><div class="actions"><button type="button" id="close-approval-dialog">Back</button><button type="submit" class="primary" id="confirm-auto-approval">Enable automatic paper trading</button></div>
</form></dialog>
<dialog id="order-action-dialog" aria-labelledby="order-action-title"><form id="order-action-form">
<div class="eyebrow">Review paper order</div><h2 id="order-action-title">Order action</h2><div id="order-action-summary" class="subtle"></div>
<div id="amend-fields" hidden><label>Total quantity<input id="amend-quantity" type="number" min="1" step="1"></label><label>Limit price<input id="amend-price" type="number" min="0.0001" step="any"></label></div>
<p id="amend-note" class="subtle" hidden>Amendments may reduce total quantity or improve the approved limit. A larger exposure or algorithm change requires a new proposal.</p>
<label>Operator<input id="order-operator" required maxlength="100" autocomplete="name" value="Local operator"></label>
<label>Reason<textarea id="order-reason" required maxlength="500" rows="2" placeholder="Why are you making this change?"></textarea></label>
<div id="order-dialog-error" class="warnings" role="alert"></div>
<div class="actions"><button type="button" id="close-order-dialog">Back</button><button type="submit" class="primary" id="confirm-order-action">Confirm</button></div>
</form></dialog>
"""

WORKSPACE_JS = r"""
    let workspace = {records:[], snapshot:null}, orderSyncBusy = false, reviewedAction = null;
    let executionAnalytics = {}, approvalPolicy = null, approvalReviewRevision = null;
    function executionPrice(value) {
      return value!=null && Number(value)>0 ? Number(value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:4}) : '—';
    }
    function benchmarkCells(record) {
      const a=executionAnalytics[record.local_order_id], ready=a?.status==='ready';
      const explanation=ready?`${a.coverage} coverage · ${a.bar_count} bars · ${orderTimestamp(a.window_start)} to ${orderTimestamp(a.window_end)} ${orderTimeZone}`:(a?.message||'No completed benchmark available');
      const signed=value=>Number(value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:'exceptZero'});
      const cost=a?.slippage_bps!=null?`<span class="${Number(a.slippage_bps)>0?'cost-adverse':'cost-better'}">${signed(a.slippage_bps)} bps</span><div class="subtle">${signed(a.price_cost)} ${esc(a.currency)}</div>`:'—';
      return `<td class="num">${executionPrice(record.average_fill_price)}<div class="subtle">${esc(record.order.currency||'')}</div></td><td class="num" title="${esc(explanation)}">${ready?executionPrice(a.twap_price):'—'}<div class="subtle">${ready?'100% coverage':esc(a?.status||'Unavailable')}</div></td><td class="num">${cost}</td>`;
    }
    const workingStates = ['PendingSubmit','ApiPending','PreSubmitted','Submitted','PendingCancel'];
    const orderTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    function orderDateAt(value, timeZone='America/New_York') {
      const date = new Date(value);
      if(!value || !Number.isFinite(date.getTime())) return '';
      const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
        timeZone, year:'numeric', month:'2-digit', day:'2-digit'
      }).formatToParts(date).map(p=>[p.type,p.value]));
      return `${parts.year}-${parts.month}-${parts.day}`;
    }
    function orderTradeDate(record) {
      // Bulk missed-window updates are not new orders. Use the intended
      // session, or actual submission date for legacy unscheduled orders.
      return record.order?.intended_trade_date || orderDateAt(record.submitted_at);
    }
    function orderTimestamp(value) {
      if(!value || !Number.isFinite(Date.parse(value))) return '—';
      return `${orderDateAt(value,orderTimeZone)} ${new Intl.DateTimeFormat('en-GB', {
        timeZone:orderTimeZone, hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23'
      }).format(new Date(value))}`;
    }
    function orderDateBounds(now=new Date()) {
      const today=orderDateAt(now), mode=el('order-date-filter').value;
      if(mode==='all') return {start:'',end:''};
      if(mode==='range') return {start:el('order-date-start').value,end:el('order-date-end').value};
      const weekStart=new Date(`${today}T12:00:00Z`);
      weekStart.setUTCDate(weekStart.getUTCDate()-6);
      return {start:mode==='week'?weekStart.toISOString().slice(0,10):today,end:today};
    }
    function matchesOrderDate(record, bounds) {
      if(el('order-date-filter').value==='all') return true;
      const day=orderTradeDate(record);
      return Boolean(day && bounds.start && bounds.end && day>=bounds.start && day<=bounds.end);
    }
    function matchesOrderStatus(record, filter) {
      if(filter==='all') return true;
      if(filter==='filled') return record.status==='filled' || record.broker_observation?.status==='Filled';
      return category(record)===filter;
    }
    function newestOrdersFirst(a,b) {
      return orderTradeDate(b).localeCompare(orderTradeDate(a)) ||
        (Date.parse(b.submitted_at)||0)-(Date.parse(a.submitted_at)||0) ||
        (Date.parse(b.updated_at)||0)-(Date.parse(a.updated_at)||0) ||
        String(a.local_order_id).localeCompare(String(b.local_order_id));
    }
    function displayedOrderQuantity(record) {
      const reported=Number(record.broker_observation?.quantity);
      // Completed-order callbacks can omit/reset totalQuantity to zero.
      return record.status==='filled'||!Number.isFinite(reported)||reported<=0 ? record.order.quantity : reported;
    }
    function orderMessage(text, error=false) {
      el('order-action-message').textContent=text;
      el('order-action-message').classList.toggle('error',error);
    }
    function category(record) {
      if(record.pending_action || record.execution_sync_issue || record.status==='pending_submit') return 'attention';
      if(record.status==='missed') return 'missed';
      if(record.status==='filled') return 'terminal';
      if(workingStates.includes(record.broker_observation?.status)) return 'working';
      if(['submitted','acknowledged','partially_filled'].includes(record.status) && !['Cancelled','ApiCancelled','Filled'].includes(record.broker_observation?.status)) return 'attention';
      return 'terminal';
    }
    function renderWorkspace() {
      const records=workspace.records || [], snapshot=workspace.snapshot;
      const fresh=snapshot && Date.now()-Date.parse(snapshot.checked_at)<45000;
      const bounds=orderDateBounds(), dateRows=records.filter(r=>matchesOrderDate(r,bounds));
      const currentlyObserved=r=>fresh && (snapshot.orders||[]).some(o=>o.order_ref===r.order_ref&&o.broker_order_id===r.broker_order_id&&o.client_id===workspace.client_id);
      el('order-date-range').hidden=el('order-date-filter').value!=='range';
      el('orders-total').textContent=dateRows.length;
      el('orders-working').textContent=fresh ? dateRows.filter(r=>currentlyObserved(r)&&category(r)==='working').length : '—';
      el('orders-pending').textContent=dateRows.filter(r=>category(r)==='attention').length;
      el('orders-sync-time').textContent=snapshot ? fmtDateTime(snapshot.checked_at) : 'Not synced';
      const filter=el('order-filter').value;
      const rows=dateRows.filter(r=>matchesOrderStatus(r,filter)).sort(newestOrdersFirst);
      const known=new Set(records.map(r=>`${r.order_ref}:${r.broker_order_id}`));
      const external=(snapshot?.orders||[]).filter(r=>!known.has(`${r.order_ref}:${r.broker_order_id}`));
      const externalRows=external.filter(b=>{
        // Unlinked broker snapshots have no reliable submission/trade date.
        // Keep current working orders visible; never invent dates from sync time.
        const active=b.source==='open'&&workingStates.includes(b.status);
        const dateAllowed=el('order-date-filter').value==='all'||active;
        const statusAllowed=filter==='all'||(filter==='working'&&active)||
          (filter==='filled'&&b.status==='Filled')||(filter==='terminal'&&!active);
        return dateAllowed&&statusAllowed;
      });
      const outsideWorking=records.filter(r=>!matchesOrderDate(r,bounds)&&currentlyObserved(r)&&category(r)==='working').length;
      const scope=el('order-date-filter').value==='all'?'all dates':`${bounds.start}–${bounds.end}`;
      const invalid=el('order-date-filter').value==='range'&&(!bounds.start||!bounds.end||bounds.start>bounds.end);
      el('order-filter-summary').textContent=invalid ? 'Choose a valid start and end date.' :
        `${rows.length} of ${dateRows.length} local orders shown · ${scope} · ${records.length} in history`+
        (externalRows.length?` · ${externalRows.length} unlinked broker orders (date unknown)`:'')+
        (outsideWorking?` · ${outsideWorking} working outside this date range — choose All dates`:'');
      el('order-timezone-note').textContent=`Trade dates: New York · Times: ${orderTimeZone} · Auto-sync 15s`;
      let html=rows.map(r=>{
        const b=r.broker_observation||{};
        const observed=currentlyObserved(r);
        const active=observed && workingStates.includes(b.status) && r.status!=='filled' && b.status!=='PendingCancel' && !r.pending_action && r.environment==='paper';
        const retry=observed && ['Cancelled','ApiCancelled'].includes(b.status) && ['cancelled','rejected'].includes(r.status) && !r.pending_action && r.filled_quantity===0 && Number(b.filled)===0 && b.filled!=null;
        const status=r.pending_action ? `${r.pending_action.action} pending` : r.status==='filled'?'Filled':(b.status || r.status);
        const timing=`<div>${r.submitted_at?esc(orderTimestamp(r.submitted_at)):'Not submitted'}</div><div class="subtle">Updated ${esc(orderTimestamp(r.updated_at))}</div><div class="subtle">Trade date ${esc(orderTradeDate(r)||'unknown')}</div>`;
        return `<tr>
          <td><span class="order-symbol">${esc(r.order.symbol)}</span><div class="subtle">${esc(r.order_ref)}</div></td>
          <td><span class="order-status ${category(r)}">${esc(status)}</span><div class="subtle">${r.pending_action?'Awaiting broker confirmation':observed?'IB confirmed':r.status==='missed'?'Not routed · missed window':r.status==='filled'?'Recorded execution history':'Last known · sync required'}</div></td>
          <td class="num">${esc(r.status==='filled'?r.filled_quantity:(b.filled??r.filled_quantity))} / ${esc(displayedOrderQuantity(r))}</td>
          ${benchmarkCells(r)}
          <td class="order-timing">${timing}</td>
          <td>${esc(r.order.side.toUpperCase())}<div class="subtle">${esc(b.algo_strategy||r.order.order_type)}</div></td>
          <td class="num">${b.limit_price ? fmtMoney(b.limit_price) : '—'}</td>
          <td>${esc(r.broker_order_id??'—')}<div class="subtle">${esc(b.account||'')}</div></td>
          <td><div class="row-actions"><button data-action="cancel" data-order="${esc(r.local_order_id)}" ${active?'':'disabled'}>Cancel</button><button title="Amend a working plain limit order within approved quantity and price limits" data-action="amend" data-order="${esc(r.local_order_id)}" ${active&&b.order_type==='LMT'&&!b.algo_strategy?'':'disabled'}>Amend</button><button title="Requires confirmed cancellation, zero fills, a current approval and matched reconciliation" data-action="resubmit" data-order="${esc(r.local_order_id)}" ${retry?'':'disabled'}>Resubmit</button></div></td>
        </tr>`;
      }).join('');
      html+=externalRows.map(b=>`<tr><td class="order-symbol">${esc(b.symbol)}</td><td><span class="order-status">${esc(b.status)}</span></td><td class="num">${esc(b.filled??'?')} / ${Number(b.quantity)>0?esc(b.quantity):'?'}</td><td class="num">${executionPrice(b.average_fill_price)}</td><td>—</td><td>—</td><td class="order-timing">Submission unknown<div class="subtle">Observed ${esc(orderTimestamp(b.checked_at))}</div></td><td>${esc(b.side)}</td><td class="num">${fmtMaybeMoney(b.limit_price)}</td><td>${esc(b.broker_order_id)}</td><td class="subtle">External / unlinked · view only</td></tr>`).join('');
      el('gateway-order-table').innerHTML=html ? `<table><thead><tr><th>Instrument / reference</th><th>Status</th><th class="num">Filled / total</th><th class="num">Avg fill</th><th class="num">TWAP estimate</th><th class="num">Slippage / price cost</th><th>Submitted / updated</th><th>Side / type</th><th class="num">Limit</th><th>IB order</th><th>Manage</th></tr></thead><tbody>${html}</tbody></table>` : `<div class="empty-state"><strong>No orders match these filters</strong>${filter==='working'&&dateRows.some(r=>matchesOrderStatus(r,'filled'))?'Filled orders remain available under All statuses or Filled.':'Choose All statuses or All dates to see more history.'}</div>`;
      el('order-audit-history').innerHTML=rows.length ? rows.map(r=>`<details><summary>${esc(r.order.symbol)} · ${esc(orderTradeDate(r)||'Date unknown')} · ${esc(r.order_ref)} · ${esc(r.message||r.status)}</summary><pre>${esc(JSON.stringify({submitted_at:r.submitted_at,updated_at:r.updated_at,trade_date:orderTradeDate(r),broker:r.broker_observation,actions:r.management_audit,executions:r.execution_fills,issue:r.execution_sync_issue},null,2))}</pre></details>`).join('') : '<p class="subtle">No order activity matches these filters.</p>';
      el('gateway-order-table').querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>openOrderAction(b.dataset.order,b.dataset.action)));
    }
    async function loadWorkspace() {
      workspace=await api('/api/v1/execution/interactive-brokers/workspace'); renderWorkspace();
      loadExecutionAnalytics().catch(()=>{});
      loadApprovalPolicy().catch(error=>{el('approval-policy-status').textContent=error.message;el('approval-mode-switch').disabled=true;});
    }
    async function loadExecutionAnalytics() {
      const bounds=orderDateBounds(), ids=workspace.records.filter(r=>r.filled_quantity>0&&matchesOrderDate(r,bounds)).slice(0,100).map(r=>r.local_order_id);
      if(!ids.length) return;
      const result=await api('/api/v1/execution/interactive-brokers/order-analytics',{method:'POST',body:JSON.stringify({local_order_ids:ids})});
      Object.assign(executionAnalytics,result); renderWorkspace();
    }
    async function loadApprovalPolicy() {
      approvalPolicy=await api('/api/v1/automation/paper-approval');
      el('approval-mode-label').textContent=approvalPolicy.enabled?'Paper automatic':'Manual';
      el('approval-mode-switch').setAttribute('aria-checked',String(approvalPolicy.enabled));
      el('approval-mode-switch').textContent=`Automatic: ${approvalPolicy.enabled?'on':'off'}`;
      el('approval-mode-switch').disabled=false;
      el('approval-policy-status').textContent=approvalPolicy.message+(approvalPolicy.enabled?` · Batch cap ${fmtMoney(approvalPolicy.max_batch_notional_cnh)} CNH`:'');
    }
    async function saveApprovalPolicy(enabled) {
      const payload={enabled,expected_revision:enabled?approvalReviewRevision:approvalPolicy.revision,confirm:enabled,
        operator:enabled?el('approval-operator').value.trim():'Local operator',
        reason:enabled?el('approval-reason').value.trim():'Switched back to manual approval in Trading operations.',
        max_batch_notional_cnh:enabled?el('approval-cap').value:approvalPolicy.max_batch_notional_cnh};
      await api('/api/v1/automation/paper-approval',{method:'PUT',body:JSON.stringify(payload)});
      await loadApprovalPolicy();
    }
    async function syncWorkspace(manual=false) {
      if(orderSyncBusy||el('order-action-dialog').open) return;
      orderSyncBusy=true; el('sync-orders-btn').disabled=true;
      try {
        await api('/api/v1/execution/interactive-brokers/orders/sync',{method:'POST'});
        await loadWorkspace();
        orderMessage('Broker snapshot updated. Missing orders retain their last known state until confirmed.');
      } catch(error) {
        orderMessage(`Gateway sync failed: ${error.message}`,true);
        await loadWorkspace().catch(()=>{});
        // Keep the last snapshot visible, but disable actions on a failed sync.
        el('gateway-order-table').querySelectorAll('button').forEach(b=>b.disabled=true);
      } finally { orderSyncBusy=false; el('sync-orders-btn').disabled=false; }
    }
    function openOrderAction(id,action) {
      const record=workspace.records.find(r=>r.local_order_id===id); if(!record) return;
      reviewedAction={record,action};
      el('order-action-title').textContent=`${action[0].toUpperCase()+action.slice(1)} ${record.order.symbol}`;
      el('order-action-summary').textContent=`Paper ${record.order.side.toUpperCase()} · ${record.order.quantity} shares · IB #${record.broker_order_id} · ${record.order_ref}. ${action==='resubmit'?'This sends a new order with the stored approved terms.':'The broker may fill an order before accepting a change.'}`;
      el('amend-fields').hidden=action!=='amend'; el('amend-note').hidden=action!=='amend';
      el('amend-quantity').required=action==='amend'; el('amend-price').required=action==='amend';
      el('amend-quantity').value=record.order.quantity; el('amend-quantity').max=record.order.quantity;
      el('amend-price').value=record.broker_observation.limit_price||record.order.reference_price;
      el('order-reason').value=''; el('order-dialog-error').textContent='';
      el('confirm-order-action').textContent=`Confirm ${action}`;
      el('order-action-dialog').showModal();
    }
    el('close-order-dialog').addEventListener('click',()=>el('order-action-dialog').close());
    el('close-approval-dialog').addEventListener('click',()=>el('approval-mode-dialog').close());
    el('approval-mode-switch').addEventListener('click',async()=>{
      if(!approvalPolicy) return;
      if(approvalPolicy.enabled) {
        el('approval-mode-switch').disabled=true;
        try {await saveApprovalPolicy(false);} catch(error) {el('approval-policy-status').textContent=error.message;el('approval-mode-switch').disabled=false;}
      } else {
        approvalReviewRevision=approvalPolicy.revision;
        el('approval-cap').value=approvalPolicy.max_batch_notional_cnh;
        el('approval-policy-error').textContent=''; el('approval-reason').value='';
        el('approval-mode-dialog').showModal();
      }
    });
    el('approval-mode-form').addEventListener('submit',async(event)=>{
      event.preventDefault(); el('confirm-auto-approval').disabled=true;
      try {await saveApprovalPolicy(true);el('approval-mode-dialog').close();}
      catch(error) {el('approval-policy-error').textContent=error.message;}
      finally {el('confirm-auto-approval').disabled=false;}
    });
    el('order-action-form').addEventListener('submit',async(event)=>{
      event.preventDefault(); if(!reviewedAction) return;
      const {record,action}=reviewedAction;
      const payload={expected_token:record.review_token,confirm:true,operator:el('order-operator').value.trim(),reason:el('order-reason').value.trim()};
      if(action==='amend') { payload.quantity=Number(el('amend-quantity').value); payload.limit_price=el('amend-price').value; }
      el('confirm-order-action').disabled=true;
      try {
        const result=await api(`/api/v1/execution/interactive-brokers/orders/${encodeURIComponent(record.local_order_id)}/${action}`,{method:'POST',body:JSON.stringify(payload)});
        el('order-action-dialog').close();
        await loadWorkspace();
        orderMessage(result.message||'Resubmission processed. Sync to verify broker status.',result.outcome==='uncertain');
      } catch(error) { el('order-dialog-error').textContent=error.message; }
      finally { el('confirm-order-action').disabled=false; }
    });
    el('sync-orders-btn').addEventListener('click',()=>syncWorkspace(true));
    el('order-filter').addEventListener('change',renderWorkspace);
    el('order-date-start').value=orderDateAt(new Date());
    el('order-date-end').value=orderDateAt(new Date());
    ['order-date-filter','order-date-start','order-date-end'].forEach(id=>el(id).addEventListener('change',()=>{renderWorkspace();loadExecutionAnalytics().catch(()=>{});}));
    loadWorkspace().then(()=>syncWorkspace()).catch(error=>orderMessage(error.message,true));
    setInterval(()=>{if(!document.hidden) syncWorkspace();},15000);
"""
