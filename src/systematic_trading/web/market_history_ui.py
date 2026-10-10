"""Shared Market History navigation and opt-in source diagnostics."""

MARKET_HISTORY_UI_HTML = r'''
<style>
 html:not([data-market-debug="true"]) .market-debug-only{display:none!important}
 [data-market-view][hidden]{display:none!important}
 body.market-data-page{background:#f4f6fa;-webkit-font-smoothing:antialiased}
 body.market-data-page>header{min-height:60px;padding:12px 28px;flex-direction:row;flex-wrap:wrap;gap:12px}
 body.market-data-page>header h1{font-size:14px;letter-spacing:.025em}
 body.market-data-page>header .actions{flex-wrap:nowrap;gap:4px}
 body.market-data-page>header .button{flex:0 0 auto;width:auto;min-height:32px;padding:6px 11px;font-size:12px}
 body.market-data-page main{max-width:1440px;padding:28px 32px 48px}
 #market-history-section{--focus:#315bc2;line-height:1.5}
 #market-history-section h2{font-size:16px;letter-spacing:-.02em;font-weight:650}
 #market-history-section .market-history-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:6px}
 #market-history-section .market-history-heading h2{font-size:27px;letter-spacing:-.035em;line-height:1.2}
 #market-history-section .market-description{margin:0;color:#65748a;font-size:13px}
 #market-history-section .market-debug-switch{display:inline-flex;flex:0 0 auto;width:auto;align-items:center;gap:8px;font-size:13px;white-space:nowrap;margin-left:auto}
 #market-history-section #market-debug{appearance:none;position:relative;flex:0 0 36px;width:36px;min-width:36px;height:20px;min-height:20px;padding:0;margin:0;border:1px solid #8793a5;border-radius:12px;background:#d7dde5;cursor:pointer}
 #market-debug::before{content:"";position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:white;box-shadow:0 1px 2px #0003}
 #market-history-section #market-debug:checked{background:#2456a6;border-color:#2456a6}
 #market-debug:checked::before{transform:translateX(16px)}
 #market-debug:focus-visible{outline:2px solid #2456a6;outline-offset:3px}
 #market-history-section button{flex:0 0 auto;width:auto;min-height:36px;border:1px solid #dce3ed;border-radius:8px;padding:7px 13px;background:#fff;color:#36465d;font-size:12px;font-weight:600;line-height:1.4;gap:7px;box-shadow:0 1px 2px #13243b04;transition:background .12s,border-color .12s,box-shadow .12s}
 #market-history-section button:hover:not(:disabled){background:#f4f7fc;border-color:#b6c5dc}
 #market-history-section button:active:not(:disabled){background:#e9eff8;box-shadow:none}
 #market-history-section button.primary{background:#315bc2;border-color:#315bc2;color:#fff;box-shadow:0 2px 3px #315bc220}
 #market-history-section button.primary:hover:not(:disabled){background:#264ca9;border-color:#264ca9}
 #market-history-section button:disabled{background:#f6f8fb;border-color:#e8edf4;color:#98a3b3;box-shadow:none;cursor:default}
 #market-history-section button:focus-visible,#market-history-section input:focus-visible,#market-history-section select:focus-visible,#market-history-section summary:focus-visible{outline:2px solid #7395df;outline-offset:3px}
 #market-history-section button svg{width:15px;height:15px;flex:none}
 #market-history-section .market-navigation{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:22px 0 20px}
 #market-history-section .data-tabs{display:inline-flex;flex-wrap:wrap;gap:3px;margin:0;padding:4px;border:1px solid #e0e6ef;border-radius:10px;background:#eaf0f7;align-items:center}
 #market-history-section .data-tabs button{background:transparent;border-color:transparent;box-shadow:none;color:#61718a;min-height:34px;padding:7px 14px}
 #market-history-section .data-tabs button[aria-selected="true"]{background:white;border-color:#e0e6ef;box-shadow:0 1px 3px #13243b0d;color:#23488e}
 #market-history-section .panel{border-color:#e0e6ef;border-radius:14px;box-shadow:0 2px 6px #13243b04}
 #market-history-section .panel-head{padding:17px 22px;min-height:58px;gap:12px;flex-wrap:wrap;border-bottom:1px solid #edf0f5}
 #market-history-section .panel-head>span{font-size:11px;color:#687991;background:#f4f7fb;border:1px solid #e9eef5;border-radius:6px;padding:3px 8px;line-height:1.5}
 #market-history-section .filters{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;padding:18px 22px;margin:0;border-bottom:1px solid #edf0f5}
 #market-history-section .filters label{display:grid;gap:6px;flex:0 1 auto;width:auto;min-width:0;color:#63728a;font-size:11px;font-weight:600}
 #market-history-section input:not([type=checkbox]),#market-history-section select{flex:none;width:100%;min-width:120px;max-width:100%;height:38px;min-height:38px;border:1px solid #dce3ed;border-radius:8px;padding:7px 10px;background:#fff;color:#24374f;font-size:13px;font-weight:400;line-height:normal;box-shadow:0 1px 2px #13243b03}
 #market-history-section input:hover,#market-history-section select:hover{border-color:#afc0d8}
 #market-history-section input::placeholder{color:#97a3b3}
 #market-history-section input.small{width:88px;min-width:76px}
 #market-history-section .filters button{min-height:38px}
 #market-history-section #governed-filters .series-field{flex:1 1 190px;max-width:300px}
 #market-history-section #governed-symbol{text-transform:uppercase;font-weight:600;letter-spacing:.035em}
 #market-history-section #governed-filters .date-field{flex:0 1 150px}
 #market-history-section .history-summary{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:24px 22px 18px;flex-wrap:wrap}
 #market-history-section .history-identity{min-width:0;flex:1 1 250px}
 #market-history-section #governed-title{display:block;font-size:23px;line-height:1.3;font-weight:650;letter-spacing:-.035em;margin-bottom:6px}
 #market-history-section #governed-basis-note{font-size:12px;color:#64748b}
 #market-history-section #governed-availability-note{font-size:11px;color:#7c899b;margin-top:4px}
 #market-history-section #governed-panel .metrics{padding:0;gap:24px;background:transparent;font-size:11px;color:#748297}
 #market-history-section #governed-panel .metrics strong{font-size:23px;color:#263b57;font-weight:600;letter-spacing:-.03em;line-height:1.4}
 #market-history-section #governed-panel .note{padding:12px 22px;font-size:12px;line-height:1.6}
 /* Fund Positioning, Energy Data and ETF Fundamentals use <div>/<p> notes that
    had no inset of their own, so their text sat flush against the panel edge
    while the other views were inset by 22px. margin:0 also normalises the <p>
    variants, which otherwise carry the browser's default paragraph margins. */
 #market-history-section #positioning-panel .note,
 #market-history-section #energy-panel .note,
 #market-history-section #issuer-panel .note{padding:12px 22px;margin:0;font-size:12px;line-height:1.6}
 #market-history-section #governed-panel .chart-tools,#market-history-section .time-chart-tools{padding:10px 22px;gap:6px;margin:0;font-size:11px;color:#748297;display:flex;align-items:center;flex-wrap:wrap;border-top:1px solid #f0f3f7}
 #market-history-section .chart-tools button,#market-history-section .time-chart-tools button,#market-history-section .range-buttons button{min-height:30px;padding:5px 10px;font-size:11px;border-color:transparent;background:#f3f6fb;box-shadow:none}
 #market-history-section .chart-tools button[aria-pressed="true"],#market-history-section .time-chart-tools button[aria-pressed="true"],#market-history-section .range-buttons button[aria-pressed="true"]{background:#e7eefc;border-color:#cedbf4;color:#244d9e}
 #market-history-section #governed-window{margin-left:auto;font-size:11px;color:#7a879a}
 #market-history-section #governed-chart-help{padding:0 22px 10px;font-size:11px;color:#8a95a5}
 #market-history-section #governed-panel .chart{padding:6px 18px 16px}
 #market-history-section #governed-panel .chart>.muted{font-size:11px;color:#7c899b;margin:0 5px}
 #market-history-section #governed-panel .chart svg{height:auto;min-height:220px;max-height:390px}
 #market-history-section #governed-panel svg text{fill:#8591a3;font-family:inherit;font-size:11px}
 #market-history-section #governed-panel .history-line{stroke:#315bc2;stroke-width:1.8;stroke-linejoin:round;stroke-linecap:round}
 #market-history-section #governed-panel .comparison-line{stroke-linejoin:round}
 #market-history-section details{margin:0;border-top:1px solid #edf0f5}
 #market-history-section details>summary{padding:15px 22px;font-size:12px;font-weight:600;color:#566880;cursor:pointer;list-style-position:inside}
 #market-history-section details[open]>summary{background:#f8fafd}
 #market-history-section #governed-panel pre{padding:0 22px;color:#66758a}
 #market-history-section table{table-layout:auto;font-size:12px}
 #market-history-section th{background:#f7f9fc;color:#728198;font-size:10px;font-weight:600;letter-spacing:.025em;white-space:nowrap}
 #market-history-section td,#market-history-section th{padding:11px 16px;border-color:#edf1f6}
 #market-history-section td{white-space:nowrap}
 #market-history-section tbody tr:hover{background:#f7faff}
 #market-history-section td details{border:0}
 #market-history-section td details>summary{padding:0}
 #market-history-section .table-wrap{scrollbar-width:thin;scrollbar-color:#ccd7e5 transparent}
 #market-history-section #golden-filters{border:1px solid #e0e6ef;padding:18px 22px;margin:0 0 14px}
 #market-history-section #golden-filters label{flex:1 1 130px}
 #market-history-section #golden-filters label.compact-field{flex:0 0 88px}
 #market-history-section #golden-filters .range-buttons{flex:1 1 auto;align-self:end;min-height:38px;gap:4px}
 #market-history-section #golden-filters #status{flex-basis:100%;font-size:11px}
 #market-history-section #market-bars-panel>.muted{font-size:11px;padding:0 3px;margin:12px 0 16px}
 #market-history-section .summary{grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-bottom:18px}
 #market-history-section .metric{padding:16px;min-height:90px;border-radius:12px;box-shadow:none}
 #market-history-section .metric label{flex:none;width:auto;font-size:10px;font-weight:600;color:#748297;margin-bottom:9px}
 #market-history-section .metric strong{font-size:21px;line-height:1.35;font-weight:600;letter-spacing:-.025em}
 #market-history-section #metric-range,#market-history-section #metric-source{font-size:12px;letter-spacing:0;line-height:1.7}
 #market-history-section #metric-range .muted{display:block}
 #market-history-section #golden-table .market-debug-only{white-space:normal;min-width:180px}
 #market-history-section .grid{gap:18px}
 #market-history-section .chart-wrap{padding:12px 18px;min-height:0}
 #market-history-section .time-chart-tools .time-chart-range{margin-left:auto}
 #market-history-section .time-chart-tools span:last-child{width:100%;font-size:10px;color:#8a95a5}
 #market-history-section .raw-section{margin-top:18px}
 #market-history-section .raw-grid{gap:16px}
 #market-history-section #research-panel .archive-note{padding:16px 22px;font-size:12px}
 #market-history-section #research-dataset{width:100%;min-width:0;max-width:100%}
 #market-history-section #research-filters label:first-child{flex:1 1 300px;max-width:480px}
 @media(max-width:1000px){
  #market-history-section .summary{grid-template-columns:repeat(3,minmax(0,1fr))}
  #market-history-section .history-summary{gap:18px}
 }
 @media(max-width:680px){
  body.market-data-page>header{padding:13px 18px;gap:8px}
  body.market-data-page>header .actions{width:100%}
  body.market-data-page main{padding:22px 16px 36px}
  #market-history-section .market-history-heading h2{font-size:24px}
  #market-history-section .market-navigation{margin:18px 0}
  #market-history-section .data-tabs button{padding:7px 10px;font-size:11px}
  #market-history-section .panel-head{padding:15px 18px}
  #market-history-section .filters{padding:16px 18px;gap:10px}
  #market-history-section #governed-filters .series-field{flex:1 1 100%;max-width:none}
  #market-history-section #governed-filters .date-field{flex:1 1 140px}
  #market-history-section .history-summary{padding:20px 18px 16px}
  #market-history-section #governed-title{font-size:21px}
  #market-history-section #governed-panel .metrics strong{font-size:21px}
  #market-history-section #governed-panel .chart-tools,#market-history-section .time-chart-tools{padding:10px 18px}
  #market-history-section #governed-window{flex-basis:100%;margin:4px 0 0}
  #market-history-section #governed-chart-help{display:none}
  #market-history-section #governed-panel .chart{padding:8px 10px 12px}
  #market-history-section #governed-panel .chart svg{min-height:180px}
  #market-history-section #golden-filters{padding:16px 18px}
  #market-history-section .metric{padding:13px 12px}
  #market-history-section .metric strong{font-size:18px}
  #market-history-section .time-chart-tools .time-chart-range{flex-basis:100%;margin-left:0}
  #market-history-section #research-filters label{flex:1 1 160px;max-width:100%}
 }
 @media(max-width:420px){
  #market-history-section .summary{grid-template-columns:repeat(2,minmax(0,1fr))}
  #market-history-section .filters button.primary{flex:1 1 auto}
  #market-history-section .data-tabs button svg{display:none}
  #market-history-section .data-tabs button{padding:7px 8px}
  #market-history-section .history-summary{gap:14px}
  #market-history-section #governed-panel .metrics{gap:20px}
 }
 @media(prefers-reduced-motion:reduce){#market-history-section button{transition:none}}
</style>
<div class="market-history-heading">
 <h2>Market History</h2>
 <label class="market-debug-switch"><input id="market-debug" type="checkbox" role="switch">Debug</label>
</div>
<p class="market-description">Explore price histories, intraday market activity and economic data vintages.</p>
<div class="market-navigation">
<nav class="data-tabs" aria-label="Market History views">
 <button id="governed-tab" type="button" aria-selected="false"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3v14h14M5 13l4-5 3 2 5-6"/></svg>Historical Daily Price</button>
 <button id="market-bars-tab" type="button" aria-selected="false"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 2v3m0 8v5M14 2v7m0 6v3"/><rect x="4" y="5" width="4" height="8" rx=".7"/><rect x="12" y="9" width="4" height="6" rx=".7"/></svg>Intraday Bars</button>
 <button id="economic-tab" type="button" aria-selected="false">Economic Data</button>
 <button id="positioning-tab" type="button" aria-selected="false">Fund Positioning</button>
 <button id="energy-tab" type="button" aria-selected="false">Energy Data</button>
 <button id="issuer-tab" type="button" aria-selected="false">ETF Fundamentals</button>
 <button id="research-tab" class="market-debug-only" type="button" aria-selected="false">Raw Data</button>
</nav>
 <span id="research-catalog-status" class="muted market-debug-only">Source archives</span>
</div>
<script>
(() => {
 const initial=new URL(location.href),views={history:['governed-panel','governed-tab'],bars:['market-bars-panel','market-bars-tab'],economics:['economic-panel','economic-tab'],positioning:['positioning-panel','positioning-tab'],energy:['energy-panel','energy-tab'],issuer:['issuer-panel','issuer-tab'],raw:['research-panel','research-tab']};
 const handlers=new Map();let active=null,debug=initial.searchParams.get('debug')==='1';
 const writeUrl=()=>{const u=new URL(location.href);u.searchParams.set('view',active||'history');if(debug)u.searchParams.set('debug','1');else u.searchParams.delete('debug');history.replaceState(null,'',u)};
 function activate(view){
  if(!Object.hasOwn(views,view)||(view==='raw'&&!debug))view='history';
  active=view;
  for(const [name,[panel,button]] of Object.entries(views)){
   const host=document.getElementById(panel);if(host)host.hidden=name!==view;
   document.getElementById(button)?.setAttribute('aria-selected',String(name===view));
  }
  writeUrl();handlers.get(view)?.();
 }
 function setDebug(enabled){
  debug=Boolean(enabled);document.documentElement.dataset.marketDebug=String(debug);
  document.getElementById('market-debug').checked=debug;
  if(!debug&&active==='raw')activate('history');else writeUrl();
  window.dispatchEvent(new CustomEvent('market-debug-change',{detail:{enabled:debug}}));
 }
 window.MarketHistory={get debug(){return debug},get active(){return active},activate,setDebug,
  register:(view,handler)=>handlers.set(view,handler)};
 document.documentElement.dataset.marketDebug=String(debug);
 window.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('market-debug').checked=debug;
  document.getElementById('market-debug').onchange=e=>setDebug(e.target.checked);
  for(const [view,[,button]] of Object.entries(views))document.getElementById(button).onclick=()=>activate(view);
  const requested=initial.searchParams.get('view');
  activate(requested==='research'?'raw':requested||'history');
 });
})();
</script>
'''
