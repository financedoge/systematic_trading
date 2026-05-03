from __future__ import annotations

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument


GLOBAL_ETF_UNIVERSE = {
    "SPY": Instrument(
        symbol="SPY",
        name="SPDR S&P 500 ETF Trust",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US",
    ),
    "VGK": Instrument(
        symbol="VGK",
        name="Vanguard FTSE Europe ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Europe",
    ),
    "EWJ": Instrument(
        symbol="EWJ",
        name="iShares MSCI Japan ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Japan",
    ),
    "EWH": Instrument(
        symbol="EWH",
        name="iShares MSCI Hong Kong ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="HK",
    ),
    "EWY": Instrument(
        symbol="EWY",
        name="iShares MSCI South Korea ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Korea",
    ),
}


MSCI_WORLD_PROXY_SYMBOL = "URTH"
MSCI_WORLD_PROXY_NAME = "MSCI World proxy (URTH)"

BENCHMARK_INSTRUMENTS = {
    MSCI_WORLD_PROXY_SYMBOL: Instrument(
        symbol=MSCI_WORLD_PROXY_SYMBOL,
        name="iShares MSCI World ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Global developed equity",
    ),
}
