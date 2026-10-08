"""Shared allocation editor on Strategies and Trading."""

def with_strategy_controls(html, page):
    if page not in ('trading','strategies') or 'id="strategy-control-script"' in html:
        return html
    return html.replace('</body>', '<style>'+CSS+'</style><script id="strategy-control-script">'+JS+'</script></body>',1)


CSS = """
#strategy-controls{padding:20px;margin-bottom:22px;line-height:1.5}
#strategy-controls h2{margin:0;font-size:19px}#strategy-controls h3{font-size:15px}
.sc-top{display:flex;justify-content:space-between;align-items:center;gap:18px}
.sc-note{font-size:12px;color:#65748a}.sc-tag{display:inline-block;padding:4px 9px;border-radius:20px;background:#e5f2eb;color:#215940;font-size:11px}
#strategy-controls button{padding:8px 12px;border:1px solid #cdd8e5;background:white;color:#244369;cursor:pointer}
#strategy-controls .sc-primary{background:#255bce;color:white;border-color:#255bce}
#strategy-controls button:disabled{opacity:.45;cursor:default}
.sc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:16px 0}
#strategy-controls label{display:flex;flex-direction:column;gap:5px;font-size:12px}
#strategy-controls input,#strategy-controls select,#strategy-controls textarea{padding:9px;border:1px solid #cbd5e1;border-radius:5px;background:white;min-width:0;box-sizing:border-box;width:100%;color:#1b2b42}
#strategy-controls input[type=checkbox]{width:auto}.sc-check{flex-direction:row!important;align-items:flex-start}
#strategy-controls table{width:100%;border-collapse:collapse;table-layout:auto;margin:12px 0}
#strategy-controls td,#strategy-controls th{text-align:left;padding:10px;border-bottom:1px solid #e5eaf1;font-size:12px;white-space:normal}
#strategy-controls td.sc-num{text-align:right;font-variant-numeric:tabular-nums}
.sc-scroll{overflow-x:auto}.sc-error{color:#a83232;background:#fff1ee;padding:10px;border-radius:5px;white-space:pre-line}
.sc-field-error{color:#a83232}#strategy-controls [aria-invalid=true]{border-color:#a83232}
.sc-warning{color:#79520b;background:#fff7db;border:1px solid #e9cc76;padding:10px;border-radius:5px;white-space:pre-line}
.sc-review{border:1px solid #b8ccec;border-radius:8px;padding:16px;background:#f7faff;margin-top:18px}
#sc-message:empty{display:none}.sc-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
#strategy-controls [hidden]{display:none!important}
"""

JS = r"""
(() => {
  if(!['/operator','/strategies'].includes(location.pathname))return;
  const root=document.createElement('section');root.id='strategy-controls';root.className='panel';
  document.querySelector('main')?.prepend(root);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct=v=>(Number(v)*100).toFixed(2)+'%';
  const money=v=>v==null?'Unavailable':Number(v).toLocaleString(undefined,{maximumFractionDigits:2,minimumFractionDigits:2});
  const stamp=v=>v?new Date(v).toLocaleString():'Date not established';
  const fieldLabels={operator:'Operator',reason:'Reason',effective_close:'Handover date',max_batch_notional_cnh:'Maximum net order batch',weight:'Capital weight',allocations:'Strategy allocation',sota_key:'SOTA designation'};
  const requiredText=key=>key==='operator'?'Enter your name in Operator.':'Enter a reason for this change.';
  const errorText=detail=>Array.isArray(detail)?detail.map(issue=>{
    const key=issue.loc?.at(-1);
    if(['operator','reason'].includes(key)&&['missing','string_too_short'].includes(issue.type))return requiredText(key);
    return (fieldLabels[key]?fieldLabels[key]+': ':'')+(issue.msg||'Check the entered value.').replace(/^Value error, /,'');
  }).join('\n'):typeof detail==='string'?detail:'The request could not be completed. Please try again.';
  const call=async(path='',body)=>{const r=await fetch('/api/v1/portfolio/strategy-control'+path,
    body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
    const d=await r.json();if(!r.ok){const error=Error(errorText(d.detail));error.detail=d.detail;throw error}return d};
  let data, preview, change, editorRevision=0;
  function invalidatePreview(){editorRevision++;preview=null;change=null}
  const name=k=>(data?.candidates.find(c=>c.strategy_key===k)?.name||k).replace(/^SOTA:\s*/, '');
  const message=t=>{root.querySelector('#sc-message').textContent=t};
  function fieldError(id,text){
    if(!id)return null;
    const field=root.querySelector('#'+id),hint=root.querySelector('#'+id+'-error');
    if(!field)return null;
    field.setAttribute('aria-invalid',text?'true':'false');
    if(hint){hint.textContent=text;hint.hidden=!text}
    return field;
  }
  function validateRequired(prefix='sc'){
    const errors=[];
    for(const key of ['operator','reason']){
      const field=root.querySelector('#'+prefix+'-'+key),text=field.value.trim()?'':requiredText(key);
      fieldError(prefix+'-'+key,text);if(text)errors.push({field,text});
    }
    if(errors.length){message(errors.map(e=>e.text).join('\n'));errors[0].field.focus();return false}
    return true;
  }
  function showError(error,prefix='sc'){
    message(error.message);let first;
    for(const issue of Array.isArray(error.detail)?error.detail:[]){
      const key=issue.loc?.at(-1);
      if(['operator','reason'].includes(key)){
        const field=fieldError(prefix+'-'+key,errorText([issue]));if(!first)first=field;
      }
    }
    first?.focus();
  }
  async function load(){
    invalidatePreview();
    root.innerHTML='<h2>Trading allocation</h2><p class="sc-note">Loading strategy roles and allocation history…</p>';
    try{data=await call();render();const key=new URLSearchParams(location.search).get('allocate');if(data.candidates.some(c=>c.strategy_key===key))edit([{strategy_key:key,weight:'1'}],'both',key)}catch(e){root.innerHTML='<h2>Trading allocation unavailable</h2><p class="sc-error">'+esc(e.message)+'</p>'}
  }
  function render(){
    const s=data.state,a=s.active;
    if(!a || !Array.isArray(a.allocations))throw Error('Allocation state is unavailable. Refresh before making a change.');
    root.innerHTML=`<div class="sc-top"><div><span class="sc-tag">PAPER PORTFOLIO</span><h2>Trading allocation</h2>
      <div class="sc-note">SOTA: ${esc(name(s.sota_key))}</div></div><button id="sc-edit" class="sc-primary">Change strategies & weights</button></div>
      <div class="sc-scroll"><table><thead><tr><th>Trading strategy</th><th>Capital target</th><th>Ledger share</th><th>Effective from</th><th>Report</th></tr></thead><tbody>
      ${a.allocations.map(r=>`<tr><td>${esc(name(r.strategy_key))}</td><td>${pct(r.weight)}</td><td>${data.capital?.weights[r.strategy_key]!=null?pct(data.capital.weights[r.strategy_key]):'Not yet recorded'}</td><td>${a.activated_at?esc(stamp(a.activated_at)):'Legacy · date not established'}</td><td><a href="/api/v1/strategies/${encodeURIComponent(r.strategy_key)}/report">View model & evidence</a></td></tr>`).join('')}
      <tr><td>Unassigned reserve cash</td><td>${pct(1-a.allocations.reduce((v,r)=>v+Number(r.weight),0))}</td><td>${data.capital?.weights['portfolio-reserve']!=null?pct(data.capital.weights['portfolio-reserve']):'—'}</td><td colspan="2">Strategy cash is retained in addition to this reserve.</td></tr></tbody></table></div>
      <p class="sc-note">${esc(data.rules.capital_rebalance)} ${data.capital?'Ledger marked on '+esc(data.capital.as_of)+'. ':''}${esc(data.rules.routing)}</p>
      ${s.pending?`<div class="sc-review"><strong>Approved change pending</strong><p>Handover after ${esc(s.pending.change.effective_close)} market close. ${esc(s.pending.change.reason)}</p><p class="${data.activation_blockers.length?'sc-error':'sc-note'}">${esc(data.pending_status||data.activation_blockers.join(' ')||'Activation will recheck the account, models and market data.')}</p><button id="sc-cancel">Cancel pending change</button></div>`:''}
      ${(data.routing_warnings||[]).length?`<p class="sc-warning">Orders waiting for routing readiness: ${esc(data.routing_warnings.join(' '))} Allocation preparation can continue.</p>`:''}
      <div id="sc-message" class="sc-error" role="alert"></div>
      <div id="sc-editor" hidden></div>
      <details id="sc-history"><summary>Strategy and allocation history · ${data.history.length} events</summary><p class="sc-note">${esc(data.rules.history)} Rollback creates a new dated change.</p>
      <div class="sc-scroll"><table><thead><tr><th>Recorded</th><th>Event</th><th>Effective close</th><th>First execution</th><th>Operator / reason</th><th></th></tr></thead><tbody>
      ${data.history.slice().reverse().map((e,i)=>`<tr><td>${esc(stamp(e.at))}</td><td>${esc(e.kind.replaceAll('_',' '))}</td><td>${esc(e.effective_close||e.state?.pending?.change?.effective_close||'—')}</td><td>${e.first_execution_at?esc(stamp(e.first_execution_at)):'—'}</td><td>${esc(e.operator)} · ${esc(e.reason)}</td><td>${e.kind==='allocation_activated'&&e.previous?.allocations?`<button data-rollback="${data.history.length-1-i}">Review rollback</button>`:''}</td></tr>`).join('')||'<tr><td colspan="6">No strategy change has been recorded.</td></tr>'}</tbody></table></div></details>
      <div id="sc-attribution"></div>`;
    root.querySelector('#sc-edit').onclick=()=>edit();
    root.querySelector('#sc-cancel')?.addEventListener('click',()=>cancelEditor());
    root.querySelectorAll('[data-rollback]').forEach(b=>b.onclick=()=>edit(data.history[Number(b.dataset.rollback)].previous.allocations));
    if(location.pathname==='/operator')loadAttribution();
  }
  function edit(allocations=data.state.active.allocations,mode='trading',sotaKey=data.state.sota_key){
    const editor=root.querySelector('#sc-editor');editor.hidden=false;invalidatePreview();message('');
    const weights=Object.fromEntries(allocations.map(r=>[r.strategy_key,Number(r.weight)*100]));
    editor.innerHTML=`<h3>Review a new configuration</h3><div class="sc-grid">
      <label>Change type<select id="sc-mode"><option value="trading">Trading allocation only</option><option value="both">Promote to SOTA & schedule trading</option><option value="sota">SOTA designation only</option></select></label>
      <label>SOTA designation<select id="sc-sota">${data.candidates.map(c=>`<option value="${esc(c.strategy_key)}">${esc(c.name)}</option>`).join('')}</select></label>
      <label>Handover after US session close<input id="sc-date" type="date" value="${esc(data.suggested_close)}"></label>
      <label>Maximum net order batch · CNH<input id="sc-cap" type="number" min="1" value="1000000"></label></div>
      <div class="sc-scroll"><table><thead><tr><th>Strategy</th><th>Capital %</th></tr></thead><tbody>${data.candidates.map(c=>`<tr><td>${esc(c.name)}</td><td><input data-weight="${esc(c.strategy_key)}" aria-label="Capital weight for ${esc(c.name)}" type="number" min="0" max="100" step="0.1" value="${weights[c.strategy_key]||0}"></td></tr>`).join('')}</tbody></table></div>
      <p class="sc-note" id="sc-total"></p><div class="sc-grid"><label>Operator (required)<input id="sc-operator" required maxlength="100" autocomplete="name" aria-describedby="sc-operator-error"><span id="sc-operator-error" class="sc-field-error" hidden></span></label><label>Reason and evidence reviewed (required)<textarea id="sc-reason" required maxlength="1000" rows="2" aria-describedby="sc-reason-help sc-reason-error" placeholder="Explain why you want to make this change."></textarea><span id="sc-reason-help" class="sc-note">Saved with the change in strategy history.</span><span id="sc-reason-error" class="sc-field-error" hidden></span></label></div>
      <p class="sc-note">After-close allocation preparation uses audited data and the last recorded account snapshot. IB can be offline. Orders need separate approval and fresh reconciliation before submission. A missed handover moves to the next available close without backdating history.</p>
      <div class="sc-actions"><button class="sc-primary" id="sc-preview">Preview change</button><button id="sc-dismiss">Close editor</button></div><div id="sc-preview-result"></div>`;
    root.querySelector('#sc-mode').value=mode;root.querySelector('#sc-sota').value=sotaKey;
    const sum=()=>{const total=[...root.querySelectorAll('[data-weight]')].reduce((v,r)=>v+Number(r.value),0);root.querySelector('#sc-total').textContent=`Assigned ${total.toFixed(2)}% · Reserve ${(100-total).toFixed(2)}%`};sum();
    editor.oninput=event=>{if(event.target.id==='sc-reviewed')return;sum();invalidatePreview();message('');fieldError(event.target.id,'');root.querySelector('#sc-confirm')?.setAttribute('disabled','')};
    root.querySelector('#sc-preview').onclick=previewEditor;
    root.querySelector('#sc-dismiss').onclick=()=>{invalidatePreview();editor.hidden=true};
    editor.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  async function previewEditor(){
    message('');invalidatePreview();const revision=editorRevision;root.querySelector('#sc-confirm')?.setAttribute('disabled','');
    if(!validateRequired())return;
    const button=root.querySelector('#sc-preview');button.disabled=true;
    try{
      const mode=root.querySelector('#sc-mode').value;
      const requestedChange={expected_revision:data.state.revision,event_id:crypto.randomUUID(),operator:root.querySelector('#sc-operator').value.trim(),
        reason:root.querySelector('#sc-reason').value.trim(),sota_key:mode==='trading'?null:root.querySelector('#sc-sota').value,
        allocations:mode==='sota'?null:[...root.querySelectorAll('[data-weight]')].filter(i=>Number(i.value)>0).map(i=>({strategy_key:i.dataset.weight,weight:String(Number(i.value)/100)})),
        effective_close:mode==='sota'?null:root.querySelector('#sc-date').value,max_batch_notional_cnh:root.querySelector('#sc-cap').value};
      const response=await call('/preview',requestedChange);
      if(revision!==editorRevision)return;
      change=requestedChange;preview=response;renderPreview();
    }catch(e){if(revision===editorRevision)showError(e)}finally{button.disabled=false}
  }
  function renderPreview(){
    if(!preview||!change)return;
    const reviewedChange=change;
    const p=preview,orders=p.proposal?.orders||[],targets=p.proposal?.targets||[];
    root.querySelector('#sc-preview-result').innerHTML=`<div class="sc-review"><h3>Review before approval</h3><p>${esc(p.effects)}</p>
      ${p.valuation_date?`<p>Paper account ${esc(p.account_id)} · Indicative orders using ${esc(p.valuation_date)} marks. Next trading session: ${esc(p.intended_trade_date)}.</p>`:''}
      <p class="sc-note">${esc(p.approval_policy)}</p>${p.blockers.length?`<p class="sc-error">Activation blockers: ${esc(p.blockers.join(' '))}</p>`:''}
      ${(p.routing_warnings||[]).length?`<p class="sc-warning">Order routing will wait: ${esc(p.routing_warnings.join(' '))} You can still schedule this allocation.</p>`:''}
      ${targets.length?`<div class="sc-scroll"><table><thead><tr><th>ETF</th><th>Asset name</th><th>Combined target</th><th>Net trade</th><th>Reference price</th></tr></thead><tbody>${[...new Set([...targets.map(t=>t.symbol),...orders.map(o=>o.symbol)])].sort().map(s=>{const t=targets.find(t=>t.symbol===s),o=orders.find(o=>o.symbol===s);return `<tr><td>${esc(s)}</td><td>${esc(AssetNames.name(s))}</td><td>${pct(t?.target_weight||0)}</td><td>${o?esc(o.side)+' '+o.quantity:'—'}</td><td>${o?money(o.reference_price):'—'}</td></tr>`}).join('')}</tbody></table></div>`:''}
      <details><summary>Evidence, model dates and limitations</summary>${Object.values(p.evidence).map(e=>`<h4><a href="${esc(e.report_url)}">${esc(e.name)}</a></h4><p>Through ${esc(e.through)} · Model fit ${esc(e.model_fit||'frozen model')} · ${esc(e.prospective_observations??0)} prospective observations since ${esc(e.prospective_start||'unknown')}</p><ul>${e.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`).join('')}</details>
      <p>Rollback allocation: ${p.rollback.map(r=>`${pct(r.weight)} ${esc(name(r.strategy_key))}`).join(' + ')}. Rollback requires a new reviewed change.</p>
      <label class="sc-check"><input id="sc-reviewed" type="checkbox">I reviewed the reports, prospective evidence, limitations, capital cap and rollback. I approve this paper configuration.</label>
      <div class="sc-actions"><button id="sc-confirm" class="sc-primary" disabled>${change.allocations?'Approve & schedule change':'Confirm SOTA designation'}</button></div></div>`;
    root.querySelector('#sc-reviewed').onchange=e=>{root.querySelector('#sc-confirm').disabled=!e.target.checked||!preview};
    root.querySelector('#sc-confirm').onclick=async()=>{if(preview!==p||change!==reviewedChange){message('Preview the changed configuration again.');return}const b=root.querySelector('#sc-confirm');b.disabled=true;try{await call('/schedule',{change:reviewedChange,review_token:p.review_token,evidence_reviewed:root.querySelector('#sc-reviewed').checked});await load()}catch(e){showError(e);b.disabled=false}};
  }
  function cancelEditor(){
    edit();root.querySelector('#sc-editor').innerHTML=`<h3>Cancel pending change</h3><div class="sc-grid"><label>Operator (required)<input id="sc-cancel-operator" required maxlength="100" aria-describedby="sc-cancel-operator-error"><span id="sc-cancel-operator-error" class="sc-field-error" hidden></span></label><label>Reason (required)<input id="sc-cancel-reason" required maxlength="1000" aria-describedby="sc-cancel-reason-error"><span id="sc-cancel-reason-error" class="sc-field-error" hidden></span></label></div><button id="sc-cancel-confirm">Confirm cancellation</button>`;
    root.querySelector('#sc-editor').oninput=event=>{message('');fieldError(event.target.id,'')};
    root.querySelector('#sc-cancel-confirm').onclick=async()=>{message('');if(!validateRequired('sc-cancel'))return;try{await call('/cancel',{expected_revision:data.state.revision,operator:root.querySelector('#sc-cancel-operator').value.trim(),reason:root.querySelector('#sc-cancel-reason').value.trim()});await load()}catch(e){showError(e,'sc-cancel')}};
  }
  document.addEventListener('click',event=>{
    const link=event.target.closest('.sc-promote');if(!link||!data)return;
    const key=link.dataset.strategy;if(!data.candidates.some(c=>c.strategy_key===key))return;
    event.preventDefault();edit([{strategy_key:key,weight:'1'}],'both',key);root.scrollIntoView({behavior:'smooth'});
  });
  async function loadAttribution(){
    try{const p=await call('/attribution');const target=root.querySelector('#sc-attribution');if(!target)return;
      target.innerHTML=`<details><summary>PnL by strategy and allocation period</summary><p class="sc-note">Marked handovers preserve gains earned before a switch. Account cost-basis PnL remains in the PnL section below.</p>
      <div class="sc-scroll"><table><thead><tr><th>Period</th><th>Strategy</th><th>Opening CNH</th><th>Capital transfers</th><th>Closing CNH</th><th>PnL CNH</th></tr></thead><tbody>${p.periods.flatMap(e=>e.sleeves.map(s=>`<tr><td>${esc(e.start)} – ${esc(e.end)}</td><td>${esc(s.name)}</td><td>${money(s.opening_nav_cnh)}</td><td>${money(s.capital_flow_cnh)}</td><td>${money(s.closing_nav_cnh)}</td><td>${money(s.pnl_cnh)}</td></tr>`)).join('')||'<tr><td colspan="6">No dated strategy handover yet. Earlier PnL remains Legacy / unknown.</td></tr>'}</tbody></table></div><p class="sc-note">${esc(p.warnings.join(' '))} ${p.account_reconciliation?.length?'Latest shared account residual: CNH '+money(p.account_reconciliation.at(-1).shared_residual_cnh)+'. ':''}${p.periods.filter(e=>Number(e.unclassified_cash_cnh)).map(e=>esc(e.start)+' shared unclassified cash: CNH '+money(e.unclassified_cash_cnh)).join('; ')}</p></details>`;
    }catch(e){const target=root.querySelector('#sc-attribution');if(target)target.textContent=e.message}
  }
  load();
  setInterval(()=>{if(data?.state.pending && root.querySelector('#sc-editor')?.hidden)load()},30000);
})();
"""
