"""USD index display uses the verified analytical publication, never an archive."""
import json
from fastapi import APIRouter, Request, HTTPException
from systematic_trading.web.research_data import _store
from systematic_trading.research.usd_data import SOURCE

router = APIRouter(prefix='/api/v1/market-data/usd')


@router.get('/history')
def history(request: Request):
    document = _store(request).document(SOURCE, 'history')
    if not document:
        raise HTTPException(503, 'USD history has not completed audited publication')
    row, publication = document
    return dict(json.loads(row['payload']), batch=publication['version'], published_at=publication['published_at'])
