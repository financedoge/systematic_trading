"""Read-only economic snapshots from verified publications."""
from datetime import date
from fastapi import APIRouter, HTTPException, Query, Request
from systematic_trading.recorders.economics import EconomicInputs, load_catalog, recorder_status
from systematic_trading.web.research_data import _store

router = APIRouter(prefix="/api/v1/market-data/economics")


@router.get("/catalog")
def catalog(request: Request):
    try:
        data, pin = load_catalog(_store(request))
        return dict(data, **pin, recorder=recorder_status(request.app.state.settings))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Economic publication is unavailable or failed verification") from exc


@router.get("/history")
def history(request: Request, series: str = Query(..., pattern="^[A-Z0-9]{1,20}$"), vintage: date = Query(...)):
    try:
        _, pin = load_catalog(_store(request))
        data = EconomicInputs(**pin).snapshot(series, str(vintage))
        return dict(data, catalog_batch=pin["batch"])
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Requested economic vintage is unpublished or failed verification") from exc
