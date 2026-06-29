import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage import SQLiteStore, TradingStore, create_transactional_store


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


def test_transactional_store_factory_rejects_unsupported_backend(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="postgres",
    )

    with pytest.raises(ValueError, match="Unsupported transactional store backend 'postgres'"):
        create_transactional_store(settings)


def test_transactional_store_factory_normalizes_supported_backend(tmp_path) -> None:
    settings = AppSettings(
        database_path=tmp_path / "factory.db",
        transactional_store_backend="SQLite",
    )

    store = create_transactional_store(settings)

    assert isinstance(store, SQLiteStore)
