"""Archive/restore controls; membership changes have no execution authority."""
HTML = '''<style>
.strategy-table-scroll{isolation:isolate;max-width:100%;overflow:auto}
.strategy-table-scroll:focus-visible{outline:3px solid #7695de;outline-offset:-3px}
.strategy-registry-table{border-collapse:separate;border-spacing:0;min-width:1380px}
.strategy-registry-table th{z-index:2}
.strategy-registry-table .strategy-name-cell{position:sticky;left:0;z-index:1;background:var(--panel,#fff);box-shadow:3px 0 5px #13243b12;width:320px;min-width:320px;max-width:320px;white-space:normal}
.strategy-registry-table th.strategy-name-cell{z-index:3;background:#f8fafc}
.strategy-name-cell .note,.strategy-name-cell .strategy-link{overflow-wrap:anywhere}
.strategy-name-cell .strategy-link{text-align:left}
.strategy-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.strategy-actions button:disabled{cursor:not-allowed;opacity:.55}
.strategy-actions .button,.strategy-actions button{font-size:12px}
.strategy-performance-note{padding:10px 14px;margin:0;border-bottom:1px solid var(--line)}
@media(max-width:700px){.strategy-registry-table .strategy-name-cell{width:180px;min-width:180px;max-width:180px}.strategy-name-cell .badge{margin-left:0}}
</style><dialog id="monitoring-dialog" style="width:min(480px,94vw);border:1px solid #ccd3dd;border-radius:9px;padding:22px">
<form id="monitoring-form"><h2 id="monitoring-title"></h2><p id="monitoring-description"></p>
<label>Operator <input id="monitoring-operator" required maxlength="100" autocomplete="name"></label>
<p><label>Reason <input id="monitoring-reason" required maxlength="1000" style="width:100%"></label></p>
<p id="monitoring-error" role="alert" style="color:#a33"></p>
<button type="button" id="monitoring-cancel">Cancel</button> <button type="submit" id="monitoring-submit">Save</button>
</form></dialog>'''

JS = '''
let monitoringRevision=0, monitoringChange=null;
/* Allocation readiness has two independent causes and they must not be shown as
   one. "Catching up" is transient: the calculation has not finished. "Not
   allocatable" is a policy state: the calculation is current but this strategy
   has no approved execution contract. Labelling the second as the first made a
   deliberate gate look like a stuck calculation. */
function allocationAction(item){
  if(item.allocation_ready){
    return `<a class="button sc-promote" data-strategy="${esc(item.strategy_id)}" href="/strategies?allocate=${encodeURIComponent(item.strategy_id)}">Promote / allocate</a>`;
  }
  if(item.calculation_status!=='Current'){
    return `<button disabled title="Wait for the complete calculation">Catching up</button>`;
  }
  const reason=item.allocation_unavailable_reason||'Allocation is not available for this strategy.';
  return `<button disabled title="${esc(reason)}">Not allocatable</button>`;
}
function monitoringActions(item){
  const key=esc(item.strategy_id);
  if(item.lifecycle==='monitored'){
    const allocation=allocationAction(item);
    return allocation+` <button data-monitoring-key="${key}" data-monitoring-action="archived" ${item.archive_blocker?'disabled':''} title="${esc(item.archive_blocker||'Pause calculations; retain the complete report')}">Archive</button>`;
  }
  return `<button data-monitoring-key="${key}" data-monitoring-action="monitored" ${item.can_restore?'':'disabled'} title="${item.can_restore?'Replay all missed sessions':'This historical artifact needs an executable strategy definition before it can be monitored'}">Restore to monitored</button>`;
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-monitoring-key]');
  if(!button||button.disabled)return;
  const restoring=button.dataset.monitoringAction==='monitored';
  monitoringChange={strategy_key:button.dataset.monitoringKey,lifecycle:button.dataset.monitoringAction,expected_revision:monitoringRevision,event_id:crypto.randomUUID()};
  document.getElementById('monitoring-title').textContent=restoring?'Restore to monitored':'Archive strategy';
  document.getElementById('monitoring-description').textContent=restoring?'All missed signals, scheduled trades and daily values will be replayed. Allocation becomes available after the complete report is current.':'Stop ongoing calculations and keep the last complete report. You can restore and catch up later.';
  document.getElementById('monitoring-error').textContent='';
  document.getElementById('monitoring-reason').value=restoring?'Resume monitoring and catch up':'Pause strategy monitoring';
  document.getElementById('monitoring-operator').value=localStorage.getItem('strategy-monitoring-operator')||'';
  document.getElementById('monitoring-dialog').showModal();
});
document.getElementById('monitoring-cancel').onclick=()=>document.getElementById('monitoring-dialog').close();
document.getElementById('monitoring-form').onsubmit=async event=>{
  event.preventDefault();const button=document.getElementById('monitoring-submit');button.disabled=true;
  try{
    const operator=document.getElementById('monitoring-operator').value.trim();
    const reason=document.getElementById('monitoring-reason').value.trim();
    const response=await fetch('/api/v1/portfolio/strategy-control/monitoring',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...monitoringChange,operator,reason})});
    const result=await response.json();if(!response.ok)throw new Error(result.detail||'Could not change monitoring');
    localStorage.setItem('strategy-monitoring-operator',operator);
    location.reload();
  }catch(error){document.getElementById('monitoring-error').textContent=error.message;}
  finally{button.disabled=false;}
};
'''
