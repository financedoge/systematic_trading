// Exercise the actual report's current-allocation renderer without network I/O.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const start = input.html.indexOf('function setupTrackedStrategy()');
const end = input.html.indexOf('function setupLegend()', start);
assert.ok(start > 0 && end > start);
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, {
    textContent: '', innerHTML: '', hidden: true, style: {},
    querySelector: () => ({style: {}}), setPointerCapture() {}
  });
  return elements.get(id);
};
const context = vm.createContext({
  report: input.report,
  document: {getElementById: get, querySelectorAll: () => []},
  fmtMoney: v => String(v), fmtPct: v => String(v), fmtNum: v => String(v),
  escapeHtml: v => String(v),
  AssetNames: {cell: () => '', name: s => s}
});
vm.runInContext(input.html.slice(start, end) + '\nsetupTrackedStrategy();', context);
assert.equal(get('currentStatePanel').hidden, false);
assert.match(get('currentWeightsTable').innerHTML, /Value USD/);
for (const id of ['calculationMeta', 'allocationMeta', 'currentWeightsTable', 'exposureMeta']) {
  const value = get(id).textContent + get(id).innerHTML;
  assert.doesNotMatch(value, /undefined|NaN/);
}
assert.match(get('exposureMeta').textContent, /Accounting currency: USD/);
