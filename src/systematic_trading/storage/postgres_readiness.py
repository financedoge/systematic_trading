"""Bounded read-only startup probes, not a full database integrity check."""
from __future__ import annotations

import psycopg
from psycopg import sql

from systematic_trading.config import AppSettings
from systematic_trading.storage.postgres import PostgresStore


def probe_postgres_readiness(settings: AppSettings) -> dict:
    """Authenticate as the application and read catalogs and required stores.

    A listening socket, pg_isready, and SELECT 1 can all succeed while relation
    reads fail. Do not initialize schemas, repair data or alter server settings.
    Each statement and the connection attempt have a finite timeout.
    """
    config = PostgresStore.from_settings(settings).config
    relations = []
    if settings.transactional_store_backend.strip().lower() == "postgres":
        relations.extend([
            ("core", "instruments"),
            ("portfolio", "proposals"),
            ("portfolio", "strategy_control_state"),
            ("events", "platform_event_outbox"),
        ])
    if settings.market_data_store_backend.strip().lower() == "parquet":
        relations.extend([
            ("native_analytics", "publication_heads"),
            ("native_analytics", "publications"),
            ("native_analytics", "heads"),
            ("native_analytics", "datasets"),
        ])
    with psycopg.connect(
        host=config.host, port=config.port, dbname=config.database,
        user=config.user, password=config.password, sslmode=config.sslmode,
        application_name=f"{settings.app_name}-startup-probe", connect_timeout=5,
        options=("-c default_transaction_read_only=on -c statement_timeout=10000 "
                 "-c lock_timeout=3000 -c transaction_timeout=30000"),
    ) as connection:
        # Exercise the same catalog view required to establish retention pins.
        connection.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE data_type IN ('json','jsonb') "
            "AND table_schema IN ('core','events','execution','portfolio')"
        ).fetchone()
        for schema, table in relations:
            # Materialize a bounded row, including out-of-line payloads, while
            # returning only its size. Empty initialized tables are valid.
            connection.execute(sql.SQL(
                "SELECT octet_length(row_to_json(probe_row)::text) "
                "FROM (SELECT * FROM {}.{} LIMIT 1) AS probe_row"
            ).format(sql.Identifier(schema), sql.Identifier(table))).fetchone()
    return {
        "status": "ready", "host": config.host, "port": config.port,
        "database": config.database,
        "checked_relations": [f"{schema}.{table}" for schema, table in relations],
    }
