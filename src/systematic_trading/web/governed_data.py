"""Read-only governed history/audit endpoints. No mutable local-file serving."""
from __future__ import annotations

from datetime import date
import json
import re

from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.market_data.golden import _sql_string
from systematic_trading.market_data.governance_store import latest_batch
from systematic_trading.web.research_data import _store, _query

router=APIRouter(prefix='/api/v1/market-data/governed')


def context(request,batch=None):
    store=_store(request)
    if batch is None:
        try:
            batch=latest_batch(store)
        except (RuntimeError,OSError) as exc:
            raise HTTPException(503,'Governed archive is temporarily unavailable') from exc
    if not batch:
        raise HTTPException(404,'No verified governed batch has been published yet')
    if not re.fullmatch('[0-9a-f]{64}',batch):
        raise HTTPException(422,'Invalid batch')
    # A supplied version must be a committed catalog, not an in-flight batch.
    found=_query(store,'SELECT version FROM analytics.publications WHERE workspace='+_sql_string(store.workspace)
        +" AND source_id='governance/catalog' AND version="+_sql_string(batch)+' LIMIT 1')
    if not found:
        raise HTTPException(404,'Batch has not been published')
    return store,batch


def scope(store,batch,symbol):
    return 'workspace='+_sql_string(store.workspace)+' AND batch='+_sql_string(batch)+' AND symbol='+_sql_string(symbol)


@router.get('/catalog')
def catalog(request:Request,batch:str|None=None):
    store,batch=context(request,batch)
    rows=_query(store,"SELECT payload FROM analytics.observations FINAL WHERE workspace="+_sql_string(store.workspace)
        +" AND source_id='governance/catalog' AND version="+_sql_string(batch)+" AND family='governed_series_catalog' ORDER BY entity")
    return dict(batch=batch,series=[json.loads(r['payload']) for r in rows],research_only=True,
        basis_note='Raw means reconstructed from recorded splits, not tape-certified. Adjusted prices include provider dividend adjustments. Unknown history is never filled.')


@router.get('/audit')
def audit(request:Request,symbol:str=Query(...,min_length=1,max_length=50),batch:str|None=None):
    store,batch=context(request,batch)
    source='governance-batch/'+batch+'/'+symbol
    rows=_query(store,'SELECT payload FROM analytics.documents FINAL WHERE workspace='+_sql_string(store.workspace)
        +' AND source_id='+_sql_string(source)+' AND version='+_sql_string(batch)+" AND point_key='audit' LIMIT 1")
    if not rows:
        raise HTTPException(404,'Unknown symbol in this batch')
    return dict(batch=batch,audit=json.loads(rows[0]['payload']))


@router.get('/series')
def series(request:Request,symbol:str=Query(...,min_length=1,max_length=50),batch:str|None=None,
           start_date:date|None=None,end_date:date|None=None,after:date|None=None,
           limit:int=Query(25000,ge=1,le=25000),comparison_source:str=Query('',max_length=300)):
    if start_date and end_date and start_date>end_date:
        raise HTTPException(422,'Start must not be after end')
    store,batch=context(request,batch)
    where=scope(store,batch,symbol)
    if start_date:
        where+=' AND trade_date>='+_sql_string(start_date.isoformat())
    if end_date:
        where+=' AND trade_date<='+_sql_string(end_date.isoformat())
    if after:
        where+=' AND trade_date>'+_sql_string(after.isoformat())
    rows=_query(store,'SELECT trade_date,payload,payload_hash FROM market_data.governed_daily FINAL WHERE '+where
        +' ORDER BY trade_date LIMIT '+str(limit+1))
    more=len(rows)>limit
    rows=rows[:limit]
    output=[dict(**json.loads(r['payload']),payload_sha256=r['payload_hash']) for r in rows]
    comparisons=[]
    if comparison_source:
        compared=_query(store,'SELECT trade_date,payload,payload_hash FROM market_data.governance_comparisons FINAL WHERE '+where
            +' AND source_id='+_sql_string(comparison_source)+' ORDER BY trade_date LIMIT '+str(limit+1))
        # Source points may precede the governed series, so report their own
        # truncation independently; never pretend a limited plot is complete.
        comparisons=[dict(**json.loads(r['payload']),payload_sha256=r['payload_hash']) for r in compared[:limit]]
        comparison_more=len(compared)>limit
    else:
        comparison_more=False
    return dict(batch=batch,symbol=symbol,rows=output,comparisons=comparisons,next_after=rows[-1]['trade_date'] if more else None,
                comparison_truncated=comparison_more,research_only=True,historical_available_at=None)


@router.get('/actions')
def actions(request:Request,symbol:str=Query(...,min_length=1,max_length=50),batch:str|None=None):
    store,batch=context(request,batch)
    source='governance-batch/'+batch+'/'+symbol
    rows=_query(store,'SELECT payload FROM analytics.observations FINAL WHERE workspace='+_sql_string(store.workspace)
        +' AND source_id='+_sql_string(source)+' AND version='+_sql_string(batch)+" AND family='governed_corporate_action' ORDER BY observed_at,point_key LIMIT 10000")
    return dict(batch=batch,actions=[json.loads(r['payload']) for r in rows],
                basis_note='Original provider event units and vintages. Dividend amounts may be split-adjusted; they are not certified as-traded cash distributions.')


@router.get('/source')
def source(request:Request,symbol:str=Query(...,min_length=1,max_length=50),source_id:str=Query(...,max_length=300),batch:str|None=None):
    store,batch=context(request,batch)
    record=audit(request,symbol,batch)['audit']
    allowed={s['source_id'] for s in record.get('sources',[])}|{s['source_id'] for s in record.get('identity_exclusions',[])}
    if source_id not in allowed:
        raise HTTPException(404,'Source does not belong to this symbol')
    # Newly collected exact documents have stable keys under the committed batch.
    docs=_query(store,'SELECT payload,media_type FROM analytics.documents FINAL WHERE workspace='+_sql_string(store.workspace)
        +' AND source_id='+_sql_string('governance-batch/'+batch+'/'+symbol)+' AND version='+_sql_string(batch)
        +' AND point_key='+_sql_string(source_id)+' LIMIT 1')
    if not docs:
        return dict(source_id=source_id,archived_in='Raw Data source archive',research_url='/platform/market-data-audit?view=raw')
    return dict(source_id=source_id,document=docs[0],historical_available_at=None)
