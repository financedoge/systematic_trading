"""Reviewable strategy-role controls; they never submit broker orders."""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from systematic_trading.live.strategy_control import (
    activation_issues, cancel_pending, candidate_evidence, next_handover, preview_change, schedule_change,
)
from systematic_trading.portfolio.strategy_allocation import AllocationChange, control_events, control_state
from systematic_trading.research.strategy_catalog import registered_strategy_definition

router = APIRouter(prefix='/api/v1/portfolio/strategy-control', tags=['strategy-control'])


class CommitChange(BaseModel):
    change: AllocationChange
    review_token: str
    evidence_reviewed: bool = False


class CancelChange(BaseModel):
    expected_revision: int = Field(ge=0)
    operator: str = Field(min_length=1,max_length=100)
    reason: str = Field(min_length=1,max_length=1000)


@router.get('')
def status(request: Request):
    store, settings = request.app.state.store, request.app.state.settings
    state = control_state(store)
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding='utf8'))
    candidates = []
    for key in config['monitored_strategy_ids']:
        definition = registered_strategy_definition(key)
        candidates.append(dict(strategy_key=key,name=definition.name,report_url='/api/v1/strategies/'+key+'/report'))
    now = datetime.now(UTC)
    history = control_events(store)
    proposals = {p.proposal_id:p for p in store.list_proposals()}
    fills = {}
    for record in store.list_broker_order_records():
        proposal = proposals.get(record.proposal_id)
        version = proposal.input_provenance.get('allocation', {}).get('version') if proposal else None
        for fill in record.execution_fills:
            if version:
                fills[version] = min(fills.get(version, fill.filled_at), fill.filled_at)
    for event in history:
        version = event.get('active', {}).get('version')
        event['first_execution_at'] = fills[version].isoformat() if version in fills else None
    capital = None
    analytics = getattr(request.app.state,'analytics',None)
    saved = analytics.document('dashboard-serving','allocation-attribution') if analytics else None
    if saved:
        attribution = json.loads(saved[0]['payload'])
        latest = next((r for r in reversed(attribution.get('sleeve_series', []))
            if r['version'] == state['active']['version']),None)
        if latest:
            from decimal import Decimal
            total = Decimal(latest['total'])
            capital = dict(as_of=latest['trade_date'], weights={k:str(Decimal(v)/total) for k,v in latest['values'].items()} if total else {})
    service = getattr(request.app.state,'trading_management_service',None)
    pending_status = service.status().strategy_change_status if service else None
    return dict(state=state, candidates=candidates, history=history, capital=capital, pending_status=pending_status,
        suggested_close=str(next_handover(now)), activation_blockers=activation_issues(settings, store, now),
        rules=dict(capital_rebalance='Monthly; actual sleeve weights drift between capital rebalances.',
            reserve='Unassigned capital remains reserve cash; each strategy also retains its own cash.',
            history='Earlier dates without verified assignment evidence are labelled Legacy / unknown.',
            routing='Paper only. Allocation approval does not submit orders. A new allocation needs fresh routing authority.'))


@router.get('/evidence/{strategy_key}')
def evidence(strategy_key: str, request: Request):
    try:
        return candidate_evidence(request.app.state.settings,strategy_key)
    except (ValueError,KeyError,OSError) as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/preview')
def preview(change: AllocationChange, request: Request):
    try:
        return preview_change(request.app.state.settings,request.app.state.store,change)
    except (ValueError,KeyError,OSError) as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/schedule')
def schedule(body: CommitChange, request: Request):
    try:
        return schedule_change(request.app.state.settings,request.app.state.store,body.change,
            body.review_token,evidence_reviewed=body.evidence_reviewed)
    except (ValueError,KeyError,OSError) as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/cancel')
def cancel(body: CancelChange, request: Request):
    try:
        return cancel_pending(request.app.state.store,body.expected_revision,body.operator,body.reason)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/attribution')
def attribution(request: Request):
    from systematic_trading.portfolio.allocation_analytics import allocation_revision, allocation_ledger_revision
    analytics = getattr(request.app.state,'analytics',None)
    saved = analytics.document('dashboard-serving','allocation-attribution') if analytics else None
    if not saved:
        return dict(periods=[],timeline=[],warnings=['Allocation attribution publication is preparing.'])
    result = json.loads(saved[0]['payload'])
    if (result['revision'] != allocation_revision(request.app.state.store)
            or result.get('ledger_revision') != allocation_ledger_revision(request.app.state.store)):
        raise HTTPException(503,'Allocation attribution is refreshing.',headers={'Retry-After':'5'})
    return result
