import json
import os
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from systematic_trading.config import AppSettings
from systematic_trading.domain import Currency, FXRate, PriceBar
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import extract_series, import_json_group, observation
from systematic_trading.research.market_data_view import StrategyMarketDataView
from systematic_trading.web.api import strategy_catalog, strategy_report, dashboard_performance


class MemoryAnalytics:
    def __init__(self):
        self.versions = {}
        self.rows = {}
        self.docs = {}
        self.writes = 0

    def latest(self, source):
        return self.versions.get(source)

    def publish(self, source, version, observations, documents=(), provenance=None):
        if (self.latest(source) or {}).get("version") == version:
            return False
        self.writes += 1
        self.rows[source] = observations
        self.docs[source] = documents
        self.versions[source] = dict(version=version, provenance=encode(provenance or {}),
                                     published_at="2026-09-26 00:00:00")
        return True

    def document(self, source, key):
        doc = next((d for d in self.docs.get(source, []) if d["point_key"] == key), None)
        return (doc, self.latest(source)) if doc else None

    def publication_index(self, prefix):
        return {key: value for key, value in self.versions.items() if key.startswith(prefix)}

    def publish_batch(self, sources):
        changed = False
        for source, version, rows, provenance in sources:
            changed |= self.publish(source, version, rows, provenance=provenance)
        return changed


def request(analytics, store=None):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(analytics=analytics, store=store)))


def test_strategy_http_reads_publication_without_touching_sources():
    analytics = MemoryAnalytics()
    analytics.publish("strategy-serving", "v1", [], [
        dict(point_key="catalog", payload=encode({"strategies": [{"strategy_id": "x"}]})),
        dict(point_key="report/x", payload="<html><body>saved result</body></html>"),
    ])
    # No settings, broker or filesystem store is available on this request.
    catalog = strategy_catalog(request(analytics))
    assert catalog["strategies"] == [{"strategy_id": "x"}]
    assert catalog["analytics"]["storage"] == "clickhouse"
    report = strategy_report("x", request(analytics))
    assert b"saved result" in report.body
    assert report.headers["x-analytics-version"] == "v1"
    with pytest.raises(HTTPException) as error:
        strategy_report("missing", request(analytics))
    assert error.value.status_code == 404


def test_initial_publication_missing_is_retryable_not_on_demand_recalculation():
    with pytest.raises(HTTPException) as error:
        strategy_catalog(request(MemoryAnalytics()))
    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == "5"


def test_account_reset_rejects_previously_published_performance():
    analytics = MemoryAnalytics()
    analytics.publish("dashboard-serving", "v1", [], [dict(point_key="performance", payload="{}")],
                      provenance={"baseline": "old-reset"})
    req = request(analytics, SimpleNamespace(latest_pnl_baseline=lambda: None))
    req.app.state.settings = AppSettings()
    with pytest.raises(HTTPException) as error:
        dashboard_performance(req)
    assert error.value.status_code == 503
    assert "baseline" in error.value.detail


def test_dated_rows_preserve_unknown_availability_and_nested_identities():
    data = {"nav_series": [{"trade_date": "2023-01-03", "nav_cnh": "100.000000000001"}],
            "features": {"SPY": {"2023-01-03": 7}},
            "fundamental": {"available_date": "2023-01-04", "period_end": "2022-12-31", "value": 5}}
    rows = extract_series(data, family="research", entity="strategy")
    assert len(rows) == 3
    nav = next(row for row in rows if row["point_key"] == "/nav_series/0")
    assert nav["available_at"] is None
    assert json.loads(nav["payload"])["nav_cnh"] == "100.000000000001"
    fundamental = next(row for row in rows if row["point_key"] == "/fundamental")
    assert fundamental["available_at"].startswith("2023-01-04")
    periods = extract_series([{"period": "2023"}, {"period": "2023-Q2"}, {"period": "2023-05"}],
                             family="metrics", entity="strategy")
    assert [row["observed_at"][:10] for row in periods] == ["2023-01-01", "2023-04-01", "2023-05-01"]


def test_dashboard_accepts_app_calculated_nav_without_legacy_extension(tmp_path, monkeypatch):
    from systematic_trading.web import api
    analytics = MemoryAnalytics()
    detail = dict(nav_series=[dict(trade_date="2026-09-25", nav_cnh="1250000")],
                  artifact_end_date="2026-09-25", warnings=[])
    analytics.publish("strategy-serving", "v1", [], [dict(
        point_key="detail/" + api.current_sota_definition().key, payload=encode(detail))])
    monkeypatch.setattr(api, "_account_nav_points", lambda *a: ([], None, None))
    monkeypatch.setattr(api, "_latest_market_data_date", lambda *a: date(2026, 9, 25))
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=AppSettings(data_dir=tmp_path), store=object(), strategy_analytics=analytics)))
    result = dashboard_performance(req)
    assert result.latest_strategy_data_date == date(2026, 9, 25)
    assert result.latest_strategy_nav_cnh == 1250000
    assert result.strategy_extension_count == 0


def test_failed_strategy_calculation_preserves_reports_and_other_projections(tmp_path, monkeypatch):
    from systematic_trading.research import analytics_service as module
    calls = []
    def failure(*args):
        raise ValueError("Invalid audited inputs")
    monkeypatch.setattr(module, "refresh_tracked_strategies", failure)
    for name in ("publish_strategies", "publish_dashboard", "import_json_group", "import_account_histories",
                 "import_transactional_histories", "import_lean_histories", "import_raw_market_data"):
        monkeypatch.setattr(module, name, lambda *args, label=name: calls.append(label))
    service = module.AnalyticsService(AppSettings(data_dir=tmp_path), object(), SimpleNamespace(initialize=lambda: None))
    status = service.refresh()
    assert status["errors"] == {"tracked-strategies": "Invalid audited inputs"}
    assert "publish_strategies" not in calls and "publish_dashboard" not in calls
    assert "import_account_histories" in calls and "import_transactional_histories" in calls


def test_file_import_is_idempotent_and_removed_rows_disappear(tmp_path):
    analytics = MemoryAnalytics()
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text('{"nav_series":[{"trade_date":"2023-01-03","nav_cnh":"1"}]}')
    second.write_text('{"nav_series":[{"trade_date":"2023-01-04","nav_cnh":"2"}]}')
    assert import_json_group(analytics, "test", [first, second], "research")
    assert len(analytics.rows["test"]) == 2
    assert not import_json_group(analytics, "test", [first, second], "research")
    first.write_text('{"nav_series":[{"trade_date":"2023-01-03","nav_cnh":"100"}]}')
    assert import_json_group(analytics, "test", [first], "research")
    assert len(analytics.rows["test"]) == 1
    assert "100" in analytics.rows["test"][0]["payload"]
    assert import_json_group(analytics, "test", [], "research")
    assert analytics.rows["test"] == []


def test_invalid_file_does_not_replace_previous_publication(tmp_path):
    analytics = MemoryAnalytics()
    path = tmp_path / "a.json"
    path.write_text('{"trade_date":"2023-01-03","nav_cnh":"1"}')
    import_json_group(analytics, "test", [path], "research")
    previous = analytics.latest("test")
    path.write_text('{"trade_date":')
    with pytest.raises(json.JSONDecodeError):
        import_json_group(analytics, "test", [path], "research")
    assert analytics.latest("test") == previous


def test_account_import_only_writes_new_captures_and_handles_deletion(tmp_path):
    from systematic_trading.research.analytics_projection import import_account_histories
    settings = AppSettings(data_dir=tmp_path)
    root = tmp_path / "live" / "account_snapshots"
    root.mkdir(parents=True)
    first = root / "one.json"
    first.write_text('{"as_of":"2026-09-24","cash":[],"positions":[]}')
    analytics = MemoryAnalytics()
    assert import_account_histories(settings, analytics)
    previous = analytics.writes
    assert not import_account_histories(settings, analytics)
    assert analytics.writes == previous
    (root / "two.json").write_text('{"as_of":"2026-09-25","cash":[],"positions":[]}')
    assert import_account_histories(settings, analytics)
    assert analytics.writes == previous + 2  # one capture plus readiness marker
    first.unlink()
    assert import_account_histories(settings, analytics)
    assert analytics.rows["account-history/one.json"] == []


def test_request_market_view_preserves_date_and_pair_bounds_and_refresh():
    day = date(2023, 1, 3)
    rates = [FXRate(rate_date=day + timedelta(days=i), base_currency=Currency.USD, rate=str(7 + i)) for i in range(3)]
    bars = [PriceBar(trade_date=r.rate_date, open=100, high=100, low=100, close=100, volume=1) for r in rates]
    calls = []

    def fx(base, **kwargs):
        calls.append((base, kwargs["quote_currency"]))
        return rates

    market = SimpleNamespace(list_fx_rates=fx, list_price_bars=lambda symbol: bars)
    view = StrategyMarketDataView(market)
    assert view.list_fx_rates(Currency.USD, end_date=day) == rates[:1]
    assert view.list_fx_rates(Currency.USD, start_date=day + timedelta(days=1)) == rates[1:]
    assert view.list_fx_rates(Currency.USD, end_date=day - timedelta(days=1)) == []
    assert len(calls) == 1
    view.list_fx_rates(Currency.USD, quote_currency=Currency.HKD)
    assert len(calls) == 2
    assert view.list_price_bars("spy", start_date=day, end_date=day) == bars[:1]
    rates = [FXRate(rate_date=day, base_currency=Currency.USD, rate="9")]
    assert StrategyMarketDataView(market).list_fx_rates(Currency.USD)[0].rate == 9
    assert view.list_fx_rates(Currency.USD)[0].rate == 7


def test_completed_session_cache_never_caches_current_time():
    from systematic_trading.daily_quality import completed_session, session_available_at
    day = date(2026, 9, 25)
    close = session_available_at(day)
    assert not completed_session(day, now=close - timedelta(seconds=1))
    assert completed_session(day, now=close)


@pytest.mark.skipif(os.getenv("ST_TEST_CLICKHOUSE") != "1", reason="Explicit disposable ClickHouse workspace required")
def test_clickhouse_verified_publication_replay_and_failure_isolation():
    analytics = AnalyticsStore.from_settings(AppSettings())
    analytics.workspace = "test-analytics-" + uuid4().hex
    analytics.initialize()
    rows = [observation("one", "strategy_nav", "test", {"trade_date": "2023-01-03", "nav_cnh": "100"}, "2023-01-03")]
    docs = [dict(point_key="catalog", media_type="application/json", payload='{"ok":true}')]
    execute = analytics.client.execute
    try:
        assert analytics.publish("test", "v1", rows, docs)
        assert not analytics.publish("test", "v1", rows, docs)
        assert json.loads(analytics.document("test", "catalog")[0]["payload"]) == {"ok": True}
        assert len(analytics.observations("test")) == 1

        def fail_commit(sql):
            if sql.startswith("INSERT INTO analytics.publications"):
                raise RuntimeError("simulated interrupted publication")
            return execute(sql)

        analytics.client.execute = fail_commit
        with pytest.raises(RuntimeError, match="interrupted"):
            analytics.publish("test", "v2", rows, docs)
        assert analytics.latest("test")["version"] == "v1"
        analytics.client.execute = execute
        assert analytics.publish("test", "v2", rows, docs)
        assert analytics.latest("test")["version"] == "v2"
        actual = analytics.query("SELECT lower(hex(SHA256(payload))) AS hash FROM analytics.observations FINAL WHERE "
                                 + analytics._where("test", "v2"))
        assert actual[0]["hash"] == digest(rows[0]["payload"])
        assert analytics.publish("test", "v3", [])
        assert analytics.observations("test") == []
        assert analytics.current_observations("test") == []
        query = analytics.query

        def corrupt_readback(sql):
            if "SHA256(payload)" in sql:
                return [{"point_key": "one", "hash": "wrong"}]
            return query(sql)

        analytics.query = corrupt_readback
        with pytest.raises(ValueError, match="readback mismatch"):
            analytics.publish("test", "v4", rows)
        analytics.query = query
        assert analytics.latest("test")["version"] == "v3"
        assert analytics.publish_batch([("batch/a", "v1", rows, {}), ("batch/b", "v1", [], {})])
        assert len(analytics.current_observations("batch/")) == 1
        assert analytics.latest("batch/b")["observation_count"] == 0
        older = observation("z", "pnl_snapshot", "account", {"created_at": "2026-09-25T10:00:00Z"}, "2026-09-25")
        newer = observation("a", "pnl_snapshot", "account", {"created_at": "2026-09-25T11:00:00Z"}, "2026-09-25")
        analytics.publish("pnl", "v1", [older, newer])
        assert [r["point_key"] for r in analytics.observations("pnl", family="pnl_snapshot", limit=1)] == ["a"]
    finally:
        analytics.client.execute = execute
        for table in ("observations", "documents", "publications"):
            analytics.client.execute(f"ALTER TABLE analytics.{table} DELETE WHERE workspace='{analytics.workspace}' SETTINGS mutations_sync=1")
