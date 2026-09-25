"""Order IDs must remain unique after moving a ledger to another Gateway."""

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import ProposalStatus
from systematic_trading.execution.broker import InteractiveBrokersOrderRouter
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store
from test_ib_execution import FakeIBClient, _proposal, matched_reconciliation


@pytest.mark.parametrize("gateway_next", [1, 2000])
def test_restored_ledger_and_broker_sequence_are_both_respected(backend_store, gateway_next):
    store = backend_store
    original = _proposal(status=ProposalStatus.APPROVED)
    store.save_proposal(original)
    old_client = FakeIBClient(first_order_id=1000)
    InteractiveBrokersOrderRouter(AppSettings(), client=old_client).submit_approved_proposal(
        proposal=original, store=store,
    )
    history = store.list_broker_order_records(original.proposal_id)
    assert len(history) == 2
    new = original.model_copy(update={"proposal_id": "after-nas-handoff"})
    store.save_proposal(new)
    client = FakeIBClient(first_order_id=gateway_next)
    router = InteractiveBrokersOrderRouter(AppSettings(), client=client)

    result = router.submit_approved_proposal(proposal=new, store=store)

    first = max(gateway_next, 1002)
    assert result.validation_issues == []
    assert [row[0] for row in client.placed_orders] == [first, first + 1]
    assert store.list_broker_order_records(original.proposal_id) == history
    assert len(store.list_broker_order_records(new.proposal_id)) == 2
    repeated = router.submit_approved_proposal(proposal=new, store=store)
    assert repeated.validation_issues
    assert len(client.placed_orders) == 2


@pytest.mark.parametrize("fail_at", [0, 1])
def test_reservation_failure_stops_batch_and_preserves_approval(backend_store, monkeypatch, fail_at):
    store = backend_store
    proposal = _proposal(status=ProposalStatus.APPROVED)
    store.save_proposal(proposal)
    reserve = store.reserve_broker_order_record

    def fail_reservation(record, **kwargs):
        if record.order_index == fail_at:
            raise RuntimeError("simulated reservation failure")
        return reserve(record, **kwargs)

    monkeypatch.setattr(store, "reserve_broker_order_record", fail_reservation)
    client = FakeIBClient()
    result = InteractiveBrokersOrderRouter(AppSettings(), client=client).submit_approved_proposal(
        proposal=proposal, store=store,
    )

    assert len(client.placed_orders) == fail_at
    assert len(result.records) == fail_at
    assert client.disconnected
    assert "Submission stopped while reserving" in result.validation_issues[0]
    assert "Approval is retained" in result.validation_issues[0]
    assert store.get_proposal(proposal.proposal_id).status == ProposalStatus.APPROVED
    assert len(store.list_broker_order_records(proposal.proposal_id)) == fail_at
