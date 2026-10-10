"""Prospective holdings, valuation and fund-size inspection."""

ISSUER_HTML = r'''
<section id="issuer-panel" class="panel" data-market-view="issuer" hidden>
 <div class="panel-head"><h2>ETF Fundamentals</h2><span id="issuer-status" aria-live="polite">Loading recorder</span></div>
 <p class="note">Issuer holdings, valuation, growth estimates and fund size. Each section keeps its own as-of date. These records build forward from capture time and do not provide historical holdings or forecast vintages.</p>
 <form id="issuer-filters" class="filters"><label>ETF<select id="issuer-fund" aria-label="Issuer ETF"></select></label><label>Captured version<select id="issuer-capture" aria-label="Issuer captured version"></select></label><button type="submit" class="primary">View snapshot</button><button id="issuer-refresh" type="button">Refresh coverage</button></form>
 <p id="issuer-warning" class="note" style="background:#fff8db;color:#77520a;border-left:3px solid #d5a52a;padding:12px" hidden></p>
 <p id="issuer-exposure" class="note"></p><p id="issuer-dates" class="note"></p>
 <div id="issuer-metrics" class="table-wrap"></div>
 <h3>Industry allocation</h3><p id="issuer-allocation-date" class="note"></p><div id="issuer-allocation" class="table-wrap"></div>
 <details id="issuer-holdings"><summary>Recorded holdings</summary><p id="issuer-holdings-note" class="note"></p><div id="issuer-positions" class="table-wrap"></div></details>
 <p id="issuer-limitations" class="note"></p>
 <details class="market-debug-only"><summary>Recorder evidence</summary><pre id="issuer-evidence"></pre></details>
</section>
<script>
(()=>{
 const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');let catalog=null,sequence=0;
 const num=x=>x===null||x===undefined?'Missing':Number(x).toLocaleString(undefined,{maximumFractionDigits:6});
 const table=(headers,rows)=>'<table><thead><tr>'+headers.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>`<td>${esc(v)}</td>`).join('')+'</tr>').join('')+'</tbody></table>';
 async function get(url){const r=await fetch(url);if(!r.ok)throw new Error(r.status===409?'Publication changed; refresh coverage.':'Issuer publication is unavailable or failed verification.');return r.json()}
 function clear(){for(const id of ['metrics','dates','allocation','allocation-date','positions','holdings-note','evidence'])$('issuer-'+id).textContent=''}
 function choices(){const f=catalog.funds.find(f=>f.symbol===$('issuer-fund').value);$('issuer-capture').innerHTML=f.captures.slice().reverse().map(c=>`<option value="${esc(c.batch)}">${esc(c.dates.nav)} · captured ${esc(c.first_seen_at)}</option>`).join('')}
 function show(data,f){
  $('issuer-dates').textContent=`${data.identity.isin} · ${data.identity.exchange} · ${data.identity.currency} · First captured ${data.first_seen_at}`;
  $('issuer-metrics').innerHTML=table(['Statistic','Value','Units','As of'],data.metrics.map(m=>[m.name,num(m.value),m.units,m.as_of]));
  $('issuer-allocation-date').textContent='As of '+data.dates.allocation;
  $('issuer-allocation').innerHTML=table(['Industry','Weight (%)'],data.industry_allocation.map(g=>[g.name,num(g.weight_percent)]));
  const h=data.holdings;$('issuer-holdings-note').textContent=`As of ${h.as_of} · ${h.rows.length} recorded rows · Weight sum ${num(h.weight_sum_percent)}% · Residual ${num(h.weight_residual_percent)} percentage points. Includes cash and derivative valuation weights; derivative notionals and missing sector labels are not supplied.`;
  $('issuer-positions').innerHTML=table(['Holding','Ticker','Identifier','Weight (%)','Shares held','Currency','Sector'],h.rows.map(r=>[r.name,r.ticker??'Missing',r.identifier,num(r.weight_percent),num(r.shares_held),r.currency,r.sector??'Missing']));
  $('issuer-evidence').textContent=JSON.stringify({publication:f.pin,capture:$('issuer-capture').value,policy:data.policy,sources:data.receipt.sources,dates:data.dates,nav_reconciled:data.nav_reconciled,holdings_weights_reconciled:h.weights_reconciled},null,2);
 }
 async function load(reset=false){const id=++sequence;clear();$('issuer-status').style.color='';$('issuer-status').textContent='Loading snapshot';
  try{
   if(reset||!catalog){const next=await get('/api/v1/market-data/issuer-etfs/catalog');if(id!==sequence)return;catalog=next;const old=$('issuer-fund').value;$('issuer-fund').innerHTML=catalog.funds.map(f=>`<option value="${esc(f.symbol)}">${esc(f.symbol)} · ${esc(f.name)}</option>`).join('');if(catalog.funds.some(f=>f.symbol===old))$('issuer-fund').value=old;choices()}
   const f=catalog.funds.find(f=>f.symbol===$('issuer-fund').value);$('issuer-exposure').textContent=f.exposure;$('issuer-limitations').innerHTML=catalog.limitations.map(esc).join('<br>');
   if(f.verification_error)throw new Error(f.verification_error);
   const messages=[];if(f.stale)messages.push('No current snapshot is available.');if(f.recorder.error)messages.push('Latest recorder attempt failed; retained publication may be older.');
   $('issuer-warning').hidden=!messages.length;$('issuer-warning').textContent=messages.join(' ');
   if(!f.pin){$('issuer-status').textContent='Awaiting first publication';return}
   const data=await get('/api/v1/market-data/issuer-etfs/history?'+new URLSearchParams({symbol:f.symbol,capture:$('issuer-capture').value,catalog_batch:f.pin.batch}));if(id!==sequence)return;
   messages.push(...data.warnings);$('issuer-warning').hidden=!messages.length;$('issuer-warning').textContent=messages.join(' ');show(data,f);$('issuer-status').textContent=`${f.captures.length} captured version(s) · ${data.metrics.length} statistics`;
  }catch(e){if(id!==sequence)return;clear();$('issuer-status').textContent=e.message;$('issuer-status').style.color='#b42318';$('issuer-warning').hidden=true}
 }
 $('issuer-fund').onchange=()=>{choices();load()};$('issuer-filters').onsubmit=e=>{e.preventDefault();load()};$('issuer-refresh').onclick=()=>load(true);window.MarketHistory.register('issuer',()=>load(true));
})();
</script>
'''
