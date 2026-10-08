"""Economic vintages are visible beside the existing market histories."""

ECONOMIC_HTML = r'''
<style>
 #economic-panel .note{padding:14px 22px;color:#64748b;font-size:12px;line-height:1.65}
 #economic-panel .economic-cards{display:flex;gap:28px;flex-wrap:wrap;padding:20px 22px}
 #economic-panel .economic-cards span{display:block;color:#718198;font-size:11px}
 #economic-panel .economic-cards strong{font-size:22px;color:#263b57}
 #economic-chart{padding:10px 22px}#economic-chart svg{width:100%;height:auto;max-height:330px}
 #economic-records{max-height:340px;overflow:auto}#economic-panel pre{white-space:pre-wrap;word-break:break-word;padding:16px 22px}
</style>
<section id="economic-panel" class="panel" data-market-view="economics" hidden>
 <div class="panel-head"><h2>Economic Data</h2><span id="economic-status" aria-live="polite">Loading recorder</span></div>
 <div class="note">Leading indicators, labor / inflation context and financial conditions, preserved in dated archives. Select a vintage to inspect its history. The monitored economic model uses its frozen eleven-series recipe; newly recorded financial indicators remain research inputs until separately tested.</div>
 <form id="economic-filters" class="filters">
  <label>Indicator<select id="economic-series" aria-label="Economic indicator"></select></label>
  <label>Archive as of<select id="economic-vintage" aria-label="Economic vintage"></select></label>
  <button type="submit" class="primary">View vintage</button><button type="button" id="economic-refresh">Refresh coverage</button>
  <button type="button" id="economic-export" disabled>Export vintage</button>
 </form>
 <div class="economic-cards" id="economic-metrics"></div>
 <div id="economic-summary" class="note" aria-live="polite"></div>
 <div id="economic-chart" role="img" aria-label="Selected economic vintage history"></div>
 <div id="economic-availability" class="note"></div>
 <details><summary>Recorded observations</summary><div id="economic-records" class="table-wrap"></div></details>
 <details><summary>Coverage and recorder status</summary><div id="economic-coverage" class="note"></div></details>
 <details><summary>Data sources still to add</summary><div id="economic-source-gaps" class="note"></div></details>
 <details><summary>Availability and research limits</summary><div id="economic-limits" class="note"></div></details>
 <details class="market-debug-only"><summary>Published evidence</summary><pre id="economic-evidence"></pre></details>
</section>
<script>
(() => {
 const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const num=x=>x===null?'Missing':Number(x).toLocaleString(undefined,{maximumFractionDigits:4});
 let catalog=null,snapshot=null,generation=0;
 async function get(url){const r=await fetch(url);if(!r.ok)throw new Error('Published economic data are unavailable. Last view cleared; retry after the recorder completes.');return r.json()}
 function clear(){snapshot=null;$('economic-export').disabled=true;for(const id of ['economic-metrics','economic-summary','economic-chart','economic-availability','economic-records','economic-evidence'])$(id).textContent=''}
 function fail(e){clear();$('economic-status').textContent=e.message}
 function vintages(){const id=$('economic-series').value,old=$('economic-vintage').value;
  const rows=catalog.snapshots.filter(r=>r.series===id).sort((a,b)=>b.vintage.localeCompare(a.vintage));
  $('economic-vintage').innerHTML=rows.map(r=>`<option value="${esc(r.vintage)}">${esc(r.vintage)}${r.usable?'':' · stale / missing'}</option>`).join('');
  if(rows.some(r=>r.vintage===old))$('economic-vintage').value=old;
 }
 async function load(){const token=++generation;clear();const id=$('economic-series').value,v=$('economic-vintage').value;
  if(!v){$('economic-status').textContent='Awaiting this indicator’s first published vintage';return}
  $('economic-status').textContent='Loading vintage';
  let d;try{d=await get('/api/v1/market-data/economics/history?'+new URLSearchParams({series:id,vintage:v}))}catch(e){if(token===generation)fail(e);return}if(token!==generation)return;
  snapshot=d;$('economic-export').disabled=false;$('economic-status').textContent=d.usable?'Published · availability limits apply':'Published · stale or missing endpoint';
  $('economic-metrics').innerHTML=`<div><span>Latest observation</span><strong>${num(d.observations.at(-1).value)}</strong></div><div><span>Observation period</span><strong>${esc(d.last)}</strong></div><div><span>Recorded observations</span><strong>${d.rows.toLocaleString()}</strong></div><div><span>Missing values</span><strong>${d.missing}</strong></div>`;
  $('economic-summary').innerHTML=esc(d.series.name+' · '+d.series.units+' · '+d.series.role)+(d.series.reference_url?' · <a target="_blank" rel="noopener" href="'+esc(d.series.reference_url)+'">Source and attribution</a>':'');
  $('economic-availability').textContent='Archive cutoff: '+d.archive_available_at.replace('T',' ')+' · First captured by this app: '+d.first_seen_at.replace('T',' ')+'. Observation dates describe the measured period, not the release date.';
  $('economic-records').innerHTML='<table><thead><tr><th>Observation period</th><th>Value</th></tr></thead><tbody>'+d.observations.slice(-200).reverse().map(r=>`<tr><td>${esc(r.date)}</td><td>${num(r.value)}</td></tr>`).join('')+'</tbody></table>';
  $('economic-evidence').textContent=JSON.stringify({catalog_batch:d.catalog_batch,receipt:d.receipt,policy:d.policy},null,2);
  chart(d);
 }
 function chart(d){const rows=d.observations,valid=rows.filter(r=>r.value!==null);if(!valid.length)return;
  const lo=Math.min(...valid.map(r=>Number(r.value))),hi=Math.max(...valid.map(r=>Number(r.value))),span=hi-lo||1;
  const x=i=>75+i*880/Math.max(1,rows.length-1),y=v=>250-(Number(v)-lo)*205/span;
  let path='',start=true;rows.forEach((r,i)=>{if(r.value===null){start=true;return}path+=(start?'M':'L')+x(i).toFixed(2)+','+y(r.value).toFixed(2);start=false});
  $('economic-chart').innerHTML=`<svg viewBox="0 0 1000 295" xmlns="http://www.w3.org/2000/svg"><line x1="75" x2="955" y1="250" y2="250" stroke="#dce3ed"/><line x1="75" x2="955" y1="45" y2="45" stroke="#edf0f5"/><path d="${path}" fill="none" stroke="#315bc2" stroke-width="1.8"/><g fill="#718198" font-size="12"><text x="4" y="49">${num(hi)}</text><text x="4" y="254">${num(lo)}</text><text x="75" y="280">${esc(rows[0].date)}</text><text x="955" y="280" text-anchor="end">${esc(rows.at(-1).date)}</text></g></svg>`;
 }
 async function refresh(){const token=++generation;clear();$('economic-status').textContent='Checking recorder coverage';let data;try{data=await get('/api/v1/market-data/economics/catalog')}catch(e){if(token===generation)fail(e);return}if(token!==generation)return;catalog=data;
  const old=$('economic-series').value;$('economic-series').innerHTML=catalog.config.series.map(s=>`<option value="${esc(s.id)}">${esc(s.name)} (${esc(s.id)})</option>`).join('');if(old)$('economic-series').value=old;
  $('economic-coverage').innerHTML=`${catalog.completed.toLocaleString()} of ${catalog.expected.toLocaleString()} planned indicator/vintage captures published through ${esc(catalog.through)}. Recorder ${catalog.recorder.enabled?'enabled':'disabled'}; owned by the application.<br>`+catalog.config.series.map(s=>`${esc(s.id)}: ${catalog.snapshots.filter(r=>r.series===s.id).length} vintages`).join(' · ')+catalog.recorder.failures.map(r=>`<br>${esc(r.key)}: ${esc(r.status)} — ${esc(r.message||'Retry pending')}`).join('');
  $('economic-limits').innerHTML=catalog.limitations.map(esc).join('<br>');
  $('economic-source-gaps').innerHTML=(catalog.config.source_gaps||[]).map(s=>`<p><strong>${esc(s.name)}</strong> · ${esc(s.status)}<br>${esc(s.detail)}</p>`).join('')||'No additional source requirements recorded.';
  vintages();await load();
 }
 $('economic-series').onchange=()=>{++generation;clear();$('economic-vintage').innerHTML='';vintages();load().catch(fail)};
 $('economic-vintage').onchange=()=>load().catch(fail);
 $('economic-filters').onsubmit=e=>{e.preventDefault();load().catch(fail)};
 $('economic-refresh').onclick=()=>refresh().catch(fail);
 $('economic-export').onclick=()=>{if(!snapshot)return;const blob=new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=snapshot.series.id+'-'+snapshot.vintage+'.json';a.click();URL.revokeObjectURL(url)};
 window.MarketHistory.register('economics',()=>refresh().catch(fail));
})();
</script>
'''
