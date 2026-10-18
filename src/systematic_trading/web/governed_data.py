"""Read-only governed history/audit endpoints. No mutable local-file serving."""
from __future__ import annotations

from datetime import date
import json
import re

from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.market_data.governance_store import latest_batch
from systematic_trading.web.research_data import _store

router=APIRouter(prefix='/api/v1/market-data/governed')


@router.get('/recorders')
def recorders(request: Request):
    from systematic_trading.recorders.research_etfs import recorder_status
    return recorder_status(request.app.state.settings)


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
    found=store.publication('governance/catalog',batch)
    if not found:
        raise HTTPException(404,'Batch has not been published')
    return store,batch


def storage_batch(store,batch,symbol):
    rows=store.pinned_rows('observations','governance/catalog',batch,family='governed_series_catalog',entity=symbol,limit=1)
    resolved=json.loads(rows[0]['payload']).get('storage_batch',batch) if rows else batch
    if not re.fullmatch('[0-9a-f]{64}',resolved):
        raise HTTPException(503,'Invalid governed storage receipt')
    return resolved


@router.get('/catalog')
def catalog(request:Request,batch:str|None=None):
    store,batch=context(request,batch)
    rows=store.pinned_rows('observations','governance/catalog',batch,family='governed_series_catalog',order=[('entity','ASC')])
    from systematic_trading.services.market_data_health import daily_coverage
    coverage = daily_coverage(request.app.state.settings, [json.loads(r['payload']) for r in rows])
    series = coverage.pop('series')
    return dict(batch=batch,series=series,coverage=coverage,research_only=True,
        basis_note='Raw means reconstructed from recorded splits, not tape-certified. Adjusted prices include provider dividend adjustments. Unknown history is never filled.')


@router.get('/audit')
def audit(request:Request,symbol:str=Query(...,min_length=1,max_length=50),batch:str|None=None):
    store,batch=context(request,batch)
    physical=storage_batch(store,batch,symbol)
    source='governance-batch/'+physical+'/'+symbol
    rows=store.pinned_rows('documents',source,physical,key='audit',limit=1)
    if not rows:
        raise HTTPException(404,'Unknown symbol in this batch')
    from systematic_trading.services.market_data_health import series_freshness
    from systematic_trading.recorders.listed_daily import expected_session, load_state
    from datetime import UTC, datetime
    audit = json.loads(rows[0]['payload'])
    audit['freshness'] = series_freshness(audit, cutoff=expected_session(datetime.now(UTC)),
        enabled=request.app.state.settings.governed_refresh_enabled,
        receipt=load_state(request.app.state.settings).get('symbols', {}).get(symbol))
    return dict(batch=batch,audit=audit)


@router.get('/series')
def series(request:Request,symbol:str=Query(...,min_length=1,max_length=50),batch:str|None=None,
           start_date:date|None=None,end_date:date|None=None,after:date|None=None,
           limit:int=Query(25000,ge=1,le=25000),comparison_source:str=Query('',max_length=300)):
    if start_date and end_date and start_date>end_date:
        raise HTTPException(422,'Start must not be after end')
    store,batch=context(request,batch)
    physical=storage_batch(store,batch,symbol)
    filters=dict(start=start_date,end=end_date,after=after,limit=limit+1)
    rows=store.governed_rows('governed_daily',physical,symbol,**filters)
    more=len(rows)>limit
    rows=rows[:limit]
    output=[dict(**json.loads(r['payload']),payload_sha256=r['payload_hash']) for r in rows]
    comparisons=[]
    if comparison_source:
        compared=store.governed_rows('governance_comparisons',physical,symbol,source_id=comparison_source,**filters)
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
    physical=storage_batch(store,batch,symbol)
    source='governance-batch/'+physical+'/'+symbol
    rows=store.pinned_rows('observations',source,physical,family='governed_corporate_action',
        order=[('observed_at','ASC'),('point_key','ASC')],limit=10000)
    return dict(batch=batch,actions=[json.loads(r['payload']) for r in rows],
                basis_note='Original provider event units and vintages. Dividend amounts may be split-adjusted; they are not certified as-traded cash distributions.')


@router.get('/source')
def source(request:Request,symbol:str=Query(...,min_length=1,max_length=50),source_id:str=Query(...,max_length=300),batch:str|None=None):
    store,batch=context(request,batch)
    record=audit(request,symbol,batch)['audit']
    physical=storage_batch(store,batch,symbol)
    allowed={s['source_id'] for s in record.get('sources',[])}|{s['source_id'] for s in record.get('identity_exclusions',[])}
    if source_id not in allowed:
        raise HTTPException(404,'Source does not belong to this symbol')
    # Newly collected exact documents have stable keys under the committed batch.
    docs=store.pinned_rows('documents','governance-batch/'+physical+'/'+symbol,physical,key=source_id,limit=1)
    if not docs:
        return dict(source_id=source_id,archived_in='Raw Data source archive',research_url='/platform/market-data-audit?view=raw')
    return dict(source_id=source_id,document=docs[0],historical_available_at=None)
