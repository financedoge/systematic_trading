from systematic_trading.data.providers import (
    DataSourceManifest,
    DataSourceType,
    FilingProvider,
    FxProvider,
    MarketDataProvider,
    ProviderCapability,
    ProviderRegistry,
)
from systematic_trading.data.sec_edgar import SecEdgarClient, company_facts_to_snapshots
from systematic_trading.data.tushare import TushareUsDailyProvider, read_tushare_token


def __getattr__(name):
    # Pure analytics must not load the broker/database adapters in offline workers.
    if name in {'IBHistoricalDataClient', 'IbApiHistoricalDataClient', 'IbHistoricalDailyBarProvider'}:
        from importlib import import_module
        value = getattr(import_module('systematic_trading.data.ib'), name)
        globals()[name] = value
        return value
    raise AttributeError(name)

__all__ = [
    "DataSourceManifest",
    "DataSourceType",
    "IBHistoricalDataClient",
    "FilingProvider",
    "FxProvider",
    "IbApiHistoricalDataClient",
    "IbHistoricalDailyBarProvider",
    "MarketDataProvider",
    "ProviderCapability",
    "ProviderRegistry",
    "SecEdgarClient",
    "TushareUsDailyProvider",
    "company_facts_to_snapshots",
    "read_tushare_token",
]
