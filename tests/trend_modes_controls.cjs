const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/trend-modes-20261025-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1],code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,src:'',scrollIntoView(){}});return elements.get(id);}
el('report-data').textContent=data;el('era').value='late';el('variant').value='selected';el('domain').value='both';el('window').value='all';
const headers=[...html.matchAll(/<th data-sort="([^"]+)"/g)].map(m=>({dataset:{sort:m[1]}}));
const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return headers;}}});vm.runInContext(code,context,{timeout:10000});const run=s=>vm.runInContext(s,context,{timeout:20000});
assert.equal(run('filtered().length'),104);
for(const era of ['late','early']){el('era').value=era;el('era').onchange();for(const variant of ['selected','regression_price','regression_volume','structure_price','structure_volume','average_price','average_volume']){el('variant').value=variant;el('variant').onchange();assert.equal(run('filtered().length'),era==='late'?104:100);for(const h of headers){h.onclick();assert.doesNotMatch(el('rows').innerHTML,/NaN|undefined|Infinity/);}for(const k of run('filtered().map(r=>r.symbol+"_"+r.domain)')){run(`choose(${JSON.stringify(k)})`);for(const id of ['comparison','parameters','trades','stress'])assert.doesNotMatch(el(id).innerHTML,/NaN|undefined|Infinity/);}}}
el('era').value='early';el('era').onchange();run('choose("XLC_short")');assert.match(el('chosen').textContent,/Insufficient/);assert.equal(el('chart-area').hidden,true);
el('era').value='late';el('variant').value='selected';el('era').onchange();for(const k of run('Object.keys(DATA.charts)')){run(`choose(${JSON.stringify(k)})`);assert.equal(el('chart-area').hidden,false);for(const w of ['all','2023','2024','2025','2026']){el('window').value=w;el('window').onchange();assert.match(el('chart').innerHTML,/<svg/);assert.doesNotMatch(el('chart').innerHTML,/NaN|undefined|Infinity/);}}
el('search').value='gld';el('search').oninput();assert.equal(run('filtered().length'),2);el('domain').value='long';el('domain').onchange();assert.equal(run('filtered().length'),1);
el('search').value='zzzz';el('search').oninput();assert.equal(run('filtered().length'),0);
console.log(JSON.stringify({status:'passed',checks:'Both eras,7 variants,1428 detail records,sorting/search/domain/missing histories; no browser-layout claim',chartWindows:run('Object.keys(DATA.charts).length')*5}));
