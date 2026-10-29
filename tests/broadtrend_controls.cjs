const fs=require('fs'),vm=require('vm'),assert=require('assert'),zlib=require('zlib');
const root='research/broadtrend-fr25-20261029-v1/';
const DATA=JSON.parse(zlib.gunzipSync(fs.readFileSync(root+'report-data.json.gz'))),els={};
function el(id){return els[id]||(els[id]={value:id==='book'?'broadtrend':'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const box={document:{getElementById:el},console,DATA};vm.createContext(box);vm.runInContext(fs.readFileSync(root+'controls.js','utf8'),box);
assert.equal(el('etf').value,'TLT');let charts=0;
for(const arm of ['broadtrend','blend']){
 el('book').value=arm;
 for(const symbol of vm.runInContext('symbols()',box)){
  el('etf').value=symbol;vm.runInContext('choose()',box);assert(!el('chart').innerHTML.includes('NaN'));assert(el('chart').innerHTML.includes('Adjusted OHLC'));charts++;
 }
}
el('lqd').events.click();assert.equal(el('etf').value,'LQD');assert.equal(el('book').value,'blend');assert(el('actualfills').innerHTML.includes('capital allocation'));
el('weakest').events.click();assert.equal(el('etf').value,'TLT');
el('chart').events.mousemove({clientX:500});assert(el('readout').textContent.includes(' H '));
el('chart').events.click({clientX:300});el('chart').events.click({clientX:600});assert(el('from').value<el('to').value);
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',box);assert(el('chart').innerHTML.includes('No complete'));assert.equal(el('actualfills').innerHTML,'');
assert.equal(charts,102);
console.log(JSON.stringify({chart_combinations:charts,date_hover_zoom:'passed',scope:'offline DOM logic; not browser layout certification'}));
