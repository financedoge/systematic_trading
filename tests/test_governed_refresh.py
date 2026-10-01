import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import encode
from systematic_trading.research import governed_refresh as module
from systematic_trading.portfolio.decision_inputs import decision_inputs
from test_analytics_projection import MemoryAnalytics


@pytest.fixture
def governed(tmp_path, monkeypatch):
    sessions,_=module.governed_sessions("2026-01-02","2026-08-04")
    days=sorted(sessions)
    root=tmp_path/"original";root.mkdir()
    for symbol in ("X","URTH"):
        rows=[dict(symbol=symbol,trade_date=d,**{"adjusted_"+f:100+i*.1 for f in ("open","high","low","close")},
                   raw_close=100+i*.1,source_volume=1000) for i,d in enumerate(days[:-1])]
        module._rows(root,f"bars/{symbol}.jsonl.gz",rows)
        module._write(root,f"audits/{symbol}.json",dict(symbol=symbol,name=symbol+" Example ETF",status="audited_with_limitations"))
    module._write(root,"catalog.json",[dict(symbol=s) for s in ("X","URTH","OTHER")])
    module._write(root,"manifest.json",{p.relative_to(root).as_posix():sha256(p) for p in root.rglob("*") if p.is_file()})
    analytics=MemoryAnalytics()
    analytics.publish("governance/catalog",sha256(root/"manifest.json"),[],provenance=dict(root=str(root)))
    monkeypatch.setattr(module,"instruments_for_definition",lambda d: {"X":None})
    written=[]
    class Verified:
        def __init__(self,*a): pass
        def initialize(self): pass
        def insert_verified(self,table,batch,symbol,records):
            assert all(r["symbol"]==symbol for r in records)
            written.append((table,batch,symbol,len(records)))
    monkeypatch.setattr(module,"GovernanceStore",Verified)
    def fetch(symbol,now):
        stamps=[int(datetime.fromisoformat(d+"T20:00:00+00:00").timestamp()) for d in days]
        prices=[100+i*.1 for i in range(len(days))]
        return encode(dict(chart=dict(result=[dict(meta=dict(symbol=symbol,currency="USD",instrumentType="ETF",
            longName=symbol+" Example ETF",exchangeTimezoneName="America/New_York",firstTradeDate=stamps[0]),
            timestamp=stamps,indicators=dict(quote=[dict(**{f:prices for f in ("open","high","low","close")},volume=[1000]*len(days))],
                                             adjclose=[dict(adjclose=prices)]),events={})]))).encode()
    config=tmp_path/"monitoring.json";module._write(tmp_path,config.name,dict(calculation=dict(warmup_start="2026-01-02")))
    settings=AppSettings(data_dir=tmp_path,strategy_monitoring_config_path=config)
    return settings,analytics,fetch,written


def test_producer_commits_after_all_symbols_and_readers_share_receipt(governed):
    settings,analytics,fetch,written=governed
    old=analytics.latest("governance/catalog")["version"]
    now=datetime(2026,8,4,22,tzinfo=UTC)
    assert module.refresh_governed_etfs(settings,analytics,now=now,fetch=fetch)
    publication=analytics.latest("governance/catalog")
    assert publication["version"] != old and len(written)==4
    catalog=[json.loads(r["payload"]) for r in analytics.rows["governance/catalog"]]
    assert next(r for r in catalog if r["symbol"]=="OTHER")["storage_batch"]==old
    bars,marks,receipt=decision_inputs(settings,["X"],date(2026,8,4),analytics=analytics)
    assert bars["X"][-1].trade_date==date(2026,8,4)
    assert marks["X"]["trade_date"]=="2026-08-04" and receipt["batch"]==publication["version"]
    assert not module.refresh_governed_etfs(settings,analytics,now=now,fetch=lambda *a:pytest.fail("Unnecessary fetch"))


def test_failed_symbol_cannot_publish_partial_catalog(governed):
    settings,analytics,fetch,written=governed
    old=analytics.latest("governance/catalog")["version"]
    def failing(symbol,now):
        if symbol=="X": raise ValueError("Provider unavailable")
        return fetch(symbol,now)
    with pytest.raises(ValueError,match="Provider unavailable"):
        module.refresh_governed_etfs(settings,analytics,now=datetime(2026,8,4,22,tzinfo=UTC),fetch=failing)
    assert analytics.latest("governance/catalog")["version"]==old and written==[]
    assert json.loads((settings.data_dir/"governance/refresh-state.json").read_text())["error"]=="Provider unavailable"


def test_acquisition_retries_after_reconnection_without_waiting_an_hour(governed):
    from datetime import timedelta
    settings, analytics, fetch, written = governed
    now = datetime(2026,8,4,22,tzinfo=UTC)
    def offline(*args):
        raise OSError("offline")
    with pytest.raises(OSError,match="offline"):
        module.refresh_governed_etfs(settings,analytics,now=now,fetch=offline)
    with pytest.raises(ValueError,match="offline"):
        module.refresh_governed_etfs(settings,analytics,now=now+timedelta(seconds=60),fetch=fetch)
    assert module.refresh_governed_etfs(settings,analytics,now=now+timedelta(seconds=301),fetch=fetch)
