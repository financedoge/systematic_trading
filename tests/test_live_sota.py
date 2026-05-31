from datetime import date, timedelta
from decimal import Decimal

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency, OrderEnvironment, OrderType
from systematic_trading.domain.market import FXRate, PriceBar
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.live import LiveAccountSnapshotInput, build_sota_live_rebalance_plan
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.sqlite import SQLiteStore


def test_sota_live_rebalance_plan_generates_and_queues_paper_orders(tmp_path) -> None:
    database_path = tmp_path / "live.db"
    store = SQLiteStore(database_path)
    store.initialize()
    as_of = _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.20")))
    settings = AppSettings(database_path=database_path, data_dir=tmp_path)
    snapshot = LiveAccountSnapshotInput(cash=[CashBalance(currency=Currency.CNH, amount=Decimal("1000000"))])

    plan = build_sota_live_rebalance_plan(
        store=store,
        broker=InteractiveBrokersAdapter(settings),
        account_snapshot=snapshot,
        decision_date=as_of,
        environment=OrderEnvironment.PAPER,
        queue=True,
    )

    assert plan.queued is True
    assert plan.strategy_key == "sota_price_volume_technical_tree_relative_adaptive_top6"
    assert plan.validation_issues == []
    assert plan.proposal.orders
    assert {order.environment for order in plan.proposal.orders} == {OrderEnvironment.PAPER}
    assert {order.order_type for order in plan.proposal.orders} == {OrderType.TWAP}
    assert plan.proposal.as_of == as_of
    assert plan.proposal.intended_trade_date == plan.intended_trade_date
    assert plan.proposal.intended_trade_date > as_of
    assert {order.intended_trade_date for order in plan.proposal.orders} == {plan.proposal.intended_trade_date}
    assert {order.execution_start_time for order in plan.proposal.orders} == {"09:30"}
    assert {order.execution_end_time for order in plan.proposal.orders} == {"10:00"}
    assert store.list_proposals()[0].proposal_id == plan.proposal.proposal_id


def test_sota_live_rebalance_plan_rejects_live_queue_in_v1(tmp_path) -> None:
    database_path = tmp_path / "live_guard.db"
    store = SQLiteStore(database_path)
    store.initialize()
    as_of = _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.20")))
    settings = AppSettings(database_path=database_path, data_dir=tmp_path)
    snapshot = LiveAccountSnapshotInput(cash=[CashBalance(currency=Currency.CNH, amount=Decimal("1000000"))])

    plan = build_sota_live_rebalance_plan(
        store=store,
        broker=InteractiveBrokersAdapter(settings),
        account_snapshot=snapshot,
        decision_date=as_of,
        environment=OrderEnvironment.LIVE,
        queue=False,
    )

    assert plan.validation_issues
    assert "live routing is disabled" in plan.validation_issues[0]


def test_sota_live_rebalance_plan_rejects_stale_market_data(tmp_path) -> None:
    database_path = tmp_path / "live_stale.db"
    store = SQLiteStore(database_path)
    store.initialize()
    as_of = _seed_sota_history(store)
    store.upsert_fx_rate(FXRate(rate_date=as_of, base_currency=Currency.USD, rate=Decimal("7.20")))
    settings = AppSettings(database_path=database_path, data_dir=tmp_path)
    snapshot = LiveAccountSnapshotInput(cash=[CashBalance(currency=Currency.CNH, amount=Decimal("1000000"))])

    with pytest.raises(ValueError, match="Latest SOTA market data"):
        build_sota_live_rebalance_plan(
            store=store,
            broker=InteractiveBrokersAdapter(settings),
            account_snapshot=snapshot,
            decision_date=as_of + timedelta(days=1),
            environment=OrderEnvironment.PAPER,
            queue=False,
        )


def _seed_sota_history(store: SQLiteStore) -> date:
    start = date(2025, 1, 2)
    trade_dates = []
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
