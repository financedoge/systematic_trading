from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures('neutral_usd_publication')
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


def missed_prepared_rebalance(setup, *, provenance=None, identifier='missed-handover'):
    """Expired application-prepared handover with no broker attempt (the 2026-10-16 case)."""
    settings, store, report = setup
    from systematic_trading.live.deferred_rebalance import prepared_proposal
    staged = stage(setup)
    inner = store.get_proposal(staged.proposal_id)
    with store._connect() as connection:
        connection.execute('DELETE FROM proposals')
    source_provenance = dict(inner.input_provenance, allocation=dict(version='legacy'))
    source_provenance.update(provenance or {})
    source = prepared_proposal(inner.model_copy(update=dict(
        proposal_id=identifier, trigger='allocation_handover', status=ProposalStatus.MISSED,
        automation_strategy_key=None, missed_at=NOW-timedelta(minutes=1),
        execution_deadline_at=NOW-timedelta(minutes=1),
        input_provenance=source_provenance)), report)
    store.save_proposal(source)
    return source


def fake_renewal(monkeypatch, store, source, *, fail=None):
    calls = []

    def refresh(settings, store, proposal_id, *, now=None, automation_strategy_key=None,
                automation_policy_revision=None, order_client=None):
        calls.append(dict(proposal_id=proposal_id, automation_strategy_key=automation_strategy_key,
            automation_policy_revision=automation_policy_revision, now=now))
        if fail is not None:
            raise fail
        successor = source.model_copy(update=dict(
            proposal_id='renew-'+proposal_id, status=ProposalStatus.PENDING,
            trigger='deferred_rebalance', created_at=now,
            execution_deadline_at=NOW+timedelta(minutes=45),
            automation_strategy_key=automation_strategy_key,
            input_provenance=dict(source.input_provenance,
                deferred_rebalance=dict(previous_proposal_id=proposal_id,
                    root_proposal_id=proposal_id))))
        store.save_proposal(successor)
        return successor

    monkeypatch.setattr('systematic_trading.live.deferred_rebalance.refresh_rebalance', refresh)
    return calls


def test_auto_policy_renews_one_missed_prepared_rebalance_and_routes_successor(setup, monkeypatch):
    settings, store, report = setup
    route = Router()
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=route)
    configure(controller)
    source = missed_prepared_rebalance(setup)
    calls = fake_renewal(monkeypatch, store, source)
    at = NOW+timedelta(minutes=3)
    write_report(settings, report.model_copy(update={'checked_at':at}))

    controller.tick(now=at)

    assert calls == [dict(proposal_id='missed-handover',
        automation_strategy_key=controller.policy.strategy_key,
        automation_policy_revision=controller.policy.revision, now=at)], controller.policy.message
    renewal = controller.policy.renewals['missed-handover']
    assert renewal['outcome'] == 'renewed' and renewal['proposal_id'] == 'renew-missed-handover'
    renewed = store.get_proposal('renew-missed-handover')
    assert renewed.automation_strategy_key == controller.policy.strategy_key
    assert renewed.status == ProposalStatus.APPROVED
    assert len(route.calls) == 1
    assert controller.policy.attempts['renew-missed-handover']['outcome'] == 'submitted'
    assert store.get_proposal('missed-handover').status == ProposalStatus.MISSED

    # A settled renewal is never repeated, even on later ticks.
    controller.tick(now=at+timedelta(minutes=1))
    assert len(calls) == 1 and len(route.calls) == 1


def test_auto_policy_does_not_renew_without_enablement_or_catch_up_authorization(setup, monkeypatch):
    settings, store, report = setup
    source = missed_prepared_rebalance(setup,
        provenance={'late_handover': dict(authorized_at=NOW.isoformat())})
    calls = fake_renewal(monkeypatch, store, source)
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=Router())
    at = NOW+timedelta(minutes=3)
    controller.tick(now=at)
    assert not calls and not controller.policy.renewals
    # An enabled policy never extends a session-limited operator catch-up authorization.
    configure(controller)
    write_report(settings, report.model_copy(update={'checked_at':at}))
    controller.tick(now=at)
    assert not calls and 'missed-handover' not in controller.policy.renewals


def test_auto_policy_does_not_renew_a_claimed_attempt_or_superseded_intent(setup, monkeypatch):
    settings, store, report = setup
    source = missed_prepared_rebalance(setup)
    calls = fake_renewal(monkeypatch, store, source)
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=Router())
    configure(controller)
    at = NOW+timedelta(minutes=3)
    write_report(settings, report.model_copy(update={'checked_at':at}))
    controller.policy.attempts['missed-handover'] = dict(outcome='review', error='routing failed')
    controller.tick(now=at)
    assert not calls
    # An existing pending successor supersedes the expired intent.
    controller.policy.attempts.clear()
    store.save_proposal(source.model_copy(update=dict(proposal_id='renew-manual', status=ProposalStatus.PENDING,
        trigger='deferred_rebalance', created_at=NOW, execution_deadline_at=NOW+timedelta(hours=1),
        input_provenance=dict(source.input_provenance,
            deferred_rebalance=dict(previous_proposal_id='missed-handover')))))
    store.save_proposal(source.model_copy(update=dict(status=ProposalStatus.MISSED)))
    controller.tick(now=at)
    assert not calls


def test_auto_policy_retries_a_blocked_renewal_after_cooldown(setup, monkeypatch):
    settings, store, report = setup
    source = missed_prepared_rebalance(setup)
    calls = fake_renewal(monkeypatch, store, source,
        fail=ValueError('Account balances changed since preparation. Refresh the rebalance and review the new orders.'))
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=Router())
    configure(controller)
    at = NOW+timedelta(minutes=3)
    write_report(settings, report.model_copy(update={'checked_at':at}))

    controller.tick(now=at)
    assert len(calls) == 1
    blocked = controller.policy.renewals['missed-handover']
    assert blocked['outcome'] == 'blocked' and 'Account balances changed' in blocked['error']
    assert 'blocked' in controller.policy.message

    controller.tick(now=at+timedelta(seconds=60))
    assert len(calls) == 1  # Cooldown prevents a tight retry loop.
    controller.tick(now=at+timedelta(seconds=controller.RENEWAL_RETRY_SECONDS+1))
    assert len(calls) == 2


@pytest.mark.parametrize("new_status", [ProposalStatus.PENDING, ProposalStatus.APPROVED, ProposalStatus.REJECTED])
@pytest.mark.parametrize("new_prepared", [True, False])
def test_auto_renewal_never_falls_back_to_an_older_independent_intent(setup, monkeypatch, new_status, new_prepared):
    settings, store, _ = setup
    source = missed_prepared_rebalance(setup)
    newer = source.model_copy(update=dict(
        proposal_id="newer-monthly-intent", created_at=source.created_at + timedelta(seconds=1),
        status=new_status, execution_deadline_at=NOW + timedelta(hours=1),
        input_provenance={k: v for k, v in source.input_provenance.items()
                          if new_prepared or k != "prepared_account"}))
    store.save_proposal(newer)
    calls = fake_renewal(monkeypatch, store, source)
    controller = PaperAutoApproval(settings, store, order_client=Orders(), router=Router())
    configure(controller)
    # The newer intent is not a lineage child of the old one. Its pending,
    # submitted or rejected status must never resurrect the old target.
    if new_status == ProposalStatus.APPROVED:
        controller.policy.attempts[newer.proposal_id] = dict(outcome="submitted")
    assert controller._renew_missed_rebalance(NOW + timedelta(minutes=3)) is None
    assert not calls


def test_renewed_rebalance_trigger_is_eligible_for_the_auto_policy(setup):
    controller, route, proposal, at = ready(setup)
    controller.store.save_proposal(proposal.model_copy(update={'trigger': 'deferred_rebalance'}))
    controller.tick(now=at)
    assert len(route.calls) == 1, controller.policy.message
    assert controller.store.get_proposal(proposal.proposal_id).status == ProposalStatus.APPROVED


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
