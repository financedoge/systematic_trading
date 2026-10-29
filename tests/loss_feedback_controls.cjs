const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('research/loss-feedback-20261026-v1/index.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const elements={};
function el(id){return elements[id]||(elements[id]={value:'',innerHTML:'',textContent:'',events:{},
 addEventListener(name,fn){this.events[name]=fn},getBoundingClientRect(){return {left:0,width:1200}}})}
const sandbox={document:{getElementById:el},console};vm.createContext(sandbox);vm.runInContext(source,sandbox);
assert.equal(el('etf').value,'EWH');assert.equal(el('arm').value,'severity');
let count=0;
for(const era of ['late','early']){
 el('era').value=era;vm.runInContext('selectCase(true)',sandbox);
 const symbols=vm.runInContext('symbols()',sandbox);
 for(const symbol of symbols)for(const arm of ['fixed','streak','severity']){
  el('etf').value=symbol;el('arm').value=arm;vm.runInContext('selectCase(true)',sandbox);
  assert(!el('chart').innerHTML.includes('NaN'),symbol+' '+era+' '+arm);
  assert(el('chart').innerHTML.includes('Audited raw ETF share volume'));
  assert(el('metrics').textContent.includes('Sharpe'));
  count++;
 }
}
assert.equal(count,306);
el('weat').events.click();assert.equal(el('etf').value,'WEAT');assert.equal(el('era').value,'late');
el('arm').value='severity';vm.runInContext('render()',sandbox);
assert(el('trades').innerHTML.includes('2023-01-05'));
el('from').value='2023-01-07';el('to').value='2023-01-10';vm.runInContext('render()',sandbox);
assert.equal(vm.runInContext('visible.length',sandbox),2);
el('chart').events.mousemove({clientX:85});assert(el('readout').textContent.includes('2023-01-09'));
el('chart').events.click({clientX:85});el('chart').events.click({clientX:1170});
assert.equal(el('from').value,'2023-01-09');assert.equal(el('to').value,'2023-01-10');
el('from').value='2030-01-01';el('to').value='2030-01-31';vm.runInContext('render()',sandbox);
assert(el('chart').innerHTML.includes('No sessions'));
el('era').value='early';vm.runInContext('selectCase(true)',sandbox);el('weakest').events.click();
assert.equal(el('etf').value,'EWY');
console.log('306 charts, both weakest defaults, exact dates, hover, two-click interval and empty ranges verified.');
