const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync(0, 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    clientWidth: 1000, textContent: '', innerHTML: '', value: '',
    querySelector: () => null, addEventListener() {}, classList: { toggle() {} }
  });
  return elements.get(id);
}
const context = vm.createContext({ assert, document: { getElementById: element, querySelectorAll: () => [] } });
// Exercise the shipped functions without starting network requests or intervals.
vm.runInContext(script.slice(0, script.indexOf('document.querySelectorAll(".tab")')), context);
vm.runInContext(`
assert.equal(shiftDateText('2026-03-31', {months: -1}), '2026-02-28');
assert.equal(shiftDateText('2024-03-31', {months: -1}), '2024-02-29');
assert.equal(shiftDateText('2024-02-29', {years: -1}), '2023-02-28');
const points = normalizedPerformanceSeries([
  {trade_date:'2026-07-13',index:'100',nav_cnh:'1000'},
  {trade_date:'2026-07-14',index:'110',nav_cnh:'1100'},
  {trade_date:'bad',index:'110',nav_cnh:'1100'},
  {trade_date:'2026-07-15',index:'120',nav_cnh:'bad'}
]);
assert.equal(points.length, 2);
const account = normalizedPerformanceSeries([{trade_date:'2026-07-14', index:'100',nav_cnh:'200'}]);
const payload = {account_alignment_date:'2026-07-14', account_alignment_nav_cnh:'200', account_alignment_strategy_index:'110',strategy:points,account};
const all = performanceGeometry(points, account, payload), zoom = performanceGeometry([points[1]], account, payload);
assert.ok(Math.abs(all.strategyY(points[1]) - all.accountY(account[0])) < 1e-9);
assert.ok(Math.abs(zoom.strategyY(points[1]) - zoom.accountY(account[0])) < 1e-9);
assert.ok(Math.abs(all.leftMax / all.rightMax - zoom.leftMax / zoom.rightMax) < 1e-9);
for (const [s,a] of [[[],[]],[points,[]],[[],account],[[points[0]],[]]]) {
  assert.doesNotMatch(performanceSvg(s,a,payload), /NaN|Infinity|undefined/);
}
state.performance.rangeKey = 'all';
renderPerformance(payload);
assert.equal(el('perf-strategy-return').textContent, '10.00%');
assert.equal(el('perf-account-return').textContent, 'n/a');
state.performance.rangeKey = 'custom'; state.performance.start = state.performance.end = '2026-07-14';
renderPerformance(payload);
assert.equal(el('perf-strategy-return').textContent, 'n/a');
renderPerformance({strategy:[],account:[]});
assert.equal(el('performance-alignment').textContent, '');
assert.equal(el('perf-range-start').value, '');
assert.equal(el('performance-analysis').innerHTML, '');
const long = Array.from({length:5000}, (_,i) => ({trade_date:dateTextFromTime(Date.UTC(2012,0,1)+i*86400000), time:Date.UTC(2012,0,1)+i*86400000,index:100+i/100,nav_cnh:1000+i}));
const svg = performanceSvg(long, [], {});
assert.equal((svg.match(/class="strategy-dot"/g)||[]).length,1);
assert.doesNotMatch(svg, /NaN|Infinity/);
const gap = [{...points[0]}, {...points[1],time:points[0].time+10*86400000}];
assert.match(performanceSvg(gap,[],{}), /class="strategy-line" d="M [^"]+ M /);
`, context);
console.log('Operator performance behavior checks passed');
