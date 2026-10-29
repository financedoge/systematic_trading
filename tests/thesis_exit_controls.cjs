const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('research/thesis-exit-20261027-v1/index.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const elements={};
function el(id){return elements[id]||(elements[id]={value:'',innerHTML:'',textContent:'',events:{},
 addEventListener(name,fn){this.events[name]=fn},getBoundingClientRect(){return {left:0,width:1200}}})}
const sandbox={document:{getElementById:el},console};vm.createContext(sandbox);vm.runInContext(source,sandbox);
const weakest=vm.runInContext('DATA.weakest',sandbox);
assert.equal(el('etf').value,weakest.late.symbol);assert.equal(el('arm').value,'directional');
let count=0;
for(const era of ['late','early']){
 el('era').value=era;vm.runInContext('selectCase(true)',sandbox);
 const symbols=vm.runInContext('symbols()',sandbox);
 for(const symbol of symbols)for(const arm of ['control','thesis','directional']){
  el('etf').value=symbol;el('arm').value=arm;vm.runInContext('selectCase(true)',sandbox);
  assert(!el('chart').innerHTML.includes('NaN'),symbol+' '+era+' '+arm);
  assert(el('chart').innerHTML.includes('Audited raw ETF share volume'));
  assert(el('metrics').textContent.includes('Sharpe'));
  assert(el('chart').innerHTML.includes('Fast states: up'));
  assert(el('parameters').textContent.includes('Selected exit rule'));
  assert(el('chart').innerHTML.includes('Slow trend:'));
  assert.equal((el('grid').innerHTML.match(/<tr>/g)||[]).length,9);
  count++;
 }
}
assert.equal(count,306);
el('weat').events.click();assert.equal(el('etf').value,'WEAT');assert.equal(el('era').value,'late');
el('arm').value='directional';vm.runInContext('render()',sandbox);
el('from').value='2023-01-07';el('to').value='2023-01-10';vm.runInContext('render()',sandbox);
assert.equal(vm.runInContext('visible.length',sandbox),2);
el('chart').events.mousemove({clientX:85});assert(el('readout').textContent.includes('2023-01-09'));
assert(el('readout').textContent.includes('entry'));
el('chart').events.click({clientX:85});el('chart').events.click({clientX:1170});
assert.equal(el('from').value,'2023-01-09');assert.equal(el('to').value,'2023-01-10');
el('from').value='2030-01-01';el('to').value='2030-01-31';vm.runInContext('render()',sandbox);
assert(el('chart').innerHTML.includes('No sessions'));
el('era').value='early';vm.runInContext('selectCase(true)',sandbox);el('weakest').events.click();
assert.equal(el('etf').value,weakest.early.symbol);
el('inda').events.click();assert.equal(el('etf').value,'INDA');assert.equal(el('arm').value,'thesis');assert.equal(el('from').value,'2024-11-01');
el('gold').events.click();assert.equal(el('etf').value,'GLD');assert.equal(el('era').value,'early');assert.equal(el('to').value,'2020-09-01');
console.log('306 chart combinations, parameter tables, weakest defaults, date hover and range selection verified.');
