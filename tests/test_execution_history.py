from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerExecutionFill, BrokerOrderRecord, FXRate, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderSide, OrderType
from systematic_trading.execution.broker import IbApiExecutionSyncClient, InteractiveBrokersExecutionSynchronizer, InteractiveBrokersOrderRouter
from systematic_trading.execution.reconciliation import reconcile_ib_paper_account
from systematic_trading.live.account_snapshot import AccountSummaryRow, IbPositionRow
from systematic_trading.live.pnl import build_pnl_baseline
from systematic_trading.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path):
    store = SQLiteStore(tmp_path / "fills.db")
    store.initialize()
    order = OrderRequest(symbol="SPY", side=OrderSide.BUY, order_type=OrderType.MARKET,
                         quantity=10, reference_price=Decimal(100), currency=Currency.USD,
                         notional_cnh=Decimal(7000), rationale="test")
    proposal = TradeProposal(proposal_id="proposal", as_of=date(2026, 8, 3), sleeve="test", summary="test",
                             orders=[order], reasoning=ProposalReasoning(summary="test"))
    store.save_proposal(proposal)
    store.save_broker_order_record(BrokerOrderRecord(
        local_order_id="local", proposal_id="proposal", order_index=0, order=order,
        order_ref="st-proposal-00", broker_order_id=10, status=BrokerOrderStatus.SUBMITTED,
        submitted_at=datetime(2026, 8, 3, 13, tzinfo=UTC), remaining_quantity=10,
    ))
    return store


def fill(execution_id="trade-a.01", quantity=4, price="100", day=3, **changes):
    return BrokerExecutionFill(
        execution_id=execution_id, account="DU123", broker_order_id=10, order_ref="st-proposal-00",
        symbol="SPY", side=OrderSide.BUY, quantity=quantity, average_price=Decimal(price),
        filled_at=datetime(2026, 8, day, 15, tzinfo=UTC), currency=Currency.USD,
    ).model_copy(update=changes)


class Executions:
    def __init__(self, fills):
        self.fills = fills

    def fetch_fills(self, profile):
        return self.fills


def sync(store, fills):
    return InteractiveBrokersExecutionSynchronizer(AppSettings(), client=Executions(fills)).sync_order_fills(store=store)


def test_overlapping_partial_history_survives_restart_without_duplicate_events(store):
    first, second = fill(), fill("trade-b.01", 6, "110", 4)
    assert sync(store, [first]).records[0].filled_quantity == 4
    restarted = SQLiteStore(store.database_path)
    assert sync(restarted, [second]).records[0].filled_quantity == 10
    before = len(restarted.list_pending_platform_events())
    assert sync(restarted, [first, second, second]).records_updated == 0
    assert sync(restarted, []).records_updated == 0
    assert len(restarted.list_pending_platform_events()) == before
    record = restarted.list_broker_order_records()[0]
    assert record.status == BrokerOrderStatus.FILLED
    assert record.average_fill_price == Decimal("106.0000")
    assert len(record.execution_fills) == 2


def test_concurrent_fill_responses_accumulate_under_one_transaction(store):
    barrier = Barrier(2)

    def update(execution):
        barrier.wait(timeout=5)
        return store.apply_broker_execution_fills("local", [execution])

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(update, [fill(), fill("trade-b.01", 6, "110", 4)]))
    assert store.list_broker_order_records()[0].filled_quantity == 10


@pytest.mark.parametrize("bad, expected", [
    (fill(execution_id=None), "no execution ID"),
    (fill(quantity=11), "exceeds ordered"),
    (fill(side=OrderSide.SELL), "identity"),
    (fill(currency=Currency.CNH), "identity"),
    (fill(filled_at=datetime(2026, 8, 3)), "timezone"),
])
def test_invalid_evidence_is_a_durable_block_without_quantity_changes(store, bad, expected):
    result = sync(store, [bad])
    record = store.list_broker_order_records()[0]
    assert record.filled_quantity == 0
    assert expected in record.execution_sync_issue
    assert result.warnings
    assert sync(store, [fill()]).records_updated == 0
    assert store.list_broker_order_records()[0].filled_quantity == 0
    router = InteractiveBrokersOrderRouter(AppSettings())
    issues = router.validate_proposal_for_submission(proposal=store.get_proposal("proposal"), store=store)
    assert any("unresolved execution history" in issue for issue in issues)


@pytest.mark.parametrize("changed", [
    fill(price="101"), fill("trade-a.02"), fill("trade-b.01", account="DU999"),
])
def test_conflicts_corrections_and_account_changes_do_not_replace_history(store, changed):
    sync(store, [fill()])
    sync(store, [changed])
    record = store.list_broker_order_records()[0]
    assert record.filled_quantity == 4
    assert record.average_fill_price == Decimal(100)
    assert record.execution_fills == [fill()]
    assert record.execution_sync_issue
    with pytest.raises(ValueError, match="requires recovery"):
        build_pnl_baseline(store, cutoff_date=date(2026, 8, 4))


def test_legacy_aggregate_does_not_guess_overlap(store):
    record = store.list_broker_order_records()[0].model_copy(update={
        "filled_quantity": 4, "average_fill_price": Decimal(100), "remaining_quantity": 6,
    })
    store.save_broker_order_record(record)
    sync(store, [fill("trade-b.01", 6, "110", 4)])
    current = store.list_broker_order_records()[0]
    assert current.filled_quantity == 4
    assert "backfill" in current.execution_sync_issue


def test_numeric_id_collision_does_not_override_reference(store):
    old = store.list_broker_order_records()[0]
    store.save_broker_order_record(old.model_copy(update={"local_order_id": "other", "order_ref": "st-other-00"}))
    sync(store, [fill()])
    records = {r.local_order_id: r for r in store.list_broker_order_records()}
    assert records["local"].filled_quantity == 4
    assert records["other"].filled_quantity == 0
    assert sync(store, [fill(order_ref="unknown")]).records_updated == 0


def test_complete_cumulative_evidence_bootstraps_legacy_order(store):
    store.save_broker_order_record(store.list_broker_order_records()[0].model_copy(update={
        "filled_quantity": 4, "average_fill_price": Decimal(100), "remaining_quantity": 6,
    }))
    sync(store, [fill(cumulative_quantity=4), fill("trade-b.01", 6, "110", 4, cumulative_quantity=10)])
    record = store.list_broker_order_records()[0]
    assert record.execution_sync_issue is None
    assert record.filled_quantity == 10
    assert len(record.execution_fills) == 2


def test_cumulative_gap_blocks_truncated_initial_history(store):
    sync(store, [fill("trade-b.01", 6, "110", 4, cumulative_quantity=10)])
    record = store.list_broker_order_records()[0]
    assert "gap or overlap" in record.execution_sync_issue
    assert record.filled_quantity == 0


def test_delayed_acknowledgment_cannot_erase_synced_executions(store):
    stale = store.list_broker_order_records()[0]
    sync(store, [fill()])
    store.save_broker_order_record(stale)
    assert store.list_broker_order_records()[0].filled_quantity == 4
    assert store.list_broker_order_records()[0].status == BrokerOrderStatus.PARTIALLY_FILLED


def test_partial_cancel_remains_cancelled_after_new_fill(store):
    store.save_broker_order_record(store.list_broker_order_records()[0].model_copy(
        update={"status": BrokerOrderStatus.CANCELLED},
    ))
    sync(store, [fill()])
    assert store.list_broker_order_records()[0].status == BrokerOrderStatus.CANCELLED


def test_outbox_failure_rolls_back_execution_evidence(store, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr("systematic_trading.storage.sqlite._insert_platform_event", fail)
    with pytest.raises(RuntimeError, match="outbox"):
        sync(store, [fill()])
    assert store.list_broker_order_records()[0].execution_fills == []
    assert store.list_broker_order_records()[0].filled_quantity == 0


class Account:
    def __init__(self, quantity):
        self.quantity = quantity

    def fetch(self, profile):
        return ([AccountSummaryRow(account="DU123", tag="TotalCashValue", value="1000", currency="USD")],
                [IbPositionRow(account="DU123", symbol="SPY", security_type="STK", currency="USD",
                               quantity=Decimal(self.quantity), average_cost=Decimal(106))], ["DU123"])


def test_execution_dates_survive_pnl_collapse_and_short_reconciliation_history(store, tmp_path):
    for day in (3, 4):
        store.upsert_fx_rate(FXRate(rate_date=date(2026, 8, day), base_currency=Currency.USD, rate=Decimal(7)))
    sync(store, [fill()])
    first = store.save_pnl_baseline(build_pnl_baseline(store, cutoff_date=date(2026, 8, 3)))
    assert sum(lot.quantity for lot in first.open_lots) == 4
    sync(store, [fill("trade-b.01", 6, "110", 4)])
    report = reconcile_ib_paper_account(settings=AppSettings(data_dir=tmp_path), store=store,
                                       execution_client=Executions([]), account_snapshot_client=Account(10))
    assert not report.has_breaks
    assert report.unmatched_local_orders == []
    second = store.save_pnl_baseline(build_pnl_baseline(store, cutoff_date=date(2026, 8, 4)))
    assert sum(lot.quantity for lot in second.open_lots) == 10
    assert second.filled_trade_count == 2
    assert sum(lot.quantity * lot.cost_price for lot in second.open_lots) == Decimal(1060)


def test_reconciliation_detects_unsynced_correction_and_account_divergence(store, tmp_path):
    sync(store, [fill()])
    report = reconcile_ib_paper_account(settings=AppSettings(data_dir=tmp_path), store=store,
                                       execution_client=Executions([fill("trade-a.02")]), account_snapshot_client=Account(4))
    assert report.has_breaks
    assert "correction" in report.execution_issues[0]
    assert report.execution_issues[0] in report.warnings
    assert "No reconciliation breaks detected." not in report.suggested_actions
    divergent = reconcile_ib_paper_account(settings=AppSettings(data_dir=tmp_path), store=store,
                                          execution_client=Executions([]), account_snapshot_client=Account(0))
    assert divergent.has_breaks
    assert divergent.position_differences
    assert divergent.execution_issues


def test_reconciliation_checks_new_execution_batch_as_a_whole(store, tmp_path):
    sync(store, [fill(cumulative_quantity=4)])
    report = reconcile_ib_paper_account(
        settings=AppSettings(data_dir=tmp_path), store=store, account_snapshot_client=Account(10),
        execution_client=Executions([fill("trade-c.01", 4, "110", 4, cumulative_quantity=10),
                                     fill("trade-b.01", 2, "110", 4, cumulative_quantity=6)]),
    )
    assert report.has_breaks
    assert report.execution_issues == []
    assert "await durable synchronization" in report.execution_sync_pending[0]
    assert report.status == "sync_pending"
    assert not report.requires_operator_confirmation
    assert store.list_broker_order_records()[0].execution_sync_issue is None


def test_ib_callback_uses_execution_price_and_captures_identity(monkeypatch):
    client = pytest.importorskip("ibapi.client").EClient
    monkeypatch.setattr(client, "connect", lambda self, *args: self.nextValidId(1))
    monkeypatch.setattr(client, "run", lambda self: None)
    monkeypatch.setattr(client, "disconnect", lambda self: None)

    def request(self, *args):
        self.execDetails(1, SimpleNamespace(symbol="SPY", currency="USD"), SimpleNamespace(
            execId="trade-b.01", acctNumber="DU123", orderId=10, orderRef="st-proposal-00",
            side="BOT", shares=6, price=110, avgPrice=106, cumQty=10, time="20260804 15:00:00 UTC",
        ))
        self.execDetailsEnd(1)

    monkeypatch.setattr(client, "reqExecutions", request)
    profile = SimpleNamespace(host="unused", port=0, client_id=1)
    result = IbApiExecutionSyncClient().fetch_fills(profile)
    assert result[0].average_price == Decimal(110)
    assert result[0].execution_id == "trade-b.01"
    assert result[0].account == "DU123"
    assert result[0].cumulative_quantity == 10
