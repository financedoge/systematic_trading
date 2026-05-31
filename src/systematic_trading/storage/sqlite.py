from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path

from systematic_trading.domain import (
    ApprovalDecision,
    BrokerOrderRecord,
    Currency,
    FXRate,
    FundamentalSnapshot,
    Instrument,
    PnLBaseline,
    PnLSnapshot,
    PriceBar,
    ProposalStatus,
    ThesisMemo,
    TradeProposal,
    WatchlistEntry,
)


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
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as connection:
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
        return record

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
                    datetime.now(tz=UTC).isoformat(),
                    updated.proposal_id,
                ),
            )
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump(model: object) -> str:
        return json.dumps(model.model_dump(mode="json"), separators=(",", ":"))
