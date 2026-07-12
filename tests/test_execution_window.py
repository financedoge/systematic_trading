from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.execution.window import attach_execution_deadline, execution_deadline, expire_due_proposals
from systematic_trading.storage.sqlite import SQLiteStore


def test_deadline_is_configured_minutes_after_new_york_open() -> None:
    settings = AppSettings(execution_rebalance_timeout_minutes=30)
    proposal = _proposal(intended_trade_date=date(2026, 7, 13))

    deadline = execution_deadline(proposal, settings)

    assert deadline == datetime(2026, 7, 13, 14, 0, tzinfo=UTC)


def test_pending_proposal_expires_to_missed_with_order_records(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "window.db", execution_rebalance_timeout_minutes=30)
    store = SQLiteStore(settings.database_path)
    store.initialize()
    proposal = attach_execution_deadline(_proposal(intended_trade_date=date(2026, 7, 13)), settings)
    store.save_proposal(proposal)

    expired = expire_due_proposals(store, settings, now=datetime(2026, 7, 13, 14, 1, tzinfo=UTC))

    assert len(expired) == 1
    stored = store.get_proposal(proposal.proposal_id)
    assert stored is not None
    assert stored.status == ProposalStatus.MISSED
    assert stored.missed_at == datetime(2026, 7, 13, 14, 1, tzinfo=UTC)
    records = store.list_broker_order_records(proposal.proposal_id)
    assert [record.status for record in records] == [BrokerOrderStatus.MISSED]
    assert records[0].remaining_quantity == proposal.orders[0].quantity


def test_accepted_broker_order_is_not_expired(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "accepted.db", execution_rebalance_timeout_minutes=30)
    store = SQLiteStore(settings.database_path)
    store.initialize()
    proposal = attach_execution_deadline(
        _proposal(intended_trade_date=date(2026, 7, 13), status=ProposalStatus.APPROVED),
        settings,
    )
    store.save_proposal(proposal)
    store.save_broker_order_record(
        BrokerOrderRecord(
            proposal_id=proposal.proposal_id,
            order_index=0,
            order=proposal.orders[0],
            order_ref="accepted-order",
            status=BrokerOrderStatus.SUBMITTED,
            submitted_at=datetime(2026, 7, 13, 13, 31, tzinfo=UTC),
        )
    )

    expired = expire_due_proposals(store, settings, now=datetime(2026, 7, 13, 14, 1, tzinfo=UTC))

    assert expired == []
    assert store.get_proposal(proposal.proposal_id).status == ProposalStatus.APPROVED


def test_api_blocks_late_approval_and_reports_missed_notional(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "late-api.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        proposal = _proposal(intended_trade_date=date(2020, 1, 2))
        client.app.state.store.save_proposal(proposal)

        approval = client.post(
            f"/api/v1/proposals/{proposal.proposal_id}/approve-and-submit",
            json={"comment": "too late"},
        )
        listed = client.get("/api/v1/proposals")
        quality = client.get("/api/v1/dashboard/execution-quality")

    assert approval.status_code == 409
    assert listed.json()[0]["status"] == "missed"
    assert listed.json()[0]["missed_reason"]
    assert quality.json()["missed_order_count"] == 1
    assert quality.json()["missed_notional_cnh"] == "36000.00"


def _proposal(
    *,
    intended_trade_date: date,
    status: ProposalStatus = ProposalStatus.PENDING,
) -> TradeProposal:
    return TradeProposal(
        proposal_id="window-test",
        as_of=date(2026, 7, 10),
        intended_trade_date=intended_trade_date,
        status=status,
        sleeve="test",
        summary="Timed rebalance",
        orders=[
            OrderRequest(
                symbol="SPY",
                side=OrderSide.BUY,
                order_type=OrderType.TWAP,
                quantity=10,
                reference_price=Decimal("500"),
                currency=Currency.USD,
                environment=OrderEnvironment.PAPER,
                notional_cnh=Decimal("36000"),
                rationale="test",
                intended_trade_date=intended_trade_date,
                execution_start_time="09:30",
                execution_end_time="10:00",
            )
        ],
        reasoning=ProposalReasoning(summary="test"),
    )
