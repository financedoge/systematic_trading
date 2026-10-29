const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/multiscale-modes-20261025-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1],code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,src:'',max:'',scrollIntoView(){},setAttribute(){},select(){},querySelector(){return {getBoundingClientRect(){return {left:0,width:1140};}}}});return elements.get(id);}
el('report-data').textContent=data;el('era').value='late';el('window').value='all';el('cursor').value='0';
const headers=[...html.matchAll(/<th data-sort="([^"]+)"/g)].map(m=>({dataset:{sort:m[1]}}));
const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return headers;}}});vm.runInContext(code,context,{timeout:20000});const run=s=>vm.runInContext(s,context,{timeout:30000});
assert.equal(run('filtered().length'),52);let records=0,windows=0;
for(const era of ['late','early']){el('era').value=era;el('era').onchange();for(const variant of run('variants')){el('variant').value=variant;el('variant').onchange();assert.equal(run('filtered().length'),era==='late'?52:50);for(const h of headers){h.onclick();assert.doesNotMatch(el('rows').innerHTML,/NaN|undefined|Infinity/);}for(const symbol of run('filtered().map(r=>r.symbol)')){run(`choose(${JSON.stringify(symbol)})`);for(const id of ['comparison','parameters','trades','stress'])assert.doesNotMatch(el(id).innerHTML+el(id).textContent,/NaN|undefined|Infinity/);records++;}}}
for(const key of run('Object.keys(DATA.charts)')){const [symbol,era,...v]=key.split('_');el('era').value=era;el('variant').value=v.join('_');run(`choose(${JSON.stringify(symbol)})`);assert.equal(el('chart-area').hidden,false);for(const year of ['all',...(era==='late'?['2022','2023','2024','2025','2026']:['2020','2021','2022'])]){el('window').value=year;el('window').onchange();assert.match(el('chart').innerHTML,/<svg/);assert.doesNotMatch(el('chart').innerHTML,/NaN|undefined|Infinity/);windows++;}for(const i of [0,Number(el('cursor').max)]){el('cursor').value=String(i);el('cursor').oninput();assert.doesNotMatch(el('readout').textContent,/NaN|undefined|Infinity/);}}
el('era').value='early';el('variant').value='selected';run('choose("XLC")');assert.match(el('parameters').textContent,/Insufficient/);assert.equal(el('chart-area').hidden,true);
el('era').value='late';el('search').value='gld';el('search').oninput();assert.equal(run('filtered().length'),1);el('search').value='zzzz';el('search').oninput();assert.equal(run('filtered().length'),0);
console.log(JSON.stringify({status:'passed',records,charts:run('Object.keys(DATA.charts).length'),windows,checks:'Both eras, all variants, sort/search, all details, chart windows and cursor; no browser-layout claim'}));

el('era').value='late';el('variant').value='selected';run('choose("TLT")');el('window').value='all';run('plot()');
el('date-start').value='2023-09-01';el('date-end').value='2024-01-31';el('date-apply').onclick();assert.equal(el('window').value,'custom');assert.equal(run('DATA.charts[key()].days[visibleIndices[0]]'),'2023-09-01');assert.match(el('selection-text').value,/2023-09-01 to 2024-01-31/);
el('inspect-date').value='2023-10-21';el('inspect-date').onchange();assert.match(el('readout').textContent,/2023-10-23/);
el('chart').onclick({clientX:70});el('chart').onclick({clientX:1070});assert.match(el('selection-text').value,/2023-09-01 to 2024-01-31/);
el('date-start').value='2024-02-01';el('date-apply').onclick();assert.match(el('date-status').textContent,/start date/);
el('date-reset').onclick();assert.equal(el('window').value,'all');console.log('Exact date, weekend snapping, two-click interval, invalid-range and reset controls passed.');
