from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderEnvironment, OrderSide, OrderType
from systematic_trading.domain.execution import BrokerExecutionFill, BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.live import AccountSummaryRow, TradingManagementService, TradingServiceStatus, trading_service_state_path
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.live.sota import LiveAccountSnapshotInput
from systematic_trading.live.trading_calendar import is_us_trading_day, us_trading_dates_after
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.sqlite import SQLiteStore


def test_trading_management_service_runs_after_close_workflow(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "service.db")
    store.initialize()
    as_of = _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.20")))
    order = OrderRequest(
        symbol="SPY",
        side=OrderSide.BUY,
        order_type=OrderType.TWAP,
        quantity=10,
        reference_price=Decimal("100"),
        currency=Currency.USD,
        environment=OrderEnvironment.PAPER,
        notional_cnh=Decimal("7200"),
        rationale="Open test lot.",
    )
    proposal = TradeProposal(
        proposal_id="service-fill",
        as_of=as_of - timedelta(days=1),
        sleeve="manual-test",
        summary="Manual fill sync seed.",
        orders=[order],
        reasoning=ProposalReasoning(summary="test"),
    )
    store.save_proposal(proposal)
    store.save_broker_order_record(
        BrokerOrderRecord(
            local_order_id="service-fill-record",
            proposal_id=proposal.proposal_id,
            environment=OrderEnvironment.PAPER,
            order_index=0,
            order=order,
            order_ref="st-service-fill-00",
            broker_order_id=1200,
            status=BrokerOrderStatus.SUBMITTED,
            submitted_at=datetime.combine(as_of, time(14, 30), tzinfo=UTC),
            remaining_quantity=10,
        )
    )
    settings = AppSettings(
        database_path=tmp_path / "service.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_after_close_time="16:20",
        automation_market_data_carry_forward=False,
    )
    service = TradingManagementService(
        settings=settings,
        store=store,
        execution_sync_client=_FakeExecutionSyncClient(
            [
                BrokerExecutionFill(
                    broker_order_id=1200,
                    order_ref="st-service-fill-00",
                    symbol="SPY",
                    side=OrderSide.BUY,
                    quantity=10,
                    average_price=Decimal("100"),
                    filled_at=datetime.combine(as_of, time(15), tzinfo=UTC),
                    currency=Currency.USD,
                )
            ]
        ),
        account_snapshot_client=_FakeAccountSnapshotClient(),
        market_data_provider=_FakeMarketDataProvider({}),
        fx_market_data_provider=_FakeMarketDataProvider({}),
    )

    status = service.run_once(now=datetime.combine(as_of, time(16, 30), tzinfo=ZoneInfo("America/New_York")))

    assert status.last_eod_date == as_of
    assert status.last_market_data_date == as_of
    assert status.last_eod_pnl_snapshot_id is not None
    assert status.last_rebalance_proposal_id is not None
    assert status.last_rebalance_artifact_path is not None
    assert (tmp_path / "live" / "trading_management_service_state.json").exists()
    assert (tmp_path / "live" / "account_snapshots").exists()
    assert (tmp_path / "live" / "sota_rebalance").exists()
    assert store.list_pnl_snapshots(limit=10)[0].snapshot_id == status.last_eod_pnl_snapshot_id
    filled = store.list_broker_order_records(proposal.proposal_id)[0]
    assert filled.status == BrokerOrderStatus.FILLED
    assert filled.filled_quantity == 10
    staged = [
        item
        for item in store.list_proposals()
        if item.sleeve == current_sota_definition().sleeve_name and item.as_of == as_of
    ]
    assert len(staged) == 1
    assert staged[0].proposal_id == status.last_rebalance_proposal_id

    second_status = service.run_once(now=datetime.combine(as_of, time(16, 45), tzinfo=ZoneInfo("America/New_York")))
    staged_after_second_run = [
        item
        for item in store.list_proposals()
        if item.sleeve == current_sota_definition().sleeve_name and item.as_of == as_of
    ]
    assert second_status.last_eod_date == as_of
    assert len(staged_after_second_run) == 1


def test_trading_management_service_retries_pending_eod_with_stored_account_snapshot(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "pending.db")
    store.initialize()
    as_of = _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.20")))
    settings = AppSettings(
        database_path=tmp_path / "pending.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_after_close_time="16:20",
    )
    snapshot_dir = tmp_path / "live" / "account_snapshots"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / f"ib_paper_account_snapshot_{as_of:%Y%m%d}_235900.json").write_text(
        LiveAccountSnapshotInput(
            as_of=as_of,
            cash=[CashBalance(currency=Currency.CNH, amount=Decimal("1000000"))],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    state_path = trading_service_state_path(settings)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        TradingServiceStatus(
            enabled=True,
            running=False,
            last_eod_pnl_date=as_of,
            last_eod_pnl_snapshot_id="already-saved",
            last_eod_pnl_total_cnh="0.00",
            next_eod_attempt_at=datetime.combine(as_of + timedelta(days=1), time(0), tzinfo=UTC),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    service = TradingManagementService(
        settings=settings,
        store=store,
        execution_sync_client=_FakeExecutionSyncClient([]),
        account_snapshot_client=_FailingAccountSnapshotClient(),
        market_data_provider=_FakeMarketDataProvider({}),
        fx_market_data_provider=_FakeMarketDataProvider({}),
    )

    status = service.run_once(now=datetime.combine(as_of + timedelta(days=1), time(9), tzinfo=ZoneInfo("America/New_York")))

    assert status.last_eod_date == as_of
    assert status.pending_eod_date is None
    assert status.last_rebalance_proposal_id is not None
    assert status.last_account_snapshot_path is not None
    assert any(event.status == "warning" and "stored same-day account snapshot" in event.message for event in status.events)
    staged = [
        item
        for item in store.list_proposals()
        if item.sleeve == current_sota_definition().sleeve_name and item.as_of == as_of
    ]
    assert len(staged) == 1


def test_trading_management_service_replays_missed_eod_dates_on_restart(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "replay.db")
    store.initialize()
    as_of = _seed_sota_history(store)
    first_missed = _previous_business_day(as_of)
    last_completed = _previous_business_day(first_missed)
    store.upsert_fx_rate(FXRate(rate_date=last_completed, base_currency=Currency.USD, rate=Decimal("7.20")))
    store.upsert_fx_rate(FXRate(rate_date=first_missed, base_currency=Currency.USD, rate=Decimal("7.21")))
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.22")))
    settings = AppSettings(
        database_path=tmp_path / "replay.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_after_close_time="16:20",
    )
    state_path = trading_service_state_path(settings)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        TradingServiceStatus(
            enabled=True,
            running=False,
            last_eod_date=last_completed,
            last_eod_pnl_date=last_completed,
            last_eod_pnl_snapshot_id="already-saved",
            last_eod_pnl_total_cnh="0.00",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    service = TradingManagementService(
        settings=settings,
        store=store,
        execution_sync_client=_FakeExecutionSyncClient([]),
        account_snapshot_client=_FakeAccountSnapshotClient(),
        market_data_provider=_FakeMarketDataProvider({}),
        fx_market_data_provider=_FakeMarketDataProvider({}),
    )

    status = service.run_once(now=datetime.combine(as_of, time(16, 45), tzinfo=ZoneInfo("America/New_York")))

    assert status.last_eod_date == as_of
    assert status.last_eod_pnl_date == as_of
    assert status.pending_eod_date is None
    assert status.pending_eod_dates == []
    snapshot_dates = {snapshot.as_of.date() for snapshot in store.list_pnl_snapshots(limit=10)}
    assert {first_missed, as_of}.issubset(snapshot_dates)
    staged_dates = {
        item.as_of
        for item in store.list_proposals()
        if item.sleeve == current_sota_definition().sleeve_name
    }
    assert {first_missed, as_of}.issubset(staged_dates)
    completed_messages = [event.message for event in status.events if event.event_type == "eod" and event.status == "ok"]
    assert any(str(first_missed) in message for message in completed_messages)
    assert any(str(as_of) in message for message in completed_messages)


def test_trading_management_service_start_retries_pending_eod_immediately_after_restart(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "restart_retry.db")
    store.initialize()
    service_date = date(2026, 5, 20)
    settings = AppSettings(
        database_path=tmp_path / "restart_retry.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_loop_interval_seconds=3600,
    )
    state_path = trading_service_state_path(settings)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        TradingServiceStatus(
            enabled=True,
            running=False,
            pending_eod_date=service_date,
            pending_eod_dates=[service_date],
            next_eod_attempt_at=datetime(2026, 5, 21, 12, tzinfo=UTC),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    service = TradingManagementService(settings=settings, store=store)

    try:
        service.start()
        status = service.status()
    finally:
        service.stop()

    assert status.pending_eod_date == service_date
    assert status.next_eod_attempt_at is None


def test_trading_management_service_notifies_on_eod_warning(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "alert.db")
    store.initialize()
    service_date = date(2026, 5, 19)
    store.upsert_price_bar("HYXU", PriceBar(trade_date=service_date - timedelta(days=1), open=Decimal("53"), high=Decimal("53"), low=Decimal("53"), close=Decimal("53"), volume=1000))
    settings = AppSettings(
        database_path=tmp_path / "alert.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_after_close_time="16:20",
        automation_market_data_carry_forward=False,
    )
    notifier = _FakeAlertNotifier()
    service = TradingManagementService(
        settings=settings,
        store=store,
        execution_sync_client=_FakeExecutionSyncClient([]),
        account_snapshot_client=_FakeAccountSnapshotClient(),
        market_data_provider=_FakeMarketDataProvider({}),
        fx_market_data_provider=_FakeMarketDataProvider({}),
        alert_notifier=notifier,
    )

    service.run_once(now=datetime.combine(service_date, time(16, 30), tzinfo=ZoneInfo("America/New_York")))

    assert any(event.event_type == "market_data" and event.status == "warning" for event in notifier.events)
    assert any(event.event_type == "rebalance_stage" and event.status == "warning" for event in notifier.events)


def test_trading_management_service_skips_market_closed_holiday_without_alerts(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "holiday.db")
    store.initialize()
    settings = AppSettings(
        database_path=tmp_path / "holiday.db",
        data_dir=tmp_path,
        automation_enabled=True,
        automation_after_close_time="16:20",
    )
    trading_service_state_path(settings).parent.mkdir(parents=True, exist_ok=True)
    trading_service_state_path(settings).write_text(
        TradingServiceStatus(
            enabled=True,
            running=False,
            last_eod_date=date(2026, 5, 22),
            last_eod_pnl_date=date(2026, 5, 22),
            last_eod_pnl_snapshot_id="already-saved",
            last_eod_pnl_total_cnh="0.00",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    notifier = _FakeAlertNotifier()
    market_provider = _FakeMarketDataProvider({})
    service = TradingManagementService(
        settings=settings,
        store=store,
        execution_sync_client=_FailingExecutionSyncClient(),
        account_snapshot_client=_FailingAccountSnapshotClient(),
        market_data_provider=market_provider,
        fx_market_data_provider=_FakeMarketDataProvider({}),
        alert_notifier=notifier,
    )

    status = service.run_once(now=datetime(2026, 5, 25, 16, 30, tzinfo=ZoneInfo("America/New_York")))

    assert not is_us_trading_day(date(2026, 5, 25))
    assert status.last_eod_date == date(2026, 5, 22)
    assert status.pending_eod_date is None
    assert market_provider.requests == []
    assert notifier.events == []
    assert status.next_execution_sync_at == datetime(2026, 5, 26, 13, 30, tzinfo=UTC)


def test_us_trading_calendar_excludes_market_holidays() -> None:
    assert not is_us_trading_day(date(2026, 5, 25))
    assert is_us_trading_day(date(2026, 5, 26))
    assert us_trading_dates_after(date(2026, 5, 22), date(2026, 5, 26)) == [date(2026, 5, 26)]


class _FakeExecutionSyncClient:
    def __init__(self, fills: list[BrokerExecutionFill]) -> None:
        self.fills = fills

    def fetch_fills(self, profile):
        return self.fills


class _FakeAccountSnapshotClient:
    def fetch(self, profile):
        return (
            [AccountSummaryRow(account="DU123", tag="TotalCashValue", value="1000000", currency="CNH")],
            [],
            ["DU123"],
        )


class _FailingAccountSnapshotClient:
    def fetch(self, profile):
        raise TimeoutError("IB account snapshot unavailable")


class _FailingExecutionSyncClient:
    def fetch_fills(self, profile):
        raise TimeoutError("IB execution sync unavailable")


class _FakeMarketDataProvider:
    def __init__(self, bars_by_symbol: dict[str, list[PriceBar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.requests = []

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        self.requests.append((symbol, start_date, end_date))
        return [
            bar
            for bar in self.bars_by_symbol.get(symbol, [])
            if start_date <= bar.trade_date <= end_date
        ]


class _FakeAlertNotifier:
    def __init__(self) -> None:
        self.events = []

    def notify(self, event) -> None:
        self.events.append(event)


def _seed_sota_history(store: SQLiteStore) -> date:
    start = date(2025, 1, 2)
    trade_dates: list[date] = []
    cursor = start
    while len(trade_dates) < 420:
        if cursor.weekday() < 5:
            trade_dates.append(cursor)
        cursor += timedelta(days=1)
    sota_symbols = sorted(instruments_for_definition(current_sota_definition()))
    for symbol_index, symbol in enumerate(sota_symbols):
        daily_step = Decimal("0.03") + Decimal(symbol_index + 1) * Decimal("0.01")
        base_close = Decimal("80") + Decimal(symbol_index * 3)
        for index, trade_date in enumerate(trade_dates):
            close = base_close + daily_step * Decimal(index) + Decimal(index % 3) * Decimal("0.35")
            store.upsert_price_bar(
                symbol,
                PriceBar(
                    trade_date=trade_date,
                    open=close,
                    high=close + Decimal("0.5"),
                    low=close - Decimal("0.5"),
                    close=close,
                    volume=1_000_000 + index * 100,
                ),
            )
    return trade_dates[-1]


def _previous_business_day(value: date) -> date:
    cursor = value - timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor
