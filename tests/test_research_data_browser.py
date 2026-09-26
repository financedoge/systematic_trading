import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from systematic_trading.web import research_data
from systematic_trading.web.platform import market_data_audit_portal


class Archive:
    workspace = 'test-workspace'

    def __init__(self):
        self.queries = []

    def query(self, sql):
        self.queries.append(sql)
        assert "workspace='test-workspace'" in sql
        assert 'sector-research/' in sql and 'constituent-research/' in sql
        if 'GROUP BY dataset,family' in sql:
            return [dict(dataset='sector-research/stocks-v1', family='research_equity_daily_bar', row_count=3,
                entity_count=1, first_observation='2015-01-02', last_observation='2015-01-06', unknown_availability=3)]
        return [dict(source_id='sector-research/stocks-v1/bars/AAPL',version='v1',point_key=str(i),entity='AAPL',
            observed_at=f'2015-01-0{i+2}',available_at=None,ingested_at='2026-09-26',payload_sha256='hash',
            payload=json.dumps(dict(close=100+i,volume=1234,historical_available_at=None))) for i in range(3)]


@pytest.fixture
def browser():
    app=FastAPI();app.include_router(research_data.router);app.state.analytics=Archive()
    with TestClient(app) as client:
        yield client,app.state.analytics


def test_catalog_exposes_research_families_and_unknown_availability(browser):
    client,archive=browser
    result=client.get('/api/v1/market-data/research/datasets').json()
    group=result['datasets'][0]
    assert group['row_count']==3
    assert group['families'][0]['label']=='Stock and ETF daily bars'
    assert group['families'][0]['unknown_availability']==3


def test_records_retain_source_hash_null_availability_and_filter_bound_cursor(browser):
    client,archive=browser
    params=dict(dataset='sector-research/stocks-v1',family='research_equity_daily_bar',entity='AAPL',limit=2,
                start_date='2015-01-01',end_date='2015-12-31')
    result=client.get('/api/v1/market-data/research/rows',params=params).json()
    assert len(result['rows'])==2 and result['next_cursor']
    assert result['rows'][0]['available_at'] is None
    assert result['rows'][0]['payload']['close']==100
    assert result['rows'][0]['payload_sha256']=='hash'
    assert "toDate(observed_at)<='2015-12-31'" in archive.queries[-1]
    assert client.get('/api/v1/market-data/research/rows',params={**params,'cursor':result['next_cursor']}).status_code==200
    assert "(source_id,point_key)>('sector-research/stocks-v1/bars/AAPL','1')" in archive.queries[-1]
    assert client.get('/api/v1/market-data/research/rows',params={**params,'entity':'MSFT','cursor':result['next_cursor']}).status_code==422


@pytest.mark.parametrize('change',[
    dict(dataset='account/secret'),dict(dataset='sector-research/../../secret'),dict(limit=5001),
    dict(start_date='2026-01-01',end_date='2015-01-01'),dict(cursor='not-a-cursor'),
])
def test_invalid_archive_queries_rejected(browser,change):
    client,_=browser
    params={**dict(dataset='sector-research/stocks-v1',family='research_equity_daily_bar'),**change}
    assert client.get('/api/v1/market-data/research/rows',params=params).status_code==422


def test_entity_is_quoted_and_archive_outage_is_explicit(browser):
    client,archive=browser
    client.get('/api/v1/market-data/research/rows',params=dict(dataset='sector-research/stocks-v1',family='research_equity_daily_bar',entity="AAPL' OR 1=1 --"))
    assert "entity='AAPL\\' OR 1=1 --'" in archive.queries[-1]
    def fail(sql):
        raise RuntimeError('connection details must not be exposed')
    archive.query=fail
    response=client.get('/api/v1/market-data/research/datasets')
    assert response.status_code==503 and 'connection details' not in response.text


def test_archive_tab_is_visible_alongside_existing_market_bar_controls():
    html=market_data_audit_portal().body.decode()
    assert 'id="research-tab"' in html and 'id="market-bars-panel"' in html
    assert 'id="golden-filters"' in html and 'id="raw-filters"' in html
    assert 'Download page JSON' in html and 'Historical stock prices' in html
    assert html.count('id="research-panel"')==1


def test_market_data_browser_does_not_require_trading_store():
    assert research_data._store(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(analytics='reader'))))=='reader'
