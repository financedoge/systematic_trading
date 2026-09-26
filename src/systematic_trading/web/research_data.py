"""Read-only access to versioned research data already published in ClickHouse."""
from __future__ import annotations

import base64
from datetime import date
import json
import re

from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.golden import _sql_string

router = APIRouter(prefix='/api/v1/market-data/research')
RESEARCH_SCOPE = "(startsWith(source_id,'sector-research/') OR startsWith(source_id,'constituent-research/'))"
DATASET_SQL = "concat(splitByChar('/',source_id)[1],'/',splitByChar('/',source_id)[2])"
LABELS = {
    'research_equity_daily_bar': 'Stock and ETF daily bars',
    'research_sector_constituent': 'Historical fund holdings',
    'research_download_status': 'Download coverage and failures',
    'research_constituent_signal': 'Constituent signals',
    'research_constituent_backtest': 'Backtest results',
    'research_constituent_contrast': 'Strategy comparisons',
    'research_constituent_tree_model': 'Fitted models',
    'research_constituent_training_label': 'Model training outcomes',
}


def _store(request):
    return getattr(request.app.state, 'analytics', None) or AnalyticsStore.from_settings(request.app.state.settings)


def _query(store, sql):
    try:
        return store.query(sql)
    except (RuntimeError, OSError) as exc:
        raise HTTPException(503, 'Research archive is temporarily unavailable') from exc


def _scope(store, dataset=None):
    where = 'workspace='+_sql_string(store.workspace)+' AND '+RESEARCH_SCOPE
    if dataset is not None:
        if not re.fullmatch(r'(sector-research|constituent-research)/[A-Za-z0-9_.-]+', dataset):
            raise HTTPException(422, 'Invalid research dataset')
        where += ' AND startsWith(source_id,'+_sql_string(dataset+'/')+')'
    return where


@router.get('/datasets')
def research_datasets(request: Request):
    store = _store(request)
    rows = _query(store, 'SELECT '+DATASET_SQL+' AS dataset, family, count() AS row_count, '
        'uniqExact(entity) AS entity_count, min(observed_at) AS first_observation, '
        'max(observed_at) AS last_observation, countIf(available_at IS NULL) AS unknown_availability '
        'FROM analytics.current_observations WHERE '+_scope(store)+' GROUP BY dataset,family ORDER BY dataset,family')
    groups = {}
    for row in rows:
        item = groups.setdefault(row['dataset'], dict(dataset=row['dataset'], title=row['dataset'].split('/')[1], families=[], row_count=0))
        item['families'].append(dict(**row, label=LABELS.get(row['family'], row['family'].removeprefix('research_').replace('_', ' ').capitalize())))
        item['row_count'] += row['row_count']
    return dict(datasets=sorted(groups.values(), key=lambda x:-x['row_count']),
        storage='ClickHouse research archive',
        availability_note='Recorded dates are not proof of historical publication. Unknown availability stays unknown; coverage and source evidence are preserved with each record.')


@router.get('/entities')
def research_entities(request: Request, dataset: str, family: str, search: str = Query('', max_length=80), limit: int = Query(100, ge=1, le=5000)):
    store = _store(request)
    where = _scope(store, dataset)+' AND family='+_sql_string(family)
    if search:
        where += ' AND positionCaseInsensitiveUTF8(entity,'+_sql_string(search)+')>0'
    rows = _query(store, 'SELECT entity,count() AS row_count,min(observed_at) AS first_observation,'
        'max(observed_at) AS last_observation FROM analytics.current_observations WHERE '+where+
        ' GROUP BY entity ORDER BY entity LIMIT '+str(limit+1))
    return dict(entities=rows[:limit], truncated=len(rows)>limit)


@router.get('/rows')
def research_rows(request: Request, dataset: str, family: str, entity: str = Query('', max_length=100),
                  start_date: date | None = None, end_date: date | None = None,
                  limit: int = Query(200, ge=1, le=5000), cursor: str | None = Query(None, max_length=4000)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, 'Start must not be after end')
    store = _store(request)
    where = _scope(store, dataset)+' AND family='+_sql_string(family)
    if entity:
        where += ' AND entity='+_sql_string(entity)
    if start_date:
        where += ' AND toDate(observed_at)>='+_sql_string(start_date.isoformat())
    if end_date:
        where += ' AND toDate(observed_at)<='+_sql_string(end_date.isoformat())
    query_hash = digest(encode(dict(dataset=dataset, family=family, entity=entity, start=start_date, end=end_date)))
    if cursor:
        try:
            position = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if position['query'] != query_hash or len(position['after']) != 2 or not all(isinstance(x,str) for x in position['after']):
                raise ValueError('Wrong query')
            source, key = position['after']
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise HTTPException(422, 'Invalid cursor for these filters') from exc
        where += ' AND (source_id,point_key)>('+_sql_string(source)+','+_sql_string(key)+')'
    rows = _query(store, 'SELECT source_id,version,point_key,entity,observed_at,available_at,ingested_at,'
        'lower(hex(SHA256(payload))) AS payload_sha256,payload FROM analytics.current_observations WHERE '+where+
        ' ORDER BY source_id,point_key LIMIT '+str(limit+1))
    more = len(rows)>limit
    rows = rows[:limit]
    next_cursor = None
    if more:
        next_cursor = base64.urlsafe_b64encode(encode(dict(query=query_hash,after=[rows[-1]['source_id'],rows[-1]['point_key']])).encode()).decode()
    for row in rows:
        row['payload'] = json.loads(row['payload'])
    return dict(dataset=dataset,family=family,entity=entity,rows=rows,next_cursor=next_cursor,
        research_only=True, historical_availability='Unknown unless explicitly recorded; ingestion is not historical availability')
