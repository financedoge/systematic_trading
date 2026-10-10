"""Read-only energy release inspection from verified publication pins."""
from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.recorders.energy import EnergyInputs, catalog as load_catalog, load_product
from systematic_trading.web.research_data import _store

router = APIRouter(prefix="/api/v1/market-data/energy")


@router.get("/catalog")
def catalog(request: Request):
    try:
        return load_catalog(_store(request), request.app.state.settings)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Energy publication is unavailable or failed verification") from exc


@router.get("/history")
def history(request: Request, product: str = Query(..., pattern="^(petroleum|natural-gas)$"),
            capture: str = Query(..., pattern="^[a-f0-9]{64}$"),
            catalog_batch: str = Query(..., pattern="^[a-f0-9]{64}$")):
    try:
        _, pin = load_product(_store(request), product)
        if pin is None:
            raise HTTPException(404, "Energy history is not yet published")
        if catalog_batch != pin["batch"]:
            raise HTTPException(409, "Energy publication changed; refresh coverage")
        return dict(EnergyInputs(**pin).capture(capture), catalog_batch=pin["batch"])
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Requested energy capture is unpublished or failed verification") from exc
