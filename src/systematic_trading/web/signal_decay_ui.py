"""Signal-decay panel: dashboard surface for the P4.13 diagnostic.

Read-only. It reports whether each monitored strategy's key signal is healthy,
weakening or decayed, and highlights any that currently carry allocation. It
never changes an allocation, an approval or a broker record.
"""
HTML = '''<style>
.signal-decay{margin:0 0 18px}
.signal-decay .decay-head{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;justify-content:space-between}
.signal-decay h2{margin:0 0 4px}
.decay-badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.decay-healthy{background:#e4f5e9;color:#1c6b36}
.decay-weakening{background:#fdf2d8;color:#8a5b00}
.decay-decayed{background:#fbe3e3;color:#96201b}
.decay-insufficient{background:#eceff3;color:#5b6673}
.decay-table-scroll{max-width:100%;overflow:auto}
.decay-table{border-collapse:separate;border-spacing:0;min-width:900px}
.decay-table th{text-align:left;white-space:nowrap}
.decay-table td{vertical-align:top}
.decay-table .num{text-align:right;font-variant-numeric:tabular-nums}
.decay-flag{font-weight:700;color:#96201b}
.decay-note{margin:6px 0 0;color:#5b6673;font-size:12px}
.decay-warn{border-left:4px solid #96201b;background:#fbe3e3;padding:10px 14px;margin:10px 0;border-radius:5px}
.decay-warn.weakening{border-left-color:#c98a00;background:#fdf2d8}
.decay-alert-summary{margin:8px 0 0;font-size:13px}
</style>
<section class="signal-decay panel" id="signal-decay">
<div class="decay-head">
<h2>Signal decay</h2>
<div class="note" id="decay-meta">Loading…</div>
</div>
<div id="decay-warnings"></div>
<div class="decay-table-scroll">
<table class="decay-table">
<thead><tr><th>Strategy</th><th>Status</th><th>Allocation</th><th>Key signal</th>
<th class="num">Long-run IC</th><th class="num">Recent IC</th><th class="num">IC IR</th>
<th class="num">Hit rate</th><th class="num">Half-life</th><th class="num">Breakeven IC</th><th>Reason</th></tr></thead>
<tbody id="decay-rows"><tr><td colspan="11" class="note">Loading signal decay…</td></tr></tbody>
</table>
</div>
<p class="decay-note" id="decay-coverage"></p>
<p class="decay-note" id="decay-limits"></p>
</section>'''

JS = '''
async function loadSignalDecay(){
  const rows=document.getElementById('decay-rows'),meta=document.getElementById('decay-meta');
  try{
    const response=await fetch('/api/v1/strategies/signal-decay');
    const data=await response.json();
    if(!data.available){
      rows.innerHTML=`<tr><td colspan="11" class="note">${esc(data.message||'Signal decay has not been computed yet.')}</td></tr>`;
      meta.textContent='No publication';return;
    }
    const h=data.headline||{};
    meta.textContent=`${h.decisions} decisions ${h.first_decision} to ${h.last_decision} · batch ${String(data.batch||'').slice(0,12)}… · ${data.cost_bps}bp costs`;
    const flagged=(data.warnings||[]).map(w=>`<div class="decay-warn ${w.status==='weakening'?'weakening':''}">
      <strong>${esc(w.label)}:</strong> ${esc(w.message)}${w.is_sota?' <em>(designated SOTA)</em>':''}${w.is_active?' <em>(active allocation)</em>':''}
      <div class="note">Review the evidence below, then decide through the normal allocation workflow. This panel changes nothing by itself.</div></div>`).join('');
    document.getElementById('decay-warnings').innerHTML=flagged;
    rows.innerHTML=(data.strategies||[]).map(s=>{
      const signals=s.signals||[];
      const details=signals.map(sig=>`<div class="note">${esc(sig.label)}: ${esc(sig.status)} — ${esc(sig.reason)}</div>`).join('');
      const primary=signals.find(sig=>sig.status===s.status)||signals[0]||{};
      const num=v=>v==null?'n/a':Number(v).toFixed(4);
      const num2=v=>v==null?'n/a':Number(v).toFixed(2);
      const weight=s.funded?`<span class="decay-flag">${(Number(s.allocation_weight)*100).toFixed(1)}%</span>${s.is_active?' <span class="note">active</span>':''}`:'<span class="note">none</span>';
      return `<tr><td><button class="strategy-link" data-id="${esc(s.strategy_key)}">${esc(s.name)}</button>${s.is_sota?' <span class="badge sota">SOTA</span>':''}</td>
        <td><span class="decay-badge decay-${esc(s.status)}">${esc(s.label)}</span></td>
        <td>${weight}</td>
        <td>${esc(primary.label||'')}${details}</td>
        <td class="num">${num(primary.long_run_ic)}</td><td class="num">${num(primary.recent_ic)}</td>
        <td class="num">${num2(primary.ic_ir)}</td><td class="num">${primary.hit_rate==null?'n/a':(Number(primary.hit_rate)*100).toFixed(0)+'%'}</td>
        <td class="num">${primary.half_life_sessions==null?'n/a':Number(primary.half_life_sessions).toFixed(0)+'d'}</td>
        <td class="num">${num(primary.breakeven_ic)}</td>
        <td>${esc(s.reason||'')}</td></tr>`;}).join('')
      ||'<tr><td colspan="11" class="note">No monitored strategies.</td></tr>';
    const gaps=data.coverage_gaps||[];
    document.getElementById('decay-coverage').textContent=gaps.length
      ? 'Not yet measured (used by a strategy but not published per decision): '+gaps.map(g=>g.name).join(', ')+'.'
      : '';
    document.getElementById('decay-limits').textContent=(data.limitations||[]).join(' ');
    rows.querySelectorAll('.strategy-link').forEach(button=>button.onclick=()=>{
      location.href='/api/v1/strategies/'+encodeURIComponent(button.dataset.id)+'/report';});
  }catch(error){
    rows.innerHTML=`<tr><td colspan="11" class="note">Could not load signal decay: ${esc(error.message)}</td></tr>`;
  }
}
loadSignalDecay();
setInterval(loadSignalDecay,30000);
'''

# Operator-page banner. Rendered only when a strategy that currently carries
# allocation has a decaying or decayed key signal, so a healthy book stays quiet.
ALERT_HTML = '''<style>
#decay-alert{display:none;margin:0 0 16px}
#decay-alert.visible{display:block}
#decay-alert .decay-alert-card{border-left:5px solid #c98a00;background:#fdf2d8;padding:12px 16px;border-radius:6px;margin-bottom:10px}
#decay-alert .decay-alert-card.decayed{border-left-color:#96201b;background:#fbe3e3}
#decay-alert h3{margin:0 0 4px;font-size:15px}
#decay-alert .decay-alert-action{margin:6px 0 0;font-size:12px;color:#5b6673}
</style>
<section id="decay-alert" role="status" aria-live="polite"></section>'''

ALERT_JS = '''
async function loadDecayAlert(){
  const host=document.getElementById('decay-alert');
  if(!host)return;
  try{
    const response=await fetch('/api/v1/strategies/signal-decay');
    const data=await response.json();
    const warnings=(data.warnings||[]);
    if(!data.available||!warnings.length){host.className='';host.innerHTML='';return;}
    host.className='visible';
    host.innerHTML=warnings.map(w=>`<div class="decay-alert-card ${w.status==='decayed'?'decayed':''}">
      <h3>${w.status==='decayed'?'Decayed':'Weakening'} signal on a funded strategy: ${esc(w.name)}</h3>
      <p>${esc(w.message)}${w.is_sota?' This is the designated SOTA.':''}${w.is_active?' It holds the active allocation.':''}</p>
      <p class="decay-alert-action">Review the Signal decay panel on
      <a href="/strategies">Strategies</a> before deciding to switch or deallocate.
      Nothing has been changed: allocations, approvals and broker records are untouched.</p></div>`).join('');
  }catch(error){host.className='';host.innerHTML='';}
}
loadDecayAlert();
setInterval(loadDecayAlert,30000);
'''
