"""Read-only discovery and reviewed, audited asset retirement."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from systematic_trading.research import strategy_assets as assets
from systematic_trading.research import strategy_asset_monitoring as monitoring
from systematic_trading.web.strategy_catalog_view import CatalogControlView

router = APIRouter(prefix='/api/v1/strategy-assets', tags=['strategy-assets'])


class Retirement(BaseModel):
    review_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_revision: int = Field(ge=0)
    event_id: str = Field(min_length=8,max_length=100,pattern='^[a-zA-Z0-9_-]+$')
    operator: str = Field(min_length=1,max_length=100)
    reason: str = Field(min_length=1,max_length=1000)


@router.get('')
def catalog(request: Request, q: str = Query(default='',max_length=200)):
    try:
        value = assets.catalog(request.app.state.settings,CatalogControlView(request.app.state.store),
            getattr(request.app.state,'analytics',None),query=q)
        from systematic_trading.research.strategy_catalog import registered_strategy_definitions
        value['composite_names'] = {d.key:d.name for d in registered_strategy_definitions()}
        return value
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/signals')
def signals(request: Request):
    value = catalog(request, '')
    return dict(signals=[a for a in value['assets'] if a['contract']['kind']=='signal' and a['tracking']=='required'],
        registry_sha256=value['plan']['registry_sha256'], composite_names=value['composite_names'])


@router.get('/{asset_id}/series')
def series(asset_id: str, request: Request, symbol: str, limit: int = Query(default=260,ge=1,le=1500)):
    try:
        if asset_id not in assets.load_registry()['assets']:
            raise ValueError('Unknown strategy asset')
        return monitoring.series(getattr(request.app.state,'analytics',None),asset_id,symbol,limit)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/{asset_id}/retirement')
def impact(asset_id: str, request: Request):
    try:
        return assets.retirement_impact(request.app.state.settings,request.app.state.store,asset_id)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/{asset_id}/retire')
def retire(asset_id: str, body: Retirement, request: Request):
    try:
        return assets.retire(request.app.state.settings,request.app.state.store,key=asset_id,**body.model_dump())
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
