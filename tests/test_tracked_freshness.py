from datetime import UTC, date, datetime
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.research.tracked_freshness import freshness, refresh_tracked_fx


def test_daily_freshness_follows_completed_sessions_and_requires_fx():
    inputs = dict(price_through="2026-09-25", valuation_through="2026-09-25")
    assert not freshness(inputs, datetime(2026,9,28,15,tzinfo=UTC))["strategy_stale"]
    assert freshness(inputs, datetime(2026,9,28,22,tzinfo=UTC))["strategy_stale"]
    inputs["price_through"] = "2026-09-28"
    assert freshness(inputs, datetime(2026,9,28,22,tzinfo=UTC))["strategy_stale"]
    inputs["valuation_through"] = "2026-09-28"
    assert not freshness(inputs, datetime(2026,9,28,22,tzinfo=UTC))["strategy_stale"]


def test_fx_catchup_uses_evidence_not_existing_rate_and_repairs_oldest_gap(tmp_path):
    path = tmp_path / "monitoring.json"
    path.write_text(json.dumps(dict(schema_version=2, calculation=dict(legacy_fx_through="2026-08-31"))))
    settings = AppSettings(data_dir=tmp_path, strategy_monitoring_config_path=path)
    calls, writes = [], []
    def fetch(symbol,start,end):
        calls.append((symbol,start,end))
        from systematic_trading.live.trading_calendar import us_trading_dates_after
        days = us_trading_dates_after(date(2026,8,31), end)
        rows = [dict(trade_date=str(d),open="7",high="7",low="7",close="7",volume=0) for d in days]
        directory=tmp_path/"market_data/fx_observations";directory.mkdir(parents=True,exist_ok=True)
        (directory/"USD_CNH_test.json").write_text(json.dumps(dict(pair=symbol,source="interactive-brokers",data_type="MIDPOINT",
            observed_at="2026-09-30T12:00:00+00:00",legs={symbol:rows},rates=rows)))
    now = datetime(2026,9,30,12,tzinfo=UTC)
    store=SimpleNamespace(upsert_fx_rate=writes.append, list_fx_rates=lambda *a,**kw:writes)
    assert refresh_tracked_fx(settings,store,now=now,provider=SimpleNamespace(fetch_daily_bars=fetch))
    assert calls == [("USD/CNH",date(2026,9,1),date(2026,9,29))]
    assert writes[-1].rate_date == date(2026,9,29)
    assert not refresh_tracked_fx(settings,store,now=now,provider=SimpleNamespace(fetch_daily_bars=lambda *a:pytest.fail("extra fetch")))


def test_missing_fx_is_explicit_and_never_fabricated(tmp_path):
    path=tmp_path/"monitoring.json"
    path.write_text(json.dumps(dict(schema_version=2,calculation=dict(legacy_fx_through="2026-09-25"))))
    settings=AppSettings(data_dir=tmp_path,strategy_monitoring_config_path=path)
    with pytest.raises(ValueError,match="unavailable from 2026-09-28"):
        refresh_tracked_fx(settings,SimpleNamespace(upsert_fx_rate=lambda _:pytest.fail("synthetic"),list_fx_rates=lambda *a,**kw:[]),
            now=datetime(2026,9,29,12,tzinfo=UTC),provider=SimpleNamespace(fetch_daily_bars=lambda *a:[]))


def test_saved_fx_evidence_repairs_interrupted_database_ingest_without_refetch(tmp_path, monkeypatch):
    from systematic_trading.research import tracked_freshness as module
    path=tmp_path/"monitoring.json"
    path.write_text(json.dumps(dict(schema_version=2,calculation=dict(legacy_fx_through="2026-09-25"))))
    settings=AppSettings(data_dir=tmp_path,strategy_monitoring_config_path=path)
    monkeypatch.setattr(module,"validated_fx_observations",lambda _:({"2026-09-28":{"rate":"7.1"}},{}))
    rates=[]
    def fail(rate):raise OSError("ClickHouse unavailable after evidence saved")
    store=SimpleNamespace(list_fx_rates=lambda *a,**kw:rates,upsert_fx_rate=fail)
    provider=SimpleNamespace(fetch_daily_bars=lambda *a:pytest.fail("Evidence already verified"))
    now=datetime(2026,9,29,12,tzinfo=UTC)
    with pytest.raises(OSError):refresh_tracked_fx(settings,store,now=now,provider=provider)
    store.upsert_fx_rate=rates.append
    assert refresh_tracked_fx(settings,store,now=now,provider=provider)
    assert len(rates)==1 and str(rates[0].rate)=="7.1"
    assert not refresh_tracked_fx(settings,store,now=now,provider=provider)


def test_yahoo_host_failure_retries_same_provider_bytes(monkeypatch):
    from systematic_trading.data import yahoo
    calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'{"evidence":"original bytes"}'
    def open_url(request,timeout):
        calls.append(request.full_url)
        if "query1" in request.full_url:
            raise HTTPError(request.full_url,403,"Forbidden",{},None)
        return Response()
    monkeypatch.setattr(yahoo,"urlopen",open_url)
    assert yahoo.fetch_chart_bytes("SPY","interval=1d") == b'{"evidence":"original bytes"}'
    assert len(calls)==2 and "query2" in calls[-1]


def test_worker_reports_fx_failure_and_new_price_dates_before_archive_jobs(tmp_path, monkeypatch):
    from systematic_trading.research import analytics_service as module
    from test_analytics_projection import MemoryAnalytics
    analytics = MemoryAnalytics()
    analytics.initialize = lambda: None
    service = module.AnalyticsService(AppSettings(data_dir=tmp_path), object(), analytics)
    def fx(*args):
        raise ValueError("FX server disconnected")
    def tracked(*args):
        assert service.status()["errors"]["strategy-fx"] == "FX server disconnected"
        analytics.publish("tracked-strategies/calculations", "v2", [],
            provenance=dict(inputs=dict(price_through="2026-09-29", valuation_through="2026-09-25")))
    def archive(*args):
        status = service.status()
        assert status["strategy_price_through"] == "2026-09-29"
        assert status["strategy_valuation_through"] == "2026-09-25"
    monkeypatch.setattr(module,"refresh_tracked_fx",fx)
    monkeypatch.setattr(module,"refresh_tracked_strategies",tracked)
    monkeypatch.setattr(module,"import_lean_histories",archive)
    for name in ("publish_strategies","import_json_group"):
        monkeypatch.setattr(module,name,lambda *args:False)
    assert service.refresh("research")["errors"] == {"strategy-fx":"FX server disconnected"}
    archive()


def test_recovered_fx_error_clears_before_calculation_and_new_publication_is_visible(tmp_path, monkeypatch):
    from systematic_trading.research import analytics_service as module
    from test_analytics_projection import MemoryAnalytics
    analytics = MemoryAnalytics()
    analytics.initialize = lambda: None
    analytics.publish("strategy-serving", "old", [])
    service = module.AnalyticsService(AppSettings(data_dir=tmp_path), object(), analytics)
    service._lane_errors = {"research": {"strategy-fx": "old timeout"}, "operations": {"market-raw": "still failing"}}
    def tracked(*args):
        assert service.status()["errors"] == {"market-raw": "still failing"}
        assert service.status()["strategy_serving_version"] == "old"
    def publish(*args):
        return analytics.publish("strategy-serving", "new", [])
    def archive(*args):
        assert service.status()["strategy_serving_version"] == "new"
    monkeypatch.setattr(module, "refresh_tracked_fx", lambda *args: True)
    monkeypatch.setattr(module, "refresh_tracked_strategies", tracked)
    monkeypatch.setattr(module, "publish_strategies", publish)
    monkeypatch.setattr(module, "import_lean_histories", archive)
    monkeypatch.setattr(module, "import_json_group", lambda *args: False)
    service.request_refresh(reason="broker_reconnected")
    assert service._wake.is_set()
    assert service.refresh("research")["errors"] == {"market-raw": "still failing"}
    assert service.status()["refresh_reason"] == "broker_reconnected"
    archive()
