from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.enums import ProposalStatus
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, latest_reconciliation_report_path, submission_reconciliation_issues
from systematic_trading.execution.window import expire_due_proposals
from systematic_trading.live.deferred_rebalance import prepared_proposal, prepared_submission_issues, refresh_rebalance
from systematic_trading.live.strategy_control import activation_issues
from systematic_trading.storage.sqlite import SQLiteStore

NOW = datetime(2026, 10, 5, 16, tzinfo=UTC)


def write_report(settings, report):
    path = latest_reconciliation_report_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(), encoding='utf-8')


@pytest.fixture
def case(tmp_path, monkeypatch):
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path/'test.db')
    store = SQLiteStore(settings.database_path)
    store.initialize()
    report = IBPaperReconciliationReport(checked_at=NOW-timedelta(days=3), managed_accounts=['DU123'],
        broker_cash=[dict(currency='USD', amount='1000')], local_order_history_count=0,
        local_order_count=0, local_filled_order_count=0, ib_fill_count=0, ib_position_count=0)
    write_report(settings, report)
    order = OrderRequest(symbol='SPY', side='buy', order_type='twap', quantity=2,
        reference_price=100, currency='USD', notional_cnh=1400, rationale='test',
        intended_trade_date=date(2026,10,2), execution_start_time='09:30', execution_end_time='10:00')
    original = prepared_proposal(TradeProposal(proposal_id='original', as_of=date(2026,10,1),
        intended_trade_date=date(2026,10,2), sleeve='test', summary='test', orders=[order],
        input_provenance=dict(allocation=dict(version='legacy')), reasoning=ProposalReasoning(summary='test')), report)
    store.save_proposal(original)
    def plan(**kwargs):
        return SimpleNamespace(validation_issues=[], proposal=original.model_copy(update=dict(
            as_of=kwargs['decision_date'], intended_trade_date=kwargs['intended_trade_date'],
            orders=[order.model_copy(update=dict(reference_price=Decimal(110), notional_cnh=Decimal(1540),
                intended_trade_date=kwargs['intended_trade_date']))])))
    monkeypatch.setattr('systematic_trading.live.allocated_plan.build_allocated_plan', plan)
    return settings, store, report, original


def test_stale_snapshot_is_warning_for_preparation_but_blocks_routing(case):
    settings, store, report, original = case
    assert activation_issues(settings, store, NOW) == []
    assert submission_reconciliation_issues(settings, now=NOW)
    assert prepared_submission_issues(settings, store, original) == []
    from systematic_trading.execution.broker import InteractiveBrokersOrderRouter
    approved = original.model_copy(update=dict(status=ProposalStatus.APPROVED))
    issues = InteractiveBrokersOrderRouter(settings).validate_proposal_for_submission(
        proposal=approved, store=store, environment=original.orders[0].environment)
    assert any('180 seconds' in issue for issue in issues)
    write_report(settings, report.model_copy(update=dict(checked_at=NOW+timedelta(seconds=10))))
    assert any('future-dated' in issue for issue in activation_issues(settings, store, NOW))


def test_missed_intent_refreshes_offline_once_without_carrying_approval(case):
    settings, store, report, original = case
    expire_due_proposals(store, settings, now=NOW)
    saved = refresh_rebalance(settings, store, 'original', now=NOW)
    assert saved.status == ProposalStatus.PENDING
    assert saved.orders[0].reference_price == 110
    assert saved.orders[0].benchmark_reference_price == 100
    assert saved.orders[0].slippage_trade_date == date(2026,10,2)
    assert saved.orders[0].intended_trade_date == NOW.date()
    assert saved.automation_strategy_key is None
    assert len(store.list_broker_order_records()) == 1  # Only the original missed marker.
    assert store.list_broker_order_records()[0].status.value == 'missed'
    assert refresh_rebalance(settings, store, 'original', now=NOW).proposal_id == saved.proposal_id
    assert len(store.list_proposals()) == 2
    assert any('newer proposal' in issue for issue in prepared_submission_issues(settings, store, original))
    later = refresh_rebalance(settings, store, saved.proposal_id, now=NOW+timedelta(days=1))
    assert later.orders[0].benchmark_reference_price == 100
    assert later.input_provenance['deferred_rebalance']['root_proposal_id'] == 'original'
    assert store.get_proposal('original').orders == original.orders


@pytest.mark.parametrize('updates', [dict(status='pending_submit'), dict(status='submitted'),
    dict(status='partially_filled', filled_quantity=1), dict(status='filled', filled_quantity=2),
    dict(status='cancelled'), dict(status='missed', broker_order_id=123),
    dict(status='missed', pending_action={'action':'cancel'}),
    dict(status='missed', execution_sync_issue='uncertain')])
def test_attempts_uncertainty_and_partial_fills_cannot_be_replayed(case, updates):
    settings, store, _, original = case
    record = BrokerOrderRecord(proposal_id='original', order_index=0, order=original.orders[0], order_ref='test')
    store.save_broker_order_record(BrokerOrderRecord.model_validate(dict(record.model_dump(), **updates)))
    with pytest.raises(ValueError):
        refresh_rebalance(settings, store, 'original', now=NOW)
    assert len(store.list_proposals()) == 1


def test_account_change_requires_new_review_and_old_allocation_cannot_refresh(case):
    settings, store, report, original = case
    write_report(settings, report.model_copy(update=dict(broker_cash=[dict(currency='USD',amount='950')])))
    assert any('balances changed' in issue for issue in prepared_submission_issues(settings, store, original))
    saved = refresh_rebalance(settings, store, 'original', now=NOW)
    assert saved.status == ProposalStatus.PENDING
    assert prepared_submission_issues(settings, store, saved) == []
    from systematic_trading.portfolio.strategy_allocation import control_state, scope_for
    state = control_state(store)
    store.commit_strategy_control(scope_for(store),0,dict(state,active=dict(state['active'],version='new')),
        dict(event_id='change-version',request_hash='change-version'))
    with pytest.raises(ValueError, match='previous trading allocation'):
        refresh_rebalance(settings, store, 'original', now=NOW)


def test_late_ancestor_execution_blocks_second_renewal(case):
    settings, store, _, original = case
    saved = refresh_rebalance(settings, store, 'original', now=NOW)
    store.save_broker_order_record(BrokerOrderRecord(proposal_id='original', order_index=0,
        order=original.orders[0],order_ref='late-fill',status='filled',filled_quantity=2))
    with pytest.raises(ValueError, match='broker attempt'):
        refresh_rebalance(settings, store, saved.proposal_id, now=NOW+timedelta(days=1))


def test_rejected_intent_does_not_get_another_chance_without_allocation_review(case):
    settings, store, _, original = case
    store.save_proposal(original.model_copy(update=dict(status=ProposalStatus.REJECTED)))
    with pytest.raises(ValueError, match='rejected'):
        refresh_rebalance(settings, store, 'original', now=NOW)


def test_api_refresh_requires_usual_approval_and_cannot_route_stale_account(case):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from systematic_trading.web.api import router
    settings, store, _, _ = case
    app = FastAPI()
    app.state.settings, app.state.store = settings, store
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/api/v1/proposals/original/refresh-rebalance')
        assert response.status_code == 200, response.text
        refreshed = response.json()
        assert refreshed['status'] == 'pending'
        # Preview/preparation does not count as the operator's order decision.
        assert not store.strategy_approval_times()
        assert not store.list_broker_order_records()
        old = client.post('/api/v1/proposals/original/decisions', json=dict(status='approved'))
        assert old.status_code == 409


def test_pnl_slippage_uses_original_price_after_renewal(case):
    from systematic_trading.live.pnl import _broker_record_fills
    settings, store, _, original = case
    refreshed = refresh_rebalance(settings, store, 'original', now=NOW)
    record = BrokerOrderRecord(proposal_id=refreshed.proposal_id, order_index=0,
        order=refreshed.orders[0], order_ref='fill', status='filled', filled_quantity=2,
        average_fill_price=Decimal(112), submitted_at=NOW, updated_at=NOW)
    store.save_broker_order_record(record)
    reference = _broker_record_fills(store, [], use_reference_prices=True)
    actual = _broker_record_fills(store, [])
    assert reference[0].price == 100 and actual[0].price == 112
    assert (actual[0].price-reference[0].price)*actual[0].quantity == 24
