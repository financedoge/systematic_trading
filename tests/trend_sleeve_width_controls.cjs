const fs=require('fs'),vm=require('vm'),assert=require('assert'),zlib=require('zlib');
const root='research/trend-sleeve-width-20261029-v1/';
const DATA=JSON.parse(zlib.gunzipSync(fs.readFileSync(root+'report-data.json.gz'))),els={};
function el(id){return els[id]||(els[id]={value:'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const box={document:{getElementById:el},console,DATA};vm.createContext(box);vm.runInContext(fs.readFileSync(root+'controls.js','utf8'),box);
assert.equal(el('width').value,'30');assert.equal(el('etf').value,'CPER');let charts=0,dates=0;
for(const n of ['15','20','30']){
 el('width').value=n;el('width').events.change();
 for(const era of ['late','early'])for(const arm of ['equal','risk','all']){
  el('era').value=era;el('pera').value=era;el('parm').value=arm;vm.runInContext('portfolioDates();choose()',box);
  for(const symbol of vm.runInContext('symbols()',box)){
   el('etf').value=symbol;vm.runInContext('choose()',box);assert(!el('chart').innerHTML.includes('NaN'));charts++;
  }
  el('worstcontributor').events.click();assert.equal(el('etf').value,DATA.attribution[era+'_'+arm+'_c5d0'][0].symbol);assert(el('actualfills').innerHTML.includes('<td>'));
  for(const d of DATA.portfolio[era+'_'+arm+'_c5d0'].decisions){el('pdate').value=d.date;vm.runInContext('portfolioTable()',box);assert(el('pinfo').textContent.includes(d.execution_date));assert(!el('pranks').innerHTML.includes('NaN'));dates++}
 }
}
assert.equal(charts,900);assert.equal(dates,513);
el('chart').events.mousemove({clientX:500});assert(el('readout').textContent.includes(' H '));
el('chart').events.click({clientX:300});el('chart').events.click({clientX:600});assert(el('from').value<el('to').value);
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',box);assert.equal(el('actualfills').innerHTML,'');
console.log(JSON.stringify({chart_combinations:charts,allocation_dates:dates,date_hover_zoom:'passed',scope:'offline DOM controls, not browser layout certification'}));
