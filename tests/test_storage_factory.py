import pytest

from systematic_trading.config import AppSettings
from systematic_trading.market_data import ClickHouseMarketDataStore
from systematic_trading.storage import PostgresStore, SQLiteStore, TradingStore, create_trading_store, create_transactional_store
from systematic_trading.storage.routed import MarketDataRoutedTradingStore


def test_transactional_store_factory_returns_sqlite_store_by_default(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "factory.db")

    store = create_transactional_store(settings)

    assert isinstance(store, SQLiteStore)
    assert isinstance(store, TradingStore)
    assert store.database_path == tmp_path / "factory.db"


def test_transactional_store_factory_accepts_explicit_database_path(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "settings.db")

    store = create_transactional_store(settings, database_path=tmp_path / "override.db")

    assert isinstance(store, SQLiteStore)
    assert store.database_path == tmp_path / "override.db"


def test_transactional_store_factory_returns_postgres_store_when_configured(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="postgres",
        postgres_app_password="secret",
    )

    store = create_transactional_store(settings)

    assert isinstance(store, PostgresStore)
    assert isinstance(store, TradingStore)
    assert store.config.database == "systematic_trading"
    assert store.config.user == "st_app"
    assert store.config.password == "secret"


def test_transactional_store_factory_rejects_unsupported_backend(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="mysql",
    )

    with pytest.raises(ValueError, match="Unsupported transactional store backend 'mysql'"):
        create_transactional_store(settings)


def test_transactional_store_factory_normalizes_supported_backend(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="SQLite",
    )

    store = create_transactional_store(settings)

    assert isinstance(store, SQLiteStore)


def test_trading_store_factory_routes_market_data_to_clickhouse_when_configured(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        market_data_store_backend="clickhouse",
    )

    store = create_trading_store(settings)

    assert isinstance(store, MarketDataRoutedTradingStore)
    assert isinstance(store.transactional_store, SQLiteStore)
    assert isinstance(store.market_data_store, ClickHouseMarketDataStore)


def test_trading_store_factory_routes_clickhouse_over_postgres_transactional_store(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="postgres",
        market_data_store_backend="clickhouse",
        postgres_app_password="secret",
    )

    store = create_trading_store(settings)

    assert isinstance(store, MarketDataRoutedTradingStore)
    assert isinstance(store.transactional_store, PostgresStore)
    assert isinstance(store.market_data_store, ClickHouseMarketDataStore)
