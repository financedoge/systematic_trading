"""Offline recovery scenarios; every broker operation uses a fake client."""
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import ApprovalDecision, BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.enums import ProposalStatus, BrokerOrderStatus
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.execution.window import expire_due_proposals
from systematic_trading.live.deferred_rebalance import refresh_rebalance, prepared_submission_issues
from systematic_trading.portfolio.rebalance_intents import (
    cancel_intent, intent_state, latest_rebalance, record_intent, sync_intents,
)
from systematic_trading.portfolio.targets import approved_target
from systematic_trading.research import current_sota_definition
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport
from test_deferred_rebalance import write_report
from test_initial_allocation import Orders
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store

NOW = datetime(2026, 10, 5, 16, tzinfo=UTC)


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path/'test.db', automation_enabled=True)
    store = SQLiteStore(settings.database_path)
    store.initialize()
    definition = current_sota_definition()
    report = IBPaperReconciliationReport(checked_at=NOW, managed_accounts=['DU123'],
        broker_cash=[dict(currency='USD', amount='1000')], local_order_history_count=0,
        local_order_count=0, local_filled_order_count=0, ib_fill_count=0, ib_position_count=0)
    write_report(settings, report)
    order = OrderRequest(symbol='SPY', side='buy', order_type='twap', quantity=10,
        reference_price=100, currency='USD', notional_cnh=7000, rationale='test',
        intended_trade_date=date(2026,10,2), execution_start_time='09:30', execution_end_time='10:00')
    proposal = TradeProposal(proposal_id='objective', created_at=NOW-timedelta(days=3),
        as_of=date(2026,10,1), target_as_of=date(2026,10,1), intended_trade_date=date(2026,10,2),
        sleeve=definition.sleeve_name, summary='test', orders=[order], trigger='portfolio_drift',
        targets=[AllocationTarget(symbol='SPY',target_weight='.4',sleeve=definition.sleeve_name,rationale='test')],
        automation_strategy_key=definition.key, input_provenance={'allocation':{'version':'legacy'}},
        reasoning=ProposalReasoning(summary='test'))
    store.save_proposal(proposal)
    def build(**kw):
        # Fresh reconciled holdings, not original order quantity, determine residual.
        held = sum(p.quantity for p in kw['account_snapshot'].positions if p.symbol == 'SPY')
        return SimpleNamespace(validation_issues=[], proposal=proposal.model_copy(update=dict(
            as_of=kw['decision_date'], intended_trade_date=kw['intended_trade_date'],
            orders=[order.model_copy(update=dict(quantity=10-held, intended_trade_date=kw['intended_trade_date']))] if held < 10 else [])))
    monkeypatch.setattr('systematic_trading.live.allocated_plan.build_allocated_plan', build)
    return settings, store, report, proposal


def test_approval_survives_zero_fill_expiry_and_restart(recovery):
    settings, store, _, source = recovery
    store.apply_decision(ApprovalDecision(proposal_id=source.proposal_id, status='approved'))
    expire_due_proposals(store, settings, now=NOW)
    reopened = SQLiteStore(settings.database_path)
    sync_intents(reopened, now=NOW)
    assert intent_state(reopened, source)['status'] == 'outstanding'
    assert approved_target(reopened, current_sota_definition(), date(2026,9,30), NOW.date()).proposal_id == source.proposal_id
    assert all(r.status.value == 'missed' and not r.broker_order_id for r in reopened.list_broker_order_records())


@pytest.mark.parametrize('trigger', ['portfolio_drift', 'scheduled_rebalance', 'empty_portfolio'])
def test_ordinary_unprepared_proposal_gets_fresh_window_and_lineage(recovery, trigger):
    settings, store, _, source = recovery
    source = source.model_copy(update={'trigger':trigger})
    store.save_proposal(source)
    expire_due_proposals(store, settings, now=NOW)
    renewed = refresh_rebalance(settings, store, source.proposal_id, now=NOW,
        automation_strategy_key=source.automation_strategy_key, automation_policy_revision=1, order_client=Orders())
    assert renewed.status == ProposalStatus.PENDING
    assert renewed.as_of == date(2026,10,2)
    assert renewed.intended_trade_date == NOW.date()
    assert renewed.input_provenance['deferred_rebalance']['root_proposal_id'] == source.proposal_id
    assert renewed.orders[0].slippage_trade_date == source.intended_trade_date
    assert store.strategy_approval_times() == {}


def terminal_record(source, *, filled=4, status='cancelled'):
    return BrokerOrderRecord(proposal_id=source.proposal_id, order_index=0, order=source.orders[0],
        order_ref='original',broker_order_id=42, status=status, submitted_at=NOW-timedelta(days=3),
        updated_at=NOW-timedelta(minutes=2), filled_quantity=filled,
        broker_observation={'status':'Cancelled', 'checked_at':(NOW-timedelta(minutes=2)).isoformat()},
        execution_fills=[dict(execution_id='fill',symbol='SPY',side='buy',quantity=filled,
            average_price=100,filled_at=NOW-timedelta(minutes=3))] if filled else [])


def test_partial_fill_only_rebuilds_residual_and_preserves_original(recovery):
    settings, store, report, source = recovery
    store.apply_decision(ApprovalDecision(proposal_id=source.proposal_id,status='approved'))
    store.save_broker_order_record(terminal_record(source))
    write_report(settings, IBPaperReconciliationReport.model_validate(dict(report.model_dump(), ib_position_count=1,
        broker_positions=[dict(symbol='SPY',quantity=4)])))
    expire_due_proposals(store, settings, now=NOW)
    renewed = refresh_rebalance(settings, store, source.proposal_id, now=NOW,
        automation_strategy_key=source.automation_strategy_key, order_client=Orders())
    assert renewed.orders[0].quantity == 6
    assert store.get_proposal(source.proposal_id).orders[0].quantity == 10
    assert store.list_broker_order_records(source.proposal_id)[0].filled_quantity == 4


@pytest.mark.parametrize('change', ['uncertain', 'working', 'incomplete_fills', 'no_terminal_proof', 'stale_reconciliation', 'open_at_ib'])
def test_residual_recovery_never_infers_success_from_absence(recovery, change):
    settings, store, report, source = recovery
    record = terminal_record(source)
    client = Orders()
    if change == 'uncertain': record = record.model_copy(update={'execution_sync_issue':'missing fill'})
    if change == 'working': record = record.model_copy(update={'status':BrokerOrderStatus.PENDING_SUBMIT})
    if change == 'incomplete_fills': record = record.model_copy(update={'execution_fills':[]})
    if change == 'no_terminal_proof': record = record.model_copy(update={'broker_observation':{}})
    if change == 'stale_reconciliation': write_report(settings, report.model_copy(update={'checked_at':NOW-timedelta(hours=1)}))
    if change == 'open_at_ib': client = Orders([{'status':'Submitted'}])
    store.save_broker_order_record(BrokerOrderRecord.model_validate(record.model_dump()))
    with pytest.raises(ValueError):
        refresh_rebalance(settings, store, source.proposal_id, now=NOW, order_client=client)
    assert len(store.list_proposals()) == 1


def test_cancellation_is_durable_and_blocks_refresh_and_all_routing(recovery):
    settings, store, _, source = recovery
    sync_intents(store, now=NOW)
    cancel_intent(store, source.proposal_id, operator='Tester', reason='Cancel objective', now=NOW)
    reopened = SQLiteStore(settings.database_path)
    expire_due_proposals(reopened, settings, now=NOW)
    sync_intents(reopened, now=NOW)
    assert intent_state(reopened, source)['status'] == 'cancelled'
    with pytest.raises(ValueError, match='closed'):
        refresh_rebalance(settings, reopened, source.proposal_id, now=NOW)
    assert any('cancelled' in e for e in prepared_submission_issues(settings, reopened, source))


def test_new_adoption_supersedes_old_objective_with_audit(recovery):
    settings, store, _, source = recovery
    newer = source.model_copy(update={'proposal_id':'new-objective','created_at':NOW,
        'as_of':NOW.date(),'target_as_of':NOW.date()})
    store.save_proposal(newer)
    store.apply_decision(ApprovalDecision(proposal_id=newer.proposal_id,status='approved'))
    sync_intents(store, now=NOW)
    assert intent_state(store, source)['status'] == 'superseded'
    assert latest_rebalance(store).proposal_id == newer.proposal_id
    with pytest.raises(ValueError, match='closed'):
        refresh_rebalance(settings, store, source.proposal_id, now=NOW)


def test_legacy_wrong_target_date_does_not_revive_earlier_window(recovery):
    settings, store, _, source = recovery
    newer = source.model_copy(update={'proposal_id':'later-cleanup','created_at':NOW,
        'target_as_of':date(2026,9,30)})
    store.save_proposal(newer)
    assert latest_rebalance(store).proposal_id == newer.proposal_id
    renewed = refresh_rebalance(settings, store, newer.proposal_id, now=NOW, order_client=Orders())
    assert renewed.target_as_of == source.target_as_of
    assert renewed.target_source_proposal_id == newer.proposal_id


def test_intent_updates_are_idempotent_and_keep_blocker_across_restarts(recovery):
    _, store, _, source = recovery
    record_intent(store, source, now=NOW, reason='Missing audited FX', next_retry_condition='FX publication arrives')
    first = intent_state(store, source)
    sync_intents(store, now=NOW+timedelta(minutes=1))
    assert intent_state(store, source) == first


def controller_for(recovery, monkeypatch):
    from systematic_trading.live.auto_approval import PaperAutoApproval, PaperApprovalPolicy
    settings, store, report, source = recovery
    controller = PaperAutoApproval(settings, store, order_client=Orders())
    controller.policy = PaperApprovalPolicy(enabled=True, revision=1, enabled_at=NOW-timedelta(days=5),
        strategy_key=source.automation_strategy_key, binding=controller._binding(), account='DU123')
    controller._save()
    monkeypatch.setattr(controller, '_preflight', lambda p, now: True)
    monkeypatch.setattr(controller, '_account', lambda now: report)
    return controller


def test_background_expiry_runs_even_when_policy_disabled_and_market_closed(recovery, monkeypatch):
    from systematic_trading.live.management_service import TradingManagementService
    settings, store, _, source = recovery
    service = TradingManagementService(settings=settings, store=store)
    monkeypatch.setattr('systematic_trading.live.strategy_control.activate_pending', lambda *a,**k:None)
    monkeypatch.setattr(service, '_execution_sync_due', lambda now:False)
    monkeypatch.setattr(service, '_is_monitoring_day', lambda now:False)
    monkeypatch.setattr(service, '_stage_portfolio_alignment', lambda now:None)
    service.run_once(now=NOW)
    assert store.get_proposal(source.proposal_id).status == ProposalStatus.MISSED
    assert intent_state(store, source)['status'] == 'outstanding'
    assert not service.auto_approval.policy.enabled


def test_expired_queue_entry_cannot_starve_valid_proposal(recovery, monkeypatch):
    from systematic_trading.domain.execution import BrokerSubmissionResult
    _, store, _, source = recovery
    valid = source.model_copy(update={'proposal_id':'valid','created_at':NOW-timedelta(seconds=1),
        'as_of':date(2026,10,2),'intended_trade_date':NOW.date(),'execution_deadline_at':NOW+timedelta(hours=1)})
    store.save_proposal(valid)
    controller = controller_for(recovery, monkeypatch)
    calls = []
    def route(**kw):
        calls.append(kw['proposal'].proposal_id)
        return BrokerSubmissionResult(proposal_id=valid.proposal_id, environment='paper')
    monkeypatch.setattr(controller.router, 'submit_approved_proposal', route)
    controller.tick(now=NOW)
    assert store.get_proposal(source.proposal_id).status == ProposalStatus.MISSED
    assert calls == ['valid']


def test_new_reserve_before_send_claim_recovers_but_legacy_claim_stays_blocked(recovery, monkeypatch):
    settings, store, report, source = recovery
    current = source.model_copy(update={'as_of':date(2026,10,2),'intended_trade_date':NOW.date(),
        'execution_deadline_at':NOW+timedelta(hours=1)})
    store.save_proposal(current)
    controller = controller_for(recovery, monkeypatch)
    def fail(**kw):
        raise TimeoutError('Connect failed before any reservation')
    monkeypatch.setattr(controller.router, 'submit_approved_proposal', fail)
    controller.tick(now=NOW)
    claim = controller.policy.attempts[source.proposal_id]
    assert claim['reserve_before_send'] and not store.list_broker_order_records()
    from systematic_trading.live.auto_approval import PaperAutoApproval
    restarted = PaperAutoApproval(settings,store,order_client=Orders())
    renewed = restarted._renew_missed_rebalance(NOW+timedelta(seconds=1))
    assert renewed is not None and renewed.proposal_id != source.proposal_id
    assert renewed.status == ProposalStatus.PENDING
    # An old claim without the durable router contract cannot use that inference.
    restarted.policy.attempts[renewed.proposal_id] = {'outcome':'review','error':'Unknown response'}
    store.save_proposal(renewed.model_copy(update={'status':ProposalStatus.MISSED}))
    restarted._save()
    assert restarted._renew_missed_rebalance(NOW+timedelta(seconds=2)) is None
    assert 'uncertain' in restarted.policy.message


def test_missed_intent_still_calculates_drift(recovery, monkeypatch):
    from systematic_trading.live.initial_allocation import stage_portfolio_alignment
    settings, store, _, source = recovery
    settings = settings.model_copy(update={'automation_queue_rebalance':True})
    expire_due_proposals(store, settings, now=NOW)
    monkeypatch.setattr(store, 'list_price_bars', lambda *a,**k:[SimpleNamespace(trade_date=date(2026,10,2),volume=1)])
    monkeypatch.setattr(store, 'list_fx_rates', lambda *a,**k:[SimpleNamespace(rate_date=date(2026,10,2))])
    monkeypatch.setattr('systematic_trading.live.initial_allocation.build_sota_live_rebalance_plan',
        lambda **kw:SimpleNamespace(validation_issues=[],proposal=source))
    rows = [dict(symbol='SPY',quantity='0',actual_weight='0',target_weight='.4',drift='-.4')]
    monkeypatch.setattr('systematic_trading.live.initial_allocation.portfolio_drift',lambda *a:rows)
    result = stage_portfolio_alignment(settings=settings,store=store,now=NOW,order_client=Orders())
    assert result.status == 'review'
    assert result.holdings == rows and result.pending_age_seconds > 0
    assert len(store.list_proposals()) == 1


def test_alignment_preserves_last_valid_drift_and_marks_review_warning(recovery, monkeypatch):
    from systematic_trading.live.initial_allocation import InitialAllocationResult
    from systematic_trading.live.management_service import TradingManagementService
    settings,store,_,source = recovery
    service = TradingManagementService(settings=settings,store=store)
    monkeypatch.setattr(service,'_refresh_alignment_fx',lambda now:None)
    rows = [dict(symbol='SPY',quantity='0',actual_weight='0',target_weight='.4',drift='-.4')]
    service._status.portfolio_alignment=InitialAllocationResult(status='review',message='Awaiting recovery',
        holdings=rows,valuation_date=date(2026,10,2),target_as_of=source.target_as_of)
    monkeypatch.setattr('systematic_trading.live.management_service.stage_portfolio_alignment',
        lambda **kw:InitialAllocationResult(status='review',message='Broker outcome uncertain'))
    service._stage_portfolio_alignment(NOW)
    result=service._status.portfolio_alignment
    assert result.holdings == rows and result.holdings_stale
    assert result.valuation_date == date(2026,10,2)
    assert service._status.events[0].status == 'warning'


def test_terminal_intent_cannot_be_resurrected_by_stale_writer(backend_store):
    store = backend_store
    definition = current_sota_definition()
    source = store.get_proposal('proposal').model_copy(update={'proposal_id':'intent-test',
        'sleeve':definition.sleeve_name,'automation_strategy_key':definition.key,'trigger':'portfolio_drift'})
    store.save_proposal(source)
    record_intent(store,source,reason='Outstanding')
    cancelled = cancel_intent(store,source.proposal_id,operator='Tester',reason='Stop')
    record_intent(store,source,reason='Stale recovery result')
    assert intent_state(store,source) == cancelled
    assert intent_state(store,source)['status'] == 'cancelled'


def test_expiry_does_not_undo_approved_virtual_cash_transfer(recovery):
    from systematic_trading.portfolio.strategy_book import replay_book, initial_book, RESERVE
    _, store, _, source = recovery
    snapshot=dict(positions=[],cash=[dict(currency='USD',amount='1000')])
    active=dict(version='legacy',opening=dict(at=(NOW-timedelta(days=4)).isoformat(),
        book=initial_book(snapshot,[dict(strategy_key='A',weight='1')])))
    intent=dict(crosses=[],cash_transfers={'A':'-10',RESERVE:'10'},fx={'USD':'1'})
    p=source.model_copy(update={'input_provenance':{'allocation':{'version':'legacy','intent':intent}}})
    store.save_proposal(p)
    store.apply_decision(ApprovalDecision(proposal_id=p.proposal_id,status='approved',decided_at=NOW))
    before=replay_book(store,active)
    store.save_proposal(store.get_proposal(p.proposal_id).model_copy(update={'status':ProposalStatus.MISSED}))
    assert replay_book(store,active) == before


def test_cancel_api_records_reason_and_preserves_proposal_and_orders(recovery):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from systematic_trading.web.api import router
    settings,store,_,source = recovery
    app = FastAPI()
    app.state.settings, app.state.store = settings, store
    app.include_router(router)
    with TestClient(app) as client:
        response=client.post(f'/api/v1/proposals/{source.proposal_id}/cancel-rebalance',
            json={'operator':'Tester','reason':'Retire this objective'})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'cancelled'
    assert store.get_proposal(source.proposal_id).orders == source.orders
    assert store.list_broker_order_records() == []


@pytest.mark.parametrize('boundary', ['account', 'environment', 'strategy'])
def test_recovery_preserves_original_account_environment_and_strategy(recovery, boundary):
    from systematic_trading.live.deferred_rebalance import prepared_proposal
    from systematic_trading.domain.enums import OrderEnvironment
    settings, store, report, source = recovery
    options = {}
    if boundary == 'account':
        source = prepared_proposal(source, report)
        write_report(settings, report.model_copy(update={'managed_accounts':['DU456']}))
    if boundary == 'environment':
        source = source.model_copy(update={'orders':[o.model_copy(update={'environment':OrderEnvironment.LIVE}) for o in source.orders]})
    if boundary == 'strategy':
        options['automation_strategy_key'] = 'different-strategy'
    store.save_proposal(source)
    with pytest.raises(ValueError):
        refresh_rebalance(settings, store, source.proposal_id, now=NOW, order_client=Orders(), **options)
    assert len(store.list_proposals()) == 1
