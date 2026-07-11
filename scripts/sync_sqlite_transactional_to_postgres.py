from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.domain import (  # noqa: E402
    ApprovalDecision,
    BrokerOrderRecord,
    FundamentalSnapshot,
    Instrument,
    PlatformEventType,
    PnLBaseline,
    PnLSnapshot,
    ThesisMemo,
    TradeProposal,
)
from systematic_trading.storage.postgres import PostgresStore  # noqa: E402
from systematic_trading.storage.event_builders import (  # noqa: E402
    fill_recorded_event,
    order_status_changed_event,
    proposal_created_event,
    proposal_decision_event,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy current SQLite transactional state into the Postgres transactional store."
    )
    parser.add_argument("--sqlite-database", type=Path, default=None, help="SQLite database to copy from.")
    args = parser.parse_args()

    settings = AppSettings()
    sqlite_database = args.sqlite_database or settings.database_path
    counts = sync_sqlite_transactional_state(sqlite_database=sqlite_database, settings=settings)
    for table, count in sorted(counts.items()):
        print(f"{table}={count}")
    return 0


def sync_sqlite_transactional_state(*, sqlite_database: Path, settings: AppSettings) -> Counter[str]:
    sqlite_database = Path(sqlite_database)
    if not sqlite_database.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_database}")

    postgres_store = PostgresStore.from_settings(settings)
    postgres_store.initialize()
    counts: Counter[str] = Counter()

    with sqlite3.connect(sqlite_database) as sqlite_connection:
        sqlite_connection.row_factory = sqlite3.Row

        source_event_ids = _sync_event_outbox(sqlite_connection, postgres_store)
        generated_event_ids: set[str] = set()
        counts["platform_event_outbox"] += len(source_event_ids)

        for row in _payload_rows(sqlite_connection, "instruments", "ORDER BY symbol ASC"):
            postgres_store.upsert_instrument(Instrument.model_validate_json(row["payload"]))
            counts["instruments"] += 1

        for row in _payload_rows(sqlite_connection, "theses", "ORDER BY symbol ASC"):
            postgres_store.upsert_thesis(ThesisMemo.model_validate_json(row["payload"]))
            counts["theses"] += 1

        for row in _payload_rows(sqlite_connection, "fundamental_snapshots", "ORDER BY available_date ASC"):
            postgres_store.upsert_fundamental_snapshot(FundamentalSnapshot.model_validate_json(row["payload"]))
            counts["fundamental_snapshots"] += 1

        for row in _payload_rows(sqlite_connection, "proposals", "ORDER BY created_at ASC, proposal_id ASC"):
            proposal = TradeProposal.model_validate_json(row["payload"])
            generated_event_ids.add(proposal_created_event(proposal).event_id)
            postgres_store.save_proposal(proposal)
            counts["proposals"] += 1

        for row in _payload_rows(sqlite_connection, "approval_decisions", "ORDER BY decided_at ASC, id ASC"):
            decision = ApprovalDecision.model_validate_json(row["payload"])
            updated_proposal = postgres_store.apply_decision(decision)
            generated_event_ids.add(proposal_decision_event(updated_proposal, decision).event_id)
            counts["approval_decisions"] += 1

        for row in _payload_rows(sqlite_connection, "broker_order_records", "ORDER BY created_at ASC, local_order_id ASC"):
            record = BrokerOrderRecord.model_validate_json(row["payload"])
            generated_event_ids.add(order_status_changed_event(record).event_id)
            fill_event = fill_recorded_event(record)
            if fill_event is not None:
                generated_event_ids.add(fill_event.event_id)
            postgres_store.save_broker_order_record(record)
            counts["broker_order_records"] += 1

        for row in _payload_rows(sqlite_connection, "pnl_baselines", "ORDER BY cutoff_at ASC, created_at ASC"):
            postgres_store.save_pnl_baseline(PnLBaseline.model_validate_json(row["payload"]))
            counts["pnl_baselines"] += 1

        for row in _payload_rows(sqlite_connection, "pnl_snapshots", "ORDER BY as_of ASC, created_at ASC"):
            postgres_store.save_pnl_snapshot(PnLSnapshot.model_validate_json(row["payload"]))
            counts["pnl_snapshots"] += 1

        counts["generated_events_deleted"] += _delete_generated_events(
            postgres_store,
            generated_event_ids=generated_event_ids,
            source_event_ids=source_event_ids,
        )

    return counts


def _sync_event_outbox(sqlite_connection: sqlite3.Connection, postgres_store: PostgresStore) -> set[str]:
    if not _table_exists(sqlite_connection, "platform_event_outbox"):
        return set()
    rows = sqlite_connection.execute(
        """
        SELECT
            event_id,
            event_type,
            subject,
            payload,
            occurred_at,
            created_at,
            published_at,
            publish_attempts,
            last_error
        FROM platform_event_outbox
        ORDER BY created_at ASC, event_id ASC
        """
    ).fetchall()
    source_event_ids: set[str] = set()
    with postgres_store._connect() as connection:
        for row in rows:
            source_event_ids.add(row["event_id"])
            payload = json.loads(row["payload"])
            schema_version = int(payload.get("schema_version", 1))
            connection.execute(
                """
                INSERT INTO events.platform_event_outbox(
                    event_id,
                    event_type,
                    schema_version,
                    subject,
                    payload,
                    occurred_at,
                    created_at,
                    published_at,
                    publish_attempts,
                    last_error
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(event_id) DO UPDATE SET
                    event_type = excluded.event_type,
                    schema_version = excluded.schema_version,
                    subject = excluded.subject,
                    payload = excluded.payload,
                    occurred_at = excluded.occurred_at,
                    created_at = excluded.created_at,
                    published_at = COALESCE(events.platform_event_outbox.published_at, excluded.published_at),
                    publish_attempts = GREATEST(
                        events.platform_event_outbox.publish_attempts,
                        excluded.publish_attempts
                    ),
                    last_error = excluded.last_error
                """,
                (
                    row["event_id"],
                    PlatformEventType(row["event_type"]).value,
                    schema_version,
                    row["subject"],
                    Jsonb(payload),
                    row["occurred_at"],
                    row["created_at"],
                    row["published_at"],
                    row["publish_attempts"],
                    row["last_error"],
                ),
            )
    return source_event_ids


def _delete_generated_events(
    postgres_store: PostgresStore,
    *,
    generated_event_ids: set[str],
    source_event_ids: set[str],
) -> int:
    ids_to_delete = sorted(generated_event_ids - source_event_ids)
    if not ids_to_delete:
        return 0
    with postgres_store._connect() as connection:
        row = connection.execute(
            "DELETE FROM events.platform_event_outbox WHERE event_id = ANY(%s) RETURNING event_id",
            (ids_to_delete,),
        ).fetchall()
    return len(row)


def _payload_rows(sqlite_connection: sqlite3.Connection, table_name: str, order_by: str) -> list[sqlite3.Row]:
    if not _table_exists(sqlite_connection, table_name):
        return []
    return sqlite_connection.execute(f"SELECT payload FROM {table_name} {order_by}").fetchall()


def _table_exists(sqlite_connection: sqlite3.Connection, table_name: str) -> bool:
    row = sqlite_connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


if __name__ == "__main__":
    raise SystemExit(main())
