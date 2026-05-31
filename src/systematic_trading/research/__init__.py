from systematic_trading.research.etf_universe import (
    BENCHMARK_INSTRUMENTS,
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    MULTI_ASSET_BENCHMARK_NAME,
    MULTI_ASSET_BENCHMARK_SYMBOL,
    MULTI_ASSET_ETF_UNIVERSE,
)
from systematic_trading.research.all_weather_universe import (
    ALL_WEATHER_ETF_SPECS,
    ALL_WEATHER_ETF_UNIVERSE,
    ALL_WEATHER_SPEC_BY_SYMBOL,
    AllWeatherETFSpec,
    grouped_counts,
)
from systematic_trading.research.stock_universe import (
    SPY_REPLACEMENT_SYMBOL,
    US_STOCK_REPLACEMENT_UNIVERSE,
    default_us_stock_symbols,
)
from systematic_trading.research.strategy_catalog import (
    StrategyDefinition,
    build_model_structure_comparison,
    current_sota_definition,
    instantiate_overlays,
    risk_parity_definition,
    strategy_definition_from_overlay,
    strategy_model_card,
)


def instruments_for_definition(definition: StrategyDefinition):
    universe_key = definition.universe_key
    if universe_key == "all_weather":
        return ALL_WEATHER_ETF_UNIVERSE
    if universe_key == "multi_asset":
        return MULTI_ASSET_ETF_UNIVERSE
    return GLOBAL_ETF_UNIVERSE

__all__ = [
    "BENCHMARK_INSTRUMENTS",
    "GLOBAL_ETF_UNIVERSE",
    "MSCI_WORLD_PROXY_NAME",
    "MSCI_WORLD_PROXY_SYMBOL",
    "MULTI_ASSET_BENCHMARK_NAME",
    "MULTI_ASSET_BENCHMARK_SYMBOL",
    "MULTI_ASSET_ETF_UNIVERSE",
    "ALL_WEATHER_ETF_SPECS",
    "ALL_WEATHER_ETF_UNIVERSE",
    "ALL_WEATHER_SPEC_BY_SYMBOL",
    "AllWeatherETFSpec",
    "SPY_REPLACEMENT_SYMBOL",
    "StrategyDefinition",
    "US_STOCK_REPLACEMENT_UNIVERSE",
    "build_model_structure_comparison",
    "current_sota_definition",
    "default_us_stock_symbols",
    "grouped_counts",
    "instantiate_overlays",
    "instruments_for_definition",
    "risk_parity_definition",
    "strategy_definition_from_overlay",
    "strategy_model_card",
]
