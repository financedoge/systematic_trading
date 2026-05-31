from datetime import date
from decimal import Decimal

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import (
    BrokerOrderStatus,
    Currency,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.domain.execution import OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.execution.broker import IBOrderSpec, _to_ib_order
from systematic_trading.execution import InteractiveBrokersOrderRouter, order_spec_for
from systematic_trading.execution.broker import InteractiveBrokersExecutionSynchronizer
from systematic_trading.research import current_sota_definition
from systematic_trading.storage.sqlite import SQLiteStore


class FakeIBClient:
    def __init__(self, *, first_order_id: int = 1000, fail_on_order_id: int | None = None) -> None:
        self.first_order_id = first_order_id
        self.fail_on_order_id = fail_on_order_id
        self.connected = False
        self.disconnected = False
        self.placed_orders = []

    def connect(self, profile):
        self.connected = True
        self.profile = profile
        return self.first_order_id

    def place_order(self, order_id, contract, order) -> None:
        if order_id == self.fail_on_order_id:
            raise RuntimeError(f"IB rejected order {order_id}")
        self.placed_orders.append((order_id, contract, order))

    def disconnect(self) -> None:
        self.disconnected = True


class FakeExecutionSyncClient:
    def __init__(self) -> None:
        self.profile = None

    def fetch_fills(self, profile):
        self.profile = profile
        return []


def test_ib_router_submits_approved_paper_proposal_and_persists_records(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal(status=ProposalStatus.APPROVED)
    store.save_proposal(proposal)
    fake_client = FakeIBClient(first_order_id=200)
    router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=fake_client)

    result = router.submit_approved_proposal(
        proposal=proposal,
        store=store,
        environment=OrderEnvironment.PAPER,
    )

    assert result.validation_issues == []
    assert [record.status for record in result.records] == [BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.SUBMITTED]
    assert [item[0] for item in fake_client.placed_orders] == [200, 201]
    assert fake_client.connected is True
    assert fake_client.disconnected is True
    first_contract = fake_client.placed_orders[0][1]
    first_order = fake_client.placed_orders[0][2]
    second_order = fake_client.placed_orders[1][2]
    assert first_contract.symbol == "SPY"
    assert first_contract.exchange == "SMART"
    assert first_contract.currency == Currency.USD
    assert first_contract.primary_exchange is None
    assert first_order.action == "BUY"
    assert first_order.order_type == "LMT"
    assert first_order.limit_price == Decimal("500")
    assert first_order.algo_strategy is None
    assert first_order.order_ref.startswith(f"st-{proposal.proposal_id}-")
    assert second_order.action == "SELL"
    assert second_order.order_type == "MKT"
    assert second_order.time_in_force == "OPG"
    stored = store.list_broker_order_records(proposal.proposal_id)
    assert [record.broker_order_id for record in stored] == [200, 201]
    assert [record.status for record in stored] == [BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.SUBMITTED]


def test_ib_router_requires_approved_proposal_before_any_connection(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal(status=ProposalStatus.PENDING)
    store.save_proposal(proposal)
    fake_client = FakeIBClient()
    router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=fake_client)

    result = router.submit_approved_proposal(
        proposal=proposal,
        store=store,
        environment=OrderEnvironment.PAPER,
    )

    assert "proposal status must be approved" in result.validation_issues[0]
    assert result.records == []
    assert fake_client.connected is False
    assert store.list_broker_order_records(proposal.proposal_id) == []


def test_ib_router_blocks_live_submission_even_for_approved_proposal(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal(status=ProposalStatus.APPROVED, environment=OrderEnvironment.LIVE)
    store.save_proposal(proposal)
    fake_client = FakeIBClient()
    router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=fake_client)

    result = router.submit_approved_proposal(
        proposal=proposal,
        store=store,
        environment=OrderEnvironment.LIVE,
    )

    assert any("live routing is disabled" in issue for issue in result.validation_issues)
    assert any("profile is disabled" in issue for issue in result.validation_issues)
    assert fake_client.connected is False


def test_ib_router_rejects_duplicate_submission_without_override(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal(status=ProposalStatus.APPROVED)
    store.save_proposal(proposal)
    router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=FakeIBClient())
    first = router.submit_approved_proposal(proposal=proposal, store=store)
    assert first.validation_issues == []
    second_client = FakeIBClient()
    second_router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=second_client)

    second = second_router.submit_approved_proposal(proposal=proposal, store=store)

    assert any("broker order records already exist" in issue for issue in second.validation_issues)
    assert second.records == []
    assert second_client.connected is False


def test_ib_router_persists_rejected_record_when_ib_client_fails(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal(status=ProposalStatus.APPROVED)
    store.save_proposal(proposal)
    fake_client = FakeIBClient(first_order_id=300, fail_on_order_id=301)
    router = InteractiveBrokersOrderRouter(AppSettings(database_path=tmp_path / "ib.db"), client=fake_client)

    result = router.submit_approved_proposal(proposal=proposal, store=store)

    assert result.validation_issues == []
    assert [record.status for record in result.records] == [BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.REJECTED]
    assert result.records[1].message == "IB rejected order 301"
    stored = store.list_broker_order_records(proposal.proposal_id)
    assert [record.status for record in stored] == [BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.REJECTED]
    assert stored[1].message == "IB rejected order 301"
    assert fake_client.disconnected is True


def test_ib_execution_sync_uses_dedicated_client_id(tmp_path) -> None:
    store = _store(tmp_path)
    fake_client = FakeExecutionSyncClient()
    synchronizer = InteractiveBrokersExecutionSynchronizer(
        AppSettings(
            database_path=tmp_path / "ib.db",
            ib_client_id=101,
            ib_execution_sync_client_id=333,
        ),
        client=fake_client,
    )

    result = synchronizer.sync_order_fills(store=store)

    assert result.fills_seen == 0
    assert fake_client.profile.client_id == 333


@pytest.mark.parametrize(
    ("order_type", "expected_type", "expected_tif", "has_limit"),
    [
        (OrderType.MARKET, "MKT", "DAY", False),
        (OrderType.LIMIT, "LMT", "DAY", True),
        (OrderType.TWAP, "LMT", "DAY", True),
        (OrderType.VWAP, "LMT", "DAY", True),
        (OrderType.MARKET_ON_OPEN, "MKT", "OPG", False),
        (OrderType.LIMIT_ON_OPEN, "LMT", "OPG", True),
    ],
)
def test_order_spec_mapping(order_type: OrderType, expected_type: str, expected_tif: str, has_limit: bool) -> None:
    request = _order("SPY", OrderSide.BUY, order_type=order_type)

    spec = order_spec_for(request, order_ref="st-test-00")

    assert spec.action == "BUY"
    assert spec.order_type == expected_type
    assert spec.time_in_force == expected_tif
    expected_limit = Decimal("515.00") if order_type in {OrderType.TWAP, OrderType.VWAP} else Decimal("500")
    assert spec.limit_price == (expected_limit if has_limit else None)
    assert spec.order_ref == "st-test-00"
    if order_type == OrderType.TWAP:
        assert spec.algo_strategy == "Twap"
        assert "strategyType" not in spec.algo_params
        assert spec.algo_params["startTime"] == "09:30:00 US/Eastern"
        assert spec.algo_params["endTime"] == "10:00:00 US/Eastern"
        assert spec.algo_params["allowPastEndTime"] == "0"
    if order_type == OrderType.VWAP:
        assert spec.algo_strategy == "Vwap"
        assert spec.algo_params["maxPctVol"] == "0.2"
        assert spec.algo_params["speedUp"] == "1"


def test_order_spec_mapping_uses_marketable_sell_limit_for_twap() -> None:
    request = _order("SPY", OrderSide.SELL, order_type=OrderType.TWAP)

    spec = order_spec_for(request, order_ref="st-test-00")

    assert spec.order_type == "LMT"
    assert spec.limit_price == Decimal("485.00")
    assert spec.algo_strategy == "Twap"


def test_order_spec_mapping_dates_open_window_twap_for_intended_trade_date() -> None:
    request = _order(
        "SPY",
        OrderSide.BUY,
        order_type=OrderType.TWAP,
        intended_trade_date=date(2026, 5, 21),
        execution_start_time="09:30",
        execution_end_time="10:00",
    )

    spec = order_spec_for(request, order_ref="st-test-00")

    assert spec.algo_params["startTime"] == "20260521 09:30:00 US/Eastern"
    assert spec.algo_params["endTime"] == "20260521 10:00:00 US/Eastern"
    assert spec.algo_params["allowPastEndTime"] == "0"


def test_ib_order_translation_disables_unsupported_legacy_attributes() -> None:
    pytest.importorskip("ibapi.order")

    order = _to_ib_order(
        IBOrderSpec(
            action="BUY",
            order_type="LMT",
            quantity=1,
            limit_price=Decimal("100.126"),
            order_ref="st-test-00",
        )
    )

    assert order.eTradeOnly is False
    assert order.firmQuoteOnly is False
    assert order.lmtPrice == 100.13


def test_ib_order_translation_sets_algo_strategy_and_params() -> None:
    pytest.importorskip("ibapi.order")

    order = _to_ib_order(
        IBOrderSpec(
            action="BUY",
            order_type="LMT",
            quantity=10,
            limit_price=Decimal("103.00"),
            order_ref="st-test-00",
            algo_strategy="Twap",
            algo_params={"startTime": "09:30:00 US/Eastern", "allowPastEndTime": "0"},
        )
    )

    assert order.algoStrategy == "Twap"
    assert {item.tag: item.value for item in order.algoParams} == {
        "startTime": "09:30:00 US/Eastern",
        "allowPastEndTime": "0",
    }


def _store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "ib.db")
    store.initialize()
    return store


def _proposal(
    *,
    status: ProposalStatus,
    environment: OrderEnvironment = OrderEnvironment.PAPER,
) -> TradeProposal:
    return TradeProposal(
        proposal_id="proposalabc1",
        as_of="2026-04-29",
        status=status,
        sleeve=current_sota_definition().sleeve_name,
        summary="test proposal",
        orders=[
            _order("SPY", OrderSide.BUY, environment=environment, order_type=OrderType.LIMIT),
            _order("TLT", OrderSide.SELL, environment=environment, order_type=OrderType.MARKET_ON_OPEN),
        ],
        reasoning=ProposalReasoning(summary="test"),
    )


def _order(
    symbol: str,
    side: OrderSide,
    *,
    environment: OrderEnvironment = OrderEnvironment.PAPER,
    order_type: OrderType = OrderType.LIMIT,
    intended_trade_date: date | None = None,
    execution_start_time: str | None = None,
    execution_end_time: str | None = None,
) -> OrderRequest:
    return OrderRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=10,
        reference_price=Decimal("500"),
        currency=Currency.USD,
        environment=environment,
        notional_cnh=Decimal("36000"),
        rationale="test",
        intended_trade_date=intended_trade_date,
        execution_start_time=execution_start_time,
        execution_end_time=execution_end_time,
    )
