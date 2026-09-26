"""Governed history and source comparison view inside Market Data."""

GOVERNED_HTML = r'''
<style>
 #governed-panel[hidden]{display:none}
 #governed-panel .filters{flex-wrap:wrap}
 #governed-panel .note{padding:12px 16px;color:#657083;line-height:1.55}
 #governed-panel .metrics{display:flex;flex-wrap:wrap;gap:24px;padding:12px 18px;background:#f7f9fc}
 #governed-panel .metrics strong{font-size:21px;display:block;color:#1d2433}
 #governed-panel svg{width:100%;height:280px}
 #governed-panel .chart{padding:10px 18px}
 #governed-panel .chart svg{touch-action:none;user-select:none;cursor:crosshair}
 #governed-panel[data-chart-mode="pan"] .chart svg{cursor:grab}
 #governed-panel .chart.dragging svg{cursor:grabbing}
 #governed-panel .chart:focus-visible{outline:2px solid #2456a6;outline-offset:-2px}
 #governed-panel .chart-tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 18px}
 #governed-panel .chart-tools button[aria-pressed="true"]{background:#2456a6;color:white;border-color:#2456a6}
 #governed-window{font-variant-numeric:tabular-nums;margin-left:8px}
 #governed-panel pre{white-space:pre-wrap;word-break:break-word;max-height:400px;overflow:auto;font-size:12px}
 #governed-panel details{margin:8px 16px}
 #governed-panel summary{cursor:pointer}
 #governed-records{max-height:450px;overflow:auto}
 #governed-catalog-table{max-height:360px;overflow:auto}
 #governed-sources{max-width:650px}
 #governed-source{max-width:430px}
 #governed-message{white-space:pre-wrap}
 #governed-title{margin-bottom:6px}
</style>
<section id="governed-panel" class="panel" hidden>
 <div class="panel-head"><h2>Audited Series</h2><span id="governed-status">Loading catalog</span></div>
 <div class="note">One dated history per symbol, with explicit price bases and source lineage. Raw prices are reconstructed from reported splits; dividend-adjusted prices follow the provider’s back-adjustment convention. Neither is certified exchange tape. Missing observations remain missing.</div>
 <form id="governed-filters" class="filters">
  <label>Underlying<input id="governed-symbol" aria-label="Governed symbol" list="governed-symbols" value="AAPL"></label><datalist id="governed-symbols"></datalist>
  <label>Price basis<select id="governed-basis" aria-label="Governed price basis"><option value="adjusted">Dividend + split adjusted</option><option value="raw">Raw — reconstructed</option></select></label>
  <label>From<input type="date" id="governed-start"></label><label>Through<input type="date" id="governed-end"></label>
  <button class="primary" type="submit">View audited history</button><button type="button" id="governed-export" disabled>Download series JSON</button><button type="button" id="governed-catalog-export">Download audit catalog</button>
 </form>
 <details><summary id="governed-catalog-summary">All underlyings and unresolved work</summary>
  <label>Coverage filter <select id="governed-catalog-filter" aria-label="Governed coverage filter"><option value="all">All underlyings</option><option value="unavailable">No governed history</option><option value="raw">Raw coverage incomplete</option><option value="gaps">Internal gaps</option><option value="identity">Historical identity review</option><option value="prelisting">Earlier identity era quarantined</option><option value="stale">Stale / delisted endpoint</option><option value="conflicts">Source price disagreements</option></select></label>
  <span id="governed-catalog-count"></span><button type="button" id="governed-catalog-next">Next 100</button><div id="governed-catalog-table" class="table-wrap"></div>
 </details>
 <div id="governed-metrics" class="metrics"></div>
 <div class="note"><strong id="governed-title"></strong><div id="governed-message"></div><small id="governed-batch"></small></div>
 <div class="chart-tools" role="group" aria-label="Chart navigation">
  <button type="button" id="governed-zoom" aria-pressed="true">Zoom</button>
  <button type="button" id="governed-pan" aria-pressed="false">Pan</button>
  <button type="button" id="governed-reset">Full history</button>
  <span id="governed-window" aria-live="polite"></span>
 </div>
 <div class="note" id="governed-chart-help">Drag across a chart to zoom into a period. Choose Pan or hold Shift while dragging to move through time. Both charts stay aligned. Full history resets the range. With a chart focused, use ← / → to pan, Home to reset, or Esc to cancel a drag.</div>
 <div id="governed-chart" class="chart" tabindex="0" role="group" aria-label="Governed price chart" aria-describedby="governed-chart-help"></div>
 <form id="governed-comparison" class="filters">
  <label>Compare source<select id="governed-source" aria-label="Governed comparison source"><option value="">None</option></select></label>
  <label>Source column<select id="governed-column" aria-label="Source comparison price basis"><option value="rebased_adjusted_close">Adjusted close, aligned to governed scale</option><option value="source_adjusted_close">Adjusted close, original source scale</option><option value="source_close">Close, original source convention</option><option value="source_volume">Volume, original source units</option></select></label>
  <button type="submit">Compare</button><button type="button" id="governed-source-download">Inspect source file</button>
 </form>
 <div id="governed-comparison-note" class="note"></div><div id="governed-source-chart" class="chart" tabindex="0" role="group" aria-label="Source comparison chart" aria-describedby="governed-chart-help"></div>
 <details open><summary>Source agreement and join decisions</summary><div id="governed-overlaps" class="table-wrap"></div></details>
 <details><summary>Gaps, identities and complete audit</summary><pre id="governed-audit"></pre></details>
 <details><summary>Dividend and split evidence</summary><button type="button" id="governed-actions-load">Load corporate actions</button><pre id="governed-actions"></pre></details>
 <details><summary>Daily rows and full lineage (latest 200 in selected range)</summary><div id="governed-records" class="table-wrap"></div></details>
</section>
<script>
(() => {
 const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const fmt=x=>Number(x||0).toLocaleString(),num=x=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:5}),pct=x=>x==null?'—':(100*x).toFixed(3)+'%';
 const requested=[null,'governed','history'].includes(new URL(location.href).searchParams.get('view'));
 let batch=null,catalog=[],audit=null,page=null,generation=0,loadedSymbol=null,catalogOffset=0;
 const DAY=86400000,chartIds=['governed-chart','governed-source-chart'];
 let viewport=null,extent=null,chartMode='zoom',gesture=null,chartFrame=null;
 const dateText=t=>new Date(t).toISOString().slice(0,10),clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
 function boundedWindow(range,bounds){
  if(!bounds)return null;
  const width=Math.min(Math.max(0,range[1]-range[0]),bounds[1]-bounds[0]);
  const start=clamp(range[0],bounds[0],bounds[1]-width);return [start,start+width];
 }
 function fullExtent(){
  const dates=[...(page?.rows||[]),...(page?.comparisons||[])].map(r=>Date.parse(r.trade_date)).filter(Number.isFinite);
  return dates.length?[Math.min(...dates),Math.max(...dates)]:null;
 }
 function visibleRows(rows){const range=viewport||extent;return range?rows.filter(r=>{const t=Date.parse(r.trade_date);return t>=range[0]&&t<=range[1]}):[]}
 function setWindow(range){
  viewport=range?boundedWindow(range,extent):null;
  if(viewport&&viewport[0]===extent[0]&&viewport[1]===extent[1])viewport=null;
 }
 function syncWindow(){
  const range=viewport||extent;
  $('governed-start').value=viewport?dateText(viewport[0]):'';$('governed-end').value=viewport?dateText(viewport[1]):'';
  $('governed-window').textContent=range?`${viewport?'Selected period':'Full history'} · ${dateText(range[0])} – ${dateText(range[1])}`:'No dated history';
  ['governed-zoom','governed-pan','governed-reset'].forEach(id=>$(id).disabled=!extent);
 }
 function setMode(mode){
  cancelGesture();chartMode=mode;$('governed-panel').dataset.chartMode=mode;
  $('governed-zoom').setAttribute('aria-pressed',String(mode==='zoom'));$('governed-pan').setAttribute('aria-pressed',String(mode==='pan'));
 }
 function resetWindow(){cancelGesture();setWindow(null);renderCharts();renderRecords()}
 function applyDateWindow(){
  const start=$('governed-start').value,end=$('governed-end').value;
  if(!extent)return;
  const range=[start?Date.parse(start):extent[0],end?Date.parse(end):extent[1]];
  if(!range.every(Number.isFinite)||range[0]>range[1])throw new Error('From must be on or before Through.');
  if(range[1]<extent[0]||range[0]>extent[1])throw new Error('Choose a period within the available history.');
  cancelGesture();setWindow([Math.max(range[0],extent[0]),Math.min(range[1],extent[1])]);render();
 }
 function plotPoint(host,event){
  const svg=host.querySelector('svg'),matrix=svg?.getScreenCTM();if(!matrix)return null;
  const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(matrix.inverse());
 }
 function cancelGesture(){
  if(!gesture)return;const g=gesture;gesture=null;
  if(chartFrame!==null){cancelAnimationFrame(chartFrame);chartFrame=null}
  if(g.mode==='pan')setWindow(g.before);
  g.host.classList.remove('dragging');if(g.host.hasPointerCapture(g.id))g.host.releasePointerCapture(g.id);
  renderCharts();renderRecords();
 }
 function bindChart(id){
  const host=$(id);
  host.onpointerdown=e=>{
   if(!extent||gesture||e.button!==0||e.isPrimary===false)return;
   const p=plotPoint(host,e);if(!p||p.x<65||p.x>965||p.y<20||p.y>230)return;
   e.preventDefault();host.focus({preventScroll:true});
   gesture={host,id:e.pointerId,start:p.x,clientStart:e.clientX,last:p.x,range:[...(viewport||extent)],before:viewport?[...viewport]:null,mode:e.shiftKey?'pan':chartMode};
   host.setPointerCapture(e.pointerId);if(gesture.mode==='pan')host.classList.add('dragging');
  };
  function move(e){
   const g=gesture;if(!g||g.host!==host||e.pointerId!==g.id)return;
   const p=plotPoint(host,e);if(!p)return;g.last=clamp(p.x,65,965);
   if(g.mode==='pan'){
    const delta=Math.round((g.start-g.last)/900*(g.range[1]-g.range[0])/DAY)*DAY;
    setWindow([g.range[0]+delta,g.range[1]+delta]);
    if(chartFrame===null)chartFrame=requestAnimationFrame(()=>{chartFrame=null;renderCharts(false)});
   }else{
    const selection=host.querySelector('.zoom-selection');selection?.setAttribute('x',Math.min(g.start,g.last));selection?.setAttribute('width',Math.abs(g.start-g.last));
   }
  }
  host.onpointermove=move;
  host.onpointerup=e=>{
   if(!gesture||gesture.host!==host||gesture.id!==e.pointerId)return;move(e);
   const g=gesture;gesture=null;if(chartFrame!==null){cancelAnimationFrame(chartFrame);chartFrame=null}
   if(g.mode==='zoom'&&Math.abs(e.clientX-g.clientStart)>=6){
    const time=x=>Math.round((g.range[0]+(x-65)/900*(g.range[1]-g.range[0]))/DAY)*DAY;
    const range=[time(Math.min(g.start,g.last)),time(Math.max(g.start,g.last))];
    if(range[1]>range[0])setWindow(range);
   }
   host.classList.remove('dragging');if(host.hasPointerCapture(g.id))host.releasePointerCapture(g.id);renderCharts();renderRecords();
  };
  host.onpointercancel=e=>{if(gesture?.id===e.pointerId)cancelGesture()};
  host.onlostpointercapture=e=>{if(gesture?.id===e.pointerId)cancelGesture()};
  host.onkeydown=e=>{
   if(e.key==='Escape'){e.preventDefault();cancelGesture()}
   if(e.key==='Home'){e.preventDefault();resetWindow()}
   if(extent&&['ArrowLeft','ArrowRight'].includes(e.key)){
    e.preventDefault();cancelGesture();const r=viewport||extent,delta=Math.max(DAY,Math.round((r[1]-r[0])/DAY/5)*DAY)*(e.key==='ArrowLeft'?-1:1);
    setWindow([r[0]+delta,r[1]+delta]);renderCharts();renderRecords();
   }
  };
 }
 const button=document.createElement('button');button.id='governed-tab';button.type='button';button.textContent='Audited Series';button.setAttribute('aria-selected','false');document.querySelector('.data-tabs').insertBefore(button,$('market-bars-tab'));
 async function get(path,params={}){const r=await fetch('/api/v1/market-data/governed/'+path+'?'+new URLSearchParams(params));if(!r.ok){let s=await r.text();try{s=JSON.parse(s).detail}catch{}throw new Error(s)}return r.json()}
 function error(e){$('governed-status').textContent='Unavailable';$('governed-message').textContent=e.message}
 function activate(){['market-bars-panel','research-panel'].forEach(id=>{if($(id))$(id).hidden=true});$('governed-panel').hidden=false;['market-bars-tab','research-tab'].forEach(id=>$(id).setAttribute('aria-selected','false'));button.setAttribute('aria-selected','true');const u=new URL(location.href);u.searchParams.set('view','history');history.replaceState(null,'',u);if(!batch)refresh().catch(error)}
 button.onclick=activate;
 function download(name,value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 function renderCatalog(){
  const key=$('governed-catalog-filter').value,filtered=catalog.filter(r=>key==='all'||key==='unavailable'&&!r.rows||key==='raw'&&(r.raw_rows||0)<(r.rows||0)||key==='gaps'&&r.internal_gaps>0||key==='identity'&&r.unresolved_historical_names?.length||key==='prelisting'&&r.pre_listing_source_observations>0||key==='stale'&&r.tail_status==='stale_or_delisted_unverified'||key==='conflicts'&&r.conflict_dates>0);
  $('governed-catalog-count').textContent=` ${fmt(filtered.length)} match · ${catalogOffset+1}–${Math.min(catalogOffset+100,filtered.length)}`;
  $('governed-catalog-next').disabled=filtered.length<=100;
  $('governed-catalog-table').innerHTML='<table><thead><tr><th>Symbol</th><th>Provider identity</th><th>Start</th><th>End</th><th>Sessions</th><th>Raw supported</th><th>Gaps</th><th>Status</th></tr></thead><tbody>'+filtered.slice(catalogOffset,catalogOffset+100).map(r=>`<tr><td><button type="button" data-governed-symbol="${esc(r.symbol)}">${esc(r.symbol)}</button></td><td>${esc(r.name||'Unresolved')}</td><td>${esc(r.first||'—')}</td><td>${esc(r.last||'—')}</td><td>${fmt(r.rows)}</td><td>${fmt(r.raw_rows)}</td><td>${fmt(r.internal_gaps)}</td><td>${esc(r.status)}</td></tr>`).join('')+'</tbody></table>';
  $('governed-catalog-table').querySelectorAll('button').forEach(b=>b.onclick=()=>{$('governed-symbol').value=b.dataset.governedSymbol;load().catch(error)});
  $('governed-catalog-next').onclick=()=>{catalogOffset=catalogOffset+100>=filtered.length?0:catalogOffset+100;renderCatalog()};
 }
 function chart(id,rows,key,title,second=[]){
  if(!extent){$(id).innerHTML='<div class="note">No dated history is available.</div>';return}
  rows=visibleRows(rows);second=visibleRows(second);
  const nums=[...rows.map(r=>r[key]),...second.map(r=>r.value)].filter(Number.isFinite);
  const [begin,end]=viewport||extent,lo=nums.length?Math.min(...nums):0,hi=nums.length?Math.max(...nums):1,span=hi-lo||1;
  const x=d=>65+(Date.parse(d)-begin)/(end-begin||1)*900,y=v=>225-(v-lo)/span*195;
  function path(data,field){let out='',last=null;const gaps=audit?.gaps||[];for(const r of data){const v=r[field];if(!Number.isFinite(v)){last=null;continue}const broken=!last||gaps.some(d=>d>last&&d<r.trade_date);out+=(broken?'M':'L')+x(r.trade_date).toFixed(2)+','+y(v).toFixed(2);last=r.trade_date}return out}
  const dots=(data,field,color)=>data.length<=250?data.filter(r=>Number.isFinite(r[field])).map(r=>`<circle cx="${x(r.trade_date)}" cy="${y(r[field])}" r="2.2" fill="${color}"/>`).join(''):'';
  $(id).innerHTML=`<div class="muted">${esc(title)}</div><svg viewBox="0 0 1000 265" role="img" aria-label="${esc(title)}" data-start="${dateText(begin)}" data-end="${dateText(end)}"><path d="M65 20V230H965" fill="none" stroke="#d8dee8"/><path class="history-line" d="${path(rows,key)}" fill="none" stroke="#2456a6" stroke-width="1.6"/><path class="comparison-line" d="${path(second,'value')}" fill="none" stroke="#cf7d21" stroke-width="1.4"/>${dots(rows,key,'#2456a6')}${dots(second,'value','#cf7d21')}${nums.length?`<text x="0" y="33" font-size="12">${esc(num(hi))}</text><text x="0" y="228" font-size="12">${esc(num(lo))}</text>`:'<text x="500" y="125" text-anchor="middle" font-size="14" fill="#657083">No supported observations for this basis and range.</text>'}<text x="65" y="252" font-size="12">${dateText(begin)}</text><text x="965" y="252" text-anchor="end" font-size="12">${dateText(end)}</text><rect class="zoom-selection" x="65" y="20" width="0" height="210" fill="#2456a6" fill-opacity="0.15" stroke="#2456a6" pointer-events="none"/></svg>`;
 }
 function renderCharts(sync=true){
  if(!page||!audit){chartIds.forEach(id=>$(id).innerHTML='');syncWindow();return}
  const basis=$('governed-basis').value,source=page.comparison_source,column=$('governed-column').value;
  const overlay=basis==='adjusted'&&column==='rebased_adjusted_close'?page.comparisons.map(r=>({trade_date:r.trade_date,value:r[column]})):[];
  chart('governed-chart',page.rows,basis+'_close',basis==='raw'?'Reconstructed raw close · USD · null values remain gaps':'Dividend + split adjusted close · USD · blue: governed; orange: aligned source',overlay);
  if(source){chart('governed-source-chart',page.comparisons,column,'Source history · '+$('governed-column').selectedOptions[0].text)}else $('governed-source-chart').innerHTML='';
  if(sync)syncWindow();
 }
 function render(){
  if(!page||!audit)return;const source=page.comparison_source;
  $('governed-status').textContent=`${fmt(page.rows.length)} dated rows loaded${page.next_after?' · truncated':''}`;
  $('governed-title').textContent=`${audit.symbol} · ${audit.name||'Identity unresolved'}`;
  $('governed-metrics').innerHTML=[['Saved sessions',audit.rows],['Raw prices supported',audit.raw_rows],['Raw volume supported',audit.raw_volume_rows],['Internal gaps',audit.internal_gaps],['Price conflict dates',audit.conflict_dates],['Joined rows',audit.joined_rows],['Earlier identity rows excluded',audit.pre_listing_source_observations]].map(([k,v])=>`<div><strong>${fmt(v)}</strong>${esc(k)}</div>`).join('');
  const missing=(audit.rows||0)-(audit.raw_rows||0),endNote=audit.tail_status==='stale_or_delisted_unverified'?' The endpoint is stale or delisted; the reason is unverified.':'';
  $('governed-message').textContent=`${audit.status.replaceAll('_',' ')} · ${audit.first||'no history'} to ${audit.last||'no history'}.${endNote}\n${missing?fmt(missing)+' sessions have no defensible raw reconstruction. ':''}Price conflicts refer to archived source comparisons, not a claim that the selected source is wrong. Historical availability and full listing-history completeness are uncertified.${audit.listing_boundary?.date?' Identity/start boundary: '+audit.listing_boundary.date+'. Earlier source observations are quarantined pending dated identity evidence.':''}${audit.unresolved_historical_names?.length?' Historical issuer names require review: '+audit.unresolved_historical_names.join('; '):''}`;
  $('governed-batch').textContent='Frozen batch '+batch+' · cutoff '+audit.requested_cutoff;
  renderCharts();
  const selected=audit.sources.find(s=>s.source_id===source);$('governed-comparison-note').textContent=selected?`${selected.source_id} · ${selected.price_basis} · ${selected.accepted?'Accepted for joining after audit':'Excluded from joining'}${selected.eligible_from?' on or after '+selected.eligible_from:''}. ${selected.pre_listing_observations?fmt(selected.pre_listing_observations)+' earlier source observations are excluded. ':''}Original source Close and volume may use different split/dividend conventions. ${page.comparison_truncated?'Source display is truncated.':''}`:'';
  $('governed-overlaps').innerHTML='<table><thead><tr><th>Compared source</th><th>Overlap</th><th>Scale</th><th>Price error p99</th><th>Return error p99</th><th>Volume error p99</th><th>Join</th></tr></thead><tbody>'+audit.overlaps.filter(r=>r.anchor===audit.primary_source).map(r=>`<tr><td>${esc(r.candidate)}</td><td>${fmt(r.overlap)}</td><td>${num(r.scale)}</td><td>${pct(r.p99_scale_error)}</td><td>${pct(r.p99_return_error)}</td><td>${pct(r.volume_p99_scale_error)}</td><td>${esc(r.reason)}</td></tr>`).join('')+'</tbody></table>';
  $('governed-audit').textContent=JSON.stringify(audit,null,2);
  renderRecords();
 }
 function renderRecords(){
  const rows=visibleRows(page?.rows||[]);
  $('governed-records').innerHTML='<table><thead><tr><th>Date</th><th>Adjusted close</th><th>Reconstructed raw close</th><th>Source volume</th><th>Reconstructed raw volume</th><th>Audit flags</th><th>Lineage</th></tr></thead><tbody>'+rows.slice(-200).reverse().map(r=>`<tr><td>${r.trade_date}</td><td>${num(r.adjusted_close)}</td><td>${num(r.raw_close)}</td><td>${num(r.source_volume)}</td><td>${num(r.raw_volume)}</td><td>${esc(r.quality_flags.join(', '))}</td><td><details><summary>Inspect</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details></td></tr>`).join('')+'</tbody></table>';
  $('governed-export').disabled=!rows.length;
 }
 async function loadSeries(g){
  // Always fetch the longest saved range; chart navigation only changes the local viewport.
  const params={batch,symbol:loadedSymbol,comparison_source:$('governed-source').value};
  const result=await get('series',params);if(g!==generation)return;
  cancelGesture();page={...result,comparison_source:params.comparison_source};extent=fullExtent();setWindow(viewport);render();
 }
 async function load(){
  const g=++generation;cancelGesture();loadedSymbol=$('governed-symbol').value.trim();page=null;audit=null;extent=null;viewport=null;renderCharts();renderRecords();
  ['governed-overlaps','governed-audit','governed-actions','governed-batch'].forEach(id=>$(id).textContent='');$('governed-source').innerHTML='<option value="">None</option>';
  $('governed-status').textContent='Loading audit';$('governed-title').textContent=loadedSymbol;$('governed-message').textContent='';$('governed-metrics').innerHTML='';$('governed-comparison-note').textContent='';
  const result=await get('audit',{batch,symbol:loadedSymbol});if(g!==generation)return;audit=result.audit;$('governed-actions').textContent='';$('governed-source').innerHTML='<option value="">None</option>'+audit.sources.map(s=>`<option value="${esc(s.source_id)}">${esc(s.source_id)}</option>`).join('');const comparison=audit.sources.find(s=>s.source_id.includes('yahoo2020'))||audit.sources.find(s=>s.source_id!==audit.primary_source);if(comparison)$('governed-source').value=comparison.source_id;await loadSeries(g);
 }
 async function refresh(){const c=await get('catalog');batch=c.batch;catalog=c.series;$('governed-symbols').innerHTML=catalog.map(r=>`<option value="${esc(r.symbol)}">${esc(r.name||'unavailable')} · ${fmt(r.rows)} rows · ${esc(r.status)}</option>`).join('');$('governed-catalog-summary').textContent=`All ${fmt(catalog.length)} underlyings · ${fmt(catalog.filter(r=>!r.rows).length)} without governed history · inspect unresolved work`;renderCatalog();await load()}
 $('governed-filters').onsubmit=async e=>{e.preventDefault();try{if(page&&loadedSymbol===$('governed-symbol').value.trim())applyDateWindow();else await load()}catch(e){error(e)}};
 $('governed-comparison').onsubmit=e=>{e.preventDefault();if(page&&audit)loadSeries(++generation).catch(error)};
 $('governed-basis').onchange=()=>{cancelGesture();render()};$('governed-column').onchange=()=>{cancelGesture();render()};
 $('governed-zoom').onclick=()=>setMode('zoom');$('governed-pan').onclick=()=>setMode('pan');$('governed-reset').onclick=resetWindow;chartIds.forEach(bindChart);
 $('governed-export').onclick=()=>{if(page)download(loadedSymbol+'-governed-'+batch.slice(0,12)+'.json',{audit,...page,rows:visibleRows(page.rows),comparisons:visibleRows(page.comparisons),view_start:dateText((viewport||extent)[0]),view_end:dateText((viewport||extent)[1])})};
 $('governed-catalog-export').onclick=()=>{if(batch)download('governed-audit-catalog-'+batch.slice(0,12)+'.json',{batch,series:catalog})};
 $('governed-catalog-filter').onchange=()=>{catalogOffset=0;renderCatalog()};
 $('governed-actions-load').onclick=async()=>{if(!page||!audit)return;try{const actionGeneration=generation;const r=await get('actions',{batch,symbol:loadedSymbol});if(actionGeneration!==generation)return;$('governed-actions').textContent=r.basis_note+'\n\n'+JSON.stringify(r.actions,null,2)}catch(e){error(e)}};
 $('governed-source-download').onclick=async()=>{if(!page||!$('governed-source').value)return;try{const r=await get('source',{batch,symbol:loadedSymbol,source_id:$('governed-source').value});download(loadedSymbol+'-source.json',r)}catch(e){error(e)}};
 window.addEventListener('DOMContentLoaded',()=>{['research-tab','market-bars-tab'].forEach(id=>$(id).addEventListener('click',()=>{$('governed-panel').hidden=true;button.setAttribute('aria-selected','false')}));if(requested)activate()});
})();
</script>
'''
