from __future__ import annotations

from systematic_trading.execution.ib_compat import compatible_ib_errors

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha1
import logging
from pathlib import Path
from threading import Event, Thread
from typing import Protocol
from zoneinfo import ZoneInfo

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
from systematic_trading.execution.window import proposal_is_expired
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.interfaces import BrokerOrderStore

logger = logging.getLogger(__name__)


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


class BrokerOrderRejectedError(RuntimeError):
    """A broker explicitly rejected an order without accepting any execution."""


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


from systematic_trading.execution.locks import serialized_orders


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

    @serialized_orders
    def submit_approved_proposal(
        self,
        *,
        proposal: TradeProposal,
        store: BrokerOrderStore,
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
        submission_issues: list[str] = []
        order_items = _selected_order_items(proposal, order_indexes)
        stage = "connecting to IB Gateway"
        try:
            broker_next_id = client.connect(profile)
            stage = "reading the restored order ledger"
            # Gateway's sequence can restart on a different installation. Keep
            # IDs above both the broker floor and every retained local order.
            # The database's unique constraint remains the final race guard.
            retained_ids = [
                record.broker_order_id for record in store.list_broker_order_records()
                if record.environment == environment and record.broker == "interactive-brokers"
                and record.broker_order_id is not None
            ]
            first_order_id = max(broker_next_id, max(retained_ids, default=0) + 1)
            submitted_at = datetime.now(tz=UTC)
            for sequence, (index, order) in enumerate(order_items):
                broker_order_id = first_order_id + sequence
                order_ref = _order_ref(proposal.proposal_id, index)
                prior_record = next((r for r in store.list_broker_order_records(proposal.proposal_id)
                                     if r.order_index == index), None)
                record = BrokerOrderRecord(
                    local_order_id=prior_record.local_order_id if prior_record else _local_order_id(proposal.proposal_id, index, order),
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
                contract = self.contract_spec_for(order.symbol)
                ib_order = order_spec_for(order, order_ref=order_ref)
                stage = f"reserving {order.symbol} before sending it to IB"
                if not store.reserve_broker_order_record(record, allow_resubmit=allow_resubmit):
                    submission_issues.append(f"{order_ref}: order intent already claimed; reconcile before retrying.")
                    break
                stage = f"recording the broker outcome for {order.symbol}"
                try:
                    client.place_order(broker_order_id, contract, ib_order)
                except Exception as exc:
                    record = record.model_copy(
                        update={
                            "status": (BrokerOrderStatus.REJECTED if isinstance(exc, BrokerOrderRejectedError)
                                       else BrokerOrderStatus.PENDING_SUBMIT),
                            "message": str(exc),
                            "updated_at": datetime.now(tz=UTC),
                        }
                    )
                    store.save_broker_order_record(record)
                    records.append(record)
                    if not isinstance(exc, BrokerOrderRejectedError):
                        # The broker may have accepted it. Preserve the claim and
                        # stop the batch until its outcome has been reconciled.
                        break
                    continue
                record = record.model_copy(
                    update={
                        "status": BrokerOrderStatus.SUBMITTED,
                        "message": "; ".join(client.warnings_for_order(broker_order_id))
                        if hasattr(client, "warnings_for_order") else None,
                        "updated_at": datetime.now(tz=UTC),
                    }
                )
                store.save_broker_order_record(record)
                records.append(record)
        except Exception as exc:
            logger.exception("Proposal %s stopped while %s", proposal.proposal_id, stage)
            submission_issues.append(
                f"Submission stopped while {stage} ({type(exc).__name__}). "
                "Approval is retained. Sync broker orders and review all recorded outcomes before retrying; "
                "earlier orders in this batch may already have reached IB."
            )
        finally:
            client.disconnect()

        return BrokerSubmissionResult(
            proposal_id=proposal.proposal_id,
            environment=environment,
            submitted_at=(records[0].submitted_at if records else None) or datetime.now(tz=UTC),
            records=records,
            validation_issues=submission_issues,
        )

    def validate_proposal_for_submission(
        self,
        *,
        proposal: TradeProposal,
        store: BrokerOrderStore,
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
        store: BrokerOrderStore,
        environment: OrderEnvironment,
        allow_resubmit: bool,
        order_indexes: set[int] | None = None,
    ) -> list[str]:
        from systematic_trading.portfolio.strategy_allocation import allocation_binding_issues
        issues: list[str] = allocation_binding_issues(store, proposal)
        order_items = _selected_order_items(proposal, order_indexes)
        if proposal.status != ProposalStatus.APPROVED:
            issues.append(f"{proposal.proposal_id}: proposal status must be approved before routing.")
        get_proposal = getattr(store, "get_proposal", None)
        current = get_proposal(proposal.proposal_id) if get_proposal else None
        if current is not None and current.status != ProposalStatus.APPROVED:
            issues.append(f"{proposal.proposal_id}: the stored approval changed; refresh before routing.")
        if proposal_is_expired(proposal, self.settings):
            issues.append(f"{proposal.proposal_id}: execution window expired; missed proposals cannot be routed.")
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
        selected_indexes = {index for index, _ in order_items}
        for record in existing_records:
            if record.order_index in selected_indexes and record.broker_observation and (
                Decimal(str(record.broker_observation.get("filled", "-1"))) != 0
            ):
                issues.append(f"{record.order_ref}: broker fill evidence is nonzero or unknown; resubmission blocked.")
            if record.order_index in selected_indexes and (
                record.status not in {BrokerOrderStatus.REJECTED, BrokerOrderStatus.CANCELLED}
                or record.filled_quantity > 0
            ):
                issues.append(f"{record.order_ref}: active, filled, or uncertain order cannot be resubmitted.")
        recovery_times = []
        for record in store.list_broker_order_records():
            if record.environment == environment:
                recovery_times.extend(audit.recovered_at for audit in record.execution_recoveries)
            if record.environment == environment and record.pending_action:
                issues.append(f"{record.order_ref}: unresolved management action blocks new routing.")
            if record.environment == environment and record.execution_sync_issue:
                issues.append(f"{record.order_ref}: unresolved execution history blocks new routing.")
            if record.environment == environment and record.status == BrokerOrderStatus.PENDING_SUBMIT:
                issues.append(f"{record.order_ref}: unresolved submission outcome blocks new routing until reconciled.")
        # Local import avoids the reconciliation/client import cycle.
        from systematic_trading.execution.reconciliation import submission_reconciliation_issues
        issues.extend(submission_reconciliation_issues(self.settings, required_after=max(recovery_times, default=None)))
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
        store: BrokerOrderStore,
        environment: OrderEnvironment = OrderEnvironment.PAPER,
    ) -> BrokerFillSyncResult:
        profile = self.adapter.profile_for(environment).model_copy(
            update={"client_id": self.settings.ib_execution_sync_client_id or self.settings.ib_client_id + 30}
        )
        client = self.client or IbApiExecutionSyncClient(evidence_dir=self.settings.data_dir / 'broker_evidence' / 'executions')
        fills = client.fetch_fills(profile)
        existing_records = [
            record
            for record in store.list_broker_order_records()
            if record.environment == environment
        ]
        from systematic_trading.execution.fills import match_execution

        fills_by_record: dict[str, list[BrokerExecutionFill]] = {}
        warnings: list[str] = []
        for fill in fills:
            record = match_execution(existing_records, fill)
            if record is None:
                warnings.append(
                    f"Unmatched IB fill for {fill.symbol} order_id={fill.broker_order_id or ''} order_ref={fill.order_ref or ''}."
                )
                continue
            fills_by_record.setdefault(record.local_order_id, []).append(fill)

        updated_records: list[BrokerOrderRecord] = []
        records_by_local_id = {record.local_order_id: record for record in existing_records}
        for local_order_id, record_fills in fills_by_record.items():
            updated = store.apply_broker_execution_fills(local_order_id, record_fills)
            if updated.execution_sync_issue:
                warnings.append(f"{updated.order_ref}: {updated.execution_sync_issue}")
            if updated != records_by_local_id[local_order_id]:
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
                self.order_warnings: dict[int, list[str]] = {}

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

            @compatible_ib_errors
            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                message = f"{reqId}:{errorCode}:{errorString}"
                self.errors.append(message)
                if reqId >= 0:
                    if errorCode == 2111:
                        # IB's documented algo-date adjustment notice. It is
                        # neither a rejection nor proof of acceptance: wait for
                        # openOrder/orderStatus, retaining the warning for audit.
                        self.order_warnings.setdefault(reqId, []).append(message)
                        return
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

    def warnings_for_order(self, order_id: int) -> list[str]:
        return list(self._app.order_warnings.get(order_id, [])) if self._app else []

    def disconnect(self) -> None:
        thread = self._thread
        if self._app is not None:
            self._app.disconnect()
        if thread is not None:
            thread.join(timeout=2)
        self._app = None
        self._thread = None


class IbApiExecutionSyncClient:
    def __init__(self, *, connection_timeout_seconds: float = 10.0, execution_timeout_seconds: float = 15.0,
                 evidence_dir: Path = Path('var/broker_evidence/executions'), history_days: int = 7) -> None:
        self.connection_timeout_seconds = connection_timeout_seconds
        self.execution_timeout_seconds = execution_timeout_seconds
        if not 1 <= history_days <= 7:
            raise ValueError('IB execution history must cover between one and seven days.')
        self.evidence_dir = evidence_dir
        self.history_days = history_days

    def fetch_fills(self, profile: BrokerConnectionProfile) -> list[BrokerExecutionFill]:
        try:
            from ibapi.client import EClient
            from ibapi.execution import ExecutionFilter
            from ibapi.server_versions import MIN_SERVER_VER_PARAMETRIZED_DAYS_OF_EXECUTIONS
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB execution sync requires the ibapi package. Install the optional IB dependency first.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = Event()
                self.done = Event()
                self.errors: list[str] = []
                self.rows: list[dict] = []
                self.completed = False
                self.request_error = None

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.ready.set()

            def execDetails(self, reqId: int, contract: object, execution: object) -> None:  # noqa: N802
                if reqId != 91001:
                    return
                # Retain the callback before parsing. Never substitute receipt
                # time for an unsupported broker timestamp or truncate shares.
                self.rows.append(dict(
                    contract={key: str(getattr(contract, key, '') or '') for key in ('symbol', 'currency', 'conId', 'secType')},
                    execution={key: str(getattr(execution, key, '') or '') for key in (
                        'execId', 'acctNumber', 'orderId', 'orderRef', 'permId', 'clientId',
                        'side', 'shares', 'price', 'cumQty', 'time', 'pendingPriceRevision')}))

            def execDetailsEnd(self, reqId: int) -> None:  # noqa: N802
                if reqId == 91001:
                    self.completed = True
                    self.done.set()

            def connectionClosed(self) -> None:  # noqa: N802
                if not self.completed:
                    self.request_error = 'IB disconnected before execution snapshot completion.'
                    self.done.set()

            @compatible_ib_errors
            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                self.errors.append(f"{reqId}:{errorCode}:{errorString}")
                if reqId == 91001 or errorCode in {1100, 1300, 502, 504}:
                    self.request_error = self.errors[-1]
                    self.done.set()

        app = _App()
        thread = None
        failure = None
        server_version = None
        try:
            app.connect(profile.host, profile.port, profile.client_id)
            thread = Thread(target=app.run, daemon=True)
            thread.start()
            if not app.ready.wait(self.connection_timeout_seconds):
                raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")
            server_version = app.serverVersion()
            query = ExecutionFilter()
            if self.history_days > 1:
                if (server_version or 0) < MIN_SERVER_VER_PARAMETRIZED_DAYS_OF_EXECUTIONS:
                    raise ValueError('IB Gateway must support multi-day executions (server version 200 or newer).')
                query.lastNDays = self.history_days
            app.reqExecutions(91001, query)
            if not app.done.wait(self.execution_timeout_seconds):
                recent_errors = app.errors[-5:]
                suffix = f" Recent IB messages: {'; '.join(recent_errors)}" if recent_errors else ""
                raise TimeoutError(f"Timed out waiting for IB execution details.{suffix}")
            if app.request_error or not app.completed:
                raise RuntimeError(app.request_error or 'IB execution snapshot did not complete.')
        except Exception as exc:
            failure = exc
        finally:
            app.disconnect()
            if thread:
                thread.join(timeout=2)
        from systematic_trading.execution.evidence import retain_execution_response
        reference = retain_execution_response(self.evidence_dir, dict(
            client_id=profile.client_id, server_version=server_version, requested_days=self.history_days,
            completed=app.completed and failure is None, request_error=str(failure) if failure else None,
            errors=app.errors, rows=app.rows), client_id=profile.client_id, captured_at=datetime.now(UTC).isoformat())
        if failure:
            raise RuntimeError(f'IB execution snapshot failed: {failure} Evidence: {reference}') from failure
        try:
            return [_execution_from_callback(row, reference) for row in app.rows]
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f'IB execution snapshot rejected: {exc} Evidence: {reference}') from exc


def _execution_from_callback(row, reference):
    execution, contract = row['execution'], row['contract']
    identifier = execution['execId']
    def whole(key):
        value = Decimal(execution[key])
        if not value.is_finite() or value <= 0 or value != value.to_integral_value():
            raise ValueError(f'Execution {identifier}: unsupported {key}={execution[key]!r}; whole positive shares required.')
        return int(value)
    side = {'BOT': OrderSide.BUY, 'SLD': OrderSide.SELL}.get(execution['side'].upper())
    if not side or not identifier or not execution['acctNumber'] or not contract['symbol']:
        raise ValueError(f'Execution {identifier}: missing or unsupported identity/side.')
    if execution['pendingPriceRevision'].lower() == 'true':
        raise ValueError(f'Execution {identifier}: broker price revision is pending; retry synchronization.')
    price = Decimal(execution['price'])
    if not price.is_finite() or price <= 0:
        raise ValueError(f'Execution {identifier}: invalid price {execution["price"]!r}.')
    return BrokerExecutionFill(execution_id=identifier, account=execution['acctNumber'],
        broker_order_id=int(execution['orderId']) if execution['orderId'] else None,
        order_ref=execution['orderRef'] or None, symbol=contract['symbol'].upper(), side=side,
        quantity=whole('shares'), cumulative_quantity=whole('cumQty'),
        average_price=price, currency=Currency(contract['currency']),
        filled_at=_parse_ib_execution_time(execution['time']), evidence_ref=reference)


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


def _parse_ib_execution_time(value: str, *, default_timezone: tzinfo | None = None) -> datetime:
    text = ' '.join(value.split())
    try:
        return datetime.strptime(text, '%Y%m%d-%H:%M:%S').replace(tzinfo=UTC)
    except ValueError:
        pass
    parts = text.split(' ')
    timezone = default_timezone
    if len(parts) == 3:
        try:
            timezone = ZoneInfo(parts.pop())
        except (KeyError, ValueError) as exc:
            raise ValueError(f'Unsupported IB execution timezone: {value!r}') from exc
    if timezone is None or len(parts) != 2:
        raise ValueError(f'IB execution time requires a full timestamp and explicit timezone: {value!r}')
    try:
        parsed = datetime.strptime(' '.join(parts), '%Y%m%d %H:%M:%S')
    except ValueError as exc:
        raise ValueError(f'Invalid IB execution timestamp: {value!r}') from exc
    local = parsed.replace(tzinfo=timezone)
    utc = local.astimezone(UTC)
    if (utc.astimezone(timezone).replace(tzinfo=None) != parsed
            or local.utcoffset() != local.replace(fold=1).utcoffset()):
        raise ValueError(f'Ambiguous or nonexistent IB execution timestamp: {value!r}')
    return utc


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
