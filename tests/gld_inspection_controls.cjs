// Exercise the saved offline chart without a browser or network access.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../research/gld-breakout-inspection-20261021-v1/index.html'), 'utf8');
const data = html.match(/<script id="inspection-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, {
    innerHTML:'', textContent:'', value:'', checked:false, handlers:{}, attrs:{},
    addEventListener(k,f){this.handlers[k]=f;}, setAttribute(k,v){this.attrs[k]=v;},
    getBoundingClientRect(){return {left:0,top:0,width:1200,height:610};},
    setPointerCapture(){}, scrollIntoView(){}, click(){},
  });
  return elements.get(id);
};
el('inspection-data').textContent=data;
el('domain').value='short';
['raw','activation','candles'].forEach(id=>{el(id).checked=true;});
let exported=null;
const context = vm.createContext({document:{getElementById:el,addEventListener(){},createElement(){return {click(){}};}},
  Blob:class {constructor(parts){exported=parts.join('');}},
  URL:{createObjectURL(){return 'blob:local-test';},revokeObjectURL(){}},setTimeout(fn){fn();}});
vm.runInContext(code, context, {timeout:10000});
function run(s){return vm.runInContext(s,context,{timeout:10000});}
function checkedChart(){assert.match(el('chart').innerHTML,/<svg|plot-clip/);assert.doesNotMatch(el('chart').innerHTML,/(?:NaN|undefined|Infinity)/);}
checkedChart();
assert.match(el('summary').innerHTML,/2023-03-13/);
assert.match(el('inspector').innerHTML,/2023-03-14/);
const total={};
for(const name of ['short','long']){
  el('domain').value=name;el('domain').handlers.change();
  const count=run('D.episodes.length');total[name]=count;
  for(let i=0;i<count;i++){run(`chooseTrade(${i})`);checkedChart();}
  for(const id of ['activation','decompose','trail','peak','candidate','candles']){el(id).checked=true;el(id).onchange();checkedChart();}
  el('late').onclick();checkedChart();assert.equal(el('from').value,'2023-01-03');
  el('all').onclick();checkedChart();
  el('csv').onclick();
  const rows=exported.split('\r\n');assert.equal(rows[0].split(',').length,24);assert.ok(rows.length>5000);
  assert.ok(rows.every(r=>r.split(',').length===24));
  for(let i=0;i<run('D.crossings.length');i++){
    el('crossing').value=String(i);el('crossFocus').onclick();checkedChart();
  }
  run('chooseTrade(D.episodes.find(e=>day(e.entry_index)>="2023").id)');
  const g=run('({left:geometry.left,right:geometry.right,lo,hi})');
  el('chart').handlers.pointerdown({clientX:g.left+100,pointerId:1});
  el('chart').handlers.pointerup({clientX:g.right-100,pointerId:1});
  assert.ok(run('hi-lo')<g.hi-g.lo);checkedChart();
  el('chart').handlers.pointermove({clientX:600});assert.match(el('inspector').innerHTML,/Effective exit level/);
  el('chart').handlers.pointerdown({clientX:600,pointerId:1});el('chart').handlers.pointerup({clientX:600,pointerId:1});
  assert.equal(run('pinned'),true);assert.match(el('inspector').innerHTML,/Pinned/);
}
console.log(JSON.stringify({status:'passed',trades:total,checks:'Both fits, every trade and crossing, chart geometry, all overlays, zoom, cursor, pin, CSV column alignment; no browser layout certification'}));
