from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Mapping, Sequence

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, PriceBar


class DataSourceType(StrEnum):
    MARKET_DATA = "market_data"
    FX = "fx"
    FILINGS = "filings"
    MACRO = "macro"
    BROKER = "broker"


class ProviderCapability(StrEnum):
    DAILY_BARS = "daily_bars"
    CORPORATE_ACTIONS = "corporate_actions"
    FX_RATES = "fx_rates"
    FILINGS = "filings"
    MACRO_SERIES = "macro_series"
    ACCOUNT_STATE = "account_state"
    ORDER_ROUTING = "order_routing"


class DataSourceManifest(BaseModel):
    source_id: str
    name: str
    source_type: DataSourceType
    regions: list[str] = Field(default_factory=list)
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    configured: bool = False
    primary: bool = False
    notes: str | None = None


class MarketDataProvider(ABC):
    manifest: DataSourceManifest

    @abstractmethod
    def fetch_daily_bars(self, symbols: Sequence[str], start_date: date, end_date: date) -> Mapping[str, list[PriceBar]]:
        raise NotImplementedError


class FxProvider(ABC):
    manifest: DataSourceManifest

    @abstractmethod
    def fetch_fx_to_cnh(self, currencies: Sequence[Currency], as_of: date) -> list[FXRate]:
        raise NotImplementedError


class FilingProvider(ABC):
    manifest: DataSourceManifest

    @abstractmethod
    def fetch_filings(self, symbol: str, limit: int = 10) -> list[dict[str, str | Decimal]]:
        raise NotImplementedError


class ProviderRegistry:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def manifests(self) -> list[DataSourceManifest]:
        primary_eod_name = self.settings.primary_eod_provider if self.settings.primary_eod_provider != "UNSET" else "Primary EOD Vendor"
        primary_eod_configured = self.settings.primary_eod_provider != "UNSET" and bool(self.settings.primary_eod_api_key)

        manifests = [
            DataSourceManifest(
                source_id="primary-eod",
                name=primary_eod_name,
                source_type=DataSourceType.MARKET_DATA,
                regions=["US", "Europe", "HK", "Japan", "Korea"],
                capabilities=[ProviderCapability.DAILY_BARS, ProviderCapability.CORPORATE_ACTIONS],
                configured=primary_eod_configured,
                primary=True,
                notes="Configure a paid global EOD vendor to make this the source of record.",
            ),
            DataSourceManifest(
                source_id="interactive-brokers",
                name="Interactive Brokers",
                source_type=DataSourceType.BROKER,
                regions=["US", "Europe", "HK", "Japan", "Korea"],
                capabilities=[ProviderCapability.ACCOUNT_STATE, ProviderCapability.ORDER_ROUTING, ProviderCapability.DAILY_BARS],
                configured=True,
                notes="Used for paper and live execution plus account state, not as the long-term historical source of record.",
            ),
            DataSourceManifest(
                source_id="sec-edgar",
                name="SEC EDGAR",
                source_type=DataSourceType.FILINGS,
                regions=["US"],
                capabilities=[ProviderCapability.FILINGS],
                configured=True,
                notes="Free filings and XBRL data for US issuers.",
            ),
            DataSourceManifest(
                source_id="edinet",
                name="EDINET",
                source_type=DataSourceType.FILINGS,
                regions=["Japan"],
                capabilities=[ProviderCapability.FILINGS],
                configured=True,
                notes="Japanese issuer filings and disclosures.",
            ),
            DataSourceManifest(
                source_id="dart",
                name="DART",
                source_type=DataSourceType.FILINGS,
                regions=["Korea"],
                capabilities=[ProviderCapability.FILINGS],
                configured=True,
                notes="Korean issuer filings and disclosures.",
            ),
            DataSourceManifest(
                source_id="hkex-filings",
                name="HKEX Issuer Filings",
                source_type=DataSourceType.FILINGS,
                regions=["HK"],
                capabilities=[ProviderCapability.FILINGS],
                configured=True,
                notes="Hong Kong issuer disclosures and announcements.",
            ),
            DataSourceManifest(
                source_id="fred",
                name="FRED",
                source_type=DataSourceType.MACRO,
                regions=["US", "Global"],
                capabilities=[ProviderCapability.MACRO_SERIES],
                configured=True,
                notes="Free macroeconomic series for context and overlays.",
            ),
            DataSourceManifest(
                source_id="oecd",
                name="OECD API",
                source_type=DataSourceType.MACRO,
                regions=["Europe", "Japan", "Korea", "Global"],
                capabilities=[ProviderCapability.MACRO_SERIES],
                configured=True,
                notes="Cross-country macro series useful for valuation context and overlays.",
            ),
        ]
        return manifests
