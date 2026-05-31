from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha1
from threading import Event, Thread
from typing import Protocol

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import (
    AssetClass,
    BrokerOrderStatus,
    Currency,
    Exchange,
    OrderEnvironment,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from systematic_trading.domain.execution import (
    BrokerExecutionFill,
    BrokerFillSyncResult,
    BrokerOrderRecord,
    BrokerSubmissionResult,
    OrderRequest,
    TradeProposal,
)
from systematic_trading.domain.market import Instrument
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.sqlite import SQLiteStore


class BrokerConnectionProfile(BaseModel):
    environment: OrderEnvironment
    host: str
    port: int
    client_id: int
    enabled: bool
    safeguards: list[str] = Field(default_factory=list)
    notes: str | None = None


class IBContractSpec(BaseModel):
    symbol: str
    security_type: str = "STK"
    exchange: str = "SMART"
    currency: Currency
    primary_exchange: str | None = None


class IBOrderSpec(BaseModel):
    action: str
    order_type: str
    quantity: int
    limit_price: Decimal | None = None
    time_in_force: str = "DAY"
    transmit: bool = True
    order_ref: str
    algo_strategy: str | None = None
    algo_params: dict[str, str] = Field(default_factory=dict)


class IBOrderClient(Protocol):
    def connect(self, profile: BrokerConnectionProfile) -> int:
        """Connect to IB and return the first valid broker order id."""

    def place_order(self, order_id: int, contract: IBContractSpec, order: IBOrderSpec) -> None:
        """Submit one order to IB."""

    def disconnect(self) -> None:
        """Disconnect from IB."""


class IBExecutionSyncClient(Protocol):
    def fetch_fills(self, profile: BrokerConnectionProfile) -> list[BrokerExecutionFill]:
        """Fetch broker executions that can be reconciled into local order records."""


class BrokerAdapter(ABC):
    @abstractmethod
    def connection_profiles(self) -> list[BrokerConnectionProfile]:
        raise NotImplementedError

    @abstractmethod
    def validate_orders(self, orders: list[OrderRequest]) -> list[str]:
        raise NotImplementedError


class InteractiveBrokersAdapter(BrokerAdapter):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def connection_profiles(self) -> list[BrokerConnectionProfile]:
        common_safeguards = [
            "Require explicit approval before submitting any order.",
            "Mirror broker state locally and reconcile positions and cash before routing.",
            "Reject stale-price and duplicate-order submissions.",
        ]
        return [
            BrokerConnectionProfile(
                environment=OrderEnvironment.PAPER,
                host=self.settings.ib_host,
                port=self.settings.ib_paper_port,
                client_id=self.settings.ib_client_id,
                enabled=True,
                safeguards=common_safeguards,
                notes="Default environment for v1 execution validation.",
            ),
            BrokerConnectionProfile(
                environment=OrderEnvironment.LIVE,
                host=self.settings.ib_host,
                port=self.settings.ib_live_port,
                client_id=self.settings.ib_client_id,
                enabled=False,
                safeguards=common_safeguards
                + ["Keep live trading disabled until paper reconciliation is stable for an extended period."],
                notes="Planned environment only. Live routing remains disabled in v1.",
            ),
        ]

    def validate_orders(self, orders: list[OrderRequest]) -> list[str]:
        issues: list[str] = []
        for order in orders:
            if order.environment == OrderEnvironment.LIVE:
                issues.append(f"{order.symbol}: live routing is disabled in v1.")
            if order.quantity <= 0:
                issues.append(f"{order.symbol}: quantity must be positive.")
        return issues

    def profile_for(self, environment: OrderEnvironment) -> BrokerConnectionProfile:
        for profile in self.connection_profiles():
            if profile.environment == environment:
                return profile
        raise ValueError(f"Unsupported IB environment: {environment}")


class InteractiveBrokersOrderRouter:
    def __init__(
        self,
        settings: AppSettings,
        *,
        client: IBOrderClient | None = None,
        instruments: dict[str, Instrument] | None = None,
    ) -> None:
        self.settings = settings
        self.adapter = InteractiveBrokersAdapter(settings)
        self.client = client
        self.instruments = instruments or instruments_for_definition(current_sota_definition())

    def submit_approved_proposal(
        self,
        *,
        proposal: TradeProposal,
        store: SQLiteStore,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
        allow_resubmit: bool = False,
        order_indexes: set[int] | None = None,
    ) -> BrokerSubmissionResult:
        validation_issues = self._validate_proposal_for_submission(
            proposal,
            store,
            environment,
            allow_resubmit,
            order_indexes=order_indexes,
        )
        if validation_issues:
            return BrokerSubmissionResult(
                proposal_id=proposal.proposal_id,
                environment=environment,
                records=[],
                validation_issues=validation_issues,
            )

        profile = self.adapter.profile_for(environment)
        client = self.client or IbApiOrderClient()
        records: list[BrokerOrderRecord] = []
        order_items = _selected_order_items(proposal, order_indexes)
        try:
            first_order_id = client.connect(profile)
            submitted_at = datetime.now(tz=UTC)
            for sequence, (index, order) in enumerate(order_items):
                broker_order_id = first_order_id + sequence
                order_ref = _order_ref(proposal.proposal_id, index)
                record = BrokerOrderRecord(
                    local_order_id=_local_order_id(proposal.proposal_id, index, order),
                    proposal_id=proposal.proposal_id,
                    environment=environment,
                    order_index=index,
                    order=order,
                    order_ref=order_ref,
                    broker_order_id=broker_order_id,
                    status=BrokerOrderStatus.PENDING_SUBMIT,
                    submitted_at=submitted_at,
                    remaining_quantity=order.quantity,
                )
                store.save_broker_order_record(record)
                contract = self.contract_spec_for(order.symbol)
                ib_order = order_spec_for(order, order_ref=order_ref)
                try:
                    client.place_order(broker_order_id, contract, ib_order)
                except Exception as exc:
                    record = record.model_copy(
                        update={
                            "status": BrokerOrderStatus.REJECTED,
                            "message": str(exc),
                            "updated_at": datetime.now(tz=UTC),
                        }
                    )
                    store.save_broker_order_record(record)
                    records.append(record)
                    continue
                record = record.model_copy(
                    update={
                        "status": BrokerOrderStatus.SUBMITTED,
                        "updated_at": datetime.now(tz=UTC),
                    }
                )
                store.save_broker_order_record(record)
                records.append(record)
        finally:
            client.disconnect()

        return BrokerSubmissionResult(
            proposal_id=proposal.proposal_id,
            environment=environment,
            submitted_at=records[0].submitted_at or datetime.now(tz=UTC),
            records=records,
        )

    def validate_proposal_for_submission(
        self,
        *,
        proposal: TradeProposal,
        store: SQLiteStore,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
        allow_resubmit: bool = False,
        order_indexes: set[int] | None = None,
    ) -> list[str]:
        return self._validate_proposal_for_submission(
            proposal,
            store,
            environment,
            allow_resubmit,
            order_indexes=order_indexes,
        )

    def contract_spec_for(self, symbol: str) -> IBContractSpec:
        instrument = self.instruments.get(symbol)
        if instrument is None:
            raise ValueError(f"{symbol} is not in the configured IB instrument universe.")
        primary_exchange = _primary_exchange(instrument)
        return IBContractSpec(
            symbol=symbol,
            currency=instrument.quote_currency,
            primary_exchange=primary_exchange,
        )

    def _validate_proposal_for_submission(
        self,
        proposal: TradeProposal,
        store: SQLiteStore,
        environment: OrderEnvironment,
        allow_resubmit: bool,
        order_indexes: set[int] | None = None,
    ) -> list[str]:
        issues: list[str] = []
        order_items = _selected_order_items(proposal, order_indexes)
        if proposal.status != ProposalStatus.APPROVED:
            issues.append(f"{proposal.proposal_id}: proposal status must be approved before routing.")
        if environment == OrderEnvironment.LIVE:
            issues.append(f"{proposal.proposal_id}: live routing is disabled in v1.")
        profile = self.adapter.profile_for(environment)
        if not profile.enabled:
            issues.append(f"{proposal.proposal_id}: IB {environment.value} profile is disabled.")
        if not order_items:
            issues.append(f"{proposal.proposal_id}: proposal has no orders to route.")
        issues.extend(self.adapter.validate_orders([order for _, order in order_items]))
        for _, order in order_items:
            if order.environment != environment:
                issues.append(
                    f"{order.symbol}: order environment {order.environment.value} does not match route environment {environment.value}."
                )
            if order.symbol not in self.instruments:
                issues.append(f"{order.symbol}: instrument is not in the configured IB route universe.")
            if order.notional_cnh <= Decimal("0"):
                issues.append(f"{order.symbol}: notional must be positive.")
            if order.quantity < 1:
                issues.append(f"{order.symbol}: quantity must be at least 1.")
        existing_records = store.list_broker_order_records(proposal.proposal_id)
        if existing_records and not allow_resubmit:
            issues.append(f"{proposal.proposal_id}: broker order records already exist; pass allow_resubmit to override.")
        return issues


class InteractiveBrokersExecutionSynchronizer:
    def __init__(
        self,
        settings: AppSettings,
        *,
        client: IBExecutionSyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.adapter = InteractiveBrokersAdapter(settings)
        self.client = client

    def sync_order_fills(
        self,
        *,
        store: SQLiteStore,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
    ) -> BrokerFillSyncResult:
        profile = self.adapter.profile_for(environment).model_copy(
            update={"client_id": self.settings.ib_execution_sync_client_id or self.settings.ib_client_id + 30}
        )
        client = self.client or IbApiExecutionSyncClient()
        fills = client.fetch_fills(profile)
        existing_records = [
            record
            for record in store.list_broker_order_records()
            if record.environment == environment
        ]
        by_broker_order_id = {
            record.broker_order_id: record
            for record in existing_records
            if record.broker_order_id is not None
        }
        by_order_ref = {
            record.order_ref: record
            for record in existing_records
            if record.order_ref
        }
        fills_by_record: dict[str, list[BrokerExecutionFill]] = {}
        warnings: list[str] = []
        for fill in fills:
            record = None
            if fill.broker_order_id is not None:
                record = by_broker_order_id.get(fill.broker_order_id)
            if record is None and fill.order_ref:
                record = by_order_ref.get(fill.order_ref)
            if record is None:
                warnings.append(
                    f"Unmatched IB fill for {fill.symbol} order_id={fill.broker_order_id or ''} order_ref={fill.order_ref or ''}."
                )
                continue
            fills_by_record.setdefault(record.local_order_id, []).append(fill)

        updated_records: list[BrokerOrderRecord] = []
        records_by_local_id = {record.local_order_id: record for record in existing_records}
        for local_order_id, record_fills in fills_by_record.items():
            record = records_by_local_id[local_order_id]
            filled_quantity = sum(fill.quantity for fill in record_fills)
            weighted_notional = sum(
                Decimal(fill.quantity) * fill.average_price
                for fill in record_fills
            )
            average_fill_price = weighted_notional / Decimal(filled_quantity)
            remaining_quantity = max(record.order.quantity - filled_quantity, 0)
            status = BrokerOrderStatus.FILLED if remaining_quantity == 0 else BrokerOrderStatus.PARTIALLY_FILLED
            updated = record.model_copy(
                update={
                    "status": status,
                    "filled_quantity": filled_quantity,
                    "remaining_quantity": remaining_quantity,
                    "average_fill_price": average_fill_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                    "updated_at": max(fill.filled_at for fill in record_fills),
                    "message": f"Synced {len(record_fills)} IB execution fill(s).",
                }
            )
            store.save_broker_order_record(updated)
            updated_records.append(updated)

        return BrokerFillSyncResult(
            environment=environment,
            fills_seen=len(fills),
            records_updated=len(updated_records),
            records=updated_records,
            warnings=warnings,
        )


class IbApiOrderClient:
    def __init__(self, *, connection_timeout_seconds: float = 10.0, order_ack_timeout_seconds: float = 15.0) -> None:
        self.connection_timeout_seconds = connection_timeout_seconds
        self.order_ack_timeout_seconds = order_ack_timeout_seconds
        self._app: object | None = None
        self._thread: Thread | None = None

    def connect(self, profile: BrokerConnectionProfile) -> int:
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB routing requires the ibapi package. Install the optional IB dependency first.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.next_order_id: int | None = None
                self.ready = Event()
                self.errors: list[str] = []
                self.order_events: dict[int, Event] = {}
                self.order_errors: dict[int, list[str]] = {}

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.next_order_id = orderId
                self.ready.set()

            def openOrder(self, orderId: int, contract: object, order: object, orderState: object) -> None:  # noqa: N802
                self.order_events.setdefault(orderId, Event()).set()

            def orderStatus(  # noqa: N802
                self,
                orderId: int,
                status: str,
                filled: float,
                remaining: float,
                avgFillPrice: float,
                permId: int,
                parentId: int,
                lastFillPrice: float,
                clientId: int,
                whyHeld: str,
                mktCapPrice: float = 0.0,
            ) -> None:
                self.order_events.setdefault(orderId, Event()).set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                message = f"{reqId}:{errorCode}:{errorString}"
                self.errors.append(message)
                if reqId >= 0:
                    self.order_errors.setdefault(reqId, []).append(message)
                    self.order_events.setdefault(reqId, Event()).set()

        app = _App()
        app.connect(profile.host, profile.port, profile.client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        if not app.ready.wait(self.connection_timeout_seconds):
            app.disconnect()
            raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")
        if app.next_order_id is None:
            app.disconnect()
            raise RuntimeError("IB did not provide a next valid order id.")
        self._app = app
        self._thread = thread
        return app.next_order_id

    def place_order(self, order_id: int, contract: IBContractSpec, order: IBOrderSpec) -> None:
        if self._app is None:
            raise RuntimeError("IB client is not connected.")
        event = self._app.order_events.setdefault(order_id, Event())
        self._app.placeOrder(order_id, _to_ib_contract(contract), _to_ib_order(order))
        if not event.wait(self.order_ack_timeout_seconds):
            recent_errors = getattr(self._app, "errors", [])[-5:]
            suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
            raise TimeoutError(f"Timed out waiting for IB acknowledgement for order {order_id}.{suffix}")
        errors = self._app.order_errors.get(order_id, [])
        if errors:
            raise RuntimeError("; ".join(errors))

    def disconnect(self) -> None:
        thread = self._thread
        if self._app is not None:
            self._app.disconnect()
        if thread is not None:
            thread.join(timeout=2)
        self._app = None
        self._thread = None


class IbApiExecutionSyncClient:
    def __init__(self, *, connection_timeout_seconds: float = 10.0, execution_timeout_seconds: float = 15.0) -> None:
        self.connection_timeout_seconds = connection_timeout_seconds
        self.execution_timeout_seconds = execution_timeout_seconds

    def fetch_fills(self, profile: BrokerConnectionProfile) -> list[BrokerExecutionFill]:
        try:
            from ibapi.client import EClient
            from ibapi.execution import ExecutionFilter
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB execution sync requires the ibapi package. Install the optional IB dependency first.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = Event()
                self.done = Event()
                self.errors: list[str] = []
                self.fills: list[BrokerExecutionFill] = []

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.ready.set()

            def execDetails(self, reqId: int, contract: object, execution: object) -> None:  # noqa: N802
                side_text = str(getattr(execution, "side", "")).upper()
                if side_text.startswith("BOT"):
                    side = OrderSide.BUY
                elif side_text.startswith("SLD"):
                    side = OrderSide.SELL
                else:
                    return
                quantity = int(Decimal(str(getattr(execution, "shares", "0"))))
                avg_price = Decimal(str(getattr(execution, "avgPrice", "0") or getattr(execution, "price", "0")))
                if quantity <= 0 or avg_price <= 0:
                    return
                broker_order_id = int(getattr(execution, "orderId")) if getattr(execution, "orderId", None) is not None else None
                order_ref = str(getattr(execution, "orderRef", "") or "") or None
                symbol = str(getattr(contract, "symbol", "") or "").upper()
                currency_text = str(getattr(contract, "currency", "") or "")
                currency = Currency(currency_text) if currency_text in Currency._value2member_map_ else None
                self.fills.append(
                    BrokerExecutionFill(
                        broker_order_id=broker_order_id,
                        order_ref=order_ref,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        average_price=avg_price,
                        filled_at=_parse_ib_execution_time(str(getattr(execution, "time", "") or "")),
                        currency=currency,
                    )
                )

            def execDetailsEnd(self, reqId: int) -> None:  # noqa: N802
                self.done.set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                self.errors.append(f"{reqId}:{errorCode}:{errorString}")

        app = _App()
        app.connect(profile.host, profile.port, profile.client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        try:
            if not app.ready.wait(self.connection_timeout_seconds):
                raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")
            app.reqExecutions(91001, ExecutionFilter())
            if not app.done.wait(self.execution_timeout_seconds):
                recent_errors = app.errors[-5:]
                suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
                raise TimeoutError(f"Timed out waiting for IB execution details.{suffix}")
            return app.fills
        finally:
            app.disconnect()
            thread.join(timeout=2)


def order_spec_for(order: OrderRequest, *, order_ref: str) -> IBOrderSpec:
    action = "BUY" if order.side == OrderSide.BUY else "SELL"
    if order.order_type == OrderType.MARKET:
        return IBOrderSpec(action=action, order_type="MKT", quantity=order.quantity, order_ref=order_ref)
    if order.order_type == OrderType.LIMIT:
        return IBOrderSpec(
            action=action,
            order_type="LMT",
            quantity=order.quantity,
            limit_price=order.reference_price,
            order_ref=order_ref,
        )
    if order.order_type == OrderType.TWAP:
        return IBOrderSpec(
            action=action,
            order_type="LMT",
            quantity=order.quantity,
            limit_price=_marketable_limit_price(order),
            order_ref=order_ref,
            algo_strategy="Twap",
            algo_params=_open_window_algo_params(order),
        )
    if order.order_type == OrderType.VWAP:
        return IBOrderSpec(
            action=action,
            order_type="LMT",
            quantity=order.quantity,
            limit_price=_marketable_limit_price(order),
            order_ref=order_ref,
            algo_strategy="Vwap",
            algo_params={
                "maxPctVol": "0.2",
                **_open_window_algo_params(order),
                "noTakeLiq": "0",
                "speedUp": "1",
            },
        )
    if order.order_type == OrderType.MARKET_ON_OPEN:
        return IBOrderSpec(
            action=action,
            order_type="MKT",
            quantity=order.quantity,
            time_in_force="OPG",
            order_ref=order_ref,
        )
    if order.order_type == OrderType.LIMIT_ON_OPEN:
        return IBOrderSpec(
            action=action,
            order_type="LMT",
            quantity=order.quantity,
            limit_price=order.reference_price,
            time_in_force="OPG",
            order_ref=order_ref,
        )
    raise ValueError(f"Unsupported order type: {order.order_type}")


def _to_ib_contract(spec: IBContractSpec) -> object:
    try:
        from ibapi.contract import Contract
    except ImportError as exc:
        raise RuntimeError("IB routing requires the ibapi package. Install the optional IB dependency first.") from exc
    contract = Contract()
    contract.symbol = spec.symbol
    contract.secType = spec.security_type
    contract.exchange = spec.exchange
    contract.currency = spec.currency.value
    if spec.primary_exchange:
        contract.primaryExchange = spec.primary_exchange
    return contract


def _to_ib_order(spec: IBOrderSpec) -> object:
    try:
        from ibapi.order import Order
    except ImportError as exc:
        raise RuntimeError("IB routing requires the ibapi package. Install the optional IB dependency first.") from exc
    order = Order()
    order.action = spec.action
    order.orderType = spec.order_type
    order.totalQuantity = spec.quantity
    order.tif = spec.time_in_force
    order.transmit = spec.transmit
    order.orderRef = spec.order_ref
    if hasattr(order, "eTradeOnly"):
        order.eTradeOnly = False
    if hasattr(order, "firmQuoteOnly"):
        order.firmQuoteOnly = False
    if spec.limit_price is not None:
        order.lmtPrice = float(spec.limit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if spec.algo_strategy is not None:
        try:
            from ibapi.tag_value import TagValue
        except ImportError as exc:
            raise RuntimeError("IB algo routing requires the ibapi package. Install the optional IB dependency first.") from exc
        order.algoStrategy = spec.algo_strategy
        order.algoParams = [TagValue(tag, value) for tag, value in spec.algo_params.items()]
    return order


def _primary_exchange(instrument: Instrument) -> str | None:
    if instrument.asset_class == AssetClass.ETF:
        return None
    if instrument.exchange in {Exchange.NYSE, Exchange.NASDAQ}:
        return instrument.exchange.value
    return None


def _order_ref(proposal_id: str, index: int) -> str:
    return f"st-{proposal_id}-{index:02d}"


def _local_order_id(proposal_id: str, index: int, order: OrderRequest) -> str:
    payload = f"{proposal_id}:{index}:{order.symbol}:{order.side.value}:{order.quantity}"
    return sha1(payload.encode("utf-8")).hexdigest()[:12]


def _marketable_limit_price(order: OrderRequest, *, price_buffer: Decimal = Decimal("0.03")) -> Decimal:
    multiplier = Decimal("1") + price_buffer if order.side == OrderSide.BUY else Decimal("1") - price_buffer
    return (order.reference_price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _open_window_algo_params(order: OrderRequest) -> dict[str, str]:
    start_time = order.execution_start_time or "09:30"
    end_time = order.execution_end_time or "10:00"
    return {
        "startTime": _ib_algo_datetime(order.intended_trade_date, start_time),
        "endTime": _ib_algo_datetime(order.intended_trade_date, end_time),
        "allowPastEndTime": "0",
    }


def _ib_algo_datetime(trade_date: date | None, time_text: str) -> str:
    normalized_time = _normalize_hhmmss(time_text)
    if trade_date is None:
        return f"{normalized_time} US/Eastern"
    return f"{trade_date:%Y%m%d} {normalized_time} US/Eastern"


def _normalize_hhmmss(value: str) -> str:
    parts = value.strip().split(":")
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
    if len(parts) == 3:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    raise ValueError(f"Invalid execution time: {value}")


def _parse_ib_execution_time(value: str) -> datetime:
    text = value.strip()
    for suffix in (" US/Eastern", " US/Central", " US/Pacific", " UTC"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    text = " ".join(text.split())
    for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(tz=UTC)


def _selected_order_items(
    proposal: TradeProposal,
    order_indexes: set[int] | None,
) -> list[tuple[int, OrderRequest]]:
    if order_indexes is None:
        return list(enumerate(proposal.orders))
    return [
        (index, order)
        for index, order in enumerate(proposal.orders)
        if index in order_indexes
    ]
