const assert = require('node:assert/strict');
const vm = require('node:vm');
const html = require('node:fs').readFileSync(0, 'utf8');
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, {textContent: '', dataset: {}, hidden: false, attrs: {},
    setAttribute(k,v) {this.attrs[k] = v}, removeAttribute(k) {delete this.attrs[k]},
    addEventListener(_, handler) {this.click = handler}});
  return elements.get(id);
};
const full = {status: 'uploading', label: 'Uploading to NAS', tone: 'active', stage: 2,
  phase_at: '2026-10-07T04:00:00Z', interval_seconds: 3600, retry_seconds: 300,
  source_roots: ['<script>do-not-execute()</script>'], repository: '<img src=x>',
  last_success: {snapshot: 'a'.repeat(64), completed_at: '2026-10-07T03:00:00Z',
    captured_at: '2026-10-07T02:40:00Z', bytes_processed: 63e9, bytes_added_packed: 22e9,
    files_processed: 210000, verification: 'Manifest checked'},
  progress: {percent: 50, bytes_done: 50e9, total_bytes: 100e9, files_done: 1000}};
const db = {label: 'Published to NAS', tone: 'good', interval_seconds: 300, postgres: true, sqlite_count: 0};
let payload = {full, database: db, checked_at: '2026-10-07T04:00:00Z'};
let fail = false, tick, requests = 0;
const context = {document: {getElementById: get}, Date, Number, AbortSignal,
  fetch: async () => {requests++; if (fail) throw Error('offline'); return {ok:true, json:async () => payload}},
  setInterval: (fn, ms) => {assert.equal(ms, 5000); tick = fn}};
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInNewContext(script, context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await flush();
  assert.equal(get('backup-progress').hidden, false);
  assert.equal(get('backup-progress-bar').value, 50);
  assert.match(get('backup-progress-text').textContent, /processed/);
  assert.equal(get('backup-step-2').attrs['aria-current'], 'step');
  assert.match(get('backup-completed').textContent, /2026/);
  assert.equal(get('backup-roots').textContent, '<script>do-not-execute()</script>');
  assert.equal(get('backup-destination').textContent, 'Destination: <img src=x>');
  const completed = get('backup-completed').textContent;
  payload.full = {...full, status: 'copying_clickhouse', stage: 1, label: 'Copying ClickHouse capture locally', progress: null};
  await tick();
  assert.equal(get('backup-progress').hidden, true);
  assert.equal(get('backup-completed').textContent, completed);
  payload.full = {...full, status: 'deferred', label: 'Waiting to retry', tone: 'warning', stage: null,
    progress: null, next_at:'2026-10-07T04:05:00Z', next_kind:'retry', pending_capture_at:'2026-10-07T03:50:00Z'};
  await tick();
  assert.match(get('backup-current').textContent, /Automatic retry every 5 min/);
  assert.match(get('backup-current').textContent, /Retained local capture/);
  assert.equal(get('backup-step-2').className, '');
  fail = true;
  await tick();
  assert.equal(get('backup-status').textContent, 'Status unavailable');
  assert.equal(get('backup-db-status').textContent, 'Status unavailable');
  assert.equal(get('backup-progress').hidden, true);
  assert.equal(get('backup-completed').textContent, completed);
  assert.match(get('backup-refresh-status').textContent, /Refresh failed/);
  fail = false;
  payload.full = {...full, status:'complete', label:'Backup complete', tone:'good', stage:4, progress:null};
  await get('backup-refresh').click();
  assert.equal(get('backup-status').textContent, 'Backup complete');
  assert.equal(get('backup-step-4').className, 'done');
  assert.ok(requests >= 5);
})().catch(error => {console.error(error); process.exitCode = 1});
