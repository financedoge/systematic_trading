"""Background analytical refresh, isolated from broker and approval workflows."""
from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from threading import Event, Lock, Thread
from types import SimpleNamespace

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.analytics_projection import (
    file_signature, import_json_group, import_transactional_histories, import_lean_histories, observation,
    publish_strategies, publish_dashboard, import_account_histories,
)
from systematic_trading.research.signal_decay_job import refresh_signal_decay
from systematic_trading.research.tracked_runtime import refresh_tracked_strategies
from systematic_trading.research.tracked_freshness import freshness, refresh_tracked_fx


def import_raw_market_data(settings, analytics):
    from systematic_trading.recorders.market_data import load_storage_policy, RawMarketDataEnvelope, canonical_payload_hash
    policy = load_storage_policy(settings.market_data_storage_policy_path)
    # Preserve raw-first writes; analytical ingestion reads closed file snapshots.
    # Hot/archive copies dedupe on original raw_event_id within each daily source.
    paths = {}
    for root in (policy.hot_spool_root, policy.local_archive_root):
        if root and root.exists():
            for path in (root / "raw").rglob("*.jsonl"):
                if "_manifest" not in path.parts:
                    relative = path.relative_to(root / "raw").as_posix()
                    paths.setdefault(relative, []).append(path)
    pending = []
    index = analytics.publication_index("market-chunk/")
    for relative, files in sorted(paths.items()):
        before = file_signature(files)
        version, source_id = digest(encode(before)), "market-chunk/" + relative
        latest = index.get(source_id)
        if latest and latest["version"] == version:
            continue
        rows = {}
        for path in sorted(files):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = RawMarketDataEnvelope.model_validate_json(line)
                if canonical_payload_hash(record.payload) != record.payload_hash:
                    raise ValueError(f"Raw payload hash mismatch in {path}")
                # A source event can be received more than once with different
                # capture/provenance metadata. Keep each distinct envelope and
                # dedupe only byte-equivalent logical copies from hot/archive.
                payload = record.model_dump(mode="json")
                identity = record.raw_event_id + "/" + digest(encode(payload))
                row = observation(identity, "market_" + record.data_kind, record.symbol or "",
                                  record.model_dump(mode="json"), record.exchange_timestamp or record.received_at,
                                  record.available_at)
                rows[identity] = row
        if file_signature(files) != before:
            raise RuntimeError("Raw chunks changed during import; retaining committed version until retry")
        pending.append((source_id, version, list(rows.values()), {"files": before}))
    changed = int(analytics.publish_batch(pending))
    # Retire the initial daily projection layout, retaining its immutable
    # versions as migration evidence. Current readers use per-chunk publications.
    for source in analytics.publication_index("market-raw/"):
        changed += analytics.publish(source, "superseded-by-per-chunk-v1", [], provenance={"layout": "per_chunk_v1"})
    return changed


class AnalyticsService:
    def __init__(self, settings, store, analytics, *, alert_notifier=None):
        self.settings, self.store, self.analytics = settings, store, analytics
        self._stop, self._lock = Event(), Lock()
        self._wake = Event()
        self._operations_wake, self._archive_wake = Event(), Event()
        self._thread = None
        self._account_thread = None
        self._archive_thread = None
        self._spot_thread = None
        self._watchdog_thread = None
        self._watchdog_last_tick = None
        self._started_at = None
        self._lane_errors = {}
        self._status = {"running": False, "last_completed_at": None, "errors": {}}
        self._strategy_inputs = {}
        self._performance_payload = None
        from systematic_trading.live.alerts import AutomationAlertNotifier
        self.alert_notifier = alert_notifier or AutomationAlertNotifier(settings,
            event_store=store if hasattr(store, 'append_platform_event') else None,
            service_name='analytics-service')
        self._reported_issues = {}

    def _report_issue(self, name, message, *, severity='error'):
        with self._lock:
            changed = self._reported_issues.get(name) != message
            self._reported_issues[name] = message
        if changed:
            logger = logging.getLogger(__name__)
            (logger.warning if severity == 'warning' else logger.error)('%s: %s', name, message)
        try:
            delivered = self.alert_notifier.notify(SimpleNamespace(timestamp=datetime.now(UTC),
                event_type='analytics_'+name, status=severity, message=message,
                details={'service': 'analytics-service', 'job': name}))
        except Exception as exc:
            # A delivery failure is itself operator-visible; never hide it.
            logging.getLogger(__name__).exception('Could not persist analytics alert')
            with self._lock:
                self._status['alert_delivery_error'] = f'Analytics alert delivery failed: {exc}'
        else:
            if delivered is not False:
                with self._lock:
                    self._status.pop('alert_delivery_error', None)

    def _check_readiness(self):
        state = self.status()
        if state.get('strategy_stale'):
            self._report_issue('strategy_freshness', state['strategy_freshness_message']+
                ' New allocations and orders must wait for complete verified inputs. '
                'Inspect calculation errors and refresh after resolving the cause.', severity='warning')
        self._check_signal_decay()
        for lane in ('research', 'operations', 'archives'):
            if self._started_at and not state.get(lane+'_running'):
                self._report_issue(lane+'_stopped', f'{lane.title()} worker has stopped. '
                    'Restart the analytics service and verify a complete refresh; last published results are retained.')
            elif state.get(lane+'_stale') and not state.get(lane+'_initializing'):
                self._report_issue(lane+'_overdue', f'{lane.title()} worker has exceeded its progress deadline. '
                    'Inspect worker logs and retained replay evidence; last published results may be stale.')

    def _check_signal_decay(self):
        """Alert when a funded strategy's key signal is decaying or decayed.

        Decision support only: this raises an operator-visible warning and never
        changes an allocation, an approval or a broker record. Unfunded
        strategies are reported on the dashboard but do not raise an alert,
        because nothing is at risk until capital is committed.
        """
        from systematic_trading.portfolio.strategy_allocation import control_state
        from systematic_trading.research import signal_health
        try:
            data = signal_health.report(self.analytics)
            if not data:
                return
            rows = signal_health.health(data, control_state(self.store))
            for warning in signal_health.warnings(rows):
                self._report_issue(
                    'signal_decay_' + warning['strategy_key'],
                    f"Signal decay: {warning['message']} Monitored through the signal-decay "
                    "diagnostic on Strategy health. Review whether to switch or deallocate; no "
                    "allocation, approval or broker record has been changed.",
                    severity='warning')
        except Exception as exc:  # never let a diagnostic break readiness reporting
            self._report_issue('signal_decay_check',
                f'Signal-decay check failed: {type(exc).__name__}: {exc}', severity='warning')

    def _watchdog_tick(self, *, now=None):
        now = now or datetime.now(UTC)
        with self._lock:
            previous = self._watchdog_last_tick
            self._watchdog_last_tick = now
        if previous and (now-previous).total_seconds() > 90:
            message = (f'Analytics monitoring paused for {int((now-previous).total_seconds())} seconds '
                f'between {previous.isoformat()} and {now.isoformat()}. Host sleep or process suspension '
                'may have interrupted database connections. Awaiting successful research, operations '
                'and archive refreshes after resume; inspect service health if recovery fails.')
            with self._lock:
                self._status['interruption'] = dict(detected_at=now.isoformat(), message=message,
                    pending_lanes=['research', 'operations', 'archives'])
                self._lane_errors.setdefault('watchdog', {})['host-interruption'] = message
                self._status['errors'] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
            self._report_issue('host_interruption', message)
            for wake in (self._wake, self._operations_wake, self._archive_wake):
                wake.set()
        # Independent of refreshes: all lanes can be blocked and still raise
        # overdue alerts, without needing an HTTP status request.
        self._check_readiness()

    def _run_watchdog(self):
        while not self._stop.wait(15):
            try:
                self._watchdog_tick()
            except Exception as exc:
                with self._lock:
                    self._lane_errors.setdefault('watchdog', {})['watchdog'] = f'Analytics watchdog failed: {exc}'
                    self._status['errors'] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                self._report_issue('watchdog', f'Analytics watchdog failed: {exc}')
            else:
                with self._lock:
                    self._lane_errors.get('watchdog', {}).pop('watchdog', None)
                    self._status['errors'] = {k:v for values in self._lane_errors.values() for k,v in values.items()}

    def _complete_interruption_refresh(self, lane, started, errors):
        with self._lock:
            interruption = self._status.get('interruption')
            if (not interruption or errors or
                    started < datetime.fromisoformat(interruption['detected_at'])):
                return
            interruption['pending_lanes'] = [name for name in interruption['pending_lanes'] if name != lane]
            if not interruption['pending_lanes']:
                interruption['recovered_at'] = datetime.now(UTC).isoformat()
                self._lane_errors.get('watchdog', {}).pop('host-interruption', None)
                self._status['errors'] = {k:v for values in self._lane_errors.values() for k,v in values.items()}

    def performance_payload(self):
        """Immutable published inputs, cached by the background operations lane."""
        with self._lock:
            return self._performance_payload

    def status(self):
        compute = None
        try:
            compute = json.loads((self.settings.data_dir / "run/strategy-compute.json").read_text(encoding="utf8"))
        except (OSError, ValueError):
            pass
        with self._lock:
            research = bool(self._thread and self._thread.is_alive())
            operations = bool(self._account_thread and self._account_thread.is_alive())
            archives = bool(self._archive_thread and self._archive_thread.is_alive())
            now = datetime.now(UTC)
            completed = self._status.get("operations_completed_at")
            operations_budget = max(300, self.settings.analytics_refresh_seconds * 3)
            stale = not completed or (now - datetime.fromisoformat(completed)).total_seconds() > operations_budget
            initializing = bool(operations and not completed and self._started_at and
                (now-self._started_at).total_seconds() <= operations_budget)
            started = self._status.get("research_job_started_at") or self._status.get("research_completed_at") or self._started_at
            budget = 7200 if self._status.get("research_job") == "tracked-strategies" else max(900, self.settings.analytics_refresh_seconds * 3)
            research_stale = bool(started and (now - (datetime.fromisoformat(started) if isinstance(started, str) else started)).total_seconds() > budget)
            research_initializing = bool(research and not self._status.get('research_completed_at') and
                self._started_at and not research_stale)
            archive_started = self._status.get("archives_job_started_at") or self._status.get("archives_completed_at") or self._started_at
            archives_stale = bool(archive_started and (now - (datetime.fromisoformat(archive_started) if isinstance(archive_started, str) else archive_started)).total_seconds() > max(3600, self.settings.analytics_refresh_seconds * 3))
            archives_initializing = bool(archives and not self._status.get('archives_completed_at') and
                self._started_at and not archives_stale)
            errors = dict(self._status['errors'])
            if self._status.get('alert_delivery_error'):
                errors['alert-delivery'] = self._status['alert_delivery_error']
            return {**self._status, "errors": errors, "running": research and operations,
                    "spot_running": bool(self._spot_thread and self._spot_thread.is_alive()),
                    **freshness(self._strategy_inputs),
                    "research_running": research, "operations_running": operations,
                    "archives_running": archives, "archives_stale": archives_stale,
                    "archives_initializing": archives_initializing, "research_initializing": research_initializing,
                    "watchdog_running": self._watchdog_thread.is_alive() if self._watchdog_thread else None,
                    "watchdog_stale": bool(self._watchdog_last_tick and (now-self._watchdog_last_tick).total_seconds() > 90),
                    "operations_stale": stale, "operations_initializing": initializing,
                    "research_stale": research_stale, "compute": compute}

    def start(self):
        self._started_at = datetime.now(UTC)
        self._watchdog_last_tick = self._started_at
        self._thread = Thread(target=self._run, args=("research",), name="analytics-research", daemon=True)
        self._account_thread = Thread(target=self._run, args=("operations",), name="analytics-operations", daemon=True)
        self._archive_thread = Thread(target=self._run, args=("archives",), name="analytics-archives", daemon=True)
        self._spot_thread = Thread(target=self._run_spot, name="analytics-spot-cash", daemon=True)
        self._watchdog_thread = Thread(target=self._run_watchdog, name="analytics-watchdog", daemon=True)
        self._account_thread.start()
        self._thread.start()
        self._archive_thread.start()
        self._spot_thread.start()
        self._watchdog_thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        self._operations_wake.set()
        self._archive_wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._account_thread:
            self._account_thread.join(timeout=5)
        if self._archive_thread:
            self._archive_thread.join(timeout=5)
        if self._spot_thread:
            self._spot_thread.join(timeout=5)
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)

    def _run_spot(self):
        from systematic_trading.research.spot_performance import refresh_spot_cash
        while not self._stop.is_set():
            try:
                payload = self.performance_payload()
                refreshed = refresh_spot_cash(self.settings, payload)
                with self._lock:
                    if self._performance_payload is payload:
                        self._performance_payload = refreshed
                    self._lane_errors['spot'] = {}
            except (OSError, ValueError, KeyError) as exc:
                with self._lock:
                    self._lane_errors['spot'] = {'spot-cash': str(exc)}
            with self._lock:
                self._status['errors'] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
            self._stop.wait(5)

    def request_refresh(self, *, reason="operator"):
        with self._lock:
            self._status.update(refresh_requested_at=datetime.now(UTC).isoformat(), refresh_reason=reason)
        self._wake.set()
        self._operations_wake.set()
        self._archive_wake.set()
        return {"queued": True, "owner": "application"}

    def refresh(self, lane="all"):
        started = datetime.now(UTC)
        self.analytics.initialize()
        if lane in {"all", "research"}:
            self._load_strategy_freshness()
        with self._lock:
            errors = dict(self._lane_errors.get(lane, {}))
        errors.pop(lane + '_worker', None)
        changed = []
        root = self.settings.data_dir
        jobs = [
            ("governed-publication", lambda: self._refresh_governed()),
            ("research-etf-recorder", lambda: self._refresh_research_etfs()),
            ("strategy-fx", lambda: refresh_tracked_fx(self.settings, self.store)),
            ("tracked-strategies", lambda: refresh_tracked_strategies(self.settings, self.store, self.analytics)),
            ("strategy-serving", lambda: publish_strategies(self.settings, self.store, self.analytics)),
            # Independent of the tracked calculation: the decay diagnostic keeps
            # working even when a strategy refuses to compute, so a decayed
            # signal stays visible during a calculation failure.
            ("signal-decay", lambda: refresh_signal_decay(self.settings, self.analytics)),
            ("economic-recorder", lambda: self._refresh_economics()),
            ("positioning-recorder", lambda: self._refresh_positioning()),
            ("energy-recorder", lambda: self._refresh_energy()),
            ("issuer-etf-recorder", lambda: self._refresh_issuer_etfs()),
            ("research-history", lambda: import_json_group(self.analytics, "research-history",
                (root / "backtests").rglob("*.json"), "research")),
            ("account-history", lambda: import_account_histories(self.settings, self.analytics)),
            ("execution-benchmarks", lambda: import_json_group(self.analytics, "execution-benchmarks",
                (root / "execution_benchmarks").glob("*.json"), "execution_benchmark")),
            ("fx-observations", lambda: import_json_group(self.analytics, "fx-observations",
                (root / "market_data" / "fx_observations").glob("*.json"), "fx_observation")),
            ("transactional-history", lambda: import_transactional_histories(self.analytics, self.store)),
            ("dashboard-serving", lambda: publish_dashboard(self.settings, self.store, self.analytics)),
            ("lean-history", lambda: import_lean_histories(self.analytics, self.store)),
            ("market-raw", lambda: import_raw_market_data(self.settings, self.analytics)),
        ]
        research = {"governed-publication", "research-etf-recorder", "strategy-fx", "tracked-strategies", "strategy-serving", "signal-decay", "economic-recorder", "positioning-recorder", "energy-recorder", "issuer-etf-recorder"}
        archives = {"research-history", "lean-history", "market-raw"}
        def owner(name):
            return "research" if name in research else "archives" if name in archives else "operations"
        # Serve the last verified account publication promptly at startup; the
        # full capture import can take minutes. The builder still checks reset,
        # allocation and publication identities, and reruns after that import.
        warming = self._performance_payload is None
        if warming:
            jobs.insert(0, ('dashboard-serving', lambda: publish_dashboard(self.settings, self.store, self.analytics)))
        jobs.sort(key=lambda item: {"operations": 0, "research": 1, "archives": 2}[owner(item[0])])
        for name, job in jobs:
            if lane != "all" and owner(name) != lane:
                continue
            if self._stop.is_set():
                break
            if "tracked-strategies" in errors and name == "strategy-serving":
                continue
            try:
                with self._lock:
                    self._status[lane + "_job"] = name
                    self._status[lane + "_job_started_at"] = datetime.now(UTC).isoformat()
                    if lane in {"all", "research"}:
                        self._status["current_job"] = name
                if job():
                    changed.append(name)
                errors.pop(name, None)
                if name == 'dashboard-serving':
                    saved = self.analytics.document('dashboard-serving', 'performance')
                    payload = json.loads(saved[0]['payload']) if saved else None
                    with self._lock:
                        self._performance_payload = payload
                # Clear a recovered dependency as soon as it succeeds, even
                # while the subsequent native calculations are still running.
                with self._lock:
                    self._lane_errors.get(lane, {}).pop(name, None)
                    self._reported_issues.pop(name, None)
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                if name in {"tracked-strategies", "strategy-serving"}:
                    self._load_strategy_freshness()
            except Exception as exc:
                errors[name] = str(exc)
                logging.getLogger(__name__).exception('Analytics job %s failed', name)
                with self._lock:
                    if name == 'dashboard-serving':
                        self._performance_payload = None
                    self._lane_errors[lane] = dict(errors)
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                # Never fall through to the legacy static SOTA marks if a
                # required monitored calculation failed on this refresh.
                # Other account/execution/raw-data projections can still refresh.
                self._report_issue(name, f'{name} failed: {exc}. Last complete publication retained; '
                    'inspect the evidence and resolve the cause before refreshing calculations.')
        if lane in {"all", "research"}:
            self._load_strategy_freshness()
        with self._lock:
            self._lane_errors[lane] = errors
            self._status.update(last_completed_at=datetime.now(UTC).isoformat(),
                errors={k:v for values in self._lane_errors.values() for k,v in values.items()}, changed=changed)
            self._status[lane + "_completed_at"] = datetime.now(UTC).isoformat()
            self._status.pop(lane + "_job", None)
            self._status.pop(lane + "_job_started_at", None)
            if lane in {"all", "research"}:
                self._status.pop("current_job", None)
        if not self._stop.is_set():
            self._complete_interruption_refresh(lane, started, errors)
        self._check_readiness()
        return self.status()

    def _load_strategy_freshness(self):
        saved = self.analytics.latest("tracked-strategies/calculations")
        serving = self.analytics.latest("strategy-serving")
        inputs = json.loads(saved["provenance"]).get("inputs", {}) if saved else {}
        with self._lock:
            self._strategy_inputs = inputs
            self._status["strategy_serving_version"] = serving["version"] if serving else None

    def _run(self, lane):
        wake = {'research': self._wake, 'operations': self._operations_wake, 'archives': self._archive_wake}[lane]
        while not self._stop.is_set():
            wake.clear()
            try:
                self.refresh(lane)
            except Exception as exc:
                with self._lock:
                    self._lane_errors.setdefault(lane, {})[lane + "_worker"] = str(exc)
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                self._report_issue(lane+'_worker', f'{lane.title()} worker failed: {exc}. '
                    'The application will retry; inspect logs if this persists.')
            wake.wait(max(300, self.settings.analytics_refresh_seconds) if lane == "archives" else self.settings.analytics_refresh_seconds)

    def _refresh_governed(self):
        if not self.settings.governed_refresh_enabled:
            return False
        from systematic_trading.research.governed_refresh import refresh_governed_etfs
        return refresh_governed_etfs(self.settings, self.analytics)

    def _refresh_research_etfs(self):
        from systematic_trading.recorders.research_etfs import refresh_research_etfs
        return refresh_research_etfs(self.settings, self.analytics)

    def _refresh_economics(self):
        from systematic_trading.recorders.economics import refresh_economics
        return refresh_economics(self.settings, self.analytics)

    def _refresh_positioning(self):
        from systematic_trading.recorders.positioning import refresh_positioning
        return refresh_positioning(self.settings, self.analytics)

    def _refresh_energy(self):
        from systematic_trading.recorders.energy import refresh_energy
        return refresh_energy(self.settings, self.analytics)

    def _refresh_issuer_etfs(self):
        from systematic_trading.recorders.issuer_etfs import refresh_issuer_etfs
        return refresh_issuer_etfs(self.settings, self.analytics)
