from __future__ import annotations

from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.market_data import ClickHouseMarketDataStore
from systematic_trading.storage.interfaces import TransactionalStore
from systematic_trading.storage.postgres import PostgresStore
from systematic_trading.storage.routed import MarketDataRoutedTradingStore
from systematic_trading.storage.sqlite import SQLiteStore

SUPPORTED_TRANSACTIONAL_STORE_BACKENDS = ("sqlite", "postgres")
SUPPORTED_MARKET_DATA_STORE_BACKENDS = ("sqlite", "clickhouse")


def create_transactional_store(
    settings: AppSettings,
    *,
    backend: str | None = None,
    database_path: Path | None = None,
) -> TransactionalStore:
    resolved_backend = _normalize_backend(backend or settings.transactional_store_backend)
    if resolved_backend == "sqlite":
        return SQLiteStore(database_path or settings.database_path)
    if resolved_backend == "postgres":
        return PostgresStore.from_settings(settings)
    raise ValueError(
        f"Unsupported transactional store backend '{resolved_backend}'. "
        f"Supported backends: {', '.join(SUPPORTED_TRANSACTIONAL_STORE_BACKENDS)}."
    )


def create_trading_store(
    settings: AppSettings,
    *,
    transactional_backend: str | None = None,
    market_data_backend: str | None = None,
    database_path: Path | None = None,
) -> TransactionalStore:
    transactional_store = create_transactional_store(
        settings,
        backend=transactional_backend,
        database_path=database_path,
    )
    resolved_market_data_backend = _normalize_backend(market_data_backend or settings.market_data_store_backend)
    if resolved_market_data_backend == "sqlite":
        if isinstance(transactional_store, PostgresStore):
            raise ValueError("Postgres transactional storage requires market_data_store_backend='clickhouse'.")
        return transactional_store
    if resolved_market_data_backend == "clickhouse":
        return MarketDataRoutedTradingStore(
            transactional_store,
            ClickHouseMarketDataStore.from_settings(settings),
        )
    raise ValueError(
        f"Unsupported market data store backend '{resolved_market_data_backend}'. "
        f"Supported backends: {', '.join(SUPPORTED_MARKET_DATA_STORE_BACKENDS)}."
    )


def _normalize_backend(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("Transactional store backend must not be empty.")
    return normalized
