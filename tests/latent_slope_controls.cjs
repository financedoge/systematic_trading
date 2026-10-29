const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/latent-slope-20261025-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1],code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
assert.doesNotMatch(html,/__EQ_|__REPORT_/);
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]));
for(const id of ['crosshair','hover-date'])ids.add(id); // created inside the chart SVG
const elements=new Map();function el(id){assert(ids.has(id),'Missing HTML element '+id);if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',setAttribute(){},select(){},querySelector(){return {getBoundingClientRect(){return {left:0,width:1140};}}}});return elements.get(id);}
el('report-data').textContent=data;el('era').value='late';
const context=vm.createContext({document:{getElementById:el}});vm.runInContext(code,context,{timeout:20000});const run=s=>vm.runInContext(s,context,{timeout:30000});
assert.equal(el('symbol').value,'WEAT');assert.equal(el('variant').value,'switch');assert.match(el('weakest-note').textContent,/WEAT/);
el('era').value='early';el('weakest').onclick();assert.equal(el('symbol').value,'MCHI');assert.equal(el('variant').value,'slope');el('era').value='late';el('weakest').onclick();
assert.deepEqual(Array.from(run('variants')),['slope','switch','context']);
assert.equal(run('symbols.length'),52);assert.equal(run('Object.keys(DATA.charts).length'),306);
assert.equal(run('Object.keys(DATA.models).length'),102);
assert.match(el('variant').innerHTML,/Continuous slopes/);assert.doesNotMatch(el('variant').innerHTML,/selected|baseline|coupled|independent/);
let cases=0;
for(const era of ['late','early']){el('era').value=era;for(const symbol of run('symbols')){el('symbol').value=symbol;for(const variant of run('variants')){el('variant').value=variant;run('choose()');for(const id of ['comparison','stress','pool','families','portfolio','chart','readout','parameters','recommended','weakest-note'])assert.doesNotMatch(el(id).innerHTML+el(id).textContent,/NaN|undefined|Infinity/);cases++;}}}
for(const key of run('Object.keys(DATA.charts)')){const [symbol,era,variant]=key.split('_');el('symbol').value=symbol;el('era').value=era;el('variant').value=variant;run('choose()');assert.match(el('chart').innerHTML,/<svg/);assert.match(el('parameters').innerHTML,/Training ends/);assert.match(el('chart').innerHTML,/Audited raw volume/);assert(run('chart().volume.length===chart().days.length && chart().volume.every(v=>Number.isFinite(v) && v>0)'));assert.match(el('recommended').textContent,/Training choice/);assert.match(el('parameters').innerHTML,/λL/);for(const i of [0,Number(el('cursor').max)]){el('cursor').value=i;run('readout()');assert.doesNotMatch(el('readout').textContent,/NaN|undefined|Infinity/);}if(variant!=='slope')assert.match(el('parameters').innerHTML,/transition matrix/);}
assert.equal(run('Object.keys(DATA.charts).filter(k=>k.includes("_late_")).length'),156);
assert.equal(run('Object.keys(DATA.charts).filter(k=>k.includes("_early_")).length'),150);
el('symbol').value='TLT';el('era').value='late';el('variant').value='context';run('choose()');assert.match(el('start').value,/2021/);
el('event-2023').onclick();assert.equal(el('start').value,'2023-09-01');assert.equal(run('chart().days[visible[0]]'),'2023-09-01');el('date').value='2023-10-21';el('date').onchange();assert.match(el('readout').textContent,/2023-10-23/);
el('chart').onclick({clientX:70});el('chart').onclick({clientX:1070});assert.match(el('selection').value,/2023-09-01 to 2024-03-28/);
el('start').value='2024-04-01';el('zoom').onclick();assert.match(el('status').textContent,/start date/);el('reset').onclick();assert.match(el('start').value,/2021/);
el('start').value='2021-01-01';el('end').value='2021-12-31';el('zoom').onclick();assert.match(el('chart').innerHTML,/Price context only/);assert.doesNotMatch(el('chart').innerHTML,/NaN|Infinity/);
assert(run('chart().slow_slope.every((v,i)=>chart().days[i]>=chart().evaluation_start||v===null)'));
el('era').value='early';el('symbol').value='XLC';run('choose()');assert.match(el('chart').innerHTML,/No chart/);
// Row navigation keeps the inspected model, rather than silently changing it.
el('era').value='late';el('variant').value='switch';el('pool').onclick({target:{closest:s=>s==='[data-symbol]'?{dataset:{symbol:'GLD'}}:null}});assert.equal(el('symbol').value,'GLD');assert.equal(el('variant').value,'switch');assert.match(el('chart').innerHTML,/<svg/);
console.log(JSON.stringify({status:'passed',cases,charts:run('Object.keys(DATA.charts).length'),checks:'Exactly three model choices; every ETF/era/model; actual parameters; custom dates, weekend snap, two-click selection, context-only dates, unavailable history and row navigation. No browser-layout claim.'}));
