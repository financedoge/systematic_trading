from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerExecutionFill
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderEnvironment, OrderSide, OrderType
from systematic_trading.domain.execution import BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.market import FXRate
from systematic_trading.execution.reconciliation import reconcile_ib_paper_account
from systematic_trading.live.account_snapshot import AccountSummaryRow, IbPositionRow
from systematic_trading.storage.sqlite import SQLiteStore


def test_ib_paper_reconciliation_reports_reset_divergence(tmp_path) -> None:
    store = _store_with_filled_order(tmp_path)
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path / "reconcile.db")

    report = reconcile_ib_paper_account(
        settings=settings,
        store=store,
        execution_client=_FakeExecutionClient(fills=[]),
        account_snapshot_client=_FakeAccountSnapshotClient(positions=[]),
        as_of=date(2026, 7, 12),
    )

    assert report.has_breaks is True
    assert report.local_filled_order_count == 1
    assert report.ib_fill_count == 0
    assert report.ib_position_count == 0
    assert [order.symbol for order in report.unmatched_local_orders] == ["SPY"]
    assert report.position_differences[0].symbol == "SPY"
    assert "account appears reset" in " ".join(report.suggested_actions)
    assert report.report_path is not None
    assert (tmp_path / "reconciliation" / "ib_paper_reconciliation_latest.json").exists()


def test_ib_paper_reconciliation_can_record_confirmed_empty_reset_baseline(tmp_path) -> None:
    store = _store_with_filled_order(tmp_path)
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path / "reconcile.db")

    report = reconcile_ib_paper_account(
        settings=settings,
        store=store,
        execution_client=_FakeExecutionClient(fills=[]),
        account_snapshot_client=_FakeAccountSnapshotClient(positions=[]),
        as_of=date(2026, 7, 12),
        record_pnl_reset_baseline=True,
        confirm_paper_reset=True,
    )

    baseline = store.latest_pnl_baseline()
    assert report.pnl_reset_baseline_id is not None
    assert baseline is not None
    assert baseline.baseline_id == report.pnl_reset_baseline_id
    assert baseline.open_lots == []
    assert baseline.filled_trade_count == 1
    assert report.reset_applied is True
    assert report.has_breaks is False

    follow_up = reconcile_ib_paper_account(
        settings=settings,
        store=store,
        execution_client=_FakeExecutionClient(fills=[]),
        account_snapshot_client=_FakeAccountSnapshotClient(positions=[]),
        as_of=date(2026, 7, 12),
    )
    assert follow_up.has_breaks is False
    assert follow_up.position_differences == []
    assert follow_up.local_filled_order_count == 0


def test_ib_reconciliation_reset_can_anchor_non_empty_broker_positions(tmp_path) -> None:
    store = _store_with_filled_order(tmp_path)
    store.upsert_fx_rate(
        FXRate(
            rate_date=date(2026, 7, 12),
            base_currency=Currency.USD,
            rate=Decimal("7.2"),
        )
    )
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path / "reconcile.db")
    broker_positions = [
        IbPositionRow(
            account="DU123",
            symbol="QQQ",
            security_type="STK",
            currency="USD",
            quantity=Decimal("4"),
            average_cost=Decimal("520"),
        )
    ]

    report = reconcile_ib_paper_account(
        settings=settings,
        store=store,
        execution_client=_FakeExecutionClient(fills=[]),
        account_snapshot_client=_FakeAccountSnapshotClient(positions=broker_positions),
        as_of=date(2026, 7, 12),
        record_pnl_reset_baseline=True,
        confirm_paper_reset=True,
    )

    baseline = store.latest_pnl_baseline()
    assert report.reset_applied is True
    assert report.has_breaks is False
    assert report.broker_positions[0].symbol == "QQQ"
    assert report.broker_positions[0].currency == Currency.USD
    assert baseline is not None
    assert baseline.source == "ib_broker_authoritative_reset"
    assert baseline.open_lots[0].symbol == "QQQ"
    assert baseline.open_lots[0].quantity == 4
    assert baseline.open_lots[0].cost_price == Decimal("520")
    assert baseline.open_lots[0].cost_fx_to_cnh == Decimal("7.2")


def test_ib_paper_reconciliation_requires_confirmation_before_reset_baseline(tmp_path) -> None:
    store = _store_with_filled_order(tmp_path)
    settings = AppSettings(data_dir=tmp_path, database_path=tmp_path / "reconcile.db")

    with pytest.raises(ValueError, match="confirm-paper-reset"):
        reconcile_ib_paper_account(
            settings=settings,
            store=store,
            execution_client=_FakeExecutionClient(fills=[]),
            account_snapshot_client=_FakeAccountSnapshotClient(positions=[]),
            as_of=date(2026, 7, 12),
            record_pnl_reset_baseline=True,
            confirm_paper_reset=False,
        )


def _store_with_filled_order(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "reconcile.db")
    store.initialize()
    order = OrderRequest(
        symbol="SPY",
        side=OrderSide.BUY,
        order_type=OrderType.TWAP,
        quantity=10,
        reference_price=Decimal("500"),
        currency=Currency.USD,
        environment=OrderEnvironment.PAPER,
        notional_cnh=Decimal("35000"),
        rationale="test",
    )
    proposal = TradeProposal(
        proposal_id="proposal-reset",
        created_at=datetime(2026, 7, 10, 1, 0, tzinfo=UTC),
        as_of=date(2026, 7, 10),
        sleeve="test",
        summary="test",
        orders=[order],
        reasoning=ProposalReasoning(summary="test"),
    )
    store.save_proposal(proposal)
    store.save_broker_order_record(
        BrokerOrderRecord(
            local_order_id="local-reset",
            proposal_id=proposal.proposal_id,
            environment=OrderEnvironment.PAPER,
            order_index=0,
            order=order,
            order_ref="st-proposal-reset-00",
            broker_order_id=100,
            status=BrokerOrderStatus.FILLED,
            submitted_at=datetime(2026, 7, 10, 1, 5, tzinfo=UTC),
            updated_at=datetime(2026, 7, 10, 1, 6, tzinfo=UTC),
            filled_quantity=10,
            remaining_quantity=0,
            average_fill_price=Decimal("501"),
        )
    )
    return store


class _FakeExecutionClient:
    def __init__(self, fills: list[BrokerExecutionFill]) -> None:
        self.fills = fills

    def fetch_fills(self, profile):
        return self.fills


class _FakeAccountSnapshotClient:
    def __init__(self, positions) -> None:
        self.positions = positions

    def fetch(self, profile):
        return (
            [AccountSummaryRow(account="DU123", tag="TotalCashValue", value="100000", currency="USD")],
            self.positions,
            ["DU123"],
        )
