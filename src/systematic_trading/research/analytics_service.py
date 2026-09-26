"""Background analytical refresh, isolated from broker and approval workflows."""
from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Lock, Thread

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.analytics_projection import (
    file_signature, import_json_group, import_transactional_histories, import_lean_histories, observation,
    publish_strategies, publish_dashboard, import_account_histories,
)


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
        self._thread = None
        self._status = {"running": False, "last_completed_at": None, "errors": {}}

    def status(self):
        with self._lock:
            return {**self._status, "running": bool(self._thread and self._thread.is_alive())}

    def start(self):
        self._thread = Thread(target=self._run, name="analytics-projection", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def refresh(self):
        self.analytics.initialize()
        errors, changed = {}, []
        root = self.settings.data_dir
        jobs = [
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
        for name, job in jobs:
            if self._stop.is_set():
                break
            try:
                if job():
                    changed.append(name)
            except Exception as exc:
                errors[name] = str(exc)
        with self._lock:
            self._status = dict(running=bool(self._thread and self._thread.is_alive()),
                                last_completed_at=datetime.now(UTC).isoformat(), errors=errors, changed=changed)
        return self.status()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as exc:
                with self._lock:
                    self._status = dict(running=True, last_completed_at=None, errors={"worker": str(exc)})
            self._stop.wait(self.settings.analytics_refresh_seconds)
