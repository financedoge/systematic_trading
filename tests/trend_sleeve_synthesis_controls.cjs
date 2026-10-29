const fs=require('fs'),vm=require('vm'),assert=require('assert');
const h=fs.readFileSync('research/trend-sleeve-synthesis-20261029-v1/index.html','utf8');
const source=h.match(/<script>([\s\S]*)<\/script>/)[1],els={};
function el(id){return els[id]||(els[id]={value:'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const box={document:{getElementById:el},console};vm.createContext(box);vm.runInContext(source,box);
assert.equal(el('etf').value,'CORN');assert(el('chartmetrics').textContent.includes('Training cutoff'));
let chartCount=0;
for(const era of ['late','early']){el('era').value=era;vm.runInContext('choose()',box);for(const symbol of vm.runInContext('symbols()',box)){
 el('etf').value=symbol;vm.runInContext('choose()',box);assert(!el('chart').innerHTML.includes('NaN'));assert(el('chart').innerHTML.includes('Adjusted OHLC'));assert(el('parameters').textContent.includes('fast_hmm'));chartCount++;
}el('weakest').events.click();assert.equal(el('etf').value,era==='late'?'CORN':'MCHI')}
assert.equal(chartCount,102);
let allocationCount=0;
for(const n of [6,10,15,20,30])for(const k of ['equal','risk']){el('n').value=String(n);el('weight').value=k;vm.runInContext('rankTable()',box);assert(el('allocation').textContent.includes('not optimized'));assert(el('rankrows').innerHTML.includes('selected'));allocationCount++}
el('era').value='late';el('etf').value='CORN';vm.runInContext('choose()',box);
el('chart').events.mousemove({clientX:500});assert(el('readout').textContent.includes(' H '));
el('chart').events.click({clientX:300});el('chart').events.click({clientX:600});assert(el('from').value<el('to').value);
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',box);assert(el('chart').innerHTML.includes('No complete'));
console.log(JSON.stringify({chart_combinations:chartCount,allocation_previews:allocationCount,date_hover_zoom:'passed'}));
