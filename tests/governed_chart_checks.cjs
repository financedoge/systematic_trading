const assert = require('node:assert/strict');
const vm = require('node:vm');
const html = require('node:fs').readFileSync(0, 'utf8');
const elements = new Map(), requests = [], frames = new Map();
let frameId = 0;
function el(id) {
  if (!elements.has(id)) {
    const attrs = {}, selection = {setAttribute(k, v) {this[k] = v;}};
    elements.set(id, {
      value: '', textContent: '', innerHTML: '', dataset: {}, selectedOptions: [{text: 'Source close'}],
      classList: {add() {}, remove() {}}, setAttribute(k, v) {attrs[k] = v;}, attrs,
      querySelector(selector) {
        if (selector === '.zoom-selection') return selection;
        if (selector === 'svg' && this.innerHTML.includes('<svg')) return {
          getScreenCTM: () => ({inverse: () => ({})}),
          createSVGPoint: () => ({x: 0, y: 0, matrixTransform() {return this;}})
        };
        return null;
      },
      querySelectorAll: () => [], addEventListener() {}, focus() {},
      setPointerCapture(id) {this.capture = id;}, hasPointerCapture(id) {return this.capture === id;},
      releasePointerCapture() {this.capture = null;}
    });
  }
  return elements.get(id);
}
const DAY = 86400000, start = Date.parse('2000-01-01');
const date = i => new Date(start + i * DAY).toISOString().slice(0, 10);
const rows = Array.from({length: 101}, (_, i) => ({trade_date: date(i), adjusted_close: i + 10, raw_close: i + 100, quality_flags: []}));
const fixture = {
  audit: {symbol: 'TEST', name: 'Test', rows: 101, raw_rows: 101, status: 'available', gaps: [], sources: [{source_id: 'archive'}], overlaps: []},
  rows, comparisons: rows.map(r => ({...r, rebased_adjusted_close: r.adjusted_close})), next_after: null
};
const context = vm.createContext({
  assert, console, URL, URLSearchParams, setTimeout, Date,
  document: {getElementById: el, createElement: () => el('new'), querySelector: () => ({insertBefore() {}})},
  location: {href: 'http://localhost/?view=bars'}, history: {replaceState() {}},
  window: {addEventListener() {}},
  requestAnimationFrame: fn => {frames.set(++frameId, fn);return frameId;},
  cancelAnimationFrame: id => frames.delete(id),
  fetch: async url => {requests.push(url);return {ok: true, json: async () => url.includes('/audit?') ? {audit: fixture.audit} : fixture};}
});
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInContext(script.replace('})();', `window.test = {
  setWindow, resetWindow, render, renderCharts, applyDateWindow, load, loadSeries, setMode,
  state: () => ({viewport, extent, gesture, generation, page}),
  seed: (p,a) => {page=p;audit=a;extent=fullExtent();viewport=null;batch='batch';loadedSymbol='TEST';render()},
};})();`), context);
const api = context.window.test;
el('governed-basis').value = 'adjusted';el('governed-column').value = 'rebased_adjusted_close';
el('governed-symbol').value = 'TEST';el('governed-source').value = 'archive';
const seed = (data = fixture, audit = fixture.audit) => api.seed({...data, comparison_source: 'archive'}, audit);
const event = (x, extra = {}) => ({clientX: x, clientY: 100, pointerId: 1, button: 0, isPrimary: true, preventDefault() {}, ...extra});
const key = (host, name) => el(host).onkeydown({key: name, preventDefault() {}});
function drag(id, from, to, extra = {}) {
  const host = el(id);host.onpointerdown(event(from, extra));host.onpointermove(event(to, extra));host.onpointerup(event(to, extra));
}
const windowDates = () => (api.state().viewport || api.state().extent).map(t => new Date(t).toISOString().slice(0, 10)).join('/');
const line = (id, cls) => el(id).innerHTML.match(new RegExp('class="' + cls + '" d="([^"]*)"'))[1];
seed();
assert.equal(windowDates(), `${date(0)}/${date(100)}`);
assert.match(el('governed-window').textContent, /Full history/);
assert.equal(el('governed-start').value, '');
drag('governed-chart', 290, 740); // middle half: days 25..75
assert.equal(windowDates(), `${date(25)}/${date(75)}`);
for (const id of ['governed-chart', 'governed-source-chart']) {
  assert.ok(el(id).innerHTML.includes(`data-start="${date(25)}" data-end="${date(75)}"`));
  assert.match(el(id).innerHTML, />85<\/text>/); // y axis rescales to the visible window
}
assert.equal(el('governed-start').value, date(25));
assert.ok(!el('governed-records').innerHTML.includes(`<td>${date(24)}</td>`));
assert.ok(el('governed-records').innerHTML.includes(`<td>${date(25)}</td>`));
assert.equal(requests.length, 0); // navigation never refetches
api.resetWindow();drag('governed-source-chart', 740, 290);
assert.equal(windowDates(), `${date(25)}/${date(75)}`); // reverse drag on source also controls governed
drag('governed-chart', 400, 403);assert.equal(windowDates(), `${date(25)}/${date(75)}`); // accidental click
api.setMode('pan');drag('governed-chart', 515, 965);
assert.equal(windowDates(), `${date(0)}/${date(50)}`); // grab right moves to older history
drag('governed-chart', 515, 965);assert.equal(windowDates(), `${date(0)}/${date(50)}`); // clamp, keep width
drag('governed-chart', 965, 65);assert.equal(windowDates(), `${date(50)}/${date(100)}`);
api.setMode('zoom');drag('governed-chart', 515, 740, {shiftKey: true});
assert.equal(windowDates(), `${date(38)}/${date(88)}`);
const before = windowDates();
el('governed-chart').onpointerdown(event(515, {shiftKey: true}));el('governed-chart').onpointermove(event(800));
key('governed-chart', 'Escape');assert.equal(windowDates(), before);assert.equal(frames.size, 0);
el('governed-chart').onpointerdown(event(515));el('governed-chart').onpointermove(event(800));
el('governed-chart').onpointercancel(event(800));assert.equal(windowDates(), before);
assert.equal(api.state().gesture, null);
drag('governed-chart', 10, 800);assert.equal(windowDates(), before); // outside plot
drag('governed-chart', 515, 800, {button: 2});assert.equal(windowDates(), before);
key('governed-source-chart', 'ArrowLeft');assert.equal(windowDates(), `${date(28)}/${date(78)}`);
key('governed-source-chart', 'Home');assert.equal(api.state().viewport, null);
api.setMode('pan');drag('governed-chart', 515, 900);assert.equal(api.state().viewport, null); // full range cannot shift
el('governed-start').value = date(10);el('governed-end').value = date(12);api.applyDateWindow();
el('governed-basis').value = 'raw';el('governed-basis').onchange();assert.equal(windowDates(), `${date(10)}/${date(12)}`);
el('governed-start').value = date(12);el('governed-end').value = date(10);
assert.throws(() => api.applyDateWindow(), /on or before/);
el('governed-start').value = date(110);el('governed-end').value = date(120);
assert.throws(() => api.applyDateWindow(), /within the available/);
el('governed-start').value = date(10);el('governed-end').value = date(10);api.applyDateWindow();
assert.match(el('governed-chart').innerHTML, /<circle /);assert.doesNotMatch(el('governed-chart').innerHTML, /NaN|Infinity/);
// Neither null values nor audited missing sessions are bridged, including the orange overlay.
el('governed-basis').value = 'adjusted';
const gaps = rows.slice(0, 6).map(r => ({...r}));gaps[2].adjusted_close = null;
seed({rows: gaps, comparisons: gaps.map(r => ({...r, rebased_adjusted_close: r.adjusted_close}))}, {...fixture.audit, gaps: [date(4)]});
assert.equal((line('governed-chart', 'history-line').match(/M/g) || []).length, 2);
assert.equal((line('governed-chart', 'comparison-line').match(/M/g) || []).length, 2);
seed({rows: [rows[0], rows[5]], comparisons: []}, {...fixture.audit, gaps: [date(3)]});
assert.equal((line('governed-chart', 'history-line').match(/M/g) || []).length, 2);
el('governed-basis').value = 'raw';seed({rows: rows.map(r => ({...r, raw_close: null})), comparisons: []});
assert.equal(line('governed-chart', 'history-line'), '');assert.match(el('governed-chart').innerHTML, /No supported observations/);
api.setMode('zoom');drag('governed-chart', 290, 740);assert.equal(windowDates(), `${date(25)}/${date(75)}`); // still navigable across empty basis
seed({rows: [], comparisons: []});assert.equal(api.state().extent, null);assert.equal(el('governed-reset').disabled, true);
assert.doesNotMatch(el('governed-chart').innerHTML, /NaN|Infinity/);
// Source dates extend the full comparison range without hiding original observations.
seed({rows: rows.slice(20), comparisons: fixture.comparisons});assert.equal(windowDates(), `${date(0)}/${date(100)}`);
(async () => {
  seed();api.setWindow([start + 20 * DAY, start + 40 * DAY]);api.renderCharts();
  await api.loadSeries(api.state().generation);assert.equal(windowDates(), `${date(20)}/${date(40)}`);
  assert.ok(!requests.at(-1).includes('start_date'));assert.ok(!requests.at(-1).includes('end_date'));
  el('governed-symbol').value = 'NEW';const loading = api.load();
  assert.equal(el('governed-audit').textContent, '');assert.equal(el('governed-export').disabled, true);
  const loadGeneration = api.state().generation;
  el('governed-comparison').onsubmit({preventDefault() {}});
  assert.equal(api.state().generation, loadGeneration); // comparison cannot interrupt an underlying load
  await loading;
  assert.equal(api.state().viewport, null);assert.equal(el('governed-start').value, '');
  assert.equal(windowDates(), `${date(0)}/${date(100)}`);
  const current = api.state().page;await api.loadSeries(api.state().generation - 1);
  assert.equal(api.state().page, current); // stale response cannot override current view
  console.log('Governed chart navigation, synchronization, gaps, date controls and loading checks passed');
})().catch(error => {console.error(error);process.exitCode = 1;});
