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
assert.equal(el('perf-strategy-return').textContent, '10.00%');
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
const comparison = {theoretical_contract:'v1',theoretical_base_nav_cnh:'1000',theoretical_periods:[],
  strategy:[{trade_date:'2026-10-01',index:100,nav_cnh:1000,is_theoretical:true,period_start:'2026-10-01'},
    {trade_date:'2026-10-02',index:110,nav_cnh:1100,is_theoretical:true,period_start:'2026-10-01'},
    {trade_date:'2026-10-05',index:132,nav_cnh:1320,is_theoretical:true,period_start:'2026-10-02'}],
  strategy_actual_rebased:[{trade_date:'2026-10-01',index:100,nav_cnh:1000,is_theoretical:true,period_start:'2026-10-01'},
    {trade_date:'2026-10-02',index:110,nav_cnh:1100,is_theoretical:true,period_start:'2026-10-01'},
    {trade_date:'2026-10-02',index:110,nav_cnh:900,is_theoretical:true,period_start:'2026-10-02',break_before:true},
    {trade_date:'2026-10-05',index:132,nav_cnh:1080,is_theoretical:true,period_start:'2026-10-02'}],
  account:[{trade_date:'2026-10-01',index:100,nav_cnh:1000},{trade_date:'2026-10-02',index:90,nav_cnh:900}]};
state.performance.rangeKey='all';
state.performance.rebaseMode='theoretical';
renderPerformance(comparison);
assert.equal(el('perf-strategy-return').textContent,'32.00%');
assert.equal(el('perf-strategy-nav').textContent,fmtMaybeMoney(1320));
assert.match(el('performance-chart').innerHTML,/theoretical P&L/i);
state.performance.rebaseMode='actual';
renderPerformance(comparison);
assert.equal(el('perf-strategy-return').textContent,'32.00%');
assert.equal(el('perf-strategy-nav').textContent,fmtMaybeMoney(1320));
assert.match(el('performance-chart').innerHTML,/class="strategy-line" d="M [^"]+ M /);
const s=normalizedPerformanceSeries(comparison.strategy_actual_rebased), a=normalizedPerformanceSeries(comparison.account);
const sameScale=performanceGeometry(s,a,comparison);
assert.equal(sameScale.strategyY(s[2]),sameScale.accountY(a[1]));
const tight=performanceGeometry([{...s[0],nav_cnh:1000034}],[{...a[0],nav_cnh:1000000}],{...comparison,theoretical_base_nav_cnh:1000000});
assert.ok(tight.leftMax-tight.leftMin<50,'P&L axis must not be padded by the full portfolio NAV');
assert.equal(filterPerformanceSeries(s,'2026-10-01','2026-10-02').at(-1).nav_cnh,1100);
assert.equal(filterPerformanceSeries(s,'2026-10-02','2026-10-05')[0].nav_cnh,900);
assert.equal(performanceStats('Strategy',s.slice(0,1)).totalReturn,0);
assert.equal(performanceStats('Strategy',[{...s[1],switch_anchor:true}]).totalReturn,0);
assert.equal(performanceStats('Strategy',[s[0],{...s[2],return_break:true}]).totalReturn,null);
const completed = {...comparison, spot_basis:{id:'v1'}};
const live = {status:'live', connected:true, performance:{basis_id:'v1',
  strategy:{trade_date:'2026-10-06',index:135,nav_cnh:1350,provisional:true,received_at:'2026-10-06T14:00:00Z',is_theoretical:true},
  account:{trade_date:'2026-10-06',index:95,nav_cnh:950,provisional:true,received_at:'2026-10-06T14:00:00Z'}}};
const firstPreview = performanceWithSpot(completed,live);
assert.equal(firstPreview.strategy.at(-1).nav_cnh,1350);
assert.equal(completed.strategy.at(-1).nav_cnh,1320,'Never mutate the daily publication');
live.performance.strategy.nav_cnh=1360;
const nextPreview=performanceWithSpot(completed,live);
assert.equal(nextPreview.strategy.length,firstPreview.strategy.length,'Replace the endpoint, never accumulate ticks');
assert.equal(nextPreview.strategy.at(-1).nav_cnh,1360);
assert.equal(performanceWithSpot(completed,{...live,status:'stale'}),completed);
assert.equal(performanceWithSpot(completed,{...live,performance:{basis_id:'new-reset'}}),completed);
const paused = retainSpotEndpoints({status:'stale',connected:false,checked_at:'2026-10-06T14:01:00Z',
  performance:{basis_id:'v1',strategy:null,account:null}},live);
assert.equal(paused.performance.strategy.stale,true);
assert.equal(performanceWithSpot(completed,paused).strategy.at(-1).nav_cnh,1360,'Keep the last endpoint explicitly stale, never bounce to the prior close');
assert.equal(retainSpotEndpoints({...paused,checked_at:'2026-10-07T14:01:00Z',performance:{basis_id:'v1',strategy:null}},live).performance.strategy,null);
state.performance.rangeKey='custom'; state.performance.start=state.performance.end='2026-10-05';
renderPerformance(completed);
assert.equal(el('perf-strategy-return').textContent,'32.00%','Cumulative return survives zooming and rebasing');
`, context);
console.log('Operator performance behavior checks passed');
