const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('research/decision-review-20261028-v1/index.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1],elements={};
function el(id){return elements[id]||(elements[id]={value:'',innerHTML:'',textContent:'',events:{},addEventListener(k,f){this.events[k]=f},getBoundingClientRect(){return {left:0,width:1200}}})}
const sandbox={document:{getElementById:el},console};vm.createContext(sandbox);vm.runInContext(source,sandbox);
assert.equal(el('etf').value,'CPER');assert.equal(el('from').value,'2025-03-04');assert.equal(el('to').value,'2025-09-04');
let count=0;
for(const era of ['late','early']){
 el('era').value=era;vm.runInContext('selectCase(true)',sandbox);
 for(const symbol of vm.runInContext('symbols()',sandbox))for(const arm of ['baseline','stop','review']){
  el('etf').value=symbol;el('arm').value=arm;vm.runInContext('selectCase(true)',sandbox);
  assert(!el('chart').innerHTML.includes('NaN'),symbol+' '+era+' '+arm);
  assert(el('chart').innerHTML.includes('Adjusted OHLC'));assert(el('chart').innerHTML.includes('Audited raw ETF share volume'));
  assert(el('metrics').textContent.includes('Sharpe'));assert(el('learning').textContent.includes('accelerated review warnings'));
  assert(el('dependence').textContent.includes('Daily correlation'));assert(el('window').textContent.includes('not restarted'));count++;
 }
}
assert.equal(count,306);el('cper').events.click();assert.equal(el('era').value,'late');assert.equal(el('from').value,'2025-03-04');
el('chart').events.mousemove({clientX:85});assert(el('readout').textContent.includes('2025-03-04'));assert(el('readout').textContent.includes(' H '));
el('chart').events.click({clientX:85});el('chart').events.click({clientX:1170});assert.equal(el('to').value,'2025-09-04');
el('iwm').events.click();assert.equal(el('etf').value,'IWM');assert.equal(el('from').value,'2024-07-01');assert.equal(el('to').value,'2024-12-01');
assert(el('trades').innerHTML.includes('2024'));el('chart').events.mousemove({clientX:1170});assert(el('readout').textContent.includes('2024-11-29'));
el('from').value='2030-01-01';el('to').value='2030-02-01';vm.runInContext('render()',sandbox);assert(el('chart').innerHTML.includes('No sessions'));
for(const era of ['late','early']){el('era').value=era;vm.runInContext('selectCase(true)',sandbox);el('weakest').events.click();assert.equal(el('etf').value,vm.runInContext(`DATA.weakest.${era}.symbol`,sandbox));assert.equal(el('arm').value,'review')}
el('weat').events.click();assert.equal(el('etf').value,'WEAT');el('tlt').events.click();assert.equal(el('etf').value,'TLT');
console.log('306 ETF/era/arm charts; OHLC candles/readouts, exact dates, interval PnL, event/trade tables and four shortcuts passed.');
