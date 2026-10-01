"""Background analytical refresh, isolated from broker and approval workflows."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from threading import Event, Lock, Thread

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.analytics_projection import (
    file_signature, import_json_group, import_transactional_histories, import_lean_histories, observation,
    publish_strategies, publish_dashboard, import_account_histories,
)
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
    def __init__(self, settings, store, analytics):
        self.settings, self.store, self.analytics = settings, store, analytics
        self._stop, self._lock = Event(), Lock()
        self._wake = Event()
        self._thread = None
        self._account_thread = None
        self._archive_thread = None
        self._lane_errors = {}
        self._status = {"running": False, "last_completed_at": None, "errors": {}}
        self._strategy_inputs = {}

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
            completed = self._status.get("operations_completed_at")
            stale = not completed or (datetime.now(UTC) - datetime.fromisoformat(completed)).total_seconds() > max(300, self.settings.analytics_refresh_seconds * 3)
            started = self._status.get("research_job_started_at") or self._status.get("research_completed_at")
            budget = 7200 if self._status.get("research_job") == "tracked-strategies" else max(900, self.settings.analytics_refresh_seconds * 3)
            research_stale = bool(started and (datetime.now(UTC) - datetime.fromisoformat(started)).total_seconds() > budget)
            archive_started = self._status.get("archives_job_started_at") or self._status.get("archives_completed_at")
            archives_stale = bool(archive_started and (datetime.now(UTC) - datetime.fromisoformat(archive_started)).total_seconds() > max(3600, self.settings.analytics_refresh_seconds * 3))
            return {**self._status, "running": research and operations,
                    **freshness(self._strategy_inputs),
                    "research_running": research, "operations_running": operations,
                    "archives_running": archives, "archives_stale": archives_stale,
                    "operations_stale": stale, "research_stale": research_stale, "compute": compute}

    def start(self):
        self._thread = Thread(target=self._run, args=("research",), name="analytics-research", daemon=True)
        self._account_thread = Thread(target=self._run, args=("operations",), name="analytics-operations", daemon=True)
        self._archive_thread = Thread(target=self._run, args=("archives",), name="analytics-archives", daemon=True)
        self._account_thread.start()
        self._thread.start()
        self._archive_thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._account_thread:
            self._account_thread.join(timeout=5)
        if self._archive_thread:
            self._archive_thread.join(timeout=5)

    def request_refresh(self, *, reason="operator"):
        with self._lock:
            self._status.update(refresh_requested_at=datetime.now(UTC).isoformat(), refresh_reason=reason)
        self._wake.set()
        return {"queued": True, "owner": "application"}

    def refresh(self, lane="all"):
        self.analytics.initialize()
        if lane in {"all", "research"}:
            self._load_strategy_freshness()
        errors, changed = {}, []
        root = self.settings.data_dir
        jobs = [
            ("governed-publication", lambda: self._refresh_governed()),
            ("strategy-fx", lambda: refresh_tracked_fx(self.settings, self.store)),
            ("tracked-strategies", lambda: refresh_tracked_strategies(self.settings, self.store, self.analytics)),
            ("strategy-serving", lambda: publish_strategies(self.settings, self.store, self.analytics)),
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
        research = {"governed-publication", "strategy-fx", "tracked-strategies", "strategy-serving"}
        archives = {"research-history", "lean-history", "market-raw"}
        def owner(name):
            return "research" if name in research else "archives" if name in archives else "operations"
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
                # Clear a recovered dependency as soon as it succeeds, even
                # while the subsequent native calculations are still running.
                with self._lock:
                    self._lane_errors.get(lane, {}).pop(name, None)
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                if name in {"tracked-strategies", "strategy-serving"}:
                    self._load_strategy_freshness()
            except Exception as exc:
                errors[name] = str(exc)
                with self._lock:
                    self._lane_errors[lane] = dict(errors)
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
                # Never fall through to the legacy static SOTA marks if a
                # required monitored calculation failed on this refresh.
                # Other account/execution/raw-data projections can still refresh.
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
        return self.status()

    def _load_strategy_freshness(self):
        saved = self.analytics.latest("tracked-strategies/calculations")
        serving = self.analytics.latest("strategy-serving")
        inputs = json.loads(saved["provenance"]).get("inputs", {}) if saved else {}
        with self._lock:
            self._strategy_inputs = inputs
            self._status["strategy_serving_version"] = serving["version"] if serving else None

    def _run(self, lane):
        while not self._stop.is_set():
            if lane == "research":
                self._wake.clear()
            try:
                self.refresh(lane)
            except Exception as exc:
                with self._lock:
                    self._lane_errors[lane] = {lane + "_worker": str(exc)}
                    self._status["errors"] = {k:v for values in self._lane_errors.values() for k,v in values.items()}
            if lane != "research":
                self._stop.wait(max(300, self.settings.analytics_refresh_seconds) if lane == "archives" else self.settings.analytics_refresh_seconds)
            else:
                self._wake.wait(self.settings.analytics_refresh_seconds)

    def _refresh_governed(self):
        if not self.settings.governed_refresh_enabled:
            return False
        from systematic_trading.research.governed_refresh import refresh_governed_etfs
        return refresh_governed_etfs(self.settings, self.analytics)
