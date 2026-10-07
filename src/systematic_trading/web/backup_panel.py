"""System page backup panel; independent polling keeps NAS optional."""

BACKUP_PANEL_HTML = r'''
<style>
  #backup-panel { margin-bottom: 12px; }
  #backup-panel .panel-head { flex-wrap: wrap; }
  .backup-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(250px, 1fr); }
  .backup-main, .backup-db { padding: 16px; min-width: 0; }
  .backup-db { border-left: 1px solid var(--line-soft); background: #fbfcfd; }
  .backup-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
  #backup-panel h3 { margin: 0; font-size: 14px; font-weight: 650; }
  .backup-badge { padding: 4px 9px; border-radius: 5px; font-size: 12px; background: #eef2f7; color: #526079; }
  .backup-badge[data-tone="active"] { background: #eaf1ff; color: var(--focus); }
  .backup-badge[data-tone="good"] { background: #e6f4ef; color: var(--good); }
  .backup-badge[data-tone="warning"] { background: #fff3df; color: #835108; }
  .backup-steps { display: flex; list-style: none; margin: 18px 0 12px; padding: 0; gap: 5px; }
  .backup-steps li { flex: 1; border-top: 3px solid var(--line); padding-top: 7px; font-size: 12px; color: var(--muted); }
  .backup-steps li.done { border-color: var(--good); color: var(--good); }
  .backup-steps li.current { border-color: var(--focus); color: var(--focus); font-weight: 650; }
  .backup-copy { color: var(--muted); font-size: 12px; line-height: 1.6; margin: 8px 0; overflow-wrap: anywhere; }
  .backup-issue { color: #835108; }
  .backup-progress progress { width: 100%; height: 10px; accent-color: var(--focus); }
  .backup-facts { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 16px; margin: 16px 0 10px; }
  .backup-facts dt, .backup-db dt { color: var(--muted); font-size: 12px; margin-bottom: 5px; }
  .backup-facts dd, .backup-db dd { margin: 0; font-size: 13px; overflow-wrap: anywhere; }
  .backup-db dl { display: grid; gap: 14px; margin: 18px 0; }
  #backup-snapshot { font-family: Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }
  .backup-footer { padding: 10px 16px; border-top: 1px solid var(--line-soft); }
  .backup-footer summary { cursor: pointer; font-size: 12px; color: var(--focus); padding: 4px 0; }
  #backup-roots { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; }
  #backup-panel [hidden] { display: none !important; }
  @media (max-width: 800px) {
    .backup-grid { grid-template-columns: 1fr; }
    .backup-db { border-left: 0; border-top: 1px solid var(--line-soft); }
  }
  @media (max-width: 420px) { .backup-facts { grid-template-columns: 1fr; } }
</style>
<section id="backup-panel" class="panel" aria-labelledby="backup-heading">
  <div class="panel-head">
    <h2 id="backup-heading">Backups</h2>
    <div class="actions"><span class="status-line" id="backup-refresh-status">Loading backup status</span><button type="button" id="backup-refresh">Refresh backups</button></div>
  </div>
  <div class="backup-grid">
    <div class="backup-main">
      <div class="backup-title"><h3>Full-system recovery</h3><span class="backup-badge" id="backup-status" role="status">Loading</span></div>
      <ol class="backup-steps" aria-label="Full backup process">
        <li id="backup-step-0">Connect</li><li id="backup-step-1">Capture</li><li id="backup-step-2">Transfer</li><li id="backup-step-3">Verify</li><li id="backup-step-4">Complete</li>
      </ol>
      <p id="backup-current" class="backup-copy">Reading local worker status…</p>
      <div id="backup-progress" class="backup-progress" hidden>
        <progress id="backup-progress-bar" max="100" aria-label="Source data processed during transfer"></progress>
        <p id="backup-progress-text" class="backup-copy"></p>
      </div>
      <p id="backup-issue" class="backup-copy backup-issue" role="status" hidden></p>
      <dl class="backup-facts">
        <div><dt>Last completed on NAS</dt><dd id="backup-completed">No completed backup recorded</dd></div>
        <div><dt>Database capture completed</dt><dd id="backup-captured">—</dd></div>
        <div><dt>Source data in last backup</dt><dd id="backup-size">—</dd></div>
        <div><dt>New encrypted data stored</dt><dd id="backup-added">—</dd></div>
      </dl>
      <p id="backup-snapshot" class="backup-copy"></p>
      <p id="backup-verification" class="backup-copy"></p>
    </div>
    <aside class="backup-db" aria-label="Database checkpoint status">
      <div class="backup-title"><h3 id="backup-db-heading">Database checkpoints</h3><span id="backup-db-status" class="backup-badge">Loading</span></div>
      <p id="backup-db-schedule" class="backup-copy"></p>
      <dl>
        <div><dt>Last checkpoint result</dt><dd id="backup-db-checked">—</dd></div>
        <div><dt>Data revision</dt><dd id="backup-db-revision">—</dd></div>
        <div><dt>NAS copy confirmed</dt><dd id="backup-db-confirmed">—</dd></div>
      </dl>
      <p id="backup-db-generation" class="backup-copy"></p>
      <p id="backup-db-issue" class="backup-copy backup-issue" hidden></p>
    </aside>
  </div>
  <div class="backup-footer">
    <p id="backup-policy" class="backup-copy">NAS backups are optional. Local trading services continue when the NAS is unavailable.</p>
    <details>
      <summary>Coverage, destination &amp; recovery checks</summary>
      <p class="backup-copy">Native PostgreSQL, ClickHouse and NATS captures; application source, configuration, operational records, research, models, audited histories, source archives and referenced dependencies. Components are captured separately; this is an application recovery set, not a bootable disk image.</p>
      <p id="backup-destination" class="backup-copy"></p>
      <p class="backup-copy">Configured required roots:</p><pre id="backup-roots" class="backup-copy"></pre>
      <p class="backup-copy">Private credentials, the recovery key, caches and rebuildable dependencies are excluded. Keep the recovery key separately. A completed backup has passed repository metadata and capture-manifest checks; a full data scrub and restore drill are separate checks.</p>
      <p id="backup-heartbeat" class="backup-copy"></p>
    </details>
  </div>
</section>
<script>
(() => {
  const get = id => document.getElementById(id);
  const text = (id, value) => { get(id).textContent = value ?? '—'; };
  const time = value => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleString() : '—';
  };
  const bytes = value => {
    if (value == null || !Number.isFinite(value)) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let index = 0;
    while (value >= 1000 && index < units.length - 1) { value /= 1000; index++; }
    return `${value.toLocaleString(undefined, {maximumFractionDigits: 2})} ${units[index]}`;
  };
  const minutes = seconds => `${Math.round(seconds / 60)} min`;
  const badge = (id, label, tone) => {
    text(id, label);
    get(id).dataset.tone = ['good', 'active', 'warning', 'muted'].includes(tone) ? tone : 'muted';
  };
  function steps(stage) {
    for (let index = 0; index < 5; index++) {
      const element = get(`backup-step-${index}`);
      element.className = stage != null && (index < stage || stage === 4) ? 'done' : stage === index ? 'current' : '';
      if (index === stage) element.setAttribute('aria-current', 'step');
      else element.removeAttribute('aria-current');
    }
  }
  function render(payload) {
    const full = payload.full, db = payload.database, last = full.last_success;
    badge('backup-status', full.label, full.tone);
    steps(full.stage);
    let current = `Phase started ${time(full.phase_at)}.`;
    if (full.status === 'complete') current = 'The NAS snapshot passed verification.';
    if (full.status === 'deferred') current = `Automatic retry every ${minutes(full.retry_seconds)}. Local services continue.`;
    if (full.status === 'paused') current = 'Backup is paused. Automatic catch-up resumes when the backup worker is started again.';
    if (full.status === 'disabled') current = 'Full recovery backups are disabled in configuration.';
    if (full.status === 'stopped') current = 'No running backup worker was found. The last completed backup is shown below.';
    if (full.status === 'stale') current = 'The worker process exists, but its heartbeat is delayed. Current progress is unconfirmed.';
    if (full.status === 'unknown') current = 'Local backup status is missing or unreadable.';
    if (full.next_at) {
      const due = Date.parse(full.next_at) <= Date.parse(payload.checked_at);
      current += due ? ` Next ${full.next_kind} is due; worker checks every ${minutes(full.retry_seconds)}.` : ` Next ${full.next_kind} around ${time(full.next_at)}.`;
    }
    if (full.pending_capture_at && full.status !== 'complete') current += ` Retained local capture: ${time(full.pending_capture_at)}.`;
    text('backup-current', current);
    get('backup-progress').hidden = !full.progress;
    if (full.progress) {
      const progress = full.progress;
      const bar = get('backup-progress-bar');
      if (progress.percent == null) bar.removeAttribute('value');
      else bar.value = progress.percent;
      text('backup-progress-text', `${progress.stale ? 'Last reported: ' : ''}${bytes(progress.bytes_done)} of ${bytes(progress.total_bytes)} processed${progress.percent == null ? '' : ` (${progress.percent.toFixed(1)}%)`}. ${progress.files_done == null ? '' : progress.files_done.toLocaleString() + ' files. '}Source totals may grow during scanning; verification follows transfer.`);
    }
    text('backup-issue', full.issue);
    get('backup-issue').hidden = !full.issue;
    text('backup-completed', last ? time(last.completed_at) : 'No completed backup recorded');
    text('backup-captured', last ? time(last.captured_at) : '—');
    text('backup-size', last ? `${bytes(last.bytes_processed)}${last.files_processed == null ? '' : ' · ' + last.files_processed.toLocaleString() + ' files'}` : '—');
    text('backup-added', last ? bytes(last.bytes_added_packed) : '—');
    text('backup-snapshot', last ? `Snapshot ${last.snapshot}` : '');
    text('backup-verification', last ? last.verification : 'A transfer is only complete after its NAS verification passes.');
    badge('backup-db-status', db.label, db.tone);
    text('backup-db-heading', db.postgres && !db.sqlite_count ? 'PostgreSQL checkpoints' : 'Database checkpoints');
    text('backup-db-schedule', `Local checkpoint and optional NAS sync every ${minutes(db.interval_seconds)} after the previous attempt. Transfer time can extend this interval.`);
    text('backup-db-checked', time(db.checked_at));
    text('backup-db-revision', time(db.revision_at));
    text('backup-db-confirmed', db.nas_confirmed_at ? time(db.nas_confirmed_at) : 'Not confirmed by the latest attempt');
    text('backup-db-generation', db.nas_generation ? `Last known NAS generation ${db.nas_generation}` : 'No NAS generation recorded');
    text('backup-db-issue', db.issue);
    get('backup-db-issue').hidden = !db.issue;
    text('backup-policy', `NAS is optional; local trading services continue offline. Full recovery runs every ${minutes(full.interval_seconds)} with automatic ${minutes(full.retry_seconds)} retries while the worker is enabled and running. Reconnection resumes a retained capture or starts a fresh one.`);
    text('backup-destination', `Destination: ${full.repository}`);
    text('backup-roots', full.source_roots.join('\n') || 'Not configured');
    text('backup-heartbeat', `Worker heartbeat: ${time(full.heartbeat_at)}. All times are in your browser's local time zone.`);
    text('backup-refresh-status', `Updated ${time(payload.checked_at)} · every 5s`);
  }
  let loading = false;
  async function refresh() {
    if (loading) return;
    loading = true;
    get('backup-refresh').disabled = true;
    try {
      const response = await fetch('/api/v1/platform/backups', {cache: 'no-store', headers: {'Accept': 'application/json'}, signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    } catch (_) {
      badge('backup-status', 'Status unavailable', 'warning');
      badge('backup-db-status', 'Status unavailable', 'warning');
      steps(null);
      get('backup-progress').hidden = true;
      text('backup-current', 'Could not refresh backup status. Previously received completion records remain below.');
      text('backup-refresh-status', 'Refresh failed · retrying every 5s');
    } finally {
      loading = false;
      get('backup-refresh').disabled = false;
    }
  }
  get('backup-refresh').addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 5000);
})();
</script>
'''
