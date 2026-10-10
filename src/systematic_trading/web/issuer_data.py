"""Verified issuer snapshots for Market Data inspection."""
from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.recorders.issuer_etfs import IssuerInputs, catalog as load_catalog, load_fund
from systematic_trading.web.research_data import _store

router = APIRouter(prefix="/api/v1/market-data/issuer-etfs")


@router.get("/catalog")
def catalog(request: Request):
    try:
        return load_catalog(_store(request), request.app.state.settings)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Issuer recorder registry is unavailable") from exc


@router.get("/history")
def history(request: Request, symbol: str = Query(..., pattern="^[A-Z]{1,5}$"),
            capture: str = Query(..., pattern="^[a-f0-9]{64}$"),
            catalog_batch: str = Query(..., pattern="^[a-f0-9]{64}$")):
    try:
        _, pin = load_fund(_store(request), symbol)
        if pin is None:
            raise HTTPException(404, "Issuer history is not yet published")
        if catalog_batch != pin["batch"]:
            raise HTTPException(409, "Issuer publication changed; refresh coverage")
        return dict(IssuerInputs(**pin).capture(capture), catalog_batch=pin["batch"])
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Requested issuer capture is unpublished or failed verification") from exc
