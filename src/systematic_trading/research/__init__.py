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
    if definition.universe_members:
        from systematic_trading.domain.market import Instrument
        members = [Instrument.model_validate(row) for row in definition.universe_members]
        if len({row.symbol for row in members}) != len(members):
            raise ValueError('Duplicate instrument in frozen strategy membership')
        return {row.symbol: row for row in sorted(members, key=lambda row: row.symbol)}
    universe_key = definition.universe_key
    if universe_key == "all_weather":
        return ALL_WEATHER_ETF_UNIVERSE
    if universe_key == "multi_asset":
        return MULTI_ASSET_ETF_UNIVERSE
    if universe_key == 'multi_asset_14':
        from systematic_trading.research.etf_universe import RESEARCH_SECTOR_ETFS
        pool = {**MULTI_ASSET_ETF_UNIVERSE, **RESEARCH_SECTOR_ETFS}
        return {s:pool[s] for s in sorted(pool)}
    if universe_key == 'global':
        return GLOBAL_ETF_UNIVERSE
    raise ValueError('Unregistered strategy universe: ' + universe_key)


def union_instruments(definitions):
    """Preserve every component and reject conflicting shared identities."""
    result = {}
    for definition in definitions:
        for symbol, instrument in instruments_for_definition(definition).items():
            if symbol in result and result[symbol] != instrument:
                raise ValueError('Conflicting allocation instrument identity: ' + symbol)
            result[symbol] = instrument
    return dict(sorted(result.items()))

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
