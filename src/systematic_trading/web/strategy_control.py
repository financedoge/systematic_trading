"""Reviewable strategy-role controls; they never submit broker orders."""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from systematic_trading.live.strategy_control import (
    activation_issues, authorize_catch_up, cancel_pending, candidate_evidence, handover_phase, next_handover, preview_change, schedule_change,
)
from systematic_trading.portfolio.strategy_allocation import AllocationChange, control_events, control_state
from systematic_trading.research.strategy_catalog import registered_strategy_definition
from systematic_trading.research.strategy_lifecycle import membership, change_membership, calculation_ready

router = APIRouter(prefix='/api/v1/portfolio/strategy-control', tags=['strategy-control'])


class CommitChange(BaseModel):
    change: AllocationChange
    review_token: str
    evidence_reviewed: bool = False


class CancelChange(BaseModel):
    expected_revision: int = Field(ge=0)
    operator: str = Field(min_length=1,max_length=100)
    reason: str = Field(min_length=1,max_length=1000)


class CatchUpChange(CancelChange):
    pending_event_id: str = Field(min_length=8,max_length=100)


class MonitoringChange(BaseModel):
    strategy_key: str = Field(min_length=1,max_length=160)
    lifecycle: str = Field(pattern='^(monitored|archived)$')
    expected_revision: int = Field(ge=0)
    event_id: str = Field(min_length=8,max_length=100,pattern='^[a-zA-Z0-9_-]+$')
    operator: str = Field(min_length=1,max_length=100)
    reason: str = Field(min_length=1,max_length=1000)


@router.post('/monitoring')
def update_monitoring(body: MonitoringChange, request: Request):
    try:
        result=change_membership(request.app.state.settings,request.app.state.store,
            key=body.strategy_key,**body.model_dump(exclude={'strategy_key'}))
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    service=getattr(request.app.state,'analytics_service',None)
    if service:
        service.request_refresh(reason='strategy_membership_changed')
    return result


@router.get('')
def status(request: Request):
    store, settings = request.app.state.store, request.app.state.settings
    state = control_state(store)
    monitoring = membership(settings,store)
    candidates = []
    analytics = getattr(request.app.state,'analytics',None)
    publication=analytics.latest('tracked-strategies/calculations') if analytics else None
    through=json.loads(publication['provenance']).get('inputs',{}).get('price_through') if publication else None
    for key in monitoring['monitored']:
        definition = registered_strategy_definition(key)
        saved=analytics.document('tracked-strategies/calculations','detail/'+key) if analytics else None
        detail=json.loads(saved[0]['payload']) if saved else {}
        if detail and calculation_ready(detail,monitoring,through):
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
    worker = service.status() if service else None
    pending_status = worker.strategy_change_status if worker else None
    calculation_service = getattr(request.app.state, 'analytics_service', None)
    calculations = calculation_readiness(calculation_service.status() if calculation_service else None)
    pending_phase = handover_phase(pending_status)
    overdue = bool(worker and (worker.heartbeat_at is None or
        (now-worker.heartbeat_at).total_seconds() > max(300, worker.execution_poll_seconds*3)))
    if state.get('pending') and (worker is None or not worker.running or overdue):
        pending_phase = 'blocked'
        pending_status = 'Trading management worker is stopped or overdue. Inspect service health to resume the saved handover.'
    from systematic_trading.execution.reconciliation import submission_reconciliation_issues
    return dict(state=state, candidates=candidates, history=history, capital=capital, pending_status=pending_status,
        pending_phase=pending_phase, calculation_status=calculations,
        suggested_close=str(next_handover(now)), activation_blockers=activation_issues(settings, store, now),
        routing_warnings=submission_reconciliation_issues(settings, now=now),
        rules=dict(capital_rebalance='Monthly; actual sleeve weights drift between capital rebalances.',
            reserve='Unassigned capital remains reserve cash; each strategy also retains its own cash.',
            history='Earlier dates without verified assignment evidence are labelled Legacy / unknown.',
            routing='Paper only. Allocation approval does not submit orders. A new allocation needs fresh routing authority.'))


def calculation_readiness(state):
    if state is None:
        return dict(severity='error', message='Calculation worker is unavailable. Start the analytics service; strategy freshness cannot be verified.')
    issues = [f'{name}: {error}' for name, error in state.get('errors', {}).items()]
    worker_error = False
    for lane in ('research', 'operations', 'archives', 'watchdog'):
        if state.get(lane+'_running') is False or (state.get(lane+'_stale') and not state.get(lane+'_initializing')):
            issues.append(f'{lane.title()} worker is stopped or overdue. Inspect service health and worker logs.')
            worker_error = True
        elif state.get(lane+'_initializing'):
            issues.append(f'{lane.title()} worker is starting; waiting for its first complete refresh.')
    if state.get('strategy_stale'):
        issues.append(state['strategy_freshness_message'])
    if not issues:
        return dict(severity='ok', message=state.get('strategy_freshness_message', 'Calculations available.'))
    severity = 'error' if state.get('errors') or worker_error else 'warning'
    return dict(severity=severity, message='\n'.join(issues)+
        '\nLast complete results are retained. Resolve the reported cause, then refresh calculations. Allocation and order checks remain enforced.')


@router.get('/evidence/{strategy_key}')
def evidence(strategy_key: str, request: Request):
    try:
        return candidate_evidence(request.app.state.settings,strategy_key,store=request.app.state.store)
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


@router.post('/catch-up')
def catch_up(body: CatchUpChange, request: Request):
    try:
        return authorize_catch_up(request.app.state.settings,request.app.state.store,**body.model_dump())
    except (ValueError,KeyError,OSError) as exc:
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
