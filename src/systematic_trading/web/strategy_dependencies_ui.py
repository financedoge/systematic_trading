"""Read-only dependency inventory and change-impact preview."""
HTML = '''<section id="strategy-dependencies" class="panel" style="margin-bottom:18px;padding:18px">
<h2>Dependencies and change impact</h2>
<p>Inspect the recipes, shared services and benchmarks a strategy needs before changing or retiring an older version.</p>
<label>Strategy <select id="dependency-key" aria-label="Dependency strategy"></select></label>
<label>Planned action <select id="dependency-action" aria-label="Dependency action">
<option value="modify">Modify existing version</option><option value="archive">Archive monitoring</option>
<option value="retire">Remove executable recipe</option></select></label>
<p id="dependency-status" role="status">Loading dependency contracts…</p>
<div id="dependency-detail"></div>
<p class="note">This preview changes nothing. Archiving keeps the recipe; required internal benchmarks and shared data publishers continue. New executable behavior requires a new version and an explicit dependency migration.</p>
</section>'''

JS = '''
let dependencyRequest=0;
async function loadStrategyDependencies(){
  const request=++dependencyRequest;
  const selector=document.getElementById('dependency-key');
  const action=document.getElementById('dependency-action').value;
  const status=document.getElementById('dependency-status');
  try{
    const response=await fetch('/api/v1/strategies/dependencies?'+new URLSearchParams({action,...(selector.value?{key:selector.value}:{})}),{cache:'no-store'});
    const data=await response.json();if(!response.ok)throw new Error(data.detail||'Dependency inspection unavailable');
    if(request!==dependencyRequest)return;
    const names=Object.fromEntries(data.strategies.map(row=>[row.strategy_key,row.name]));
    if(!selector.options.length){
      selector.innerHTML=data.strategies.map(row=>`<option value="${esc(row.strategy_key)}">${esc(row.name)}${row.monitored?' · monitored':''}</option>`).join('');
      selector.value=data.strategies.find(row=>row.monitored)?.strategy_key||data.strategies[0]?.strategy_key||'';
      if(selector.value)return loadStrategyDependencies();
    }
    const row=data.strategies.find(item=>item.strategy_key===selector.value);
    if(!row)throw new Error('Selected strategy is not registered');
    const impact=data.impact||{};
    const labels=keys=>keys.length?keys.map(key=>esc(names[key]||key)).join('<br>'):'None';
    status.textContent=row.contract_ok?'Executable contract verified. '+(impact.allowed?'This action has no dependency blocker.':'Change blocked by current dependencies or roles.'):'Dependency blocked: '+row.issue;
    const problems=[...(impact.blockers||[]),...Object.values(data.issues||{})];
    document.getElementById('dependency-detail').innerHTML=`
      ${problems.length?`<p role="alert">${[...new Set(problems)].map(esc).join('<br>')}</p>`:''}
      <table><tbody>
      <tr><th scope="row">Recipe parents</th><td>${labels(row.parents)}</td></tr>
      <tr><th scope="row">Required benchmarks</th><td>${labels(row.benchmarks)}</td></tr>
      <tr><th scope="row">Shared services</th><td>${row.services.map(service=>esc(service.name||service.id)).join('<br>')||'None'}</td></tr>
      <tr><th scope="row">Requires continuing monitoring</th><td>${labels(row.requires_monitoring)}</td></tr>
      <tr><th scope="row">Optional comparisons</th><td>${labels(row.optional_comparisons)}</td></tr>
      <tr><th scope="row">Protected strategies using this version</th><td>${labels(row.required_by)}</td></tr>
      <tr><th scope="row">Other consumers, including archived strategies</th><td>${labels(row.consumers)}</td></tr>
      </tbody></table><p>${esc(impact.message||'')}</p>`;
  }catch(error){if(request===dependencyRequest){status.textContent='Dependency inspection unavailable: '+error.message;document.getElementById('dependency-detail').innerHTML='';}}
}
document.getElementById('dependency-key').addEventListener('change',loadStrategyDependencies);
document.getElementById('dependency-action').addEventListener('change',loadStrategyDependencies);
loadStrategyDependencies();
'''
