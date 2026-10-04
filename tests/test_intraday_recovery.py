from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from systematic_trading.recorders.market_data import CapturedMarketDataBar, CaptureMode, IBMarketDataMode
from systematic_trading.recorders.recovery import RecoveryLedger, RecoveryWindow, WindowRecorder, recovery_windows, retention_floor


NOW = datetime(2026, 10, 4, 14, tzinfo=UTC)


def ledger(tmp_path, **kw):
    return RecoveryLedger(tmp_path / "recovery.json", identity={"environment": "paper"}, **kw)


def test_six_calendar_month_retention_including_month_end():
    assert retention_floor(NOW) == datetime(2026, 4, 4, 14, tzinfo=UTC)
    assert retention_floor(datetime(2026, 8, 31, tzinfo=UTC)) == datetime(2026, 2, 28, tzinfo=UTC)


def test_bootstrap_recovers_whole_available_history_and_preserves_expired_gaps(tmp_path):
    recovery = ledger(tmp_path)
    windows = recovery.plan(["SPY", "QQQ"], NOW)
    assert min(w.start.date() for w in windows) == date(2026, 4, 6)
    assert max(w.end.date() for w in windows) == date(2026, 10, 2)
    assert len(windows) > 1600
    recovery.plan(["SPY", "QQQ"], NOW + timedelta(days=5))
    assert "expired" in {r["status"] for r in recovery.data["windows"].values()}


def test_holidays_early_closes_dst_and_delayed_tail():
    windows = recovery_windows(["SPY"], date(2026, 11, 26), datetime(2026, 11, 27, 18, 19, tzinfo=UTC))
    assert len(windows) == 3
    assert windows[0].start.hour == 14
    assert windows[-1].end == datetime(2026, 11, 27, 17, 30, tzinfo=UTC)
    final = recovery_windows(["SPY"], date(2026, 11, 27), datetime(2026, 11, 27, 18, 20, tzinfo=UTC))
    assert len(final) == 4 and final[-1].expected_slots == 360
    assert recovery_windows(["SPY"], date(2026, 7, 3), datetime(2026, 7, 4, tzinfo=UTC)) == []


def test_checkpoint_resumes_full_windows_and_pacing_across_restart(tmp_path):
    recovery = ledger(tmp_path, start_date=date(2026, 10, 1))
    fetched = []
    def fetch(window):
        fetched.append(window)
        return {"completed": True, "slots": window.expected_slots}
    result = recovery.step(["SPY"], NOW, fetch, clock=lambda: NOW)
    assert result["windows_by_status"]["complete"] == 1
    assert fetched[0].start.date() == date(2026, 10, 2)
    resumed = ledger(tmp_path)
    resumed.step(["SPY"], NOW + timedelta(seconds=10), fetch)
    assert len(fetched) == 1
    resumed.step(["SPY"], NOW + timedelta(seconds=31), fetch, clock=lambda: NOW+timedelta(seconds=31))
    assert len(fetched) == 2 and fetched[1].start.date() == date(2026, 10, 1)
    assert fetched[0].key != fetched[1].key
    assert len((tmp_path / "recovery.attempts.jsonl").read_text().splitlines()) == 2


def test_crash_claim_is_paced_then_retried_and_never_considered_complete(tmp_path):
    recovery = ledger(tmp_path, start_date=date(2026, 10, 2))
    def crash(window):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        recovery.step(["SPY"], NOW, crash)
    resumed = ledger(tmp_path)
    assert resumed.summary(["SPY"], NOW)["windows_by_status"]["in_progress"] == 1
    assert resumed.next_window(["SPY"], NOW) is None
    # Replay may interleave the oldest backlog, but the claimed window is kept.
    assert resumed.next_window(["SPY"], NOW+timedelta(seconds=31)) is not None


@pytest.mark.parametrize("result,status", [
    ({"completed": False, "slots": 360, "errors": ["timeout"]}, "retry"),
    ({"completed": True, "slots": 359}, "source_partial"),
    ({"completed": True, "slots": 0}, "retry"),
])
def test_partial_timeout_and_empty_are_not_complete_and_other_symbols_progress(tmp_path, result, status):
    recovery = ledger(tmp_path, start_date=date(2026, 10, 2))
    summary = recovery.step(["SPY", "QQQ"], NOW, lambda window: result, clock=lambda: NOW)
    assert summary["windows_by_status"][status] == 1
    assert summary["windows_by_status"].get("complete", 0) == 0
    assert summary["pending_windows"] == summary["windows_total"]
    assert recovery.next_window(["SPY", "QQQ"], NOW+timedelta(seconds=31)).symbol == "QQQ"


def test_corrupt_or_mismatched_checkpoints_fail_without_reinitializing(tmp_path):
    recovery = ledger(tmp_path)
    recovery.save()
    original = recovery.path.read_bytes()
    with pytest.raises(ValueError, match="identity"):
        RecoveryLedger(recovery.path, identity={"environment": "live"})
    assert recovery.path.read_bytes() == original
    recovery.path.write_text("{")
    with pytest.raises(ValueError):
        ledger(tmp_path)


def test_ib_pacing_response_cools_all_symbols_across_restart(tmp_path):
    recovery = ledger(tmp_path, start_date=date(2026, 10, 2))
    recovery.step(["SPY", "QQQ"], NOW, lambda window: {
        "completed": False, "slots": 0, "errors": ["94001:162:Historical data pacing violation"]}, clock=lambda: NOW)
    assert ledger(tmp_path).next_window(["SPY", "QQQ"], NOW+timedelta(minutes=5)) is None
    assert ledger(tmp_path).next_window(["SPY", "QQQ"], NOW+timedelta(minutes=10)) is not None


def test_recovery_window_preserves_provenance_and_rejects_bad_source_time():
    window = RecoveryWindow("SPY", datetime(2026, 10, 2, 19, 30, tzinfo=UTC), datetime(2026, 10, 2, 20, tzinfo=UTC))
    stored = []
    recorder = WindowRecorder(SimpleNamespace(record_bar=stored.append), window)
    bar = CapturedMarketDataBar(symbol="SPY", exchange_timestamp=window.start, open=100, high=101,
        low=99, close=100, volume=5, capture_mode=CaptureMode.HISTORICAL_BACKFILL)
    recorder.record_bar(bar)
    assert len(recorder.slots) == 1
    assert stored[0].market_data_mode == IBMarketDataMode.UNKNOWN
    assert stored[0].received_at > window.end
    assert "ib_historical_recovery" in stored[0].quality_flags
    for changes in ({"exchange_timestamp":None}, {"exchange_timestamp":window.end}, {"symbol":"QQQ"},
                    {"exchange_timestamp":window.start+timedelta(seconds=1)}, {"bar_size_seconds":60}):
        with pytest.raises(ValueError):
            recorder.record_bar(bar.model_copy(update=changes))
    assert len(stored) == 1


def test_new_day_and_new_symbol_are_discovered_without_stream_failure(tmp_path):
    recovery = ledger(tmp_path, start_date=date(2026, 10, 2))
    before = recovery.summary(["SPY"], NOW)["windows_total"]
    later = datetime(2026, 10, 5, 20, 21, tzinfo=UTC)
    assert recovery.summary(["SPY", "QQQ"], later)["windows_total"] == before * 4


def test_raw_and_catalog_precede_batched_outbox_and_replay_is_idempotent(tmp_path):
    from systematic_trading.recorders import MarketDataRecorder, RawDataCatalog, RawMarketDataWriter
    from systematic_trading.recorders.recovery import RecoveryEventBatch
    from systematic_trading.storage.sqlite import SQLiteStore
    store = SQLiteStore(tmp_path / "test.db")
    store.initialize()
    batch = RecoveryEventBatch(store)
    catalog = RawDataCatalog(tmp_path / "raw", fsync=False)
    recorder = MarketDataRecorder(writer=RawMarketDataWriter(tmp_path / "raw", fsync=False),
        catalog=catalog, state_path=tmp_path / "state.json", state_interval_seconds=5)
    checked = WindowRecorder(recorder, RecoveryWindow("SPY", NOW, NOW+timedelta(hours=1)), event_batch=batch)
    bar = CapturedMarketDataBar(symbol="SPY", exchange_timestamp=NOW, open=100, high=101,
        low=99, close=100, volume=5, capture_mode=CaptureMode.HISTORICAL_BACKFILL)
    for _ in range(2):
        checked.record_bar(bar)
    assert len(catalog.query().entries) == 2
    assert store.list_pending_platform_events() == []
    assert recorder.events_appended == 0
    batch.flush()
    assert len(store.list_pending_platform_events()) == 1
    checked.record_bar(bar)
    batch.flush()
    assert len(store.list_pending_platform_events()) == 1


def test_outbox_failure_cannot_advance_recovery_checkpoint(tmp_path):
    from systematic_trading.recorders.recovery import RecoveryEventBatch
    def fail(events):
        raise OSError("database unavailable")
    recovery = ledger(tmp_path, start_date=date(2026, 10, 2))
    batch = RecoveryEventBatch(SimpleNamespace(append_platform_events=fail))
    def fetch(window):
        batch.append_platform_event("raw-already-durable")
        batch.flush()
        return {"completed": True, "slots": window.expected_slots}
    result = recovery.step(["SPY"], NOW, fetch, clock=lambda: NOW)
    assert result["windows_by_status"]["retry"] == 1
    assert "database unavailable" in result["last_result"]["errors"][0]
    assert batch.events == ["raw-already-durable"]


def test_concurrent_catalog_appends_keep_distinct_offsets_and_bounded_queries(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import json
    from systematic_trading.recorders import MarketDataRecorder, RawDataCatalog, RawMarketDataWriter
    def write(index):
        recorder = MarketDataRecorder(writer=RawMarketDataWriter(tmp_path, part_id=str(index), fsync=False),
            catalog=RawDataCatalog(tmp_path, fsync=False), state_path=tmp_path / f"state-{index}.json")
        recorder.record_bar(CapturedMarketDataBar(symbol="SPY", exchange_timestamp=NOW+timedelta(seconds=index*5),
            open=100, high=101, low=99, close=100, volume=5))
        return recorder.last_catalog_ref
    with ThreadPoolExecutor(max_workers=4) as executor:
        refs = list(executor.map(write, range(25)))
    assert len(set(refs)) == 25
    for ref in refs:
        path, offset = ref.rsplit("#offset=", 1)
        with open(path, "rb") as stream:
            stream.seek(int(offset))
            assert json.loads(stream.readline())["symbol"] == "SPY"
    catalog = RawDataCatalog(tmp_path)
    result = catalog.query(limit=3)
    assert result.matched_entries == 25 and len(result.entries) == 3
    assert result.entries[0].exchange_timestamp == NOW+timedelta(seconds=22*5)
    assert len(catalog.query(summarize=True).entries) == 1
    assert all(entry.bar_size_seconds == 5 for entry in result.entries)
