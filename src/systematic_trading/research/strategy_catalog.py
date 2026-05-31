from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from systematic_trading.signals import (
    AdaptiveTrendOverlay,
    AssetPoolFilterOverlay,
    BasketRiskControlOverlay,
    CommodityRiskGuardOverlay,
    CountryCompositeFactorOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
    SimpleDecisionTreeModel,
    SleeveCappedMomentumOverlay,
    TechnicalDecisionTreeAllocatorOverlay,
    TimeSeriesMomentumOverlay,
    TrendQualityFilterOverlay,
)
from systematic_trading.signals.base import TargetOverlay
from systematic_trading.research.all_weather_universe import ALL_WEATHER_SPEC_BY_SYMBOL
from systematic_trading.research.sota_models import SOTA_PRICE_VOLUME_TECHNICAL_TREE_MODEL_JSON


@dataclass(frozen=True)
class OverlaySpec:
    kind: str
    parameters: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class StrategyDefinition:
    key: str
    name: str
    sleeve_name: str
    state: str
    description: str
    promoted_on: str | None = None
    universe_key: str = "global"
    scheduler: str = "static_monthly"
    overlays: tuple[OverlaySpec, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "sleeveName": self.sleeve_name,
            "state": self.state,
            "description": self.description,
            "promotedOn": self.promoted_on,
            "universeKey": self.universe_key,
            "scheduler": self.scheduler,
            "overlays": [overlay.to_dict() for overlay in self.overlays],
        }


def risk_parity_definition() -> StrategyDefinition:
    return StrategyDefinition(
        key="risk_parity",
        name="Baseline risk parity",
        sleeve_name="baseline-risk-parity",
        state="baseline",
        description="Monthly inverse-volatility ETF allocation with a max weight cap and cash reserve.",
    )


def current_sota_definition() -> StrategyDefinition:
    return StrategyDefinition(
        key="sota_price_volume_technical_tree_relative_adaptive_top6",
        name="SOTA: price/volume top 6 + technical tree + relative/adaptive",
        sleeve_name="sota-price-volume-technical-tree-relative-adaptive-top6",
        state="sota",
        promoted_on="2026-05-26",
        universe_key="multi_asset",
        scheduler="static_monthly",
        description=(
            "Expanded multi-asset ETF universe with inverse-volatility base weights, a price/volume top-six "
            "pool filter, a frozen pre-2023 technical decision-tree tilt, a restrained 20/60d relative-momentum "
            "tilt, and adaptive trend exposure scaling. Promoted because it has the strongest stability-adjusted "
            "profile after penalizing weak in-sample Sharpe."
        ),
        overlays=(
            OverlaySpec(
                kind="asset_pool_filter",
                parameters={
                    "shortMomentumBars": "63",
                    "mediumMomentumBars": "126",
                    "longMomentumBars": "252",
                    "volumeBars": "21",
                    "slowVolumeBars": "126",
                    "trendWeight": "0.75",
                    "volumeWeight": "0.25",
                    "topN": "6",
                    "minSelected": "4",
                    "requirePositiveLongMomentum": "true",
                    "minLongMomentum": "0",
                    "reallocateSelected": "true",
                },
            ),
            OverlaySpec(
                kind="decision_tree",
                parameters={
                    "maxDepth": "3",
                    "minSamplesLeaf": "25",
                    "trainingSamples": "1572",
                    "tilt": "0.16",
                    "maxActiveWeight": "0.06",
                    "valuationScores": "",
                    "macroScores": "",
                    "model": SOTA_PRICE_VOLUME_TECHNICAL_TREE_MODEL_JSON,
                },
            ),
            OverlaySpec(
                kind="relative_momentum",
                parameters={
                    "mediumLookbackBars": "20",
                    "longLookbackBars": "60",
                    "fastVolatilityBars": "21",
                    "slowVolatilityBars": "252",
                    "drawdownLookbackBars": "252",
                    "calmTilt": "0.12",
                    "riskTilt": "0.12",
                    "drawdownTrigger": "-0.08",
                    "volatilityRatioTrigger": "1.35",
                    "maxActiveWeight": "0.05",
                },
            ),
            OverlaySpec(
                kind="adaptive_trend",
                parameters={
                    "shortLookbackBars": "63",
                    "mediumLookbackBars": "126",
                    "longLookbackBars": "252",
                    "reboundLookbackBars": "21",
                    "volumeLookbackBars": "21",
                    "fastVolatilityBars": "21",
                    "slowVolatilityBars": "252",
                    "shortThreshold": "0",
                    "mediumThreshold": "-0.03",
                    "longThreshold": "-0.05",
                    "weakScale": "0.50",
                    "neutralScale": "0.80",
                    "defensiveScale": "0.35",
                    "reboundScale": "1.00",
                    "reallocateResidual": "true",
                },
            ),
        ),
    )


def strategy_definition_from_overlay(overlay: TargetOverlay) -> StrategyDefinition:
    if isinstance(overlay, SleeveCappedMomentumOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            universe_key="all_weather",
            scheduler="dynamic_monthly",
            description=(
                "Research candidate using dynamic all-weather sleeve-capped momentum selection "
                "with asset-class and region diversification caps."
            ),
            overlays=(
                OverlaySpec(
                    kind="sleeve_capped_momentum",
                    parameters={
                        "metadataSource": "all_weather",
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "mediumMomentumBars": str(overlay.medium_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "volumeBars": str(overlay.volume_bars),
                        "slowVolumeBars": str(overlay.slow_volume_bars),
                        "trendWeight": str(overlay.trend_weight),
                        "volumeWeight": str(overlay.volume_weight),
                        "topN": str(overlay.top_n),
                        "maxPerSleeve": str(overlay.max_per_sleeve),
                        "maxPerAssetClass": json.dumps(overlay.max_per_asset_class, separators=(",", ":")),
                        "minPerAssetClass": json.dumps(overlay.min_per_asset_class, separators=(",", ":")),
                        "maxPerRegion": json.dumps(overlay.max_per_region, separators=(",", ":")),
                        "requirePositiveLongMomentum": str(overlay.require_positive_long_momentum).lower(),
                        "minLongMomentum": str(overlay.min_long_momentum),
                        "reallocateSelected": str(overlay.reallocate_selected).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, CommodityRiskGuardOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            universe_key="all_weather",
            scheduler="dynamic_monthly",
            description="Research candidate using an asset-class-level commodity risk guard.",
            overlays=(
                OverlaySpec(
                    kind="commodity_guard",
                    parameters={
                        "metadataSource": "all_weather",
                        "guardedAssetClass": overlay.guarded_asset_class,
                        "maxAssetClassWeight": str(overlay.max_asset_class_weight),
                        "triggeredScale": str(overlay.triggered_scale),
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "slowMomentumBars": str(overlay.slow_momentum_bars),
                        "shortMomentumThreshold": str(overlay.short_momentum_threshold),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "volatilitySpikeMultiple": str(overlay.volatility_spike_multiple),
                        "reallocateResidual": str(overlay.reallocate_residual).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, AssetPoolFilterOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate that filters the investable ETF pool using point-in-time "
                "momentum and volume ranking signals."
            ),
            overlays=(
                OverlaySpec(
                    kind="asset_pool_filter",
                    parameters={
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "mediumMomentumBars": str(overlay.medium_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "volumeBars": str(overlay.volume_bars),
                        "slowVolumeBars": str(overlay.slow_volume_bars),
                        "trendWeight": str(overlay.trend_weight),
                        "volumeWeight": str(overlay.volume_weight),
                        "topN": str(overlay.top_n),
                        "minSelected": str(overlay.min_selected),
                        "requirePositiveLongMomentum": str(overlay.require_positive_long_momentum).lower(),
                        "minLongMomentum": str(overlay.min_long_momentum),
                        "reallocateSelected": str(overlay.reallocate_selected).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, TrendQualityFilterOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate that selects ETFs using raw momentum, risk-adjusted momentum, "
                "trend consistency, drawdown quality, and optional low-volatility ranks."
            ),
            overlays=(
                OverlaySpec(
                    kind="trend_quality_filter",
                    parameters={
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "mediumMomentumBars": str(overlay.medium_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "volatilityBars": str(overlay.volatility_bars),
                        "consistencyBars": str(overlay.consistency_bars),
                        "drawdownLookbackBars": str(overlay.drawdown_lookback_bars),
                        "momentumWeight": str(overlay.momentum_weight),
                        "riskAdjustedWeight": str(overlay.risk_adjusted_weight),
                        "consistencyWeight": str(overlay.consistency_weight),
                        "drawdownWeight": str(overlay.drawdown_weight),
                        "lowVolatilityWeight": str(overlay.low_volatility_weight),
                        "topN": str(overlay.top_n),
                        "minSelected": str(overlay.min_selected),
                        "requirePositiveLongMomentum": str(overlay.require_positive_long_momentum).lower(),
                        "minLongMomentum": str(overlay.min_long_momentum),
                        "fallbackToTopRanked": str(overlay.fallback_to_top_ranked).lower(),
                        "reallocateSelected": str(overlay.reallocate_selected).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, DecisionTreeSignalOverlay):
        summary = dict(overlay.model.training_summary)
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using an in-sample-trained regression decision tree over the signal library."
            ),
            overlays=(
                OverlaySpec(
                    kind="decision_tree",
                    parameters={
                        "maxDepth": str(overlay.model.max_depth),
                        "minSamplesLeaf": str(overlay.model.min_samples_leaf),
                        "trainingSamples": str(summary.get("samples", "0")),
                        "tilt": str(overlay.tilt),
                        "maxActiveWeight": str(overlay.max_active_weight),
                        "valuationScores": _score_map_param(overlay.valuation_scores),
                        "macroScores": _score_map_param(overlay.macro_scores),
                        "model": json.dumps(overlay.model.to_dict(), separators=(",", ":")),
                    },
                ),
            ),
        )
    if isinstance(overlay, TechnicalDecisionTreeAllocatorOverlay):
        summary = dict(overlay.model.training_summary)
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using a pre-OOS trained technical decision tree plus cross-sectional "
                "momentum and technical-health ranks for ETF selection and allocation."
            ),
            overlays=(
                OverlaySpec(
                    kind="technical_tree_allocator",
                    parameters={
                        "maxDepth": str(overlay.model.max_depth),
                        "minSamplesLeaf": str(overlay.model.min_samples_leaf),
                        "trainingSamples": str(summary.get("samples", "0")),
                        "topN": str(overlay.top_n),
                        "minSelected": str(overlay.min_selected),
                        "treeWeight": str(overlay.tree_weight),
                        "momentumWeight": str(overlay.momentum_weight),
                        "technicalWeight": str(overlay.technical_weight),
                        "allocationTilt": str(overlay.allocation_tilt),
                        "minLongMomentum": str(overlay.min_long_momentum),
                        "requirePositiveTimeseries": str(overlay.require_positive_timeseries).lower(),
                        "reallocateSelected": str(overlay.reallocate_selected).lower(),
                        "valuationScores": _score_map_param(overlay.valuation_scores),
                        "macroScores": _score_map_param(overlay.macro_scores),
                        "model": json.dumps(overlay.model.to_dict(), separators=(",", ":")),
                    },
                ),
            ),
        )
    if isinstance(overlay, CountryCompositeFactorOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using country ETF trend, volume, mean-reversion, valuation, "
                "and macro-growth factor tilts."
            ),
            overlays=(
                OverlaySpec(
                    kind="country_factor",
                    parameters={
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "mediumMomentumBars": str(overlay.medium_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "reversalBars": str(overlay.reversal_bars),
                        "meanReversionBars": str(overlay.mean_reversion_bars),
                        "volumeBars": str(overlay.volume_bars),
                        "slowVolumeBars": str(overlay.slow_volume_bars),
                        "trendWeight": str(overlay.trend_weight),
                        "volumeWeight": str(overlay.volume_weight),
                        "meanReversionWeight": str(overlay.mean_reversion_weight),
                        "valuationWeight": str(overlay.valuation_weight),
                        "macroWeight": str(overlay.macro_weight),
                        "tilt": str(overlay.tilt),
                        "maxActiveWeight": str(overlay.max_active_weight),
                        "valuationScores": _score_map_param(overlay.valuation_scores),
                        "macroScores": _score_map_param(overlay.macro_scores),
                    },
                ),
            ),
        )
    if isinstance(overlay, RegimeGatedRelativeMomentumOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using a regime-gated cross-sectional relative momentum overlay.",
            overlays=(
                OverlaySpec(
                    kind="relative_momentum",
                    parameters={
                        "mediumLookbackBars": str(overlay.medium_lookback_bars),
                        "longLookbackBars": str(overlay.long_lookback_bars),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "drawdownLookbackBars": str(overlay.drawdown_lookback_bars),
                        "calmTilt": str(overlay.calm_tilt),
                        "riskTilt": str(overlay.risk_tilt),
                        "drawdownTrigger": str(overlay.drawdown_trigger),
                        "volatilityRatioTrigger": str(overlay.volatility_ratio_trigger),
                        "maxActiveWeight": str(overlay.max_active_weight),
                    },
                ),
            ),
        )
    if isinstance(overlay, BasketRiskControlOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using portfolio-level breadth, drawdown, and volatility controls "
                "to scale exposure and leave residual weight in cash during weak regimes."
            ),
            overlays=(
                OverlaySpec(
                    kind="basket_risk_control",
                    parameters={
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "movingAverageBars": str(overlay.moving_average_bars),
                        "drawdownLookbackBars": str(overlay.drawdown_lookback_bars),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "weakBreadthThreshold": str(overlay.weak_breadth_threshold),
                        "healthyBreadthThreshold": str(overlay.healthy_breadth_threshold),
                        "shortMomentumThreshold": str(overlay.short_momentum_threshold),
                        "longMomentumThreshold": str(overlay.long_momentum_threshold),
                        "drawdownTrigger": str(overlay.drawdown_trigger),
                        "severeDrawdownTrigger": str(overlay.severe_drawdown_trigger),
                        "volatilityRatioTrigger": str(overlay.volatility_ratio_trigger),
                        "severeVolatilityRatioTrigger": str(overlay.severe_volatility_ratio_trigger),
                        "neutralScale": str(overlay.neutral_scale),
                        "defensiveScale": str(overlay.defensive_scale),
                        "severeScale": str(overlay.severe_scale),
                    },
                ),
            ),
        )
    if isinstance(overlay, AdaptiveTrendOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using adaptive trend exposure scaling.",
            overlays=(
                OverlaySpec(
                    kind="adaptive_trend",
                    parameters={
                        "shortLookbackBars": str(overlay.short_lookback_bars),
                        "mediumLookbackBars": str(overlay.medium_lookback_bars),
                        "longLookbackBars": str(overlay.long_lookback_bars),
                        "reboundLookbackBars": str(overlay.rebound_lookback_bars),
                        "volumeLookbackBars": str(overlay.volume_lookback_bars),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "shortThreshold": str(overlay.short_threshold),
                        "mediumThreshold": str(overlay.medium_threshold),
                        "longThreshold": str(overlay.long_threshold),
                        "weakScale": str(overlay.weak_scale),
                        "neutralScale": str(overlay.neutral_scale),
                        "defensiveScale": str(overlay.defensive_scale),
                        "reboundScale": str(overlay.rebound_scale),
                        "reallocateResidual": str(overlay.reallocate_residual).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, TimeSeriesMomentumOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using absolute time-series momentum gating.",
            overlays=(
                OverlaySpec(
                    kind="time_series_momentum",
                    parameters={
                        "lookbackBars": str(overlay.lookback_bars),
                        "threshold": str(overlay.threshold),
                        "reallocateSurvivors": str(overlay.reallocate_survivors).lower(),
                    },
                ),
            ),
        )
    raise TypeError(f"Unsupported overlay type: {type(overlay).__name__}")


def instantiate_overlays(definition: StrategyDefinition) -> list[TargetOverlay]:
    overlays: list[TargetOverlay] = []
    for spec in definition.overlays:
        params = spec.parameters
        if spec.kind == "relative_momentum":
            overlays.append(
                RegimeGatedRelativeMomentumOverlay(
                    medium_lookback_bars=int(params["mediumLookbackBars"]),
                    long_lookback_bars=int(params["longLookbackBars"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    drawdown_lookback_bars=int(params["drawdownLookbackBars"]),
                    calm_tilt=Decimal(params["calmTilt"]),
                    risk_tilt=Decimal(params["riskTilt"]),
                    drawdown_trigger=Decimal(params["drawdownTrigger"]),
                    volatility_ratio_trigger=Decimal(params["volatilityRatioTrigger"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                )
            )
        elif spec.kind == "basket_risk_control":
            overlays.append(
                BasketRiskControlOverlay(
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    moving_average_bars=int(params["movingAverageBars"]),
                    drawdown_lookback_bars=int(params["drawdownLookbackBars"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    weak_breadth_threshold=Decimal(params["weakBreadthThreshold"]),
                    healthy_breadth_threshold=Decimal(params["healthyBreadthThreshold"]),
                    short_momentum_threshold=Decimal(params["shortMomentumThreshold"]),
                    long_momentum_threshold=Decimal(params["longMomentumThreshold"]),
                    drawdown_trigger=Decimal(params["drawdownTrigger"]),
                    severe_drawdown_trigger=Decimal(params["severeDrawdownTrigger"]),
                    volatility_ratio_trigger=Decimal(params["volatilityRatioTrigger"]),
                    severe_volatility_ratio_trigger=Decimal(params["severeVolatilityRatioTrigger"]),
                    neutral_scale=Decimal(params["neutralScale"]),
                    defensive_scale=Decimal(params["defensiveScale"]),
                    severe_scale=Decimal(params["severeScale"]),
                )
            )
        elif spec.kind == "sleeve_capped_momentum":
            overlays.append(
                SleeveCappedMomentumOverlay(
                    sleeve_by_symbol={symbol: item.sleeve for symbol, item in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
                    asset_class_by_symbol={
                        symbol: item.asset_class_group for symbol, item in ALL_WEATHER_SPEC_BY_SYMBOL.items()
                    },
                    region_by_symbol={symbol: item.region_group for symbol, item in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    medium_momentum_bars=int(params["mediumMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    volume_bars=int(params["volumeBars"]),
                    slow_volume_bars=int(params["slowVolumeBars"]),
                    trend_weight=Decimal(params["trendWeight"]),
                    volume_weight=Decimal(params["volumeWeight"]),
                    top_n=int(params["topN"]),
                    max_per_sleeve=int(params["maxPerSleeve"]),
                    max_per_asset_class=_parse_int_map(params["maxPerAssetClass"]),
                    min_per_asset_class=_parse_int_map(params.get("minPerAssetClass", "{}")),
                    max_per_region=_parse_int_map(params["maxPerRegion"]),
                    require_positive_long_momentum=_bool(params["requirePositiveLongMomentum"]),
                    min_long_momentum=Decimal(params["minLongMomentum"]),
                    reallocate_selected=_bool(params["reallocateSelected"]),
                )
            )
        elif spec.kind == "commodity_guard":
            overlays.append(
                CommodityRiskGuardOverlay(
                    asset_class_by_symbol={
                        symbol: item.asset_class_group for symbol, item in ALL_WEATHER_SPEC_BY_SYMBOL.items()
                    },
                    guarded_asset_class=params["guardedAssetClass"],
                    max_asset_class_weight=Decimal(params["maxAssetClassWeight"]),
                    triggered_scale=Decimal(params["triggeredScale"]),
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    slow_momentum_bars=int(params["slowMomentumBars"]),
                    short_momentum_threshold=Decimal(params["shortMomentumThreshold"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    volatility_spike_multiple=Decimal(params["volatilitySpikeMultiple"]),
                    reallocate_residual=_bool(params["reallocateResidual"]),
                )
            )
        elif spec.kind == "asset_pool_filter":
            overlays.append(
                AssetPoolFilterOverlay(
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    medium_momentum_bars=int(params["mediumMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    volume_bars=int(params["volumeBars"]),
                    slow_volume_bars=int(params["slowVolumeBars"]),
                    trend_weight=Decimal(params["trendWeight"]),
                    volume_weight=Decimal(params["volumeWeight"]),
                    top_n=int(params["topN"]),
                    min_selected=int(params["minSelected"]),
                    require_positive_long_momentum=_bool(params["requirePositiveLongMomentum"]),
                    min_long_momentum=Decimal(params["minLongMomentum"]),
                    reallocate_selected=_bool(params["reallocateSelected"]),
                )
            )
        elif spec.kind == "trend_quality_filter":
            overlays.append(
                TrendQualityFilterOverlay(
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    medium_momentum_bars=int(params["mediumMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    volatility_bars=int(params["volatilityBars"]),
                    consistency_bars=int(params["consistencyBars"]),
                    drawdown_lookback_bars=int(params["drawdownLookbackBars"]),
                    momentum_weight=Decimal(params["momentumWeight"]),
                    risk_adjusted_weight=Decimal(params["riskAdjustedWeight"]),
                    consistency_weight=Decimal(params["consistencyWeight"]),
                    drawdown_weight=Decimal(params["drawdownWeight"]),
                    low_volatility_weight=Decimal(params["lowVolatilityWeight"]),
                    top_n=int(params["topN"]),
                    min_selected=int(params["minSelected"]),
                    require_positive_long_momentum=_bool(params["requirePositiveLongMomentum"]),
                    min_long_momentum=Decimal(params["minLongMomentum"]),
                    fallback_to_top_ranked=_bool(params["fallbackToTopRanked"]),
                    reallocate_selected=_bool(params["reallocateSelected"]),
                )
            )
        elif spec.kind == "decision_tree":
            overlays.append(
                DecisionTreeSignalOverlay(
                    model=SimpleDecisionTreeModel.from_dict(json.loads(params["model"])),
                    tilt=Decimal(params["tilt"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                    valuation_scores=_parse_score_map(params.get("valuationScores", "")),
                    macro_scores=_parse_score_map(params.get("macroScores", "")),
                )
            )
        elif spec.kind == "technical_tree_allocator":
            overlays.append(
                TechnicalDecisionTreeAllocatorOverlay(
                    model=SimpleDecisionTreeModel.from_dict(json.loads(params["model"])),
                    top_n=int(params["topN"]),
                    min_selected=int(params["minSelected"]),
                    tree_weight=Decimal(params["treeWeight"]),
                    momentum_weight=Decimal(params["momentumWeight"]),
                    technical_weight=Decimal(params["technicalWeight"]),
                    allocation_tilt=Decimal(params["allocationTilt"]),
                    min_long_momentum=Decimal(params["minLongMomentum"]),
                    require_positive_timeseries=_bool(params["requirePositiveTimeseries"]),
                    reallocate_selected=_bool(params["reallocateSelected"]),
                    valuation_scores=_parse_score_map(params.get("valuationScores", "")),
                    macro_scores=_parse_score_map(params.get("macroScores", "")),
                )
            )
        elif spec.kind == "country_factor":
            overlays.append(
                CountryCompositeFactorOverlay(
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    medium_momentum_bars=int(params["mediumMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    reversal_bars=int(params["reversalBars"]),
                    mean_reversion_bars=int(params["meanReversionBars"]),
                    volume_bars=int(params["volumeBars"]),
                    slow_volume_bars=int(params["slowVolumeBars"]),
                    trend_weight=Decimal(params["trendWeight"]),
                    volume_weight=Decimal(params["volumeWeight"]),
                    mean_reversion_weight=Decimal(params["meanReversionWeight"]),
                    valuation_weight=Decimal(params["valuationWeight"]),
                    macro_weight=Decimal(params["macroWeight"]),
                    tilt=Decimal(params["tilt"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                    valuation_scores=_parse_score_map(params.get("valuationScores", "")),
                    macro_scores=_parse_score_map(params.get("macroScores", "")),
                )
            )
        elif spec.kind == "adaptive_trend":
            overlays.append(
                AdaptiveTrendOverlay(
                    short_lookback_bars=int(params["shortLookbackBars"]),
                    medium_lookback_bars=int(params["mediumLookbackBars"]),
                    long_lookback_bars=int(params["longLookbackBars"]),
                    rebound_lookback_bars=int(params["reboundLookbackBars"]),
                    volume_lookback_bars=int(params["volumeLookbackBars"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    short_threshold=Decimal(params["shortThreshold"]),
                    medium_threshold=Decimal(params["mediumThreshold"]),
                    long_threshold=Decimal(params["longThreshold"]),
                    weak_scale=Decimal(params["weakScale"]),
                    neutral_scale=Decimal(params["neutralScale"]),
                    defensive_scale=Decimal(params["defensiveScale"]),
                    rebound_scale=Decimal(params["reboundScale"]),
                    reallocate_residual=_bool(params["reallocateResidual"]),
                )
            )
        elif spec.kind == "time_series_momentum":
            overlays.append(
                TimeSeriesMomentumOverlay(
                    lookback_bars=int(params["lookbackBars"]),
                    threshold=Decimal(params["threshold"]),
                    reallocate_survivors=_bool(params["reallocateSurvivors"]),
                )
            )
        else:
            raise ValueError(f"Unsupported overlay spec: {spec.kind}")
    return overlays


def build_model_structure_comparison(
    *,
    baseline: StrategyDefinition,
    candidate: StrategyDefinition,
) -> dict[str, Any]:
    return {
        "baseline": strategy_model_card(baseline),
        "candidate": strategy_model_card(candidate),
    }


def strategy_model_card(definition: StrategyDefinition) -> dict[str, Any]:
    layers = _model_layers(definition)
    return {
        "definition": definition.to_dict(),
        "layers": layers,
        "layerDiagram": _layer_mermaid(layers),
        "decisionTree": _decision_tree_mermaid(definition),
    }


def _model_layers(definition: StrategyDefinition) -> list[dict[str, str]]:
    layers = [
        {
            "id": "data",
            "title": "Market data",
            "detail": "Adjusted ETF closes, volumes, and USD/CNH FX for the configured ETF basket.",
        },
        {
            "id": "schedule",
            "title": "Monthly rebalance",
            "detail": "Recompute targets on the first available trading day of each month.",
        },
        {
            "id": "risk_parity",
            "title": "Risk parity beta",
            "detail": "63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve.",
        },
    ]
    for index, overlay in enumerate(definition.overlays, start=1):
        layers.append(_overlay_layer(overlay, index))
    layers.append(
        {
            "id": "targets",
            "title": "Final target weights",
            "detail": "Normalize portfolio weights and feed the daily backtest execution engine.",
        }
    )
    return layers


def _overlay_layer(overlay: OverlaySpec, index: int) -> dict[str, str]:
    params = overlay.parameters
    if overlay.kind == "relative_momentum":
        detail = (
            f"Score = 45% {params['mediumLookbackBars']}d momentum + 55% {params['longLookbackBars']}d momentum; "
            f"regime drawdown trigger {params['drawdownTrigger']}, vol-ratio trigger {params['volatilityRatioTrigger']}; "
            f"tilt {params['calmTilt']} calm / {params['riskTilt']} risk; cap active weight {params['maxActiveWeight']}."
        )
        title = "Relative momentum overlay"
    elif overlay.kind == "basket_risk_control":
        detail = (
            f"Watch {params['shortMomentumBars']}/{params['longMomentumBars']}d basket momentum, "
            f"{params['movingAverageBars']}d breadth, drawdown trigger {params['drawdownTrigger']}, "
            f"and vol-ratio trigger {params['volatilityRatioTrigger']}; scale to "
            f"{params['neutralScale']}/{params['defensiveScale']}/{params['severeScale']} when weak."
        )
        title = "Basket risk control"
    elif overlay.kind == "sleeve_capped_momentum":
        detail = (
            f"Rank the dynamic all-weather ETF pool using {params['shortMomentumBars']}/"
            f"{params['mediumMomentumBars']}/{params['longMomentumBars']}d momentum and "
            f"{params['volumeBars']}d volume pressure; keep top {params['topN']} subject to sleeve, "
            "asset-class, and region caps; reallocate selected assets."
        )
        title = "Sleeve-capped momentum selector"
    elif overlay.kind == "commodity_guard":
        detail = (
            f"Guard {params['guardedAssetClass']} exposure: cap gross weight at {params['maxAssetClassWeight']}, "
            f"scale by {params['triggeredScale']} when {params['shortMomentumBars']}d basket momentum <= "
            f"{params['shortMomentumThreshold']} or fast volatility is {params['volatilitySpikeMultiple']}x slow volatility."
        )
        title = "Commodity risk guard"
    elif overlay.kind == "asset_pool_filter":
        mode = "reallocate selected assets" if _bool(params["reallocateSelected"]) else "hold filtered weight in cash"
        gate = (
            f"requires {params['longMomentumBars']}d momentum > {params['minLongMomentum']}"
            if _bool(params["requirePositiveLongMomentum"])
            else "uses rank only"
        )
        detail = (
            f"Rank assets using {params['shortMomentumBars']}/{params['mediumMomentumBars']}/"
            f"{params['longMomentumBars']}d momentum and {params['volumeBars']}d volume pressure; "
            f"select top {params['topN']} with minimum {params['minSelected']}; {gate}; {mode}."
        )
        title = "Asset-pool filter overlay"
    elif overlay.kind == "trend_quality_filter":
        mode = "reallocate selected assets" if _bool(params["reallocateSelected"]) else "hold filtered weight in cash"
        detail = (
            f"Rank assets using {params['shortMomentumBars']}/{params['mediumMomentumBars']}/"
            f"{params['longMomentumBars']}d momentum, momentum per volatility, "
            f"{params['consistencyBars']}d consistency, and {params['drawdownLookbackBars']}d drawdown quality; "
            f"select top {params['topN']} with minimum {params['minSelected']}; {mode}."
        )
        title = "Trend-quality filter overlay"
    elif overlay.kind == "decision_tree":
        detail = (
            f"Train a max-depth {params['maxDepth']} regression tree on {params['trainingSamples']} "
            f"in-sample asset-month observations from the signal library; tilt {params['tilt']}, "
            f"cap active weight {params['maxActiveWeight']}."
        )
        title = "Decision-tree signal overlay"
    elif overlay.kind == "technical_tree_allocator":
        detail = (
            f"Train a max-depth {params['maxDepth']} regression tree on {params['trainingSamples']} "
            "pre-OOS asset-month observations; combine tree, cross-sectional momentum, and MACD/Bollinger/RSI "
            f"technical ranks; keep top {params['topN']} with minimum {params['minSelected']}."
        )
        title = "Technical tree allocator"
    elif overlay.kind == "country_factor":
        detail = (
            f"Blend {params['shortMomentumBars']}/{params['mediumMomentumBars']}/{params['longMomentumBars']}d trend, "
            f"{params['volumeBars']}d volume pressure, {params['reversalBars']}/{params['meanReversionBars']}d "
            f"mean reversion, valuation priors, and macro-growth priors; tilt {params['tilt']}, "
            f"cap active weight {params['maxActiveWeight']}."
        )
        title = "Country factor overlay"
    elif overlay.kind == "adaptive_trend":
        detail = (
            f"Blend {params['shortLookbackBars']}/{params['mediumLookbackBars']}/{params['longLookbackBars']}d trend, "
            f"volume, rebound, and volatility shock gates; scales {params['weakScale']}, "
            f"{params['neutralScale']}, {params['defensiveScale']}, {params['reboundScale']}."
        )
        title = "Adaptive trend overlay"
    elif overlay.kind == "time_series_momentum":
        mode = "reallocate survivors" if _bool(params["reallocateSurvivors"]) else "hold residual cash"
        detail = (
            f"Keep assets above {params['lookbackBars']}d return threshold {params['threshold']}; otherwise reduce to zero and {mode}."
        )
        title = "Time-series momentum overlay"
    else:
        title = overlay.kind.replace("_", " ").title()
        detail = "Custom overlay."
    return {"id": f"overlay_{index}", "title": title, "detail": detail}


def _layer_mermaid(layers: list[dict[str, str]]) -> str:
    lines = ["flowchart LR"]
    for index, layer in enumerate(layers):
        node_id = f"L{index + 1}"
        lines.append(f'  {node_id}["{_mermaid_label(layer["title"], layer["detail"])}"]')
        if index:
            lines.append(f"  L{index} --> {node_id}")
    return "\n".join(lines)


def _decision_tree_mermaid(definition: StrategyDefinition) -> str:
    if not definition.overlays:
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Monthly rebalance date"]) --> B{"Enough 63-bar history for every ETF?"}',
                '  B -- "No" --> C["Skip rebalance until history is available"]',
                '  B -- "Yes" --> D["Compute realized volatility by ETF"]',
                '  D --> E{"All volatilities positive?"}',
                '  E -- "No" --> C',
                '  E -- "Yes" --> F["Allocate inverse to volatility"]',
                '  F --> G["Apply 45% max weight and 2% cash reserve"]',
                '  G --> H(["Final risk-parity targets"])',
            ]
        )
    overlay_kinds = [overlay.kind for overlay in definition.overlays]
    if overlay_kinds == ["sleeve_capped_momentum", "commodity_guard", "relative_momentum"]:
        return _sota_dynamic_commodity_guard_tree(definition.overlays)
    trees = [_overlay_decision_tree(overlay) for overlay in definition.overlays]
    if len(trees) == 1:
        return trees[0]
    return "\n\n".join(trees)


def _sota_dynamic_commodity_guard_tree(overlays: tuple[OverlaySpec, ...]) -> str:
    sleeve_params = overlays[0].parameters
    guard_params = overlays[1].parameters
    momentum_params = overlays[2].parameters
    return "\n".join(
        [
            "flowchart TD",
            '  A(["Monthly rebalance date"]) --> B{"Enough dynamic all-weather price and volume history?"}',
            '  B -- "No" --> C["Skip rebalance until ETF histories are eligible"]',
            '  B -- "Yes" --> D["Compute inverse-volatility base weights on currently eligible ETFs"]',
            (
                f'  D --> E["Score ETFs with {sleeve_params["shortMomentumBars"]}/'
                f'{sleeve_params["mediumMomentumBars"]}/{sleeve_params["longMomentumBars"]}d momentum '
                f'and {sleeve_params["volumeBars"]}d volume pressure"]'
            ),
            f'  E --> F["Keep top {sleeve_params["topN"]} subject to sleeve, asset-class, and region caps"]',
            '  F --> G["Reallocate selected weights"]',
            '  G --> H{"Commodity gross weight above cap?"}',
            f'  H -- "Yes" --> I["Scale commodity sleeve toward {guard_params["maxAssetClassWeight"]} cap"]',
            (
                f'  H -- "No" --> J{{"{guard_params["shortMomentumBars"]}d commodity momentum <= '
                f'{guard_params["shortMomentumThreshold"]}?"}}'
            ),
            f'  J -- "Yes" --> K["Scale commodity targets by {guard_params["triggeredScale"]}"]',
            (
                f'  J -- "No" --> L{{"Fast commodity vol >= {guard_params["volatilitySpikeMultiple"]}x '
                'slow vol?"}'
            ),
            '  L -- "Yes" --> K',
            '  L -- "No" --> M["Leave commodity targets unchanged"]',
            '  I --> N["Reallocate residual to non-commodity selected assets"]',
            '  K --> N',
            '  M --> O{"Basket drawdown or volatility-risk regime?"}',
            '  N --> O',
            f'  O -- "Risk" --> P["Use relative-momentum tilt {momentum_params["riskTilt"]}"]',
            f'  O -- "Calm" --> Q["Use relative-momentum tilt {momentum_params["calmTilt"]}"]',
            (
                f'  P --> R["Rank ETFs by {momentum_params["mediumLookbackBars"]}/'
                f'{momentum_params["longLookbackBars"]}d relative momentum"]'
            ),
            '  Q --> R',
            f'  R --> S["Cap active delta at +/-{momentum_params["maxActiveWeight"]} per ETF"]',
            '  S --> T["Rescale to preserve invested weight"]',
            '  T --> U(["Final SOTA targets"])',
        ]
    )


def _overlay_decision_tree(overlay: OverlaySpec) -> str:
    params = overlay.parameters
    if overlay.kind == "relative_momentum":
        return "\n".join(
            [
                "flowchart TD",
                (
                    f'  A(["Risk-parity targets"]) --> B{{"Enough {params["mediumLookbackBars"]}d '
                    f'and {params["longLookbackBars"]}d history for the basket?"}}'
                ),
                '  B -- "No" --> C["Keep risk-parity targets"]',
                (
                    f'  B -- "Yes" --> D["Score each ETF = 45% {params["mediumLookbackBars"]}d '
                    f'momentum + 55% {params["longLookbackBars"]}d momentum"]'
                ),
                (
                    f'  D --> E{{"Basket drawdown <= {params["drawdownTrigger"]} '
                    f'or vol-ratio >= {params["volatilityRatioTrigger"]}?"}}'
                ),
                f'  E -- "Yes" --> F["Use risk tilt {params["riskTilt"]}"]',
                f'  E -- "No" --> G["Use calm tilt {params["calmTilt"]}"]',
                '  F --> H["Rank ETFs by score"]',
                '  G --> H',
                '  H --> I["Multiply base weight by 1 + tilt * rank score"]',
                f'  I --> J["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  J --> K["Rescale to preserve original invested weight"]',
                '  K --> L(["Final SOTA/research targets"])',
            ]
        )
    if overlay.kind == "basket_risk_control":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Post-selection target basket"]) --> B{"Enough basket history?"}',
                '  B -- "No" --> C["Keep target basket unchanged"]',
                (
                    f'  B -- "Yes" --> D["Compute weighted {params["shortMomentumBars"]}/'
                    f'{params["longMomentumBars"]}d momentum, {params["movingAverageBars"]}d breadth, '
                    'drawdown, and fast/slow volatility ratio"]'
                ),
                (
                    f'  D --> E{{"Severe drawdown <= {params["severeDrawdownTrigger"]}, '
                    f'weak breadth, or vol-ratio >= {params["severeVolatilityRatioTrigger"]}?"}}'
                ),
                f'  E -- "Yes" --> F["Scale basket to {params["severeScale"]}; leave residual cash"]',
                (
                    f'  E -- "No" --> G{{"Breadth <= {params["weakBreadthThreshold"]}, '
                    f'drawdown <= {params["drawdownTrigger"]}, or vol-ratio >= {params["volatilityRatioTrigger"]}?"}}'
                ),
                f'  G -- "Yes" --> H["Scale basket to {params["defensiveScale"]}; leave residual cash"]',
                (
                    f'  G -- "No" --> I{{"Breadth below {params["healthyBreadthThreshold"]} '
                    'or short momentum weak?"}'
                ),
                f'  I -- "Yes" --> J["Scale basket to {params["neutralScale"]}; leave residual cash"]',
                '  I -- "No" --> K["Keep full exposure"]',
                '  F --> L(["Final risk-controlled targets"])',
                '  H --> L',
                '  J --> L',
                '  K --> L',
            ]
        )
    if overlay.kind == "asset_pool_filter":
        mode = "Reallocate removed weight to selected assets" if _bool(params["reallocateSelected"]) else "Leave removed weight in cash"
        gate_label = (
            f"{params['longMomentumBars']}d momentum > {params['minLongMomentum']}?"
            if _bool(params["requirePositiveLongMomentum"])
            else "Asset has a valid rank?"
        )
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough price/volume history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                (
                    f'  B -- "Yes" --> D["Score assets with {params["shortMomentumBars"]}/'
                    f'{params["mediumMomentumBars"]}/{params["longMomentumBars"]}d momentum '
                    f'and {params["volumeBars"]}d volume pressure"]'
                ),
                f'  D --> E{{"{gate_label}"}}',
                '  E -- "No" --> F["Remove from selected pool"]',
                f'  E -- "Yes" --> G["Rank and keep top {params["topN"]} assets"]',
                f'  G --> H["Require at least {params["minSelected"]} selected assets"]',
                f'  F --> I["{mode}"]',
                '  H --> I',
                '  I --> J(["Final filtered multi-asset targets"])',
            ]
        )
    if overlay.kind == "trend_quality_filter":
        mode = "Reallocate selected weights" if _bool(params["reallocateSelected"]) else "Leave removed weight in cash"
        gate_label = (
            f"{params['longMomentumBars']}d momentum > {params['minLongMomentum']}?"
            if _bool(params["requirePositiveLongMomentum"])
            else "Asset has a valid trend-quality rank?"
        )
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough price history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                (
                    f'  B -- "Yes" --> D["Rank assets by {params["shortMomentumBars"]}/'
                    f'{params["mediumMomentumBars"]}/{params["longMomentumBars"]}d momentum, '
                    'risk-adjusted momentum, consistency, and drawdown quality"]'
                ),
                f'  D --> E{{"{gate_label}"}}',
                '  E -- "No" --> F["Remove unless fallback is needed"]',
                f'  E -- "Yes" --> G["Rank and keep top {params["topN"]} assets"]',
                f'  G --> H["Require at least {params["minSelected"]} selected assets"]',
                f'  F --> I["{mode}"]',
                '  H --> I',
                '  I --> J(["Final trend-quality targets"])',
            ]
        )
    if overlay.kind == "sleeve_capped_momentum":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Dynamic all-weather risk-parity targets"]) --> B{"Enough point-in-time price and volume history?"}',
                '  B -- "No" --> C["Keep base dynamic risk-parity targets"]',
                (
                    f'  B -- "Yes" --> D["Score ETFs with {params["shortMomentumBars"]}/'
                    f'{params["mediumMomentumBars"]}/{params["longMomentumBars"]}d momentum '
                    f'and {params["volumeBars"]}d volume pressure"]'
                ),
                f'  D --> E["Rank globally and keep top {params["topN"]}"]',
                f'  E --> F["Apply max {params["maxPerSleeve"]} per sleeve plus asset-class and region caps"]',
                '  F --> G["Reallocate selected weights"]',
                '  G --> H(["Sleeve-capped selected targets"])',
            ]
        )
    if overlay.kind == "commodity_guard":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Sleeve-selected targets"]) --> B{"Commodity gross weight above cap?"}',
                f'  B -- "Yes" --> C["Scale commodity sleeve toward {params["maxAssetClassWeight"]} cap"]',
                f'  B -- "No" --> D{{"{params["shortMomentumBars"]}d commodity momentum <= {params["shortMomentumThreshold"]}?"}}',
                f'  D -- "Yes" --> E["Scale commodity targets by {params["triggeredScale"]}"]',
                (
                    f'  D -- "No" --> F{{"Fast commodity vol >= {params["volatilitySpikeMultiple"]}x '
                    'slow vol?"}'
                ),
                f'  F -- "Yes" --> E',
                '  F -- "No" --> G["Leave targets unchanged"]',
                '  C --> H["Reallocate residual to non-commodity selected assets"]',
                '  E --> H',
                '  G --> I(["Commodity-guarded targets"])',
                '  H --> I',
            ]
        )
    if overlay.kind == "decision_tree":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["In-sample rebalance rows"]) --> B["Compute signal-library features"]',
                '  B --> C["Target = next-month asset return minus basket mean"]',
                f'  C --> D["Fit regression tree, max depth {params["maxDepth"]}"]',
                '  D --> E(["Freeze tree before OOS starts"])',
                '  E --> F["Score ETFs at each rebalance"]',
                f'  F --> G["Rank forecasts and apply tilt {params["tilt"]}"]',
                f'  G --> H["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  H --> I["Rescale to preserve original invested weight"]',
                '  I --> J(["Final decision-tree targets"])',
            ]
        )
    if overlay.kind == "technical_tree_allocator":
        gate_label = (
            f"252d momentum > {params['minLongMomentum']} and above 252d MA?"
            if _bool(params["requirePositiveTimeseries"])
            else "Valid composite rank?"
        )
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Pre-2023 rebalance rows"]) --> B["Compute signal-library features, including MACD and Bollinger bands"]',
                '  B --> C["Target = next-month asset return minus basket mean"]',
                f'  C --> D["Fit regression tree, max depth {params["maxDepth"]}"]',
                '  D --> E(["Freeze tree before OOS starts"])',
                '  E --> F["At each rebalance, score ETFs with frozen tree forecasts"]',
                '  F --> G["Rank tree forecasts, cross-sectional momentum, and technical health"]',
                (
                    f'  G --> H["Blend ranks: tree {params["treeWeight"]}, momentum {params["momentumWeight"]}, '
                    f'technical {params["technicalWeight"]}"]'
                ),
                f'  H --> I{{"{gate_label}"}}',
                f'  I -- "Pass" --> J["Keep top {params["topN"]} assets"]',
                f'  I -- "Too few" --> K["Fallback to top-ranked assets until min {params["minSelected"]}"]',
                f'  J --> L["Allocate by base risk-parity weight times 1 + {params["allocationTilt"]} * composite score"]',
                '  K --> L',
                '  L --> M["Rescale selected assets to preserve invested weight"]',
                '  M --> N(["Final technical tree targets"])',
            ]
        )
    if overlay.kind == "country_factor":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough price and volume history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                '  B -- "Yes" --> D["Rank trend, volume pressure, and mean-reversion factors"]',
                '  D --> E["Add valuation and macro-growth score maps when supplied"]',
                f'  E --> F["Blend factor scores using tilt {params["tilt"]}"]',
                f'  F --> G["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  G --> H["Rescale to preserve original invested weight"]',
                '  H --> I(["Final country factor targets"])',
            ]
        )
    if overlay.kind == "adaptive_trend":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough short/medium/long trend history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                '  B -- "Yes" --> D["Score trend across short, medium, and long windows"]',
                '  D --> E{"Volatility shock?"}',
                f'  E -- "Yes" --> F["Use defensive scale {params["defensiveScale"]}"]',
                '  E -- "No" --> G{"Rebound or volume confirmation?"}',
                f'  G -- "Yes" --> H["Use rebound/neutral scale up to {params["reboundScale"]}"]',
                f'  G -- "No" --> I["Use weak/neutral/full trend scale starting at {params["weakScale"]}"]',
                '  F --> J["Optionally reallocate residual to stronger assets"]',
                '  H --> J',
                '  I --> J',
                '  J --> K(["Final adaptive targets"])',
            ]
        )
    if overlay.kind == "time_series_momentum":
        mode = "reallocate survivors" if _bool(params["reallocateSurvivors"]) else "leave residual in cash"
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough lookback history for asset?"}',
                '  B -- "No" --> C["Keep asset weight"]',
                f'  B -- "Yes" --> D{{"{params["lookbackBars"]}d return > {params["threshold"]}?"}}',
                '  D -- "Yes" --> C',
                '  D -- "No" --> E["Set asset weight to zero"]',
                f'  E --> F["{mode}"]',
                '  F --> G(["Final trend targets"])',
            ]
        )
    return "\n".join(["flowchart TD", '  A(["Custom overlay"]) --> B(["Final targets"])'])


def _mermaid_label(title: str, detail: str) -> str:
    return f"{_escape_mermaid(title)}<br/>{_escape_mermaid(detail)}"


def _escape_mermaid(value: str) -> str:
    return value.replace('"', "'")


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _score_map_param(values: dict[str, Decimal]) -> str:
    return ",".join(f"{symbol}:{value}" for symbol, value in sorted(values.items()))


def _parse_score_map(value: str) -> dict[str, Decimal]:
    scores: dict[str, Decimal] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        if ":" in item:
            symbol, score = item.split(":", 1)
        else:
            symbol, score = item.split("=", 1)
        scores[symbol.strip().upper()] = Decimal(score.strip())
    return scores


def _parse_int_map(value: str) -> dict[str, int]:
    if not value.strip():
        return {}
    parsed = json.loads(value)
    return {str(key): int(item) for key, item in parsed.items()}
