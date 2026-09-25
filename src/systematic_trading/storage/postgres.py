from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from systematic_trading.config import AppSettings
from systematic_trading.domain import (
    ApprovalDecision,
    AnyPlatformEvent,
    BrokerOrderRecord,
    BrokerExecutionFill,
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
    decode_platform_event,
)
from systematic_trading.storage.event_builders import (
    fill_recorded_event,
    order_status_changed_event,
    proposal_created_event,
    proposal_decision_event,
    proposal_environment,
)
from systematic_trading.execution.fills import merge_execution_fills, preserve_execution_evidence, validate_baseline_state
from systematic_trading.execution.recovery import ExecutionRecoveryRequest, recover_execution_record


@dataclass(frozen=True)
class PostgresConnectionConfig:
    host: str
    port: int
    database: str
    user: str
    password: str | None = None
    sslmode: str = "prefer"
    application_name: str = "systematic-trading"


class PostgresStore:
    def __init__(self, config: PostgresConnectionConfig) -> None:
        self.config = config

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "PostgresStore":
        password = settings.postgres_app_password or settings.app_postgre_db_password
        return cls(
            PostgresConnectionConfig(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_database,
                user=settings.postgres_app_user,
                password=password,
                sslmode=settings.postgres_sslmode,
                application_name=f"{settings.app_name}-app",
            )
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    to_regclass('portfolio.proposals') AS proposals_table,
                    to_regclass('events.platform_event_outbox') AS outbox_table
                """
            ).fetchone()
        if row is None or row["proposals_table"] is None or row["outbox_table"] is None:
            raise RuntimeError(
                "Postgres transactional tables are not initialized. "
                "Run scripts/apply_postgres_migrations.py with the migrator role first."
            )

    def upsert_instrument(self, instrument: Instrument) -> Instrument:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO core.instruments(
                    symbol,
                    name,
                    asset_class,
                    exchange,
                    quote_currency,
                    country,
                    sector,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    asset_class = excluded.asset_class,
                    exchange = excluded.exchange,
                    quote_currency = excluded.quote_currency,
                    country = excluded.country,
                    sector = excluded.sector,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    instrument.symbol,
                    instrument.name,
                    instrument.asset_class.value,
                    instrument.exchange.value,
                    instrument.quote_currency.value,
                    instrument.country,
                    instrument.sector,
                    _jsonb(instrument),
                ),
            )
        return instrument

    def list_instruments(self) -> list[Instrument]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM core.instruments ORDER BY symbol ASC").fetchall()
        return [Instrument.model_validate(row["payload"]) for row in rows]

    def upsert_thesis(self, thesis: ThesisMemo) -> ThesisMemo:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO core.theses(symbol, status, summary, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s, now(), now())
                ON CONFLICT(symbol) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (thesis.symbol, thesis.status.value, thesis.summary, _jsonb(thesis)),
            )
        return thesis

    def list_theses(self) -> list[ThesisMemo]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM core.theses ORDER BY symbol ASC").fetchall()
        return [ThesisMemo.model_validate(row["payload"]) for row in rows]

    def list_watchlist(self) -> list[WatchlistEntry]:
        instruments = {instrument.symbol: instrument for instrument in self.list_instruments()}
        theses = {thesis.symbol: thesis for thesis in self.list_theses()}
        return [
            WatchlistEntry(instrument=instrument, thesis=theses.get(symbol))
            for symbol, instrument in sorted(instruments.items())
        ]

    def save_proposal(self, proposal: TradeProposal) -> TradeProposal:
        now = datetime.now(tz=UTC)
        event = proposal_created_event(proposal)
        with self._connect() as connection:
            _upsert_proposal(connection, proposal, updated_at=now)
            _replace_proposal_targets(connection, proposal)
            _replace_proposal_orders(connection, proposal)
            _insert_platform_event(connection, event, created_at=now)
        return proposal

    def queue_proposal_once(self, proposal: TradeProposal) -> TradeProposal:
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("proposal:" + proposal.proposal_id,))
            row = connection.execute("SELECT payload FROM portfolio.proposals WHERE proposal_id = %s", (proposal.proposal_id,)).fetchone()
            if row is not None:
                return TradeProposal.model_validate(row["payload"])
            now = datetime.now(tz=UTC)
            _upsert_proposal(connection, proposal, updated_at=now)
            _replace_proposal_targets(connection, proposal)
            _replace_proposal_orders(connection, proposal)
            _insert_platform_event(connection, proposal_created_event(proposal), created_at=now)
        return proposal

    def get_proposal(self, proposal_id: str) -> TradeProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM portfolio.proposals WHERE proposal_id = %s",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return TradeProposal.model_validate(row["payload"])

    def list_proposals(self, status: ProposalStatus | None = None) -> list[TradeProposal]:
        query = "SELECT payload FROM portfolio.proposals"
        params: list[Any] = []
        if status is not None:
            query += " WHERE status = %s"
            params.append(status.value)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [TradeProposal.model_validate(row["payload"]) for row in rows]

    def apply_decision(self, decision: ApprovalDecision, *, expected_status: ProposalStatus | None = None) -> TradeProposal:
        now = datetime.now(tz=UTC)
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM portfolio.proposals WHERE proposal_id = %s FOR UPDATE", (decision.proposal_id,)).fetchone()
            if row is None:
                raise KeyError(decision.proposal_id)
            proposal = TradeProposal.model_validate(row['payload'])
            if expected_status is not None and proposal.status != expected_status:
                raise ValueError("Proposal changed before its approval could be recorded.")
            updated = proposal.model_copy(update={"status": decision.status})
            event = proposal_decision_event(updated, decision)
            _insert_platform_event(connection, event, created_at=now)
            connection.execute(
                """
                INSERT INTO portfolio.approval_decisions(
                    proposal_id,
                    status,
                    decided_at,
                    comment,
                    payload,
                    event_id,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT(event_id) DO NOTHING
                """,
                (
                    decision.proposal_id,
                    decision.status.value,
                    decision.decided_at,
                    decision.comment,
                    _jsonb(decision),
                    event.event_id,
                ),
            )
            _upsert_proposal(connection, updated, updated_at=now)
            _replace_proposal_targets(connection, updated)
            _replace_proposal_orders(connection, updated)
        return updated

    def save_broker_order_record(self, record: BrokerOrderRecord) -> BrokerOrderRecord:
        self._write_broker_order_record(record)
        return record

    def apply_broker_execution_fills(
        self, local_order_id: str, fills: list[BrokerExecutionFill],
    ) -> BrokerOrderRecord:
        with self._connect() as connection:
            _lock_execution_ledger(connection)
            row = connection.execute(
                "SELECT payload FROM execution.broker_orders WHERE local_order_id = %s FOR UPDATE", (local_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(local_order_id)
            record = BrokerOrderRecord.model_validate(row["payload"])
            updated = merge_execution_fills(record, fills)
            if updated != record:
                self._write_broker_order_record(updated, connection=connection)
            return updated

    def update_order_management(self, local_order_id: str, transform) -> BrokerOrderRecord:
        """Serialize a lifecycle transition with fills and its outbox event."""
        with self._connect() as connection:
            _lock_execution_ledger(connection)
            row = connection.execute(
                "SELECT payload FROM execution.broker_orders WHERE local_order_id = %s FOR UPDATE", (local_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(local_order_id)
            record = BrokerOrderRecord.model_validate(row["payload"])
            updated = transform(record)
            self._write_broker_order_record(updated, connection=connection)
            return updated

    def recover_broker_executions(
        self, request: ExecutionRecoveryRequest, *, review_token: str,
    ) -> BrokerOrderRecord:
        with self._connect() as connection:
            _lock_execution_ledger(connection)
            row = connection.execute(
                "SELECT payload FROM execution.broker_orders WHERE local_order_id = %s FOR UPDATE", (request.local_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(request.local_order_id)
            record = BrokerOrderRecord.model_validate(row["payload"])
            baseline_row = connection.execute(
                "SELECT payload FROM portfolio.pnl_baselines ORDER BY cutoff_at DESC, created_at DESC LIMIT 1",
            ).fetchone()
            baseline = PnLBaseline.model_validate(baseline_row["payload"]) if baseline_row else None
            recovered = recover_execution_record(record, request, baseline, review_token=review_token)
            self._write_broker_order_record(recovered, connection=connection, recovery=True)
            return recovered

    def reserve_broker_order_record(self, record: BrokerOrderRecord, *, allow_resubmit: bool = False) -> bool:
        return self._write_broker_order_record(record, reserve=True, allow_resubmit=allow_resubmit)

    def _write_broker_order_record(
        self, record: BrokerOrderRecord, *, reserve: bool = False, allow_resubmit: bool = False,
        connection: psycopg.Connection | None = None, recovery: bool = False,
    ) -> bool:
        now = datetime.now(tz=UTC)
        with self._connect() if connection is None else nullcontext(connection) as connection:
            _lock_execution_ledger(connection)
            if reserve:
                # Transaction-scoped lock also serializes claims from other processes.
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"order-intent:{record.proposal_id}:{record.order_index}",),
                )
                rows = connection.execute(
                    "SELECT payload FROM execution.broker_orders WHERE proposal_id = %s AND order_index = %s",
                    (record.proposal_id, record.order_index),
                ).fetchall()
                for row in rows:
                    existing = BrokerOrderRecord.model_validate(row["payload"])
                    if (not allow_resubmit or existing.status.value not in {"rejected", "cancelled"}
                            or existing.filled_quantity > 0 or existing.pending_action
                        or existing.broker_observation and str(existing.broker_observation.get("filled", "unknown")) not in {"0", "0.0"}):
                        return False
            prior = connection.execute(
                "SELECT payload FROM execution.broker_orders WHERE local_order_id = %s FOR UPDATE", (record.local_order_id,),
            ).fetchone()
            if prior is not None and not recovery:
                record = preserve_execution_evidence(BrokerOrderRecord.model_validate(prior["payload"]), record)
            order_event = order_status_changed_event(record)
            fill_event = fill_recorded_event(record)
            if prior is not None:
                previous_record = BrokerOrderRecord.model_validate(prior["payload"])
                if (previous_record.filled_quantity == record.filled_quantity
                        and previous_record.average_fill_price == record.average_fill_price
                        and previous_record.execution_fills == record.execution_fills):
                    fill_event = None

            connection.execute(
                """
                INSERT INTO execution.broker_orders(
                    local_order_id,
                    proposal_id,
                    order_index,
                    environment,
                    broker,
                    broker_order_id,
                    order_ref,
                    symbol,
                    side,
                    order_type,
                    quantity,
                    status,
                    submitted_at,
                    updated_at,
                    filled_quantity,
                    remaining_quantity,
                    average_fill_price,
                    message,
                    payload,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
                )
                ON CONFLICT(local_order_id) DO UPDATE SET
                    broker_order_id = excluded.broker_order_id,
                    status = excluded.status,
                    quantity = excluded.quantity,
                    submitted_at = COALESCE(excluded.submitted_at, execution.broker_orders.submitted_at),
                    updated_at = excluded.updated_at,
                    filled_quantity = excluded.filled_quantity,
                    remaining_quantity = excluded.remaining_quantity,
                    average_fill_price = excluded.average_fill_price,
                    message = excluded.message,
                    payload = excluded.payload
                """,
                (
                    record.local_order_id,
                    record.proposal_id,
                    record.order_index,
                    record.environment.value,
                    record.broker,
                    record.broker_order_id,
                    record.order_ref,
                    record.order.symbol,
                    record.order.side.value,
                    record.order.order_type.value,
                    Decimal(record.order.quantity),
                    record.status.value,
                    record.submitted_at,
                    record.updated_at,
                    Decimal(record.filled_quantity),
                    Decimal(record.remaining_quantity) if record.remaining_quantity is not None else None,
                    record.average_fill_price,
                    record.message,
                    _jsonb(record),
                ),
            )
            _insert_platform_event(connection, order_event, created_at=now)
            connection.execute(
                """
                INSERT INTO execution.broker_order_status_history(
                    status_event_id,
                    local_order_id,
                    status,
                    broker_order_id,
                    message,
                    observed_at,
                    payload,
                    event_id,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT(status_event_id) DO NOTHING
                """,
                (
                    order_event.event_id,
                    record.local_order_id,
                    record.status.value,
                    record.broker_order_id,
                    record.message,
                    record.updated_at,
                    _jsonb(record),
                    order_event.event_id,
                ),
            )
            if fill_event is not None:
                _insert_platform_event(connection, fill_event, created_at=now)
                connection.execute(
                    """
                    INSERT INTO execution.fills(
                        fill_id,
                        local_order_id,
                        proposal_id,
                        environment,
                        broker,
                        broker_order_id,
                        order_ref,
                        symbol,
                        side,
                        quantity,
                        average_price,
                        currency,
                        filled_at,
                        payload,
                        event_id,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT(fill_id) DO NOTHING
                    """,
                    (
                        fill_event.event_id,
                        record.local_order_id,
                        record.proposal_id,
                        record.environment.value,
                        record.broker,
                        record.broker_order_id,
                        record.order_ref,
                        record.order.symbol,
                        record.order.side.value,
                        Decimal(record.filled_quantity),
                        record.average_fill_price,
                        record.order.currency.value,
                        record.updated_at,
                        _jsonb(fill_event.payload),
                        fill_event.event_id,
                    ),
                )
        return True

    def save_broker_order_records(self, records: list[BrokerOrderRecord]) -> list[BrokerOrderRecord]:
        for record in records:
            self.save_broker_order_record(record)
        return records

    def list_broker_order_records(self, proposal_id: str | None = None) -> list[BrokerOrderRecord]:
        query = "SELECT payload FROM execution.broker_orders"
        params: list[Any] = []
        if proposal_id is not None:
            query += " WHERE proposal_id = %s"
            params.append(proposal_id)
        query += " ORDER BY proposal_id ASC, order_index ASC, local_order_id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [BrokerOrderRecord.model_validate(row["payload"]) for row in rows]

    def save_pnl_snapshot(self, snapshot: PnLSnapshot) -> PnLSnapshot:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO portfolio.pnl_snapshots(
                    snapshot_id,
                    as_of,
                    source,
                    baseline_id,
                    total_pnl_cnh,
                    payload,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    as_of = excluded.as_of,
                    source = excluded.source,
                    baseline_id = excluded.baseline_id,
                    total_pnl_cnh = excluded.total_pnl_cnh,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.as_of,
                    snapshot.source,
                    snapshot.baseline_id,
                    snapshot.total_pnl_cnh,
                    _jsonb(snapshot),
                    snapshot.created_at,
                ),
            )
        return snapshot

    def list_pnl_snapshots(self, *, limit: int = 100) -> list[PnLSnapshot]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM portfolio.pnl_snapshots
                ORDER BY as_of DESC, created_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [PnLSnapshot.model_validate(row["payload"]) for row in rows]

    def save_pnl_baseline(self, baseline: PnLBaseline) -> PnLBaseline:
        with self._connect() as connection:
            _lock_execution_ledger(connection)
            if baseline.execution_state_token is not None:
                rows = connection.execute("SELECT payload FROM execution.broker_orders").fetchall()
                records = [BrokerOrderRecord.model_validate(row["payload"]) for row in rows]
                prior = connection.execute(
                    "SELECT payload FROM portfolio.pnl_baselines ORDER BY cutoff_at DESC, created_at DESC LIMIT 1",
                ).fetchone()
                previous = PnLBaseline.model_validate(prior["payload"]) if prior else None
                validate_baseline_state(baseline, records, previous)
            connection.execute(
                """
                INSERT INTO portfolio.pnl_baselines(
                    baseline_id,
                    cutoff_at,
                    source,
                    realized_pnl_cnh,
                    payload,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(baseline_id) DO UPDATE SET
                    cutoff_at = excluded.cutoff_at,
                    source = excluded.source,
                    realized_pnl_cnh = excluded.realized_pnl_cnh,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (
                    baseline.baseline_id,
                    baseline.cutoff_at,
                    baseline.source,
                    baseline.realized_pnl_cnh,
                    _jsonb(baseline),
                    baseline.created_at,
                ),
            )
        return baseline

    def latest_pnl_baseline(self) -> PnLBaseline | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM portfolio.pnl_baselines
                ORDER BY cutoff_at DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return PnLBaseline.model_validate(row["payload"])

    def upsert_price_bar(self, symbol: str, bar: PriceBar) -> PriceBar:
        raise _market_data_not_in_postgres("price bars")

    def list_price_bars(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PriceBar]:
        raise _market_data_not_in_postgres("price bars")

    def upsert_fx_rate(self, rate: FXRate) -> FXRate:
        raise _market_data_not_in_postgres("FX rates")

    def list_fx_rates(
        self,
        base_currency: Currency,
        *,
        quote_currency: Currency = Currency.CNH,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[FXRate]:
        raise _market_data_not_in_postgres("FX rates")

    def upsert_fundamental_snapshot(self, snapshot: FundamentalSnapshot) -> FundamentalSnapshot:
        now = datetime.now(tz=UTC)
        symbol = snapshot.symbol.upper()
        normalized = snapshot.model_copy(update={"symbol": symbol})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO core.fundamental_snapshots(
                    symbol,
                    period_end,
                    available_date,
                    filing_date,
                    source,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now(), %s)
                ON CONFLICT(symbol, period_end, available_date) DO UPDATE SET
                    filing_date = excluded.filing_date,
                    source = excluded.source,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized.symbol,
                    normalized.period_end,
                    normalized.available_date,
                    normalized.filing_date,
                    normalized.source,
                    _jsonb(normalized),
                    now,
                ),
            )
        return normalized

    def list_fundamental_snapshots(
        self,
        symbol: str,
        *,
        start_available_date: date | None = None,
        end_available_date: date | None = None,
    ) -> list[FundamentalSnapshot]:
        query = "SELECT payload FROM core.fundamental_snapshots WHERE symbol = %s"
        params: list[Any] = [symbol.upper()]
        if start_available_date is not None:
            query += " AND available_date >= %s"
            params.append(start_available_date)
        if end_available_date is not None:
            query += " AND available_date <= %s"
            params.append(end_available_date)
        query += " ORDER BY available_date ASC, period_end ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [FundamentalSnapshot.model_validate(row["payload"]) for row in rows]

    def latest_fundamental_snapshot(self, symbol: str, *, as_of: date) -> FundamentalSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM core.fundamental_snapshots
                WHERE symbol = %s AND available_date <= %s
                ORDER BY available_date DESC, period_end DESC
                LIMIT 1
                """,
                (symbol.upper(), as_of),
            ).fetchone()
        if row is None:
            return None
        return FundamentalSnapshot.model_validate(row["payload"])

    def append_platform_event(self, event: AnyPlatformEvent) -> PlatformEventOutboxRecord:
        now = datetime.now(tz=UTC)
        with self._connect() as connection:
            _insert_platform_event(connection, event, created_at=now)
        record = self.get_platform_event_outbox_record(event.event_id)
        if record is None:
            raise RuntimeError(f"failed to append platform event {event.event_id}")
        return record

    def get_platform_event_outbox_record(self, event_id: str) -> PlatformEventOutboxRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events.platform_event_outbox WHERE event_id = %s",
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return _event_outbox_record_from_row(row)

    def list_pending_platform_events(self, *, limit: int = 100) -> list[PlatformEventOutboxRecord]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM events.platform_event_outbox
                WHERE published_at IS NULL
                ORDER BY created_at ASC, event_id ASC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_event_outbox_record_from_row(row) for row in rows]

    def list_platform_event_outbox_records(
        self,
        *,
        limit: int = 1000,
        published: bool | None = None,
        event_type: PlatformEventType | None = None,
    ) -> list[PlatformEventOutboxRecord]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query = "SELECT * FROM events.platform_event_outbox"
        clauses: list[str] = []
        params: list[Any] = []
        if published is True:
            clauses.append("published_at IS NOT NULL")
        elif published is False:
            clauses.append("published_at IS NULL")
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(event_type.value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC, event_id ASC LIMIT %s"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_event_outbox_record_from_row(row) for row in rows]

    def mark_platform_event_published(
        self,
        event_id: str,
        *,
        published_at: datetime | None = None,
    ) -> PlatformEventOutboxRecord | None:
        resolved_published_at = _datetime_to_utc(published_at or datetime.now(tz=UTC))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE events.platform_event_outbox
                SET
                    published_at = COALESCE(published_at, %s),
                    publish_attempts = CASE
                        WHEN published_at IS NULL THEN publish_attempts + 1
                        ELSE publish_attempts
                    END,
                    last_error = NULL
                WHERE event_id = %s
                """,
                (resolved_published_at, event_id),
            )
        return self.get_platform_event_outbox_record(event_id)

    def record_platform_event_publish_failure(
        self,
        event_id: str,
        error: str,
    ) -> PlatformEventOutboxRecord | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE events.platform_event_outbox
                SET
                    publish_attempts = publish_attempts + 1,
                    last_error = %s
                WHERE event_id = %s AND published_at IS NULL
                """,
                (error, event_id),
            )
        return self.get_platform_event_outbox_record(event_id)

    def _connect(self) -> psycopg.Connection:
        kwargs: dict[str, Any] = {
            "host": self.config.host,
            "port": self.config.port,
            "dbname": self.config.database,
            "user": self.config.user,
            "sslmode": self.config.sslmode,
            "application_name": self.config.application_name,
            "options": "-c timezone=UTC",
            "row_factory": dict_row,
        }
        if self.config.password:
            kwargs["password"] = self.config.password
        return psycopg.connect(**kwargs)


def _upsert_proposal(connection: psycopg.Connection, proposal: TradeProposal, *, updated_at: datetime) -> None:
    environment = proposal_environment(proposal)
    connection.execute(
        """
        INSERT INTO portfolio.proposals(
            proposal_id,
            status,
            environment,
            sleeve,
            as_of,
            intended_trade_date,
            base_currency,
            summary,
            payload,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(proposal_id) DO UPDATE SET
            status = excluded.status,
            environment = excluded.environment,
            sleeve = excluded.sleeve,
            as_of = excluded.as_of,
            intended_trade_date = excluded.intended_trade_date,
            base_currency = excluded.base_currency,
            summary = excluded.summary,
            payload = excluded.payload,
            updated_at = excluded.updated_at
        """,
        (
            proposal.proposal_id,
            proposal.status.value,
            environment.value if environment is not None else "mixed",
            proposal.sleeve,
            proposal.as_of,
            proposal.intended_trade_date,
            proposal.base_currency.value,
            proposal.summary,
            _jsonb(proposal),
            proposal.created_at,
            updated_at,
        ),
    )


def _replace_proposal_targets(connection: psycopg.Connection, proposal: TradeProposal) -> None:
    connection.execute("DELETE FROM portfolio.proposal_targets WHERE proposal_id = %s", (proposal.proposal_id,))
    for target in proposal.targets:
        connection.execute(
            """
            INSERT INTO portfolio.proposal_targets(proposal_id, symbol, target_weight, sleeve, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                proposal.proposal_id,
                target.symbol,
                target.target_weight,
                target.sleeve,
                _jsonb(target),
            ),
        )


def _replace_proposal_orders(connection: psycopg.Connection, proposal: TradeProposal) -> None:
    connection.execute("DELETE FROM portfolio.proposal_orders WHERE proposal_id = %s", (proposal.proposal_id,))
    for order_index, order in enumerate(proposal.orders):
        connection.execute(
            """
            INSERT INTO portfolio.proposal_orders(
                proposal_id,
                order_index,
                symbol,
                side,
                order_type,
                quantity,
                reference_price,
                currency,
                environment,
                notional_cnh,
                intended_trade_date,
                payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                proposal.proposal_id,
                order_index,
                order.symbol,
                order.side.value,
                order.order_type.value,
                Decimal(order.quantity),
                order.reference_price,
                order.currency.value,
                order.environment.value,
                order.notional_cnh,
                order.intended_trade_date,
                _jsonb(order),
            ),
        )


def _insert_platform_event(
    connection: psycopg.Connection,
    event: AnyPlatformEvent,
    *,
    created_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO events.platform_event_outbox(
            event_id,
            event_type,
            schema_version,
            subject,
            payload,
            occurred_at,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(event_id) DO NOTHING
        """,
        (
            event.event_id,
            event.event_type.value,
            event.schema_version,
            event.subject,
            _jsonb(event),
            event.occurred_at,
            created_at,
        ),
    )


def _event_outbox_record_from_row(row: dict[str, Any]) -> PlatformEventOutboxRecord:
    return PlatformEventOutboxRecord(
        event_id=row["event_id"],
        event_type=PlatformEventType(row["event_type"]),
        subject=row["subject"],
        payload=decode_platform_event(row["payload"]),
        occurred_at=_datetime_to_utc(row["occurred_at"]),
        created_at=_datetime_to_utc(row["created_at"]),
        published_at=_datetime_to_utc(row["published_at"]) if row["published_at"] is not None else None,
        publish_attempts=row["publish_attempts"],
        last_error=row["last_error"],
    )


def _jsonb(model: object) -> Jsonb:
    return Jsonb(model.model_dump(mode="json"))


def _market_data_not_in_postgres(kind: str) -> RuntimeError:
    return RuntimeError(
        f"PostgresStore does not persist {kind}. "
        "Use create_trading_store with ST_MARKET_DATA_STORE_BACKEND=clickhouse so market data stays in ClickHouse."
    )


def _datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event outbox timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _lock_execution_ledger(connection: psycopg.Connection) -> None:
    # Shared with baseline writes and recovery: local paper order traffic is low,
    # and correctness across order/baseline snapshots takes priority over parallel writes.
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("execution-ledger",))
