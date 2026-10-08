"""Read-only CFTC futures positioning history from an audited publication."""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from systematic_trading.recorders.positioning import catalog as load_catalog, history as load_history
from systematic_trading.web.research_data import _store

router = APIRouter(prefix="/api/v1/market-data/positioning")


@router.get("/catalog")
def catalog(request: Request):
    try:
        return load_catalog(_store(request), request.app.state.settings)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "CFTC positioning publication is unavailable or failed verification") from exc


@router.get("/history")
def history(request: Request, market: str = Query(..., pattern="^[0-9]{6}$"),
            start: date = Query(default=date(2000, 1, 1)), end: date = Query(default=date(2999, 12, 31))):
    try:
        data = load_history(_store(request), market, str(start), str(end))
        return {"market": market, "rows": data, "count": len(data)}
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Requested CFTC positioning history is unavailable or failed verification") from exc
