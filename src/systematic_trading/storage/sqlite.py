from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path

from systematic_trading.domain import (
    ApprovalDecision,
    Currency,
    FXRate,
    Instrument,
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump(model: object) -> str:
        return json.dumps(model.model_dump(mode="json"), separators=(",", ":"))
