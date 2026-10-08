"""An operator may recover one approved handover in its original next session."""
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.live import strategy_control as module
from systematic_trading.live.sota import LiveAccountSnapshotInput
from systematic_trading.portfolio.strategy_allocation import AllocationChange, control_state, scope_for
from systematic_trading.storage.sqlite import SQLiteStore

NOW = datetime(2026,10,8,14,tzinfo=UTC)


@pytest.fixture
def case(tmp_path, monkeypatch):
    settings = AppSettings(data_dir=tmp_path,database_path=tmp_path/'test.db')
    store = SQLiteStore(settings.database_path)
    store.initialize()
    state = control_state(store)
    change = AllocationChange(expected_revision=0,event_id='pending-event',operator='Operator',reason='Approved strategy',
        allocations=[dict(strategy_key=state['sota_key'],weight='1')],effective_close='2026-10-07')
    active = dict(version=change.event_id,key='allocation-'+change.event_id,
        allocations=[r.model_dump(mode='json') for r in change.allocations],effective_close=change.effective_close)
    pending = dict(change=change.model_dump(mode='json'),approved_at='2026-10-07T19:00:00+00:00',
        preview=dict(active=active,evidence={}))
    store.commit_strategy_control(scope_for(store),0,dict(state,pending=pending),dict(event_id='pending-event',request_hash='pending'))
    monkeypatch.setattr(module,'require_monitored',lambda *args:{'revision':0})
    monkeypatch.setattr(module,'activation_issues',lambda *args:[])
    monkeypatch.setattr(module,'submission_reconciliation_issues',lambda *args,**kw:[])
    snapshot = LiveAccountSnapshotInput(as_of=date(2026,10,7),captured_at=NOW,cash=[dict(currency='USD',amount=1000)])
    monkeypatch.setattr(module,'snapshot_for',lambda *args:snapshot)
    report = SimpleNamespace(checked_at=NOW,managed_accounts=['DU123'],broker_positions=[],
        broker_cash=[dict(currency='USD',amount='1000')])
    monkeypatch.setattr(module,'load_latest_ib_reconciliation',lambda *args:report)
    order = OrderRequest(symbol='SPY',side='buy',order_type='twap',quantity=2,reference_price=100,currency='USD',
        notional_cnh=1400,rationale='Test',intended_trade_date=date(2026,10,8),
        execution_start_time='09:30',execution_end_time='10:00')
    proposal = TradeProposal(as_of=date(2026,10,7),intended_trade_date=date(2026,10,8),sleeve=active['key'],
        summary='Test',reasoning=ProposalReasoning(summary='Test'),orders=[order],
        input_provenance=dict(allocation=dict(version=active['version'],intent=dict(prices={'SPY':'100'},fx={'USD':'1'}))))
    captured = []
    def plan(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(proposal=proposal,validation_issues=[])
    monkeypatch.setattr('systematic_trading.live.allocated_plan.build_allocated_plan',plan)
    return settings,store,captured


def authorize(case, now=NOW, **updates):
    settings,store,_ = case
    values = dict(expected_revision=1,pending_event_id='pending-event',operator='Operator',reason='Recover overdue paper rebalance')
    return module.authorize_catch_up(settings,store,**dict(values,**updates),now=now)


def test_explicit_catch_up_keeps_original_signals_actual_times_and_fresh_order_window(case):
    settings,store,captured = case
    assert 'window missed' in module.activate_pending(settings,store,now=NOW)
    assert not captured and not store.list_proposals()
    authorize(case)
    assert 'activated' in module.activate_pending(settings,store,now=NOW)
    state = control_state(store)
    assert state['pending'] is None and state['active']['effective_close'] == '2026-10-07'
    assert state['active']['activated_at'] == NOW.isoformat()
    assert state['active']['approved_at'] == '2026-10-07T19:00:00+00:00'
    assert captured[0]['decision_date'] == date(2026,10,7)
    assert captured[0]['intended_trade_date'] == date(2026,10,8)
    proposal = store.list_proposals()[0]
    assert proposal.status.value == 'pending' and proposal.automation_strategy_key is None
    assert proposal.created_at == NOW and proposal.execution_deadline_at > NOW
    assert proposal.orders[0].execution_start_time == '10:03'
    assert proposal.orders[0].slippage_start_time == '09:30'
    assert proposal.input_provenance['late_handover']['pending_event_id'] == 'pending-event'
    assert not store.list_broker_order_records()
    assert module.activate_pending(settings,store,now=NOW) is None
    assert len(store.list_proposals()) == 1


@pytest.mark.parametrize('now', [NOW-timedelta(hours=1), NOW+timedelta(hours=6), NOW+timedelta(days=1)])
def test_catch_up_cannot_authorize_outside_original_open_session(case, now):
    with pytest.raises(ValueError,match='original next trading session'):
        authorize(case,now=now)


def test_catch_up_requires_full_remaining_window_matching_revision_and_event(case):
    with pytest.raises(ValueError,match='complete execution window'):
        authorize(case,now=NOW.replace(hour=19,minute=59))
    with pytest.raises(ValueError,match='pending allocation changed'):
        authorize(case,pending_event_id='another-event')
    with pytest.raises(ValueError):
        authorize(case,expected_revision=0)
    assert control_state(case[1])['revision'] == 1


def test_catch_up_rechecks_fresh_reconciliation_and_expires(case,monkeypatch):
    settings,store,_ = case
    authorize(case)
    monkeypatch.setattr(module,'submission_reconciliation_issues',lambda *args,**kw:['Stale account snapshot'])
    assert module.activate_pending(settings,store,now=NOW) == 'Stale account snapshot'
    assert not store.list_proposals() and control_state(store)['pending']
    assert 'expired' in module.activate_pending(settings,store,now=NOW+timedelta(hours=6))


def test_catch_up_is_paper_only(case):
    settings,store,_ = case
    with pytest.raises(ValueError,match='paper portfolio only'):
        module.authorize_catch_up(settings.model_copy(update={'default_environment':'live'}),store,1,
            'pending-event','Operator','Reason',now=NOW)


def test_catch_up_uses_completion_time_for_snapshot_freshness_and_window(case,monkeypatch):
    settings,store,_ = case
    authorize(case)
    checked=[]
    monkeypatch.setattr(module,'activation_issues',lambda settings,store,now:checked.append(now) or [])
    complete = NOW+timedelta(minutes=4)
    assert 'activated' in module.activate_pending(settings,store,now=NOW,clock=lambda:complete)
    assert checked == [NOW,complete]
    proposal = store.list_proposals()[0]
    assert proposal.created_at == complete and proposal.orders[0].execution_start_time == '10:07'
    assert control_state(store)['active']['activated_at'] == complete.isoformat()


def test_catch_up_expiry_during_preparation_does_not_commit(case):
    settings,store,_ = case
    authorize(case)
    assert 'expired during preparation' in module.activate_pending(settings,store,now=NOW,
        clock=lambda:NOW+timedelta(hours=6))
    assert control_state(store)['pending'] and not store.list_proposals()
