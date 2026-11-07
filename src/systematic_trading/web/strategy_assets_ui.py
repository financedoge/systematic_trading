"""Asset discovery, source evidence, signal monitoring and retirement review."""
SIGNAL_HTML = '''<style>#signal-assets td{white-space:normal;overflow-wrap:anywhere;max-width:380px;vertical-align:top}#signal-assets th{text-align:left}#signal-assets td,#signal-assets th{padding:9px}#signal-assets table{width:100%}</style><section class="panel" id="signal-assets" style="padding:16px;margin-bottom:18px">
<h2>Tracked signal assets</h2><p>Every signal required by a tracked composite appears here automatically.
Calculation freshness and effectiveness are separate checks. <a href="/strategy-assets">Browse all time-series, models and signals</a>.</p>
<div style="overflow:auto;max-height:540px"><table><thead><tr><th>Signal</th><th>Tracking</th><th>Data / calculation</th><th>Effectiveness</th><th>Consumers</th><th>Evidence</th></tr></thead>
<tbody id="signal-asset-rows"><tr><td colspan="6">Loading signal assets…</td></tr></tbody></table></div></section>'''

SIGNAL_JS = '''
async function loadSignalAssets(){
 const host=document.getElementById('signal-asset-rows');if(!host)return;
 try{const response=await fetch('/api/v1/strategy-assets/signals',{cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(data.detail||'Monitoring unavailable');
 const priority=a=>a.evidence?.freshness==='stale'?0:a.evidence?.effectiveness==='decayed'?1:a.evidence?.effectiveness==='weakening'?2:a.evidence?.health?3:4;
 host.innerHTML=data.signals.sort((a,b)=>priority(a)-priority(b)||a.name.localeCompare(b.name)).map(a=>{const e=a.evidence||{};
 return `<tr><td><a href="/strategy-assets#${encodeURIComponent(a.asset_id)}">${esc(a.name)}</a></td>
 <td>Required</td><td>${esc(e.freshness||e.status||'unpublished')}${e.through?' · '+esc(e.through):''}</td>
 <td>${esc(e.effectiveness||'insufficient')}</td><td>${a.required_by.map(k=>esc(data.composite_names?.[k]||k)).join('<br>')}</td><td>${esc(e.reason||'No diagnostic published')}</td></tr>`;
 }).join('')||'<tr><td colspan="6">No signals currently required.</td></tr>';
 }catch(error){host.innerHTML=`<tr><td colspan="6">Signal monitoring unavailable: ${esc(error.message)}</td></tr>`;}
}
loadSignalAssets();setInterval(loadSignalAssets,30000);
'''

HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Strategy assets</title><style>
main{max-width:1500px;margin:24px auto;padding:0 22px}h2{font-size:19px;margin:0 0 10px}p{line-height:1.5}
.asset-layout{display:grid;grid-template-columns:minmax(310px,1fr) minmax(0,1.7fr);gap:20px;align-items:start}
.asset-pane{padding:20px}.asset-list{max-height:780px;overflow:auto}.asset-item{display:block;width:100%;text-align:left;padding:13px;border:0;border-bottom:1px solid #dfe6ee;background:white;cursor:pointer;color:inherit}
.asset-item[aria-current=true]{background:#edf3ff;border-left:4px solid #315bc2}.asset-item small{display:block;margin-top:5px;color:#65748a}
input,select,button{padding:8px}#asset-search{width:100%;box-sizing:border-box;margin-bottom:12px}.asset-detail{overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse}td,th{padding:9px;text-align:left;border-bottom:1px solid #dfe6ee;vertical-align:top;font-size:13px}
.muted{color:#65748a}.asset-badge{display:inline-block;background:#edf1f6;padding:4px 8px;border-radius:7px;font-size:12px;margin-right:6px}
.asset-warning{background:#fff5df;padding:12px;border-left:3px solid #b1842d}.asset-chart{width:100%;height:190px;background:#f7f9fc;border-radius:8px}
pre{white-space:pre-wrap;font-size:12px;max-height:320px;overflow:auto}.asset-tools{display:flex;gap:8px;flex-wrap:wrap}
@media(max-width:900px){.asset-layout{grid-template-columns:1fr}.asset-list{max-height:360px}}
</style></head><body><header></header><main>
<h1>Strategy assets</h1><p>Reusable time-series, model versions and signals. Tracked composites determine what stays maintained.
Search here before building a new input. <a href="/strategies#signal-assets">Signal monitoring</a> · <a href="/platform/market-data-audit">Raw data audits</a></p>
<p id="asset-meta" role="status">Loading governed catalog…</p><div class="asset-layout">
<section class="panel asset-pane"><label for="asset-search">Find an existing asset</label><input id="asset-search" type="search" placeholder="Name, provider, basis, version…">
<div id="asset-list" class="asset-list"></div></section><section class="panel asset-pane asset-detail" id="asset-detail">Select an asset.</section></div>
<dialog id="asset-retire-dialog"><form id="asset-retire-form"><h2>Retire unused asset version</h2><p id="asset-retire-review"></p>
<p><label>Operator <input id="asset-retire-operator" required maxlength="100"></label></p>
<p><label>Reason <input id="asset-retire-reason" required maxlength="1000"></label></p><p id="asset-retire-error" role="alert"></p>
<button type="button" id="asset-retire-cancel">Cancel</button> <button id="asset-retire-submit">Retire version</button></form></dialog>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let catalog=null,selected='',retirement=null,seriesRequest=0;
const pct=v=>v==null?'Unavailable':(v*100).toFixed(3)+'%';
async function get(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d;}
function renderList(){const q=document.getElementById('asset-search').value.toLowerCase();
 document.getElementById('asset-list').innerHTML=catalog.assets.filter(a=>JSON.stringify(a).toLowerCase().includes(q)).map(a=>
 `<button class="asset-item" data-key="${esc(a.asset_id)}" aria-current="${a.asset_id===selected}"><strong>${esc(a.name)}</strong><small>${esc(a.contract.kind)} · ${esc(a.tracking)} · ${esc(a.lifecycle)}</small></button>`).join('');
 document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>{location.hash=b.dataset.key;showAsset(b.dataset.key);});}
function showAsset(key){selected=key;renderList();const a=catalog.assets.find(x=>x.asset_id===key);if(!a)return;
 const e=a.evidence||{},h=e.health||{};const labels=xs=>xs.length?xs.map(k=>esc(catalog.composite_names?.[k]||k)).join('<br>'):'None';
 document.getElementById('asset-detail').innerHTML=`<h2>${esc(a.name)}</h2><p><span class="asset-badge">${esc(a.contract.kind)}</span><span class="asset-badge">${esc(a.tracking)}</span><span class="asset-badge">${esc(a.lifecycle)}</span></p>
 <p>${esc(a.asset_id)} · ${esc(a.contract.cadence)}</p><p class="asset-warning">${esc(e.reason||'No diagnostic available.')}</p>
 ${h.universe_size?`<p><strong>${h.current_long} / ${h.universe_size}</strong> next-open long intents · through ${esc(e.through)} · ${esc(e.freshness)}<br>${h.completed_decisions} completed prospective labels; signed next-open return mean ${pct(h.directional_forward_mean)} (gross diagnostic).</p>`:''}
 <table><tbody><tr><th>Required by</th><td>${labels(a.required_by)}</td></tr><tr><th>All retained consumers</th><td>${labels(a.consumers)}</td></tr>
 <tr><th>Input assets</th><td>${Object.keys(a.contract.inputs).map(k=>`<a href="#${encodeURIComponent(k)}">${esc(k)}</a>`).join('<br>')||'None'}</td></tr>
 <tr><th>Price / activity basis</th><td>${esc(a.contract.basis)}</td></tr><tr><th>Availability</th><td>${esc(a.contract.availability)}</td></tr>
 <tr><th>Missing data</th><td>${esc(a.contract.missing)}</td></tr></tbody></table>
 ${e.symbols?`<h3>Published signal history</h3><label>ETF <select id="asset-symbol">${e.symbols.map(s=>`<option>${esc(s)}</option>`).join('')}</select></label><div id="asset-series">Loading…</div>`:''}
 <p>${a.limitations.map(esc).join('<br>')}</p><div class="asset-tools">${a.inspection_url?`<a href="${a.inspection_url}">Inspect source audits</a>`:''}<button id="asset-retire-preview">Check retirement impact</button></div>
 <p id="asset-impact" role="status"></p><details><summary>Version, source and calculation evidence</summary><pre>${esc(JSON.stringify({contract:a.contract,sha256:a.sha256,evidence:e},null,2))}</pre></details>`;
 document.getElementById('asset-retire-preview').onclick=previewRetirement;
 if(e.symbols){document.getElementById('asset-symbol').onchange=loadSeries;loadSeries();}}
function chart(rows,fields,title){const w=700,h=160,pad=20;const values=rows.flatMap(r=>fields.map(f=>Number(r[f]))).filter(Number.isFinite);if(!values.length)return '';
 const low=Math.min(...values),high=Math.max(...values),range=high-low||1;const colors=['#315bc2','#bc7137'];
 return `<p>${esc(title)}</p><svg class="asset-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}">${fields.map((f,j)=>`<path fill="none" stroke="${colors[j]}" stroke-width="1.6" d="${rows.map((r,i)=>`${i?'L':'M'}${pad+i*(w-2*pad)/Math.max(1,rows.length-1)},${h-pad-(Number(r[f])-low)/range*(h-2*pad)}`).join(' ')}"/>`).join('')}<text x="20" y="14" fill="#65748a" font-size="11">${high.toFixed(3)}</text><text x="20" y="157" fill="#65748a" font-size="11">${low.toFixed(3)}</text></svg>`;}
async function loadSeries(){const request=++seriesRequest,key=selected,symbol=document.getElementById('asset-symbol').value;
 try{const d=await get('/api/v1/strategy-assets/'+encodeURIComponent(key)+'/series?'+new URLSearchParams({symbol,limit:'260'}));if(request!==seriesRequest||key!==selected)return;
 const latest=d.rows.at(-1),health=catalog.assets.find(a=>a.asset_id===key)?.evidence?.health;
 const perSymbol=health?.per_symbol?.find(s=>s.symbol===symbol);
 document.getElementById('asset-series').innerHTML=d.rows.length?`<p><strong>${esc(symbol)}</strong> · next-open intent: ${latest.desired?'Long':'Cash'} · virtual position: ${latest.held?'Long':'Cash'} · close-tested stop: ${latest.stop==null?'Unavailable':Number(latest.stop).toFixed(3)}<br>Completed prospective directional return mean: ${pct(perSymbol?.directional_forward_mean)} (${perSymbol?.completed_decisions??0} daily labels).</p>`+chart(d.rows,['close'],'Audited adjusted close')+chart(d.rows,['fast_up','desired'],'Fast up score (blue); next-open long intent (orange)')+`<p class="muted">${esc(d.rows[0].date)} to ${esc(d.rows.at(-1).date)} · ${d.rows.length} published sessions. Scores are not calibrated probabilities.</p>`:'No observations.';
 }catch(e){if(request===seriesRequest&&key===selected)document.getElementById('asset-series').textContent=e.message;}}
async function previewRetirement(){try{retirement=await get('/api/v1/strategy-assets/'+encodeURIComponent(selected)+'/retirement');
 const text=retirement.allowed?'No retained consumers. Retirement preserves the definition and historical evidence.':'Blocked: '+retirement.blockers.join(' ')+' Consumers: '+[...retirement.consumers,...retirement.asset_consumers].join(', ');
 document.getElementById('asset-impact').textContent=text;if(retirement.allowed){document.getElementById('asset-retire-review').textContent=text;document.getElementById('asset-retire-error').textContent='';document.getElementById('asset-retire-dialog').showModal();}
 }catch(e){document.getElementById('asset-impact').textContent=e.message;}}
document.getElementById('asset-retire-cancel').onclick=()=>document.getElementById('asset-retire-dialog').close();
document.getElementById('asset-retire-form').onsubmit=async event=>{event.preventDefault();const button=document.getElementById('asset-retire-submit');button.disabled=true;
 try{await get('/api/v1/strategy-assets/'+encodeURIComponent(retirement.asset_id)+'/retire',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_sha256:retirement.review_sha256,expected_revision:retirement.asset_revision,event_id:crypto.randomUUID(),operator:document.getElementById('asset-retire-operator').value,reason:document.getElementById('asset-retire-reason').value})});location.reload();}
 catch(e){document.getElementById('asset-retire-error').textContent=e.message;}finally{button.disabled=false;}};
document.getElementById('asset-search').oninput=renderList;
window.addEventListener('hashchange',()=>{if(catalog)showAsset(decodeURIComponent(location.hash.slice(1)));});
get('/api/v1/strategy-assets').then(d=>{catalog=d;document.getElementById('asset-meta').textContent=`${d.assets.length} assets · ${d.plan.jobs.length} required · ${d.plan.monitored_signals.length} signals monitored`;
 showAsset(decodeURIComponent(location.hash.slice(1))||'broadtrend-signals-v1');}).catch(e=>document.getElementById('asset-meta').textContent=e.message);
</script></main></body></html>'''
