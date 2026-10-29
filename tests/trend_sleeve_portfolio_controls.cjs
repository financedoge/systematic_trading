const fs=require('fs'),vm=require('vm'),assert=require('assert'),zlib=require('zlib');
const root='research/trend-sleeve-portfolio-20261029-v1/';
const DATA=JSON.parse(zlib.gunzipSync(fs.readFileSync(root+'report-data.json.gz'))),els={};
function el(id){return els[id]||(els[id]={value:'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const box={document:{getElementById:el},console,DATA};vm.createContext(box);vm.runInContext(fs.readFileSync(root+'controls.js','utf8'),box);
assert.equal(el('etf').value,'TLT');let charts=0,decisions=0;
for(const era of ['late','early']){
 el('era').value=era;vm.runInContext('choose()',box);
 for(const symbol of vm.runInContext('symbols()',box)){
  el('etf').value=symbol;vm.runInContext('choose()',box);assert(!el('chart').innerHTML.includes('NaN'));assert(el('chart').innerHTML.includes('Adjusted OHLC'));charts++;
 }
 el('weakest').events.click();assert.equal(el('etf').value,era==='late'?'TLT':'MCHI');
 el('worstcontributor').events.click();assert.equal(el('etf').value,era==='late'?'IAT':'XLY');assert(el('actualfills').innerHTML.includes('signal'));
 for(const arm of ['equal','risk','all']){
  el('pera').value=era;el('parm').value=arm;vm.runInContext('portfolioDates()',box);
  const ds=DATA.portfolio[era+'_'+arm+'_c5d0'].decisions;
  for(const d of ds){el('pdate').value=d.date;vm.runInContext('portfolioTable()',box);assert(el('pinfo').textContent.includes(d.execution_date));assert(el('pranks').innerHTML.includes('selected'));assert(!el('pranks').innerHTML.includes('NaN'));decisions++;}
 }
}
assert.equal(charts,100);assert.equal(decisions,171);
el('chart').events.mousemove({clientX:500});assert(el('readout').textContent.includes(' H '));
el('chart').events.click({clientX:300});el('chart').events.click({clientX:600});assert(el('from').value<el('to').value);
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',box);assert(el('chart').innerHTML.includes('No complete'));assert.equal(el('actualfills').innerHTML,'');
console.log(JSON.stringify({chart_combinations:charts,allocation_dates:decisions,date_hover_zoom:'passed',scope:'offline DOM logic; not browser layout certification'}));
