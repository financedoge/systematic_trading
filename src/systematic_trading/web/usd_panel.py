"""Broad-dollar index tab in Market Data."""
USD_HTML = r'''
<section id="usd-panel" class="panel" hidden>
 <div class="panel-head"><h2>USD · Broad Dollar Index</h2><span id="usd-status" role="status">Loading</span></div>
 <div style="padding:16px">
 <p>Federal Reserve nominal broad dollar index · <strong>DTWEXBGS</strong> · January 2006 average = 100.</p>
 <p id="usd-meta"></p><p id="usd-changes"></p>
 <div class="filters"><label>From <input id="usd-start" type="date"></label><label>Through <input id="usd-end" type="date"></label>
 <button id="usd-reset" type="button">Full history</button><button id="usd-download" type="button">Download published data</button></div>
 <div id="usd-chart" aria-label="USD broad dollar index history" role="img"></div>
 <p id="usd-basis"></p><p><a href="https://www.federalreserve.gov/releases/h10/Summary/" target="_blank" rel="noopener">Federal Reserve methodology</a> ·
 <a href="https://alfred.stlouisfed.org/series?seid=DTWEXBGS" target="_blank" rel="noopener">ALFRED vintage archive</a></p>
 <details><summary>Publication and audit details</summary><pre id="usd-audit" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>
 </div>
</section>
<script>
(()=>{
 const $=id=>document.getElementById(id),requestedUsd=new URL(location.href).searchParams.get('view')==='usd';let data=null;
 function draw(){
   const rows=data.observations.filter(r=>(!$('usd-start').value||r.date>=$('usd-start').value)&&(!$('usd-end').value||r.date<=$('usd-end').value));
   const valid=rows.filter(r=>r.value!==null);if(!valid.length){$('usd-chart').textContent='No published observations in this range.';return;}
   const lo=Math.min(...valid.map(r=>+r.value)),hi=Math.max(...valid.map(r=>+r.value)),a=Date.parse(rows[0].date),b=Date.parse(rows.at(-1).date);
   const x=r=>60+900*(Date.parse(r.date)-a)/(b-a||1),y=r=>270-230*(+r.value-lo)/(hi-lo||1);let path='',move=true;
   for(const r of rows){if(r.value===null){move=true;continue;}path+=(move?'M':'L')+x(r).toFixed(2)+' '+y(r).toFixed(2)+' ';move=false;}
   $('usd-chart').innerHTML=`<svg viewBox="0 0 1000 320" style="width:100%;max-height:380px" role="img" aria-label="USD index levels with missing observations retained"><path d="${path}" fill="none" stroke="#2463a7" stroke-width="1.7"/><text x="4" y="44">${hi.toFixed(1)}</text><text x="4" y="275">${lo.toFixed(1)}</text><text x="60" y="310">${rows[0].date}</text><text x="850" y="310">${rows.at(-1).date}</text></svg>`;
 }
 async function load(){try{
   const r=await fetch('/api/v1/market-data/usd/history');if(!r.ok)throw new Error(await r.text());data=await r.json();
   $('usd-status').textContent='Published · '+data.observation_date;
   const last=data.observations.filter(r=>r.value!==null).at(-1);
   $('usd-meta').textContent=`Latest level ${Number(last.value).toFixed(4)} on ${last.date}. Vintage ${data.vintage_date}; ${data.published_vintages} archived signal snapshots.`;
   $('usd-changes').textContent=`21 observations: ${(100*data.features.USD21).toFixed(2)}% · 63 observations: ${(100*data.features.USD63).toFixed(2)}%. Rising values mean a stronger USD.`;
   $('usd-basis').textContent=data.basis+' Missing observations remain gaps. USD/CNH exposure remains unhedged.';
   const {observations,...audit}=data;$('usd-audit').textContent=JSON.stringify({...audit,rows:observations.length,missing:observations.filter(r=>r.value===null).length},null,2);draw();
 }catch(e){$('usd-status').textContent='Unavailable';$('usd-meta').textContent=e.message;}}
 function activate(){for(const id of ['market-bars-panel','research-panel','governed-panel'])if($(id))$(id).hidden=true;
   for(const id of ['market-bars-tab','research-tab','governed-tab'])if($(id))$(id).setAttribute('aria-selected','false');
   $('usd-panel').hidden=false;$('usd-tab').setAttribute('aria-selected','true');const u=new URL(location.href);u.searchParams.set('view','usd');history.replaceState(null,'',u);if(!data)load();}
 window.addEventListener('DOMContentLoaded',()=>{
   const tab=document.createElement('button');tab.id='usd-tab';tab.type='button';tab.textContent='USD index';tab.setAttribute('aria-selected','false');document.querySelector('.data-tabs').appendChild(tab);tab.onclick=activate;
   for(const id of ['market-bars-tab','research-tab','governed-tab'])$(id)?.addEventListener('click',()=>{$('usd-panel').hidden=true;tab.setAttribute('aria-selected','false');});
   $('usd-start').onchange=$('usd-end').onchange=()=>{if(data)draw();};$('usd-reset').onclick=()=>{$('usd-start').value=$('usd-end').value='';if(data)draw();};
   $('usd-download').onclick=()=>{if(!data)return;const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=url;a.download='USD-DTWEXBGS-'+data.vintage_date+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
   if(requestedUsd)activate();
 });
})();
</script>
'''
