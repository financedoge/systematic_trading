const assert = require('node:assert/strict'), vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, {innerHTML:'', value:'0', textContent:'',
    classList:{toggle(){}}, querySelector:()=>({style:{}}), addEventListener(){}});
  return elements.get(id);
};
function context(html) {
  const ctx = vm.createContext({assert, el, document:{getElementById:el},
    esc:String, fmtMoney:String, fmtMaybeMoney:String, fmtPct:String, fmtMaybePct:String,
    fmtSignedPct:String, fmtSignedMoney:String, fmtMaybeBps:String, fmtDateTime:String});
  vm.runInContext(html.match(/<script id="asset-names-script">([\s\S]*?)<\/script>/)[1], ctx);
  return ctx;
}
function checkTable(id, expectedName='SPDR Gold Shares') {
  const html = el(id).innerHTML;
  assert.ok(html.includes(expectedName), `${id}: missing name`);
  const headers = html.match(/<thead>[\s\S]*?<\/thead>/)[0];
  assert.match(headers, /Asset name/);
  const width = [...headers.matchAll(/<th[ >]/g)].length;
  for (const row of html.match(/<tbody>([\s\S]*?)<\/tbody>/)[1].matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    assert.equal([...row[1].matchAll(/<td[ >]/g)].length, width, `${id}: shifted cells`);
  }
}
const op = context(input.operator);
vm.runInContext(`
assert.equal(AssetNames.name('GLD'), 'SPDR Gold Shares');
assert.equal(AssetNames.name(' spy '), 'SPDR S&P 500 ETF Trust');
assert.equal(AssetNames.name('Cash'), 'Cash balance');
assert.equal(AssetNames.name('MISSING'), 'Name unavailable');
assert.equal(AssetNames.name('__proto__'), 'Name unavailable');
assert.equal(AssetNames.name(''), '—');
assert.equal(AssetNames.cell('SPY'), '<td class="asset-name">SPDR S&amp;P 500 ETF Trust</td>');
assert.ok(!AssetNames.cell('X', '<img src=x onerror=alert(1)>').includes('<img'));
`, op);
// Run production render functions; values and ticker cells remain separate from labels.
for (const [start, end] of [
  ['function renderHoldings(', 'function renderLivePnl('],
  ['function renderLivePnl(', 'let livePnlLoading'],
  ['function renderOrders(', 'async function renderBrokerRecords('],
  ['function renderPnlTable(', 'function pnlHistorySvg('],
  ['function renderMissedOrdersTable(', 'function pnlComparisonSvg('],
]) {
  const index = input.operator.indexOf(start);
  vm.runInContext(input.operator.slice(index, input.operator.indexOf(end, index)), op);
}
vm.runInContext(`
const row={symbol:'GLD', quantity:42, target_weight:.35, account_quantity:42, strategy_weight:.35};
renderHoldings({rows:[row]}); renderOrders({orders:[row]}); renderTargets({targets:[row]});
renderPnlTable([row]); renderLivePnl({positions:[row]});
renderMissedOrdersTable([row]); renderExecutionSlippageTable([row]);
`, op);
for (const id of ['holdings-table', 'orders-table', 'targets-table', 'pnl-table', 'live-pnl-table',
                  'execution-missed-table', 'execution-slippage-table']) checkTable(id);
assert.match(el('orders-table').innerHTML, /<td>GLD<\/td><td class="asset-name">/);
assert.match(el('orders-table').innerHTML, />42<\/td>/);
assert.match(el('targets-table').innerHTML, />0.35<\/td>/);
const reportContext = context(input.report);
const script = [...input.report.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)]
  .map(match=>match[1]).find(script=>script.includes('const report ='));
vm.runInContext(script.slice(0, script.lastIndexOf('    setupHeader();')), reportContext);
vm.runInContext('setupTrackedStrategy(); renderContributions(); setupLegend();', reportContext);
for (const id of ['currentWeightsTable','usdForecasts','rollingForecasts','rollingStages','contributionTable']) checkTable(id);
assert.match(el('currentWeightsTable').innerHTML, /Cash balance/);
assert.match(el('currentWeightsTable').innerHTML, /35.00%/);
assert.match(el('currentWeightsTable').innerHTML, /CNH 12,345/);
assert.match(el('rollingFeatures').innerHTML, /SPDR Gold Shares/);
assert.match(el('legend').innerHTML, /GLD · SPDR Gold Shares/);
console.log('Name coverage, escaping, table alignment and unchanged portfolio values passed.');
