from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from systematic_trading import __version__
from systematic_trading.config import AppSettings, get_settings
from systematic_trading.data.providers import ProviderRegistry
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.live import TradingManagementService
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.web.api import router
from systematic_trading.web.operator import router as operator_router


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    store = SQLiteStore(resolved_settings.database_path)
    provider_registry = ProviderRegistry(resolved_settings)
    broker = InteractiveBrokersAdapter(resolved_settings)
    trading_management_service = (
        TradingManagementService(settings=resolved_settings, store=store)
        if resolved_settings.automation_enabled
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.initialize()
        app.state.settings = resolved_settings
        app.state.store = store
        app.state.provider_registry = provider_registry
        app.state.broker = broker
        app.state.trading_management_service = trading_management_service
        if trading_management_service is not None:
            trading_management_service.start()
        yield
        if trading_management_service is not None:
            trading_management_service.stop()

    app = FastAPI(
        title="Systematic Trading",
        version=__version__,
        description="Operator-focused research, backtesting, and execution toolkit.",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(operator_router)
    app.include_router(router)
    return app


app = create_app()
