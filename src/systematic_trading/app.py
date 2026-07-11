from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from systematic_trading import __version__
from systematic_trading.config import AppSettings, get_settings
from systematic_trading.data.providers import ProviderRegistry
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.live import TradingManagementService
from systematic_trading.services import (
    OperationalLogger,
    PlatformHealthState,
    ServiceRuntimeSnapshot,
    build_platform_health,
    default_operational_log_path,
)
from systematic_trading.storage import create_trading_store
from systematic_trading.web.api import router
from systematic_trading.web.market_data_audit import router as market_data_audit_router
from systematic_trading.web.operator import router as operator_router
from systematic_trading.web.platform_actions import router as platform_actions_router
from systematic_trading.web.platform import router as platform_router


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    store = create_trading_store(resolved_settings)
    provider_registry = ProviderRegistry(resolved_settings)
    broker = InteractiveBrokersAdapter(resolved_settings)
    operation_logger = OperationalLogger(
        path=default_operational_log_path(resolved_settings),
        service_id="operator_dashboard",
    )
    trading_management_service = (
        TradingManagementService(settings=resolved_settings, store=store)
        if resolved_settings.automation_enabled
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        operation_logger.info(
            "operator_lifespan_starting",
            message="Operator dashboard API lifespan starting.",
            automation_enabled=resolved_settings.automation_enabled,
            database_path=resolved_settings.database_path,
            data_dir=resolved_settings.data_dir,
            default_environment=resolved_settings.default_environment.value,
        )
        store.initialize()
        app.state.settings = resolved_settings
        app.state.store = store
        app.state.provider_registry = provider_registry
        app.state.broker = broker
        app.state.trading_management_service = trading_management_service
        if trading_management_service is not None:
            trading_management_service.start()
            operation_logger.info(
                "automation_loop_started",
                message="Trading management automation loop started.",
            )
        yield
        if trading_management_service is not None:
            trading_management_service.stop()
            operation_logger.info(
                "automation_loop_stopped",
                message="Trading management automation loop stopped.",
            )
        operation_logger.info(
            "operator_lifespan_stopped",
            message="Operator dashboard API lifespan stopped.",
        )

    app = FastAPI(
        title="Systematic Trading",
        version=__version__,
        description="Operator-focused research, backtesting, and execution toolkit.",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=PlatformHealthState)
    def health() -> PlatformHealthState:
        checked_at = datetime.now(tz=UTC)
        service_overrides = {
            "operator_dashboard": ServiceRuntimeSnapshot(
                running=True,
                heartbeat_at=checked_at,
                message="Operator dashboard API responded.",
            )
        }
        service = getattr(app.state, "trading_management_service", None)
        if service is not None:
            status = service.status()
            service_overrides["trading_management_loop"] = ServiceRuntimeSnapshot(
                running=status.running,
                started_at=status.started_at,
                heartbeat_at=status.heartbeat_at,
                last_error=status.last_error,
                message="Trading management loop status loaded from embedded worker.",
                details={
                    "pending_eod_date": status.pending_eod_date.isoformat() if status.pending_eod_date else None,
                    "pending_eod_count": len(status.pending_eod_dates),
                    "last_eod_date": status.last_eod_date.isoformat() if status.last_eod_date else None,
                    "ib_automation_consecutive_errors": status.ib_automation_consecutive_errors,
                    "ib_automation_circuit_open_until": status.ib_automation_circuit_open_until.isoformat()
                    if status.ib_automation_circuit_open_until
                    else None,
                },
            )
        return build_platform_health(
            settings=resolved_settings,
            service_overrides=service_overrides,
            now=checked_at,
        )

    app.include_router(operator_router)
    app.include_router(platform_router)
    app.include_router(router)
    app.include_router(market_data_audit_router)
    app.include_router(platform_actions_router)
    return app


app = create_app()
