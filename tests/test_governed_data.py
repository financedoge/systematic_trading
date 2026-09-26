import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from systematic_trading.market_data.governance_store import GovernanceStore
from systematic_trading.web import governed_data
from systematic_trading.web.platform import market_data_audit_portal


BATCH='a'*64


class Store:
    workspace='workspace'
    def __init__(self):
        self.queries=[]
        self.committed=True
    def latest(self,source):
        assert source=='governance/catalog'
        return dict(version=BATCH)
    def query(self,sql):
        self.queries.append(sql)
        assert "workspace='workspace'" in sql
        if 'FROM analytics.publications' in sql:
            return [dict(version=BATCH)] if self.committed else []
        if 'analytics.documents' in sql:
            return [dict(payload=json.dumps(dict(symbol='AAPL',sources=[dict(source_id='owned')])))]
        if 'market_data.governed_daily' in sql or 'governance_comparisons' in sql:
            return [dict(trade_date=f'2020-01-0{i+1}',payload_hash='hash',payload=json.dumps(dict(symbol='AAPL',trade_date=f'2020-01-0{i+1}',raw_close=None,adjusted_close=100))) for i in range(3)]
        return [dict(payload=json.dumps(dict(symbol='AAPL',rows=3)))]


@pytest.fixture
def client():
    app=FastAPI();app.include_router(governed_data.router);app.state.analytics=Store()
    with TestClient(app) as c:
        yield c,app.state.analytics


def test_catalog_reads_only_committed_workspace_batch(client):
    c,s=client
    result=c.get('/api/v1/market-data/governed/catalog').json()
    assert result['batch']==BATCH and result['series'][0]['symbol']=='AAPL'
    assert 'not tape-certified' in result['basis_note']
    s.committed=False
    assert c.get('/api/v1/market-data/governed/catalog',params={'batch':BATCH}).status_code==404


def test_governed_rows_keep_null_raw_and_hashes_and_date_paging(client):
    c,s=client
    r=c.get('/api/v1/market-data/governed/series',params=dict(symbol='AAPL',batch=BATCH,limit=2,
        start_date='2020-01-01',end_date='2020-02-01',comparison_source='owned')).json()
    assert len(r['rows'])==2 and r['next_after']=='2020-01-02'
    assert r['rows'][0]['raw_close'] is None and r['rows'][0]['payload_sha256']=='hash'
    assert r['comparison_truncated'] and r['historical_available_at'] is None
    assert "trade_date>='2020-01-01'" in s.queries[-1]
    c.get('/api/v1/market-data/governed/series',params=dict(symbol="AAPL' OR 1=1 --",after='2020-01-02'))
    assert "symbol='AAPL\\' OR 1=1 --'" in s.queries[-1]
    assert "trade_date>'2020-01-02'" in s.queries[-1]


@pytest.mark.parametrize('params',[dict(symbol='AAPL',limit=25001),dict(symbol='AAPL',batch='wrong'),
    dict(symbol='AAPL',start_date='2022-01-01',end_date='2020-01-01')])
def test_invalid_requests_rejected(client,params):
    assert client[0].get('/api/v1/market-data/governed/series',params=params).status_code==422


def test_source_drilldown_is_bound_to_symbol_audit(client):
    c,_=client
    assert c.get('/api/v1/market-data/governed/source',params=dict(symbol='AAPL',source_id='unowned')).status_code==404


def test_actions_state_original_provider_units(client):
    result=client[0].get('/api/v1/market-data/governed/actions',params={'symbol':'AAPL'}).json()
    assert 'may be split-adjusted' in result['basis_note']


def test_ingester_rejects_duplicate_daily_identity_before_writing():
    store=GovernanceStore(SimpleNamespace(workspace='workspace'))
    r=dict(trade_date='2020-01-01',source_id='s')
    with pytest.raises(ValueError,match='Duplicate'):
        store.insert_verified('governed_daily',BATCH,'AAPL',[r,r])


def test_governed_tab_preserves_source_and_market_views():
    html=market_data_audit_portal().body.decode()
    for value in ('Governed Histories','id="governed-panel"','id="research-panel"','id="market-bars-panel"','id="raw-filters"'):
        assert value in html
    assert 'Raw — reconstructed' in html and 'Close is not necessarily raw' in html
    assert 'Earlier identity era quarantined' in html and 'Identity/start boundary' in html
