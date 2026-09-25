from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from systematic_trading.execution.recovery import ExecutionRecoveryRequest

from systematic_trading.domain import (
    ApprovalDecision,
    AnyPlatformEvent,
    BrokerExecutionFill,
    BrokerOrderRecord,
    Currency,
    FXRate,
    FundamentalSnapshot,
    Instrument,
    PlatformEventOutboxRecord,
    PlatformEventType,
    PnLBaseline,
    PnLSnapshot,
    PriceBar,
    ProposalStatus,
    ThesisMemo,
    TradeProposal,
    WatchlistEntry,
)


@runtime_checkable
class InitializableStore(Protocol):
    def initialize(self) -> None:
        ...


@runtime_checkable
class WatchlistStore(Protocol):
    def upsert_instrument(self, instrument: Instrument) -> Instrument:
        ...

    def list_instruments(self) -> list[Instrument]:
        ...

    def upsert_thesis(self, thesis: ThesisMemo) -> ThesisMemo:
        ...

    def list_theses(self) -> list[ThesisMemo]:
        ...

    def list_watchlist(self) -> list[WatchlistEntry]:
        ...


@runtime_checkable
class ProposalStore(Protocol):
    def queue_proposal_once(self, proposal: TradeProposal) -> TradeProposal:
        """Insert a deterministic proposal once without overwriting decisions."""
        ...

    def save_proposal(self, proposal: TradeProposal) -> TradeProposal:
        ...

    def get_proposal(self, proposal_id: str) -> TradeProposal | None:
        ...

    def list_proposals(self, status: ProposalStatus | None = None) -> list[TradeProposal]:
        ...

    def apply_decision(self, decision: ApprovalDecision, *, expected_status: ProposalStatus | None = None) -> TradeProposal:
        ...


@runtime_checkable
class BrokerOrderStore(Protocol):
    def update_order_management(self, local_order_id: str, transform) -> BrokerOrderRecord:
        """Atomically transform the latest order, preserving concurrent fills."""
        ...

    def recover_broker_executions(
        self, request: ExecutionRecoveryRequest, *, review_token: str,
    ) -> BrokerOrderRecord:
        """Apply a reviewed paper recovery atomically with its audit and outbox."""
        ...

    def apply_broker_execution_fills(
        self, local_order_id: str, fills: list[BrokerExecutionFill],
    ) -> BrokerOrderRecord:
        """Atomically merge execution evidence and persist cumulative order state."""
        ...

    def reserve_broker_order_record(self, record: BrokerOrderRecord, *, allow_resubmit: bool = False) -> bool:
        """Atomically claim an unsubmitted intent or an unfilled, confirmed failure."""
        ...

    def save_broker_order_record(self, record: BrokerOrderRecord) -> BrokerOrderRecord:
        ...

    def save_broker_order_records(self, records: list[BrokerOrderRecord]) -> list[BrokerOrderRecord]:
        ...

    def list_broker_order_records(self, proposal_id: str | None = None) -> list[BrokerOrderRecord]:
        ...


@runtime_checkable
class MarketDataStore(Protocol):
    def upsert_price_bar(self, symbol: str, bar: PriceBar) -> PriceBar:
        ...

    def list_price_bars(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PriceBar]:
        ...

    def upsert_fx_rate(self, rate: FXRate) -> FXRate:
        ...

    def list_fx_rates(
        self,
        base_currency: Currency,
        *,
        quote_currency: Currency = Currency.CNH,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[FXRate]:
        ...

    def upsert_fundamental_snapshot(self, snapshot: FundamentalSnapshot) -> FundamentalSnapshot:
        ...

    def list_fundamental_snapshots(
        self,
        symbol: str,
        *,
        start_available_date: date | None = None,
        end_available_date: date | None = None,
    ) -> list[FundamentalSnapshot]:
        ...

    def latest_fundamental_snapshot(self, symbol: str, *, as_of: date) -> FundamentalSnapshot | None:
        ...


@runtime_checkable
class PnLStore(Protocol):
    def save_pnl_snapshot(self, snapshot: PnLSnapshot) -> PnLSnapshot:
        ...

    def list_pnl_snapshots(self, *, limit: int = 100) -> list[PnLSnapshot]:
        ...

    def save_pnl_baseline(self, baseline: PnLBaseline) -> PnLBaseline:
        ...

    def latest_pnl_baseline(self) -> PnLBaseline | None:
        ...


@runtime_checkable
class PlatformEventAppendStore(Protocol):
    def append_platform_event(self, event: AnyPlatformEvent) -> PlatformEventOutboxRecord:
        ...


@runtime_checkable
class PlatformEventOutboxStore(Protocol):
    def list_pending_platform_events(self, *, limit: int = 100) -> list[PlatformEventOutboxRecord]:
        ...

    def mark_platform_event_published(
        self,
        event_id: str,
        *,
        published_at: datetime | None = None,
    ) -> PlatformEventOutboxRecord | None:
        ...

    def record_platform_event_publish_failure(
        self,
        event_id: str,
        error: str,
    ) -> PlatformEventOutboxRecord | None:
        ...


@runtime_checkable
class PlatformEventOutboxReplayStore(Protocol):
    def list_platform_event_outbox_records(
        self,
        *,
        limit: int = 1000,
        published: bool | None = None,
        event_type: PlatformEventType | None = None,
    ) -> list[PlatformEventOutboxRecord]:
        ...


@runtime_checkable
class TradingStore(
    InitializableStore,
    WatchlistStore,
    ProposalStore,
    BrokerOrderStore,
    MarketDataStore,
    PnLStore,
    PlatformEventAppendStore,
    PlatformEventOutboxStore,
    PlatformEventOutboxReplayStore,
    Protocol,
):
    """Transactional store contract shared by app, services, and operator scripts."""


TransactionalStore = TradingStore
