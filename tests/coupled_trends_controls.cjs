const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/coupled-trends-20261025-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1],code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',setAttribute(){},select(){},querySelector(){return {getBoundingClientRect(){return {left:0,width:1140};}}}});return elements.get(id);}
el('report-data').textContent=data;el('era').value='late';
const context=vm.createContext({document:{getElementById:el}});vm.runInContext(code,context,{timeout:20000});const run=s=>vm.runInContext(s,context,{timeout:30000});
let cases=0;
for(const era of ['late','early']){el('era').value=era;for(const symbol of run('symbols')){el('symbol').value=symbol;for(const variant of run('variants')){el('variant').value=variant;run('choose()');for(const id of ['comparison','stress','pool','families','portfolio','chart','readout'])assert.doesNotMatch(el(id).innerHTML+el(id).textContent,/NaN|undefined|Infinity/);cases++;}}}
for(const key of run('Object.keys(DATA.charts)')){const [symbol,era,...variant]=key.split('_');el('symbol').value=symbol;el('era').value=era;el('variant').value=variant.join('_');run('choose()');assert.match(el('chart').innerHTML,/<svg/);for(const i of [0,Number(el('cursor').max)]){el('cursor').value=i;run('readout()');assert.doesNotMatch(el('readout').textContent,/NaN|undefined|Infinity/);}}
el('symbol').value='TLT';el('era').value='late';el('variant').value='selected';run('choose()');assert.match(el('start').value,/2021/);
el('event-2023').onclick();assert.equal(el('start').value,'2023-09-01');assert.equal(run('chart().days[visible[0]]'),'2023-09-01');el('date').value='2023-10-21';el('date').onchange();assert.match(el('readout').textContent,/2023-10-23/);
el('chart').onclick({clientX:70});el('chart').onclick({clientX:1070});assert.match(el('selection').value,/2023-09-01 to 2024-03-28/);
el('start').value='2024-04-01';el('zoom').onclick();assert.match(el('status').textContent,/start date/);el('reset').onclick();assert.match(el('start').value,/2021/);
el('start').value='2021-01-01';el('end').value='2021-12-31';el('zoom').onclick();assert.match(el('chart').innerHTML,/Price context only/);assert.doesNotMatch(el('chart').innerHTML,/NaN|Infinity/);
el('era').value='early';el('symbol').value='XLC';el('variant').value='selected';run('choose()');assert.match(el('chart').innerHTML,/No chart/);
console.log(JSON.stringify({status:'passed',cases,charts:run('Object.keys(DATA.charts).length'),checks:'All ETFs/eras/variants; custom intervals, weekend snap, two-click selection, context-only dates, unavailable history. No browser-layout claim.'}));
