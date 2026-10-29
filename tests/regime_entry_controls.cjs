const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('research/regime-entry-20261027-v1/index.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1],elements={};
function el(id){return elements[id]||(elements[id]={value:'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const sandbox={document:{getElementById:el},console};vm.createContext(sandbox);vm.runInContext(source,sandbox);
const weakest=vm.runInContext('DATA.weakest',sandbox);assert.equal(el('etf').value,weakest.late.symbol);
let count=0;
for(const era of ['late','early']){
 el('era').value=era;vm.runInContext('selectCase(true)',sandbox);
 for(const symbol of vm.runInContext('symbols()',sandbox))for(const arm of ['control','hmm','guarded']){
  el('etf').value=symbol;el('arm').value=arm;vm.runInContext('selectCase(true)',sandbox);
  assert(!el('chart').innerHTML.includes('NaN'),symbol+' '+era+' '+arm);
  assert(el('chart').innerHTML.includes('Selected detector:'));
  assert(el('chart').innerHTML.includes('Audited raw ETF share volume'));
  assert(el('parameters').textContent.includes('Online policy learning is fixed'));
  assert(el('dependence').textContent.includes('Daily correlation'));
  assert.equal((el('regimes').innerHTML.match(/<tr>/g)||[]).length,3);count++;
 }
}
assert.equal(count,306);el('weat').events.click();assert.equal(el('etf').value,'WEAT');
el('from').value='2023-01-07';el('to').value='2023-01-10';vm.runInContext('render()',sandbox);
assert.equal(vm.runInContext('visible.length',sandbox),2);el('chart').events.mousemove({clientX:85});assert(el('readout').textContent.includes('2023-01-09'));
el('chart').events.click({clientX:85});el('chart').events.click({clientX:1170});assert.equal(el('from').value,'2023-01-09');assert.equal(el('to').value,'2023-01-10');
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',sandbox);assert(el('chart').innerHTML.includes('No sessions'));
el('era').value='early';vm.runInContext('selectCase(true)',sandbox);el('weakest').events.click();assert.equal(el('etf').value,weakest.early.symbol);
el('tlt').events.click();assert.equal(el('etf').value,'TLT');assert.equal(el('from').value,'2023-08-01');
el('inda').events.click();assert.equal(el('etf').value,'INDA');el('gold').events.click();assert.equal(el('era').value,'early');assert.equal(el('to').value,'2020-09-01');
console.log('306 chart combinations, date ranges/hover, diagnostics and four incident shortcuts verified.');
