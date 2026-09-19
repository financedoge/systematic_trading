from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
import runpy
import sys

import pytest

from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.config import AppSettings
from systematic_trading.domain import (
    BrokerOrderRecord, Currency, FXRate, OrderRequest, PnLBaseline, PnLOpenLot,
    PriceBar, ProposalReasoning, TradeProposal,
)
from systematic_trading.domain.enums import AssetClass, BrokerOrderStatus, Exchange, OrderSide, OrderType, ProposalStatus
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
from systematic_trading.execution.broker import BrokerOrderRejectedError, InteractiveBrokersAdapter, InteractiveBrokersOrderRouter
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, PositionDifference
from systematic_trading.execution.window import expire_due_proposals
from systematic_trading.live.market_data import refresh_sota_market_data
from systematic_trading.live.pnl import build_pnl_baseline
from systematic_trading.live import sota
from systematic_trading.storage import create_trading_store
from systematic_trading.storage.sqlite import SQLiteStore


D = Decimal


def instrument():
    return Instrument(symbol="SPY", name="SPY", asset_class=AssetClass.ETF,
                      exchange=Exchange.NYSE, quote_currency=Currency.USD, country="US")


def proposal():
    return TradeProposal(
        as_of=date.today(), status=ProposalStatus.APPROVED, sleeve="test", summary="test",
        orders=[OrderRequest(symbol="SPY", side=OrderSide.BUY, order_type=OrderType.MARKET,
                             quantity=10, reference_price=D(100), currency=Currency.USD,
                             notional_cnh=D(1000), rationale="test")],
        reasoning=ProposalReasoning(summary="test"),
    )


def storage(tmp_path):
    store = SQLiteStore(tmp_path / "regression.db")
    store.initialize()
    return store


def reconciliation(settings, **changes):
    report = IBPaperReconciliationReport(
        checked_at=datetime.now(UTC), local_order_history_count=0, local_order_count=0,
        local_filled_order_count=0, ib_fill_count=0, ib_position_count=0,
    ).model_copy(update=changes)
    path = settings.data_dir / "reconciliation" / "ib_paper_reconciliation_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(), encoding="utf-8")
    return path


class Client:
    def __init__(self, *, error=None, barrier=None, first_id=100):
        self.error, self.barrier, self.first_id = error, barrier, first_id
        self.connected = False
        self.sent = []

    def connect(self, profile):
        self.connected = True
        if self.barrier:
            self.barrier.wait(timeout=5)
        return self.first_id

    def place_order(self, order_id, contract, order):
        self.sent.append(order_id)
        if self.error:
            raise self.error

    def disconnect(self):
        pass


def test_opening_intents_are_invariant_to_execution_day_close_and_fx():
    first, second = date(2026, 1, 5), date(2026, 1, 6)
    target = AllocationTarget(symbol="SPY", target_weight=D('.5'), sleeve="test", rationale="test")
    intents = []
    for close, fx in [(100, 1), (200, 1), (100, 2)]:
        result = DailyBacktestEngine().run(
            trade_dates=[first, second], instruments={"SPY": instrument()},
            initial_cash=[CashBalance(currency=Currency.CNH, amount=D(10000))],
            daily_prices={first: {"SPY": D(100)}, second: {"SPY": D(close)}},
            daily_fx_to_cnh={first: {Currency.USD: D(1)}, second: {Currency.USD: D(fx)}},
            daily_rebalance_prices={first: {"SPY": D(100)}, second: {"SPY": D(100)}},
            daily_execution_prices={first: {"SPY": D(100)}, second: {"SPY": D(100)}},
            decision_dates_by_trade_date={second: first},
            target_schedule={first: [target], second: [target]},
        )
        intents.append(result.proposals[1].orders)
    assert intents == [[], [], []]


def test_gap_purchase_uses_existing_usd_cash():
    day = date(2026, 1, 5)
    result = DailyBacktestEngine().run(
        trade_dates=[day], instruments={"SPY": instrument()},
        initial_cash=[CashBalance(currency=Currency.USD, amount=D(900))],
        daily_prices={day: {"SPY": D(90)}}, daily_execution_prices={day: {"SPY": D(100)}},
        daily_fx_to_cnh={day: {Currency.USD: D(1)}},
        target_schedule={day: [AllocationTarget(symbol="SPY", target_weight=D(1), sleeve="test", rationale="test")]},
    )
    assert result.proposals[0].orders[0].quantity == 10
    assert result.final_snapshot.positions[0].quantity == 9
    assert result.final_snapshot.cash == []


@pytest.mark.parametrize("failure", ["missing", "stale", "future", "break", "malformed"])
def test_shared_router_blocks_bad_reconciliation_before_connect(tmp_path, failure):
    settings, store, client = AppSettings(data_dir=tmp_path), storage(tmp_path), Client()
    if failure != "missing":
        changes = {}
        if failure == "stale":
            changes["checked_at"] = datetime.now(UTC) - timedelta(seconds=181)
        if failure == "future":
            changes["checked_at"] = datetime.now(UTC) + timedelta(minutes=1)
        if failure == "break":
            changes["position_differences"] = [PositionDifference(symbol="SPY", local_quantity=0, ib_quantity=1, difference=1)]
        path = reconciliation(settings, **changes)
        if failure == "malformed":
            path.write_text("{", encoding="utf-8")
    result = InteractiveBrokersOrderRouter(settings, client=client).submit_approved_proposal(proposal=proposal(), store=store)
    assert any("reconciliation" in issue for issue in result.validation_issues)
    assert not client.connected
    assert store.list_broker_order_records() == []


@pytest.mark.parametrize("error", [TimeoutError("lost acknowledgment"), ConnectionError("lost connection"), RuntimeError("unknown broker response")])
def test_uncertain_submission_survives_expiry_and_cannot_be_retried(tmp_path, error):
    settings, store, p = AppSettings(data_dir=tmp_path), storage(tmp_path), proposal()
    reconciliation(settings)
    p.execution_deadline_at = datetime.now(UTC) + timedelta(minutes=1)
    store.save_proposal(p)
    first = Client(error=error)
    result = InteractiveBrokersOrderRouter(settings, client=first).submit_approved_proposal(proposal=p, store=store)
    assert result.records[0].status == BrokerOrderStatus.PENDING_SUBMIT
    assert expire_due_proposals(store, settings, now=datetime.now(UTC) + timedelta(minutes=2)) == []
    second = Client(first_id=200)
    retry = InteractiveBrokersOrderRouter(settings, client=second).submit_approved_proposal(proposal=p, store=store, allow_resubmit=True)
    assert any("uncertain" in issue for issue in retry.validation_issues)
    assert first.sent == [100] and second.sent == []
    assert store.list_broker_order_records()[0].broker_order_id == 100


def test_only_confirmed_unfilled_rejection_can_retry(tmp_path):
    settings, store, p = AppSettings(data_dir=tmp_path), storage(tmp_path), proposal()
    reconciliation(settings)
    first = Client(error=BrokerOrderRejectedError("explicit rejection"))
    router = InteractiveBrokersOrderRouter(settings, client=first)
    assert router.submit_approved_proposal(proposal=p, store=store).records[0].status == BrokerOrderStatus.REJECTED
    second = Client(first_id=200)
    result = InteractiveBrokersOrderRouter(settings, client=second).submit_approved_proposal(proposal=p, store=store, allow_resubmit=True)
    assert not result.validation_issues
    assert second.sent == [200]


def test_uncertain_order_blocks_a_different_proposal(tmp_path):
    settings, store = AppSettings(data_dir=tmp_path), storage(tmp_path)
    reconciliation(settings)
    first = InteractiveBrokersOrderRouter(settings, client=Client(error=TimeoutError("lost ack")))
    first.submit_approved_proposal(proposal=proposal(), store=store)
    client = Client()
    result = InteractiveBrokersOrderRouter(settings, client=client).submit_approved_proposal(proposal=proposal(), store=store)
    assert any("unresolved submission" in issue for issue in result.validation_issues)
    assert not client.connected


def test_cancelled_partial_fill_cannot_retry_full_quantity(tmp_path):
    settings, store, p = AppSettings(data_dir=tmp_path), storage(tmp_path), proposal()
    reconciliation(settings)
    store.save_broker_order_record(BrokerOrderRecord(
        proposal_id=p.proposal_id, order_index=0, order=p.orders[0], order_ref="partial",
        status=BrokerOrderStatus.CANCELLED, filled_quantity=3, average_fill_price=D(100),
    ))
    client = Client()
    result = InteractiveBrokersOrderRouter(settings, client=client).submit_approved_proposal(
        proposal=p, store=store, allow_resubmit=True,
    )
    assert result.validation_issues and not client.connected


def test_concurrent_routers_only_send_one_order(tmp_path):
    settings, store, p = AppSettings(data_dir=tmp_path), storage(tmp_path), proposal()
    reconciliation(settings)
    barrier = Barrier(2)
    clients = [Client(barrier=barrier, first_id=n) for n in (100, 200)]
    routers = [InteractiveBrokersOrderRouter(settings, client=c) for c in clients]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda r: r.submit_approved_proposal(proposal=p, store=store), routers))
    assert sum(len(c.sent) for c in clients) == 1
    assert sum(bool(r.validation_issues) for r in results) == 1
    assert len(store.list_broker_order_records()) == 1


def test_baseline_collapse_preserves_reset_lots_and_excludes_pre_reset_trades(tmp_path):
    store, p = storage(tmp_path), proposal()
    reset_at = datetime(2026, 7, 1, tzinfo=UTC)
    lot = PnLOpenLot(symbol="SPY", quantity=10, cost_price=D(100), cost_fx_to_cnh=D(7),
                    currency=Currency.USD, opened_at=reset_at, source_order_id="reset")
    previous = PnLBaseline(cutoff_at=reset_at, source="ib_broker_authoritative_reset",
                           open_lots=[lot], filled_trade_count=1,
                           realized_pnl_cnh=D(50), realized_pnl_by_symbol_cnh={"SPY": D(50)})
    store.save_pnl_baseline(previous)
    store.save_broker_order_record(BrokerOrderRecord(
        proposal_id=p.proposal_id, order_index=0, order=p.orders[0], order_ref="old",
        status=BrokerOrderStatus.FILLED, filled_quantity=100, average_fill_price=D(10),
        submitted_at=reset_at - timedelta(days=2), updated_at=reset_at - timedelta(days=1),
    ))
    result = build_pnl_baseline(store, cutoff_date=date(2026, 7, 2))
    assert result.open_lots == [lot]
    assert result.realized_pnl_cnh == 50 and result.filled_trade_count == 1
    store.save_pnl_baseline(result)
    assert build_pnl_baseline(store, cutoff_date=date(2026, 7, 3)).open_lots == [lot]
    with pytest.raises(ValueError, match="before the current baseline"):
        build_pnl_baseline(store, cutoff_date=date(2026, 6, 30))


class EmptyProvider:
    def __init__(self):
        self.requests = []

    def fetch_daily_bars(self, symbol, start_date, end_date):
        self.requests.append((symbol, start_date, end_date))
        return []


def test_repeated_outages_cannot_renew_stale_data(tmp_path):
    store, provider = storage(tmp_path), EmptyProvider()
    start = date(2026, 1, 5)
    store.upsert_price_bar("SPY", PriceBar(trade_date=start, open=100, high=100, low=100, close=100, volume=100))
    store.upsert_fx_rate(FXRate(rate_date=start, base_currency=Currency.USD, rate=D(7)))
    for days in (1, 2, 3, 4, 7, 14):
        result = refresh_sota_market_data(store=store, symbols=["SPY"], target_date=start + timedelta(days=days),
                                         provider=provider, fx_provider=provider, allow_stale_carry_forward=True)
        assert result.latest_bar_date == result.latest_fx_date == start
        assert result.carried_forward_price_bars == result.carried_forward_fx_rates == 0
    assert len(store.list_price_bars("SPY")) == len(store.list_fx_rates(Currency.USD)) == 1


def test_missing_symbol_or_legacy_synthetic_bar_cannot_report_complete_data(tmp_path):
    store, provider = storage(tmp_path), EmptyProvider()
    day = date(2026, 1, 5)
    store.upsert_price_bar("SPY", PriceBar(trade_date=day, open=100, high=100, low=100, close=100, volume=0))
    result = refresh_sota_market_data(store=store, symbols=["SPY", "TLT"], target_date=day,
                                     provider=provider, fx_provider=provider)
    assert result.latest_bar_date is None
    assert ("SPY", day, day) in provider.requests


def test_invalid_postgres_sqlite_combination_fails_before_database_access():
    with pytest.raises(ValueError, match="requires market_data_store_backend"):
        create_trading_store(AppSettings(transactional_store_backend="postgres", market_data_store_backend="sqlite"))


@pytest.mark.parametrize("problem", ["stale_fx", "stale_position", "synthetic_position", "stale_snapshot_date"])
def test_live_plan_rejects_stale_inputs_even_when_another_symbol_is_current(tmp_path, monkeypatch, problem):
    store = storage(tmp_path)
    start, day = date(2026, 1, 5), date(2026, 1, 8)
    instruments = {symbol: instrument().model_copy(update={"symbol": symbol}) for symbol in ("SPY", "TLT", "QQQ")}
    for symbol in instruments:
        for offset, close in enumerate((100, 102, 101, 104)):
            if symbol == "SPY" and problem == "stale_position" and offset == 3:
                continue
            store.upsert_price_bar(symbol, PriceBar(
                trade_date=start + timedelta(days=offset), open=close, high=close, low=close, close=close,
                volume=0 if symbol == "SPY" and problem == "synthetic_position" and offset == 3 else 100,
            ))
    store.upsert_fx_rate(FXRate(rate_date=day - timedelta(days=1) if problem == "stale_fx" else day,
                               base_currency=Currency.USD, rate=D(7)))
    monkeypatch.setattr(sota, "current_sota_definition", lambda: SimpleNamespace(key="test", name="test", sleeve_name="test"))
    monkeypatch.setattr(sota, "instruments_for_definition", lambda definition: instruments)
    monkeypatch.setattr(sota, "instantiate_overlays", lambda definition: [])
    snapshot = sota.LiveAccountSnapshotInput(
        as_of=day + timedelta(days=1) if problem == "stale_snapshot_date" else day,
        cash=[CashBalance(currency=Currency.CNH, amount=D(10000))],
        positions=[sota.AccountPositionInput(symbol="SPY", quantity=1, average_cost=D(100))],
    )
    with pytest.raises(ValueError, match="Stale|Missing latest price|Latest SOTA market data"):
        sota.build_sota_live_rebalance_plan(
            store=store, broker=InteractiveBrokersAdapter(AppSettings(data_dir=tmp_path)),
            account_snapshot=snapshot, lookback_bars=2, max_weight=D('.6'), queue=True,
        )
    assert store.list_proposals() == []


def test_submission_cli_uses_configured_store_factory(tmp_path, monkeypatch, capsys):
    store, p = storage(tmp_path), proposal()
    store.save_proposal(p)
    reconciliation(AppSettings(data_dir=tmp_path))
    monkeypatch.setenv("ST_TRANSACTIONAL_STORE_BACKEND", "postgres")
    monkeypatch.setenv("ST_MARKET_DATA_STORE_BACKEND", "clickhouse")
    namespace = runpy.run_path(str(Path("scripts/submit_ib_paper_orders.py")))
    seen = []

    def factory(settings, **kwargs):
        seen.append(settings.transactional_store_backend)
        return store

    monkeypatch.setitem(namespace["main"].__globals__, "create_trading_store", factory)
    monkeypatch.setattr(sys, "argv", ["submit_ib_paper_orders.py", "--proposal-id", p.proposal_id])
    namespace["main"]()
    assert seen == ["postgres"]
    assert "Validation passed" in capsys.readouterr().out
