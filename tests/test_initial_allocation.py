from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from shutil import copyfile
from threading import Barrier
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import FXRate, PnLBaseline
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderType, ProposalStatus
from systematic_trading.domain.execution import ApprovalDecision, BrokerOrderRecord, ProposalReasoning, TradeProposal
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, latest_reconciliation_report_path
from systematic_trading.live.initial_allocation import initial_allocation_window, stage_initial_allocation, stage_portfolio_alignment, latest_monthly_target_date
from systematic_trading.live.sota import AccountPositionInput, LiveAccountSnapshotInput
from systematic_trading.live.market_data import MarketDataRefreshResult
from systematic_trading.research import current_sota_definition
from systematic_trading.live.management_service import TradingManagementService, TradingServiceStatus
from systematic_trading.storage.sqlite import SQLiteStore
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store
from test_trading_management_service import _seed_sota_history

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 18, 11, 15, tzinfo=NY)
DECISION = date(2026, 8, 17)


class Orders:
    def __init__(self, rows=None, fail=False):
        self.rows = rows or []
        self.fail = fail
        self.calls = 0

    def connect(self, profile):
        self.calls += 1

    def snapshot(self):
        if self.fail:
            raise TimeoutError("Snapshot incomplete")
        return self.rows

    def disconnect(self):
        pass


@pytest.fixture(scope="module")
def history_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("initial-history") / "template.db"
    store = SQLiteStore(path)
    store.initialize()
    _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=DECISION, base_currency=Currency.USD, rate=Decimal("7.20")))
    store.upsert_fx_rate(FXRate(rate_date=DECISION, base_currency=Currency.HKD, rate=Decimal("0.92")))
    return path


@pytest.fixture
def setup(tmp_path, history_db):
    path = tmp_path / "initial.db"
    copyfile(history_db, path)
    settings = AppSettings(data_dir=tmp_path, database_path=path, automation_enabled=True, automation_queue_rebalance=True)
    store = SQLiteStore(path)
    report = IBPaperReconciliationReport(checked_at=NOW, managed_accounts=["DU123"],
        broker_cash=[dict(currency="HKD", amount="1000000")], local_order_history_count=0,
        local_order_count=0, local_filled_order_count=0, ib_fill_count=0, ib_position_count=0)
    write_report(settings, report)
    return settings, store, report


def write_report(settings, report):
    path = latest_reconciliation_report_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(), encoding="utf-8")


def stage(setup, **kwargs):
    settings, store, _ = setup
    return stage_initial_allocation(settings=settings, store=store, now=NOW, order_client=kwargs.get("client", Orders()))


@pytest.mark.parametrize("at, decision, start, end", [
    ("2026-09-25T08:00", "2026-09-24", "2026-09-25T09:30", "2026-09-25T10:00"),
    ("2026-09-25T11:15", "2026-09-24", "2026-09-25T11:18", "2026-09-25T11:48"),
    ("2026-09-25T15:45", "2026-09-24", "2026-09-28T09:30", "2026-09-28T10:00"),
    ("2026-09-25T17:00", "2026-09-25", "2026-09-28T09:30", "2026-09-28T10:00"),
    ("2026-09-26T12:00", "2026-09-25", "2026-09-28T09:30", "2026-09-28T10:00"),
    ("2026-09-07T08:00", "2026-09-04", "2026-09-08T09:30", "2026-09-08T10:00"),
    ("2026-11-27T12:45", "2026-11-25", "2026-11-30T09:30", "2026-11-30T10:00"),
])
def test_window_respects_sessions_holidays_and_early_close(at, decision, start, end):
    result = initial_allocation_window(AppSettings(), datetime.fromisoformat(at).replace(tzinfo=NY))
    assert result == (date.fromisoformat(decision), datetime.fromisoformat(start).replace(tzinfo=NY),
        datetime.fromisoformat(end).replace(tzinfo=NY))


def test_empty_account_stages_intraday_twap_once_without_submitting(setup):
    settings, store, _ = setup
    client = Orders()
    result = stage(setup, client=client)
    assert result.status == "queued"
    proposal = store.get_proposal(result.proposal_id)
    assert proposal.trigger == "empty_portfolio"
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.as_of == DECISION  # Seed also contains future bars; they must not be used.
    assert proposal.intended_trade_date == NOW.date()
    assert proposal.orders and all(order.order_type == OrderType.TWAP for order in proposal.orders)
    assert {order.execution_start_time for order in proposal.orders} == {"11:18"}
    assert {order.execution_end_time for order in proposal.orders} == {"11:48"}
    assert proposal.execution_deadline_at == NOW.replace(hour=11, minute=48).astimezone(UTC)
    assert not store.list_broker_order_records()
    assert stage(setup, client=client).status == "pending"
    assert client.calls == 1
    assert len(store.list_proposals()) == 1
    assert result.artifact_path


@pytest.mark.parametrize("updates, expected", [
    ({"checked_at": NOW - timedelta(seconds=181)}, "blocked"),
    ({"checked_at": NOW + timedelta(seconds=10)}, "blocked"),
    ({"execution_issues": ["unmatched execution"]}, "blocked"),
    ({"warnings": ["incomplete account summary"]}, "blocked"),
    ({"managed_accounts": ["U123"]}, "blocked"),
    ({"managed_accounts": ["DU123", "DU456"]}, "blocked"),
    ({"broker_cash": []}, "blocked"),
    ({"broker_cash": [{"currency": "HKD", "amount": "0"}]}, "blocked"),
    ({"broker_cash": [{"currency": "USD", "amount": "-100"}, {"currency": "HKD", "amount": "1000"}]}, "blocked"),
    ({"ib_position_count": 1}, "invested"),
    ({"broker_positions": [{"symbol": "OUTSIDE", "quantity": 1}]}, "invested"),
])
def test_account_gates_do_not_create_proposals(setup, updates, expected):
    settings, store, report = setup
    write_report(settings, IBPaperReconciliationReport.model_validate({**report.model_dump(), **updates}))
    client = Orders()
    assert stage(setup, client=client).status == expected
    assert not store.list_proposals()
    assert client.calls == 0


@pytest.mark.parametrize("what", ["bars", "usd_fx", "hkd_fx"])
def test_missing_data_blocks_initial_allocation(setup, monkeypatch, what):
    _, store, _ = setup
    if what == "bars":
        monkeypatch.setattr(store, "list_price_bars", lambda *a, **kw: [])
    else:
        original = store.list_fx_rates
        currency = Currency.USD if what == "usd_fx" else Currency.HKD
        monkeypatch.setattr(store, "list_fx_rates", lambda c, **kw: [] if c == currency else original(c, **kw))
    client = Orders()
    result = stage(setup, client=client)
    assert result.status == "blocked"
    assert not store.list_proposals()
    assert client.calls == 0


@pytest.mark.parametrize("status", ["Submitted", "PendingCancel", "Inactive", "Unknown", ""])
def test_any_broker_open_or_uncertain_order_prevents_building(setup, status):
    assert stage(setup, client=Orders([dict(status=status)])).status == "blocked"
    assert not setup[1].list_proposals()


def test_incomplete_broker_snapshot_fails_closed(setup):
    with pytest.raises(TimeoutError):
        stage(setup, client=Orders(fail=True))
    assert not setup[1].list_proposals()


@pytest.mark.parametrize("status", [ProposalStatus.APPROVED, ProposalStatus.REJECTED])
def test_existing_operator_decision_is_never_replaced(setup, status):
    _, store, _ = setup
    initial = stage(setup)
    store.apply_decision(ApprovalDecision(proposal_id=initial.proposal_id, status=status))
    assert stage(setup).status == "review"
    assert store.get_proposal(initial.proposal_id).status == status
    assert len(store.list_proposals()) == 1


@pytest.mark.parametrize("status, before_baseline, uncertain, expected", [
    (BrokerOrderStatus.SUBMITTED, False, False, "blocked"),
    (BrokerOrderStatus.SUBMITTED, True, False, "queued"),
    (BrokerOrderStatus.PENDING_SUBMIT, True, False, "blocked"),
    (BrokerOrderStatus.SUBMITTED, True, True, "blocked"),
])
def test_local_orders_and_reconciled_history(setup, status, before_baseline, uncertain, expected):
    _, store, _ = setup
    # Reuse an actual generated order, then remove only the proposal from this test DB.
    initial = stage(setup)
    order = store.get_proposal(initial.proposal_id).orders[0]
    with store._connect() as connection:
        connection.execute("DELETE FROM proposals")
    store.save_pnl_baseline(PnLBaseline(cutoff_at=NOW - timedelta(days=1)))
    store.save_broker_order_record(BrokerOrderRecord(proposal_id="old", order_index=0, order=order,
        order_ref="old", status=status, submitted_at=NOW - timedelta(days=2) if before_baseline else NOW,
        execution_sync_issue="unknown" if uncertain else None))
    assert stage(setup).status == expected


def test_service_checks_initial_allocation_before_eod_and_exposes_blocker(setup, monkeypatch):
    settings, store, _ = setup
    service = TradingManagementService(settings=settings, store=store, order_management_client=Orders())
    monkeypatch.setattr(service, "_execution_sync_due", lambda now: False)
    monkeypatch.setattr(service, "_refresh_eod_backlog", lambda now: None)
    monkeypatch.setattr(service, "_eod_due", lambda now: False)
    status = service.run_once(now=NOW)
    assert status.portfolio_alignment_status == "queued"
    assert status.last_rebalance_proposal_id == status.portfolio_alignment_proposal_id
    assert "approval" in status.portfolio_alignment_message


def test_atomic_queue_preserves_decision_and_emits_one_event(backend_store):
    store = backend_store
    proposal = store.get_proposal("proposal").model_copy(update={"proposal_id": "initial-atomic", "trigger": "empty_portfolio"})
    barrier = Barrier(2)
    def enqueue():
        barrier.wait(timeout=10)
        return store.queue_proposal_once(proposal)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: enqueue(), range(2)))
    assert results[0] == results[1]
    store.apply_decision(ApprovalDecision(proposal_id=proposal.proposal_id, status=ProposalStatus.REJECTED))
    assert store.queue_proposal_once(proposal).status == ProposalStatus.REJECTED
    events = [record for record in store.list_platform_event_outbox_records(limit=100)
        if record.event_type == "proposal.created" and record.payload.payload.proposal_id == proposal.proposal_id]
    assert len(events) == 1


def invested_setup(setup, drift):
    settings, store, report = setup
    positions = [AccountPositionInput(symbol=s, quantity=1000) for s in ("SPY", "TLT")]
    report = report.model_copy(update={"ib_position_count": 2, "broker_positions": positions,
        "broker_cash": [dict(currency="USD", amount="10000")]})
    write_report(settings, report)
    values = {p.symbol: store.list_price_bars(p.symbol, end_date=DECISION)[-1].close * p.quantity for p in positions}
    nav = sum(values.values()) + Decimal(10000)
    sleeve = current_sota_definition().sleeve_name
    targets = [AllocationTarget(symbol=s, target_weight=values[s]/nav + (Decimal(drift) if s == "SPY" else -Decimal(drift)),
        sleeve=sleeve, rationale="Approved monthly targets") for s in values]
    target = TradeProposal(proposal_id="active-target", created_at=NOW - timedelta(days=18), as_of=date(2026, 7, 31),
        target_as_of=date(2026, 7, 31), intended_trade_date=date(2026, 8, 3), status=ProposalStatus.APPROVED,
        execution_deadline_at=NOW - timedelta(days=15), sleeve=sleeve, targets=targets,
        summary="Monthly strategy targets", reasoning=ProposalReasoning(summary="test"))
    store.save_proposal(target)
    return target


@pytest.mark.parametrize("drift, expected", [("0", "aligned"), ("0.0199", "aligned"), ("0.02", "queued"), ("0.07", "queued")])
def test_drift_threshold_uses_percentage_points_and_active_targets(setup, drift, expected):
    settings, store, _ = setup
    source = invested_setup(setup, drift)
    client = Orders()
    result = stage_portfolio_alignment(settings=settings, store=store, now=NOW, order_client=client)
    assert result.status == expected
    assert result.target_as_of == date(2026, 7, 31)
    assert result.valuation_date == DECISION
    spy = next(row for row in result.holdings if row["symbol"] == "SPY")
    assert abs(Decimal(spy["drift"]) + Decimal(drift)) < Decimal("0.0000000001")
    assert not store.list_broker_order_records()
    if expected == "queued":
        proposal = store.get_proposal(result.proposal_id)
        assert proposal.trigger == "portfolio_drift"
        assert proposal.targets == source.targets
        assert proposal.target_source_proposal_id == source.proposal_id
        assert {order.side.value for order in proposal.orders} == {"buy", "sell"}
        assert all(order.order_type == OrderType.TWAP for order in proposal.orders)
        second = stage_portfolio_alignment(settings=settings, store=store, now=NOW, order_client=client)
        assert second.status == "pending"
        assert second.holdings == result.holdings
        assert client.calls == 1
    else:
        assert client.calls == 0


def test_drift_waits_for_working_broker_order_and_keeps_monitoring(setup):
    settings, store, _ = setup
    invested_setup(setup, "0.07")
    result = stage_portfolio_alignment(settings=settings, store=store, now=NOW, order_client=Orders([dict(status="Submitted")]))
    assert result.status == "blocked"
    assert result.holdings
    assert len(store.list_proposals()) == 1


def test_rejected_drift_is_not_recreated_on_next_session(setup):
    settings, store, report = setup
    invested_setup(setup, "0.07")
    result = stage_portfolio_alignment(settings=settings, store=store, now=NOW, order_client=Orders())
    store.apply_decision(ApprovalDecision(proposal_id=result.proposal_id, status=ProposalStatus.REJECTED))
    next_day = NOW + timedelta(days=1)
    current_report = IBPaperReconciliationReport.model_validate_json(latest_reconciliation_report_path(settings).read_text(encoding="utf-8"))
    write_report(settings, current_report.model_copy(update={"checked_at": next_day}))
    store.upsert_fx_rate(FXRate(rate_date=DECISION + timedelta(days=1), base_currency=Currency.USD, rate=Decimal("7.20")))
    second = stage_portfolio_alignment(settings=settings, store=store, now=next_day, order_client=Orders())
    assert second.status == "review"
    assert len(store.list_proposals()) == 2


def test_monthly_targets_are_not_recalculated_daily(setup):
    settings, store, _ = setup
    invested_setup(setup, "0.07")
    with store._connect() as connection:
        connection.execute("DELETE FROM proposals")
    result = stage_portfolio_alignment(settings=settings, store=store, now=NOW, order_client=Orders())
    assert result.status == "queued"
    assert result.target_as_of == date(2026, 7, 31)
    assert store.get_proposal(result.proposal_id).target_source_proposal_id is None


def test_monthly_target_dates_follow_month_end_calendar():
    assert latest_monthly_target_date(date(2026, 8, 18)) == date(2026, 7, 31)
    assert latest_monthly_target_date(date(2026, 8, 31)) == date(2026, 8, 31)
    assert latest_monthly_target_date(date(2026, 10, 31)) == date(2026, 10, 30)


def test_monthly_workflow_waits_for_existing_alignment_proposal(setup, monkeypatch):
    settings, store, _ = setup
    initial = stage(setup)
    proposal = store.get_proposal(initial.proposal_id).model_copy(update={
        "execution_deadline_at": datetime(2026, 9, 1, 14, tzinfo=UTC)})
    store.save_proposal(proposal)
    service_date = date(2026, 8, 31)
    service = TradingManagementService(settings=settings, store=store, order_management_client=Orders())
    service._status = TradingServiceStatus(pending_eod_date=service_date, last_reconciliation_status="matched", last_eod_pnl_date=service_date)
    monkeypatch.setattr(service, "_sync_executions", lambda now: None)
    monkeypatch.setattr(service, "_refresh_market_data", lambda day: MarketDataRefreshResult(target_date=day, latest_bar_date=day, latest_fx_date=day))
    monkeypatch.setattr("systematic_trading.live.management_service.fetch_and_write_account_snapshot", lambda **kwargs:
        SimpleNamespace(snapshot=LiveAccountSnapshotInput(as_of=service_date), output_path="test.json", warnings=[], managed_accounts=["DU123"]))
    service._run_eod(datetime(2026, 8, 31, 17, tzinfo=NY))
    assert len(store.list_proposals()) == 1
    assert service.status().last_eod_date is None
    assert "Waiting for portfolio-alignment proposal" in service.status().last_error


@pytest.mark.parametrize("condition, expected", [("covered", "queued"), ("missing_attempt", "pending"),
    ("new_attempt", "pending"), ("working_broker", "blocked"), ("uncertain_old", "blocked")])
def test_undated_legacy_approval_only_clears_when_attempts_are_covered_by_baseline(setup, condition, expected):
    _, store, _ = setup
    initial = stage(setup)
    order = store.get_proposal(initial.proposal_id).orders[0]
    with store._connect() as connection:
        connection.execute("DELETE FROM proposals")
    store.save_pnl_baseline(PnLBaseline(cutoff_at=NOW-timedelta(days=1)))
    old = TradeProposal(proposal_id="old-approved", created_at=NOW-timedelta(days=30), as_of=NOW.date()-timedelta(days=31),
        status=ProposalStatus.APPROVED, sleeve="legacy", summary="Historical approval", orders=[order], reasoning=ProposalReasoning(summary="test"))
    store.save_proposal(old)
    if condition != "missing_attempt":
        store.save_broker_order_record(BrokerOrderRecord(proposal_id=old.proposal_id, order_index=0, order=order,
            order_ref="old", status=BrokerOrderStatus.SUBMITTED,
            submitted_at=NOW if condition == "new_attempt" else NOW-timedelta(days=20),
            execution_sync_issue="uncertain" if condition == "uncertain_old" else None))
    client = Orders([dict(status="Submitted")]) if condition == "working_broker" else Orders()
    result = stage(setup, client=client)
    assert result.status == expected
    assert store.get_proposal(old.proposal_id) == old
    assert all(record.status == BrokerOrderStatus.SUBMITTED for record in store.list_broker_order_records())
