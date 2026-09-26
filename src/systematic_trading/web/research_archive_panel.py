"""Research archive tab embedded in the existing Market Data page."""

RESEARCH_ARCHIVE_HTML = r'''
<style>
 .data-tabs {display:flex;gap:8px;margin:0 0 16px;align-items:center}
 .data-tabs button[aria-selected="true"] {background:#2456a6;color:white}
 #research-panel[hidden],#market-bars-panel[hidden]{display:none}
 #research-panel .archive-note{padding:12px 16px;color:#657083;line-height:1.55}
 #research-panel .filters {flex-wrap:wrap}
 #research-dataset {max-width:440px;width:35vw;min-width:240px}
 #research-table {max-height:550px;overflow:auto}
 #research-table td{white-space:nowrap}
 #research-table pre{white-space:pre-wrap;word-break:break-word;max-width:680px;font-size:12px}
 #research-chart{padding:8px 18px}
 #research-chart svg{width:100%;max-height:230px}
 #research-status{margin-left:auto}
</style>
<h2>Market History</h2>
<p class="muted">Audited continuous series and recorded market bars, with original sources available for inspection.</p>
<nav class="data-tabs" aria-label="Market History views">
 <button id="market-bars-tab" type="button" aria-selected="false">Recorded Bars</button>
</nav>
<nav class="data-tabs raw-data-navigation" aria-label="Market History source archive" style="padding-left:18px;border-left:2px solid #d8dee8;font-size:12px">
 <button id="research-tab" type="button" aria-selected="false">Raw Data</button>
 <span id="research-catalog-status" class="muted">Loading source archive…</span>
</nav>
<section id="research-panel" class="panel" hidden>
 <div class="panel-head"><h2>Raw Data</h2><span id="research-status">Loading</span></div>
 <div class="archive-note">Historical stock prices, dated fund holdings, constituent signals and study results saved for reuse. Source Close is not necessarily raw: Yahoo Close is split-adjusted, and Stooq OHLC is dividend/split-adjusted. Market History → Audited Series separates the supported price bases and audits overlaps. Use that published series for new research; this archive retains source evidence and legacy study artifacts. Historical publication dates may be unknown.</div>
 <form id="research-filters" class="filters">
  <label>Dataset<select id="research-dataset" aria-label="Research dataset"></select></label>
  <label>Data type<select id="research-family" aria-label="Research data type"></select></label>
  <label>Symbol / entity<input id="research-entity" list="research-entities" placeholder="All entities" aria-label="Research symbol"></label><datalist id="research-entities"></datalist>
  <label>From<input id="research-start" type="date"></label><label>Through<input id="research-end" type="date"></label>
  <label>Page size<select id="research-limit"><option>200</option><option>1000</option><option>5000</option></select></label>
  <button type="submit" class="primary">View data</button><button id="research-refresh" type="button">Refresh archive</button>
  <button id="research-download" type="button" disabled>Download page JSON</button><button id="research-next" type="button" disabled>Next page</button>
 </form>
 <div id="research-coverage" class="archive-note"></div>
 <div id="research-chart"></div><div id="research-table" class="table-wrap"></div>
</section>
<script>
(() => {
 const $=id=>document.getElementById(id), esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const fmt=x=>Number(x).toLocaleString(), ds=x=>x?String(x).slice(0,10):'undated';
 let catalog=[], page=null, next=null, generation=0;
 async function get(path,params={}) {const r=await fetch('/api/v1/market-data/research/'+path+'?'+new URLSearchParams(params));if(!r.ok){let msg=await r.text();try{msg=JSON.parse(msg).detail}catch{}throw new Error(msg)}return r.json()}
 function activeFamily(){return catalog.find(x=>x.dataset===$('research-dataset').value)?.families.find(x=>x.family===$('research-family').value)}
 function message(error){$('research-status').textContent='Unavailable';$('research-table').innerHTML='<div class="error">'+esc(error.message)+'</div>'}
 function tab(research){$('research-panel').hidden=!research;const bars=$('market-bars-panel');if(bars)bars.hidden=research;$('research-tab').setAttribute('aria-selected',String(research));$('market-bars-tab').setAttribute('aria-selected',String(!research));const u=new URL(location.href);if(research)u.searchParams.set('view','raw');else u.searchParams.set('view','bars');history.replaceState(null,'',u)}
 $('research-tab').onclick=()=>tab(true);$('market-bars-tab').onclick=()=>tab(false);
 function renderChart(rows){
  const all=rows.filter(x=>Number.isFinite(x.payload.adjusted_close)&&x.payload.adjusted_close>0).sort((a,b)=>a.observed_at.localeCompare(b.observed_at));
  if(all.length<2||new Set(all.map(x=>x.entity)).size!==1){ChartNavigation.clear('research-chart');$('research-chart').innerHTML='';return}
  if(new Set(all.map(x=>x.source_id)).size!==1){ChartNavigation.clear('research-chart');$('research-chart').textContent='This page contains multiple source histories. Inspect their price conventions below; they are not joined into one chart.';return}
  const view=ChartNavigation.view('research-chart',all,r=>Date.parse(r.observed_at),()=>renderChart(rows),{left:50,right:950,top:25,bottom:175},{key:all[0].source_id+'|'+all[0].entity+'|'+all[0].observed_at,resetLabel:'Full loaded page',scope:'Source archive · loaded page'});
  const valid=view.rows;if(!valid.length){$('research-chart').textContent='No observations in this period. Use Full loaded page to reset.';return}
  const values=valid.map(x=>x.payload.adjusted_close),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1;
  const points=values.map((v,i)=>`${50+(view.range[1]===view.range[0] ? .5 : (Date.parse(valid[i].observed_at)-view.range[0])/(view.range[1]-view.range[0]))*900},${170-(v-lo)/span*140}`).join(' ');
  $('research-chart').innerHTML=`<div class="muted">${esc(valid[0].entity)} · adjusted close · ${fmt(values.length)} loaded observations</div><svg viewBox="0 0 1000 210" role="img" aria-label="Research adjusted closing price history"><path d="M50 25V175H950" fill="none" stroke="#cbd5e1"/><polyline points="${points}" fill="none" stroke="#2456a6" stroke-width="2"/><text x="0" y="34" font-size="12">${hi.toFixed(2)}</text><text x="0" y="174" font-size="12">${lo.toFixed(2)}</text><text x="50" y="200" font-size="12">${ds(valid[0].observed_at)}</text><text x="850" y="200" font-size="12">${ds(valid.at(-1).observed_at)}</text></svg>`;
 }
 function render(data){
  page=data;next=data.next_cursor;$('research-next').disabled=!next;$('research-download').disabled=!data.rows.length;
  $('research-status').textContent=`${fmt(data.rows.length)} records loaded${next?' · more available':''}`;
  const f=activeFamily();$('research-coverage').textContent=f?`${fmt(f.row_count)} saved records · ${fmt(f.entity_count)} entities · ${ds(f.first_observation)} to ${ds(f.last_observation)} · ${fmt(f.unknown_availability)} records with unknown historical availability. Use the filters above to narrow the displayed records.`:'';
  renderChart(data.rows);
  if(!data.rows.length){$('research-table').innerHTML='<div class="archive-note">No records match these filters. Clear the symbol or widen the dates.</div>';return}
  const bars=data.family==='research_equity_daily_bar',holdings=data.family==='research_sector_constituent';
  const fields=bars?['open','high','low','close','adjusted_close','volume']:holdings?['name','sector','weight_pct','market_value','assumed_available']:data.family==='research_constituent_backtest'?['period','cagr','sharpe','information_ratio','cagr_delta']:data.family==='research_constituent_signal'?['value_coverage','name_coverage','hhi_smoothed','hhi_velocity','hhi_acceleration','breadth','signed_activity']:['value_coverage','name_coverage','status'];
  const names={open:'Source open',high:'Source high',low:'Source low',close:'Source close',volume:'Source volume',name:'Name',sector:'Sector',status:'Status',adjusted_close:'Adjusted close',weight_pct:'Weight %',market_value:'Holding value',assumed_available:'Assumed available',value_coverage:'Value coverage',name_coverage:'Name coverage'};
  Object.assign(names,{period:'Period',cagr:'CAGR',sharpe:'Sharpe',information_ratio:'IR',cagr_delta:'CAGR change',hhi_smoothed:'HHI',hhi_velocity:'HHI derivative',hhi_acceleration:'HHI second derivative',breadth:'Breadth',signed_activity:'Signed activity'});
  const value=x=>typeof x==='number'?(x!==0&&Math.abs(x)<.0001?x.toExponential(3):x.toLocaleString(undefined,{maximumFractionDigits:4})):x??'—';
  const field=(r,k)=>['cagr','cagr_delta'].includes(k)&&typeof r.payload[k]==='number'?(100*r.payload[k]).toFixed(3)+'%':value(r.payload[k]??r.payload.values?.[k]??(k==='period'?r.point_key.split('/').at(-1):null));
  $('research-table').innerHTML='<table><thead><tr><th>Date</th><th>Entity</th>'+fields.map(k=>'<th>'+esc(names[k]||k)+'</th>').join('')+'<th>Source & record</th></tr></thead><tbody>'+data.rows.map(r=>'<tr><td>'+esc(ds(r.observed_at))+'</td><td>'+esc(r.entity)+'</td>'+fields.map(k=>'<td>'+esc(field(r,k))+'</td>').join('')+'<td><details><summary>Inspect</summary><pre>'+esc(JSON.stringify(r,null,2))+'</pre></details></td></tr>').join('')+'</tbody></table>';
 }
 async function load(cursor=null){const g=++generation;$('research-status').textContent='Loading records';$('research-next').disabled=true;const q={dataset:$('research-dataset').value,family:$('research-family').value,entity:$('research-entity').value.trim(),limit:$('research-limit').value};if($('research-start').value)q.start_date=$('research-start').value;if($('research-end').value)q.end_date=$('research-end').value;if(cursor)q.cursor=cursor;const data=await get('rows',q);if(g===generation)render(data)}
 async function familyChanged(){++generation;next=null;$('research-next').disabled=true;$('research-start').value='';$('research-end').value='';const f=activeFamily();if(!f)return;const dataset=$('research-dataset').value,family=f.family;const x=await get('entities',{dataset,family,limit:5000});if(dataset!==$('research-dataset').value||family!==$('research-family').value)return;$('research-entities').innerHTML=x.entities.map(e=>`<option value="${esc(e.entity)}">${fmt(e.row_count)} records</option>`).join('');$('research-entity').value=family==='research_equity_daily_bar'?(x.entities.find(e=>e.entity==='AAPL')?.entity||x.entities[0]?.entity||''):family==='research_constituent_signal'?'SPY':'';await load()}
 async function datasetChanged(){const x=catalog.find(x=>x.dataset===$('research-dataset').value);if(!x)return;const sorted=[...x.families].sort((a,b)=>(a.family==='research_equity_daily_bar'?-1:0)-(b.family==='research_equity_daily_bar'?-1:0)||b.row_count-a.row_count);$('research-family').innerHTML=sorted.map(f=>`<option value="${esc(f.family)}">${esc(f.label)} (${fmt(f.row_count)})</option>`).join('');await familyChanged()}
 async function refresh(){const old=$('research-dataset').value;const x=await get('datasets');catalog=x.datasets;$('research-catalog-status').textContent=`${catalog.length} datasets · ${fmt(catalog.reduce((n,x)=>n+x.row_count,0))} saved records`;$('research-dataset').innerHTML=catalog.map(x=>`<option value="${esc(x.dataset)}">${esc(x.title)}</option>`).join('');if(catalog.some(x=>x.dataset===old))$('research-dataset').value=old;if(catalog.length)await datasetChanged();else{$('research-status').textContent='No research publications';$('research-table').innerHTML=''}}
 $('research-filters').onsubmit=e=>{e.preventDefault();load().catch(message)};$('research-dataset').onchange=()=>datasetChanged().catch(message);$('research-family').onchange=()=>familyChanged().catch(message);$('research-next').onclick=()=>load(next).catch(message);$('research-refresh').onclick=()=>refresh().catch(message);
 $('research-download').onclick=()=>{if(!page)return;const blob=new Blob([JSON.stringify(page,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='research-data-page.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 document.addEventListener('DOMContentLoaded',()=>{tab(new URL(location.href).searchParams.get('view')==='research'||new URL(location.href).searchParams.get('view')==='raw');refresh().catch(e=>{$('research-catalog-status').textContent='Research archive unavailable';message(e)})});
})();
</script>
'''
