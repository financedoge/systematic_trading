from datetime import date

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage.postgres import PostgresStore
from test_execution_recovery import isolated_postgres


def test_postgres_acquisition_batch_is_atomic_and_idempotent(isolated_postgres):
    from pathlib import Path
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from systematic_trading.storage.postgres import PostgresConnectionConfig
    from test_event_outbox import _market_event
    database = "recorder_" + uuid4().hex[:12]
    with psycopg.connect(**isolated_postgres, dbname="postgres", autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    with psycopg.connect(**isolated_postgres, dbname=database) as connection:
        connection.execute(Path("deploy/postgres/migrations/001_initial_transactional_store.sql").read_text())
    store = PostgresStore(PostgresConnectionConfig(database=database, **isolated_postgres))
    events = [_market_event(f"recorder-{i}", "SPY") for i in range(3)]
    store.append_platform_events(events)
    store.append_platform_events(events)
    assert len(store.list_pending_platform_events()) == 3
    with pytest.raises(AttributeError):
        store.append_platform_events([_market_event("rolled-back", "SPY"), object()])
    assert store.get_platform_event_outbox_record("rolled-back") is None


def test_postgres_store_from_settings_uses_legacy_local_password_alias() -> None:
    settings = AppSettings(
        postgres_app_password=None,
        app_postgre_db_password="legacy-secret",
    )

    store = PostgresStore.from_settings(settings)

    assert store.config.password == "legacy-secret"


def test_postgres_store_refuses_direct_price_bar_reads() -> None:
    store = PostgresStore.from_settings(AppSettings(postgres_app_password="secret"))

    with pytest.raises(RuntimeError, match="market data stays in ClickHouse"):
        store.list_price_bars("SPY", start_date=date(2026, 1, 1))
