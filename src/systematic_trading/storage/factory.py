from __future__ import annotations

from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.storage.interfaces import TransactionalStore
from systematic_trading.storage.sqlite import SQLiteStore

SUPPORTED_TRANSACTIONAL_STORE_BACKENDS = ("sqlite",)


def create_transactional_store(
    settings: AppSettings,
    *,
    backend: str | None = None,
    database_path: Path | None = None,
) -> TransactionalStore:
    resolved_backend = _normalize_backend(backend or settings.transactional_store_backend)
    if resolved_backend == "sqlite":
        return SQLiteStore(database_path or settings.database_path)
    raise ValueError(
        f"Unsupported transactional store backend '{resolved_backend}'. "
        f"Supported backends: {', '.join(SUPPORTED_TRANSACTIONAL_STORE_BACKENDS)}. "
        "Postgres is the target state, but its runtime adapter is not implemented yet."
    )


def _normalize_backend(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("Transactional store backend must not be empty.")
    return normalized
