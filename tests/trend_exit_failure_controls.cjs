const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/trend-exit-failure-review-20261023-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,src:'',scrollIntoView(){}});return elements.get(id);}
el('report-data').textContent=data;el('era').value='late';el('order').value='loss';
const context=vm.createContext({document:{getElementById:el}});vm.runInContext(code,context,{timeout:10000});
const run=s=>vm.runInContext(s,context,{timeout:20000});
assert.equal(run('groups().length'),52);assert.equal(run('groups()[0].symbol'),'SLV');
assert.equal(el('trade').value,'3');assert.match(el('trade-note').textContent,/-13.57%/);
for(const era of ['late','early']){el('era').value=era;el('era').onchange();for(const order of ['loss','damage','missed','symbol']){el('order').value=order;el('order').onchange();assert.equal(run('groups().length'),era==='late'?52:50);assert.equal(run('groups().at(-1).symbol'),'BIL');assert.doesNotMatch(el('rows').innerHTML,/NaN|undefined|Infinity/);}for(const key of run('universe().map(r=>r.symbol+"_"+r.domain)')){run(`choose(${JSON.stringify(key)})`);for(const id of ['comparison','trades','years','stress','states'])assert.doesNotMatch(el(id).innerHTML,/NaN|undefined|Infinity/);}}
el('era').value='early';el('era').onchange();run('choose("XLC_short")');assert.match(el('rules').textContent,/Insufficient/);assert.equal(el('plot-area').hidden,true);
el('era').value='late';el('era').onchange();for(const key of run('DATA.focus')){run(`choose(${JSON.stringify(key)})`);assert.equal(el('plot-area').hidden,false);for(const value of ['all',...run(`DATA.details[${JSON.stringify(key)}].trades.map((_,i)=>String(i))`)]){el('trade').value=value;el('trade').onchange();assert.match(el('chart').innerHTML,/<svg/);assert.doesNotMatch(el('chart').innerHTML,/NaN|undefined|Infinity/);}}
el('search').value='slv';el('search').oninput();assert.equal(run('groups().length'),1);
el('search').value='zzzz';el('search').oninput();assert.equal(run('groups().length'),0);
el('search').value='';el('order').value='damage';el('order').onchange();assert.equal(run('groups()[0].symbol'),'SOXX');
console.log(JSON.stringify({status:'passed',checks:'52 ETFs, two eras, all204 detail records, rankings/search, all31 focus chart views; no browser-layout claim'}));
