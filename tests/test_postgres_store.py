from datetime import date

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage.postgres import PostgresStore


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
