"""Archive/restore controls; membership changes have no execution authority."""
HTML = '''<style>.strategy-name-cell{min-width:280px;max-width:360px;white-space:normal}.strategy-name-cell .note{overflow-wrap:anywhere}.strategy-name-cell .strategy-link{text-align:left}.strategy-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.strategy-actions button:disabled{cursor:not-allowed;opacity:.55}.strategy-actions .button,.strategy-actions button{font-size:12px}</style><dialog id="monitoring-dialog" style="width:min(480px,94vw);border:1px solid #ccd3dd;border-radius:9px;padding:22px">
<form id="monitoring-form"><h2 id="monitoring-title"></h2><p id="monitoring-description"></p>
<label>Operator <input id="monitoring-operator" required maxlength="100" autocomplete="name"></label>
<p><label>Reason <input id="monitoring-reason" required maxlength="1000" style="width:100%"></label></p>
<p id="monitoring-error" role="alert" style="color:#a33"></p>
<button type="button" id="monitoring-cancel">Cancel</button> <button type="submit" id="monitoring-submit">Save</button>
</form></dialog>'''

JS = '''
let monitoringRevision=0, monitoringChange=null;
function monitoringActions(item){
  const key=esc(item.strategy_id);
  if(item.lifecycle==='monitored'){
    const allocation=item.allocation_ready?`<a class="button sc-promote" data-strategy="${key}" href="/strategies?allocate=${encodeURIComponent(item.strategy_id)}">Promote / allocate</a>`:`<button disabled title="Wait for the complete calculation">Catching up</button>`;
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
