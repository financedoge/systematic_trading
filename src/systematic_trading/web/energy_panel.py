"""Release-aware energy fundamentals inspection in Market Data."""

ENERGY_HTML = r'''
<section id="energy-panel" class="panel" data-market-view="energy" hidden>
 <div class="panel-head"><h2>Energy Data</h2><span id="energy-status" aria-live="polite">Loading recorder</span></div>
 <p class="note">EIA physical inventories, supply and demand context. Each release retains its own values and capture time. A reported change is not a surprise relative to market expectations. Weekly changes below are differences of displayed levels; EIA's reported changes may differ because of rounding.</p>
 <form id="energy-filters" class="filters"><label>Report<select id="energy-product" aria-label="Energy report"></select></label><label>Captured version<select id="energy-capture" aria-label="Energy captured version"></select></label><button type="submit" class="primary">View release</button><button id="energy-refresh" type="button">Refresh coverage</button></form>
 <p id="energy-warning" class="note" style="background:#fff8db;color:#77520a;border-left:3px solid #d5a52a;padding:12px" hidden></p>
 <p id="energy-dates" class="note"></p><div id="energy-records" class="table-wrap"></div>
 <details id="energy-reference" hidden><summary>Crude inventory history as recorded in this release</summary><p class="note">This rolling history may contain revisions. All rows became available to this app at the selected capture time. It cannot be used for earlier decisions.</p><div id="energy-reference-rows" class="table-wrap"></div></details>
 <p id="energy-limitations" class="note"></p>
 <details class="market-debug-only"><summary>Recorder evidence</summary><pre id="energy-evidence"></pre></details>
</section>
<script>
(()=>{
 const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');let catalog=null,sequence=0;
 const num=x=>x===undefined?'—':x===null?'Missing':Number(x).toLocaleString(undefined,{maximumFractionDigits:3});
 async function get(url){const response=await fetch(url);if(!response.ok)throw new Error(response.status===409?'Publication changed; refresh coverage.':'Energy publication is unavailable or failed verification.');return response.json()}
 function choices(){const p=catalog.products.find(p=>p.id===$('energy-product').value);$('energy-capture').innerHTML=p.captures.slice().reverse().map(c=>`<option value="${esc(c.batch)}">${esc(c.source_release_at)} · captured ${esc(c.first_seen_at)}</option>`).join('');return p}
 function show(data,p){$('energy-dates').textContent=`Week ending ${data.report_date} · Source release ${data.source_release_at} · Available to app ${data.first_seen_at}`;
  $('energy-records').innerHTML='<table><thead><tr><th>Indicator</th><th>Value</th><th>Units</th><th>Prior week</th><th>Weekly change</th><th>4-week average</th><th>Revision / reclassification</th></tr></thead><tbody>'+data.metrics.map(m=>`<tr><td>${esc(m.name)}</td><td>${num(m.value)}</td><td>${esc(m.units)}</td><td>${num(m.previous_value)}</td><td>${num(m.change)}</td><td>${num(m.four_week_average)}</td><td>${esc(m.revision_flag??m.source_row?.revision_flag?.[0]??'Not supplied')} / ${esc(m.reclassification_flag??m.source_row?.reclassification_flag?.[0]??'Not supplied')}</td></tr>`).join('')+'</tbody></table>';
  const rows=data.reference_history?.rows||[];$('energy-reference').hidden=!rows.length;$('energy-reference-rows').innerHTML='<table><thead><tr><th>Week ending</th><th>Million barrels</th></tr></thead><tbody>'+rows.slice().reverse().map(r=>`<tr><td>${esc(r.date)}</td><td>${num(r.value)}</td></tr>`).join('')+'</tbody></table>';
  $('energy-evidence').textContent=JSON.stringify({publication:p.pin,capture:$('energy-capture').value,policy:data.policy,sources:data.receipt.sources},null,2)
 }
 async function load(reset=false){const id=++sequence;if(reset||!catalog){const next=await get('/api/v1/market-data/energy/catalog');if(id!==sequence)return;catalog=next;const old=$('energy-product').value;$('energy-product').innerHTML=catalog.products.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');if(old)$('energy-product').value=old;choices()}
  const p=catalog.products.find(p=>p.id===$('energy-product').value);$('energy-status').style.color='';$('energy-limitations').innerHTML=catalog.limitations.map(esc).join('<br>');
  const messages=[catalog.availability];if(p.stale)messages.push('No current release is available; inspect dates before use.');if(p.recorder.error)messages.push('Recorder check failed: '+p.recorder.error);
  $('energy-warning').textContent=messages.join(' ');$('energy-warning').hidden=false;$('energy-warning').style.borderColor=p.recorder.error?'#c2413b':'#d5a52a';
  if(!p.pin){$('energy-status').textContent='Awaiting first publication';$('energy-records').textContent='';$('energy-dates').textContent='';$('energy-reference').hidden=true;return}
  const data=await get('/api/v1/market-data/energy/history?'+new URLSearchParams({product:p.id,capture:$('energy-capture').value,catalog_batch:p.pin.batch}));if(id!==sequence)return;show(data,p);$('energy-status').textContent=`${p.captures.length} captured version(s) · ${data.metrics.length} indicators`;
 }
 function fail(e){$('energy-status').textContent=e.message;$('energy-status').style.color='#b42318';$('energy-records').textContent='';$('energy-dates').textContent='';$('energy-reference').hidden=true}
 $('energy-product').onchange=()=>{choices();load().catch(fail)};$('energy-filters').onsubmit=e=>{e.preventDefault();load().catch(fail)};$('energy-refresh').onclick=()=>load(true).catch(fail);window.MarketHistory.register('energy',()=>load(true).catch(fail));
})();
</script>
'''
