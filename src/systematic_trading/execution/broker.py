from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.domain.execution import OrderRequest


class BrokerConnectionProfile(BaseModel):
    environment: OrderEnvironment
    host: str
    port: int
    client_id: int
    enabled: bool
    safeguards: list[str] = Field(default_factory=list)
    notes: str | None = None


class BrokerAdapter(ABC):
    @abstractmethod
    def connection_profiles(self) -> list[BrokerConnectionProfile]:
        raise NotImplementedError

    @abstractmethod
    def validate_orders(self, orders: list[OrderRequest]) -> list[str]:
        raise NotImplementedError


class InteractiveBrokersAdapter(BrokerAdapter):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def connection_profiles(self) -> list[BrokerConnectionProfile]:
        common_safeguards = [
            "Require explicit approval before submitting any order.",
            "Mirror broker state locally and reconcile positions and cash before routing.",
            "Reject stale-price and duplicate-order submissions.",
        ]
        return [
            BrokerConnectionProfile(
                environment=OrderEnvironment.PAPER,
                host=self.settings.ib_host,
                port=self.settings.ib_paper_port,
                client_id=self.settings.ib_client_id,
                enabled=True,
                safeguards=common_safeguards,
                notes="Default environment for v1 execution validation.",
            ),
            BrokerConnectionProfile(
                environment=OrderEnvironment.LIVE,
                host=self.settings.ib_host,
                port=self.settings.ib_live_port,
                client_id=self.settings.ib_client_id,
                enabled=False,
                safeguards=common_safeguards + ["Keep live trading disabled until paper reconciliation is stable for an extended period."],
                notes="Planned environment only. Live routing remains disabled in v1.",
            ),
        ]

    def validate_orders(self, orders: list[OrderRequest]) -> list[str]:
        issues: list[str] = []
        for order in orders:
            if order.environment == OrderEnvironment.LIVE:
                issues.append(f"{order.symbol}: live routing is disabled in v1.")
            if order.quantity <= 0:
                issues.append(f"{order.symbol}: quantity must be positive.")
        return issues
