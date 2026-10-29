// Offline report-control contract; no browser or network access.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/etf-breakout-failure-review-20261023-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',scrollIntoView(){}});return elements.get(id);}
el('report-data').textContent=data;el('domain').value='short';el('era').value='late';el('filter').value='all';
const headers=[...html.matchAll(/<th data-key="([^"]+)"/g)].map(m=>({dataset:{key:m[1]}}));
const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return headers;}}});
vm.runInContext(code,context,{timeout:10000});const run=s=>vm.runInContext(s,context,{timeout:10000});
assert.equal(run('filtered().length'),52);assert.match(el('detail-title').textContent,/IAT/);
for(const era of ['late','early']){el('era').value=era;el('era').onchange();for(const domain of ['short','long','both']){el('domain').value=domain;el('domain').onchange();assert.equal(run('filtered().length'),(era==='late'?52:50)*(domain==='both'?2:1));for(const header of headers){header.onclick();assert.doesNotMatch(el('rows').innerHTML,/NaN|undefined|Infinity/);}for(const k of run('filtered().map(key)')){run(`choose(${JSON.stringify(k)})`);assert.doesNotMatch(el('diagnosis').innerHTML,/NaN|undefined|Infinity/);}}}
el('era').value='late';el('domain').value='short';el('search').value='gld';el('search').oninput();assert.equal(run('filtered().length'),1);assert.match(el('rows').innerHTML,/GLD/);
el('search').value='';for(const filter of ['loss','lag','sharpe','sparse','weakfit']){el('filter').value=filter;el('filter').onchange();assert.ok(run('filtered().every(r=>r.era==="late"&&r.domain==="short")'));}
el('filter').value='all';el('domain').value='both';el('filter').onchange();assert.equal(run('filtered().length'),104);
run('choose("XLY_short")');assert.match(el('diagnosis').innerHTML,/armed the trail but still exited/);
el('era').value='early';el('domain').value='long';el('search').value='GLD';
el('weak').onclick({target:{closest(){return {dataset:{case:'IAT_short'}};}}});
assert.equal(el('era').value,'late');assert.equal(el('domain').value,'short');assert.equal(el('search').value,'');
assert.equal(run('filtered().length'),52);assert.match(el('detail-title').textContent,/IAT/);
console.log(JSON.stringify({status:'passed',rows:204,checks:'Both eras/domains, all available detail records, sorting, filters, null IC, GLD distinction and armed-but-ineffective exits; no browser-layout certification'}));
