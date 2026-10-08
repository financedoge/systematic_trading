"""Fund positioning view embedded in Market History."""

POSITIONING_HTML = r'''
<section id="positioning-panel" class="panel" data-market-view="positioning" hidden>
 <div class="panel-head"><h2>Fund Positioning</h2><span id="positioning-status" aria-live="polite">Loading recorder</span></div>
 <div class="note">CFTC disaggregated futures-only positioning for selected energy and metal contracts. Net positions are normalized by open interest. This describes futures traders, not ETF fund flows or ETF holdings; linked ETFs are economic proxies only.</div>
 <form id="positioning-filters" class="filters"><label>Market<select id="positioning-market" aria-label="Futures market"></select></label><button type="submit" class="primary">View history</button><button id="positioning-refresh" type="button">Refresh coverage</button></form>
 <div id="positioning-coverage" class="note"></div><div id="positioning-limitations" class="note"></div>
 <div id="positioning-records" class="table-wrap"></div>
 <details class="market-debug-only"><summary>Recorder evidence</summary><pre id="positioning-evidence"></pre></details>
</section>
<script>
(()=>{const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');let catalog=null;
async function get(url){const r=await fetch(url);if(!r.ok)throw new Error('Positioning publication is unavailable; retry after recorder recovery.');return r.json()}
function show(rows){$('positioning-records').innerHTML='<table><thead><tr><th>Position date</th><th>First seen by app</th><th>Open interest</th><th>Managed money net / OI</th><th>Producer net / OI</th><th>Swap dealer net / OI</th></tr></thead><tbody>'+rows.slice(-260).reverse().map(r=>`<tr><td>${esc(r.report_date)}</td><td>${esc(r.first_seen_at)}</td><td>${Number(r.open_interest||0).toLocaleString()}</td><td>${r.managed_money_net_pct_oi===null?'Missing':(100*Number(r.managed_money_net_pct_oi)).toFixed(2)+'%'}</td><td>${r.producer_merchant_net_pct_oi===null?'Missing':(100*Number(r.producer_merchant_net_pct_oi)).toFixed(2)+'%'}</td><td>${r.swap_dealer_net_pct_oi===null?'Missing':(100*Number(r.swap_dealer_net_pct_oi)).toFixed(2)+'%'}</td></tr>`).join('')+'</tbody></table>'}
async function load(){if(!catalog)catalog=await get('/api/v1/market-data/positioning/catalog');const old=$('positioning-market').value;$('positioning-market').innerHTML=catalog.config.markets.map(m=>`<option value="${esc(m.code)}">${esc(m.name)} (${esc(m.group)})</option>`).join('');if(old)$('positioning-market').value=old;const code=$('positioning-market').value;const rows=await get('/api/v1/market-data/positioning/history?'+new URLSearchParams({market:code}));show(rows.rows);$('positioning-status').textContent=`Published · ${catalog.rows.toLocaleString()} records through ${catalog.through||'unavailable'}`;$('positioning-coverage').innerHTML=catalog.markets.map(m=>`${esc(m.name)}: ${m.rows} reports through ${esc(m.through||'none')}`).join(' · ');$('positioning-limitations').innerHTML=catalog.limitations.map(esc).join('<br>');$('positioning-evidence').textContent=JSON.stringify({publication:catalog.version,source:catalog.config.source_url,history_start:catalog.config.history_start},null,2)}
function fail(e){$('positioning-status').textContent=e.message;$('positioning-records').textContent=''}
$('positioning-filters').onsubmit=e=>{e.preventDefault();load().catch(fail)};$('positioning-refresh').onclick=()=>{catalog=null;load().catch(fail)};window.MarketHistory.register('positioning',()=>load().catch(fail));})();
</script>
'''
