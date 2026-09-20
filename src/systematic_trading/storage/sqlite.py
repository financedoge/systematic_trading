from __future__ import annotations

import json
import sqlite3
from contextlib import nullcontext
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path

from systematic_trading.domain import (
    ApprovalDecision,
    BrokerOrderRecord,
    BrokerExecutionFill,
    Currency,
    FXRate,
    FundamentalSnapshot,
    Instrument,
    AnyPlatformEvent,
    PnLBaseline,
    PnLSnapshot,
    PlatformEventOutboxRecord,
    PlatformEventType,
    PriceBar,
    ProposalStatus,
    ThesisMemo,
    TradeProposal,
    WatchlistEntry,
    decode_platform_event,
)
from systematic_trading.storage.event_builders import (
    fill_recorded_event as _fill_recorded_event,
    order_status_changed_event as _order_status_changed_event,
    proposal_created_event as _proposal_created_event,
    proposal_decision_event as _proposal_decision_event,
)
from systematic_trading.execution.fills import merge_execution_fills, preserve_execution_evidence, validate_baseline_state
from systematic_trading.execution.recovery import ExecutionRecoveryRequest, recover_execution_record


class SQLiteStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS instruments (
                    symbol TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS theses (
                    symbol TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approval_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
                );

                CREATE TABLE IF NOT EXISTS price_bars (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS fx_rates (
                    base_currency TEXT NOT NULL,
                    quote_currency TEXT NOT NULL,
                    rate_date TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (base_currency, quote_currency, rate_date)
                );

                CREATE TABLE IF NOT EXISTS fundamental_snapshots (
                    symbol TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    available_date TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, period_end, available_date)
                );

                CREATE INDEX IF NOT EXISTS idx_fundamental_snapshots_symbol_available
                    ON fundamental_snapshots(symbol, available_date);

                CREATE TABLE IF NOT EXISTS broker_order_records (
                    local_order_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    broker TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    broker_order_id INTEGER,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
                );

                CREATE INDEX IF NOT EXISTS idx_broker_order_records_proposal
                    ON broker_order_records(proposal_id);

                CREATE TABLE IF NOT EXISTS pnl_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_as_of
                    ON pnl_snapshots(as_of);

                CREATE TABLE IF NOT EXISTS pnl_baselines (
                    baseline_id TEXT PRIMARY KEY,
                    cutoff_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pnl_baselines_cutoff_at
                    ON pnl_baselines(cutoff_at);

                CREATE TABLE IF NOT EXISTS platform_event_outbox (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    publish_attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_pending
                    ON platform_event_outbox(published_at, created_at, event_id);

                CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_type
                    ON platform_event_outbox(event_type, occurred_at);
                """
            )

    def upsert_instrument(self, instrument: Instrument) -> Instrument:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO instruments(symbol, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (instrument.symbol, self._dump(instrument), now),
            )
        return instrument

    def list_instruments(self) -> list[Instrument]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM instruments ORDER BY symbol ASC").fetchall()
        return [Instrument.model_validate_json(row["payload"]) for row in rows]

    def upsert_thesis(self, thesis: ThesisMemo) -> ThesisMemo:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO theses(symbol, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (thesis.symbol, self._dump(thesis), now),
            )
        return thesis

    def list_theses(self) -> list[ThesisMemo]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM theses ORDER BY symbol ASC").fetchall()
        return [ThesisMemo.model_validate_json(row["payload"]) for row in rows]

    def list_watchlist(self) -> list[WatchlistEntry]:
        instruments = {instrument.symbol: instrument for instrument in self.list_instruments()}
        theses = {thesis.symbol: thesis for thesis in self.list_theses()}
        return [
            WatchlistEntry(instrument=instrument, thesis=theses.get(symbol))
            for symbol, instrument in sorted(instruments.items())
        ]

    def save_proposal(self, proposal: TradeProposal) -> TradeProposal:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO proposals(proposal_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    proposal.proposal_id,
                    proposal.status.value,
                    self._dump(proposal),
                    proposal.created_at.isoformat(),
                    now,
                ),
            )
            _insert_platform_event(connection, _proposal_created_event(proposal), created_at=now)
        return proposal

    def get_proposal(self, proposal_id: str) -> TradeProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return TradeProposal.model_validate_json(row["payload"])

    def list_proposals(self, status: ProposalStatus | None = None) -> list[TradeProposal]:
        query = "SELECT payload FROM proposals"
        params: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY created_at DESC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [TradeProposal.model_validate_json(row["payload"]) for row in rows]

    def save_broker_order_record(self, record: BrokerOrderRecord) -> BrokerOrderRecord:
        self._write_broker_order_record(record)
        return record

    def apply_broker_execution_fills(
        self, local_order_id: str, fills: list[BrokerExecutionFill],
    ) -> BrokerOrderRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM broker_order_records WHERE local_order_id = ?", (local_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(local_order_id)
            record = BrokerOrderRecord.model_validate_json(row["payload"])
            updated = merge_execution_fills(record, fills)
            if updated != record:
                self._write_broker_order_record(updated, connection=connection)
            return updated

    def recover_broker_executions(
        self, request: ExecutionRecoveryRequest, *, review_token: str,
    ) -> BrokerOrderRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM broker_order_records WHERE local_order_id = ?", (request.local_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(request.local_order_id)
            record = BrokerOrderRecord.model_validate_json(row["payload"])
            baseline_row = connection.execute(
                "SELECT payload FROM pnl_baselines ORDER BY cutoff_at DESC, created_at DESC LIMIT 1",
            ).fetchone()
            baseline = PnLBaseline.model_validate_json(baseline_row["payload"]) if baseline_row else None
            recovered = recover_execution_record(record, request, baseline, review_token=review_token)
            self._write_broker_order_record(recovered, connection=connection, recovery=True)
            return recovered

    def reserve_broker_order_record(self, record: BrokerOrderRecord, *, allow_resubmit: bool = False) -> bool:
        return self._write_broker_order_record(record, reserve=True, allow_resubmit=allow_resubmit)

    def _write_broker_order_record(
        self, record: BrokerOrderRecord, *, reserve: bool = False, allow_resubmit: bool = False,
        connection: sqlite3.Connection | None = None, recovery: bool = False,
    ) -> bool:
        now = datetime.now(tz=UTC).isoformat()
        own_connection = connection is None
        with self._connect() if own_connection else nullcontext(connection) as connection:
            if own_connection:
                connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT payload FROM broker_order_records WHERE local_order_id = ?", (record.local_order_id,),
            ).fetchone()
            if prior is not None and not recovery:
                record = preserve_execution_evidence(BrokerOrderRecord.model_validate_json(prior["payload"]), record)
            if reserve:
                rows = connection.execute(
                    "SELECT payload FROM broker_order_records WHERE proposal_id = ?",
                    (record.proposal_id,),
                ).fetchall()
                previous = [BrokerOrderRecord.model_validate_json(row["payload"]) for row in rows]
                for existing in previous:
                    if existing.order_index == record.order_index and (
                        not allow_resubmit or existing.status.value not in {"rejected", "cancelled"}
                        or existing.filled_quantity > 0
                    ):
                        return False
            connection.execute(
                """
                INSERT INTO broker_order_records(
                    local_order_id,
                    proposal_id,
                    broker,
                    environment,
                    broker_order_id,
                    status,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_order_id) DO UPDATE SET
                    broker_order_id=excluded.broker_order_id,
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    record.local_order_id,
                    record.proposal_id,
                    record.broker,
                    record.environment.value,
                    record.broker_order_id,
                    record.status.value,
                    self._dump(record),
                    record.submitted_at.isoformat() if record.submitted_at is not None else now,
                    now,
                ),
            )
            _insert_platform_event(connection, _order_status_changed_event(record), created_at=now)
            fill_event = _fill_recorded_event(record)
            if fill_event is not None:
                _insert_platform_event(connection, fill_event, created_at=now)
        return True

    def save_broker_order_records(self, records: list[BrokerOrderRecord]) -> list[BrokerOrderRecord]:
        for record in records:
            self.save_broker_order_record(record)
        return records

    def list_broker_order_records(self, proposal_id: str | None = None) -> list[BrokerOrderRecord]:
        query = "SELECT payload FROM broker_order_records"
        params: tuple[str, ...] = ()
        if proposal_id is not None:
            query += " WHERE proposal_id = ?"
            params = (proposal_id,)
        query += " ORDER BY created_at ASC, local_order_id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        records = [BrokerOrderRecord.model_validate_json(row["payload"]) for row in rows]
        return sorted(records, key=lambda record: (record.proposal_id, record.order_index, record.local_order_id))

    def save_pnl_snapshot(self, snapshot: PnLSnapshot) -> PnLSnapshot:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pnl_snapshots(snapshot_id, as_of, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    as_of=excluded.as_of,
                    payload=excluded.payload,
                    created_at=excluded.created_at
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.as_of.isoformat(),
                    self._dump(snapshot),
                    snapshot.created_at.isoformat(),
                ),
            )
        return snapshot

    def list_pnl_snapshots(self, *, limit: int = 100) -> list[PnLSnapshot]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM pnl_snapshots
                ORDER BY as_of DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [PnLSnapshot.model_validate_json(row["payload"]) for row in rows]

    def save_pnl_baseline(self, baseline: PnLBaseline) -> PnLBaseline:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if baseline.execution_state_token is not None:
                rows = connection.execute("SELECT payload FROM broker_order_records").fetchall()
                records = [BrokerOrderRecord.model_validate_json(row["payload"]) for row in rows]
                prior = connection.execute(
                    "SELECT payload FROM pnl_baselines ORDER BY cutoff_at DESC, created_at DESC LIMIT 1",
                ).fetchone()
                previous = PnLBaseline.model_validate_json(prior["payload"]) if prior else None
                validate_baseline_state(baseline, records, previous)
            connection.execute(
                """
                INSERT INTO pnl_baselines(baseline_id, cutoff_at, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(baseline_id) DO UPDATE SET
                    cutoff_at=excluded.cutoff_at,
                    payload=excluded.payload,
                    created_at=excluded.created_at
                """,
                (
                    baseline.baseline_id,
                    baseline.cutoff_at.isoformat(),
                    self._dump(baseline),
                    baseline.created_at.isoformat(),
                ),
            )
        return baseline

    def latest_pnl_baseline(self) -> PnLBaseline | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM pnl_baselines
                ORDER BY cutoff_at DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return PnLBaseline.model_validate_json(row["payload"])

    def apply_decision(self, decision: ApprovalDecision) -> TradeProposal:
        proposal = self.get_proposal(decision.proposal_id)
        if proposal is None:
            raise KeyError(decision.proposal_id)

        updated = proposal.model_copy(update={"status": decision.status})
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approval_decisions(proposal_id, status, payload, decided_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    decision.proposal_id,
                    decision.status.value,
                    self._dump(decision),
                    decision.decided_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE proposals
                SET status = ?, payload = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (
                    updated.status.value,
                    self._dump(updated),
                    now,
                    updated.proposal_id,
                ),
            )
            _insert_platform_event(connection, _proposal_decision_event(updated, decision), created_at=now)
        return updated

    def upsert_price_bar(self, symbol: str, bar: PriceBar) -> PriceBar:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO price_bars(symbol, trade_date, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (symbol, bar.trade_date.isoformat(), self._dump(bar), now),
            )
        return bar

    def list_price_bars(
        self,
        symbol: str,
        *,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[PriceBar]:
        query = "SELECT payload FROM price_bars WHERE symbol = ?"
        params: list[str] = [symbol]
        if start_date is not None:
            query += " AND trade_date >= ?"
            params.append(start_date.isoformat())
        if end_date is not None:
            query += " AND trade_date <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY trade_date ASC"

        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [PriceBar.model_validate_json(row["payload"]) for row in rows]

    def upsert_fx_rate(self, rate: FXRate) -> FXRate:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fx_rates(base_currency, quote_currency, rate_date, payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(base_currency, quote_currency, rate_date) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    rate.base_currency.value,
                    rate.quote_currency.value,
                    rate.rate_date.isoformat(),
                    self._dump(rate),
                    now,
                ),
            )
        return rate

    def list_fx_rates(
        self,
        base_currency: Currency,
        *,
        quote_currency: Currency = Currency.CNH,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[FXRate]:
        query = "SELECT payload FROM fx_rates WHERE base_currency = ? AND quote_currency = ?"
        params = [base_currency.value, quote_currency.value]
        if start_date is not None:
            query += " AND rate_date >= ?"
            params.append(start_date.isoformat())
        if end_date is not None:
            query += " AND rate_date <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY rate_date ASC"

        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [FXRate.model_validate_json(row["payload"]) for row in rows]

    def upsert_fundamental_snapshot(self, snapshot: FundamentalSnapshot) -> FundamentalSnapshot:
        now = datetime.now(tz=UTC).isoformat()
        symbol = snapshot.symbol.upper()
        normalized = snapshot.model_copy(update={"symbol": symbol})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fundamental_snapshots(symbol, period_end, available_date, payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol, period_end, available_date) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    normalized.symbol,
                    normalized.period_end.isoformat(),
                    normalized.available_date.isoformat(),
                    self._dump(normalized),
                    now,
                ),
            )
        return normalized

    def list_fundamental_snapshots(
        self,
        symbol: str,
        *,
        start_available_date: Date | None = None,
        end_available_date: Date | None = None,
    ) -> list[FundamentalSnapshot]:
        query = "SELECT payload FROM fundamental_snapshots WHERE symbol = ?"
        params: list[str] = [symbol.upper()]
        if start_available_date is not None:
            query += " AND available_date >= ?"
            params.append(start_available_date.isoformat())
        if end_available_date is not None:
            query += " AND available_date <= ?"
            params.append(end_available_date.isoformat())
        query += " ORDER BY available_date ASC, period_end ASC"

        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [FundamentalSnapshot.model_validate_json(row["payload"]) for row in rows]

    def latest_fundamental_snapshot(self, symbol: str, *, as_of: Date) -> FundamentalSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM fundamental_snapshots
                WHERE symbol = ? AND available_date <= ?
                ORDER BY available_date DESC, period_end DESC
                LIMIT 1
                """,
                (symbol.upper(), as_of.isoformat()),
            ).fetchone()
        if row is None:
            return None
        return FundamentalSnapshot.model_validate_json(row["payload"])

    def append_platform_event(self, event: AnyPlatformEvent) -> PlatformEventOutboxRecord:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
            _insert_platform_event(connection, event, created_at=now)
        record = self.get_platform_event_outbox_record(event.event_id)
        if record is None:
            raise RuntimeError(f"failed to append platform event {event.event_id}")
        return record

    def get_platform_event_outbox_record(self, event_id: str) -> PlatformEventOutboxRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM platform_event_outbox
                WHERE event_id = ?
                """,
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
                FROM platform_event_outbox
                WHERE published_at IS NULL
                ORDER BY created_at ASC, event_id ASC
                LIMIT ?
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
        query = "SELECT * FROM platform_event_outbox"
        clauses: list[str] = []
        params: list[str | int] = []
        if published is True:
            clauses.append("published_at IS NOT NULL")
        elif published is False:
            clauses.append("published_at IS NULL")
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type.value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC, event_id ASC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [_event_outbox_record_from_row(row) for row in rows]

    def mark_platform_event_published(
        self,
        event_id: str,
        *,
        published_at: datetime | None = None,
    ) -> PlatformEventOutboxRecord | None:
        resolved_published_at = _datetime_to_utc(published_at or datetime.now(tz=UTC)).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE platform_event_outbox
                SET
                    published_at = COALESCE(published_at, ?),
                    publish_attempts = CASE
                        WHEN published_at IS NULL THEN publish_attempts + 1
                        ELSE publish_attempts
                    END,
                    last_error = NULL
                WHERE event_id = ?
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
                UPDATE platform_event_outbox
                SET
                    publish_attempts = publish_attempts + 1,
                    last_error = ?
                WHERE event_id = ? AND published_at IS NULL
                """,
                (error, event_id),
            )
        return self.get_platform_event_outbox_record(event_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump(model: object) -> str:
        return _dump_model(model)


def _insert_platform_event(
    connection: sqlite3.Connection,
    event: AnyPlatformEvent,
    *,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO platform_event_outbox(
            event_id,
            event_type,
            subject,
            payload,
            occurred_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO NOTHING
        """,
        (
            event.event_id,
            event.event_type.value,
            event.subject,
            _dump_model(event),
            event.occurred_at.isoformat(),
            created_at,
        ),
    )


def _dump_model(model: object) -> str:
    return json.dumps(model.model_dump(mode="json"), separators=(",", ":"))


def _event_outbox_record_from_row(row: sqlite3.Row) -> PlatformEventOutboxRecord:
    return PlatformEventOutboxRecord(
        event_id=row["event_id"],
        event_type=PlatformEventType(row["event_type"]),
        subject=row["subject"],
        payload=decode_platform_event(row["payload"]),
        occurred_at=_datetime_from_iso(row["occurred_at"]),
        created_at=_datetime_from_iso(row["created_at"]),
        published_at=_datetime_from_iso(row["published_at"]) if row["published_at"] is not None else None,
        publish_attempts=row["publish_attempts"],
        last_error=row["last_error"],
    )


def _datetime_from_iso(value: str) -> datetime:
    return _datetime_to_utc(datetime.fromisoformat(value))


def _datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event outbox timestamps must be timezone-aware")
    return value.astimezone(UTC)
