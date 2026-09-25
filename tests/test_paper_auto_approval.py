from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment, ProposalStatus
from systematic_trading.domain.execution import ApprovalDecision, BrokerOrderRecord, BrokerSubmissionResult
from systematic_trading.live.auto_approval import PaperAutoApproval, PaperApprovalUpdate
from test_initial_allocation import setup, history_db, stage, NOW, Orders, write_report
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store


class Router:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def submit_approved_proposal(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise TimeoutError('Uncertain broker response')
        p = kw['proposal']
        records = [BrokerOrderRecord(proposal_id=p.proposal_id, order_index=i, order=o,
                    order_ref=f'auto-{i}', status=BrokerOrderStatus.SUBMITTED) for i,o in enumerate(p.orders)]
        return BrokerSubmissionResult(proposal_id=p.proposal_id, environment=OrderEnvironment.PAPER, records=records)


def configure(controller, **updates):
    values = dict(enabled=True, expected_revision=controller.policy.revision, confirm=True,
                  operator='Tester', reason='Paper automation test', max_batch_notional_cnh='2000000')
    values.update(updates)
    return controller.configure(PaperApprovalUpdate(**values), now=NOW-timedelta(seconds=1))


def ready(setup):
    settings, store, report = setup
    route = Router()
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=route)
    configure(controller)
    proposal = store.get_proposal(stage(setup).proposal_id)
    at = NOW+timedelta(minutes=3)
    write_report(settings, report.model_copy(update={'checked_at':at}))
    return controller, route, proposal, at


def test_manual_default_never_routes(setup):
    settings, store, _ = setup
    stage(setup)
    route = Router()
    controller = PaperAutoApproval(settings, store, router=route)
    controller.tick(now=NOW)
    assert not controller.status().enabled
    assert not route.calls


def test_new_strategy_proposal_approves_and_routes_once_with_audit(setup):
    c, route, p, at = ready(setup)
    c.tick(now=at)
    assert len(route.calls) == 1, c.policy.message
    assert route.calls[0]['allow_resubmit'] is False
    assert c.store.get_proposal(p.proposal_id).status == ProposalStatus.APPROVED
    assert c.policy.attempts[p.proposal_id]['outcome'] == 'submitted'
    c.tick(now=at)
    assert len(route.calls) == 1
    restarted = PaperAutoApproval(c.settings,c.store,router=route)
    assert restarted.policy.enabled
    assert restarted.policy.attempts == c.policy.attempts
    configure(c, enabled=False)
    assert not c.status().enabled


@pytest.mark.parametrize('case', ['old','wrong_strategy','rejected','future','before_window','expired','stale_data','cap','changed_orders','open_broker_order','stale_reconciliation','account_changed','cash_liability'])
def test_auto_gates_preserve_unapproved_state(setup, case):
    c, route, p, at = ready(setup)
    updates = {}
    if case == 'old': updates['created_at'] = NOW-timedelta(days=1)
    if case == 'wrong_strategy': updates['automation_strategy_key'] = 'another-strategy'
    if case == 'rejected': updates['status'] = ProposalStatus.REJECTED
    if case == 'future': updates['intended_trade_date'] = at.date()+timedelta(days=1)
    if case == 'before_window': at = NOW
    if case == 'expired': at += timedelta(hours=1)
    if case == 'stale_data': updates['as_of'] = p.as_of-timedelta(days=1)
    if case == 'cap': c.policy.max_batch_notional_cnh = Decimal('1')
    if case == 'changed_orders': updates['orders'] = [p.orders[0].model_copy(update={'quantity':1}),*p.orders[1:]]
    if case == 'open_broker_order': c.order_client = Orders([{'status':'Submitted','source':'open','order_ref':'external','broker_order_id':999}])
    if case in {'stale_reconciliation','account_changed','cash_liability'}:
        _, _, report = setup
        change={'checked_at':at-timedelta(seconds=181)} if case=='stale_reconciliation' else (
            {'checked_at':at,'managed_accounts':['DU999']} if case=='account_changed' else
            {'checked_at':at,'broker_cash':[{'currency':'HKD','amount':'-1'}]})
        write_report(c.settings,report.model_copy(update=change))
    c.store.save_proposal(p.model_copy(update=updates))
    c.tick(now=at)
    assert not route.calls, c.policy.message
    assert c.store.get_proposal(p.proposal_id).status != ProposalStatus.APPROVED


def test_uncertain_attempt_and_restart_never_auto_retry(setup):
    c, route, p, at = ready(setup)
    route.fail = True
    c.tick(now=at)
    assert len(route.calls) == 1
    assert c.policy.attempts[p.proposal_id]['outcome'] == 'review'
    # Even if someone returns the proposal to pending, the attempt stays claimed.
    c.store.save_proposal(p)
    restarted = PaperAutoApproval(c.settings,c.store,order_client=Orders(),router=route)
    restarted.tick(now=at)
    assert len(route.calls) == 1


def test_policy_confirmation_revision_machine_and_corruption(setup, monkeypatch):
    settings, store, _ = setup
    c = PaperAutoApproval(settings,store)
    with pytest.raises(ValueError,match='Confirm'): configure(c, confirm=False)
    configure(c)
    with pytest.raises(ValueError,match='changed'): configure(c, expected_revision=0)
    monkeypatch.setattr('systematic_trading.live.auto_approval.platform.node',lambda:'other-host')
    assert not PaperAutoApproval(settings,store).policy.enabled
    c.path.write_text('{bad',encoding='utf-8')
    assert not PaperAutoApproval(settings,store).policy.enabled


def test_atomic_approval_cannot_overwrite_operator_rejection(backend_store):
    store = backend_store
    store.apply_decision(ApprovalDecision(proposal_id='proposal',status=ProposalStatus.REJECTED))
    with pytest.raises(ValueError):
        store.apply_decision(ApprovalDecision(proposal_id='proposal',status=ProposalStatus.APPROVED), expected_status=ProposalStatus.PENDING)
    assert store.get_proposal('proposal').status == ProposalStatus.REJECTED


def test_disabled_service_api_remains_manual_and_rejects_enable(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path,database_path=tmp_path/'api.db',automation_enabled=False))) as client:
        assert not client.get('/api/v1/automation/paper-approval').json()['enabled']
        response=client.put('/api/v1/automation/paper-approval',json=dict(enabled=True,expected_revision=0,
            confirm=True,operator='Test',reason='Test'))
        assert response.status_code == 409
