"""App-owned post-trade observation collection; no order or approval authority."""
from collections import Counter
from datetime import UTC, datetime
import logging
from pathlib import Path
from threading import Event, Lock, Thread

from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderType
from systematic_trading.execution.benchmark_qualification import publish_references
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.runtime_io import atomic_json


class ExecutionBenchmarkCollector:
    def __init__(self, settings, store, benchmarks, analytics=None):
        self.settings, self.store, self.benchmarks, self.analytics = settings, store, benchmarks, analytics
        self._stop, self._lock = Event(), Lock()
        self._thread = None
        self._state = dict(enabled=settings.execution_benchmark_collection_enabled, running=False,
                           checked_at=None, last_error=None, coverage=None, publication=None)

    def start(self):
        if not self.settings.execution_benchmark_collection_enabled or self._thread is not None:
            return
        self._thread = Thread(target=self._run, name="execution-benchmark-collector", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def status(self, *, include_orders=False):
        with self._lock:
            state = dict(self._state)
            if state.get("coverage") and not include_orders:
                state["coverage"] = {key: value for key, value in state["coverage"].items() if key != "orders"}
        state["running"] = bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
        return state

    def refresh(self, *, now=None):
        now = now or datetime.now(UTC)
        records = self.store.list_broker_order_records()
        # Recent fills first; durable retry cooldowns let older windows advance on later cycles.
        records.sort(key=lambda row: (row.order.intended_trade_date or row.updated_at.date(), row.local_order_id), reverse=True)
        rows, eligible = [], []
        for record in records:
            if self._stop.is_set():
                break
            if record.environment != OrderEnvironment.PAPER:
                continue
            item = dict(local_order_id=record.local_order_id, symbol=record.order.symbol,
                        currency=record.order.currency.value, order_type=record.order.order_type.value,
                        status=record.status.value, filled_quantity=record.filled_quantity,
                        execution_detail_status="quantity_complete" if record.execution_fills and
                        sum(fill.quantity for fill in record.execution_fills) == record.filled_quantity
                        and not record.execution_sync_issue else "incomplete",
                        original=None, routed=None, original_session=None, routed_session=None)
            if not record.filled_quantity:
                item["collection_status"] = "not_filled"
            elif record.broker != "interactive-brokers" or record.order.environment != OrderEnvironment.PAPER:
                item["collection_status"] = "unsupported_broker_environment"
            elif record.order.order_type != OrderType.TWAP:
                item["collection_status"] = "unsupported_order_type"
            elif record.execution_sync_issue:
                item["collection_status"] = "execution_review_required"
            elif record.order.currency != Currency.USD:
                item["collection_status"] = "unsupported_currency_contract"
            else:
                eligible.append((record, item))
                for name, original in (("original", True), ("routed", False)):
                    result = self.benchmarks.get(record, now=now, original_intent=original)
                    item[name] = {key: value for key, value in result.items() if key in {
                        "status", "message", "window_start", "window_end", "benchmark_key", "next_retry_at",
                        "observed_at", "coverage", "bar_count", "price_basis", "research_approved"}}
                item["collection_status"] = item["original"]["status"]
            rows.append(item)
        # Order windows have first use of the bounded queue. Session requests
        # share that queue and deduplicate across windows/orders on the same day.
        sessions = {}
        for record, item in eligible:
            for name, original in (("original_session", True), ("routed_session", False)):
                result = self.benchmarks.get_session(record, now=now, original_intent=original)
                item[name] = {key: value for key, value in result.items() if key in {
                    "status", "message", "window_start", "window_end", "benchmark_key", "next_retry_at"}}
                if result.get("benchmark_key"):
                    sessions[result["benchmark_key"]] = result
        rows.sort(key=lambda row: row["local_order_id"])
        windows = {}
        for row in rows:
            for name in ("original", "routed"):
                result = row[name]
                if result and result.get("benchmark_key"):
                    windows[result["benchmark_key"]] = result["status"]
        references = publish_references(self.settings, self.analytics, sessions)
        report = dict(version=2, scope="All retained paper orders; original/routed TWAP windows and regular sessions",
                      paper_order_count=len(rows), filled_order_count=sum(row["filled_quantity"] > 0 for row in rows),
                      order_status_counts=dict(Counter(row["collection_status"] for row in rows)),
                      window_status_counts=dict(Counter(windows.values())), unique_window_count=len(windows),
                      session_status_counts=dict(Counter(r["status"] for r in sessions.values())),
                      unique_session_count=len(sessions), reference_audit=references,
                      basis="Operational captures; separately published retrospective reference audits retain source limitations",
                      close_status=references["status"], session_vwap_status=references["status"], orders=rows)
        publication = None
        if self.analytics is not None:
            version = digest(encode(report))
            self.analytics.publish("execution-benchmark-coverage", version, [], [dict(
                point_key="coverage", media_type="application/json", payload=encode(report))],
                provenance=dict(format=1, role="post_trade_coverage", research_approved=False,
                                collector_source=digest(Path(__file__).read_bytes())))
            publication = dict(source_id="execution-benchmark-coverage", version=version)
        state = dict(enabled=True, checked_at=now.isoformat(), last_error=None, coverage=report, publication=publication)
        atomic_json(self.settings.data_dir / "run" / "execution_benchmark_collection.json", state)
        with self._lock:
            self._state = state
        return report

    def _run(self):
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as exc:
                logging.getLogger(__name__).exception("Execution benchmark collection cycle failed")
                with self._lock:
                    self._state.update(last_error=str(exc), checked_at=datetime.now(UTC).isoformat())
            self._stop.wait(self.settings.execution_benchmark_refresh_seconds)
