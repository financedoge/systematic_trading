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
MULTI_ASSET_BENCHMARK_SYMBOL = "AOR"
MULTI_ASSET_BENCHMARK_NAME = "Multi-asset allocation proxy (AOR)"

MULTI_ASSET_ETF_UNIVERSE = {
    **GLOBAL_ETF_UNIVERSE,
    "MCHI": Instrument(
        symbol="MCHI",
        name="iShares MSCI China ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="China",
    ),
    "IEF": Instrument(
        symbol="IEF",
        name="iShares 7-10 Year Treasury Bond ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US bonds",
    ),
    "TLT": Instrument(
        symbol="TLT",
        name="iShares 20+ Year Treasury Bond ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US bonds",
    ),
    "LQD": Instrument(
        symbol="LQD",
        name="iShares iBoxx $ Investment Grade Corporate Bond ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US credit",
    ),
    "HYG": Instrument(
        symbol="HYG",
        name="iShares iBoxx $ High Yield Corporate Bond ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US credit",
    ),
    "GLD": Instrument(
        symbol="GLD",
        name="SPDR Gold Shares",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Commodity gold",
    ),
    "DBC": Instrument(
        symbol="DBC",
        name="Invesco DB Commodity Index Tracking Fund",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Broad commodities",
    ),
}

BENCHMARK_INSTRUMENTS = {
    MSCI_WORLD_PROXY_SYMBOL: Instrument(
        symbol=MSCI_WORLD_PROXY_SYMBOL,
        name="iShares MSCI World ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Global developed equity",
    ),
    MULTI_ASSET_BENCHMARK_SYMBOL: Instrument(
        symbol=MULTI_ASSET_BENCHMARK_SYMBOL,
        name="iShares Core Growth Allocation ETF",
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="Global multi-asset",
    ),
}
