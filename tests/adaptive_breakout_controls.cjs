// Local DOM contract for the standalone report; does not automate a browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../research/adaptive-breakout-20261023-v1/index.html'),'utf8');
const data=html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',scrollIntoView(){}});return elements.get(id);}
el('report-data').textContent=data;el('domain').value='both';el('era').value='late';el('variant').value='joint_fit';
const headers=[...html.matchAll(/<th data-sort="([^"]+)"/g)].map(m=>({dataset:{sort:m[1]}}));
const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return headers;}}});
vm.runInContext(code,context,{timeout:10000});const run=s=>vm.runInContext(s,context,{timeout:20000});
assert.equal(run('filtered().length'),104);
for(const era of ['late','early']){
  el('era').value=era;el('era').onchange();
  for(const variant of ['baseline','exit_fit','trend_fit','range_fit','joint_fit','first_lower_control']){
    el('variant').value=variant;el('variant').onchange();
    assert.equal(run('filtered().length'),era==='late'?104:100);
    for(const header of headers){header.onclick();assert.doesNotMatch(el('rows').innerHTML,/NaN|undefined|Infinity/);}
    for(const k of run('filtered().map(r=>r.symbol+"_"+r.domain)')){
      run(`choose(${JSON.stringify(k)})`);
      for(const id of ['comparison','regimes','stress'])assert.doesNotMatch(el(id).innerHTML,/NaN|undefined|Infinity/);
    }
  }
}
el('era').value='early';el('era').onchange();run('choose("XLC_short")');assert.match(el('components').textContent,/Insufficient/);
el('era').value='late';el('variant').value='joint_fit';el('search').value='gld';el('search').oninput();assert.equal(run('filtered().length'),2);
el('domain').value='short';el('domain').onchange();assert.equal(run('filtered().length'),1);
console.log(JSON.stringify({status:'passed',checks:'Both eras, all6 variants,204 ETF/domain records per variant, sorting, search, missing histories, detail/regime/friction tables; no browser-layout claim'}));
